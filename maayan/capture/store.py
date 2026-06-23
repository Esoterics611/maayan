"""SQLite persistence for sessions + annotations (same DB file as chunks)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from maayan.capture.models import Annotation, Session

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id             TEXT PRIMARY KEY,
    timestamp      TEXT NOT NULL,
    question       TEXT NOT NULL,
    retrieved_refs TEXT NOT NULL,   -- json array
    answer_text    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS annotations (
    id           TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    timestamp    TEXT NOT NULL,
    author       TEXT NOT NULL,
    kind         TEXT NOT NULL,
    body         TEXT NOT NULL,
    linked_refs  TEXT NOT NULL,     -- json array
    move         TEXT,
    directive    TEXT,                          -- seed: "now develop X", kept out of embed text
    opens_aspect INTEGER NOT NULL DEFAULT 0     -- 1 = a seed that leads a new aspect
);
CREATE INDEX IF NOT EXISTS idx_annotations_session ON annotations(session_id);
"""

# Columns added after the original schema shipped. Applied idempotently so existing
# DBs upgrade in place without breaking (a fresh DB already has them from _SCHEMA).
_MIGRATIONS = (
    "ALTER TABLE annotations ADD COLUMN directive TEXT",
    "ALTER TABLE annotations ADD COLUMN opens_aspect INTEGER NOT NULL DEFAULT 0",
)


class CaptureStore:
    """Stores sessions and annotations."""

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: shared safely across FastAPI worker threads
        # (Python 3.12 sqlite3 is serialized). See corpus/store.py.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """Apply additive column migrations to pre-existing DBs (idempotent)."""
        for statement in _MIGRATIONS:
            try:
                self._conn.execute(statement)
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc):
                    raise

    # -- sessions ------------------------------------------------------------
    def save_session(self, session: Session) -> Session:
        self._conn.execute(
            "INSERT OR REPLACE INTO sessions (id, timestamp, question, retrieved_refs, "
            "answer_text) VALUES (?, ?, ?, ?, ?)",
            (
                session.id,
                session.timestamp.isoformat(),
                session.question,
                json.dumps(session.retrieved_refs, ensure_ascii=False),
                session.answer_text,
            ),
        )
        self._conn.commit()
        return session

    def get_session(self, session_id: str) -> Session | None:
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return self._row_to_session(row) if row else None

    def list_sessions(self, limit: int = 50) -> list[Session]:
        rows = self._conn.execute(
            "SELECT * FROM sessions ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [self._row_to_session(r) for r in rows]

    # -- annotations ---------------------------------------------------------
    def save_annotation(self, annotation: Annotation) -> Annotation:
        self._conn.execute(
            "INSERT OR REPLACE INTO annotations (id, session_id, timestamp, author, kind, "
            "body, linked_refs, move, directive, opens_aspect) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                annotation.id,
                annotation.session_id,
                annotation.timestamp.isoformat(),
                annotation.author,
                annotation.kind,
                annotation.body,
                json.dumps(annotation.linked_refs, ensure_ascii=False),
                annotation.move,
                annotation.directive,
                int(annotation.opens_aspect),
            ),
        )
        self._conn.commit()
        return annotation

    def get_annotations(self, session_id: str) -> list[Annotation]:
        rows = self._conn.execute(
            "SELECT * FROM annotations WHERE session_id = ? ORDER BY timestamp", (session_id,)
        )
        return [self._row_to_annotation(r) for r in rows]

    def get_annotation(self, annotation_id: str) -> Annotation | None:
        """Fetch one contribution by its id (used to develop a seed)."""
        row = self._conn.execute(
            "SELECT * FROM annotations WHERE id = ?", (annotation_id,)
        ).fetchone()
        return self._row_to_annotation(row) if row else None

    def counts_by_author(self) -> dict[str, int]:
        """Contribution counts grouped by author (for the stats dashboard)."""
        rows = self._conn.execute(
            "SELECT author, COUNT(*) AS n FROM annotations GROUP BY author ORDER BY author"
        )
        return {r["author"]: int(r["n"]) for r in rows}

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> CaptureStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- mapping -------------------------------------------------------------
    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> Session:
        return Session(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            question=row["question"],
            retrieved_refs=json.loads(row["retrieved_refs"]),
            answer_text=row["answer_text"],
        )

    @staticmethod
    def _row_to_annotation(row: sqlite3.Row) -> Annotation:
        return Annotation(
            id=row["id"],
            session_id=row["session_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            author=row["author"],
            kind=row["kind"],
            body=row["body"],
            linked_refs=json.loads(row["linked_refs"]),
            move=row["move"],
            directive=row["directive"],
            opens_aspect=bool(row["opens_aspect"]),
        )
