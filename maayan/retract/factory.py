"""Retraction service factory (DI at the edge)."""

from __future__ import annotations

from maayan.clock import SystemClock
from maayan.config import Settings
from maayan.corpus.store import ChunkStore
from maayan.develop.store import DevelopmentStore
from maayan.embed.base import Embedder
from maayan.graph.store import GraphStore
from maayan.index.qdrant import QdrantIndex, build_qdrant_client
from maayan.lexicon.store import TermStore
from maayan.retract.service import RetractionService
from maayan.retract.store import RetractionStore


def build_retraction_service(
    settings: Settings, *, embedder: Embedder | None = None
) -> RetractionService:
    """Assemble a RetractionService wired to the same stores + collection as the rest.

    Deletion needs no vectors, so no embedder is built here: the Qdrant handle is
    sized from `settings.embed_dim` (what every embedder is constructed with). A
    shared embedder may still be passed (`maayan ui` does) and its dim wins.
    """
    dim = embedder.dim if embedder is not None else settings.embed_dim
    index = QdrantIndex(build_qdrant_client(settings), settings.collection_name, dim)
    return RetractionService(
        ChunkStore(settings.db_path),
        RetractionStore(settings.db_path),
        index,
        SystemClock(),
        DevelopmentStore(settings.db_path),
        TermStore(settings.db_path),
        GraphStore(settings.db_path),
    )
