# Esoteric Torah RAG — Local Build Plan + Claude Code Prompts

> This is the original build plan and prompt sequence for the **maayan** project.
> Saved verbatim so the build can be reproduced / continued prompt-by-prompt.

A local-first system: **Qdrant** (vector DB) + **bge-m3** (local embeddings) + **OpenRouter** (generation via open models), with an expert capture loop. Python.

---

## 0. What you're building (one paragraph)

A pipeline that ingests chassidus/Kabbalah text, embeds it, stores it in Qdrant, retrieves the relevant pieces for a question, and asks an open model (via OpenRouter) to answer **only from those retrieved pieces, with citations**. Then a loop that records how an expert corrects and connects sources, and feeds that back in as new retrievable material. That feedback loop is the part that makes this yours.

## 1. What runs where

- **Local (your laptop):** Qdrant (Docker), the embedding model (bge-m3), the reranker, all app code, the UI.
- **Cloud:** only the final generation call → OpenRouter (an open model like Qwen / Llama / DeepSeek — pick from their current catalog and test 2–3 for Hebrew quality).
- **Later, optional:** swap OpenRouter → Ollama so generation is local too (Prompt 8).

## 2. Prerequisites

- Docker Desktop (for Qdrant).
- Python 3.12, `uv` for envs.
- An OpenRouter API key.
- ~16 GB RAM is comfortable for bge-m3 on CPU/MPS; a Mac with unified memory is ideal.
- Sefaria texts are **CC-BY-NC** — fine for personal/non-commercial use, attribute the source, revisit if you ever commercialize.

## 3. Stack

| Layer | Choice | Why |
|---|---|---|
| Vector DB | Qdrant (local Docker) | open, fast, native hybrid (dense + sparse) |
| Embeddings | `BAAI/bge-m3`, run locally via `sentence-transformers`/`FlagEmbedding` | one model gives dense + sparse, handles Hebrew |
| Reranker (optional) | `BAAI/bge-reranker-v2-m3`, local | tightens top-k before generation |
| Generation | OpenRouter (OpenAI-compatible API), open model from config | model-agnostic, swap without code change |
| Corpus source | Sefaria API (+ your transcribed shiurim) | structured refs, much chassidus/kabbalah |
| Orchestration | thin custom Python (qdrant-client + FlagEmbedding + openai client) | control, no framework magic |

> Alternative embedding model if bge-m3 underperforms on your corpus: `intfloat/multilingual-e5-large` (dense only — you'd drop sparse and lean on Qdrant full-text filters instead). For rabbinic Hebrew specifically, evaluate DICTA's models later via the eval harness (Prompt 7).

## 4. Build order

Run the prompts in sequence in Claude Code, one at a time, in an empty repo. After each, let it write and pass its tests before moving on.

0. Bootstrap + `CLAUDE.md` (house rules live here)
1. Sefaria ingestion
2. Embedding + Qdrant indexing
3. Hybrid retrieval (+ optional rerank)
4. RAG generation via OpenRouter (grounded + cited + refuses ungrounded)
5. Capture loop (expert corrections/connections → back into the index)
6. Local chat + capture UI
7. Eval harness (optional, sets up later fine-tuning)
8. Local generation swap via Ollama (optional)

---

# The prompts

Paste each block as-is. They assume Claude Code is at the repo root.

---

### Prompt 0 — Bootstrap & house rules

```
Set up a new Python 3.12 project called "p'nimiyus-rag" (use a safe dir name like pnimiyus_rag). Use uv for environment and dependency management.

Create this structure:
  pnimiyus_rag/
    config.py        # pydantic-settings, loads from .env, no secrets in code
    corpus/          # ingestion
    embed/           # embedding service
    index/           # qdrant client + indexing
    retrieve/        # search
    generate/        # openrouter client + RAG
    capture/         # expert annotation loop
    cli.py           # typer CLI entrypoint
  tests/
  docker-compose.yml # qdrant service, local volume
  .env.example
  Makefile           # up, down, index, search, ask, test, ui
  CLAUDE.md
  pyproject.toml

Write CLAUDE.md documenting the architecture and these house rules, which ALL future work must follow:
- Typed throughout (mypy-clean). Pydantic models for all data crossing module boundaries.
- No time.sleep in business logic. Use an injectable Clock; any waiting/backoff is async or driven by the injected clock so tests don't sleep.
- Dependency injection: services (embedder, qdrant client, generation backend, clock) are passed in, never constructed inside business logic. This is what lets us swap OpenRouter for Ollama later.
- Config-driven: model names, collection names, top-k, OpenRouter base URL/model all come from config, never hardcoded.
- No secrets in code or logs. Read keys from env.
- Default-deny on generation: the system must refuse to answer when retrieval returns nothing that supports the answer. Never let the model answer from its own memory.
- Every code change ships with tests. Use pytest. Mock network and models in unit tests.

Add docker-compose for Qdrant (latest, with a named local volume) and a Makefile target `up`/`down`. Add .env.example with OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_BASE_URL, QDRANT_URL, EMBED_MODEL.

Initialize git, write a short README, and verify `uv run python -c "import pnimiyus_rag"` works and `docker compose config` is valid. Do not write application logic yet — just the skeleton, config, and CLAUDE.md.
```

---

### Prompt 1 — Sefaria ingestion

```
Implement corpus ingestion from the Sefaria API. Follow CLAUDE.md.

Goal: pull a configurable list of chassidus/Kabbalah works (start with: Tanya, Likutei Torah, Torah Or — make the list config-driven), and normalize them into chunks ready for embedding.

Requirements:
- A typed SefariaClient that fetches a text by its index/ref and returns structured segments with their canonical ref (e.g. "Tanya, Chapter 1:3"), the Hebrew text, and the English text if present. Use the v3 text API; respect rate limits via the injected Clock and async, NOT time.sleep.
- A Chunk pydantic model: id, ref, book, section_path, lang ("he"/"en"), text, source ("sefaria"), plus a metadata dict.
- Chunk by the text's OWN structure (one segment = one chunk). Do not use fixed token windows — preserve the natural unit (pasuk / os / se'if).
- Light Hebrew normalization step (separate, testable function): strip surrounding markup/HTML, normalize whitespace, keep nikkud. Leave a documented hook where rashei-teivot expansion can be added later — do not attempt it now.
- Persist chunks to local SQLite (and optionally JSONL export). Idempotent: re-running upserts by id, doesn't duplicate.
- CLI: `cli.py ingest --book "Tanya"` and `ingest --all`.
- Tests: use a recorded API fixture (vcr-style or a small saved JSON) so tests don't hit the network. Test the normalizer and the chunker independently.

Show me a sample of 5 ingested chunks when done.
```

---

### Prompt 2 — Embedding + Qdrant indexing

```
Implement the embedding service and Qdrant indexing. Follow CLAUDE.md.

Requirements:
- An Embedder interface (protocol) with embed(texts) -> dense vectors AND sparse vectors. Concrete implementation wraps BAAI/bge-m3 (FlagEmbedding), loaded once, run locally (CPU/MPS). Batch internally. Model name from config.
- Index module: create a Qdrant collection with a NAMED dense vector (correct dim + cosine) and a sparse vector, so we can do hybrid search later. Make collection name and vector params config-driven. Creation is idempotent.
- An indexing pipeline that reads chunks from SQLite, embeds them in batches, and upserts to Qdrant with full payload (ref, book, section_path, lang, source, text). Re-running is idempotent (upsert by stable id).
- CLI: `cli.py index` (indexes everything not yet indexed) and `index --rebuild`.
- Tests: mock the embedder (return fixed vectors) and run against an ephemeral in-memory/temporary Qdrant instance. Verify collection schema, upsert, and idempotency.

Report collection point count and a sample payload when done.
```

---

### Prompt 3 — Hybrid retrieval (+ optional rerank)

```
Implement retrieval. Follow CLAUDE.md.

Requirements:
- A Retriever that takes a query string, embeds it with the same bge-m3 Embedder (dense + sparse), and runs a HYBRID search in Qdrant using the Query API with fusion (RRF) over the dense and sparse vectors. Return top-k SearchResult objects: ref, text, score, payload. top-k from config.
- Optional rerank stage behind a config flag: if enabled, load BAAI/bge-reranker-v2-m3 locally and rerank the fused candidates, returning the top-n. Keep it injectable so it can be disabled in tests.
- Support metadata filters (e.g. restrict to a book, or to source="expert" vs source="sefaria").
- CLI: `cli.py search "מהי בחירה חופשית" --k 8` prints refs + scores + first line of each.
- Tests: ephemeral Qdrant seeded with a handful of known chunks; assert that a query retrieves the expected ref above an unrelated one. Mock the reranker.

Show search output for two sample Hebrew queries.
```

---

### Prompt 4 — RAG generation via OpenRouter

```
Implement grounded generation. Follow CLAUDE.md — especially default-deny.

Requirements:
- A GenerationBackend protocol: generate(system, messages) -> text. Concrete OpenRouterBackend uses the OpenAI-compatible client pointed at OPENROUTER_BASE_URL with OPENROUTER_MODEL and OPENROUTER_API_KEY from config. Keep it injectable (we'll add an Ollama backend later with the same interface).
- A RAG service that: takes a question, calls the Retriever, and if retrieval returns nothing above a configurable score threshold, RETURNS A REFUSAL ("I don't have a source for this") WITHOUT calling the model. This is the default-deny rule — enforce it in code, not just the prompt.
- When sources exist: build a context block listing each retrieved source with its ref, and a strict system prompt instructing the model to answer ONLY from the provided sources, to cite the ref inline for every claim, to say so plainly when the sources don't cover the question, and to never introduce outside facts or invent mekoros. Return an Answer object: text + the list of cited refs + the raw retrieved sources.
- CLI: `cli.py ask "..."` prints the answer and a Sources section with refs.
- Tests: mock the GenerationBackend and Retriever. Assert that (a) empty retrieval → refusal with no backend call, (b) populated retrieval → backend called with the sources in context, (c) the returned answer surfaces the cited refs.

Demonstrate one grounded answer and one refusal (ask something not in the corpus).
```

---

### Prompt 5 — The capture loop

```
Implement the expert capture loop. Follow CLAUDE.md. This is the core differentiator.

Requirements:
- A Session model persisted to SQLite: id, timestamp (from injected Clock), question, retrieved_refs, answer_text.
- An Annotation model: id, session_id, author (expert name/id), kind (one of an enum: "correction", "connection", "addition", "objection"), body (the expert's text), linked_refs (zero or more source refs this annotation ties together), and a free "move" tag (e.g. "pasuk->concept", "sefirah->nefesh"). Make the enum and tags extensible via config.
- A function that converts each Annotation into one or more retrievable Chunks (source="expert", with the author and kind in metadata and the linked_refs preserved), embeds them with the same Embedder, and upserts them into the SAME Qdrant collection. After this, expert annotations are retrievable alongside the printed text — closing the loop.
- CLI: `cli.py annotate --session <id> --kind connection --body "..." --refs "Tanya 1:3,Likutei Torah ..." --move "pasuk->concept"`.
- A retrieval flag to weight or boost expert-sourced chunks (config-driven), so the system can prefer human-vetted connections when present.
- Tests: create a session, add an annotation, run the conversion, assert a new expert-sourced point exists in Qdrant and is retrievable by a related query; assert metadata (author, kind, linked_refs) round-trips.

Walk through one full cycle: ask → answer → expert adds a connection → re-ask a related question → show the expert connection now surfacing in retrieval.
```

---

### Prompt 6 — Local chat + capture UI

```
Build a minimal LOCAL web UI. Follow CLAUDE.md. Prioritize working over pretty.

Requirements:
- FastAPI backend exposing: POST /ask (question -> answer + sources + session_id), POST /annotate (session_id + annotation fields), GET /session/{id}.
- A single static page (vanilla JS or htmx, no build step) with: a question box; an answer panel that renders the answer and a clickable Sources list (each showing its ref and text); and an "Annotate" panel where the expert picks a kind, writes a note, optionally selects which of the shown sources to link, and tags a move. Submitting calls /annotate.
- Reuse the existing RAG service and capture loop — the UI is a thin layer, no business logic in the route handlers.
- Make: `make ui` runs it locally on a fixed port.
- Tests: FastAPI TestClient hitting /ask (mocked RAG) and /annotate (mocked capture); assert wiring, not the model.

Confirm I can run `make up && make ui`, ask a question in the browser, see cited sources, and submit an annotation that lands in SQLite + Qdrant.
```

---

### Prompt 7 — Eval harness (optional, do before fine-tuning)

```
Add a retrieval evaluation harness. Follow CLAUDE.md.

Requirements:
- A gold set format (YAML/JSON): a list of {question, expected_refs}. Seed it with ~15 examples I can edit.
- A script that runs each question through the Retriever and computes hit@k, recall@k, and MRR against expected_refs. Output a small table.
- A comparison mode: run the same gold set across configurable variants (embedding model, rerank on/off, hybrid vs dense-only, top-k) and print a side-by-side table, so I can justify model/chunking choices with numbers instead of vibes.
- Make the embedding model swappable here specifically so I can later drop in multilingual-e5-large or a DICTA rabbinic-Hebrew model and measure.
- Tests on the metric functions with tiny hand-checked inputs.

Run it once on the seed gold set and show the table.
```

---

### Prompt 8 — Local generation swap via Ollama (optional)

```
Add a fully-local generation option. Follow CLAUDE.md.

Requirements:
- An OllamaBackend implementing the same GenerationBackend protocol as OpenRouterBackend, talking to a local Ollama server, model from config.
- A config switch GENERATION_BACKEND = "openrouter" | "ollama" that selects which backend is injected. No other code changes anywhere.
- Document in CLAUDE.md how to pull a suitable open instruct model in Ollama and switch over, and note the tradeoff (offline + private + free vs. smaller model quality, especially for Hebrew).
- Tests: assert the factory returns the right backend per config; mock both servers.

Show the same question answered with backend=openrouter and backend=ollama.
```

---

## 5. After this works

- **Quality is the corpus, not the code.** Once the loop runs, the leverage is getting real people to ask and annotate. The eval harness tells you when retrieval is actually good.
- **Fine-tuning is later.** Only once you have a meaningful volume of expert annotations does it make sense — and it changes fluency/register, not correctness. RAG with citations stays the backbone regardless.
- **Add your shiurim.** Your transcribed Gal Einai / Ginsburgh material is exactly the high-value expert layer — it ingests through the same Chunk model with source="expert" (or "shiur").
