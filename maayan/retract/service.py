"""RetractionService: the eraser for layered knowledge (Prompt 17).

Removing knowledge is a provenanced operation, not a silent delete. `retract`:

  1. resolves the chunk (by stable id or by ref),
  2. REJECTS printed text (`sefaria` / `chabad`) in code — it is immutable,
  3. deletes the point from Qdrant (gone from retrieval),
  4. tombstones the corpus chunk so `index --rebuild` never re-embeds it,
  5. cascades: a `derived` chunk's Development → status "retracted"; a `term`
     chunk's Term → marked retracted,
  6. records an attributed, timestamped `Retraction` audit row.

Correction is retract + re-add: ids are content-derived/idempotent, so there is no
in-place edit — you retract the wrong chunk (reason: superseded) and add the right
one through the existing capture / develop / add-term loops. All collaborators are
injected (DI house rule); no embedder is needed (deletion does not embed).
"""

from __future__ import annotations

import uuid
from typing import Protocol

from maayan.clock import Clock
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.develop.store import DevelopmentStore
from maayan.index.qdrant import QdrantIndex
from maayan.lexicon.store import TermStore
from maayan.retract.models import Retraction
from maayan.retract.store import RetractionStore

# Printed text is immutable: never retractable, rejected in code.
PRINTED_SOURCES = frozenset({"sefaria", "chabad"})
# Only layered, human-added knowledge is retractable.
RETRACTABLE_SOURCES = frozenset({"expert", "derived", "term"})


class Retracting(Protocol):
    """The methods the UI/CLI depend on (DI seam, mirrors `Developing`)."""

    def retract(self, target: str, *, author: str, reason: str) -> Retraction: ...

    def list_retractions(self) -> list[Retraction]: ...


class RetractionService:
    """Retract a piece of layered knowledge, provenanced — never a silent delete."""

    def __init__(
        self,
        chunk_store: ChunkStore,
        retraction_store: RetractionStore,
        index: QdrantIndex,
        clock: Clock,
        development_store: DevelopmentStore,
        term_store: TermStore,
    ) -> None:
        self._chunks = chunk_store
        self._retractions = retraction_store
        self._index = index
        self._clock = clock
        self._developments = development_store
        self._terms = term_store

    def retract(self, target: str, *, author: str, reason: str) -> Retraction:
        """Retract the chunk identified by `target` (a stable chunk id OR a ref).

        Raises ValueError if the chunk is not found, if `target` is an ambiguous ref
        (pass the chunk id), or if the chunk is printed text (immutable).
        """
        chunk = self._resolve(target)
        if chunk.source in PRINTED_SOURCES:
            raise ValueError(
                f"{chunk.ref!r} is printed text (source={chunk.source!r}) and is immutable — "
                "it cannot be retracted. Only expert/derived/term knowledge is retractable."
            )
        if chunk.source not in RETRACTABLE_SOURCES:
            raise ValueError(
                f"Source {chunk.source!r} is not retractable "
                f"(retractable: {', '.join(sorted(RETRACTABLE_SOURCES))})."
            )

        # Build (and validate: blank author rejected) BEFORE any mutation, so a
        # rejected retraction never leaves the chunk half-removed.
        retraction = Retraction(
            id=str(uuid.uuid4()),
            chunk_id=chunk.id,
            ref=chunk.ref,
            source=chunk.source,
            author=author,
            reason=reason,
            timestamp=self._clock.now(),
        )

        # (c) gone from retrieval, (d) tombstoned so --rebuild never re-embeds it.
        self._index.delete_points([chunk.id])
        self._chunks.mark_retracted([chunk.id])

        # Cascade to the originating artifact so its own status reflects the retraction.
        if chunk.source == "derived":
            self._retract_development(chunk.metadata.get("development_id"))
        elif chunk.source == "term":
            self._retract_term(chunk.metadata.get("term_id"))

        return self._retractions.save_retraction(retraction)

    def list_retractions(self) -> list[Retraction]:
        return self._retractions.list_retractions()

    def get_retraction(self, retraction_id: str) -> Retraction | None:
        return self._retractions.get_retraction(retraction_id)

    # -- internals -----------------------------------------------------------
    def _resolve(self, target: str) -> Chunk:
        """Resolve `target` to a single chunk by stable id, then by exact ref."""
        chunk = self._chunks.get_chunk(target)
        if chunk is not None:
            return chunk
        matches = self._chunks.get_by_ref(target)
        if not matches:
            raise ValueError(f"No chunk found for {target!r} (tried as chunk id and as ref).")
        if len(matches) > 1:
            raise ValueError(
                f"{target!r} matches {len(matches)} chunks (e.g. he+en); "
                "pass the specific chunk id instead."
            )
        return matches[0]

    def _retract_development(self, development_id: object) -> None:
        if not isinstance(development_id, str):
            return
        dev = self._developments.get_development(development_id)
        if dev is not None:
            self._developments.save_development(dev.model_copy(update={"status": "retracted"}))

    def _retract_term(self, term_id: object) -> None:
        if isinstance(term_id, str):
            self._terms.mark_retracted(term_id)
