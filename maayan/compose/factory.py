"""Composition service factory (DI at the edge)."""

from __future__ import annotations

from maayan.capture.factory import build_capture_service
from maayan.clock import SystemClock
from maayan.compose.service import CompositionService
from maayan.compose.store import CompositionStore
from maayan.config import Settings
from maayan.embed.base import Embedder
from maayan.embed.factory import build_embedder
from maayan.generate.factory import build_generation_backend
from maayan.generate.parent import build_parent_context
from maayan.retrieve.factory import build_retriever
from maayan.threads.factory import build_thread_service


def build_composition_service(
    settings: Settings, *, embedder: Embedder | None = None
) -> CompositionService:
    """Assemble a CompositionService wired to the same retriever/backend/stores as the rest.

    The retriever (for `fill` + auto-outline) and the capture service (for
    `promote_connection`) share the one embedder, so `maayan ui` builds it once.

    The backend is passed to `build_retriever` as well as to the service: with
    `query_expand_enabled` on, that is what lets `fill` use the SAME expansion (LLM
    reformulations + HyDE) that `ask` gets. Without it the flag silently means
    something weaker here than it does there (R3).
    """
    embedder = embedder or build_embedder(settings)
    backend = build_generation_backend(settings)
    return CompositionService(
        build_retriever(settings, embedder=embedder, backend=backend),
        backend,
        CompositionStore(settings.db_path),
        build_thread_service(settings),
        SystemClock(),
        settings,
        build_capture_service(settings, embedder=embedder),
        parent_context=build_parent_context(settings),
    )
