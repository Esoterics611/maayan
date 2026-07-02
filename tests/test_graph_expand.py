"""Tests for Prompt 35 — graph-aware retrieval.

The invariant under test: the default-deny gate is decided on the SEED retrieval
alone. A refused query must never touch the graph (a spy enforces it), expansion
must only follow approved edges, budgets and filters hold, and every expanded hit
carries its via provenance. In-memory Qdrant + HashingEmbedder + seeded stores —
no network, no models.
"""

from __future__ import annotations

from datetime import UTC, datetime

from qdrant_client import QdrantClient

from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.embed.fake import HashingEmbedder
from maayan.generate.base import Message
from maayan.generate.rag import RAGService
from maayan.graph.models import Concept, ConceptEndpoint, RefEndpoint, Relation
from maayan.graph.store import GraphStore
from maayan.index.pipeline import index_chunks
from maayan.index.qdrant import QdrantIndex
from maayan.retrieve.graph_expand import GraphExpandingRetriever
from maayan.retrieve.retriever import Retriever

DIM = 128
T0 = datetime(2026, 7, 1, tzinfo=UTC)
TANYA = "Tanya, Part I; Likkutei Amarim 18:1"
TORAH_OHR = "Torah Ohr, Vayera 14:1"
SEED_TEXT = "אהבה מסותרת בלב כל ישראל מצד הנשמה"


class SpyGraph:
    """GraphStore wrapper that counts reads — proves a refusal never touches it."""

    def __init__(self, store: GraphStore) -> None:
        self._store = store
        self.calls = 0

    def neighbors(self, endpoint, *, types=None, status="approved"):  # noqa: ANN001, ANN201
        self.calls += 1
        return self._store.neighbors(endpoint, types=types, status=status)

    def list_concepts(self):  # noqa: ANN201
        self.calls += 1
        return self._store.list_concepts()


def _chunk(ref: str, text: str, *, source: str = "sefaria", lang: str = "he") -> Chunk:
    return Chunk.make(
        ref=ref, book=ref.split(",")[0], section_path=["x"], lang=lang,  # type: ignore[arg-type]
        text=text, source=source,
    )


def _edge(
    subject: str,
    obj: str,
    *,
    rel_type: str = "connects",
    status: str = "approved",
    author: str = "R. Ginsburgh",
) -> Relation:
    return Relation.make(
        subject=RefEndpoint(ref=subject), object=RefEndpoint(ref=obj),
        rel_type=rel_type, evidence="expert", confidence=1.0, status=status,  # type: ignore[arg-type]
        author=author, created_at=T0,
    )


class _Setup:
    """One in-memory world: seed chunk indexed in Qdrant, far chunks only walkable."""

    def __init__(self, *, seeds: int = 3, limit: int = 4, threshold: float = 0.9) -> None:
        self.chunks = ChunkStore(":memory:")
        self.graph = GraphStore(":memory:")
        self.spy = SpyGraph(self.graph)
        self.embedder = HashingEmbedder(dim=DIM)
        self.index = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
        self.index.ensure_collection()
        self.inner = Retriever(self.index, self.embedder, top_k=8)
        self.retriever = GraphExpandingRetriever(
            self.inner, self.spy, self.chunks,
            score_threshold=threshold, seeds=seeds, limit=limit,
        )

    def seed_searchable(self, chunk: Chunk) -> Chunk:
        """A chunk findable by search (in Qdrant) and resolvable (in the store)."""
        self.chunks.upsert_chunks([chunk])
        index_chunks(
            store=self.chunks, embedder=self.embedder, index=self.index, batch_size=8
        )
        return chunk

    def add_walkable(self, chunk: Chunk) -> Chunk:
        """A chunk NOT in Qdrant — reachable only by walking the graph."""
        self.chunks.upsert_chunks([chunk])
        self.chunks.mark_indexed([chunk.id])  # keep later index_chunks from adding it
        return chunk


def test_supported_query_retrieves_the_far_side_of_an_approved_edge() -> None:
    s = _Setup()
    s.seed_searchable(_chunk(TANYA, SEED_TEXT))
    far = s.add_walkable(_chunk(TORAH_OHR, "התגלות האהבה בעבודת התפילה"))
    s.graph.save_relation(_edge(TANYA, TORAH_OHR))

    result = s.retriever.retrieve(SEED_TEXT)  # exact text → cosine 1.0, gate passes

    refs = [r.ref for r in result.results]
    assert refs[0] == TANYA  # the seed leads
    assert far.ref in refs  # the far side arrived by knowledge, not search
    expanded = next(r for r in result.results if r.ref == far.ref)
    assert expanded.via is not None
    assert expanded.via.rel_type == "connects"
    assert expanded.via.author == "R. Ginsburgh"
    assert expanded.via.evidence == "expert"
    assert expanded.via.seed_ref == TANYA
    # Seed hits carry no via — the absence is meaningful.
    assert next(r for r in result.results if r.ref == TANYA).via is None
    # Seed relevance is untouched (the gate value must not be inflated by expansion).
    assert result.relevance == s.inner.retrieve(SEED_TEXT).relevance


def test_below_threshold_query_refuses_without_touching_the_graph() -> None:
    s = _Setup(threshold=0.99)
    s.seed_searchable(_chunk(TANYA, SEED_TEXT))
    s.graph.save_relation(_edge(TANYA, TORAH_OHR))

    result = s.retriever.retrieve("something entirely unrelated to the corpus")

    assert result.relevance < 0.99
    assert all(r.via is None for r in result.results)  # nothing expanded
    assert s.spy.calls == 0  # THE invariant: the graph was never consulted


def test_empty_seed_results_short_circuit_without_graph_calls() -> None:
    s = _Setup()  # nothing indexed at all
    result = s.retriever.retrieve("any question")
    assert result.results == []
    assert s.spy.calls == 0


def test_only_approved_relations_expand() -> None:
    s = _Setup()
    s.seed_searchable(_chunk(TANYA, SEED_TEXT))
    proposed_far = s.add_walkable(_chunk("Torah Ohr, Noach 2:1", "טקסט מוצע"))
    retracted_far = s.add_walkable(_chunk("Torah Ohr, Bo 3:1", "טקסט שנפסל"))
    s.graph.save_relation(_edge(TANYA, proposed_far.ref, status="proposed"))
    saved = s.graph.save_relation(_edge(TANYA, retracted_far.ref))
    s.graph.mark_retracted(saved.id)

    refs = [r.ref for r in s.retriever.retrieve(SEED_TEXT).results]
    assert proposed_far.ref not in refs
    assert retracted_far.ref not in refs


def test_expansion_budget_is_respected() -> None:
    s = _Setup(limit=2)
    s.seed_searchable(_chunk(TANYA, SEED_TEXT))
    for i in range(5):
        far = s.add_walkable(_chunk(f"Torah Ohr, Miketz {i}:1", f"מקור רחוק {i}"))
        s.graph.save_relation(_edge(TANYA, far.ref))

    result = s.retriever.retrieve(SEED_TEXT)
    assert sum(1 for r in result.results if r.via is not None) == 2


def test_out_of_corpus_anchors_and_retracted_chunks_are_skipped() -> None:
    s = _Setup()
    s.seed_searchable(_chunk(TANYA, SEED_TEXT))
    # A pasuk anchor with no local chunk, and a tombstoned far chunk.
    s.graph.save_relation(_edge(TANYA, "Deuteronomy 30:14", rel_type="quotes_pasuk"))
    tombstoned = s.add_walkable(_chunk("Torah Ohr, Yitro 1:1", "נמחק"))
    s.graph.save_relation(_edge(TANYA, tombstoned.ref))
    s.chunks.mark_retracted([tombstoned.id])

    result = s.retriever.retrieve(SEED_TEXT)
    assert all(r.via is None for r in result.results)  # nothing addable → seeds only


def test_source_filter_applies_to_expanded_chunks_too() -> None:
    s = _Setup()
    s.seed_searchable(_chunk(TANYA, SEED_TEXT))
    expert_far = s.add_walkable(
        _chunk("Expert · connection · x1", "תובנה של הרב", source="expert")
    )
    printed_far = s.add_walkable(_chunk(TORAH_OHR, "מקור מודפס"))
    s.graph.save_relation(_edge(TANYA, expert_far.ref))
    s.graph.save_relation(_edge(TANYA, printed_far.ref))

    refs = [r.ref for r in s.retriever.retrieve(SEED_TEXT, source="sefaria").results]
    assert printed_far.ref in refs
    assert expert_far.ref not in refs  # the A-text ablation stays honest


def test_concepts_named_in_the_query_expand_too() -> None:
    s = _Setup()
    s.seed_searchable(_chunk(TANYA, SEED_TEXT))
    s.add_walkable(_chunk(TORAH_OHR, "ביאור עניין הביטול"))
    concept = Concept.make(canonical="ביטול", author="R. Ginsburgh", created_at=T0)
    s.graph.save_concept(concept)
    s.graph.save_relation(Relation.make(
        subject=ConceptEndpoint(concept_id=concept.id), object=RefEndpoint(ref=TORAH_OHR),
        rel_type="defines", evidence="expert", confidence=1.0, status="approved",
        author="R. Ginsburgh", created_at=T0,
    ))

    result = s.retriever.retrieve(SEED_TEXT + " ביטול")
    expanded = [r for r in result.results if r.via is not None]
    assert [r.ref for r in expanded] == [TORAH_OHR]
    assert expanded[0].via is not None and expanded[0].via.seed_ref == "ביטול"


# -- through the RAG service: the gate and the grounding, end to end -------------

class _FakeBackend:
    """Scripted backend; also proves a refusal never generates."""

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, system_prompt: str, messages: list[Message]) -> str:
        self.calls += 1
        return "תשובה מבוססת [S1][S2]"


def test_rag_answer_cites_the_graph_expanded_source() -> None:
    s = _Setup()
    s.seed_searchable(_chunk(TANYA, SEED_TEXT))
    far = s.add_walkable(_chunk(TORAH_OHR, "התגלות האהבה"))
    s.graph.save_relation(_edge(TANYA, TORAH_OHR))
    backend = _FakeBackend()
    rag = RAGService(s.retriever, backend, score_threshold=0.9)

    answer = rag.ask(SEED_TEXT)

    assert answer.grounded
    assert far.ref in [src.ref for src in answer.sources]
    assert far.ref in answer.cited_refs  # [S2] resolved to the expanded source
    via_sources = [src for src in answer.sources if src.via is not None]
    assert len(via_sources) == 1  # provenance survives into the answer model


def test_rag_refusal_with_graph_wrapper_never_calls_model_or_graph() -> None:
    s = _Setup(threshold=0.99)
    s.seed_searchable(_chunk(TANYA, SEED_TEXT))
    backend = _FakeBackend()
    rag = RAGService(s.retriever, backend, score_threshold=0.99)

    answer = rag.ask("totally unrelated question about nothing")

    assert not answer.grounded
    assert backend.calls == 0
    assert s.spy.calls == 0
