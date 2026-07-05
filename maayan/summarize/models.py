"""Typed models for gated section summaries (Prompt 42)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SummaryStatus = Literal["proposed", "approved", "rejected"]

_SUMMARY_NS = uuid.UUID("2f9a1c7e-4b60-4d8a-8e13-9c5a2d7b0f44")


def summary_id(parent_ref: str) -> str:
    """Deterministic id per section — re-summarizing a section upserts, never duplicates."""
    return str(uuid.uuid5(_SUMMARY_NS, parent_ref))


def summary_chunk_id(parent_ref: str) -> str:
    """Deterministic id for the indexed summary chunk of a section."""
    return str(uuid.uuid5(_SUMMARY_NS, f"chunk|{parent_ref}"))


class Summary(BaseModel):
    """A model-drafted, corpus-grounded section summary awaiting expert approval.

    `parent_ref` anchors the section; `child_refs` are the passages it summarizes. A
    summary is `supported` only if it cites at least one child and the faithfulness pass
    flags nothing — an ungrounded summary is recorded but never indexable.
    """

    id: str
    book: str
    parent_ref: str
    parent_label: str = ""
    child_refs: list[str] = Field(default_factory=list)
    text: str = ""
    cited_refs: list[str] = Field(default_factory=list)
    model: str = ""
    supported: bool = False
    unsupported_claims: list[str] = Field(default_factory=list)
    status: SummaryStatus = "proposed"
    author: str = ""  # set on approval (the human approver)
    created_at: datetime

    def summary_chunk_ref(self) -> str:
        """Human-readable, stable ref for this summary's indexed chunk."""
        return f"Summary · {self.parent_label or self.parent_ref}"
