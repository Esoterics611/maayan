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
        self, session_id: str, *, author, kind, body, linked_refs: Sequence[str] = (),
        move=None, directive=None, opens_aspect=False,
    ) -> Annotation:
        if kind not in self.allowed_kinds:
            raise ValueError(f"Unknown kind {kind!r}")
        a = Annotation(
            id="ann-1", session_id=session_id, timestamp=NOW, author=author, kind=kind,
            body=body, linked_refs=list(linked_refs), move=move,
            directive=directive, opens_aspect=opens_aspect,
        )
        self.annotations.append(a)
        return a

    def get_session(self, session_id: str) -> Session | None:
        return self.sessions.get(session_id)

    def get_annotations(self, session_id: str) -> list[Annotation]:
        return [a for a in self.annotations if a.session_id == session_id]


class _StubThreads:
    """No-op thread service; the one-shot routes below don't touch it."""

    def list_threads(self):  # noqa: ANN201
        return []

    def get_thread_with_turns(self, thread_id):  # noqa: ANN001, ANN201
        return None


class _StubDevelop:
    def get_development(self, development_id):  # noqa: ANN001, ANN201
        return None


class _StubTerms:
    def list_terms(self):  # noqa: ANN201
        return []


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


def _client(grounded: bool = True) -> tuple[TestClient, FakeRag, FakeCapture]:
    rag = FakeRag(_answer(grounded))
    capture = FakeCapture()
    app = create_app(  # type: ignore[arg-type]
        rag, capture, _StubThreads(), _StubDevelop(), _StubTerms(), _StubRetract(),
        _StubStats(), _StubCompose(),
    )
    return TestClient(app), rag, capture


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
    r = client.post(
        "/annotate",
        json={"session_id": "sess-1", "body": "x", "kind": "bogus", "author": "R. G"},
    )
    assert r.status_code == 400


def test_annotate_missing_author_rejected() -> None:
    client, _, _ = _client()
    client.post("/ask", json={"question": "q"})
    # No author at all → request-model validation (422).
    missing = client.post(
        "/annotate", json={"session_id": "sess-1", "body": "x", "kind": "connection"}
    )
    assert missing.status_code == 422
    # Blank author → model validator raises, surfaced as 400.
    blank = client.post(
        "/annotate",
        json={"session_id": "sess-1", "body": "x", "kind": "connection", "author": "  "},
    )
    assert blank.status_code == 400


def test_annotate_seed_passes_directive_and_opens_aspect() -> None:
    client, _, capture = _client()
    client.post("/ask", json={"question": "מהי בחירה"})
    r = client.post("/annotate", json={
        "session_id": "sess-1", "body": "ahava b'ta'anugim framework", "kind": "connection",
        "author": "R. G", "opens_aspect": True, "directive": "find the hint in Tanya",
    })
    assert r.status_code == 200
    assert r.json()["opens_aspect"] is True
    saved = capture.annotations[0]
    assert saved.opens_aspect is True
    assert saved.directive == "find the hint in Tanya"


def test_get_session() -> None:
    client, _, _ = _client()
    client.post("/ask", json={"question": "מהי בחירה"})
    r = client.get("/session/sess-1")
    assert r.status_code == 200
    assert r.json()["id"] == "sess-1"
    assert client.get("/session/missing").status_code == 404


# -- PWA shell (Prompt 23) ---------------------------------------------------
def test_manifest_served() -> None:
    client, _, _ = _client()
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/manifest+json")
    body = r.json()
    assert body["name"].startswith("maayan")
    assert any(icon["sizes"] == "512x512" for icon in body["icons"])


def test_service_worker_served() -> None:
    client, _, _ = _client()
    r = client.get("/sw.js")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/javascript")
    # Served from the root so its scope can cover the whole app.
    assert r.headers["service-worker-allowed"] == "/"
    assert "addEventListener" in r.text


def test_icons_served() -> None:
    client, _, _ = _client()
    for path in ("/icon-192.png", "/icon-512.png"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert r.headers["content-type"] == "image/png"


def test_index_references_pwa_and_mobile_chrome() -> None:
    client, _, _ = _client()
    html = client.get("/").text
    assert "/manifest.webmanifest" in html
    assert "/sw.js" in html
    assert 'id="tabbar"' in html  # the bottom mobile nav
    assert 'id="menuBtn"' in html  # the drawer hamburger


def test_voice_dictation_controls_present() -> None:
    # Prompt 24 is browser-API UI; we assert the affordances + fallback branch ship,
    # not that real speech recognition runs.
    client, _, _ = _client()
    html = client.get("/").text
    # A mic button next to each static capture field, plus the language toggle.
    for el_id in ('id="micQ"', 'id="micSeed"', 'id="micTerm"', 'id="voiceLang"'):
        assert el_id in html, el_id
    # The dynamic connection field gets a mic via the reusable builder.
    assert "mkMic" in html
    # Web Speech happy path + graceful MediaRecorder fallback both exist.
    assert "webkitSpeechRecognition" in html
    assert "MediaRecorder" in html
    # Regression: dictation must listen continuously and auto-restart through pauses,
    # not stop after the first phrase (continuous=false captured only the first word).
    assert "rec.continuous = true" in html
    assert "rec.continuous = false" not in html
    assert "rec.start()" in html  # the onend auto-restart keeps the session alive
    # The Prompt 26 server path is stubbed honestly, not half-wired.
    assert "server transcription" in html


def test_beyond_typing_controls_present() -> None:
    # Prompt 30 is browser-API UI (OCR upload, selection menu, inbox overlay); assert
    # the affordances + wiring ship, not that real OCR/selection runs.
    client, _, _ = _client()
    html = client.get("/").text
    # OCR camera buttons next to the seed + term capture fields, plus the reusable builder.
    for el_id in ('id="ocrSeed"', 'id="ocrTerm"', 'id="inboxBtn"', 'id="selMenu"'):
        assert el_id in html, el_id
    assert "/api/ocr" in html and "mkOcr" in html
    # Highlight-to-act wires the EXISTING flows via a selection menu.
    for act in ('data-act="connect"', 'data-act="term"', 'data-act="seed"'):
        assert act in html, act
    # Quick-capture inbox talks to the inbox API and offers move-to-thread.
    assert "/api/inbox" in html and "openInbox" in html and "moveThread" in html


def test_reading_experience_controls_present() -> None:
    # Prompt 29 reader/library + reading modes ship in the page (browser-driven UI).
    client, _, _ = _client()
    html = client.get("/").text
    assert "openReader" in html        # source-in-context reader
    assert "openLibrary" in html       # sefer browser (Library tab)
    assert "maayan.readmode" in html   # reading mode persisted in localStorage
    assert "cycleReadMode" in html
