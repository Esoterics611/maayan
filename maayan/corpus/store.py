"""Local SQLite persistence for chunks.

Idempotent by design: chunk ids are deterministic, so re-ingesting upserts in
place rather than duplicating. When a chunk's text changes on re-ingest, its
`indexed` flag is reset so the indexing pipeline (Prompt 2) re-embeds it.

This is local disk I/O, not network, so it is synchronous — no Clock needed. The
store is still injected (constructed at the edges), per the DI house rule.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Sequence
from pathlib import Path

from maayan.corpus.models import Chunk

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id            TEXT PRIMARY KEY,
    ref           TEXT NOT NULL,
    book          TEXT NOT NULL,
    section_path  TEXT NOT NULL,   -- json array
    lang          TEXT NOT NULL,
    text          TEXT NOT NULL,
    source        TEXT NOT NULL,
    metadata      TEXT NOT NULL,   -- json object
    indexed       INTEGER NOT NULL DEFAULT 0,
    retracted     INTEGER NOT NULL DEFAULT 0   -- tombstone: removed from retrieval (Prompt 17)
);
CREATE INDEX IF NOT EXISTS idx_chunks_book ON chunks(book);
CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source);
CREATE INDEX IF NOT EXISTS idx_chunks_indexed ON chunks(indexed);
"""


class ChunkStore:
    """SQLite-backed store for `Chunk`s."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: FastAPI runs sync handlers in worker threads;
        # Python 3.12's sqlite3 is serialized (threadsafety=3), so sharing the
        # connection across threads is safe.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """Idempotent column migrations for DBs created before a column existed.

        New DBs get `retracted` from `_SCHEMA`; older DBs are missing it, so add it
        in place (default 0 = not retracted) without disturbing existing rows. Same
        discipline as the `indexed` column.
        """
        existing = {row["name"] for row in self._conn.execute("PRAGMA table_info(chunks)")}
        if "retracted" not in existing:
            self._conn.execute(
                "ALTER TABLE chunks ADD COLUMN retracted INTEGER NOT NULL DEFAULT 0"
            )

    # -- writes --------------------------------------------------------------
    def upsert_chunks(self, chunks: Iterable[Chunk]) -> int:
        """Insert or update chunks by id. Returns the number written.

        If an existing chunk's text changes, `indexed` resets to 0 so it will be
        re-embedded; unchanged rows keep their `indexed` state.
        """
        rows = [
            (
                c.id,
                c.ref,
                c.book,
                json.dumps(c.section_path, ensure_ascii=False),
                c.lang,
                c.text,
                c.source,
                json.dumps(c.metadata, ensure_ascii=False),
            )
            for c in chunks
        ]
        if not rows:
            return 0
        self._conn.executemany(
            """
            INSERT INTO chunks (id, ref, book, section_path, lang, text, source, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                ref          = excluded.ref,
                book         = excluded.book,
                section_path = excluded.section_path,
                lang         = excluded.lang,
                text         = excluded.text,
                source       = excluded.source,
                metadata     = excluded.metadata,
                indexed      = CASE WHEN chunks.text <> excluded.text THEN 0 ELSE chunks.indexed END
            """,
            rows,
        )
        self._conn.commit()
        return len(rows)

    def mark_indexed(self, ids: Sequence[str]) -> None:
        """Mark chunks as indexed in Qdrant (used by the indexing pipeline)."""
        if not ids:
            return
        self._conn.executemany("UPDATE chunks SET indexed = 1 WHERE id = ?", [(i,) for i in ids])
        self._conn.commit()

    def mark_retracted(self, ids: Sequence[str]) -> None:
        """Tombstone chunks so they leave retrieval and survive `index --rebuild` gone.

        A retracted chunk stays in the table (its retraction is provenanced) but is
        excluded from every retrieval-facing read, so the indexing pipeline never
        re-embeds it.
        """
        if not ids:
            return
        self._conn.executemany(
            "UPDATE chunks SET retracted = 1 WHERE id = ?", [(i,) for i in ids]
        )
        self._conn.commit()

    # -- reads ---------------------------------------------------------------
    def get_chunks(
        self,
        *,
        source: str | None = None,
        book: str | None = None,
        only_unindexed: bool = False,
        include_retracted: bool = False,
        limit: int | None = None,
    ) -> list[Chunk]:
        clauses: list[str] = []
        params: list[object] = []
        if source is not None:
            clauses.append("source = ?")
            params.append(source)
        if book is not None:
            clauses.append("book = ?")
            params.append(book)
        if only_unindexed:
            clauses.append("indexed = 0")
        if not include_retracted:
            clauses.append("retracted = 0")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM chunks {where} ORDER BY ref"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return [self._row_to_chunk(r) for r in self._conn.execute(sql, params)]

    def get_chunk(self, chunk_id: str, *, include_retracted: bool = True) -> Chunk | None:
        """Fetch one chunk by its stable id (retracted included by default — for resolving)."""
        row = self._conn.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
        if row is None or (not include_retracted and row["retracted"]):
            return None
        return self._row_to_chunk(row)

    def get_by_ref(self, ref: str, *, include_retracted: bool = True) -> list[Chunk]:
        """Fetch chunks whose ref matches exactly (a ref may have he+en variants)."""
        sql = "SELECT * FROM chunks WHERE ref = ?"
        if not include_retracted:
            sql += " AND retracted = 0"
        return [self._row_to_chunk(r) for r in self._conn.execute(sql + " ORDER BY lang", (ref,))]

    def counts_by_source(self, *, include_retracted: bool = False) -> dict[str, int]:
        """Live chunk counts grouped by source (sefaria/chabad/expert/derived/term)."""
        where = "" if include_retracted else "WHERE retracted = 0"
        rows = self._conn.execute(
            f"SELECT source, COUNT(*) AS n FROM chunks {where} GROUP BY source"
        )
        return {r["source"]: int(r["n"]) for r in rows}

    def counts_by_book(self, *, include_retracted: bool = False) -> dict[str, int]:
        """Live chunk counts grouped by book."""
        where = "" if include_retracted else "WHERE retracted = 0"
        rows = self._conn.execute(
            f"SELECT book, COUNT(*) AS n FROM chunks {where} GROUP BY book ORDER BY book"
        )
        return {r["book"]: int(r["n"]) for r in rows}

    def count(
        self,
        *,
        source: str | None = None,
        only_unindexed: bool = False,
        include_retracted: bool = False,
    ) -> int:
        clauses: list[str] = []
        params: list[object] = []
        if source is not None:
            clauses.append("source = ?")
            params.append(source)
        if only_unindexed:
            clauses.append("indexed = 0")
        if not include_retracted:
            clauses.append("retracted = 0")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        cur = self._conn.execute(f"SELECT COUNT(*) AS n FROM chunks {where}", params)
        return int(cur.fetchone()["n"])

    # -- export / lifecycle --------------------------------------------------
    def export_jsonl(self, path: str) -> int:
        """Dump all chunks to a JSONL file. Returns the number written."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        chunks = self.get_chunks()
        with open(path, "w", encoding="utf-8") as fh:
            for c in chunks:
                fh.write(c.model_dump_json() + "\n")
        return len(chunks)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ChunkStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def _row_to_chunk(row: sqlite3.Row) -> Chunk:
        return Chunk(
            id=row["id"],
            ref=row["ref"],
            book=row["book"],
            section_path=json.loads(row["section_path"]),
            lang=row["lang"],
            text=row["text"],
            source=row["source"],
            metadata=json.loads(row["metadata"]),
        )
