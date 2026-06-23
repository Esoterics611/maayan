"""Tests for Prompt 17 — retract & correct (the eraser).

Ephemeral Qdrant + the deterministic HashingEmbedder; no network, no real models.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from maayan.clock import FakeClock
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.develop.models import Development
from maayan.develop.store import DevelopmentStore
from maayan.embed.fake import HashingEmbedder
from maayan.index.pipeline import index_chunks
from maayan.index.qdrant import QdrantIndex
from maayan.lexicon.models import Term
from maayan.lexicon.store import TermStore
from maayan.retract.service import RetractionService
from maayan.retract.store import RetractionStore
from maayan.retrieve.retriever import Retriever
from maayan.ui.app import create_app

DIM = 128


class Setup(NamedTuple):
    svc: RetractionService
    chunks: ChunkStore
    index: QdrantIndex
    embedder: HashingEmbedder
    developments: DevelopmentStore
    terms: TermStore
    retractions: RetractionStore


def _setup() -> Setup:
    chunks = ChunkStore(":memory:")
    retractions = RetractionStore(":memory:")
    developments = DevelopmentStore(":memory:")
    terms = TermStore(":memory:")
    embedder = HashingEmbedder(dim=DIM)
    index = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
    svc = RetractionService(chunks, retractions, index, FakeClock(), developments, terms)
    return Setup(svc, chunks, index, embedder, developments, terms, retractions)


def _seed_indexed(s: Setup, chunk: Chunk) -> Chunk:
    """Persist a chunk (indexed=1) and embed+upsert it into Qdrant, like the services do."""
    s.chunks.upsert_chunks([chunk])
    s.chunks.mark_indexed([chunk.id])
    s.index.ensure_collection()
    embeddings = s.embedder.embed([chunk.text])
    s.index.upsert_chunks(list(zip([chunk], embeddings, strict=True)))
    return chunk


def _expert_chunk(text: str = "ahava connects nefesh to keser") -> Chunk:
    return Chunk.make(
        ref="Expert · connection · abcd1234", book="Expert", section_path=["connection"],
        lang="en", text=text, source="expert",
        metadata={"author": "R. Ginsburgh", "contribution_id": "c-1"},
    )


def _retrieve_refs(s: Setup, query: str) -> list[str]:
    return [r.ref for r in Retriever(s.index, s.embedder, top_k=10).search(query)]


# -- the core behavior --------------------------------------------------------

def test_retract_removes_point_and_chunk_is_no_longer_retrieved() -> None:
    s = _setup()
    chunk = _seed_indexed(s, _expert_chunk())
    assert chunk.ref in _retrieve_refs(s, "ahava connects nefesh keser")

    s.svc.retract(chunk.ref, author="Editor", reason="wrong connection")

    assert chunk.ref not in _retrieve_refs(s, "ahava connects nefesh keser")
    assert s.index.retrieve(chunk.id) is None  # point gone from Qdrant


def test_retracted_chunk_is_skipped_by_index_rebuild() -> None:
    s = _setup()
    keep = _seed_indexed(s, Chunk.make(
        ref="Tanya, Part I; Likkutei Amarim 1:1", book="Tanya", section_path=["1", "1"],
        lang="en", text="the printed source stays", source="sefaria",
    ))
    drop = _seed_indexed(s, _expert_chunk("retract me unique-token-zzz"))

    s.svc.retract(drop.ref, author="Editor", reason="superseded")

    # A full rebuild re-embeds from the store — and must NOT bring the tombstone back.
    index_chunks(store=s.chunks, embedder=s.embedder, index=s.index, batch_size=8, rebuild=True)
    refs = _retrieve_refs(s, "retract me unique-token-zzz")
    assert drop.ref not in refs
    assert keep.ref in _retrieve_refs(s, "printed source stays")
    assert s.index.retrieve(drop.id) is None


def test_retracting_printed_text_is_rejected() -> None:
    s = _setup()
    for source in ("sefaria", "chabad"):
        chunk = _seed_indexed(s, Chunk.make(
            ref=f"Printed {source} 1:1", book="Tanya", section_path=["1"],
            lang="en", text=f"printed {source} text", source=source,
        ))
        with pytest.raises(ValueError, match="printed text"):
            s.svc.retract(chunk.ref, author="Editor", reason="nope")
        # The printed chunk is untouched: still indexed, still retrievable.
        assert s.index.retrieve(chunk.id) is not None
        assert s.chunks.count(source=source) == 1


def test_retraction_round_trips_with_full_provenance() -> None:
    s = _setup()
    chunk = _seed_indexed(s, _expert_chunk())

    r = s.svc.retract(chunk.ref, author="R. Editor", reason="typo")

    assert r.chunk_id == chunk.id
    assert r.ref == chunk.ref
    assert r.source == "expert"
    assert r.author == "R. Editor"
    assert r.reason == "typo"
    # Persisted and listable with provenance intact.
    stored = s.retractions.get_retraction(r.id)
    assert stored is not None and stored.model_dump() == r.model_dump()
    assert [x.id for x in s.svc.list_retractions()] == [r.id]


def test_blank_author_is_rejected_and_nothing_is_removed() -> None:
    s = _setup()
    chunk = _seed_indexed(s, _expert_chunk())

    with pytest.raises(ValueError, match="author"):
        s.svc.retract(chunk.ref, author="   ", reason="oops")

    # Rejected before any mutation: the chunk is still indexed and retrievable.
    assert s.index.retrieve(chunk.id) is not None
    assert chunk.ref in _retrieve_refs(s, "ahava connects nefesh keser")
    assert s.retractions.count() == 0


def test_unknown_target_is_rejected() -> None:
    s = _setup()
    with pytest.raises(ValueError, match="No chunk found"):
        s.svc.retract("does-not-exist", author="Editor", reason="x")


# -- cascade: derived → development retracted; term → term retracted ----------

def test_retracting_derived_chunk_flips_its_development_to_retracted() -> None:
    s = _setup()
    dev = Development(
        id="dev-1", thread_id="t-1", seed_id="seed-1", author="R. Ginsburgh",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC), model="m", status="approved",
        grounded=True, text="developed", cited_refs=["Tanya 1:6"], grounded_in=["Tanya 1:6"],
    )
    s.developments.save_development(dev)
    chunk = _seed_indexed(s, Chunk.make(
        ref="Derived · dev-1", book="Derived", section_path=["Derived"], lang="en",
        text="a derived development", source="derived", metadata={"development_id": "dev-1"},
    ))

    s.svc.retract(chunk.ref, author="Editor", reason="reconsidered")

    flipped = s.developments.get_development("dev-1")
    assert flipped is not None and flipped.status == "retracted"


def test_retracting_term_chunk_marks_the_term_retracted() -> None:
    s = _setup()
    term = Term(id="term-1", canonical="Ab", definition="Name of 72", author="R. Ginsburgh")
    s.terms.create_term(term)
    chunk = _seed_indexed(s, Chunk.make(
        ref="Term · Ab", book="Lexicon", section_path=["Lexicon"], lang="en",
        text="Ab — Name of 72", source="term", metadata={"term_id": "term-1"},
    ))

    s.svc.retract(chunk.ref, author="Editor", reason="duplicate")

    marked = s.terms.get_term("term-1")
    assert marked is not None and marked.retracted is True


# -- UI route happy-path + rejection path ------------------------------------

class _Stub:
    """Catch-all stub for the UI collaborators the retract routes never touch."""

    def __getattr__(self, _name: str):  # noqa: ANN204
        raise AssertionError("retract routes must not call other services")


def _ui_client(s: Setup) -> TestClient:
    app = create_app(  # type: ignore[arg-type]
        _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), s.svc, _Stub(), _Stub()
    )
    return TestClient(app)


def test_ui_retract_happy_path() -> None:
    s = _setup()
    chunk = _seed_indexed(s, _expert_chunk())
    client = _ui_client(s)

    resp = client.post(
        "/retract", json={"target": chunk.ref, "author": "Editor", "reason": "wrong"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ref"] == chunk.ref and body["source"] == "expert" and body["author"] == "Editor"
    assert chunk.ref not in _retrieve_refs(s, "ahava connects nefesh keser")
    # And it lists.
    listed = client.get("/retractions").json()
    assert [x["id"] for x in listed] == [body["id"]]


def test_ui_retract_rejects_printed_text_with_400() -> None:
    s = _setup()
    chunk = _seed_indexed(s, Chunk.make(
        ref="Tanya 1:1", book="Tanya", section_path=["1"], lang="he",
        text="printed", source="sefaria",
    ))
    client = _ui_client(s)

    resp = client.post(
        "/retract", json={"target": chunk.ref, "author": "Editor", "reason": "no"}
    )
    assert resp.status_code == 400
    assert "printed text" in resp.json()["detail"]
    assert s.index.retrieve(chunk.id) is not None  # untouched


def test_ui_retract_rejects_blank_author_with_400() -> None:
    s = _setup()
    chunk = _seed_indexed(s, _expert_chunk())
    client = _ui_client(s)

    resp = client.post("/retract", json={"target": chunk.ref, "author": "  ", "reason": "x"})
    assert resp.status_code == 400
    assert s.index.retrieve(chunk.id) is not None  # nothing removed
