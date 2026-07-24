"""Tests for the default-deny gate (R2). Pure functions of signals — no index, no models.

The measured failure being fixed: with the shipped `dense_top >= 0.45`, five of twelve
blatantly off-topic queries cleared the gate, because over ~9k passages the single top
cosine is a max over noise and something always scores 0.43+.
"""

from __future__ import annotations

import pytest

from maayan.config import Settings
from maayan.retrieve.gate import DenseTopGate, HybridPoolGate, build_gate
from maayan.retrieve.models import GateSignals

# Real signal shapes measured on the live corpus (folded index).
ON_TOPIC = GateSignals(
    dense_top=0.620, dense_mean=0.572, sparse_top=0.132, sparse_mean=0.123, pool=10
)
OFF_TOPIC = GateSignals(  # "explain the theory of general relativity"
    dense_top=0.500, dense_mean=0.462, sparse_top=0.048, sparse_mean=0.041, pool=10
)
# A query whose wording barely matches semantically but hits the exact term hard.
LEXICAL_MATCH = GateSignals(
    dense_top=0.470, dense_mean=0.440, sparse_top=0.190, sparse_mean=0.175, pool=10
)


def test_dense_top_gate_reproduces_the_original_behavior() -> None:
    gate = DenseTopGate(0.45)
    assert gate.relevance(ON_TOPIC) == ON_TOPIC.dense_top
    assert gate.evaluate(ON_TOPIC).answered
    assert gate.evaluate(GateSignals(dense_top=0.40)).answered is False


def test_dense_top_at_the_shipped_threshold_lets_off_topic_through() -> None:
    """The defect, pinned: an off-topic query clears `dense_top >= 0.45`."""
    assert DenseTopGate(0.45).evaluate(OFF_TOPIC).answered is True


def test_hybrid_pool_gate_refuses_that_same_off_topic_query() -> None:
    gate = HybridPoolGate(0.795, sparse_weight=3.0)
    assert gate.evaluate(OFF_TOPIC).answered is False
    assert gate.evaluate(ON_TOPIC).answered is True


def test_hybrid_gate_lets_a_strong_lexical_match_carry_a_mediocre_cosine() -> None:
    """R2's stated failure mode: exact-term match refused for middling cosine."""
    # Cosine alone would refuse it at any threshold that also refuses OFF_TOPIC...
    assert LEXICAL_MATCH.dense_top < OFF_TOPIC.dense_top
    assert DenseTopGate(0.50).evaluate(LEXICAL_MATCH).answered is False
    # ...but the lexical branch, which sees the term match, carries it over the line.
    gate = HybridPoolGate(0.795, sparse_weight=3.0)
    assert gate.evaluate(LEXICAL_MATCH).answered is True
    assert gate.evaluate(OFF_TOPIC).answered is False


def test_sparse_weight_is_what_puts_the_branches_on_comparable_footing() -> None:
    signals = GateSignals(dense_mean=0.50, sparse_mean=0.10)
    assert HybridPoolGate(0.0, sparse_weight=0.0).relevance(signals) == pytest.approx(0.50)
    assert HybridPoolGate(0.0, sparse_weight=3.0).relevance(signals) == pytest.approx(0.80)


def test_a_reranker_score_overrides_either_gate() -> None:
    signals = ON_TOPIC.model_copy(update={"rerank_top": 0.91})
    for gate in (DenseTopGate(0.45), HybridPoolGate(0.795, sparse_weight=3.0)):
        decision = gate.evaluate(signals)
        assert decision.signal == "rerank_top"
        assert decision.relevance == 0.91


def test_decision_carries_the_threshold_it_was_judged_against() -> None:
    decision = HybridPoolGate(0.795, sparse_weight=3.0).evaluate(OFF_TOPIC)
    assert decision.threshold == 0.795
    assert decision.margin == pytest.approx(decision.relevance - 0.795)
    assert decision.margin < 0


def test_build_gate_selects_by_name_and_rejects_unknowns() -> None:
    args = {"score_threshold": 0.45, "hybrid_threshold": 0.795, "sparse_weight": 3.0}
    assert isinstance(build_gate("dense_top", **args), DenseTopGate)  # type: ignore[arg-type]
    assert isinstance(build_gate("hybrid_pool", **args), HybridPoolGate)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Unknown gate_signal"):
        build_gate("magic", **args)  # type: ignore[arg-type]


def test_effective_threshold_follows_the_gate_so_scales_are_never_crossed() -> None:
    """Each gate's threshold is its own; reusing the other's would disable the gate."""
    hybrid = Settings(gate_signal="hybrid_pool", score_threshold=0.45, gate_hybrid_threshold=0.795)
    assert hybrid.effective_score_threshold == 0.795

    dense = Settings(gate_signal="dense_top", score_threshold=0.45, gate_hybrid_threshold=0.795)
    assert dense.effective_score_threshold == 0.45
