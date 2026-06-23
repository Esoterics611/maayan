# Lesson 4.2 — Running and reading the harness

> Module 4, Lesson 2 · ~20 min, hands-on at the terminal.
> The one question this answers: **how do I run the whole gold set through retrieval, and how do
> I read the table it gives back — including the line about refusals?**

Lesson 4.1 gave you the metrics and the gold set. Now you run them together with one command and
learn to *read* the result. This is the skill that turns "I changed a knob" into "I changed a
knob and recall@5 went from 0.71 to 0.78." Read the table well and you can tune the system with
intent (Module 7) instead of guessing.

---

## One command

```bash
uv run maayan eval
```

That's it. Under the hood (read `evaluate` in [cli.py](../../maayan/cli.py) and `run_eval` in
[harness.py](../../maayan/eval/harness.py)) it: loads the gold set, runs **every** question
through the *real* retriever, scores each with hit@k / recall@k / MRR, and aggregates. It prints
the gold-set path, the active `score_threshold`, and a small table.

> **Prerequisite — index the full Tanya first.** The gold set covers all 53 chapters of Tanya
> Part I. If you only ingested two chapters back in Lesson 0.3, most questions can't be answered
> and your hit@k will look terrible — *correctly*, because the corpus doesn't contain the
> answers. For meaningful numbers, ingest the whole book first:
> ```bash
> uv run maayan ingest --book "Tanya, Part I; Likkutei Amarim"   # no --limit = all chapters
> make index
> ```
> (This is a bigger download than the two-chapter slice, but a one-time cost.)

---

## Reading the table

You'll get something shaped like this (your exact numbers will differ):

```
Gold set: eval/goldset.yaml (NN questions)
Default-deny gate threshold: 0.45

Gold set: NN questions (P positive, G negative)

   k |   hit@k | recall@k
------------------------------
   1 |   0.620 |    0.480
   3 |   0.840 |    0.690
   5 |   0.900 |    0.780
  10 |   0.960 |    0.870

MRR: 0.712

Default-deny gate (higher is better):
  answered (of positives): 0.940
  refused  (of negatives): 0.889
```

How to read it, line by line:

- **The k rows.** As `k` grows, `hit@k` and `recall@k` can only rise — you're allowing more
  results, so it gets easier to have caught the right ones. The *shape* matters: a high
  `hit@1` means the very top result is usually right; a big jump from `hit@1` to `hit@5` means
  the right answer is often present but not ranked first (a job for rerank — Module 2.4). The
  `eval_ks` shown (1, 3, 5, 10) are config (`eval_ks`).
- **MRR.** One summary number for "how high, on average, is the first correct answer." Closer to
  1.0 = right answers sit near the top.
- **The gate block — don't skip it.** This is the part eyeballing never showed you.

---

## The default-deny gate rates (the line that's really about trust)

Recall from Module 3 that the system's defining behavior is **refusing** when nothing supports
an answer. The harness measures that directly, against the same `score_threshold` the live
system uses (`run_eval` takes it as an argument — read the docstring: "the eval measures the
same decision the system makes at answer time"). Two rates, and **both want to be high**:

| Rate | What it measures | Failure it catches |
|---|---|---|
| **answered (of positives)** | fraction of answerable questions whose `relevance` ≥ threshold | **over-refusal** — the gate is too strict and refuses good questions |
| **refused (of negatives)** | fraction of unanswerable questions whose `relevance` < threshold | **under-refusal** — the gate is too loose and fabricates |

This is the central tension of `score_threshold`, now visible as a trade-off you can *see*:

- Raise the threshold → `refused` goes **up** (good, catches more junk) but `answered` goes
  **down** (bad, starts refusing real questions).
- Lower it → the reverse.

The "right" threshold is the one that keeps **both** rates high on *your* corpus. That's why
Module 3.3 said you tune the threshold "with the eval harness" — *this* is the instrument. You're
not guessing `0.45`; you're reading what it does to both rates and choosing.

> ### Under the hood — positives and negatives do different jobs
> `run_eval` splits the gold set: **positive** cases (those with `expected_refs`) drive
> hit@k / recall@k / MRR — ranking quality. **Negative** cases (`should_refuse: true`, empty
> refs) are *excluded* from ranking metrics and instead feed `refusal_rate` — gate quality. A
> positive also contributes to `answer_rate`. So one gold set measures two different things:
> *can it find the right passage?* and *does it know when there's no right passage?* Lesson 4.3
> is about writing both kinds well.

---

## Comparing variants (justifying a change)

The real power: run several configurations on the *same* gold set, side by side.

```bash
uv run maayan eval --compare
```

This uses `default_variants()` (hybrid k=10, hybrid k=5, dense-only k=10 — see
[harness.py](../../maayan/eval/harness.py)) and prints one row per variant with hit / recall /
MRR / answer / refusal. Now "hybrid beats dense-only" stops being folklore (Lesson 2.3) and
becomes a number you can point at. This is exactly how you'd justify turning rerank on, or
switching embedding models, in Module 8.1.

---

## Hands-on

Full Tanya indexed (see the prerequisite box).

1. **Run the baseline.** `uv run maayan eval`. Read every line. Which `k` gives `hit@k` ≥ 0.9?
   Is `hit@1` high (top result usually right) or is there a big climb to `hit@5` (right answer
   present but mis-ranked)? Write down what that shape implies.

2. **Read the gate rates aloud.** What fraction of answerable questions would the system answer,
   and what fraction of unanswerable ones would it refuse? If either is low, say which failure
   it is (over- or under-refusal).

3. **Watch the threshold trade-off directly.** Re-run with a stricter and a looser gate:

   ```bash
   SCORE_THRESHOLD=0.65 uv run maayan eval
   SCORE_THRESHOLD=0.25 uv run maayan eval
   ```

   Note how `answered` and `refused` move in *opposite* directions. You've just seen, in
   numbers, why the threshold is a balance and not a "bigger is better" knob.

4. **Compare variants.** `uv run maayan eval --compare`. Does hybrid beat dense-only on your
   corpus? By how much, at k=5? That delta is the kind of evidence Module 8 turns into a
   decision.

---

## You should now be able to say…

- How to run the harness (`maayan eval`) and what it does end to end.
- How to read the k-rows and MRR, and what the *shape* (hit@1 vs. hit@5) tells you.
- What the two **gate rates** mean, that both should be high, and how `score_threshold` trades
  them off — the instrument for tuning the gate.
- How `--compare` turns a configuration choice into a defensible number.

Next: **[4.3 — Gold sets & honest measurement](04-3-gold-sets.md)** — the numbers are only as
honest as the gold set behind them. We'll see what makes a good case, why negative cases matter,
and add one yourself.
