"""UI/route tests for the quick-capture inbox (Prompt 30).

Real InboxService (in-memory SQLite) with capture + threads faked, so the
move-to-thread path proves it reuses the EXISTING seed flow (add_annotation +
add_turn) without a real embedder/Qdrant.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from maayan.capture.models import Annotation
from maayan.clock import SystemClock
from maayan.config import Settings
from maayan.inbox.service import InboxService
from maayan.inbox.store import InboxStore
from maayan.ui.app import create_app
from maayan.users.service import UserService
from maayan.users.store import UserStore

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeCapture:
    allowed_kinds = ("correction", "connection", "addition", "objection")

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def add_annotation(
        self, session_id: str, *, author: str, kind: str, body: str,
        linked_refs: object = (), move: object = None,
        directive: object = None, opens_aspect: bool = False,
    ) -> Annotation:
        if kind not in self.allowed_kinds:
            raise ValueError(f"Unknown kind {kind!r}")
        self.calls.append(
            {"thread_id": session_id, "kind": kind, "body": body, "opens_aspect": opens_aspect}
        )
        return Annotation(
            id="seed-1", session_id=session_id, timestamp=NOW, author=author,
            kind=kind, body=body, directive=directive, opens_aspect=opens_aspect,
        )


class _FakeThreads:
    def __init__(self, known: set[str]) -> None:
        self._known = known
        self.turns: list[dict[str, object]] = []

    def get_thread_with_turns(self, thread_id: str) -> object | None:
        return object() if thread_id in self._known else None

    def add_turn(
        self, thread_id: str, *, turn_type: str, author: str, text: str, record_id: str
    ) -> None:
        self.turns.append({"thread_id": thread_id, "turn_type": turn_type, "record_id": record_id})


def _client(
    *, inbox: InboxService | None = None,
    capture: _FakeCapture | None = None, threads: _FakeThreads | None = None,
) -> tuple[TestClient, _FakeCapture, _FakeThreads]:
    cap = capture or _FakeCapture()
    thr = threads or _FakeThreads({"thr-1"})
    inb = inbox if inbox is not None else InboxService(InboxStore(":memory:"), SystemClock())
    app = create_app(  # type: ignore[arg-type]
        None, cap, thr, None, None, None, None, None, inbox=inb,
    )
    return TestClient(app), cap, thr


def _capture_item(client: TestClient, text: str = "a fleeting idea") -> str:
    r = client.post("/api/inbox", json={"text": text, "author": "R. G"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_capture_then_list() -> None:
    client, _, _ = _client()
    item_id = _capture_item(client)
    items = client.get("/api/inbox").json()
    assert [i["id"] for i in items] == [item_id]
    assert items[0]["status"] == "open"
    assert items[0]["author"] == "R. G"


def test_capture_blank_author_is_400() -> None:
    client, _, _ = _client()
    r = client.post("/api/inbox", json={"text": "x", "author": "  "})
    assert r.status_code == 400


def test_move_reuses_seed_flow_and_marks_item() -> None:
    client, cap, thr = _client()
    item_id = _capture_item(client)
    r = client.post(f"/api/inbox/{item_id}/move", json={"thread_id": "thr-1"})
    assert r.status_code == 200, r.text
    moved = r.json()
    assert moved["status"] == "moved"
    assert moved["thread_id"] == "thr-1"
    assert moved["record_id"] == "seed-1"
    # Reused the existing seed flow: an opens_aspect annotation + a seed turn.
    assert cap.calls == [
        {"thread_id": "thr-1", "kind": "addition", "body": "a fleeting idea", "opens_aspect": True}
    ]
    assert thr.turns and thr.turns[0]["turn_type"] == "seed"
    # No longer open once triaged.
    assert client.get("/api/inbox").json() == []


def test_move_unknown_item_is_404() -> None:
    client, _, _ = _client()
    assert client.post("/api/inbox/nope/move", json={"thread_id": "thr-1"}).status_code == 404


def test_move_unknown_thread_is_404() -> None:
    client, _, _ = _client()
    item_id = _capture_item(client)
    r = client.post(f"/api/inbox/{item_id}/move", json={"thread_id": "ghost"})
    assert r.status_code == 404


def test_inbox_disabled_is_503() -> None:
    app = create_app(None, None, None, None, None, None, None, None)  # type: ignore[arg-type]
    client = TestClient(app)
    assert client.get("/api/inbox").status_code == 503
    assert client.post("/api/inbox", json={"text": "x", "author": "R"}).status_code == 503


def test_inbox_requires_auth_when_enabled(tmp_path: Path) -> None:
    settings = Settings(db_path=str(tmp_path / "u.sqlite3"), pbkdf2_iterations=1000)
    users = UserService(UserStore(settings.db_path), SystemClock(), settings)
    inb = InboxService(InboxStore(":memory:"), SystemClock())
    app = create_app(  # type: ignore[arg-type]
        None, _FakeCapture(), _FakeThreads({"thr-1"}), None, None, None, None, None,
        users=users, inbox=inb, auth_enabled=True,
    )
    client = TestClient(app)
    assert client.get("/api/inbox").status_code == 401
    assert client.post("/api/inbox", json={"text": "x", "author": "R"}).status_code == 401
