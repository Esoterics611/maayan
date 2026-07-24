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

    generation_max_tokens: int = Field(
        default=4096,
        description=(
            "Cap on output tokens per generation call. Without it OpenRouter reserves the "
            "model's full context, which 402s on low balances and some free endpoints reject "
            "outright; 4096 is generous for grounded answers and per-section fills."
        ),
    )
    generation_timeout: float = Field(
        default=120.0,
        description="Per-request timeout (s) for cloud generation; free endpoints can be slow.",
    )
    generation_max_retries: int = Field(
        default=5,
        description=(
            "Client-side retries for transient 429/5xx (the SDK honors Retry-After). Free "
            "OpenRouter models are heavily contended, so retries keep a drip run alive."
        ),
    )

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
    embed_fold_nikkud: bool = Field(
        default=True,
        description=(
            "Strip nikkud/te'amim from text on its way INTO the embedder (documents and "
            "queries alike). Stored corpus text keeps its nikkud. bge-m3 tokenizes nikkud "
            "as separate subwords, so a vocalized passage and the unvocalized query that "
            "should match it share only ~10-17% of their sparse terms. Takes effect for "
            "documents only after a re-index (the vectors change); queries are unaffected "
            "either way, since nobody types nikkud."
        ),
    )

    # ---- Reranker (local, optional) -----------------------------------------
    rerank_enabled: bool = Field(default=False)
    rerank_model: str = Field(default="BAAI/bge-reranker-v2-m3")
    rerank_candidates: int = Field(
        default=30, description="Fused candidates fetched for the reranker to reorder."
    )
    rerank_device: str = Field(
        default="",
        description='Torch device for the reranker; blank falls back to EMBED_DEVICE.',
    )
    rerank_batch_size: int = Field(
        default=16, description="Query/document pairs scored per forward pass."
    )
    rerank_max_length: int = Field(
        default=512,
        description="Token cap per (query, document) pair. bge-reranker-v2-m3 supports more, "
        "but 512 covers a passage and keeps latency and VRAM bounded.",
    )

    # ---- Health checks ------------------------------------------------------
    health_timeout: float = Field(
        default=5.0, description="Per-probe network timeout (s). Health must fail fast."
    )
    health_check_generation: bool = Field(
        default=True,
        description=(
            "Probe the generation backend's reachability. Lists models — it NEVER calls a "
            "completion endpoint, so asking 'are you alive?' never bills tokens."
        ),
    )
    health_probe_text: str = Field(
        default="בדיקה", description="Tiny string the embedder probe encodes."
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
    gate_signal: str = Field(
        default="hybrid_pool",
        description=(
            'Which signal the default-deny gate judges on: "hybrid_pool" (pooled dense '
            'cosine + weighted pooled sparse) or "dense_top" (the original single top '
            "cosine). Each carries its OWN threshold — see `effective_score_threshold` — "
            "because they are on different scales and must never share a number."
        ),
    )
    gate_hybrid_threshold: float = Field(
        default=0.795,
        description=(
            "Threshold for gate_signal='hybrid_pool' (dense_mean + weight*sparse_mean). "
            "Derived empirically on the folded index: 42 gold positives vs 22 negatives "
            "(10 authored + 12 blatantly off-topic) → answers 100% of positives, refuses "
            "91% of negatives. NOT on the cosine scale; do not reuse SCORE_THRESHOLD here."
        ),
    )
    gate_sparse_weight: float = Field(
        default=3.0,
        description=(
            "Weight on the pooled sparse term in the hybrid gate. Sparse scores sit around "
            "0.05-0.15 vs cosine's 0.40-0.65, so this puts them on comparable footing. "
            "Corpus- and model-dependent, hence configured rather than baked in."
        ),
    )
    gate_pool: int = Field(
        default=10,
        description=(
            "Candidate depth the gate's mean relevance signals average over. A single "
            "top cosine is a max over ~9k points (noisy); pooling the top-N is a much "
            "lower-variance estimate of how much relevant material actually exists."
        ),
    )

    # Per-surface gate overrides. Blank (None) → the global threshold, so by default
    # every surface behaves identically and nothing changes. They exist because the
    # surfaces ask retrieval for different things: `ask` answers one question from the
    # best sources; `compose` fills a whole outline section by section, where a thin
    # section should become an honest gap rather than thin prose; `develop` proposes
    # NEW knowledge for a human to approve, where a bad proposal costs review time.
    # Tune with `maayan eval` per surface — do not guess.
    ask_score_threshold: float | None = Field(
        default=None, description="Gate threshold for `ask`. Blank → the global one."
    )
    compose_score_threshold: float | None = Field(
        default=None, description="Gate threshold for compose `fill`. Blank → the global one."
    )
    develop_score_threshold: float | None = Field(
        default=None, description="Gate threshold for `develop`. Blank → the global one."
    )

    def surface_threshold(self, surface: str | None = None) -> float:
        """The gate threshold for one surface, falling back to the global one.

        THE accessor for the answer/refuse comparison. Callers must never read
        `score_threshold` or `gate_hybrid_threshold` directly: which of those applies
        depends on `gate_signal`, and they are on different scales.
        """
        override = {
            "ask": self.ask_score_threshold,
            "compose": self.compose_score_threshold,
            "develop": self.develop_score_threshold,
        }.get(surface or "")
        return self.effective_score_threshold if override is None else override

    @property
    def effective_score_threshold(self) -> float:
        """The threshold that matches the configured gate signal.

        `relevance` on a `RetrievalResult` is whatever the injected gate computed, so
        every caller comparing against a threshold must use THIS, never
        `score_threshold` directly — the two signals are on different scales and
        crossing them silently disables the gate in one direction or the other.
        """
        if self.gate_signal == "hybrid_pool":
            return self.gate_hybrid_threshold
        return self.score_threshold
    dedupe_refs: bool = Field(
        default=True,
        description=(
            "Keep only the best-scoring hit per ref. 791 refs in this corpus exist twice "
            "(Hebrew source + English translation share the citation), so without this a "
            "grounding set can spend two top_k slots on one passage and cite it as both "
            "[S3] and [S5]. Keeps the higher-scoring copy, so it self-adapts to the "
            "question's language."
        ),
    )
    inspect_show: int = Field(
        default=8, description="Hits per stage listed by the retrieval inspector (display only)."
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
    summary_boost: float = Field(
        default=1.0,
        description="Multiplier for source='summary' chunks (gated section summaries, Prompt 42).",
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

    # ---- Lexicon auto-population (Phase 3) ----------------------------------
    # Claude-as-builder: a strong model DRAFTS term definitions, but only from
    # retrieved corpus sources, with citations, and every draft is queued for expert
    # approval before it is indexed — nothing auto-trusted (mirrors the capture loop).
    lexicon_draft_model: str = Field(
        default="",
        description=(
            "Model id used to DRAFT lexicon/connector definitions. Blank → the generation "
            "model (free Qwen). Set to the OpenRouter Claude slug (e.g. "
            "'anthropic/claude-opus-4.8') to draft with Claude; drafts are still "
            "corpus-grounded, cited, and expert-gated before indexing."
        ),
    )
    lexicon_draft_top_k: int = Field(
        default=6, description="Corpus sources retrieved to ground (and gate) one term draft."
    )
    lexicon_draft_verify: bool = Field(
        default=True,
        description="Run the faithfulness pass on each draft; flagged drafts are unsupported.",
    )
    lexicon_mine_min_count: int = Field(
        default=3,
        description="Min corpus occurrences for a gershayim token to be a term candidate.",
    )
    lexicon_mine_top_n: int = Field(
        default=50, description="Cap on mined term candidates returned (ranked by frequency)."
    )

    # ---- Populate drip (`maayan populate`) ----------------------------------
    # Free generation endpoints rate-limit hard, so populate runs as a paced drip
    # with backoff (Clock-injected, so tests never wait). Each draft persists as it
    # happens → a run that dies mid-way resumes cleanly.
    populate_pace_seconds: float = Field(
        default=20.0, description="Seconds between drafts in a populate run."
    )
    populate_backoff_seconds: float = Field(
        default=30.0, description="Base linear backoff after a retryable draft error (× attempt)."
    )
    populate_max_retries: int = Field(
        default=5, description="Max attempts per item before skipping it (it resumes next run)."
    )
    populate_connector_k: int = Field(
        default=8, description="Sources retrieved per probe when mining connection candidates."
    )

    # ---- Knowledge graph (Phase 7, Prompt 33) --------------------------------
    graph_default_confidence: float = Field(
        default=1.0,
        description="Confidence assigned to human-asserted edges (expert adds, backfill).",
    )
    graph_bootstrap_confidence: float = Field(
        default=0.6,
        description=(
            "Confidence for edges lifted from bootstrap-drafted connections: they passed "
            "the faithfulness gate but no human review, so they start below expert edges "
            "and the inquiry queue can rank them for re-review."
        ),
    )
    graph_expand_enabled: bool = Field(
        default=False,
        description=(
            "Widen supported retrievals one hop along approved graph edges. The "
            "default-deny gate is decided on the seed retrieval alone — expansion can "
            "enrich a supported answer, never rescue a refusal."
        ),
    )
    graph_expand_seeds: int = Field(
        default=3, description="How many top seed hits to expand from (one hop each)."
    )
    graph_expand_limit: int = Field(
        default=4, description="Hard cap on chunks added by graph expansion per query."
    )
    graph_links_enabled: bool = Field(
        default=True,
        description=(
            "Allow `maayan graph ingest-links` (curated Sefaria links → edges). Pacing "
            "reuses sefaria_rate_limit_seconds, mirroring the corpus ingester."
        ),
    )
    sefaria_link_categories: list[str] = Field(
        default=["Tanakh", "Talmud", "Mishnah", "Midrash", "Kabbalah"],
        description=(
            "Sefaria link categories kept as citation edges. Verified against the live "
            "/api/links payload (2026-07-02): 'Tanakh' targets become quotes_pasuk (the "
            "pasuk-join key), the rest become quotes. 'Commentary' (e.g. 'Sources and "
            "References on Torah Ohr') and 'Jewish Thought' are meta-material, not "
            "citations, and are deliberately not kept."
        ),
    )

    # ---- Inquiry queue (Phase 7, Prompt 37) ----------------------------------
    ask_log_enabled: bool = Field(
        default=True,
        description=(
            "Log every ask (question, refused, top score) so refused questions become "
            "inquiries instead of evaporating. No new PII: user mirrors existing auth."
        ),
    )
    inquiry_confidence_threshold: float = Field(
        default=0.7,
        description="Approved relations below this confidence surface for expert review.",
    )
    inquiry_count_weight: float = Field(
        default=0.8,
        description="Priority weight × an item's count signal (e.g. refusals in a cluster).",
    )
    inquiry_recency_weight: float = Field(
        default=1.0, description="Priority weight × the item's recency score (0..1)."
    )
    inquiry_recency_halflife_days: float = Field(
        default=7.0, description="Days after which an item's recency score halves."
    )
    inquiry_kind_weights: dict[str, float] = Field(
        default={
            "refused_question": 5.0,
            "contradiction": 4.5,
            "undergrounded_term": 3.5,
            "low_evidence_relation": 2.5,
            "re_review": 1.5,
        },
        description=(
            "Base priority per inquiry kind — the queue's values, stated in config: "
            "learners' unanswered questions first, then conflicts, then coverage gaps."
        ),
    )

    # ---- Chavrusa agent (Phase 7, Prompt 39) ---------------------------------
    agent_enabled: bool = Field(
        default=False,
        description=(
            "The bounded multi-hop study loop behind `ask --agent`. The default-deny "
            "gate is unchanged: a refused seed never reaches the model."
        ),
    )
    agent_max_hops: int = Field(
        default=4, description="Max actions the agent may take before force-concluding."
    )
    agent_max_chunks: int = Field(
        default=12, description="Max chunks in the agent's working set."
    )
    agent_max_calls: int = Field(
        default=6,
        description="Max model calls for CHOOSING actions (conclude's synthesis is extra).",
    )

    # ---- Study programs (Phase 7, Prompt 40) --------------------------------
    # A sweep runs the chavrusa over a sefer unit by unit, drafting typed edge
    # proposals for the gates. It reuses the populate drip's pacing/backoff/resume
    # (populate_*), so only the study-specific knobs live here. Nothing it drafts is
    # auto-approved — every edge lands "proposed" (evidence derived_bootstrap).
    study_program_model: str = Field(
        default="",
        description=(
            "Model id used to DRAFT study-program proposals (mirrors lexicon_draft_model). "
            "Blank → the generation model. Set the OpenRouter Claude slug to sweep with "
            "Claude while maayan's own answers stay on the configured model."
        ),
    )
    study_program_k: int = Field(
        default=8,
        description="Corpus sources co-retrieved per unit to ground (and gate) its proposals.",
    )
    study_unit_max_proposals: int = Field(
        default=6, description="Per-unit budget: hard cap on proposals drafted from one unit."
    )
    study_pace_seconds: float = Field(
        default=20.0, description="Seconds between units in a study sweep (drip pacing)."
    )
    study_draft_verify: bool = Field(
        default=True,
        description="Run the faithfulness pass on each proposal; flagged ones are unsupported.",
    )

    # ---- Structural depth (Phase 7, Prompt 42) ------------------------------
    # Two additions, both gated, neither touching printed text: a window of a hit's
    # neighboring passages fed to the model at generation time (citation stays the hit),
    # and gated one-level section summaries indexed as source="summary".
    parent_context_chars: int = Field(
        default=0,
        description=(
            "Chars of neighboring same-section passages attached to each hit at generation "
            "time (0 = off). Context only — the citation is always the retrieved passage."
        ),
    )
    summary_draft_model: str = Field(
        default="",
        description="Model id used to DRAFT section summaries (mirrors lexicon_draft_model).",
    )
    summary_pace_seconds: float = Field(
        default=20.0, description="Seconds between sections in a `summarize` drip run."
    )
    summary_draft_verify: bool = Field(
        default=True,
        description="Run the faithfulness pass on each summary; flagged summaries are unsupported.",
    )

    # ---- Consolidation + chazarah (Phase 7, Prompt 41) ----------------------
    # Sugya pages consolidate a cluster of approved knowledge into a curated, versioned,
    # gated topic page; chazarah resurfaces aging/low-evidence/never-used knowledge for
    # re-review. Neither weakens the gate — pages index only on approval, and superseding
    # a version retracts the old chunks through the audited retract flow.
    sugya_min_cluster_size: int = Field(
        default=2,
        description="Min corpus refs in a connected component for it to form a sugya cluster.",
    )
    sugya_draft_model: str = Field(
        default="",
        description=(
            "Model id used to DRAFT sugya pages (mirrors lexicon_draft_model). Blank → the "
            "generation model."
        ),
    )
    chazarah_bootstrap_days: float = Field(
        default=90.0,
        description="Bootstrap-evidence edges older than this many days come up for re-review.",
    )
    chazarah_base_interval_days: float = Field(
        default=30.0,
        description="Initial spaced-repetition interval for a newly scheduled re-review target.",
    )
    chazarah_interval_factor: float = Field(
        default=2.0,
        description="Each re-review confirmation multiplies the target's next-review interval.",
    )

    # ---- Captured goldset / eval flywheel (Phase 7, Prompt 38) ---------------
    captured_goldset_enabled: bool = Field(
        default=True,
        description=(
            "Every gated approval (connection/development/term, answered inquiry) "
            "auto-drafts a deterministic regression example; retraction removes it."
        ),
    )
    captured_reports_dir: str = Field(
        default="eval/captured_reports",
        description="Where `eval --captured` writes date-stamped JSON reports (trendable).",
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
    backup_dir: str = Field(
        default="data/backups",
        description="Where `maayan backup` writes timestamped SQLite copies of the knowledge.",
    )
    backup_keep: int = Field(
        default=14, description="How many recent SQLite backups to retain (older are pruned)."
    )
    log_level: str = Field(
        default="INFO", description="Log level for maayan's own logs at the CLI entrypoints."
    )

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
    eval_lexical_goldset_path: str = Field(
        default="eval/lexical_goldset.yaml",
        description=(
            "GENERATED lexical-recall cases (term -> every chunk that contains it). "
            "Ground truth comes from the corpus, not from authored questions, so it "
            "measures recall of a term's whole discussion rather than top-1 relevance."
        ),
    )
    eval_lexical_terms: list[str] = Field(
        default=[
            "צמצום", "קליפת נוגה", "אין סוף", "דירה בתחתונים", "אתכפיא", "אתהפכא",
            "ממלא כל עלמין", "סובב כל עלמין", "נפש הבהמית", "נפש האלקית",
            "יחודא עילאה", "יחודא תתאה", "שבירת הכלים", "תהו ותיקון", "אהבה ויראה",
            "גילוי אלקות", "עבודת התפלה", "חכמה בינה ודעת", "אור מקיף", "אור פנימי",
            "הארת הנשמה", "תשובה עילאה", "אתערותא דלתתא", "אתערותא דלעילא",
            "פנימיות הלב",
        ],
        description="Candidate terms for the lexical recall guard; --rebuild keeps those in range.",
    )
    eval_lexical_min_occurrences: int = Field(
        default=3, description="Below this a term's recall@k is noise — skip it."
    )
    eval_lexical_max_occurrences: int = Field(
        default=400,
        description=(
            "Skip terms above this. The corpus is dense in its own vocabulary, so most "
            "real concepts occur in the hundreds; precision@k carries those, while recall "
            "is capped by k. Far beyond this the term is vocabulary, not a topic."
        ),
    )

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

    # ---- Benchmark (head-to-head: grounded maayan vs frontier closed-book) ---
    bench_goldset_path: str = Field(
        default="eval/benchmark_goldset.yaml",
        description="Expert gold set for the head-to-head benchmark (adds `answer` + `stratum`).",
    )
    bench_closed_book_model: str = Field(
        default="",
        description="Arm B: the frontier model answering closed-book. Blank → generation model.",
    )
    bench_judge_model: str = Field(
        default="",
        description=(
            "Blinded pairwise grader model. Blank → eval_judge_model, else the generation model. "
            "Prefer a strong model that is NEITHER arm under test."
        ),
    )
    bench_seed: int = Field(
        default=0, description="RNG seed for blinding (answer-order randomization) — reproducible."
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
