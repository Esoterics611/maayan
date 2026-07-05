"""Typed models for consolidation (Prompt 41): clusters and sugya pages.

A `Cluster` is a deterministic grouping of related, approved knowledge (a connected
component over approved graph edges, optionally anchored on a shared Concept). A
`SugyaPage` is what one cluster consolidates into: a curated, cited, versioned topic
page — proposed → approved → superseded — that indexes as retrievable ``sugya`` chunks
only once the Rav approves it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

SugyaStatus = Literal["proposed", "approved", "superseded", "rejected"]

_SUGYA_NS = uuid.UUID("b7e6d2a4-1c3f-4e8a-9d21-6f0a8c5e4b12")


class Cluster(BaseModel):
    """A deterministic group of related approved knowledge, before any drafting.

    `refs` are the corpus refs in the component (sorted, deduped — the identity);
    `relation_ids` the approved edges that bind them; `concept` the shared Concept
    canonical when the component touches one, else None; `chunk_ids` the expert/derived
    chunks whose ref sits in the component.
    """

    concept: str | None = None
    refs: list[str] = Field(default_factory=list)
    relation_ids: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)

    @property
    def key(self) -> str:
        """Stable identity for a cluster: its sorted refs. Same component → same key."""
        return "|".join(self.refs)


class SugyaSection(BaseModel):
    """One drafted section of a sugya page — grounded, with the refs it cited."""

    title: str
    body: str
    cited_refs: list[str] = Field(default_factory=list)


class SugyaPage(BaseModel):
    """A curated, versioned consolidation of one cluster (proposed → approved → superseded).

    `chunk_ids` is set on approval — the exact ``sugya`` chunks this version indexed, so
    that approving version N+1 retracts precisely them through the audited retract flow.
    `supersedes` links a version to the page id it replaces; `page_key` is the stable
    identity across versions (the cluster key), so a book's sugya has one lineage.
    """

    id: str
    page_key: str  # stable across versions (the cluster key)
    concept: str | None
    title: str
    sections: list[SugyaSection] = Field(default_factory=list)
    cited_refs: list[str] = Field(default_factory=list)
    version: int = 1
    status: SugyaStatus = "proposed"
    author: str
    supersedes: str | None = None
    chunk_ids: list[str] = Field(default_factory=list)
    model: str = ""
    created_at: datetime

    @field_validator("author")
    @classmethod
    def _author_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("author is required (a sugya page must be attributed)")
        return cleaned

    @classmethod
    def make(
        cls,
        *,
        page_key: str,
        concept: str | None,
        title: str,
        sections: list[SugyaSection],
        author: str,
        created_at: datetime,
        version: int = 1,
        supersedes: str | None = None,
        model: str = "",
    ) -> SugyaPage:
        cited: list[str] = []
        for section in sections:
            for ref in section.cited_refs:
                if ref not in cited:
                    cited.append(ref)
        return cls(
            id=str(uuid.uuid4()),
            page_key=page_key,
            concept=concept,
            title=title,
            sections=sections,
            cited_refs=cited,
            version=version,
            author=author,
            supersedes=supersedes,
            model=model,
            created_at=created_at,
        )


class ChazarahSchedule(BaseModel):
    """Spaced-repetition state for one re-reviewable target (Anki-style intervals).

    Each confirmation multiplies `interval_days` (config factor) and pushes
    `next_review_at` out — knowledge the Rav keeps affirming resurfaces ever less often.
    """

    target_id: str
    target_kind: str  # "relation" | "chunk" | "term"
    interval_days: float
    next_review_at: datetime
    reviews: int = 0
    last_reviewed_at: datetime | None = None


class ChazarahReport(BaseModel):
    """Outcome of one `maayan chazarah` pass (idempotent on open re_review items)."""

    scheduled: int = 0  # targets with a schedule row after this pass
    queued: int = 0  # due targets that produced/refreshed an open re_review inquiry
    by_reason: dict[str, int] = Field(default_factory=dict)


def sugya_chunk_ref(page: SugyaPage, section_index: int) -> str:
    """Human-readable, stable ref for one section's indexed chunk."""
    tag = page.concept or page.title
    return f"Sugya · {tag} · v{page.version} §{section_index + 1}"


def sugya_chunk_id(page: SugyaPage, section_index: int) -> str:
    """Deterministic id for a sugya section chunk (page id + section index)."""
    return str(uuid.uuid5(_SUGYA_NS, f"{page.id}|{section_index}"))
