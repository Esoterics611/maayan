"""Central configuration for maayan.

All tunables live here and are loaded from the environment / .env. Nothing in the
codebase may hardcode model names, collection names, URLs, top-k, thresholds, etc.
Secrets (API keys) are read from env only and never logged.

House rule: services read from a `Settings` instance that is injected, not
constructed inline in business logic. `get_settings()` is provided as a cached
convenience for entrypoints (CLI / UI), not for use inside library functions.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment / `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Generation (cloud) -------------------------------------------------
    openrouter_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="OpenRouter API key. Read from env; never hardcode or log.",
    )
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")
    openrouter_model: str = Field(default="qwen/qwen-2.5-72b-instruct")

    # Generation backend selector (Prompt 8 adds the Ollama option).
    generation_backend: str = Field(
        default="openrouter",
        description='Which generation backend to inject: "openrouter" | "ollama".',
    )
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="qwen2.5:7b-instruct")

    @property
    def generation_model(self) -> str:
        """The model id of the selected generation backend (for provenance/logging)."""
        return self.ollama_model if self.generation_backend == "ollama" else self.openrouter_model

    # ---- Vector DB (local) --------------------------------------------------
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: SecretStr = Field(default=SecretStr(""))
    collection_name: str = Field(default="maayan")

    # ---- Embeddings (local) -------------------------------------------------
    embed_backend: str = Field(
        default="bgem3",
        description='Embedder implementation: "bgem3" (real) | "hashing" (dev/test, no GPU).',
    )
    embed_model: str = Field(default="BAAI/bge-m3")
    embed_dim: int = Field(default=1024, description="Dense vector dim for bge-m3.")
    embed_batch_size: int = Field(default=16)
    embed_device: str = Field(
        default="auto", description='Torch device: "auto" | "cpu" | "cuda" | "mps".'
    )

    # ---- Reranker (local, optional) -----------------------------------------
    rerank_enabled: bool = Field(default=False)
    rerank_model: str = Field(default="BAAI/bge-reranker-v2-m3")
    rerank_candidates: int = Field(
        default=30, description="Fused candidates fetched for the reranker to reorder."
    )

    # ---- Retrieval ----------------------------------------------------------
    top_k: int = Field(default=8, description="Candidates fused/returned by hybrid search.")
    score_threshold: float = Field(
        default=0.45,
        description=(
            "Min top relevance for RAG to answer; below this it refuses (default-deny). "
            "Absolute measure (top dense-cosine, or reranker score when rerank is on), "
            "NOT the RRF rank score. bge-m3 cosine clusters in a narrow band, so tune "
            "this per corpus via the eval harness; enabling rerank sharpens separation."
        ),
    )
    expert_boost: float = Field(
        default=1.0,
        description="Multiplier applied to source='expert' chunk scores (>1 prefers humans).",
    )
    derived_boost: float = Field(
        default=1.0,
        description="Multiplier for source='derived' chunks (reviewed+approved developments).",
    )
    term_boost: float = Field(
        default=1.0,
        description="Multiplier for source='term' chunks (curated lexicon entries / Holy Names).",
    )

    # ---- Corpus -------------------------------------------------------------
    # Config-driven list of works to ingest. Each entry is a Sefaria *base ref*
    # (the node ref above the chapter level) that the client enumerates chapter
    # by chapter. Initial focus: Likutei Amarim (Tanya, Part I) — the core text.
    # Add e.g. "Likutei Torah", "Torah Or" later; complex texts need their full
    # node ref (find it via `GET /api/shape/<title>`).
    books: list[str] = Field(default=["Tanya, Part I; Likkutei Amarim"])
    ingest_langs: list[str] = Field(
        default=["he", "en"], description="Which languages to ingest when available."
    )
    sefaria_base_url: str = Field(default="https://www.sefaria.org/api")
    sefaria_rate_limit_seconds: float = Field(
        default=0.5, description="Min delay between Sefaria requests (via injected Clock)."
    )

    # ---- Capture loop -------------------------------------------------------
    annotation_kinds: list[str] = Field(
        default=["correction", "connection", "addition", "objection"]
    )

    # ---- Topic threads ------------------------------------------------------
    thread_context_turns: int = Field(
        default=6,
        description="How many prior thread turns to pass as conversation context (Prompt 11).",
    )

    # ---- Develop step -------------------------------------------------------
    develop_top_k: int = Field(
        default=8,
        description="How many corpus sources to retrieve + ground a seed development on.",
    )
    develop_auto_approve: bool = Field(
        default=False,
        description="If true, develop() approves immediately; else it waits for approve().",
    )

    # ---- Storage / paths ----------------------------------------------------
    db_path: str = Field(default="data/maayan.sqlite3")

    # ---- Evaluation ---------------------------------------------------------
    eval_goldset_path: str = Field(default="eval/goldset.yaml")
    eval_develop_goldset_path: str = Field(
        default="eval/develop_goldset.yaml",
        description="Seeds (supported/unsupported) for scoring the develop step (Prompt 15).",
    )
    eval_ks: list[int] = Field(default=[1, 3, 5, 10])

    # ---- UI -----------------------------------------------------------------
    ui_host: str = Field(default="127.0.0.1")
    ui_port: int = Field(default=8000)


@lru_cache
def get_settings() -> Settings:
    """Cached settings for entrypoints (CLI/UI). Library code takes Settings via DI."""
    return Settings()
