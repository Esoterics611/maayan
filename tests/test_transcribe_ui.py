"""UI/route tests for async transcription (Prompt 26).

FakeTranscriber + in-memory stores via TestClient — no real Whisper, no network.
TestClient runs FastAPI BackgroundTasks before the call returns, so a transcribe
POST has finished its job by the time we poll it.
"""

from __future__ import annotations

import io
import wave
from pathlib import Path

from fastapi.testclient import TestClient

from maayan.audio.store import AudioStore
from maayan.clock import FakeClock, SystemClock
from maayan.config import Settings
from maayan.lexicon.models import Term
from maayan.transcribe.fake import FakeTranscriber
from maayan.transcribe.models import Transcript
from maayan.transcribe.service import TranscriptionService
from maayan.transcribe.store import TranscriptionStore
from maayan.ui.app import create_app
from maayan.users.service import UserService
from maayan.users.store import UserStore


class _Terms:
    """TermService stand-in for review suggestions; only list_terms() is used."""

    def __init__(self, terms: list[Term]) -> None:
        self._terms = terms

    def list_terms(self) -> list[Term]:
        return self._terms


def _wav_bytes(rate: int = 8000, secs: float = 0.2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * secs))
    return buf.getvalue()


class _BoomTranscriber:
    def transcribe(self, audio_path: Path, lang: str | None = None) -> Transcript:
        raise RuntimeError("decode failed")


def _service(
    tmp_path: Path, transcriber: object | None = None, terms: object | None = None
) -> TranscriptionService:
    clock = FakeClock()
    return TranscriptionService(
        transcriber or FakeTranscriber(clock),  # type: ignore[arg-type]
        AudioStore(":memory:", clock),
        TranscriptionStore(":memory:"),
        clock,
        audio_dir=str(tmp_path / "audio"),
        terms=terms,  # type: ignore[arg-type]
    )


def _client(
    tmp_path: Path, transcriber: object | None = None, terms: object | None = None
) -> TestClient:
    svc = _service(tmp_path, transcriber, terms)
    app = create_app(  # type: ignore[arg-type]
        None, None, None, None, None, None, None, None, transcription=svc
    )
    return TestClient(app)


def _make_transcript(client: TestClient) -> tuple[str, str]:
    """Upload + transcribe a clip; return (audio_id, transcript_id)."""
    audio_id = _upload(client)
    job = client.post(f"/api/audio/{audio_id}/transcribe").json()
    job = client.get(f"/api/jobs/{job['id']}").json()
    return audio_id, job["transcript_id"]


def _upload(client: TestClient) -> str:
    r = client.post("/api/audio", files={"file": ("shiur.wav", _wav_bytes(), "audio/wav")})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_upload_returns_asset(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post("/api/audio", files={"file": ("shiur.wav", _wav_bytes(), "audio/wav")})
    assert r.status_code == 200
    asset = r.json()
    assert asset["filename"] == "shiur.wav"
    assert asset["owner"] == "local"  # no auth → local owner
    assert asset["sha256"]


def test_transcribe_runs_to_done_with_transcript(tmp_path: Path) -> None:
    client = _client(tmp_path)
    audio_id = _upload(client)

    started = client.post(f"/api/audio/{audio_id}/transcribe")
    assert started.status_code == 200
    job_id = started.json()["id"]

    # BackgroundTasks already ran under TestClient → terminal state on poll.
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "done"
    assert job["progress"] == 1.0
    assert job["transcript_id"]

    transcript = client.get(f"/api/transcripts/{job['transcript_id']}").json()
    assert transcript["audio_id"] == audio_id
    assert transcript["backend"] == "fake"
    assert [s["idx"] for s in transcript["segments"]] == [0, 1, 2]


def test_transcribe_unknown_audio_is_404(tmp_path: Path) -> None:
    client = _client(tmp_path)
    assert client.post("/api/audio/nope/transcribe").status_code == 404


def test_missing_job_and_transcript_are_404(tmp_path: Path) -> None:
    client = _client(tmp_path)
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.get("/api/transcripts/nope").status_code == 404


def test_failed_transcription_sets_error(tmp_path: Path) -> None:
    client = _client(tmp_path, transcriber=_BoomTranscriber())
    audio_id = _upload(client)
    job_id = client.post(f"/api/audio/{audio_id}/transcribe").json()["id"]
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "error"
    assert "decode failed" in job["error"]
    assert job["transcript_id"] is None


def test_get_transcript_includes_lexicon_suggestions(tmp_path: Path) -> None:
    nefesh = Term(
        id="nef", canonical="נפש (Nefesh)", surface_forms=["נפש"],
        definition="the soul", author="R. G",
    )
    client = _client(tmp_path, terms=_Terms([nefesh]))
    _, transcript_id = _make_transcript(client)
    tr = client.get(f"/api/transcripts/{transcript_id}").json()
    # The fake transcript's 2nd segment contains "נפש" → a suggestion is offered.
    seg = next(s for s in tr["segments"] if any(sg for sg in s["suggestions"]))
    assert seg["suggestions"][0]["canonical"] == "נפש (Nefesh)"
    # The raw text is untouched (suggestion only).
    assert seg["edited_text"] is None


def test_patch_segment_persists_edit(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _, transcript_id = _make_transcript(client)
    r = client.patch(
        f"/api/transcripts/{transcript_id}/segments/0",
        json={"edited_text": "תוקן", "speaker": "Maggid"},
    )
    assert r.status_code == 200
    assert r.json()["segments"][0]["edited_text"] == "תוקן"
    # Persisted across a fresh GET.
    again = client.get(f"/api/transcripts/{transcript_id}").json()
    assert again["segments"][0]["edited_text"] == "תוקן"
    assert again["segments"][0]["speaker"] == "Maggid"


def test_patch_bad_segment_index_is_404(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _, transcript_id = _make_transcript(client)
    r = client.patch(f"/api/transcripts/{transcript_id}/segments/99", json={"edited_text": "x"})
    assert r.status_code == 404


def test_review_marks_transcript_reviewed(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _, transcript_id = _make_transcript(client)
    r = client.post(f"/api/transcripts/{transcript_id}/review")
    assert r.status_code == 200
    assert r.json()["status"] == "reviewed"


def test_audio_file_is_served(tmp_path: Path) -> None:
    client = _client(tmp_path)
    audio_id, _ = _make_transcript(client)
    r = client.get(f"/api/audio/{audio_id}/file")
    assert r.status_code == 200
    assert client.get("/api/audio/nope/file").status_code == 404


def test_audio_endpoints_require_auth_when_enabled(tmp_path: Path) -> None:
    settings = Settings(db_path=str(tmp_path / "u.sqlite3"), pbkdf2_iterations=1000)
    users = UserService(UserStore(settings.db_path), SystemClock(), settings)
    app = create_app(  # type: ignore[arg-type]
        None, None, None, None, None, None, None, None,
        users=users, transcription=_service(tmp_path), auth_enabled=True,
    )
    client = TestClient(app)
    # No session → the auth wall returns 401 for the API before reaching the route.
    assert client.post(
        "/api/audio", files={"file": ("a.wav", _wav_bytes(), "audio/wav")}
    ).status_code == 401
    assert client.get("/api/jobs/x").status_code == 401
