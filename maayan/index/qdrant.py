"""Qdrant collection management + upsert.

Hybrid-ready schema: one NAMED dense vector ("dense", cosine) plus a named sparse
vector ("sparse"). Collection name and dense dim are config-driven. Creation is
idempotent. The `QdrantClient` is injected (built by `build_qdrant_client`).
"""

from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient, models

from maayan.config import Settings
from maayan.corpus.models import Chunk
from maayan.embed.base import Embedding

DENSE_VECTOR = "dense"
SPARSE_VECTOR = "sparse"


def chunk_payload(chunk: Chunk) -> dict[str, Any]:
    """Payload stored alongside the vectors — enough to cite + filter + display."""
    return {
        "ref": chunk.ref,
        "book": chunk.book,
        "section_path": chunk.section_path,
        "lang": chunk.lang,
        "source": chunk.source,
        "text": chunk.text,
        "metadata": chunk.metadata,
    }


def build_qdrant_client(settings: Settings) -> QdrantClient:
    """Build a QdrantClient from config.

    `qdrant_url` is interpreted as: an http(s) URL → server mode; ":memory:" →
    ephemeral in-memory; anything else → a local on-disk path (no Docker needed).
    """
    url = settings.qdrant_url
    if url == ":memory:":
        return QdrantClient(location=":memory:")
    if url.startswith(("http://", "https://")):
        api_key = settings.qdrant_api_key.get_secret_value() or None
        return QdrantClient(url=url, api_key=api_key)
    return QdrantClient(path=url)


class QdrantIndex:
    """Wraps a Qdrant collection with the hybrid (dense + sparse) schema."""

    def __init__(self, client: QdrantClient, collection: str, dim: int) -> None:
        self._client = client
        self._collection = collection
        self._dim = dim

    def ensure_collection(self) -> None:
        """Create the collection with the hybrid schema if it does not exist."""
        if self._client.collection_exists(self._collection):
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config={
                DENSE_VECTOR: models.VectorParams(
                    size=self._dim, distance=models.Distance.COSINE
                )
            },
            sparse_vectors_config={SPARSE_VECTOR: models.SparseVectorParams()},
        )

    def recreate_collection(self) -> None:
        """Drop and recreate the collection (used by `index --rebuild`)."""
        if self._client.collection_exists(self._collection):
            self._client.delete_collection(self._collection)
        self.ensure_collection()

    def upsert_chunks(self, items: list[tuple[Chunk, Embedding]]) -> int:
        """Upsert (chunk, embedding) pairs as points keyed by the chunk's stable id."""
        if not items:
            return 0
        points = [
            models.PointStruct(
                id=chunk.id,
                vector={
                    DENSE_VECTOR: emb.dense,
                    SPARSE_VECTOR: models.SparseVector(
                        indices=emb.sparse_indices, values=emb.sparse_values
                    ),
                },
                payload=chunk_payload(chunk),
            )
            for chunk, emb in items
        ]
        self._client.upsert(collection_name=self._collection, points=points)
        return len(points)

    def query_hybrid(
        self,
        dense: list[float],
        sparse_indices: list[int],
        sparse_values: list[float],
        *,
        limit: int,
        query_filter: models.Filter | None = None,
    ) -> list[models.ScoredPoint]:
        """Hybrid search: RRF fusion over the dense + sparse vectors (Query API)."""
        response = self._client.query_points(
            collection_name=self._collection,
            prefetch=[
                models.Prefetch(
                    query=dense, using=DENSE_VECTOR, limit=limit, filter=query_filter
                ),
                models.Prefetch(
                    query=models.SparseVector(indices=sparse_indices, values=sparse_values),
                    using=SPARSE_VECTOR,
                    limit=limit,
                    filter=query_filter,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
        )
        return response.points

    def count(self) -> int:
        return self._client.count(self._collection).count

    def retrieve(self, point_id: str) -> dict[str, Any] | None:
        """Fetch a single point's payload by id (used in tests/demos)."""
        records = self._client.retrieve(
            self._collection, ids=[point_id], with_payload=True, with_vectors=False
        )
        if not records:
            return None
        return dict(records[0].payload or {})

    @property
    def collection(self) -> str:
        return self._collection

    @property
    def client(self) -> QdrantClient:
        return self._client
