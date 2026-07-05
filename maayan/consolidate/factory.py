"""Consolidation factories (DI at the edge): SugyaService + ChazarahScheduler."""

from __future__ import annotations

from maayan.clock import SystemClock
from maayan.config import Settings
from maayan.consolidate.draft import SugyaDrafter
from maayan.consolidate.schedule_store import ScheduleStore
from maayan.consolidate.scheduler import ChazarahScheduler
from maayan.consolidate.service import SugyaService
from maayan.consolidate.store import SugyaStore
from maayan.corpus.store import ChunkStore
from maayan.embed.base import Embedder
from maayan.embed.factory import build_embedder
from maayan.generate.base import GenerationBackend
from maayan.generate.factory import build_generation_backend
from maayan.graph.store import GraphStore
from maayan.index.qdrant import QdrantIndex, build_qdrant_client
from maayan.inquiry.log import AskLog
from maayan.inquiry.store import InquiryStore
from maayan.retract.factory import build_retraction_service


def build_sugya_service(
    settings: Settings,
    *,
    embedder: Embedder | None = None,
    backend: GenerationBackend | None = None,
) -> SugyaService:
    """Assemble the sugya consolidation service wired to the shared stores + collection."""
    embedder = embedder or build_embedder(settings)
    draft_settings = settings
    if settings.sugya_draft_model:
        field = "ollama_model" if settings.generation_backend == "ollama" else "openrouter_model"
        draft_settings = settings.model_copy(update={field: settings.sugya_draft_model})
    backend = backend or build_generation_backend(draft_settings)
    chunks = ChunkStore(settings.db_path)
    graph = GraphStore(settings.db_path)
    index = QdrantIndex(
        build_qdrant_client(settings), settings.collection_name, embedder.dim
    )
    drafter = SugyaDrafter(
        backend, chunks, graph, SystemClock(), model=draft_settings.generation_model
    )
    return SugyaService(
        drafter,
        graph,
        chunks,
        SugyaStore(settings.db_path),
        embedder,
        index,
        build_retraction_service(settings, embedder=embedder),
        SystemClock(),
        min_cluster_size=settings.sugya_min_cluster_size,
    )


def build_chazarah_scheduler(settings: Settings) -> ChazarahScheduler:
    """Assemble the chazarah scheduler over the shared graph / ask-log / inquiry stores."""
    clock = SystemClock()
    return ChazarahScheduler(
        GraphStore(settings.db_path),
        AskLog(settings.db_path, clock),
        InquiryStore(settings.db_path, clock),
        ScheduleStore(settings.db_path, clock),
        clock,
        settings,
    )
