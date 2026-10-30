# dpp-conformance

A conformance checker for the **Document Parsing Protocol (DPP)** — the
"answer key" for document parsing published by LlamaIndex as working
draft 0.1 (140 rules, each with example pages and the output it expects).

Parsers disagree about what a correctly parsed page even is: flatten a
two-row table header and every word survives while the meaning changes.
DPP writes the rules down. This project grades real parsers against
them: it extracts DPP's published samples, runs parsers over the sample
pages, and scores each output **rule by rule** — applying DPP's own
accepted-alternative equivalences, and failing near-misses (a flattened
header, a dropped `[blank]`, an approximated chart value) on the specific
component that names the violation.

> DPP is LlamaIndex's work, not this project's. Credit, licences and
> what material is included here and why: [ATTRIBUTION.md](ATTRIBUTION.md).

## Measured results

Benchmark: the deterministic subset of DPP samples defined in
`data/results.json` (complete samples with a page image, evenly spaced
per family; 71 samples). Each parser ran on this machine (2 CPU, no GPU)
over the sample page images; outputs were graded by this checker.
Grading rules: [docs/JUDGING.md](docs/JUDGING.md).

| Parser | Conforming samples | Tables | Forms | Charts | Headings | Layout | Text | Document | Images/diagrams |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pymupdf-text | 0/71 (0.0%) | 0/20 (0.0%) | 0/8 (0.0%) | 0/14 (0.0%) | 0/8 (0.0%) | 0/8 (0.0%) | 0/6 (0.0%) | 0/3 (0.0%) | 0/4 (0.0%) |
| docling | 1/71 (1.4%) | 0/20 (0.0%) | 0/8 (0.0%) | 0/14 (0.0%) | 1/8 (12.5%) | 0/8 (0.0%) | 0/6 (0.0%) | 0/3 (0.0%) | 0/4 (0.0%) |

What the numbers mean — and do not mean:

- DPP conformance is deliberately strict: values must be copied
  exactly, headers kept as printed, blanks marked. A parser can extract
  text well and still conform on few samples. The per-component
  failures in `data/results.json` show *where* each parser diverges
  (structure vs values vs markers), which is the useful part.
- The `pymupdf-text` arm reads a PDF text layer. DPP sample pages are
  rendered images, so it scores zero — DPP's own Conformance chapter
  says outputs are judged "against the document as rendered … never
  against the file's text layer"; this arm exists to price that
  sentence.
- Docling is the substantive arm: a real open-source layout+OCR+table
  pipeline, run on CPU with default settings.

## What DPP publishes, and what this checker can grade

Measured from the DPP repository at commit
`a9c49e24f6db653500cf7eab4b08019f23b74ea6` (2026-10-29):

- **141** rule files carry a `rule_id` (the protocol's "140 rules" plus
  front-matter-bearing auxiliaries); **99 rules** ship at least one
  machine-usable sample (a page image plus an "Expected Markdown"
  block); **365 samples** in total.
- **159** of the 365 samples are *complete* (the expected output is the
  whole region); the other 206 are excerpts or elided with
  `<!-- … -->`, and can verify preservation but not full structure.
- Samples by family: tables 178, text 42, charts 38, headings 37,
  layout 29, forms 28, document 6, images-and-diagrams 5, lists 2.
  The lists family's two samples are both partial, so no complete
  lists sample exists to benchmark against.

So v1 coverage is: **every published DPP sample, graded** — but the
protocol rules without samples (42 of 141) can only be read, not
machine-graded, and rules whose samples are all partial are graded on
preservation only. The checker also verifies itself against the full
answer key: grading every expected output against itself passes
365/365 (run `dpp-conformance selftest`).

## How conformance is judged

Both outputs are decomposed into tables (HTML or pipe tables, expanded
to full grids with spans resolved) and text lines, canonicalised with
DPP's own equivalences (visually identical characters; `thead`/`tbody`
transparency; blank spacer rows ≡ absent), then compared component by
component: table structure (dimensions, header pattern, span structure,
`data-level`s), table content (every cell verbatim; values exact —
`4.1` ≠ `4.10`), text content, and DPP markers (`[blank]`, `[x]`,
`[ ]`, `[illegible]`). Full detail, including deliberate strictness and
known limits: [docs/JUDGING.md](docs/JUDGING.md).

## Install and use

```bash
pip install .                # checker only (no parser dependencies)
pip install ".[parsers]"     # + PyMuPDF and Docling for the parser arms
```

Grade one output against one DPP expected output:

```bash
dpp-conformance grade --expected examples/tables-multi-row-header-tiers/expected.md \
                      --candidate my-parser-output.md --family tables
# prints a JSON verdict: passed, per-component results, first difference
```

## Reproducing the benchmark

```bash
git clone https://github.com/run-llama/document_parsing_protocol
dpp-conformance extract --protocol document_parsing_protocol/protocol \
                        --out data/corpus.json
dpp-conformance selftest --corpus data/corpus.json
dpp-conformance run --protocol document_parsing_protocol/protocol \
                    --corpus data/corpus.json \
                    --arms pymupdf-text docling --out data/results.json
```

Parser outputs are cached under `data/parse-cache/` so re-grading is
fast and the exact outputs behind the table above can be inspected.

## Limitations

- v1 grades sample regions, not whole documents; document-level DPP
  rules ("one form per document", cross-page table continuation) are
  out of scope.
- Extra content a parser adds is reported but not gated, except where
  it changes a table grid or a marker count.
- Chart values are graded exactly as printed; DPP's tolerances for
  values *read off axes* are not implemented.
- The sidecar (bounding boxes / element positions) is not graded.
- Four subset samples are SVG pages. Neither bundled arm can open SVG
  in v1 (the PyMuPDF arm's image loader cannot identify the format;
  Docling rejects it as not allowed), so those four appear in
  `data/results.json` as parse errors for both arms, not as grades.
- Docling results are for its default CPU pipeline at the version
  recorded in BUILD_REPORT.md; other parsers (e.g. Marker) were not
  run — see BUILD_REPORT.md for what was attempted.

## Licence

This project's code: MIT (`LICENSE`). DPP protocol text and examples:
CC BY 4.0, credit "Document Parsing Protocol, LlamaIndex"; the three
bundled example page images are DPP constructed examples (CC0). See
[ATTRIBUTION.md](ATTRIBUTION.md).
