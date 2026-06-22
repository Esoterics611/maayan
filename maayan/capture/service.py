"""The capture service: record sessions, accept annotations, close the loop.

Adding an annotation (a) persists it, (b) converts it to expert chunk(s),
(c) persists those chunks to the corpus store (marked indexed so a rebuild keeps
them), and (d) embeds + upserts them into the SAME Qdrant collection — after which
they are retrievable alongside the printed text. All collaborators are injected.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from maayan.capture.convert import annotation_to_chunks
from maayan.capture.models import Annotation, Session
from maayan.capture.store import CaptureStore
from maayan.clock import Clock
from maayan.corpus.store import ChunkStore
from maayan.embed.base import Embedder
from maayan.generate.rag import Answer
from maayan.index.qdrant import QdrantIndex


class CaptureService:
    """Records sessions and turns expert annotations into indexed knowledge."""

    def __init__(
        self,
        capture_store: CaptureStore,
        chunk_store: ChunkStore,
        embedder: Embedder,
        index: QdrantIndex,
        clock: Clock,
        *,
        allowed_kinds: Sequence[str],
    ) -> None:
        self._capture = capture_store
        self._chunks = chunk_store
        self._embedder = embedder
        self._index = index
        self._clock = clock
        self._allowed_kinds = tuple(allowed_kinds)

    @property
    def allowed_kinds(self) -> tuple[str, ...]:
        return self._allowed_kinds

    def get_session(self, session_id: str) -> Session | None:
        return self._capture.get_session(session_id)

    def get_annotations(self, session_id: str) -> list[Annotation]:
        return self._capture.get_annotations(session_id)

    def get_annotation(self, annotation_id: str) -> Annotation | None:
        return self._capture.get_annotation(annotation_id)

    def start_session(self, answer: Answer) -> Session:
        """Record a session from a RAG Answer and return it (with its new id)."""
        session = Session(
            id=str(uuid.uuid4()),
            timestamp=self._clock.now(),
            question=answer.question,
            retrieved_refs=[s.ref for s in answer.sources],
            answer_text=answer.text,
        )
        return self._capture.save_session(session)

    def add_annotation(
        self,
        session_id: str,
        *,
        author: str,
        kind: str,
        body: str,
        linked_refs: Sequence[str] = (),
        move: str | None = None,
        directive: str | None = None,
        opens_aspect: bool = False,
    ) -> Annotation:
        """Validate, persist, convert→embed→index a contribution. Closes the loop.

        A blank ``author`` and an unknown ``kind`` are both rejected (the former by
        the model validator, raising a ``ValueError``).
        """
        if kind not in self._allowed_kinds:
            raise ValueError(
                f"Unknown kind {kind!r}. Allowed (config): {', '.join(self._allowed_kinds)}"
            )

        annotation = Annotation(
            id=str(uuid.uuid4()),
            session_id=session_id,
            timestamp=self._clock.now(),
            author=author,
            kind=kind,
            body=body,
            linked_refs=list(linked_refs),
            move=move,
            directive=directive,
            opens_aspect=opens_aspect,
        )
        self._capture.save_annotation(annotation)

        chunks = annotation_to_chunks(annotation)
        # Persist to the corpus store (indexed=1) so `index --rebuild` keeps them.
        self._chunks.upsert_chunks(chunks)
        self._chunks.mark_indexed([c.id for c in chunks])
        # Embed + upsert into the same Qdrant collection as the printed text.
        self._index.ensure_collection()
        embeddings = self._embedder.embed([c.text for c in chunks])
        self._index.upsert_chunks(list(zip(chunks, embeddings, strict=True)))

        return annotation
