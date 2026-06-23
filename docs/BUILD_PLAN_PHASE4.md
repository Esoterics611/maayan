# maayan — Build Plan, Phase 4: Steward-ready — correct, measure, see the corpus

> Companion to [docs/BUILD_PLAN.md](BUILD_PLAN.md) (Prompts 0–8) and
> [docs/BUILD_PLAN_PHASE2.md](BUILD_PLAN_PHASE2.md) (Prompts 9–16). Phase 3
> (companion texts + cross-text connections + Ollama backup) shipped without a
> numbered plan; this phase continues the sequence as **Prompts 17–19** and closes
> Phase 3 out formally.
>
> **Every prompt must follow [CLAUDE.md](../CLAUDE.md)** — typed + `mypy --strict`,
> dependency injection, config-driven, no secrets, default-deny, tests mock network
> + models, ephemeral/in-memory Qdrant for index/retrieve tests. Run them one at a
> time; let `make test`/`typecheck`/`lint` pass before moving on.

---

## 0. Why this phase exists (and why it's small)

The build is essentially complete. Prompts 0–16 ship the whole loop — ask →
grounded/cited answer (or enforced refusal) → capture (correct / connect / **seed**)
→ **develop** under a directive → **approve** → indexed as `derived` → term lexicon
that protects Holy Names from expansion — and Phase 3 added the three-book corpus
(Tanya, Torah Or, Likutei Torah) with cross-text connections.

So this is **not** another feature phase. The project's own guidance is unanimous
(BUILD_PLAN §5; OVERVIEW "what support enables"): from here the leverage is *corpus
+ scholars + measured quality*, not more code. Phase 4 is the short, disciplined set
of things that stand between "a working system" and "an instrument a scholar can put
real hours into and trust." Nothing speculative — each item closes a verified gap.

### The gaps, named precisely

1. **There is no eraser.** You can *add* knowledge three ways (annotate, develop →
   approve, add-term), but a grep of the codebase finds **no delete / retract /
   supersede / correct** anywhere. Once a chunk is indexed it is permanent. A scholar
   *will* index a wrong connection, a typo'd term, or approve a development they later
   reconsider — and today that error lives forever and keeps surfacing in retrieval.
   For a system whose entire value is *accumulated, trusted* expert knowledge, an
   eraser is the first necessary thing. **Prompt 17.**

2. **Phase 3's headline is unmeasured.** The shipped gold set is **Tanya-only**. The
   whole claim of Phase 3 is *cross-text co-retrieval* — an answer that cites Tanya +
   Torah Or + Likutei Torah together. There is currently no number proving it works.
   House rule is "numbers, not vibes." **Prompt 18.**

3. **No window into the asset.** There is no `maayan stats`. A steward can't see
   chunks-by-source, contributions-by-author, developments awaiting approval, or what
   has been retracted — which is exactly the information needed to *decide what to
   retract* and to watch the corpus grow. Small, but it's the reviewer's dashboard.
   **Prompt 19.**

## 1. Decisions already made (build to these)

- **Retraction is provenanced, not a silent delete.** Removing knowledge is itself an
  attributed, timestamped audit record (who retracted, when, why). The chunk leaves
  retrieval, but the *fact that it was retracted* is preserved. This mirrors the
  house value that printed text is immutable and provenance travels with everything.
- **Only the layered knowledge is retractable.** `sefaria` and `chabad` are printed
  text — **never** retractable. Retraction applies only to `expert` / `derived` /
  `term` chunks. Attempting to retract printed text is a rejected operation, in code.
- **Retraction survives a rebuild.** A retracted chunk is removed from Qdrant *and*
  flagged in the corpus store so `index --rebuild` does **not** re-embed it — the same
  durability discipline that makes expert/derived/term chunks survive a rebuild today
  (they're persisted with `indexed=1`; retraction adds a `retracted=1` tombstone).
- **Correction = retract + re-add.** There is no in-place edit of an indexed chunk
  (ids are content-derived and idempotent). To "correct," you retract the wrong chunk
  (reason: superseded) and add the right one. Keep `retract` atomic; document the
  two-step correction flow rather than building a bespoke edit path.
- **Measurement reuses the existing harness.** The cross-text eval is a new gold set +
  one new metric inside `maayan/eval/`, surfaced through the same `maayan eval` CLI —
  not a parallel system.

## 2. New/changed data model

Define as pydantic models (CLAUDE.md rule 1). Add columns via idempotent migrations
that don't break existing DBs (follow the `indexed` column pattern in
`maayan/corpus/store.py`).

- **`Retraction`**: `id, chunk_id, ref, source` (the retracted chunk's source),
  `author` (**required** — blank rejected, as in Prompt 9), `reason: str`,
  `timestamp` (from injected Clock). Persisted in SQLite (same DB file).
- **`ChunkStore`** gains a `retracted INTEGER NOT NULL DEFAULT 0` column + a
  `mark_retracted(ids)` write and a `retracted`-aware read so `--rebuild` skips
  tombstoned chunks. Existing rows default to `0` (not retracted).
- **Cross-text gold set** (`eval/crosstext_goldset.yaml`): a list of
  `{question, expected_refs}` where `expected_refs` deliberately span ≥2 books.

## 3. Invariants to re-check at every step (don't regress)

- Default-deny stays enforced in code for `ask`, follow-ups, and `develop`.
- Printed text (`sefaria`/`chabad`) is immutable and **not** retractable.
- Provenance travels with every artifact — including the *removal* of one.
- A retracted chunk is gone from retrieval *and* from a `--rebuild`.
- Typed + `mypy --strict`, DI, config-driven, secrets only via env, tests mock
  network/models, ephemeral Qdrant for index/retrieve tests.

---

# The prompts

Paste each block as-is into a fresh Claude Code session at the repo root.

---

### Prompt 17 — Retract & correct (the eraser)

```
Add the ability to RETRACT a piece of layered knowledge. Follow CLAUDE.md. This is the
first necessary gap: today knowledge can only be added (annotate, develop→approve,
add-term) — there is no delete/retract/correct anywhere, so a wrong connection, a typo'd
term, or a regretted approval is permanent and keeps surfacing in retrieval.

Design (build to these — they're decided in docs/BUILD_PLAN_PHASE4.md):
- A retraction is PROVENANCED, not a silent delete: an attributed, timestamped audit
  record (who, when, why). The chunk leaves retrieval; the fact that it was retracted is
  preserved.
- Only `expert` / `derived` / `term` chunks are retractable. `sefaria` and `chabad` are
  printed text and are NEVER retractable — attempting it is rejected IN CODE with a clear
  error, not just discouraged.
- Retraction must survive a rebuild: remove the point from Qdrant AND flag the corpus
  store so `index --rebuild` does not re-embed it.
- Correction is retract + re-add (ids are content-derived/idempotent; no in-place edit).
  Don't build a bespoke edit path — document the two-step flow.

Requirements:
- New pydantic `Retraction` model: id, chunk_id, ref, source, author (REQUIRED — blank
  rejected, as in Prompt 9), reason: str, timestamp (from injected Clock). Persist in a
  RetractionStore in the same SQLite DB (idempotent migration).
- maayan/corpus/store.py (ChunkStore): add a `retracted INTEGER NOT NULL DEFAULT 0`
  column via idempotent migration; add `mark_retracted(ids)`; make the pending/rebuild
  reads skip retracted chunks so they are never re-embedded.
- A RetractionService (all collaborators injected: chunk store, retraction store, Qdrant
  index, clock, settings) with retract(chunk_id_or_ref, *, author, reason) that:
  (a) resolves the chunk, (b) rejects if its source is sefaria/chabad, (c) deletes the
  point from Qdrant, (d) marks the corpus chunk retracted, (e) records the Retraction.
  For a `derived` chunk also flip its Development to status="retracted"; for a `term`
  chunk mark the term retracted. List with list_retractions().
- CLI: `maayan retract <ref-or-chunk-id> --author "..." --reason "..."` and
  `maayan retractions` (list). Reject printed-text retraction with a clear message.
- UI: a small "Retract" affordance on expert/derived/term source cards and on
  development proposals (author REQUIRED + sticky as in Prompt 9; a reason box). Thin
  route wiring RetractionService — no logic in the handler.
- Tests (ephemeral Qdrant; mock embedder/network): retract removes the point and the
  chunk is no longer retrieved; a retracted chunk is skipped by `index --rebuild`;
  retracting a sefaria/chabad chunk is rejected; the Retraction round-trips with full
  provenance; blank author rejected; the UI route happy-path + the rejection path.

Demo: index an expert connection, retrieve it, retract it (named author + reason), show
it gone from search AND absent after `index --rebuild`; then show that retracting a Tanya
(sefaria) chunk is refused.
```

---

### Prompt 18 — Cross-text retrieval eval (measure Phase 3's headline)

```
Measure cross-text co-retrieval — the headline claim of Phase 3 that is currently
unmeasured. Follow CLAUDE.md. The shipped gold set is Tanya-only; nothing proves that a
question can actually pull Tanya + Torah Or + Likutei Torah together.

Requirements:
- A cross-text gold set (eval/crosstext_goldset.yaml): ~10 questions whose expected_refs
  deliberately span ≥2 of {Tanya, Torah Or, Likutei Torah}. Documented header explaining
  the intent; editable. Each entry {question, expected_refs}, same format as the existing
  gold set so it reuses the loader.
- A new PURE, unit-tested metric in maayan/eval/: book-diversity / cross-text coverage@k —
  for a question whose expected refs span B books, the fraction of those books represented
  in the top-k results (and a boolean "≥2 distinct books retrieved"). Keep it small and
  hand-checkable; derive a result's book from its ref/payload exactly as retrieval does.
- A harness entry run_crosstext_eval(...) + CLI `maayan eval --crosstext` that prints a
  table (per-question books-expected vs books-retrieved, plus aggregate). Reuse the
  injected Retriever; fully mockable; no network/models.
- A CI guard that the shipped crosstext_goldset.yaml is well-formed (mirror
  test_shipped_goldset_is_well_formed): every entry has a question and expected_refs that
  span ≥2 distinct books.
- Tests: the metric on tiny hand-checked inputs (single-book, all-books, partial);
  run_crosstext_eval aggregation with a fake retriever (no network/models).

Show the cross-text eval table on the seed gold set when done (with a mocked retriever in
tests; note in output that a real run needs the full three-book corpus indexed).
```

---

### Prompt 19 — Knowledge-base health: `maayan stats` (+ close Phase 3/4 docs)

```
Add a steward's-eye view of the Knowledge base and close out the docs. Follow CLAUDE.md.
A reviewer needs to see what's in the corpus to decide what to retract and to watch it
grow; there is no such view today.

Requirements:
- A StatsService (all stores injected) that aggregates, read-only, from the SQLite stores
  (+ optional Qdrant point count): chunks by source (sefaria/chabad/expert/derived/term)
  and by book; contributions by author; developments by status
  (proposed/approved/rejected/retracted); count of retractions; counts of threads and
  terms. Return a typed pydantic Stats model — no loose dicts across the boundary.
- CLI: `maayan stats` prints a compact table. Optionally a thin `GET /stats` route + a
  small UI panel reusing the same service (no logic in the handler).
- Tests: aggregation against a seeded temp SQLite (a couple of chunks per source, a few
  contributions/developments/retractions) asserting exact counts; the route happy-path
  with a mocked service.
- Docs (do these as part of this prompt):
  - README §8 Status: flip Phase 3 to COMPLETE; add a "Phase 4" section with Prompts
    17–19 and tick them as they land.
  - docs/RUNBOOK.md: add a §"Correcting a mistake" (retract flow), a stats line in §8
    Measure (`maayan eval --crosstext`), and a `maayan stats` example.
  - docs/TEACHING.md: a short "when you get it wrong" note — retraction is how the corpus
    self-corrects without ever editing printed text.

Show `maayan stats` output on a small seeded DB when done.
```

---

## 4. Suggested order & checkpoints

17 → 18 → 19. They are independent enough to reorder, but this order front-loads the
one with real user impact (the eraser), then the measurement, then the docs/visibility
that reference both.

- **After 17:** a scholar can safely make mistakes — wrong knowledge is retractable,
  provenanced, and stays gone across a rebuild. This is what makes sustained, trusting
  use possible. Worth a manual pass in the UI.
- **After 18:** Phase 3's cross-text claim is backed by a number, not a vibe. Run it
  against the real three-book index once and record the baseline.
- **After 19:** the steward can see the asset and the docs declare Phases 3–4 done.

## 5. What is deliberately NOT in this phase

To keep "only necessary things" honest, these were considered and **excluded** — they're
corpus/ops activities or speculative features, not blocking code gaps:

- **Corpus expansion** beyond the three texts — real leverage, but it's config + data
  (the Sefaria and chabad adapters already exist), not a build prompt.
- **Backup/export commands** — the entire knowledge layer is one SQLite file that
  `--rebuild` re-embeds; "copy the file" is the backup. Revisit only if multi-machine
  sync becomes a real need.
- **Fine-tuning / a trained model** — explicitly later (BUILD_PLAN §5); only meaningful
  after a large volume of approved contributions, and it changes register, not
  correctness. RAG + citations stays the backbone regardless.
- **Auth / multi-user roles** — the system is local-first and single-steward today.
  Provenance already carries the author name; real multi-user access control is a
  deployment concern for if/when it leaves one machine.
