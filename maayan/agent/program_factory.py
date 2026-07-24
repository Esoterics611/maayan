"""Study-program runner factory (DI at the edge).

The drafting model is swapped here, exactly like the lexicon/connector populators: if
`study_program_model` is set (e.g. the OpenRouter Claude slug) the sweep drafts with it
while the rest of maayan keeps its configured generation model. Pacing/backoff/resume
reuse the populate drip knobs.
"""

from __future__ import annotations

from maayan.agent.program import StudyProgramRunner
from maayan.agent.program_drafter import ProgramDrafter
from maayan.agent.program_store import ProgramStore
from maayan.clock import SystemClock
from maayan.config import Settings
from maayan.corpus.store import ChunkStore
from maayan.embed.base import Embedder
from maayan.embed.factory import build_embedder
from maayan.generate.base import GenerationBackend
from maayan.generate.factory import build_generation_backend
from maayan.graph.store import GraphStore
from maayan.retrieve.factory import build_retriever


def build_study_program_runner(
    settings: Settings,
    *,
    embedder: Embedder | None = None,
    backend: GenerationBackend | None = None,
) -> StudyProgramRunner:
    """Assemble the study-program runner over the same stores + retriever as the rest."""
    embedder = embedder or build_embedder(settings)
    draft_settings = settings
    if settings.study_program_model:
        field = "ollama_model" if settings.generation_backend == "ollama" else "openrouter_model"
        draft_settings = settings.model_copy(update={field: settings.study_program_model})
    backend = backend or build_generation_backend(draft_settings)
    chunks = ChunkStore(settings.db_path)
    drafter = ProgramDrafter(
        build_retriever(settings, embedder=embedder, backend=backend),
        backend,
        chunks,
        SystemClock(),
        model=draft_settings.generation_model,
        k=settings.study_program_k,
        max_proposals=settings.study_unit_max_proposals,
        verify=settings.study_draft_verify,
    )
    return StudyProgramRunner(
        drafter,
        chunks,
        GraphStore(settings.db_path),
        ProgramStore(settings.db_path),
        SystemClock(),
        pace=settings.study_pace_seconds,
        bootstrap_confidence=settings.graph_bootstrap_confidence,
        max_retries=settings.populate_max_retries,
        backoff=settings.populate_backoff_seconds,
    )
