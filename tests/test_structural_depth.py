"""Tests for Prompt 42 — parent context + gated section summaries.

Fakes throughout. The invariants: the parent-context window honors section order and a
char budget; the citation stays the exact hit even with a neighbor in the model's
context (citation integrity); summary drafting gates and indexes with parent/child
metadata; and the summary boost is applied in the SAME place as the existing boosts.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from qdrant_client import QdrantClient

from maayan.clock import FakeClock
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.embed.fake import HashingEmbedder
from maayan.generate.base import Message
from maayan.generate.parent import SectionWindowProvider
from maayan.generate.rag import RAGService, build_context
from maayan.index.pipeline import index_chunks
from maayan.index.qdrant import QdrantIndex
from maayan.retrieve.models import SearchResult
from maayan.retrieve.retriever import Retriever
from maayan.summarize.draft import SummaryDrafter
from maayan.summarize.service import SummaryService
from maayan.summarize.store import SummaryStore

DIM = 128
T0 = datetime(2026, 7, 1, tzinfo=UTC)
BOOK = "Tanya, Part I; Likkutei Amarim"


def _section(n: int, text: str) -> Chunk:
    return Chunk.make(
        ref=f"{BOOK} 1:{n}", book=BOOK, section_path=["Perek 1", str(n)],
        lang="he", text=text, source="sefaria",
    )


# -- parent context -----------------------------------------------------------------

def test_window_honors_section_order_and_budget() -> None:
    chunks = ChunkStore(":memory:")
    chunks.upsert_chunks([_section(i, f"passage number {i} " + "x" * 20) for i in range(1, 6)])
    provider = SectionWindowProvider(chunks)

    # A generous budget pulls neighbors on both sides, emitted in section order.
    window = provider.window(f"{BOOK} 1:3", "he", max_chars=1000)
    assert "passage number 3" not in window  # the hit itself is excluded
    assert "passage number 2" in window and "passage number 4" in window
    assert window.index("passage number 2") < window.index("passage number 4")  # order kept

    # A tiny budget stops after the first neighbor; off (0) yields nothing.
    tight = provider.window(f"{BOOK} 1:3", "he", max_chars=5)
    assert tight.count("passage number") == 1
    assert provider.window(f"{BOOK} 1:3", "he", max_chars=0) == ""
    assert provider.window("nope", "he", max_chars=1000) == ""


def test_build_context_renders_window_as_non_citable() -> None:
    hit = SearchResult(
        ref="A 1:1", text="the hit", score=0.0, lang="he", source="sefaria",
        payload={}, parent_context="the neighbor passage",
    )
    rendered = build_context([hit])
    assert "[S1] (A 1:1) the hit" in rendered
    assert "the neighbor passage" in rendered
    assert "do NOT cite" in rendered  # the window is labelled non-citable


class CitingBackend:
    """Answers by citing [S1] only — and mentions the neighbor text (a trap)."""

    def generate(self, system_prompt: str, messages: list[Message]) -> str:
        return "הביאור נשען על המקור [S1] וגם על ההקשר הסובב."


def test_citation_integrity_never_cites_a_neighbor() -> None:
    chunks = ChunkStore(":memory:")
    chunks.upsert_chunks([_section(1, "the cited passage"), _section(2, "the neighbor passage")])
    rag = RAGService(
        _NoRetriever(),  # type: ignore[arg-type]
        CitingBackend(),  # type: ignore[arg-type]
        score_threshold=0.0,
        parent_context=SectionWindowProvider(chunks),
        parent_context_chars=1000,
    )
    hit = SearchResult(
        ref=f"{BOOK} 1:1", text="the cited passage", score=0.9, lang="he",
        source="sefaria", payload={"ref": f"{BOOK} 1:1"},
    )
    answer = rag.synthesize("מה הביאור?", [hit])

    # The window reached the model (it's on the hit)…
    assert "neighbor passage" in hit.parent_context
    # …but the citation resolves to the HIT alone — never the neighbor.
    assert answer.cited_refs == [f"{BOOK} 1:1"]
    assert f"{BOOK} 1:2" not in answer.cited_refs


class _NoRetriever:
    """A retriever that must never be called (synthesize takes sources directly)."""

    def retrieve(self, *a: object, **k: object) -> object:  # pragma: no cover
        raise AssertionError("synthesize must not retrieve")


# -- gated summaries ----------------------------------------------------------------

class SummaryBackend:
    """Drafts a cited summary; passes the faithfulness check ('OK')."""

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, system_prompt: str, messages: list[Message]) -> str:
        self.calls += 1
        if "citation checker" in system_prompt:
            return "OK"
        return "הפרק עוסק בעבודת הבירורים [S1] ובביטול [S2]."


def _summary_world() -> tuple[SummaryService, ChunkStore, QdrantIndex, HashingEmbedder]:
    chunks = ChunkStore(":memory:")
    chunks.upsert_chunks([_section(1, "עבודת הבירורים"), _section(2, "ענין הביטול")])
    embedder = HashingEmbedder(dim=DIM)
    index = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
    index.ensure_collection()
    index_chunks(store=chunks, embedder=embedder, index=index, batch_size=8)
    drafter = SummaryDrafter(SummaryBackend(), FakeClock(T0), model="fake")  # type: ignore[arg-type]
    service = SummaryService(
        drafter, chunks, SummaryStore(":memory:"), embedder, index, FakeClock(T0), pace=1.0
    )
    return service, chunks, index, embedder


def test_summary_drafts_gates_and_indexes_with_parent_metadata() -> None:
    service, chunks, _index, _embedder = _summary_world()

    stats = asyncio.run(service.draft_book(BOOK))
    assert stats.supported == 1  # one section, one grounded summary
    pending = service.list(status="proposed")
    assert len(pending) == 1
    summary = pending[0]
    assert summary.supported
    assert set(summary.cited_refs) <= {f"{BOOK} 1:1", f"{BOOK} 1:2"}
    assert chunks.get_chunks(source="summary") == []  # a proposal indexes nothing

    approved = service.approve(summary.id, author="rav")
    assert approved.status == "approved" and approved.author == "rav"
    indexed = chunks.get_chunks(source="summary")
    assert len(indexed) == 1
    chunk = indexed[0]
    assert chunk.source == "summary"
    assert chunk.metadata["parent_ref"] == summary.parent_ref
    assert chunk.metadata["child_refs"] == summary.child_refs


def test_summary_approve_refuses_ungrounded() -> None:
    service, _chunks, _index, _embedder = _summary_world()

    class InsufficientBackend:
        def generate(self, system_prompt: str, messages: list[Message]) -> str:
            return "INSUFFICIENT"

    service._drafter = SummaryDrafter(  # type: ignore[attr-defined]
        InsufficientBackend(), FakeClock(T0), model="fake",  # type: ignore[arg-type]
    )
    asyncio.run(service.draft_book(BOOK, persist_unsupported=True))
    ungrounded = service.list()[0]
    assert not ungrounded.supported
    try:
        service.approve(ungrounded.id, author="rav")
    except ValueError as exc:
        assert "unsupported" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected a refusal to index an ungrounded summary")


# -- summary boost (same place as the other boosts) ---------------------------------

def test_summary_boost_applied_like_other_source_boosts() -> None:
    embedder = HashingEmbedder(dim=DIM)
    index = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
    index.ensure_collection()
    chunks = ChunkStore(":memory:")
    chunks.upsert_chunks(
        [
            Chunk.make(
                ref="Summary · Perek 1", book="Summary",
                section_path=["Summary", "Perek 1"], lang="he",
                text="סיכום עבודת הבירורים והביטול", source="summary",
            )
        ]
    )
    index_chunks(store=chunks, embedder=embedder, index=index, batch_size=8)

    plain = Retriever(index, embedder, top_k=5, summary_boost=1.0)
    boosted = Retriever(index, embedder, top_k=5, summary_boost=3.0)
    q = "עבודת הבירורים"
    base = next(r for r in plain.search(q) if r.source == "summary")
    up = next(r for r in boosted.search(q) if r.source == "summary")
    assert up.score == base.score * 3.0  # multiplied in _apply_source_boosts, nowhere special
