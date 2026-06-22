"""Models for the expert capture loop.

A `Session` records a question and the answer it received. A `Contribution` (the
evolved `Annotation`) is an expert's correction/connection/addition/objection on
that session, optionally tying several source refs together with a free-form
"move" tag. A contribution can also *open a new aspect* — i.e. plant a **seed**: a
piece of knowledge (`body`) plus a separate **directive** telling the model what to
develop from it. Contributions are later converted into expert-sourced chunks and
indexed alongside the printed text.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class Session(BaseModel):
    """A recorded ask: the question, the refs retrieved, and the answer text."""

    id: str
    timestamp: datetime
    question: str
    retrieved_refs: list[str] = Field(default_factory=list)
    answer_text: str


class Annotation(BaseModel):
    """An expert's contribution on a session.

    `kind` is validated against the config-driven `annotation_kinds` list (so the
    set is extensible), and `move` is a free tag (e.g. "pasuk->concept").

    A contribution is either a *correction/connection* (attaches to a passage) or a
    *seed* that `opens_aspect` — knowledge (`body`) carrying a `directive` for the
    model to develop. The directive is kept SEPARATE from `body` so it never
    pollutes the embedded/retrievable text. `author` is required: provenance is the
    point, so anonymous/blank contributions are rejected.
    """

    id: str
    session_id: str
    timestamp: datetime
    author: str
    kind: str
    body: str
    linked_refs: list[str] = Field(default_factory=list)
    move: str | None = None
    directive: str | None = None  # the "now develop X" instruction, SEPARATE from body
    opens_aspect: bool = False  # marks a seed that leads a new aspect

    @field_validator("author")
    @classmethod
    def _author_required(cls, value: str) -> str:
        """Reject a missing/blank author — every contribution must be attributed."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("author is required (no anonymous/default contributions)")
        return cleaned


# Forward-looking name: an Annotation is a Contribution. New code should prefer
# `Contribution`; the `Annotation` name stays for backward compatibility.
Contribution = Annotation
