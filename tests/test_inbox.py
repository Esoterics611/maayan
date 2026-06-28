"""Tests for the quick-capture inbox service + store (Prompt 30).

In-memory SQLite + FakeClock — no network, no real time. Covers persistence, the
provenance/empty guards, and the move-to-thread lifecycle bookkeeping.
"""

from __future__ import annotations

import pytest

from maayan.clock import FakeClock
from maayan.inbox.service import InboxService
from maayan.inbox.store import InboxStore


def _service() -> InboxService:
    return InboxService(InboxStore(":memory:"), FakeClock())


def test_capture_persists_and_lists_open() -> None:
    svc = _service()
    item = svc.capture(text="אהבה בתענוגים", author="R. G")
    assert item.status == "open"
    assert item.thread_id is None
    listed = svc.list_open()
    assert [i.id for i in listed] == [item.id]
    assert svc.get(item.id) is not None


def test_blank_author_and_text_are_rejected() -> None:
    svc = _service()
    with pytest.raises(ValueError, match="author is required"):
        svc.capture(text="x", author="   ")
    with pytest.raises(ValueError, match="cannot be empty"):
        svc.capture(text="  ", author="R. G")


def test_move_marks_item_and_drops_it_from_open() -> None:
    svc = _service()
    item = svc.capture(text="a fleeting idea", author="R. G")
    moved = svc.mark_moved(item.id, thread_id="thr-1", record_id="seed-9")
    assert moved.status == "moved"
    assert moved.thread_id == "thr-1"
    assert moved.record_id == "seed-9"
    # No longer surfaced as open, but still retrievable by id (audit trail).
    assert svc.list_open() == []
    assert svc.get(item.id) is not None


def test_get_unknown_is_none_and_move_unknown_raises() -> None:
    svc = _service()
    assert svc.get("nope") is None
    with pytest.raises(ValueError, match="inbox item not found"):
        svc.mark_moved("nope", thread_id="t", record_id="r")
