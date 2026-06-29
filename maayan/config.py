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
    shiur_boost: float = Field(
        default=1.0,
        description="Multiplier for source='shiur' chunks (approved transcribed recordings).",
    )

    # ---- Query expansion (Prompt 31a) ---------------------------------------
    # Off by default so existing behavior/eval baseline are unchanged. When on, the
    # base hybrid retriever is wrapped in a MultiQueryRetriever: the query is expanded
    # into several retrieval queries which are searched and RRF-fused. Additive only —
    # the absolute relevance gate (default-deny) is unchanged.
    query_expand_enabled: bool = Field(
        default=False,
        description="Expand the query into multiple retrieval queries and RRF-fuse the hits.",
    )
    query_expand_lexicon: bool = Field(
        default=True,
        description="Deterministic lexicon expansion (inject curated term vocabulary). No model.",
    )
    query_expand_hyde: bool = Field(
        default=True,
        description="Add a HyDE (hypothetical-source) passage as a query (needs a backend).",
    )
    query_expand_variants: int = Field(
        default=3, description="How many LLM reformulations to request (needs a backend)."
    )
    query_expand_max_queries: int = Field(
        default=6, description="Hard cap on total retrieval queries after dedupe (incl. original)."
    )

    # ---- Reasoning & synthesis (Prompt 31b) ---------------------------------
    # Off by default. When on, `ask` runs a two-stage flow: ANALYZE the retrieved
    # sources into a compact study map (claims + agreements/tensions), then SYNTHESIZE
    # a single woven, cited answer from sources + study map. Default-deny is unchanged
    # and still fires before any model call.
    rag_reasoning_enabled: bool = Field(
        default=False,
        description="Two-stage analyze→synthesize answering instead of a single generation pass.",
    )
    answer_verify_enabled: bool = Field(
        default=False,
        description="After answering, flag sentences not supported by their cited [S#] sources.",
    )

    # ---- Corpus -------------------------------------------------------------
    # Config-driven list of works to ingest. Each entry is a Sefaria *base ref*
    # that resolves to a depth-2 node (chapters → segments), which the client
    # enumerates chapter by chapter. Tanya, Part I is the core text; Torah Ohr (the
    # Alter Rebbe's chassidus on Bereishis/Shemos) is the companion — its parshiyot
    # are each depth-2 on Sefaria, so we list them by parsha node ref.
    #   NOTE: Likutei Torah is NOT on Sefaria; it needs a separate ingestion adapter
    #   (chabadlibrary.org / Hebrew Wikisource). See docs.
    #   Find/verify any node ref via `GET /api/shape/<title>` (must be a flat
    #   `chapters: [int, ...]`); whole-book refs with nested parshiyot won't ingest.
    books: list[str] = Field(
        default=[
            "Tanya, Part I; Likkutei Amarim",
            # --- Torah Ohr (Bereishis) ---
            "Torah Ohr, Bereshit",
            "Torah Ohr, Noach",
            "Torah Ohr, Lech Lecha",
            "Torah Ohr, Vayera",
            "Torah Ohr, Chayei Sara",
            "Torah Ohr, Toldot",
            "Torah Ohr, Vayetzei",
            "Torah Ohr, Vayishlach",
            "Torah Ohr, Vayeshev",
            "Torah Ohr, Miketz",
            "Torah Ohr, Vayigash",
            "Torah Ohr, Vayechi",
            # --- Torah Ohr (Shemos) ---
            "Torah Ohr, Shemot",
            "Torah Ohr, Vaera",
            "Torah Ohr, Bo",
            "Torah Ohr, Beshalach",
            "Torah Ohr, Yitro",
            "Torah Ohr, Mishpatim",
            "Torah Ohr, Terumah",
            "Torah Ohr, Tetzaveh",
            "Torah Ohr, Parashat Zakhor",
            "Torah Ohr, Ki Tisa",
            "Torah Ohr, Vayakhel",
            "Torah Ohr, Megillat Esther",
        ]
    )
    ingest_langs: list[str] = Field(
        default=["he", "en"], description="Which languages to ingest when available."
    )
    sefaria_base_url: str = Field(default="https://www.sefaria.org/api")
    sefaria_rate_limit_seconds: float = Field(
        default=0.5, description="Min delay between Sefaria requests (via injected Clock)."
    )

    # ---- Chabad Library corpus (non-Sefaria) --------------------------------
    # Likutei Torah is NOT on Sefaria; we pull it from chabadlibrary.org's JSON API
    # (api/main?path=<section_id>, brotli-encoded). Map book name → root section id.
    # Find ids by walking the tree from the root call (see docs/CORPUS.md).
    chabad_base_url: str = Field(default="https://chabadlibrary.org/books/api")
    chabad_books: dict[str, int] = Field(
        default={"Likutei Torah": 4000000000},
        description="Chabad Library book name → root section id (non-Sefaria source).",
    )
    chabad_rate_limit_seconds: float = Field(
        default=0.3, description="Min delay between Chabad Library requests (via Clock)."
    )
    chabad_chunk_chars: int = Field(
        default=1000,
        description=(
            "Target max characters per Likutei Torah chunk. A long section is split at "
            "SENTENCE boundaries into coherent passages (ref '… §2') for retrieval "
            "precision; short sections stay whole. 0 = one chunk per section."
        ),
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

    # ---- Compose step (Phase 5) ---------------------------------------------
    compose_auto_outline: bool = Field(
        default=False,
        description=(
            "If true, a proposed outline is filled immediately (quick drafts); if false, "
            "the outline is returned for the expert to edit/approve before any fill."
        ),
    )
    compose_max_sections: int = Field(
        default=8, description="Hard cap on sections an outline may propose."
    )
    compose_section_top_k: int = Field(
        default=6, description="Sources retrieved per section to ground (and gate) its fill."
    )
    compose_transitions: bool = Field(
        default=False,
        description=(
            "If true, assembly adds connective transitions between supported sections "
            "(glue only — the prompt forbids any new claim or citation in a transition)."
        ),
    )

    # ---- Transcription / shiur pipeline (Phase 6) ---------------------------
    # Swappable like the generation backend: "whisper" (local, faster-whisper),
    # "fake" (deterministic/offline; also via CLI --mock), "cloud" (documented swap).
    transcribe_backend: str = Field(default="whisper")
    whisper_model: str = Field(
        default="large-v3",
        description='faster-whisper model; "medium" trades Hebrew quality for speed.',
    )
    whisper_device: str = Field(default="auto", description='"auto" | "cpu" | "cuda".')
    whisper_compute_type: str = Field(
        default="float16", description='CTranslate2 compute type; CPU falls back to int8.'
    )
    transcribe_lang: str = Field(default="he", description="Default ASR language code.")
    transcribe_diarize: bool = Field(
        default=False, description="Label speakers (shiur Q&A); wired in a later prompt."
    )
    audio_dir: str = Field(default="data/audio", description="Where stored recordings live.")
    shiur_chunk_chars: int = Field(
        default=800,
        description=(
            "Target max characters per shiur chunk on approval: consecutive transcript "
            "segments are packed up to this budget (chabad_chunk_chars-style) so retrieval "
            "units are coherent, not per-utterance. 0 = one chunk for the whole transcript."
        ),
    )

    # ---- OCR capture (Phase 6, Prompt 30) -----------------------------------
    # Swappable like the transcription backend: "none" (off; default — OCR is
    # additive), "fake" (deterministic/offline; also via CLI --mock), "tesseract"
    # (local pytesseract; needs the tesseract-ocr + heb traineddata system deps),
    # "cloud" (documented swap). OCR text is never auto-ingested — it fills a capture
    # field for the same human review gate as every other contribution.
    ocr_backend: str = Field(default="none")
    ocr_lang: str = Field(
        default="heb",
        description='Tesseract language code(s), e.g. "heb", "eng", "heb+eng".',
    )

    # ---- Storage / paths ----------------------------------------------------
    db_path: str = Field(default="data/maayan.sqlite3")

    # ---- Evaluation ---------------------------------------------------------
    eval_goldset_path: str = Field(default="eval/goldset.yaml")
    eval_develop_goldset_path: str = Field(
        default="eval/develop_goldset.yaml",
        description="Seeds (supported/unsupported) for scoring the develop step (Prompt 15).",
    )
    eval_crosstext_goldset_path: str = Field(
        default="eval/crosstext_goldset.yaml",
        description="Questions whose expected refs span ≥2 books, for the cross-text eval.",
    )
    eval_ks: list[int] = Field(default=[1, 3, 5, 10])

    # ---- Answer-quality eval (Prompt 32) ------------------------------------
    eval_answer_goldset_path: str = Field(
        default="eval/goldset.yaml",
        description=(
            "Gold set for the answer-quality eval (`eval --answer`). Reuses the retrieval "
            "gold set by default; point at a synthesis-focused set to stress reasoning."
        ),
    )
    eval_judge_model: str = Field(
        default="",
        description=(
            "Model id for the faithfulness judge. Blank → use the generation model. Prefer a "
            "strong model, ideally NOT the one under test (avoids self-grading bias)."
        ),
    )

    # ---- UI -----------------------------------------------------------------
    ui_host: str = Field(default="127.0.0.1")
    ui_port: int = Field(default=8000)

    # ---- Auth / multi-user (off by default) ---------------------------------
    # When false, the UI is wide open exactly as before (local dev + tests unchanged).
    # The cloud deploy sets AUTH_ENABLED=true to put a login wall in front of everything.
    auth_enabled: bool = Field(
        default=False,
        description="Require login for the UI. Defaults false so local dev/tests are unchanged.",
    )
    session_ttl_hours: int = Field(default=168, description="Session lifetime in hours (7 days).")
    session_cookie_name: str = Field(default="maayan_session")
    auth_cookie_secure: bool = Field(
        default=False,
        description="Send the session cookie over HTTPS only. Set true in production.",
    )
    pbkdf2_iterations: int = Field(
        default=240_000,
        description="PBKDF2-HMAC-SHA256 rounds for password hashing; raise over time.",
    )
    seed_admin_username: str = Field(
        default="",
        description="Optional first-admin username, seeded once on UI startup if absent.",
    )
    seed_admin_password: SecretStr = Field(
        default=SecretStr(""),
        description="Optional first-admin password (env only). Ignored if blank or user exists.",
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings for entrypoints (CLI/UI). Library code takes Settings via DI."""
    return Settings()
