"""Tests for connection auto-population: cross-text mining, grounded drafting, gate.

No network, no real models: the retriever and generation backend are fakes, the
embedder is the hashing stub, Qdrant/SQLite run in memory.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from qdrant_client import QdrantClient

from maayan.capture.populate import (
    ConnectionCandidate,
    ConnectionDrafter,
    ConnectionEnd,
    ConnectionPopulator,
    ConnectionSuggestion,
    book_of,
    mine_connection_candidates,
)
from maayan.capture.service import CaptureService
from maayan.capture.store import CaptureStore
from maayan.capture.suggestions import ConnectionSuggestionStore
from maayan.clock import FakeClock
from maayan.corpus.store import ChunkStore
from maayan.embed.fake import HashingEmbedder
from maayan.generate.base import Message
from maayan.index.qdrant import QdrantIndex
from maayan.retrieve.models import RetrievalResult, SearchResult

DIM = 128


# -- fakes --------------------------------------------------------------------

class FakeRetriever:
    """Returns a fixed result list for any query."""

    def __init__(self, results: list[SearchResult], relevance: float = 0.7) -> None:
        self._result = RetrievalResult(results=results, relevance=relevance)

    def retrieve(
        self, query: str, *, k: int | None = None, book: str | None = None,
        source: str | None = None,
    ) -> RetrievalResult:
        return self._result


class SequencedBackend:
    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[tuple[str, list[Message]]] = []

    def generate(self, system: str, messages: Sequence[Message]) -> str:
        self.calls.append((system, list(messages)))
        return self._replies.pop(0)


def _src(ref: str, text: str = "טקסט", source: str = "sefaria") -> SearchResult:
    return SearchResult(ref=ref, text=text, score=0.6, lang="he", source=source,
                        payload={"ref": ref})


def _candidate() -> ConnectionCandidate:
    return ConnectionCandidate(query="ביטול", ends=[
        ConnectionEnd(ref="Tanya, Part I; Likkutei Amarim 19", book="Tanya", text="אהבה מסותרת"),
        ConnectionEnd(ref="Torah Ohr, Bereshit 2", book="Torah Ohr", text="ענין הביטול"),
    ])


# -- book_of + mining ---------------------------------------------------------

def test_book_of_uses_payload_then_ref_prefix() -> None:
    assert book_of(_src("Tanya, Part I; Likkutei Amarim 1")) == "Tanya"
    assert book_of(_src("Torah Ohr, Bereshit 2")) == "Torah Ohr"
    assert book_of(_src("Likutei Torah, Bamidbar")) == "Likutei Torah"


def test_mine_pairs_only_across_distinct_books() -> None:
    results = [
        _src("Tanya, Part I; Likkutei Amarim 19"),
        _src("Torah Ohr, Bereshit 2"),
        _src("Likutei Torah, Bamidbar"),
    ]
    cands = mine_connection_candidates(FakeRetriever(results), ["ביטול"], k=8, max_per_probe=5)
    pairs = {frozenset(e.book for e in c.ends) for c in cands}
    assert {"Tanya", "Torah Ohr"} in pairs
    assert {"Tanya", "Likutei Torah"} in pairs
    assert {"Torah Ohr", "Likutei Torah"} in pairs
    # every candidate spans two different books
    assert all(c.ends[0].book != c.ends[1].book for c in cands)


def test_mine_skips_same_book_and_curated_sources() -> None:
    results = [
        _src("Tanya, Part I; Likkutei Amarim 1"),
        _src("Tanya, Part I; Likkutei Amarim 2"),          # same book → no pair
        _src("Term · ע\"ב", source="term"),                 # curated layer → excluded
    ]
    assert mine_connection_candidates(FakeRetriever(results), ["x"]) == []


def test_mine_dedupes_pairs_across_probes() -> None:
    results = [_src("Tanya, Part I; Likkutei Amarim 19"), _src("Torah Ohr, Bereshit 2")]
    cands = mine_connection_candidates(FakeRetriever(results), ["a", "b", "c"], max_per_probe=5)
    assert len(cands) == 1                                  # same pair surfaced by 3 probes → once


# -- drafter: cross-text grounding gate --------------------------------------

def _drafter(backend: SequencedBackend, *, verify: bool = True) -> ConnectionDrafter:
    return ConnectionDrafter(backend, FakeClock(), model="fake-model", verify=verify)


def test_supported_connection_cites_both_ends_and_passes_verify() -> None:
    backend = SequencedBackend(["שני המקורות מבארים את הביטול [S1][S2].", "OK"])
    sug = _drafter(backend).draft(_candidate())
    assert sug.supported is True
    assert set(sug.source_refs) == {"Tanya, Part I; Likkutei Amarim 19", "Torah Ohr, Bereshit 2"}
    assert sug.books == ["Tanya", "Torah Ohr"]
    assert len(backend.calls) == 2                          # draft + verify
    assert "SOURCES:" in backend.calls[0][1][0].content     # both ends handed to the model


def test_one_sided_connection_is_unsupported() -> None:
    # Cites only [S1] → draws on a single book → not a cross-text connection.
    backend = SequencedBackend(["רק מקור אחד [S1].", "OK"])
    sug = _drafter(backend).draft(_candidate())
    assert sug.supported is False


def test_insufficient_reply_is_unsupported_without_verify() -> None:
    backend = SequencedBackend(["INSUFFICIENT"])
    sug = _drafter(backend).draft(_candidate())
    assert sug.supported is False and sug.statement == ""
    assert len(backend.calls) == 1                          # no verify after a refusal


def test_verify_flag_makes_connection_unsupported() -> None:
    backend = SequencedBackend(["טענה [S1][S2].", "טענה [S1][S2]."])  # verifier flags one line
    sug = _drafter(backend).draft(_candidate())
    assert sug.supported is False
    assert sug.unsupported_claims == ["טענה [S1][S2]."]


# -- populator: queue + expert-gate approval ---------------------------------

def _populator(drafter: ConnectionDrafter) -> tuple[ConnectionPopulator, ChunkStore]:
    embedder = HashingEmbedder(dim=DIM)
    index = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
    chunks = ChunkStore(":memory:")
    capture = CaptureService(CaptureStore(":memory:"), chunks, embedder, index, FakeClock(),
                             allowed_kinds=["connection"])
    pop = ConnectionPopulator(drafter, ConnectionSuggestionStore(":memory:"), capture)
    return pop, chunks


def test_approve_indexes_connection_chunk() -> None:
    backend = SequencedBackend(["שני המקורות מבארים את הביטול [S1][S2].", "OK"])
    pop, chunks = _populator(_drafter(backend))

    [sug] = pop.suggest([_candidate()])
    assert sug.supported is True and len(pop.list_pending()) == 1

    ann = pop.approve(sug.id, author="R. Rendel")
    assert ann.kind == "connection" and ann.author == "R. Rendel"
    assert ann.linked_refs == sug.refs
    assert chunks.count(source="expert") == 1               # the connection is now retrievable
    assert pop.list_pending() == []                         # left the queue


def test_approve_refuses_unsupported_connection() -> None:
    store = ConnectionSuggestionStore(":memory:")
    pop, _ = _populator(_drafter(SequencedBackend([])))
    pop = ConnectionPopulator(pop._drafter, store, pop._capture)  # share store we can poke
    bad = store.create(ConnectionSuggestion(id="x", query="q", supported=False,
                                            created_at=datetime(2026, 1, 1, tzinfo=UTC)))
    with pytest.raises(ValueError):
        pop.approve(bad.id, author="A")


# -- suggestion store roundtrip ----------------------------------------------

def test_connection_suggestion_store_roundtrip_and_status() -> None:
    store = ConnectionSuggestionStore(":memory:")
    sug = ConnectionSuggestion(
        id="c1", query="ביטול", refs=["Tanya 19", "Torah Ohr 2"], books=["Tanya", "Torah Ohr"],
        statement="ביאור [S1][S2]", source_refs=["Tanya 19", "Torah Ohr 2"], supported=True,
        model="m", created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    store.create(sug)
    [back] = store.list(status="pending")
    assert back.books == ["Tanya", "Torah Ohr"] and back.supported is True
    store.set_status("c1", "approved")
    assert store.list(status="pending") == [] and store.count(status="approved") == 1
