# maayan — Esoteric Torah RAG

> **maayan** (מעיין, "wellspring") — a local-first RAG system for chassidus /
> Kabbalah text, with an expert capture loop that turns a scholar's corrections
> and connections into new retrievable knowledge. The capture loop is the point.

This file is the contract. **All work in this repo must follow the house rules
below.** Read it before changing anything.

---

## What this is

A pipeline that:

1. **Ingests** chassidus/Kabbalah text from Sefaria (and, later, transcribed
   shiurim), preserving each text's natural unit (pasuk / os / se'if) as a chunk.
2. **Embeds** chunks locally with `bge-m3` (dense + sparse in one model).
3. **Indexes** them in a local Qdrant collection (named dense vector + sparse
   vector → hybrid search).
4. **Retrieves** the relevant chunks for a question via hybrid (RRF) search, with
   an optional local reranker.
5. **Generates** an answer via OpenRouter (an open model) that is **grounded only
   in the retrieved sources, with inline citations** — and **refuses** when
   nothing supports an answer.
6. **Captures** how an expert corrects/connects sources, converts those
   annotations into expert-sourced chunks, and feeds them back into the same
   index — closing the loop.

## What runs where

| Concern | Where |
|---|---|
| Qdrant, embeddings, reranker, app code, UI | **Local** |
| Final generation call | **Cloud** (OpenRouter) — swappable to local Ollama (Prompt 8) |

> **Deployment:** the same stack can run on a free always-on VM (Oracle Always Free + a
> public URL via Tailscale, with per-user login). The whole backend stays together — only
> the host moves. Plan, manual steps, and runbook: [docs/cloud_deploy/](docs/cloud_deploy/README.md).
> Auth is off by default (`auth_enabled=false`) so local dev/tests are unchanged.

---

## House rules (non-negotiable)

1. **Typed throughout, mypy-clean.** `mypy` runs in strict mode (`make typecheck`).
   Every datum that crosses a module boundary is a **pydantic model**, not a loose
   dict/tuple.
2. **No `time.sleep` in business logic.** Use the injectable `Clock`
   (`maayan/clock.py`). Any waiting/backoff is `async` and driven by the injected
   clock so tests never actually sleep (`FakeClock`).
3. **Dependency injection.** Services — embedder, Qdrant client, generation
   backend, clock, settings — are **passed in**, never constructed inside business
   logic. This is what lets us swap OpenRouter → Ollama and real models → mocks
   without touching the logic. Construction happens at the edges (`cli.py`, the UI
   route wiring, tests).
4. **Config-driven.** Model names, collection names, top-k, thresholds, base URLs,
   the corpus book list — all come from `maayan/config.py` (`Settings`). Nothing
   is hardcoded in logic.
5. **No secrets in code or logs.** API keys are read from env via `Settings`
   (`SecretStr`). Never print or log a key.
6. **Default-deny on generation.** If retrieval returns nothing above
   `score_threshold`, the system **refuses without calling the model**. This is
   enforced in code, not just in the prompt. The model must never answer from its
   own memory — only from retrieved sources, with citations.
7. **Every change ships with tests.** `pytest`. Unit tests **mock the network and
   the models** (no real OpenRouter / Sefaria / model downloads in unit tests).
   Use ephemeral/in-memory Qdrant for index/retrieve tests.

---

## Architecture / layout

```
maayan/
  config.py        Settings (pydantic-settings). The single source of tunables.
  clock.py         Clock protocol + SystemClock + FakeClock (DI for time/waiting).
  corpus/          Sefaria ingestion → Chunk models → SQLite.            (Prompt 1)
  embed/           Embedder protocol + bge-m3 impl (dense + sparse).     (Prompt 2)
  index/           Qdrant collection mgmt + indexing pipeline.           (Prompt 2)
  retrieve/        Hybrid (RRF) Retriever + optional reranker.           (Prompt 3)
  generate/        GenerationBackend protocol, OpenRouter/Ollama, RAG.   (Prompt 4/8)
  capture/         Session + Annotation models → expert chunks.          (Prompt 5)
  cli.py           Typer entrypoint — thin; builds + injects services.
tests/             pytest; network + models mocked.
docs/BUILD_PLAN.md The original plan + the prompt for each build step.
docker-compose.yml Local Qdrant (named volume).
```

### Data model spine

- **`Chunk`** is the unit that flows corpus → embed → index → retrieve. Fields:
  `id, ref, book, section_path, lang ("he"/"en"), text, source, metadata`.
  `source` is `"sefaria"` for printed text, `"expert"` (or `"shiur"`) for
  human-captured knowledge. Expert chunks live in the **same** collection and are
  retrievable alongside the text — that is the loop.

### Backend swap (why DI matters)

`generate/` defines a `GenerationBackend` protocol. `OpenRouterBackend` (cloud)
and, later, `OllamaBackend` (local) both implement it. `GENERATION_BACKEND` in
config selects which is injected — **no other code changes**.

---

## Dependencies

Core deps install fast. Heavy ML deps (torch, FlagEmbedding) and the web UI are
**extras** so the skeleton and unit tests stay quick:

```bash
uv sync                 # core: pydantic, typer, httpx, qdrant-client, openai + dev tools
uv sync --extra ml      # adds torch + FlagEmbedding (needed from Prompt 2 on)
uv sync --extra ui      # adds fastapi + uvicorn (Prompt 6)
```

---

## Workflow

```bash
make up         # start local Qdrant (docker)
make down       # stop it
make test       # pytest (network/models mocked)
make typecheck  # mypy --strict
make lint       # ruff
make ingest     # pull + chunk corpus            (Prompt 1)
make index      # embed + upsert into Qdrant      (Prompt 2)
make search Q='...'   # hybrid retrieval          (Prompt 3)
make ask Q='...'      # grounded, cited answer    (Prompt 4)
make ui         # local FastAPI chat + capture UI (Prompt 6)
```

### Definition of done for any change
1. `make test` passes (new behavior has tests; network/models mocked).
2. `make typecheck` is clean.
3. `make lint` is clean.
4. New tunables are in `config.py`; no hardcoded models/URLs/keys.

---

## Conventions / gotchas

- **Refs are canonical Sefaria refs** (e.g. `"Tanya, Chapter 1:3"`) and double as
  human-readable citations. Keep them stable; chunk `id` derives from the ref so
  re-ingest is idempotent (upsert, never duplicate).
- **Hebrew handling:** normalization strips markup and normalizes whitespace but
  **keeps nikkud**. There is a documented hook for rashei-teivot expansion — do
  not implement it speculatively.
- **Licensing:** Sefaria text is **CC-BY-NC**. Fine for personal/non-commercial
  use; attribute Sefaria; revisit before any commercial use.
- **Generation backend swap to Ollama** (Prompt 8): pull an open instruct model
  (`ollama pull qwen2.5:7b-instruct`), set `GENERATION_BACKEND=ollama` and
  `OLLAMA_MODEL`. Tradeoff: offline + private + free, but smaller models are
  weaker — especially on Hebrew. RAG + citations stays the backbone regardless.
