"""Text normalisation and DPP equivalence canonicalisation.

The equivalences implemented here come from the Document Parsing Protocol
itself (draft 0.1), principally the "Accepted Alternatives" appendix and the
"Conformance" chapter of run-llama/document_parsing_protocol (CC BY 4.0):

* visually identical characters never count as a difference:
  micro sign (U+00B5) == Greek mu (U+03BC); non-breaking hyphen (U+2011),
  minus sign (U+2212), figure/en dashes == hyphen-minus in comparison;
  non-breaking space == space;
* ``thead``/``tbody``/``tfoot`` wrappers (or their absence) are equivalent
  (handled in :mod:`dpp_conformance.tables`, which ignores the wrappers);
* purely blank spacer rows: presence == absence (also in tables.py).

On top of the protocol's own equivalences, the checker applies a small set of
*comparison-only* normalisations, documented in docs/JUDGING.md: HTML entities
are decoded, whitespace is collapsed, and inline emphasis markup
(``<strong>``/``<b>``/``<em>``/``<i>``/``**``/``*``) is stripped, because
emphasis is typographic styling rather than cell content. Case is *not*
folded: DPP requires labels to keep their printed capitalisation.
"""

from __future__ import annotations

import html
import re

# Visually identical characters (DPP, "Accepted Alternatives").
_CHAR_MAP = {
    "\u00b5": "\u03bc",  # micro sign -> Greek small mu
    "\u2011": "-",  # non-breaking hyphen
    "\u2010": "-",  # hyphen
    "\u2012": "-",  # figure dash
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash (comparison only)
    "\u2212": "-",  # minus sign
    "\u00a0": " ",  # no-break space
    "\u202f": " ",  # narrow no-break space
    "\u2007": " ",  # figure space
    "\u3000": " ",  # ideographic space
    "\u200b": "",  # zero width space
    "\ufeff": "",  # zero width no-break space / BOM
}
_CHAR_TABLE = str.maketrans(_CHAR_MAP)

_TAG_RE = re.compile(r"<[^>]+>")
_MD_EMPHASIS_RE = re.compile(r"(\*\*|__|\*|_)")
_WS_RE = re.compile(r"\s+")


def canon_text(s: str) -> str:
    """Canonicalise a plain-text fragment for comparison.

    Decodes HTML entities, applies DPP's visually-identical-character
    equivalences, collapses all whitespace runs to single spaces and strips.
    Case is preserved.
    """
    if not s:
        return ""
    s = html.unescape(s)
    s = s.translate(_CHAR_TABLE)
    s = _WS_RE.sub(" ", s)
    return s.strip()


def strip_markup(s: str) -> str:
    """Remove HTML tags and Markdown emphasis markers, keeping the text."""
    s = _TAG_RE.sub(" ", s)
    s = _MD_EMPHASIS_RE.sub("", s)
    return s


def canon_cell(s: str) -> str:
    """Canonicalise a table cell's raw inner content for comparison."""
    s = s.replace("<br/>", " ").replace("<br>", " ").replace("<br />", " ")
    return canon_text(strip_markup(s))


def canon_line(s: str) -> str:
    """Canonicalise a non-table Markdown line for comparison."""
    s = s.strip()
    # Drop ATX heading markers and blockquote markers; keep the words.
    s = re.sub(r"^#{1,6}\s+", "", s)
    s = re.sub(r"^>\s?", "", s)
    return canon_text(strip_markup(s))


def tokens(s: str) -> list[str]:
    """Tokenise an already-canonicalised string on whitespace."""
    return s.split(" ") if s else []
