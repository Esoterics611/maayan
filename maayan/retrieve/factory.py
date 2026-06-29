"""Retriever factory — assembles index + embedder (+ optional reranker, + optional
query expansion) from config.

When `query_expand_enabled` (or the `expand=` override) is on, the base hybrid
retriever is wrapped in a `MultiQueryRetriever` driven by a `CompositeExpander`
(lexicon vocabulary + optional LLM reformulations/HyDE). Expansion is additive and
gated, so with it off this returns exactly the plain `Retriever` as before.
"""

from __future__ import annotations

from maayan.config import Settings
from maayan.embed.base import Embedder
from maayan.embed.factory import build_embedder
from maayan.generate.base import GenerationBackend
from maayan.index.qdrant import QdrantIndex, build_qdrant_client
from maayan.lexicon.store import TermStore
from maayan.retrieve.expand import (
    CompositeExpander,
    LexiconExpander,
    LLMQueryExpander,
    QueryExpander,
    TermSource,
)
from maayan.retrieve.reranker import Reranker
from maayan.retrieve.retriever import MultiQueryRetriever, Retriever, Retrieving


def build_retriever(
    settings: Settings,
    *,
    embedder: Embedder | None = None,
    hybrid: bool | None = None,
    rerank: bool | None = None,
    top_k: int | None = None,
    expand: bool | None = None,
    backend: GenerationBackend | None = None,
    term_store: TermSource | None = None,
) -> Retrieving:
    """Construct a retriever wired to Qdrant, the embedder, (optionally) a reranker,
    and (optionally) query expansion.

    The `hybrid`/`rerank`/`top_k`/`expand` overrides exist for the eval harness and
    CLI to compare variants; when None they fall back to config. `backend` enables the
    LLM expander (reformulations + HyDE); without it expansion is lexicon-only.
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
    resolved_top_k = top_k if top_k is not None else settings.top_k
    base = Retriever(
        index,
        embedder,
        top_k=resolved_top_k,
        reranker=reranker,
        rerank_candidates=settings.rerank_candidates,
        expert_boost=settings.expert_boost,
        derived_boost=settings.derived_boost,
        term_boost=settings.term_boost,
        shiur_boost=settings.shiur_boost,
        hybrid=True if hybrid is None else hybrid,
    )

    use_expand = settings.query_expand_enabled if expand is None else expand
    if not use_expand:
        return base

    expanders: list[QueryExpander] = []
    if settings.query_expand_lexicon:
        terms = term_store or TermStore(settings.db_path)
        expanders.append(LexiconExpander(terms))
    if backend is not None:
        expanders.append(
            LLMQueryExpander(
                backend,
                variants=settings.query_expand_variants,
                hyde=settings.query_expand_hyde,
            )
        )
    if not expanders:
        return base  # expansion on but nothing to expand with → plain retriever
    composite = CompositeExpander(expanders, max_queries=settings.query_expand_max_queries)
    return MultiQueryRetriever(base, composite, top_k=resolved_top_k)
