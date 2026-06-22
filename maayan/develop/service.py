"""DevelopmentService: develop a seed under its directive, grounded in the corpus.

The shape mirrors `RAGService` on purpose — same default-deny discipline, same
citation hygiene, a new verb:

  1. Retrieve fresh on (seed body + directive) via the injected retriever.
  2. DEFAULT-DENY: if relevance is below threshold, return a refusal Development with
     NO model call. The corpus simply doesn't support the seed, and we say so.
  3. Otherwise the model develops the seed: the prompt separates the citable SOURCES
     from the expert SEED ("framework — attribute it, never cite it as a source"), and
     the development cites ONLY retrieved sources.

The result is a PROPOSAL (status="proposed"), persisted and appended to the thread as
a "development" turn — but NOT indexed as corpus. Approval (Prompt 13) does that.
Everything is injected; no models/prompts/urls are hardcoded in logic.
"""

from __future__ import annotations

import uuid

from maayan.capture.models import Annotation
from maayan.clock import Clock
from maayan.config import Settings
from maayan.corpus.store import ChunkStore
from maayan.develop.convert import development_to_chunk
from maayan.develop.models import Development
from maayan.develop.store import DevelopmentStore
from maayan.embed.base import Embedder
from maayan.generate.base import GenerationBackend, Message
from maayan.generate.rag import build_context, extract_cited_refs
from maayan.index.qdrant import QdrantIndex
from maayan.retrieve.retriever import Retrieving
from maayan.threads.service import ThreadService

DEFAULT_DEVELOP_SYSTEM_PROMPT = (
    "You are a careful study assistant for chassidus and Kabbalah (p'nimiyus haTorah). "
    "An expert has planted a SEED: a framework (often drawn from texts NOT in this corpus) "
    "plus a directive for what to develop. Develop the seed by fulfilling the directive, "
    "grounded ONLY in the numbered SOURCES. Rules:\n"
    "1. Ground every claim in the SOURCES and cite it with its bracket tag, e.g. [S1].\n"
    "2. The SEED is the expert's framework: you may ATTRIBUTE it (e.g. 'per the expert "
    "seed') but NEVER cite it as a retrieved source and never treat it as evidence.\n"
    "3. Add no outside facts and never invent mekoros. If the sources do not actually "
    "support the directive, say so plainly rather than forcing a connection.\n"
    "4. Answer in the language of the seed/directive, faithful to the sources' meaning."
)

DEFAULT_DEVELOP_REFUSAL = (
    "No support for this seed in the indexed corpus — retrieval found nothing relevant "
    "enough to ground a development. Ingest the relevant text, or refine the seed."
)


def build_develop_messages(seed: Annotation, sources_block: str) -> list[Message]:
    """Compose the develop prompt: the SEED (non-citable) then the citable SOURCES."""
    seed_lines = [
        "EXPERT SEED (framework — attribute it, do NOT cite it as a retrieved source):",
        seed.body,
    ]
    if seed.directive:
        seed_lines.append(f"DIRECTIVE: {seed.directive}")
    content = (
        f"{chr(10).join(seed_lines)}\n\n"
        f"{sources_block}\n\n"
        "Develop the seed: fulfill the directive, grounding every claim ONLY in the "
        "numbered sources and citing each with its [S#] tag. Do not cite the seed."
    )
    return [Message(role="user", content=content)]


class DevelopmentService:
    """Retrieve → (default-deny gate) → grounded, cited development. Produces a proposal."""

    def __init__(
        self,
        retriever: Retrieving,
        backend: GenerationBackend,
        store: DevelopmentStore,
        threads: ThreadService,
        clock: Clock,
        settings: Settings,
        embedder: Embedder,
        chunk_store: ChunkStore,
        index: QdrantIndex,
        *,
        system_prompt: str = DEFAULT_DEVELOP_SYSTEM_PROMPT,
        refusal_text: str = DEFAULT_DEVELOP_REFUSAL,
    ) -> None:
        self._retriever = retriever
        self._backend = backend
        self._store = store
        self._threads = threads
        self._clock = clock
        self._settings = settings
        self._embedder = embedder
        self._chunks = chunk_store
        self._index = index
        self._system_prompt = system_prompt
        self._refusal_text = refusal_text

    def develop(self, seed: Annotation, *, thread_id: str) -> Development:
        """Develop `seed` grounded in the corpus; return a proposal (or honest refusal).

        When `develop_auto_approve` is set, a grounded development is approved (indexed)
        immediately; otherwise it waits for `approve()`.
        """
        query = self._build_query(seed)
        retrieval = self._retriever.retrieve(query, k=self._settings.develop_top_k)
        sources = retrieval.results

        # DEFAULT-DENY: refuse without calling the model when the corpus doesn't support it.
        if not sources or retrieval.relevance < self._settings.score_threshold:
            return self._finish(
                seed,
                thread_id,
                model="",
                grounded=False,
                text=self._refusal_text,
                cited_refs=[],
                grounded_in=[],
            )

        messages = build_develop_messages(seed, build_context(sources))
        text = self._backend.generate(self._system_prompt, messages)
        dev = self._finish(
            seed,
            thread_id,
            model=self._settings.generation_model,
            grounded=True,
            text=text,
            cited_refs=extract_cited_refs(text, sources),
            grounded_in=[s.ref for s in sources],
        )
        if self._settings.develop_auto_approve:
            return self.approve(dev.id)
        return dev

    def approve(self, development_id: str) -> Development:
        """Approve a grounded proposal → index it as a `derived` corpus chunk."""
        dev = self._require(development_id)
        if not dev.grounded:
            raise ValueError("Cannot approve an ungrounded development (it was a refusal).")
        approved = dev.model_copy(update={"status": "approved"})
        self._store.save_development(approved)
        self._index_derived(approved)
        return approved

    def reject(self, development_id: str) -> Development:
        """Reject a proposal. Indexes nothing — the corpus is unchanged."""
        rejected = self._require(development_id).model_copy(update={"status": "rejected"})
        self._store.save_development(rejected)
        return rejected

    def get_development(self, development_id: str) -> Development | None:
        return self._store.get_development(development_id)

    def _require(self, development_id: str) -> Development:
        dev = self._store.get_development(development_id)
        if dev is None:
            raise ValueError(f"Development {development_id!r} not found.")
        return dev

    def _index_derived(self, dev: Development) -> None:
        """Persist the derived chunk (marked indexed) and embed + upsert it into Qdrant."""
        chunk = development_to_chunk(dev)
        self._chunks.upsert_chunks([chunk])
        self._chunks.mark_indexed([chunk.id])
        self._index.ensure_collection()
        embeddings = self._embedder.embed([chunk.text])
        self._index.upsert_chunks(list(zip([chunk], embeddings, strict=True)))

    @staticmethod
    def _build_query(seed: Annotation) -> str:
        """Retrieval query = the seed knowledge plus its directive (the corpus-facing ask)."""
        return seed.body if not seed.directive else f"{seed.body} {seed.directive}"

    def _finish(
        self,
        seed: Annotation,
        thread_id: str,
        *,
        model: str,
        grounded: bool,
        text: str,
        cited_refs: list[str],
        grounded_in: list[str],
    ) -> Development:
        """Build, persist, and thread-append a Development (proposal or refusal)."""
        dev = Development(
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            seed_id=seed.id,
            author=seed.author,
            timestamp=self._clock.now(),
            model=model,
            status="proposed",
            grounded=grounded,
            text=text,
            cited_refs=cited_refs,
            grounded_in=grounded_in,
        )
        self._store.save_development(dev)
        self._threads.add_turn(
            thread_id,
            turn_type="development",
            author=model or "model",
            text=text,
            record_id=dev.id,
        )
        return dev
