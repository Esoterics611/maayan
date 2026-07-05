"""SummaryService (Prompt 42): drip-draft → gate → index gated section summaries.

Mirrors the develop/populate discipline: drafting produces PROPOSALS (indexing nothing);
`approve` is the only path that indexes — as a ``source="summary"`` chunk carrying the
parent ref and child refs in metadata, retrievable like everything else and retractable
through the audited flow. Printed text is never touched. Pacing/backoff/resume reuse the
populate drip; deterministic ids make re-runs idempotent.
"""

from __future__ import annotations

from collections.abc import Sequence

from maayan.capture.convert import detect_lang
from maayan.clock import Clock
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.embed.base import Embedder
from maayan.index.qdrant import QdrantIndex
from maayan.populate.drip import DripStats, run_drip
from maayan.summarize.draft import SummaryDrafter
from maayan.summarize.models import Summary, summary_chunk_id
from maayan.summarize.store import SummaryStore


class SummaryService:
    """Draft, gate, and index one-level section summaries; collaborators injected."""

    def __init__(
        self,
        drafter: SummaryDrafter,
        chunks: ChunkStore,
        store: SummaryStore,
        embedder: Embedder,
        index: QdrantIndex,
        clock: Clock,
        *,
        pace: float = 20.0,
        max_retries: int = 5,
        backoff: float = 30.0,
    ) -> None:
        self._drafter = drafter
        self._chunks = chunks
        self._store = store
        self._embedder = embedder
        self._index = index
        self._clock = clock
        self._pace = pace
        self._max_retries = max_retries
        self._backoff = backoff

    async def draft_book(
        self, book: str, *, units: int | None = None, persist_unsupported: bool = False
    ) -> DripStats:
        """Draft a summary per section of `book` (paced), skipping already-summarized ones."""
        todo: list[tuple[str, str]] = [
            (label, ref)
            for label, ref, _lang in self._chunks.list_sections(book)
            if ref and not self._already_summarized(ref)
        ]
        if units is not None:
            todo = todo[:units]

        def draft_one(section: tuple[str, str]) -> Sequence[Summary]:
            label, ref = section
            children = self._chunks.get_section(ref, lang="he", include_retracted=False)
            summary = self._drafter.draft(
                book=book, parent_ref=ref, parent_label=label, children=children
            )
            if summary.supported or persist_unsupported:
                self._store.save(summary)
            return [summary]

        return await run_drip(
            todo, draft_one, clock=self._clock, pace=self._pace,
            max_retries=self._max_retries, backoff=self._backoff,
        )

    def approve(self, summary_id: str, *, author: str) -> Summary:
        """Promote a supported summary to an indexed ``summary`` chunk (author = approver)."""
        summary = self._require(summary_id)
        if not summary.supported:
            raise ValueError("Refusing to index an unsupported (ungrounded) summary.")
        if summary.status == "approved":
            raise ValueError(f"Summary {summary_id!r} is already approved.")
        approved = summary.model_copy(update={"status": "approved", "author": author.strip()})
        self._index_summary(approved)
        return self._store.save(approved)

    def reject(self, summary_id: str) -> Summary:
        """Reject a proposed summary. Indexes nothing — the corpus is unchanged."""
        rejected = self._require(summary_id).model_copy(update={"status": "rejected"})
        return self._store.save(rejected)

    def get(self, summary_id: str) -> Summary | None:
        return self._store.get(summary_id)

    def list(self, *, status: str | None = None, book: str | None = None) -> list[Summary]:
        return self._store.list(status=status, book=book)

    # -- internals ---------------------------------------------------------------
    def _already_summarized(self, parent_ref: str) -> bool:
        from maayan.summarize.models import summary_id as _sid

        return self._store.get(_sid(parent_ref)) is not None

    def _index_summary(self, summary: Summary) -> None:
        """Index one summary as a retrievable ``summary`` chunk with parent/child metadata."""
        chunk = Chunk(
            id=summary_chunk_id(summary.parent_ref),
            ref=summary.summary_chunk_ref(),
            book=summary.book,
            section_path=[summary.book, "summary", summary.parent_label or summary.parent_ref],
            lang=detect_lang(summary.text),
            text=summary.text,
            source="summary",
            metadata={
                "parent_ref": summary.parent_ref,
                "child_refs": summary.child_refs,
                "cited_refs": summary.cited_refs,
                "author": summary.author,
                "summary_id": summary.id,
            },
        )
        self._chunks.upsert_chunks([chunk])
        self._chunks.mark_indexed([chunk.id])
        self._index.ensure_collection()
        embeddings = self._embedder.embed([chunk.text])
        self._index.upsert_chunks(list(zip([chunk], embeddings, strict=True)))

    def _require(self, summary_id: str) -> Summary:
        summary = self._store.get(summary_id)
        if summary is None:
            raise ValueError(f"Summary {summary_id!r} not found.")
        return summary
