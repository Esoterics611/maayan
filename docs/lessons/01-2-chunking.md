# Lesson 1.2 — Chunking: the unit of retrieval

> Module 1, Lesson 2 · ~20 min read + a hands-on at the terminal.
> The one question this answers: **what, exactly, gets embedded and retrieved — a book? a
> sentence? — and who decides where one piece ends and the next begins?**

Lesson 1.1 turned *text* into a searchable vector. But text of what *size*? You don't embed
all of Tanya as one giant vector — you'd never be able to point at *which part* answered the
question. You embed **chunks**. Choosing what a chunk *is* turns out to be one of the most
consequential design decisions in any RAG system, and maayan makes a deliberate, opinionated
choice. This lesson is that choice.

---

## Why not just embed the whole book?

Imagine embedding an entire chapter of Likutei Torah as a single vector. Two problems:

1. **The vector becomes mush.** A long passage is "about" many things at once; averaging all
   of them into one point in meaning-space blurs it. A question about one fine point gets
   matched against a smudge, and retrieval gets worse.
2. **The citation becomes useless.** Even if it matched, the system could only tell you "it's
   somewhere in this chapter." The entire promise of maayan — *every claim traces to a
   source you can check* — dies if the source is ten paragraphs long.

So you retrieve **passages**, not books. A chunk has to be **small enough to be precise and
citable**, yet **large enough to carry a complete thought.** Where you draw that line is
*chunking.*

---

## The easy way (that maayan rejects)

The common, lazy approach is **fixed-size windows**: chop the text every N tokens (say, every
512), maybe with a little overlap. It's simple and it's what a lot of RAG tutorials do. But
for Torah it's wrong, because it cuts **across the meaning**:

- A window can split a single thought mid-sentence — half the idea in one chunk, half in the
  next, neither retrievable on its own.
- The boundaries are arbitrary, so a chunk's "citation" is "characters 1024–1536 of the
  file" — meaningless to a person. You couldn't open the sefer to it.

The text you're working with *already comes pre-divided into meaning-units* — by people, over
centuries, for exactly this purpose. A pasuk. An *os* (a lettered sub-section). A se'if. A
paragraph of Likutei Amarim. Throwing that structure away to impose a blind character count
is throwing away the most useful gift the source gives you.

---

## maayan's rule: one natural unit = one chunk

> **maayan chunks by the text's *own* structure. One segment — one pasuk / os / se'if /
> paragraph — becomes one chunk.** No fixed windows. The natural unit is preserved so that the
> chunk is both a coherent thought *and* a real, openable citation.

This is stated at the top of [maayan/corpus/chunker.py](../../maayan/corpus/chunker.py):
"chunk by the text's OWN structure — one segment = one chunk." Read that file; it's short.
The work happens in three small functions:

| Function | What it does |
|---|---|
| `segment_to_chunks` | one fetched segment → its chunk(s) — one per language present |
| `section_to_chunks` | one section (e.g. a chapter) → all its segments' chunks, in order |
| `sections_to_chunks` | many sections → one flat, ordered list |

Notice what `segment_to_chunks` does *not* do: no splitting, no merging, no windowing. It
normalizes the text (Lesson 1.3), and if anything survives, it emits **one chunk per language
that's actually present** (Hebrew and/or English) — skipping empties. A segment with Hebrew
and English yields two chunks; a Hebrew-only segment yields one. They're separate chunks
because they're separately searchable.

---

## The `Chunk` — the spine of the whole system

You met the chunk in Lesson 0.2 as "the thing that flows through every stage." Here it is for
real. Open [maayan/corpus/models.py](../../maayan/corpus/models.py) and read the `Chunk`
model:

| Field | What it is | Why it matters |
|---|---|---|
| `id` | a stable, derived id | makes re-ingest an **upsert**, not a duplicate (below) |
| `ref` | canonical citation, e.g. *"Tanya, Part I; Likkutei Amarim 1:1"* | **doubles as the human-readable source line** |
| `book` | e.g. *"Tanya"* | lets you filter retrieval by book (`--book`) |
| `section_path` | e.g. `["Chapter 1", "Paragraph 1"]` | the structural breadcrumb |
| `lang` | `"he"` or `"en"` | one language per chunk |
| `text` | the normalized text itself | what actually gets embedded |
| `source` | `"sefaria"` / `"expert"` / `"derived"` … | **provenance** — the seed of the capture loop (Module 6) |
| `metadata` | open dict | room to grow without schema churn |

The `ref` doing double duty — identity *and* citation — is the small, elegant idea that makes
grounded citations cheap: the thing you retrieve already knows how to name itself.

> ### Under the hood — why re-ingesting never duplicates
> Look at `chunk_id` at the top of `models.py`. A chunk's id is a **deterministic** hash of
> `(source, ref, lang)` — feed the same three in, get the same id out, every time. So when you
> re-ingest Tanya, each chunk lands on the *same* id it had before and **overwrites in place**
> instead of creating a second copy. That's *idempotency*, and it's why the [RUNBOOK](../RUNBOOK.md)
> can tell you to just re-run `ingest` without fear. (The store even resets a chunk's
> `indexed` flag if its text changed, so it gets re-embedded — that's Module 2.2.) The chunk
> is stored locally in SQLite by [store.py](../../maayan/corpus/store.py); the id is the
> primary key.

---

## Hands-on

You ingested two chapters of Tanya in Lesson 0.3. Let's look at the actual chunks that
produced. From the repo root (this reads the local SQLite store directly):

```bash
uv run python - <<'PY'
from maayan.config import Settings
from maayan.corpus.store import ChunkStore

store = ChunkStore(Settings().db_path)          # data/maayan.sqlite3
for c in store.get_chunks(limit=3):             # ordered by ref
    print("ref:         ", c.ref)
    print("  book/lang/src:", c.book, "/", c.lang, "/", c.source)
    print("  section_path:", c.section_path)
    print("  id:          ", c.id)
    print("  text[:80]:   ", c.text[:80])
    print()
print("total chunks in store:", store.count())
PY
```

1. **Read three chunks.** For each, confirm the four things that make it a good unit of
   retrieval: its `ref` is a citation you could *open a sefer to*; its `text` is a coherent
   piece (not cut mid-thought); its `section_path` shows where it sits; its `source` is
   `sefaria`. This is the shape of everything the system retrieves.

2. **Find the same passage in two languages (if present).** Pick a `ref` and re-query it:

   ```bash
   uv run python - <<'PY'
   from maayan.config import Settings
   from maayan.corpus.store import ChunkStore
   store = ChunkStore(Settings().db_path)
   ref = store.get_chunks(limit=1)[0].ref          # grab a real ref
   for c in store.get_by_ref(ref):
       print(c.lang, "->", c.id)
   PY
   ```

   If you ingested both languages you'll see two chunks, **same ref, different id** — because
   the id folds in `lang`. That's the idempotency rule from the box above, made visible.

3. **Prove idempotency yourself.** Note `store.count()` from step 1. Re-run the ingest from
   Lesson 0.3 (`uv run maayan ingest --book "Tanya, Part I; Likkutei Amarim" --limit 2`), then
   re-run step 1's count. It should be **unchanged** — same refs → same ids → upsert, not
   duplicate. (You'll watch the *indexing* side of this in Module 2.2.)

4. **Spot the design choice.** Look at your longest chunk and your shortest. They're
   different lengths — because they follow the *text's* divisions, not a fixed number. In a
   sentence, say why that's better here than cutting every 512 tokens.

---

## You should now be able to say…

- Why you retrieve **passages, not whole books** (precision *and* citability), and the
  size trade-off a chunk has to balance.
- Why maayan chunks by the text's **own** structure (one segment = one chunk) instead of
  fixed token windows — and what fixed windows would break.
- The fields of a `Chunk`, especially that `ref` is both its identity *and* its citation, and
  that `source` carries provenance.
- Why re-ingesting is safe: the deterministic `chunk_id` makes it an **upsert**.

Next: **[1.3 — Hebrew normalization (and what you deliberately don't do)](01-3-normalization.md)** —
before a segment becomes a chunk, its text is cleaned. We'll see exactly what gets stripped,
what's protected (nikkud), and the one transformation maayan refuses to do automatically.
