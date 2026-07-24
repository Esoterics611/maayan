"""Tests for the retrieval inspector — ephemeral Qdrant, hashing embedder, no network."""

from __future__ import annotations

from collections.abc import Sequence

from qdrant_client import QdrantClient

from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.embed.fake import HashingEmbedder
from maayan.index.pipeline import index_chunks
from maayan.index.qdrant import QdrantIndex
from maayan.retrieve.expand import ExpandedQuery
from maayan.retrieve.inspect import RetrievalInspector
from maayan.retrieve.trace import format_trace

DIM = 128


def _chunk(ref: str, text: str, source: str = "sefaria") -> Chunk:
    return Chunk.make(
        ref=ref, book="Tanya", section_path=["Chapter 1"],
        lang="he", text=text, source=source,  # type: ignore[arg-type]
    )


def _index(chunks: list[Chunk], embedder: HashingEmbedder) -> QdrantIndex:
    store = ChunkStore(":memory:")
    store.upsert_chunks(chunks)
    idx = QdrantIndex(QdrantClient(location=":memory:"), "test", embedder.dim)
    index_chunks(store=store, embedder=embedder, index=idx, batch_size=16)
    store.close()
    return idx


CHUNKS = [
    _chunk("Free 1:1", "בחירה חופשית של האדם בעבודת השם"),
    _chunk("Prayer 1:1", "עבודת התפילה והכוונה שבלב"),
    _chunk("Love 1:1", "אהבת השם יתברך בכל לבבך"),
]


def _inspector(**kwargs: object) -> RetrievalInspector:
    emb = HashingEmbedder(dim=DIM)
    return RetrievalInspector(_index(CHUNKS, emb), emb, **kwargs)  # type: ignore[arg-type]


def test_trace_reports_every_branch_separately() -> None:
    trace = _inspector(threshold=0.0, pool=3).inspect("בחירה חופשית")
    assert len(trace.queries) == 1
    names = [s.name for s in trace.queries[0].stages]
    assert names == ["dense", "sparse", "fused"]  # no reranker → no rerank stage
    for stage in trace.queries[0].stages:
        assert stage.hits, f"{stage.name} returned nothing"
        # Ranks are 0-based and contiguous, scores descending.
        assert [h.rank for h in stage.hits] == list(range(len(stage.hits)))
        assert all(
            a.score >= b.score for a, b in zip(stage.hits, stage.hits[1:], strict=False)
        )
    assert trace.results[0].ref == "Free 1:1"


def test_gate_signals_are_populated_and_pooled() -> None:
    trace = _inspector(threshold=0.0, pool=3).inspect("בחירה חופשית")
    s = trace.signals
    assert s.pool == 3
    # A real lexical overlap exists, so both branches score above zero...
    assert s.dense_top > 0.0 and s.sparse_top > 0.0
    # ...and the top of a branch is never below its pooled mean.
    assert s.dense_top >= s.dense_mean
    assert s.sparse_top >= s.sparse_mean


def test_gate_decision_follows_the_threshold() -> None:
    answered = _inspector(threshold=0.0).inspect("בחירה חופשית")
    assert answered.answered and answered.decision == "ANSWER"
    assert answered.gate_signal == "dense_top"
    assert answered.relevance == answered.signals.dense_top

    refused = _inspector(threshold=1.5).inspect("בחירה חופשית")
    assert not refused.answered and refused.decision == "REFUSE"
    # Refusing does not hide what WAS found — that is the point of the trace.
    assert refused.queries[0].stages[0].hits


class _FakeReranker:
    """Scores documents by whether they contain a token."""

    def __init__(self, token: str) -> None:
        self._token = token

    def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        return [9.0 if self._token in doc else 0.5 for doc in documents]


def test_reranker_adds_a_stage_and_becomes_the_gate_signal() -> None:
    trace = _inspector(threshold=1.0, reranker=_FakeReranker("תפילה")).inspect("עבודת השם")
    stage_names = [s.name for s in trace.queries[0].stages]
    assert stage_names == ["dense", "sparse", "fused", "rerank"]
    # The cross-encoder score replaces cosine as the gate signal (as in Retriever).
    assert trace.gate_signal == "rerank_top"
    assert trace.relevance == 9.0
    assert trace.signals.rerank_top == 9.0
    # ...and it reorders the ranking the caller gets.
    assert trace.results[0].ref == "Prayer 1:1"


class _FakeExpander:
    """Expands into a fixed set of variants."""

    def expand(self, query: str) -> ExpandedQuery:
        return ExpandedQuery(original=query, queries=[query, "אהבת השם"])


def test_expansion_shows_every_query_actually_sent() -> None:
    trace = _inspector(threshold=0.0, expander=_FakeExpander()).inspect("בחירה חופשית")
    assert [q.query for q in trace.queries] == ["בחירה חופשית", "אהבת השם"]
    # Aggregate signals take the best any variant achieved (as MultiQueryRetriever does).
    assert trace.signals.dense_top == max(q.signals.dense_top for q in trace.queries)


def test_stage_rank_of_finds_cross_stage_agreement() -> None:
    trace = _inspector(threshold=0.0).inspect("בחירה חופשית")
    dense = trace.queries[0].stage("dense")
    fused = trace.queries[0].stage("fused")
    assert dense is not None and fused is not None
    assert dense.rank_of("Free 1:1") == 0
    assert fused.rank_of("Free 1:1") is not None
    assert dense.rank_of("Nonexistent 9:9") is None


def test_format_trace_renders_stages_signals_and_decision() -> None:
    text = format_trace(_inspector(threshold=1.5).inspect("בחירה חופשית"))
    assert "[dense]" in text and "[sparse]" in text and "[fused]" in text
    assert "GATE: REFUSE" in text
    assert "dense_top=" in text and "sparse_mean@" in text
    assert "Free 1:1" in text
