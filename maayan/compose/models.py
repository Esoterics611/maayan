"""Pydantic models for the composition layer (Phase 5).

The spine: a `Brief` (the spec) produces a `Composition` (the document), which is an
ordered list of `Section`s. The first content type is the shiur/class outline; essay
and digest are the same engine in a different register, so `content_type` is a config
Literal rather than a new module. Provenance travels with everything (author, brief,
per-section grounded refs, gaps), as elsewhere in the codebase.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from maayan.corpus.models import Lang

ContentType = Literal["shiur_outline", "essay", "digest", "other"]
CompositionStatus = Literal["proposed", "approved", "rejected"]


class SourceScope(BaseModel):
    """Optional retrieval filters, passed straight through to the retriever."""

    book: str | None = None
    source: str | None = None


class Brief(BaseModel):
    """The spec for a composition — what the piece should do, and in what register."""

    id: str
    title: str
    intent: str  # what the piece should do / teach
    content_type: ContentType = "shiur_outline"
    lang: Lang = "he"
    target_sections: int | None = None  # caller's desired count (still bounded by config)
    source_scope: SourceScope = Field(default_factory=SourceScope)
    seed_frameworks: list[str] = Field(default_factory=list)  # attributed, never cited
    author: str  # REQUIRED — blank rejected, as in Prompt 9
    thread_id: str | None = None

    @field_validator("author")
    @classmethod
    def _author_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("author is required (a composition must be attributed)")
        return cleaned


class Section(BaseModel):
    """One section of a composition: a heading + the retrieval sub-question that grounds it.

    The outline (Prompt 20) fills `heading` + `query` with empty `text`; the fill step
    (Prompt 21) sets `text`/`cited_refs`/`grounded_in`/`supported` — or marks it an
    honest gap (`supported=False`) when the corpus doesn't reach it.
    """

    heading: str
    query: str  # the retrieval sub-question for this section
    text: str = ""
    cited_refs: list[str] = Field(default_factory=list)
    grounded_in: list[str] = Field(default_factory=list)
    supported: bool = False


class Composition(BaseModel):
    """A reviewable document (mirrors `Development`): proposed → approved/rejected."""

    id: str
    brief_id: str
    thread_id: str | None = None
    status: CompositionStatus = "proposed"
    sections: list[Section] = Field(default_factory=list)
    model: str
    created_at: datetime

    @property
    def cited_refs(self) -> list[str]:
        """Distinct refs cited across all sections, in first-seen order."""
        return _distinct(ref for s in self.sections for ref in s.cited_refs)

    @property
    def grounded_in(self) -> list[str]:
        """Distinct refs retrieved across all sections, in first-seen order."""
        return _distinct(ref for s in self.sections for ref in s.grounded_in)

    @property
    def supported_sections(self) -> int:
        return sum(1 for s in self.sections if s.supported)

    @property
    def gap_sections(self) -> int:
        return sum(1 for s in self.sections if not s.supported)


def _distinct(refs: Iterable[str]) -> list[str]:
    seen: list[str] = []
    for ref in refs:
        if ref and ref not in seen:
            seen.append(ref)
    return seen
