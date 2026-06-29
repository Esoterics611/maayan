"""Local OCR via Tesseract (pytesseract + Pillow).

Heavy/system-dependent, so `pytesseract` and `PIL` are imported lazily (only when an
image is actually OCR'd) and live under the `ml` extra plus the `tesseract-ocr` /
`tesseract-ocr-heb` system packages. Unit tests use `FakeOCRer`; this is never called
in CI. Hebrew needs the `heb` traineddata installed alongside Tesseract.
"""

from __future__ import annotations

from pathlib import Path


class TesseractOCRer:
    """pytesseract backend. Language code is Tesseract-style ("heb", "eng")."""

    def __init__(self, *, default_lang: str = "heb") -> None:
        self._default_lang = default_lang

    def ocr(self, image_path: Path, lang: str | None = None) -> str:
        import pytesseract  # lazy: system dep, not needed for the core skeleton
        from PIL import Image

        language = lang or self._default_lang
        with Image.open(str(image_path)) as img:
            text: str = pytesseract.image_to_string(img, lang=language)
        return text.strip()
