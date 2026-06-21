"""Tests for the SQLite ChunkStore — idempotency, filters, indexed flag."""

from __future__ import annotations

from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore


def _chunk(ref: str, text: str, lang: str = "he", source: str = "sefaria") -> Chunk:
    return Chunk.make(
        ref=ref, book="Tanya", section_path=["Chapter 1", "Paragraph 1"],
        lang=lang, text=text, source=source,  # type: ignore[arg-type]
    )


def test_upsert_is_idempotent_by_id() -> None:
    store = ChunkStore(":memory:")
    chunks = [_chunk("Tanya 1:1", "שלום"), _chunk("Tanya 1:2", "עולם")]
    store.upsert_chunks(chunks)
    store.upsert_chunks(chunks)  # re-run: no duplicates
    assert store.count() == 2
    store.close()


def test_section_path_and_metadata_round_trip() -> None:
    store = ChunkStore(":memory:")
    c = _chunk("Tanya 1:1", "שלום")
    store.upsert_chunks([c])
    got = store.get_chunks()[0]
    assert got.section_path == ["Chapter 1", "Paragraph 1"]
    assert got.ref == "Tanya 1:1"
    assert got.lang == "he"
    store.close()


def test_changed_text_resets_indexed_flag() -> None:
    store = ChunkStore(":memory:")
    c = _chunk("Tanya 1:1", "old")
    store.upsert_chunks([c])
    store.mark_indexed([c.id])
    assert store.count(only_unindexed=True) == 0

    # Re-ingest with new text → indexed resets, unchanged would not.
    store.upsert_chunks([_chunk("Tanya 1:1", "new")])
    assert store.count(only_unindexed=True) == 1
    store.close()


def test_unchanged_text_keeps_indexed_flag() -> None:
    store = ChunkStore(":memory:")
    c = _chunk("Tanya 1:1", "same")
    store.upsert_chunks([c])
    store.mark_indexed([c.id])
    store.upsert_chunks([_chunk("Tanya 1:1", "same")])
    assert store.count(only_unindexed=True) == 0
    store.close()


def test_filters_by_source_and_book() -> None:
    store = ChunkStore(":memory:")
    store.upsert_chunks([
        _chunk("Tanya 1:1", "a", source="sefaria"),
        _chunk("Expert 1", "b", source="expert"),
    ])
    assert store.count(source="expert") == 1
    assert {c.source for c in store.get_chunks(source="sefaria")} == {"sefaria"}
    store.close()
