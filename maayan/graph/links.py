"""Curated + deterministic edges at $0 (Prompt 34): Sefaria links + pasuk anchors.

Two model-free sources of graph edges:

1. **Sefaria's curated link graph** — `GET /api/links/{ref}` returns human-curated
   intertextual links for any ref (verified live 2026-07-02: a flat JSON list of
   link objects carrying `ref`, `anchorRef`, `category`, `type`). Links in a kept
   category (config: `sefaria_link_categories`) become relations: rel_type
   "quotes_pasuk" when the target is Tanach, else "quotes"; evidence "curated";
   author "sefaria:links". Curated human data passes the gate by policy, so the
   relations land "approved" — the author string keeps them distinguishable.

2. **The pasuk as a join key** — two corpus passages quoting the same pasuk are
   related by construction. Every pair of corpus refs sharing a `quotes_pasuk`
   target gains a "parallels" relation, evidence "deterministic", author
   "system:pasuk-join", the shared pasuk in the note. This is the cross-work
   linking (Tanya ↔ Torah Ohr through a shared pasuk) at zero model cost.

Resumable like the populate drip: fetched refs land in a cursor table and are
skipped on re-run; failures are NOT cursored, so the next run retries them.
Confidence 1.0 on both sources is policy, not a tunable: curated links are
asserted by Sefaria's editors, and the pasuk join is true by construction.
"""

from __future__ import annotations

import sqlite3
from itertools import combinations
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from maayan.clock import Clock
from maayan.config import Settings
from maayan.corpus.store import ChunkStore
from maayan.graph.models import (
    LinksIngestResult,
    PasukJoinResult,
    RefEndpoint,
    Relation,
    RelationType,
)
from maayan.graph.store import GraphStore

LINKS_AUTHOR = "sefaria:links"
PASUK_JOIN_AUTHOR = "system:pasuk-join"
# The Sefaria category that marks a Tanach target → rel_type "quotes_pasuk".
TANAKH_CATEGORY = "Tanakh"
# Policy, not tunables (see module docstring).
CURATED_CONFIDENCE = 1.0
DETERMINISTIC_CONFIDENCE = 1.0


class SefariaLink(BaseModel):
    """One curated link as returned by /api/links/{ref} (the fields we use)."""

    ref: str  # the far (linked) ref
    anchor_ref: str  # the ref the link is anchored on (ours)
    category: str = ""
    link_type: str = ""  # payload "type", e.g. "quotation" | "commentary" | ""


class SefariaLinksError(RuntimeError):
    """Raised when the links endpoint returns an error payload or a non-list."""


def parse_links(data: Any) -> list[SefariaLink]:
    """Parse a raw /api/links payload; malformed entries are skipped, not fatal."""
    if isinstance(data, dict) and data.get("error"):
        raise SefariaLinksError(str(data["error"]))
    if not isinstance(data, list):
        raise SefariaLinksError(f"Expected a list of links, got {type(data).__name__}.")
    links: list[SefariaLink] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        ref = str(entry.get("ref") or "").strip()
        anchor = str(entry.get("anchorRef") or "").strip()
        if not ref or not anchor:
            continue
        links.append(
            SefariaLink(
                ref=ref,
                anchor_ref=anchor,
                category=str(entry.get("category") or ""),
                link_type=str(entry.get("type") or ""),
            )
        )
    return links


class SefariaLinksClient:
    """Fetches curated links from Sefaria. DI + Clock pacing, like SefariaClient."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        clock: Clock,
        *,
        base_url: str = "https://www.sefaria.org/api",
        rate_limit_seconds: float = 0.5,
    ) -> None:
        self._http = http
        self._clock = clock
        self._base_url = base_url.rstrip("/")
        self._rate_limit_seconds = rate_limit_seconds
        self._last_request: float | None = None

    async def _throttle(self) -> None:
        """Ensure at least `rate_limit_seconds` between requests, via the Clock."""
        if self._last_request is not None:
            wait = self._rate_limit_seconds - (self._clock.monotonic() - self._last_request)
            if wait > 0:
                await self._clock.sleep(wait)
        self._last_request = self._clock.monotonic()

    async def fetch_links(self, ref: str) -> list[SefariaLink]:
        await self._throttle()
        resp = await self._http.get(f"{self._base_url}/links/{quote(ref)}")
        resp.raise_for_status()
        return parse_links(resp.json())


class LinksCursorStore:
    """Which refs have had their links fetched — the drip-style resume cursor."""

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(
            "CREATE TABLE IF NOT EXISTS graph_links_cursor (\n"
            "    ref        TEXT PRIMARY KEY,\n"
            "    fetched_at TEXT NOT NULL,\n"
            "    links_kept INTEGER NOT NULL\n"
            ");"
        )
        self._conn.commit()

    def is_fetched(self, ref: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM graph_links_cursor WHERE ref = ?", (ref,)
        ).fetchone()
        return row is not None

    def mark_fetched(self, ref: str, *, links_kept: int, clock: Clock) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO graph_links_cursor (ref, fetched_at, links_kept) "
            "VALUES (?, ?, ?)",
            (ref, clock.now().isoformat(), links_kept),
        )
        self._conn.commit()

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM graph_links_cursor").fetchone()
        return int(row["n"])

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> LinksCursorStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def link_to_relation(
    our_ref: str, link: SefariaLink, clock: Clock, settings: Settings
) -> Relation | None:
    """Map one curated link to a Relation, or None when its category isn't kept."""
    if link.category not in settings.sefaria_link_categories:
        return None
    if link.ref == our_ref:
        return None  # no self-loops
    rel_type: RelationType = "quotes_pasuk" if link.category == TANAKH_CATEGORY else "quotes"
    return Relation.make(
        subject=RefEndpoint(ref=our_ref),
        object=RefEndpoint(ref=link.ref),
        rel_type=rel_type,
        evidence="curated",
        confidence=CURATED_CONFIDENCE,
        status="approved",  # curated human data passes the gate by policy
        author=LINKS_AUTHOR,
        note=f"category: {link.category}" + (f", type: {link.link_type}" if link.link_type else ""),
        created_at=clock.now(),
    )


async def ingest_links(
    chunk_store: ChunkStore,
    graph_store: GraphStore,
    cursor: LinksCursorStore,
    client: SefariaLinksClient,
    clock: Clock,
    settings: Settings,
    *,
    book: str | None = None,
    limit: int | None = None,
) -> LinksIngestResult:
    """Fetch curated links for every (unfetched) sefaria chunk ref in the corpus."""
    result = LinksIngestResult()
    for ref in _corpus_refs(chunk_store, book=book):
        result.refs_seen += 1
        if cursor.is_fetched(ref):
            result.refs_skipped += 1
            continue
        if limit is not None and result.refs_fetched >= limit:
            break
        try:
            links = await client.fetch_links(ref)
        except (httpx.HTTPError, SefariaLinksError):
            # Not cursored: the next run retries this ref (drip-style resumability).
            result.refs_failed += 1
            continue
        result.refs_fetched += 1
        result.links_seen += len(links)
        kept = 0
        for link in links:
            relation = link_to_relation(ref, link, clock, settings)
            if relation is None:
                continue
            kept += 1
            if graph_store.get_relation(relation.id) is None:
                result.relations_created += 1
            else:
                result.relations_existing += 1
            graph_store.save_relation(relation)
        result.links_kept += kept
        cursor.mark_fetched(ref, links_kept=kept, clock=clock)
    return result


def pasuk_join(graph_store: GraphStore, clock: Clock) -> PasukJoinResult:
    """Join corpus refs through shared pasuk anchors — deterministic, no model.

    Every unordered pair of refs holding an approved `quotes_pasuk` edge to the
    same target gains a "parallels" relation. Pairs are ordered lexically so the
    derived relation id (and therefore the join) is idempotent.
    """
    result = PasukJoinResult()
    by_pasuk: dict[str, set[str]] = {}
    for relation in graph_store.list_relations(rel_type="quotes_pasuk", status="approved"):
        s_endpoint, o_endpoint = relation.subject, relation.object
        if isinstance(s_endpoint, RefEndpoint) and isinstance(o_endpoint, RefEndpoint):
            by_pasuk.setdefault(o_endpoint.ref, set()).add(s_endpoint.ref)
    for pasuk, refs in sorted(by_pasuk.items()):
        if len(refs) < 2:
            continue
        result.pasukim += 1
        for left, right in combinations(sorted(refs), 2):
            result.pairs += 1
            relation = Relation.make(
                subject=RefEndpoint(ref=left),
                object=RefEndpoint(ref=right),
                rel_type="parallels",
                evidence="deterministic",
                confidence=DETERMINISTIC_CONFIDENCE,
                status="approved",  # true by construction; the note shows the construction
                author=PASUK_JOIN_AUTHOR,
                note=f"shared pasuk: {pasuk}",
                created_at=clock.now(),
            )
            if graph_store.get_relation(relation.id) is None:
                result.relations_created += 1
            else:
                result.relations_existing += 1
            graph_store.save_relation(relation)
    return result


def _corpus_refs(chunk_store: ChunkStore, *, book: str | None) -> list[str]:
    """Distinct sefaria chunk refs (he+en share a ref), optionally book-filtered.

    `book` matches either the chunk's book field ("Tanya") or a ref prefix
    ("Tanya, Part I; Likkutei Amarim"), so the CLI accepts both spellings.
    """
    refs: list[str] = []
    seen: set[str] = set()
    for chunk in chunk_store.get_chunks(source="sefaria"):
        if book is not None and chunk.book != book and not chunk.ref.startswith(book):
            continue
        if chunk.ref not in seen:
            seen.add(chunk.ref)
            refs.append(chunk.ref)
    return refs
