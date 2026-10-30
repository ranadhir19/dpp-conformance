"""Command-line interface for dpp-conformance.

Commands:
  extract   Build the sample corpus JSON from a DPP protocol checkout.
  grade     Grade one candidate file against one expected file.
  selftest  Grade every corpus sample's expected output against itself
            (a checker that cannot pass the answer key is broken).
  run       Run parser arms over a deterministic subset of the corpus
            and write measured conformance results as JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .corpus import (Sample, extract_protocol, find_image, samples_from_json,
                     samples_to_json)
from .grade import grade
from .report import aggregate, render_text

# Per-family caps for the parser-run subset (complete samples only).
DEFAULT_CAPS = {
    "tables": 20, "charts": 14, "forms": 8, "headings": 8, "layout": 8,
    "text": 6, "document": 3, "images-diagrams": 4, "lists": 2,
}


def select_subset(samples: list[Sample], caps: dict[str, int]) -> list[Sample]:
    """Deterministic stratified subset: complete samples with an image.

    Within each family, samples are sorted by (rule_id, sample_name) and
    picked at evenly spaced positions up to the family cap. No randomness:
    the same corpus always yields the same subset.
    """
    eligible = [s for s in samples if s.image and not s.partial]
    chosen: list[Sample] = []
    families = sorted({s.family for s in eligible})
    for fam in families:
        group = sorted((s for s in eligible if s.family == fam),
                       key=lambda s: (s.rule_id, s.sample_name))
        cap = caps.get(fam, 4)
        if len(group) <= cap:
            chosen.extend(group)
        else:
            step = len(group) / cap
            chosen.extend(group[int(i * step)] for i in range(cap))
    return chosen


def cmd_extract(args) -> int:
    samples = extract_protocol(args.protocol)
    Path(args.out).write_text(samples_to_json(samples), encoding="utf-8")
    n_rules = len({s.rule_id for s in samples})
    print(f"extracted {len(samples)} samples from {n_rules} rules "
          f"-> {args.out}")
    return 0


def cmd_grade(args) -> int:
    expected = Path(args.expected).read_text(encoding="utf-8")
    candidate = Path(args.candidate).read_text(encoding="utf-8")
    r = grade(expected, candidate, family=args.family or "", partial=args.partial)
    print(json.dumps(r.to_dict(), indent=1))
    return 0 if r.passed else 1


def cmd_selftest(args) -> int:
    samples = samples_from_json(Path(args.corpus).read_text(encoding="utf-8"))
    results = [(s, grade(s.expected, s.expected, s.family, s.partial))
               for s in samples]
    summary = aggregate(samples, results)
    print(render_text(summary, results, "Self-test: expected vs expected"))
    return 0 if summary["overall"]["rate"] == 1.0 else 1


def _write_with_retry(path: Path, text: str, attempts: int = 300) -> None:
    """Write a file, retrying transient permission errors.

    Some sandboxes intermittently deny writes for seconds at a time; a
    benchmark that computed for an hour must not die on its final write.
    """
    import time

    last: Exception | None = None
    for _ in range(attempts):
        try:
            path.write_text(text, encoding="utf-8")
            return
        except PermissionError as e:
            last = e
            time.sleep(2)
    assert last is not None
    raise last


def _parse_with_timeout(arm: str, image: str, work_dir: Path,
                        timeout: int) -> tuple[str, str | None]:
    """Run one parse in a subprocess so a hung or crashing parser is a
    recorded failed parse, never a stalled benchmark.

    The worker reports through files, never pipes: ML parsers spawn
    grandchildren that inherit pipe ends and can hold a capturing
    parent open forever. The worker runs in its own session so a
    timeout can kill the whole process group.
    """
    import os
    import signal
    import subprocess

    tmp_out = work_dir / "parse-worker-out.md"
    tmp_err = work_dir / "parse-worker-err.txt"
    err_fh = None
    for _ in range(600):  # tolerate transient write denials in the sandbox
        try:
            err_fh = open(tmp_err, "w", encoding="utf-8")
            break
        except PermissionError:
            import time
            time.sleep(2)
    if err_fh is None:
        return "", "parse failed: could not open worker error log"
    before_ns = tmp_out.stat().st_mtime_ns if tmp_out.exists() else -1
    with err_fh:
        proc = subprocess.Popen(
            [sys.executable, "-m", "dpp_conformance.parse_worker",
             arm, image, str(tmp_out)],
            stdout=subprocess.DEVNULL, stderr=err_fh,
            start_new_session=True)
        try:
            returncode = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            return "", f"parse timed out after {timeout}s"
    # The output file is the contract, not the exit code: a worker that
    # delivered its Markdown has succeeded even if interpreter shutdown
    # poisons its exit status (observed: exit 120 when the worker's
    # stderr stream fails to flush at exit).
    if tmp_out.exists() and tmp_out.stat().st_mtime_ns > before_ns:
        text = tmp_out.read_text(encoding="utf-8")
        try:
            tmp_out.unlink()
        except PermissionError:
            pass  # the next worker truncates it anyway
        return text, None
    if returncode != 0:
        tail = tmp_err.read_text(encoding="utf-8").strip().splitlines()
        detail = tail[-1] if tail else f"exit code {returncode}"
        return "", f"parse failed: {detail}"
    return "", "parse failed: worker produced no output"


def cmd_run(args) -> int:
    samples = samples_from_json(Path(args.corpus).read_text(encoding="utf-8"))
    subset = select_subset(samples, DEFAULT_CAPS)
    cache_dir = Path(args.cache)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out: dict = {"subset": {"size": len(subset),
                            "caps": DEFAULT_CAPS,
                            "rule": "complete samples with image, evenly "
                                    "spaced per family"},
                 "arms": {}}
    for arm in args.arms:
        results = []
        per_sample = []
        for s in subset:
            image = find_image(args.protocol, s.image) if s.image else None
            if image is None:
                per_sample.append({"sample": s.sample_id, "error": "image not found"})
                continue
            import hashlib
            digest = hashlib.md5(s.sample_id.encode()).hexdigest()[:10]
            cache_file = cache_dir / f"{arm}--{s.rule_id}--{digest}.md"
            if cache_file.exists() and not args.no_cache:
                candidate = cache_file.read_text(encoding="utf-8")
                error = None
            else:
                candidate, error = _parse_with_timeout(
                    arm, str(image), cache_dir, args.parse_timeout)
                if error is None:
                    try:
                        _write_with_retry(cache_file, candidate)
                    except PermissionError:
                        pass  # caching is an optimisation; grade anyway
            r = grade(s.expected, candidate, s.family, s.partial)
            results.append((s, r))
            per_sample.append({"sample": s.sample_id, "family": s.family,
                               "passed": r.passed, "first_diff": r.first_diff,
                               "error": error})
        summary = aggregate(subset, results)
        out["arms"][arm] = {"summary": summary, "samples": per_sample}
        print(render_text(summary, results, f"Arm: {arm}"))
    _write_with_retry(Path(args.out), json.dumps(out, indent=1))
    print(f"wrote {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dpp-conformance")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("extract")
    p.add_argument("--protocol", required=True, help="DPP protocol/ directory")
    p.add_argument("--out", default="data/corpus.json")
    p.set_defaults(fn=cmd_extract)

    p = sub.add_parser("grade")
    p.add_argument("--expected", required=True)
    p.add_argument("--candidate", required=True)
    p.add_argument("--family", default="")
    p.add_argument("--partial", action="store_true")
    p.set_defaults(fn=cmd_grade)

    p = sub.add_parser("selftest")
    p.add_argument("--corpus", default="data/corpus.json")
    p.set_defaults(fn=cmd_selftest)

    p = sub.add_parser("run")
    p.add_argument("--corpus", default="data/corpus.json")
    p.add_argument("--protocol", required=True, help="DPP protocol/ directory (for images)")
    p.add_argument("--arms", nargs="+", default=["pymupdf-text"])
    p.add_argument("--parse-timeout", type=int, default=1200,
                   help="per-page parse timeout in seconds (default 1200)")
    p.add_argument("--cache", default="data/parse-cache")
    p.add_argument("--out", default="data/results.json")
    p.add_argument("--no-cache", action="store_true")
    p.set_defaults(fn=cmd_run)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
