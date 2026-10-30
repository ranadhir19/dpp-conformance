"""Parser arms: run real document parsers over DPP sample page images.

Two arms are provided:

``pymupdf-text``
    A text-layer extractor. The sample page image is embedded in a
    one-page PDF and PyMuPDF reads the page's text. DPP sample pages are
    rendered page images, so this arm sees no text layer and returns
    (almost) nothing. That is a genuine, measured result, not a bug: DPP's
    Conformance chapter insists an output is judged "against the document
    as rendered ... never against the file's text layer", and this arm
    quantifies what a text-layer pipeline scores under that rule: zero.

``docling``
    IBM's Docling pipeline (layout analysis + OCR + table structure) run
    directly on the page image, exporting Markdown. This is the substantive
    arm: a real, CPU-feasible, open-source document parser.

Both arms return a Markdown string. Errors are raised as RuntimeError with
the underlying message so the runner can record a failed parse honestly
instead of grading an empty output silently.
"""

from __future__ import annotations

import io
from pathlib import Path


def pymupdf_text(image_path: str | Path) -> str:
    """Extract text via PyMuPDF from the image wrapped in a one-page PDF."""
    try:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz  # older PyMuPDF
        from PIL import Image
    except ImportError as e:  # pragma: no cover - environment dependent
        raise RuntimeError(f"pymupdf-text arm unavailable: {e}") from e

    image_path = Path(image_path)
    with Image.open(image_path) as im:
        w, h = im.size
    # Treat the image as rendered at 200 dpi: page size in points.
    page_w, page_h = w * 72 / 200, h * 72 / 200
    doc = fitz.open()
    page = doc.new_page(width=page_w, height=page_h)
    page.insert_image(fitz.Rect(0, 0, page_w, page_h), filename=str(image_path))
    text = page.get_text("text")
    doc.close()
    return text


class _DoclingArm:
    """Lazy singleton around Docling's DocumentConverter (CPU pipeline)."""

    def __init__(self) -> None:
        self._converter = None

    def _get(self):
        if self._converter is None:
            try:
                from docling.document_converter import DocumentConverter
            except ImportError as e:  # pragma: no cover
                raise RuntimeError(f"docling arm unavailable: {e}") from e
            self._converter = DocumentConverter()
        return self._converter

    def parse(self, image_path: str | Path) -> str:
        converter = self._get()
        result = converter.convert(str(image_path))
        return result.document.export_to_markdown()


_DOCLING = _DoclingArm()


def docling_parse(image_path: str | Path) -> str:
    return _DOCLING.parse(image_path)


ARMS = {
    "pymupdf-text": pymupdf_text,
    "docling": docling_parse,
}


def run_arm(arm: str, image_path: str | Path) -> str:
    if arm not in ARMS:
        raise ValueError(f"unknown parser arm {arm!r}; choose from {sorted(ARMS)}")
    return ARMS[arm](image_path)
