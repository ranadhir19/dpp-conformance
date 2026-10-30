"""Grading tests, built around the user's validation protocol:

* a known-conforming output MUST pass (including DPP's accepted
  alternative forms, which the protocol says a checker MUST treat as equal);
* near-miss negatives MUST fail, and must fail on the specific component
  that names the violated rule — a checker that passes everything, or
  fails everything for the wrong reason, is a defect.

The table fixture is the two-tier header case from the DPP launch post
(LlamaIndex blog, 2026-10-29), reduced to two data rows.
"""

from dpp_conformance.grade import grade

EXPECTED_TABLE = """
<table>
  <tr> <th></th> <th colspan="5">2023</th> <th colspan="3">2024</th> </tr>
  <tr> <th><em>Fiscal year ending December,</em></th> <th>Q1</th> <th>Q2</th> <th>Q3</th> <th>Q4</th> <th>FY</th> <th>Q1</th> <th>Q2</th> <th>Q3</th> </tr>
  <tr> <td data-level="0"><strong>Systemwide Same Shop Sales</strong></td> <td><strong>(2.0)%</strong></td> <td><strong>3.8 %</strong></td> <td><strong>4.0 %</strong></td> <td><strong>5.0 %</strong></td> <td><strong>2.8 %</strong></td> <td><strong>10.0 %</strong></td> <td><strong>4.1 %</strong></td> <td><strong>2.7 %</strong></td> </tr>
  <tr> <td data-level="1">Ticket</td> <td>6.3 %</td> <td>6.4 %</td> <td>9.5 %</td> <td>5.4 %</td> <td>7.2 %</td> <td>8.8 %</td> <td>6.1 %</td> <td>1.9 %</td> </tr>
</table>
"""

EXPECTED_FORM = """### \\[Part I\\] Information About the Partnership

- \\[A\\] **Partnership's employer identification number**: 27-4162308
- \\[D\\] **Check if this is a publicly traded partnership (PTP)**: [ ]
- **CONTACT NAME:** Melinda Clayton
- **FAX (A/C, No):** [blank]
- **Paid preparer:** [x]
"""

EXPECTED_CHART = """
<table data-source="chart">
  <caption><strong>Figure 7. Average monthly usage</strong></caption>
  <tr> <th></th> <th>Car sharing</th> <th>Ride hailing</th> </tr>
  <tr> <td>Global</td> <td>2.9</td> <td>3.5</td> </tr>
  <tr> <td>SEA</td> <td>3.6</td> <td>4.4</td> </tr>
</table>
"""


# ---- known-conforming outputs pass -------------------------------------

def test_identity_passes():
    assert grade(EXPECTED_TABLE, EXPECTED_TABLE, "tables").passed
    assert grade(EXPECTED_FORM, EXPECTED_FORM, "forms").passed
    assert grade(EXPECTED_CHART, EXPECTED_CHART, "charts").passed


def test_thead_tbody_equivalence_passes():
    wrapped = EXPECTED_TABLE.replace("<table>", "<table><thead>", 1)
    wrapped = wrapped.replace('<tr> <td data-level="0">',
                              '</thead><tbody><tr> <td data-level="0">', 1)
    wrapped = wrapped.replace("</table>", "</tbody></table>", 1)
    assert grade(EXPECTED_TABLE, wrapped, "tables").passed


def test_emphasis_style_swap_passes():
    variant = EXPECTED_TABLE.replace("<strong>", "<b>").replace("</strong>", "</b>")
    variant = variant.replace("<em>", "<i>").replace("</em>", "</i>")
    assert grade(EXPECTED_TABLE, variant, "tables").passed


def test_extra_blank_spacer_row_passes():
    variant = EXPECTED_TABLE.replace(
        '<tr> <td data-level="1">',
        '<tr> <td> </td> <td> </td> <td> </td> <td> </td> <td> </td> '
        '<td> </td> <td> </td> <td> </td> <td> </td> </tr>\n'
        '  <tr> <td data-level="1">', 1)
    assert grade(EXPECTED_TABLE, variant, "tables").passed


# ---- near-miss negatives fail on the named component --------------------

def test_flattened_header_fails_structure():
    """The blog's parser B: years merged into quarter labels ('2024 Q2')."""
    flat = """
| Fiscal year ending December, | 2023 Q1 | 2023 Q2 | 2023 Q3 | 2023 Q4 | 2023 FY | 2024 Q1 | 2024 Q2 | 2024 Q3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Systemwide Same Shop Sales | (2.0)% | 3.8 % | 4.0 % | 5.0 % | 2.8 % | 10.0 % | 4.1 % | 2.7 % |
| Ticket | 6.3 % | 6.4 % | 9.5 % | 5.4 % | 7.2 % | 8.8 % | 6.1 % | 1.9 % |
"""
    r = grade(EXPECTED_TABLE, flat, "tables")
    assert not r.passed
    assert r.component("table_structure").passed is False


def test_quarters_pushed_into_body_fails_structure():
    """The blog's parser A: the quarter row demoted to a body row."""
    demoted = EXPECTED_TABLE.replace(
        "<tr> <th><em>Fiscal year ending December,</em></th>",
        "<tr> <td><em>Fiscal year ending December,</em></td>")
    demoted = demoted.replace("<th>Q1</th>", "<td>Q1</td>").replace(
        "<th>Q2</th>", "<td>Q2</td>").replace("<th>Q3</th>", "<td>Q3</td>")
    demoted = demoted.replace("<th>Q4</th>", "<td>Q4</td>").replace(
        "<th>FY</th>", "<td>FY</td>")
    r = grade(EXPECTED_TABLE, demoted, "tables")
    assert not r.passed
    assert r.component("table_structure").passed is False


def test_dropped_blank_column_fails_structure():
    expected = """
<table>
  <tr> <th>SL No</th> <th>Name of Item</th> <th>Bidder's Response</th> </tr>
  <tr> <td>1</td> <td>Brand</td> <td> </td> </tr>
  <tr> <td>2</td> <td>Model</td> <td> </td> </tr>
</table>
"""
    dropped = """
<table>
  <tr> <th>SL No</th> <th>Name of Item</th> </tr>
  <tr> <td>1</td> <td>Brand</td> </tr>
  <tr> <td>2</td> <td>Model</td> </tr>
</table>
"""
    r = grade(expected, dropped, "tables")
    assert not r.passed
    assert r.component("table_structure").passed is False


def test_invented_corner_label_fails_content():
    variant = EXPECTED_TABLE.replace("<tr> <th></th>", "<tr> <th>Category</th>", 1)
    r = grade(EXPECTED_TABLE, variant, "tables")
    assert not r.passed
    assert r.component("table_content").passed is False
    assert "(0,0)" in r.component("table_content").detail


def test_dropped_blank_marker_fails():
    variant = EXPECTED_FORM.replace("- **FAX (A/C, No):** [blank]\n", "")
    r = grade(EXPECTED_FORM, variant, "forms")
    assert not r.passed
    assert r.component("markers").passed is False


def test_checkbox_state_flip_fails():
    variant = EXPECTED_FORM.replace("**Paid preparer:** [x]",
                                    "**Paid preparer:** [ ]")
    r = grade(EXPECTED_FORM, variant, "forms")
    assert not r.passed


def test_form_value_changed_fails_text_content():
    variant = EXPECTED_FORM.replace("27-4162308", "27-4162309")
    r = grade(EXPECTED_FORM, variant, "forms")
    assert not r.passed
    assert r.component("text_content").passed is False


def test_chart_value_approximated_fails_content():
    variant = EXPECTED_CHART.replace("<td>4.4</td>", "<td>4.5</td>")
    r = grade(EXPECTED_CHART, variant, "charts")
    assert not r.passed
    assert r.component("table_content").passed is False
    assert "4.4" in r.component("table_content").detail


def test_chart_value_reformatted_fails_content():
    """DPP copies printed values exactly: 2.9 is not 2.90."""
    variant = EXPECTED_CHART.replace("<td>2.9</td>", "<td>2.90</td>")
    r = grade(EXPECTED_CHART, variant, "charts")
    assert not r.passed
    assert r.component("table_content").passed is False


def test_missing_table_fails():
    r = grade(EXPECTED_TABLE, "No table here at all.", "tables")
    assert not r.passed
    assert r.component("table_present").passed is False


def test_partial_sample_uses_preservation_not_structure():
    """An excerpt's cells must survive; extra structure is not demanded."""
    expected = EXPECTED_TABLE  # graded as partial here
    superset = EXPECTED_TABLE.replace(
        "</table>",
        "  <tr> <td data-level=\"1\">Average Check</td> <td>1.0 %</td> "
        "<td>1.1 %</td> <td>1.2 %</td> <td>1.3 %</td> <td>1.4 %</td> "
        "<td>1.5 %</td> <td>1.6 %</td> <td>1.7 %</td> </tr>\n</table>")
    r = grade(expected, superset, "tables", partial=True)
    assert r.passed
    r2 = grade(expected, superset, "tables", partial=False)
    assert not r2.passed  # the same pair fails under complete grading
