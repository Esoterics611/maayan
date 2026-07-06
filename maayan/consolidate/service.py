"""SugyaService (Prompt 41): draft → gate → index → version a sugya page.

The trust core is untouched:

* drafting produces a PROPOSAL and indexes nothing;
* `approve` is the only path that indexes — as ``source="sugya"`` chunks, retrievable
  like everything else, carrying full provenance (concept, version, cited refs, author);
* approving version N+1 supersedes N: N's exact chunks are retracted through the
  EXISTING audited retract flow (who/when/why), and the page history is kept.

Every collaborator is injected; no models/urls/thresholds are hardcoded here.
"""

from __future__ import annotations

from maayan.capture.convert import detect_lang
from maayan.clock import Clock
from maayan.consolidate.cluster import find_cluster
from maayan.consolidate.draft import SugyaDrafter
from maayan.consolidate.models import SugyaPage, sugya_chunk_id, sugya_chunk_ref
from maayan.consolidate.store import SugyaStore
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.embed.base import Embedder
from maayan.graph.store import GraphStore
from maayan.index.qdrant import QdrantIndex
from maayan.retract.service import Retracting


class SugyaService:
    """Consolidate a cluster into a curated, versioned, gated sugya page."""

    def __init__(
        self,
        drafter: SugyaDrafter,
        graph: GraphStore,
        chunks: ChunkStore,
        store: SugyaStore,
        embedder: Embedder,
        index: QdrantIndex,
        retractor: Retracting,
        clock: Clock,
        *,
        min_cluster_size: int = 2,
    ) -> None:
        self._drafter = drafter
        self._graph = graph
        self._chunks = chunks
        self._store = store
        self._embedder = embedder
        self._index = index
        self._retractor = retractor
        self._clock = clock
        self._min_cluster_size = min_cluster_size

    def draft(self, *, concept: str, author: str) -> SugyaPage:
        """Draft a proposed sugya page for the cluster anchored on `concept`."""
        cluster = find_cluster(
            self._graph, self._chunks, concept=concept, min_size=self._min_cluster_size
        )
        if cluster is None:
            raise ValueError(
                f"No cluster of size ≥ {self._min_cluster_size} anchored on concept {concept!r}."
            )
        page = self._drafter.draft(cluster, author=author)
        return self._store.save_page(page)

    def get(self, page_id: str) -> SugyaPage | None:
        return self._store.get_page(page_id)

    def approve(self, page_id: str, *, author: str) -> SugyaPage:
        """Approve a proposed page → index it; supersede + retract the prior version."""
        page = self._require(page_id)
        if page.status != "proposed":
            raise ValueError(
                f"Sugya page {page_id!r} is {page.status!r}; only a proposed page can be approved."
            )
        indexable = [s for s in page.sections if s.body.strip()]
        if not indexable:
            raise ValueError("Refusing to approve a sugya page with no grounded sections.")

        prior = self._store.latest_approved(page.page_key)
        version = prior.version + 1 if prior is not None else 1
        approved = page.model_copy(
            update={
                "status": "approved",
                "version": version,
                "supersedes": prior.id if prior is not None else None,
                "author": author.strip() or page.author,
            }
        )
        approved.chunk_ids = self._index_page(approved)
        self._store.save_page(approved)

        # Supersede N through the EXISTING audited retract flow — never a silent delete.
        if prior is not None:
            for chunk_id in prior.chunk_ids:
                self._retractor.retract(
                    chunk_id,
                    author=author,
                    reason=f"superseded by sugya v{version} ({approved.id})",
                )
            self._store.save_page(prior.model_copy(update={"status": "superseded"}))
        return approved

    def reject(self, page_id: str) -> SugyaPage:
        """Reject a proposed page. Indexes nothing — the corpus is unchanged."""
        page = self._require(page_id)
        if page.status != "proposed":
            raise ValueError(
                f"Sugya page {page_id!r} is {page.status!r}; only a proposed page can be rejected."
            )
        rejected = page.model_copy(update={"status": "rejected"})
        return self._store.save_page(rejected)

    # -- internals ---------------------------------------------------------------
    def _index_page(self, page: SugyaPage) -> list[str]:
        """Index each non-empty section as a retrievable ``sugya`` chunk; return their ids."""
        chunks: list[Chunk] = []
        for i, section in enumerate(page.sections):
            body = section.body.strip()
            if not body:
                continue
            chunks.append(
                Chunk(
                    id=sugya_chunk_id(page, i),
                    ref=sugya_chunk_ref(page, i),
                    book="Sugya",
                    section_path=["Sugya", page.concept or page.title, section.title],
                    lang=detect_lang(body),
                    text=body,
                    source="sugya",
                    metadata={
                        "page_id": page.id,
                        "page_key": page.page_key,
                        "concept": page.concept,
                        "version": page.version,
                        "section_title": section.title,
                        "cited_refs": section.cited_refs,
                        "author": page.author,
                    },
                )
            )
        if not chunks:
            return []
        self._chunks.upsert_chunks(chunks)
        self._chunks.mark_indexed([c.id for c in chunks])
        self._index.ensure_collection()
        embeddings = self._embedder.embed([c.text for c in chunks])
        self._index.upsert_chunks(list(zip(chunks, embeddings, strict=True)))
        return [c.id for c in chunks]

    def _require(self, page_id: str) -> SugyaPage:
        page = self._store.get_page(page_id)
        if page is None:
            raise ValueError(f"Sugya page {page_id!r} not found.")
        return page

    # NOTE: defined last because the name shadows builtin `list` in the annotations
    # of the methods above (mirrors InquiryStore.list).
    def list(self, *, status: str | None = None) -> list[SugyaPage]:
        return self._store.list_pages(status=status)
