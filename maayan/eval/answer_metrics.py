"""Metrics for the answer step. Pure, hand-checkable functions.

These score the *answer* `ask` produces, orthogonally to retrieval ranking:

- **citation precision** — of the refs an answer *cites*, the fraction that match a
  gold expected ref. Caveat: gold sets are not exhaustive, so a correct citation to a
  source the gold simply didn't list counts against precision — read it as a soft
  signal, with recall as the firmer number.
- **citation recall** — of the gold expected refs, the fraction the answer actually
  cited ("did it cite the key mekoros?").
- **citation grounding** — handled by :func:`maayan.eval.develop_metrics.grounding_score`
  (fraction of cited refs that were in the retrieved set); re-exported here so the
  answer harness has one import site.

Ref matching is the same prefix-aware match the retrieval metrics use
(:func:`maayan.eval.metrics.ref_matches`), so a chapter-level gold ref matches any
segment cited within it.
"""

from __future__ import annotations

from collections.abc import Sequence

from maayan.eval.develop_metrics import grounding_score as grounding_score
from maayan.eval.metrics import ref_matches


def citation_precision(cited_refs: Sequence[str], expected_refs: Sequence[str]) -> float:
    """Fraction of CITED refs that match a gold expected ref (vacuous 1.0 if none cited)."""
    if not cited_refs:
        return 1.0
    correct = sum(1 for c in cited_refs if any(ref_matches(e, c) for e in expected_refs))
    return correct / len(cited_refs)


def citation_recall(cited_refs: Sequence[str], expected_refs: Sequence[str]) -> float:
    """Fraction of gold expected refs that the answer cited (vacuous 1.0 if none expected)."""
    if not expected_refs:
        return 1.0
    found = sum(1 for e in expected_refs if any(ref_matches(e, c) for c in cited_refs))
    return found / len(expected_refs)
