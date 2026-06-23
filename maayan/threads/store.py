"""SQLite persistence for topic threads + their turns (same DB file as chunks).

New tables only, created with `IF NOT EXISTS`, so this layers onto an existing DB
without breaking sessions/annotations. Pure persistence — no clock, no business
logic: timestamps arrive already set on the models (the service owns the Clock).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from maayan.threads.models import Thread, ThreadTurn, TurnType

_SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS thread_turns (
    id         TEXT PRIMARY KEY,
    thread_id  TEXT NOT NULL,
    ordinal    INTEGER NOT NULL,
    turn_type  TEXT NOT NULL,
    timestamp  TEXT NOT NULL,
    author     TEXT NOT NULL,
    record_id  TEXT,
    text       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_thread_turns_thread ON thread_turns(thread_id, ordinal);
"""


class ThreadStore:
    """Stores threads and their ordered turns."""

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: shared safely across FastAPI worker threads
        # (Python 3.12 sqlite3 is serialized). See corpus/store.py.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- threads -------------------------------------------------------------
    def create_thread(self, thread: Thread) -> Thread:
        self._conn.execute(
            "INSERT OR REPLACE INTO threads (id, title, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (
                thread.id,
                thread.title,
                thread.created_at.isoformat(),
                thread.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return thread

    def get_thread(self, thread_id: str) -> Thread | None:
        row = self._conn.execute(
            "SELECT * FROM threads WHERE id = ?", (thread_id,)
        ).fetchone()
        return self._row_to_thread(row) if row else None

    def list_threads(self, limit: int = 50) -> list[Thread]:
        rows = self._conn.execute(
            "SELECT * FROM threads ORDER BY updated_at DESC LIMIT ?", (limit,)
        )
        return [self._row_to_thread(r) for r in rows]

    def count(self) -> int:
        """Total number of threads (for the stats dashboard)."""
        return int(self._conn.execute("SELECT COUNT(*) AS n FROM threads").fetchone()["n"])

    # -- turns ---------------------------------------------------------------
    def append_turn(self, turn: ThreadTurn) -> ThreadTurn:
        """Persist a turn and bump the parent thread's updated_at to the turn's time."""
        self._conn.execute(
            "INSERT OR REPLACE INTO thread_turns (id, thread_id, ordinal, turn_type, "
            "timestamp, author, record_id, text) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                turn.id,
                turn.thread_id,
                turn.ordinal,
                turn.turn_type,
                turn.timestamp.isoformat(),
                turn.author,
                turn.record_id,
                turn.text,
            ),
        )
        self._conn.execute(
            "UPDATE threads SET updated_at = ? WHERE id = ?",
            (turn.timestamp.isoformat(), turn.thread_id),
        )
        self._conn.commit()
        return turn

    def get_turns(self, thread_id: str) -> list[ThreadTurn]:
        rows = self._conn.execute(
            "SELECT * FROM thread_turns WHERE thread_id = ? ORDER BY ordinal", (thread_id,)
        )
        return [self._row_to_turn(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ThreadStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- mapping -------------------------------------------------------------
    @staticmethod
    def _row_to_thread(row: sqlite3.Row) -> Thread:
        return Thread(
            id=row["id"],
            title=row["title"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _row_to_turn(row: sqlite3.Row) -> ThreadTurn:
        # turn_type is constrained at write time (TurnType); cast on read.
        turn_type: TurnType = row["turn_type"]
        return ThreadTurn(
            id=row["id"],
            thread_id=row["thread_id"],
            ordinal=row["ordinal"],
            turn_type=turn_type,
            timestamp=datetime.fromisoformat(row["timestamp"]),
            author=row["author"],
            record_id=row["record_id"],
            text=row["text"],
        )
