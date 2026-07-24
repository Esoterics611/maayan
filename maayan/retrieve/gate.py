"""The default-deny gate: which signal decides "answer or refuse", and at what level.

The gate was one line — top dense cosine vs `score_threshold` — and measurement showed
that line cannot do the job. On the live corpus bge-m3 cosine occupies a narrow band
(roughly 0.37-0.65 for everything), so a single absolute cutoff sits inside the noise:
at the shipped 0.45, five of twelve blatantly off-topic queries ("explain the theory of
general relativity", "מה שלומך היום") cleared the gate, because over ~9k passages the
maximum cosine is a max over noise and there is always *something* at 0.43+.

Two changes follow from that, both measured rather than assumed:

*Pool, don't peak.* The mean cosine over the top-N is a far lower-variance estimate of
"how much relevant material is actually here" than the single best hit.

*Use the lexical branch too.* R2's stated failure — a strong exact-term match refused
for mediocre cosine — is real, and the sparse branch is the only signal that sees it.
Sparse scores live on a different scale, so they enter through a configured weight.

Gates are pure functions of `GateSignals`, injected into `Retriever`, and carry their
own threshold — the two are a matched pair and must never be mixed across scales.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from maayan.retrieve.models import GateSignals


class GateDecision(BaseModel):
    """What the gate concluded, and from what — the whole basis of a refusal."""

    signal: str  # which signal produced `relevance`
    relevance: float
    threshold: float
    answered: bool

    @property
    def margin(self) -> float:
        """How far above (or below) the line — useful for spotting borderline calls."""
        return self.relevance - self.threshold


@runtime_checkable
class RelevanceGate(Protocol):
    """Turns retrieval signals into the answer/refuse decision (DI seam)."""

    @property
    def threshold(self) -> float:
        """The level `relevance` is compared against. Scale depends on the gate."""
        ...

    def relevance(self, signals: GateSignals) -> float:
        """The absolute relevance score this gate judges on."""
        ...

    def evaluate(self, signals: GateSignals) -> GateDecision:
        ...


class DenseTopGate:
    """The original gate: top dense cosine vs a threshold.

    Kept as the compatibility path (`GATE_SIGNAL=dense_top`) so an existing tuned
    `SCORE_THRESHOLD` keeps meaning exactly what it used to.
    """

    name = "dense_top"

    def __init__(self, threshold: float) -> None:
        self._threshold = threshold

    @property
    def threshold(self) -> float:
        return self._threshold

    def relevance(self, signals: GateSignals) -> float:
        # A cross-encoder score, when one was computed, is far more discriminative
        # than bi-encoder cosine — so it wins, as it always did here.
        if signals.rerank_top is not None:
            return signals.rerank_top
        return signals.dense_top

    def evaluate(self, signals: GateSignals) -> GateDecision:
        score = self.relevance(signals)
        name = "rerank_top" if signals.rerank_top is not None else self.name
        return GateDecision(
            signal=name, relevance=score, threshold=self._threshold,
            answered=score >= self._threshold,
        )


class HybridPoolGate:
    """Pooled dense cosine plus weighted pooled sparse: `dense_mean + w * sparse_mean`.

    Both terms are means over the top-`gate_pool` hits of their branch. The weight
    puts the sparse term (which sits around 0.05-0.15) on a comparable footing with
    cosine (0.40-0.65); it is configured, not baked in, because it depends on the
    corpus and the embedding model.

    The threshold is NOT on the cosine scale — it belongs to this gate and is carried
    with it, so swapping gates can never silently reuse the other one's number.
    """

    name = "hybrid_pool"

    def __init__(self, threshold: float, *, sparse_weight: float) -> None:
        self._threshold = threshold
        self._sparse_weight = sparse_weight

    @property
    def threshold(self) -> float:
        return self._threshold

    def relevance(self, signals: GateSignals) -> float:
        if signals.rerank_top is not None:
            return signals.rerank_top
        return signals.dense_mean + self._sparse_weight * signals.sparse_mean

    def evaluate(self, signals: GateSignals) -> GateDecision:
        score = self.relevance(signals)
        name = "rerank_top" if signals.rerank_top is not None else self.name
        return GateDecision(
            signal=name, relevance=score, threshold=self._threshold,
            answered=score >= self._threshold,
        )


def build_gate(
    gate_signal: str,
    *,
    score_threshold: float,
    hybrid_threshold: float,
    sparse_weight: float,
) -> RelevanceGate:
    """Construct the configured gate. Each gate carries the threshold that fits its scale."""
    if gate_signal == "hybrid_pool":
        return HybridPoolGate(hybrid_threshold, sparse_weight=sparse_weight)
    if gate_signal == "dense_top":
        return DenseTopGate(score_threshold)
    raise ValueError(f"Unknown gate_signal: {gate_signal!r}")
