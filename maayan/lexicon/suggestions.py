"""SQLite persistence for drafted-but-unapproved lexicon entries (the expert gate).

A `TermSuggestion` is what the auto-populator produces: a definition DRAFTED by a
model strictly from retrieved corpus sources (with citations), not yet trusted. It
sits in this queue with `status="pending"` until the expert approves it — at which
point it becomes a real `Term` via `TermService.add_term` and only then enters
retrieval. Same DB file + `IF NOT EXISTS` discipline as the rest of the stores, so
it layers on without disturbing existing tables.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from maayan.lexicon.populate import TermSuggestion

_SCHEMA = """
CREATE TABLE IF NOT EXISTS term_suggestions (
    id                 TEXT PRIMARY KEY,
    canonical          TEXT NOT NULL,
    surface_forms      TEXT NOT NULL,   -- json array
    term_type          TEXT NOT NULL,
    definition         TEXT NOT NULL,
    source_refs        TEXT NOT NULL,   -- json array
    related_terms      TEXT NOT NULL,   -- json array
    gematria           INTEGER,
    sacred             INTEGER NOT NULL DEFAULT 0,
    origin             TEXT NOT NULL,
    model              TEXT NOT NULL,
    supported          INTEGER NOT NULL DEFAULT 0,
    unsupported_claims TEXT NOT NULL,   -- json array
    status             TEXT NOT NULL DEFAULT 'pending',
    created_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_suggestions_status ON term_suggestions(status);
"""


class SuggestionStore:
    """Stores drafted term suggestions and their review status."""

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def create(self, suggestion: TermSuggestion) -> TermSuggestion:
        self._conn.execute(
            "INSERT OR REPLACE INTO term_suggestions (id, canonical, surface_forms, "
            "term_type, definition, source_refs, related_terms, gematria, sacred, origin, "
            "model, supported, unsupported_claims, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                suggestion.id,
                suggestion.canonical,
                json.dumps(suggestion.surface_forms, ensure_ascii=False),
                suggestion.term_type,
                suggestion.definition,
                json.dumps(suggestion.source_refs, ensure_ascii=False),
                json.dumps(suggestion.related_terms, ensure_ascii=False),
                suggestion.gematria,
                int(suggestion.sacred),
                suggestion.origin,
                suggestion.model,
                int(suggestion.supported),
                json.dumps(suggestion.unsupported_claims, ensure_ascii=False),
                suggestion.status,
                suggestion.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return suggestion

    def get(self, suggestion_id: str) -> TermSuggestion | None:
        row = self._conn.execute(
            "SELECT * FROM term_suggestions WHERE id = ?", (suggestion_id,)
        ).fetchone()
        return self._row_to_suggestion(row) if row else None

    def list(self, *, status: str | None = None) -> list[TermSuggestion]:
        if status is None:
            rows = self._conn.execute("SELECT * FROM term_suggestions ORDER BY created_at")
        else:
            rows = self._conn.execute(
                "SELECT * FROM term_suggestions WHERE status = ? ORDER BY created_at", (status,)
            )
        return [self._row_to_suggestion(r) for r in rows]

    def set_status(self, suggestion_id: str, status: str) -> None:
        self._conn.execute(
            "UPDATE term_suggestions SET status = ? WHERE id = ?", (status, suggestion_id)
        )
        self._conn.commit()

    def count(self, *, status: str | None = None) -> int:
        if status is None:
            cur = self._conn.execute("SELECT COUNT(*) AS n FROM term_suggestions")
        else:
            cur = self._conn.execute(
                "SELECT COUNT(*) AS n FROM term_suggestions WHERE status = ?", (status,)
            )
        return int(cur.fetchone()["n"])

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SuggestionStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def _row_to_suggestion(row: sqlite3.Row) -> TermSuggestion:
        return TermSuggestion(
            id=row["id"],
            canonical=row["canonical"],
            surface_forms=json.loads(row["surface_forms"]),
            term_type=row["term_type"],
            definition=row["definition"],
            source_refs=json.loads(row["source_refs"]),
            related_terms=json.loads(row["related_terms"]),
            gematria=row["gematria"],
            sacred=bool(row["sacred"]),
            origin=row["origin"],
            model=row["model"],
            supported=bool(row["supported"]),
            unsupported_claims=json.loads(row["unsupported_claims"]),
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
