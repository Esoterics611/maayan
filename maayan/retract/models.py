"""Model for a Retraction — the provenanced removal of a layered-knowledge chunk.

A retraction is NOT a silent delete: it is an attributed, timestamped audit record
(who retracted, when, why) for an `expert` / `derived` / `term` chunk. The chunk is
removed from retrieval and tombstoned in the corpus store, but the retraction itself
is preserved so the *removal* carries provenance, mirroring the house value that
printed text is immutable and provenance travels with everything.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class Retraction(BaseModel):
    """One provenanced retraction of a layered-knowledge chunk."""

    id: str
    chunk_id: str  # the retracted chunk's stable id (the Qdrant point id)
    ref: str  # the retracted chunk's ref (human-readable)
    source: str  # the retracted chunk's source: "expert" | "derived" | "term"
    author: str  # who retracted it (REQUIRED — blank rejected, as in Prompt 9)
    reason: str  # why it was retracted (e.g. "superseded", "typo", "wrong connection")
    timestamp: datetime

    @field_validator("author")
    @classmethod
    def _author_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("author is required (a retraction must be attributed)")
        return cleaned
