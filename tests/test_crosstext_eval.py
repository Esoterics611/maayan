"""Tests for Prompt 18 — cross-text (book-diversity) eval.

Pure metrics on hand-checked inputs + harness aggregation with a fake retriever
(no network, no models) + a CI guard on the shipped gold set.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from maayan.eval.crosstext_harness import run_crosstext_eval
from maayan.eval.crosstext_metrics import (
    CROSSTEXT_BOOKS,
    book_of_ref,
    coverage_at_k,
    distinct_books_at_k,
)
from maayan.eval.goldset import GoldExample, load_goldset
from maayan.retrieve.models import RetrievalResult, SearchResult

TANYA = "Tanya, Part I; Likkutei Amarim 1:1"
TORAH_OHR = "Torah Ohr, Bereshit 2:3"
LIKUTEI = "Likutei Torah, Bamidbar, §2"


# -- book_of_ref: derive the book from a ref (longest-prefix match) ------------
def test_book_of_ref_recognizes_each_book() -> None:
    assert book_of_ref(TANYA) == "Tanya"
    assert book_of_ref(TORAH_OHR) == "Torah Ohr"
    assert book_of_ref(LIKUTEI) == "Likutei Torah"


def test_book_of_ref_unknown_is_none() -> None:
    assert book_of_ref("Zohar, Bereshit 1a") is None


# -- coverage_at_k: single-book, all-books, partial ---------------------------
def test_coverage_partial_all_and_none() -> None:
    expected = ["Tanya", "Torah Ohr"]
    # both books present in top-2 → full coverage
    assert coverage_at_k(expected, ["Tanya", "Torah Ohr"], k=2) == pytest.approx(1.0)
    # only one of the two books present → 0.5
    assert coverage_at_k(expected, ["Tanya", "Tanya"], k=2) == pytest.approx(0.5)
    # the covering book is at rank 3, outside top-2 → 0.5 (only Tanya counts)
    assert coverage_at_k(expected, ["Tanya", "Tanya", "Torah Ohr"], k=2) == pytest.approx(0.5)
    # nothing expected (not a cross-text question) → 0.0
    assert coverage_at_k([], ["Tanya", "Torah Ohr"], k=2) == 0.0


def test_coverage_all_three_books() -> None:
    expected = ["Tanya", "Torah Ohr", "Likutei Torah"]
    retrieved = ["Tanya", "Torah Ohr", "Likutei Torah", "Tanya"]
    assert coverage_at_k(expected, retrieved, k=4) == pytest.approx(1.0)
    assert coverage_at_k(expected, retrieved, k=2) == pytest.approx(2 / 3)


def test_distinct_books_at_k() -> None:
    assert distinct_books_at_k(["Tanya", "Tanya", "Torah Ohr"], k=3) == 2
    assert distinct_books_at_k(["Tanya", "Tanya"], k=3) == 1
    assert distinct_books_at_k(["Tanya", "Torah Ohr", "Likutei Torah"], k=2) == 2  # top-2 only
    assert distinct_books_at_k([], k=3) == 0


# -- harness aggregation with a fake retriever --------------------------------
class _FakeRetriever:
    """Returns fixed refs per question; book derives from the ref prefix."""

    def __init__(self, answers: dict[str, list[str]]) -> None:
        self._answers = answers

    def retrieve(self, query: str, *, k=None, book=None, source=None) -> RetrievalResult:
        refs = self._answers.get(query, [])
        results = [
            SearchResult(ref=r, text="", score=1.0 - i * 0.1, lang="he", source="sefaria",
                         payload={"book": book_of_ref(r) or ""})
            for i, r in enumerate(refs)
        ]
        return RetrievalResult(results=results, relevance=results[0].score if results else 0.0)


def test_run_crosstext_eval_aggregates() -> None:
    retriever = _FakeRetriever({
        # q1: spans Tanya+Torah Ohr, retrieval pulls both → coverage 1.0, multi-book yes
        "q1": [TANYA, TORAH_OHR],
        # q2: spans Tanya+Likutei Torah, retrieval only pulls Tanya → coverage 0.5, single-book
        "q2": [TANYA, TANYA],
    })
    examples = [
        GoldExample(question="q1", expected_refs=[TANYA, TORAH_OHR]),
        GoldExample(question="q2", expected_refs=[TANYA, LIKUTEI]),
    ]
    report = run_crosstext_eval(retriever, examples, k=10)

    assert report.n == 2
    assert report.questions[0].coverage == pytest.approx(1.0)
    assert report.questions[0].multi_book is True
    assert report.questions[0].expected_books == ["Tanya", "Torah Ohr"]
    assert report.questions[1].coverage == pytest.approx(0.5)
    assert report.questions[1].multi_book is False
    assert report.mean_coverage == pytest.approx(0.75)
    assert report.multi_book_rate == pytest.approx(0.5)


def test_run_crosstext_eval_respects_k_window() -> None:
    # The covering book sits at rank 3; with k=2 it's out of the window.
    retriever = _FakeRetriever({"q": [TANYA, TANYA, TORAH_OHR]})
    examples = [GoldExample(question="q", expected_refs=[TANYA, TORAH_OHR])]
    assert run_crosstext_eval(retriever, examples, k=2).questions[0].coverage == pytest.approx(0.5)
    assert run_crosstext_eval(retriever, examples, k=3).questions[0].coverage == pytest.approx(1.0)


# -- CI guard: the shipped gold set is well-formed ----------------------------
def test_shipped_crosstext_goldset_is_well_formed() -> None:
    """Every shipped entry must have a question and expected_refs spanning ≥2 books."""
    path = Path(__file__).resolve().parents[1] / "eval" / "crosstext_goldset.yaml"
    examples = load_goldset(str(path))
    assert len(examples) >= 8, "want a broad cross-text gold set"
    for e in examples:
        assert e.question.strip(), "every entry needs a question"
        books = {book_of_ref(r) for r in e.expected_refs}
        books.discard(None)
        assert len(books) >= 2, (
            f"cross-text entry must span ≥2 known books, got {books}: {e.question!r}"
        )
        for r in e.expected_refs:
            assert book_of_ref(r) in CROSSTEXT_BOOKS, f"ref of unknown book: {r!r}"
