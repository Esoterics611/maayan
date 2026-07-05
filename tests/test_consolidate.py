"""Tests for Prompt 41 — consolidation (sugya pages) + chazarah (memory hygiene).

Fakes throughout. The invariants: clustering is deterministic; a drafted page cites
ONLY its cluster's refs; approving version N+1 retracts EXACTLY version N's chunks
through the audited retract flow; the scheduler's spaced-repetition intervals multiply
on confirmation; and never-retrieved detection joins AskLog citations against the graph.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from qdrant_client import QdrantClient

from maayan.clock import FakeClock
from maayan.config import Settings
from maayan.consolidate.cluster import build_clusters
from maayan.consolidate.draft import SugyaDrafter
from maayan.consolidate.schedule_store import ScheduleStore
from maayan.consolidate.scheduler import ChazarahScheduler
from maayan.consolidate.service import SugyaService
from maayan.consolidate.store import SugyaStore
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.develop.store import DevelopmentStore
from maayan.embed.fake import HashingEmbedder
from maayan.generate.base import Message
from maayan.graph.models import Concept, ConceptEndpoint, RefEndpoint, Relation, concept_id
from maayan.graph.store import GraphStore
from maayan.index.qdrant import QdrantIndex
from maayan.inquiry.log import AskLog
from maayan.inquiry.store import InquiryStore
from maayan.lexicon.store import TermStore
from maayan.retract.service import RetractionService
from maayan.retract.store import RetractionStore

DIM = 128
T0 = datetime(2026, 7, 1, tzinfo=UTC)
A = "Tanya, Part I; Likkutei Amarim 18:1"
B = "Torah Ohr, Vayigash 1:1"
CONCEPT = "ביטול"


class SugyaBackend:
    """Returns a fixed sugya page JSON citing [S1] and [S1][S2]; counts calls."""

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, system_prompt: str, messages: list[Message]) -> str:
        self.calls += 1
        return json.dumps(
            {
                "title": "סוגיית הביטול",
                "sections": [
                    {"title": "מקורות", "body": "המקור מלמד על הביטול [S1]"},
                    {"title": "קשרים", "body": "השני מפרש את הראשון [S1][S2]"},
                    {"title": "שאלות פתוחות", "body": "מה היחס למסירות נפש?"},
                ],
            }
        )


class World:
    def __init__(self) -> None:
        self.clock = FakeClock(T0)
        self.chunks = ChunkStore(":memory:")
        self.graph = GraphStore(":memory:")
        self.sugya_store = SugyaStore(":memory:")
        self.embedder = HashingEmbedder(dim=DIM)
        self.index = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
        self.index.ensure_collection()
        self.retractions = RetractionStore(":memory:")
        self.settings = Settings()
        self.retractor = RetractionService(
            self.chunks,
            self.retractions,
            self.index,
            self.clock,
            DevelopmentStore(":memory:"),
            TermStore(":memory:"),
            self.graph,
            recorder=None,
        )
        self.backend = SugyaBackend()
        self.drafter = SugyaDrafter(
            self.backend,  # type: ignore[arg-type]
            self.chunks,
            self.graph,
            self.clock,
            model="fake",
        )
        self.service = SugyaService(
            self.drafter,
            self.graph,
            self.chunks,
            self.sugya_store,
            self.embedder,
            self.index,
            self.retractor,
            self.clock,
            min_cluster_size=2,
        )

    def seed_corpus(self, *refs: str) -> None:
        chunks = [
            Chunk.make(
                ref=ref, book=ref.split(",")[0], section_path=[ref, "1"], lang="he",
                text=f"טקסט על הביטול — {ref}", source="sefaria",
            )
            for ref in refs
        ]
        self.chunks.upsert_chunks(chunks)

    def seed_concept_cluster(self) -> None:
        """A cluster of refs A,B anchored on the concept ביטול (via a defines edge)."""
        self.seed_corpus(A, B)
        self.graph.save_concept(
            Concept.make(canonical=CONCEPT, author="rav", created_at=T0)
        )
        self._approved(RefEndpoint(ref=A), RefEndpoint(ref=B), "explains")
        self._approved(
            RefEndpoint(ref=A), ConceptEndpoint(concept_id=concept_id(CONCEPT)), "defines"
        )

    def _approved(
        self,
        subject: RefEndpoint | ConceptEndpoint,
        obj: RefEndpoint | ConceptEndpoint,
        rel_type: str,
        *,
        evidence: str = "expert",
        confidence: float = 1.0,
        created_at: datetime | None = None,
    ) -> Relation:
        relation = Relation.make(
            subject=subject, object=obj, rel_type=rel_type,  # type: ignore[arg-type]
            evidence=evidence,  # type: ignore[arg-type]
            confidence=confidence, status="approved", author="rav",
            created_at=created_at or T0,
        )
        return self.graph.save_relation(relation)


# -- clustering ---------------------------------------------------------------------

def test_clustering_is_deterministic_and_respects_min_size() -> None:
    world = World()
    world.seed_corpus(A, B, "Book C 1:1", "Book D 1:1", "Lonely 1:1")
    world._approved(RefEndpoint(ref=A), RefEndpoint(ref=B), "explains")
    world._approved(RefEndpoint(ref="Book C 1:1"), RefEndpoint(ref="Book D 1:1"), "parallels")
    # A singleton-ref edge (ref ↔ concept) forms no cluster (min_size 2 refs).
    world.graph.save_concept(Concept.make(canonical="כתר", author="rav", created_at=T0))
    world._approved(
        RefEndpoint(ref="Lonely 1:1"), ConceptEndpoint(concept_id=concept_id("כתר")), "defines"
    )

    first = build_clusters(world.graph, world.chunks, min_size=2)
    second = build_clusters(world.graph, world.chunks, min_size=2)
    assert [c.model_dump() for c in first] == [c.model_dump() for c in second]  # deterministic
    assert len(first) == 2  # the lonely ref↔concept component is dropped
    assert all(len(c.refs) >= 2 for c in first)
    assert first[0].refs == sorted(first[0].refs)


# -- drafting -----------------------------------------------------------------------

def test_drafted_page_cites_only_cluster_refs() -> None:
    world = World()
    world.seed_concept_cluster()
    page = world.service.draft(concept=CONCEPT, author="rav")

    assert page.status == "proposed"
    assert page.chunk_ids == []  # a proposal indexes nothing
    assert set(page.cited_refs) <= {A, B}  # can only cite its own cluster
    assert page.cited_refs  # and it did cite something


def test_draft_requires_a_cluster() -> None:
    world = World()
    world.seed_concept_cluster()
    try:
        world.service.draft(concept="does-not-exist", author="rav")
    except ValueError as exc:
        assert "No cluster" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for a missing cluster")


# -- gate + versioning --------------------------------------------------------------

def test_approve_indexes_sugya_chunks_gate_holds() -> None:
    world = World()
    world.seed_concept_cluster()
    page = world.service.draft(concept=CONCEPT, author="rav")
    approved = world.service.approve(page.id, author="rav")

    assert approved.status == "approved"
    assert approved.version == 1
    # Two grounded sections indexed (the third has no citation but has body → indexed too).
    live = world.chunks.get_chunks(source="sugya")
    assert {c.id for c in live} == set(approved.chunk_ids)
    assert all(c.source == "sugya" for c in live)
    assert all(c.metadata.get("concept") == CONCEPT for c in live)


def test_version_supersede_retracts_exactly_the_old_chunks_audited() -> None:
    world = World()
    world.seed_concept_cluster()

    v1 = world.service.approve(
        world.service.draft(concept=CONCEPT, author="rav").id, author="rav"
    )
    v2 = world.service.approve(
        world.service.draft(concept=CONCEPT, author="rav").id, author="rav"
    )

    assert v2.version == 2
    assert v2.supersedes == v1.id
    # v1's page is superseded; its exact chunks are retracted (gone from retrieval).
    assert world.sugya_store.get_page(v1.id).status == "superseded"  # type: ignore[union-attr]
    for chunk_id in v1.chunk_ids:
        assert world.chunks.get_chunk(chunk_id, include_retracted=False) is None
    for chunk_id in v2.chunk_ids:
        assert world.chunks.get_chunk(chunk_id, include_retracted=False) is not None
    # …and the removal is audited, one row per old chunk, attributed.
    audited = {r.chunk_id: r for r in world.retractions.list_retractions()}
    assert set(v1.chunk_ids) <= set(audited)
    assert all(audited[cid].source == "sugya" for cid in v1.chunk_ids)
    assert all("superseded" in audited[cid].reason for cid in v1.chunk_ids)


# -- chazarah scheduler -------------------------------------------------------------

def _scheduler(world: World) -> tuple[ChazarahScheduler, InquiryStore, ScheduleStore, AskLog]:
    ask_log = AskLog(":memory:", world.clock)
    inquiries = InquiryStore(":memory:", world.clock)
    schedule = ScheduleStore(":memory:", world.clock)
    scheduler = ChazarahScheduler(
        world.graph, ask_log, inquiries, schedule, world.clock, world.settings
    )
    return scheduler, inquiries, schedule, ask_log


def test_chazarah_schedules_stale_bootstrap_and_intervals_multiply() -> None:
    world = World()
    old = T0 - timedelta(days=200)  # older than chazarah_bootstrap_days (90)
    rel = world._approved(
        RefEndpoint(ref=A), RefEndpoint(ref=B), "connects",
        evidence="derived_bootstrap", confidence=0.6, created_at=old,
    )
    scheduler, inquiries, schedule, _log = _scheduler(world)

    report = scheduler.run()
    assert report.queued == 1
    assert report.by_reason.get("stale_bootstrap") == 1
    assert len(inquiries.list(status="open", kind="re_review")) == 1

    base = world.settings.chazarah_base_interval_days
    factor = world.settings.chazarah_interval_factor
    scheduler.confirm(rel.id)
    sched = schedule.get(rel.id)
    assert sched is not None
    assert sched.interval_days == base * factor
    assert sched.reviews == 1
    assert sched.next_review_at > world.clock.now()  # pushed into the future

    # A second pass, same clock: no longer due → nothing re-queued.
    assert scheduler.run().queued == 0


def test_chazarah_never_retrieved_join() -> None:
    world = World()
    # An expert, confident, recent edge — only the citation join can flag it.
    world._approved(RefEndpoint(ref=A), RefEndpoint(ref=B), "explains")
    # A second edge whose endpoint WAS cited in a logged ask — not never-retrieved.
    world.seed_corpus("Book C 1:1", "Book D 1:1")
    world._approved(RefEndpoint(ref="Book C 1:1"), RefEndpoint(ref="Book D 1:1"), "parallels")

    scheduler, inquiries, _schedule, ask_log = _scheduler(world)
    ask_log.record(question="on C", refused=False, top_score=0.9, cited_refs=["Book C 1:1"])

    report = scheduler.run()
    assert report.by_reason.get("never_retrieved") == 1  # only the A↔B edge
    open_items = inquiries.list(status="open", kind="re_review")
    reasons = {
        item.payload.reason  # type: ignore[union-attr]
        for item in open_items
    }
    assert reasons == {"never_retrieved"}


def test_chazarah_no_asks_no_never_retrieved() -> None:
    world = World()
    world._approved(RefEndpoint(ref=A), RefEndpoint(ref=B), "explains")  # expert, recent
    scheduler, inquiries, _schedule, _log = _scheduler(world)

    # With zero logged asks, "never retrieved" is vacuously true for everything —
    # the guard suppresses it so a fresh install isn't flooded.
    report = scheduler.run()
    assert report.queued == 0
    assert inquiries.list(status="open", kind="re_review") == []
