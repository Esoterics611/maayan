"""Local Whisper transcription via faster-whisper (CTranslate2).

Heavy + GPU-capable, so `faster_whisper` is imported lazily (only when a transcript
is actually requested) and lives under the `ml` extra — the core skeleton and unit
tests stay light. Unit tests use `FakeTranscriber`; this is never called in CI.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from maayan.clock import Clock
from maayan.transcribe.models import Transcript, TranscriptSegment


class WhisperTranscriber:
    """faster-whisper backend. Word/segment timestamps; device + compute from config."""

    def __init__(
        self,
        model_name: str,
        *,
        clock: Clock,
        device: str = "auto",
        compute_type: str = "float16",
        default_lang: str = "he",
        diarize: bool = False,
    ) -> None:
        self._model_name = model_name
        self._clock = clock
        self._device = device
        self._compute_type = compute_type
        self._default_lang = default_lang
        self._diarize = diarize
        self._model: object | None = None  # lazily constructed on first use

    def _resolve_device(self) -> tuple[str, str]:
        """Pick (device, compute_type), honoring 'auto' and CPU's float16 limitation."""
        device = self._device
        if device == "auto":
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:  # noqa: BLE001 - torch absent → assume CPU
                device = "cpu"
        compute_type = self._compute_type
        if device == "cpu" and compute_type == "float16":
            compute_type = "int8"  # CTranslate2 CPU has no float16
        return device, compute_type

    def _ensure_model(self) -> object:
        if self._model is None:
            from faster_whisper import WhisperModel

            device, compute_type = self._resolve_device()
            self._model = WhisperModel(
                self._model_name, device=device, compute_type=compute_type
            )
        return self._model

    def transcribe(self, audio_path: Path, lang: str | None = None) -> Transcript:
        model = self._ensure_model()
        language = lang or self._default_lang
        segments_iter, info = model.transcribe(  # type: ignore[attr-defined]
            str(audio_path), language=language, word_timestamps=True
        )
        segments = [
            TranscriptSegment(
                idx=i, start_s=float(s.start), end_s=float(s.end), text=s.text.strip()
            )
            for i, s in enumerate(segments_iter)
        ]
        return Transcript(
            id=str(uuid.uuid4()),
            lang=language or getattr(info, "language", "") or self._default_lang,
            backend="whisper",
            model=self._model_name,
            segments=segments,
            created_at=self._clock.now(),
        )
