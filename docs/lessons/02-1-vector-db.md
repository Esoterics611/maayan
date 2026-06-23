# Lesson 2.1 — Vector databases & the collection

> Module 2, Lesson 1 · ~15 min read + a hands-on at the terminal.
> The one question this answers: **once a passage is a vector, where does it actually live —
> and what gets stored next to it so the answer can cite it?**

Module 1 turned passages into vectors (dense + sparse) and decided what a passage *is* (a
chunk). This module is about the other half of the "R": **storing** those vectors somewhere
you can search fast, and **pulling back** the relevant few for a question. This lesson is the
storage. It's the box labeled `index/` in the Lesson 0.2 diagram.

---

## Why an ordinary database won't do

You could put your chunks in SQLite (you already do — that's the corpus store from Lesson
1.2). But SQLite can only answer questions like "give me the row where `ref = X`." It cannot
answer the question retrieval actually needs:

> "Of my thousands of 1024-number vectors, which handful point in *almost the same direction*
> as this query's vector?"

That's a *nearest-neighbor* search in high-dimensional space, and it's a specialized job. A
**vector database** is built for exactly it: store millions of vectors, and given a new one,
return the closest matches in milliseconds. maayan uses **Qdrant**, running locally (Docker,
or even in-process — recall "what runs where": the database is local).

---

## What Qdrant stores: vectors **plus a payload**

Here's the part people miss. A vector database doesn't just store bare numbers. Each entry —
Qdrant calls it a **point** — carries two things:

1. **The vectors** — what you search *by*.
2. **A payload** — arbitrary data you search *for* and display. For maayan, the payload is
   everything you need to **cite and show** the result without a second lookup.

Open [maayan/index/qdrant.py](../../maayan/index/qdrant.py) and read `chunk_payload`. The
payload is the chunk minus its vectors: `ref`, `book`, `section_path`, `lang`, `source`,
`text`, `metadata`. So when retrieval finds a nearby point, it *already has the citation*
(`ref`), the provenance (`source`), and the text to display — no round-trip to SQLite. That's
why an answer can footnote itself instantly.

| Part of a point | Comes from | Used for |
|---|---|---|
| dense vector (`"dense"`) | bge-m3 dense | meaning-based nearest-neighbor |
| sparse vector (`"sparse"`) | bge-m3 sparse | wording-based match |
| payload (`ref`, `text`, `source`, …) | the `Chunk` | citation, display, filtering |
| point **id** | the chunk's stable `chunk_id` | idempotent upsert (Lesson 2.2) |

---

## The collection: two named vectors in one place

In Qdrant, points live in a **collection** (think: one named table). maayan uses a single
collection — its name is config, `collection_name`, default `"maayan"`. Read the
`QdrantIndex.ensure_collection` method. Notice the schema it creates:

```python
vectors_config={ "dense": VectorParams(size=dim, distance=COSINE) }
sparse_vectors_config={ "sparse": SparseVectorParams() }
```

Two things to take away:

- **Named vectors.** Each point holds *two* vectors under two names — `"dense"` and
  `"sparse"` (the constants `DENSE_VECTOR` / `SPARSE_VECTOR` at the top of the file). Storing
  both, side by side, in one collection is what makes *hybrid* search possible later — you can
  query either, or fuse them (Lesson 2.3).
- **Cosine distance** for the dense vector. That's the same "angle between vectors" you
  measured by hand in Lesson 1.1 — Qdrant does it at scale. The dense `size` is config-driven
  (`embed_dim`, 1024), never hardcoded.

> ### Under the hood — local, ephemeral, or server: one knob
> `build_qdrant_client` reads `qdrant_url` and decides *where* the database is: an `http(s)`
> URL → talk to a Qdrant server (the Docker one from `make up`, default
> `http://localhost:6333`); `":memory:"` → an ephemeral in-process database that vanishes
> when the command ends (this is what the unit tests use — no Docker, per the house rules);
> any other string → a local on-disk path. Same code, three deployments, selected by config.
> This is the dependency-injection discipline (Module 5) reaching all the way down to the
> database.

Two more methods worth a glance now, because later lessons lean on them:
`recreate_collection` (drop + recreate — that's what `index --rebuild` calls) and
`delete_points` (remove points by id — that's how a *retraction* leaves retrieval, Module 6).

---

## Hands-on

You need Qdrant up and the corpus indexed (from Lesson 0.3: `make up`, then `make index`).
Let's look inside the collection. From the repo root:

```bash
uv run python - <<'PY'
from maayan.config import Settings
from maayan.corpus.store import ChunkStore
from maayan.index.qdrant import QdrantIndex, build_qdrant_client

s = Settings()
idx = QdrantIndex(build_qdrant_client(s), s.collection_name, s.embed_dim)
print("collection:", s.collection_name, "| points:", idx.count())

# Pull one real point's payload (by a chunk id from the store):
cid = ChunkStore(s.db_path).get_chunks(limit=1)[0].id
payload = idx.retrieve(cid)
for key in ("ref", "book", "lang", "source"):
    print(f"  {key:6}: {payload[key]}")
print("  text  :", payload["text"][:70], "…")
PY
```

1. **Count the points.** How many points are in the collection? Compare it to
   `store.count()` from Lesson 1.2. (They may differ if you ingested both languages, or
   re-indexed — that's fine; the point is they're in the same ballpark.) `make index` prints
   this same number at the end — confirm they agree.

2. **Read one payload.** Confirm it carries `ref`, `source`, and `text` — i.e. *everything
   needed to cite and display this result with no further lookup.* That self-sufficiency is
   the whole reason the payload exists. Which field would the final answer print as the
   footnote? (Answer: `ref`.)

3. **Find the two named vectors.** Re-open `ensure_collection` in `qdrant.py` and point to
   the exact lines that declare the `"dense"` and `"sparse"` vectors. In one sentence: why
   store both in the *same* collection instead of two separate databases?

---

## You should now be able to say…

- Why retrieval needs a **vector database** (fast nearest-neighbor search), not a plain
  table.
- That each Qdrant **point** carries vectors *and* a **payload**, and that maayan's payload is
  exactly what's needed to cite + display a result.
- That the collection holds **two named vectors** (`dense`, `sparse`) per point, with cosine
  distance on the dense one — the setup that makes hybrid search possible.
- That `qdrant_url` selects server / in-memory / on-disk with no code change.

Next: **[2.2 — The indexing pipeline](02-2-indexing-pipeline.md)** — how chunks actually get
*into* this collection, in batches, and why running it twice never creates a duplicate.
