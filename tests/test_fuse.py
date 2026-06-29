"""Tests for Reciprocal Rank Fusion (pure; no models)."""

from __future__ import annotations

from maayan.retrieve.fuse import rrf_fuse
from maayan.retrieve.models import SearchResult


def _r(ref: str, score: float = 0.0) -> SearchResult:
    return SearchResult(ref=ref, text=ref, score=score, lang="he", source="sefaria", payload={})


def test_fuse_rewards_agreement_across_lists() -> None:
    # A is top of BOTH lists; B and C each appear in only one list. The chunk found
    # by several query variants beats chunks found by just one — the whole point of
    # fusing multi-query retrieval.
    list1 = [_r("A"), _r("B")]
    list2 = [_r("A"), _r("C")]
    fused = rrf_fuse([list1, list2], limit=3)
    refs = [r.ref for r in fused]
    assert refs[0] == "A"  # consensus across variants wins
    # B and C are symmetric (rank 1 in one list each) → tie broken by ref asc.
    assert refs[1:] == ["B", "C"]


def test_fuse_is_deterministic_and_order_independent_for_ties() -> None:
    a = [_r("X"), _r("Y")]
    b = [_r("Y"), _r("X")]
    assert [r.ref for r in rrf_fuse([a, b], limit=2)] == [
        r.ref for r in rrf_fuse([b, a], limit=2)
    ]


def test_fuse_dedupes_by_ref_and_sets_fused_score() -> None:
    single = [_r("A"), _r("B")]
    fused = rrf_fuse([single, single], limit=5)
    assert [r.ref for r in fused] == ["A", "B"]  # no duplicates
    # A is rank 0 in both lists: 2 * 1/(60+0); B is rank 1 in both: 2 * 1/(60+1).
    assert fused[0].score == 2.0 / 60
    assert fused[0].score > fused[1].score


def test_fuse_respects_limit() -> None:
    lst = [_r("A"), _r("B"), _r("C"), _r("D")]
    assert len(rrf_fuse([lst], limit=2)) == 2


def test_fuse_empty() -> None:
    assert rrf_fuse([], limit=5) == []
    assert rrf_fuse([[]], limit=5) == []
