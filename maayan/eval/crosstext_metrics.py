"""Cross-text (book-diversity) metrics — pure, hand-checkable functions.

Phase 3's headline is *co-retrieval across books*: a question whose answer should
draw on Tanya + Torah Ohr + Likutei Torah together. These metrics measure exactly
that, at BOOK granularity (not segment granularity — that's what hit@k/recall@k in
:mod:`maayan.eval.metrics` already cover):

- ``coverage_at_k`` — of the books a question's expected refs span, the fraction
  represented somewhere in the top-k retrieved results.
- ``distinct_books_at_k`` — how many distinct books the top-k actually pulled from
  (``>= 2`` is the boolean "cross-text retrieval happened at all").

A result's book is derived from its ref/payload exactly as retrieval labels it: the
canonical book name prefixes the ref (e.g. "Tanya, Part I; …", "Torah Ohr, Bereshit …",
"Likutei Torah, …"), so :func:`book_of_ref` recovers it without any model.
"""

from __future__ import annotations

from collections.abc import Sequence

# The three texts whose co-retrieval Phase 3 claims. Names prefix their refs, so they
# double as the recognizer for `book_of_ref` (longest match wins, so "Torah Ohr" and
# "Likutei Torah" are matched whole, never shadowed by a shorter name).
CROSSTEXT_BOOKS: tuple[str, ...] = ("Tanya", "Torah Ohr", "Likutei Torah")


def book_of_ref(ref: str, books: Sequence[str] = CROSSTEXT_BOOKS) -> str | None:
    """The canonical book whose name prefixes `ref` (longest match), or None."""
    matches = [b for b in books if ref == b or ref.startswith(b)]
    return max(matches, key=len) if matches else None


def coverage_at_k(
    expected_books: Sequence[str | None], retrieved_books: Sequence[str | None], k: int
) -> float:
    """Fraction of the EXPECTED books represented among the first k retrieved books.

    `retrieved_books` is one book label per retrieved result, in rank order; the first
    k are considered. 0.0 when nothing is expected (the question isn't cross-text).
    """
    expected = {b for b in expected_books if b}
    if not expected:
        return 0.0
    top = {b for b in retrieved_books[:k] if b}
    return len(expected & top) / len(expected)


def distinct_books_at_k(retrieved_books: Sequence[str | None], k: int) -> int:
    """How many distinct (non-empty) books the first k retrieved results span."""
    return len({b for b in retrieved_books[:k] if b})
