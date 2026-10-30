from pathlib import Path

from dpp_conformance.corpus import extract_protocol

MINI = Path(__file__).parent / "fixtures" / "mini-protocol"


def test_mini_protocol_extraction():
    samples = extract_protocol(MINI)
    # 3 rule files vendored from DPP draft 0.1 (see fixtures ATTRIBUTION):
    # Multi-Row Header Tiers (7), chart Labels (1), Checkboxes (1).
    assert len(samples) == 9
    assert {s.rule_id for s in samples} == {
        "tables-multi-row-header-tiers",
        "charts-labels",
        "forms-checkboxes",
    }
    assert {s.family for s in samples} == {"tables", "charts", "forms"}


def test_sample_fields():
    samples = extract_protocol(MINI)
    by_id = {s.sample_id: s for s in samples}
    s = by_id["tables-multi-row-header-tiers::5lineperrow"]
    assert s.image == "zoo-5lineperrow.png"
    assert s.partial is False
    assert "<table" in s.expected
    partials = [x for x in samples if x.partial]
    # Two elided excerpts in Header Tiers + the Checkboxes excerpt.
    assert len(partials) == 3
    assert all(x.image for x in samples)


def test_extraction_is_deterministic():
    a = extract_protocol(MINI)
    b = extract_protocol(MINI)
    assert [s.sample_id for s in a] == [s.sample_id for s in b]
    assert [s.expected for s in a] == [s.expected for s in b]
