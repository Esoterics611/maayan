"""Request/response models for the local UI API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from maayan.users.models import Role, UserOut


class AskRequest(BaseModel):
    question: str
    k: int | None = None
    # Chavrusa mode (Prompt 39): run the bounded multi-hop study loop instead of the
    # one-shot ask. The refusal gate is unchanged — a refused seed never reaches the model.
    agent: bool = False


class ViaOut(BaseModel):
    """Graph-expansion provenance for one source (the via-line, Prompt 35)."""

    rel_type: str
    evidence: str
    author: str
    seed_ref: str
    note: str | None = None


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
    # Graph-expanded hits only: the relation that brought this source (None on seeds).
    via: ViaOut | None = None


class AskResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    grounded: bool
    cited_refs: list[str]
    sources: list[SourceOut]
    # Reasoning mode (RAG_REASONING_ENABLED): the study map behind the answer (or None).
    reasoning: str | None = None
    # Verify mode (ANSWER_VERIFY_ENABLED): answer sentences not supported by their sources.
    unsupported_claims: list[str] = Field(default_factory=list)
    # Chavrusa mode (Prompt 39): the persisted study trace's id, so the UI can open the
    # stepper ("כיצד נלמד?"). None for a plain ask or a refusal (nothing was studied).
    trace_id: str | None = None


class InquiryOut(BaseModel):
    """One inquiry card (שאלות לרב): the voice, the printed math, the deep link."""

    id: str
    kind: str
    title: str
    detail: str
    payload: dict[str, object]  # the typed per-kind payload, serialized
    priority: float
    priority_parts: dict[str, float]  # printed on the card — transparency over polish
    status: str
    created_at: str
    resolution: str | None = None


class InquiriesResponse(BaseModel):
    items: list[InquiryOut]
    # The harvest line: today's answered items by kind — the UI's only metric.
    harvest: dict[str, int] = Field(default_factory=dict)


class AnswerInquiryRequest(BaseModel):
    resolution: str  # what answering created (chunk/term/relation id + note)


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


# -- OCR + quick-capture inbox (Prompt 30) -----------------------------------
class OcrResponse(BaseModel):
    """Text extracted from a photographed page. Never auto-ingested — the UI drops it
    into a capture field for the same human review gate as every other contribution."""

    text: str
    lang: str


class CaptureThoughtRequest(BaseModel):
    """One-tap quick capture. Author required (provenance); blank rejected by the model."""

    text: str
    author: str = ""  # filled from the logged-in user when auth is on


class InboxItemOut(BaseModel):
    id: str
    author: str
    text: str
    created_at: str
    status: str
    thread_id: str | None = None
    record_id: str | None = None


class MoveInboxRequest(BaseModel):
    """Triage a parked thought into a thread, where it becomes a develop-able seed."""

    thread_id: str
    kind: str = "addition"
    directive: str | None = None


# -- the Review workbench (הכרעות): one queue for every gate ------------------
class DevelopmentReviewOut(BaseModel):
    """A proposed development awaiting judgment, listed across all threads."""

    id: str
    thread_id: str
    seed_id: str
    author: str
    status: str
    grounded: bool
    text: str
    cited_refs: list[str] = Field(default_factory=list)
    grounded_in: list[str] = Field(default_factory=list)
    created_at: str


class RelationReviewOut(BaseModel):
    """A proposed graph edge (e.g. a study-program draft) awaiting judgment."""

    id: str
    subject_label: str
    object_label: str
    rel_type: str
    evidence: str
    confidence: float
    status: str
    author: str
    note: str | None = None
    created_at: str


class ReviewQueueResponse(BaseModel):
    """Everything waiting for the scholar's click, in one place."""

    developments: list[DevelopmentReviewOut] = Field(default_factory=list)
    relations: list[RelationReviewOut] = Field(default_factory=list)
    inquiries: list[InquiryOut] = Field(default_factory=list)
    inbox: list[InboxItemOut] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    total: int = 0
    # The day's harvest (answered inquiries by kind) — encouragement, not telemetry.
    harvest: dict[str, int] = Field(default_factory=dict)


class ApproveRelationRequest(BaseModel):
    """Author for the attributed graph gate; omitted when auth supplies identity."""

    author: str | None = None


# -- the Gold panel (שאלות זהב): the eval flywheel, visible -------------------
class GoldExampleOut(BaseModel):
    """One captured regression example — an approval that became a permanent test."""

    id: str
    question: str
    expected_refs: list[str] = Field(default_factory=list)
    origin_kind: str
    created_at: str
    retracted: bool = False


class GoldReportOut(BaseModel):
    """The latest `eval --captured` run, surfaced read-only."""

    date: str
    n_ranked: int
    n_gate_only: int
    hit: dict[str, float] = Field(default_factory=dict)
    recall: dict[str, float] = Field(default_factory=dict)
    mrr: float = 0.0
    answer_rate: float = 0.0


class GoldsetResponse(BaseModel):
    total: int
    by_origin: dict[str, int] = Field(default_factory=dict)
    gate_only: int = 0  # examples that test only the refusal gate (no expected refs)
    examples: list[GoldExampleOut] = Field(default_factory=list)
    last_report: GoldReportOut | None = None


# -- verify (R5): retrieval-only "did it learn?" — never calls the model ------
class VerifyHit(BaseModel):
    ref: str
    source: str
    score: float


class VerifyResponse(BaseModel):
    question: str
    ref: str
    found: bool
    rank: int | None = None  # 1-based position of `ref` among the results, when found
    top: list[VerifyHit] = Field(default_factory=list)


# -- contributions: browse the expert's captured knowledge (connections/seeds/…) ----------
class ContributionOut(BaseModel):
    id: str
    author: str
    kind: str
    body: str
    linked_refs: list[str] = Field(default_factory=list)
    directive: str | None = None
    opens_aspect: bool = False  # already a seed → no "turn into seed" affordance
    created_at: str


class ContributionsResponse(BaseModel):
    contributions: list[ContributionOut] = Field(default_factory=list)
    total: int = 0
