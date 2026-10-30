# Attribution

**dpp-conformance** is an independent project by Ranadhir Ghosh. It is not
affiliated with or endorsed by LlamaIndex.

The conformance targets come from the **Document Parsing Protocol (DPP)**,
draft 0.1, by **LlamaIndex**:

- Repository: https://github.com/run-llama/document_parsing_protocol
  (commit a9c49e24f6db653500cf7eab4b08019f23b74ea6)
- Site: https://parseprotocol.com
- Launch post: https://www.llamaindex.ai/blog/introducing-the-document-parsing-protocol

Licences, per the DPP repository's own `LICENSE`, `LICENSE-docs` and
`NOTICE` files:

- DPP **code** is MIT-licensed. This project does not copy DPP code; the
  checker is an original implementation of the protocol's conformance
  model.
- The **protocol text and its examples** are **CC BY 4.0** — "use, adapt
  and build on it, including commercially, with credit to 'Document
  Parsing Protocol, LlamaIndex'". Under that licence this repository
  includes:
  - `data/corpus.json` — the 365 expected outputs extracted mechanically
    from the protocol's rule files (extraction code in
    `src/dpp_conformance/corpus.py`), with rule ids, titles and source
    file paths preserved per sample;
  - `tests/fixtures/mini-protocol/` — three rule files copied verbatim
    for offline tests;
  - `examples/*/expected.md` — three expected outputs, verbatim.
- The three page images in `examples/` were selected using DPP's own
  `resources/convention-library/publication-provenance.json`: each is
  recorded there as **constructed** material (CC0 per DPP's `NOTICE`):
  - `examples/tables-multi-row-header-tiers/page.png` (`zoo-5lineperrow.png`)
  - `examples/forms-checklists/page.png` (`bag-insurance-checklist.png`)
  - `examples/charts-bars-and-histograms/page.png` (`chart-premium-hist.png`)
- The remaining 300+ DPP sample page images are **not** redistributed
  here; run the extractor and the parser arms against your own checkout
  of the DPP repository (see README, "Reproducing the benchmark").

The LlamaIndex name and logos are trademarks of LlamaIndex and are not
covered by either licence; they are used here only to identify the
protocol this checker grades against.

This project's own code is MIT-licensed (see `LICENSE`).
