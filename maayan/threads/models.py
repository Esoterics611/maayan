"""Models for persistent topic threads.

A `Thread` is a single line of inquiry that accumulates over many turns. A
`ThreadTurn` is one event in that thread — an `ask` (a grounded RAG answer), a
`seed` (an expert contribution that opens an aspect), a `development` (a model
development of a seed), or a `refinement` (a follow-up note). Each turn keeps a
`record_id` pointing at the underlying record (session / contribution /
development) plus a `text` snapshot so a thread renders without re-joining.

An `ask` turn additionally carries an `AnswerSnapshot`: the answer *and the sources
it was grounded in*, exactly as they were shown. Without it a reopened thread keeps
the words and loses the material — and the material is what the expert teaches from.
The models here mirror the retrieval/generation shapes deliberately rather than
importing them: only `threads/flow.py` may depend on those layers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TurnType = Literal["ask", "seed", "development", "refinement", "composition"]


class Thread(BaseModel):
    """A topic: a reopenable, listable line of inquiry."""

    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class TurnVia(BaseModel):
    """Why a graph-expanded source appeared, snapshotted alongside it."""

    rel_type: str
    evidence: str
    author: str
    seed_ref: str
    note: str | None = None


class TurnSource(BaseModel):
    """One retrieved source as it stood under an answer.

    A snapshot, not a live reference: reopening the thread must show what the scholar
    actually saw, even after the index has moved underneath (a chunk re-embedded,
    retracted, or re-scored). `cited` records whether the answer leaned on it.
    """

    ref: str
    text: str
    lang: str
    source: str
    score: float
    cited: bool = False
    # source="shiur": lets a cited source play from its moment in the recording.
    audio_id: str | None = None
    start_s: float | None = None
    via: TurnVia | None = None


class AnswerSnapshot(BaseModel):
    """A grounded answer with its sources, persisted on the ask turn that produced it.

    This is what makes a reopened thread teachable rather than merely readable: the
    source cards, their citation marks, and the refusal verdict all survive a reload.
    """

    question: str
    text: str
    grounded: bool
    cited_refs: list[str] = Field(default_factory=list)
    sources: list[TurnSource] = Field(default_factory=list)
    reasoning: str | None = None  # the study map, in reasoning mode
    unsupported_claims: list[str] = Field(default_factory=list)


class ThreadTurn(BaseModel):
    """One ordered event in a thread, with a snapshot for display + provenance."""

    id: str
    thread_id: str
    ordinal: int  # 1-based position within the thread
    turn_type: TurnType
    timestamp: datetime
    author: str  # "model" or a person's name
    record_id: str | None = None  # session_id / contribution_id / development_id
    text: str  # snapshot of the turn for display
    # "ask" turns only: the answer + its sources, so they outlive the page (R7).
    answer: AnswerSnapshot | None = None


class ThreadWithTurns(BaseModel):
    """A thread plus its ordered turns (the typed result of a 'show thread')."""

    thread: Thread
    turns: list[ThreadTurn] = Field(default_factory=list)
