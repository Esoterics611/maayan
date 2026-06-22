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
- **`goldset.py`** — a `GoldExample` model and a YAML/JSON loader. The seed set
  (`eval/goldset.yaml`) is ~15 hand-curated questions over *Likutei Amarim*, in
  both Hebrew and English, and is *meant to be edited* — better gold = more
  trustworthy numbers.
- **`harness.py`** — `run_eval` aggregates metrics over the gold set;
  `run_comparison` evaluates several `VariantConfig`s (hybrid vs dense-only,
  top-k, **swappable embedding model**) on the same questions and prints a
  side-by-side table.

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

### P2 — Make the gold set worth trusting
- Grow it from ~15 to ~50+ questions, spanning more of the corpus (not just the
  early chapters), with a few **negative** questions whose correct behavior is a
  *refusal* (so default-deny gets measured too).
- Have the expert (the actual scholar) review/author the gold refs. Right now they
  are reasonable but not authoritative; the file header already says so.

### P3 — Measure the things the harness can't yet see
- **Answer-grounding metrics**, not just retrieval: of the refs the model cited,
  how many were actually retrieved? (catches hallucinated citations). And a
  refusal-precision/recall pass over the negative questions.
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

*Generated as a teaching companion to the maayan build. Numbers in §3 were measured
on 2026-06-22 against the live local index; re-run `make eval` to refresh them.*
