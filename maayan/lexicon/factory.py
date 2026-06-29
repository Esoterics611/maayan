"""Term service factory (DI at the edge)."""

from __future__ import annotations

from maayan.clock import SystemClock
from maayan.config import Settings
from maayan.corpus.store import ChunkStore
from maayan.embed.base import Embedder
from maayan.embed.factory import build_embedder
from maayan.generate.base import GenerationBackend
from maayan.generate.factory import build_generation_backend
from maayan.index.qdrant import QdrantIndex, build_qdrant_client
from maayan.lexicon.populate import LexiconDrafter, LexiconPopulator
from maayan.lexicon.service import TermService
from maayan.lexicon.store import TermStore
from maayan.lexicon.suggestions import SuggestionStore
from maayan.retrieve.factory import build_retriever


def build_term_service(
    settings: Settings, *, embedder: Embedder | None = None
) -> TermService:
    """Assemble a TermService wired to the same stores + collection as the rest."""
    embedder = embedder or build_embedder(settings)
    index = QdrantIndex(
        build_qdrant_client(settings), settings.collection_name, embedder.dim
    )
    return TermService(
        TermStore(settings.db_path),
        ChunkStore(settings.db_path),
        embedder,
        index,
        SystemClock(),
    )


def build_lexicon_populator(
    settings: Settings,
    *,
    embedder: Embedder | None = None,
    backend: GenerationBackend | None = None,
) -> LexiconPopulator:
    """Assemble the lexicon auto-populator (drafter + review queue + term service).

    The drafting model is swapped here, at the edge: if `lexicon_draft_model` is set
    (e.g. the OpenRouter Claude slug) the drafter uses it while the rest of maayan keeps
    its configured generation model. Drafts are corpus-grounded and queued for approval.
    """
    embedder = embedder or build_embedder(settings)
    draft_settings = settings
    if settings.lexicon_draft_model:
        field = "ollama_model" if settings.generation_backend == "ollama" else "openrouter_model"
        draft_settings = settings.model_copy(update={field: settings.lexicon_draft_model})
    backend = backend or build_generation_backend(draft_settings)
    drafter = LexiconDrafter(
        build_retriever(settings, embedder=embedder),
        backend,
        SystemClock(),
        model=draft_settings.generation_model,
        top_k=settings.lexicon_draft_top_k,
        score_threshold=settings.score_threshold,
        verify=settings.lexicon_draft_verify,
    )
    return LexiconPopulator(
        drafter,
        SuggestionStore(settings.db_path),
        build_term_service(settings, embedder=embedder),
    )
