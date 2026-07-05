# Next session — Phase 7 complete

## Where things stand (2026-07-05)

**Phase 7 (docs/BUILD_PLAN_PHASE7.md, prompts 33–42) is COMPLETE.** All ten prompts are
implemented, green (460 tests, mypy strict clean, ruff clean), and merged to local
`main` with `--no-ff` merge commits. `origin/main` had advanced to include Prompt 39, so
the old "origin is stale" caveat no longer applies — branch off `main`.

The three prompts finished this session (each on its own branch off `main`, merged):

- **Prompt 40 — study programs** (`maayan/agent/program*.py`): `StudyProgramRunner`
  sweeps a sefer unit by unit (reusing the populate drip for pacing/backoff/resume);
  `ProgramDrafter` proposes typed edges whose object must be a co-retrieved source (no
  invented mekoros), each faithfulness-checked, landing as `status="proposed"`
  `derived_bootstrap` relations — nothing auto-approved. CLI: `study run|status|report`.
- **Prompt 41 — chazarah** (`maayan/consolidate/`): deterministic clustering (union-find
  over approved edges) → `SugyaDrafter` (sources → connections → open questions, cites
  only the cluster's refs) → `SugyaService` gate; approving version N+1 supersedes N,
  retracting its exact chunks through the **audited retract flow** (`sugya` added to
  `RETRACTABLE_SOURCES`). `ChazarahScheduler` queues `re_review` inquiries
  (stale-bootstrap / low-confidence / never-retrieved) with Anki-style intervals.
  `AskLog` gained a `cited_refs` column (migration-safe) for the never-retrieved join.
  CLI: `sugya draft|approve|reject|list`, `chazarah`.
- **Prompt 42 — structural depth**: parent-context answering
  (`SearchResult.parent_context` + `SectionWindowProvider`; `RAGService` attaches a hit's
  section window at generation time — **the citation stays the exact hit**, asserted;
  default `PARENT_CONTEXT_CHARS=0` so the eval baseline is unchanged). Gated one-level
  section summaries (`maayan/summarize/`, `source="summary"`, proposed→approved gate like
  develop, retractable, `summary_boost` wired in the same place as the other source
  boosts). CLI: `summarize`, `summaries`, `summary-approve|-reject`.

**Nothing is pushed to origin** — the merges are local; the Rav reviews and pushes.

## What's left (not code — verification + the top-model program)

1. **Live "Show" runs.** Each of 40/41/42 has a `Show:` step in BUILD_PLAN_PHASE7.md to
   run against the real DB (needs local Qdrant + bge-m3). These are CLI-first features;
   their scholar-facing surfaces are automatic (proposed edges via graph/inquiry; sugya
   and summary chunks are retrievable in Library/reader).
2. **UI_EXECUTION_PLAN §2.3 browser review pass** — open every surface, check the five
   UI_SPEC rules, run the §3 e2e protocol top to bottom.
3. **The top-model program** (BUILD_PLAN_PHASE7 §7): ontology review with the Rav → the
   Great Sweep (Prompt 40 at scale, measuring elasticity) → the adversarial bikores →
   the synthesis exam / the paper.
