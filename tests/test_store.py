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


# -- reading / library (Prompt 29) -------------------------------------------
def _mk(ref: str, section_path: list[str], *, book: str = "Tanya", lang: str = "he") -> Chunk:
    return Chunk.make(ref=ref, book=book, section_path=section_path, lang=lang, text=ref)


def test_get_section_returns_same_chapter_he_preferred() -> None:
    store = ChunkStore(":memory:")
    store.upsert_chunks([
        _mk("Tanya 1:1", ["Chapter 1", "Paragraph 1"]),
        _mk("Tanya 1:2", ["Chapter 1", "Paragraph 2"]),
        _mk("Tanya 1:2", ["Chapter 1", "Paragraph 2"], lang="en"),
        _mk("Tanya 2:1", ["Chapter 2", "Paragraph 1"]),
    ])
    section = store.get_section("Tanya 1:2")  # he preferred, same chapter only
    assert [(c.ref, c.lang) for c in section] == [("Tanya 1:1", "he"), ("Tanya 1:2", "he")]
    # Explicit lang override pulls the English section.
    en = store.get_section("Tanya 1:2", lang="en")
    assert [c.lang for c in en] == ["en"]
    assert store.get_section("missing") == []
    store.close()


def test_library_index_and_sections() -> None:
    store = ChunkStore(":memory:")
    store.upsert_chunks([
        _mk("Tanya 1:1", ["Chapter 1", "Paragraph 1"]),
        _mk("Tanya 2:1", ["Chapter 2", "Paragraph 1"]),
        Chunk.make(ref="Shiur: Demo §1 @ 00:00", book="Demo", section_path=["Shiur"],
                   lang="he", text="x", source="shiur"),
    ])
    index = store.library_index()
    assert ("Tanya", "sefaria", 2) in index
    assert ("Demo", "shiur", 1) in index
    # Tanya's table of contents = its two chapters; a shiur is one section.
    assert [label for (label, _r, _l) in store.list_sections("Tanya")] == ["Chapter 1", "Chapter 2"]
    assert [label for (label, _r, _l) in store.list_sections("Demo")] == ["Demo"]
    store.close()
