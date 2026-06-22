"""ThreadService: own thread/turn lifecycle, with the Clock injected.

The store is pure persistence; this service stamps timestamps (via the injected
Clock), assigns 1-based ordinals, and returns typed composites. Construction happens
at the edges (CLI / UI wiring / tests).
"""

from __future__ import annotations

import uuid

from maayan.clock import Clock
from maayan.threads.models import Thread, ThreadTurn, ThreadWithTurns, TurnType
from maayan.threads.store import ThreadStore


class ThreadService:
    """Create threads and append ordered, provenance-bearing turns."""

    def __init__(self, store: ThreadStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def start_thread(self, title: str) -> Thread:
        now = self._clock.now()
        thread = Thread(id=str(uuid.uuid4()), title=title, created_at=now, updated_at=now)
        return self._store.create_thread(thread)

    def add_turn(
        self,
        thread_id: str,
        *,
        turn_type: TurnType,
        author: str,
        text: str,
        record_id: str | None = None,
    ) -> ThreadTurn:
        """Append a turn; its ordinal is the next 1-based slot in the thread."""
        ordinal = len(self._store.get_turns(thread_id)) + 1
        turn = ThreadTurn(
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            ordinal=ordinal,
            turn_type=turn_type,
            timestamp=self._clock.now(),
            author=author,
            record_id=record_id,
            text=text,
        )
        return self._store.append_turn(turn)

    def get_thread_with_turns(self, thread_id: str) -> ThreadWithTurns | None:
        thread = self._store.get_thread(thread_id)
        if thread is None:
            return None
        return ThreadWithTurns(thread=thread, turns=self._store.get_turns(thread_id))

    def list_threads(self) -> list[Thread]:
        return self._store.list_threads()
