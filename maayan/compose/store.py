"""SQLite persistence for briefs + compositions (same DB file as the rest).

New tables created with `IF NOT EXISTS`, layering onto an existing DB. Pure
persistence — the service owns the Clock and all policy. Sections (and the brief's
scope/frameworks) are stored as JSON, mirroring how developments store their ref lists.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from maayan.compose.models import (
    Brief,
    Composition,
    CompositionStatus,
    ContentType,
    Section,
    SourceScope,
)
from maayan.corpus.models import Lang

_SCHEMA = """
CREATE TABLE IF NOT EXISTS briefs (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    intent          TEXT NOT NULL,
    content_type    TEXT NOT NULL,
    lang            TEXT NOT NULL,
    target_sections INTEGER,
    source_scope    TEXT NOT NULL,   -- json object
    seed_frameworks TEXT NOT NULL,   -- json array
    author          TEXT NOT NULL,
    thread_id       TEXT
);
CREATE TABLE IF NOT EXISTS compositions (
    id          TEXT PRIMARY KEY,
    brief_id    TEXT NOT NULL,
    thread_id   TEXT,
    status      TEXT NOT NULL,
    sections    TEXT NOT NULL,       -- json array of Section
    model       TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_compositions_brief ON compositions(brief_id);
"""


class CompositionStore:
    """Stores briefs and their compositions (proposed / approved / rejected)."""

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- briefs --------------------------------------------------------------
    def save_brief(self, brief: Brief) -> Brief:
        self._conn.execute(
            "INSERT OR REPLACE INTO briefs (id, title, intent, content_type, lang, "
            "target_sections, source_scope, seed_frameworks, author, thread_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                brief.id,
                brief.title,
                brief.intent,
                brief.content_type,
                brief.lang,
                brief.target_sections,
                brief.source_scope.model_dump_json(),
                json.dumps(brief.seed_frameworks, ensure_ascii=False),
                brief.author,
                brief.thread_id,
            ),
        )
        self._conn.commit()
        return brief

    def get_brief(self, brief_id: str) -> Brief | None:
        row = self._conn.execute("SELECT * FROM briefs WHERE id = ?", (brief_id,)).fetchone()
        return self._row_to_brief(row) if row else None

    # -- compositions --------------------------------------------------------
    def save_composition(self, composition: Composition) -> Composition:
        self._conn.execute(
            "INSERT OR REPLACE INTO compositions (id, brief_id, thread_id, status, "
            "sections, model, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                composition.id,
                composition.brief_id,
                composition.thread_id,
                composition.status,
                json.dumps([s.model_dump() for s in composition.sections], ensure_ascii=False),
                composition.model,
                composition.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return composition

    def get_composition(self, composition_id: str) -> Composition | None:
        row = self._conn.execute(
            "SELECT * FROM compositions WHERE id = ?", (composition_id,)
        ).fetchone()
        return self._row_to_composition(row) if row else None

    def list_compositions(self) -> list[Composition]:
        return [
            self._row_to_composition(r)
            for r in self._conn.execute("SELECT * FROM compositions ORDER BY created_at")
        ]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> CompositionStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- mapping -------------------------------------------------------------
    @staticmethod
    def _row_to_brief(row: sqlite3.Row) -> Brief:
        content_type: ContentType = row["content_type"]
        lang: Lang = row["lang"]
        return Brief(
            id=row["id"],
            title=row["title"],
            intent=row["intent"],
            content_type=content_type,
            lang=lang,
            target_sections=row["target_sections"],
            source_scope=SourceScope.model_validate_json(row["source_scope"]),
            seed_frameworks=json.loads(row["seed_frameworks"]),
            author=row["author"],
            thread_id=row["thread_id"],
        )

    @staticmethod
    def _row_to_composition(row: sqlite3.Row) -> Composition:
        status: CompositionStatus = row["status"]
        sections = [Section.model_validate(s) for s in json.loads(row["sections"])]
        return Composition(
            id=row["id"],
            brief_id=row["brief_id"],
            thread_id=row["thread_id"],
            status=status,
            sections=sections,
            model=row["model"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
