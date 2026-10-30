# Examples

Three complete DPP samples, one each from the tables, forms and charts
families. Each folder holds the sample's page image (`page.png`) and the
output DPP expects for it (`expected.md`). Provenance and licensing: see
the repository's `ATTRIBUTION.md` — the expected outputs are CC BY 4.0
("Document Parsing Protocol, LlamaIndex"); the page images are DPP
"constructed" examples (CC0).

Try the checker on one:

```bash
# Grade the expected output against itself (must pass):
dpp-conformance grade --expected examples/tables-multi-row-header-tiers/expected.md \
                      --candidate examples/tables-multi-row-header-tiers/expected.md \
                      --family tables

# Parse the page with a real parser, then grade the result:
python -c "from dpp_conformance.parsers import docling_parse; \
print(docling_parse('examples/tables-multi-row-header-tiers/page.png'))" > /tmp/out.md
dpp-conformance grade --expected examples/tables-multi-row-header-tiers/expected.md \
                      --candidate /tmp/out.md --family tables
```
