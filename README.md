# maayan · מעיין — Esoteric Torah RAG

**maayan** (מעיין, "wellspring") is a **local-first** retrieval system for chassidus /
Kabbalah (p'nimiyus haTorah). It ingests Torah sources, retrieves the relevant
pieces for a question, and asks an open model to answer **only from those sources,
with citations** — refusing when nothing supports an answer. An **expert capture
loop** records how a scholar corrects and connects sources and feeds that back in
as new retrievable knowledge. **That loop is the point.**

In **Phase 2** ([plan](docs/BUILD_PLAN_PHASE2.md)) that loop grows teeth. Instead of
a note that just sits there, an expert plants a **seed** — knowledge (often from
*outside* the indexed corpus) plus a **directive** ("now find where this is hinted in
Tanya"). The model **develops** the seed *grounded in retrieved sources and cited*,
and once the expert **approves**, it becomes new **attributed corpus** future
questions retrieve. Lines of inquiry live in persistent **topic threads**, and a
curated **term lexicon** teaches the system that tokens like ע״ב (the Name of 72) are
*terms / Holy Names*, not acronyms to expand.

Corpus: **Tanya (Part I)** + its companions **Torah Or** (Sefaria) and **Likutei
Torah** (from chabadlibrary.org — it isn't on Sefaria). Asking retrieves across all
three, so the Assistant answers — and you teach it connections — *between* the texts.

> **Just want to run it?** **[docs/RUNBOOK.md](docs/RUNBOOK.md)** walks you from
> `make up` → ingest all three texts → index → ask across them → **teach a connection
> and confirm it learned**.

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
| `DERIVED_BOOST` | `1.0` | Multiplier for derived chunks (approved model developments of a seed) |

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
#    becomes retrievable alongside the printed text (the loop). Author is REQUIRED;
#    refs contain commas, so pass each with a repeatable --ref (never a comma split):
uv run maayan annotate --session <SESSION_ID> --author "R. Ginsburgh" \
    --kind connection \
    --body "ההבדל בשורש הנפש: אצל הבינוני נפש הבהמית עדיין תקיפה, והעבודה היא אתהפכא" \
    --ref "Tanya, Part I; Likkutei Amarim 1:13" \
    --ref "Tanya, Part I; Likkutei Amarim 9:6" \
    --move "kelipah->avodah"

#    …or plant a SEED — knowledge plus a directive the model will later develop
#    (Prompt 12). The directive is kept OUT of the embedded text so it can't pollute
#    retrieval; it rides in metadata:
uv run maayan annotate --session <SESSION_ID> --author "R. Ginsburgh" \
    --kind connection --opens-aspect \
    --body 'אהבה בתענוגים היא גילוי שם ע"ב לאחר יחוד מ"ה וב"ן' \
    --directive "מצא היכן זה נרמז בתניא"

# 6. Re-search a related query → the expert connection now surfaces
uv run maayan search "אתהפכא חשוכא לנהורא נפש הבהמית"

# 7. Measure retrieval quality against the gold set (hit@k / recall@k / MRR + gate)
make eval                           # single report
make eval ARGS='--compare'          # hybrid vs dense-only vs top-k, side by side
```

### Phase 2: the develop loop + term lexicon (CLI, end to end)

This is the heart of the project — an expert plants a **seed**, the model **develops**
it grounded in the corpus, and on **approval** it becomes retrievable corpus. Threads
hold the line of inquiry; the **lexicon** teaches the system its Holy Names.

```bash
# A. Start a topic thread and ask within it (prior turns become NON-citable context).
uv run maayan ask "מהי אהבה בתענוגים?" --topic "ahava b'ta'anugim"
#   → prints the answer + a Session id + a Thread id. Continue the thread:
uv run maayan ask "ואיך זה קשור לשם ע\"ב?" --thread <THREAD_ID>

# B. Plant a SEED on that session — knowledge PLUS a directive to develop later.
#    --opens-aspect marks it a seed; --directive is kept OUT of the embedded text.
uv run maayan annotate --session <SESSION_ID> --author "R. Ginsburgh" \
    --kind connection --opens-aspect \
    --body 'אהבה בתענוגים היא גילוי שם ע"ב לאחר יחוד מ"ה וב"ן' \
    --directive "מצא היכן זה נרמז בתניא"
#   → prints a contribution id (the seed). It is indexed as a source="expert" chunk.

# C. DEVELOP the seed — the model grounds it in retrieved Tanya sources and cites them,
#    OR refuses honestly if the corpus doesn't support it (default-deny, no model call).
uv run maayan develop --seed <CONTRIBUTION_ID>
#   → prints the proposed development, its grounded-in refs + citations, a Development id.

# D. APPROVE it → indexed as a source="derived" chunk with full provenance
#    (seed author, developing model, grounded_in refs). Or `reject` to index nothing.
uv run maayan approve <DEVELOPMENT_ID>           # (or: uv run maayan reject <DEVELOPMENT_ID>)
uv run maayan search "אהבה בתענוגים" --source derived   # the derived knowledge now surfaces

# E. Inspect threads + sessions any time.
uv run maayan threads                  # list topic threads
uv run maayan thread <THREAD_ID>       # show its ordered turns (ask / seed / development)
uv run maayan session <SESSION_ID>     # show a session + its contributions

# F. TERM LEXICON — define a Holy Name / technical term as an entity so it is never
#    expanded as an abbreviation, and its definition surfaces in retrieval.
uv run maayan add-term \
    --canonical 'ע"ב (Name of 72 / Ab)' \
    --definition 'the Ab expansion of Havayah, gematria 72; sibling to ס"ג/מ"ה/ב"ן' \
    --type expansion --gematria 72 --sacred \
    --surface 'ע"ב' --surface 'עב' \
    --related 'ס"ג' --related 'מ"ה' --related 'ב"ן' \
    --author "R. Ginsburgh"
uv run maayan terms                    # list curated terms
uv run maayan term <TERM_ID>           # show one term
uv run maayan search 'יחוד מ"ה וב"ן' --source term     # the term definition surfaces

# G. Measure the develop step (no DB writes; supported seeds should develop, unsupported refuse).
uv run maayan eval --develop
```

### The web UI

```bash
make up      # Qdrant
make ui      # → http://127.0.0.1:8000
```

The UI is organized around **topic threads**. Start (or reopen) a topic from the
sidebar, then within that thread you can:

- **Ask** — a grounded, cited answer; follow-ups use the thread as context but still
  refuse when unsupported. Sources are badged **sefaria / expert / derived / term**.
- **Seed a new aspect** — author (required, remembered via localStorage) + the seed
  knowledge + a *directive* (kept out of the embedded text).
- **Develop this** on a seed — the model proposes a grounded, cited elaboration.
- **Approve / Reject** the proposal — approving indexes it as a `derived` chunk that
  future questions retrieve; rejecting indexes nothing. Printed text is never edited.
- **Define a term** (the *Term ▾* composer) — register a Holy Name / technical term as
  an entity (canonical, type, definition, surface forms, gematria). Select text in a
  source first to pre-fill its surface form. Defined terms show in the sidebar lexicon
  and surface in retrieval, badged **term**.

---

## 4. CLI reference

| Command | What it does |
|---|---|
| `maayan ingest --all` / `--book "<ref>"` `[--limit N]` `[--sample K]` | Pull + normalize + chunk from Sefaria (Tanya + Torah Or) into SQLite |
| `maayan ingest-chabad --all` / `--book "<name>"` `[--limit N]` | Pull a non-Sefaria text (Likutei Torah) from chabadlibrary.org into SQLite |
| `maayan index` `[--rebuild]` | Embed (bge-m3) + upsert into Qdrant (hybrid schema) |
| `maayan search "<q>"` `[--k N] [--book ..] [--source sefaria\|chabad\|expert\|derived\|term]` | Hybrid retrieval (RRF), prints refs + scores + provenance |
| `maayan ask "<q>"` `[--k N] [--book ..] [--thread <id> \| --topic "<title>"]` | Grounded, cited answer (or a refusal); records a session. `--topic` starts a thread, `--thread` continues one — using prior turns as **non-citable** context |
| `maayan annotate --session <id> --author "<name>" --body "..."` `[--kind --ref (repeatable) --refs "a \| b" --move --opens-aspect --directive "..."]` | Add an expert contribution or **seed**; indexes it. `--author` required; refs keep their commas (repeatable `--ref`, or `--refs` split on ` \| `) |
| `maayan session <id>` | Show a session and its contributions (seeds flagged, directives shown) |
| `maayan threads` | List persisted topic threads (most recent first) |
| `maayan thread <id>` | Show a topic thread with its ordered turns |
| `maayan develop --seed <id>` `[--thread <id>]` | Develop a seed under its directive — grounded + cited (a **proposal**, not corpus; refuses honestly if unsupported) |
| `maayan approve <development_id>` | Approve a proposal → index it as a retrievable `derived` corpus chunk |
| `maayan reject <development_id>` | Reject a proposal; nothing is indexed |
| `maayan add-term --canonical "<form>" --definition "..." --author "<name>"` `[--type .. --surface (repeatable) --related (repeatable) --source-ref (repeatable) --gematria N --sacred]` | Define a **term / Holy Name** as an entity; indexes it as a `term` chunk and protects its surface forms from expansion |
| `maayan terms` | List curated lexicon terms |
| `maayan term <id>` | Show one lexicon term (definition, surface forms, related, sources) |
| `maayan ui` | Run the local FastAPI chat + capture UI |
| `maayan eval` `[--goldset path] [--compare] [--k N]` | Score **retrieval** vs a gold set (hit@k/recall@k/MRR + gate rates); `--compare` tables variants |
| `maayan eval --develop` `[--goldset path]` | Score the **develop step**: develop rate, refusal rate, grounding (no DB writes) |
| `maayan version` | Print version |

`make help` lists the Make targets (`up/down/logs`, `test/typecheck/lint/fmt`,
`ingest/index/search/ask/ui/eval`).

---

## 5. How it works (design)

- **Corpus** (`maayan/corpus/`): async Sefaria v3 client (rate-limited via an
  injected clock) for Tanya + Torah Or, plus a `chabad.py` adapter that walks
  chabadlibrary.org's JSON API for **Likutei Torah** (not on Sefaria) — both feed the
  same Hebrew normalizer (strips markup/footnotes, **keeps nikkud**),
  one-segment-per-chunk (pasuk/os/se'if), idempotent SQLite store. See
  [docs/RUNBOOK.md](docs/RUNBOOK.md) for sources, licensing, and how it works.
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
- **Capture** (`maayan/capture/`): sessions + **contributions** → expert chunks
  indexed into the **same** collection. This is the differentiator. A contribution is
  either a *correction/connection* (attaches to a passage) or a **seed** that
  `opens_aspect` — knowledge plus a separate **directive**. Provenance (real author —
  *required* — kind, directive, linked refs) travels in metadata; a seed's directive
  is kept **out** of the embedded text so it never pollutes retrieval.
- **Threads** (`maayan/threads/`): persistent, reopenable **topic threads** — each a
  line of inquiry that accumulates ordered turns (`ask` / `seed` / `development` /
  `refinement`) in SQLite, every turn carrying provenance + a display snapshot.
- **Develop** (`maayan/develop/`): the model develops a seed under its directive,
  grounded in freshly-retrieved sources and cited — producing a **proposal** (not
  corpus). The same default-deny gate applies: it refuses, with no model call, when
  the corpus doesn't support the seed. On **approval** the proposal becomes a
  `source="derived"` chunk in the same collection — full provenance (seed, author,
  developing model, `grounded_in` refs) — while `reject` indexes nothing. Printed text
  stays immutable; derived knowledge layers on as a separate, badged chunk, and
  `DERIVED_BOOST` lets reviewed-and-approved knowledge be preferred in ranking.
- **Lexicon** (`maayan/lexicon/`): expert-defined **terms / Holy Names** (ע״ב, ס״ג,
  sefirot, partzufim, …) as `source="term"` chunks in the same collection, with full
  provenance. Surface-form matching folds gershayim/quote/nikkud variants, and those
  folded forms become a **protected-terms deny-list** that the abbreviation-expansion
  hook may never expand — so a registered Name is structurally safe from being mangled.
  `TERM_BOOST` lets curated definitions be preferred in ranking.
- **UI** (`maayan/ui/`): thin FastAPI layer over the RAG / capture / thread / develop
  services — a thread-centric loop (ask, seed, develop, approve/reject) with sources
  badged by provenance. Route handlers carry no logic.
- **Eval** (`maayan/eval/`): a YAML/JSON gold set (positive cases + `should_refuse`
  negatives) + pure metric functions (hit@k / recall@k / MRR, prefix-aware ref
  matching) + a harness that compares retrieval variants (hybrid vs dense-only,
  top-k, swappable embedding model) and reports default-deny gate rates — so
  model/chunking choices are justified with numbers, not vibes. A second gold set of
  **seeds** (`eval/develop_goldset.yaml`, supported / unsupported) scores the *develop*
  step (`maayan eval --develop`): **develop rate** (supported seeds developed),
  **refusal rate** (unsupported seeds honestly refused), and **grounding** (cited refs
  that were actually retrieved — catches fabricated citations).

House rules (enforced): typed + `mypy --strict`, dependency injection everywhere,
no `time.sleep` in logic (injected `Clock`), config-driven, no secrets in code,
default-deny generation, tests mock network + models. See **[CLAUDE.md](CLAUDE.md)**
and the original plan + prompts in **[docs/BUILD_PLAN.md](docs/BUILD_PLAN.md)**.

> **New here?** **[docs/TEACHING.md](docs/TEACHING.md)** is a guided walkthrough of
> the whole system — every engineering pattern it uses, the measured eval results,
> and **hands-on exercises to test your understanding.** Start there.

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
- [x] **Prompt 7** — Eval harness (retrieval metrics + variant comparison)
- [x] **Prompt 8** — Local generation via Ollama (offline *backup*; OpenRouter stays default)

### Phase 2 — Seeds → development → topic threads ([plan](docs/BUILD_PLAN_PHASE2.md))

- [x] **Prompt 9** — Contributions: seeds vs corrections, required provenance, `--refs` bug fix
- [x] **Prompt 10** — Topic threads, persisted server-side (SQLite)
- [x] **Prompt 11** — Context-aware, grounded follow-ups (thread context, never bypasses default-deny)
- [x] **Prompt 12** — The **Develop** step (expert-directed, grounded, refuses honestly → a proposal)
- [x] **Prompt 13** — Approval gate → `derived` corpus chunks (provenance + `derived_boost`)
- [x] **Prompt 14** — UI: topic threads, seed, develop, approve (thin routes over the services)
- [x] **Prompt 15** — Eval: measure development quality (grounding + honest refusal)
- [x] **Prompt 16** — Term lexicon: Holy Names & technical terms (don't expand them)

**Phase 2 is complete.** The seed → develop → approve loop runs end-to-end (CLI + UI),
is measured by the develop eval, and the term lexicon protects Holy Names from
expansion while surfacing their definitions in retrieval.

### Phase 3 — companion texts + cross-text connections (in progress)

- [x] Ollama backup backend (Prompt 8)
- [x] **Torah Or** ingested from Sefaria (24 parsha nodes)
- [x] **Likutei Torah** ingested from chabadlibrary.org (new `source="chabad"` adapter; not on Sefaria)
- [x] Cross-text connections: co-retrieval across all three texts + taught `expert` connections whose `linked_refs` span books (visible in `search`)
- [ ] Dedicated "Connect these sources" affordance in the web UI (CLI flow works today; see [RUNBOOK](docs/RUNBOOK.md) §6)

---

## License / attribution

Sefaria texts are **CC-BY-NC**. This project is for personal, non-commercial Torah
study; attribute [Sefaria](https://www.sefaria.org). Revisit licensing before any
commercial use.
