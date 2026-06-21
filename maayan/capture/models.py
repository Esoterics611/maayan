"""Models for the expert capture loop.

A `Session` records a question and the answer it received. An `Annotation` is an
expert's correction/connection/addition/objection on that session, optionally
tying several source refs together with a free-form "move" tag. Annotations are
later converted into expert-sourced chunks and indexed alongside the printed text.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Session(BaseModel):
    """A recorded ask: the question, the refs retrieved, and the answer text."""

    id: str
    timestamp: datetime
    question: str
    retrieved_refs: list[str] = Field(default_factory=list)
    answer_text: str


class Annotation(BaseModel):
    """An expert's note on a session.

    `kind` is validated against the config-driven `annotation_kinds` list (so the
    set is extensible), and `move` is a free tag (e.g. "pasuk->concept").
    """

    id: str
    session_id: str
    timestamp: datetime
    author: str
    kind: str
    body: str
    linked_refs: list[str] = Field(default_factory=list)
    move: str | None = None
