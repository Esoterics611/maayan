"""Blinded head-to-head benchmark: grounded maayan (Arm A) vs closed-book frontier (Arm B).

- **Arm A — maayan:** answers only from retrieved, cited passages (the `RAGService`).
  Run twice for the ablation: `+synthetic` (all sources) vs `text-only`
  (`source="sefaria"`, excluding the populated term/connection layer).
- **Arm B — frontier closed-book:** answers the same question from the model's own
  knowledge — no retrieval, no tools.
- **Grader:** a separate frontier model scores the two answers against the expert's
  gold answer, **blinded** — the two are shown as "Answer 1 / Answer 2" in randomized
  order, identities hidden — to defuse self-preference.

Everything is injected (`Asking`, `ClosedBook`, `PairwiseJudge`), so unit tests run
with no network and no real models.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from maayan.config import Settings
from maayan.eval.answer_harness import Asking
from maayan.eval.goldset import GoldExample
from maayan.generate.base import GenerationBackend, Message

Winner = Literal["maayan", "frontier", "tie", "n/a"]
Slot = Literal["A", "B", "tie"]

CLOSED_BOOK_SYSTEM_PROMPT = (
    "Answer the question about Chassidus / Kabbalah from your own knowledge. You have no "
    "external sources and no web access. Be specific and name ma'amarim / mekoros where "
    "you can. If you are not sure, say so plainly rather than inventing a source."
)

PAIRWISE_SYSTEM_PROMPT = (
    "You are an impartial expert grader of answers about Chassidus / Kabbalah. You are "
    "given a QUESTION, a GOLD answer (the reference), and two candidate answers, ANSWER 1 "
    "and ANSWER 2. Decide which candidate is the better answer to the question, judged "
    "against the gold: reward factual accuracy and correct mekoros; penalize invented "
    "citations and unsupported claims. Do not prefer an answer for being longer. Output "
    "exactly two lines:\nREASON: <one short sentence>\nWINNER: 1 | 2 | tie"
)


class ClosedBook(Protocol):
    """Arm B: answer from the model's own knowledge, no retrieval (DI seam)."""

    def answer(self, question: str) -> str: ...


class PairwiseVerdict(BaseModel):
    """A blinded comparison: which SLOT (A=Answer 1, B=Answer 2) is better."""

    winner: Slot
    reason: str = ""


class PairwiseJudge(Protocol):
    """Blinded grader: pick the better of two candidate answers vs the gold (DI seam)."""

    def compare(
        self, question: str, gold: str, answer_a: str, answer_b: str
    ) -> PairwiseVerdict: ...


class BenchmarkRow(BaseModel):
    """One question's outcome (winner already de-blinded to real identities)."""

    question: str
    stratum: str
    maayan_answered: bool
    winner: Winner
    ablation_gain: bool | None = None  # +synthetic answered where text-only refused


class BenchmarkReport(BaseModel):
    """Aggregated head-to-head results."""

    n: int
    n_graded: int
    maayan_win_rate: float
    frontier_win_rate: float
    tie_rate: float
    maayan_answer_rate: float
    ablation_coverage_gain: int
    by_stratum: dict[str, float] = Field(default_factory=dict)
    rows: list[BenchmarkRow] = Field(default_factory=list)


class ClosedBookAnswerer:
    """Arm B implementation: one generation call, no retrieval."""

    def __init__(
        self, backend: GenerationBackend, *, system: str = CLOSED_BOOK_SYSTEM_PROMPT
    ) -> None:
        self._backend = backend
        self._system = system

    def answer(self, question: str) -> str:
        reply = self._backend.generate(self._system, [Message(role="user", content=question)])
        return reply.strip()


class LLMPairwiseJudge:
    """Blinded grader backed by a (ideally frontier) generation model."""

    def __init__(self, backend: GenerationBackend, *, system: str = PAIRWISE_SYSTEM_PROMPT) -> None:
        self._backend = backend
        self._system = system

    def compare(self, question: str, gold: str, answer_a: str, answer_b: str) -> PairwiseVerdict:
        content = (
            f"QUESTION: {question}\n\n"
            f"GOLD ANSWER: {gold}\n\n"
            f"ANSWER 1:\n{answer_a}\n\n"
            f"ANSWER 2:\n{answer_b}"
        )
        reply = self._backend.generate(self._system, [Message(role="user", content=content)])
        return parse_pairwise(reply)


def parse_pairwise(reply: str) -> PairwiseVerdict:
    """Pull WINNER (1 | 2 | tie) and REASON out of the grader's reply, tolerantly."""
    winner: Slot = "tie"
    reason = ""
    for line in reply.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("WINNER"):
            tail = stripped.split(":", 1)[-1].strip().lower()
            if tail.startswith("1"):
                winner = "A"
            elif tail.startswith("2"):
                winner = "B"
            else:
                winner = "tie"
        elif upper.startswith("REASON"):
            reason = stripped.split(":", 1)[-1].strip()
    return PairwiseVerdict(winner=winner, reason=reason)


def _deblind(slot: Slot, maayan_is_first: bool) -> Winner:
    if slot == "tie":
        return "tie"
    maayan_slot: Slot = "A" if maayan_is_first else "B"
    return "maayan" if slot == maayan_slot else "frontier"


def run_benchmark(
    asker: Asking,
    closed_book: ClosedBook,
    judge: PairwiseJudge,
    examples: Sequence[GoldExample],
    *,
    seed: int = 0,
    ablation: bool = True,
) -> BenchmarkReport:
    """Run every gradable question through both arms + a blinded grader; aggregate."""
    rng = random.Random(seed)
    rows: list[BenchmarkRow] = []
    for ex in examples:
        stratum = ex.stratum or "unspecified"
        arm_a = asker.ask(ex.question)  # +synthetic: all sources
        ablation_gain: bool | None = None
        if ablation:
            arm_a_text = asker.ask(ex.question, source="sefaria")  # text-only
            ablation_gain = arm_a.grounded and not arm_a_text.grounded

        # Negatives and gold-less questions are not graded head-to-head.
        if ex.should_refuse or ex.answer is None:
            rows.append(
                BenchmarkRow(
                    question=ex.question, stratum=stratum,
                    maayan_answered=arm_a.grounded, winner="n/a", ablation_gain=ablation_gain,
                )
            )
            continue

        maayan_text = arm_a.text if arm_a.grounded else "(no grounded answer — refused)"
        frontier_text = closed_book.answer(ex.question)
        maayan_is_first = rng.random() < 0.5
        first, second = (
            (maayan_text, frontier_text) if maayan_is_first else (frontier_text, maayan_text)
        )
        verdict = judge.compare(ex.question, ex.answer, first, second)
        rows.append(
            BenchmarkRow(
                question=ex.question, stratum=stratum, maayan_answered=arm_a.grounded,
                winner=_deblind(verdict.winner, maayan_is_first), ablation_gain=ablation_gain,
            )
        )
    return _aggregate(rows)


def _aggregate(rows: list[BenchmarkRow]) -> BenchmarkReport:
    graded = [r for r in rows if r.winner != "n/a"]
    n_graded = len(graded)
    wins = sum(1 for r in graded if r.winner == "maayan")
    losses = sum(1 for r in graded if r.winner == "frontier")
    ties = sum(1 for r in graded if r.winner == "tie")

    by_stratum: dict[str, float] = {}
    strata = {r.stratum for r in graded}
    for s in sorted(strata):
        sub = [r for r in graded if r.stratum == s]
        by_stratum[s] = sum(1 for r in sub if r.winner == "maayan") / len(sub) if sub else 0.0

    return BenchmarkReport(
        n=len(rows),
        n_graded=n_graded,
        maayan_win_rate=wins / n_graded if n_graded else 0.0,
        frontier_win_rate=losses / n_graded if n_graded else 0.0,
        tie_rate=ties / n_graded if n_graded else 0.0,
        maayan_answer_rate=(sum(1 for r in graded if r.maayan_answered) / n_graded)
        if n_graded
        else 0.0,
        ablation_coverage_gain=sum(1 for r in rows if r.ablation_gain),
        by_stratum=by_stratum,
        rows=rows,
    )


def format_benchmark_report(report: BenchmarkReport) -> str:
    """Render the head-to-head report as a small table."""
    lines = [
        f"Benchmark: {report.n} questions ({report.n_graded} graded head-to-head)",
        "",
        "Blinded win-rate (maayan vs frontier closed-book):",
        f"  maayan wins:   {report.maayan_win_rate:.3f}",
        f"  frontier wins: {report.frontier_win_rate:.3f}",
        f"  ties:          {report.tie_rate:.3f}",
        "",
        f"maayan answered (of graded): {report.maayan_answer_rate:.3f}",
        f"ablation coverage gain (+synthetic answered where text-only refused): "
        f"{report.ablation_coverage_gain}",
    ]
    if report.by_stratum:
        lines.append("")
        lines.append("maayan win-rate by stratum:")
        lines.extend(f"  {s}: {rate:.3f}" for s, rate in report.by_stratum.items())
    return "\n".join(lines)


def _swap_model(settings: Settings, model: str) -> Settings:
    field = "ollama_model" if settings.generation_backend == "ollama" else "openrouter_model"
    return settings.model_copy(update={field: model})


def build_closed_book(settings: Settings) -> ClosedBookAnswerer:
    """Arm B: a generation backend on the configured closed-book model (default: gen model)."""
    from maayan.generate.factory import build_generation_backend

    model = settings.bench_closed_book_model or settings.generation_model
    return ClosedBookAnswerer(build_generation_backend(_swap_model(settings, model)))


def build_pairwise_judge(settings: Settings) -> LLMPairwiseJudge:
    """The blinded grader on the configured judge model (default: eval judge, else gen model)."""
    from maayan.generate.factory import build_generation_backend

    model = settings.bench_judge_model or settings.eval_judge_model or settings.generation_model
    return LLMPairwiseJudge(build_generation_backend(_swap_model(settings, model)))
