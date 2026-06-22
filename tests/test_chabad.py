"""Tests for the Chabad Library ingester (Likutei Torah source) — network mocked.

A small fake tree (book → 1 parsha → 2 daf-pages) is served via respx so the tree
walk, HTML normalization, and chunk provenance are exercised with no real network.
"""

from __future__ import annotations

import httpx
import respx

from maayan.clock import FakeClock
from maayan.corpus.chabad import (
    ChabadLeaf,
    ChabadLibraryClient,
    chabad_leaf_to_chunks,
    ingest_chabad_book,
    split_passages,
)
from maayan.corpus.store import ChunkStore

BASE = "https://chabadlibrary.org/books/api"

# Fake tree: root 100 → parsha 200 → leaves 301, 302.
_TREE: dict[str, dict] = {
    "100": {"content": {"type": "children", "data": [{"id": 200, "heading": "פרשה ויקרא"}]}},
    "200": {
        "content": {
            "type": "children",
            "data": [{"id": 301, "heading": "א א"}, {"id": 302, "heading": "א ב"}],
        }
    },
    "301": {"content": {"type": "page", "data": {"text": "<h3>ויקרא</h3> <b>ויקרא אל משה</b>"}}},
    "302": {"content": {"type": "page", "data": {"text": "<p>טקסט שני</p>"}}},
}


def _route(request: httpx.Request) -> httpx.Response:
    path = request.url.params.get("path")
    return httpx.Response(200, json=_TREE[path])


def _client(http: httpx.AsyncClient) -> ChabadLibraryClient:
    return ChabadLibraryClient(http, FakeClock(), base_url=BASE, rate_limit_seconds=0.3)


@respx.mock
async def test_iter_leaves_walks_tree_with_heading_path() -> None:
    respx.get(url__regex=rf"{BASE}/main.*").mock(side_effect=_route)
    async with httpx.AsyncClient() as http:
        leaves = [leaf async for leaf in _client(http).iter_leaves(100)]
    assert [leaf.id for leaf in leaves] == [301, 302]
    # Each leaf carries its ancestor headings (parsha) plus its own (daf-amud).
    assert leaves[0].path == ["פרשה ויקרא", "א א"]
    assert "ויקרא אל משה" in leaves[0].text_html


@respx.mock
async def test_max_leaves_stops_early() -> None:
    respx.get(url__regex=rf"{BASE}/main.*").mock(side_effect=_route)
    async with httpx.AsyncClient() as http:
        leaves = [leaf async for leaf in _client(http).iter_leaves(100, max_leaves=1)]
    assert len(leaves) == 1


def test_chabad_leaf_to_chunks_strips_html_keeps_provenance() -> None:
    leaf = ChabadLeaf(id=301, path=["פרשה ויקרא", "א א"], text_html="<h3>ויקרא</h3> <b>טקסט</b>")
    [chunk] = chabad_leaf_to_chunks(leaf, book="Likutei Torah")  # short → one chunk
    assert chunk.source == "chabad"
    assert chunk.book == "Likutei Torah"
    assert chunk.ref == "Likutei Torah, פרשה ויקרא, א א"
    assert chunk.lang == "he"
    assert "<" not in chunk.text and "ויקרא" in chunk.text  # HTML stripped, text kept
    assert chunk.metadata["provider"] == "chabadlibrary.org"
    assert chunk.metadata["section_id"] == 301


def test_chabad_leaf_to_chunks_skips_empty() -> None:
    assert chabad_leaf_to_chunks(ChabadLeaf(id=9, path=["x"], text_html="  "), book="LT") == []


def test_split_passages_packs_whole_sentences() -> None:
    # Three ~20-char sentences; max 25 → each (or pairs) split at sentence boundaries.
    text = "ראשון כאן עכשיו טוב. שני כאן עכשיו טוב. שלישי כאן עכשיו טוב."
    parts = split_passages(text, max_chars=25)
    assert len(parts) >= 2
    assert all(len(p) <= 40 for p in parts)  # bounded, never mid-sentence
    assert "".join(parts).count("טוב") == 3  # every sentence preserved
    # Disabled / short stays whole.
    assert split_passages(text, max_chars=0) == [text]
    assert split_passages("short.", max_chars=1000) == ["short."]


def test_long_leaf_splits_into_numbered_passages() -> None:
    long_html = " ".join(f"משפט מספר {i} עם תוכן נוסף כאן." for i in range(40))
    chunks = chabad_leaf_to_chunks(
        ChabadLeaf(id=7, path=["פרשה ויקרא", "א א"], text_html=long_html),
        book="Likutei Torah", max_chars=200,
    )
    assert len(chunks) > 1
    assert chunks[0].ref == "Likutei Torah, פרשה ויקרא, א א §1"
    assert chunks[1].ref == "Likutei Torah, פרשה ויקרא, א א §2"
    assert chunks[1].metadata["passage"] == 2
    assert chunks[1].metadata["section_id"] == 7  # same source section, traceable


@respx.mock
async def test_ingest_chabad_book_upserts_chunks_idempotently() -> None:
    respx.get(url__regex=rf"{BASE}/main.*").mock(side_effect=_route)
    with ChunkStore(":memory:") as store:
        async with httpx.AsyncClient() as http:
            client = _client(http)
            result = await ingest_chabad_book(100, "Likutei Torah", client=client, store=store)
            assert result.book == "Likutei Torah"
            assert result.sections == 2 and result.chunks == 2
            assert store.count(source="chabad") == 2
            # Re-ingest is an upsert (stable ids), not a duplicate.
            again = await ingest_chabad_book(100, "Likutei Torah", client=client, store=store)
            assert again.chunks == 2
            assert store.count(source="chabad") == 2
