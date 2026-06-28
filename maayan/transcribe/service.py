"""Transcription orchestration: store audio, enqueue a job, run it off-thread.

`run_job` is what FastAPI BackgroundTasks calls after the response is sent — it marks
the job running, transcribes, persists the transcript, and marks the job done (or
error). No `time.sleep`/blocking wait: the UI polls the job row for progress. All
collaborators are injected so tests use FakeTranscriber + in-memory stores.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from maayan.audio.models import AudioAsset
from maayan.audio.store import AudioStore
from maayan.clock import Clock
from maayan.corpus.normalize import fold_surface
from maayan.transcribe.base import Transcriber
from maayan.transcribe.models import TermSuggestion, Transcript, TranscriptionJob
from maayan.transcribe.store import TranscriptionStore

if TYPE_CHECKING:
    from maayan.lexicon.service import TermService

# Punctuation trimmed off a token before lexicon folding (keeps Hebrew letters/nikkud;
# fold_surface itself drops nikkud + gershayim/quotes for matching).
_PUNCT = " \t\r\n.,;:!?\"'()[]{}…—–-־׃׀"


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
        terms: TermService | None = None,
    ) -> None:
        self._transcriber = transcriber
        self._audio = audio_store
        self._store = store
        self._clock = clock
        self._audio_dir = audio_dir
        self._terms = terms

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

    # -- review --------------------------------------------------------------
    def suggest_corrections(self, transcript: Transcript) -> Transcript:
        """Offer lexicon-based term fixes per segment (never overwrites text).

        Reuses the lexicon's own folding (gershayim/quote/nikkud-insensitive) so a
        registered surface form like ע"ב / עב is matched the same way it is elsewhere.
        Pure read: suggestions are computed here, not persisted.
        """
        if self._terms is None:
            return transcript
        # folded surface form → (canonical display form, term id)
        form_map: dict[str, tuple[str, str]] = {}
        for term in self._terms.list_terms():
            if getattr(term, "retracted", False):
                continue
            for surface in term.surface_forms:
                folded = fold_surface(surface)
                if folded:
                    form_map.setdefault(folded, (term.canonical, term.id))
        if not form_map:
            return transcript

        new_segments = []
        for seg in transcript.segments:
            suggestions: list[TermSuggestion] = []
            seen: set[str] = set()
            for raw in seg.text.split():
                token = raw.strip(_PUNCT)
                folded = fold_surface(token)
                if not folded or folded in seen or folded not in form_map:
                    continue
                canonical, term_id = form_map[folded]
                seen.add(folded)
                if token != canonical:  # already canonical → nothing to suggest
                    suggestions.append(
                        TermSuggestion(surface=token, canonical=canonical, term_id=term_id)
                    )
            new_segments.append(seg.model_copy(update={"suggestions": suggestions}))
        return transcript.model_copy(update={"segments": new_segments})

    def update_segment(
        self, transcript_id: str, idx: int, *,
        edited_text: str | None = None, speaker: str | None = None,
    ) -> Transcript:
        """Set a segment's edited_text and/or speaker (the human's correction)."""
        transcript = self._store.get_transcript(transcript_id)
        if transcript is None:
            raise ValueError("transcript not found")
        if idx < 0 or idx >= len(transcript.segments):
            raise ValueError("segment index out of range")
        updates: dict[str, str] = {}
        if edited_text is not None:
            updates["edited_text"] = edited_text
        if speaker is not None:
            updates["speaker"] = speaker
        segments = list(transcript.segments)
        segments[idx] = segments[idx].model_copy(update=updates)
        return self._store.save_transcript(transcript.model_copy(update={"segments": segments}))

    def mark_reviewed(self, transcript_id: str) -> Transcript:
        """Flip status to 'reviewed' (the human gate before corpus ingestion in Prompt 28)."""
        transcript = self._store.get_transcript(transcript_id)
        if transcript is None:
            raise ValueError("transcript not found")
        return self._store.save_transcript(transcript.model_copy(update={"status": "reviewed"}))
