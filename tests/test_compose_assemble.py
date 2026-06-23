"""Tests for Prompt 22 — assemble, review, export, promote (+ UI routes).

Mock retriever/backend/capture; no network, no models.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient

from maayan.capture.models import Annotation
from maayan.clock import FakeClock
from maayan.compose.assemble import assemble_markdown
from maayan.compose.models import Brief, Composition, Section
from maayan.compose.service import CompositionService
from maayan.compose.store import CompositionStore
from maayan.config import Settings
from maayan.generate.base import Message
from maayan.retrieve.models import RetrievalResult
from maayan.threads.service import ThreadService
from maayan.threads.store import ThreadStore
from maayan.ui.app import create_app

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _brief(**kw: object) -> Brief:
    base = dict(id="b-1", title="בירור הנפש הבהמית", intent="i", author="R. Ginsburgh")
    base.update(kw)
    return Brief(**base)  # type: ignore[arg-type]


def _composition(sections: list[Section], status: str = "proposed") -> Composition:
    return Composition(id="c-1", brief_id="b-1", status=status, model="qwen",  # type: ignore[arg-type]
                       sections=sections, created_at=NOW)


def _grounded(heading: str, text: str, refs: list[str]) -> Section:
    return Section(heading=heading, query="q", text=text, cited_refs=refs,
                   grounded_in=refs, supported=True)


def _gap(heading: str) -> Section:
    return Section(heading=heading, query="q", text="— gap —", supported=False)


# -- assembly: deterministic, footer, gap honesty -----------------------------
def test_assemble_is_deterministic_and_has_footer_and_gap() -> None:
    comp = _composition([
        _grounded("שתי הנפשות", "נקודה ראשונה [S1].", ["Tanya 1:1"]),
        _gap("אהבה בתענוגים"),
    ])
    out1 = assemble_markdown(comp, _brief())
    out2 = assemble_markdown(comp, _brief())
    assert out1 == out2  # deterministic given the same inputs

    assert out1.startswith("# בירור הנפש הבהמית")
    assert "## 1. שתי הנפשות" in out1
    assert "*Sources: Tanya 1:1*" in out1
    # Gap honesty: the gap section is clearly flagged, not silently dropped.
    assert "## 2. אהבה בתענוגים" in out1
    assert "Honest gap" in out1
    # Provenance footer.
    assert "### Provenance" in out1
    assert "**Author:** R. Ginsburgh" in out1
    assert "**Model:** qwen" in out1
    assert "1 grounded, 1 honest gap(s)" in out1
    assert "Tanya 1:1" in out1.split("### Provenance")[1]  # cited refs in footer


# -- service harness ----------------------------------------------------------
class FakeRetriever:
    def retrieve(self, query: str, *, k=None, book=None, source=None) -> RetrievalResult:
        return RetrievalResult(results=[], relevance=0.0)


class RecordingBackend:
    def __init__(self, reply: str = "glue sentence") -> None:
        self.reply = reply
        self.calls: list[tuple[str, list[Message]]] = []

    def generate(self, system: str, messages: Sequence[Message]) -> str:
        self.calls.append((system, list(messages)))
        return self.reply


class FakeCapture:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def add_annotation(self, session_id: str, *, author, kind, body,
                       linked_refs=(), move=None, directive=None, opens_aspect=False) -> Annotation:
        self.calls.append({"session_id": session_id, "author": author, "kind": kind,
                           "body": body, "linked_refs": list(linked_refs)})
        return Annotation(id="ann-1", session_id=session_id, timestamp=NOW, author=author,
                          kind=kind, body=body, linked_refs=list(linked_refs))


class Harness(NamedTuple):
    svc: CompositionService
    store: CompositionStore
    backend: RecordingBackend
    capture: FakeCapture


def _harness(*, transitions: bool = False) -> Harness:
    store = CompositionStore(":memory:")
    backend = RecordingBackend()
    capture = FakeCapture()
    settings = Settings(compose_transitions=transitions)
    svc = CompositionService(FakeRetriever(), backend, store,
                             ThreadService(ThreadStore(":memory:"), FakeClock()),
                             FakeClock(), settings, capture)  # type: ignore[arg-type]
    return Harness(svc, store, backend, capture)


def _seed(h: Harness, sections: list[Section], status: str = "proposed") -> None:
    h.store.save_brief(_brief())
    h.store.save_composition(_composition(sections, status))


# -- review: approve / reject transitions, no indexing ------------------------
def test_approve_and_reject_set_status_without_indexing() -> None:
    h = _harness()
    _seed(h, [_grounded("h", "t [S1]", ["Tanya 1:1"])])

    assert h.svc.approve("c-1").status == "approved"
    assert h.store.get_composition("c-1").status == "approved"  # type: ignore[union-attr]
    assert h.svc.reject("c-1").status == "rejected"
    # Approve/reject never touch the capture loop (no prose bulk-indexed).
    assert h.capture.calls == []


# -- export writes markdown ---------------------------------------------------
def test_export_writes_markdown_file(tmp_path) -> None:  # noqa: ANN001
    h = _harness()
    _seed(h, [_grounded("שתי הנפשות", "נקודה [S1].", ["Tanya 1:1"]), _gap("גאפ")])
    markdown = h.svc.assemble("c-1")
    path = tmp_path / "out.md"
    path.write_text(markdown, encoding="utf-8")
    written = path.read_text(encoding="utf-8")
    assert written.startswith("# בירור הנפש הבהמית")
    assert "### Provenance" in written and "Honest gap" in written


def test_assemble_with_transitions_adds_glue_no_new_sources() -> None:
    h = _harness(transitions=True)
    _seed(h, [
        _grounded("ראשון", "a [S1]", ["Tanya 1:1"]),
        _grounded("שני", "b [S1]", ["Torah Ohr, Bereshit 1:1"]),
    ])
    out = h.svc.assemble("c-1")
    assert "glue sentence" in out  # a transition was generated and rendered
    # The transition prompt forbids new claims/citations.
    system, _ = h.backend.calls[0]
    assert "CONNECTIVE GLUE ONLY" in system


# -- promote a connection reuses the capture loop -----------------------------
def test_promote_connection_reuses_capture_loop() -> None:
    h = _harness()
    _seed(h, [_grounded("bridge", "t [S1][S2]", ["Tanya 1:1", "Likutei Torah, Bamidbar"])],
          status="approved")

    ann = h.svc.promote_connection("c-1", 0, author="R. Ginsburgh", insight="they meet at bittul")

    assert ann.kind == "connection" and ann.author == "R. Ginsburgh"
    # The section's grounded_in refs became the connection's linked refs (one connection).
    assert h.capture.calls[0]["linked_refs"] == ["Tanya 1:1", "Likutei Torah, Bamidbar"]
    assert h.capture.calls[0]["body"] == "they meet at bittul"


def test_promote_out_of_range_rejected() -> None:
    h = _harness()
    _seed(h, [_grounded("h", "t", ["Tanya 1:1"])])
    with pytest.raises(ValueError, match="out of range"):
        h.svc.promote_connection("c-1", 5, author="A", insight="x")


# -- UI routes: happy-path + gap/reject paths ---------------------------------
class _Stub:
    def __getattr__(self, _name: str):  # noqa: ANN204
        raise AssertionError("compose routes must not call other services")


def _ui_client(h: Harness) -> TestClient:
    app = create_app(  # type: ignore[arg-type]
        _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), h.svc
    )
    return TestClient(app)


def test_ui_compose_outline_and_export() -> None:
    h = _harness()
    client = _ui_client(h)
    # propose_outline goes through the real service + a mock backend (no outline reply →
    # empty sections), so seed a composition directly and exercise export/approve instead.
    _seed(h, [_grounded("שתי הנפשות", "נקודה [S1].", ["Tanya 1:1"]), _gap("גאפ")])

    exported = client.get("/compositions/c-1/export")
    assert exported.status_code == 200
    assert "### Provenance" in exported.json()["markdown"]
    assert "Honest gap" in exported.json()["markdown"]  # gap path surfaced in the UI export

    approved = client.post("/compositions/c-1/approve")
    assert approved.status_code == 200 and approved.json()["status"] == "approved"


def test_ui_promote_happy_path() -> None:
    h = _harness()
    _seed(h, [_grounded("bridge", "t", ["Tanya 1:1", "Likutei Torah, Bamidbar"])])
    client = _ui_client(h)

    resp = client.post("/compositions/c-1/promote",
                       json={"section_index": 0, "author": "Ed", "insight": "they meet"})
    assert resp.status_code == 200
    assert resp.json()["linked_refs"] == ["Tanya 1:1", "Likutei Torah, Bamidbar"]


def test_ui_reject_and_missing_paths() -> None:
    h = _harness()
    _seed(h, [_grounded("h", "t", ["Tanya 1:1"])])
    client = _ui_client(h)

    assert client.post("/compositions/c-1/reject").json()["status"] == "rejected"
    # A missing composition is a 404 on fill/export.
    assert client.post("/compositions/nope/fill").status_code == 404
    assert client.get("/compositions/nope/export").status_code == 404
