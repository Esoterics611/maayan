"""Tests for persistent topic threads (temp/in-memory SQLite; no network/models)."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from maayan.capture.models import Session
from maayan.generate.rag import Answer, ContextTurn
from maayan.retrieve.models import SearchResult, Via
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


# -- answer persistence on the ask turn (UI_REDESIGN R7) ------------------------
class _Recorder:
    """A capture service, structurally: opens a session for an answer."""

    def __init__(self) -> None:
        self.answers: list[Answer] = []

    def start_session(self, answer: Answer) -> Session:
        self.answers.append(answer)
        return Session(
            id=f"sess-{len(self.answers)}", timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            question=answer.question, retrieved_refs=[s.ref for s in answer.sources],
            answer_text=answer.text,
        )


class FakeAskWithSources:
    """Returns an answer whose sources cover the shapes the snapshot must carry."""

    def ask(self, question: str, *, context_turns: Sequence[ContextTurn] = ()) -> Answer:
        return Answer(
            question=question, text="because [S1]", grounded=True,
            cited_refs=["Tanya, Chapter 1:3"],
            sources=[
                SearchResult(
                    ref="Tanya, Chapter 1:3", text="printed", score=0.81, lang="he",
                    source="sefaria", payload={"ref": "Tanya, Chapter 1:3"},
                ),
                SearchResult(
                    ref="Shiur 4", text="spoken", score=0.63, lang="he", source="shiur",
                    payload={"metadata": {"audio_id": "aud-1", "start_s": 42.5}},
                    via=Via(relation_id="rel-1", rel_type="explains", evidence="explicit",
                            author="R. G", seed_ref="Tanya, Chapter 1:3"),
                ),
            ],
        )


def test_ask_in_thread_persists_the_answer_and_its_sources(tmp_path) -> None:
    """The sources are the teachable material — a reload must not be what erases them."""
    db = str(tmp_path / "threads.sqlite3")
    svc = _service(db)
    t = svc.start_thread("souls")

    result = ask_in_thread(
        FakeAskWithSources(), svc, t.id, "מהי בחירה", max_context_turns=6,
        record=_Recorder(),
    )

    # Reload from a FRESH connection: this is the reload the UI does, not a cache read.
    detail = _service(db).get_thread_with_turns(t.id)
    assert detail is not None
    turn = detail.turns[-1]
    assert turn.record_id == "sess-1" == result.session_id  # still annotatable
    assert turn.answer is not None
    assert turn.answer.text == "because [S1]"
    assert turn.answer.grounded is True
    assert [s.ref for s in turn.answer.sources] == ["Tanya, Chapter 1:3", "Shiur 4"]
    # The citation mark survives, so [S#] links and the ✦ badge still mean something.
    assert [s.cited for s in turn.answer.sources] == [True, False]
    # …as do the affordances that hang off a source: play-from-here and the via-line.
    shiur = turn.answer.sources[1]
    assert (shiur.audio_id, shiur.start_s) == ("aud-1", 42.5)
    assert shiur.via is not None and shiur.via.seed_ref == "Tanya, Chapter 1:3"
    # The context snapshot is untouched — the model still reads Q:/A:, not JSON.
    assert turn.text.startswith("Q: מהי בחירה")


def test_ask_in_thread_without_a_recorder_still_persists_the_answer() -> None:
    """No capture wired (the CLI's older path): the sources persist, session stays None."""
    svc = _service(":memory:")
    t = svc.start_thread("x")

    result = ask_in_thread(FakeAskWithSources(), svc, t.id, "q", max_context_turns=0)

    assert result.session_id is None
    assert result.turn.record_id is None
    assert result.turn.answer is not None and len(result.turn.answer.sources) == 2


def test_turns_without_an_answer_round_trip_as_none() -> None:
    """Seeds/developments carry no answer — and neither do asks written before R7."""
    svc = _service(":memory:")
    t = svc.start_thread("x")
    svc.add_turn(t.id, turn_type="seed", author="R. G", text="a seed")
    detail = svc.get_thread_with_turns(t.id)
    assert detail is not None and detail.turns[0].answer is None


def test_store_adds_the_answer_column_to_a_pre_existing_table(tmp_path) -> None:
    """`CREATE TABLE IF NOT EXISTS` is a no-op on a live DB — the column needs adding.

    Without this, every already-deployed install would keep the old five-column shape
    and fail on the first ask.
    """
    db = str(tmp_path / "old.sqlite3")
    old = sqlite3.connect(db)  # the schema exactly as it shipped before R7
    old.executescript(
        "CREATE TABLE threads (id TEXT PRIMARY KEY, title TEXT NOT NULL, "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL);"
        "CREATE TABLE thread_turns (id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, "
        "ordinal INTEGER NOT NULL, turn_type TEXT NOT NULL, timestamp TEXT NOT NULL, "
        "author TEXT NOT NULL, record_id TEXT, text TEXT NOT NULL);"
        "INSERT INTO threads VALUES ('t1', 'old topic', '2026-01-01', '2026-01-01');"
        "INSERT INTO thread_turns VALUES ('u1', 't1', 1, 'ask', '2026-01-01', "
        "'model', NULL, 'Q: old\nA: old');"
    )
    old.commit()
    old.close()

    svc = _service(db)  # opening the store migrates it

    detail = svc.get_thread_with_turns("t1")
    assert detail is not None
    assert detail.turns[0].answer is None  # the old turn reads back, just without one
    # …and a new ask on the same DB can now store its sources.
    ask_in_thread(FakeAskWithSources(), svc, "t1", "q", max_context_turns=0)
    reloaded = _service(db).get_thread_with_turns("t1")
    assert reloaded is not None
    assert reloaded.turns[1].answer is not None
    assert len(reloaded.turns[1].answer.sources) == 2


def test_factory_builds_service(tmp_path) -> None:
    from maayan.config import Settings

    settings = Settings(db_path=str(tmp_path / "m.sqlite3"))
    svc = build_thread_service(settings)
    t = svc.start_thread("via factory")
    assert svc.get_thread_with_turns(t.id) is not None
