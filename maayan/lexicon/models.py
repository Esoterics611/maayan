"""Model for a lexicon Term — a Holy Name / technical term as an ENTITY.

Tokens like ע״ב carry gershayim and *look* like rashei-teivot, but they are terms
(ע״ב is the *Ab* expansion of the Tetragrammaton, gematria 72), not abbreviations to
expand. A `Term` is expert-defined knowledge that layers on top of the immutable text
and becomes a retrievable `source="term"` chunk. `surface_forms` are matched
gershayim/quote/nikkud-insensitively (see `corpus.normalize.fold_surface`).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

TermType = Literal["name", "sefirah", "partzuf", "expansion", "concept", "other"]


class Term(BaseModel):
    """One curated lexicon entry, with provenance (author required)."""

    id: str
    canonical: str  # display form, e.g. 'ע"ב (Name of 72 / Ab)'
    surface_forms: list[str] = Field(default_factory=list)  # variants to match in text
    term_type: TermType = "concept"
    definition: str
    related_terms: list[str] = Field(default_factory=list)  # sibling terms, e.g. ס"ג/מ"ה/ב"ן
    source_refs: list[str] = Field(default_factory=list)
    gematria: int | None = None
    sacred: bool = False  # a Holy Name — display/handle with care
    author: str

    @field_validator("author")
    @classmethod
    def _author_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("author is required (no anonymous lexicon entries)")
        return cleaned
