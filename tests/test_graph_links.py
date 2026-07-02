"""Tests for Prompt 34 — curated Sefaria links + deterministic pasuk anchors.

No network: the parser and mapping run on fixture payloads captured from one
real /api/links response; the client is exercised through respx; ingestion uses
a scripted fake client. Time runs on FakeClock.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx

from maayan.clock import FakeClock
from maayan.config import Settings
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.graph.links import (
    LINKS_AUTHOR,
    PASUK_JOIN_AUTHOR,
    LinksCursorStore,
    SefariaLink,
    SefariaLinksClient,
    SefariaLinksError,
    ingest_links,
    link_to_relation,
    parse_links,
    pasuk_join,
)
from maayan.graph.models import ConceptEndpoint, RefEndpoint, Relation
from maayan.graph.store import GraphStore

BASE = "https://www.sefaria.org/api"
TANYA_18_1 = "Tanya, Part I; Likkutei Amarim 18:1"
TANYA_1_1 = "Tanya, Part I; Likkutei Amarim 1:1"
TORAH_OHR = "Torah Ohr, Vayera 14:1"
DEVARIM = "Deuteronomy 30:14"
T0 = datetime(2026, 7, 1, tzinfo=UTC)


def _settings() -> Settings:
    return Settings(_env_file=None)


# -- parser ---------------------------------------------------------------------

def test_parse_links_reads_the_real_payload(links_tanya_18_1_json: Any) -> None:
    links = parse_links(links_tanya_18_1_json)
    assert len(links) == 1
    link = links[0]
    assert link.ref == DEVARIM
    assert link.anchor_ref == TANYA_18_1
    assert link.category == "Tanakh"


def test_parse_links_mixed_categories(links_tanya_1_1_json: Any) -> None:
    links = parse_links(links_tanya_1_1_json)
    assert len(links) == 5
    assert {link.category for link in links} == {
        "Midrash", "Talmud", "Mishnah", "Jewish Thought",
    }


def test_parse_links_tolerates_junk_entries_and_rejects_error_payloads() -> None:
    assert parse_links([]) == []
    # Malformed entries are skipped, well-formed ones survive.
    links = parse_links([
        "not-a-dict",
        {"ref": "", "anchorRef": TANYA_18_1},
        {"anchorRef": TANYA_18_1},
        {"ref": DEVARIM, "anchorRef": TANYA_18_1, "category": "Tanakh"},
    ])
    assert [link.ref for link in links] == [DEVARIM]
    with pytest.raises(SefariaLinksError, match="boom"):
        parse_links({"error": "boom"})
    with pytest.raises(SefariaLinksError, match="Expected a list"):
        parse_links({"links": []})


# -- mapping ----------------------------------------------------------------------

def _link(ref: str = DEVARIM, category: str = "Tanakh", link_type: str = "") -> SefariaLink:
    return SefariaLink(ref=ref, anchor_ref=TANYA_18_1, category=category, link_type=link_type)


def test_tanakh_link_maps_to_quotes_pasuk_curated_approved() -> None:
    relation = link_to_relation(TANYA_18_1, _link(), FakeClock(), _settings())
    assert relation is not None
    assert relation.rel_type == "quotes_pasuk"
    assert relation.evidence == "curated"
    assert relation.status == "approved"  # curated data passes the gate by policy
    assert relation.confidence == 1.0
    assert relation.author == LINKS_AUTHOR
    assert relation.subject == RefEndpoint(ref=TANYA_18_1)
    assert relation.object == RefEndpoint(ref=DEVARIM)


def test_non_tanakh_kept_category_maps_to_quotes() -> None:
    relation = link_to_relation(
        TANYA_1_1, _link(ref="Niddah 30b:25", category="Talmud"), FakeClock(), _settings()
    )
    assert relation is not None and relation.rel_type == "quotes"


def test_unkept_categories_and_self_links_map_to_none() -> None:
    clock, settings = FakeClock(), _settings()
    assert link_to_relation(TANYA_18_1, _link(category="Commentary"), clock, settings) is None
    assert link_to_relation(TANYA_18_1, _link(category="Jewish Thought"), clock, settings) is None
    assert link_to_relation(TANYA_18_1, _link(ref=TANYA_18_1), clock, settings) is None


# -- client -----------------------------------------------------------------------

@respx.mock
async def test_client_fetches_and_paces_via_the_injected_clock(
    links_tanya_18_1_json: Any,
) -> None:
    respx.get(url__regex=r".*/links/.*").mock(
        return_value=httpx.Response(200, json=links_tanya_18_1_json)
    )
    clock = FakeClock()
    async with httpx.AsyncClient() as http:
        client = SefariaLinksClient(http, clock, base_url=BASE, rate_limit_seconds=0.5)
        first = await client.fetch_links(TANYA_18_1)
        second = await client.fetch_links(TANYA_1_1)
    assert [link.ref for link in first] == [DEVARIM]
    assert len(second) == 1
    assert clock.slept and clock.slept[0] == pytest.approx(0.5)  # paced, not time.sleep


# -- ingestion (fake client; resumable; idempotent) ---------------------------------

class _FakeLinksClient:
    """Scripted stand-in for SefariaLinksClient; counts fetches per ref."""

    def __init__(self, responses: dict[str, list[SefariaLink] | Exception]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    async def fetch_links(self, ref: str) -> list[SefariaLink]:
        self.calls.append(ref)
        scripted = self.responses.get(ref, [])
        if isinstance(scripted, Exception):
            raise scripted
        return scripted


def _sefaria_chunk(ref: str, lang: str = "he") -> Chunk:
    return Chunk.make(
        ref=ref, book=ref.split(",")[0], section_path=["x"], lang=lang,  # type: ignore[arg-type]
        text="טקסט", source="sefaria",
    )


def _ingest_setup() -> tuple[ChunkStore, GraphStore, LinksCursorStore, FakeClock, Settings]:
    return (
        ChunkStore(":memory:"), GraphStore(":memory:"), LinksCursorStore(":memory:"),
        FakeClock(), _settings(),
    )


async def test_ingest_links_creates_edges_and_dedupes_bilingual_refs() -> None:
    chunks, graph, cursor, clock, settings = _ingest_setup()
    # he + en share one ref → exactly one fetch.
    chunks.upsert_chunks([_sefaria_chunk(TANYA_18_1, "he"), _sefaria_chunk(TANYA_18_1, "en")])
    client = _FakeLinksClient({TANYA_18_1: [_link(), _link(category="Commentary")]})

    result = await ingest_links(chunks, graph, cursor, client, clock, settings)  # type: ignore[arg-type]

    assert client.calls == [TANYA_18_1]
    assert result.refs_seen == 1 and result.refs_fetched == 1
    assert result.links_seen == 2 and result.links_kept == 1
    assert result.relations_created == 1
    edge = graph.list_relations()[0]
    assert edge.rel_type == "quotes_pasuk" and edge.author == LINKS_AUTHOR


async def test_ingest_links_resumes_from_the_cursor() -> None:
    chunks, graph, cursor, clock, settings = _ingest_setup()
    chunks.upsert_chunks([_sefaria_chunk(TANYA_18_1), _sefaria_chunk(TANYA_1_1)])
    client = _FakeLinksClient({TANYA_18_1: [_link()], TANYA_1_1: []})

    first = await ingest_links(chunks, graph, cursor, client, clock, settings)  # type: ignore[arg-type]
    second = await ingest_links(chunks, graph, cursor, client, clock, settings)  # type: ignore[arg-type]

    assert first.refs_fetched == 2
    assert second.refs_fetched == 0 and second.refs_skipped == 2
    assert len(client.calls) == 2  # nothing re-fetched
    assert len(graph.list_relations()) == 1  # and nothing duplicated


async def test_ingest_links_limit_and_book_filter() -> None:
    chunks, graph, cursor, clock, settings = _ingest_setup()
    chunks.upsert_chunks([
        _sefaria_chunk(TANYA_18_1), _sefaria_chunk(TANYA_1_1), _sefaria_chunk(TORAH_OHR),
    ])
    client = _FakeLinksClient({})

    limited = await ingest_links(  # type: ignore[arg-type]
        chunks, graph, cursor, client, clock, settings, limit=1
    )
    assert limited.refs_fetched == 1

    only_torah_ohr = await ingest_links(  # type: ignore[arg-type]
        chunks, graph, cursor, client, clock, settings, book="Torah Ohr"
    )
    assert only_torah_ohr.refs_seen == 1
    assert TORAH_OHR in client.calls


async def test_ingest_links_failures_are_retried_next_run_not_cursored() -> None:
    chunks, graph, cursor, clock, settings = _ingest_setup()
    chunks.upsert_chunks([_sefaria_chunk(TANYA_18_1)])
    failing = _FakeLinksClient({TANYA_18_1: httpx.ConnectError("down")})

    first = await ingest_links(chunks, graph, cursor, failing, clock, settings)  # type: ignore[arg-type]
    assert first.refs_failed == 1 and cursor.count() == 0

    recovered = _FakeLinksClient({TANYA_18_1: [_link()]})
    second = await ingest_links(chunks, graph, cursor, recovered, clock, settings)  # type: ignore[arg-type]
    assert second.refs_fetched == 1 and second.relations_created == 1


# -- the pasuk join ------------------------------------------------------------------

def _quotes_pasuk(subject: str, pasuk: str = DEVARIM) -> Relation:
    return Relation.make(
        subject=RefEndpoint(ref=subject), object=RefEndpoint(ref=pasuk),
        rel_type="quotes_pasuk", evidence="curated", confidence=1.0, status="approved",
        author=LINKS_AUTHOR, created_at=T0,
    )


def test_pasuk_join_connects_two_corpus_refs_across_works() -> None:
    graph = GraphStore(":memory:")
    graph.save_relation(_quotes_pasuk(TANYA_18_1))
    graph.save_relation(_quotes_pasuk(TORAH_OHR))
    graph.save_relation(_quotes_pasuk(TANYA_1_1, pasuk="Genesis 1:1"))  # unshared

    result = pasuk_join(graph, FakeClock())

    assert result.pasukim == 1 and result.pairs == 1
    assert result.relations_created == 1
    edge = graph.list_relations(rel_type="parallels")[0]
    assert edge.evidence == "deterministic"
    assert edge.status == "approved"
    assert edge.author == PASUK_JOIN_AUTHOR
    assert edge.note == f"shared pasuk: {DEVARIM}"
    # The pair is the cross-WORK connection the bootstrap populate could not reach.
    subject, obj = edge.subject, edge.object
    assert isinstance(subject, RefEndpoint) and isinstance(obj, RefEndpoint)
    assert {subject.ref, obj.ref} == {TANYA_18_1, TORAH_OHR}


def test_pasuk_join_is_idempotent_and_only_walks_approved_ref_edges() -> None:
    graph = GraphStore(":memory:")
    graph.save_relation(_quotes_pasuk(TANYA_18_1))
    graph.save_relation(_quotes_pasuk(TORAH_OHR))
    # A proposed quotes_pasuk edge must not feed the join.
    proposed = Relation.make(
        subject=RefEndpoint(ref=TANYA_1_1), object=RefEndpoint(ref=DEVARIM),
        rel_type="quotes_pasuk", evidence="expert", confidence=1.0, status="proposed",
        author="R. G", created_at=T0,
    )
    graph.save_relation(proposed)
    # Concept-typed endpoints are ignored by the join.
    graph.save_relation(Relation.make(
        subject=ConceptEndpoint(concept_id="c-1"), object=RefEndpoint(ref=DEVARIM),
        rel_type="quotes_pasuk", evidence="expert", confidence=1.0, status="approved",
        author="R. G", created_at=T0,
    ))

    first = pasuk_join(graph, FakeClock())
    second = pasuk_join(graph, FakeClock())

    assert first.relations_created == 1  # only the Tanya18 ↔ TorahOhr pair
    assert second.relations_created == 0
    assert second.relations_existing == 1
    assert len(graph.list_relations(rel_type="parallels")) == 1
