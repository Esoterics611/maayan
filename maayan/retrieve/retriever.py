"""Hybrid retrieval over the Qdrant index.

Pipeline: embed the query (dense + sparse) → RRF fusion in Qdrant → optional
expert-source boost → optional cross-encoder rerank → top-k. Everything is
injected (index, embedder, optional reranker), per the DI house rule.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from qdrant_client import models

from maayan.embed.base import Embedder
from maayan.index.qdrant import QdrantIndex
from maayan.retrieve.models import RetrievalResult, SearchResult
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
        hybrid: bool = True,
    ) -> None:
        self._index = index
        self._embedder = embedder
        self._top_k = top_k
        self._reranker = reranker
        self._rerank_candidates = rerank_candidates
        self._expert_boost = expert_boost
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
        results = [self._to_result(p) for p in points]
        results = self._apply_expert_boost(results)

        if self._reranker is not None and results:
            # The cross-encoder score is a far more discriminative relevance signal
            # than bi-encoder cosine, so use it for the gate too (computed for free).
            raw_scores = self._reranker.rerank(query, [r.text for r in results])
            for r, s in zip(results, raw_scores, strict=True):
                r.score = s * (self._expert_boost if r.source == "expert" else 1.0)
            results.sort(key=lambda r: r.score, reverse=True)
            relevance = max(raw_scores) if raw_scores else 0.0
        else:
            results.sort(key=lambda r: r.score, reverse=True)
            if self._hybrid:
                # Absolute relevance gate: top dense cosine (RRF scores are rank-based).
                dense_top = self._index.query_dense(emb.dense, limit=1, query_filter=flt)
                relevance = float(dense_top[0].score) if dense_top else 0.0
            else:
                # Dense-only: result scores already are cosine similarities.
                relevance = results[0].score if results else 0.0

        return RetrievalResult(results=results[:final_k], relevance=relevance)

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
    @staticmethod
    def _to_result(point: models.ScoredPoint) -> SearchResult:
        payload = dict(point.payload or {})
        return SearchResult(
            ref=str(payload.get("ref", "")),
            text=str(payload.get("text", "")),
            score=float(point.score),
            lang=str(payload.get("lang", "")),
            source=str(payload.get("source", "")),
            payload=payload,
        )

    def _apply_expert_boost(self, results: list[SearchResult]) -> list[SearchResult]:
        if self._expert_boost == 1.0:
            return results
        for r in results:
            if r.source == "expert":
                r.score *= self._expert_boost
        return results
