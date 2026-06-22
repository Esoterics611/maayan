"""Evaluation harness: run a gold set through the Retriever and report metrics.

Computes hit@k / recall@k / MRR, and can compare configurable variants (hybrid vs
dense-only, rerank on/off, top-k, embedding model) side by side — so model and
chunking choices are justified with numbers, not vibes.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from pydantic import BaseModel

from maayan.config import Settings
from maayan.embed.base import Embedder
from maayan.embed.factory import build_embedder
from maayan.eval.goldset import GoldExample
from maayan.eval.metrics import hit_at_k, mrr, recall_at_k
from maayan.retrieve.factory import build_retriever
from maayan.retrieve.retriever import Retrieving


@dataclass(frozen=True)
class EvalReport:
    """Aggregated eval results.

    Retrieval metrics (`hit`/`recall`/`mrr`) are computed over POSITIVE examples
    only. The default-deny gate is summarized by two rates against `score_threshold`
    (both want to be high): `answer_rate` = fraction of positives the gate would
    answer (relevance ≥ threshold; over-refusal hurts it), and `refusal_rate` =
    fraction of negatives it would refuse (relevance < threshold).
    """

    variant: str
    n: int
    ks: list[int]
    hit: dict[int, float]
    recall: dict[int, float]
    mrr: float
    n_positive: int = 0
    n_negative: int = 0
    answer_rate: float = 0.0
    refusal_rate: float = 0.0


def run_eval(
    retriever: Retrieving,
    examples: list[GoldExample],
    ks: list[int],
    *,
    score_threshold: float,
) -> EvalReport:
    """Run every gold question through the retriever and aggregate metrics.

    Positives drive the ranking metrics; negatives (and positives) drive the gate
    rates. `score_threshold` mirrors the RAG default-deny gate (relevance < it →
    refuse), so the eval measures the same decision the system makes at answer time.
    """
    positives = [ex for ex in examples if not ex.should_refuse]
    negatives = [ex for ex in examples if ex.should_refuse]
    max_k = max(ks)
    hit_sum = {k: 0.0 for k in ks}
    recall_sum = {k: 0.0 for k in ks}
    mrr_sum = 0.0
    answered = 0
    for ex in positives:
        result = retriever.retrieve(ex.question, k=max_k)
        retrieved = [r.ref for r in result.results]
        for k in ks:
            hit_sum[k] += hit_at_k(retrieved, ex.expected_refs, k)
            recall_sum[k] += recall_at_k(retrieved, ex.expected_refs, k)
        mrr_sum += mrr(retrieved, ex.expected_refs)
        if result.relevance >= score_threshold:
            answered += 1
    refused = sum(
        1
        for ex in negatives
        if retriever.retrieve(ex.question, k=max_k).relevance < score_threshold
    )
    np_ = len(positives)
    denom = np_ or 1
    return EvalReport(
        variant="default",
        n=len(examples),
        ks=ks,
        hit={k: hit_sum[k] / denom for k in ks},
        recall={k: recall_sum[k] / denom for k in ks},
        mrr=mrr_sum / denom,
        n_positive=np_,
        n_negative=len(negatives),
        answer_rate=answered / np_ if np_ else 0.0,
        refusal_rate=refused / len(negatives) if negatives else 0.0,
    )


def _rate(value: float, count: int) -> str:
    """Format a gate rate, or 'n/a' when there are no examples of that kind."""
    return f"{value:.3f}" if count else "  n/a"


def format_report(report: EvalReport) -> str:
    """Render a single report as a small table."""
    lines = [
        f"Gold set: {report.n} questions "
        f"({report.n_positive} positive, {report.n_negative} negative)",
        "",
    ]
    header = f"{'k':>4} | {'hit@k':>7} | {'recall@k':>9}"
    lines.append(header)
    lines.append("-" * len(header))
    for k in report.ks:
        lines.append(f"{k:>4} | {report.hit[k]:>7.3f} | {report.recall[k]:>9.3f}")
    lines.append("")
    lines.append(f"MRR: {report.mrr:.3f}")
    lines.append("")
    lines.append("Default-deny gate (higher is better):")
    lines.append(f"  answered (of positives): {_rate(report.answer_rate, report.n_positive)}")
    lines.append(f"  refused  (of negatives): {_rate(report.refusal_rate, report.n_negative)}")
    return "\n".join(lines)


class VariantConfig(BaseModel):
    """One retrieval configuration to evaluate."""

    name: str
    hybrid: bool = True
    rerank: bool = False
    top_k: int = 10
    embed_backend: str | None = None
    embed_model: str | None = None


def run_comparison(
    settings: Settings,
    variants: list[VariantConfig],
    examples: list[GoldExample],
    ks: list[int],
    *,
    score_threshold: float,
    embedder: Embedder | None = None,
) -> list[EvalReport]:
    """Evaluate several variants on the same gold set. Reuses one embedder when possible."""
    base_embedder = embedder or build_embedder(settings)
    reports: list[EvalReport] = []
    for v in variants:
        overrides: dict[str, object] = {}
        if v.embed_backend is not None:
            overrides["embed_backend"] = v.embed_backend
        if v.embed_model is not None:
            overrides["embed_model"] = v.embed_model
        # Reuse the shared embedder unless this variant changes the embedding model.
        if overrides:
            variant_settings = settings.model_copy(update=overrides)
            retriever = build_retriever(
                variant_settings, hybrid=v.hybrid, rerank=v.rerank, top_k=v.top_k
            )
        else:
            retriever = build_retriever(
                settings, embedder=base_embedder, hybrid=v.hybrid, rerank=v.rerank, top_k=v.top_k
            )
        report = run_eval(retriever, examples, ks, score_threshold=score_threshold)
        reports.append(replace(report, variant=v.name))
    return reports


def format_comparison(reports: list[EvalReport], k: int) -> str:
    """Render variants side by side at a chosen k (incl. the default-deny gate rates)."""
    name_w = max((len(r.variant) for r in reports), default=7)
    header = (
        f"{'variant':<{name_w}} | {f'hit@{k}':>7} | {f'recall@{k}':>9} | "
        f"{'MRR':>6} | {'answ':>5} | {'refus':>5}"
    )
    lines = [header, "-" * len(header)]
    for r in reports:
        lines.append(
            f"{r.variant:<{name_w}} | {r.hit.get(k, 0.0):>7.3f} | "
            f"{r.recall.get(k, 0.0):>9.3f} | {r.mrr:>6.3f} | "
            f"{_rate(r.answer_rate, r.n_positive):>5} | {_rate(r.refusal_rate, r.n_negative):>5}"
        )
    return "\n".join(lines)


def default_variants() -> list[VariantConfig]:
    """Variants that need no extra downloads (same bge-m3 embedder)."""
    return [
        VariantConfig(name="hybrid k=10", hybrid=True, top_k=10),
        VariantConfig(name="hybrid k=5", hybrid=True, top_k=5),
        VariantConfig(name="dense-only k=10", hybrid=False, top_k=10),
    ]
