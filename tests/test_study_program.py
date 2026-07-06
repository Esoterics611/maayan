"""Tests for Prompt 40 — study programs: the sweep.

Fake backend, in-memory Qdrant, fake clock. The invariants that matter: a sweep
drafts typed edges that land as *proposed* relations (never approved); the funnel
counts drafted/passed/queued honestly; a faithfulness-failed proposal is counted but
never queued; the run is resumable from its cursor; and the report math matches the
persisted counts. No gate is ever bypassed — nothing lands "approved".
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from qdrant_client import QdrantClient

from maayan.agent.program import StudyProgramRunner, render_report_markdown
from maayan.agent.program_drafter import ProgramDrafter
from maayan.agent.program_store import ProgramStore
from maayan.clock import FakeClock
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.embed.fake import HashingEmbedder
from maayan.generate.base import Message
from maayan.graph.store import GraphStore
from maayan.index.pipeline import index_chunks
from maayan.index.qdrant import QdrantIndex
from maayan.retrieve.retriever import Retriever

DIM = 128
T0 = datetime(2026, 7, 1, tzinfo=UTC)
BOOK = "Sefer HaTest"


class ProgramBackend:
    """A controllable fake: one edge per draft to [S1]; a scripted verify verdict."""

    def __init__(self, *, verify_reply: str = "OK", rel_type: str = "explains") -> None:
        self.calls = 0
        self.draft_calls = 0
        self.verify_calls = 0
        self._verify_reply = verify_reply
        self._rel_type = rel_type

    def generate(self, system_prompt: str, messages: list[Message]) -> str:
        self.calls += 1
        if "citation checker" in system_prompt:  # VERIFY_SYSTEM_PROMPT
            self.verify_calls += 1
            return self._verify_reply
        self.draft_calls += 1
        return json.dumps(
            {
                "proposals": [
                    {
                        "object": "S1",
                        "rel_type": self._rel_type,
                        "note": "this unit relates to the source [S1]",
                        "grounds": ["S1"],
                    }
                ]
            }
        )


class World:
    def __init__(self, *, verify_reply: str = "OK", rel_type: str = "explains") -> None:
        self.chunks = ChunkStore(":memory:")
        self.graph = GraphStore(":memory:")
        self.store = ProgramStore(":memory:")
        self.embedder = HashingEmbedder(dim=DIM)
        self.index = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
        self.index.ensure_collection()
        self.retriever = Retriever(self.index, self.embedder, top_k=8)
        self.backend = ProgramBackend(verify_reply=verify_reply, rel_type=rel_type)
        self.clock = FakeClock(T0)

    def seed_book(self, chapters: int = 3) -> None:
        chunks = [
            Chunk.make(
                ref=f"{BOOK} {i}:1",
                book=BOOK,
                section_path=[f"Perek {i}", "1"],
                lang="he",
                text=f"פרק {i} — עבודת הבירורים והביטול, ניצוץ מספר {i} בעבודת ה'",
                source="sefaria",
            )
            for i in range(1, chapters + 1)
        ]
        self.chunks.upsert_chunks(chunks)
        index_chunks(store=self.chunks, embedder=self.embedder, index=self.index, batch_size=8)

    def runner(self, *, verify: bool = True, max_proposals: int = 6) -> StudyProgramRunner:
        drafter = ProgramDrafter(
            self.retriever,
            self.backend,  # type: ignore[arg-type]
            self.chunks,
            self.clock,
            model="fake-model",
            k=8,
            max_proposals=max_proposals,
            verify=verify,
        )
        return StudyProgramRunner(
            drafter,
            self.chunks,
            self.graph,
            self.store,
            self.clock,
            pace=20.0,
            bootstrap_confidence=0.6,
        )


def test_sweep_drafts_proposed_relations_no_gate_bypass() -> None:
    world = World()
    world.seed_book(3)
    runner = world.runner()

    program = runner.create(book=BOOK, task="relations", author="program:tester", model="fake")
    program = asyncio.run(runner.run(program))

    assert program.status == "done"
    assert program.cursor == program.total_units == 3
    assert program.counts.drafted == 3
    assert program.counts.passed_checks == 3
    assert program.counts.queued == 3
    # one draft call + one verify call per unit
    assert program.counts.model_calls == 6

    proposed = world.graph.list_relations(status="proposed")
    assert len(proposed) == 3
    assert all(r.status == "proposed" for r in proposed)
    assert all(r.evidence == "derived_bootstrap" for r in proposed)
    assert all(r.author == "program:tester" for r in proposed)
    # THE gate: nothing the sweep drafts is ever approved.
    assert world.graph.list_relations(status="approved") == []


def test_faithfulness_failed_counted_not_queued() -> None:
    world = World(verify_reply="this claim is not supported by the source")
    world.seed_book(3)
    runner = world.runner()

    program = runner.create(book=BOOK, task="relations", author="program:tester")
    program = asyncio.run(runner.run(program))

    assert program.counts.drafted == 3  # the model proposed an edge in each unit
    assert program.counts.passed_checks == 0  # but the faithfulness pass flagged them
    assert program.counts.queued == 0
    assert world.graph.list_relations(status="proposed") == []


def test_resumable_from_cursor() -> None:
    world = World()
    world.seed_book(3)
    runner = world.runner()

    program = runner.create(book=BOOK, task="relations", author="program:tester")
    program = asyncio.run(runner.run(program, units=1))
    assert program.cursor == 1
    assert program.status == "paused"
    assert len(world.graph.list_relations(status="proposed")) == 1

    # Simulate a fresh process: reload the program and continue with a new runner.
    resumed = world.store.get_program(program.id)
    assert resumed is not None
    runner2 = world.runner()
    resumed = asyncio.run(runner2.run(resumed, units=1))
    assert resumed.cursor == 2
    assert len(world.graph.list_relations(status="proposed")) == 2
    assert [u.unit_index for u in world.store.unit_results(program.id)] == [0, 1]


def test_idempotent_rerun_does_not_duplicate() -> None:
    world = World()
    world.seed_book(2)
    runner = world.runner()

    program = runner.create(book=BOOK, task="relations", author="program:tester")
    asyncio.run(runner.run(program))
    first = len(world.graph.list_relations(status="proposed"))

    # Re-run the same book from cursor 0 (a fresh program, same author) → dedupe.
    again = runner.create(book=BOOK, task="relations", author="program:tester")
    again = asyncio.run(runner.run(again))
    assert len(world.graph.list_relations(status="proposed")) == first  # no duplicates
    assert again.counts.queued == 0  # everything deduped onto existing edges


def test_report_math() -> None:
    world = World()
    world.seed_book(3)
    runner = world.runner()

    program = runner.create(book=BOOK, task="relations", author="program:tester")
    program = asyncio.run(runner.run(program))

    report = runner.build_report(program.id)
    assert report.program.counts.queued == 3
    assert len(report.units) == 3
    assert sum(u.counts.queued for u in report.units) == report.program.counts.queued
    assert report.evidence_histogram == {"derived_bootstrap": 3}

    markdown = render_report_markdown(report)
    assert "Study program report" in markdown
    assert "derived_bootstrap: 3" in markdown


def test_object_must_be_a_retrieved_source() -> None:
    """An invented object (out-of-range tag) is dropped — no mekor is fabricated."""
    world = World()
    world.seed_book(2)

    class InventingBackend(ProgramBackend):
        def generate(self, system_prompt: str, messages: list[Message]) -> str:
            self.calls += 1
            if "citation checker" in system_prompt:
                return "OK"
            return json.dumps(
                {"proposals": [{"object": "S99", "rel_type": "explains", "grounds": ["S99"]}]}
            )

    world.backend = InventingBackend()
    runner = world.runner()
    program = runner.create(book=BOOK, task="relations", author="program:tester")
    program = asyncio.run(runner.run(program))

    assert program.counts.drafted == 0  # nothing resolved to a real source
    assert world.graph.list_relations(status="proposed") == []


def test_terms_task_constrains_rel_types() -> None:
    """A relations-only verb under --task terms is rejected (out of the allowed set)."""
    world = World(rel_type="argues_with")  # not allowed for the 'terms' task
    world.seed_book(2)
    runner = world.runner()

    program = runner.create(book=BOOK, task="terms", author="program:tester")
    program = asyncio.run(runner.run(program))

    assert program.counts.drafted == 0
    assert world.graph.list_relations(status="proposed") == []
