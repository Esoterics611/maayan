# Lesson 4.1 — Why eval exists, and the metrics

> Module 4, Lesson 1 · ~20 min read + a short hands-on.
> The one question this answers: **how do I know whether retrieval is actually *good*, instead
> of just trusting that it feels right?**

You can now explain the whole pipeline (Modules 0–3). But "I asked a few questions and the
answers looked fine" is not knowledge — it's a vibe. The moment you change a knob
(`score_threshold`, rerank on/off, a different embedding model) you need to answer: *did that
make retrieval better or worse?* You cannot answer that by eye. This module replaces the vibe
with **numbers**. This lesson is the numbers themselves.

---

## Why you can't just "look at the answers"

Three reasons eyeballing fails:

1. **It doesn't scale.** You can sanity-check 3 answers, not 50. Quality is a property of the
   *distribution* of questions, not a lucky example.
2. **It's not comparable.** "Variant A felt sharper than B" can't be defended or reproduced.
   To justify a change you need the same questions scored the same way, before and after.
3. **It hides the gate.** The most important behavior — *refusing* when it should — is
   invisible unless you deliberately test questions that *ought* to be refused.

So maayan ships an **eval harness**: a fixed set of questions with known-correct answers, run
through the real retriever, scored by standard metrics. Read the module header in
[maayan/eval/harness.py](../../maayan/eval/harness.py) — its whole reason for being is "so
model and chunking choices are justified with numbers, not vibes."

---

## The gold set: questions with known answers

Evaluation needs a ground truth to score against. That's the **gold set** — a hand-curated
list of cases. Open [eval/goldset.yaml](../../eval/goldset.yaml) and read a few. Each case is a
`GoldExample` ([goldset.py](../../maayan/eval/goldset.py)):

```yaml
- question: "מהן שתי הנפשות של האדם?"
  expected_refs: ["Tanya, Part I; Likkutei Amarim 1", "Tanya, Part I; Likkutei Amarim 2"]
  note: two souls — divine and animal
```

`expected_refs` is "if retrieval is working, *these* are the chapters it should pull back." The
gold set covers every chapter of Tanya Part I, plus a handful of **negative** cases (more on
those in Lesson 4.3). It's hand-made and editable — the file header says so: "better gold = more
trustworthy numbers."

> ### Under the hood — chapter-level gold, segment-level retrieval
> Your chunks are *segments* (`...Amarim 1:13`), but the gold refs are written at *chapter*
> granularity (`...Amarim 1`). How do they match? Read `ref_matches` in
> [metrics.py](../../maayan/eval/metrics.py): a retrieved ref counts if it equals the expected
> ref *or starts with it plus a colon*. So a chapter-level expectation matches any segment
> inside that chapter. This lets you write gold sets at the granularity you actually think in
> ("the answer is in chapter 1") without listing every segment.

---

## The three metrics, in plain language

All three live in [metrics.py](../../maayan/eval/metrics.py) — pure, hand-checkable functions.
Each answers a different question about the ranked list retrieval returned:

| Metric | Plain-language question | How it's scored |
|---|---|---|
| **hit@k** | "Did *any* right answer show up in the top *k*?" | 1.0 if yes, 0.0 if no |
| **recall@k** | "Of *all* the right answers, what fraction did we find in the top *k*?" | found / expected |
| **MRR** | "How *high* was the first right answer?" | 1 / (rank of first hit) |

A worked example. Suppose for a question the expected chapters are `{1, 2}` and retrieval
returns, in order: `[5, 1, 9, 2, 7]`.

- **hit@3** = 1.0 — chapter 1 is within the top 3. (At least one right answer appeared.)
- **recall@3** = 0.5 — of the two expected (1 and 2), only chapter 1 is in the top 3. (2 is at
  rank 4.)
- **MRR** = 1/2 = 0.5 — the first correct answer (chapter 1) was at rank 2.

Each captures something the others miss: `hit@k` asks "did we get *anything* right?"; `recall@k`
asks "did we get it *all*?"; `MRR` rewards putting the right answer *near the top* (rank 1 beats
rank 5 even if both are a "hit"). Read together, they describe retrieval quality far better than
any single number — or any glance.

---

## Hands-on

No need to run the full harness yet (that's Lesson 4.2) — first, *trust the metrics by checking
them by hand.* They're pure functions:

```bash
uv run python - <<'PY'
from maayan.eval.metrics import hit_at_k, recall_at_k, mrr
retrieved = ["ch5", "ch1", "ch9", "ch2", "ch7"]   # ranked output
expected  = ["ch1", "ch2"]                          # gold answer
print("hit@3   :", hit_at_k(retrieved, expected, 3))    # 1.0
print("recall@3:", recall_at_k(retrieved, expected, 3)) # 0.5
print("MRR     :", mrr(retrieved, expected))            # 0.5
PY
```

1. **Confirm the worked example.** The output should match the numbers above. If you can
   predict them before running, you understand the metrics.

2. **Probe each metric's blind spot.** Change `retrieved` so that `hit@3` stays 1.0 but
   `recall@3` drops, then so that `recall@3` is 1.0 but `MRR` is low. Each edit teaches you what
   that metric does *not* see. (Hint: move the right answers around in the list.)

3. **See chapter-vs-segment matching.** Try `hit_at_k(["Tanya, Part I; Likkutei Amarim 1:13"],
   ["Tanya, Part I; Likkutei Amarim 1"], 5)`. It's 1.0 — a segment satisfies a chapter-level
   expectation. That's `ref_matches` doing its prefix trick.

---

## You should now be able to say…

- Why eyeballing answers can't tell you if retrieval is good (scale, comparability, the hidden
  gate).
- What a **gold set** is — `{question, expected_refs}` cases — and why gold refs can be written
  at chapter granularity (prefix matching).
- What **hit@k**, **recall@k**, and **MRR** each measure, and why you need all three.

Next: **[4.2 — Running and reading the harness](04-2-running-the-harness.md)** — run these
metrics over the whole gold set with one command, and learn to read the table it prints,
including the default-deny gate rates.
