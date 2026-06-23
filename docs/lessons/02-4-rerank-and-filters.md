# Lesson 2.4 — Reranking & filters

> Module 2, Lesson 4 · ~20 min read + a hands-on at the terminal.
> The one question this answers: **how do I sharpen the top results, and how do I restrict
> retrieval to a particular book or kind of source?**

Hybrid + RRF (Lesson 2.3) gives a good ranked list, fast. This lesson adds two refinements
that sit on top of it: an optional **reranker** that re-reads the best candidates for a
sharper order, and **filters** that narrow *what's eligible* in the first place. Both are
small, both are config-driven, and both close out the retrieval module.

---

## The speed/quality trade-off behind reranking

Hybrid search is a **bi-encoder** method: the query and each passage are embedded
*separately*, then compared by vector distance. That's what makes it fast — you embed the
passages once, at index time, and only the query at search time. But "compared separately"
also means the model never looks at the query and a passage *together*; it can miss subtle
relevance.

A **cross-encoder** reranker does the opposite: it takes `(query, passage)` as a *pair* and
reads them together, producing a far more discriminating relevance score. That's slower — it's
a fresh model pass per candidate — so you'd never run it over the whole corpus. The standard
pattern, which maayan follows, is **retrieve-then-rerank**:

> Use fast hybrid search to fetch a *pool* of candidates (say 30), then run the slow, accurate
> reranker on just those 30 to reorder the top few. Cheap where you can be, expensive only
> where it counts.

---

## How it's wired

Two files:

- [maayan/retrieve/reranker.py](../../maayan/retrieve/reranker.py) — a `Reranker` *protocol*
  (`rerank(query, documents) -> list[float]`, higher = more relevant) and a concrete
  `BGEReranker` (`bge-reranker-v2-m3`). Like the embedder, it's behind a protocol so it can be
  `None` (off) in tests, or swapped.
- [maayan/retrieve/retriever.py](../../maayan/retrieve/retriever.py) — the `Retriever`
  decides whether to use it.

Read the `retrieve` method. The relevant logic:

```python
pool = max(final_k, rerank_candidates) if reranker else final_k   # fetch more if reranking
... hybrid search returns `pool` candidates ...
if reranker is not None:
    raw_scores = reranker.rerank(query, [r.text for r in results])  # re-read each pair
    # the cross-encoder score replaces the RRF score, and …
    relevance = max(raw_scores)                                     # … also becomes the gate value
```

Two things to notice. First, when a reranker is present it fetches a **bigger pool**
(`rerank_candidates`, default 30) so there's something for it to reorder, then trims to your
`k` after. Second — important — when reranking is on, the **cross-encoder score becomes the
`relevance`** that the default-deny gate checks (Module 3), not the dense cosine from Lesson
2.3. The config docstring on `score_threshold` even notes that "enabling rerank sharpens
separation," which is why the threshold may want re-tuning when you turn rerank on. By default
**`rerank_enabled` is `false`** — it's an opt-in quality upgrade with a latency and
model-download cost.

> ### Under the hood — source boosts ride along here too
> The same `retrieve` method applies *source boosts* before/with ranking: `expert_boost`,
> `derived_boost`, `term_boost` (all default `1.0` = no effect). These multiply the score of
> chunks that came from a human expert, an approved development, or the curated lexicon — so
> that when a scholar's contribution is *as* relevant as printed text, it can be made to rank
> at or above it. That's a Module 6/7 concern (it only matters once you have non-`sefaria`
> chunks), but notice it lives right here in the retriever, as a clean multiplier. With the
> defaults at `1.0`, retrieval treats every source equally.

---

## Filters: narrowing what's eligible

Sometimes you don't want to reorder results — you want to *exclude* some entirely. That's a
**filter**, and it's a different mechanism from scoring: it constrains which points the search
is even allowed to consider. Read `_build_filter` in `retriever.py` — it builds a Qdrant
filter from three optional constraints:

| Filter | CLI flag | Effect |
|---|---|---|
| `book` | `--book "Tanya"` | only points whose payload `book` matches |
| `source` | `--source sefaria` | only that provenance (`sefaria`/`expert`/`derived`/`term`) |
| `langs` | (API) | only those languages |

You've already used `--book` since Module 0. The key idea: a filter is applied *inside* the
search (it's passed into each `Prefetch`), so it shapes the candidate pool **before** ranking
— not a post-hoc removal. Filtering by `--source` becomes especially meaningful in Module 6,
when the collection holds expert and derived chunks beside the printed text and you want to
ask "what did *I* contribute on this?" versus "what does the printed text say?"

---

## Hands-on

Qdrant up, corpus indexed.

**1. Use the filters you now understand.** Restrict by book, then by source:

```bash
uv run maayan search "שתי הנפשות" --book "Tanya" --k 5
uv run maayan search "שתי הנפשות" --book "Tanya" --source sefaria --k 5
```

Right now every chunk is `source=sefaria`, so the second command returns the same results —
but you've just written the query you'll use in Module 6 to separate printed text from your
own contributions. Note that the filter changes *what's eligible*, not the order of what's
left.

**2. Turn the reranker on and compare ordering.** This downloads `bge-reranker-v2-m3` the
first time (a one-time cost, like bge-m3) and is slower per query. Run the *same* query with
rerank off, then on, and compare the top few refs:

```bash
uv run maayan search "ההבדל בין צדיק לבינוני" --book "Tanya" --k 5
RERANK_ENABLED=true uv run maayan search "ההבדל בין צדיק לבינוני" --book "Tanya" --k 5
```

Did the order change? Often the reranker promotes a passage that's *genuinely* most on-point
above one that merely shared vocabulary. On a two-chapter corpus the effect may be small;
it grows with corpus size and query subtlety. Note what moved.

**3. See rerank change the *gate* number, not just the order.** Reuse the relevance snippet
from Lesson 2.3, once normally and once with `RERANK_ENABLED=true`:

```bash
RERANK_ENABLED=true uv run python - <<'PY'
from maayan.config import Settings
from maayan.retrieve.factory import build_retriever
r = build_retriever(Settings())
res = r.retrieve("ההבדל בין צדיק לבינוני", k=3, book="Tanya")
print(f"relevance (now a reranker score): {res.relevance:.3f}")
PY
```

The `relevance` is now the cross-encoder's score, not the dense cosine. That's why
`score_threshold` may need a different value when rerank is on — you've just seen the number
the gate reads come from a different source. (You'll tune this deliberately in Module 7.2.)

---

## You should now be able to say…

- The bi-encoder (fast, separate) vs. cross-encoder (slow, paired) trade-off, and the
  **retrieve-then-rerank** pattern that uses each where it fits.
- That rerank is **off by default**, fetches a larger candidate pool (`rerank_candidates`),
  and — when on — supplies the `relevance` value the refusal gate checks.
- That **filters** (`--book`, `--source`, langs) constrain *eligibility* before ranking, a
  different lever from scoring/boosts.
- That **source boosts** live in the retriever as score multipliers (default 1.0), ready for
  when the corpus holds more than printed text.

**That's Module 2.** You now know where vectors live (2.1), how they get there idempotently
(2.2), how a question fuses two searches into a ranked list with two distinct scores (2.3),
and how to sharpen and narrow that list (2.4). You also keep meeting one number — `relevance`
— that decides whether the system answers at all.

Next: **Module 3** is that decision. We open `generate/`: how retrieved passages become a
cited answer, and how the **default-deny gate** uses `relevance` to refuse rather than
fabricate. When you're ready, ask me to **build out Module 3**.
