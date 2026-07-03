"""SQLite persistence for study traces (same DB file as the rest).

A trace is stored whole (JSON of the typed model) — it is a document, not a
query target; `GET /api/traces/{id}` and `--show-trace` read it back as one.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from maayan.agent.models import StudyTrace

_SCHEMA = """
CREATE TABLE IF NOT EXISTS study_traces (
    id         TEXT PRIMARY KEY,
    question   TEXT NOT NULL,
    trace      TEXT NOT NULL,    -- json (the full StudyTrace)
    created_at TEXT NOT NULL
);
"""


class TraceStore:
    """Stores study traces — the chavrusa's notebooks."""

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def save(self, trace: StudyTrace) -> StudyTrace:
        self._conn.execute(
            "INSERT OR REPLACE INTO study_traces (id, question, trace, created_at) "
            "VALUES (?, ?, ?, ?)",
            (trace.id, trace.question, trace.model_dump_json(), trace.created_at.isoformat()),
        )
        self._conn.commit()
        return trace

    def get(self, trace_id: str) -> StudyTrace | None:
        row = self._conn.execute(
            "SELECT trace FROM study_traces WHERE id = ?", (trace_id,)
        ).fetchone()
        return StudyTrace.model_validate_json(row["trace"]) if row else None

    def list_recent(self, limit: int = 20) -> list[StudyTrace]:
        rows = self._conn.execute(
            "SELECT trace FROM study_traces ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [StudyTrace.model_validate_json(r["trace"]) for r in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> TraceStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
