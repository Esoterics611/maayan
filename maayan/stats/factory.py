"""Stats service factory (DI at the edge).

No embedder is built: the Qdrant handle only needs a dim to *create* a collection,
and stats only *counts* points, so the configured `embed_dim` suffices and we avoid
loading a heavy embedding model just to read a number.
"""

from __future__ import annotations

from maayan.capture.store import CaptureStore
from maayan.config import Settings
from maayan.corpus.store import ChunkStore
from maayan.develop.store import DevelopmentStore
from maayan.index.qdrant import QdrantIndex, build_qdrant_client
from maayan.lexicon.store import TermStore
from maayan.retract.store import RetractionStore
from maayan.stats.service import StatsService
from maayan.threads.store import ThreadStore


def build_stats_service(settings: Settings) -> StatsService:
    """Assemble a StatsService over the shared DB + the live Qdrant collection."""
    index = QdrantIndex(
        build_qdrant_client(settings), settings.collection_name, settings.embed_dim
    )
    return StatsService(
        ChunkStore(settings.db_path),
        CaptureStore(settings.db_path),
        DevelopmentStore(settings.db_path),
        RetractionStore(settings.db_path),
        ThreadStore(settings.db_path),
        TermStore(settings.db_path),
        index,
    )
