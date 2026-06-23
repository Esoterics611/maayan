# Lesson 7.1 — Setup & dependencies

> Module 7, Lesson 1 · ~15 min read + a hands-on at the terminal.
> The one question this answers: **what do I actually install and start to run maayan, and why
> are the heavy pieces optional?**

You've understood the system; now you operate it. Module 7 is the operator's manual — setup,
knobs, backend choice, growing the corpus, the UI. We start at the foundation: dependencies and
the local services. The guiding design idea here is **the heavy stuff is opt-in**, so the
skeleton and the tests stay fast (you felt this in Module 5 — tests need none of it).

---

## Three dependency tiers (and why)

Open [pyproject.toml](../../pyproject.toml) and find `[project.optional-dependencies]`. maayan
splits its dependencies into a fast core plus two **extras**:

| Install | Adds | Needed for |
|---|---|---|
| `uv sync` | core: pydantic, typer, httpx, qdrant-client, openai | skeleton, CLI, **all unit tests** |
| `uv sync --extra ml` | `FlagEmbedding`, `torch` | real embeddings/rerank (bge-m3) — Module 1 on |
| `uv sync --extra ui` | `fastapi`, `uvicorn` | the web UI — Lesson 7.5 |

The reason for the split (stated in [CLAUDE.md](../../CLAUDE.md) "Dependencies"): `torch` +
`FlagEmbedding` are large and slow to install, and `fastapi` is only for the browser UI. Keeping
them as extras means a fresh checkout installs and *tests* in seconds — the unit tests mock the
models (Lesson 5.4), so they never need `ml` at all. You only pay for the heavy deps when you do
real retrieval. For day-to-day operation you'll want both extras:

```bash
uv sync --extra ml --extra ui
```

---

## The two local services you start

maayan is local-first (Lesson 0.2). Two things run on your machine:

1. **Qdrant** — the vector database (Lesson 2.1). Start/stop it with Docker:
   ```bash
   make up      # Qdrant on :6333
   make down    # stop it
   ```
   No Docker? Set `QDRANT_URL=:memory:` (ephemeral) or a local path (`QDRANT_URL=data/qdrant`)
   in `.env` — `build_qdrant_client` handles all three (Lesson 2.1). Or pass `--mock` for an
   offline, no-Docker run (Lesson 5.1).
2. **The embedding model** — `bge-m3`, downloaded on first `index` (~2.3 GB, one-time), then
   cached and run locally (Lesson 1.1).

The only thing *not* local is the generation call (Lesson 3.1) — and even that is swappable to
local Ollama (Lesson 7.3).

---

## Secrets: the `.env` file

The one credential you need (for cloud generation) is an OpenRouter key. It lives in `.env`,
never in code:

```bash
cp .env.example .env        # then edit: OPENROUTER_API_KEY=sk-or-...
```

Recall Lesson 5.3: every setting — including this key — is a `Settings` field, and the key is a
`SecretStr` read from env, never logged. `.env` overrides the defaults in `config.py`. (And
recall from Lesson 3.3: ingest, index, search, and *refusals* need **no** key — only a grounded
answer calls the cloud.)

> ### Under the hood — `uv` and reproducibility
> maayan uses `uv` (a fast Python package manager) with a lockfile, so `uv sync` reproduces the
> exact dependency set. `uv run <cmd>` runs inside that environment without you activating a
> venv — which is why every hands-on in this curriculum is `uv run maayan …`. The extras are
> *additive*: `uv sync --extra ml --extra ui` gives you core + both. There's no "did I activate
> the right environment?" failure mode.

[RUNBOOK §2](../RUNBOOK.md) is the authoritative, copy-pasteable version of all this — keep it
open while you operate.

---

## Hands-on

1. **Confirm your install.** From the repo root:

   ```bash
   uv run maayan version
   ```

   If that prints a version, your core install works. (It needs no models or Docker.)

2. **Check the two services.** Run `make up`, then confirm Qdrant is reachable — the CLI's
   `require_qdrant` (Lesson 5.1) will tell you fast if it isn't:

   ```bash
   uv run maayan search "test" --k 1
   ```

   If Qdrant is down, you'll get the "✗ Qdrant is not reachable… `make up`… or `--mock`"
   guidance. That fail-fast message *is* the operator UX.

3. **Read the source of truth.** Open [RUNBOOK §2](../RUNBOOK.md) and skim the setup block.
   Identify which step you'd skip if you only wanted to run unit tests (answer: the `ml`/`ui`
   extras, the key, and Qdrant — `make test` needs none of them).

4. **Locate the extras boundary.** In `pyproject.toml`, confirm `torch` is under `ml`, not core.
   In one sentence: why does that choice make the *test suite* fast?

---

## You should now be able to say…

- The three dependency tiers (core / `ml` / `ui`) and **why the heavy ones are optional** (fast
  skeleton + tests).
- The two local services — **Qdrant** (`make up`/`down`, or `:memory:`/path/`--mock`) and the
  **bge-m3** model (one-time download).
- That the OpenRouter key lives in **`.env`** as a secret, and which operations need no key at
  all.
- That [RUNBOOK §2](../RUNBOOK.md) is the authoritative setup reference.

Next: **[7.2 — The knobs that matter](07-2-the-knobs.md)** — now that it runs, the handful of
config knobs that actually change behavior, what each does, and when to reach for it.
