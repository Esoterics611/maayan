"""Transcription orchestration: store audio, enqueue a job, run it off-thread.

`run_job` is what FastAPI BackgroundTasks calls after the response is sent — it marks
the job running, transcribes, persists the transcript, and marks the job done (or
error). No `time.sleep`/blocking wait: the UI polls the job row for progress. All
collaborators are injected so tests use FakeTranscriber + in-memory stores.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from maayan.audio.models import AudioAsset
from maayan.audio.store import AudioStore
from maayan.clock import Clock
from maayan.transcribe.base import Transcriber
from maayan.transcribe.models import Transcript, TranscriptionJob
from maayan.transcribe.store import TranscriptionStore


class TranscriptionService:
    """Stores recordings and runs transcription jobs the UI can poll."""

    def __init__(
        self,
        transcriber: Transcriber,
        audio_store: AudioStore,
        store: TranscriptionStore,
        clock: Clock,
        *,
        audio_dir: str,
    ) -> None:
        self._transcriber = transcriber
        self._audio = audio_store
        self._store = store
        self._clock = clock
        self._audio_dir = audio_dir

    # -- audio ---------------------------------------------------------------
    def store_audio(
        self, source_path: str | Path, *, owner: str, original_filename: str | None = None
    ) -> AudioAsset:
        return self._audio.store_file(
            source_path, owner=owner, audio_dir=self._audio_dir,
            original_filename=original_filename,
        )

    def get_audio(self, audio_id: str) -> AudioAsset | None:
        return self._audio.get(audio_id)

    # -- jobs ----------------------------------------------------------------
    def enqueue(self, audio_id: str) -> TranscriptionJob:
        now = self._clock.now()
        job = TranscriptionJob(
            id=str(uuid.uuid4()), audio_id=audio_id, status="queued",
            created_at=now, updated_at=now,
        )
        return self._store.save_job(job)

    def get_job(self, job_id: str) -> TranscriptionJob | None:
        return self._store.get_job(job_id)

    def get_transcript(self, transcript_id: str) -> Transcript | None:
        return self._store.get_transcript(transcript_id)

    def run_job(self, job_id: str) -> None:
        """Background worker: transcribe the job's audio. Any failure → status=error."""
        job = self._store.get_job(job_id)
        if job is None:
            return
        self._store.save_job(
            job.model_copy(update={"status": "running", "progress": 0.1,
                                   "updated_at": self._clock.now()})
        )
        try:
            asset = self._audio.get(job.audio_id)
            if asset is None:
                raise ValueError(f"audio asset {job.audio_id} not found")
            transcript = self._transcriber.transcribe(Path(asset.path))
            transcript = transcript.model_copy(update={"audio_id": asset.id})
            self._store.save_transcript(transcript)
            self._store.save_job(
                job.model_copy(update={
                    "status": "done", "progress": 1.0, "transcript_id": transcript.id,
                    "updated_at": self._clock.now(),
                })
            )
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI as an error job
            self._store.save_job(
                job.model_copy(update={"status": "error", "error": str(exc),
                                       "updated_at": self._clock.now()})
            )
