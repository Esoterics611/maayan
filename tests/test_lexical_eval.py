"""Tests for the lexical recall guard — pure logic + a stub retriever, no models."""

from __future__ import annotations

from maayan.corpus.models import Chunk
from maayan.eval.lexical import (
    LexicalCase,
    LexicalGoldset,
    find_occurrences,
    format_lexical_report,
    load_lexical_goldset,
    run_lexical_eval,
    save_lexical_goldset,
    select_cases,
)
from maayan.retrieve.models import RetrievalResult, SearchResult


def _chunk(ref: str, text: str, book: str = "Tanya") -> Chunk:
    return Chunk.make(
        ref=ref, book=book, section_path=[ref], lang="he", text=text,
        source="sefaria",  # type: ignore[arg-type]
    )


CHUNKS = [
    _chunk("A 1", "ענין הצמצום הוא העלם האור"),
    _chunk("A 2", "וצמצום הראשון היה כדי לגלות"),
    _chunk("A 3", "הַצִּמְצוּם בְּאוֹר אֵין סוֹף", book="Torah Ohr"),  # vocalized
    _chunk("A 4", "ביטול היש לאין"),
]


def test_occurrences_match_across_nikkud_and_gershayim() -> None:
    # The vocalized chunk must count: folding is exactly what R5 was about.
    assert find_occurrences(CHUNKS, "צמצום") == ["A 1", "A 2", "A 3"]
    assert find_occurrences(CHUNKS, "ביטול") == ["A 4"]
    assert find_occurrences(CHUNKS, "לא קיים") == []
    assert find_occurrences(CHUNKS, "") == []


def test_select_cases_skips_terms_outside_the_occurrence_range() -> None:
    cases = select_cases(CHUNKS, ["צמצום", "ביטול"], min_occurrences=3, max_occurrences=40)
    # "ביטול" occurs once — recall@k on it would be a coin flip, so it is dropped.
    assert [c.term for c in cases] == ["צמצום"]
    assert cases[0].occurrences == 3
    assert cases[0].books == ["Tanya", "Torah Ohr"]

    too_common = select_cases(CHUNKS, ["צמצום"], min_occurrences=1, max_occurrences=2)
    assert too_common == []


class _StubRetriever:
    """Returns a fixed ranking per query."""

    def __init__(self, ranking: dict[str, list[str]]) -> None:
        self._ranking = ranking

    def retrieve(self, query: str, **kwargs: object) -> RetrievalResult:
        refs = self._ranking.get(query, [])
        return RetrievalResult(
            results=[
                SearchResult(ref=r, text="", score=1.0, lang="he", source="sefaria", payload={})
                for r in refs
            ],
            relevance=1.0,
        )


CASE = LexicalCase(term="צמצום", expected_refs=["A 1", "A 2", "A 3"])


def test_recall_counts_how_much_of_the_discussion_surfaced() -> None:
    # Two of three known occurrences are in the top 3; the third is at rank 5.
    retriever = _StubRetriever({"צמצום": ["A 1", "X", "A 2", "Y", "A 3"]})
    report = run_lexical_eval(retriever, [CASE], ks=[1, 3, 5])
    assert report.recall[1] == 1 / 3
    assert report.recall[3] == 2 / 3
    assert report.recall[5] == 1.0
    # Micro counts are absolute refs found, not per-case averages.
    assert report.found[3] == 2 and report.found[5] == 3
    assert report.total_occurrences == 3


def test_precision_measures_whether_the_top_k_actually_contains_the_term() -> None:
    retriever = _StubRetriever({"צמצום": ["A 1", "X", "A 2", "Y", "A 3"]})
    report = run_lexical_eval(retriever, [CASE], ks=[1, 3, 5])
    assert report.precision[1] == 1.0  # rank 1 contains the term
    assert report.precision[3] == 2 / 3
    assert report.precision[5] == 3 / 5


def test_precision_stays_meaningful_where_recall_is_capped_by_k() -> None:
    """A term in 300 passages can never have high recall@10 — precision still discriminates."""
    common = LexicalCase(term="ביטול", expected_refs=[f"C {i}" for i in range(300)])
    perfect = _StubRetriever({"ביטול": [f"C {i}" for i in range(10)]})
    junk = _StubRetriever({"ביטול": [f"noise {i}" for i in range(10)]})

    good = run_lexical_eval(perfect, [common], ks=[10])
    bad = run_lexical_eval(junk, [common], ks=[10])
    # Recall cannot tell these apart in any useful way (10/300 vs 0/300)...
    assert good.recall[10] < 0.04
    # ...while precision separates them completely.
    assert good.precision[10] == 1.0 and bad.precision[10] == 0.0


def test_top_one_relevance_can_hide_terrible_recall() -> None:
    """The failure the question gold set cannot see: rank 1 right, everything else missed."""
    retriever = _StubRetriever({"צמצום": ["A 1"] + [f"noise {i}" for i in range(9)]})
    report = run_lexical_eval(retriever, [CASE], ks=[1, 10])
    assert report.recall[1] == 1 / 3  # a perfect top-1 ...
    assert report.recall[10] == 1 / 3  # ... and still only a third of the discussion
    assert report.precision[10] == 0.1  # ...and 9 of 10 results do not contain the term


def test_report_names_the_worst_terms() -> None:
    retriever = _StubRetriever({"צמצום": ["A 1", "n1", "n2"], "ביטול": ["B 1", "B 2"]})
    good = LexicalCase(term="ביטול", expected_refs=["B 1", "B 2"])
    report = run_lexical_eval(retriever, [CASE, good], ks=[10])
    text = format_lexical_report(report)
    assert "2 terms" in text and "5 known occurrences" in text
    # Worst-precision-first puts the failing term at the top of the list.
    assert text.index("צמצום") < text.index("ביטול")


def test_goldset_round_trips_through_yaml(tmp_path: object) -> None:
    path = f"{tmp_path}/lex.yaml"  # type: ignore[str-bytes-safe]
    original = LexicalGoldset(corpus_chunks=len(CHUNKS), cases=[CASE])
    save_lexical_goldset(original, path)
    loaded = load_lexical_goldset(path)
    assert loaded == original
    # The corpus size is recorded so a stale ground truth is detectable.
    assert loaded.corpus_chunks == 4
