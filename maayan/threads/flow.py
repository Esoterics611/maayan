"""Thread ⇄ RAG orchestration: ask within a thread, context-aware but grounded.

Asking inside a thread (a) reads the last N turns and passes them to the RAG service
as NON-citable conversation context (so a follow-up like "and the animal soul?"
resolves), and (b) appends an "ask" turn snapshotting the exchange. Retrieval and
default-deny are untouched — that lives in `RAGService.ask`.

This is the only place the threads package depends on the generate layer; the core
store/service stay decoupled. Everything is injected (no construction here).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel

from maayan.generate.rag import Answer, ContextTurn
from maayan.threads.models import ThreadTurn
from maayan.threads.service import ThreadService


class Asking(Protocol):
    """The slice of RAGService this flow needs (structurally typed for easy mocking)."""

    def ask(self, question: str, *, context_turns: Sequence[ContextTurn] = ...) -> Answer:
        ...


class ThreadAskResult(BaseModel):
    """Typed result of asking within a thread (no loose tuples across boundaries)."""

    answer: Answer
    turn: ThreadTurn


def to_context_turns(turns: Sequence[ThreadTurn]) -> list[ContextTurn]:
    """Map persisted thread turns to non-citable conversation context for the model."""
    return [ContextTurn(speaker=t.turn_type, text=t.text) for t in turns]


def _ask_snapshot(question: str, answer: Answer) -> str:
    """A compact display/context snapshot of one ask exchange."""
    return f"Q: {question}\nA: {answer.text}"


def ask_in_thread(
    rag: Asking,
    threads: ThreadService,
    thread_id: str,
    question: str,
    *,
    max_context_turns: int,
    author: str = "model",
) -> ThreadAskResult:
    """Ask `question` within a thread, using its last `max_context_turns` as context."""
    detail = threads.get_thread_with_turns(thread_id)
    prior = detail.turns[-max_context_turns:] if detail and max_context_turns > 0 else []
    answer = rag.ask(question, context_turns=to_context_turns(prior))
    turn = threads.add_turn(
        thread_id, turn_type="ask", author=author, text=_ask_snapshot(question, answer)
    )
    return ThreadAskResult(answer=answer, turn=turn)
