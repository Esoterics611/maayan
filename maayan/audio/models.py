"""Typed model for a stored audio asset."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AudioAsset(BaseModel):
    """A stored recording. `sha256` (of the original bytes) makes re-upload idempotent.

    `duration_s` / `sample_rate` are best-effort: they're filled when the stored file
    is a readable WAV, else left None (e.g. when ffmpeg is absent and a non-WAV upload
    is kept as-is).
    """

    id: str
    owner: str
    filename: str  # original upload name (for display)
    path: str  # where the stored (normalized) file lives on disk
    duration_s: float | None = None
    sample_rate: int | None = None
    sha256: str
    created_at: datetime
