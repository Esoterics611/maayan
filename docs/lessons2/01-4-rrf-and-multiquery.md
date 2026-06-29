# Lesson 1.4 — Fusing the nets: RRF + the drop-in retriever

> Module 1, Lesson 4 · ~18 min read + a hands-on (no backend required).
> The one question this answers: **once we have several queries, how do their results become
> one ranked list — and how does this slot into the system without touching `ask`, `develop`,
> or threads?**

We can now widen the net three ways (1.2–1.3). Each query returns its own ranked list. This
lesson merges them and — just as importantly — shows how the whole thing plugs in *invisibly*.

---

## RRF, again — now across queries, not vector types

You already met Reciprocal Rank Fusion in Course 1 (2.3), where it fused **dense vs. sparse**
results for one query. Here it does the same job one level up: fuse the result lists of
**several queries**. The math is identical and lives in
[retrieve/fuse.py](../../maayan/retrieve/fuse.py):

```python
fused[ref] += 1.0 / (rrf_k + rank)     # sum over every list the ref appears in
```

Each result contributes `1/(rrf_k + rank)` from each list it appears in (rank is 0-based,
`rrf_k=60`). A passage retrieved by **several** of your queries accumulates from each and rises;
one found by a single query still gets credit, but less. So fusion rewards exactly what you
want: sources that *multiple* phrasings agree are relevant.

It's pure and deterministic — deduped by `ref`, ties broken by `ref` ascending (same
reproducibility discipline as Course 1). No model, fully unit-tested in `tests/test_fuse.py`.

> ### Under the hood — RRF rewards agreement, sometimes surprisingly
> Because `rrf_k=60` is large, RRF is nearly linear: two appearances at rank 1 (`2/61`) can
> outscore one appearance at rank 0 (`1/60`). That's intentional — *consensus across queries* is
> a strong signal — but it means a chunk every variant retrieves in its mid-list can rise above
> a chunk one variant loved. If you ever want top-rank to dominate more, that's the `rrf_k`
> dial (smaller = top ranks matter more).

---

## Keeping the refusal gate honest: `relevance = max`

Here's the subtle part. The fused `score` is rank-based — RRF *always* ranks something first,
even for a nonsense question (Course 1, 2.3 taught you this). So the fused score **cannot** be
the number the default-deny gate checks. The `MultiQueryRetriever` handles this exactly right:

```python
for q in queries:
    sub = self._base.retrieve(q, ...)
    result_lists.append(sub.results)
    relevance = max(relevance, sub.relevance)      # absolute, per-variant
fused = rrf_fuse(result_lists, limit=k or self._top_k)
return RetrievalResult(results=fused, relevance=relevance)
```

It fuses the *ranked lists* for ordering, but carries **`relevance = the maximum absolute
relevance across the variants`** — i.e. "did *any* phrasing of the question find something
genuinely relevant?" That's the honest question for the gate, and it's still the absolute dense-
cosine measure from Course 1, never the RRF score. Expansion widens the net; it does **not**
lower the bar for answering.

---

## The drop-in: nothing downstream changes

`MultiQueryRetriever` implements the **same `Retrieving` protocol** as the base `Retriever`
(Course 1, Module 5 — program to the interface). It wraps a base retriever + an expander:

```
MultiQueryRetriever.retrieve(q)
   └─ expander.expand(q) → [q, variant1, …, HyDE, lexicon-aug]
   └─ for each: base.retrieve(...)         # the ordinary hybrid+rerank pipeline
   └─ rrf_fuse(lists)  +  relevance = max
```

Because it *is* a `Retrieving`, every caller — `RAGService.ask`, `DevelopmentService`, the
thread flow — uses it with **zero changes**. The factory decides which to build:

```python
# retrieve/factory.py
if not use_expand:
    return base                              # plain Retriever, exactly as Course 1
...
return MultiQueryRetriever(base, CompositeExpander(expanders, ...), top_k=resolved_top_k)
```

This is the DI payoff from Course 1 made concrete: a substantial new capability added behind an
existing seam, invisible to everything that depends on it.

---

## Hands-on

No backend needed — use lexicon-only expansion so it runs offline.

**1. Watch a fused source appear.** Compare the base retriever to the expanded one on your
Lesson 0.1 question (use one that mentions a lexicon term, so lexicon expansion fires):

```bash
uv run python - <<'PY'
from maayan.config import Settings
from maayan.retrieve.factory import build_retriever

s = Settings()
q = 'מהו ע"ב'                       # a query naming a term you've defined
base = build_retriever(s, expand=False)
expanded = build_retriever(s, expand=True)        # backend=None → lexicon-only

base_refs = [r.ref for r in base.retrieve(q, k=8).results]
exp_refs  = [r.ref for r in expanded.retrieve(q, k=8).results]
print("base    :", base_refs)
print("expanded:", exp_refs)
print("NEW in expanded:", [r for r in exp_refs if r not in base_refs])
print("base relevance vs expanded:",
      round(base.retrieve(q, k=8).relevance, 3),
      round(expanded.retrieve(q, k=8).relevance, 3))
PY
```

The "NEW in expanded" line is the source(s) the related-term family pulled in — quite possibly
the ref you marked missing in Lesson 0.1. Note the `relevance` numbers: expanded's is `max`
across variants, so it's `>=` base's — never lower.

**2. Confirm the drop-in.** Notice you never touched `ask` to get this — `build_retriever(...,
expand=True)` returned a different object behind the same `Retrieving` interface. That's the
whole trick.

---

## You should now be able to say…

- How RRF fuses several queries' results into one ranking, and why it rewards cross-query
  agreement (and the `rrf_k` caveat).
- Why the gate uses **`relevance = max` across variants** (absolute), never the rank-based fused
  score — expansion widens the net without lowering the bar.
- How `MultiQueryRetriever` drops in behind the `Retrieving` protocol so `ask`/`develop`/threads
  are unchanged — DI from Course 1, paying off.

Next: **[2.1 — One pass vs. two stages](02-1-one-pass-vs-two-stages.md)** — we move from finding
the sources to *thinking* about them.
