# maayan — Build Plan, Phase 2: Seeds → Development → Topic Threads

> Companion to [docs/BUILD_PLAN.md](BUILD_PLAN.md) (Prompts 0–8). These continue the
> sequence as **Prompts 9–15**. They are independent of Prompt 8 (Ollama).
> **Every prompt must follow [CLAUDE.md](../CLAUDE.md)** — typed + `mypy --strict`,
> dependency injection, config-driven, no secrets, default-deny, tests mock network
> + models. Run them one at a time; let `make test`/`typecheck`/`lint` pass before
> moving on.

---

## 0. Why this phase exists (the shift)

Today the expert loop saves **annotations**: an expert note becomes a passive,
retrievable `source="expert"` chunk. That's it. The note just *sits there*.

What we actually want (discovered while testing): the expert plants a **seed** —
often knowledge from *outside* the indexed corpus, plus a **directive** — and the
**model develops it** under that direction, growing a **new aspect** of the corpus.

### The real example that drove this

An expert seed saved during testing (annotation `c3d520c0`), translated:

> *Ahava b'ta'anugim is the revelation of the Name Ab (ע״ב) after the unification
> of Mah (מ״ה) and Ban (ב״ן), via ahavat olam — explained at length in **Likutei
> Torah / Torah Or, Vayechi**. **Now find where this is hinted at in Tanya.***

Two things are fused in one text field: **knowledge** (a framework from texts not in
the corpus) and a **directive** ("find the hint in Tanya"). The current system
stored both as inert text and did nothing with the directive. This phase makes the
directive *executable*: the model retrieves grounded Tanya sources, develops the
seed into a cited elaboration, and — once the expert approves — that becomes new,
attributed corpus that future questions retrieve.

## 1. Decisions already made (build to these)

- **Follow-ups are context-aware but still grounded.** The model sees prior turns to
  interpret a follow-up, but every answer is freshly retrieved, cited, and refuses
  if unsupported. Default-deny is never bypassed.
- **Topic threads persist server-side** (reopenable, listable), in SQLite.
- **Approval gate:** model-developed knowledge is a *proposal* until the expert
  approves it; only then is it indexed as corpus. Config-toggleable
  (`develop_auto_approve`, default `false`).
- **Printed text stays immutable.** Sefaria refs are canonical; expert seeds and
  model developments *layer on top* as separate chunks — we never edit the source.

## 2. Source taxonomy (provenance is the point)

`Chunk.source` gains a third value. Retrieval and the UI must keep these distinct:

| `source` | Meaning | Who/what produced it |
|---|---|---|
| `sefaria` | Printed text | Sefaria (immutable) |
| `expert` | A human seed/correction/connection | the reviewer (named) |
| `derived` | A model development of a seed, **approved** | model, grounded in refs, from an expert seed |

Every `expert`/`derived` chunk carries provenance in metadata: `author` (real name,
never the default), `seed_id`, `developed_by` (model id) for derived, `grounded_in`
(the refs the development cited), `thread_id`.

## 3. New/changed data model (the spine for this phase)

Define these as pydantic models (see CLAUDE.md rule 1). Keep existing `Annotation`
working; add fields with defaults for backward compatibility.

- **`Contribution`** (evolves `Annotation`): add `directive: str | None = None` (the
  "develop this" instruction, separate from `body` the knowledge) and
  `opens_aspect: bool = False` (marks a seed that leads a new aspect). `author`
  becomes **required** (no silent `"expert"`).
- **`Thread`** (a topic): `id, title, created_at, updated_at`.
- **`ThreadTurn`**: `id, thread_id, ordinal, turn_type` (`"ask" | "seed" |
  "development" | "refinement"`), `timestamp, author` (`"model"` or a person),
  and a reference to the underlying record (`session_id` / `contribution_id` /
  `development_id`) plus a text snapshot for display.
- **`Development`**: `id, thread_id, seed_id, timestamp, model, status`
  (`"proposed" | "approved" | "rejected"`), `text, cited_refs, grounded_in`.

## 4. Already done

- **UI source-card CSS bug** (English text squashed behind the checkbox) — fixed in
  `maayan/ui/static/index.html`. Phase 2 UI work (Prompt 14) builds on the fix.

---

# The prompts

Paste each block as-is into a fresh Claude Code session at the repo root.

---

### Prompt 9 — Contributions: seeds vs corrections, provenance, ref-bug fix

```
Evolve the expert capture model from "annotations" into first-class "contributions".
Follow CLAUDE.md. Keep the existing Annotation flow working (additive, backward-compatible).

Context: today an expert note is stored as one passive source="expert" chunk. We need
to (a) distinguish a *correction/connection* (attaches to a passage) from a *seed*
(opens a new aspect and carries a directive for the model to develop), and (b) fix
two real provenance leaks found in testing.

Requirements:
- In maayan/capture/models.py, extend the contribution model with:
    - directive: str | None = None   # the "now develop X" instruction, SEPARATE from body
    - opens_aspect: bool = False      # marks a seed that leads a new aspect
  Make `author` required (no default "expert"); a missing/blank author is a validation error.
- Fix the CLI --refs bug: refs CONTAIN commas (e.g. "Tanya, Part I; Likkutei Amarim 1:13"),
  so the current comma split shreds them. In maayan/cli.py annotate, accept refs without
  corrupting them — use a repeatable --ref option (preferred) and/or split on a delimiter that
  refs never contain (e.g. newline or " | "). Verify with a two-ref example that the stored
  linked_refs are intact.
- In maayan/capture/convert.py, when a contribution opens_aspect (a seed), keep the embedded
  chunk text = the knowledge (body) only; do NOT bury the directive in the embedded text
  (store the directive in metadata instead, so it doesn't pollute retrieval). Preserve all
  provenance in metadata (author, kind, opens_aspect, directive, linked_refs, move,
  session_id, contribution_id).
- UI (maayan/ui/static/index.html + ui/models.py + ui/app.py): make the Author field required
  and sticky (remember the last author via localStorage); add a "this opens a new aspect"
  checkbox and an optional "Directive (what should the model develop?)" input that map to the
  new fields.
- Tests: validation rejects blank author; --refs round-trips multi-comma refs intact; a seed
  contribution stores directive in metadata and NOT in the embedded text; existing capture
  tests still pass.

Show a before/after of a seed contribution's stored chunk text + metadata when done.
```

---

### Prompt 10 — Topic threads, persisted server-side

```
Add persistent topic threads so a line of inquiry accumulates over many turns. Follow CLAUDE.md.

Requirements:
- New pydantic models (maayan/capture/models.py or a new maayan/threads/ module): Thread
  (id, title, created_at, updated_at) and ThreadTurn (id, thread_id, ordinal, turn_type in
  {"ask","seed","development","refinement"}, timestamp, author, a reference id to the
  underlying record, and a text snapshot for display).
- Persist them in SQLite alongside sessions/annotations (new tables; idempotent migrations
  that don't break existing DBs). A ThreadStore with: create_thread, get_thread, list_threads,
  append_turn, get_turns. All collaborators injected (Clock for timestamps).
- A ThreadService that wires the store and exposes: start_thread(title), add_turn(...),
  get_thread_with_turns(id), list_threads().
- CLI: `maayan threads` (list), `maayan thread <id>` (show a thread with its ordered turns).
- Config: thread_context_turns (default 6) for later use.
- Tests: create a thread, append turns of each type, reload and assert order + provenance;
  list/show. Use an in-memory/temp SQLite.

Show a thread with 3 turns (an ask, a seed, a refinement) when done.
```

---

### Prompt 11 — Context-aware, grounded follow-ups

```
Make RAG follow-ups conversation-aware WITHOUT weakening grounding. Follow CLAUDE.md.

Requirements:
- Extend RAGService.ask (maayan/generate/rag.py) to accept optional prior turns as
  CONVERSATION CONTEXT: e.g. ask(question, *, context_turns: Sequence[...] = (), ...).
  The context is included in the prompt ONLY to help the model interpret the follow-up.
- Hard rules, enforced and tested:
    - Retrieval still runs fresh on the current question every turn.
    - Default-deny is unchanged: empty/low-relevance retrieval => refuse, no model call.
    - The answer must cite ONLY retrieved sources, never the conversation context. Make the
      prompt clearly separate "Conversation so far (for context only, do not cite)" from
      "Sources (cite these)".
- The number of prior turns included comes from config (thread_context_turns).
- Wire it into the thread flow: asking within a thread passes the last N turns as context and
  appends an "ask" turn.
- Tests (mock the GenerationBackend + Retriever): (a) context turns appear in the prompt and
  are labeled non-citable; (b) empty retrieval still refuses with no backend call even with
  context present; (c) the answer surfaces only retrieved cited refs.

Demo: a 2-turn exchange where turn 2 is a pronoun follow-up ("and the animal soul?") that
only resolves because of context, yet still cites freshly-retrieved sources.
```

---

### Prompt 12 — The Develop step (expert-directed, grounded, refuses honestly)

```
Add the core of this phase: the model DEVELOPS a seed under the expert's directive,
grounded in the corpus. Follow CLAUDE.md. This produces a PROPOSAL, not corpus yet.

Context: a seed carries (a) a framework, often from texts NOT in the corpus, and (b) a
directive like "find where this is hinted in Tanya". Development must ground the corpus-side
in retrieved sources while attributing the framework to the expert seed — and refuse if the
corpus does not support it.

Requirements:
- A DevelopmentService (maayan/develop/ new module) with develop(seed, *, thread_id) that:
    1. Builds a retrieval query from the seed body + directive; retrieves via the injected
       Retriever (config: develop_top_k).
    2. If retrieval relevance is below score_threshold => return a refusal Development
       ("no support for this in the corpus") with NO model call. (Default-deny.)
    3. Otherwise asks the GenerationBackend to develop the seed: the prompt includes the
       retrieved corpus SOURCES (to cite) and the expert SEED separately ("expert-provided
       framework — attribute it, do not cite it as a retrieved source"), and instructs the
       model to fulfill the directive grounded ONLY in the sources.
- Output a Development model: text, cited_refs, grounded_in (retrieved refs), model id,
  status="proposed", provenance (seed_id, author, thread_id). Persist it (proposed) and
  append a "development" turn to the thread. Do NOT index it as corpus yet.
- Everything injected (retriever, backend, clock, settings). No hardcoded models/prompts/urls.
- CLI: `maayan develop --seed <contribution_id>` prints the proposed development + its citations.
- Tests (mock retriever + backend): (a) below-threshold retrieval => refusal Development, no
  backend call; (b) good retrieval => development cites retrieved refs and records grounded_in
  + seed provenance; (c) the seed framework is passed as non-citable context.

Demo: run develop on the "ahava b'ta'anugim — find the hint in Tanya" seed and show the
proposed, cited development (or an honest refusal if nothing supports it).
```

---

### Prompt 13 — Approval gate → derived corpus chunks

```
Turn approved developments into retrievable corpus, with provenance. Follow CLAUDE.md.

Requirements:
- Add source="derived" to the Chunk taxonomy. A converter (maayan/develop/convert.py) turns
  an APPROVED Development into a Chunk: source="derived", book="Derived" (or the aspect title),
  a stable ref, text=the development, metadata={seed_id, author, developed_by=<model>,
  grounded_in=[refs], thread_id, development_id}.
- DevelopmentService.approve(development_id): set status="approved", persist+mark_indexed the
  derived chunk, embed + upsert into the SAME Qdrant collection. reject(development_id): set
  status="rejected", index nothing.
- Config: develop_auto_approve (default false) — when true, develop() approves immediately;
  when false, developments wait for approve(). derived_boost (default 1.0) analogous to
  expert_boost, applied in the retriever so reviewed-and-approved knowledge can be preferred.
- Retrieval/CLI surfacing: search results show source (sefaria/expert/derived) and, for
  derived, the seed author + grounded_in. `maayan search --source derived` filters to them.
- Tests: approve => derived chunk indexed + retrievable with full provenance; reject =>
  nothing indexed; auto_approve path; derived_boost changes ranking.

Demo: approve the development from Prompt 12, then ask a related question and show the derived
chunk surfacing with its "developed from expert seed by <model>, grounded in <refs>" provenance.
```

---

### Prompt 14 — UI: topic threads, seed, develop, approve

```
Rebuild the UI around persistent topic threads and the seed→develop→approve loop.
Follow CLAUDE.md. Thin route handlers only; logic stays in the services.

Requirements:
- Thread-centric layout: a persistent question/composer at the bottom; a scrollable thread
  above that accumulates turns in order — model answers (with citations + sources), expert
  seeds, model developments (rendered as PROPOSALS with Approve/Reject buttons), and expert
  refinements. A "New topic" button (with title) and a thread list to reopen past topics.
- Author field required + sticky (from Prompt 9). A "Seed a new aspect" affordance with the
  Directive input. An "Develop this" button on a seed turn that calls the develop endpoint;
  Approve/Reject on a development turn.
- New FastAPI routes (ui/app.py + ui/models.py), each wiring to ThreadService /
  CaptureService / DevelopmentService / RAGService: list/create threads, ask-in-thread,
  add-seed, develop-seed, approve/reject-development, get-thread.
- Keep grounding visible: cited sources marked; derived/expert results badged distinctly
  (sefaria vs expert vs derived). RTL via dir="auto" (already in place).
- Tests: FastAPI TestClient with mocked services for every route (happy path + the refusal /
  reject paths). No real models/network.

Demo (in the browser): seed an aspect, click Develop, see a grounded cited proposal, Approve
it, ask a follow-up in the same thread and watch the derived knowledge surface.
```

---

### Prompt 15 — Eval: measure development quality (grounding + honest refusal)

```
Extend the eval harness to score the develop step, not just retrieval. Follow CLAUDE.md.

Requirements:
- A small develop gold set (eval/develop_goldset.yaml): seeds with a directive, each marked
  either "supported" (the corpus genuinely hints at it -> expect a grounded development) or
  "unsupported" (expect a refusal). Seed ~8, editable, documented header.
- Metrics (pure, unit-tested with hand inputs) in maayan/eval/: 
    - grounding: of the refs a development CITES, the fraction that were actually retrieved
      (catches fabricated citations) -> 1.0 ideal;
    - develop-refusal accuracy: unsupported seeds correctly refused, supported seeds correctly
      developed (mirror the default-deny gate rates already in the harness).
- A harness entry (run_develop_eval) + CLI `maayan eval --develop` that prints the table.
  Reuse the injected retriever/backend; mockable.
- Tests: metric functions on tiny inputs; run_develop_eval aggregation with a fake
  retriever/backend (no network/models); a CI-checked guard that the real develop_goldset.yaml
  is well-formed (like test_shipped_goldset_is_well_formed).

Show the develop-eval table on the seed set when done.
```

---

## 5. Suggested order & checkpoints

9 → 10 → 11 → 12 → 13 → 14 → 15. Natural checkpoints:

- **After 9–11:** threads persist and follow-ups are conversational yet grounded. Worth a
  manual pass in the UI.
- **After 12–13:** the seed→develop→approve loop works end-to-end from the CLI — the heart of
  the phase. Re-run the *ahava b'ta'anugim* seed and confirm the development is grounded/cited
  or honestly refused.
- **After 14–15:** the loop is usable in the browser and measurable. Update
  [docs/TEACHING.md](TEACHING.md) (a new "developing the corpus" section + exercises) and tick
  this phase in the README status.

## 6. Invariants to re-check at every step (don't regress)

- Default-deny is enforced in code (no model call below threshold) — for `ask`, follow-ups,
  AND develop.
- Citations only ever reference retrieved sources; the expert seed/framework and conversation
  context are attributed but never cited as retrieved.
- Printed Sefaria text is immutable; expert/derived knowledge layers on as separate chunks.
- Provenance travels with every artifact (real author, seed id, model id, grounded refs).
- Typed + `mypy --strict`, DI, config-driven, secrets only via env, tests mock network/models.
