"""OCRer interface.

An `OCRer` turns an image of a page into text. Tesseract (local) and, later, a
cloud OCR both implement it; callers depend only on this protocol, so the backend
is swapped via config with no other code changes (cf. `transcribe/`, `generate/`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class OCRer(Protocol):
    """Extracts text from an image file."""

    def ocr(self, image_path: Path, lang: str | None = None) -> str:
        """OCR `image_path`; `lang` overrides the configured default (e.g. "heb")."""
        ...
