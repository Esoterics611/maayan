# Lesson 2.3 — Hybrid retrieval & fusion (RRF)

> Module 2, Lesson 3 · ~20 min read + a hands-on at the terminal.
> The one question this answers: **when I ask a question, how does the system combine
> "meaning" search and "wording" search into one ranked list — and what do the scores mean?**

This is the heart of the "R." Points are sitting in the collection (Lessons 2.1–2.2). Now a
question arrives. maayan runs **two** searches and **fuses** them, then hands back a ranked
list plus a number that decides — in Module 3 — whether to answer at all. Get this lesson and
you understand why retrieval returns what it does.

---

## Two weak signals, fused, beat one strong one

Recall the dense/sparse split from Lesson 1.1:

- **Dense** search finds passages that *mean* something similar — great for paraphrase and
  synonyms, but it can drift toward "vaguely on topic."
- **Sparse** search finds passages that share the actual *words* — great for a precise term
  or a name, but blind to rephrasing.

Each alone has a failure mode. The insight behind **hybrid search** is that their failure
modes are *different*, so combining them covers both. A passage that ranks high on *both*
meaning and wording is almost certainly what you want.

So maayan, given a query, embeds it once (dense + sparse, Lesson 1.1) and runs **both**
searches against the collection's two named vectors. Then it has to merge two ranked lists
into one. That merging is the interesting part.

---

## RRF: fuse by *rank*, not by score

You can't just add the dense and sparse scores together — they're on completely different
scales (cosine similarity vs. lexical weight), so one would swamp the other. The trick maayan
uses is **Reciprocal Rank Fusion (RRF)**, and it's beautifully simple:

> For each result, ignore its raw score and look only at its **position** in each list. A
> passage ranked #1 contributes `1/(k+1)`; #2 contributes `1/(k+2)`; and so on. Add up a
> passage's contributions across both lists. Highest total wins.

Because it uses *rank position* instead of raw score, RRF doesn't care that the two scales
differ. A passage near the top of *both* lists accumulates the most and rises; a passage that
only one method liked still gets some credit but ranks lower. Two weak agreeing signals beat
one strong lonely one.

This is wired in `QdrantIndex.query_hybrid` ([qdrant.py](../../maayan/index/qdrant.py)): it
issues two `Prefetch`es (one `using="dense"`, one `using="sparse"`) and combines them with
`FusionQuery(fusion=Fusion.RRF)`. Qdrant does the fusion for you; the method just expresses
the recipe.

---

## The two scores — and why the difference is the whole ballgame

Open [maayan/retrieve/models.py](../../maayan/retrieve/models.py). There are **two** numbers,
and confusing them is the most common mistake in reading this system:

| Number | Where | What it is | What it can tell you |
|---|---|---|---|
| `SearchResult.score` | on each result | the **RRF fusion** value (rank-based) | *relative* order within this query's results |
| `RetrievalResult.relevance` | once, on the whole result | the **top dense cosine similarity** | *absolute* "is anything here actually relevant?" |

Read the docstring on `RetrievalResult` — it says it outright: the RRF `score` "only reflects
rank position and so cannot tell 'relevant' from 'best of irrelevant'." That's the key. RRF
will *always* rank something #1, even for a nonsense query — being best-of-the-batch says
nothing about whether the batch is any good. So RRF is great for **ordering** but useless for
the question Module 3 must answer: *should we answer at all, or refuse?*

That question needs an **absolute** measure, so the retriever computes one separately: the
cosine similarity of the single closest dense match (`query_dense(..., limit=1)`). That's
`relevance`. Look at [retriever.py](../../maayan/retrieve/retriever.py) around the end of
`retrieve` — when hybrid is on, it runs a tiny extra dense-only query just to get this
absolute number. **`relevance` is the value the default-deny gate checks** (Module 3, Lesson
3.3). Hold that thread: the `score` you *see* in `search` output is not the number that
decides refusal.

> ### Under the hood — why ties are broken by `ref`
> RRF sums `1/(k+rank)`, which produces lots of *exactly equal* totals, and Qdrant returns
> tied points in arbitrary order. If the retriever sorted by score alone, the same query
> could rank differently run-to-run — and the eval harness (Module 4) would be
> non-reproducible. So `_rank_key` sorts by `(-score, ref)`: score descending, then the
> unique `ref` ascending as a deterministic tiebreaker. The embedder is already deterministic,
> so with this, the entire retrieve path is reproducible. Small detail, big payoff for trust.

---

## Hands-on

Qdrant up, corpus indexed. Let's read both scores.

**1. See the ranked list and its RRF scores.** The CLI shows `SearchResult.score` (the RRF
value) in brackets:

```bash
uv run maayan search "ההבדל בין צדיק לבינוני" --book "Tanya" --k 5
```

Each line is `[score] ref (lang/source)`. Read the scores top to bottom — they decrease.
Remember: these are **rank-based** fusion values. They tell you the *order*, not whether any
result is truly relevant.

**2. Watch `--k` change how much you get (not the order).** Run the same query with `--k 3`
then `--k 8`. The top results stay in the same order; `--k` just controls how far down the
list you see. (`top_k`, default 8, is the config default when you omit `--k`.)

**3. Now reveal the *other* number — the one that gates answers.** The CLI doesn't print
`relevance`, so peek at it directly:

```bash
uv run python - <<'PY'
from maayan.config import Settings
from maayan.retrieve.factory import build_retriever

r = build_retriever(Settings())
for q in ["ההבדל בין צדיק לבינוני", "מהי נקודת הרתיחה של מים"]:
    res = r.retrieve(q, k=3, book="Tanya")
    top = res.results[0].score if res.results else None
    print(f"relevance(abs)={res.relevance:.3f}  top RRF score={top}  ::  {q}")
PY
```

Compare the two questions. The on-topic one should have a **higher `relevance`** than the
boiling-point one — *even though both produce a ranked list with a #1 result and a non-trivial
RRF score.* That gap between "RRF always ranks something first" and "relevance knows it's
junk" is exactly the gap the refusal gate lives in. Write down both `relevance` values; recall
`score_threshold` defaults to `0.45` (Module 0) — which question would clear it?

---

## You should now be able to say…

- Why **hybrid** search (dense + sparse) beats either alone — their failure modes differ.
- What **RRF** does: fuse two lists by *rank position*, sidestepping incompatible score
  scales.
- The crucial difference between `score` (RRF, **relative** order) and `relevance` (top dense
  cosine, **absolute**) — and that `relevance` is what the refusal gate will check.
- Why ranking is made deterministic (tie-break by `ref`) and why that matters for eval.

Next: **[2.4 — Reranking & filters](02-4-rerank-and-filters.md)** — an optional second pass
that re-reads the top candidates for sharper ordering, plus the `--book` / `--source` filters
you've been using.
