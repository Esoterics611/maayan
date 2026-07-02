"""Tests for Prompt 33 — the knowledge-graph spine.

Models (discriminated Endpoint union), GraphStore (CRUD, dedupe, the approval
gate), the backfill from expert connection chunks, and the graph CLI. No network,
no models — everything runs on in-memory SQLite.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

import maayan.cli as cli
from maayan.cli import app
from maayan.clock import FakeClock
from maayan.config import Settings
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.graph.backfill import backfill_relations
from maayan.graph.models import (
    Concept,
    ConceptEndpoint,
    RefEndpoint,
    Relation,
    concept_id,
    endpoint_str,
    relation_id,
)
from maayan.graph.store import GraphStore

T0 = datetime(2026, 7, 1, tzinfo=UTC)
TANYA_18 = "Tanya, Part I; Likkutei Amarim 18"
TORAH_OHR = "Torah Ohr, Vayera 14a"
LIKUTEI = "Likutei Torah, Re'eh 27b"


def _relation(
    subject: str = TANYA_18,
    obj: str = TORAH_OHR,
    *,
    rel_type: str = "connects",
    evidence: str = "expert",
    confidence: float = 1.0,
    status: str = "proposed",
    author: str = "R. Ginsburgh",
    source_chunk_id: str | None = None,
    note: str | None = None,
) -> Relation:
    return Relation.make(
        subject=RefEndpoint(ref=subject),
        object=RefEndpoint(ref=obj),
        rel_type=rel_type,  # type: ignore[arg-type]
        evidence=evidence,  # type: ignore[arg-type]
        confidence=confidence,
        status=status,  # type: ignore[arg-type]
        author=author,
        source_chunk_id=source_chunk_id,
        note=note,
        created_at=T0,
    )


# -- models --------------------------------------------------------------------

def test_endpoint_union_round_trips_both_kinds() -> None:
    for endpoint in (RefEndpoint(ref=TANYA_18), ConceptEndpoint(concept_id="c-1")):
        relation = _relation()
        payload = relation.model_copy(update={"subject": endpoint}).model_dump()
        back = Relation.model_validate(payload)
        assert back.subject == endpoint


def test_endpoint_union_rejects_unknown_tag_and_blank_values() -> None:
    payload = _relation().model_dump()
    payload["subject"] = {"endpoint_type": "url", "ref": "http://x"}
    with pytest.raises(ValidationError):
        Relation.model_validate(payload)
    with pytest.raises(ValidationError):
        RefEndpoint(ref="   ")
    with pytest.raises(ValidationError):
        ConceptEndpoint(concept_id="")


def test_author_and_confidence_are_validated() -> None:
    with pytest.raises(ValidationError, match="author"):
        _relation(author="   ")
    with pytest.raises(ValidationError):
        _relation(confidence=1.5)
    with pytest.raises(ValidationError, match="author"):
        Concept.make(canonical="ביטול", author=" ", created_at=T0)


def test_ids_are_deterministic() -> None:
    a = relation_id(RefEndpoint(ref=TANYA_18), RefEndpoint(ref=TORAH_OHR), "connects")
    b = relation_id(RefEndpoint(ref=TANYA_18), RefEndpoint(ref=TORAH_OHR), "connects")
    assert a == b
    assert a != relation_id(RefEndpoint(ref=TANYA_18), RefEndpoint(ref=TORAH_OHR), "explains")
    # Direction matters (explains/quotes are directional).
    assert a != relation_id(RefEndpoint(ref=TORAH_OHR), RefEndpoint(ref=TANYA_18), "connects")
    assert concept_id("ביטול") == concept_id("ביטול")


# -- store: concepts -------------------------------------------------------------

def test_concept_round_trip_and_lookup_by_alias() -> None:
    store = GraphStore(":memory:")
    concept = Concept.make(
        canonical="ביטול", aliases=["ביטול במציאות", "bitul"], kind="avodah",
        term_id="term-9", author="R. Ginsburgh", created_at=T0,
    )
    store.save_concept(concept)
    assert store.get_concept(concept.id) == concept
    assert store.find_concept("ביטול") == concept
    assert store.find_concept("bitul") == concept
    assert store.find_concept("לא קיים") is None
    assert [c.canonical for c in store.list_concepts()] == ["ביטול"]


# -- store: relations, dedupe, the gate ------------------------------------------

def test_relation_round_trip_and_relations_for_both_directions() -> None:
    store = GraphStore(":memory:")
    stored = store.save_relation(_relation(note="shared pasuk"))
    assert store.get_relation(stored.id) == stored
    # Touching either endpoint finds the edge.
    assert store.relations_for(RefEndpoint(ref=TANYA_18)) == [stored]
    assert store.relations_for(RefEndpoint(ref=TORAH_OHR)) == [stored]
    # Type filter.
    assert store.relations_for(RefEndpoint(ref=TANYA_18), types=["explains"]) == []


def test_dedupe_second_insert_updates_not_duplicates() -> None:
    store = GraphStore(":memory:")
    first = store.save_relation(_relation(evidence="deterministic", confidence=0.5))
    again = store.save_relation(_relation(evidence="deterministic", confidence=0.9))
    assert again.id == first.id
    assert len(store.list_relations()) == 1
    assert again.confidence == 0.9  # updated, not duplicated


def test_dedupe_never_downgrades_evidence() -> None:
    store = GraphStore(":memory:")
    store.save_relation(_relation(evidence="expert", confidence=1.0))
    kept = store.save_relation(
        _relation(evidence="derived_bootstrap", confidence=0.3, author="bootstrap:free")
    )
    assert kept.evidence == "expert"  # the weaker re-assertion changed nothing
    assert kept.confidence == 1.0
    assert kept.author == "R. Ginsburgh"
    upgraded = store.save_relation(_relation(evidence="expert", confidence=0.8))
    assert upgraded.evidence == "expert" and upgraded.confidence == 0.8


def test_dedupe_preserves_status_a_human_set() -> None:
    store = GraphStore(":memory:")
    stored = store.save_relation(_relation())
    store.approve(stored.id, author="Rav")
    re_inserted = store.save_relation(_relation())  # arrives "proposed" again
    assert re_inserted.status == "approved"  # the human decision survives


def test_gate_only_approved_relations_reach_neighbors() -> None:
    store = GraphStore(":memory:")
    stored = store.save_relation(_relation())
    assert store.neighbors(RefEndpoint(ref=TANYA_18)) == []  # proposed is invisible

    approved = store.approve(stored.id, author="Rav")
    assert approved.status == "approved"
    steps = store.neighbors(RefEndpoint(ref=TANYA_18))
    assert len(steps) == 1
    assert steps[0].endpoint == RefEndpoint(ref=TORAH_OHR)  # the FAR side
    assert steps[0].relation.id == stored.id
    # From the other side, the far endpoint flips.
    back = store.neighbors(RefEndpoint(ref=TORAH_OHR))
    assert back[0].endpoint == RefEndpoint(ref=TANYA_18)


def test_approve_validates_author_id_and_state() -> None:
    store = GraphStore(":memory:")
    stored = store.save_relation(_relation())
    with pytest.raises(ValueError, match="author"):
        store.approve(stored.id, author="   ")
    with pytest.raises(ValueError, match="No relation"):
        store.approve("missing", author="Rav")
    store.approve(stored.id, author="Rav")
    with pytest.raises(ValueError, match="proposed"):
        store.approve(stored.id, author="Rav")  # not re-runnable


def test_approving_bootstrap_edge_becomes_derived_approved_by_the_approver() -> None:
    store = GraphStore(":memory:")
    stored = store.save_relation(
        _relation(evidence="derived_bootstrap", confidence=0.6, author="bootstrap:free-model")
    )
    approved = store.approve(stored.id, author="Rav")
    assert approved.evidence == "derived_approved"
    assert approved.author == "Rav"  # the human now vouches
    # A human-asserted edge keeps its original author through approval.
    other = store.save_relation(_relation(obj=LIKUTEI))
    approved2 = store.approve(other.id, author="Someone Else")
    assert approved2.author == "R. Ginsburgh" and approved2.evidence == "expert"


def test_neighbors_filters_by_type_and_counts_tally() -> None:
    store = GraphStore(":memory:")
    a = store.save_relation(_relation())
    b = store.save_relation(_relation(obj=LIKUTEI, rel_type="explains"))
    store.approve(a.id, author="Rav")
    store.approve(b.id, author="Rav")
    only = store.neighbors(RefEndpoint(ref=TANYA_18), types=["explains"])
    assert [s.relation.rel_type for s in only] == ["explains"]

    counts = store.counts()
    assert counts.relations == 2
    assert counts.by_rel_type == {"connects": 1, "explains": 1}
    assert counts.by_status == {"approved": 2}
    assert counts.by_evidence == {"expert": 2}


# -- backfill --------------------------------------------------------------------

def _connection_chunk(
    *, refs: list[str], author: str = "R. Ginsburgh", kind: str = "connection", cid: str = "c-1"
) -> Chunk:
    return Chunk.make(
        ref=f"Expert · {kind} · {cid}", book="Expert", section_path=[kind],
        lang="he", text="השוואה בין המקורות", source="expert",
        metadata={"author": author, "kind": kind, "linked_refs": refs, "contribution_id": cid},
    )


def _backfill_setup() -> tuple[ChunkStore, GraphStore, FakeClock, Settings]:
    return ChunkStore(":memory:"), GraphStore(":memory:"), FakeClock(), Settings(_env_file=None)


def test_backfill_lifts_each_pair_into_an_approved_expert_edge() -> None:
    chunks, graph, clock, settings = _backfill_setup()
    chunk = _connection_chunk(refs=[TANYA_18, TORAH_OHR, LIKUTEI])
    chunks.upsert_chunks([chunk])

    result = backfill_relations(chunks, graph, clock, settings)

    assert result.connection_chunks == 1
    assert result.relations_created == 3  # C(3,2) pairs
    edges = graph.list_relations()
    assert {(e.status, e.evidence, e.author) for e in edges} == {
        ("approved", "expert", "R. Ginsburgh")
    }
    assert all(e.rel_type == "connects" for e in edges)
    assert all(e.source_chunk_id == chunk.id for e in edges)
    assert all(e.confidence == settings.graph_default_confidence for e in edges)
    # The far side of Tanya 18's margins now includes both partners.
    fars = {endpoint_str(s.endpoint) for s in graph.neighbors(RefEndpoint(ref=TANYA_18))}
    assert fars == {TORAH_OHR, LIKUTEI}


def test_backfill_bootstrap_author_maps_to_bootstrap_evidence_and_confidence() -> None:
    chunks, graph, clock, settings = _backfill_setup()
    chunks.upsert_chunks(
        [_connection_chunk(refs=[TANYA_18, TORAH_OHR], author="bootstrap:gpt-oss-120b:free")]
    )
    backfill_relations(chunks, graph, clock, settings)
    edge = graph.list_relations()[0]
    assert edge.evidence == "derived_bootstrap"
    assert edge.confidence == settings.graph_bootstrap_confidence
    assert edge.author == "bootstrap:gpt-oss-120b:free"  # provenance preserved
    assert edge.status == "approved"  # passed the populate faithfulness gate


def test_backfill_is_idempotent() -> None:
    chunks, graph, clock, settings = _backfill_setup()
    chunks.upsert_chunks([_connection_chunk(refs=[TANYA_18, TORAH_OHR, LIKUTEI])])
    first = backfill_relations(chunks, graph, clock, settings)
    second = backfill_relations(chunks, graph, clock, settings)
    assert first.relations_created == 3
    assert second.relations_created == 0
    assert second.relations_existing == 3
    assert len(graph.list_relations()) == 3


def test_backfill_skips_non_connections_short_lists_blank_authors_and_tombstones() -> None:
    chunks, graph, clock, settings = _backfill_setup()
    correction = _connection_chunk(refs=[TANYA_18, TORAH_OHR], kind="correction", cid="c-2")
    single = _connection_chunk(refs=[TANYA_18], cid="c-3")
    anonymous = _connection_chunk(refs=[TANYA_18, TORAH_OHR], author="  ", cid="c-4")
    retracted = _connection_chunk(refs=[TANYA_18, LIKUTEI], cid="c-5")
    chunks.upsert_chunks([correction, single, anonymous, retracted])
    chunks.mark_retracted([retracted.id])

    result = backfill_relations(chunks, graph, clock, settings)

    assert result.relations_created == 0
    assert result.connection_chunks == 0
    assert result.skipped_chunks == 3  # the tombstoned chunk is never even seen
    assert graph.list_relations() == []


def test_backfill_dedupes_repeated_refs_within_one_chunk() -> None:
    chunks, graph, clock, settings = _backfill_setup()
    chunks.upsert_chunks([_connection_chunk(refs=[TANYA_18, TORAH_OHR, TANYA_18])])
    result = backfill_relations(chunks, graph, clock, settings)
    assert result.relations_created == 1  # not a self-loop, not a duplicate pair


# -- CLI ---------------------------------------------------------------------------

def _runner():  # noqa: ANN202
    from typer.testing import CliRunner

    return CliRunner()


@pytest.fixture
def cli_graph(monkeypatch: pytest.MonkeyPatch) -> GraphStore:
    """One shared in-memory GraphStore behind the CLI commands."""
    store = GraphStore(":memory:")
    monkeypatch.setattr(cli, "_graph_store_cli", lambda: store)
    return store


def test_cli_add_creates_proposed_and_approve_gates_it(cli_graph: GraphStore) -> None:
    result = _runner().invoke(app, [
        "graph", "add", "--type", "connects", "--author", "R. Ginsburgh",
        "--subject", TANYA_18, "--object", TORAH_OHR,
    ])
    assert result.exit_code == 0, result.output
    assert "proposed" in result.output
    edge = cli_graph.list_relations()[0]
    assert edge.status == "proposed" and edge.evidence == "expert"

    approved = _runner().invoke(app, ["graph", "approve", edge.id, "--author", "Rav"])
    assert approved.exit_code == 0, approved.output
    stored = cli_graph.get_relation(edge.id)
    assert stored is not None and stored.status == "approved"


def test_cli_add_rejects_unknown_type_and_ambiguous_endpoint(cli_graph: GraphStore) -> None:
    bad_type = _runner().invoke(app, [
        "graph", "add", "--type", "likes", "--author", "A",
        "--subject", TANYA_18, "--object", TORAH_OHR,
    ])
    assert bad_type.exit_code == 1
    assert "unknown --type" in bad_type.output
    both = _runner().invoke(app, [
        "graph", "add", "--type", "connects", "--author", "A",
        "--subject", TANYA_18, "--subject-concept", "c-1", "--object", TORAH_OHR,
    ])
    assert both.exit_code == 1
    assert "exactly one" in both.output
    assert cli_graph.list_relations() == []


def test_cli_show_groups_by_type_with_evidence_badges(cli_graph: GraphStore) -> None:
    a = cli_graph.save_relation(_relation())
    b = cli_graph.save_relation(_relation(obj=LIKUTEI, rel_type="explains"))
    cli_graph.approve(a.id, author="Rav")
    cli_graph.approve(b.id, author="Rav")

    result = _runner().invoke(app, ["graph", "show", "--ref", TANYA_18])
    assert result.exit_code == 0, result.output
    assert "connects:" in result.output and "explains:" in result.output
    assert "●" in result.output  # the expert badge
    assert "R. Ginsburgh" in result.output

    empty = _runner().invoke(app, ["graph", "show", "--ref", "Unknown 1:1"])
    assert empty.exit_code == 0
    assert "no relations" in empty.output
