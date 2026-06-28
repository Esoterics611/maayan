"""SQLite persistence for transcripts + transcription jobs (same DB file as chunks).

One store, two tables (like CaptureStore's sessions + annotations): the async job row
the UI polls, and the transcript the finished job produces. Both round-trip the typed
pydantic models; segments are stored as a JSON blob.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from maayan.transcribe.models import Transcript, TranscriptionJob, TranscriptSegment

_SCHEMA = """
CREATE TABLE IF NOT EXISTS transcripts (
    id         TEXT PRIMARY KEY,
    audio_id   TEXT NOT NULL,
    lang       TEXT NOT NULL,
    backend    TEXT NOT NULL,
    model      TEXT NOT NULL,
    status     TEXT NOT NULL,
    segments   TEXT NOT NULL,          -- json array of TranscriptSegment
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transcription_jobs (
    id            TEXT PRIMARY KEY,
    audio_id      TEXT NOT NULL,
    status        TEXT NOT NULL,
    progress      REAL NOT NULL DEFAULT 0,
    transcript_id TEXT,
    error         TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
"""


class TranscriptionStore:
    """Persists transcripts and the jobs that produce them."""

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: shared across FastAPI worker threads (see corpus/store.py).
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- transcripts ---------------------------------------------------------
    def save_transcript(self, transcript: Transcript) -> Transcript:
        self._conn.execute(
            "INSERT OR REPLACE INTO transcripts (id, audio_id, lang, backend, model, status, "
            "segments, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                transcript.id, transcript.audio_id, transcript.lang, transcript.backend,
                transcript.model, transcript.status,
                json.dumps([s.model_dump() for s in transcript.segments], ensure_ascii=False),
                transcript.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return transcript

    def get_transcript(self, transcript_id: str) -> Transcript | None:
        row = self._conn.execute(
            "SELECT * FROM transcripts WHERE id = ?", (transcript_id,)
        ).fetchone()
        return self._row_to_transcript(row) if row else None

    # -- jobs ----------------------------------------------------------------
    def save_job(self, job: TranscriptionJob) -> TranscriptionJob:
        self._conn.execute(
            "INSERT OR REPLACE INTO transcription_jobs (id, audio_id, status, progress, "
            "transcript_id, error, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                job.id, job.audio_id, job.status, job.progress, job.transcript_id,
                job.error, job.created_at.isoformat(), job.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return job

    def get_job(self, job_id: str) -> TranscriptionJob | None:
        row = self._conn.execute(
            "SELECT * FROM transcription_jobs WHERE id = ?", (job_id,)
        ).fetchone()
        return self._row_to_job(row) if row else None

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> TranscriptionStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- mapping -------------------------------------------------------------
    @staticmethod
    def _row_to_transcript(row: sqlite3.Row) -> Transcript:
        return Transcript(
            id=row["id"],
            audio_id=row["audio_id"],
            lang=row["lang"],
            backend=row["backend"],
            model=row["model"],
            status=row["status"],
            segments=[TranscriptSegment(**s) for s in json.loads(row["segments"])],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> TranscriptionJob:
        return TranscriptionJob(
            id=row["id"],
            audio_id=row["audio_id"],
            status=row["status"],
            progress=row["progress"],
            transcript_id=row["transcript_id"],
            error=row["error"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
