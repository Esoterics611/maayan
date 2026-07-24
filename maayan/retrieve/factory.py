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
from maayan.retrieve.gate import RelevanceGate, build_gate
from maayan.retrieve.inspect import RetrievalInspector
from maayan.retrieve.reranker import Reranker
from maayan.retrieve.retriever import MultiQueryRetriever, Retriever, Retrieving


def build_relevance_gate(settings: Settings) -> RelevanceGate:
    """The configured default-deny gate. One construction point for every surface."""
    return build_gate(
        settings.gate_signal,
        # The RAW per-signal thresholds: `build_gate` selects between them, so passing
        # `effective_score_threshold` here would be circular.
        score_threshold=settings.score_threshold,
        hybrid_threshold=settings.gate_hybrid_threshold,
        sparse_weight=settings.gate_sparse_weight,
    )


def build_retriever(
    settings: Settings,
    *,
    embedder: Embedder | None = None,
    hybrid: bool | None = None,
    rerank: bool | None = None,
    top_k: int | None = None,
    expand: bool | None = None,
    graph: bool | None = None,
    backend: GenerationBackend | None = None,
    term_store: TermSource | None = None,
) -> Retrieving:
    """Construct a retriever wired to Qdrant, the embedder, (optionally) a reranker,
    (optionally) query expansion, and (optionally) graph expansion.

    The `hybrid`/`rerank`/`top_k`/`expand`/`graph` overrides exist for the eval
    harness and CLI to compare variants; when None they fall back to config.
    `backend` enables the LLM expander (reformulations + HyDE); without it expansion
    is lexicon-only. Graph expansion wraps the OUTERMOST retriever so its gate sees
    exactly the relevance the RAG gate will see.
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
        summary_boost=settings.summary_boost,
        hybrid=True if hybrid is None else hybrid,
        gate=build_relevance_gate(settings),
        gate_pool=settings.gate_pool,
    )

    retriever: Retrieving = base
    use_expand = settings.query_expand_enabled if expand is None else expand
    if use_expand:
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
        if expanders:  # expansion on but nothing to expand with → plain retriever
            composite = CompositeExpander(
                expanders, max_queries=settings.query_expand_max_queries
            )
            retriever = MultiQueryRetriever(base, composite, top_k=resolved_top_k)

    use_graph = settings.graph_expand_enabled if graph is None else graph
    if use_graph:
        from maayan.corpus.store import ChunkStore
        from maayan.graph.store import GraphStore
        from maayan.retrieve.graph_expand import GraphExpandingRetriever

        retriever = GraphExpandingRetriever(
            retriever,
            GraphStore(settings.db_path),
            ChunkStore(settings.db_path),
            score_threshold=settings.effective_score_threshold,
            seeds=settings.graph_expand_seeds,
            limit=settings.graph_expand_limit,
            reranker=reranker,
        )
    return retriever


def build_inspector(
    settings: Settings,
    *,
    embedder: Embedder | None = None,
    rerank: bool | None = None,
    expand: bool | None = None,
    backend: GenerationBackend | None = None,
    term_store: TermSource | None = None,
) -> RetrievalInspector:
    """Assemble a `RetrievalInspector` from the same parts as `build_retriever`.

    Deliberately shares the embedder, index and (optional) reranker/expander wiring so
    the trace reports what production actually sees. Graph expansion is not wrapped:
    the inspector's job is the search itself, and a graph hop adds refs that were never
    ranked by a branch.
    """
    embedder = embedder or build_embedder(settings)
    index = QdrantIndex(build_qdrant_client(settings), settings.collection_name, embedder.dim)
    reranker: Reranker | None = None
    if settings.rerank_enabled if rerank is None else rerank:
        from maayan.retrieve.reranker import BGEReranker

        reranker = BGEReranker(settings.rerank_model)

    expander: QueryExpander | None = None
    if settings.query_expand_enabled if expand is None else expand:
        expanders: list[QueryExpander] = []
        if settings.query_expand_lexicon:
            expanders.append(LexiconExpander(term_store or TermStore(settings.db_path)))
        if backend is not None:
            expanders.append(
                LLMQueryExpander(
                    backend,
                    variants=settings.query_expand_variants,
                    hyde=settings.query_expand_hyde,
                )
            )
        if expanders:
            expander = CompositeExpander(
                expanders, max_queries=settings.query_expand_max_queries
            )

    return RetrievalInspector(
        index,
        embedder,
        gate=build_relevance_gate(settings),
        pool=settings.gate_pool,
        show=settings.inspect_show,
        expander=expander,
        reranker=reranker,
    )
