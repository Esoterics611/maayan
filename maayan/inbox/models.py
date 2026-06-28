"""Models for the quick-capture inbox.

An `InboxItem` is a raw captured thought with provenance (`author`) and a lifecycle:
`open` until it is triaged into a thread, then `moved` (recording the destination
thread and the seed it became). Like every contribution, a blank author is rejected
and empty text is meaningless, so both are validated.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

InboxStatus = Literal["open", "moved"]


class InboxItem(BaseModel):
    """A captured thought parked for later triage into a thread."""

    id: str
    author: str
    text: str
    created_at: datetime
    status: InboxStatus = "open"
    thread_id: str | None = None  # set when moved
    record_id: str | None = None  # the seed/annotation id created on move

    @field_validator("author")
    @classmethod
    def _author_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("author is required (no anonymous captures)")
        return cleaned

    @field_validator("text")
    @classmethod
    def _text_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("a captured thought cannot be empty")
        return cleaned
