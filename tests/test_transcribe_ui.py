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
from maayan.transcribe.fake import FakeTranscriber
from maayan.transcribe.models import Transcript
from maayan.transcribe.service import TranscriptionService
from maayan.transcribe.store import TranscriptionStore
from maayan.ui.app import create_app
from maayan.users.service import UserService
from maayan.users.store import UserStore


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


def _service(tmp_path: Path, transcriber: object | None = None) -> TranscriptionService:
    clock = FakeClock()
    return TranscriptionService(
        transcriber or FakeTranscriber(clock),  # type: ignore[arg-type]
        AudioStore(":memory:", clock),
        TranscriptionStore(":memory:"),
        clock,
        audio_dir=str(tmp_path / "audio"),
    )


def _client(tmp_path: Path, transcriber: object | None = None) -> TestClient:
    svc = _service(tmp_path, transcriber)
    app = create_app(  # type: ignore[arg-type]
        None, None, None, None, None, None, None, None, transcription=svc
    )
    return TestClient(app)


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
