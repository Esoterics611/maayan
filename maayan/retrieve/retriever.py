"""Hybrid retrieval over the Qdrant index.

Pipeline: embed the query (dense + sparse) → RRF fusion in Qdrant → optional
expert-source boost → optional cross-encoder rerank → top-k. Everything is
injected (index, embedder, optional reranker), per the DI house rule.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from qdrant_client import models

from maayan.embed.base import Embedder, Embedding
from maayan.index.qdrant import QdrantIndex
from maayan.retrieve.expand import QueryExpander
from maayan.retrieve.fuse import DEFAULT_RRF_K, rrf_fuse
from maayan.retrieve.gate import RelevanceGate
from maayan.retrieve.models import GateSignals, RetrievalResult, SearchResult
from maayan.retrieve.reranker import Reranker


@runtime_checkable
class Retrieving(Protocol):
    """Minimal retrieval interface the RAG service depends on (DI seam)."""

    def retrieve(
        self,
        query: str,
        *,
        k: int | None = None,
        book: str | None = None,
        source: str | None = None,
    ) -> RetrievalResult:
        ...


def _build_filter(
    book: str | None, source: str | None, langs: Sequence[str] | None
) -> models.Filter | None:
    must: list[models.Condition] = []
    if book:
        must.append(models.FieldCondition(key="book", match=models.MatchValue(value=book)))
    if source:
        must.append(models.FieldCondition(key="source", match=models.MatchValue(value=source)))
    if langs:
        must.append(models.FieldCondition(key="lang", match=models.MatchAny(any=list(langs))))
    return models.Filter(must=must) if must else None


def _to_search_result(point: models.ScoredPoint) -> SearchResult:
    """Qdrant point → `SearchResult`, carrying the whole payload for citation/display.

    Module-level (not a `Retriever` method) so the inspector builds results exactly
    the same way the retriever does — one definition, no drift.
    """
    payload = dict(point.payload or {})
    return SearchResult(
        ref=str(payload.get("ref", "")),
        text=str(payload.get("text", "")),
        score=float(point.score),
        lang=str(payload.get("lang", "")),
        source=str(payload.get("source", "")),
        payload=payload,
    )


def _rank_key(result: SearchResult) -> tuple[float, str]:
    """Deterministic total order for ranking: score desc, then ref asc.

    RRF fusion sums 1/(k+rank), which yields many *exactly* tied scores, and Qdrant
    returns tied points in a nondeterministic order. A stable sort by score alone
    therefore preserves that arbitrary order, so identical queries can rank
    differently run to run. Breaking ties by the (unique) ref makes ranking — and
    thus the eval harness — reproducible. The embedder is already deterministic, so
    this is the only nondeterminism in the retrieve path.
    """
    return (-result.score, result.ref)


class Retriever:
    """Hybrid retriever with optional rerank and expert-source boosting."""

    def __init__(
        self,
        index: QdrantIndex,
        embedder: Embedder,
        *,
        top_k: int = 8,
        reranker: Reranker | None = None,
        rerank_candidates: int = 30,
        expert_boost: float = 1.0,
        derived_boost: float = 1.0,
        term_boost: float = 1.0,
        shiur_boost: float = 1.0,
        summary_boost: float = 1.0,
        hybrid: bool = True,
        gate: RelevanceGate | None = None,
        gate_pool: int = 10,
    ) -> None:
        self._gate = gate
        self._gate_pool = gate_pool
        self._index = index
        self._embedder = embedder
        self._top_k = top_k
        self._reranker = reranker
        self._rerank_candidates = rerank_candidates
        self._expert_boost = expert_boost
        self._derived_boost = derived_boost
        self._term_boost = term_boost
        self._shiur_boost = shiur_boost
        self._summary_boost = summary_boost
        self._hybrid = hybrid

    def retrieve(
        self,
        query: str,
        *,
        k: int | None = None,
        book: str | None = None,
        source: str | None = None,
        langs: Sequence[str] | None = None,
    ) -> RetrievalResult:
        """Hybrid ranking + an absolute relevance score (top dense cosine) for gating."""
        final_k = k or self._top_k
        # Fetch a larger candidate pool when a reranker will reorder it.
        pool = max(final_k, self._rerank_candidates) if self._reranker else final_k

        emb = self._embedder.embed_query(query)
        flt = _build_filter(book, source, langs)
        if self._hybrid:
            points = self._index.query_hybrid(
                emb.dense, emb.sparse_indices, emb.sparse_values, limit=pool, query_filter=flt
            )
        else:
            points = self._index.query_dense(emb.dense, limit=pool, query_filter=flt)
        results = [_to_search_result(p) for p in points]
        results = self._apply_source_boosts(results)

        rerank_top: float | None = None
        if self._reranker is not None and results:
            # The cross-encoder score is a far more discriminative relevance signal
            # than bi-encoder cosine, so use it for the gate too (computed for free).
            raw_scores = self._reranker.rerank(query, [r.text for r in results])
            for r, s in zip(results, raw_scores, strict=True):
                r.score = s * self._source_boost(r.source)
            rerank_top = max(raw_scores) if raw_scores else 0.0
        results.sort(key=_rank_key)

        signals = self._gate_signals(emb, flt, results, rerank_top)
        gate = self._gate
        relevance = gate.relevance(signals) if gate is not None else signals.dense_top
        return RetrievalResult(
            results=results[:final_k], relevance=relevance, signals=signals
        )

    def search(
        self,
        query: str,
        *,
        k: int | None = None,
        book: str | None = None,
        source: str | None = None,
        langs: Sequence[str] | None = None,
    ) -> list[SearchResult]:
        """Convenience wrapper returning just the ranked results (used by the CLI)."""
        return self.retrieve(query, k=k, book=book, source=source, langs=langs).results

    # -- internals -----------------------------------------------------------
    def _gate_signals(
        self,
        emb: Embedding,
        flt: models.Filter | None,
        results: list[SearchResult],
        rerank_top: float | None,
    ) -> GateSignals:
        """Absolute per-branch signals for the gate.

        RRF fusion scores are rank-based and cannot tell "relevant" from "best of
        irrelevant", so the branches are queried on their own. In dense-only mode the
        result scores already ARE cosines and no extra query is needed; in hybrid mode
        this costs two small local Qdrant reads per retrieve.
        """
        pool = self._gate_pool
        if not self._hybrid:
            scores = [r.score for r in results[:pool]]
            top = scores[0] if scores else 0.0
            mean = statistics.fmean(scores) if scores else 0.0
            return GateSignals(
                dense_top=top, dense_mean=mean, rerank_top=rerank_top, pool=pool
            )
        dense = self._index.query_dense(emb.dense, limit=pool, query_filter=flt)
        sparse = self._index.query_sparse(
            emb.sparse_indices, emb.sparse_values, limit=pool, query_filter=flt
        )
        d = [float(p.score) for p in dense]
        s = [float(p.score) for p in sparse]
        return GateSignals(
            dense_top=d[0] if d else 0.0,
            dense_mean=statistics.fmean(d) if d else 0.0,
            sparse_top=s[0] if s else 0.0,
            sparse_mean=statistics.fmean(s) if s else 0.0,
            rerank_top=rerank_top,
            pool=pool,
        )

    def _source_boost(self, source: str) -> float:
        """Score multiplier per source: expert, derived, term, shiur, summary (all human-gated)."""
        if source == "expert":
            return self._expert_boost
        if source == "derived":
            return self._derived_boost
        if source == "term":
            return self._term_boost
        if source == "shiur":
            return self._shiur_boost
        if source == "summary":
            return self._summary_boost
        return 1.0

    def _apply_source_boosts(self, results: list[SearchResult]) -> list[SearchResult]:
        if (
            self._expert_boost == 1.0 and self._derived_boost == 1.0
            and self._term_boost == 1.0 and self._shiur_boost == 1.0
            and self._summary_boost == 1.0
        ):
            return results
        for r in results:
            boost = self._source_boost(r.source)
            if boost != 1.0:
                r.score *= boost
        return results


class MultiQueryRetriever:
    """Expand the query, retrieve each variant, RRF-fuse — a drop-in `Retrieving`.

    Wraps a base `Retriever` and a `QueryExpander`. Because it satisfies the
    `Retrieving` protocol, `RAGService` / `DevelopmentService` / threads use it with
    no change. The default-deny gate stays honest: the fused `score` is RRF (rank-
    based, not comparable to `score_threshold`), so `relevance` is carried separately
    as the MAX absolute relevance across variants — "is anything actually relevant to
    *some* phrasing of the question?".
    """

    def __init__(
        self,
        base: Retriever,
        expander: QueryExpander,
        *,
        top_k: int = 8,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> None:
        self._base = base
        self._expander = expander
        self._top_k = top_k
        self._rrf_k = rrf_k

    def retrieve(
        self,
        query: str,
        *,
        k: int | None = None,
        book: str | None = None,
        source: str | None = None,
        langs: Sequence[str] | None = None,
    ) -> RetrievalResult:
        queries = self._expander.expand(query).queries
        result_lists: list[list[SearchResult]] = []
        relevance = 0.0
        for q in queries:
            sub = self._base.retrieve(q, k=k, book=book, source=source, langs=langs)
            result_lists.append(sub.results)
            relevance = max(relevance, sub.relevance)
        fused = rrf_fuse(result_lists, limit=k or self._top_k, rrf_k=self._rrf_k)
        return RetrievalResult(results=fused, relevance=relevance)

    def search(
        self,
        query: str,
        *,
        k: int | None = None,
        book: str | None = None,
        source: str | None = None,
        langs: Sequence[str] | None = None,
    ) -> list[SearchResult]:
        """Convenience wrapper returning just the ranked results (used by the CLI)."""
        return self.retrieve(query, k=k, book=book, source=source, langs=langs).results
