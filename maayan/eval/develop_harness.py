"""Develop eval harness: run a seed gold set through the develop step + report.

Mirrors :mod:`maayan.eval.harness` (retrieval), but measures the *develop* verb:
each gold seed is minted as a `Contribution` (a seed with a directive), developed
under the same default-deny discipline, and scored on

- **develop rate** — of the *supported* seeds, how many produced a grounded
  development (over-refusal hurts this);
- **refusal rate** — of the *unsupported* seeds, how many were correctly refused
  with no forced connection (mirrors the gate rate in the retrieval harness);
- **grounding** — over the developments that were produced, the mean
  :func:`grounding_score` (cited refs that were actually retrieved → catches
  fabricated citations).

Everything is injected — a `Developing` (the real `DevelopmentService` or a fake),
a `ThreadService` (each seed gets its own thread), and a `Clock` for the seed
timestamp — so the unit tests run with no network and no real models.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from maayan.capture.models import Annotation
from maayan.clock import Clock
from maayan.develop.models import Development
from maayan.eval.develop_goldset import DevelopGoldExample
from maayan.eval.develop_metrics import grounding_score
from maayan.threads.service import ThreadService


class Developing(Protocol):
    """The single method the develop harness depends on (DI seam)."""

    def develop(self, seed: Annotation, *, thread_id: str) -> Development:
        ...


@dataclass(frozen=True)
class DevelopReport:
    """Aggregated develop-eval results (every rate: higher is better)."""

    n: int
    n_supported: int
    n_unsupported: int
    n_developed: int  # how many seeds produced a grounded development
    develop_rate: float  # of supported seeds, fraction correctly developed
    refusal_rate: float  # of unsupported seeds, fraction correctly refused
    grounding: float  # mean grounding_score over the developed seeds


def _seed_from(example: DevelopGoldExample, thread_id: str, clock: Clock) -> Annotation:
    """Mint a seed Contribution from a gold example (author is never blank)."""
    return Annotation(
        id=str(uuid.uuid4()),
        session_id=thread_id,
        timestamp=clock.now(),
        author=example.author,
        kind="connection",
        body=example.body,
        directive=example.directive,
        opens_aspect=True,
    )


def run_develop_eval(
    developer: Developing,
    threads: ThreadService,
    clock: Clock,
    examples: Sequence[DevelopGoldExample],
) -> DevelopReport:
    """Develop every gold seed and aggregate the develop-step metrics.

    `threads` must be the SAME thread service the `developer` appends turns to, so a
    per-seed thread exists when the development turn is recorded.
    """
    n_supported = sum(1 for ex in examples if ex.supported)
    n_unsupported = len(examples) - n_supported
    developed_supported = 0
    refused_unsupported = 0
    grounding_sum = 0.0
    n_developed = 0

    for ex in examples:
        thread = threads.start_thread(ex.note or ex.body[:40] or "develop-eval")
        seed = _seed_from(ex, thread.id, clock)
        dev = developer.develop(seed, thread_id=thread.id)
        if dev.grounded:
            n_developed += 1
            grounding_sum += grounding_score(dev.cited_refs, dev.grounded_in)
            if ex.supported:
                developed_supported += 1
        elif not ex.supported:
            refused_unsupported += 1

    return DevelopReport(
        n=len(examples),
        n_supported=n_supported,
        n_unsupported=n_unsupported,
        n_developed=n_developed,
        develop_rate=developed_supported / n_supported if n_supported else 0.0,
        refusal_rate=refused_unsupported / n_unsupported if n_unsupported else 0.0,
        grounding=grounding_sum / n_developed if n_developed else 0.0,
    )


def _rate(value: float, count: int) -> str:
    """Format a rate, or 'n/a' when there are no examples of that kind."""
    return f"{value:.3f}" if count else "  n/a"


def format_develop_report(report: DevelopReport) -> str:
    """Render a develop report as a small table."""
    return "\n".join(
        [
            f"Develop gold set: {report.n} seeds "
            f"({report.n_supported} supported, {report.n_unsupported} unsupported)",
            "",
            "Develop step (higher is better):",
            f"  developed (of supported):   {_rate(report.develop_rate, report.n_supported)}",
            f"  refused   (of unsupported): {_rate(report.refusal_rate, report.n_unsupported)}",
            f"  grounding (cited ⊆ retrieved, over {report.n_developed} developed): "
            f"{_rate(report.grounding, report.n_developed)}",
        ]
    )
