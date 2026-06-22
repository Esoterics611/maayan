"""Retrieval metrics: hit@k, recall@k, MRR. Pure, hand-checkable functions.

Ref matching is prefix-aware: a chapter-level gold ref like
"Tanya, Part I; Likkutei Amarim 1" matches any segment retrieved within it
("...Amarim 1:13"), so gold sets can be written at chapter granularity.
"""

from __future__ import annotations

from collections.abc import Sequence


def ref_matches(expected: str, retrieved: str) -> bool:
    """True if a retrieved ref satisfies an expected (possibly chapter-level) ref."""
    return retrieved == expected or retrieved.startswith(expected + ":")


def _hits(retrieved: Sequence[str], expected: Sequence[str]) -> list[bool]:
    """For each retrieved ref (in order), whether it matches any expected ref."""
    return [any(ref_matches(e, r) for e in expected) for r in retrieved]


def hit_at_k(retrieved: Sequence[str], expected: Sequence[str], k: int) -> float:
    """1.0 if any expected ref appears in the top-k, else 0.0."""
    if not expected:
        return 0.0
    return 1.0 if any(_hits(retrieved[:k], expected)) else 0.0


def recall_at_k(retrieved: Sequence[str], expected: Sequence[str], k: int) -> float:
    """Fraction of expected refs found within the top-k."""
    if not expected:
        return 0.0
    top = retrieved[:k]
    found = sum(1 for e in expected if any(ref_matches(e, r) for r in top))
    return found / len(expected)


def mrr(retrieved: Sequence[str], expected: Sequence[str], k: int | None = None) -> float:
    """Reciprocal rank of the first matching retrieved ref (0 if none)."""
    seq = retrieved[:k] if k is not None else retrieved
    for i, hit in enumerate(_hits(seq, expected), start=1):
        if hit:
            return 1.0 / i
    return 0.0
