"""Tests for the eval harness — metrics (hand-checked), gold-set loading, aggregation.

No network and no real models: the harness is exercised with a fake retriever
that returns a fixed ref order per question.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from maayan.eval.goldset import GoldExample, load_goldset
from maayan.eval.harness import EvalReport, format_comparison, format_report, run_eval
from maayan.eval.metrics import hit_at_k, mrr, recall_at_k, ref_matches
from maayan.retrieve.models import RetrievalResult, SearchResult


# -- metrics: prefix-aware ref matching ---------------------------------------
def test_ref_matches_exact_and_chapter_prefix() -> None:
    assert ref_matches("Tanya 1", "Tanya 1")  # exact
    assert ref_matches("Tanya 1", "Tanya 1:13")  # segment within chapter
    assert not ref_matches("Tanya 1", "Tanya 13")  # not a prefix segment
    assert not ref_matches("Tanya 1", "Tanya 10")  # "1" must be followed by ":"
    assert not ref_matches("Tanya 1:13", "Tanya 1")  # narrower expected, broader retrieved


# -- metrics: hit@k / recall@k / mrr on tiny hand-checked inputs ---------------
RETRIEVED = ["B", "A", "C", "D"]  # A is at rank 2


def test_hit_at_k() -> None:
    assert hit_at_k(RETRIEVED, ["A"], k=1) == 0.0  # A is rank 2, not in top-1
    assert hit_at_k(RETRIEVED, ["A"], k=2) == 1.0
    assert hit_at_k(RETRIEVED, ["Z"], k=4) == 0.0  # absent
    assert hit_at_k(RETRIEVED, [], k=4) == 0.0  # no expected refs → 0


def test_recall_at_k_counts_each_expected_once() -> None:
    # Two expected, one (A) in top-2 → recall 0.5; both in top-3 → 1.0.
    assert recall_at_k(RETRIEVED, ["A", "C"], k=2) == pytest.approx(0.5)
    assert recall_at_k(RETRIEVED, ["A", "C"], k=3) == pytest.approx(1.0)
    assert recall_at_k(RETRIEVED, ["A", "Z"], k=4) == pytest.approx(0.5)


def test_recall_chapter_ref_not_double_counted() -> None:
    # Two segments of the same chapter retrieved; one chapter-level expected ref → 1.0, not 2.0.
    retrieved = ["Tanya 1:1", "Tanya 1:2", "Tanya 2:1"]
    assert recall_at_k(retrieved, ["Tanya 1"], k=3) == pytest.approx(1.0)


def test_mrr_is_reciprocal_of_first_hit_rank() -> None:
    assert mrr(RETRIEVED, ["A"]) == pytest.approx(0.5)  # first hit at rank 2
    assert mrr(RETRIEVED, ["B"]) == pytest.approx(1.0)  # rank 1
    assert mrr(RETRIEVED, ["Z"]) == 0.0  # no hit
    assert mrr(RETRIEVED, ["C", "B"]) == pytest.approx(1.0)  # earliest of any expected


# -- gold-set loading ----------------------------------------------------------
def test_load_goldset_yaml(tmp_path: Path) -> None:
    p = tmp_path / "gold.yaml"
    p.write_text(
        'examples:\n  - question: "q1"\n    expected_refs: ["A", "B"]\n'
        '  - question: "q2"\n    expected_refs: ["C"]\n    note: "n"\n',
        encoding="utf-8",
    )
    examples = load_goldset(str(p))
    assert [e.question for e in examples] == ["q1", "q2"]
    assert examples[0].expected_refs == ["A", "B"]
    assert examples[1].note == "n"


def test_load_goldset_json_bare_list(tmp_path: Path) -> None:
    p = tmp_path / "gold.json"
    p.write_text(json.dumps([{"question": "q", "expected_refs": ["A"]}]), encoding="utf-8")
    examples = load_goldset(str(p))
    assert examples == [GoldExample(question="q", expected_refs=["A"])]


def test_shipped_goldset_is_well_formed() -> None:
    """Guard the real eval/goldset.yaml in CI (no model needed) so a typo there
    can't ship green — the unit tests above only exercise synthetic gold."""
    path = Path(__file__).resolve().parents[1] / "eval" / "goldset.yaml"
    examples = load_goldset(str(path))
    positives = [e for e in examples if not e.should_refuse]
    negatives = [e for e in examples if e.should_refuse]
    assert len(positives) >= 30, "want a broad positive gold set"
    assert len(negatives) >= 5, "want some refusal cases to measure default-deny"
    for e in positives:
        assert e.expected_refs, f"positive without refs: {e.question!r}"
        assert all(r.startswith("Tanya, Part I; Likkutei Amarim ") for r in e.expected_refs), (
            f"unexpected ref format in {e.question!r}: {e.expected_refs}"
        )
    for e in negatives:
        assert not e.expected_refs, f"negative should have no refs: {e.question!r}"


# -- harness aggregation (fake retriever, no network) --------------------------
class _FakeRetriever:
    """Returns fixed refs per question; relevance defaults to the top score but can
    be pinned per question to exercise the default-deny gate."""

    def __init__(
        self,
        answers: dict[str, list[str]],
        relevance: dict[str, float] | None = None,
    ) -> None:
        self._answers = answers
        self._relevance = relevance or {}

    def retrieve(
        self,
        query: str,
        *,
        k: int | None = None,
        book: str | None = None,
        source: str | None = None,
    ) -> RetrievalResult:
        refs = self._answers.get(query, [])
        results = [
            SearchResult(
                ref=r, text="", score=1.0 - i * 0.1, lang="he", source="sefaria", payload={}
            )
            for i, r in enumerate(refs)
        ]
        top = results[0].score if results else 0.0
        return RetrievalResult(results=results, relevance=self._relevance.get(query, top))


def test_run_eval_aggregates_across_questions() -> None:
    retriever = _FakeRetriever(
        {
            "q1": ["A", "X", "Y"],  # expected A at rank 1 → perfect
            "q2": ["X", "B", "Y"],  # expected B at rank 2
        }
    )
    examples = [
        GoldExample(question="q1", expected_refs=["A"]),
        GoldExample(question="q2", expected_refs=["B"]),
    ]
    report = run_eval(retriever, examples, ks=[1, 3], score_threshold=0.4)

    assert report.n == 2
    assert report.n_positive == 2
    assert report.n_negative == 0
    assert report.hit[1] == pytest.approx(0.5)  # only q1 hits at k=1
    assert report.hit[3] == pytest.approx(1.0)  # both hit by k=3
    assert report.recall[3] == pytest.approx(1.0)
    assert report.mrr == pytest.approx((1.0 + 0.5) / 2)  # ranks 1 and 2
    assert report.answer_rate == pytest.approx(1.0)  # both positives clear the gate
    assert report.refusal_rate == pytest.approx(0.0)  # no negatives → 0.0


def test_run_eval_negatives_excluded_and_gate_rates() -> None:
    # One good positive (answered), one low-relevance negative (correctly refused),
    # one high-relevance negative (wrongly answered → drags refusal_rate to 0.5).
    retriever = _FakeRetriever(
        answers={"good": ["A"], "junk": ["Z"], "tricky": ["W"]},
        relevance={"good": 0.9, "junk": 0.1, "tricky": 0.8},
    )
    examples = [
        GoldExample(question="good", expected_refs=["A"]),
        GoldExample(question="junk", should_refuse=True),
        GoldExample(question="tricky", should_refuse=True),
    ]
    report = run_eval(retriever, examples, ks=[1], score_threshold=0.4)

    assert report.n == 3
    assert report.n_positive == 1 and report.n_negative == 2
    # Ranking metrics are over the single positive only — negatives don't dilute them.
    assert report.hit[1] == pytest.approx(1.0)
    assert report.mrr == pytest.approx(1.0)
    assert report.answer_rate == pytest.approx(1.0)  # the positive cleared the gate
    assert report.refusal_rate == pytest.approx(0.5)  # only "junk" fell below threshold


def test_format_report_and_comparison_render_numbers() -> None:
    report = EvalReport(
        variant="hybrid",
        n=3,
        ks=[1, 5],
        hit={1: 0.667, 5: 1.0},
        recall={1: 0.5, 5: 0.9},
        mrr=0.75,
        n_positive=2,
        n_negative=1,
        answer_rate=1.0,
        refusal_rate=0.5,
    )
    text = format_report(report)
    assert "Gold set: 3 questions (2 positive, 1 negative)" in text
    assert "MRR: 0.750" in text
    assert "refused  (of negatives): 0.500" in text

    table = format_comparison([report], k=5)
    assert "hybrid" in table
    assert "1.000" in table  # hit@5
    assert "refus" in table  # gate column present
