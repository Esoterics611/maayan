"""The quick-capture inbox service: park a thought, list, mark it triaged.

Deliberately thin storage logic — id + time come from the injected `Clock` (house
rule: no inline time), validation lives on the `InboxItem` model. Turning a parked
thought into a thread seed is orchestrated at the UI edge (the `/api/inbox/{id}/move`
route reuses the EXISTING seed flow), so this service stays decoupled from capture
and threads and is trivially testable.
"""

from __future__ import annotations

import uuid

from maayan.clock import Clock
from maayan.inbox.models import InboxItem
from maayan.inbox.store import InboxStore


class InboxService:
    """Parks captured thoughts and records their move-to-thread triage."""

    def __init__(self, store: InboxStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def capture(self, *, text: str, author: str) -> InboxItem:
        """Park a new thought (blank author/text are rejected by the model validator)."""
        item = InboxItem(
            id=str(uuid.uuid4()),
            author=author,
            text=text,
            created_at=self._clock.now(),
        )
        return self._store.save(item)

    def list_open(self) -> list[InboxItem]:
        return self._store.list_open()

    def get(self, item_id: str) -> InboxItem | None:
        return self._store.get(item_id)

    def mark_moved(self, item_id: str, *, thread_id: str, record_id: str) -> InboxItem:
        """Record that an item was triaged into `thread_id` as seed `record_id`."""
        item = self._store.get(item_id)
        if item is None:
            raise ValueError(f"inbox item not found: {item_id}")
        moved = item.model_copy(
            update={"status": "moved", "thread_id": thread_id, "record_id": record_id}
        )
        return self._store.save(moved)
