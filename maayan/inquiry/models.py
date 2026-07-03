"""Models for the inquiry queue: ask telemetry + the items the system asks the Rav.

Every `InquiryItem` renders as a question addressed to the scholar (Hebrew voice,
never a database row), carries a typed per-kind payload (discriminated union, not
a loose dict), and prints its own priority arithmetic — an opaque queue would
spend the Rav's trust along with his time.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

InquiryKind = Literal[
    "refused_question",
    "undergrounded_term",
    "low_evidence_relation",
    "contradiction",
    "re_review",
]

InquiryStatus = Literal["open", "answered", "dismissed"]

# Deterministic item ids: kind + a per-kind dedupe key → regeneration upserts the
# same item instead of duplicating it, and a dismissed id STAYS dismissed.
_INQUIRY_NS = uuid.UUID("7c2a30e4-6c6f-4630-9d0e-52e28936cf1d")


def inquiry_id(kind: str, dedupe_key: str) -> str:
    return str(uuid.uuid5(_INQUIRY_NS, f"{kind}|{dedupe_key}"))


class AskRecord(BaseModel):
    """One logged ask: the raw material for the refused-question generator."""

    id: str
    question: str
    refused: bool
    top_score: float
    session_id: str | None = None
    thread_id: str | None = None
    user: str | None = None  # mirrors existing auth; no new PII
    timestamp: datetime


class RefusedQuestionPayload(BaseModel):
    """A cluster of near-duplicate refused questions."""

    kind: Literal["refused_question"] = "refused_question"
    questions: list[str]  # distinct phrasings, most recent last
    count: int  # total refusals in the cluster (the priority signal)
    last_asked: datetime


class UndergroundedTermPayload(BaseModel):
    """A term the free drafter could not ground — maybe the corpus still supports it."""

    kind: Literal["undergrounded_term"] = "undergrounded_term"
    canonical: str
    suggestion_id: str
    model: str = ""  # the drafter that failed (provenance)
    unsupported_claims: list[str] = Field(default_factory=list)


class LowEvidenceRelationPayload(BaseModel):
    """An approved edge standing on bootstrap evidence or low confidence."""

    kind: Literal["low_evidence_relation"] = "low_evidence_relation"
    relation_id: str
    subject: str
    object: str
    rel_type: str
    evidence: str
    confidence: float
    author: str


class ContradictionPayload(BaseModel):
    """Two approved relations on the same endpoints that argue with each other."""

    kind: Literal["contradiction"] = "contradiction"
    relation_a_id: str
    relation_b_id: str
    subject: str
    object: str
    rel_type_a: str
    rel_type_b: str
    authors: list[str]


class ReReviewPayload(BaseModel):
    """Chazarah: aging, low-evidence knowledge due for re-confirmation (Prompt 41)."""

    kind: Literal["re_review"] = "re_review"
    target_id: str
    target_kind: str  # e.g. "relation" | "chunk" | "term"
    reason: str


InquiryPayload = Annotated[
    RefusedQuestionPayload
    | UndergroundedTermPayload
    | LowEvidenceRelationPayload
    | ContradictionPayload
    | ReReviewPayload,
    Field(discriminator="kind"),
]


class InquiryItem(BaseModel):
    """One question the system asks the scholar, ranked and resolvable."""

    id: str
    kind: InquiryKind
    title: str  # the card's voice — natural Hebrew, addressed to the Rav
    detail: str
    payload: InquiryPayload
    priority: float
    priority_parts: dict[str, float] = Field(default_factory=dict)  # printed on the card
    status: InquiryStatus = "open"
    created_at: datetime
    answered_at: datetime | None = None
    resolution: str | None = None  # what answering created (chunk/term/relation id)


class GenerateReport(BaseModel):
    """Outcome of one `maayan inquiries generate` run (idempotent on open items)."""

    created: int = 0
    refreshed: int = 0  # open items whose priority/payload were updated in place
    skipped_terminal: int = 0  # ids already answered/dismissed — never resurrected
    by_kind: dict[str, int] = Field(default_factory=dict)
