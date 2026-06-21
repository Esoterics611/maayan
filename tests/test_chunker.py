"""Unit tests for the chunker (one segment = one chunk, per language)."""

from __future__ import annotations

from maayan.corpus.chunker import section_to_chunks, segment_to_chunks
from maayan.corpus.models import SefariaSection, SefariaSegment, chunk_id


def _segment(ref: str, he: str | None, en: str | None) -> SefariaSegment:
    return SefariaSegment(
        ref=ref, book="Tanya", section_path=["Chapter 1", "Paragraph 1"], he=he, en=en
    )


def test_segment_yields_one_chunk_per_present_language() -> None:
    seg = _segment("Tanya 1:1", he="<b>שָׁלוֹם</b>", en="Peace")
    chunks = segment_to_chunks(seg, langs=("he", "en"))
    assert [c.lang for c in chunks] == ["he", "en"]
    assert chunks[0].text == "שָׁלוֹם"
    assert chunks[1].text == "Peace"
    assert all(c.source == "sefaria" for c in chunks)
    assert all(c.ref == "Tanya 1:1" for c in chunks)


def test_segment_skips_missing_and_empty_languages() -> None:
    seg = _segment("Tanya 1:2", he="טֶקְסְט", en=None)
    assert [c.lang for c in segment_to_chunks(seg)] == ["he"]

    empty = _segment("Tanya 1:3", he="   <i></i>  ", en="")
    assert segment_to_chunks(empty) == []


def test_chunk_ids_are_deterministic() -> None:
    seg = _segment("Tanya 1:1", he="שלום", en=None)
    c1 = segment_to_chunks(seg)[0]
    c2 = segment_to_chunks(seg)[0]
    assert c1.id == c2.id == chunk_id("sefaria", "Tanya 1:1", "he")
    # Different language → different id.
    assert chunk_id("sefaria", "Tanya 1:1", "he") != chunk_id("sefaria", "Tanya 1:1", "en")


def test_lang_filter_restricts_output() -> None:
    seg = _segment("Tanya 1:1", he="שלום", en="Peace")
    assert [c.lang for c in segment_to_chunks(seg, langs=("he",))] == ["he"]


def test_section_to_chunks_preserves_order() -> None:
    section = SefariaSection(
        ref="Tanya 1",
        book="Tanya",
        section_names=["Chapter", "Paragraph"],
        segments=[
            _segment("Tanya 1:1", he="א", en=None),
            _segment("Tanya 1:2", he="ב", en=None),
        ],
    )
    chunks = section_to_chunks(section, langs=("he",))
    assert [c.ref for c in chunks] == ["Tanya 1:1", "Tanya 1:2"]
