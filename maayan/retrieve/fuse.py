"""Reciprocal Rank Fusion (RRF) over several ranked result lists.

Multi-query retrieval issues one search per query *variant* and must merge the
ranked lists into a single ordering. RRF is the standard, score-agnostic way to do
that: a document's fused score is the sum over lists of ``1 / (rrf_k + rank)``, so a
chunk that ranks high in several variants beats one that ranks high in only one —
*without* comparing the lists' raw scores (which, post-rerank or post-RRF inside a
single search, are not on a shared scale).

Pure and deterministic: dedupe by `ref`, tie-break by `ref` ascending — mirroring
`retriever._rank_key`, so identical inputs always fuse to the same order. No models,
so it is fully unit-testable on its own.
"""

from __future__ import annotations

from collections.abc import Sequence

from maayan.retrieve.models import SearchResult

DEFAULT_RRF_K = 60


def rrf_fuse(
    result_lists: Sequence[Sequence[SearchResult]],
    *,
    limit: int,
    rrf_k: int = DEFAULT_RRF_K,
) -> list[SearchResult]:
    """Fuse ranked `SearchResult` lists into one ranking via Reciprocal Rank Fusion.

    Each list is assumed already ranked best-first. A result's fused score is the sum
    of ``1 / (rrf_k + rank)`` over every list it appears in (rank is 0-based). Results
    are deduped by `ref`; the first-seen `SearchResult` object is kept and its `score`
    is overwritten with the fused score so downstream ranking/display stay consistent.
    Returns the top `limit`, ordered by fused score desc then `ref` asc.
    """
    fused: dict[str, float] = {}
    chosen: dict[str, SearchResult] = {}
    for results in result_lists:
        for rank, result in enumerate(results):
            fused[result.ref] = fused.get(result.ref, 0.0) + 1.0 / (rrf_k + rank)
            chosen.setdefault(result.ref, result)

    ordered = sorted(chosen.values(), key=lambda r: (-fused[r.ref], r.ref))
    for r in ordered:
        r.score = fused[r.ref]
    return ordered[:limit]
