"""SQLite persistence for study programs (same DB file as the rest).

Two tables, both `IF NOT EXISTS` — the program (its resumable cursor + running funnel)
and one row per processed unit (the report's rows). Writes are idempotent upserts, so a
crash-and-resume re-processing a unit overwrites its row rather than duplicating it.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import cast

from maayan.agent.program_models import (
    ProgramCounts,
    ProgramStatus,
    ProgramTask,
    StudyProgram,
    UnitResult,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS study_programs (
    id            TEXT PRIMARY KEY,
    book          TEXT NOT NULL,
    task          TEXT NOT NULL,
    cursor        INTEGER NOT NULL,
    total_units   INTEGER NOT NULL,
    status        TEXT NOT NULL,
    drafted       INTEGER NOT NULL,
    passed_checks INTEGER NOT NULL,
    queued        INTEGER NOT NULL,
    model_calls   INTEGER NOT NULL,
    model         TEXT NOT NULL,
    author        TEXT NOT NULL,
    started_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS study_program_units (
    program_id    TEXT NOT NULL,
    unit_index    INTEGER NOT NULL,
    label         TEXT NOT NULL,
    ref           TEXT NOT NULL,
    drafted       INTEGER NOT NULL,
    passed_checks INTEGER NOT NULL,
    queued        INTEGER NOT NULL,
    model_calls   INTEGER NOT NULL,
    PRIMARY KEY (program_id, unit_index)
);
CREATE INDEX IF NOT EXISTS idx_program_units ON study_program_units(program_id);
"""


class ProgramStore:
    """Stores study programs + their per-unit results; idempotent upserts throughout."""

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- programs ----------------------------------------------------------------
    def save_program(self, program: StudyProgram) -> StudyProgram:
        self._conn.execute(
            "INSERT OR REPLACE INTO study_programs (id, book, task, cursor, total_units, "
            "status, drafted, passed_checks, queued, model_calls, model, author, "
            "started_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                program.id,
                program.book,
                program.task,
                program.cursor,
                program.total_units,
                program.status,
                program.counts.drafted,
                program.counts.passed_checks,
                program.counts.queued,
                program.counts.model_calls,
                program.model,
                program.author,
                program.started_at.isoformat(),
                program.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return program

    def get_program(self, program_id: str) -> StudyProgram | None:
        row = self._conn.execute(
            "SELECT * FROM study_programs WHERE id = ?", (program_id,)
        ).fetchone()
        return self._row_to_program(row) if row else None

    def list_programs(self) -> list[StudyProgram]:
        rows = self._conn.execute("SELECT * FROM study_programs ORDER BY started_at, id")
        return [self._row_to_program(r) for r in rows]

    # -- unit results ------------------------------------------------------------
    def save_unit_result(self, program_id: str, result: UnitResult) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO study_program_units (program_id, unit_index, label, "
            "ref, drafted, passed_checks, queued, model_calls) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                program_id,
                result.unit_index,
                result.label,
                result.ref,
                result.counts.drafted,
                result.counts.passed_checks,
                result.counts.queued,
                result.counts.model_calls,
            ),
        )
        self._conn.commit()

    def unit_results(self, program_id: str) -> list[UnitResult]:
        rows = self._conn.execute(
            "SELECT * FROM study_program_units WHERE program_id = ? ORDER BY unit_index",
            (program_id,),
        )
        return [self._row_to_unit(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ProgramStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- mapping -----------------------------------------------------------------
    @staticmethod
    def _row_to_program(row: sqlite3.Row) -> StudyProgram:
        return StudyProgram(
            id=row["id"],
            book=row["book"],
            task=cast("ProgramTask", row["task"]),
            cursor=row["cursor"],
            total_units=row["total_units"],
            status=cast("ProgramStatus", row["status"]),
            counts=ProgramCounts(
                drafted=row["drafted"],
                passed_checks=row["passed_checks"],
                queued=row["queued"],
                model_calls=row["model_calls"],
            ),
            model=row["model"],
            author=row["author"],
            started_at=datetime.fromisoformat(row["started_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _row_to_unit(row: sqlite3.Row) -> UnitResult:
        return UnitResult(
            unit_index=row["unit_index"],
            label=row["label"],
            ref=row["ref"],
            counts=ProgramCounts(
                drafted=row["drafted"],
                passed_checks=row["passed_checks"],
                queued=row["queued"],
                model_calls=row["model_calls"],
            ),
        )
