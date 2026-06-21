"""Retriever factory — assembles index + embedder (+ optional reranker) from config."""

from __future__ import annotations

from maayan.config import Settings
from maayan.embed.base import Embedder
from maayan.embed.factory import build_embedder
from maayan.index.qdrant import QdrantIndex, build_qdrant_client
from maayan.retrieve.reranker import Reranker
from maayan.retrieve.retriever import Retriever


def build_retriever(settings: Settings, *, embedder: Embedder | None = None) -> Retriever:
    """Construct a Retriever wired to Qdrant, the embedder, and (optionally) a reranker."""
    embedder = embedder or build_embedder(settings)
    index = QdrantIndex(
        build_qdrant_client(settings), settings.collection_name, embedder.dim
    )
    reranker: Reranker | None = None
    if settings.rerank_enabled:
        from maayan.retrieve.reranker import BGEReranker

        reranker = BGEReranker(settings.rerank_model)
    return Retriever(
        index,
        embedder,
        top_k=settings.top_k,
        reranker=reranker,
        rerank_candidates=settings.rerank_candidates,
        expert_boost=settings.expert_boost,
    )
