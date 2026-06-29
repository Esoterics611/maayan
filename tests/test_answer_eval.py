"""Tests for the answer-quality harness (asker + judge mocked; no network)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from maayan.eval.answer_harness import run_answer_eval
from maayan.eval.goldset import GoldExample
from maayan.eval.judge import Judgment
from maayan.generate.rag import Answer
from maayan.retrieve.models import SearchResult

CH1 = "Tanya, Part I; Likkutei Amarim 1"
SEG1 = "Tanya, Part I; Likkutei Amarim 1:13"
WRONG = "Tanya, Part I; Likkutei Amarim 9"


def _src(ref: str) -> SearchResult:
    return SearchResult(ref=ref, text="t", score=0.5, lang="he", source="sefaria", payload={})


def _answer(
    question: str, *, grounded: bool, cited: list[str], retrieved: list[str], text: str
) -> Answer:
    return Answer(
        question=question, text=text, grounded=grounded,
        cited_refs=cited, sources=[_src(r) for r in retrieved],
    )


class FakeAsker:
    """Returns a canned Answer per question."""

    def __init__(self, answers: dict[str, Answer]) -> None:
        self._answers = answers

    def ask(self, question: str, *, k=None, book=None, source=None) -> Answer:
        return self._answers[question]


class FakeJudge:
    """Faithful unless the answer text contains 'BAD'."""

    def judge(self, question: str, answer_text: str, sources: Sequence[SearchResult]) -> Judgment:
        bad = "BAD" in answer_text
        return Judgment(faithful=not bad, unsupported_claims=["x"] if bad else [])


def _setup() -> tuple[FakeAsker, list[GoldExample]]:
    answers = {
        "neg": _answer("neg", grounded=False, cited=[], retrieved=[], text="refused"),
        "pos_good": _answer(
            "pos_good", grounded=True, cited=[SEG1], retrieved=[SEG1], text="good [S1]"
        ),
        "pos_wrongcite": _answer(
            "pos_wrongcite", grounded=True, cited=[WRONG], retrieved=[WRONG], text="cite [S1]"
        ),
        "pos_unfaithful": _answer(
            "pos_unfaithful", grounded=True, cited=[CH1], retrieved=[CH1], text="BAD [S1]"
        ),
        "pos_refused": _answer(
            "pos_refused", grounded=False, cited=[], retrieved=[], text="refused"
        ),
    }
    examples = [
        GoldExample(question="neg", should_refuse=True),
        GoldExample(question="pos_good", expected_refs=[CH1]),
        GoldExample(question="pos_wrongcite", expected_refs=[CH1]),
        GoldExample(question="pos_unfaithful", expected_refs=[CH1]),
        GoldExample(question="pos_refused", expected_refs=[CH1]),
    ]
    return FakeAsker(answers), examples


def test_report_aggregates_every_metric() -> None:
    asker, examples = _setup()
    r = run_answer_eval(asker, FakeJudge(), examples)

    assert (r.n, r.n_positive, r.n_negative) == (5, 4, 1)
    assert r.n_answered == 3 and r.n_judged == 3        # pos_refused not answered
    assert r.answer_rate == 0.75                        # 3 of 4 positives answered
    assert r.refusal_rate == 1.0                        # the one negative refused
    # precision/recall: good=1, wrongcite=0, unfaithful=1 → mean 2/3
    assert r.citation_precision == pytest.approx(2 / 3)
    assert r.citation_recall == pytest.approx(2 / 3)
    assert r.citation_grounding == 1.0                  # all cited refs were retrieved
    # faithfulness: good + wrongcite faithful, unfaithful not → 2/3
    assert r.faithfulness == pytest.approx(2 / 3)


def test_all_refused_positives_zero_answer_rate() -> None:
    asker = FakeAsker({"p": _answer("p", grounded=False, cited=[], retrieved=[], text="refused")})
    r = run_answer_eval(asker, FakeJudge(), [GoldExample(question="p", expected_refs=[CH1])])
    assert r.answer_rate == 0.0 and r.n_answered == 0
    assert r.faithfulness == 0.0  # nothing judged → vacuous 0


def test_format_report_smoke() -> None:
    from maayan.eval.answer_harness import format_answer_report

    asker, examples = _setup()
    out = format_answer_report(run_answer_eval(asker, FakeJudge(), examples))
    assert "faithfulness (judge)" in out and "answered (of positives)" in out
