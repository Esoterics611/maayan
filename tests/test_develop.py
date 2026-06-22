"""Tests for the develop step — grounded, cited, refuses honestly (retriever+backend mocked)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from qdrant_client import QdrantClient

from maayan.capture.models import Annotation
from maayan.clock import FakeClock
from maayan.config import Settings
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.develop.service import DevelopmentService
from maayan.develop.store import DevelopmentStore
from maayan.embed.fake import HashingEmbedder
from maayan.generate.base import Message
from maayan.index.pipeline import index_chunks
from maayan.index.qdrant import QdrantIndex
from maayan.retrieve.models import RetrievalResult, SearchResult
from maayan.retrieve.retriever import Retriever
from maayan.threads.service import ThreadService
from maayan.threads.store import ThreadStore

DIM = 128


class FakeRetriever:
    def __init__(self, results: list[SearchResult], relevance: float) -> None:
        self._result = RetrievalResult(results=results, relevance=relevance)
        self.queries: list[str] = []

    def retrieve(self, query: str, *, k=None, book=None, source=None) -> RetrievalResult:
        self.queries.append(query)
        return self._result


class RecordingBackend:
    def __init__(self, reply: str = "Developed, grounded in [S1].") -> None:
        self.reply = reply
        self.calls: list[tuple[str, list[Message]]] = []

    def generate(self, system: str, messages: Sequence[Message]) -> str:
        self.calls.append((system, list(messages)))
        return self.reply


def _seed() -> Annotation:
    return Annotation(
        id="seed-1", session_id="s1", timestamp=FakeClock().now(), author="R. Ginsburgh",
        kind="connection", body="אהבה בתענוגים היא גילוי שם ע\"ב", opens_aspect=True,
        directive="מצא היכן זה נרמז בתניא",
    )


def _result(ref: str, text: str = "t") -> SearchResult:
    return SearchResult(ref=ref, text=text, score=0.6, lang="he", source="sefaria", payload={})


class Harness(NamedTuple):
    svc: DevelopmentService
    store: DevelopmentStore
    threads: ThreadService
    settings: Settings
    chunks: ChunkStore
    index: QdrantIndex
    embedder: HashingEmbedder


def _harness(
    retriever: FakeRetriever,
    backend: RecordingBackend,
    *,
    threshold: float = 0.4,
    auto_approve: bool = False,
    derived_boost: float = 1.0,
) -> Harness:
    store = DevelopmentStore(":memory:")
    threads = ThreadService(ThreadStore(":memory:"), FakeClock())
    embedder = HashingEmbedder(dim=DIM)
    index = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
    chunks = ChunkStore(":memory:")
    settings = Settings(
        score_threshold=threshold, develop_top_k=5,
        develop_auto_approve=auto_approve, derived_boost=derived_boost,
    )
    svc = DevelopmentService(
        retriever, backend, store, threads, FakeClock(), settings, embedder, chunks, index
    )
    return Harness(svc, store, threads, settings, chunks, index, embedder)


def test_below_threshold_refuses_without_calling_model() -> None:
    backend = RecordingBackend()
    h = _harness(FakeRetriever([_result("Tanya 1:1")], relevance=0.1), backend)
    thread = h.threads.start_thread("t")

    dev = h.svc.develop(_seed(), thread_id=thread.id)

    assert dev.grounded is False
    assert dev.model == ""  # no model call
    assert dev.cited_refs == [] and dev.grounded_in == []
    assert backend.calls == []  # default-deny: model never called
    assert h.store.get_development(dev.id) is not None  # refusal still persisted


def test_empty_retrieval_refuses() -> None:
    backend = RecordingBackend()
    h = _harness(FakeRetriever([], relevance=0.0), backend)
    thread = h.threads.start_thread("t")
    dev = h.svc.develop(_seed(), thread_id=thread.id)
    assert dev.grounded is False
    assert backend.calls == []


def test_grounded_development_cites_records_provenance_and_appends_turn() -> None:
    backend = RecordingBackend(reply="כפי שנרמז [S1], וגם [S2].")
    results = [
        _result("Tanya, Part I; Likkutei Amarim 1:6"),
        _result("Tanya, Part I; Likkutei Amarim 9:1"),
    ]
    h = _harness(FakeRetriever(results, relevance=0.7), backend)
    thread = h.threads.start_thread("ahava b'ta'anugim")
    seed = _seed()

    dev = h.svc.develop(seed, thread_id=thread.id)

    assert dev.grounded is True
    assert dev.cited_refs == [
        "Tanya, Part I; Likkutei Amarim 1:6", "Tanya, Part I; Likkutei Amarim 9:1"
    ]
    assert dev.grounded_in == [r.ref for r in results]
    # Provenance: which seed, whose seed, which thread, which model.
    assert dev.seed_id == seed.id
    assert dev.author == "R. Ginsburgh"
    assert dev.thread_id == thread.id
    assert dev.model == h.settings.generation_model
    assert dev.status == "proposed"
    # Persisted + a development turn appended to the thread, pointing back at the dev.
    assert h.store.get_development(dev.id) is not None
    turns = h.threads.get_thread_with_turns(thread.id).turns  # type: ignore[union-attr]
    assert turns[-1].turn_type == "development"
    assert turns[-1].record_id == dev.id


def test_seed_framework_passed_as_noncitable_and_query_uses_directive() -> None:
    backend = RecordingBackend(reply="[S1]")
    retriever = FakeRetriever([_result("Tanya 1:6")], relevance=0.7)
    h = _harness(retriever, backend)
    thread = h.threads.start_thread("t")
    seed = _seed()

    h.svc.develop(seed, thread_id=thread.id)

    system, messages = backend.calls[0]
    content = messages[0].content
    # The seed framework + directive are in the prompt, labelled non-citable.
    assert "EXPERT SEED" in content
    assert seed.body in content
    assert seed.directive in content  # type: ignore[operator]
    assert "do NOT cite" in content
    # System prompt forbids citing the seed as a source.
    assert "never cite it as a retrieved source" in system.lower() or "attribute" in system.lower()
    # Retrieval query fused the seed body + directive.
    assert seed.body in retriever.queries[0]
    assert seed.directive in retriever.queries[0]  # type: ignore[operator]


# -- Prompt 13: approval gate → derived corpus chunks -------------------------

def test_approve_indexes_derived_chunk_retrievable_with_provenance() -> None:
    backend = RecordingBackend(reply="פיתוח הרעיון בתניא")
    h = _harness(FakeRetriever([_result("Tanya 1:6", "אהבת עולם")], relevance=0.7), backend)
    thread = h.threads.start_thread("t")
    dev = h.svc.develop(_seed(), thread_id=thread.id)
    assert dev.status == "proposed"

    approved = h.svc.approve(dev.id)
    assert approved.status == "approved"
    # Persisted as a derived corpus chunk, marked indexed (so rebuild keeps it).
    assert h.chunks.count(source="derived") == 1
    assert h.chunks.count(only_unindexed=True) == 0

    # Retrievable from Qdrant with full provenance.
    found = Retriever(h.index, h.embedder, top_k=5).search("פיתוח")
    derived = [r for r in found if r.source == "derived"]
    assert derived, "approved development should be retrievable as a derived chunk"
    meta = derived[0].payload["metadata"]
    assert meta["author"] == "R. Ginsburgh"
    assert meta["developed_by"] == h.settings.generation_model
    assert meta["grounded_in"] == ["Tanya 1:6"]
    assert meta["seed_id"] == "seed-1"
    assert meta["development_id"] == dev.id


def test_reject_indexes_nothing() -> None:
    h = _harness(FakeRetriever([_result("Tanya 1:6")], relevance=0.7), RecordingBackend())
    thread = h.threads.start_thread("t")
    dev = h.svc.develop(_seed(), thread_id=thread.id)

    rejected = h.svc.reject(dev.id)
    assert rejected.status == "rejected"
    assert h.chunks.count(source="derived") == 0


def test_auto_approve_indexes_immediately() -> None:
    backend = RecordingBackend(reply="פיתוח [S1]")
    h = _harness(FakeRetriever([_result("Tanya 1:6")], relevance=0.7), backend, auto_approve=True)
    thread = h.threads.start_thread("t")

    dev = h.svc.develop(_seed(), thread_id=thread.id)

    assert dev.status == "approved"
    assert h.chunks.count(source="derived") == 1


def test_cannot_approve_a_refusal() -> None:
    import pytest

    h = _harness(FakeRetriever([_result("Tanya 1:6")], relevance=0.1), RecordingBackend())
    thread = h.threads.start_thread("t")
    dev = h.svc.develop(_seed(), thread_id=thread.id)  # below threshold → refusal
    with pytest.raises(ValueError, match="ungrounded"):
        h.svc.approve(dev.id)


def test_derived_boost_changes_ranking() -> None:
    # Seed a sefaria chunk and an approved derived chunk that both match the query.
    backend = RecordingBackend(reply="נפש הבהמית קשורה לכוחות הנפש")
    h = _harness(FakeRetriever([_result("Tanya 1:6")], relevance=0.7), backend, auto_approve=True)
    h.chunks.upsert_chunks([
        Chunk.make(ref="Tanya 1:6", book="Tanya", section_path=["1", "6"],
                   lang="he", text="נפש הבהמית", source="sefaria")
    ])
    index_chunks(store=h.chunks, embedder=h.embedder, index=h.index, batch_size=8)
    thread = h.threads.start_thread("t")
    h.svc.develop(_seed(), thread_id=thread.id)  # auto-approved derived chunk

    boosted = Retriever(h.index, h.embedder, top_k=5, derived_boost=8.0)
    top = boosted.search("נפש הבהמית")
    assert top[0].source == "derived"  # the boost lifts approved knowledge to the top
