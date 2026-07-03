"""Agent service factory (DI at the edge)."""

from __future__ import annotations

from maayan.agent.service import AgentService
from maayan.agent.store import TraceStore
from maayan.clock import SystemClock
from maayan.config import Settings
from maayan.corpus.store import ChunkStore
from maayan.embed.base import Embedder
from maayan.generate.base import GenerationBackend
from maayan.generate.rag import RAGService
from maayan.graph.store import GraphStore
from maayan.lexicon.store import TermStore
from maayan.retrieve.retriever import Retrieving


def build_agent_service(
    settings: Settings,
    retriever: Retrieving,
    rag: RAGService,
    backend: GenerationBackend,
    *,
    embedder: Embedder | None = None,  # noqa: ARG001 - symmetry with sibling factories
) -> AgentService:
    """Assemble the chavrusa agent over the SAME retriever/RAG the plain ask uses.

    Sharing the retriever and RAGService instances (not just their config) is
    the reuse guarantee: the agent's gate inputs and conclude path are literally
    the ones `ask` runs.
    """
    return AgentService(
        retriever,
        rag,
        backend,
        ChunkStore(settings.db_path),
        GraphStore(settings.db_path),
        TermStore(settings.db_path),
        TraceStore(settings.db_path),
        SystemClock(),
        score_threshold=settings.score_threshold,
        max_hops=settings.agent_max_hops,
        max_chunks=settings.agent_max_chunks,
        max_calls=settings.agent_max_calls,
    )
