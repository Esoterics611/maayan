"""Tests for hybrid retrieval — ephemeral Qdrant, hashing embedder, mocked reranker."""

from __future__ import annotations

from collections.abc import Sequence

from qdrant_client import QdrantClient

from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.embed.fake import HashingEmbedder
from maayan.index.pipeline import index_chunks
from maayan.index.qdrant import QdrantIndex
from maayan.retrieve.models import SearchResult
from maayan.retrieve.retriever import Retriever, _rank_key

DIM = 128


def _chunk(ref: str, text: str, source: str = "sefaria", lang: str = "he") -> Chunk:
    return Chunk.make(
        ref=ref, book="Tanya", section_path=["Chapter 1", "Paragraph 1"],
        lang=lang, text=text, source=source,  # type: ignore[arg-type]
    )


def _seeded_index(chunks: list[Chunk], embedder: HashingEmbedder) -> QdrantIndex:
    store = ChunkStore(":memory:")
    store.upsert_chunks(chunks)
    idx = QdrantIndex(QdrantClient(location=":memory:"), "test", embedder.dim)
    index_chunks(store=store, embedder=embedder, index=idx, batch_size=16)
    store.close()
    return idx


def test_hybrid_retrieves_relevant_above_unrelated() -> None:
    emb = HashingEmbedder(dim=DIM)
    chunks = [
        _chunk("Free 1:1", "בחירה חופשית של האדם בעבודת השם"),
        _chunk("Prayer 1:1", "עבודת התפילה והכוונה שבלב"),
        _chunk("Love 1:1", "אהבת השם יתברך בכל לבבך"),
    ]
    retriever = Retriever(_seeded_index(chunks, emb), emb, top_k=3)
    results = retriever.search("בחירה חופשית")
    assert results[0].ref == "Free 1:1"
    assert results[0].score >= results[-1].score


def test_shiur_boost_promotes_shiur_source() -> None:
    emb = HashingEmbedder(dim=DIM)
    chunks = [
        _chunk("Sefaria 1:1", "בחירה חופשית של האדם", source="sefaria"),
        _chunk("Shiur: Demo §1", "בחירה חופשית של האדם", source="shiur"),
    ]
    idx = _seeded_index(chunks, emb)
    # Identical text → tied scores; a strong shiur_boost makes the shiur win.
    boosted = Retriever(idx, emb, top_k=5, shiur_boost=5.0).search("בחירה חופשית")
    assert boosted[0].source == "shiur"


def test_metadata_filter_by_source() -> None:
    emb = HashingEmbedder(dim=DIM)
    chunks = [
        _chunk("Sefaria 1:1", "בחירה חופשית של האדם", source="sefaria"),
        _chunk("Expert 1", "בחירה חופשית לפי המורה", source="expert"),
    ]
    retriever = Retriever(_seeded_index(chunks, emb), emb, top_k=5)
    expert_only = retriever.search("בחירה חופשית", source="expert")
    assert {r.source for r in expert_only} == {"expert"}
    assert all(r.ref == "Expert 1" for r in expert_only)


def test_rank_key_breaks_rrf_ties_deterministically() -> None:
    # RRF yields exact score ties; Qdrant returns them in arbitrary order. The rank
    # key must impose score-desc, then ref-asc — independent of input order.
    def _r(ref: str, score: float) -> SearchResult:
        return SearchResult(ref=ref, text="", score=score, lang="he", source="sefaria", payload={})

    scrambled = [_r("Tanya 5", 0.5), _r("Tanya 2", 0.9), _r("Tanya 1", 0.5), _r("Tanya 3", 0.9)]
    ranked = [r.ref for r in sorted(scrambled, key=_rank_key)]
    # Higher score first; within a tied score, refs ascending — and stable across runs.
    assert ranked == ["Tanya 2", "Tanya 3", "Tanya 1", "Tanya 5"]
    assert ranked == [r.ref for r in sorted(reversed(scrambled), key=_rank_key)]


class _FakeReranker:
    """Reranker that ranks by a target ref appearing in the document text."""

    def __init__(self, boost_token: str) -> None:
        self._token = boost_token

    def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        return [10.0 if self._token in doc else 0.0 for doc in documents]


def test_reranker_reorders_candidates() -> None:
    emb = HashingEmbedder(dim=DIM)
    chunks = [
        _chunk("A 1:1", "בחירה חופשית רגילה"),
        _chunk("B 1:1", "בחירה חופשית עם המילה הסודית פלא"),
    ]
    idx = _seeded_index(chunks, emb)

    # Without rerank, A may rank first; with a reranker favoring "פלא", B wins.
    reranker = _FakeReranker("פלא")
    retriever = Retriever(idx, emb, top_k=2, reranker=reranker, rerank_candidates=10)
    results = retriever.search("בחירה חופשית")
    assert results[0].ref == "B 1:1"
    assert results[0].score == 10.0


def test_expert_boost_scales_expert_scores() -> None:
    emb = HashingEmbedder(dim=DIM)
    chunks = [
        _chunk("Sefaria 1:1", "בחירה חופשית של האדם", source="sefaria"),
        _chunk("Expert 1", "בחירה חופשית של האדם", source="expert"),
    ]
    idx = _seeded_index(chunks, emb)

    baseline = Retriever(idx, emb, top_k=5, expert_boost=1.0).search("בחירה חופשית")
    boosted = Retriever(idx, emb, top_k=5, expert_boost=5.0).search("בחירה חופשית")

    expert_base = next(r.score for r in baseline if r.source == "expert")
    expert_boosted = next(r.score for r in boosted if r.source == "expert")
    assert expert_boosted > expert_base
    # With a large boost, the expert chunk should surface first.
    assert boosted[0].source == "expert"
