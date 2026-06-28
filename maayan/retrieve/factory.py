"""Retriever factory — assembles index + embedder (+ optional reranker) from config."""

from __future__ import annotations

from maayan.config import Settings
from maayan.embed.base import Embedder
from maayan.embed.factory import build_embedder
from maayan.index.qdrant import QdrantIndex, build_qdrant_client
from maayan.retrieve.reranker import Reranker
from maayan.retrieve.retriever import Retriever


def build_retriever(
    settings: Settings,
    *,
    embedder: Embedder | None = None,
    hybrid: bool | None = None,
    rerank: bool | None = None,
    top_k: int | None = None,
) -> Retriever:
    """Construct a Retriever wired to Qdrant, the embedder, and (optionally) a reranker.

    The `hybrid`/`rerank`/`top_k` overrides exist for the eval harness to compare
    variants; when None they fall back to config.
    """
    embedder = embedder or build_embedder(settings)
    index = QdrantIndex(
        build_qdrant_client(settings), settings.collection_name, embedder.dim
    )
    use_rerank = settings.rerank_enabled if rerank is None else rerank
    reranker: Reranker | None = None
    if use_rerank:
        from maayan.retrieve.reranker import BGEReranker

        reranker = BGEReranker(settings.rerank_model)
    return Retriever(
        index,
        embedder,
        top_k=top_k if top_k is not None else settings.top_k,
        reranker=reranker,
        rerank_candidates=settings.rerank_candidates,
        expert_boost=settings.expert_boost,
        derived_boost=settings.derived_boost,
        term_boost=settings.term_boost,
        shiur_boost=settings.shiur_boost,
        hybrid=True if hybrid is None else hybrid,
    )
