"""Tests for the OCR module (Prompt 30) — protocol, fake backend, factory.

No real Tesseract: `FakeOCRer` is deterministic and dependency-free, exactly like
`FakeTranscriber` for audio. The factory's DI seam is exercised without importing
any `ml`-extra deps.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from maayan.config import Settings
from maayan.ocr.base import OCRer
from maayan.ocr.factory import build_ocrer
from maayan.ocr.fake import FakeOCRer


def test_fake_ocrer_satisfies_protocol_and_is_deterministic() -> None:
    ocrer = FakeOCRer()
    assert isinstance(ocrer, OCRer)
    out1 = ocrer.ocr(Path("/tmp/likutei-page-42.png"))
    out2 = ocrer.ocr(Path("/tmp/likutei-page-42.png"))
    assert out1 == out2  # deterministic
    assert "likutei-page-42" in out1  # derived from the file stem
    assert "\n" in out1  # multi-line so callers see real text flow


def test_fake_ocrer_lang_override_reflected() -> None:
    ocrer = FakeOCRer(default_lang="heb")
    assert "(heb)" in ocrer.ocr(Path("p.png"))
    assert "(eng)" in ocrer.ocr(Path("p.png"), lang="eng")


def test_factory_none_disables_ocr() -> None:
    # Default config: OCR is off and additive — the factory returns None.
    assert build_ocrer(Settings()) is None
    assert build_ocrer(Settings(ocr_backend="none")) is None


def test_factory_fake_backend() -> None:
    ocrer = build_ocrer(Settings(ocr_backend="fake", ocr_lang="eng"))
    assert isinstance(ocrer, FakeOCRer)
    assert "(eng)" in ocrer.ocr(Path("x.png"))  # honors configured default lang


def test_factory_tesseract_constructs_without_importing_deps() -> None:
    # Construction must not import pytesseract/PIL (lazy until .ocr() is called).
    ocrer = build_ocrer(Settings(ocr_backend="tesseract"))
    assert ocrer is not None
    assert isinstance(ocrer, OCRer)


def test_factory_cloud_is_documented_swap() -> None:
    with pytest.raises(NotImplementedError):
        build_ocrer(Settings(ocr_backend="cloud"))


def test_factory_unknown_backend_raises() -> None:
    with pytest.raises(ValueError, match="Unknown ocr_backend"):
        build_ocrer(Settings(ocr_backend="bogus"))
