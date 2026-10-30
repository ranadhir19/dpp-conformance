# How conformance is judged

This checker grades a candidate Markdown output against the expected
output DPP publishes for one sample page. The model follows DPP's own
"Conformance" chapter (draft 0.1): a violated MUST is an error and makes
the output non-conforming *for that sample*; forms the protocol accepts
as alternatives MUST be treated as equal by a checker.

## What is compared

Both documents are decomposed into **tables** and **text lines**:

- HTML tables and Markdown pipe tables are parsed into a fully expanded
  grid (rowspan/colspan resolved). Every grid position knows its text,
  whether it came from a `<th>`, its `data-level`, and which source cell
  it belongs to.
- The remaining lines are compared as text.

Before comparison, both sides are canonicalised (see
`src/dpp_conformance/normalize.py`):

- HTML entities decoded; whitespace collapsed;
- DPP's visually-identical characters unified (micro sign ≡ Greek mu,
  non-breaking hyphen / minus sign / en & figure dashes ≡ hyphen-minus,
  non-breaking space ≡ space);
- inline emphasis markup stripped (`<strong>`, `<b>`, `<em>`, `<i>`,
  `**`, `*`): emphasis is styling, not content;
- case is *not* folded — DPP requires labels to keep their printed
  capitalisation.

And in tables:

- `thead`/`tbody`/`tfoot` wrappers are transparent (DPP equivalence);
- purely blank spacer rows are dropped from both grids — presence ≡
  absence (DPP equivalence). Columns are never dropped: an all-blank
  column proven by its header must be kept.

## Components

| Component | Gating | What it checks |
| --- | --- | --- |
| `table_present` | yes | a table exists when the expected output has one |
| `table_structure` | complete samples | grid dimensions, per-cell header pattern, span structure (expanded origin pattern), `data-level`s — all equal |
| `table_content` | complete samples | every expanded cell's text equal, verbatim after canonicalisation; table caption equal |
| `table_cell_recall` | partial samples | every expected source cell's text survives in the candidate (multiset inclusion) |
| `text_content` | yes | every expected non-table line is preserved: as a substring of the candidate's plain text, or with all of its tokens present |
| `markers` | yes | candidate contains at least as many `[blank]`, `[x]`, `[ ]`, `[illegible]` markers as the expected output |
| `chart_annotation` | no (finding) | chart tables carry `data-source="chart"` |

A sample **passes** iff every applicable gating component passes. The
report names the first failing component and the differing fragment
(e.g. `table_content: cell (2,7): expected '4.1 %', got '4.2 %'`).

## Complete vs partial samples

About 57% of DPP's published samples are *partial*: the expected output
is labelled an excerpt, or elides content with `<!-- … -->`. An excerpt
cannot prove a parser wrong about structure it never shows, so partial
samples gate on **preservation** (cell recall + text + markers) and
report structure/content as findings. The parser benchmark in the
README uses complete samples only.

## Deliberate strictness, and known limits

- **Values are exact.** `4.1` ≠ `4.10` ≠ `4.2`. DPP: "Printed values are
  copied exactly." (DPP's chart chapter discusses tolerances for values
  read off axes; v1 of this checker grades the printed-value samples,
  where no tolerance applies, and does not implement axis-read
  tolerances.)
- **Producing extra content is reported, not gated**, in v1 — except
  where it changes a grid (an invented header label changes the header
  pattern or a cell, and fails `table_structure`/`table_content`).
  Whole-document grading of full pages (rather than sample regions) is
  future work.
- **One form per document** ("Choices Made Once Per Document") is a
  document-level DPP rule; per-sample grading cannot see it. Not judged.
- **`data-level` stub hierarchy** is compared as part of structure;
  parsers that flatten stub indentation lose those cells' levels and
  fail structure even when every word is right. That is DPP's position,
  not an accident of this checker.
- Sidecar/bounding-box options are out of scope for v1.
