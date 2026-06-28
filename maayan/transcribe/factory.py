"""Transcriber factory — selects the backend from config (DI seam).

`TRANSCRIBE_BACKEND` decides which transcriber is injected; no other code changes
when swapping local Whisper ↔ a cloud ASR. `fake` is the deterministic test/offline
backend (also selected by the CLI `--mock` flag).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from maayan.clock import Clock, SystemClock
from maayan.config import Settings
from maayan.embed.base import Embedder
from maayan.transcribe.base import Transcriber

if TYPE_CHECKING:
    from maayan.transcribe.service import TranscriptionService


def build_transcriber(settings: Settings, *, clock: Clock | None = None) -> Transcriber:
    clock = clock or SystemClock()
    backend = settings.transcribe_backend
    if backend == "fake":
        from maayan.transcribe.fake import FakeTranscriber

        return FakeTranscriber(clock, default_lang=settings.transcribe_lang)
    if backend == "whisper":
        from maayan.transcribe.whisper import WhisperTranscriber

        return WhisperTranscriber(
            settings.whisper_model,
            clock=clock,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
            default_lang=settings.transcribe_lang,
            diarize=settings.transcribe_diarize,
        )
    if backend == "cloud":
        raise NotImplementedError(
            "Cloud transcription is a documented swap point, not built yet "
            "(see docs/BUILD_PLAN_PHASE6.md §3). Set TRANSCRIBE_BACKEND=whisper for local "
            "Whisper, or =fake for the offline/test backend."
        )
    raise ValueError(f"Unknown transcribe_backend: {backend!r}")


def build_transcription_service(
    settings: Settings,
    *,
    clock: Clock | None = None,
    terms: object | None = None,
    embedder: Embedder | None = None,
) -> TranscriptionService:
    """Assemble the TranscriptionService wired to the same DB, audio dir, embedder, and
    Qdrant collection as the rest (DI at the edge).

    `terms` (a TermService) powers lexicon review suggestions; `embedder` is shared so we
    don't load bge-m3 twice. Both are built here if not passed, so the service is
    self-contained. The chunk store + index let approve() ingest shiur chunks via the
    EXISTING pipeline.
    """
    from maayan.audio.store import AudioStore
    from maayan.corpus.store import ChunkStore
    from maayan.embed.factory import build_embedder
    from maayan.index.qdrant import QdrantIndex, build_qdrant_client
    from maayan.lexicon.factory import build_term_service
    from maayan.transcribe.service import TranscriptionService
    from maayan.transcribe.store import TranscriptionStore

    clock = clock or SystemClock()
    emb = embedder or build_embedder(settings)
    term_service = terms or build_term_service(settings, embedder=emb)
    index = QdrantIndex(build_qdrant_client(settings), settings.collection_name, emb.dim)
    return TranscriptionService(
        build_transcriber(settings, clock=clock),
        AudioStore(settings.db_path, clock),
        TranscriptionStore(settings.db_path),
        clock,
        audio_dir=settings.audio_dir,
        terms=term_service,  # type: ignore[arg-type]
        embedder=emb,
        chunk_store=ChunkStore(settings.db_path),
        index=index,
        shiur_chunk_chars=settings.shiur_chunk_chars,
    )
