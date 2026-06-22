"""Metrics for the develop step. Pure, hand-checkable functions.

The develop step has two qualities worth measuring, both orthogonal to retrieval
ranking:

- **grounding** — of the refs a development *cites*, the fraction that were actually
  in the retrieved set. A citation to a ref that was never retrieved is a fabrication;
  1.0 means every citation is backed by a source the model was actually given.
- **refusal correctness** — captured at the harness level (a supported seed should be
  developed; an unsupported seed should be refused), mirroring the default-deny gate
  rates of the retrieval harness.
"""

from __future__ import annotations

from collections.abc import Sequence


def grounding_score(cited_refs: Sequence[str], retrieved_refs: Sequence[str]) -> float:
    """Fraction of CITED refs that were actually retrieved (1.0 = no fabricated citation).

    A grounded development must cite only sources it was given. Any cited ref absent
    from ``retrieved_refs`` is a fabrication and drags the score down. With no
    citations there is nothing to fabricate, so the score is a vacuous 1.0.
    """
    if not cited_refs:
        return 1.0
    retrieved = set(retrieved_refs)
    grounded = sum(1 for ref in cited_refs if ref in retrieved)
    return grounded / len(cited_refs)
