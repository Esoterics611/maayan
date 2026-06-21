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
    move         TEXT
);
CREATE INDEX IF NOT EXISTS idx_annotations_session ON annotations(session_id);
"""


class CaptureStore:
    """Stores sessions and annotations."""

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

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
            "body, linked_refs, move) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                annotation.id,
                annotation.session_id,
                annotation.timestamp.isoformat(),
                annotation.author,
                annotation.kind,
                annotation.body,
                json.dumps(annotation.linked_refs, ensure_ascii=False),
                annotation.move,
            ),
        )
        self._conn.commit()
        return annotation

    def get_annotations(self, session_id: str) -> list[Annotation]:
        rows = self._conn.execute(
            "SELECT * FROM annotations WHERE session_id = ? ORDER BY timestamp", (session_id,)
        )
        return [self._row_to_annotation(r) for r in rows]

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
        )
