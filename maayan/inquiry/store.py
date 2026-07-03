"""SQLite persistence for inquiry items (same DB file as the rest).

The store owns the dedupe/lifecycle rules the queue's trustworthiness rests on:
item ids are deterministic (kind + dedupe key), so regeneration UPSERTS an open
item in place — refreshed priority, same identity — and a terminal item
(answered/dismissed) is never resurrected. A dismissal teaches the queue.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from pydantic import TypeAdapter

from maayan.clock import Clock
from maayan.inquiry.models import InquiryItem, InquiryPayload

_SCHEMA = """
CREATE TABLE IF NOT EXISTS inquiries (
    id             TEXT PRIMARY KEY,
    kind           TEXT NOT NULL,
    title          TEXT NOT NULL,
    detail         TEXT NOT NULL,
    payload        TEXT NOT NULL,   -- json (typed per-kind, discriminated by "kind")
    priority       REAL NOT NULL,
    priority_parts TEXT NOT NULL,   -- json {component: value} — printed on the card
    status         TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    answered_at    TEXT,
    resolution     TEXT
);
CREATE INDEX IF NOT EXISTS idx_inquiries_status ON inquiries(status);
CREATE INDEX IF NOT EXISTS idx_inquiries_kind   ON inquiries(kind);
"""

_PAYLOAD = TypeAdapter[InquiryPayload](InquiryPayload)
_PARTS = TypeAdapter[dict[str, float]](dict[str, float])


class InquiryStore:
    """Stores inquiry items; owns upsert dedupe + answered/dismissed transitions."""

    def __init__(self, db_path: str, clock: Clock) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._clock = clock

    def upsert_open(self, item: InquiryItem) -> str:
        """Insert a drafted item, or refresh it in place if still open.

        Returns "created" | "refreshed" | "terminal". A terminal (answered or
        dismissed) id is left untouched — the Rav's decision is never undone by
        a regeneration run.
        """
        existing = self._conn.execute(
            "SELECT status FROM inquiries WHERE id = ?", (item.id,)
        ).fetchone()
        if existing is None:
            self._conn.execute(
                "INSERT INTO inquiries (id, kind, title, detail, payload, priority, "
                "priority_parts, status, created_at, answered_at, resolution) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item.id,
                    item.kind,
                    item.title,
                    item.detail,
                    _PAYLOAD.dump_json(item.payload).decode(),
                    item.priority,
                    _PARTS.dump_json(item.priority_parts).decode(),
                    item.status,
                    item.created_at.isoformat(),
                    item.answered_at.isoformat() if item.answered_at else None,
                    item.resolution,
                ),
            )
            self._conn.commit()
            return "created"
        if existing["status"] != "open":
            return "terminal"
        self._conn.execute(
            "UPDATE inquiries SET title = ?, detail = ?, payload = ?, priority = ?, "
            "priority_parts = ? WHERE id = ?",
            (
                item.title,
                item.detail,
                _PAYLOAD.dump_json(item.payload).decode(),
                item.priority,
                _PARTS.dump_json(item.priority_parts).decode(),
                item.id,
            ),
        )
        self._conn.commit()
        return "refreshed"

    def get(self, item_id: str) -> InquiryItem | None:
        row = self._conn.execute("SELECT * FROM inquiries WHERE id = ?", (item_id,)).fetchone()
        return self._row_to_item(row) if row else None

    def mark_answered(self, item_id: str, *, resolution: str) -> InquiryItem:
        """Close an item with what answering created (chunk/term/relation id)."""
        return self._close(item_id, status="answered", resolution=resolution)

    def mark_dismissed(self, item_id: str, *, resolution: str = "dismissed") -> InquiryItem:
        """Dismiss an item — a first-class outcome that teaches the queue."""
        return self._close(item_id, status="dismissed", resolution=resolution)

    def answered_since(self, since: datetime) -> list[InquiryItem]:
        """Items answered at/after `since` — the harvest line's raw material."""
        rows = self._conn.execute(
            "SELECT * FROM inquiries WHERE status = 'answered' AND answered_at >= ? "
            "ORDER BY answered_at",
            (since.isoformat(),),
        )
        return [self._row_to_item(r) for r in rows]

    def harvest_today(self) -> dict[str, int]:
        """Today's answered items by kind — the one metric in the entire UI.

        Deliberately not a chart, no history, resets daily: immediate, personal
        feedback that this session's hour crystallized into artifacts.
        """
        start = self._clock.now().replace(hour=0, minute=0, second=0, microsecond=0)
        counts: dict[str, int] = {}
        for item in self.answered_since(start):
            counts[item.kind] = counts.get(item.kind, 0) + 1
        return counts

    @property
    def clock(self) -> Clock:
        """The store's clock — shared with the generators at wiring time."""
        return self._clock

    # NOTE: defined last because the name shadows builtin `list` in annotations
    # that follow it inside the class body.
    def list(
        self, *, status: str | None = "open", kind: str | None = None
    ) -> list[InquiryItem]:
        """Items ordered by priority (desc), ties by recency (newest first)."""
        clauses: list[str] = []
        params: list[object] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM inquiries {where} ORDER BY priority DESC, created_at DESC",
            params,
        )
        return [self._row_to_item(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> InquiryStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- internals ---------------------------------------------------------------
    def _close(self, item_id: str, *, status: str, resolution: str) -> InquiryItem:
        item = self.get(item_id)
        if item is None:
            raise ValueError(f"No inquiry with id {item_id!r}.")
        if item.status != "open":
            raise ValueError(f"Inquiry {item_id!r} is already {item.status!r}.")
        self._conn.execute(
            "UPDATE inquiries SET status = ?, answered_at = ?, resolution = ? WHERE id = ?",
            (status, self._clock.now().isoformat(), resolution, item_id),
        )
        self._conn.commit()
        closed = self.get(item_id)
        assert closed is not None  # just updated under the same connection
        return closed

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> InquiryItem:
        return InquiryItem(
            id=row["id"],
            kind=row["kind"],
            title=row["title"],
            detail=row["detail"],
            payload=_PAYLOAD.validate_json(row["payload"]),
            priority=row["priority"],
            priority_parts=_PARTS.validate_json(row["priority_parts"]),
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            answered_at=(
                datetime.fromisoformat(row["answered_at"]) if row["answered_at"] else None
            ),
            resolution=row["resolution"],
        )
