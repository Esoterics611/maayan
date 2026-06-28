"""Typed models for transcription (the spine corpus → embed → index reuses later).

`TranscriptSegment` carries the audio timestamps that let a cited shiur chunk
deep-link back to the moment in the recording (Prompt 28's "▶ play from 12:34").
`edited_text` holds the human's correction (Prompt 27) without losing the raw ASR.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# raw → reviewed (human edited) → approved (ingested as shiur corpus) | rejected.
TranscriptStatus = Literal["raw", "reviewed", "approved", "rejected"]

# queued → running → done | error. Polled by the UI; the work runs off the request.
JobStatus = Literal["queued", "running", "done", "error"]


class TranscriptSegment(BaseModel):
    """One timestamped span of speech."""

    idx: int
    start_s: float
    end_s: float
    speaker: str | None = None
    text: str
    edited_text: str | None = None

    @property
    def display_text(self) -> str:
        """The human-corrected text if present, else the raw ASR text."""
        return self.edited_text if self.edited_text is not None else self.text


class Transcript(BaseModel):
    """A recording's full transcript, plus its provenance + review status."""

    id: str
    audio_id: str = ""  # the AudioAsset it came from; set by the orchestrator
    lang: str
    backend: str
    model: str
    status: TranscriptStatus = "raw"
    segments: list[TranscriptSegment] = Field(default_factory=list)
    created_at: datetime


class TranscriptionJob(BaseModel):
    """An async transcription unit the UI polls. The work runs off the request thread
    (FastAPI BackgroundTasks); progress/status land here, never via a blocking wait."""

    id: str
    audio_id: str
    status: JobStatus = "queued"
    progress: float = 0.0
    transcript_id: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
