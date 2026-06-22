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

import re
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

# Split AFTER a sentence-ending period + whitespace. Hebrew abbreviations here use
# gershayim (״) / geresh (׳), not ".", so a "." reliably marks a sentence end.
_SENTENCE_BOUNDARY = re.compile(r"(?<=\.)\s+")


def split_passages(text: str, *, max_chars: int) -> list[str]:
    """Split text into coherent passages of <= ~max_chars, never mid-sentence.

    Whole sentences are packed greedily up to ``max_chars``; a single over-long
    sentence becomes its own passage. A tiny trailing remainder is merged back so we
    never emit slivers. ``max_chars <= 0`` (or text already short) → one passage.
    """
    text = text.strip()
    if not text:
        return []
    if max_chars <= 0 or len(text) <= max_chars:
        return [text]
    passages: list[str] = []
    current = ""
    for sentence in _SENTENCE_BOUNDARY.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if current and len(current) + 1 + len(sentence) > max_chars:
            passages.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}" if current else sentence
    if current:
        if passages and len(current) < max_chars // 4:
            passages[-1] = f"{passages[-1]} {current}"  # merge a sliver tail
        else:
            passages.append(current)
    return passages


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


def chabad_leaf_to_chunks(leaf: ChabadLeaf, *, book: str, max_chars: int = 0) -> list[Chunk]:
    """Normalize a leaf's HTML and split it into one or more `source="chabad"` chunks.

    A short section yields one chunk (ref ``Book, parsha, א א``); a long one is split at
    sentence boundaries into passages, each a chunk with a ``§N`` suffix so the citation
    stays precise and traceable. Empty leaves yield nothing.
    """
    text = normalize_text(leaf.text_html)
    section_path = leaf.path or [book]
    base_ref = f"{book}, {', '.join(section_path)}" if section_path else book
    passages = split_passages(text, max_chars=max_chars)
    chunks: list[Chunk] = []
    multi = len(passages) > 1
    for i, passage in enumerate(passages, start=1):
        ref = f"{base_ref} §{i}" if multi else base_ref
        path = [*section_path, f"§{i}"] if multi else section_path
        chunks.append(
            Chunk.make(
                ref=ref,
                book=book,
                section_path=path,
                lang="he",  # the Chabad Library chassidus text is Hebrew
                text=passage,
                source=CHABAD_SOURCE,
                metadata={
                    "provider": "chabadlibrary.org",
                    "section_id": leaf.id,
                    "path": section_path,
                    "passage": i,
                },
            )
        )
    return chunks


async def ingest_chabad_book(
    root_id: int,
    book: str,
    *,
    client: ChabadLibraryClient,
    store: ChunkStore,
    max_leaves: int | None = None,
    max_chars: int = 0,
) -> IngestResult:
    """Walk a Chabad Library book, normalize+split each leaf, and upsert chunks."""
    written = 0
    leaves = 0
    async for leaf in client.iter_leaves(root_id, max_leaves=max_leaves):
        chunks = chabad_leaf_to_chunks(leaf, book=book, max_chars=max_chars)
        if not chunks:
            continue
        written += store.upsert_chunks(chunks)
        leaves += 1
    return IngestResult(book=book, sections=leaves, chunks=written)


async def ingest_chabad_books(
    books: Sequence[tuple[str, int]],
    *,
    client: ChabadLibraryClient,
    store: ChunkStore,
    max_leaves: int | None = None,
    max_chars: int = 0,
) -> list[IngestResult]:
    """Ingest several Chabad Library books (name, root_id) in sequence."""
    results: list[IngestResult] = []
    for book, root_id in books:
        results.append(
            await ingest_chabad_book(
                root_id, book, client=client, store=store,
                max_leaves=max_leaves, max_chars=max_chars,
            )
        )
    return results
