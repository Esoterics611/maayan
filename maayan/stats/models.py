"""Typed Stats model — the boundary type for the knowledge-base dashboard.

A single pydantic model crosses the StatsService → CLI/route boundary (house rule:
typed boundaries, no loose dicts handed across). The per-group counts are typed
`dict[str, int]` *fields inside* the model, which is fine — the model is the contract.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Stats(BaseModel):
    """An aggregate snapshot of the knowledge base (all read-only)."""

    total_chunks: int  # live (non-retracted) chunks
    chunks_by_source: dict[str, int] = Field(default_factory=dict)  # sefaria/chabad/expert/...
    chunks_by_book: dict[str, int] = Field(default_factory=dict)
    contributions_by_author: dict[str, int] = Field(default_factory=dict)
    developments_by_status: dict[str, int] = Field(default_factory=dict)  # proposed/approved/...
    retractions: int = 0
    threads: int = 0
    terms: int = 0  # live lexicon terms
    qdrant_points: int | None = None  # None when the vector store wasn't reachable
