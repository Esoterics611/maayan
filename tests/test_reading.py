"""Reading/library route tests (Prompt 29) — thin reads over a seeded ChunkStore."""

from __future__ import annotations

from fastapi.testclient import TestClient

from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.ui.app import create_app


def _client() -> TestClient:
    store = ChunkStore(":memory:")
    store.upsert_chunks([
        Chunk.make(ref="Tanya 1:1", book="Tanya", section_path=["Chapter 1", "Paragraph 1"],
                   lang="he", text="ראשית"),
        Chunk.make(ref="Tanya 1:2", book="Tanya", section_path=["Chapter 1", "Paragraph 2"],
                   lang="he", text="ועוד"),
        Chunk.make(ref="Tanya 2:1", book="Tanya", section_path=["Chapter 2", "Paragraph 1"],
                   lang="he", text="פרק ב"),
    ])
    app = create_app(  # type: ignore[arg-type]
        None, None, None, None, None, None, None, None, chunks=store
    )
    return TestClient(app)


def test_source_in_context_returns_section_with_cited_flag() -> None:
    client = _client()
    r = client.get("/api/source", params={"ref": "Tanya 1:2"})
    assert r.status_code == 200
    data = r.json()
    assert data["label"] == "Chapter 1" and data["book"] == "Tanya"
    # Whole chapter, in order, with the requested ref flagged for highlight.
    assert [(c["ref"], c["cited"]) for c in data["chunks"]] == [
        ("Tanya 1:1", False), ("Tanya 1:2", True),
    ]
    assert client.get("/api/source", params={"ref": "nope"}).status_code == 404


def test_library_and_sections() -> None:
    client = _client()
    lib = client.get("/api/library").json()
    assert {"book": "Tanya", "source": "sefaria", "count": 3} in lib["entries"]
    secs = client.get("/api/library/sections", params={"book": "Tanya"}).json()
    assert [s["label"] for s in secs["sections"]] == ["Chapter 1", "Chapter 2"]


def test_reading_routes_inert_without_store() -> None:
    app = create_app(None, None, None, None, None, None, None, None)  # type: ignore[arg-type]
    client = TestClient(app)
    assert client.get("/api/source", params={"ref": "x"}).status_code == 503
    assert client.get("/api/library").status_code == 503
