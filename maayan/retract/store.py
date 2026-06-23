"""SQLite persistence for retractions (same DB file as the rest).

A new table created with `IF NOT EXISTS`, so it layers onto an existing DB without
touching chunks/sessions/threads/developments/terms. Pure persistence — the service
owns the Clock and all policy.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from maayan.retract.models import Retraction

_SCHEMA = """
CREATE TABLE IF NOT EXISTS retractions (
    id        TEXT PRIMARY KEY,
    chunk_id  TEXT NOT NULL,
    ref       TEXT NOT NULL,
    source    TEXT NOT NULL,
    author    TEXT NOT NULL,
    reason    TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_retractions_chunk ON retractions(chunk_id);
"""


class RetractionStore:
    """Stores retraction audit records (who retracted what, when, and why)."""

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def save_retraction(self, retraction: Retraction) -> Retraction:
        self._conn.execute(
            "INSERT OR REPLACE INTO retractions "
            "(id, chunk_id, ref, source, author, reason, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                retraction.id,
                retraction.chunk_id,
                retraction.ref,
                retraction.source,
                retraction.author,
                retraction.reason,
                retraction.timestamp.isoformat(),
            ),
        )
        self._conn.commit()
        return retraction

    def get_retraction(self, retraction_id: str) -> Retraction | None:
        row = self._conn.execute(
            "SELECT * FROM retractions WHERE id = ?", (retraction_id,)
        ).fetchone()
        return self._row_to_retraction(row) if row else None

    def list_retractions(self) -> list[Retraction]:
        return [
            self._row_to_retraction(r)
            for r in self._conn.execute("SELECT * FROM retractions ORDER BY timestamp")
        ]

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) AS n FROM retractions").fetchone()["n"])

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> RetractionStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def _row_to_retraction(row: sqlite3.Row) -> Retraction:
        return Retraction(
            id=row["id"],
            chunk_id=row["chunk_id"],
            ref=row["ref"],
            source=row["source"],
            author=row["author"],
            reason=row["reason"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )
