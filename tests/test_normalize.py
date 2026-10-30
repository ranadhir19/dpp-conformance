from dpp_conformance.normalize import canon_cell, canon_line, canon_text


def test_html_entities_decoded():
    assert canon_text("Fish &amp; Chips") == "Fish & Chips"


def test_visually_identical_characters_equivalent():
    # DPP "Accepted Alternatives": these pairs never count as a difference.
    assert canon_text("µ") == canon_text("μ")  # micro sign == Greek mu
    assert canon_text("a‑b") == "a-b"  # non-breaking hyphen
    assert canon_text("−5") == "-5"  # minus sign
    assert canon_text("3–4") == "3-4"  # en dash
    assert canon_text("a b") == "a b"  # non-breaking space


def test_whitespace_collapsed_case_preserved():
    assert canon_text("  Total \n  Weight ") == "Total Weight"
    assert canon_text("FAX (A/C, No)") == "FAX (A/C, No)"


def test_cell_markup_stripped_br_is_space():
    assert canon_cell("<strong>90</strong>") == "90"
    assert canon_cell("ISO/IEC11801<br/>EN50399") == "ISO/IEC11801 EN50399"
    assert canon_cell("<em>Fiscal year</em>") == "Fiscal year"


def test_line_heading_markers_stripped():
    assert canon_line("### [Part I] Information") == "[Part I] Information"
