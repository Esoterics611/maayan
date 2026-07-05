"""SQLite persistence for the chazarah schedule (same DB file as the rest).

One row per re-reviewable target, holding its spaced-repetition interval and next-review
date. Upserts are idempotent; `confirm` advances the interval and pushes the next review.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from maayan.clock import Clock
from maayan.consolidate.models import ChazarahSchedule

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chazarah_schedule (
    target_id        TEXT PRIMARY KEY,
    target_kind      TEXT NOT NULL,
    interval_days    REAL NOT NULL,
    next_review_at   TEXT NOT NULL,
    reviews          INTEGER NOT NULL,
    last_reviewed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_chazarah_next ON chazarah_schedule(next_review_at);
"""


class ScheduleStore:
    """Stores chazarah schedules; the scheduler owns the interval policy."""

    def __init__(self, db_path: str, clock: Clock) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._clock = clock

    def get(self, target_id: str) -> ChazarahSchedule | None:
        row = self._conn.execute(
            "SELECT * FROM chazarah_schedule WHERE target_id = ?", (target_id,)
        ).fetchone()
        return self._row_to_schedule(row) if row else None

    def save(self, schedule: ChazarahSchedule) -> ChazarahSchedule:
        self._conn.execute(
            "INSERT OR REPLACE INTO chazarah_schedule (target_id, target_kind, interval_days, "
            "next_review_at, reviews, last_reviewed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                schedule.target_id,
                schedule.target_kind,
                schedule.interval_days,
                schedule.next_review_at.isoformat(),
                schedule.reviews,
                schedule.last_reviewed_at.isoformat() if schedule.last_reviewed_at else None,
            ),
        )
        self._conn.commit()
        return schedule

    def ensure(
        self, target_id: str, target_kind: str, *, base_interval_days: float
    ) -> tuple[ChazarahSchedule, bool]:
        """Return (schedule, created). A new target is due now (next_review = now)."""
        existing = self.get(target_id)
        if existing is not None:
            return existing, False
        schedule = ChazarahSchedule(
            target_id=target_id,
            target_kind=target_kind,
            interval_days=base_interval_days,
            next_review_at=self._clock.now(),
            reviews=0,
        )
        return self.save(schedule), True

    def confirm(self, target_id: str, *, factor: float) -> ChazarahSchedule:
        """Record a re-review: multiply the interval and push the next review out."""
        schedule = self.get(target_id)
        if schedule is None:
            raise ValueError(f"No chazarah schedule for target {target_id!r}.")
        now = self._clock.now()
        interval = schedule.interval_days * factor
        return self.save(
            schedule.model_copy(
                update={
                    "interval_days": interval,
                    "next_review_at": now + timedelta(days=interval),
                    "reviews": schedule.reviews + 1,
                    "last_reviewed_at": now,
                }
            )
        )

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM chazarah_schedule").fetchone()
        return int(row["n"])

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ScheduleStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def _row_to_schedule(row: sqlite3.Row) -> ChazarahSchedule:
        return ChazarahSchedule(
            target_id=row["target_id"],
            target_kind=row["target_kind"],
            interval_days=row["interval_days"],
            next_review_at=datetime.fromisoformat(row["next_review_at"]),
            reviews=row["reviews"],
            last_reviewed_at=(
                datetime.fromisoformat(row["last_reviewed_at"])
                if row["last_reviewed_at"]
                else None
            ),
        )
