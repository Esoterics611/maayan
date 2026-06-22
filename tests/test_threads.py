"""Tests for persistent topic threads (temp/in-memory SQLite; no network/models)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from maayan.generate.rag import Answer, ContextTurn
from maayan.threads.factory import build_thread_service
from maayan.threads.flow import ask_in_thread
from maayan.threads.service import ThreadService
from maayan.threads.store import ThreadStore


class TickClock:
    """Clock that advances one minute per `now()` — gives strictly increasing times."""

    def __init__(self) -> None:
        self._t = datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        self._t += timedelta(minutes=1)
        return self._t

    def monotonic(self) -> float:
        return 0.0

    async def sleep(self, seconds: float) -> None:  # pragma: no cover - unused
        return None


def _service(db: str) -> ThreadService:
    return ThreadService(ThreadStore(db), TickClock())


def test_thread_three_turns_persist_in_order_with_provenance(tmp_path) -> None:
    db = str(tmp_path / "threads.sqlite3")
    svc = _service(db)
    thread = svc.start_thread("ahava b'ta'anugim")

    svc.add_turn(thread.id, turn_type="ask", author="model",
                 text="What is ahava b'ta'anugim?", record_id="sess-1")
    svc.add_turn(thread.id, turn_type="seed", author="R. Ginsburgh",
                 text="It is the revelation of the Name Ab…", record_id="contrib-1")
    svc.add_turn(thread.id, turn_type="refinement", author="R. Ginsburgh",
                 text="Focus on the Vayechi sources.", record_id=None)

    # Reload from a FRESH connection on the same DB → real persistence, not cache.
    reloaded = _service(db)
    detail = reloaded.get_thread_with_turns(thread.id)
    assert detail is not None
    assert detail.thread.title == "ahava b'ta'anugim"

    turns = detail.turns
    assert [t.ordinal for t in turns] == [1, 2, 3]  # order preserved
    assert [t.turn_type for t in turns] == ["ask", "seed", "refinement"]
    assert [t.author for t in turns] == ["model", "R. Ginsburgh", "R. Ginsburgh"]
    assert [t.record_id for t in turns] == ["sess-1", "contrib-1", None]
    assert turns[0].text.startswith("What is")


def test_add_turn_bumps_thread_updated_at() -> None:
    svc = _service(":memory:")
    thread = svc.start_thread("topic")
    before = thread.updated_at
    svc.add_turn(thread.id, turn_type="ask", author="model", text="q")
    detail = svc.get_thread_with_turns(thread.id)
    assert detail is not None
    assert detail.thread.updated_at > before  # activity moved the thread forward


def test_list_threads_orders_by_recent_activity() -> None:
    svc = _service(":memory:")
    a = svc.start_thread("first")
    b = svc.start_thread("second")
    # Touch `a` after `b` was created → `a` should sort first (most recent).
    svc.add_turn(a.id, turn_type="ask", author="model", text="q")
    listed = [t.id for t in svc.list_threads()]
    assert listed[0] == a.id
    assert set(listed) == {a.id, b.id}


def test_get_thread_with_turns_none_for_missing() -> None:
    svc = _service(":memory:")
    assert svc.get_thread_with_turns("nope") is None


class FakeAsk:
    """Records the context it was handed; returns a fixed grounded answer."""

    def __init__(self) -> None:
        self.received: list[list[ContextTurn]] = []

    def ask(self, question: str, *, context_turns: Sequence[ContextTurn] = ()) -> Answer:
        self.received.append(list(context_turns))
        return Answer(
            question=question, text="grounded [S1]", grounded=True,
            cited_refs=["Tanya 1:3"], sources=[],
        )


def test_ask_in_thread_passes_prior_turns_as_context_and_appends_ask() -> None:
    svc = _service(":memory:")
    t = svc.start_thread("souls")
    svc.add_turn(t.id, turn_type="ask", author="model", text="Q: מהי נפש האלוקית\nA: …")
    svc.add_turn(t.id, turn_type="seed", author="R. G", text="seed note")

    rag = FakeAsk()
    result = ask_in_thread(rag, svc, t.id, "ונפש הבהמית?", max_context_turns=6)

    # The two prior turns were mapped to non-citable context (speaker = turn_type).
    assert [c.speaker for c in rag.received[0]] == ["ask", "seed"]
    assert rag.received[0][0].text.startswith("Q: מהי")
    # A new ask turn was appended snapshotting the exchange.
    detail = svc.get_thread_with_turns(t.id)
    assert detail is not None
    assert detail.turns[-1].turn_type == "ask"
    assert detail.turns[-1].text.startswith("Q: ונפש הבהמית?")
    assert result.turn.ordinal == 3
    assert result.answer.grounded is True


def test_ask_in_thread_truncates_to_last_n() -> None:
    svc = _service(":memory:")
    t = svc.start_thread("x")
    for i in range(5):
        svc.add_turn(t.id, turn_type="refinement", author="a", text=f"turn{i}")
    rag = FakeAsk()
    ask_in_thread(rag, svc, t.id, "q", max_context_turns=2)
    assert [c.text for c in rag.received[0]] == ["turn3", "turn4"]  # last 2 only


def test_factory_builds_service(tmp_path) -> None:
    from maayan.config import Settings

    settings = Settings(db_path=str(tmp_path / "m.sqlite3"))
    svc = build_thread_service(settings)
    t = svc.start_thread("via factory")
    assert svc.get_thread_with_turns(t.id) is not None
