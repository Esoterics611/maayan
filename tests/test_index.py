"""Tests for embedding + Qdrant indexing.

Uses qdrant-client's in-memory mode (no Docker) and the dependency-free
HashingEmbedder (no model download), per the house rule that unit tests mock
models and don't hit the network.
"""

from __future__ import annotations

from qdrant_client import QdrantClient

from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.embed.fake import HashingEmbedder
from maayan.index.pipeline import index_chunks
from maayan.index.qdrant import DENSE_VECTOR, SPARSE_VECTOR, QdrantIndex

DIM = 64


def _chunk(ref: str, text: str, source: str = "sefaria") -> Chunk:
    return Chunk.make(
        ref=ref, book="Tanya", section_path=["Chapter 1", "Paragraph 1"],
        lang="he", text=text, source=source,
    )


def _index() -> QdrantIndex:
    return QdrantIndex(QdrantClient(location=":memory:"), "test_maayan", DIM)


def test_ensure_collection_is_idempotent_with_hybrid_schema() -> None:
    idx = _index()
    idx.ensure_collection()
    idx.ensure_collection()  # second call must not error
    info = idx.client.get_collection("test_maayan")
    assert DENSE_VECTOR in info.config.params.vectors  # named dense vector
    assert info.config.params.sparse_vectors is not None
    assert SPARSE_VECTOR in info.config.params.sparse_vectors


def test_index_pipeline_writes_points_and_payload() -> None:
    store = ChunkStore(":memory:")
    store.upsert_chunks([_chunk("Tanya 1:1", "שלום עולם"), _chunk("Tanya 1:2", "אהבה")])
    idx = _index()
    result = index_chunks(
        store=store, embedder=HashingEmbedder(dim=DIM), index=idx, batch_size=8
    )
    assert result.embedded == 2
    assert result.total_points == 2

    # Payload round-trips.
    cid = store.get_chunks()[0].id
    payload = idx.retrieve(cid)
    assert payload is not None
    assert payload["book"] == "Tanya"
    assert payload["section_path"] == ["Chapter 1", "Paragraph 1"]
    assert payload["source"] == "sefaria"
    assert payload["text"]
    store.close()


def test_index_is_idempotent_and_incremental() -> None:
    store = ChunkStore(":memory:")
    store.upsert_chunks([_chunk("Tanya 1:1", "שלום")])
    idx = _index()
    emb = HashingEmbedder(dim=DIM)

    first = index_chunks(store=store, embedder=emb, index=idx, batch_size=8)
    assert first.embedded == 1

    # Nothing new to index → no re-embed, point count stable.
    second = index_chunks(store=store, embedder=emb, index=idx, batch_size=8)
    assert second.embedded == 0
    assert second.total_points == 1

    # Add a chunk → only the new one is embedded.
    store.upsert_chunks([_chunk("Tanya 1:2", "עולם")])
    third = index_chunks(store=store, embedder=emb, index=idx, batch_size=8)
    assert third.embedded == 1
    assert third.total_points == 2
    store.close()


def test_rebuild_reembeds_everything() -> None:
    store = ChunkStore(":memory:")
    store.upsert_chunks([_chunk("Tanya 1:1", "שלום"), _chunk("Tanya 1:2", "עולם")])
    idx = _index()
    emb = HashingEmbedder(dim=DIM)
    index_chunks(store=store, embedder=emb, index=idx, batch_size=8)

    rebuilt = index_chunks(store=store, embedder=emb, index=idx, batch_size=8, rebuild=True)
    assert rebuilt.embedded == 2
    assert rebuilt.total_points == 2
    store.close()


def test_hashing_embedder_shapes() -> None:
    emb = HashingEmbedder(dim=DIM)
    [e] = emb.embed(["שלום עולם שלום"])
    assert len(e.dense) == DIM
    assert len(e.sparse_indices) == len(e.sparse_values)
    assert e.sparse_indices  # repeated token still yields sparse entries
