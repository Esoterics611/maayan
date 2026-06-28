"""StatsService: aggregate the knowledge base, read-only.

All stores are injected (DI house rule). Nothing here writes; it only counts. The
Qdrant point count is best-effort — if the vector store isn't reachable, the rest of
the dashboard still renders and `qdrant_points` is left None.
"""

from __future__ import annotations

from typing import Protocol

from maayan.capture.store import CaptureStore
from maayan.corpus.store import ChunkStore
from maayan.develop.store import DevelopmentStore
from maayan.index.qdrant import QdrantIndex
from maayan.lexicon.store import TermStore
from maayan.retract.store import RetractionStore
from maayan.stats.models import Stats
from maayan.threads.store import ThreadStore

# The canonical source order for display (others, if any, are appended after).
_SOURCE_ORDER = ("sefaria", "chabad", "expert", "derived", "term", "shiur")


class Statsing(Protocol):
    """The single method the UI/CLI depend on (DI seam)."""

    def collect(self) -> Stats: ...


class StatsService:
    """Read-only aggregation across every store + an optional Qdrant point count."""

    def __init__(
        self,
        chunk_store: ChunkStore,
        capture_store: CaptureStore,
        development_store: DevelopmentStore,
        retraction_store: RetractionStore,
        thread_store: ThreadStore,
        term_store: TermStore,
        index: QdrantIndex | None = None,
    ) -> None:
        self._chunks = chunk_store
        self._capture = capture_store
        self._developments = development_store
        self._retractions = retraction_store
        self._threads = thread_store
        self._terms = term_store
        self._index = index

    def collect(self) -> Stats:
        return Stats(
            total_chunks=self._chunks.count(),
            chunks_by_source=self._chunks.counts_by_source(),
            chunks_by_book=self._chunks.counts_by_book(),
            contributions_by_author=self._capture.counts_by_author(),
            developments_by_status=self._developments.counts_by_status(),
            retractions=self._retractions.count(),
            threads=self._threads.count(),
            terms=self._terms.count(),
            qdrant_points=self._qdrant_count(),
        )

    def _qdrant_count(self) -> int | None:
        if self._index is None:
            return None
        try:
            return self._index.count()
        except Exception:  # noqa: BLE001 — best-effort; a down vector store must not break stats
            return None


def _ordered(counts: dict[str, int], order: tuple[str, ...]) -> list[tuple[str, int]]:
    """Counts in a stable display order: known keys first (in `order`), then the rest."""
    known = [(k, counts[k]) for k in order if k in counts]
    rest = sorted((k, v) for k, v in counts.items() if k not in order)
    return known + rest


def format_stats(stats: Stats) -> str:
    """Render the dashboard as a compact, aligned table."""
    lines = [
        "Knowledge base — health",
        "=" * 32,
        f"Live chunks: {stats.total_chunks}"
        + (f"   (Qdrant points: {stats.qdrant_points})" if stats.qdrant_points is not None else ""),
        "",
        "Chunks by source:",
    ]
    for source, n in _ordered(stats.chunks_by_source, _SOURCE_ORDER):
        lines.append(f"  {source:<10} {n:>6}")
    lines += ["", "Chunks by book:"]
    for book, n in sorted(stats.chunks_by_book.items()):
        lines.append(f"  {book:<22} {n:>6}")
    lines += ["", f"Contributions by author ({sum(stats.contributions_by_author.values())} total):"]
    for author, n in sorted(stats.contributions_by_author.items()):
        lines.append(f"  {author:<22} {n:>6}")
    lines += ["", "Developments by status:"]
    for status, n in _ordered(
        stats.developments_by_status, ("proposed", "approved", "rejected", "retracted")
    ):
        lines.append(f"  {status:<10} {n:>6}")
    lines += [
        "",
        f"Retractions: {stats.retractions}",
        f"Threads:     {stats.threads}",
        f"Terms:       {stats.terms}",
    ]
    return "\n".join(lines)
