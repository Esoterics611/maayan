"""UI/route tests for OCR capture (Prompt 30).

FakeOCRer via TestClient — no real Tesseract, no network. Verifies the route returns
text, honors the lang override, is inert when OCR is disabled, never ingests, and is
behind the auth wall when auth is on.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from maayan.clock import SystemClock
from maayan.config import Settings
from maayan.ocr.fake import FakeOCRer
from maayan.ui.app import create_app
from maayan.users.service import UserService
from maayan.users.store import UserStore

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32  # bytes only; FakeOCRer reads the name, not pixels


def _client(ocr: object | None = FakeOCRer()) -> TestClient:
    app = create_app(  # type: ignore[arg-type]
        None, None, None, None, None, None, None, None, ocr=ocr
    )
    return TestClient(app)


def test_ocr_returns_text_from_image() -> None:
    client = _client()
    r = client.post("/api/ocr", files={"file": ("likutei-p7.png", _PNG, "image/png")})
    assert r.status_code == 200, r.text
    body = r.json()
    # The FakeOCRer's deterministic signature proves the bytes went through the OCRer.
    assert "דף לדוגמה" in body["text"] and "(heb)" in body["text"]
    assert body["lang"] == "heb"  # configured default


def test_ocr_lang_override() -> None:
    client = _client()
    r = client.post("/api/ocr?lang=eng", files={"file": ("p.png", _PNG, "image/png")})
    assert r.status_code == 200
    assert r.json()["lang"] == "eng"
    assert "(eng)" in r.json()["text"]


def test_ocr_never_auto_ingests() -> None:
    # The route has no chunk store / index and returns text only — there is nothing it
    # *could* ingest. The response carries the text for the human review gate, full stop.
    client = _client()
    body = client.post("/api/ocr", files={"file": ("p.png", _PNG, "image/png")}).json()
    assert set(body.keys()) == {"text", "lang"}


def test_ocr_disabled_is_503() -> None:
    client = _client(ocr=None)  # ocr_backend="none" → no OCRer injected
    r = client.post("/api/ocr", files={"file": ("p.png", _PNG, "image/png")})
    assert r.status_code == 503


def test_ocr_requires_auth_when_enabled(tmp_path: Path) -> None:
    settings = Settings(db_path=str(tmp_path / "u.sqlite3"), pbkdf2_iterations=1000)
    users = UserService(UserStore(settings.db_path), SystemClock(), settings)
    app = create_app(  # type: ignore[arg-type]
        None, None, None, None, None, None, None, None,
        users=users, ocr=FakeOCRer(), auth_enabled=True,
    )
    client = TestClient(app)
    r = client.post("/api/ocr", files={"file": ("p.png", _PNG, "image/png")})
    assert r.status_code == 401  # auth wall stops it before the route
