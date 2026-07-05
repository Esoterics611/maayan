"""SQLite persistence for sugya pages (same DB file as the rest).

One table, versioned by `page_key`: many rows can share a key (v1 superseded, v2
approved, v3 proposed…), so the store keeps the full history and the service asks it for
the current approved version when superseding.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import cast

from maayan.consolidate.models import SugyaPage, SugyaSection, SugyaStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sugya_pages (
    id         TEXT PRIMARY KEY,
    page_key   TEXT NOT NULL,
    concept    TEXT,
    title      TEXT NOT NULL,
    sections   TEXT NOT NULL,   -- json array of {title, body, cited_refs}
    cited_refs TEXT NOT NULL,   -- json array
    version    INTEGER NOT NULL,
    status     TEXT NOT NULL,
    author     TEXT NOT NULL,
    supersedes TEXT,
    chunk_ids  TEXT NOT NULL,   -- json array (the sugya chunks this version indexed)
    model      TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sugya_key    ON sugya_pages(page_key);
CREATE INDEX IF NOT EXISTS idx_sugya_status ON sugya_pages(status);
"""


class SugyaStore:
    """Stores sugya pages across versions; the service owns the gate + supersede policy."""

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def save_page(self, page: SugyaPage) -> SugyaPage:
        self._conn.execute(
            "INSERT OR REPLACE INTO sugya_pages (id, page_key, concept, title, sections, "
            "cited_refs, version, status, author, supersedes, chunk_ids, model, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                page.id,
                page.page_key,
                page.concept,
                page.title,
                json.dumps([s.model_dump() for s in page.sections], ensure_ascii=False),
                json.dumps(page.cited_refs, ensure_ascii=False),
                page.version,
                page.status,
                page.author,
                page.supersedes,
                json.dumps(page.chunk_ids, ensure_ascii=False),
                page.model,
                page.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return page

    def get_page(self, page_id: str) -> SugyaPage | None:
        row = self._conn.execute(
            "SELECT * FROM sugya_pages WHERE id = ?", (page_id,)
        ).fetchone()
        return self._row_to_page(row) if row else None

    def latest_approved(self, page_key: str) -> SugyaPage | None:
        """The current approved version for a key (the one a new version supersedes)."""
        row = self._conn.execute(
            "SELECT * FROM sugya_pages WHERE page_key = ? AND status = 'approved' "
            "ORDER BY version DESC LIMIT 1",
            (page_key,),
        ).fetchone()
        return self._row_to_page(row) if row else None

    def list_pages(self, *, status: str | None = None) -> list[SugyaPage]:
        if status is not None:
            rows = self._conn.execute(
                "SELECT * FROM sugya_pages WHERE status = ? ORDER BY created_at, id", (status,)
            )
        else:
            rows = self._conn.execute("SELECT * FROM sugya_pages ORDER BY created_at, id")
        return [self._row_to_page(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SugyaStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def _row_to_page(row: sqlite3.Row) -> SugyaPage:
        return SugyaPage(
            id=row["id"],
            page_key=row["page_key"],
            concept=row["concept"],
            title=row["title"],
            sections=[SugyaSection(**s) for s in json.loads(row["sections"])],
            cited_refs=json.loads(row["cited_refs"]),
            version=row["version"],
            status=cast("SugyaStatus", row["status"]),
            author=row["author"],
            supersedes=row["supersedes"],
            chunk_ids=json.loads(row["chunk_ids"]),
            model=row["model"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
