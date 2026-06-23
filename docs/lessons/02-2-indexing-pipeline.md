# Lesson 2.2 — The indexing pipeline

> Module 2, Lesson 2 · ~15 min read + a hands-on at the terminal.
> The one question this answers: **how do chunks actually get from SQLite into Qdrant — and
> why can I re-run it a hundred times without duplicating anything?**

You have chunks in SQLite (Module 1) and an empty collection waiting in Qdrant (Lesson 2.1).
The **indexing pipeline** is the conveyor belt between them: read chunks → embed them → upsert
them as points. It's small — one function — but it embodies two house values you'll see
everywhere: **idempotency** and **doing only the work that's needed.**

---

## The pipeline in one function

Open [maayan/index/pipeline.py](../../maayan/index/pipeline.py) and read `index_chunks`. The
whole thing is a short loop:

```
chunks ← store.get_chunks(only_unindexed=True)      # what still needs doing
for each batch of chunks:
    embeddings ← embedder.embed([c.text ...])        # Module 1's bge-m3
    index.upsert_chunks(zip(chunks, embeddings))     # → Qdrant points
    store.mark_indexed([c.id ...])                   # remember we did these
return IndexResult(embedded, total_points)
```

Three deliberate moves hide in those lines:

1. **It works in batches** (`_batched`, size from `embed_batch_size`). Embedding is the
   expensive step; sending 16 passages to bge-m3 at once is far faster than 16 separate calls.
2. **It marks what it indexed.** After each batch is safely in Qdrant, `store.mark_indexed`
   flips those chunks' `indexed` flag to 1 in SQLite. The store now *remembers* they're done.
3. **It returns a typed result** (`IndexResult`), not a loose tuple — the boundary-is-a-model
   house rule again.

Notice what's *not* here: no model is constructed inside this function. The `store`,
`embedder`, and `index` are all **passed in** (injected). That's why the same pipeline runs
with real bge-m3 in production and the instant `HashingEmbedder` + in-memory Qdrant in tests.

---

## Incremental by default: only embed what's new

Look at the very first branch of `index_chunks`:

```python
if rebuild:
    index.recreate_collection()
    chunks = store.get_chunks()                 # everything
else:
    index.ensure_collection()
    chunks = store.get_chunks(only_unindexed=True)   # just the new/changed
```

The default path asks the store for **only the chunks not yet indexed**. So the *first*
`make index` embeds everything; the *second* finds nothing to do and is nearly instant. You
don't re-pay the embedding cost for text that hasn't changed. This is why the [RUNBOOK](../RUNBOOK.md)
treats `index` as a thing you just run whenever — it's cheap when there's nothing new.

> ### Under the hood — how does a *changed* chunk get re-embedded?
> Two stable facts cooperate. (1) A chunk's id is deterministic (Lesson 1.2), so a re-ingest
> lands on the *same* row. (2) In [store.py](../../maayan/corpus/store.py), `upsert_chunks`
> has a clever clause: on conflict it updates the row, and sets
> `indexed = CASE WHEN text changed THEN 0 ELSE indexed END`. So if you re-ingest and the
> text is *byte-identical*, `indexed` stays 1 and the next `index` skips it; if the text
> *changed*, `indexed` flips back to 0 and the next `index` re-embeds exactly that chunk.
> Incremental indexing is correct, not just fast — it never goes stale and never redoes
> settled work.

---

## Idempotency: why re-running never duplicates

This is the property worth internalizing. Run `index` once, twice, ten times — the collection
ends with the **same** points, never doubles. Two mechanisms guarantee it, one on each side:

| Side | Mechanism | Effect |
|---|---|---|
| Qdrant | `upsert_chunks` keys each point by the chunk's **stable id** | re-upserting an id **overwrites** that point, never appends |
| SQLite | the `indexed` flag + `only_unindexed` | a settled chunk isn't even *sent* to Qdrant again |

The id is the linchpin (you proved it deterministic in Lesson 1.2). Because the point id *is*
the chunk id, "insert this passage" and "I already have this passage" resolve to the same
point. There's no separate de-duplication step — idempotency falls out of using a meaningful,
stable id. (`--rebuild` is the deliberate escape hatch: it drops the whole collection first,
for when you change the embedding model or schema and *want* a clean re-embed.)

---

## Hands-on

Qdrant up, corpus indexed (Lesson 0.3). Let's *watch* incremental indexing and idempotency.

1. **Run it once more — and watch it find nothing.** You already indexed in Module 0. Run:

   ```bash
   uv run maayan index
   ```

   Read the output: `Chunks to index: 0` (or close to it) and `Embedded 0 chunks`. The point
   count is unchanged. Nothing was re-embedded, because nothing was unindexed. That's move #2
   from above, paying off.

2. **Re-ingest, then re-index — still no duplicates.** Re-ingest the same two chapters
   (identical text), then index again:

   ```bash
   uv run maayan ingest --book "Tanya, Part I; Likkutei Amarim" --limit 2
   uv run maayan index
   ```

   The ingest upserts the same ids (no new rows); the index again sees 0 unindexed. Confirm
   the collection's point count (from Lesson 2.1's snippet, or the line `index` prints) is
   **identical** to before. You just re-ran the whole front of the pipeline and changed
   nothing — that's idempotency.

3. **Force a full rebuild — same destination.** Now the escape hatch:

   ```bash
   uv run maayan index --rebuild
   ```

   This time it *does* re-embed everything (`Embedded N chunks`) — but the final point count
   lands on the **same N** as before. Same destination, more work. Write down when you'd
   actually want `--rebuild` (hint: you changed `embed_model`, or the collection schema).

---

## You should now be able to say…

- What the indexing pipeline does, in one breath: read chunks → embed in batches → upsert as
  points → mark indexed.
- Why it's **incremental** by default (only unindexed chunks) and how a *changed* chunk gets
  re-embedded (the `indexed`-reset clause in `upsert_chunks`).
- Why re-running is **idempotent** — stable point ids overwrite, and the `indexed` flag skips
  settled work — and what `--rebuild` is for.
- That every collaborator is injected, so the same pipeline runs in prod and in fast tests.

Next: **[2.3 — Hybrid retrieval & fusion (RRF)](02-3-hybrid-rrf.md)** — the points are in the
collection; now a question goes in and the relevant few come back. We'll see how dense and
sparse searches are *fused*, and meet the two different scores that matter.
