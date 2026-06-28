"""A deterministic, dependency-free transcriber for tests and no-GPU demos.

`FakeTranscriber` returns fixed, ordered, timestamped segments derived from the
file name — enough to exercise the pipeline (store → transcribe → review → ingest)
without downloading Whisper. It satisfies the `Transcriber` protocol so it drops in
via DI, exactly like `HashingEmbedder` does for embeddings.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from maayan.clock import Clock
from maayan.transcribe.models import Transcript, TranscriptSegment


class FakeTranscriber:
    """Deterministic transcript output for tests/offline demos. Not real ASR."""

    def __init__(self, clock: Clock, *, default_lang: str = "he") -> None:
        self._clock = clock
        self._default_lang = default_lang

    def transcribe(self, audio_path: Path, lang: str | None = None) -> Transcript:
        stem = Path(audio_path).stem
        spans: list[tuple[float, float, str]] = [
            (0.0, 2.0, f"שיעור לדוגמה: {stem}"),
            (2.0, 4.5, "פתיחה על בירור נפש הבהמית"),
            (4.5, 7.0, "A sample English passage for mixed-language tests."),
        ]
        segments = [
            TranscriptSegment(idx=i, start_s=s, end_s=e, text=t)
            for i, (s, e, t) in enumerate(spans)
        ]
        return Transcript(
            id=str(uuid.uuid4()),
            lang=lang or self._default_lang,
            backend="fake",
            model="fake",
            segments=segments,
            created_at=self._clock.now(),
        )
