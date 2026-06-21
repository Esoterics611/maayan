"""Models for the retrieval layer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SearchResult(BaseModel):
    """One retrieved chunk with its score and full payload (for citation/display)."""

    ref: str
    text: str
    score: float
    lang: str
    source: str
    payload: dict[str, Any]

    def first_line(self, width: int = 100) -> str:
        """First line of the text, trimmed — handy for CLI output."""
        line = self.text.strip().splitlines()[0] if self.text.strip() else ""
        return line[:width]
