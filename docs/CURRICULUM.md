# Learning maayan — a hands-on path through RAG

> A self-study curriculum for the owner of this system. The goal: close the gap between
> *having* a working RAG system and *understanding and running* one. Every concept is
> anchored to a real file in this repo and a command you can run — you already own the
> textbook.

## How to use this

- **Order matters.** Each module builds on the last. Module 0 gets the whole thing running
  in your hands first (motivation + a map); then we open each box.
- **Three things per lesson:** the *idea* (the concept), the *anchor* (where it lives in
  your code), and the *hands-on* (something to run, inspect, or change). Do the hands-on —
  that's where it sticks.
- **Lessons are stubs here.** This file is the outline. Ask me to "build out Lesson X.Y"
  and I'll write the full lesson (explanation + the code walkthrough + the exercise) as its
  own doc under `docs/lessons/`.
- **Pace:** roughly one module per sitting. You can stop after Module 4 and already
  understand RAG end-to-end; Modules 5–8 are about *your* system specifically and running
  it for real.

## What you'll be able to do by the end

Explain how a question becomes a grounded, cited answer; reason about *why* retrieval
returns what it does and how to make it better; operate the full pipeline (ingest → index →
ask → capture → develop); tune the knobs with intent; read the eval numbers; and extend the
system without breaking its guarantees.

## Prerequisites

Comfort reading Python (you don't need to write much); a terminal; the repo set up per
[RUNBOOK §2](RUNBOOK.md). No machine-learning background assumed — we build it as we go.

---

## Module 0 — Orientation: the whole loop in your hands

*Goal: see the entire system work once, end to end, and hold a mental map before zooming in.*

- **0.1 — What RAG is, and the problem it solves.** Why a language model alone can't be
  trusted for Torah (it invents mekoros), and how *Retrieval-Augmented Generation* fixes
  that: answer only from retrieved sources, with citations. Anchor: [docs/OVERVIEW.md](OVERVIEW.md).
- **0.2 — The maayan thesis in one picture.** The pipeline (ingest → embed → index →
  retrieve → generate → capture) and the loop that makes it yours. Anchor: [CLAUDE.md](../CLAUDE.md)
  "What this is".
- **0.3 — Run it once, all the way.** `make up`, ingest two chapters, index, `search`,
  `ask` — and deliberately ask something *not* in the corpus to watch it **refuse**.
  Hands-on: [RUNBOOK §3–5](RUNBOOK.md). This single refusal is the whole point; we'll
  spend Module 3 on why it happens.

---

## Module 1 — Turning text into searchable meaning (embeddings & chunking)

*Goal: understand the "R" inputs — how text becomes numbers a computer can compare, and why
you chunk it the way you do.*

- **1.1 — Embeddings & vector space.** What an embedding is: a piece of text → a list of
  numbers (a vector) positioned so that *similar meaning = nearby in space*. Dense vs.
  sparse vectors, and why `bge-m3` gives you both from one model. Anchor: `maayan/embed/`.
  Hands-on: embed two related and two unrelated Hebrew phrases; compare their similarity.
- **1.2 — Chunking: the unit of retrieval.** Why you retrieve *passages*, not whole books,
  and why maayan chunks by the text's **own** structure (a pasuk / os / se'if) instead of
  fixed token windows. Anchor: `maayan/corpus/chunker.py`, the `Chunk` model in
  `maayan/corpus/models.py`. Hands-on: inspect 3 ingested chunks in SQLite.
- **1.3 — Hebrew normalization (and what you deliberately *don't* do).** Stripping markup,
  keeping nikkud, and why rashei-teivot are *not* auto-expanded. Anchor: the normalizer in
  `maayan/corpus/`, `tests/test_normalize.py`. Hands-on: run a raw vs. normalized passage.

---

## Module 2 — Finding the right passages (vector DB & hybrid search)

*Goal: understand where chunks live and how a query pulls back the relevant few.*

- **2.1 — Vector databases & the collection.** What Qdrant stores: vectors + a *payload*
  (ref, book, source, text). Named dense + sparse vectors in one collection. Anchor:
  `maayan/index/qdrant.py`. Hands-on: print the collection's point count and one payload.
- **2.2 — The indexing pipeline.** Embed in batches, upsert by stable id (idempotency —
  why re-running never duplicates), the `indexed` flag. Anchor: `maayan/index/pipeline.py`,
  `maayan/corpus/store.py`. Hands-on: re-run `index` and watch nothing duplicate.
- **2.3 — Hybrid retrieval & fusion (RRF).** Dense (meaning) + sparse (wording) searches,
  combined with Reciprocal Rank Fusion — why two weak signals beat one. The `relevance`
  score and `SearchResult`. Anchor: `maayan/retrieve/retriever.py`,
  `maayan/retrieve/models.py`. Hands-on: `search` with `--k`, read the scores.
- **2.4 — Reranking & filters.** The optional second-pass reranker that sharpens the
  top-k, and metadata filters (`--book`, `--source`). Anchor: the rerank path in
  `maayan/retrieve/`. Hands-on: toggle `RERANK_ENABLED`, compare ordering.

---

## Module 3 — The trust core (generation, grounding, default-deny)

*Goal: understand the "G" — how retrieved passages become a cited answer, and how the system
is built to refuse rather than fabricate.*

- **3.1 — The generation backend (a swappable box).** `GenerationBackend` as a protocol;
  OpenRouter today, Ollama as a drop-in. Anchor: `maayan/generate/base.py`,
  `maayan/generate/ollama.py`. (We'll see *why* it swaps cleanly in Module 5.)
- **3.2 — The grounded prompt & citations.** How sources become a numbered, citable block
  and how `[S#]` tags resolve back to refs. Anchor: `build_context` / `extract_cited_refs`
  in `maayan/generate/rag.py:67`. Hands-on: read an answer, match each `[S#]` to a source.
- **3.3 — Default-deny: the rule that lives in code, not the prompt.** The gate at
  `maayan/generate/rag.py:137` — refuse *before* calling the model when nothing clears the
  threshold. Why this is in code and not "please don't hallucinate." Anchor: `RAGService.ask`.
  Hands-on: trigger a refusal, then *lower* `SCORE_THRESHOLD` and watch the gate open.
- **3.4 — Context-aware follow-ups without losing grounding.** How prior turns help
  interpret a question but are *never citable*. Anchor: `ContextTurn` / `build_conversation`
  in `rag.py`. Hands-on: a pronoun follow-up that only resolves with context.

---

## Module 4 — Knowing if it's actually good (evaluation)

*Goal: replace "it feels right" with numbers.*

- **4.1 — Why eval exists, and the metrics.** hit@k, recall@k, MRR — what each one
  answers, in plain language. Anchor: `maayan/eval/`, the gold set YAMLs in `eval/`.
- **4.2 — Running and reading the harness.** Anchor: `maayan eval`. Hands-on: run it; read
  the table; understand the default-deny gate-rate line.
- **4.3 — Gold sets & honest measurement.** What makes a good `{question, expected_refs}`
  case; negative cases; why the cross-text claim still needs its own gold set (Phase 4,
  Prompt 18). Hands-on: add one gold case and re-run.

---

## Module 5 — How it's built to last (the engineering spine)

*Goal: understand the house rules that make the system testable, swappable, and trustworthy —
so you can change it without fear.*

- **5.1 — Dependency injection: why nothing constructs its own collaborators.** How
  passing services *in* is exactly what lets OpenRouter → Ollama and real models → mocks
  with no logic changes. Anchor: the wiring in `maayan/cli.py`; the house rule in
  [CLAUDE.md](../CLAUDE.md). Hands-on: trace one `ask` from `cli.py` to `RAGService`.
- **5.2 — Typed throughout, pydantic at every boundary.** Why every cross-module datum is
  a model, and what `mypy --strict` buys you. Anchor: any `models.py`. Hands-on: `make typecheck`.
- **5.3 — Config-driven everything.** `Settings` as the single source of tunables — no
  hardcoded models/urls/thresholds. Anchor: `maayan/config.py`. Hands-on: find where a
  knob you used earlier is defined.
- **5.4 — The Clock, and testing without the network.** Why there's no `time.sleep`, and how
  tests mock models/network and use in-memory Qdrant. Anchor: `maayan/clock.py`, `tests/`.
  Hands-on: `make test`, then open one test and see what's faked.

---

## Module 6 — The differentiator (the capture & develop loop)

*Goal: understand the part that makes this more than a search engine — how a scholar's
reasoning becomes durable, retrievable, attributed knowledge.*

- **6.1 — Provenance & the source taxonomy.** `sefaria` / `chabad` / `expert` / `derived` /
  `term` — why every chunk carries who made it, and why printed text is immutable. Anchor:
  [RUNBOOK §0](RUNBOOK.md) table, the `Chunk.source` field.
- **6.2 — Capture: an expert note becomes a retrievable chunk.** Annotations →
  `source="expert"` chunks in the same collection. Anchor: `maayan/capture/`. Hands-on:
  teach a connection ([RUNBOOK §6](RUNBOOK.md)), confirm it surfaces in `search`.
- **6.3 — Seeds vs. corrections, and the develop step.** A seed = knowledge + a directive;
  `develop` grounds it in the corpus or refuses honestly. Anchor:
  `maayan/develop/service.py`. Hands-on: run a seed → develop.
- **6.4 — The approval gate → derived corpus.** Why model output is a *proposal* until a
  human approves, and how an approved development becomes a `derived` chunk with full
  lineage. Anchor: `DevelopmentService.approve`. Hands-on: approve, then re-ask.
- **6.5 — Threads & the term lexicon.** Persistent topic threads; protecting Holy Names
  from expansion. Anchor: `maayan/threads/`, `maayan/lexicon/`. Hands-on: define a term,
  confirm it isn't mangled.

---

## Module 7 — Running it for real (operating & tuning)

*Goal: confidently operate, tune, and feed the system day to day.*

- **7.1 — Setup & dependencies.** `uv` and the `ml` / `ui` extras, Docker/Qdrant,
  `.env` and secrets. Anchor: [RUNBOOK §2](RUNBOOK.md), `pyproject.toml`.
- **7.2 — The knobs that matter.** `SCORE_THRESHOLD`, `top_k`, `EXPERT_BOOST` /
  `DERIVED_BOOST` / `TERM_BOOST`, rerank — what each does to behavior and when to reach
  for it. Anchor: `maayan/config.py`. Hands-on: change a boost, watch ranking move.
- **7.3 — Choosing & swapping the generation backend.** OpenRouter vs. local Ollama —
  cost, privacy, Hebrew quality tradeoffs. Anchor: [RUNBOOK troubleshooting](RUNBOOK.md).
  Hands-on: run the same question on both.
- **7.4 — Growing the corpus.** Adding a Sefaria book (config) vs. a non-Sefaria source
  (the chabad adapter). Anchor: `config.books` / `config.chabad_books`,
  `maayan/corpus/chabad.py`. Hands-on: ingest one more text.
- **7.5 — The web UI as a thin layer.** How routes wire to services and nothing more.
  Anchor: `maayan/ui/app.py`. Hands-on: `make ui`, do the full loop in the browser.

---

## Module 8 — The horizon (extending it well)

*Goal: see where this goes next and how to add capability without breaking the guarantees.*

- **8.1 — Reading quality and improving it.** Using eval to justify a chunking/model/knob
  change with numbers instead of vibes. Ties Module 4 to a real decision.
- **8.2 — Phase 4: the eraser & measurement.** Why retraction matters and how it stays
  provenanced. Anchor: [BUILD_PLAN_PHASE4.md](BUILD_PLAN_PHASE4.md).
- **8.3 — Phase 5: composition.** From grounded answers to grounded documents — the same
  unit, run per section, with default-deny per section. Anchor:
  [BUILD_PLAN_PHASE5.md](BUILD_PLAN_PHASE5.md).
- **8.4 — When (and when not) to fine-tune.** Why RAG + citations stays the backbone, and
  why fine-tuning is a later, register-not-correctness move. Anchor: [BUILD_PLAN §5](BUILD_PLAN.md).

---

## A note on sequencing

Modules **0–4** are *RAG, the universal concepts* — they'd apply to any RAG system.
Modules **5–8** are *this system specifically* — its engineering discipline, its capture
loop, and operating it. If your goal today is "understand RAG," do 0–4. If it's "run and own
maayan," keep going. Either way, start with Module 0 and actually run the loop.
