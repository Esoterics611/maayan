"""SQLite persistence for quick-capture inbox items (same DB file as chunks).

Pure storage: it parks captured thoughts and records when one is moved into a thread.
Time + ids come from the caller (the service uses the injected `Clock`); this layer
just reads/writes rows (cf. `audio/store.py`).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from maayan.inbox.models import InboxItem

_SCHEMA = """
CREATE TABLE IF NOT EXISTS inbox_items (
    id         TEXT PRIMARY KEY,
    author     TEXT NOT NULL,
    text       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'open',
    thread_id  TEXT,
    record_id  TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_inbox_status ON inbox_items(status);
"""


class InboxStore:
    """Stores inbox items and their move-to-thread lifecycle."""

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: shared across FastAPI worker threads (see corpus/store.py).
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def save(self, item: InboxItem) -> InboxItem:
        self._conn.execute(
            "INSERT OR REPLACE INTO inbox_items (id, author, text, status, thread_id, "
            "record_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                item.id, item.author, item.text, item.status,
                item.thread_id, item.record_id, item.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return item

    def get(self, item_id: str) -> InboxItem | None:
        row = self._conn.execute(
            "SELECT * FROM inbox_items WHERE id = ?", (item_id,)
        ).fetchone()
        return self._row_to_item(row) if row else None

    def list_open(self, limit: int = 100) -> list[InboxItem]:
        rows = self._conn.execute(
            "SELECT * FROM inbox_items WHERE status = 'open' "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_item(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> InboxStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> InboxItem:
        return InboxItem(
            id=row["id"],
            author=row["author"],
            text=row["text"],
            status=row["status"],
            thread_id=row["thread_id"],
            record_id=row["record_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
