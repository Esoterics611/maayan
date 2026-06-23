"""SQLite persistence for developments (same DB file as chunks/sessions/threads).

A new table created with `IF NOT EXISTS`, so it layers onto an existing DB. Pure
persistence — the service owns the Clock and all policy.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from maayan.develop.models import Development, DevelopmentStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS developments (
    id          TEXT PRIMARY KEY,
    thread_id   TEXT NOT NULL,
    seed_id     TEXT NOT NULL,
    author      TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    model       TEXT NOT NULL,
    status      TEXT NOT NULL,
    grounded    INTEGER NOT NULL,
    text        TEXT NOT NULL,
    cited_refs  TEXT NOT NULL,   -- json array
    grounded_in TEXT NOT NULL    -- json array
);
CREATE INDEX IF NOT EXISTS idx_developments_thread ON developments(thread_id);
"""


class DevelopmentStore:
    """Stores developments (proposed / approved / rejected)."""

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def save_development(self, dev: Development) -> Development:
        self._conn.execute(
            "INSERT OR REPLACE INTO developments (id, thread_id, seed_id, author, timestamp, "
            "model, status, grounded, text, cited_refs, grounded_in) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                dev.id,
                dev.thread_id,
                dev.seed_id,
                dev.author,
                dev.timestamp.isoformat(),
                dev.model,
                dev.status,
                int(dev.grounded),
                dev.text,
                json.dumps(dev.cited_refs, ensure_ascii=False),
                json.dumps(dev.grounded_in, ensure_ascii=False),
            ),
        )
        self._conn.commit()
        return dev

    def get_development(self, development_id: str) -> Development | None:
        row = self._conn.execute(
            "SELECT * FROM developments WHERE id = ?", (development_id,)
        ).fetchone()
        return self._row_to_development(row) if row else None

    def counts_by_status(self) -> dict[str, int]:
        """Development counts grouped by status (proposed/approved/rejected/retracted)."""
        rows = self._conn.execute(
            "SELECT status, COUNT(*) AS n FROM developments GROUP BY status"
        )
        return {r["status"]: int(r["n"]) for r in rows}

    def list_developments(self, thread_id: str | None = None) -> list[Development]:
        if thread_id is None:
            rows = self._conn.execute("SELECT * FROM developments ORDER BY timestamp")
        else:
            rows = self._conn.execute(
                "SELECT * FROM developments WHERE thread_id = ? ORDER BY timestamp", (thread_id,)
            )
        return [self._row_to_development(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> DevelopmentStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def _row_to_development(row: sqlite3.Row) -> Development:
        status: DevelopmentStatus = row["status"]
        return Development(
            id=row["id"],
            thread_id=row["thread_id"],
            seed_id=row["seed_id"],
            author=row["author"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            model=row["model"],
            status=status,
            grounded=bool(row["grounded"]),
            text=row["text"],
            cited_refs=json.loads(row["cited_refs"]),
            grounded_in=json.loads(row["grounded_in"]),
        )
