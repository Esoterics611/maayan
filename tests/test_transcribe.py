"""Tests for the transcription spine + audio store (Prompt 25).

No real Whisper, no network: the fake backend is deterministic and the audio store
is exercised with tiny generated WAVs. ffmpeg-missing is simulated by monkeypatch.
"""

from __future__ import annotations

import wave
from pathlib import Path

import pytest

from maayan.audio.store import AudioStore
from maayan.clock import FakeClock
from maayan.config import Settings
from maayan.transcribe.base import Transcriber
from maayan.transcribe.factory import build_transcriber
from maayan.transcribe.fake import FakeTranscriber
from maayan.transcribe.models import Transcript


def _make_wav(path: Path, rate: int = 8000, secs: float = 0.2) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * secs))


# -- transcriber -------------------------------------------------------------
def test_fake_transcribe_round_trips_ordered_timestamped_segments() -> None:
    clock = FakeClock()
    t = FakeTranscriber(clock)
    assert isinstance(t, Transcriber)  # satisfies the protocol (DI seam)

    tr = t.transcribe(Path("recordings/shiur_aleph.wav"))
    assert tr.backend == "fake"
    assert tr.created_at == clock.now()
    assert [s.idx for s in tr.segments] == [0, 1, 2]
    # Segments are ordered and non-overlapping with valid spans.
    for s in tr.segments:
        assert s.start_s <= s.end_s
    for a, b in zip(tr.segments, tr.segments[1:], strict=False):
        assert a.end_s <= b.start_s
    # Deterministic + tied to the file name.
    assert "shiur_aleph" in tr.segments[0].text
    # Clean pydantic round-trip.
    assert Transcript.model_validate(tr.model_dump()) == tr


def test_lang_override_beats_default() -> None:
    t = FakeTranscriber(FakeClock(), default_lang="he")
    assert t.transcribe(Path("x.wav")).lang == "he"
    assert t.transcribe(Path("x.wav"), lang="en").lang == "en"


def test_segment_display_text_prefers_edit() -> None:
    tr = FakeTranscriber(FakeClock()).transcribe(Path("x.wav"))
    seg = tr.segments[0]
    assert seg.display_text == seg.text
    edited = seg.model_copy(update={"edited_text": "corrected"})
    assert edited.display_text == "corrected"


# -- factory (config selects the backend) ------------------------------------
def test_factory_selects_fake() -> None:
    t = build_transcriber(Settings(transcribe_backend="fake"), clock=FakeClock())
    assert isinstance(t, FakeTranscriber)


def test_factory_whisper_is_lazy() -> None:
    # Construction must not import faster_whisper (only first transcribe() does).
    t = build_transcriber(Settings(transcribe_backend="whisper"), clock=FakeClock())
    assert type(t).__name__ == "WhisperTranscriber"


def test_factory_cloud_is_documented_swap_point() -> None:
    with pytest.raises(NotImplementedError):
        build_transcriber(Settings(transcribe_backend="cloud"))


def test_factory_unknown_backend_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown transcribe_backend"):
        build_transcriber(Settings(transcribe_backend="nope"))


# -- audio store -------------------------------------------------------------
def test_store_file_is_idempotent_by_sha256(tmp_path: Path) -> None:
    src = tmp_path / "a.wav"
    _make_wav(src)
    store = AudioStore(":memory:", FakeClock())
    audio_dir = str(tmp_path / "audio")

    a1 = store.store_file(src, owner="cli", audio_dir=audio_dir)
    a2 = store.store_file(src, owner="cli", audio_dir=audio_dir)  # same bytes → same row

    assert a1 == a2
    assert len(store.list_assets()) == 1
    assert store.get(a1.id) == a1
    got = store.get_by_sha256(a1.sha256)
    assert got is not None and got.id == a1.id
    assert Path(a1.path).exists()


def test_store_file_degrades_without_ffmpeg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulate ffmpeg missing: the file is kept as-is (not normalized) with a warning.
    monkeypatch.setattr("maayan.audio.store.shutil.which", lambda _name: None)
    src = tmp_path / "b.wav"
    _make_wav(src, rate=8000)
    store = AudioStore(":memory:", FakeClock())

    with pytest.warns(UserWarning, match="ffmpeg not found"):
        asset = store.store_file(src, owner="x", audio_dir=str(tmp_path / "audio"))

    assert Path(asset.path).exists()
    assert asset.path.endswith(".wav")
    assert asset.sample_rate == 8000  # untouched (would be 16000 if normalized)
