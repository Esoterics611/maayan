"""Tests for Prompt 37 — the inquiry queue (שאלות לרב).

AskLog telemetry, the four generators from seeded data, transparent ranking,
store dedupe + answer/dismiss transitions, and the UI routes. All stores are
in-memory; time runs on FakeClock; no models, no network.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient

from maayan.clock import FakeClock
from maayan.config import Settings
from maayan.generate.rag import Answer
from maayan.graph.models import RefEndpoint, Relation
from maayan.graph.store import GraphStore
from maayan.inquiry.generate import (
    contradictions,
    generate_inquiries,
    low_evidence_relations,
    rank,
    refused_questions,
    undergrounded_terms,
)
from maayan.inquiry.log import AskLog
from maayan.inquiry.models import RefusedQuestionPayload, inquiry_id
from maayan.inquiry.store import InquiryStore
from maayan.lexicon.populate import TermSuggestion
from maayan.lexicon.suggestions import SuggestionStore
from maayan.ui.app import create_app

T0 = datetime(2026, 7, 1, tzinfo=UTC)
TANYA = "Tanya, Part I; Likkutei Amarim 18"
TORAH_OHR = "Torah Ohr, Vayera 14a"


def _settings() -> Settings:
    return Settings(_env_file=None)


def _relation(
    *,
    rel_type: str = "connects",
    evidence: str = "expert",
    confidence: float = 1.0,
    author: str = "R. Ginsburgh",
    subject: str = TANYA,
    obj: str = TORAH_OHR,
) -> Relation:
    return Relation.make(
        subject=RefEndpoint(ref=subject), object=RefEndpoint(ref=obj),
        rel_type=rel_type, evidence=evidence, confidence=confidence,  # type: ignore[arg-type]
        status="approved", author=author, created_at=T0,
    )


# -- AskLog --------------------------------------------------------------------

def test_ask_log_round_trips_and_filters_refusals() -> None:
    log = AskLog(":memory:", FakeClock(T0))
    log.record(question="מהו ביטול?", refused=True, top_score=0.2, session_id="s1")
    log.record(question="מהי אהבה?", refused=False, top_score=0.8, user="rav")

    refused = log.list_refused()
    assert [r.question for r in refused] == ["מהו ביטול?"]
    assert refused[0].session_id == "s1" and refused[0].timestamp == T0
    assert log.count() == 2 and log.count(refused=True) == 1


# -- ranking (transparent math) --------------------------------------------------

def test_priority_is_the_printed_sum_of_its_parts() -> None:
    clock = FakeClock(T0)
    priority, parts = rank(
        "refused_question", count=3, last_seen=T0, clock=clock, settings=_settings()
    )
    # The plan's own example: 3×refusals(2.4) + recency(1.0) + kind(5.0) = 8.4.
    assert parts == {"count": 2.4, "recency": 1.0, "kind": 5.0}
    assert priority == pytest.approx(8.4)


def test_recency_decays_with_age_and_breaks_ties() -> None:
    clock = FakeClock(T0 + timedelta(days=7))  # one half-life later
    _, parts = rank("contradiction", count=1, last_seen=T0, clock=clock, settings=_settings())
    assert parts["recency"] == pytest.approx(0.5)


# -- generators -------------------------------------------------------------------

def test_refused_questions_cluster_by_folded_text() -> None:
    clock = FakeClock(T0)
    log = AskLog(":memory:", clock)
    # Three refusals, two of them the same question up to quotes/nikkud folding.
    log.record(question="מהו ביטול?", refused=True, top_score=0.1)
    log.record(question='מהו "ביטול"?', refused=True, top_score=0.15)
    log.record(question="מהי הוראת הבעש\"ט על צמצום?", refused=True, top_score=0.2)
    log.record(question="שאלה שנענתה", refused=False, top_score=0.9)

    items = refused_questions(log, clock, _settings())

    assert len(items) == 2
    by_count = sorted(items, key=lambda i: -i.priority)
    top = by_count[0]
    assert top.kind == "refused_question"
    payload = top.payload
    assert isinstance(payload, RefusedQuestionPayload)
    assert payload.count == 2  # the cluster
    assert len(payload.questions) == 2  # distinct phrasings preserved
    assert "המערכת סירבה" in top.title


def test_undergrounded_terms_come_from_the_deny_list_only() -> None:
    clock = FakeClock(T0)
    store = SuggestionStore(":memory:")
    store.create(TermSuggestion(
        id="s-denied", canonical="כתר", supported=False, status="pending",
        model="free-model", unsupported_claims=["לא נמצא בסיס"], created_at=T0,
    ))
    store.create(TermSuggestion(  # grounded fine → normal review queue, not an inquiry
        id="s-ok", canonical="חכמה", supported=True, status="pending", created_at=T0,
    ))
    store.create(TermSuggestion(  # already human-rejected → resolved
        id="s-rejected", canonical="בינה", supported=False, status="rejected", created_at=T0,
    ))

    items = undergrounded_terms(store, clock, _settings())

    assert len(items) == 1
    assert "כתר" in items[0].title
    assert items[0].payload.kind == "undergrounded_term"


def test_low_evidence_relations_flags_bootstrap_and_low_confidence() -> None:
    clock = FakeClock(T0)
    graph = GraphStore(":memory:")
    graph.save_relation(_relation(evidence="derived_bootstrap", confidence=0.6,
                                  author="bootstrap:free"))
    graph.save_relation(_relation(obj="Torah Ohr, Miketz 5:11", confidence=0.5))  # low conf
    graph.save_relation(_relation(obj="Torah Ohr, Bo 1:1"))  # strong: not flagged
    proposed = Relation.make(  # not approved → invisible to the generator
        subject=RefEndpoint(ref=TANYA), object=RefEndpoint(ref="Torah Ohr, Yitro 2:2"),
        rel_type="connects", evidence="derived_bootstrap", confidence=0.6,
        status="proposed", author="bootstrap:free", created_at=T0,
    )
    graph.save_relation(proposed)

    items = low_evidence_relations(graph, clock, _settings())

    assert len(items) == 2
    assert all(i.kind == "low_evidence_relation" for i in items)
    assert any("bootstrap" in i.title for i in items)


def test_contradictions_surface_argues_with_vs_agreeing_edge() -> None:
    clock = FakeClock(T0)
    graph = GraphStore(":memory:")
    graph.save_relation(_relation(rel_type="argues_with", author="R. A"))
    graph.save_relation(_relation(rel_type="explains", author="R. B"))
    graph.save_relation(_relation(rel_type="quotes", author="R. C"))  # not an agreement claim
    # A different pair with no conflict.
    graph.save_relation(_relation(rel_type="explains", subject="Tanya 3", obj="Tanya 4"))

    items = contradictions(graph, clock, _settings())

    assert len(items) == 1
    item = items[0]
    assert item.kind == "contradiction"
    assert "argues_with" in item.title and "explains" in item.title
    assert item.payload.kind == "contradiction"
    assert set(item.payload.authors) == {"R. A", "R. B"}  # type: ignore[union-attr]


# -- orchestrator: dedupe + terminal ids stay closed --------------------------------

class Deps(NamedTuple):
    store: InquiryStore
    clock: FakeClock
    log: AskLog
    graph: GraphStore
    suggestions: SuggestionStore


def _deps() -> Deps:
    clock = FakeClock(T0)
    return Deps(
        InquiryStore(":memory:", clock), clock, AskLog(":memory:", clock),
        GraphStore(":memory:"), SuggestionStore(":memory:"),
    )


def test_generate_is_idempotent_on_open_items() -> None:
    d = _deps()
    d.log.record(question="מהו ביטול?", refused=True, top_score=0.1)
    d.graph.save_relation(_relation(evidence="derived_bootstrap", confidence=0.6,
                                    author="bootstrap:free"))

    first = generate_inquiries(d.store, d.clock, _settings(),
                               ask_log=d.log, suggestions=d.suggestions, graph=d.graph)
    second = generate_inquiries(d.store, d.clock, _settings(),
                                ask_log=d.log, suggestions=d.suggestions, graph=d.graph)

    assert first.created == 2
    assert second.created == 0 and second.refreshed == 2
    assert len(d.store.list(status="open")) == 2


def test_dismissed_items_are_never_resurrected_and_refusal_count_refreshes() -> None:
    d = _deps()
    d.log.record(question="מהו ביטול?", refused=True, top_score=0.1)
    generate_inquiries(d.store, d.clock, _settings(), ask_log=d.log)
    item = d.store.list(status="open")[0]
    d.store.mark_dismissed(item.id)

    # The same question refused again → regeneration must NOT reopen the id.
    d.log.record(question="מהו ביטול?", refused=True, top_score=0.1)
    report = generate_inquiries(d.store, d.clock, _settings(), ask_log=d.log)

    assert report.created == 0 and report.skipped_terminal == 1
    assert d.store.list(status="open") == []

    # A different refusal still creates a new item whose count refreshes on regen.
    d.log.record(question="שאלה חדשה לגמרי", refused=True, top_score=0.1)
    generate_inquiries(d.store, d.clock, _settings(), ask_log=d.log)
    d.log.record(question="שאלה חדשה לגמרי", refused=True, top_score=0.1)
    generate_inquiries(d.store, d.clock, _settings(), ask_log=d.log)
    fresh = d.store.list(status="open")[0]
    assert isinstance(fresh.payload, RefusedQuestionPayload) and fresh.payload.count == 2


def test_answer_and_dismiss_transitions_record_resolution() -> None:
    d = _deps()
    d.log.record(question="מהו ביטול?", refused=True, top_score=0.1)
    generate_inquiries(d.store, d.clock, _settings(), ask_log=d.log)
    item = d.store.list(status="open")[0]

    answered = d.store.mark_answered(item.id, resolution="expert chunk exp_9f2")
    assert answered.status == "answered"
    assert answered.resolution == "expert chunk exp_9f2"
    assert answered.answered_at == T0
    with pytest.raises(ValueError, match="already"):
        d.store.mark_answered(item.id, resolution="again")
    with pytest.raises(ValueError, match="No inquiry"):
        d.store.mark_dismissed("missing")
    assert d.store.harvest_today() == {"refused_question": 1}


def test_priority_orders_the_open_list() -> None:
    d = _deps()
    for _ in range(3):
        d.log.record(question="מהו ביטול?", refused=True, top_score=0.1)
    d.graph.save_relation(_relation(evidence="derived_bootstrap", confidence=0.6,
                                    author="bootstrap:free"))
    generate_inquiries(d.store, d.clock, _settings(), ask_log=d.log, graph=d.graph)

    kinds = [i.kind for i in d.store.list(status="open")]
    assert kinds == ["refused_question", "low_evidence_relation"]  # 8.4 before 4.3


# -- the full path: an ask's refusal becomes an open inquiry -------------------------

class _RefusingRag:
    def ask(self, question: str, **kwargs: object) -> Answer:
        return Answer(question=question, text="refused", grounded=False,
                      cited_refs=[], sources=[], relevance=0.12)


class _FakeSession(NamedTuple):
    id: str


class _FakeCapture:
    def start_session(self, answer: Answer) -> _FakeSession:
        return _FakeSession(id="sess-1")


class _Stub:
    def __getattr__(self, _name: str):  # noqa: ANN204
        raise AssertionError("inquiry routes must not touch unrelated services")


def _client(d: Deps) -> TestClient:
    app = create_app(  # type: ignore[arg-type]
        _RefusingRag(), _FakeCapture(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(),
        ask_log=d.log, inquiries=d.store, graph=d.graph, suggestions=d.suggestions,
        settings=_settings(),
    )
    return TestClient(app)


def test_ui_refused_ask_lands_in_the_log_and_becomes_an_inquiry() -> None:
    d = _deps()
    client = _client(d)

    resp = client.post("/ask", json={"question": "מהו ביטול במקום?"})
    assert resp.status_code == 200 and resp.json()["grounded"] is False
    assert d.log.count(refused=True) == 1
    record = d.log.list_refused()[0]
    assert record.session_id == "sess-1" and record.top_score == pytest.approx(0.12)

    generated = client.post("/api/inquiries/generate")
    assert generated.status_code == 200 and generated.json()["created"] == 1

    listed = client.get("/api/inquiries").json()
    assert len(listed["items"]) == 1
    card = listed["items"][0]
    assert card["kind"] == "refused_question"
    assert "ביטול במקום" in card["title"]
    assert card["priority_parts"]  # the math is on the card


def test_ui_answer_and_dismiss_routes() -> None:
    d = _deps()
    client = _client(d)
    client.post("/ask", json={"question": "מהו ביטול?"})
    client.post("/api/inquiries/generate")
    item_id = client.get("/api/inquiries").json()["items"][0]["id"]

    answered = client.post(f"/api/inquiries/{item_id}/answer",
                           json={"resolution": "relation r-1"})
    assert answered.status_code == 200
    assert answered.json()["status"] == "answered"
    assert client.get("/api/inquiries").json()["items"] == []
    assert client.get("/api/inquiries").json()["harvest"] == {"refused_question": 1}

    again = client.post(f"/api/inquiries/{item_id}/dismiss")
    assert again.status_code == 400  # terminal transitions are final

    # Kind filter mirrors `maayan inquiries --kind`.
    assert client.get("/api/inquiries", params={"kind": "contradiction"}).json()["items"] == []


def test_ui_routes_are_inert_without_wiring() -> None:
    app = create_app(  # type: ignore[arg-type]
        _RefusingRag(), _FakeCapture(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(),
    )
    client = TestClient(app)
    assert client.post("/ask", json={"question": "בלי טלמטריה"}).status_code == 200  # no crash
    assert client.get("/api/inquiries").status_code == 503


def test_inquiry_ids_are_deterministic() -> None:
    assert inquiry_id("refused_question", "key") == inquiry_id("refused_question", "key")
    assert inquiry_id("refused_question", "key") != inquiry_id("contradiction", "key")
