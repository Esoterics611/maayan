# Lesson 7.2 — The knobs that matter

> Module 7, Lesson 2 · ~20 min, hands-on at the terminal.
> The one question this answers: **of all the settings in `config.py`, which ones actually change
> retrieval behavior — and how do I reach for the right one with intent?**

You've met most of these knobs in passing. This lesson collects the few that matter for tuning,
says what each *does to behavior*, and — crucially — pairs each with the eval harness (Module 4)
so you turn knobs with evidence, not vibes. All of them live in
[maayan/config.py](../../maayan/config.py) and are settable via env / `.env` (Lesson 5.3).

---

## The five knobs you'll actually touch

| Knob | Default | What it does | Reach for it when… |
|---|---|---|---|
| `score_threshold` | `0.45` | the default-deny bar (Lesson 3.3) | it refuses good questions (lower) or answers junk (raise) |
| `top_k` | `8` | how many candidates fused/returned | answers miss context (raise) or include noise (lower) |
| `rerank_enabled` | `false` | the cross-encoder second pass (Lesson 2.4) | ordering is off and you'll pay latency for quality |
| `expert_boost` / `derived_boost` / `term_boost` | `1.0` | rank multipliers per source (Lesson 2.4) | you want human/curated knowledge to outrank text |
| `embed_model` | `BAAI/bge-m3` | the embedder itself (Lesson 1.1) | you're evaluating a different model (rebuild needed) |

Two you'll rarely touch but should know: `rerank_candidates` (`30`, the pool the reranker
reorders) and `embed_dim` (`1024`, must match the model). Changing `embed_model` or `embed_dim`
requires `index --rebuild` (Lesson 2.2) — the vectors must be recomputed.

---

## `score_threshold`: the trust dial

This is the one you'll tune most, because it sets the answer/refuse balance. From Lesson 4.2 you
already know the trade-off as *numbers*:

- **Raise it** → more refusals. The `refused (of negatives)` rate goes up (catches more junk), but
  `answered (of positives)` goes down (starts refusing real questions). Over-strict.
- **Lower it** → the reverse. Risks fabrication on weak matches. Over-loose.

The config description spells out a subtlety: bge-m3 cosine "clusters in a narrow band," so the
useful range is corpus-specific — `0.45` is a *starting* point, not a law. And note (Lesson 2.4):
when `rerank_enabled` is on, `relevance` becomes the *reranker's* score, which separates good from
bad more sharply — so the threshold often wants re-tuning after you enable rerank. **The right way
to set it is the eval harness**, watching both gate rates.

---

## The source boosts: making human knowledge win

The boosts (`expert_boost`, `derived_boost`, `term_boost`) are the operator's lever over the
capture loop (Module 6). At the default `1.0`, an `expert` chunk competes with `sefaria` purely on
relevance. Set `expert_boost=1.2` and a scholar's contribution, when it's relevant, gets nudged
*above* the printed text — encoding the editorial choice "when my expert addressed this, prefer
their framing." This only matters once you have non-`sefaria` chunks; it's how you decide *how
loudly* the loop speaks. Use it deliberately — too high and human notes drown out the text they're
supposed to illuminate.

> ### Under the hood — why these are knobs and not constants
> Every one of these is a `Settings` field precisely so you can tune it per corpus *without
> touching logic* (Lesson 5.3) and *measure the effect* (Module 4). A different corpus (more
> books, a different language mix) has a different ideal threshold and top_k. Hardcoding any of
> them would freeze the system to one corpus. The combination — config-driven knobs + an eval
> harness that reads the same `score_threshold` the live system uses — is what makes tuning a
> *measurement*, not a guess.

---

## Hands-on — tune one knob with evidence

Full Tanya indexed (Lesson 4.2 prerequisite), so the gold set is meaningful.

**1. Establish a baseline.** `uv run maayan eval`. Write down `hit@5`, `MRR`, and both gate rates
at the default `score_threshold=0.45`.

**2. Move the trust dial and watch both rates.**

```bash
SCORE_THRESHOLD=0.60 uv run maayan eval     # stricter
SCORE_THRESHOLD=0.30 uv run maayan eval     # looser
```

Confirm `answered` and `refused` move in opposite directions (Lesson 4.2). Pick the value that
keeps **both** high on your corpus — that's your tuned threshold, chosen by evidence.

**3. Weigh rerank as a real decision.** Compare ordering quality with and without the second pass:

```bash
uv run maayan eval --compare                          # baseline variants
RERANK_ENABLED=true uv run maayan eval                # rerank on
```

Did `MRR` / `hit@1` improve enough to justify the added latency and model download? That cost/
benefit judgment — read off the numbers — is exactly how an operator decides to flip a knob
(Module 8.1 generalizes it).

**4. Feel a boost (preview).** If you created an `expert` chunk in Module 6, search a query it's
relevant to, then re-run with `EXPERT_BOOST=1.5 uv run maayan search "<that query>" --k 5`. Watch
your contribution climb the ranking. In a sentence: when would boosting *too* hard be a mistake?

---

## You should now be able to say…

- The five knobs that matter (`score_threshold`, `top_k`, `rerank_enabled`, the source boosts,
  `embed_model`) and what each does to behavior.
- That `score_threshold` is the **trust dial**, tuned via the **eval harness** by balancing the
  two gate rates — and that rerank shifts the number it reads.
- That the **boosts** are the operator's control over how loudly the capture loop ranks, default
  `1.0`.
- That `embed_model`/`embed_dim` changes require an `index --rebuild`.

Next: **[7.3 — Choosing & swapping the generation backend](07-3-backend-swap.md)** — the cloud↔
local decision you previewed in 3.1, now as an operational choice with a real swap.
