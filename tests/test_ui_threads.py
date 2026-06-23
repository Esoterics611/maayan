"""Tests for the Phase-2 thread UI routes — TestClient + mocked services, no network.

The real (lightweight, in-memory) `ThreadService` is used as the spine so turn
ordering/appending is exercised for real; the heavy services (RAG, capture, develop)
are faked. `FakeDevelop` is wired to the thread service so it appends a development
turn exactly as the real service does.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from maayan.capture.models import Annotation, Session
from maayan.clock import FakeClock
from maayan.develop.models import Development
from maayan.generate.rag import Answer, ContextTurn
from maayan.lexicon.models import Term
from maayan.retrieve.models import SearchResult
from maayan.threads.service import ThreadService
from maayan.threads.store import ThreadStore
from maayan.ui.app import create_app

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakeRag:
    def __init__(self, grounded: bool = True) -> None:
        self.grounded = grounded
        self.contexts: list[list[ContextTurn]] = []

    def ask(self, question: str, *, k=None, book=None, source=None,
            context_turns: Sequence[ContextTurn] = ()) -> Answer:
        self.contexts.append(list(context_turns))
        sources = [SearchResult(
            ref="Tanya 1:6", text="derived knowledge", score=0.7, lang="he",
            source="derived", payload={"ref": "Tanya 1:6"},
        )]
        return Answer(
            question=question, text="answer [S1]" if self.grounded else "no source",
            grounded=self.grounded, cited_refs=["Tanya 1:6"] if self.grounded else [],
            sources=sources,
        )


class FakeCapture:
    allowed_kinds = ("correction", "connection")

    def __init__(self) -> None:
        self.annotations: dict[str, Annotation] = {}
        self._sessions = 0

    def add_annotation(self, session_id: str, *, author, kind, body, linked_refs=(),
                       move=None, directive=None, opens_aspect=False) -> Annotation:
        a = Annotation(  # blank author raises ValidationError (a ValueError) → 400
            id=f"contrib-{len(self.annotations) + 1}", session_id=session_id, timestamp=NOW,
            author=author, kind=kind, body=body, linked_refs=list(linked_refs), move=move,
            directive=directive, opens_aspect=opens_aspect,
        )
        self.annotations[a.id] = a
        return a

    def get_annotation(self, annotation_id: str) -> Annotation | None:
        return self.annotations.get(annotation_id)

    def start_session(self, answer: Answer) -> Session:
        self._sessions += 1
        return Session(
            id=f"sess-{self._sessions}", timestamp=NOW, question=answer.question,
            retrieved_refs=[s.ref for s in answer.sources], answer_text=answer.text,
        )


class FakeDevelop:
    """Mirrors DevelopmentService externally; appends the develop turn via threads."""

    def __init__(self, threads: ThreadService, *, grounded: bool = True) -> None:
        self._threads = threads
        self.grounded = grounded
        self.devs: dict[str, Development] = {}

    def develop(self, seed: Annotation, *, thread_id: str) -> Development:
        d = Development(
            id=f"dev-{len(self.devs) + 1}", thread_id=thread_id, seed_id=seed.id,
            author=seed.author, timestamp=NOW, model="test-model" if self.grounded else "",
            status="proposed", grounded=self.grounded,
            text="developed [S1]" if self.grounded else "no support",
            cited_refs=["Tanya 1:6"] if self.grounded else [],
            grounded_in=["Tanya 1:6"] if self.grounded else [],
        )
        self.devs[d.id] = d
        self._threads.add_turn(
            thread_id, turn_type="development", author=d.model or "model",
            text=d.text, record_id=d.id,
        )
        return d

    def get_development(self, development_id: str) -> Development | None:
        return self.devs.get(development_id)

    def approve(self, development_id: str) -> Development:
        d = self.devs[development_id]
        if not d.grounded:
            raise ValueError("Cannot approve an ungrounded development.")
        d = d.model_copy(update={"status": "approved"})
        self.devs[development_id] = d
        return d

    def reject(self, development_id: str) -> Development:
        d = self.devs[development_id].model_copy(update={"status": "rejected"})
        self.devs[development_id] = d
        return d


class FakeTerms:
    def __init__(self) -> None:
        self.terms: list[Term] = []

    def add_term(self, *, canonical, definition, author, term_type="concept",
                 surface_forms=(), related_terms=(), source_refs=(),
                 gematria=None, sacred=False) -> Term:
        t = Term(  # blank author raises ValidationError (a ValueError) → 400
            id=f"term-{len(self.terms) + 1}", canonical=canonical, definition=definition,
            author=author, term_type=term_type, surface_forms=list(surface_forms),
            related_terms=list(related_terms), source_refs=list(source_refs),
            gematria=gematria, sacred=sacred,
        )
        self.terms.append(t)
        return t

    def list_terms(self) -> list[Term]:
        return self.terms


class _StubRetract:
    def retract(self, target, *, author, reason):  # noqa: ANN001, ANN201
        raise NotImplementedError

    def list_retractions(self):  # noqa: ANN201
        return []


class _StubStats:
    def collect(self):  # noqa: ANN201
        from maayan.stats.models import Stats

        return Stats(total_chunks=0)


class _StubCompose:
    def list_compositions(self):  # noqa: ANN201
        return []


def _client(*, rag_grounded: bool = True, dev_grounded: bool = True) -> TestClient:
    rag = FakeRag(grounded=rag_grounded)
    capture = FakeCapture()
    threads = ThreadService(ThreadStore(":memory:"), FakeClock())
    develop = FakeDevelop(threads, grounded=dev_grounded)
    terms = FakeTerms()
    app = create_app(  # type: ignore[arg-type]
        rag, capture, threads, develop, terms, _StubRetract(), _StubStats(), _StubCompose(),
        context_turns=6,
    )
    return TestClient(app)


def _new_thread(client: TestClient, title: str = "topic") -> str:
    return client.post("/threads", json={"title": title}).json()["id"]


def test_create_and_list_threads() -> None:
    client = _client()
    r = client.post("/threads", json={"title": "ahava b'ta'anugim"})
    assert r.status_code == 200
    tid = r.json()["id"]
    assert r.json()["title"] == "ahava b'ta'anugim"
    assert any(t["id"] == tid for t in client.get("/threads").json())


def test_get_thread_404() -> None:
    assert _client().get("/threads/nope").status_code == 404


def test_ask_in_thread_grounded_appends_turn_and_badges_source() -> None:
    client = _client()
    tid = _new_thread(client)
    r = client.post(f"/threads/{tid}/ask", json={"question": "מהי בחירה"})
    assert r.status_code == 200
    data = r.json()
    assert data["grounded"] is True
    assert data["sources"][0]["source"] == "derived"  # badged distinctly
    turns = client.get(f"/threads/{tid}").json()["turns"]
    assert turns[-1]["turn_type"] == "ask"


def test_ask_in_thread_refusal_passes_through() -> None:
    client = _client(rag_grounded=False)
    tid = _new_thread(client)
    data = client.post(f"/threads/{tid}/ask", json={"question": "baseball"}).json()
    assert data["grounded"] is False


def test_ask_in_missing_thread_404() -> None:
    assert _client().post("/threads/nope/ask", json={"question": "x"}).status_code == 404


def test_seed_then_thread_shows_seed_with_directive() -> None:
    client = _client()
    tid = _new_thread(client)
    r = client.post(f"/threads/{tid}/seed",
                    json={"author": "R. G", "body": "seed body", "directive": "find the hint"})
    assert r.status_code == 200
    cid = r.json()["contribution_id"]
    seed_turns = [t for t in client.get(f"/threads/{tid}").json()["turns"] if t["is_seed"]]
    assert seed_turns and seed_turns[0]["directive"] == "find the hint"
    assert seed_turns[0]["record_id"] == cid


def test_seed_blank_author_returns_400() -> None:
    client = _client()
    tid = _new_thread(client)
    r = client.post(f"/threads/{tid}/seed", json={"author": "  ", "body": "x"})
    assert r.status_code == 400


def test_develop_seed_then_thread_shows_proposal_enriched() -> None:
    client = _client()
    tid = _new_thread(client)
    cid = client.post(f"/threads/{tid}/seed",
                      json={"author": "R. G", "body": "b", "directive": "d"}).json()[
        "contribution_id"]
    r = client.post(f"/threads/{tid}/develop", json={"seed_id": cid})
    assert r.status_code == 200
    dev = r.json()
    assert dev["grounded"] is True and dev["status"] == "proposed"
    assert dev["cited_refs"] == ["Tanya 1:6"]
    # The development turn is rendered with its status + citations (drives Approve/Reject).
    dev_turns = [t for t in client.get(f"/threads/{tid}").json()["turns"]
                 if t["turn_type"] == "development"]
    assert dev_turns and dev_turns[0]["status"] == "proposed"
    assert dev_turns[0]["cited_refs"] == ["Tanya 1:6"]
    assert dev_turns[0]["record_id"] == dev["id"]


def test_develop_missing_seed_404() -> None:
    client = _client()
    tid = _new_thread(client)
    assert client.post(f"/threads/{tid}/develop", json={"seed_id": "nope"}).status_code == 404


def _seed_and_develop(client: TestClient, tid: str) -> str:
    cid = client.post(f"/threads/{tid}/seed",
                      json={"author": "R. G", "body": "b", "directive": "d"}).json()[
        "contribution_id"]
    return client.post(f"/threads/{tid}/develop", json={"seed_id": cid}).json()["id"]


def test_approve_development() -> None:
    client = _client()
    tid = _new_thread(client)
    did = _seed_and_develop(client, tid)
    r = client.post(f"/developments/{did}/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


def test_reject_development() -> None:
    client = _client()
    tid = _new_thread(client)
    did = _seed_and_develop(client, tid)
    assert client.post(f"/developments/{did}/reject").json()["status"] == "rejected"


def test_approve_refusal_returns_400() -> None:
    client = _client(dev_grounded=False)
    tid = _new_thread(client)
    did = _seed_and_develop(client, tid)
    assert client.post(f"/developments/{did}/approve").status_code == 400


def test_connect_sources_links_refs_across_books() -> None:
    # The "Connect these sources" UX: ask in a thread → use the returned session →
    # annotate a connection whose linked_refs span Tanya + Likutei Torah.
    client = _client()
    tid = _new_thread(client)
    sid = client.post(f"/threads/{tid}/ask", json={"question": "אהבת עולם"}).json()["session_id"]
    refs = ["Tanya, Part I; Likkutei Amarim 18", "Likutei Torah, פרשה ויקרא, א א"]
    r = client.post("/annotate", json={
        "session_id": sid, "author": "R. Ginsburgh", "kind": "connection",
        "body": "אהבת עולם בתניא היא היסוד לאהבה בתענוגים בלקוטי תורה", "linked_refs": refs,
    })
    assert r.status_code == 200
    assert r.json()["linked_refs"] == refs  # the cross-text bridge is preserved intact


def test_index_html_has_connect_affordance() -> None:
    html = _client().get("/").text
    for marker in ("connectSelected", "srcpick", "Connect selected"):
        assert marker in html, f"missing connect-sources markup: {marker}"


def test_add_and_list_term() -> None:
    client = _client()
    r = client.post("/terms", json={
        "canonical": 'ע"ב (Name of 72)', "definition": "the Ab expansion of Havayah",
        "author": "R. Ginsburgh", "term_type": "expansion",
        "surface_forms": ['ע"ב', "עב"], "gematria": 72,
    })
    assert r.status_code == 200
    assert r.json()["term_type"] == "expansion"
    listed = client.get("/terms").json()
    assert any(t["canonical"].startswith('ע"ב') for t in listed)


def test_add_term_blank_author_returns_400() -> None:
    client = _client()
    r = client.post("/terms", json={"canonical": "x", "definition": "y", "author": "  "})
    assert r.status_code == 400
