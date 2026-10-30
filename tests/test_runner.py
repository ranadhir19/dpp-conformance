"""The benchmark runner must survive bad parses: a parser that errors or
hangs on a page is recorded as a failed parse, never a stalled run."""

from pathlib import Path

import pytest

from dpp_conformance.cli import _parse_with_timeout

EXAMPLE = (Path(__file__).parent.parent
           / "examples" / "tables-multi-row-header-tiers" / "page.png")


def test_worker_parses_a_real_page(tmp_path):
    pytest.importorskip("pymupdf")
    text, error = _parse_with_timeout("pymupdf-text", str(EXAMPLE),
                                      tmp_path, timeout=120)
    assert error is None
    assert isinstance(text, str)  # image-only page: text layer is empty


def test_unknown_arm_is_a_recorded_error_not_a_crash(tmp_path):
    text, error = _parse_with_timeout("no-such-arm", str(EXAMPLE),
                                      tmp_path, timeout=120)
    assert text == ""
    assert error is not None and "parse failed" in error
