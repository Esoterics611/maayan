"""Models for persistent topic threads.

A `Thread` is a single line of inquiry that accumulates over many turns. A
`ThreadTurn` is one event in that thread — an `ask` (a grounded RAG answer), a
`seed` (an expert contribution that opens an aspect), a `development` (a model
development of a seed), or a `refinement` (a follow-up note). Each turn keeps a
`record_id` pointing at the underlying record (session / contribution /
development) plus a `text` snapshot so a thread renders without re-joining.
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


class ThreadWithTurns(BaseModel):
    """A thread plus its ordered turns (the typed result of a 'show thread')."""

    thread: Thread
    turns: list[ThreadTurn] = Field(default_factory=list)
