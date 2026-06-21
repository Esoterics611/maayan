"""Pydantic models for the corpus layer.

`Chunk` is the unit that flows corpus → embed → index → retrieve. Everything that
crosses a module boundary is one of these models (house rule: typed boundaries).
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

Lang = Literal["he", "en"]

# Stable namespace so chunk ids are deterministic across runs → idempotent upsert.
_CHUNK_NS = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def chunk_id(source: str, ref: str, lang: str) -> str:
    """Deterministic id for a chunk. Same (source, ref, lang) → same id, always.

    Qdrant point ids must be UUID or int; a UUID5 satisfies that and is stable,
    which is what makes re-ingest/re-index an upsert rather than a duplicate.
    """
    return str(uuid.uuid5(_CHUNK_NS, f"{source}|{ref}|{lang}"))


class Chunk(BaseModel):
    """One natural unit of text (a pasuk / os / se'if / paragraph), one language."""

    id: str
    ref: str  # canonical Sefaria ref, e.g. "Tanya, Part I; Likkutei Amarim 1:1"
    book: str  # e.g. "Tanya"
    section_path: list[str]  # e.g. ["Chapter 1", "Paragraph 1"]
    lang: Lang
    text: str  # normalized text (markup stripped, whitespace collapsed, nikkud kept)
    source: str = "sefaria"  # "sefaria" | "expert" | "shiur" ...
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def make(
        cls,
        *,
        ref: str,
        book: str,
        section_path: list[str],
        lang: Lang,
        text: str,
        source: str = "sefaria",
        metadata: dict[str, Any] | None = None,
    ) -> Chunk:
        """Construct a Chunk with a deterministic id derived from (source, ref, lang)."""
        return cls(
            id=chunk_id(source, ref, lang),
            ref=ref,
            book=book,
            section_path=section_path,
            lang=lang,
            text=text,
            source=source,
            metadata=metadata or {},
        )


class SefariaSegment(BaseModel):
    """A single segment as fetched from Sefaria, before normalization/chunking.

    Holds the *raw* (markup-bearing) Hebrew and/or English text for one segment,
    plus its canonical ref and structural path.
    """

    ref: str
    book: str
    section_path: list[str]
    he: str | None = None  # raw Hebrew (may contain HTML)
    en: str | None = None  # raw English (may contain HTML)


class SefariaSection(BaseModel):
    """A fetched section (e.g. one chapter) and its ordered segments."""

    ref: str  # the section ref, e.g. "Tanya, Part I; Likkutei Amarim 1"
    book: str
    section_names: list[str]  # e.g. ["Chapter", "Paragraph"]
    segments: list[SefariaSegment]
    metadata: dict[str, Any] = Field(default_factory=dict)


class SefariaShape(BaseModel):
    """Structure of a base ref: how many chapters and segments-per-chapter."""

    ref: str
    book: str
    chapter_lengths: list[int]  # paragraphs per chapter; len == number of chapters

    @property
    def num_chapters(self) -> int:
        return len(self.chapter_lengths)
