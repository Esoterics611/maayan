"""Cross-text eval harness: run a gold set and report book-diversity@k.

Reuses the existing :class:`~maayan.eval.goldset.GoldExample` loader — a cross-text
gold question is just a ``{question, expected_refs}`` whose expected refs deliberately
span ≥2 books. For each question we retrieve once via the injected Retriever, label
each result's book, and score:

- per-question ``coverage`` — of the books this question spans, the fraction the
  top-k retrieved, and
- ``multi_book`` — whether the top-k pulled from ≥2 distinct books at all,

then aggregate to a mean coverage and a multi-book rate. Fully mockable: a fake
retriever with no network/models drives the unit tests.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from maayan.eval.crosstext_metrics import (
    CROSSTEXT_BOOKS,
    book_of_ref,
    coverage_at_k,
    distinct_books_at_k,
)
from maayan.eval.goldset import GoldExample
from maayan.retrieve.models import SearchResult
from maayan.retrieve.retriever import Retrieving


@dataclass(frozen=True)
class CrosstextQuestionResult:
    """One question's cross-text outcome (books expected vs books retrieved)."""

    question: str
    expected_books: list[str]
    retrieved_books: list[str]  # distinct books in the top-k, in first-seen order
    coverage: float
    multi_book: bool


@dataclass(frozen=True)
class CrosstextReport:
    """Aggregated cross-text results (both numbers: higher is better)."""

    k: int
    n: int
    questions: list[CrosstextQuestionResult]
    mean_coverage: float
    multi_book_rate: float  # fraction of questions whose top-k spanned ≥2 books


def _result_book(result: SearchResult, books: Sequence[str]) -> str | None:
    """Label a result's book from its payload (authoritative) or its ref."""
    payload_book = result.payload.get("book")
    if isinstance(payload_book, str) and payload_book in books:
        return payload_book
    return book_of_ref(result.ref, books)


def _distinct(values: Sequence[str | None]) -> list[str]:
    """Distinct non-empty labels, preserving first-seen order."""
    seen: list[str] = []
    for v in values:
        if v and v not in seen:
            seen.append(v)
    return seen


def run_crosstext_eval(
    retriever: Retrieving,
    examples: Sequence[GoldExample],
    *,
    k: int,
    books: Sequence[str] = CROSSTEXT_BOOKS,
) -> CrosstextReport:
    """Run every cross-text gold question through the retriever and aggregate."""
    questions: list[CrosstextQuestionResult] = []
    coverage_sum = 0.0
    multi_book = 0
    for ex in examples:
        expected_books = _distinct([book_of_ref(r, books) for r in ex.expected_refs])
        result = retriever.retrieve(ex.question, k=k)
        retrieved_labels = [_result_book(r, books) for r in result.results]
        coverage = coverage_at_k(expected_books, retrieved_labels, k)
        is_multi = distinct_books_at_k(retrieved_labels, k) >= 2
        coverage_sum += coverage
        multi_book += int(is_multi)
        questions.append(
            CrosstextQuestionResult(
                question=ex.question,
                expected_books=expected_books,
                retrieved_books=_distinct(retrieved_labels)[:k],
                coverage=coverage,
                multi_book=is_multi,
            )
        )
    n = len(questions)
    return CrosstextReport(
        k=k,
        n=n,
        questions=questions,
        mean_coverage=coverage_sum / n if n else 0.0,
        multi_book_rate=multi_book / n if n else 0.0,
    )


def format_crosstext_report(report: CrosstextReport) -> str:
    """Render the per-question table plus the aggregate (and the real-run caveat)."""
    lines = [
        f"Cross-text gold set: {report.n} questions · top-k = {report.k}",
        "",
        f"{'coverage':>9} | {'≥2 books':>8} | books expected → retrieved",
        "-" * 64,
    ]
    for q in report.questions:
        exp = "+".join(q.expected_books) or "—"
        got = "+".join(q.retrieved_books) or "—"
        lines.append(
            f"{q.coverage:>9.3f} | {('yes' if q.multi_book else 'no'):>8} | {exp} → {got}"
        )
    lines += [
        "-" * 64,
        f"mean cross-text coverage@{report.k}: {report.mean_coverage:.3f}",
        f"≥2-book retrieval rate:        {report.multi_book_rate:.3f}",
        "",
        "Note: a meaningful run needs the full three-book corpus (Tanya + Torah Ohr +",
        "Likutei Torah) ingested and indexed; against a partial index, coverage is a",
        "floor, not the ceiling.",
    ]
    return "\n".join(lines)
