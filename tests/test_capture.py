"""Tests for the expert capture loop (the core differentiator).

Ephemeral Qdrant + HashingEmbedder + FakeClock; no network, no real models.
"""

from __future__ import annotations

import pytest
from qdrant_client import QdrantClient

from maayan.capture.convert import annotation_to_chunks, detect_lang
from maayan.capture.models import Annotation
from maayan.capture.service import CaptureService
from maayan.capture.store import CaptureStore
from maayan.clock import FakeClock
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.embed.fake import HashingEmbedder
from maayan.generate.rag import Answer
from maayan.index.pipeline import index_chunks
from maayan.index.qdrant import QdrantIndex
from maayan.retrieve.models import SearchResult
from maayan.retrieve.retriever import Retriever

DIM = 128
KINDS = ["correction", "connection", "addition", "objection"]


def _service(index: QdrantIndex, embedder: HashingEmbedder) -> CaptureService:
    return CaptureService(
        CaptureStore(":memory:"),
        ChunkStore(":memory:"),
        embedder,
        index,
        FakeClock(),
        allowed_kinds=KINDS,
    )


def _answer(question: str, refs: list[str]) -> Answer:
    sources = [
        SearchResult(ref=r, text="t", score=0.5, lang="he", source="sefaria", payload={})
        for r in refs
    ]
    return Answer(question=question, text="ans", grounded=True, cited_refs=refs, sources=sources)


def test_detect_lang() -> None:
    assert detect_lang("שלום עולם") == "he"
    assert detect_lang("hello world") == "en"


def test_annotation_converts_to_expert_chunk_with_metadata() -> None:
    ann = Annotation(
        id="abcd1234ef", session_id="s1", timestamp=FakeClock().now(),
        author="R. Ginsburgh", kind="connection", body="הקשר בין צמצום לבחירה",
        linked_refs=["Tanya 1:3", "Tanya 2:1"], move="sefirah->nefesh",
    )
    [chunk] = annotation_to_chunks(ann)
    assert chunk.source == "expert"
    assert chunk.lang == "he"
    assert chunk.metadata["author"] == "R. Ginsburgh"
    assert chunk.metadata["kind"] == "connection"
    assert chunk.metadata["linked_refs"] == ["Tanya 1:3", "Tanya 2:1"]
    assert "צמצום" in chunk.text
    assert "Tanya 1:3" in chunk.text  # linked refs embedded for retrievability


def test_start_session_persists() -> None:
    idx = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
    svc = _service(idx, HashingEmbedder(dim=DIM))
    session = svc.start_session(_answer("מהי בחירה", ["Tanya 1:1", "Tanya 1:2"]))
    assert session.retrieved_refs == ["Tanya 1:1", "Tanya 1:2"]
    assert svc._capture.get_session(session.id) is not None  # noqa: SLF001


def test_unknown_kind_rejected() -> None:
    idx = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
    svc = _service(idx, HashingEmbedder(dim=DIM))
    with pytest.raises(ValueError, match="Unknown kind"):
        svc.add_annotation("s1", author="x", kind="nonsense", body="b")


def test_annotation_is_indexed_and_retrievable_and_round_trips() -> None:
    embedder = HashingEmbedder(dim=DIM)
    idx = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
    idx.ensure_collection()
    svc = _service(idx, embedder)

    ann = svc.add_annotation(
        "s1", author="R. Ginsburgh", kind="connection",
        body="צמצום הראשון הוא שורש הבחירה החופשית",
        linked_refs=["Tanya 1:3"], move="sefirah->nefesh",
    )

    # Persisted to the capture store.
    assert svc._capture.get_annotations("s1")[0].id == ann.id  # noqa: SLF001
    # Persisted to the corpus store as an expert chunk (and marked indexed).
    assert svc._chunks.count(source="expert") == 1  # noqa: SLF001
    assert svc._chunks.count(only_unindexed=True) == 0  # noqa: SLF001

    # Retrievable by a related query, metadata round-trips through Qdrant.
    retriever = Retriever(idx, embedder, top_k=5)
    results = retriever.search("צמצום ובחירה")
    assert results[0].source == "expert"
    assert results[0].payload["metadata"]["author"] == "R. Ginsburgh"
    assert results[0].payload["metadata"]["linked_refs"] == ["Tanya 1:3"]


def test_expert_connection_surfaces_alongside_sefaria() -> None:
    """Full cycle: index a sefaria chunk, add an expert connection, re-query."""
    embedder = HashingEmbedder(dim=DIM)
    idx = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)

    # Seed printed text.
    store = ChunkStore(":memory:")
    store.upsert_chunks([
        Chunk.make(ref="Tanya 1:3", book="Tanya", section_path=["Chapter 1", "Paragraph 3"],
                   lang="he", text="בחירה חופשית של האדם", source="sefaria")
    ])
    index_chunks(store=store, embedder=embedder, index=idx, batch_size=8)
    store.close()

    # Expert ties a new concept to it.
    svc = _service(idx, embedder)
    svc.add_annotation(
        "s1", author="expert", kind="connection",
        body="בחירה חופשית קשורה לצמצום הראשון", linked_refs=["Tanya 1:3"],
    )

    # With a strong expert boost, the human connection surfaces first.
    boosted = Retriever(idx, embedder, top_k=5, expert_boost=5.0)
    results = boosted.search("בחירה חופשית")
    assert any(r.source == "expert" for r in results)
    assert results[0].source == "expert"
