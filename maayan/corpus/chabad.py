"""Async client + ingestion for the Chabad Library (chabadlibrary.org) JSON API.

Likutei Torah is **not on Sefaria**, so we pull it from chabadlibrary.org, whose
SPA is backed by a clean JSON API:

    GET {base}/main?path=<section_id>   ->   {"content": {...}, "sections": {...}}

`content.type` is ``"children"`` for a section (``content.data`` = a list of
``{id, heading}``) or ``"page"`` for a leaf (``content.data.text`` = the text as
HTML). We walk a book's tree (book → parshiyot → daf-pages), strip the HTML with the
same normalizer used for Sefaria (markup out, **nikkud kept**), and emit `Chunk`s
tagged ``source="chabad"`` so they sit in the same Knowledge base as the Sefaria
text, distinguishable by provenance.

DI throughout: the `httpx.AsyncClient` and `Clock` are injected; rate limiting is
driven by the injected clock (never `time.sleep`). Responses are brotli-encoded —
httpx decodes them transparently because `brotli` is a dependency.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx
from pydantic import BaseModel, Field

from maayan.clock import Clock
from maayan.corpus.ingest import IngestResult
from maayan.corpus.models import Chunk
from maayan.corpus.normalize import normalize_text
from maayan.corpus.store import ChunkStore

CHABAD_SOURCE = "chabad"


class ChabadError(RuntimeError):
    """Raised when the Chabad Library API returns an error or an unexpected shape."""


class ChabadChild(BaseModel):
    """One child node (a section or a leaf) under a Chabad Library section."""

    id: int
    heading: str


class ChabadNode(BaseModel):
    """A resolved node: either a section (children) or a leaf page (text HTML)."""

    id: int
    is_leaf: bool
    children: list[ChabadChild] = Field(default_factory=list)
    text_html: str | None = None


class ChabadLeaf(BaseModel):
    """A leaf page with its ancestor headings (for the citation ref) and text HTML."""

    id: int
    path: list[str]  # ancestor headings from the root book down to (and incl.) the leaf
    text_html: str


class ChabadLibraryClient:
    """Walks the Chabad Library tree and yields leaf pages. Rate-limited via the Clock."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        clock: Clock,
        *,
        base_url: str = "https://chabadlibrary.org/books/api",
        rate_limit_seconds: float = 0.3,
    ) -> None:
        self._http = http
        self._clock = clock
        self._base_url = base_url.rstrip("/")
        self._rate_limit_seconds = rate_limit_seconds
        self._last_request: float | None = None

    async def _throttle(self) -> None:
        if self._last_request is not None:
            wait = self._rate_limit_seconds - (self._clock.monotonic() - self._last_request)
            if wait > 0:
                await self._clock.sleep(wait)
        self._last_request = self._clock.monotonic()

    async def fetch_node(self, section_id: int) -> ChabadNode:
        """Resolve one section id to its children (a section) or its text (a leaf)."""
        await self._throttle()
        resp = await self._http.get(
            f"{self._base_url}/main", params={"path": str(section_id)}
        )
        resp.raise_for_status()
        data: Any = resp.json()
        if not isinstance(data, dict) or "content" not in data:
            raise ChabadError(f"Unexpected response for section {section_id!r}.")
        content = data["content"] or {}
        if content.get("type") == "page":
            page = content.get("data") or {}
            return ChabadNode(id=section_id, is_leaf=True, text_html=str(page.get("text", "")))
        raw_children = content.get("data") or []
        children = [
            ChabadChild(id=int(c["id"]), heading=str(c.get("heading", "")))
            for c in raw_children
            if isinstance(c, dict) and "id" in c
        ]
        return ChabadNode(id=section_id, is_leaf=False, children=children)

    async def iter_leaves(
        self, root_id: int, *, max_leaves: int | None = None
    ) -> AsyncIterator[ChabadLeaf]:
        """Depth-first walk of a book tree, yielding leaf pages with their heading path."""
        count = 0
        async for leaf in self._walk(root_id, []):
            yield leaf
            count += 1
            if max_leaves is not None and count >= max_leaves:
                return

    async def _walk(self, node_id: int, parents: list[str]) -> AsyncIterator[ChabadLeaf]:
        node = await self.fetch_node(node_id)
        if node.is_leaf:
            yield ChabadLeaf(id=node_id, path=parents, text_html=node.text_html or "")
            return
        for child in node.children:
            async for leaf in self._walk(child.id, [*parents, child.heading]):
                yield leaf


def chabad_leaf_to_chunk(leaf: ChabadLeaf, *, book: str) -> Chunk | None:
    """Normalize a leaf's HTML to one Hebrew `Chunk` (source="chabad"); None if empty."""
    text = normalize_text(leaf.text_html)
    if not text:
        return None
    section_path = leaf.path or [book]
    ref = f"{book}, {', '.join(section_path)}" if section_path else book
    return Chunk.make(
        ref=ref,
        book=book,
        section_path=section_path,
        lang="he",  # the Chabad Library chassidus text is Hebrew
        text=text,
        source=CHABAD_SOURCE,
        metadata={
            "provider": "chabadlibrary.org",
            "section_id": leaf.id,
            "path": section_path,
        },
    )


async def ingest_chabad_book(
    root_id: int,
    book: str,
    *,
    client: ChabadLibraryClient,
    store: ChunkStore,
    max_leaves: int | None = None,
) -> IngestResult:
    """Walk a Chabad Library book, normalize each leaf, and upsert chunks into the store."""
    written = 0
    leaves = 0
    async for leaf in client.iter_leaves(root_id, max_leaves=max_leaves):
        chunk = chabad_leaf_to_chunk(leaf, book=book)
        if chunk is None:
            continue
        written += store.upsert_chunks([chunk])
        leaves += 1
    return IngestResult(book=book, sections=leaves, chunks=written)


async def ingest_chabad_books(
    books: Sequence[tuple[str, int]],
    *,
    client: ChabadLibraryClient,
    store: ChunkStore,
    max_leaves: int | None = None,
) -> list[IngestResult]:
    """Ingest several Chabad Library books (name, root_id) in sequence."""
    results: list[IngestResult] = []
    for book, root_id in books:
        results.append(
            await ingest_chabad_book(
                root_id, book, client=client, store=store, max_leaves=max_leaves
            )
        )
    return results
