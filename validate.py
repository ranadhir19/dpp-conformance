#!/usr/bin/env python3
"""Validation harness for dpp-conformance.

Stages (each reported PASS/FAIL; the run fails if any stage fails):
  1. import/compile check of the package;
  2. full test suite (pytest);
  3. bundled-example self-grade: each examples/*/expected.md graded
     against itself must PASS, and against a value-mutated copy must FAIL
     (the checker must be able to fail something);
  4. corpus extraction smoke test on the vendored mini-protocol fixture
     (expected: 9 samples, 3 rules);
  5. results consistency: the conformance figures quoted in README.md
     must match data/results.json exactly (guards stale numbers).

Run: python3 validate.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}


def stage(name: str, ok: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def main() -> int:
    ok = True

    # 1. import / compile
    r = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", str(ROOT / "src")],
        capture_output=True, text=True)
    imp = subprocess.run(
        [sys.executable, "-c", "import dpp_conformance; "
                               "print(dpp_conformance.__version__)"],
        capture_output=True, text=True, env=ENV)
    ok &= stage("import/compile", r.returncode == 0 and imp.returncode == 0,
                imp.stdout.strip() or imp.stderr.strip()[:200])

    # 2. test suite
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q"],
        capture_output=True, text=True, cwd=ROOT, env=ENV)
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    ok &= stage("test suite", r.returncode == 0, tail)

    # 3. bundled examples: identity passes, value mutation fails
    sys.path.insert(0, str(ROOT / "src"))
    from dpp_conformance.grade import grade  # noqa: E402

    ex_ok, ex_detail = True, ""
    for d in sorted((ROOT / "examples").iterdir()):
        exp_file = d / "expected.md"
        if not exp_file.exists():
            continue
        expected = exp_file.read_text(encoding="utf-8")
        fam = d.name.split("-")[0]
        fam = {"tables": "tables", "forms": "forms", "charts": "charts"}.get(fam, fam)
        if not grade(expected, expected, fam).passed:
            ex_ok, ex_detail = False, f"{d.name}: identity grade failed"
            break
        import re
        m = re.search(r"\d", expected)
        if m:  # flip the first digit inside the expected output
            mutated = expected[:m.start()] + ("9" if m.group() != "9" else "7") \
                + expected[m.end():]
            if grade(expected, mutated, fam).passed:
                ex_ok, ex_detail = False, f"{d.name}: mutated grade passed"
                break
    ok &= stage("bundled examples self-grade", ex_ok, ex_detail)

    # 4. corpus extraction smoke test
    from dpp_conformance.corpus import extract_protocol  # noqa: E402

    samples = extract_protocol(ROOT / "tests" / "fixtures" / "mini-protocol")
    ok &= stage("corpus extraction (mini fixture)",
                len(samples) == 9 and len({s.rule_id for s in samples}) == 3,
                f"{len(samples)} samples")

    # 5. README numbers match data/results.json
    results_path = ROOT / "data" / "results.json"
    if results_path.exists():
        results = json.loads(results_path.read_text(encoding="utf-8"))
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        missing = []
        for arm, blob in results.get("arms", {}).items():
            o = blob["summary"]["overall"]
            needle = f"{o['passed']}/{o['n']} ({o['rate'] * 100:.1f}%)"
            if needle not in readme:
                missing.append(f"{arm}: {needle}")
        ok &= stage("README results consistency", not missing,
                    "; ".join(missing))
    else:
        ok &= stage("README results consistency", False, "data/results.json missing")

    print("\nOVERALL:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
