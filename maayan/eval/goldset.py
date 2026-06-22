"""Gold set: a list of {question, expected_refs} for retrieval evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class GoldExample(BaseModel):
    """One eval case.

    Positive cases carry the chapter(s) that should be retrieved (`expected_refs`).
    Negative cases set `should_refuse: true` and leave `expected_refs` empty — the
    correct behavior is for the default-deny gate to refuse (relevance below the
    threshold), so they measure the gate rather than ranking.
    """

    question: str
    expected_refs: list[str] = Field(default_factory=list)
    should_refuse: bool = False
    note: str | None = None


def load_goldset(path: str) -> list[GoldExample]:
    """Load a gold set from YAML (.yaml/.yml) or JSON."""
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) if p.suffix in (".yaml", ".yml") else json.loads(raw)
    items = data["examples"] if isinstance(data, dict) else data
    return [GoldExample.model_validate(item) for item in items]
