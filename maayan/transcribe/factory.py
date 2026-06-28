"""Transcriber factory — selects the backend from config (DI seam).

`TRANSCRIBE_BACKEND` decides which transcriber is injected; no other code changes
when swapping local Whisper ↔ a cloud ASR. `fake` is the deterministic test/offline
backend (also selected by the CLI `--mock` flag).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from maayan.clock import Clock, SystemClock
from maayan.config import Settings
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
    settings: Settings, *, clock: Clock | None = None
) -> TranscriptionService:
    """Assemble the TranscriptionService wired to the same DB + audio dir (DI at the edge)."""
    from maayan.audio.store import AudioStore
    from maayan.transcribe.service import TranscriptionService
    from maayan.transcribe.store import TranscriptionStore

    clock = clock or SystemClock()
    return TranscriptionService(
        build_transcriber(settings, clock=clock),
        AudioStore(settings.db_path, clock),
        TranscriptionStore(settings.db_path),
        clock,
        audio_dir=settings.audio_dir,
    )
