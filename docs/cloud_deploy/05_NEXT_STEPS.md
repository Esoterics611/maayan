# Near-term backlog — what the system needs now

> Distilled from the "deliberately NOT in this phase" lists of
> [BUILD_PLAN_PHASE4.md](../BUILD_PLAN_PHASE4.md) and
> [BUILD_PLAN_PHASE5.md](../BUILD_PLAN_PHASE5.md), plus what going public surfaces. This is
> the backlog to pull from **while you work through the curriculum and use the system**.
> Ordered by leverage. Each item: *why now*, *rough size*, *where it lives*.

## P0 — directly enables/secures the public deploy
1. **User management / auth** — *being built now*; see
   [02_USER_MANAGEMENT.md](02_USER_MANAGEMENT.md). Blocks a safe public URL. **L**.
   `maayan/users/`, `maayan/ui/app.py`.
2. **OpenRouter spend guardrail** — a configurable **daily generation cap** that reuses the
   existing default-deny refusal path, so a public URL can't run up a bill. *Why now:* the
   moment it's public, spend is unbounded. **S–M**, config-driven. `maayan/generate/rag.py`,
   `config.py`. (Full version in [04 §D2](04_HOSTING_MIGRATION.md).)
3. **Backup & restore command** — `maayan backup` / `maayan restore` for the SQLite file
   (Qdrant is re-derivable via `index --rebuild`). *Why now:* once experts contribute, the DB
   is irreplaceable, and "it's one file" makes this cheap. **S**. New `maayan/backup/` or a
   CLI command. (Phase-4 deferred it as "copy the file" — true locally, but a real command
   makes off-VM backups trivial.)

## P1 — quality you'll want as you actually use it
4. **Run the eval baseline on the full 3-book index and record it.** *Why now:* Phase 3's
   cross-text claim should be a number before you tune thresholds from curriculum experience.
   **S** (run `make eval` + `maayan eval --crosstext`, record in `eval/` + RUNBOOK). Pure ops.
5. **Server-side `author` from session** — when `auth_enabled`, stop trusting the
   client-sent author; stamp it from the logged-in user. *Why now:* provenance integrity once
   multiple people contribute. **S**. `maayan/ui/app.py` (the author-bearing routes).
6. **Per-user rate limiting** on `/ask` + `/compose` (FakeClock-testable). *Why now:* a shared
   public URL needs fairness + a second layer under the spend cap. **M**. `maayan/ui/app.py`.

## P2 — corpus & capability growth (real leverage, but data/ops, not blockers)
7. **Corpus expansion** beyond the three texts — it's **config + data**; the Sefaria and
   Chabad adapters already exist. *Why now:* more corpus = more the system can ground.
   **S per book** (edit `BOOKS` in `config.py`, re-ingest/index). No new code.
8. **Essay / digest registers** for Composition — same engine, new `content_type` values
   (Phase-5 left `shiur_outline` first, others as registers). **M**. `maayan/compose/`.
9. **Promote-connection UX polish** — make turning a composition's `grounded_in` into an
   expert/derived chunk a one-click, obvious flow in the UI. **S–M**. `maayan/ui/` + compose.

## P3 — later / explicitly deferred
10. **Fine-tuning / a trained model** — only meaningful after a large volume of approved
    contributions; changes register, not correctness. RAG + citations stays the backbone.
    Out of scope until the corpus + contributions are large. (See BUILD_PLAN §5.)

---

### How to use this list
- The deploy needs **P0 #1–#2** before the URL is shared widely; **#3** soon after.
- **P1 #4** is a quick, high-value thing to do *with* your curriculum work — it turns your
  hands-on experience into recorded eval numbers you can tune against.
- Everything in **P2** is pull-when-you-want; none blocks the deploy.
- Keep this file honest: when an item ships, move it out and note where it landed.
