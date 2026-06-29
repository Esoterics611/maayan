# Lesson 1.1 — Why a verbatim query under-retrieves

> Module 1, Lesson 1 · ~12 min read + a hands-on.
> The one question this answers: **why isn't embedding the question once and searching good
> enough — what does a single query systematically miss?**

Course 1, Lesson 1.1 taught you that an embedding places text in a space where *similar meaning
= nearby*. That's true, and it's why retrieval works at all. This lesson is about its blind
spot — the gap that query expansion (the rest of Module 1) exists to close.

---

## One question is one point in space

When you ask, the retriever does this, once:

```python
emb = self._embedder.embed_query(query)   # retrieve/retriever.py
```

Your whole question collapses to a **single** dense vector (plus a sparse one). Retrieval then
returns the passages nearest *that one point*. Everything hangs on your exact phrasing landing
near the passages that answer it.

For many questions it does. For conceptual ones, it often doesn't — and here's why.

---

## The vocabulary-mismatch problem

The passage that answers a deep question frequently shares **no surface words** with the
question, and may not even state the relationship you're asking about:

- You ask about a *relationship* ("מה הקשר בין…"). The source never says "relationship"; it just
  discusses idea A in one place and idea B in another, and a scholar knows they connect.
- You use a common word; the text uses an abbreviation, an Aramaic synonym, or a Kabbalistic
  term of art for the same concept.
- You ask in English; the answer is in Hebrew (or vice versa). `bge-m3` is multilingual, which
  helps — but cross-language matches still sit *farther apart* than same-language ones.

Each of these pushes the answer's vector **away** from your question's vector. A single search
ranks by that one distance, so a genuinely-relevant passage can land at rank 12 — past your
`top_k` — and simply never be seen. The generator can't cite what retrieval didn't return.

> ### Under the hood — hybrid search helps, but doesn't solve this
> You already fuse dense (meaning) and sparse (wording) search (Course 1, 2.3). Sparse catches
> exact shared terms, which mitigates *some* mismatch. But when the question and answer share
> *neither* meaning-vector proximity *nor* literal words — the conceptual case — both halves of
> hybrid search miss together. The fix isn't a better single query; it's **more than one
> query**.

---

## The reframe: don't search smarter, search *wider*

If any *one* phrasing is a narrow net, cast several. Rephrase the question; inject the precise
term; even draft a hypothetical answer and search with that. Each casts the net around a
slightly different point in space, and together they cover the region where the real answer
lives. Then fuse the catches.

That's the whole of Module 1:

- **1.2** — generative widening (multi-query + HyDE),
- **1.3** — deterministic widening with your lexicon,
- **1.4** — fusing the catches (RRF) and wiring it in transparently.

---

## Hands-on

Reuse the conceptual question and the "expected but missing" ref you noted in Lesson 0.1.

**1. Confirm the miss, and find its cause.** Run the question and also a query using the
*words you'd expect the source itself to use*:

```bash
uv run maayan search "מה הקשר בין צמצום לבריאת העולם" --k 10
uv run maayan search "צמצום אור אין סוף מקום פנוי" --k 10
```

The second query — phrased like the *source*, not like a *question* — likely surfaces passages
the first missed, higher up. That delta is the vocabulary-mismatch problem in your own corpus:
same information need, different words, different results.

**2. Note the asymmetry.** Pick a passage you know well and search once with a paraphrase and
once with a near-quote of it. The near-quote ranks it higher. Real users ask in paraphrase —
which is exactly why we need to manufacture the near-quote phrasings ourselves (next two
lessons).

---

## You should now be able to say…

- Why a single query is a **single point** in vector space, and retrieval ranks by distance to
  it.
- The **vocabulary-mismatch** problem: conceptual questions share neither proximity nor words
  with their answers, so relevant passages fall past `top_k`.
- Why hybrid search mitigates but doesn't solve it, and why the fix is **searching wider** (many
  queries), not searching smarter (one better query).

Next: **[1.2 — Multi-query & HyDE](01-2-multiquery-hyde.md)** — the generative way to widen the
net.
