"""Blinded head-to-head benchmark harness — de-blinding, ablation, aggregation (fakes only)."""

from __future__ import annotations

from typing import Any

from maayan.eval.benchmark import (
    PairwiseVerdict,
    _deblind,
    format_benchmark_report,
    parse_pairwise,
    run_benchmark,
)
from maayan.eval.goldset import GoldExample
from maayan.generate.rag import Answer


class FakeAsker:
    """Arm A stand-in: grounding can differ for text-only (source='sefaria') vs all sources."""

    def __init__(
        self, *, grounded_all: bool = True, grounded_text: bool = True, text: str = "MAAYAN"
    ) -> None:
        self.grounded_all = grounded_all
        self.grounded_text = grounded_text
        self.text = text

    def ask(
        self,
        question: str,
        *,
        k: int | None = None,
        book: str | None = None,
        source: str | None = None,
    ) -> Answer:
        grounded = self.grounded_text if source == "sefaria" else self.grounded_all
        return Answer(
            question=question, text=self.text, grounded=grounded, cited_refs=[], sources=[]
        )


class FakeClosedBook:
    def __init__(self, text: str = "FRONTIER") -> None:
        self.text = text

    def answer(self, question: str) -> str:
        return self.text


class PrefersTextJudge:
    """Picks whichever blinded slot contains `target` — lets us prove de-blinding is correct."""

    def __init__(self, target: str) -> None:
        self.target = target

    def compare(self, question: str, gold: str, answer_a: str, answer_b: str) -> PairwiseVerdict:
        if self.target in answer_a:
            return PairwiseVerdict(winner="A")
        if self.target in answer_b:
            return PairwiseVerdict(winner="B")
        return PairwiseVerdict(winner="tie")


def _ex(q: str, **kw: Any) -> GoldExample:
    return GoldExample(question=q, **kw)


def test_parse_pairwise_reads_winner_and_reason() -> None:
    assert parse_pairwise("REASON: better mekoros\nWINNER: 1").winner == "A"
    assert parse_pairwise("WINNER: 2").winner == "B"
    assert parse_pairwise("WINNER: tie").winner == "tie"
    assert parse_pairwise("no verdict at all").winner == "tie"
    assert parse_pairwise("REASON: x\nWINNER: 1").reason == "x"


def test_deblind_maps_slot_to_identity() -> None:
    assert _deblind("A", True) == "maayan"
    assert _deblind("B", True) == "frontier"
    assert _deblind("A", False) == "frontier"
    assert _deblind("B", False) == "maayan"
    assert _deblind("tie", True) == "tie"


def test_maayan_wins_regardless_of_blind_order() -> None:
    examples = [_ex(f"q{i}", answer="gold", stratum="torah_ohr") for i in range(6)]
    report = run_benchmark(
        FakeAsker(text="MAAYAN"), FakeClosedBook(), PrefersTextJudge("MAAYAN"), examples, seed=1
    )
    assert report.n_graded == 6
    assert report.maayan_win_rate == 1.0
    assert report.frontier_win_rate == 0.0
    assert report.by_stratum["torah_ohr"] == 1.0
    assert format_benchmark_report(report)  # renders without error


def test_frontier_wins_when_judge_prefers_it() -> None:
    report = run_benchmark(
        FakeAsker(text="MAAYAN"),
        FakeClosedBook("FRONTIER"),
        PrefersTextJudge("FRONTIER"),
        [_ex("q", answer="gold", stratum="tanya_control")],
    )
    assert (report.maayan_win_rate, report.frontier_win_rate) == (0.0, 1.0)


def test_negatives_and_goldless_are_not_graded() -> None:
    examples = [
        _ex("neg", should_refuse=True, stratum="negative"),
        _ex("nogold", stratum="torah_ohr"),  # answer=None → skipped
        _ex("q", answer="gold", stratum="torah_ohr"),
    ]
    report = run_benchmark(
        FakeAsker(text="MAAYAN"), FakeClosedBook(), PrefersTextJudge("MAAYAN"), examples
    )
    assert (report.n, report.n_graded, report.maayan_win_rate) == (3, 1, 1.0)


def test_ablation_counts_synthetic_only_coverage() -> None:
    asker = FakeAsker(grounded_all=True, grounded_text=False, text="MAAYAN")
    report = run_benchmark(
        asker, FakeClosedBook(), PrefersTextJudge("MAAYAN"),
        [_ex("q", answer="gold", stratum="cross_text")], ablation=True,
    )
    assert report.ablation_coverage_gain == 1


def test_no_ablation_probe_when_disabled() -> None:
    asker = FakeAsker(grounded_all=True, grounded_text=False)
    report = run_benchmark(
        asker, FakeClosedBook(), PrefersTextJudge("x"),
        [_ex("q", answer="gold")], ablation=False,
    )
    assert report.ablation_coverage_gain == 0


def test_refused_positive_still_graded_and_lowers_answer_rate() -> None:
    asker = FakeAsker(grounded_all=False, grounded_text=False, text="X")
    report = run_benchmark(
        asker, FakeClosedBook("FRONTIER"), PrefersTextJudge("FRONTIER"),
        [_ex("q", answer="gold", stratum="torah_ohr")],
    )
    assert report.n_graded == 1
    assert report.maayan_answer_rate == 0.0
    assert report.maayan_win_rate == 0.0
