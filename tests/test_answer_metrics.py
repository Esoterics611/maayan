"""Tests for answer-quality metrics (pure; no models)."""

from __future__ import annotations

from maayan.eval.answer_metrics import citation_precision, citation_recall, grounding_score

CH1 = "Tanya, Part I; Likkutei Amarim 1"
CH2 = "Tanya, Part I; Likkutei Amarim 2"
SEG1 = "Tanya, Part I; Likkutei Amarim 1:13"  # a segment within chapter 1


def test_precision_perfect_and_prefix_aware() -> None:
    # A segment-level citation matches a chapter-level gold ref (prefix match).
    assert citation_precision([SEG1, CH2], [CH1, CH2]) == 1.0


def test_precision_penalizes_wrong_citation() -> None:
    # One of two citations isn't in the gold set.
    assert citation_precision([CH1, "Tanya, Part I; Likkutei Amarim 9"], [CH1]) == 0.5


def test_precision_vacuous_when_nothing_cited() -> None:
    assert citation_precision([], [CH1]) == 1.0


def test_recall_counts_expected_found() -> None:
    assert citation_recall([CH1], [CH1, CH2]) == 0.5         # cited 1 of 2 expected
    assert citation_recall([SEG1, CH2], [CH1, CH2]) == 1.0   # both, prefix-aware


def test_recall_vacuous_when_nothing_expected() -> None:
    assert citation_recall([CH1], []) == 1.0


def test_grounding_reexported_catches_fabrication() -> None:
    # cited ⊆ retrieved → 1.0; a cited ref never retrieved drags it down.
    assert grounding_score([CH1], [CH1, CH2]) == 1.0
    assert grounding_score([CH1, "Ghost 1"], [CH1]) == 0.5
