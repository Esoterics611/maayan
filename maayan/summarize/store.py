"""SQLite persistence for section summaries (same DB file as the rest)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import cast

from maayan.summarize.models import Summary, SummaryStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS summaries (
    id                 TEXT PRIMARY KEY,
    book               TEXT NOT NULL,
    parent_ref         TEXT NOT NULL,
    parent_label       TEXT NOT NULL,
    child_refs         TEXT NOT NULL,   -- json array
    text               TEXT NOT NULL,
    cited_refs         TEXT NOT NULL,   -- json array
    model              TEXT NOT NULL,
    supported          INTEGER NOT NULL,
    unsupported_claims TEXT NOT NULL,   -- json array
    status             TEXT NOT NULL,
    author             TEXT NOT NULL,
    created_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_summaries_status ON summaries(status);
CREATE INDEX IF NOT EXISTS idx_summaries_book   ON summaries(book);
"""


class SummaryStore:
    """Stores section summaries; the service owns the approval gate + indexing."""

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def save(self, summary: Summary) -> Summary:
        self._conn.execute(
            "INSERT OR REPLACE INTO summaries (id, book, parent_ref, parent_label, child_refs, "
            "text, cited_refs, model, supported, unsupported_claims, status, author, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                summary.id,
                summary.book,
                summary.parent_ref,
                summary.parent_label,
                json.dumps(summary.child_refs, ensure_ascii=False),
                summary.text,
                json.dumps(summary.cited_refs, ensure_ascii=False),
                summary.model,
                int(summary.supported),
                json.dumps(summary.unsupported_claims, ensure_ascii=False),
                summary.status,
                summary.author,
                summary.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return summary

    def get(self, summary_id: str) -> Summary | None:
        row = self._conn.execute(
            "SELECT * FROM summaries WHERE id = ?", (summary_id,)
        ).fetchone()
        return self._row_to_summary(row) if row else None

    def list(self, *, status: str | None = None, book: str | None = None) -> list[Summary]:
        clauses: list[str] = []
        params: list[object] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if book is not None:
            clauses.append("book = ?")
            params.append(book)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM summaries {where} ORDER BY parent_ref", params
        )
        return [self._row_to_summary(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SummaryStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def _row_to_summary(row: sqlite3.Row) -> Summary:
        return Summary(
            id=row["id"],
            book=row["book"],
            parent_ref=row["parent_ref"],
            parent_label=row["parent_label"],
            child_refs=json.loads(row["child_refs"]),
            text=row["text"],
            cited_refs=json.loads(row["cited_refs"]),
            model=row["model"],
            supported=bool(row["supported"]),
            unsupported_claims=json.loads(row["unsupported_claims"]),
            status=cast("SummaryStatus", row["status"]),
            author=row["author"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
