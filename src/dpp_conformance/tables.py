"""Table extraction and grid expansion.

Both HTML tables (DPP's canonical form for anything with spans) and Markdown
pipe tables are parsed into one common model: a fully expanded grid in which
every position knows its canonical text, whether it came from a header cell
(``<th>``), its ``data-level`` (stub hierarchy), and which source cell it
belongs to (its *origin*). Span structure can then be compared exactly:
two renderings have the same span structure iff their expanded origin grids
agree.

DPP equivalences applied here (draft 0.1, "Accepted Alternatives"):

* ``thead``/``tbody``/``tfoot`` wrappers are transparent;
* purely blank spacer rows: presence == absence, so all-empty rows are
  dropped from the expanded grid before comparison. Columns are never
  dropped: an all-blank column proven by its header is a classic DPP error
  case ("Barely-Existing Columns and Headers").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

from .normalize import canon_cell


@dataclass
class RawCell:
    text: str  # canonicalised text
    header: bool = False
    level: int | None = None
    colspan: int = 1
    rowspan: int = 1


@dataclass
class Grid:
    """A fully expanded table grid."""

    texts: tuple[tuple[str, ...], ...]  # [row][col] canonical text
    headers: tuple[tuple[bool, ...], ...]  # [row][col] came from <th>
    levels: tuple[tuple[int | None, ...], ...]  # [row][col] data-level
    origins: tuple[tuple[int, ...], ...]  # [row][col] source-cell id
    caption: str = ""
    source: str | None = None  # value of data-source attr, e.g. "chart"

    @property
    def n_rows(self) -> int:
        return len(self.texts)

    @property
    def n_cols(self) -> int:
        return len(self.texts[0]) if self.texts else 0

    def cell_texts_multiset(self) -> list[str]:
        """One entry per *source cell* (not per expanded position)."""
        seen: dict[int, str] = {}
        for r in range(self.n_rows):
            for c in range(self.n_cols):
                seen.setdefault(self.origins[r][c], self.texts[r][c])
        return list(seen.values())


def _expand(rows: list[list[RawCell]], caption: str, source: str | None) -> Grid:
    """Expand rowspan/colspan into a full grid, then drop blank spacer rows."""
    placed: dict[tuple[int, int], tuple[str, bool, int | None, int]] = {}
    origin = 0
    max_r = max_c = 0
    for r, row in enumerate(rows):
        c = 0
        for cell in row:
            while (r, c) in placed:
                c += 1
            for dr in range(cell.rowspan):
                for dc in range(cell.colspan):
                    placed[(r + dr, c + dc)] = (cell.text, cell.header, cell.level, origin)
                    max_r = max(max_r, r + dr)
                    max_c = max(max_c, c + dc)
            origin += 1
            c += cell.colspan
    n_rows, n_cols = max_r + 1, max_c + 1
    texts = tuple(
        tuple(placed.get((r, c), ("", False, None, -1))[0] for c in range(n_cols))
        for r in range(n_rows)
    )
    headers = tuple(
        tuple(placed.get((r, c), ("", False, None, -1))[1] for c in range(n_cols))
        for r in range(n_rows)
    )
    levels = tuple(
        tuple(placed.get((r, c), ("", False, None, -1))[2] for c in range(n_cols))
        for r in range(n_rows)
    )
    origins = tuple(
        tuple(placed.get((r, c), ("", False, None, -1))[3] for c in range(n_cols))
        for r in range(n_rows)
    )
    # DPP equivalence: purely blank spacer rows, presence == absence.
    keep = [r for r in range(n_rows) if any(texts[r][c] for c in range(n_cols))]
    if len(keep) != n_rows:
        texts = tuple(texts[r] for r in keep)
        headers = tuple(headers[r] for r in keep)
        levels = tuple(levels[r] for r in keep)
        origins = tuple(origins[r] for r in keep)
    # Origin ids are arbitrary labels: renumber by first occurrence in
    # reading order so two grids' span structures compare by pattern,
    # not by the accident of how many cells preceded them.
    remap: dict[int, int] = {}
    canon_origins = []
    for r in range(len(texts)):
        row = []
        for c in range(len(texts[r])):
            o = origins[r][c]
            if o not in remap:
                remap[o] = len(remap)
            row.append(remap[o])
        canon_origins.append(tuple(row))
    return Grid(texts=texts, headers=headers, levels=levels,
                origins=tuple(canon_origins), caption=caption, source=source)


class _HTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[RawCell]] = []
        self.caption = ""
        self.source: str | None = None
        self._row: list[RawCell] | None = None
        self._cell: dict | None = None
        self._in_caption = False
        self._caption_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self.source = a.get("data-source")
        elif tag == "caption":
            self._in_caption = True
        elif tag == "tr":
            self._row = []
        elif tag in ("th", "td") and self._row is not None:
            def _int(name):
                try:
                    return max(1, int(a.get(name, "1")))
                except ValueError:
                    return 1

            level = None
            if a.get("data-level") is not None:
                try:
                    level = int(a["data-level"])
                except ValueError:
                    level = None
            self._cell = {
                "parts": [], "header": tag == "th", "level": level,
                "colspan": _int("colspan"), "rowspan": _int("rowspan"),
            }
        elif tag == "br" and self._cell is not None:
            self._cell["parts"].append(" ")

    def handle_endtag(self, tag):
        if tag == "caption":
            self._in_caption = False
            self.caption = canon_cell(" ".join(self._caption_parts))
        elif tag in ("th", "td") and self._cell is not None and self._row is not None:
            self._row.append(RawCell(
                text=canon_cell(" ".join(self._cell["parts"])),
                header=self._cell["header"], level=self._cell["level"],
                colspan=self._cell["colspan"], rowspan=self._cell["rowspan"],
            ))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell["parts"].append(data)
        elif self._in_caption:
            self._caption_parts.append(data)


_HTML_TABLE_RE = re.compile(r"<table\b.*?</table>", re.S | re.I)
_PIPE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_SEPARATOR_RE = re.compile(r"^\s*\|?[\s:\-|]+\|?\s*$")


def parse_html_table(fragment: str) -> Grid:
    p = _HTMLTableParser()
    p.feed(fragment)
    p.close()
    return _expand(p.rows, p.caption, p.source)


def _parse_pipe_table(lines: list[str]) -> Grid:
    rows: list[list[RawCell]] = []
    for i, line in enumerate(lines):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if _SEPARATOR_RE.match(line) and set(line) <= set("|-: "):
            continue
        is_header = False
        if i + 1 < len(lines) and _SEPARATOR_RE.match(lines[i + 1]) and "-" in lines[i + 1]:
            is_header = True
        rows.append([RawCell(text=canon_cell(c), header=is_header) for c in cells])
    width = max((len(r) for r in rows), default=0)
    for r in rows:
        r.extend(RawCell(text="") for _ in range(width - len(r)))
    return _expand(rows, "", None)


@dataclass
class ExtractedDoc:
    tables: list[Grid] = field(default_factory=list)
    text_lines: list[str] = field(default_factory=list)  # raw non-table lines


def extract(md: str) -> ExtractedDoc:
    """Split a Markdown document into its tables and its remaining lines."""
    positioned: list[tuple[int, Grid]] = []  # (char offset, grid), document order
    consumed: list[tuple[int, int]] = []  # char spans of HTML tables
    for m in _HTML_TABLE_RE.finditer(md):
        positioned.append((m.start(), parse_html_table(m.group(0))))
        consumed.append((m.start(), m.end()))

    def _in_span(pos: int) -> bool:
        return any(a <= pos < b for a, b in consumed)

    lines: list[str] = []
    pos = 0
    raw_lines = md.split("\n")
    offsets = []
    for ln in raw_lines:
        offsets.append(pos)
        pos += len(ln) + 1

    pipe_run: list[str] = []
    pipe_start = 0

    def flush_pipe():
        nonlocal pipe_run
        if len(pipe_run) >= 2:
            positioned.append((pipe_start, _parse_pipe_table(pipe_run)))
        elif pipe_run:
            lines.extend(pipe_run)
        pipe_run = []

    for off, ln in zip(offsets, raw_lines):
        if _in_span(off):
            flush_pipe()
            continue
        if _PIPE_ROW_RE.match(ln):
            if not pipe_run:
                pipe_start = off
            pipe_run.append(ln)
        else:
            flush_pipe()
            lines.append(ln)
    flush_pipe()
    positioned.sort(key=lambda t: t[0])
    return ExtractedDoc(tables=[g for _, g in positioned], text_lines=lines)
