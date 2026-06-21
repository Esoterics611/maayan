"""Ingestion orchestration: Sefaria → chunks → SQLite.

Pure orchestration over injected collaborators (client, store). No I/O construction
here — the CLI builds the concrete `SefariaClient`/`ChunkStore` and passes them in.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from maayan.corpus.chunker import section_to_chunks
from maayan.corpus.models import Lang
from maayan.corpus.sefaria import SefariaClient
from maayan.corpus.store import ChunkStore


@dataclass(frozen=True)
class IngestResult:
    book: str
    sections: int
    chunks: int


async def ingest_book(
    base_ref: str,
    *,
    client: SefariaClient,
    store: ChunkStore,
    langs: Sequence[Lang] = ("he", "en"),
    max_chapters: int | None = None,
    expand_abbreviations: bool = False,
) -> IngestResult:
    """Fetch a book chapter by chapter, chunk it, and upsert into the store."""
    sections = 0
    chunks_written = 0
    book_name = base_ref
    async for section in client.iter_book_sections(base_ref, max_chapters=max_chapters):
        book_name = section.book
        chunks = section_to_chunks(
            section, langs=langs, expand_abbreviations=expand_abbreviations
        )
        chunks_written += store.upsert_chunks(chunks)
        sections += 1
    return IngestResult(book=book_name, sections=sections, chunks=chunks_written)


async def ingest_books(
    base_refs: Sequence[str],
    *,
    client: SefariaClient,
    store: ChunkStore,
    langs: Sequence[Lang] = ("he", "en"),
    max_chapters: int | None = None,
    expand_abbreviations: bool = False,
) -> list[IngestResult]:
    """Ingest several books in sequence (rate limiting handled by the client)."""
    results: list[IngestResult] = []
    for ref in base_refs:
        results.append(
            await ingest_book(
                ref,
                client=client,
                store=store,
                langs=langs,
                max_chapters=max_chapters,
                expand_abbreviations=expand_abbreviations,
            )
        )
    return results
