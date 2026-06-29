"""SQLite persistence for drafted-but-unapproved cross-text connections (expert gate).

Mirrors :class:`maayan.lexicon.suggestions.SuggestionStore`, for connections. A
:class:`~maayan.capture.populate.ConnectionSuggestion` sits here as ``pending`` until an
expert approves it, at which point it becomes an indexed ``connection`` annotation. Same
DB file + ``IF NOT EXISTS`` discipline as the rest of the stores.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from maayan.capture.populate import ConnectionSuggestion

_SCHEMA = """
CREATE TABLE IF NOT EXISTS connection_suggestions (
    id                 TEXT PRIMARY KEY,
    query              TEXT NOT NULL,
    refs               TEXT NOT NULL,   -- json array
    books              TEXT NOT NULL,   -- json array
    statement          TEXT NOT NULL,
    source_refs        TEXT NOT NULL,   -- json array
    model              TEXT NOT NULL,
    supported          INTEGER NOT NULL DEFAULT 0,
    unsupported_claims TEXT NOT NULL,   -- json array
    status             TEXT NOT NULL DEFAULT 'pending',
    created_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conn_suggestions_status ON connection_suggestions(status);
"""


class ConnectionSuggestionStore:
    """Stores drafted connection suggestions and their review status."""

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def create(self, suggestion: ConnectionSuggestion) -> ConnectionSuggestion:
        self._conn.execute(
            "INSERT OR REPLACE INTO connection_suggestions (id, query, refs, books, statement, "
            "source_refs, model, supported, unsupported_claims, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                suggestion.id,
                suggestion.query,
                json.dumps(suggestion.refs, ensure_ascii=False),
                json.dumps(suggestion.books, ensure_ascii=False),
                suggestion.statement,
                json.dumps(suggestion.source_refs, ensure_ascii=False),
                suggestion.model,
                int(suggestion.supported),
                json.dumps(suggestion.unsupported_claims, ensure_ascii=False),
                suggestion.status,
                suggestion.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return suggestion

    def get(self, suggestion_id: str) -> ConnectionSuggestion | None:
        row = self._conn.execute(
            "SELECT * FROM connection_suggestions WHERE id = ?", (suggestion_id,)
        ).fetchone()
        return self._row_to_suggestion(row) if row else None

    def list(self, *, status: str | None = None) -> list[ConnectionSuggestion]:
        if status is None:
            rows = self._conn.execute("SELECT * FROM connection_suggestions ORDER BY created_at")
        else:
            rows = self._conn.execute(
                "SELECT * FROM connection_suggestions WHERE status = ? ORDER BY created_at",
                (status,),
            )
        return [self._row_to_suggestion(r) for r in rows]

    def set_status(self, suggestion_id: str, status: str) -> None:
        self._conn.execute(
            "UPDATE connection_suggestions SET status = ? WHERE id = ?", (status, suggestion_id)
        )
        self._conn.commit()

    def count(self, *, status: str | None = None) -> int:
        if status is None:
            cur = self._conn.execute("SELECT COUNT(*) AS n FROM connection_suggestions")
        else:
            cur = self._conn.execute(
                "SELECT COUNT(*) AS n FROM connection_suggestions WHERE status = ?", (status,)
            )
        return int(cur.fetchone()["n"])

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ConnectionSuggestionStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def _row_to_suggestion(row: sqlite3.Row) -> ConnectionSuggestion:
        return ConnectionSuggestion(
            id=row["id"],
            query=row["query"],
            refs=json.loads(row["refs"]),
            books=json.loads(row["books"]),
            statement=row["statement"],
            source_refs=json.loads(row["source_refs"]),
            model=row["model"],
            supported=bool(row["supported"]),
            unsupported_claims=json.loads(row["unsupported_claims"]),
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
