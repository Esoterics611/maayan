"""TermService: add curated terms, index them, expose the protected-terms set.

Adding a term (a) persists it, (b) converts it to a `source="term"` chunk, (c)
persists that chunk to the corpus store (marked indexed), and (d) embeds + upserts it
into the SAME Qdrant collection — after which the term definition is retrievable
alongside the text. `protected_terms()` exposes the folded surface forms so the
rashei-teivot hook never expands a registered term / Holy Name. All collaborators
injected (mirrors CaptureService).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from maayan.clock import Clock
from maayan.corpus.normalize import fold_surface
from maayan.corpus.store import ChunkStore
from maayan.embed.base import Embedder
from maayan.index.qdrant import QdrantIndex
from maayan.lexicon.convert import term_to_chunk
from maayan.lexicon.models import Term, TermType
from maayan.lexicon.store import TermStore


class TermService:
    """Curate terms and turn them into indexed, retrievable lexicon knowledge."""

    def __init__(
        self,
        term_store: TermStore,
        chunk_store: ChunkStore,
        embedder: Embedder,
        index: QdrantIndex,
        clock: Clock,
    ) -> None:
        self._terms = term_store
        self._chunks = chunk_store
        self._embedder = embedder
        self._index = index
        self._clock = clock

    def get_term(self, term_id: str) -> Term | None:
        return self._terms.get_term(term_id)

    def list_terms(self) -> list[Term]:
        return self._terms.list_terms()

    def find_by_surface_form(self, query: str) -> list[Term]:
        return self._terms.find_by_surface_form(query)

    def protected_terms(self) -> frozenset[str]:
        """Folded surface forms (+ canonicals) that must never be expanded as rashei-teivot."""
        forms: set[str] = set()
        for term in self._terms.list_terms():
            for f in (term.canonical, *term.surface_forms):
                folded = fold_surface(f)
                if folded:
                    forms.add(folded)
        return frozenset(forms)

    def add_term(
        self,
        *,
        canonical: str,
        definition: str,
        author: str,
        surface_forms: Sequence[str] = (),
        term_type: TermType = "concept",
        related_terms: Sequence[str] = (),
        source_refs: Sequence[str] = (),
        gematria: int | None = None,
        sacred: bool = False,
    ) -> Term:
        """Validate, persist, convert→embed→index a term. Blank author is rejected."""
        term = Term(
            id=str(uuid.uuid4()),
            canonical=canonical,
            surface_forms=list(surface_forms),
            term_type=term_type,
            definition=definition,
            related_terms=list(related_terms),
            source_refs=list(source_refs),
            gematria=gematria,
            sacred=sacred,
            author=author,
        )
        self._terms.create_term(term)

        chunk = term_to_chunk(term)
        self._chunks.upsert_chunks([chunk])
        self._chunks.mark_indexed([chunk.id])
        self._index.ensure_collection()
        embeddings = self._embedder.embed([chunk.text])
        self._index.upsert_chunks(list(zip([chunk], embeddings, strict=True)))
        return term
