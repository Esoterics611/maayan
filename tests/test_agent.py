"""Tests for Prompt 39 — the bounded chavrusa agent.

Scripted fake backend, in-memory Qdrant, seeded graph. The invariants: a refused
seed never calls the backend and persists no trace; a deterministic 3-hop path
(search → walk_graph → conclude) answers citing a chunk only reachable via the
walk; every budget cap force-concludes honestly; a malformed action gets exactly
one repair retry; the trace's step/call accounting is exact.
"""

from __future__ import annotations

from datetime import UTC, datetime

from qdrant_client import QdrantClient

from maayan.agent.models import ConcludeAction, SearchAction, WalkGraphAction
from maayan.agent.service import AgentService
from maayan.agent.store import TraceStore
from maayan.clock import FakeClock
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.embed.fake import HashingEmbedder
from maayan.generate.base import Message
from maayan.generate.rag import RAGService
from maayan.graph.models import RefEndpoint, Relation
from maayan.graph.store import GraphStore
from maayan.index.pipeline import index_chunks
from maayan.index.qdrant import QdrantIndex
from maayan.lexicon.models import Term
from maayan.lexicon.store import TermStore
from maayan.retrieve.retriever import Retriever

DIM = 128
T0 = datetime(2026, 7, 1, tzinfo=UTC)
TANYA = "Tanya, Part I; Likkutei Amarim 37:1"
TORAH_OHR = "Torah Ohr, Vayigash 1:1"
SEED_TEXT = "עבודת הבירורים בניצוצות הקדושה"


class ScriptedBackend:
    """Returns scripted replies in order; counts every call."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls = 0

    def generate(self, system_prompt: str, messages: list[Message]) -> str:
        self.calls += 1
        if not self.replies:
            raise AssertionError("backend called more times than the script allows")
        return self.replies.pop(0)


class World:
    def __init__(
        self,
        replies: list[str],
        *,
        threshold: float = 0.9,
        max_hops: int = 4,
        max_chunks: int = 12,
        max_calls: int = 6,
    ) -> None:
        self.chunks = ChunkStore(":memory:")
        self.graph = GraphStore(":memory:")
        self.terms = TermStore(":memory:")
        self.traces = TraceStore(":memory:")
        self.embedder = HashingEmbedder(dim=DIM)
        self.index = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
        self.index.ensure_collection()
        self.retriever = Retriever(self.index, self.embedder, top_k=8)
        self.backend = ScriptedBackend(replies)
        self.rag = RAGService(self.retriever, self.backend, score_threshold=threshold)  # type: ignore[arg-type]
        self.agent = AgentService(
            self.retriever, self.rag, self.backend, self.chunks, self.graph,  # type: ignore[arg-type]
            self.terms, self.traces, FakeClock(T0),
            score_threshold=threshold, max_hops=max_hops,
            max_chunks=max_chunks, max_calls=max_calls,
        )

    def seed_searchable(self, ref: str = TANYA, text: str = SEED_TEXT) -> Chunk:
        chunk = Chunk.make(
            ref=ref, book="Tanya", section_path=["x"], lang="he", text=text, source="sefaria"
        )
        self.chunks.upsert_chunks([chunk])
        index_chunks(store=self.chunks, embedder=self.embedder, index=self.index, batch_size=8)
        return chunk

    def add_walkable(self, ref: str, text: str) -> Chunk:
        chunk = Chunk.make(
            ref=ref, book=ref.split(",")[0], section_path=["x"], lang="he",  # type: ignore[arg-type]
            text=text, source="sefaria",
        )
        self.chunks.upsert_chunks([chunk])
        self.chunks.mark_indexed([chunk.id])
        return chunk

    def connect(self, subject: str, obj: str) -> Relation:
        return self.graph.save_relation(Relation.make(
            subject=RefEndpoint(ref=subject), object=RefEndpoint(ref=obj),
            rel_type="connects", evidence="expert", confidence=1.0, status="approved",
            author="R. Ginsburgh", created_at=T0,
        ))


def test_three_hop_path_cites_a_chunk_only_reachable_via_the_walk() -> None:
    world = World([
        f'{{"verb": "walk_graph", "ref": "{TANYA}"}}',
        '{"verb": "conclude"}',
        "תשובה מלאה [S1][S2]",  # the conclude synthesis
    ])
    world.seed_searchable()
    far = world.add_walkable(TORAH_OHR, "המשך הבירור בתורה אור")  # NOT in Qdrant
    world.connect(TANYA, TORAH_OHR)

    trace = world.agent.study(SEED_TEXT)

    assert trace.answer.grounded
    assert far.ref in [s.ref for s in trace.answer.sources]
    assert far.ref in trace.answer.cited_refs  # [S2] resolved to the walked chunk
    walked = next(s for s in trace.answer.sources if s.ref == far.ref)
    assert walked.via is not None and walked.via.author == "R. Ginsburgh"
    # Step accounting: walk + conclude, one call each, plus one synthesis call.
    assert [s.action.verb for s in trace.steps] == ["walk_graph", "conclude"]
    assert isinstance(trace.steps[0].action, WalkGraphAction)
    assert trace.steps[0].digest.edges[0].far == TORAH_OHR
    assert trace.steps[0].digest.added_chunks == 1
    assert trace.budgets.hops_used == 2
    assert trace.budgets.calls_used == 3  # 2 action choices + 1 synthesize
    assert trace.forced is False
    # Persisted, retrievable, identical.
    stored = world.traces.get(trace.id)
    assert stored is not None and stored.model_dump() == trace.model_dump()


def test_refused_seed_never_calls_the_backend_and_persists_no_trace() -> None:
    world = World([], threshold=0.99)
    world.seed_searchable()

    trace = world.agent.study("שאלה שאין לה שום קשר לקורפוס")

    assert trace.answer.grounded is False
    assert trace.steps == []
    assert world.backend.calls == 0  # the gate fired before ANY model call
    assert world.traces.get(trace.id) is None  # nothing was studied — no notebook


def test_hop_budget_force_concludes_honestly() -> None:
    world = World([
        '{"verb": "search", "query": "עוד חיפוש"}',
        '{"verb": "search", "query": "ועוד אחד"}',
        "תשובה [S1]",
    ], max_hops=2)
    world.seed_searchable()

    trace = world.agent.study(SEED_TEXT)

    assert trace.budgets.exhausted == "hops"
    assert trace.forced is True
    assert trace.answer.grounded  # concluded with what it has, honestly marked
    assert len(trace.steps) == 2


def test_call_budget_force_concludes() -> None:
    world = World([
        '{"verb": "search", "query": "חיפוש"}',
        "תשובה [S1]",
    ], max_calls=1)
    world.seed_searchable()

    trace = world.agent.study(SEED_TEXT)

    assert trace.budgets.exhausted == "calls"
    assert trace.forced is True
    assert len(trace.steps) == 1


def test_chunk_budget_caps_the_working_set() -> None:
    world = World([
        f'{{"verb": "walk_graph", "ref": "{TANYA}"}}',
        '{"verb": "conclude"}',
        "תשובה [S1]",
    ], max_chunks=1)
    world.seed_searchable()
    world.add_walkable(TORAH_OHR, "רחוק")
    world.connect(TANYA, TORAH_OHR)

    trace = world.agent.study(SEED_TEXT)

    assert trace.budgets.chunks_used == 1  # the seed filled the budget
    assert trace.steps[0].digest.added_chunks == 0
    assert [s.ref for s in trace.answer.sources] == [TANYA]


def test_malformed_action_gets_one_repair_then_force_concludes() -> None:
    world = World([
        "definitely not json",
        "still { not valid",
        "תשובה [S1]",
    ])
    world.seed_searchable()

    trace = world.agent.study(SEED_TEXT)

    assert trace.forced is True
    assert len(trace.steps) == 1
    step = trace.steps[0]
    assert isinstance(step.action, ConcludeAction)
    assert step.calls_spent == 2  # the original + exactly one repair
    assert step.digest.note is not None and "malformed" in step.digest.note
    assert trace.answer.grounded


def test_malformed_then_repaired_action_continues_normally() -> None:
    world = World([
        "sorry, here you go:",
        '{"verb": "conclude"}',
        "תשובה [S1]",
    ])
    world.seed_searchable()

    trace = world.agent.study(SEED_TEXT)

    assert trace.forced is False
    assert isinstance(trace.steps[0].action, ConcludeAction)
    assert trace.steps[0].calls_spent == 2


def test_below_threshold_search_adds_nothing() -> None:
    world = World([
        '{"verb": "search", "query": "שאלה לא קשורה בכלל לגמרי"}',
        '{"verb": "conclude"}',
        "תשובה [S1]",
    ], threshold=0.9)
    world.seed_searchable()

    trace = world.agent.study(SEED_TEXT)

    search_step = trace.steps[0]
    assert isinstance(search_step.action, SearchAction)
    assert search_step.digest.added_chunks == 0
    assert search_step.digest.note is not None and "below threshold" in search_step.digest.note
    assert [s.ref for s in trace.answer.sources] == [TANYA]  # only the seed


def test_open_section_and_lookup_term_execute_via_existing_stores() -> None:
    world = World([
        f'{{"verb": "open_section", "ref": "{TORAH_OHR}"}}',
        '{"verb": "lookup_term", "term": "בירור"}',
        '{"verb": "conclude"}',
        "תשובה [S1][S2][S3]",
    ])
    world.seed_searchable()
    world.add_walkable(TORAH_OHR, "הקטע שנפתח במכוון")
    world.terms.create_term(Term(
        id="term-1", canonical="בירור", surface_forms=["בירור"],
        definition="העלאת ניצוצות", author="R. Ginsburgh",
    ))
    term_chunk = Chunk.make(
        ref="Term · בירור", book="Lexicon", section_path=["Lexicon"], lang="he",
        text="בירור — העלאת ניצוצות", source="term", metadata={"term_id": "term-1"},
    )
    world.chunks.upsert_chunks([term_chunk])
    world.chunks.mark_indexed([term_chunk.id])

    trace = world.agent.study(SEED_TEXT)

    assert trace.steps[0].digest.refs_opened == [TORAH_OHR]
    assert trace.steps[1].digest.term == "בירור"
    refs = [s.ref for s in trace.answer.sources]
    assert TORAH_OHR in refs and "Term · בירור" in refs

    # Unknown ref / unknown term: honest notes, nothing added, loop unharmed.
    world2 = World([
        '{"verb": "open_section", "ref": "Nope 1:1"}',
        '{"verb": "lookup_term", "term": "לא-מונח"}',
        '{"verb": "conclude"}',
        "תשובה [S1]",
    ])
    world2.seed_searchable()
    trace2 = world2.agent.study(SEED_TEXT)
    note0 = trace2.steps[0].digest.note
    note1 = trace2.steps[1].digest.note
    assert note0 is not None and "not in the corpus" in note0
    assert note1 is not None and "no lexicon entry" in note1


def test_trace_api_route_serves_the_stored_trace() -> None:
    from fastapi.testclient import TestClient

    from maayan.ui.app import create_app

    class _Stub:
        def __getattr__(self, _name: str):  # noqa: ANN204
            raise AssertionError("trace routes must not touch other services")

    world = World([
        '{"verb": "conclude"}',
        "תשובה [S1]",
    ])
    world.seed_searchable()
    trace = world.agent.study(SEED_TEXT)

    app = create_app(  # type: ignore[arg-type]
        _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(),
        traces=world.traces,
    )
    client = TestClient(app)
    resp = client.get(f"/api/traces/{trace.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["question"] == SEED_TEXT
    assert [s["action"]["verb"] for s in body["steps"]] == ["conclude"]
    assert client.get("/api/traces/nope").status_code == 404

    unwired = create_app(  # type: ignore[arg-type]
        _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(),
    )
    assert TestClient(unwired).get("/api/traces/x").status_code == 503
