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
from maayan.lexicon.models import Term
from maayan.transcribe.base import Transcriber
from maayan.transcribe.factory import build_transcriber
from maayan.transcribe.fake import FakeTranscriber
from maayan.transcribe.models import Transcript, TranscriptSegment
from maayan.transcribe.service import TranscriptionService
from maayan.transcribe.store import TranscriptionStore


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


# -- review: lexicon suggestions, edit, mark reviewed (Prompt 27) -------------
class _Terms:
    """Minimal TermService stand-in: only list_terms() is used by suggestions."""

    def __init__(self, terms: list[Term]) -> None:
        self._terms = terms

    def list_terms(self) -> list[Term]:
        return self._terms


def _ab_term() -> Term:
    return Term(
        id="ab", canonical='ע"ב (Ab)', surface_forms=['ע"ב', "עב"],
        definition="the Ab expansion", author="R. G",
    )


def _review_svc(
    tmp_path: Path, terms: object | None = None
) -> tuple[TranscriptionService, TranscriptionStore]:
    clock = FakeClock()
    store = TranscriptionStore(":memory:")
    svc = TranscriptionService(
        FakeTranscriber(clock), AudioStore(":memory:", clock), store, clock,
        audio_dir=str(tmp_path / "a"), terms=terms,  # type: ignore[arg-type]
    )
    return svc, store


def _transcript() -> Transcript:
    return Transcript(
        id="t1", audio_id="a1", lang="he", backend="fake", model="fake",
        created_at=FakeClock().now(),
        segments=[
            TranscriptSegment(idx=0, start_s=0.0, end_s=1.0, text="גילוי שם עב בעולם"),
            TranscriptSegment(idx=1, start_s=1.0, end_s=2.0, text="אהבה רבה"),
        ],
    )


def test_suggest_corrections_matches_surface_forms_without_overwriting(tmp_path: Path) -> None:
    svc, _ = _review_svc(tmp_path, terms=_Terms([_ab_term()]))
    enriched = svc.suggest_corrections(_transcript())

    # The folded surface "עב" matches the registered term → suggest the canonical form.
    s0 = enriched.segments[0]
    assert [sg.surface for sg in s0.suggestions] == ["עב"]
    assert s0.suggestions[0].canonical == 'ע"ב (Ab)'
    # A segment with no registered term yields nothing.
    assert enriched.segments[1].suggestions == []
    # Text is NEVER overwritten — the human decides.
    assert s0.text == "גילוי שם עב בעולם"
    assert s0.edited_text is None


def test_suggest_corrections_noop_without_lexicon(tmp_path: Path) -> None:
    svc, _ = _review_svc(tmp_path, terms=None)
    enriched = svc.suggest_corrections(_transcript())
    assert all(s.suggestions == [] for s in enriched.segments)


def test_update_segment_persists_edit_and_speaker(tmp_path: Path) -> None:
    svc, store = _review_svc(tmp_path)
    store.save_transcript(_transcript())
    updated = svc.update_segment("t1", 0, edited_text='גילוי שם ע"ב בעולם', speaker="Maggid")
    assert updated.segments[0].edited_text == 'גילוי שם ע"ב בעולם'
    assert updated.segments[0].speaker == "Maggid"
    # Persisted.
    again = store.get_transcript("t1")
    assert again is not None and again.segments[0].edited_text == 'גילוי שם ע"ב בעולם'


def test_update_segment_validates_target(tmp_path: Path) -> None:
    svc, store = _review_svc(tmp_path)
    store.save_transcript(_transcript())
    with pytest.raises(ValueError, match="out of range"):
        svc.update_segment("t1", 9, edited_text="x")
    with pytest.raises(ValueError, match="not found"):
        svc.update_segment("missing", 0, edited_text="x")


def test_mark_reviewed_flips_status(tmp_path: Path) -> None:
    svc, store = _review_svc(tmp_path)
    store.save_transcript(_transcript())
    assert svc.mark_reviewed("t1").status == "reviewed"
    again = store.get_transcript("t1")
    assert again is not None and again.status == "reviewed"


# -- approve → shiur chunks → index (Prompt 28) ------------------------------
def test_transcript_to_chunks_windows_and_carries_provenance() -> None:
    from maayan.transcribe.convert import transcript_to_chunks

    tr = Transcript(
        id="t1", audio_id="a1", lang="he", backend="fake", model="fake",
        created_at=FakeClock().now(),
        segments=[
            TranscriptSegment(idx=0, start_s=0.0, end_s=2.0, text="alpha", speaker="R"),
            TranscriptSegment(idx=1, start_s=2.0, end_s=4.0, text="beta"),
            TranscriptSegment(idx=2, start_s=4.0, end_s=6.0, text="gamma"),
        ],
    )
    one = transcript_to_chunks(tr, title="Demo", author="R. G", max_chars=0)
    assert len(one) == 1
    c = one[0]
    assert c.source == "shiur"
    assert c.text == "alpha beta gamma"
    assert c.ref.startswith("Shiur: Demo")
    assert c.metadata["audio_id"] == "a1" and c.metadata["author"] == "R. G"
    assert c.metadata["start_s"] == 0.0 and c.metadata["end_s"] == 6.0
    # Deterministic id (idempotent re-approve).
    assert transcript_to_chunks(tr, title="Demo", author="R. G", max_chars=0)[0].id == c.id
    # A small budget windows into several chunks, each keeping its own start.
    many = transcript_to_chunks(tr, title="Demo", author="R. G", max_chars=6)
    assert len(many) >= 2
    assert many[0].metadata["start_s"] == 0.0


def _indexed_svc(
    tmp_path: Path,
) -> tuple[TranscriptionService, TranscriptionStore, object, object, object]:
    from qdrant_client import QdrantClient

    from maayan.corpus.store import ChunkStore
    from maayan.embed.fake import HashingEmbedder
    from maayan.index.qdrant import QdrantIndex

    clock = FakeClock()
    store = TranscriptionStore(":memory:")
    chunk_store = ChunkStore(":memory:")
    emb = HashingEmbedder(dim=64)
    index = QdrantIndex(QdrantClient(location=":memory:"), "shiur_test", emb.dim)
    svc = TranscriptionService(
        FakeTranscriber(clock), AudioStore(":memory:", clock), store, clock,
        audio_dir=str(tmp_path / "a"), embedder=emb, chunk_store=chunk_store,
        index=index, shiur_chunk_chars=0,
    )
    return svc, store, chunk_store, index, emb


def test_approve_gates_on_reviewed_then_indexes_retrievable_shiur(tmp_path: Path) -> None:
    from maayan.retrieve.retriever import Retriever

    svc, store, chunk_store, index, emb = _indexed_svc(tmp_path)
    store.save_transcript(_transcript())  # status "raw"

    with pytest.raises(ValueError, match="reviewed"):
        svc.approve("t1", author="R. G")

    svc.mark_reviewed("t1")
    produced = svc.approve("t1", author="R. G")
    assert produced and all(c.source == "shiur" for c in produced)
    assert all(c.metadata["author"] == "R. G" for c in produced)
    assert store.get_transcript("t1").status == "approved"  # type: ignore[union-attr]
    assert chunk_store.counts_by_source().get("shiur", 0) >= 1

    # Retrievable alongside the rest of the corpus.
    results = Retriever(index, emb, top_k=5).search("אהבה רבה")  # type: ignore[arg-type]
    assert any(r.source == "shiur" for r in results)


def test_approve_requires_author(tmp_path: Path) -> None:
    svc, store, *_ = _indexed_svc(tmp_path)
    store.save_transcript(_transcript().model_copy(update={"status": "reviewed"}))
    with pytest.raises(ValueError, match="author is required"):
        svc.approve("t1", author="   ")


def test_approve_without_indexing_configured_errors(tmp_path: Path) -> None:
    svc, store = _review_svc(tmp_path)  # no embedder/chunk_store/index
    store.save_transcript(_transcript().model_copy(update={"status": "reviewed"}))
    with pytest.raises(ValueError, match="indexing not configured"):
        svc.approve("t1", author="R. G")


def test_reject_sets_status(tmp_path: Path) -> None:
    svc, store, *_ = _indexed_svc(tmp_path)
    store.save_transcript(_transcript())
    assert svc.reject("t1").status == "rejected"
