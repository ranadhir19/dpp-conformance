"""Extract the DPP sample corpus from a checkout of the DPP repository.

The Document Parsing Protocol (run-llama/document_parsing_protocol, draft
0.1) publishes its rules as one Markdown file per rule under ``protocol/``,
grouped by chapter. Most rules carry worked samples: a page image
(``![[name.png]]`` in ``protocol/_attachments/``) followed by a
``<details>`` block whose summary starts with "Expected Markdown" and whose
fenced code block is the output the protocol expects for that page.

This module turns those files into a flat list of :class:`Sample` records.
A sample is *partial* when its expected output is an excerpt or contains an
elision (``<!-- ... -->`` or ``...``): partial samples can verify that
content is preserved, but cannot verify completeness of structure.

The protocol text and its examples are CC BY 4.0 (credit: "Document Parsing
Protocol, LlamaIndex"); see ATTRIBUTION.md.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

CHAPTER_FAMILIES = {
    "01 Conventions": "conventions",
    "02 Principles": "principles",
    "03 Output model": "output-model",
    "04 Document level": "document",
    "05 Layout": "layout",
    "06 Headings and page structure": "headings",
    "07 Text": "text",
    "08 Lists": "lists",
    "09 Tables": "tables",
    "10 Forms": "forms",
    "11 Charts": "charts",
    "12 Images and diagrams": "images-diagrams",
    "13 Other": "other",
    "A Equivalent forms": "equivalences",
    "C Producing ground truth": "ground-truth",
    "D Quick reference": "reference",
}

_IMG_RE = re.compile(r"!\[\[([^\]]+)\]\]")
_EXPECTED_RE = re.compile(
    r"<summary>(Expected Markdown[^<]*)</summary>\s*```markdown\n(.*?)```", re.S
)
_HEADING_RE = re.compile(r"^#{2,4}\s+(.*)$", re.M)
_SAMPLE_NAME_RE = re.compile(r"\*\*Sample\*\*\s*—\s*`([^`]+)`")
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.S)


@dataclass
class Sample:
    rule_id: str
    rule_title: str
    family: str
    chapter: str
    sample_name: str
    image: str | None  # image file name in protocol/_attachments, or None
    expected: str  # expected Markdown output for the sample page
    summary: str  # the <summary> label, e.g. "Expected Markdown · excerpt"
    partial: bool  # excerpt or elided: cannot verify full structure
    source_file: str  # rule file, relative to the protocol checkout root

    @property
    def sample_id(self) -> str:
        return f"{self.rule_id}::{self.sample_name}"


def _frontmatter(text: str) -> dict[str, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def _is_partial(summary: str, expected: str) -> bool:
    if "excerpt" in summary.lower():
        return True
    if "<!--" in expected:  # elision comment inside the expected output
        return True
    # A line consisting only of an ellipsis marks omitted rows/content.
    return any(ln.strip() in ("…", "...") for ln in expected.split("\n"))


def extract_protocol(protocol_dir: str | Path) -> list[Sample]:
    """Extract every sample from a DPP ``protocol/`` directory."""
    protocol_dir = Path(protocol_dir)
    samples: list[Sample] = []
    for path in sorted(protocol_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = _frontmatter(text)
        rule_id = fm.get("rule_id")
        if not rule_id:
            continue
        rel = path.relative_to(protocol_dir)
        chapter = rel.parts[0] if len(rel.parts) > 1 else ""
        family = CHAPTER_FAMILIES.get(chapter, "root")

        # Walk the file in order, tracking the most recent image, sample
        # heading and bold "Sample — `name`" marker before each block.
        events: list[tuple[int, str, str]] = []  # (pos, kind, value)
        for m in _IMG_RE.finditer(text):
            events.append((m.start(), "image", m.group(1)))
        for m in _HEADING_RE.finditer(text):
            events.append((m.start(), "heading", m.group(1)))
        for m in _SAMPLE_NAME_RE.finditer(text):
            events.append((m.start(), "name", m.group(1)))
        for m in _EXPECTED_RE.finditer(text):
            events.append((m.start(), "expected", m.group(0)))
        events.sort(key=lambda e: e[0])

        last_image: str | None = None
        last_name = ""
        idx = 0
        used_names: dict[str, int] = {}
        for pos, kind, value in events:
            if kind == "image":
                last_image = value
            elif kind == "name":
                last_name = value
            elif kind == "heading":
                if "Sample" in value:
                    nm = _SAMPLE_NAME_RE.search(value)
                    if nm:
                        last_name = nm.group(1)
                    else:
                        h = value.replace("**", "").strip()
                        h = re.sub(r"^[^A-Za-z]*", "", h)  # leading emoji/symbols
                        h = re.sub(r"^Sample\s*[—:-]\s*", "", h)
                        last_name = h.strip()[:80]
            elif kind == "expected":
                m = _EXPECTED_RE.match(value)
                summary, expected = m.group(1), m.group(2)
                name = last_name or f"sample-{idx}"
                if name in used_names:  # keep sample_id unique within a rule
                    used_names[name] += 1
                    name = f"{name}#{used_names[name]}"
                else:
                    used_names[name] = 1
                samples.append(Sample(
                    rule_id=rule_id,
                    rule_title=fm.get("title", ""),
                    family=family,
                    chapter=chapter,
                    sample_name=name,
                    image=last_image,
                    expected=expected.rstrip("\n"),
                    summary=summary,
                    partial=_is_partial(summary, expected),
                    source_file=str(rel),
                ))
                idx += 1
                last_image = None
    return samples


def samples_to_json(samples: list[Sample]) -> str:
    return json.dumps([asdict(s) for s in samples], indent=1, ensure_ascii=False)


def samples_from_json(text: str) -> list[Sample]:
    return [Sample(**d) for d in json.loads(text)]


def find_image(protocol_dir: str | Path, image: str) -> Path | None:
    """Resolve an image file name inside protocol/_attachments (recursive)."""
    att = Path(protocol_dir) / "_attachments"
    for p in att.rglob(image):
        return p
    return None
