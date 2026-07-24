"""Thread ⇄ RAG orchestration: ask within a thread, context-aware but grounded.

Asking inside a thread (a) reads the last N turns and passes them to the RAG service
as NON-citable conversation context (so a follow-up like "and the animal soul?"
resolves), and (b) appends an "ask" turn snapshotting the exchange — the words *and*
the sources they were grounded in. Retrieval and default-deny are untouched — that
lives in `RAGService.ask`.

This is the only place the threads package depends on the generate/retrieve layers;
the core store/service stay decoupled. Everything is injected (no construction here).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel

from maayan.generate.rag import Answer, ContextTurn
from maayan.retrieve.models import SearchResult
from maayan.threads.models import AnswerSnapshot, ThreadTurn, TurnSource, TurnVia
from maayan.threads.service import ThreadService


class Asking(Protocol):
    """The slice of RAGService this flow needs (structurally typed for easy mocking)."""

    def ask(self, question: str, *, context_turns: Sequence[ContextTurn] = ...) -> Answer:
        ...


class Recorded(Protocol):
    """Anything carrying an id — the capture `Session`, structurally.

    Typed this way so the flow can open a session without importing the capture
    layer: threads already reach into generate/retrieve, and one more concrete
    dependency would make the package the hub it was designed not to be.
    """

    id: str


class Recording(Protocol):
    """The slice of CaptureService this flow needs: make the answer annotatable."""

    def start_session(self, answer: Answer) -> Recorded:
        ...


class ThreadAskResult(BaseModel):
    """Typed result of asking within a thread (no loose tuples across boundaries)."""

    answer: Answer
    turn: ThreadTurn
    # The capture session opened for this ask — None when no recorder was injected.
    session_id: str | None = None


def to_context_turns(turns: Sequence[ThreadTurn]) -> list[ContextTurn]:
    """Map persisted thread turns to non-citable conversation context for the model."""
    return [ContextTurn(speaker=t.turn_type, text=t.text) for t in turns]


def _ask_snapshot(question: str, answer: Answer) -> str:
    """A compact display/context snapshot of one ask exchange."""
    return f"Q: {question}\nA: {answer.text}"


def _turn_source(source: SearchResult, *, cited: bool) -> TurnSource:
    """Flatten one retrieved hit into its persistable display form."""
    meta = source.payload.get("metadata") or {} if isinstance(source.payload, dict) else {}
    is_shiur = source.source == "shiur"
    via = source.via
    return TurnSource(
        ref=source.ref, text=source.text, lang=source.lang, source=source.source,
        score=source.score, cited=cited,
        audio_id=meta.get("audio_id") if is_shiur else None,
        start_s=meta.get("start_s") if is_shiur else None,
        via=TurnVia(
            rel_type=via.rel_type, evidence=via.evidence, author=via.author,
            seed_ref=via.seed_ref, note=via.note,
        ) if via is not None else None,
    )


def snapshot_answer(answer: Answer) -> AnswerSnapshot:
    """Map a live `Answer` onto the snapshot that gets persisted and rendered.

    The UI builds *both* the live ask response and a reopened turn from this one
    mapping, so a restored answer and a fresh one are the same thing on the wire —
    which is the whole point: the reader must not be able to tell them apart.
    """
    cited = set(answer.cited_refs)
    return AnswerSnapshot(
        question=answer.question,
        text=answer.text,
        grounded=answer.grounded,
        cited_refs=list(answer.cited_refs),
        sources=[_turn_source(s, cited=s.ref in cited) for s in answer.sources],
        reasoning=answer.reasoning,
        unsupported_claims=list(answer.unsupported_claims),
    )


def ask_in_thread(
    rag: Asking,
    threads: ThreadService,
    thread_id: str,
    question: str,
    *,
    max_context_turns: int,
    author: str = "model",
    record: Recording | None = None,
) -> ThreadAskResult:
    """Ask `question` within a thread, using its last `max_context_turns` as context."""
    detail = threads.get_thread_with_turns(thread_id)
    prior = detail.turns[-max_context_turns:] if detail and max_context_turns > 0 else []
    answer = rag.ask(question, context_turns=to_context_turns(prior))
    # The capture session opens BEFORE the turn is appended so the turn can carry its
    # id: annotating a reopened answer needs a session, and without one the teaching
    # affordances would work on the freshest ask only.
    session_id = record.start_session(answer).id if record is not None else None
    turn = threads.add_turn(
        thread_id, turn_type="ask", author=author, text=_ask_snapshot(question, answer),
        record_id=session_id, answer=snapshot_answer(answer),
    )
    return ThreadAskResult(answer=answer, turn=turn, session_id=session_id)
