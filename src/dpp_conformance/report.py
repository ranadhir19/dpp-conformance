"""Aggregate per-sample grades into conformance scores and reports."""

from __future__ import annotations

from collections import defaultdict

from .corpus import Sample
from .grade import GradeResult


def aggregate(samples: list[Sample],
              results: list[tuple[Sample, GradeResult]]) -> dict:
    """Build the summary structure: overall, per-family and per-rule rates."""
    def bucket(items):
        n = len(items)
        passed = sum(1 for _, r in items if r.passed)
        return {"n": n, "passed": passed,
                "rate": (passed / n) if n else None}

    by_family: dict[str, list] = defaultdict(list)
    by_rule: dict[str, list] = defaultdict(list)
    for s, r in results:
        by_family[s.family].append((s, r))
        by_rule[s.rule_id].append((s, r))
    return {
        "overall": bucket(results),
        "by_family": {k: bucket(v) for k, v in sorted(by_family.items())},
        "by_rule": {k: bucket(v) for k, v in sorted(by_rule.items())},
    }


def render_text(summary: dict, results: list[tuple[Sample, GradeResult]],
                title: str = "DPP conformance report") -> str:
    lines = [f"# {title}", ""]
    o = summary["overall"]
    lines.append(f"Overall: {o['passed']}/{o['n']} samples conform "
                 f"({(o['rate'] or 0) * 100:.1f}%)")
    lines.append("")
    lines.append("By family:")
    for fam, b in summary["by_family"].items():
        lines.append(f"  {fam:16s} {b['passed']:3d}/{b['n']:3d}  "
                     f"{(b['rate'] or 0) * 100:5.1f}%")
    lines.append("")
    lines.append("Failures:")
    any_fail = False
    for s, r in results:
        if not r.passed:
            any_fail = True
            lines.append(f"  FAIL {s.sample_id} [{s.family}] {r.first_diff}")
    if not any_fail:
        lines.append("  (none)")
    return "\n".join(lines) + "\n"
