"""Term service factory (DI at the edge)."""

from __future__ import annotations

from maayan.clock import SystemClock
from maayan.config import Settings
from maayan.corpus.store import ChunkStore
from maayan.embed.base import Embedder
from maayan.embed.factory import build_embedder
from maayan.index.qdrant import QdrantIndex, build_qdrant_client
from maayan.lexicon.service import TermService
from maayan.lexicon.store import TermStore


def build_term_service(
    settings: Settings, *, embedder: Embedder | None = None
) -> TermService:
    """Assemble a TermService wired to the same stores + collection as the rest."""
    embedder = embedder or build_embedder(settings)
    index = QdrantIndex(
        build_qdrant_client(settings), settings.collection_name, embedder.dim
    )
    return TermService(
        TermStore(settings.db_path),
        ChunkStore(settings.db_path),
        embedder,
        index,
        SystemClock(),
    )
