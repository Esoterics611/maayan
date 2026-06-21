# maayan · מעיין — Esoteric Torah RAG

**maayan** (מעיין, "wellspring") is a **local-first** retrieval system for chassidus /
Kabbalah (p'nimiyus haTorah). It ingests Torah sources, retrieves the relevant
pieces for a question, and asks an open model to answer **only from those sources,
with citations** — refusing when nothing supports an answer. An **expert capture
loop** records how a scholar corrects and connects sources and feeds that back in
as new retrievable knowledge. **That loop is the point.**

Initial corpus focus: **Likutei Amarim (Tanya, Part I).**

```
        question
           │
   ┌───────▼────────┐   hybrid (dense+sparse, RRF)   ┌──────────────┐
   │   Retriever     │ ─────────────────────────────▶│    Qdrant     │
   └───────┬────────┘                                 │ (local Docker)│
           │ sources + relevance                      └──────▲───────┘
   ┌───────▼────────┐  default-deny gate                     │ expert chunks
   │   RAG service   │  (refuse if unsupported)               │
   └───────┬────────┘                                 ┌──────┴───────┐
           │ grounded + cited                          │ Capture loop │◀── expert
   ┌───────▼────────┐   OpenRouter (cloud, swappable)  │  annotations │   (UI/CLI)
   │   Generation    │ ─────────────────────────────▶  └──────────────┘
   └────────────────┘
```

| Runs **locally** | Runs in the **cloud** |
|---|---|
| Qdrant, bge-m3 embeddings, optional reranker, all app code, the UI | Only the final generation call → OpenRouter (swappable to local Ollama) |

---

## 1. Prerequisites

- **Python 3.12** and **[uv](https://docs.astral.sh/uv/)** (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Docker** (for local Qdrant)
- An **[OpenRouter](https://openrouter.ai/) API key** (only for cloud generation; ingestion/indexing/retrieval need no key)
- ~16 GB RAM is comfortable for bge-m3 on CPU; a CUDA GPU or Apple-silicon (MPS) makes embedding much faster (auto-detected)
- First index run downloads **bge-m3 (~2.3 GB)** from Hugging Face

---

## 2. Setup

```bash
git clone https://github.com/Esoterics611/maayan.git
cd maayan

# Dependencies. Core installs fast; ML + UI are extras.
uv sync                          # core (pydantic, typer, httpx, qdrant-client, openai) + dev tools
uv sync --extra ml --extra ui    # adds torch + FlagEmbedding (embeddings) and FastAPI (UI)

# Configuration
cp .env.example .env             # then edit .env and set OPENROUTER_API_KEY=sk-or-...

# Start local Qdrant (Docker)
make up                          # docker compose up -d   (Qdrant on :6333)
```

`.env` keys you’ll likely set (see `.env.example` for all):

| Key | Default | Meaning |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Your OpenRouter key (cloud generation only). **Never commit `.env`.** |
| `OPENROUTER_MODEL` | `qwen/qwen-2.5-72b-instruct` | Open model for generation; test a few for Hebrew |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint (`:memory:` or a path also work, no Docker) |
| `EMBED_MODEL` | `BAAI/bge-m3` | Local embedding model |
| `SCORE_THRESHOLD` | `0.45` | Default-deny gate: min relevance to answer (tune per corpus) |
| `RERANK_ENABLED` | `false` | Enable the local cross-encoder reranker |
| `EXPERT_BOOST` | `1.0` | Multiplier for expert-sourced chunks (>1 prefers human-vetted) |

---

## 3. Run it (end to end)

```bash
# 1. Ingest the corpus from Sefaria (Likutei Amarim by default) → SQLite
make ingest                         # = maayan ingest --all
#   or a quick sample:  uv run maayan ingest --book "Tanya, Part I; Likkutei Amarim" --limit 2

# 2. Embed + index into Qdrant (downloads bge-m3 on first run)
make index                          # incremental;  add --rebuild to re-embed everything

# 3. Retrieve (hybrid dense+sparse, no model/key needed)
uv run maayan search "מהי נפש הבהמית" --k 5

# 4. Ask — grounded answer with citations (needs OPENROUTER_API_KEY)
uv run maayan ask "מה ההבדל בין צדיק לבינוני?"
#   → prints the answer, a Sources list (cited ones marked *), and a Session id

# 5. Capture expert knowledge against that session — it gets indexed and
#    becomes retrievable alongside the printed text (the loop):
uv run maayan annotate --session <SESSION_ID> --author "R. Ginsburgh" \
    --kind connection \
    --body "ההבדל בשורש הנפש: אצל הבינוני נפש הבהמית עדיין תקיפה, והעבודה היא אתהפכא" \
    --refs "Tanya, Part I; Likkutei Amarim 1:13, Tanya, Part I; Likkutei Amarim 9:6" \
    --move "kelipah->avodah"

# 6. Re-search a related query → the expert connection now surfaces
uv run maayan search "אתהפכא חשוכא לנהורא נפש הבהמית"
```

### The web UI

```bash
make up      # Qdrant
make ui      # → http://127.0.0.1:8000
```

Ask in the browser, see cited sources, tick the sources you want to link, pick a
kind (correction / connection / addition / objection), write a note, and save —
the annotation lands in **SQLite + Qdrant** and surfaces in future retrieval.

---

## 4. CLI reference

| Command | What it does |
|---|---|
| `maayan ingest --all` / `--book "<ref>"` `[--limit N]` `[--sample K]` | Pull + normalize + chunk from Sefaria into SQLite |
| `maayan index` `[--rebuild]` | Embed (bge-m3) + upsert into Qdrant (hybrid schema) |
| `maayan search "<q>"` `[--k N] [--book ..] [--source sefaria\|expert]` | Hybrid retrieval (RRF), prints refs + scores |
| `maayan ask "<q>"` `[--k N] [--book ..]` | Grounded, cited answer (or a refusal); records a session |
| `maayan annotate --session <id> --body "..."` `[--kind --author --refs --move]` | Add expert knowledge; indexes it |
| `maayan session <id>` | Show a session and its annotations |
| `maayan ui` | Run the local FastAPI chat + capture UI |
| `maayan version` | Print version |

`make help` lists the Make targets (`up/down/logs`, `test/typecheck/lint/fmt`,
`ingest/index/search/ask/ui`).

---

## 5. How it works (design)

- **Corpus** (`maayan/corpus/`): async Sefaria v3 client (rate-limited via an
  injected clock), Hebrew normalizer (strips markup/footnotes, **keeps nikkud**),
  one-segment-per-chunk (pasuk/os/se'if), idempotent SQLite store.
- **Embedding** (`maayan/embed/`): `bge-m3` gives **dense + sparse** in one pass;
  a dependency-free `HashingEmbedder` backs tests/no-GPU demos.
- **Index** (`maayan/index/`): Qdrant collection with a named dense (cosine) +
  sparse vector; idempotent upsert keyed by a stable chunk id.
- **Retrieve** (`maayan/retrieve/`): RRF fusion over dense+sparse, metadata
  filters, optional cross-encoder rerank, config-driven expert boost.
- **Generate** (`maayan/generate/`): a `GenerationBackend` protocol
  (OpenRouter now, Ollama next) and a RAG service whose **default-deny is enforced
  in code** — it refuses, without calling the model, when retrieval relevance is
  below the threshold; otherwise the model is told to answer only from numbered
  sources and cite each claim.
- **Capture** (`maayan/capture/`): sessions + annotations → expert chunks indexed
  into the **same** collection. This is the differentiator.
- **UI** (`maayan/ui/`): thin FastAPI layer over the RAG + capture services.

House rules (enforced): typed + `mypy --strict`, dependency injection everywhere,
no `time.sleep` in logic (injected `Clock`), config-driven, no secrets in code,
default-deny generation, tests mock network + models. See **[CLAUDE.md](CLAUDE.md)**
and the original plan + prompts in **[docs/BUILD_PLAN.md](docs/BUILD_PLAN.md)**.

---

## 6. Development

```bash
make test        # pytest (network + models mocked; in-memory Qdrant)
make typecheck   # mypy --strict
make lint        # ruff
```

CI (GitHub Actions) runs lint + typecheck + tests on every push/PR.

---

## 7. Troubleshooting

- **Docker socket permission denied** — add your user to the docker group, or for
  a quick local fix: `sudo chmod 666 /var/run/docker.sock`. On WSL with snap
  Docker: `sudo snap start docker`.
- **No GPU / slow embedding** — bge-m3 runs on CPU automatically (set
  `EMBED_DEVICE=cpu` to force). It’s slower but works.
- **`ask` errors with a 401 / missing key** — set `OPENROUTER_API_KEY` in `.env`.
  Retrieval (`search`) and the refusal path need no key.
- **No Docker at all** — set `QDRANT_URL=:memory:` (ephemeral) or a local path
  (persistent) to run Qdrant embedded in-process.
- **Everything refuses / nothing refuses** — tune `SCORE_THRESHOLD`; bge-m3
  cosine clusters in a narrow band. Enabling the reranker sharpens the gate.

---

## 8. Status

- [x] **Prompt 0** — Bootstrap, house rules, config, Docker, CI
- [x] **Prompt 1** — Sefaria ingestion (Likutei Amarim / Tanya focus)
- [x] **Prompt 2** — Embedding (bge-m3, dense+sparse) + Qdrant indexing
- [x] **Prompt 3** — Hybrid retrieval (RRF) + optional rerank + filters
- [x] **Prompt 4** — RAG via OpenRouter (grounded, cited, default-deny in code)
- [x] **Prompt 5** — Expert capture loop (annotations → indexed expert chunks)
- [x] **Prompt 6** — Local chat + capture UI (FastAPI)
- [ ] Prompt 7 — Eval harness (retrieval metrics + variant comparison)
- [ ] Prompt 8 — Local generation via Ollama

---

## License / attribution

Sefaria texts are **CC-BY-NC**. This project is for personal, non-commercial Torah
study; attribute [Sefaria](https://www.sefaria.org). Revisit licensing before any
commercial use.
