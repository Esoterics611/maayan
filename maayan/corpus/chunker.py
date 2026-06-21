"""Chunking: turn fetched Sefaria sections into normalized `Chunk`s.

House decision: chunk by the text's OWN structure — **one segment = one chunk**
(a pasuk / os / se'if / paragraph). No fixed token windows; the natural unit is
preserved so citations stay meaningful. Each segment yields up to one chunk per
requested language (he/en) that is actually present and non-empty after
normalization.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from maayan.corpus.models import Chunk, Lang, SefariaSection, SefariaSegment
from maayan.corpus.normalize import normalize_text


def segment_to_chunks(
    segment: SefariaSegment,
    *,
    langs: Sequence[Lang] = ("he", "en"),
    source: str = "sefaria",
    expand_abbreviations: bool = False,
) -> list[Chunk]:
    """Convert one segment into chunks (one per available, non-empty language)."""
    chunks: list[Chunk] = []
    raw_by_lang: dict[Lang, str | None] = {"he": segment.he, "en": segment.en}
    for lang in langs:
        raw = raw_by_lang.get(lang)
        if not raw:
            continue
        text = normalize_text(raw, expand_abbreviations=expand_abbreviations)
        if not text:
            continue
        chunks.append(
            Chunk.make(
                ref=segment.ref,
                book=segment.book,
                section_path=segment.section_path,
                lang=lang,
                text=text,
                source=source,
            )
        )
    return chunks


def section_to_chunks(
    section: SefariaSection,
    *,
    langs: Sequence[Lang] = ("he", "en"),
    source: str = "sefaria",
    expand_abbreviations: bool = False,
) -> list[Chunk]:
    """Convert all segments of a section into chunks, in order."""
    chunks: list[Chunk] = []
    for seg in section.segments:
        chunks.extend(
            segment_to_chunks(
                seg, langs=langs, source=source, expand_abbreviations=expand_abbreviations
            )
        )
    return chunks


def sections_to_chunks(
    sections: Iterable[SefariaSection],
    *,
    langs: Sequence[Lang] = ("he", "en"),
    source: str = "sefaria",
    expand_abbreviations: bool = False,
) -> list[Chunk]:
    """Flatten many sections into a single ordered list of chunks."""
    chunks: list[Chunk] = []
    for section in sections:
        chunks.extend(
            section_to_chunks(
                section, langs=langs, source=source, expand_abbreviations=expand_abbreviations
            )
        )
    return chunks
