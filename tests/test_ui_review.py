"""Tests for the Review workbench + Gold panel + verify routes (UI redesign Phase 1).

Wiring only, per house rules: every service is a fake; no network, no models,
no real Qdrant. The queue must be honest about absent wiring (empty lists, not
errors) and the gates must stay attributed.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from maayan.develop.models import Development
from maayan.eval.captured import CapturedExample, CapturedOrigin
from maayan.graph.models import ConceptEndpoint, RefEndpoint, Relation
from maayan.inbox.models import InboxItem
from maayan.inquiry.models import InquiryItem, RefusedQuestionPayload
from maayan.retrieve.models import RetrievalResult, SearchResult
from maayan.ui.app import create_app

from .test_ui import (
    FakeCapture,
    FakeRag,
    _answer,
    _StubCompose,
    _StubRetract,
    _StubStats,
    _StubTerms,
    _StubThreads,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _development(status: str = "proposed") -> Development:
    return Development(
        id="dev-1", thread_id="t-1", seed_id="seed-1", author="R. G", timestamp=NOW,
        model="m", status=status, grounded=True, text="פיתוח [S1]",
        cited_refs=["Tanya 1:1"], grounded_in=["Tanya 1:1"],
    )


class FakeDevelop:
    def __init__(self, devs: list[Development] | None = None) -> None:
        self.devs = devs or []

    def get_development(self, development_id: str) -> Development | None:
        return next((d for d in self.devs if d.id == development_id), None)

    def list_developments(self, *, status: str | None = None) -> list[Development]:
        return [d for d in self.devs if status is None or d.status == status]


def _relation(status: str = "proposed", evidence: str = "derived_bootstrap") -> Relation:
    return Relation(
        id="rel-1", subject=RefEndpoint(ref="Tanya 1:1"),
        object=ConceptEndpoint(concept_id="c-1"), rel_type="parallels",
        evidence=evidence, confidence=0.8, status=status, author="drafter",
        note="דמיון לשוני", created_at=NOW,
    )


class FakeGraph:
    def __init__(self, relations: list[Relation] | None = None) -> None:
        self.relations = {r.id: r for r in (relations or [])}

    def list_relations(self, *, status=None, rel_type=None, evidence=None, limit=None):  # noqa: ANN001, ANN201
        return [r for r in self.relations.values() if status is None or r.status == status]

    def get_relation(self, relation_id: str) -> Relation | None:
        return self.relations.get(relation_id)

    def get_concept(self, concept_id):  # noqa: ANN001, ANN201
        return None  # label falls back to the concept id

    def approve(self, relation_id: str, *, author: str) -> Relation:
        rel = self.relations.get(relation_id)
        if rel is None:
            raise ValueError(f"No relation with id {relation_id!r}.")
        if rel.status != "proposed":
            raise ValueError(f"Relation {relation_id!r} is {rel.status!r}")
        update: dict[str, object] = {"status": "approved"}
        if rel.evidence == "derived_bootstrap":
            update |= {"evidence": "derived_approved", "author": author}
        self.relations[relation_id] = rel.model_copy(update=update)
        return self.relations[relation_id]

    def mark_retracted(self, relation_id: str) -> None:
        rel = self.relations[relation_id]
        self.relations[relation_id] = rel.model_copy(update={"status": "retracted"})


class FakeInquiries:
    def __init__(self, items: list[InquiryItem] | None = None) -> None:
        self.items = items or []

    def list(self, *, status=None, kind=None):  # noqa: ANN001, ANN201
        return [i for i in self.items if status is None or i.status == status]

    def harvest_today(self) -> dict[str, int]:
        return {"refused_question": 1}


class FakeInbox:
    def __init__(self, items: list[InboxItem] | None = None) -> None:
        self.items = items or []

    def list_open(self) -> list[InboxItem]:
        return [i for i in self.items if i.status == "open"]


class FakeCaptured:
    def __init__(self, examples: list[CapturedExample] | None = None) -> None:
        self.examples = examples or []

    def list_examples(self, *, include_retracted: bool = False) -> list[CapturedExample]:
        if include_retracted:
            return list(self.examples)
        return [e for e in self.examples if not e.retracted]


class FakeRetriever:
    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results
        self.calls: list[str] = []

    def retrieve(self, query, *, k=None, book=None, source=None):  # noqa: ANN001, ANN201
        self.calls.append(query)
        return RetrievalResult(results=self.results, relevance=0.9)


def _inquiry() -> InquiryItem:
    return InquiryItem(
        id="inq-1", kind="refused_question", title="שאלה שנדחתה", detail="נשאלה פעמיים",
        payload=RefusedQuestionPayload(questions=["מהי אמונה?"], count=2, last_asked=NOW),
        priority=2.0, priority_parts={"refusals": 2.0}, created_at=NOW,
    )


def _client(**overrides):  # noqa: ANN003, ANN201
    kwargs: dict[str, object] = dict(
        users=None, graph=None, inquiries=None, inbox=None, captured=None, retriever=None,
    )
    kwargs.update(overrides)
    app = create_app(  # type: ignore[arg-type]
        FakeRag(_answer()), FakeCapture(), _StubThreads(), overrides.get("develop_svc")
        or FakeDevelop(), _StubTerms(), _StubRetract(), _StubStats(), _StubCompose(),
        **{k: v for k, v in kwargs.items() if k != "develop_svc"},
    )
    return TestClient(app)


# -- the Review workbench queue ------------------------------------------------
def test_review_queue_aggregates_all_gates() -> None:
    client = _client(
        develop_svc=FakeDevelop([_development(), _development("approved").model_copy(
            update={"id": "dev-2"})]),
        graph=FakeGraph([_relation()]),
        inquiries=FakeInquiries([_inquiry()]),
        inbox=FakeInbox([InboxItem(id="in-1", author="R. G", text="מחשבה", created_at=NOW)]),
    )
    data = client.get("/api/review/queue").json()
    assert data["counts"] == {
        "developments": 1, "relations": 1, "inquiries": 1, "inbox": 1,
    }
    assert data["total"] == 4
    assert data["developments"][0]["id"] == "dev-1"          # only the proposed one
    assert data["developments"][0]["status"] == "proposed"
    assert data["relations"][0]["subject_label"] == "Tanya 1:1"
    assert data["relations"][0]["object_label"] == "c-1"     # concept id fallback
    assert data["inquiries"][0]["id"] == "inq-1"
    assert data["inbox"][0]["id"] == "in-1"
    assert data["harvest"] == {"refused_question": 1}


def test_review_queue_is_inert_without_optional_wiring() -> None:
    data = _client().get("/api/review/queue").json()
    assert data["total"] == 0
    assert data["developments"] == data["relations"] == []
    assert data["inquiries"] == data["inbox"] == []
    assert data["harvest"] == {}


# -- relation gates (the first UI review surface for study-program output) ------
def test_approve_relation_attributes_the_approver() -> None:
    graph = FakeGraph([_relation()])
    client = _client(graph=graph)
    r = client.post("/api/relations/rel-1/approve", json={"author": "הרב"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "approved"
    assert body["evidence"] == "derived_approved"  # bootstrap → approved, re-attributed
    assert body["author"] == "הרב"


def test_approve_relation_requires_author() -> None:
    client = _client(graph=FakeGraph([_relation()]))
    assert client.post("/api/relations/rel-1/approve", json={}).status_code == 400


def test_approve_relation_missing_returns_404() -> None:
    client = _client(graph=FakeGraph())
    r = client.post("/api/relations/rel-x/approve", json={"author": "הרב"})
    assert r.status_code == 404


def test_approve_relation_not_proposed_returns_400() -> None:
    client = _client(graph=FakeGraph([_relation(status="approved")]))
    r = client.post("/api/relations/rel-1/approve", json={"author": "הרב"})
    assert r.status_code == 400


def test_reject_relation_marks_retracted() -> None:
    graph = FakeGraph([_relation()])
    client = _client(graph=graph)
    r = client.post("/api/relations/rel-1/reject")
    assert r.status_code == 200
    assert r.json()["status"] == "retracted"
    assert graph.relations["rel-1"].status == "retracted"


def test_relation_routes_503_without_graph() -> None:
    client = _client()
    assert client.post("/api/relations/x/approve", json={"author": "a"}).status_code == 503
    assert client.post("/api/relations/x/reject").status_code == 503


# -- the Gold panel --------------------------------------------------------------
def _example(id_: str, *, kind: str = "connection", retracted: bool = False,
             refs: list[str] | None = None) -> CapturedExample:
    return CapturedExample(
        id=id_, question=f"שאלה {id_}",
        expected_refs=["Tanya 1:1"] if refs is None else refs,
        gold_answer="…", origin=CapturedOrigin(kind=kind, source_id=f"src-{id_}"),  # type: ignore[arg-type]
        created_at=NOW, retracted=retracted,
    )


def test_goldset_counts_origins_and_hygiene() -> None:
    client = _client(captured=FakeCaptured([
        _example("a"), _example("b", kind="term"),
        _example("c", kind="term", retracted=True), _example("d", kind="inquiry", refs=[]),
    ]))
    data = client.get("/api/goldset").json()
    assert data["total"] == 3                       # retracted example not counted…
    assert len(data["examples"]) == 4               # …but still listed (hygiene visible)
    assert data["by_origin"] == {"connection": 1, "term": 1, "inquiry": 1}
    assert data["gate_only"] == 1                   # the empty-refs example tests the gate
    assert data["last_report"] is None              # no settings injected → no report


def test_goldset_503_without_store() -> None:
    assert _client().get("/api/goldset").status_code == 503


# -- verify: retrieval-only "did it learn?" --------------------------------------
def test_verify_finds_expert_chunk_by_prefix() -> None:
    hits = [
        SearchResult(ref="Tanya 1:1", text="…", score=0.7, lang="he",
                     source="sefaria", payload={}),
        SearchResult(ref="Expert · connection · ab12cd34", text="החיבור", score=0.6,
                     lang="he", source="expert", payload={}),
    ]
    retriever = FakeRetriever(hits)
    client = _client(retriever=retriever)
    data = client.get("/api/verify", params={
        "question": "מהי אמונה?", "ref": "Expert · connection · ab12cd34"}).json()
    assert data["found"] is True
    assert data["rank"] == 2
    assert [t["ref"] for t in data["top"]] == [h.ref for h in hits]
    assert retriever.calls == ["מהי אמונה?"]


def test_verify_honest_when_not_found() -> None:
    client = _client(retriever=FakeRetriever([]))
    data = client.get("/api/verify", params={"question": "q", "ref": "Expert · x"}).json()
    assert data["found"] is False and data["rank"] is None


def test_verify_503_without_retriever() -> None:
    assert _client().get("/api/verify", params={"question": "q"}).status_code == 503
