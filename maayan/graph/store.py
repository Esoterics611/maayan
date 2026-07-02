"""SQLite persistence for the knowledge graph (same DB file as the rest).

New tables layered with `IF NOT EXISTS` — nothing existing is touched. Pure
persistence plus the two policies that keep the graph trustworthy:

* **Dedupe** — one row per (subject, object, rel_type). A second insert of the
  same edge updates evidence/confidence instead of duplicating, and only ever
  *raises* the evidence tier (per `EVIDENCE_RANK`); a weaker re-assertion can
  never silently downgrade a stronger one. Dedupe never changes `status`: a
  human decision (approved/retracted) is not undone by a re-insert.
* **The gate** — relations are created "proposed"; `approve(...)` (attributed)
  is the only path to "approved", and `neighbors()` serves approved edges only.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from maayan.graph.models import (
    EVIDENCE_RANK,
    Concept,
    ConceptEndpoint,
    GraphCounts,
    Neighbor,
    RefEndpoint,
    Relation,
    endpoint_key,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS graph_concepts (
    id         TEXT PRIMARY KEY,
    canonical  TEXT NOT NULL UNIQUE,
    aliases    TEXT NOT NULL,          -- json array
    kind       TEXT NOT NULL,
    term_id    TEXT,
    author     TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_relations (
    id              TEXT PRIMARY KEY,
    subject_kind    TEXT NOT NULL,     -- "ref" | "concept"
    subject_value   TEXT NOT NULL,
    object_kind     TEXT NOT NULL,
    object_value    TEXT NOT NULL,
    rel_type        TEXT NOT NULL,
    evidence        TEXT NOT NULL,
    confidence      REAL NOT NULL,
    status          TEXT NOT NULL,
    author          TEXT NOT NULL,
    source_chunk_id TEXT,
    note            TEXT,
    created_at      TEXT NOT NULL,
    UNIQUE (subject_kind, subject_value, object_kind, object_value, rel_type)
);
CREATE INDEX IF NOT EXISTS idx_graph_rel_subject ON graph_relations(subject_kind, subject_value);
CREATE INDEX IF NOT EXISTS idx_graph_rel_object  ON graph_relations(object_kind, object_value);
CREATE INDEX IF NOT EXISTS idx_graph_rel_status  ON graph_relations(status);
CREATE INDEX IF NOT EXISTS idx_graph_rel_chunk   ON graph_relations(source_chunk_id);
"""


class GraphStore:
    """Stores concepts and typed relations; owns dedupe + the approval gate."""

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: shared safely across FastAPI worker threads
        # (Python 3.12 sqlite3 is serialized). See corpus/store.py.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- concepts --------------------------------------------------------------
    def save_concept(self, concept: Concept) -> Concept:
        self._conn.execute(
            "INSERT OR REPLACE INTO graph_concepts "
            "(id, canonical, aliases, kind, term_id, author, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                concept.id,
                concept.canonical,
                json.dumps(concept.aliases, ensure_ascii=False),
                concept.kind,
                concept.term_id,
                concept.author,
                concept.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return concept

    def get_concept(self, concept_id: str) -> Concept | None:
        row = self._conn.execute(
            "SELECT * FROM graph_concepts WHERE id = ?", (concept_id,)
        ).fetchone()
        return self._row_to_concept(row) if row else None

    def find_concept(self, name: str) -> Concept | None:
        """Look a concept up by canonical name, falling back to an alias scan."""
        row = self._conn.execute(
            "SELECT * FROM graph_concepts WHERE canonical = ?", (name,)
        ).fetchone()
        if row:
            return self._row_to_concept(row)
        for candidate in self._conn.execute("SELECT * FROM graph_concepts"):
            if name in json.loads(candidate["aliases"]):
                return self._row_to_concept(candidate)
        return None

    def list_concepts(self) -> list[Concept]:
        rows = self._conn.execute("SELECT * FROM graph_concepts ORDER BY canonical")
        return [self._row_to_concept(r) for r in rows]

    # -- relations: writes -----------------------------------------------------
    def save_relation(self, relation: Relation) -> Relation:
        """Insert an edge, deduping on (subject, object, rel_type).

        On a duplicate: evidence/confidence/note/author update only when the new
        evidence tier is at least as strong as the stored one (never a silent
        downgrade); id, status and created_at always survive. Returns the stored
        row either way.
        """
        s_kind, s_value = endpoint_key(relation.subject)
        o_kind, o_value = endpoint_key(relation.object)
        existing = self._conn.execute(
            "SELECT * FROM graph_relations WHERE subject_kind = ? AND subject_value = ? "
            "AND object_kind = ? AND object_value = ? AND rel_type = ?",
            (s_kind, s_value, o_kind, o_value, relation.rel_type),
        ).fetchone()
        if existing is None:
            self._conn.execute(
                "INSERT INTO graph_relations (id, subject_kind, subject_value, object_kind, "
                "object_value, rel_type, evidence, confidence, status, author, "
                "source_chunk_id, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    relation.id,
                    s_kind,
                    s_value,
                    o_kind,
                    o_value,
                    relation.rel_type,
                    relation.evidence,
                    relation.confidence,
                    relation.status,
                    relation.author,
                    relation.source_chunk_id,
                    relation.note,
                    relation.created_at.isoformat(),
                ),
            )
            self._conn.commit()
            return relation
        if EVIDENCE_RANK[relation.evidence] >= EVIDENCE_RANK[existing["evidence"]]:
            self._conn.execute(
                "UPDATE graph_relations SET evidence = ?, confidence = ?, author = ?, "
                "note = COALESCE(?, note), source_chunk_id = COALESCE(?, source_chunk_id) "
                "WHERE id = ?",
                (
                    relation.evidence,
                    relation.confidence,
                    relation.author,
                    relation.note,
                    relation.source_chunk_id,
                    existing["id"],
                ),
            )
            self._conn.commit()
        stored = self.get_relation(str(existing["id"]))
        assert stored is not None  # just written/read under the same connection
        return stored

    def approve(self, relation_id: str, *, author: str) -> Relation:
        """The gate: flip one *proposed* relation to approved, attributed.

        A model-drafted edge (evidence "derived_bootstrap") becomes
        "derived_approved" and carries the approver as its author — the human is
        now the one vouching. Human/curated evidence keeps its original author.
        Anything not "proposed" is rejected (approve is not re-runnable).
        """
        approver = author.strip()
        if not approver:
            raise ValueError("author is required (an approval must be attributed)")
        relation = self.get_relation(relation_id)
        if relation is None:
            raise ValueError(f"No relation with id {relation_id!r}.")
        if relation.status != "proposed":
            raise ValueError(
                f"Relation {relation_id!r} is {relation.status!r}; only a proposed "
                "relation can be approved."
            )
        update = {"status": "approved"}
        if relation.evidence == "derived_bootstrap":
            update |= {"evidence": "derived_approved", "author": approver}
        approved = relation.model_copy(update=update)
        self._conn.execute(
            "UPDATE graph_relations SET status = ?, evidence = ?, author = ? WHERE id = ?",
            (approved.status, approved.evidence, approved.author, approved.id),
        )
        self._conn.commit()
        return approved

    def mark_retracted(self, relation_id: str) -> None:
        """Tombstone one relation (policy + audit live in the retract service)."""
        self._conn.execute(
            "UPDATE graph_relations SET status = 'retracted' WHERE id = ?", (relation_id,)
        )
        self._conn.commit()

    # -- relations: reads --------------------------------------------------------
    def get_relation(self, relation_id: str) -> Relation | None:
        row = self._conn.execute(
            "SELECT * FROM graph_relations WHERE id = ?", (relation_id,)
        ).fetchone()
        return self._row_to_relation(row) if row else None

    def relations_for(
        self,
        endpoint: RefEndpoint | ConceptEndpoint,
        *,
        status: str | None = None,
        types: list[str] | None = None,
    ) -> list[Relation]:
        """Every relation touching `endpoint` (as subject or object)."""
        kind, value = endpoint_key(endpoint)
        clauses = [
            "((subject_kind = ? AND subject_value = ?) OR (object_kind = ? AND object_value = ?))"
        ]
        params: list[object] = [kind, value, kind, value]
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if types:
            clauses.append(f"rel_type IN ({', '.join('?' * len(types))})")
            params.extend(types)
        rows = self._conn.execute(
            f"SELECT * FROM graph_relations WHERE {' AND '.join(clauses)} "
            "ORDER BY rel_type, created_at",
            params,
        )
        return [self._row_to_relation(r) for r in rows]

    def neighbors(
        self,
        endpoint: RefEndpoint | ConceptEndpoint,
        *,
        types: list[str] | None = None,
        status: str = "approved",
    ) -> list[Neighbor]:
        """Walk one hop: the far endpoint of each relation touching `endpoint`.

        Approved-only by default — proposed/retracted edges are invisible to
        retrieval and views (the gate, enforced at the read).
        """
        kind, value = endpoint_key(endpoint)
        steps: list[Neighbor] = []
        for relation in self.relations_for(endpoint, status=status, types=types):
            far = (
                relation.object
                if endpoint_key(relation.subject) == (kind, value)
                else relation.subject
            )
            steps.append(Neighbor(endpoint=far, relation=relation))
        return steps

    def relations_from_chunk(self, source_chunk_id: str) -> list[Relation]:
        """Relations lifted from a given prose chunk (for retraction cascade)."""
        rows = self._conn.execute(
            "SELECT * FROM graph_relations WHERE source_chunk_id = ?", (source_chunk_id,)
        )
        return [self._row_to_relation(r) for r in rows]

    def list_relations(
        self,
        *,
        status: str | None = None,
        rel_type: str | None = None,
        evidence: str | None = None,
        limit: int | None = None,
    ) -> list[Relation]:
        clauses: list[str] = []
        params: list[object] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if rel_type is not None:
            clauses.append("rel_type = ?")
            params.append(rel_type)
        if evidence is not None:
            clauses.append("evidence = ?")
            params.append(evidence)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM graph_relations {where} ORDER BY created_at, id"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return [self._row_to_relation(r) for r in self._conn.execute(sql, params)]

    def counts(self) -> GraphCounts:
        def tally(column: str) -> dict[str, int]:
            rows = self._conn.execute(
                f"SELECT {column} AS k, COUNT(*) AS n FROM graph_relations GROUP BY {column}"  # noqa: S608 - column is a literal below
            )
            return {r["k"]: int(r["n"]) for r in rows}

        concepts = int(
            self._conn.execute("SELECT COUNT(*) AS n FROM graph_concepts").fetchone()["n"]
        )
        relations = int(
            self._conn.execute("SELECT COUNT(*) AS n FROM graph_relations").fetchone()["n"]
        )
        return GraphCounts(
            concepts=concepts,
            relations=relations,
            by_rel_type=tally("rel_type"),
            by_evidence=tally("evidence"),
            by_status=tally("status"),
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> GraphStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- mapping -----------------------------------------------------------------
    @staticmethod
    def _row_to_concept(row: sqlite3.Row) -> Concept:
        return Concept(
            id=row["id"],
            canonical=row["canonical"],
            aliases=json.loads(row["aliases"]),
            kind=row["kind"],
            term_id=row["term_id"],
            author=row["author"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _row_to_relation(row: sqlite3.Row) -> Relation:
        def endpoint(kind: str, value: str) -> RefEndpoint | ConceptEndpoint:
            if kind == "ref":
                return RefEndpoint(ref=value)
            return ConceptEndpoint(concept_id=value)

        return Relation(
            id=row["id"],
            subject=endpoint(row["subject_kind"], row["subject_value"]),
            object=endpoint(row["object_kind"], row["object_value"]),
            rel_type=row["rel_type"],
            evidence=row["evidence"],
            confidence=row["confidence"],
            status=row["status"],
            author=row["author"],
            source_chunk_id=row["source_chunk_id"],
            note=row["note"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
