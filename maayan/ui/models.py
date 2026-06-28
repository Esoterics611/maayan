"""Request/response models for the local UI API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from maayan.users.models import Role, UserOut


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
    # For source="shiur": lets a cited source play from its moment in the recording.
    audio_id: str | None = None
    start_s: float | None = None


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


# ---- Phase 4: retraction (the eraser) --------------------------------------


class RetractRequest(BaseModel):
    target: str  # the ref or chunk id of the expert/derived/term chunk
    author: str  # required — provenance (blank rejected by the model validator)
    reason: str = ""


class RetractResponse(BaseModel):
    id: str
    chunk_id: str
    ref: str
    source: str
    author: str
    reason: str


# ---- Phase 5: composition (brief → outline → fill → review → export) -------


class ComposeRequest(BaseModel):
    title: str
    intent: str
    author: str  # required — provenance (blank rejected by the model validator)
    content_type: str = "shiur_outline"
    target_sections: int | None = None
    book: str | None = None  # source-scope filter
    seed_frameworks: list[str] = Field(default_factory=list)
    thread_id: str | None = None


class SectionOut(BaseModel):
    heading: str
    query: str
    text: str = ""
    cited_refs: list[str] = Field(default_factory=list)
    grounded_in: list[str] = Field(default_factory=list)
    supported: bool = False


class CompositionResponse(BaseModel):
    id: str
    brief_id: str
    status: str
    model: str
    sections: list[SectionOut]
    cited_refs: list[str]
    grounded_in: list[str]
    supported_sections: int
    gap_sections: int


class PromoteRequest(BaseModel):
    section_index: int  # 0-based
    author: str
    insight: str


class ExportResponse(BaseModel):
    markdown: str


# ---- Auth / users ----------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""
    role: Role = "member"


class SetActiveRequest(BaseModel):
    active: bool


class SetPasswordRequest(BaseModel):
    password: str


class MeResponse(BaseModel):
    """Who am I + whether auth is on. Drives the UI's auth chrome and author auto-fill."""

    auth_enabled: bool
    user: UserOut | None = None


class UpdateSegmentRequest(BaseModel):
    """Edit one transcript segment during review (Prompt 27). Both fields optional."""

    edited_text: str | None = None
    speaker: str | None = None


class ApproveTranscriptRequest(BaseModel):
    """Approve a reviewed transcript into shiur corpus. Author required (provenance)."""

    author: str


class ApproveTranscriptResponse(BaseModel):
    transcript_id: str
    status: str
    chunk_count: int
    refs: list[str] = Field(default_factory=list)


# -- reading / library (Prompt 29) -------------------------------------------
class SourceContextChunk(BaseModel):
    ref: str
    lang: str
    text: str
    source: str
    cited: bool = False  # the segment the citation pointed at (highlight in the reader)


class SourceContextResponse(BaseModel):
    ref: str
    label: str  # the section label (parent path), e.g. "Chapter 1"
    book: str
    chunks: list[SourceContextChunk] = Field(default_factory=list)


class LibraryEntry(BaseModel):
    book: str
    source: str
    count: int


class LibraryResponse(BaseModel):
    entries: list[LibraryEntry] = Field(default_factory=list)


class SectionEntry(BaseModel):
    label: str
    ref: str
    lang: str


class SectionsResponse(BaseModel):
    book: str
    sections: list[SectionEntry] = Field(default_factory=list)
