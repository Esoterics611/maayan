"""Develop gold set: seeds (with a directive) labelled supported / unsupported.

Each case is an expert *seed* — knowledge plus a directive — paired with a
judgement about whether the indexed corpus genuinely hints at it:

- ``supported: true``  → the corpus supports the directive, so the develop step
  should produce a grounded, cited development.
- ``supported: false`` → nothing in the corpus supports it, so the develop step
  should *refuse* (default-deny) rather than force a connection.

This mirrors the positive / ``should_refuse`` split of the retrieval gold set
(:mod:`maayan.eval.goldset`), but for the develop verb instead of ``ask``.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from pydantic import BaseModel


class DevelopGoldExample(BaseModel):
    """One develop eval case: a seed + whether the corpus should support it.

    ``body`` is the seed knowledge (often from texts *outside* the corpus) and
    ``directive`` is the separate "now develop X" instruction. ``author`` is carried
    so the minted seed satisfies the required-provenance rule (it is never blank).
    """

    body: str
    supported: bool
    directive: str | None = None
    author: str = "gold"
    note: str | None = None


def load_develop_goldset(path: str) -> list[DevelopGoldExample]:
    """Load a develop gold set from YAML (.yaml/.yml) or JSON."""
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) if p.suffix in (".yaml", ".yml") else json.loads(raw)
    items = data["examples"] if isinstance(data, dict) else data
    return [DevelopGoldExample.model_validate(item) for item in items]
