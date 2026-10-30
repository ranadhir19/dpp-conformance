from dpp_conformance.tables import extract, parse_html_table

TWO_TIER = """
<table>
  <tr> <th></th> <th colspan="2">2023</th> <th>2024</th> </tr>
  <tr> <th>Item</th> <th>Q1</th> <th>Q2</th> <th>Q1</th> </tr>
  <tr> <td data-level="0">Sales</td> <td>3.8 %</td> <td>4.0 %</td> <td>10.0 %</td> </tr>
</table>
"""


def test_span_expansion():
    g = parse_html_table(TWO_TIER)
    assert (g.n_rows, g.n_cols) == (3, 4)
    # The "2023" header spans Q1 and Q2: same origin in both positions.
    assert g.texts[0][1] == g.texts[0][2] == "2023"
    assert g.origins[0][1] == g.origins[0][2]
    assert g.origins[0][1] != g.origins[0][3]
    assert g.headers[0][1] and g.headers[1][0]
    assert not g.headers[2][0]
    assert g.levels[2][0] == 0


def test_thead_tbody_wrappers_transparent():
    wrapped = TWO_TIER.replace("<table>", "<table><thead>", 1)
    wrapped = wrapped.replace(
        '<tr> <td data-level="0">', '</thead><tbody><tr> <td data-level="0">', 1)
    wrapped = wrapped.replace("</table>", "</tbody></table>", 1)
    g1, g2 = parse_html_table(TWO_TIER), parse_html_table(wrapped)
    assert (g1.texts, g1.headers, g1.origins) == (g2.texts, g2.headers, g2.origins)


def test_rowspan_expansion():
    g = parse_html_table(
        "<table><tr><td rowspan='2'>6</td><td>Material</td></tr>"
        "<tr><td>Structure</td></tr></table>")
    assert (g.n_rows, g.n_cols) == (2, 2)
    assert g.texts[1][0] == "6"
    assert g.origins[0][0] == g.origins[1][0]


def test_blank_spacer_rows_dropped_but_blank_columns_kept():
    g = parse_html_table(
        "<table><tr><th>A</th><th>Bidder's Response</th></tr>"
        "<tr><td>1</td><td> </td></tr>"
        "<tr><td> </td><td> </td></tr>"
        "<tr><td>2</td><td> </td></tr></table>")
    assert g.n_rows == 3  # the all-blank spacer row is gone
    assert g.n_cols == 2  # the all-blank body column is NOT dropped


def test_pipe_table_parsed_with_header():
    doc = extract("| Item | Q1 |\n| --- | --- |\n| Sales | 3.8 |\n")
    assert len(doc.tables) == 1
    g = doc.tables[0]
    assert (g.n_rows, g.n_cols) == (2, 2)
    assert g.headers[0] == (True, True)
    assert g.texts[1][1] == "3.8"


def test_extract_splits_tables_and_lines():
    doc = extract("# Title\n\nsome prose\n\n" + TWO_TIER + "\ntrailing line\n")
    assert len(doc.tables) == 1
    assert any("some prose" in ln for ln in doc.text_lines)
    assert any("trailing line" in ln for ln in doc.text_lines)
