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
    kind: str = "connection"
    author: str = "expert"
    linked_refs: list[str] = Field(default_factory=list)
    move: str | None = None


class AnnotateResponse(BaseModel):
    annotation_id: str
    session_id: str
    kind: str
    author: str
    linked_refs: list[str]


class AnnotationOut(BaseModel):
    id: str
    kind: str
    author: str
    body: str
    linked_refs: list[str]
    move: str | None = None


class SessionResponse(BaseModel):
    id: str
    question: str
    answer_text: str
    retrieved_refs: list[str]
    annotations: list[AnnotationOut]
