# Next session — resume Phase 7

## Where things stand (2026-07-03)

- **Branch `prompt39-chavrusa-agent` @ `972a4d6`** — committed, green (437+ tests, mypy/ruff clean), **not merged**.
  - Prompt 39 (chavrusa agent) complete: `maayan/agent/`, `ask --agent [--show-trace]`, `GET /api/traces/{id}`.
  - UI wiring (the gap that had orphaned the agent): a **חברותא** toggle in the composer runs the study loop and shows a **כיצד נלמד? ▸** trace stepper.
  - **Retraction ledger** surfaced (stats count → מה נמחק audit overlay).
  - **docs/UI_EXECUTION_PLAN_PHASE7.md** — full CLI/route → UI surface audit + a 20-step browser-only e2e protocol + what stays CLI and why.
- **Not done:** Prompts **40** (study programs), **41** (chazarah/sugya pages), **42** (parent context + gated summaries).
- **Base caveat:** the 33–39 code exists **only locally**. `origin/main` is stale at `3288577` (33–38 were merged locally, never pushed). Any worktree/branch must start from the local `prompt39-chavrusa-agent` tip, **not** `origin/main`.

## What NOT to repeat

Parallelizing 40/41/42 with `isolation:worktree` subagents **failed**: the worktree base resolved to stale `origin/main` (missing `maayan/graph`, `maayan/agent`, `maayan/inquiry`), so the agents couldn't build. And 40/41/42 all edit `config.py` + `cli.py` + `ui/app.py` + `index.html`, so parallel branches conflict three ways. **Do them sequentially** on branches off `prompt39-chavrusa-agent`, reusing the existing `.venv`.

## Paste this to resume

> Continue Phase 7 of maayan. Branch off the current `prompt39-chavrusa-agent` tip (it has prompts 33–39; do **not** branch from `origin/main`, which is stale). Implement the remaining prompts **one at a time, sequentially** (they all touch `config.py`/`cli.py`/`ui/app.py`/`index.html`, so don't parallelize): **Prompt 40 → 41 → 42**, each verbatim from `docs/BUILD_PLAN_PHASE7.md`, following `CLAUDE.md` and the UI surfaces in `docs/UI_SPEC_PHASE7.md` §6. For each: new branch `promptNN-<slug>`, DoD green (`make test`, `make typecheck`, `make lint`), commit. Prompt 40 depends on `maayan/agent/`; 41 on graph(33)+inquiry(37); 42 is standalone. Keep the trust core fixed (default-deny never weakened, nothing model-drafted auto-approved, printed text immutable, retraction via the existing audited service). When all three are green, run each prompt's live "Show" step against the local DB and report.
