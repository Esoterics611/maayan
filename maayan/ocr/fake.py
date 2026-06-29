"""A deterministic, dependency-free OCRer for tests and no-Tesseract demos.

`FakeOCRer` returns fixed text derived from the file name — enough to exercise the
capture path (photograph → text → review field) without installing Tesseract. It
satisfies the `OCRer` protocol so it drops in via DI, exactly like `FakeTranscriber`
does for audio and `HashingEmbedder` does for embeddings.
"""

from __future__ import annotations

from pathlib import Path


class FakeOCRer:
    """Deterministic OCR output for tests/offline demos. Not real OCR."""

    def __init__(self, *, default_lang: str = "heb") -> None:
        self._default_lang = default_lang

    def ocr(self, image_path: Path, lang: str | None = None) -> str:
        stem = Path(image_path).stem
        used = lang or self._default_lang
        # Two short lines so callers can see multi-line OCR text flow into a field.
        return f"דף לדוגמה: {stem}\nשורה שנייה מתוך התמונה ({used})."
