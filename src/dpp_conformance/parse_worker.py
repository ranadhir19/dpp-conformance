"""Single-parse worker, run as a subprocess by the benchmark runner.

Usage: python -m dpp_conformance.parse_worker ARM IMAGE_PATH OUT_PATH

Runs one parser arm over one page image and writes the Markdown output
to OUT_PATH. The benchmark runner executes parses in subprocesses with a
timeout because real parsers can hang or crash on pathological pages
(dense tables are the classic case); a hung parse must be recorded as a
failed parse, not stall the whole benchmark.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: parse_worker ARM IMAGE_PATH OUT_PATH", file=sys.stderr)
        return 2
    arm, image_path, out_path = argv
    from .parsers import run_arm

    markdown = run_arm(arm, image_path)
    # Retry the delivery write: a parse that took minutes must not be
    # lost to a transient filesystem write denial.
    import time

    for attempt in range(600):
        try:
            Path(out_path).write_text(markdown, encoding="utf-8")
            break
        except PermissionError:
            if attempt == 599:
                raise
            time.sleep(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
