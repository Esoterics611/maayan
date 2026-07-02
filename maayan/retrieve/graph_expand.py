"""Graph-aware retrieval (Prompt 35): hybrid search finds the entry points, the
graph widens the grounding.

The trust core does NOT move. The default-deny decision is made on the seed
retrieval alone — a below-threshold query returns the seed result untouched and
the graph store is never called (tests enforce this with a spy). Expansion can
enrich a supported answer; it can never rescue a refusal.

One hop, approved edges only: for the top `seeds` hits, follow
`GraphStore.neighbors()` (which serves only status="approved" relations) and
resolve the far refs to live corpus chunks; additionally, when a Concept's name
appears in the query (fold-insensitive, same matching as the lexicon), walk from
that concept too. Every expanded hit carries a `via` — the relation that brought
it — so the scholar always sees WHY a source appeared.

Scores: with a reranker, the merged set is re-scored by the cross-encoder (one
comparable scale). Without one, expanded hits are appended AFTER the seeds in
walk order, carrying the relation's confidence as their score — NOT comparable
to seed scores; the via-line, not the number, is their explanation.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from maayan.capture.convert import detect_lang
from maayan.corpus.models import Chunk
from maayan.corpus.normalize import fold_surface
from maayan.graph.models import Concept, ConceptEndpoint, Neighbor, RefEndpoint
from maayan.index.qdrant import chunk_payload
from maayan.retrieve.models import RetrievalResult, SearchResult, Via
from maayan.retrieve.reranker import Reranker
from maayan.retrieve.retriever import Retrieving, _rank_key


class GraphSource(Protocol):
    """The two graph reads expansion needs (DI seam; GraphStore satisfies it)."""

    def neighbors(
        self,
        endpoint: RefEndpoint | ConceptEndpoint,
        *,
        types: list[str] | None = None,
        status: str = "approved",
    ) -> list[Neighbor]:
        ...

    def list_concepts(self) -> list[Concept]:
        ...


class ChunkSource(Protocol):
    """The one corpus read expansion needs (DI seam; ChunkStore satisfies it)."""

    def get_by_ref(self, ref: str, *, include_retracted: bool = True) -> list[Chunk]:
        ...


class GraphExpandingRetriever:
    """Widen a *supported* retrieval one hop along approved edges — a `Retrieving`."""

    def __init__(
        self,
        inner: Retrieving,
        graph: GraphSource,
        chunks: ChunkSource,
        *,
        score_threshold: float,
        seeds: int,
        limit: int,
        reranker: Reranker | None = None,
        min_concept_len: int = 2,
    ) -> None:
        self._inner = inner
        self._graph = graph
        self._chunks = chunks
        self._score_threshold = score_threshold
        self._seeds = seeds
        self._limit = limit
        self._reranker = reranker
        self._min_concept_len = min_concept_len

    def retrieve(
        self,
        query: str,
        *,
        k: int | None = None,
        book: str | None = None,
        source: str | None = None,
    ) -> RetrievalResult:
        seed = self._inner.retrieve(query, k=k, book=book, source=source)

        # DEFAULT-DENY on the seeds ALONE: below threshold, the graph is never
        # touched — expansion may enrich a supported answer, never rescue a refusal.
        if not seed.results or seed.relevance < self._score_threshold:
            return seed

        added = self._expand(query, seed.results, book=book, source=source)
        if not added:
            return seed

        if self._reranker is not None:
            merged = seed.results + added
            scores = self._reranker.rerank(query, [r.text for r in merged])
            for result, score in zip(merged, scores, strict=True):
                result.score = score
            merged.sort(key=_rank_key)
            return RetrievalResult(results=merged, relevance=seed.relevance)
        return RetrievalResult(results=seed.results + added, relevance=seed.relevance)

    def search(
        self,
        query: str,
        *,
        k: int | None = None,
        book: str | None = None,
        source: str | None = None,
    ) -> list[SearchResult]:
        """Convenience wrapper returning just the ranked results (used by the CLI)."""
        return self.retrieve(query, k=k, book=book, source=source).results

    # -- internals -------------------------------------------------------------
    def _expand(
        self,
        query: str,
        seeds: list[SearchResult],
        *,
        book: str | None,
        source: str | None,
    ) -> list[SearchResult]:
        added: list[SearchResult] = []
        seen_refs = {hit.ref for hit in seeds}
        lang = detect_lang(query)

        # 1) One hop from the top seed hits.
        for hit in seeds[: self._seeds]:
            if len(added) >= self._limit:
                break
            steps = self._graph.neighbors(RefEndpoint(ref=hit.ref))
            self._collect(steps, hit.ref, added, seen_refs, lang, book=book, source=source)

        # 2) One hop from Concepts named in the query (lexicon-style fold matching).
        if len(added) < self._limit:
            for concept in self._concepts_in(query):
                if len(added) >= self._limit:
                    break
                steps = self._graph.neighbors(ConceptEndpoint(concept_id=concept.id))
                self._collect(
                    steps, concept.canonical, added, seen_refs, lang, book=book, source=source
                )
        return added

    def _collect(
        self,
        steps: Sequence[Neighbor],
        seed_ref: str,
        added: list[SearchResult],
        seen_refs: set[str],
        lang: str,
        *,
        book: str | None,
        source: str | None,
    ) -> None:
        """Resolve walk steps to chunks, honoring budget, filters, and dedupe."""
        for step in steps:
            if len(added) >= self._limit:
                return
            far = step.endpoint
            if not isinstance(far, RefEndpoint) or far.ref in seen_refs:
                continue  # concept far-ends have no chunk to add; refs only, once each
            chunk = self._resolve_chunk(far.ref, lang, book=book, source=source)
            if chunk is None:
                continue  # outside the corpus (e.g. a bare pasuk anchor) — nothing to add
            seen_refs.add(far.ref)
            relation = step.relation
            added.append(
                SearchResult(
                    ref=chunk.ref,
                    text=chunk.text,
                    score=relation.confidence,
                    lang=chunk.lang,
                    source=chunk.source,
                    payload=chunk_payload(chunk),
                    via=Via(
                        rel_type=relation.rel_type,
                        evidence=relation.evidence,
                        author=relation.author,
                        seed_ref=seed_ref,
                        relation_id=relation.id,
                        note=relation.note,
                    ),
                )
            )

    def _resolve_chunk(
        self, ref: str, lang: str, *, book: str | None, source: str | None
    ) -> Chunk | None:
        """The live chunk for a ref (query-language preferred), honoring filters."""
        candidates = [
            chunk
            for chunk in self._chunks.get_by_ref(ref, include_retracted=False)
            if (book is None or chunk.book == book)
            and (source is None or chunk.source == source)
        ]
        if not candidates:
            return None
        for chunk in candidates:
            if chunk.lang == lang:
                return chunk
        return candidates[0]

    def _concepts_in(self, query: str) -> list[Concept]:
        """Concepts whose canonical/alias appears in the query (fold-insensitive)."""
        folded_query = fold_surface(query)
        if not folded_query:
            return []
        found: list[Concept] = []
        for concept in self._graph.list_concepts():
            names = [concept.canonical, *concept.aliases]
            for name in names:
                folded = fold_surface(name)
                if len(folded) >= self._min_concept_len and folded in folded_query:
                    found.append(concept)
                    break
        return found
