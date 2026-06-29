"""Answer-quality eval harness: run a gold set through `ask` + report.

Mirrors :mod:`maayan.eval.develop_harness`, but measures the *answer* `ask` produces.
Each gold example is asked; then:

- **answer rate** — of *positive* examples, the fraction actually answered
  (`Answer.grounded`); over-refusal hurts it.
- **refusal rate** — of *negative* examples (`should_refuse`), the fraction correctly
  refused — default-deny measured at the answer level (the whole `ask` pipeline).
- **citation precision / recall** — over answered positives, cited refs vs the gold
  `expected_refs` (see :mod:`maayan.eval.answer_metrics`).
- **citation grounding** — over answered positives, fraction of cited refs that were in
  the retrieved sources (catches fabricated citations).
- **faithfulness** — over answered positives, the fraction an independent
  :class:`~maayan.eval.judge.AnswerJudge` deems fully supported.

Everything is injected — an `Asking` (the real `RAGService` or a fake) and an
`AnswerJudge` (the real `LLMJudge` or a fake) — so unit tests run with no network and
no real models.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from maayan.eval.answer_metrics import citation_precision, citation_recall, grounding_score
from maayan.eval.goldset import GoldExample
from maayan.eval.judge import AnswerJudge
from maayan.generate.rag import Answer


class Asking(Protocol):
    """The single method the answer harness depends on (DI seam; `RAGService` satisfies it)."""

    def ask(
        self, question: str, *, k: int | None = None, book: str | None = None,
        source: str | None = None,
    ) -> Answer:
        ...


@dataclass(frozen=True)
class AnswerReport:
    """Aggregated answer-eval results (every rate: higher is better)."""

    n: int
    n_positive: int
    n_negative: int
    n_answered: int  # answered positives (the denominator for the quality means)
    n_judged: int
    answer_rate: float  # of positives, fraction answered
    refusal_rate: float  # of negatives, fraction correctly refused
    citation_precision: float  # mean over answered positives
    citation_recall: float
    citation_grounding: float
    faithfulness: float  # fraction of judged answers deemed fully supported


def run_answer_eval(
    asker: Asking,
    judge: AnswerJudge,
    examples: Sequence[GoldExample],
) -> AnswerReport:
    """Ask every gold question, score the answers, and aggregate the metrics."""
    n_positive = sum(1 for ex in examples if not ex.should_refuse)
    n_negative = len(examples) - n_positive

    answered = 0
    refused_correct = 0
    judged = 0
    prec_sum = rec_sum = ground_sum = faithful_sum = 0.0

    for ex in examples:
        answer = asker.ask(ex.question)
        if ex.should_refuse:
            if not answer.grounded:
                refused_correct += 1
            continue
        # positive
        if not answer.grounded:
            continue  # over-refusal: counts against answer_rate
        answered += 1
        retrieved = [s.ref for s in answer.sources]
        prec_sum += citation_precision(answer.cited_refs, ex.expected_refs)
        rec_sum += citation_recall(answer.cited_refs, ex.expected_refs)
        ground_sum += grounding_score(answer.cited_refs, retrieved)
        verdict = judge.judge(ex.question, answer.text, answer.sources)
        judged += 1
        faithful_sum += 1.0 if verdict.faithful else 0.0

    return AnswerReport(
        n=len(examples),
        n_positive=n_positive,
        n_negative=n_negative,
        n_answered=answered,
        n_judged=judged,
        answer_rate=answered / n_positive if n_positive else 0.0,
        refusal_rate=refused_correct / n_negative if n_negative else 0.0,
        citation_precision=prec_sum / answered if answered else 0.0,
        citation_recall=rec_sum / answered if answered else 0.0,
        citation_grounding=ground_sum / answered if answered else 0.0,
        faithfulness=faithful_sum / judged if judged else 0.0,
    )


def _rate(value: float, count: int) -> str:
    """Format a rate, or 'n/a' when there are no examples of that kind."""
    return f"{value:.3f}" if count else "  n/a"


def format_answer_report(report: AnswerReport) -> str:
    """Render an answer report as a small table."""
    a = report.n_answered
    return "\n".join(
        [
            f"Answer gold set: {report.n} questions "
            f"({report.n_positive} positive, {report.n_negative} negative)",
            "",
            "Gate (higher is better):",
            f"  answered (of positives): {_rate(report.answer_rate, report.n_positive)}",
            f"  refused  (of negatives): {_rate(report.refusal_rate, report.n_negative)}",
            "",
            f"Answer quality (over {a} answered positive(s)):",
            f"  citation precision: {_rate(report.citation_precision, a)}",
            f"  citation recall:    {_rate(report.citation_recall, a)}",
            f"  citation grounding: {_rate(report.citation_grounding, a)}",
            f"  faithfulness (judge): {_rate(report.faithfulness, report.n_judged)}",
        ]
    )
