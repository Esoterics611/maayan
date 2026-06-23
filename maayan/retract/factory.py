"""Retraction service factory (DI at the edge)."""

from __future__ import annotations

from maayan.clock import SystemClock
from maayan.config import Settings
from maayan.corpus.store import ChunkStore
from maayan.develop.store import DevelopmentStore
from maayan.embed.base import Embedder
from maayan.embed.factory import build_embedder
from maayan.index.qdrant import QdrantIndex, build_qdrant_client
from maayan.lexicon.store import TermStore
from maayan.retract.service import RetractionService
from maayan.retract.store import RetractionStore


def build_retraction_service(
    settings: Settings, *, embedder: Embedder | None = None
) -> RetractionService:
    """Assemble a RetractionService wired to the same stores + collection as the rest.

    The embedder is only used to size the Qdrant collection handle (deletion needs no
    vectors); it is shared when one is passed so `maayan ui` builds it once.
    """
    embedder = embedder or build_embedder(settings)
    index = QdrantIndex(
        build_qdrant_client(settings), settings.collection_name, embedder.dim
    )
    return RetractionService(
        ChunkStore(settings.db_path),
        RetractionStore(settings.db_path),
        index,
        SystemClock(),
        DevelopmentStore(settings.db_path),
        TermStore(settings.db_path),
    )
