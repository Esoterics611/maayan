"""Models for the retrieval layer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Via(BaseModel):
    """Why an expanded hit is here: the approved relation that brought it (Prompt 35).

    Carried on graph-expanded results only — a seed hit has no via, and that absence
    is meaningful (unmarked = found by search, marked = brought by knowledge). The
    four facts the scholar must always see: how (rel_type), on whose word (author +
    evidence), and from where (seed_ref).
    """

    rel_type: str
    evidence: str
    author: str
    seed_ref: str  # the ref (or concept) the hop started from
    relation_id: str
    note: str | None = None


class SearchResult(BaseModel):
    """One retrieved chunk with its score and full payload (for citation/display)."""

    ref: str
    text: str
    score: float
    lang: str
    source: str
    payload: dict[str, Any]
    via: Via | None = None  # set only on graph-expanded hits
    # A window of neighboring passages from the same section (Prompt 42), added at
    # generation time for context ONLY. Never citable — the citation stays this hit.
    parent_context: str = ""

    def first_line(self, width: int = 100) -> str:
        """First line of the text, trimmed — handy for CLI output."""
        line = self.text.strip().splitlines()[0] if self.text.strip() else ""
        return line[:width]


class RetrievalResult(BaseModel):
    """Ranked results plus an absolute relevance score used for the answer/refuse gate.

    `relevance` is the top dense-cosine similarity (0..1-ish), an *absolute* measure —
    unlike the RRF fusion `score` on each result, which only reflects rank position
    and so cannot tell "relevant" from "best of irrelevant".
    """

    results: list[SearchResult]
    relevance: float
