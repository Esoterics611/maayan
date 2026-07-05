"""AskLog: question/refusal telemetry (SQLite, same DB file as the rest).

Today a refused question evaporates — the system's own confession of ignorance,
thrown away. The AskLog keeps it: every ask records the question, whether the
gate refused, and the top relevance score, so the refused-question generator can
cluster them into inquiries for the Rav. No new PII: `user` mirrors the existing
auth identity (None when auth is off). Recording is called at the edges (CLI /
UI routes) right where the session is captured; `ASK_LOG_ENABLED` gates it.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from maayan.clock import Clock
from maayan.inquiry.models import AskRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ask_log (
    id         TEXT PRIMARY KEY,
    question   TEXT NOT NULL,
    refused    INTEGER NOT NULL,
    top_score  REAL NOT NULL,
    session_id TEXT,
    thread_id  TEXT,
    user       TEXT,
    cited_refs TEXT NOT NULL DEFAULT '[]',   -- json array (chazarah's never-retrieved join)
    timestamp  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ask_log_refused ON ask_log(refused);
"""


class AskLog:
    """Persists ask telemetry; the clock is injected (no direct time reads)."""

    def __init__(self, db_path: str, clock: Clock) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()
        self._clock = clock

    def _migrate(self) -> None:
        """Add `cited_refs` in place for DBs created before it existed (default '[]')."""
        existing = {row["name"] for row in self._conn.execute("PRAGMA table_info(ask_log)")}
        if "cited_refs" not in existing:
            self._conn.execute(
                "ALTER TABLE ask_log ADD COLUMN cited_refs TEXT NOT NULL DEFAULT '[]'"
            )

    def record(
        self,
        *,
        question: str,
        refused: bool,
        top_score: float,
        session_id: str | None = None,
        thread_id: str | None = None,
        user: str | None = None,
        cited_refs: Sequence[str] = (),
    ) -> AskRecord:
        record = AskRecord(
            id=str(uuid.uuid4()),
            question=question,
            refused=refused,
            top_score=top_score,
            session_id=session_id,
            thread_id=thread_id,
            user=user,
            cited_refs=list(cited_refs),
            timestamp=self._clock.now(),
        )
        self._conn.execute(
            "INSERT INTO ask_log (id, question, refused, top_score, session_id, thread_id, "
            "user, cited_refs, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.id,
                record.question,
                int(record.refused),
                record.top_score,
                record.session_id,
                record.thread_id,
                record.user,
                json.dumps(record.cited_refs, ensure_ascii=False),
                record.timestamp.isoformat(),
            ),
        )
        self._conn.commit()
        return record

    def cited_refs_ever(self) -> set[str]:
        """Every ref any logged answer cited — chazarah's 'has been retrieved' set."""
        seen: set[str] = set()
        for row in self._conn.execute("SELECT cited_refs FROM ask_log"):
            seen.update(json.loads(row["cited_refs"]))
        return seen

    def list_refused(self, *, limit: int | None = None) -> list[AskRecord]:
        sql = "SELECT * FROM ask_log WHERE refused = 1 ORDER BY timestamp"
        params: list[object] = []
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return [self._row_to_record(r) for r in self._conn.execute(sql, params)]

    def count(self, *, refused: bool | None = None) -> int:
        if refused is None:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM ask_log").fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM ask_log WHERE refused = ?", (int(refused),)
            ).fetchone()
        return int(row["n"])

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> AskLog:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> AskRecord:
        return AskRecord(
            id=row["id"],
            question=row["question"],
            refused=bool(row["refused"]),
            top_score=row["top_score"],
            session_id=row["session_id"],
            thread_id=row["thread_id"],
            user=row["user"],
            cited_refs=json.loads(row["cited_refs"]) if "cited_refs" in row.keys() else [],
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )
