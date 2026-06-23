# Lesson 8.1 — Reading quality and improving it

> Module 8, Lesson 1 · ~15 min read + a hands-on at the terminal.
> The one question this answers: **how do I turn "I wonder if this would be better" into a
> decision I can defend with numbers?**

You've reached the horizon — where maayan goes next, and how to extend it without breaking its
guarantees. This first lesson is the bridge from Module 4 (you *can* measure) to Module 7 (you
*can* tune) to a disciplined habit: **never change retrieval on a hunch; change it on a measured
delta.** It's a short lesson because you already have every tool. What's new is the *method*.

---

## The temptation, and the discipline

It's tempting to flip `rerank_enabled`, swap the embedding model, or re-chunk because a few
answers felt off. But "felt off" is the vibe Module 4 warned against. The discipline is a loop:

> **hypothesis → measure baseline → make the change → measure again → compare → decide.**

The eval harness exists precisely so this loop is one command at each step. BUILD_PLAN §5 says it
in plain words about the harness: a comparison mode so you can "justify model/chunking choices
with numbers instead of vibes." That sentence is this whole lesson.

---

## What you can justify this way

Three kinds of change, each a real decision an operator faces:

| Change | The hypothesis | Read it off… |
|---|---|---|
| **Enable rerank** | "ordering is off; a second pass will fix it" | `MRR` / `hit@1` up enough to justify latency? (7.2) |
| **Swap embedding model** | "a Hebrew-specialized model retrieves better" | `recall@k` across the gold set, after `index --rebuild` |
| **Re-tune `score_threshold`** | "it over-refuses / under-refuses" | the two gate rates balanced (4.2) |

The embedding-model case is worth dwelling on: the harness was *built* to make the embedder
swappable specifically so you can drop in `multilingual-e5-large` or a DICTA rabbinic-Hebrew model
and **measure** whether it helps your corpus — rather than assuming. A model being "better in
general" means nothing; better *on your gold set* is a number.

> ### Under the hood — the comparison is apples-to-apples by construction
> `maayan eval --compare` runs every variant against the *same* gold set with the *same* metrics
> (Module 4.2's `run_comparison`). And ranking is deterministic (the `_rank_key` tie-break by
> `ref`, Lesson 2.3), so a variant's score is reproducible run to run. That's what makes the delta
> trustworthy: nothing moved except the one knob you're testing. A change that doesn't move the
> numbers isn't worth its complexity; a change that moves them earns its place.

The honest part: sometimes you'll measure and find the change *doesn't* help — or helps one metric
and hurts another. That's not a failed experiment; that's the experiment doing its job. Better to
learn it from the table than to ship a regression on a feeling.

---

## Hands-on

Full Tanya indexed (so the gold set is meaningful).

1. **Run the comparison.** `uv run maayan eval --compare`. This is your menu of "what if" answers
   for the built-in variants (hybrid k=10 / k=5 / dense-only). Which wins at `k=5`? By how much?

2. **Frame one real decision.** Pick a change you might actually make (say, enabling rerank).
   Write the hypothesis in one sentence, then measure both sides:

   ```bash
   uv run maayan eval                       # baseline
   RERANK_ENABLED=true uv run maayan eval    # the change
   ```

   Record the deltas in `MRR` and `hit@1`. Now decide *and write down why* — "yes, MRR +0.06
   justifies the latency" or "no, +0.01 isn't worth the model download." That sentence is a
   defensible engineering decision, not a vibe.

3. **Find the seam for a model swap.** You won't download a new model now, but locate where you'd
   point it: `embed_model` in [config.py](../../maayan/config.py), and recall it needs
   `index --rebuild` (7.2). In one sentence: why must you rebuild the index to fairly compare two
   embedding models?

---

## You should now be able to say…

- The improvement loop: **hypothesis → baseline → change → re-measure → compare → decide.**
- The three changes you can justify with numbers (rerank, embedding model, threshold) and which
  metric reads each.
- Why the comparison is apples-to-apples (same gold set, same metrics, deterministic ranking) —
  and that a null or negative result is a *successful* measurement.

Next: **[8.2 — Phase 4: the eraser & measurement](08-2-phase4-eraser.md)** — the ability to
*remove* knowledge (provenanced, never silent) and to measure the cross-text claim that earlier
went unmeasured.
