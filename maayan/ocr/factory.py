"""OCRer factory — selects the backend from config (DI seam).

`OCR_BACKEND` decides which OCRer is injected; no other code changes when swapping
local Tesseract ↔ a cloud OCR. `none` (the default) means the feature is off — the
factory returns `None` and the `/api/ocr` route stays inert, so OCR is purely
additive. `fake` is the deterministic test/offline backend (also via CLI `--mock`).
"""

from __future__ import annotations

from maayan.config import Settings
from maayan.ocr.base import OCRer


def build_ocrer(settings: Settings) -> OCRer | None:
    """Build the configured OCRer, or `None` when OCR is disabled (`ocr_backend="none"`)."""
    backend = settings.ocr_backend
    if backend == "none":
        return None
    if backend == "fake":
        from maayan.ocr.fake import FakeOCRer

        return FakeOCRer(default_lang=settings.ocr_lang)
    if backend == "tesseract":
        from maayan.ocr.tesseract import TesseractOCRer

        return TesseractOCRer(default_lang=settings.ocr_lang)
    if backend == "cloud":
        raise NotImplementedError(
            "Cloud OCR is a documented swap point, not built yet (see "
            "docs/BUILD_PLAN_PHASE6.md §Prompt 30). Set OCR_BACKEND=tesseract for local "
            "OCR, or =fake for the offline/test backend."
        )
    raise ValueError(f"Unknown ocr_backend: {backend!r}")
