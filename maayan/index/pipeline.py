"""Indexing pipeline: SQLite chunks → embeddings → Qdrant points.

Idempotent. Incremental by default (only chunks not yet indexed); `--rebuild`
drops the collection and re-embeds everything. All collaborators are injected.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.embed.base import Embedder
from maayan.index.qdrant import QdrantIndex


@dataclass(frozen=True)
class IndexResult:
    embedded: int
    total_points: int


def _batched(items: Sequence[Chunk], size: int) -> Iterator[list[Chunk]]:
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


def index_chunks(
    *,
    store: ChunkStore,
    embedder: Embedder,
    index: QdrantIndex,
    batch_size: int = 16,
    rebuild: bool = False,
) -> IndexResult:
    """Embed and upsert chunks into Qdrant. Marks chunks indexed in the store."""
    if rebuild:
        index.recreate_collection()
        chunks = store.get_chunks()
    else:
        index.ensure_collection()
        chunks = store.get_chunks(only_unindexed=True)

    embedded = 0
    for batch in _batched(chunks, batch_size):
        embeddings = embedder.embed([c.text for c in batch])
        index.upsert_chunks(list(zip(batch, embeddings, strict=True)))
        store.mark_indexed([c.id for c in batch])
        embedded += len(batch)

    return IndexResult(embedded=embedded, total_points=index.count())
