"""Tests for MultiQueryRetriever — ephemeral Qdrant + hashing embedder, fake expander."""

from __future__ import annotations

from qdrant_client import QdrantClient

from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.embed.fake import HashingEmbedder
from maayan.index.pipeline import index_chunks
from maayan.index.qdrant import QdrantIndex
from maayan.retrieve.expand import ExpandedQuery
from maayan.retrieve.retriever import MultiQueryRetriever, Retriever

DIM = 128


def _chunk(ref: str, text: str) -> Chunk:
    return Chunk.make(
        ref=ref, book="Tanya", section_path=["Chapter 1", "Paragraph 1"],
        lang="he", text=text, source="sefaria",
    )


def _seeded_index(chunks: list[Chunk], embedder: HashingEmbedder) -> QdrantIndex:
    store = ChunkStore(":memory:")
    store.upsert_chunks(chunks)
    idx = QdrantIndex(QdrantClient(location=":memory:"), "test", embedder.dim)
    index_chunks(store=store, embedder=embedder, index=idx, batch_size=16)
    store.close()
    return idx


class FixedExpander:
    """Returns the same set of query variants regardless of input (test seam)."""

    def __init__(self, queries: list[str]) -> None:
        self._queries = queries

    def expand(self, query: str) -> ExpandedQuery:
        return ExpandedQuery(original=query, queries=self._queries)


def test_expansion_surfaces_hits_the_raw_query_misses() -> None:
    # The hashing embedder ranks by shared tokens. At k=1 the raw query "alpha"
    # surfaces only the alpha chunk; expanding to ["alpha", "beta"] and RRF-fusing
    # surfaces BOTH the alpha and beta chunks — the whole point of multi-query.
    emb = HashingEmbedder(dim=DIM)
    chunks = [
        _chunk("A 1:1", "alpha alpha alpha"),
        _chunk("B 1:1", "beta beta beta"),
        _chunk("C 1:1", "gamma gamma gamma"),
        _chunk("D 1:1", "delta delta delta"),
    ]
    # Each variant contributes its single top hit (base top_k=1); fusion returns top 2.
    base = Retriever(_seeded_index(chunks, emb), emb, top_k=1)

    # The raw "alpha" query's top hit is the alpha chunk — the beta chunk is missed.
    assert [r.ref for r in base.retrieve("alpha").results] == ["A 1:1"]

    # Expanding to ["alpha", "beta"] and fusing pulls the beta chunk in alongside it.
    mq = MultiQueryRetriever(base, FixedExpander(["alpha", "beta"]), top_k=2)
    assert {r.ref for r in mq.retrieve("alpha").results} == {"A 1:1", "B 1:1"}


def test_relevance_is_max_over_variants() -> None:
    emb = HashingEmbedder(dim=DIM)
    chunks = [_chunk("A 1:1", "alpha topic"), _chunk("B 1:1", "beta subject")]
    base = Retriever(_seeded_index(chunks, emb), emb, top_k=5)

    # A variant that matches a chunk exactly should drive relevance up, even if the
    # original (a nonsense token) matches nothing.
    matching = base.retrieve("alpha topic").relevance
    mq = MultiQueryRetriever(base, FixedExpander(["zzzznomatch", "alpha topic"]), top_k=5)
    assert mq.retrieve("zzzznomatch").relevance == matching
    assert matching > 0.0


def test_single_variant_matches_base_ranking() -> None:
    # With one variant equal to the query, fusion is a no-op on ordering.
    emb = HashingEmbedder(dim=DIM)
    chunks = [
        _chunk("A 1:1", "alpha beta gamma"),
        _chunk("B 1:1", "alpha beta"),
        _chunk("C 1:1", "delta"),
    ]
    base = Retriever(_seeded_index(chunks, emb), emb, top_k=3)
    mq = MultiQueryRetriever(base, FixedExpander(["alpha beta"]), top_k=3)
    base_refs = [r.ref for r in base.retrieve("alpha beta").results]
    mq_refs = [r.ref for r in mq.retrieve("alpha beta").results]
    assert mq_refs == base_refs


def test_respects_k_override() -> None:
    emb = HashingEmbedder(dim=DIM)
    chunks = [_chunk(f"R {i}", f"word{i} common") for i in range(5)]
    base = Retriever(_seeded_index(chunks, emb), emb, top_k=10)
    mq = MultiQueryRetriever(base, FixedExpander(["common"]), top_k=10)
    assert len(mq.retrieve("common", k=2).results) == 2
