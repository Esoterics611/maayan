"""Pydantic models for the knowledge graph: Concept, Endpoint, Relation.

The vocabularies here are SCHEMA — the shape the next years of knowledge land in.
`RelationType` follows the citator lesson (the edge's type is its value) and
`EvidenceCode` the curation lesson (every assertion says how it is known):

  evidence   strength  meaning
  ---------  --------  -----------------------------------------------------
  expert         5     stated by a named scholar (the gold standard)
  curated        4     human-curated upstream data (e.g. Sefaria's link graph)
  deterministic  3     machine-derived by construction (e.g. a shared pasuk)
  derived_approved 2   model-drafted, human-gated
  derived_bootstrap 1  model-drafted by the free bootstrap; NOT human-reviewed

An `Endpoint` is either a canonical ref or a concept — an explicit discriminated
union, never a bare string, so the two address spaces cannot be confused.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

ConceptKind = Literal["sefirah", "partzuf", "olam", "name", "avodah", "concept"]

RelationType = Literal[
    "quotes",
    "quotes_pasuk",
    "explains",
    "is_mashal_for",
    "corresponds_to",
    "argues_with",
    "develops",
    "parallels",
    "defines",
    "connects",
]

EvidenceCode = Literal[
    "expert", "curated", "deterministic", "derived_approved", "derived_bootstrap"
]

RelationStatus = Literal["proposed", "approved", "retracted"]

# Evidence strength, used by the store's dedupe policy: a re-insert of an existing
# edge may raise its evidence tier, never silently lower it (the gate is the asset).
EVIDENCE_RANK: dict[str, int] = {
    "expert": 5,
    "curated": 4,
    "deterministic": 3,
    "derived_approved": 2,
    "derived_bootstrap": 1,
}

# The one badge grammar for evidence codes (UI spec Rule 2) — used identically in
# CLI output, margins, via-lines, inquiry cards, and traces. Never restyle locally.
EVIDENCE_GLYPH: dict[str, str] = {
    "expert": "●",
    "curated": "◆",
    "deterministic": "⚙",
    "derived_approved": "◐",
    "derived_bootstrap": "◌",
}

# Stable namespaces → deterministic ids → idempotent re-runs (backfill, link
# ingestion) upsert instead of duplicating, exactly like chunk ids.
_CONCEPT_NS = uuid.UUID("0d1caf62-3a52-49a1-9b3f-1f4f5f16f9a1")
_RELATION_NS = uuid.UUID("5b0e6a1e-8f0f-4a4e-b0a7-2f6cf5f7d3b2")


class Concept(BaseModel):
    """A named idea (sefirah, partzuf, olam, Holy Name, avodah, concept).

    `term_id` optionally links into the existing lexicon so a concept and its
    curated definition stay one entity, not two.
    """

    id: str
    canonical: str
    aliases: list[str] = Field(default_factory=list)
    kind: ConceptKind = "concept"
    term_id: str | None = None
    author: str
    created_at: datetime

    @field_validator("author")
    @classmethod
    def _author_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("author is required (no anonymous concepts)")
        return cleaned

    @field_validator("canonical")
    @classmethod
    def _canonical_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("canonical name is required")
        return cleaned

    @classmethod
    def make(
        cls,
        *,
        canonical: str,
        author: str,
        created_at: datetime,
        aliases: list[str] | None = None,
        kind: ConceptKind = "concept",
        term_id: str | None = None,
    ) -> Concept:
        """Construct a Concept with a deterministic id derived from its canonical name."""
        return cls(
            id=concept_id(canonical),
            canonical=canonical,
            aliases=aliases or [],
            kind=kind,
            term_id=term_id,
            author=author,
            created_at=created_at,
        )


def concept_id(canonical: str) -> str:
    """Deterministic id for a concept: same canonical name → same id, always."""
    return str(uuid.uuid5(_CONCEPT_NS, canonical.strip()))


class RefEndpoint(BaseModel):
    """An endpoint addressing a canonical (Sefaria/chabad) ref string.

    The ref need not resolve to a local chunk — a pasuk outside the corpus is a
    legitimate anchor.
    """

    endpoint_type: Literal["ref"] = "ref"
    ref: str

    @field_validator("ref")
    @classmethod
    def _ref_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("ref endpoint requires a non-empty ref")
        return cleaned


class ConceptEndpoint(BaseModel):
    """An endpoint addressing a Concept by id."""

    endpoint_type: Literal["concept"] = "concept"
    concept_id: str

    @field_validator("concept_id")
    @classmethod
    def _concept_id_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("concept endpoint requires a non-empty concept_id")
        return cleaned


Endpoint = Annotated[RefEndpoint | ConceptEndpoint, Field(discriminator="endpoint_type")]


def endpoint_key(endpoint: RefEndpoint | ConceptEndpoint) -> tuple[str, str]:
    """(kind, value) storage key for an endpoint — the store's address form."""
    if isinstance(endpoint, RefEndpoint):
        return ("ref", endpoint.ref)
    return ("concept", endpoint.concept_id)


def endpoint_str(endpoint: RefEndpoint | ConceptEndpoint) -> str:
    """Human-readable endpoint (for CLI output and retraction audit refs)."""
    kind, value = endpoint_key(endpoint)
    return value if kind == "ref" else f"concept:{value}"


def relation_id(
    subject: RefEndpoint | ConceptEndpoint,
    obj: RefEndpoint | ConceptEndpoint,
    rel_type: RelationType,
) -> str:
    """Deterministic id for (subject, object, rel_type) — the dedupe identity."""
    s_kind, s_value = endpoint_key(subject)
    o_kind, o_value = endpoint_key(obj)
    return str(uuid.uuid5(_RELATION_NS, f"{s_kind}|{s_value}|{o_kind}|{o_value}|{rel_type}"))


class Relation(BaseModel):
    """One typed, provenanced edge: subject —rel_type→ object.

    Created "proposed"; only `GraphStore.approve` (attributed) makes it
    "approved", and only approved relations are ever served to retrieval/views.
    `source_chunk_id` points at the prose chunk this edge was lifted from, when
    there is one — the edge is a structured view of that knowledge, not a copy.
    """

    id: str
    subject: Endpoint
    object: Endpoint
    rel_type: RelationType
    evidence: EvidenceCode
    confidence: float = Field(ge=0.0, le=1.0)
    status: RelationStatus = "proposed"
    author: str
    source_chunk_id: str | None = None
    note: str | None = None
    created_at: datetime

    @field_validator("author")
    @classmethod
    def _author_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("author is required (no anonymous relations)")
        return cleaned

    @classmethod
    def make(
        cls,
        *,
        subject: RefEndpoint | ConceptEndpoint,
        object: RefEndpoint | ConceptEndpoint,  # noqa: A002 - mirrors the field name
        rel_type: RelationType,
        evidence: EvidenceCode,
        confidence: float,
        author: str,
        created_at: datetime,
        status: RelationStatus = "proposed",
        source_chunk_id: str | None = None,
        note: str | None = None,
    ) -> Relation:
        """Construct a Relation with the deterministic dedupe-identity id."""
        return cls(
            id=relation_id(subject, object, rel_type),
            subject=subject,
            object=object,
            rel_type=rel_type,
            evidence=evidence,
            confidence=confidence,
            status=status,
            author=author,
            source_chunk_id=source_chunk_id,
            note=note,
            created_at=created_at,
        )


class Neighbor(BaseModel):
    """One graph-walk step: the far endpoint plus the relation that carries you there.

    The relation IS the provenance — retrieval's "via" line (Prompt 35) and the
    margins (Prompt 36) both need who/how, not just where.
    """

    endpoint: Endpoint
    relation: Relation


class GraphCounts(BaseModel):
    """Store-wide tallies for `graph stats` and reports."""

    concepts: int = 0
    relations: int = 0
    by_rel_type: dict[str, int] = Field(default_factory=dict)
    by_evidence: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)


class BackfillResult(BaseModel):
    """Outcome of `maayan graph backfill` (idempotent: rerun ⇒ created == 0)."""

    chunks_seen: int = 0
    connection_chunks: int = 0
    relations_created: int = 0
    relations_existing: int = 0
    skipped_chunks: int = 0


class LinksIngestResult(BaseModel):
    """Outcome of `maayan graph ingest-links` (resumable: rerun skips fetched refs)."""

    refs_seen: int = 0
    refs_fetched: int = 0
    refs_skipped: int = 0  # already in the cursor from a previous run
    refs_failed: int = 0  # fetch errors; NOT cursored, so the next run retries them
    links_seen: int = 0
    links_kept: int = 0  # in a kept category (config: sefaria_link_categories)
    relations_created: int = 0
    relations_existing: int = 0


class PasukJoinResult(BaseModel):
    """Outcome of the deterministic pasuk join (idempotent)."""

    pasukim: int = 0  # distinct quotes_pasuk targets shared by ≥2 corpus refs
    pairs: int = 0
    relations_created: int = 0
    relations_existing: int = 0
