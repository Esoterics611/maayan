# maayan — a teaching walkthrough

> Read [CLAUDE.md](../CLAUDE.md) first for the contract, and
> [README.md](../README.md) to run it. **This document is the "why."** It explains
> the whole system end to end and, more importantly, teaches the engineering
> *skills* the codebase is built to demonstrate — each one transferable to any
> other project. It closes with a concrete plan to make this phase perfect.

---

## 0. The one-paragraph mental model

A question comes in. We **embed** it locally, **retrieve** the handful of source
chunks that actually support an answer, and only then ask a cloud model to write
an answer **grounded in those chunks, with citations** — refusing outright when
nothing supports it. An expert reads the answer, **corrects or connects** it, and
those notes become new retrievable chunks in the *same* index. Ask again and the
expert's knowledge surfaces alongside the printed text. That feedback loop — not
the model — is the product. Everything else (typing, DI, config, eval) exists so
that loop stays trustworthy as it grows.

**Phase 2 (§5) gives that loop teeth.** A note that just *sits there* becomes a
**seed**: knowledge (often from outside the corpus) plus a **directive** the model
**develops** — grounded in freshly-retrieved sources, cited, and refused if the
corpus doesn't support it. Once the expert **approves**, the development becomes new
*attributed* corpus. Lines of inquiry are organized into persistent **topic
threads**, and a **term lexicon** teaches the system which tokens are Holy
Names/terms rather than acronyms.

---

## 1. The data spine: one model, end to end

Every layer speaks in one currency: the **`Chunk`** (`maayan/corpus/models.py`).
Corpus → embed → index → retrieve → capture all pass `Chunk`s (or models derived
from them). Because the unit is the same everywhere, an *expert annotation* and a
*printed pasuk* are indistinguishable to the retriever — they live in the same
Qdrant collection, differing only by a `source` field (`"sefaria"` vs `"expert"`).
That single design decision is what makes the capture loop possible at all.

```
Sefaria ──ingest──▶ Chunk ──embed──▶ (dense+sparse) ──index──▶ Qdrant
                      ▲                                           │
                      │                                        retrieve
                  capture                                         │
                      │                                           ▼
                  Annotation ◀──── expert reads ◀──── grounded, cited answer
```

**Skill — model the domain's natural unit, not the storage format.** We chunk by
*pasuk / os / se'if* (the text's own joints), not by 512-token windows. Citations
become human-meaningful for free (`"Tanya, Part I; Likkutei Amarim 1:13"`), and
re-ingest is idempotent because the chunk `id` derives from that ref. When you
pick your unit, pick the one your *users* already think in.

---

## 2. The skills, taught from the code

### 2.1 Dependency injection — the reason everything is swappable

Look at `maayan/cli.py`: it builds the concrete embedder, Qdrant client,
generation backend, and clock, then *passes them in*. No business-logic module
ever constructs its own collaborators. The payoff is concrete:

- `GENERATION_BACKEND=openrouter|ollama` swaps cloud for local generation with
  **zero changes** to the RAG service — both implement the `GenerationBackend`
  protocol (`maayan/generate/`).
- Tests inject a `HashingEmbedder` (no GPU, no download) and an in-memory Qdrant.
  The retriever can't tell the difference — see `tests/test_retrieve.py`.

**Skill — construct at the edges, inject toward the center.** The center
(business logic) should depend on *protocols*, never on concretions. The edges
(`cli.py`, UI wiring, tests) are the only places allowed to say `new`.

### 2.2 Typed boundaries with pydantic — make illegal states unrepresentable

House rule #1: every datum crossing a module boundary is a pydantic model, and
`mypy --strict` must pass. `Chunk`, `SearchResult`, `RetrievalResult`,
`GoldExample`, `EvalReport` — none of them are loose dicts. The benefit isn't
ceremony; it's that a malformed gold-set entry fails *at load* with a clear error
(`GoldExample.model_validate`), not three layers deep with a `KeyError`.

**Skill — put a validating type on every seam.** Inside a function, use whatever
is convenient. The moment data crosses a boundary (file, network, module), give
it a type that *refuses* to exist if it's wrong.

### 2.3 Inject time — the `Clock`, and why `time.sleep` is banned in logic

House rule #2. The Sefaria client rate-limits itself by awaiting an injected
`Clock` (`maayan/clock.py`), so production uses `SystemClock` and tests use
`FakeClock` and **never actually sleep**. A rate-limit test runs in microseconds.

**Skill — treat time as a dependency.** Anything that waits, backs off, expires,
or timestamps should take a clock. Then "what happens after 30 days" is a unit
test, not a guess.

### 2.4 Default-deny, enforced in code — not in the prompt

House rule #6, and the spine of trust. If retrieval relevance is below
`score_threshold`, the RAG service **returns a refusal without calling the
model** (`maayan/generate/rag.py`). The model is *structurally* prevented from
answering from its own memory. A prompt that says "only use the sources" is a
suggestion; a branch that never makes the API call is a guarantee.

There's a subtlety worth internalizing: the gate uses an **absolute** relevance
signal (top dense cosine similarity), *not* the RRF fusion score. RRF scores are
rank-based — they tell you the best of what came back, never whether any of it is
actually relevant. Using the wrong signal here would make default-deny silently
useless. (See `RetrievalResult.relevance` and the gate logic in
`retriever.py`.)

**Skill — enforce invariants in control flow, not in instructions.** If a rule
matters, make the unsafe path *unreachable in code*, then test that it is.

### 2.5 Config as the single source of tunables

House rule #4. Model names, collection names, top-k, thresholds, base URLs, the
book list, and now the eval gold-set path and `eval_ks` all live in
`maayan/config.py` (`Settings`, from `pydantic-settings`). Secrets are
`SecretStr` read from env (house rule #5) — never logged. Changing retrieval
breadth is an env var, not a code edit.

**Skill — if you'd tune it in an experiment, it belongs in config.** Hardcoded
constants are fine for things you'll never vary; the moment you might A/B it,
lift it out.

### 2.6 Hybrid retrieval & RRF — why two retrievers beat one

`bge-m3` produces a **dense** vector (semantic similarity) and a **sparse** vector
(lexical / term overlap) in one pass. Qdrant fuses them with **Reciprocal Rank
Fusion**: each document's score is `Σ 1/(k + rank_in_list)` across the dense and
sparse rankings (`maayan/index/qdrant.py:query_hybrid`). Dense catches "means the
same thing"; sparse catches "uses the same rare word" (critical for Hebrew
technical terms and rashei-teivot). RRF needs no score normalization between the
two — it only looks at ranks.

**Skill — combine retrievers by rank, not by raw score.** Scores from different
models aren't comparable; ranks always are. RRF is the cheapest correct way to
ensemble.

### 2.7 The eval harness — replacing vibes with numbers (Prompt 7, just finished)

You cannot improve what you cannot measure. The harness (`maayan/eval/`) is three
small, independently testable pieces:

- **`metrics.py`** — pure functions: `hit_at_k`, `recall_at_k`, `mrr`. Ref
  matching is **prefix-aware**, so a chapter-level gold ref
  (`"...Likkutei Amarim 1"`) matches any segment retrieved within it (`"...1:13"`).
  That lets the gold set be written at the granularity a scholar actually knows.
- **`goldset.py`** — a `GoldExample` model and a YAML/JSON loader. The set
  (`eval/goldset.yaml`) is now **52 hand-curated cases over all 53 chapters** of
  *Likutei Amarim*, He + En, and is *meant to be edited*. Two kinds:
  **positive** cases carry the chapter(s) that should rank; **negative** cases set
  `should_refuse: true` — the right behavior is for the **default-deny gate to
  refuse** (off-corpus questions: other texts, halacha, anachronisms). Negatives
  measure the gate, not ranking, so they're excluded from hit/recall/MRR.
- **`harness.py`** — `run_eval` aggregates ranking metrics over the *positives*
  and, using the same `score_threshold` the RAG gate uses, reports two gate rates:
  **answer-rate** (positives it would answer — over-refusal hurts this) and
  **refusal-rate** (negatives it would refuse). `run_comparison` evaluates several
  `VariantConfig`s (hybrid vs dense-only, top-k, **swappable embedding model**) on
  the same questions and prints them side by side, gate rates included.

Run it:

```bash
make eval                  # single report against the seed gold set
make eval ARGS='--compare' # variant comparison table
```

**Skill — make evaluation a first-class, cheap-to-run artifact.** Metrics as pure
functions get unit-tested with hand-checked inputs (`tests/test_eval.py`); the
harness is the thing you run before *and after* every retrieval change so a
"clever improvement" that actually regresses recall gets caught immediately.

---

## 3. What the numbers actually say (measured, not claimed)

> The tables below were measured on the **original 15-question seed**. The gold set
> has since grown to **52 cases (42 positive + 10 negative)** spanning all 53
> chapters (P2, below), and `make eval` now also prints the default-deny gate rates.
> Re-run `make eval` for current figures; the seed numbers are kept here because the
> *lesson* they teach (next page) doesn't change.

Run on the live index (1,396 chunks of *Likutei Amarim*, bge-m3), 15-question
seed gold set:

```
   k |   hit@k |  recall@k
--------------------------
   1 |   0.267 |     0.233
   3 |   0.533 |     0.422
   5 |   0.800 |     0.600
  10 |   0.867 |     0.711
MRR: 0.457
```

Variant comparison at k=5:

```
variant         |   hit@5 |  recall@5 |    MRR
----------------------------------------------
hybrid k=10     |   0.800 |     0.600 |  0.457
hybrid k=5      |   0.800 |     0.600 |  0.457
dense-only k=10 |   0.867 |     0.678 |  0.608
```

Two honest takeaways:

1. **Dense-only currently beats hybrid on this gold set** (MRR 0.61 vs 0.46). That
   is exactly the kind of counter-intuitive result the harness exists to surface —
   sparse fusion may be adding noise on short, conceptual Hebrew questions. This is
   a *finding to investigate*, not yet a config change to make (15 questions is a
   small n).
2. **These numbers are now reproducible — and getting there found a real bug.**
   In the first run, the two hybrid rows differed (MRR 0.39 vs 0.45) even though
   `run_eval` queries every variant at `k = max(eval_ks) = 10`, so they *must*
   score identically. Diagnosis (see `§4 / P1`): the **embedder is fully
   deterministic** (verified: identical vectors across calls), but **Qdrant returns
   RRF-tied results in a nondeterministic order**, and a stable sort by score alone
   preserved that arbitrary order. The fix is a deterministic tiebreaker —
   `_rank_key = (-score, ref)` in `retriever.py` — so ties resolve the same way
   every run. Two separate `make eval` processes now produce byte-identical tables.
   *The lesson: the surprising eval result wasn't noise to wave away; it was a
   reproducibility bug the harness flushed out.*

**Skill — read your eval for surprises, not just for the headline number.** The
most valuable output of a benchmark is the result you didn't expect.

---

## 4. Plan to make this phase perfect

The phase (retrieval + grounded generation + capture + eval) *works*. To call it
*done well*, in rough priority order:

### P1 — Make eval reproducible (DONE — and a worked example of diagnosis)
This was the first thing to fix: a benchmark you can't reproduce can't justify a
decision. How it actually went, because the method matters more than the result:
- **Reproduced and isolated, didn't guess.** A 12-line diagnostic embedded the same
  query 4× (dense diff `0.0`, sparse identical → embedder is *not* the culprit) and
  then ran `query_hybrid` 4× on that *fixed* embedding (order shuffled → Qdrant is).
  This killed the original plan's assumption ("seed torch") before writing any code.
- **Root cause.** RRF sums `1/(k+rank)` → many *exactly* tied scores; Qdrant returns
  tied points in arbitrary order; Python's *stable* sort then faithfully preserves
  that arbitrary order. The bug hid behind a correct-looking `sort`.
- **Fix.** A deterministic total order — `_rank_key = (-score, ref)` in
  `retriever.py` — applied wherever results are ranked. Ties now resolve by ref.
- **Verified.** Two separate `make eval` processes produce byte-identical tables,
  and the two hybrid variants now agree (MRR 0.457 each). Locked in by a unit test
  (`test_rank_key_breaks_rrf_ties_deterministically`).
- **Lesson worth keeping:** the embedder being deterministic on *this* GPU doesn't
  guarantee it elsewhere (fp16/CUDA atomics). The cheap insurance — a CI smoke run
  that asserts `make eval` is stable across two invocations — is folded into P5.

### P2 — Make the gold set worth trusting (DONE — and it made the harness richer)
- **Grown ~15 → 52 cases over all 53 chapters**, He + En, weighted toward the
  previously-uncovered later chapters (33–53).
- **Negatives added.** 10 cases marked `should_refuse: true` — off-corpus questions
  (other texts, halacha, anachronisms, and a deliberate near-miss: Tanya Part III,
  which isn't indexed). A negative question retrieving nothing relevant is a
  *success*, so feeding negatives into hit/recall/MRR would be wrong — they'd score
  0 and tank the averages. So the harness now **splits positives from negatives**:
  ranking metrics over positives only, and a **default-deny gate** measured against
  the same `score_threshold` the live system uses (answer-rate over positives,
  refusal-rate over negatives). *Lesson: a new kind of test case can demand a new
  metric — don't shoehorn it into the old one.*
- **CI-guarded.** `test_shipped_goldset_is_well_formed` loads the real YAML in CI
  (no model needed), so a typo in the gold set can't ship green even though the
  other unit tests use synthetic gold.
- **Still open:** the refs are reasonable but not yet scholar-authoritative — the
  one step here that needs the actual expert, not the engineer.

### P3 — Measure the things the harness can't yet see
- **Answer-grounding metrics**, not just retrieval: of the refs the model cited,
  how many were actually retrieved? (catches hallucinated citations). *(The refusal
  side of this — a precision/recall view of the gate — landed early with P2's
  negatives; grounding of cited refs is the remaining piece.)*
- **Latency + token cost** per question, logged alongside quality, so a tradeoff
  table ("dense-only is faster *and* better here") is one command away.

### P4 — Close the embedding-model loop the harness was built for
- Add `multilingual-e5-large` (dense-only) and a DICTA rabbinic-Hebrew model as
  selectable `embed_backend`s, then run `--compare` to decide bge-m3 vs the
  alternatives **on numbers**. This is the entire reason `embed_model`/`embed_backend`
  are variant knobs.

### P5 — Polish the seams
- A `make eval-ci` smoke variant (HashingEmbedder, no downloads) so eval runs in CI
  on every PR without GPU.
- Document the eval workflow in CLAUDE.md's "Definition of done" so retrieval
  changes are *required* to show before/after numbers.

When P1–P3 are green, this phase is not just working — it's *defensible*: every
retrieval and model choice in the system can be backed by a number anyone can
reproduce. That's the bar.

---

## 5. Phase 2 — developing the corpus (notes → knowledge)

Phase 1 made a trustworthy *reader*: ask, retrieve, ground, cite, refuse. Phase 2
([docs/BUILD_PLAN_PHASE2.md](BUILD_PLAN_PHASE2.md)) makes a trustworthy *writer*: the
expert's input stops being inert text and starts **growing the corpus** — under the
same grounded/cited/default-deny discipline. Status as you read this: **Prompts 9–10
are built; 11–16 are specified and in progress.** Each subsection below names what's
done vs planned.

### 5.1 The shift: a seed is knowledge *plus a directive* (Prompt 9 — DONE)

The discovery that drove the whole phase: during testing an expert saved a note that
fused two different things in one text field — **knowledge** ("ahava b'ta'anugim is
the revelation of the Name ע״ב after the unification of מ״ה and ב״ן…", a framework
from texts *not* in the corpus) and a **directive** ("now find where this is hinted
in Tanya"). The old system embedded the whole blob as one passive `source="expert"`
chunk and did nothing with the directive.

So a `Contribution` (the evolved `Annotation`, `maayan/capture/models.py`) now carries
`directive: str | None` and `opens_aspect: bool` *separately* from `body`. The
converter (`capture/convert.py`) keeps a seed's **embedded text = the knowledge
(`body`) only**; the directive rides in **metadata**, never in the retrievable text.

**Skill — separate the data from the instruction about the data.** A "find X" command
is not knowledge; if you embed it, you pollute retrieval (now every search for that
topic surfaces an imperative sentence). Keep executable intent in a typed field, out
of the content. Verify it yourself:

```bash
uv run python -c "
from datetime import UTC, datetime
from maayan.capture.models import Annotation
from maayan.capture.convert import annotation_to_chunks
a = Annotation(id='x', session_id='s', timestamp=datetime.now(UTC), author='R. G',
    kind='connection', body='the knowledge', directive='find the hint in Tanya', opens_aspect=True)
[c] = annotation_to_chunks(a)
print('text :', repr(c.text))            # -> 'the knowledge'  (directive absent)
print('meta :', c.metadata['directive']) # -> 'find the hint in Tanya'
"
```

### 5.2 Provenance is the point — required author, and a four-value taxonomy

Two related rules landed in Prompt 9 and frame the rest of the phase:

- **`author` is required**, validated at the model boundary (a `field_validator`
  rejects blank/whitespace). There is no silent `"expert"` default any more —
  anonymous knowledge can't enter the corpus. *Skill — make attribution a validation
  invariant, not a convention.* An unattributed contribution should be *impossible to
  construct*, the same way a malformed `GoldExample` is (§2.2).
- **`Chunk.source` becomes a four-value taxonomy**: `sefaria` (printed, immutable) ·
  `expert` (a human seed/correction) · `derived` (a model development, **approved**) ·
  `term` (a lexicon entry). Retrieval and UI keep these **distinct and badged**, and
  printed text is **never edited** — expert/derived/term knowledge *layers on top* as
  separate chunks. *Skill — model provenance as first-class data.* "Who said this and
  on what basis" is a field you can filter, boost, and display — not a comment.

### 5.3 A real bug, a real lesson: never split on a delimiter your data contains (Prompt 9 — DONE)

The CLI `annotate` used to read `--refs "a, b"` and split on commas. But canonical
Sefaria refs *contain commas*: `"Tanya, Part I; Likkutei Amarim 1:13"`. The split
shredded one ref into three fragments — a silent provenance corruption. The fix: a
**repeatable `--ref`** option (each value taken verbatim) plus a `--refs` that splits
on `" | "`, a delimiter refs never contain.

**Skill — your delimiter must be outside your data's alphabet.** Before splitting on
a character, ask "can a legitimate value contain it?" For human-authored domain
strings the answer is usually yes for `,` `;` `:` `-`. Prefer repeated flags, or a
separator the domain guarantees it won't use. Cheap to get right, expensive to debug
later (the corruption is invisible until someone reads the stored refs).

### 5.4 Topic threads: persist the line of inquiry (Prompt 10 — DONE)

A single question is Phase 1; a *line of inquiry* that accumulates over many turns is
Phase 2. `maayan/threads/` adds a `Thread` (id, title, timestamps) and ordered
`ThreadTurn`s — each typed `ask | seed | development | refinement`, each carrying its
`author`, a `record_id` pointing at the underlying record (session / contribution /
development), and a **text snapshot** so the thread renders without re-joining. They
persist in SQLite (`maayan threads` to list, `maayan thread <id>` to show).

Note the layering, which mirrors the rest of the codebase:

- **`ThreadStore` is pure persistence** — it takes no `Clock` and makes no decisions.
  It even bumps a thread's `updated_at` from *the turn's own timestamp*, so it never
  needs to know the time.
- **`ThreadService` owns policy** — it injects the `Clock` (house rule #2), stamps
  timestamps, and assigns 1-based ordinals. The new `thread_context_turns` config
  (default 6) is the knob Prompt 11 will read.

**Skill — push time and numbering into the service, keep the store dumb.** A store
that knows the clock is a store you can't reorder, replay, or test deterministically.
Decisions (when, in what order) are policy; storage is mechanism — keep the seam.

### 5.5 Context-aware follow-ups — conversational, still grounded (Prompt 11 — DONE)

A thread is only useful if turn 2 can say "and the animal soul?" and be understood.
`RAGService.ask` now takes `context_turns: Sequence[ContextTurn]` — prior turns handed
to the model **only to interpret the current question**. The hard rules are enforced
in code, not hoped for in the prompt:

- **Retrieval still runs fresh on the current question alone.** The context never
  feeds retrieval, so grounding can't drift onto what was said earlier.
- **Default-deny is unchanged.** The below-threshold refusal returns *before any
  prompt is built*, so context can never sneak a model call past the gate (tested:
  empty retrieval + context present ⇒ still refuses, zero backend calls).
- **The context is non-citable.** It's rendered as a clearly-labelled "CONVERSATION
  SO FAR (do NOT cite…)" block *before* the citable `SOURCES:` block, and the system
  prompt forbids citing it. `cited_refs` is resolved only against the fresh sources —
  a ref that appears *only* in the conversation is never cited.

`ContextTurn` is deliberately a separate model from `threads.ThreadTurn`: the
generator must not depend on the thread layer. The bridge lives in one place,
`threads/flow.py::ask_in_thread`, which reads the last `thread_context_turns` (config)
turns, maps them to `ContextTurn`s, asks, and appends the new `ask` turn.

**Skill — when you relax a constraint for usefulness, re-pin it in code.** "See the
conversation" is exactly the kind of feature that quietly erodes grounding ("well, it
*was* in the context…"). The discipline is to make the relaxation *structural*:
separate blocks, a citation resolver that only knows the fresh sources, and a gate
that fires before the prompt exists. Convenience for the reader, zero give on trust.

### 5.6 The develop step — the same discipline, a new verb (Prompt 12 — DONE)

`DevelopmentService.develop(seed, *, thread_id)` (`maayan/develop/`) is `RAGService`'s
twin, with a new verb. It builds a query from the seed's body + directive, retrieves
fresh, and **if relevance is below `score_threshold`, returns a refusal `Development`
with no model call** — default-deny (§2.4) re-applied to a *new* operation. Otherwise
it asks the model to fulfil the directive with a prompt that **separates** the
retrieved corpus SOURCES (cite these) from the expert SEED ("framework — attribute it,
do **not** cite it as a retrieved source"). The output is a `Development` carrying
`status="proposed"`, `grounded`, `cited_refs`, `grounded_in`, and provenance
(`seed_id`, `author`, `thread_id`, `model`). It is persisted and appended to the
thread as a `development` turn — but **not indexed as corpus**. Approval does that
(§5.7).

Notice what made this cheap to build correctly: the citation resolver
(`extract_cited_refs`) and the numbered-sources renderer (`build_context`) were
*reused* from `rag.py`, so `develop`'s citations resolve against the fresh sources by
the exact same logic — a context- or seed-only ref can't be cited.

**Skill — re-apply your invariants to every new code path; don't assume they
generalize for free.** "Grounded, cited, refuses honestly" is true of `ask` because
it's *enforced* there; `develop` only inherits it because it enforces it again (and a
test asserts the below-threshold path makes zero backend calls). Same with citation
hygiene: the seed framework, like the conversation context in §5.5, is **attributed
but never cited** — only retrieved sources are citable. An invariant is a property of
code, not of a phase.

### 5.7 The approval gate — human-in-the-loop before knowledge becomes authoritative (Prompt 13 — DONE)

A development is a *proposal* until the expert approves it (`develop_auto_approve`
defaults `false`). `DevelopmentService.approve(id)` converts it into a
`source="derived"` chunk — with full provenance (`seed_id`, `author`,
`developed_by=<model>`, `grounded_in=[refs]`, `thread_id`, `development_id`) — and
embeds + upserts it into the *same* Qdrant collection (the exact pattern
`CaptureService` uses for expert chunks). `reject()` indexes nothing. The fourth
source value is now real end to end: `search --source derived` filters to it, results
badge it, and `derived_boost` (sibling to `expert_boost`, both resolved in
`Retriever._source_boost`) lets reviewed knowledge be preferred. Approving a *refusal*
is refused — there's nothing grounded to promote.

**Skill — put a human gate between "the model produced this" and "the system believes
this."** The model develops; the *expert* decides what becomes corpus. The gate is
what lets you trust the derived layer later — and it's why printed text stays
immutable and derived knowledge is a separate, labelled chunk, never an edit to the
source. (`approve`/`reject` + `develop_auto_approve` are just the *policy* over that
one structural fact.)

### 5.8 The thread UI — thin routes, logic in the services (Prompt 14 — DONE)

The browser UI (`maayan/ui/`) is rebuilt around topic threads: a sidebar of threads, a
scrollable turn list (ask / seed / development / refinement), and one composer that can
ask *or* plant a seed. Each user action is one `fetch` to one route, and **every route
is a thin wrapper over a service** — `create_app(rag, capture, threads, develop)` wires
them, and the handlers do nothing but translate HTTP ↔ service call. The seed→develop→
approve loop you ran from the CLI (§5.6–5.7) is the same services, now clickable;
sources are badged sefaria / expert / derived, and a development renders as a *proposal*
with Approve/Reject until it's promoted.

Two design points worth lifting out:
- **The generator never learns about threads.** Asking in a thread goes through
  `threads/flow.py::ask_in_thread` (§5.5), so the route just calls it — the thread layer
  composes the RAG layer, never the other way round.
- **The turn snapshot vs. the live record.** A `ThreadTurn` stores a display snapshot;
  on `GET /threads/{id}` the route *enriches* development turns with the live
  `Development` (status + citations, to drive the buttons) and seed turns with their
  directive. The snapshot keeps reads cheap; the enrichment keeps the buttons correct.

**Skill — the route is plumbing; resist putting logic in it.** Every test in
`tests/test_ui_threads.py` mocks the services and asserts the *wiring* (right service
called, right status on the refusal/reject paths). When the handler is thin, that's all
there is to test — the behavior is tested once, in the service.

### 5.9 The term lexicon — encode expertise as data, not as a clever heuristic (Prompt 16 — PLANNED)

Tokens like **ע״ב** carry gershayim (״) and *look* like rashei-teivot, but they are
**terms / Holy Names** (ע״ב is the *Ab* expansion of the Tetragrammaton, gematria 72;
sibling to ס״ג/מ״ה/ב״ן). Expanding them as abbreviations mangles meaning; the embedder
alone doesn't know them. The fix is a curated `Term` lexicon — define a term once as a
`source="term"` entity and every future question retrieves that definition — plus a
**protected-terms deny-list** that the documented rashei-teivot hook (CLAUDE.md) must
never expand.

**Skill — when a heuristic would be wrong, reach for a curated table instead.**
"Expand abbreviations" is a tempting rule that silently corrupts a whole category of
sacred terms. The disciplined move is not a smarter guesser but an *expert-maintained
deny-list / glossary*: domain knowledge lives as data the pipeline consults, with a
named author, not as code nobody can audit. (This is also the one *non-speculative*
reason to touch that hook at all.)

---

## 6. Exercises — test your understanding

The goal: be able to explain, and *change*, every part of what we built. Work top
to bottom; each group maps to a section above. **Predict the answer first, then run
the command to check.** Answers are collapsed — open them only after you've
committed to a guess. ⭐ = warm-up, ⭐⭐ = solid, ⭐⭐⭐ = you really get it.

> Setup once: `uv sync --extra ml --extra ui`, `make up`, `make ingest`, `make
> index`. Exercises that only touch pure functions need none of that.

### A. Orient yourself ⭐
1. Without grepping, list the six stages a question passes through from `maayan
   ask` to a printed answer, and name the module that owns each.
2. What is the single data type that flows through corpus → embed → index →
   retrieve? Why does that choice make the expert-capture loop possible?

<details><summary>Answers</summary>

1. Retriever (`retrieve/`) → [RAG default-deny gate] (`generate/rag.py`) →
   Generation backend (`generate/`) → answer; the question was first embedded
   (`embed/`) and searched in Qdrant (`index/`). Capture (`capture/`) records the
   session afterward.
2. `Chunk` (`corpus/models.py`). Expert annotations become `Chunk`s with
   `source="expert"` in the *same* collection, so retrieval can't tell them from
   printed text — that's the loop.
</details>

### B. Dependency injection ⭐⭐
1. Run `grep -rn "build_retriever\|build_embedder\|build_generation_backend"
   maayan/`. Every hit is in `cli.py`, the UI wiring, or a factory — none inside
   `generate/rag.py` or `retrieve/retriever.py`. Why is that the whole point?
2. `RAGService` takes a `Retrieving` and a `GenerationBackend` in its constructor.
   What would break about the Ollama swap (Prompt 8) if it instead constructed an
   `OpenRouterBackend` inside `ask()`?
3. ⭐⭐⭐ Write three lines of pseudocode for a test that checks default-deny
   *without any network or model*. Which fakes do you inject?

<details><summary>Answers</summary>

1. Business logic depends only on *protocols*; concretions are built at the edges
   and passed in. That's what lets real↔mock and OpenRouter↔Ollama swap with no
   change to the logic.
2. The `GENERATION_BACKEND` config switch would be dead — you couldn't select
   Ollama without editing `ask()`. DI is what makes the swap "config only."
3. Inject a fake `Retrieving` that returns `RetrievalResult(results=[],
   relevance=0.0)` and a `GenerationBackend` mock; assert `ask()` returns a refusal
   and the mock was **never called**. (See `tests/test_rag.py`.)
</details>

### C. Typed boundaries ⭐⭐
1. Add a `GoldExample` to a YAML file with `expected_refs: "Tanya 1"` (a string,
   not a list). Run `make eval`. What happens, and *where* — at load or deep in the
   loop? Why is that good?
2. ⭐⭐⭐ `RetrievalResult` carries both per-result `score` and a top-level
   `relevance`. Why can't the gate just use `max(score)` of the results?

<details><summary>Answers</summary>

1. It fails immediately in `load_goldset` via `GoldExample.model_validate` with a
   clear validation error — at the boundary, not three layers deep as a `KeyError`.
2. In hybrid mode the per-result `score` is an **RRF rank** score (best-of-list),
   which can't distinguish "relevant" from "best of irrelevant". `relevance` is an
   *absolute* top dense-cosine, which is what an absolute gate needs.
</details>

### D. Inject time ⭐⭐
1. The Sefaria client rate-limits itself. Find where it waits (`grep -rn "clock"
   maayan/corpus/`). Why does its rate-limit test run in microseconds?
2. ⭐⭐⭐ You add exponential backoff to a future API client. Per the house rules,
   what *must not* appear in it, and what do you inject instead?

<details><summary>Answers</summary>

1. It `await`s the injected `Clock`; tests inject `FakeClock`, which advances
   virtual time instantly — no real sleeping.
2. No `time.sleep`. Inject a `Clock` and drive all waiting through it (async), so a
   "what happens after N seconds" path is a unit test.
</details>

### E. Default-deny gate ⭐⭐
1. Predict: with `SCORE_THRESHOLD=0.99`, what does `uv run maayan ask "What is the
   capital of France?"` do, and does it spend an OpenRouter token? Run it.
2. Now run `SCORE_THRESHOLD=0.99 make eval`. Predict the direction of `answered (of
   positives)` and `refused (of negatives)` versus the default threshold. Why?
3. ⭐⭐⭐ Conversely, `SCORE_THRESHOLD=0.0`: what do the two gate rates become, and
   what real-world failure does that represent?

<details><summary>Answers</summary>

1. It refuses — and spends **zero** tokens; default-deny short-circuits before the
   model call (`rag.py:108`).
2. `answered` drops (real questions now wrongly refused — over-refusal) while
   `refused` rises toward 1.0. The threshold trades the two off.
3. `answered → 1.0`, `refused → 0.0`: the system answers everything, including
   off-corpus junk — i.e. it would hallucinate-from-nothing. That's exactly what
   default-deny exists to prevent.
</details>

### F. Hybrid retrieval & RRF ⭐⭐
1. In one sentence each: what does the *dense* vector catch that the *sparse* one
   misses, and vice-versa? Why does RRF fuse by **rank** rather than raw score?
2. ⭐⭐⭐ `run_eval` queries every variant at `k = max(eval_ks)`. Explain why
   "hybrid k=10" and "hybrid k=5" must therefore produce identical rankings — and
   what it meant when an early run showed they didn't.

<details><summary>Answers</summary>

1. Dense catches "means the same thing" (semantics); sparse catches "uses the same
   rare term" (lexical, key for Hebrew technical words). Scores from two different
   models aren't comparable; ranks always are, so RRF fuses ranks.
2. Both issue the *same* query at limit 10 (top_k is overridden by the `k=10`
   passed in), so identical results → identical metrics. When they differed, it
   exposed a **reproducibility bug** (next group).
</details>

### G. The eval metrics ⭐⭐
Predict each, then verify with
`uv run python -c "from maayan.eval.metrics import *; print(<expr>)"`:
1. `hit_at_k(["b","a","c"], ["a"], 1)` and `…k=2`
2. `recall_at_k(["a","x"], ["a","b"], 2)`
3. `mrr(["b","a"], ["a"])` and `mrr(["x","y"], ["a"])`
4. `ref_matches("Tanya 1", "Tanya 1:13")` and `ref_matches("Tanya 1", "Tanya 12")`
5. ⭐⭐⭐ Why does #4's second case return `False`, and what bug would a naive
   `retrieved.startswith(expected)` introduce?

<details><summary>Answers</summary>

1. `0.0` (a is rank 2), then `1.0`.
2. `0.5` (found `a`, not `b`).
3. `0.5` (first hit at rank 2), then `0.0` (no hit).
4. `True`, then `False`.
5. Matching requires the expected ref followed by `":"` (or exact). Naive
   `startswith("Tanya 1")` would wrongly match `"Tanya 12"`, `"Tanya 13"`, … —
   chapter 1 would "match" chapters 12–19.
</details>

### H. Reproducibility — re-derive the fix ⭐⭐⭐
1. Run `make eval ARGS='--compare'` twice; confirm the tables are byte-identical.
2. Temporarily change both `results.sort(key=_rank_key)` lines in
   `retriever.py` back to `results.sort(key=lambda r: r.score, reverse=True)`,
   re-run twice, and watch the hybrid MRR wobble. **Revert.**
3. Explain the chain: RRF score ties → Qdrant's order for ties → Python's *stable*
   sort → why a `(-score, ref)` key fixes it but `model.eval()`/seeding would not.

<details><summary>Answers</summary>

3. RRF sums `1/(k+rank)`, producing many exact ties; Qdrant returns tied points in
   an arbitrary order; a stable sort by score alone preserves that arbitrary order,
   so runs differ. The embedder was *verified deterministic*, so seeding fixes
   nothing — only a deterministic tiebreaker (`ref`) imposes a total order.
</details>

### I. Negatives & the gate (P2) ⭐⭐
1. Add one negative to `eval/goldset.yaml` (`should_refuse: true`, no
   `expected_refs`) with a clearly off-corpus question. Run `make eval`. Which
   numbers move — the hit@k table, or the gate rates? Why only those?
2. Add a *near-miss* negative (a real Tanya-adjacent topic that isn't in Part I).
   If `refused (of negatives)` drops, what have you learned about the threshold?
3. ⭐⭐⭐ A teammate "improves" recall by adding every example to `expected_refs`.
   Why is the harness's positive/negative split what stops that from silently
   inflating the score?

<details><summary>Answers</summary>

1. Only the gate rates (`refused (of negatives)`); negatives are excluded from
   hit/recall/MRR by design, since "retrieved nothing relevant" is *success* for
   them, not a miss.
2. The gate is too permissive for that query (it would answer something off-corpus)
   — a real, actionable finding: raise the threshold or improve the relevance
   signal (e.g. the reranker).
3. Negatives have no `expected_refs` and are never scored on ranking; you can't
   pad recall with them. Inflating positives' refs is visible in the diff and
   defeats the purpose — the split keeps the two concerns honest.
</details>

### J. Capstone ⭐⭐⭐
1. Set `EXPERT_BOOST=5`, capture an expert connection on a question (`ask` →
   `annotate`), then re-`search` a related query. Trace *why* the expert chunk now
   ranks where it does — name every step from `embed_query` to the final sort.
2. You want to claim "dense-only beats hybrid for this corpus." List the exact
   commands and the two things you must check before the claim is trustworthy
   (hint: one is about the gold set, one about the run).

<details><summary>Answers</summary>

1. `embed_query` → `query_hybrid` (RRF) → `_to_result` → `_apply_expert_boost`
   (multiplies expert scores ×5) → `results.sort(key=_rank_key)` → top-k. The boost
   raises the expert chunk's score so the deterministic sort ranks it higher.
2. `make eval ARGS='--compare'`. Check (a) the gold set is large/representative
   enough that the gap isn't noise (n, chapter coverage, expert-reviewed refs), and
   (b) the run is reproducible (two runs identical) so the gap is real, not tie
   jitter.
</details>

### K. Phase 2 — seeds, threads, provenance ⭐⭐
1. Predict, then run the §5.1 snippet: where does a seed's `directive` end up — the
   embedded chunk **text** or its **metadata** — and why must it not be in the text?
2. Predict, then run:
   `uv run python -c "from maayan.cli import _parse_refs; print(_parse_refs([], 'Tanya, Part I; Likkutei Amarim 1:13 | X, Y'))"`.
   How many refs come out, and what happened to the commas?
3. ⭐⭐⭐ `author` is validated on the `Annotation` **model** (a `field_validator`),
   not only in the CLI/UI. What class of bug does the model-level check prevent that a
   CLI-only check would not?
4. ⭐⭐⭐ `ThreadStore` takes no `Clock`, yet appending a turn advances the thread's
   `updated_at`. How does it get the time, and why would "the store reads the clock"
   be an anti-pattern here?

<details><summary>Answers</summary>

1. **Metadata.** The embedded text is the knowledge (`body`) only. If the directive
   were embedded, every retrieval on that topic would surface an imperative ("find
   the hint in Tanya…") and pollute both ranking and the grounded answer.
2. **Two** refs — `['Tanya, Part I; Likkutei Amarim 1:13', 'X, Y']`. `--refs` splits
   only on `" | "`, so the commas *inside* each ref are preserved (the old comma
   split would have produced four broken fragments).
3. Contributions are constructed in several places (CLI, the UI route, and future
   import/develop paths). A model-level validator makes an unattributed contribution
   **unrepresentable everywhere at once**; a CLI-only check leaves every other caller
   free to create blank-author records. Same principle as §2.2 — validate at the type.
4. `append_turn` writes `updated_at = turn.timestamp`, and that timestamp was stamped
   by the **service's** injected `Clock`. The store stays a pure mechanism, so tests
   drive it with `FakeClock` and replays/reorderings stay deterministic; a store that
   read the wall clock could not be (house rule #2, and §5.4).
</details>

---

*Generated as a teaching companion to the maayan build. Numbers in §3 were measured
on 2026-06-22 against the live local index; re-run `make eval` to refresh them.*
