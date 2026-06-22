"""SQLite persistence for lexicon terms (same DB file as the rest).

A new table created with `IF NOT EXISTS`, so it layers onto an existing DB without
breaking sessions/annotations/threads/developments.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from maayan.corpus.normalize import fold_surface
from maayan.lexicon.models import Term, TermType

_SCHEMA = """
CREATE TABLE IF NOT EXISTS terms (
    id            TEXT PRIMARY KEY,
    canonical     TEXT NOT NULL,
    surface_forms TEXT NOT NULL,   -- json array
    term_type     TEXT NOT NULL,
    definition    TEXT NOT NULL,
    related_terms TEXT NOT NULL,   -- json array
    source_refs   TEXT NOT NULL,   -- json array
    gematria      INTEGER,
    sacred        INTEGER NOT NULL DEFAULT 0,
    author        TEXT NOT NULL
);
"""


class TermStore:
    """Stores lexicon terms; finds them by tolerant surface-form match."""

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def create_term(self, term: Term) -> Term:
        self._conn.execute(
            "INSERT OR REPLACE INTO terms (id, canonical, surface_forms, term_type, "
            "definition, related_terms, source_refs, gematria, sacred, author) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                term.id,
                term.canonical,
                json.dumps(term.surface_forms, ensure_ascii=False),
                term.term_type,
                term.definition,
                json.dumps(term.related_terms, ensure_ascii=False),
                json.dumps(term.source_refs, ensure_ascii=False),
                term.gematria,
                int(term.sacred),
                term.author,
            ),
        )
        self._conn.commit()
        return term

    def get_term(self, term_id: str) -> Term | None:
        row = self._conn.execute("SELECT * FROM terms WHERE id = ?", (term_id,)).fetchone()
        return self._row_to_term(row) if row else None

    def list_terms(self) -> list[Term]:
        return [self._row_to_term(r) for r in self._conn.execute(
            "SELECT * FROM terms ORDER BY canonical"
        )]

    def find_by_surface_form(self, query: str) -> list[Term]:
        """All terms with a surface form (or canonical) that folds equal to `query`."""
        target = fold_surface(query)
        out = []
        for term in self.list_terms():
            forms = [term.canonical, *term.surface_forms]
            if any(fold_surface(f) == target for f in forms):
                out.append(term)
        return out

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> TermStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def _row_to_term(row: sqlite3.Row) -> Term:
        term_type: TermType = row["term_type"]
        return Term(
            id=row["id"],
            canonical=row["canonical"],
            surface_forms=json.loads(row["surface_forms"]),
            term_type=term_type,
            definition=row["definition"],
            related_terms=json.loads(row["related_terms"]),
            source_refs=json.loads(row["source_refs"]),
            gematria=row["gematria"],
            sacred=bool(row["sacred"]),
            author=row["author"],
        )
