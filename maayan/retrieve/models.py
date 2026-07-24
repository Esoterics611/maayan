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


class GateSignals(BaseModel):
    """The absolute relevance signals a refusal gate can be built from.

    All are computed over the same candidate pool. The `_top` values are the single
    best score in a branch; the `_mean` values average the pool, which is a much
    lower-variance estimate of "how much relevant material is actually there" — over
    ~9k points the single top cosine is a max over noise. `rerank_top` is present
    only when a cross-encoder ran.
    """

    dense_top: float = 0.0
    dense_mean: float = 0.0
    sparse_top: float = 0.0
    sparse_mean: float = 0.0
    rerank_top: float | None = None
    pool: int = 0  # how many hits the means were taken over


class RetrievalResult(BaseModel):
    """Ranked results plus an absolute relevance score used for the answer/refuse gate.

    `relevance` is an *absolute* measure — unlike the RRF fusion `score` on each result,
    which only reflects rank position and so cannot tell "relevant" from "best of
    irrelevant". WHICH absolute measure depends on the injected `RelevanceGate`, so
    callers must compare it against `Settings.effective_score_threshold` rather than
    `score_threshold`: the gates are on different scales.

    `signals` carries the raw per-branch signals the gate judged on, when available —
    kept so a refusal can be explained after the fact without re-running the query.
    """

    results: list[SearchResult]
    relevance: float
    signals: GateSignals | None = None
