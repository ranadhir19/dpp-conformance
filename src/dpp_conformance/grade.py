"""Grade a candidate output against a DPP sample's expected output.

Grading follows the protocol's own conformance language (DPP draft 0.1,
"Conformance"): a violated MUST is an error and makes the output
non-conforming *for that sample*; accepted alternative forms must be treated
as equal (they are canonicalised away in :mod:`normalize` and
:mod:`tables` before comparison).

A sample is graded on named components. Gating components decide PASS/FAIL;
the rest are reported as findings. For *complete* samples the gating
components are exact: table structure (dimensions, header pattern, span
structure) and table content (every cell, verbatim after canonicalisation)
and text content (every expected non-table line preserved). For *partial*
samples (excerpts / elided expected outputs) exact structure cannot be
demanded, so gating falls back to preservation: every expected cell text and
text line must survive in the candidate.

Special DPP markers (``[blank]``, ``[x]``, ``[ ]``, ``[illegible]``) are
counted over the whole document: producing fewer of them than the expected
output is an error (a dropped ``[blank]`` is exactly the failure DPP's forms
rules exist to catch). Producing more is reported, not gated, in v1.

Numbers are compared as exact printed tokens: ``4.1`` != ``4.10`` != ``4.2``.
DPP: "Printed values are copied exactly."
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .normalize import canon_line, tokens
from .tables import Grid, extract

MARKERS = ("[blank]", "[x]", "[ ]", "[illegible]")


@dataclass
class Component:
    name: str
    passed: bool | None  # None = not applicable
    gating: bool
    detail: str = ""


@dataclass
class GradeResult:
    passed: bool
    components: list[Component] = field(default_factory=list)
    first_diff: str = ""

    def component(self, name: str) -> Component | None:
        for c in self.components:
            if c.name == name:
                return c
        return None

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "first_diff": self.first_diff,
            "components": [
                {"name": c.name, "passed": c.passed, "gating": c.gating,
                 "detail": c.detail}
                for c in self.components
            ],
        }


def _plain_text(md_tables, text_lines) -> str:
    """Whole-document canonical plain text: lines plus table cell texts."""
    parts = [canon_line(ln) for ln in text_lines]
    for g in md_tables:
        for row in g.texts:
            parts.extend(row)
    return " ".join(p for p in parts if p)


def _expected_text_lines(text_lines: list[str]) -> list[str]:
    out = []
    for ln in text_lines:
        s = ln.strip()
        if not s or s.startswith("<!--"):
            continue
        c = canon_line(ln)
        if c:
            out.append(c)
    return out


def _best_table_pair(exp: Grid, candidates: list[Grid]) -> tuple[Grid | None, float]:
    """Pick the candidate table that best matches the expected grid."""
    best, best_key = None, None
    for cand in candidates:
        if cand.n_rows == exp.n_rows and cand.n_cols == exp.n_cols:
            match = sum(
                1
                for r in range(exp.n_rows)
                for c in range(exp.n_cols)
                if cand.texts[r][c] == exp.texts[r][c]
            )
            key = (1, match)
        else:
            shared = len(set(exp.cell_texts_multiset()) & set(cand.cell_texts_multiset()))
            key = (0, shared)
        if best_key is None or key > best_key:
            best, best_key = cand, key
    frac = 0.0
    if best is not None and best.n_rows == exp.n_rows and best.n_cols == exp.n_cols and exp.n_rows:
        total = exp.n_rows * exp.n_cols
        frac = sum(
            1
            for r in range(exp.n_rows)
            for c in range(exp.n_cols)
            if best.texts[r][c] == exp.texts[r][c]
        ) / total
    return best, frac


def _first_cell_diff(exp: Grid, cand: Grid) -> str:
    for r in range(exp.n_rows):
        for c in range(exp.n_cols):
            if cand.texts[r][c] != exp.texts[r][c]:
                return f"cell ({r},{c}): expected {exp.texts[r][c]!r}, got {cand.texts[r][c]!r}"
    return ""


def grade(expected_md: str, candidate_md: str, family: str = "",
          partial: bool = False) -> GradeResult:
    exp = extract(expected_md)
    cand = extract(candidate_md)
    comps: list[Component] = []

    # ---- table components -------------------------------------------------
    if exp.tables:
        comps.append(Component(
            "table_present", bool(cand.tables), True,
            "" if cand.tables else "expected a table; candidate has none"))
        if cand.tables:
            for i, et in enumerate(exp.tables):
                ct, frac = _best_table_pair(et, cand.tables)
                suffix = f"_{i}" if len(exp.tables) > 1 else ""
                if ct is None:
                    continue
                dims_ok = (ct.n_rows, ct.n_cols) == (et.n_rows, et.n_cols)
                if dims_ok:
                    struct_ok = ct.headers == et.headers and ct.origins == et.origins \
                        and ct.levels == et.levels
                    struct_detail = "" if struct_ok else (
                        "header pattern or span structure differs "
                        f"(headers equal: {ct.headers == et.headers}, "
                        f"spans equal: {ct.origins == et.origins}, "
                        f"levels equal: {ct.levels == et.levels})")
                    caption_ok = ct.caption == et.caption
                    content_ok = frac == 1.0 and caption_ok
                    content_detail = "" if content_ok else (
                        _first_cell_diff(et, ct) if frac < 1.0 else
                        f"caption differs: expected {et.caption!r}, got {ct.caption!r}")
                else:
                    struct_ok = False
                    struct_detail = (f"grid dimensions differ: expected "
                                     f"{et.n_rows}x{et.n_cols}, got {ct.n_rows}x{ct.n_cols}")
                    content_ok = False
                    content_detail = struct_detail
                comps.append(Component(f"table_structure{suffix}", struct_ok,
                                       not partial, struct_detail))
                comps.append(Component(f"table_content{suffix}", content_ok,
                                       not partial, content_detail))
                # Preservation fallback (gating for partial samples):
                exp_cells = Counter(et.cell_texts_multiset())
                cand_cells = Counter(ct.cell_texts_multiset())
                missing = exp_cells - cand_cells
                comps.append(Component(
                    f"table_cell_recall{suffix}", not missing, partial,
                    "" if not missing else
                    f"{sum(missing.values())} expected cell(s) missing, e.g. "
                    f"{next(iter(missing))!r}"))
                if family == "charts":
                    chart_ok = (ct.source == "chart") if et.source == "chart" else None
                    comps.append(Component(
                        f"chart_annotation{suffix}", chart_ok, False,
                        "" if chart_ok else
                        "expected a chart-sourced table (data-source=\"chart\")"))
    # ---- text content ------------------------------------------------------
    exp_lines = _expected_text_lines(exp.text_lines)
    if exp_lines:
        cand_plain = _plain_text(cand.tables, cand.text_lines)
        cand_tokens = Counter(tokens(cand_plain))
        bad_line, missing_toks = "", []
        for ln in exp_lines:
            if ln in cand_plain:
                continue
            need = Counter(tokens(ln))
            missing = need - cand_tokens
            if missing:
                bad_line, missing_toks = ln, sorted(missing.elements())
                break
        comps.append(Component(
            "text_content", not bad_line, True,
            "" if not bad_line else
            f"line not preserved: {bad_line!r}; missing tokens: {missing_toks[:6]}"))
    # ---- DPP markers --------------------------------------------------------
    exp_counts = {m: expected_md.count(m) for m in MARKERS}
    cand_counts = {m: candidate_md.count(m) for m in MARKERS}
    short = {m: (exp_counts[m], cand_counts[m]) for m in MARKERS
             if cand_counts[m] < exp_counts[m]}
    comps.append(Component(
        "markers", not short, True,
        "" if not short else
        "; ".join(f"{m}: expected {e}, got {c}" for m, (e, c) in short.items())))

    gating = [c for c in comps if c.gating and c.passed is not None]
    passed = all(c.passed for c in gating)
    first_diff = ""
    for c in comps:
        if c.gating and c.passed is False and c.detail:
            first_diff = f"{c.name}: {c.detail}"
            break
    return GradeResult(passed=passed, components=comps, first_diff=first_diff)
