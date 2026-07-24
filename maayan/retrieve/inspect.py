"""Retrieval inspector: run a query and report every stage instead of just the answer.

Production retrieval collapses the dense branch, the sparse (lexical) branch and the
RRF fusion into one ranked list plus a single `relevance` float. That is the right
interface for answering, and the wrong one for diagnosis — when a question refuses
unexpectedly there is no way to tell whether the corpus lacks the material, the
lexical branch missed, or the gate threshold is simply mistuned.

`RetrievalInspector` issues the branches separately and returns a `RetrievalTrace`.
It is deliberately a *read-only observer*: it never changes what production returns,
and it takes the same injected index/embedder/expander/reranker, so what it shows is
what the retriever would see.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence

from pydantic import BaseModel
from qdrant_client import models

from maayan.embed.base import Embedder
from maayan.index.qdrant import QdrantIndex
from maayan.retrieve.expand import QueryExpander
from maayan.retrieve.gate import RelevanceGate
from maayan.retrieve.models import GateSignals, SearchResult
from maayan.retrieve.reranker import Reranker
from maayan.retrieve.retriever import _build_filter, _to_search_result
from maayan.retrieve.trace import (
    QueryTrace,
    RetrievalTrace,
    StageHit,
    StageTrace,
)


class _TracedQuery(BaseModel):
    """Internal pairing: one variant's trace plus the ranking it produced."""

    trace: QueryTrace
    results: list[SearchResult]


def _stage(name: str, points: Sequence[models.ScoredPoint], limit: int) -> StageTrace:
    hits = [
        StageHit(
            rank=i,
            ref=str((p.payload or {}).get("ref", "")),
            score=float(p.score),
            book=str((p.payload or {}).get("book", "")),
            source=str((p.payload or {}).get("source", "")),
        )
        for i, p in enumerate(points[:limit])
    ]
    return StageTrace(name=name, hits=hits)


def _top_and_mean(points: Sequence[models.ScoredPoint], pool: int) -> tuple[float, float]:
    """Top score and mean of the top `pool` scores (0.0 for an empty branch)."""
    scores = [float(p.score) for p in points[:pool]]
    if not scores:
        return 0.0, 0.0
    return scores[0], statistics.fmean(scores)


class RetrievalInspector:
    """Runs each retrieval branch separately and reports what the gate would decide.

    `pool` is the candidate depth the mean signals are averaged over; `show` caps how
    many hits each stage lists (display only — it never affects the signals).
    """

    def __init__(
        self,
        index: QdrantIndex,
        embedder: Embedder,
        *,
        gate: RelevanceGate,
        pool: int = 10,
        show: int = 8,
        expander: QueryExpander | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        self._index = index
        self._embedder = embedder
        self._gate = gate
        self._pool = pool
        self._show = show
        self._expander = expander
        self._reranker = reranker

    def inspect(
        self,
        question: str,
        *,
        k: int | None = None,
        book: str | None = None,
        source: str | None = None,
        langs: Sequence[str] | None = None,
    ) -> RetrievalTrace:
        """Retrieve `question` and return the full per-stage trace."""
        show = k or self._show
        flt = _build_filter(book, source, langs)
        queries = self._expander.expand(question).queries if self._expander else [question]

        traced = [self._trace_one(q, flt, show) for q in queries]
        traces = [t.trace for t in traced]
        # Aggregate exactly as MultiQueryRetriever does: the best any variant achieved.
        # "Is anything relevant to *some* phrasing of the question?"
        aggregate = GateSignals(
            dense_top=max((t.signals.dense_top for t in traces), default=0.0),
            dense_mean=max((t.signals.dense_mean for t in traces), default=0.0),
            sparse_top=max((t.signals.sparse_top for t in traces), default=0.0),
            sparse_mean=max((t.signals.sparse_mean for t in traces), default=0.0),
            rerank_top=max(
                (t.signals.rerank_top for t in traces if t.signals.rerank_top is not None),
                default=None,
            ),
            pool=self._pool,
        )
        # THE SAME gate object production uses — the trace must never explain a
        # decision differently from how it was actually made.
        decision = self._gate.evaluate(aggregate)
        results = traced[0].results[:show] if traced else []
        return RetrievalTrace(
            question=question,
            queries=traces,
            signals=aggregate,
            relevance=decision.relevance,
            threshold=decision.threshold,
            gate_signal=decision.signal,
            answered=bool(results) and decision.answered,
            results=results,
        )

    # -- internals -----------------------------------------------------------
    def _trace_one(
        self, query: str, flt: models.Filter | None, show: int
    ) -> _TracedQuery:
        emb = self._embedder.embed_query(query)
        depth = max(self._pool, show)
        dense = self._index.query_dense(emb.dense, limit=depth, query_filter=flt)
        sparse = self._index.query_sparse(
            emb.sparse_indices, emb.sparse_values, limit=depth, query_filter=flt
        )
        fused = self._index.query_hybrid(
            emb.dense, emb.sparse_indices, emb.sparse_values, limit=depth, query_filter=flt
        )
        dense_top, dense_mean = _top_and_mean(dense, self._pool)
        sparse_top, sparse_mean = _top_and_mean(sparse, self._pool)

        stages = [
            _stage("dense", dense, show),
            _stage("sparse", sparse, show),
            _stage("fused", fused, show),
        ]
        rerank_top: float | None = None
        ranked = list(fused)
        if self._reranker is not None and fused:
            scores = self._reranker.rerank(
                query, [str((p.payload or {}).get("text", "")) for p in fused]
            )
            order = sorted(range(len(fused)), key=lambda i: -scores[i])
            stages.append(
                StageTrace(
                    name="rerank",
                    hits=[
                        StageHit(
                            rank=rank,
                            ref=str((fused[i].payload or {}).get("ref", "")),
                            score=scores[i],
                            book=str((fused[i].payload or {}).get("book", "")),
                            source=str((fused[i].payload or {}).get("source", "")),
                        )
                        for rank, i in enumerate(order[:show])
                    ],
                )
            )
            ranked = [fused[i] for i in order]
            rerank_top = max(scores)

        return _TracedQuery(
            trace=QueryTrace(
                query=query,
                stages=stages,
                signals=GateSignals(
                    dense_top=dense_top, dense_mean=dense_mean,
                    sparse_top=sparse_top, sparse_mean=sparse_mean,
                    rerank_top=rerank_top, pool=self._pool,
                ),
            ),
            results=[_to_search_result(p) for p in ranked],
        )
