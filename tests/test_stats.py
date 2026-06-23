"""Tests for Prompt 19 — `maayan stats` (knowledge-base health).

Aggregation against a seeded temp SQLite (exact counts) + the /stats route with a
mocked service. No network, no models.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from maayan.capture.models import Annotation
from maayan.capture.store import CaptureStore
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.develop.models import Development
from maayan.develop.store import DevelopmentStore
from maayan.embed.fake import HashingEmbedder
from maayan.index.qdrant import QdrantIndex
from maayan.lexicon.models import Term
from maayan.lexicon.store import TermStore
from maayan.retract.models import Retraction
from maayan.retract.store import RetractionStore
from maayan.stats.models import Stats
from maayan.stats.service import StatsService, format_stats
from maayan.threads.models import Thread
from maayan.threads.store import ThreadStore
from maayan.ui.app import create_app

DIM = 64
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _ann(author: str, n: int) -> Annotation:
    return Annotation(id=f"a-{n}", session_id="s", timestamp=NOW, author=author,
                      kind="connection", body="b")


def _dev(status: str, n: int) -> Development:
    return Development(id=f"d-{n}", thread_id="t", seed_id="s", author="A", timestamp=NOW,
                       model="m", status=status, grounded=True, text="x")  # type: ignore[arg-type]


def _seed_db(db: str) -> ChunkStore:
    chunks = ChunkStore(db)
    chunks.upsert_chunks([
        Chunk.make(ref="Tanya 1:1", book="Tanya", section_path=["1"], lang="he", text="a",
                   source="sefaria"),
        Chunk.make(ref="Tanya 1:2", book="Tanya", section_path=["1"], lang="he", text="b",
                   source="sefaria"),
        Chunk.make(ref="Torah Ohr, Bereshit 1:1", book="Torah Ohr", section_path=["1"],
                   lang="he", text="c", source="sefaria"),
        Chunk.make(ref="Expert · x", book="Expert", section_path=["x"], lang="en", text="d",
                   source="expert"),
        Chunk.make(ref="Derived · y", book="Derived", section_path=["y"], lang="en", text="e",
                   source="derived"),
    ])
    # One retracted expert chunk — must be excluded from the live counts.
    gone = Chunk.make(ref="Expert · gone", book="Expert", section_path=["x"], lang="en",
                      text="f", source="expert")
    chunks.upsert_chunks([gone])
    chunks.mark_retracted([gone.id])

    capture = CaptureStore(db)
    capture.save_annotation(_ann("Alice", 1))
    capture.save_annotation(_ann("Alice", 2))
    capture.save_annotation(_ann("Bob", 3))

    devs = DevelopmentStore(db)
    devs.save_development(_dev("proposed", 1))
    devs.save_development(_dev("approved", 2))
    devs.save_development(_dev("retracted", 3))

    RetractionStore(db).save_retraction(Retraction(
        id="r-1", chunk_id="c", ref="Expert · gone", source="expert", author="Ed",
        reason="superseded", timestamp=NOW))

    th = ThreadStore(db)
    th.create_thread(Thread(id="t-1", title="one", created_at=NOW, updated_at=NOW))
    th.create_thread(Thread(id="t-2", title="two", created_at=NOW, updated_at=NOW))

    terms = TermStore(db)
    terms.create_term(Term(id="term-1", canonical="Ab", definition="72", author="A"))
    gone_term = Term(id="term-2", canonical="Sag", definition="63", author="A")
    terms.create_term(gone_term)
    terms.mark_retracted("term-2")  # live terms count excludes it
    return chunks


def test_aggregates_exact_counts(tmp_path: Path) -> None:
    db = str(tmp_path / "maayan.sqlite3")
    _seed_db(db)

    # Seed Qdrant with two points so the optional point count flows through.
    index = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
    emb = HashingEmbedder(dim=DIM)
    index.ensure_collection()
    pts = [
        Chunk.make(ref="p1", book="B", section_path=["1"], lang="en", text="x", source="sefaria"),
        Chunk.make(ref="p2", book="B", section_path=["1"], lang="en", text="y", source="sefaria"),
    ]
    index.upsert_chunks(list(zip(pts, emb.embed([p.text for p in pts]), strict=True)))

    svc = StatsService(
        ChunkStore(db), CaptureStore(db), DevelopmentStore(db),
        RetractionStore(db), ThreadStore(db), TermStore(db), index,
    )
    stats = svc.collect()

    assert stats.total_chunks == 5  # the retracted expert chunk is excluded
    assert stats.chunks_by_source == {"sefaria": 3, "expert": 1, "derived": 1}
    assert stats.chunks_by_book == {"Tanya": 2, "Torah Ohr": 1, "Expert": 1, "Derived": 1}
    assert stats.contributions_by_author == {"Alice": 2, "Bob": 1}
    assert stats.developments_by_status == {"proposed": 1, "approved": 1, "retracted": 1}
    assert stats.retractions == 1
    assert stats.threads == 2
    assert stats.terms == 1  # the retracted term is excluded
    assert stats.qdrant_points == 2


def test_qdrant_count_is_none_without_index(tmp_path: Path) -> None:
    db = str(tmp_path / "maayan.sqlite3")
    _seed_db(db)
    svc = StatsService(
        ChunkStore(db), CaptureStore(db), DevelopmentStore(db),
        RetractionStore(db), ThreadStore(db), TermStore(db), None,
    )
    assert svc.collect().qdrant_points is None


def test_format_stats_renders_numbers() -> None:
    stats = Stats(
        total_chunks=5, chunks_by_source={"sefaria": 3, "expert": 2},
        chunks_by_book={"Tanya": 3}, contributions_by_author={"Alice": 2},
        developments_by_status={"approved": 1}, retractions=1, threads=2, terms=4,
        qdrant_points=5,
    )
    text = format_stats(stats)
    assert "Live chunks: 5" in text
    assert "Qdrant points: 5" in text
    assert "sefaria" in text and "Tanya" in text and "Alice" in text
    assert "Retractions: 1" in text and "Terms:       4" in text


# -- route happy-path with a mocked service ----------------------------------
class _Stub:
    def __getattr__(self, _name: str):  # noqa: ANN204
        raise AssertionError("the /stats route must not call other services")


class _FakeStats:
    def collect(self) -> Stats:
        return Stats(total_chunks=7, chunks_by_source={"sefaria": 7}, threads=1, terms=2)


def test_stats_route_happy_path() -> None:
    app = create_app(  # type: ignore[arg-type]
        _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), _Stub(), _FakeStats(), _Stub()
    )
    resp = TestClient(app).get("/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_chunks"] == 7
    assert body["chunks_by_source"] == {"sefaria": 7}
    assert body["terms"] == 2
