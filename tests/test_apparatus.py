"""Tests for Prompt 36 — the margins (a daf apparatus per ref).

Fake/in-memory stores throughout: a seeded ref assembles the full apparatus
(grouped edges, matched terms, the expert layer, developments); an unknown ref
returns an EMPTY apparatus, not an error; the route degrades and is auth-aware.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from maayan.clock import SystemClock
from maayan.config import Settings
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.develop.models import Development
from maayan.develop.store import DevelopmentStore
from maayan.graph.apparatus import ApparatusService
from maayan.graph.models import RefEndpoint, Relation
from maayan.graph.store import GraphStore
from maayan.lexicon.models import Term
from maayan.lexicon.store import TermStore
from maayan.ui.app import create_app
from maayan.users.service import UserService
from maayan.users.store import UserStore

T0 = datetime(2026, 7, 1, tzinfo=UTC)
TANYA = "Tanya, Part I; Likkutei Amarim 18:1"
TORAH_OHR = "Torah Ohr, Vayera 14:1"
DEVARIM = "Deuteronomy 30:14"


def _edge(
    obj: str, *, rel_type: str = "connects", status: str = "approved",
    evidence: str = "expert", author: str = "R. Ginsburgh",
) -> Relation:
    return Relation.make(
        subject=RefEndpoint(ref=TANYA), object=RefEndpoint(ref=obj),
        rel_type=rel_type, evidence=evidence, confidence=1.0, status=status,  # type: ignore[arg-type]
        author=author, created_at=T0,
    )


class _World:
    def __init__(self) -> None:
        self.chunks = ChunkStore(":memory:")
        self.graph = GraphStore(":memory:")
        self.terms = TermStore(":memory:")
        self.developments = DevelopmentStore(":memory:")
        self.service = ApparatusService(self.chunks, self.graph, self.terms, self.developments)

    def seed_full(self) -> None:
        # The passage itself + a far corpus chunk.
        self.chunks.upsert_chunks([
            Chunk.make(ref=TANYA, book="Tanya", section_path=["18"], lang="he",
                       text="כי קרוב אליך הדבר מאד — אהבה מסותרת", source="sefaria"),
            Chunk.make(ref=TORAH_OHR, book="Torah Ohr", section_path=["14"], lang="he",
                       text="התגלות האהבה בעבודת התפילה", source="sefaria"),
        ])
        # Edges: a pasuk anchor (outside the corpus) + an expert connection.
        self.graph.save_relation(
            _edge(DEVARIM, rel_type="quotes_pasuk", evidence="curated", author="sefaria:links")
        )
        self.graph.save_relation(_edge(TORAH_OHR))
        # A term whose surface form appears in the passage text.
        self.terms.create_term(Term(
            id="term-1", canonical="אהבה מסותרת", surface_forms=["אהבה מסותרת"],
            definition="האהבה הטבעית שבכל נפש", author="R. Ginsburgh",
        ))
        # An expert chunk referencing the ref, and an approved development on it.
        self.chunks.upsert_chunks([Chunk.make(
            ref="Expert · connection · c1", book="Expert", section_path=["connection"],
            lang="he", text="ההבדל בין אהבה מסותרת לאהבת עולם",
            source="expert",
            metadata={"author": "R. Ginsburgh", "kind": "connection", "linked_refs": [TANYA]},
        )])
        self.developments.save_development(Development(
            id="dev-1", thread_id="t-1", seed_id="s-1", author="R. Ginsburgh",
            timestamp=T0, model="m", status="approved", grounded=True,
            text="פיתוח על יסוד הפרק", cited_refs=[TANYA], grounded_in=[TANYA],
        ))


def test_full_apparatus_assembles_all_groups_in_the_fixed_order() -> None:
    world = _World()
    world.seed_full()

    a = world.service.assemble(TANYA)

    assert a.in_corpus is True
    assert a.total == 5  # 2 edges + 1 term + 1 expert chunk + 1 development
    # Anchors first (the fixed order), then the relations.
    assert [g.rel_type for g in a.relation_groups] == ["quotes_pasuk", "connects"]
    pasuk = a.relation_groups[0].items[0]
    assert pasuk.far_label == DEVARIM
    assert pasuk.in_corpus is False and pasuk.far_snippet is None  # a bare anchor, still real
    connect = a.relation_groups[1].items[0]
    assert connect.in_corpus is True
    assert connect.far_snippet is not None and "התגלות האהבה" in connect.far_snippet
    assert connect.relation.author == "R. Ginsburgh"  # who says — always visible
    assert [t.canonical for t in a.terms] == ["אהבה מסותרת"]
    assert [x.source for x in a.expert_layer] == ["expert"]
    assert a.expert_layer[0].author == "R. Ginsburgh"
    assert [d.development_id for d in a.developments] == ["dev-1"]


def test_unknown_ref_returns_an_empty_apparatus_not_an_error() -> None:
    world = _World()
    a = world.service.assemble("Some, Unknown Ref 1:1")
    assert a.in_corpus is False
    assert a.total == 0
    assert a.relation_groups == [] and a.terms == []
    assert a.expert_layer == [] and a.developments == []


def test_only_approved_edges_and_live_terms_appear() -> None:
    world = _World()
    world.chunks.upsert_chunks([Chunk.make(
        ref=TANYA, book="Tanya", section_path=["18"], lang="he",
        text="אהבה מסותרת", source="sefaria",
    )])
    world.graph.save_relation(_edge(TORAH_OHR, status="proposed"))
    world.terms.create_term(Term(
        id="term-r", canonical="אהבה מסותרת", surface_forms=["אהבה מסותרת"],
        definition="x", author="R. G",
    ))
    world.terms.mark_retracted("term-r")

    a = world.service.assemble(TANYA)
    assert a.relation_groups == []  # the proposed edge is invisible
    assert a.terms == []  # the retracted term too


def test_far_endpoint_direction_flips_when_ref_is_the_object() -> None:
    world = _World()
    incoming = Relation.make(
        subject=RefEndpoint(ref=TORAH_OHR), object=RefEndpoint(ref=TANYA),
        rel_type="explains", evidence="expert", confidence=1.0, status="approved",
        author="R. Ginsburgh", created_at=T0,
    )
    world.graph.save_relation(incoming)
    a = world.service.assemble(TANYA)
    assert a.relation_groups[0].items[0].far_label == TORAH_OHR  # the FAR side, not self


def test_retracted_expert_chunk_leaves_the_margins() -> None:
    world = _World()
    world.seed_full()
    expert = world.chunks.get_chunks(source="expert")[0]
    world.chunks.mark_retracted([expert.id])
    a = world.service.assemble(TANYA)
    assert a.expert_layer == []


# -- the route: thin, degradable, auth-aware ----------------------------------------

class _Stub:
    def __getattr__(self, _name: str):  # noqa: ANN204
        raise AssertionError("apparatus routes must not touch unrelated services")


def _client(world: _World, **kwargs: object) -> TestClient:
    app = create_app(  # type: ignore[arg-type]
        _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(),
        apparatus=world.service, **kwargs,
    )
    return TestClient(app)


def test_api_apparatus_returns_the_margins_with_total() -> None:
    world = _World()
    world.seed_full()
    resp = _client(world).get("/api/apparatus", params={"ref": TANYA})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5  # the count badge (גליון · 5) travels over the wire
    assert body["in_corpus"] is True
    assert [g["rel_type"] for g in body["relation_groups"]] == ["quotes_pasuk", "connects"]
    # Unknown ref: empty apparatus, still 200.
    empty = _client(world).get("/api/apparatus", params={"ref": "Nope 1:1"}).json()
    assert empty["total"] == 0


def test_api_apparatus_inert_when_unwired_and_behind_the_auth_wall(tmp_path: Path) -> None:
    unwired = create_app(  # type: ignore[arg-type]
        _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(),
    )
    assert TestClient(unwired).get("/api/apparatus", params={"ref": TANYA}).status_code == 503

    settings = Settings(_env_file=None, db_path=str(tmp_path / "auth.sqlite3"))
    users = UserService(UserStore(settings.db_path), SystemClock(), settings)
    users.create_user(username="rav", password="password123", display_name="Rav", role="admin")
    world = _World()
    world.seed_full()
    client = _client(world, users=users, auth_enabled=True)
    assert client.get("/api/apparatus", params={"ref": TANYA}).status_code == 401
    client.post("/api/login", json={"username": "rav", "password": "password123"})
    assert client.get("/api/apparatus", params={"ref": TANYA}).status_code == 200
