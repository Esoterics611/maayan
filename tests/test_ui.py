"""Tests for the FastAPI UI — wiring only, with RAG + capture mocked."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from maayan.capture.models import Annotation, Session
from maayan.generate.rag import Answer
from maayan.retrieve.models import SearchResult
from maayan.ui.app import create_app

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _answer(grounded: bool = True) -> Answer:
    sources = [
        SearchResult(
            ref="Tanya 1:1", text="בחירה חופשית", score=0.6, lang="he",
            source="sefaria", payload={},
        )
    ]
    return Answer(
        question="מהי בחירה", text="תשובה [S1]" if grounded else "I don't have a source.",
        grounded=grounded, cited_refs=["Tanya 1:1"] if grounded else [], sources=sources,
    )


class FakeRag:
    def __init__(self, answer: Answer) -> None:
        self._answer = answer
        self.calls: list[str] = []

    def ask(self, question: str, *, k=None, book=None, source=None) -> Answer:
        self.calls.append(question)
        return self._answer


class FakeCapture:
    allowed_kinds = ("correction", "connection")

    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}
        self.annotations: list[Annotation] = []

    def start_session(self, answer: Answer) -> Session:
        s = Session(
            id="sess-1", timestamp=NOW, question=answer.question,
            retrieved_refs=[x.ref for x in answer.sources], answer_text=answer.text,
        )
        self.sessions[s.id] = s
        return s

    def add_annotation(
        self, session_id: str, *, author, kind, body, linked_refs: Sequence[str] = (), move=None
    ) -> Annotation:
        if kind not in self.allowed_kinds:
            raise ValueError(f"Unknown kind {kind!r}")
        a = Annotation(
            id="ann-1", session_id=session_id, timestamp=NOW, author=author, kind=kind,
            body=body, linked_refs=list(linked_refs), move=move,
        )
        self.annotations.append(a)
        return a

    def get_session(self, session_id: str) -> Session | None:
        return self.sessions.get(session_id)

    def get_annotations(self, session_id: str) -> list[Annotation]:
        return [a for a in self.annotations if a.session_id == session_id]


def _client(grounded: bool = True) -> tuple[TestClient, FakeRag, FakeCapture]:
    rag = FakeRag(_answer(grounded))
    capture = FakeCapture()
    return TestClient(create_app(rag, capture)), rag, capture  # type: ignore[arg-type]


def test_index_serves_html() -> None:
    client, _, _ = _client()
    r = client.get("/")
    assert r.status_code == 200
    assert "maayan" in r.text


def test_kinds_endpoint() -> None:
    client, _, _ = _client()
    assert client.get("/kinds").json() == ["correction", "connection"]


def test_ask_wires_rag_and_records_session() -> None:
    client, rag, capture = _client()
    r = client.post("/ask", json={"question": "מהי בחירה"})
    assert r.status_code == 200
    data = r.json()
    assert data["session_id"] == "sess-1"
    assert data["grounded"] is True
    assert data["sources"][0]["ref"] == "Tanya 1:1"
    assert data["sources"][0]["cited"] is True
    assert rag.calls == ["מהי בחירה"]
    assert "sess-1" in capture.sessions


def test_ask_passes_through_refusal() -> None:
    client, _, _ = _client(grounded=False)
    data = client.post("/ask", json={"question": "baseball rules"}).json()
    assert data["grounded"] is False


def test_annotate_wires_capture() -> None:
    client, _, capture = _client()
    client.post("/ask", json={"question": "מהי בחירה"})
    r = client.post("/annotate", json={
        "session_id": "sess-1", "body": "חיבור", "kind": "connection",
        "author": "R. G", "linked_refs": ["Tanya 1:1"], "move": "a->b",
    })
    assert r.status_code == 200
    assert r.json()["annotation_id"] == "ann-1"
    assert capture.annotations[0].body == "חיבור"


def test_annotate_bad_kind_returns_400() -> None:
    client, _, _ = _client()
    client.post("/ask", json={"question": "q"})
    r = client.post("/annotate", json={"session_id": "sess-1", "body": "x", "kind": "bogus"})
    assert r.status_code == 400


def test_get_session() -> None:
    client, _, _ = _client()
    client.post("/ask", json={"question": "מהי בחירה"})
    r = client.get("/session/sess-1")
    assert r.status_code == 200
    assert r.json()["id"] == "sess-1"
    assert client.get("/session/missing").status_code == 404
