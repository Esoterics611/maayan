"""Request/response models for the local UI API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str
    k: int | None = None


class SourceOut(BaseModel):
    ref: str
    text: str
    lang: str
    source: str
    score: float
    cited: bool = False


class AskResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    grounded: bool
    cited_refs: list[str]
    sources: list[SourceOut]


class AnnotateRequest(BaseModel):
    session_id: str
    body: str
    author: str  # required — provenance; blank is rejected by the model validator
    kind: str = "connection"
    linked_refs: list[str] = Field(default_factory=list)
    move: str | None = None
    directive: str | None = None  # seed: what the model should develop (separate from body)
    opens_aspect: bool = False


class AnnotateResponse(BaseModel):
    annotation_id: str
    session_id: str
    kind: str
    author: str
    linked_refs: list[str]
    opens_aspect: bool = False


class AnnotationOut(BaseModel):
    id: str
    kind: str
    author: str
    body: str
    linked_refs: list[str]
    move: str | None = None
    directive: str | None = None
    opens_aspect: bool = False


class SessionResponse(BaseModel):
    id: str
    question: str
    answer_text: str
    retrieved_refs: list[str]
    annotations: list[AnnotationOut]


# ---- Phase 2: topic threads + seed → develop → approve ---------------------


class ThreadOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class TurnOut(BaseModel):
    """A thread turn for display, enriched per type (develop status, seed directive)."""

    id: str
    ordinal: int
    turn_type: str
    author: str
    text: str
    record_id: str | None = None
    # development turns:
    status: str | None = None  # proposed | approved | rejected
    grounded: bool | None = None
    cited_refs: list[str] = Field(default_factory=list)
    grounded_in: list[str] = Field(default_factory=list)
    # seed turns:
    is_seed: bool = False
    directive: str | None = None


class ThreadDetailResponse(BaseModel):
    thread: ThreadOut
    turns: list[TurnOut]


class CreateThreadRequest(BaseModel):
    title: str


class AskInThreadRequest(BaseModel):
    question: str


class SeedRequest(BaseModel):
    author: str  # required — provenance (blank rejected by the model validator)
    body: str
    directive: str | None = None
    kind: str = "connection"
    linked_refs: list[str] = Field(default_factory=list)


class SeedResponse(BaseModel):
    contribution_id: str
    author: str
    directive: str | None = None


class DevelopRequest(BaseModel):
    seed_id: str  # contribution id of the seed to develop


class DevelopmentResponse(BaseModel):
    id: str
    status: str
    grounded: bool
    text: str
    cited_refs: list[str]
    grounded_in: list[str]
    model: str


class TermRequest(BaseModel):
    canonical: str
    definition: str
    author: str  # required — provenance (blank rejected by the model validator)
    term_type: str = "concept"
    surface_forms: list[str] = Field(default_factory=list)
    related_terms: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    gematria: int | None = None
    sacred: bool = False


class TermResponse(BaseModel):
    id: str
    canonical: str
    term_type: str
    author: str
    surface_forms: list[str]
