"""Typed protocol for the chavrusa loop: actions, steps, budgets, the trace.

`StudyAction` is a closed, discriminated union — five verbs and no others; the
model's reply is parsed against it strictly (SWE-agent's lesson: agent quality
is a function of action-space design). A `StudyTrace` is itself teaching
material — the record of how a sugya was worked, budget honesty included.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from maayan.generate.rag import Answer


class SearchAction(BaseModel):
    """Run a fresh retrieval with a (possibly revised) query."""

    verb: Literal["search"] = "search"
    query: str


class OpenSectionAction(BaseModel):
    """Open a specific passage by canonical ref (follow a mareh makom)."""

    verb: Literal["open_section"] = "open_section"
    ref: str


class WalkGraphAction(BaseModel):
    """Follow approved graph edges one hop out from a ref."""

    verb: Literal["walk_graph"] = "walk_graph"
    ref: str


class LookupTermAction(BaseModel):
    """Look a term up in the curated lexicon."""

    verb: Literal["lookup_term"] = "lookup_term"
    term: str


class ConcludeAction(BaseModel):
    """Stop studying and synthesize from the working set."""

    verb: Literal["conclude"] = "conclude"


StudyAction = Annotated[
    SearchAction | OpenSectionAction | WalkGraphAction | LookupTermAction | ConcludeAction,
    Field(discriminator="verb"),
]


class HitDigest(BaseModel):
    """One retrieved/gathered chunk, compactly."""

    ref: str
    score: float
    source: str


class EdgeDigest(BaseModel):
    """One graph edge followed, with its provenance."""

    rel_type: str
    far: str
    author: str
    evidence: str


class StepDigest(BaseModel):
    """The compact typed result of one action — what the step actually yielded."""

    hits: list[HitDigest] = Field(default_factory=list)
    refs_opened: list[str] = Field(default_factory=list)
    edges: list[EdgeDigest] = Field(default_factory=list)
    term: str | None = None
    added_chunks: int = 0
    note: str | None = None  # honesty channel: "below threshold", "unknown ref", …


class StudyStep(BaseModel):
    """One hop: the action the model chose, what it yielded, what it cost."""

    action: StudyAction
    digest: StepDigest
    calls_spent: int = 0  # model calls consumed choosing this action (incl. repair)


class BudgetState(BaseModel):
    """Hard limits and usage — exhaustion is shown honestly, never disguised."""

    hops_used: int = 0
    hops_max: int
    chunks_used: int = 0
    chunks_max: int
    calls_used: int = 0
    calls_max: int
    exhausted: str | None = None  # which budget forced the conclude, if any


class StudyTrace(BaseModel):
    """The chavrusa's notebook: how the sugya was worked, end to end."""

    id: str
    question: str
    steps: list[StudyStep]
    answer: Answer
    budgets: BudgetState
    forced: bool = False  # True → a budget (or a malformed reply) forced the conclude
    created_at: datetime
