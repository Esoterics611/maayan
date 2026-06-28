"""Transcriber interface.

A `Transcriber` turns an audio file into a timestamped `Transcript`. Whisper (local)
and, later, a cloud backend both implement it; callers depend only on this protocol,
so the backend is swapped via config with no other code changes (cf. `generate/`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from maayan.transcribe.models import Transcript


@runtime_checkable
class Transcriber(Protocol):
    """Produces a timestamped transcript from an audio file."""

    def transcribe(self, audio_path: Path, lang: str | None = None) -> Transcript:
        """Transcribe `audio_path`; `lang` overrides the configured default."""
        ...
