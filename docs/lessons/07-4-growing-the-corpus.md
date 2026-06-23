# Lesson 7.4 — Growing the corpus

> Module 7, Lesson 4 · ~20 min, hands-on at the terminal.
> The one question this answers: **how do I add more text to the system — both the easy case (it's
> on Sefaria) and the hard case (it isn't)?**

A RAG system is only as good as what it can retrieve. Eventually you'll want more than the
starter corpus. This lesson is how you grow it: the common path (a Sefaria book — pure config) and
the adapter path (a source Sefaria doesn't have). It also reinforces a theme from Module 5 — adding
a *Sefaria* book touches **no code**, because the book list is config.

---

## Two kinds of source

Recall the provenance taxonomy (Lesson 6.1): printed text is either `sefaria` or `chabad`. That
split exists for exactly this reason — **not everything is on Sefaria**. The flagship example is
in your corpus already: Likutei Torah isn't on Sefaria at all (the Hebrew Wikisource copy is an
empty stub), so it's pulled from chabadlibrary.org. So "grow the corpus" has two paths:

| Path | When | What you change |
|---|---|---|
| **Sefaria book** | the text is on Sefaria | add a string to `config.books` — **no code** |
| **Non-Sefaria** | it isn't (e.g. Likutei Torah) | use/extend the chabad adapter |

---

## The easy path: add a Sefaria book (config only)

Open [config.py](../../maayan/config.py) and find `books` — a `list[str]` of Sefaria refs (Tanya
Part I, and all the Torah Ohr parsha nodes). To add a book, you add its ref to that list (or
ingest it ad hoc with `--book`). Then ingest + index:

```bash
uv run maayan ingest --book "Torah Ohr, Toldot"     # one book, ad hoc
make index                                           # embed the new chunks (incremental)
```

That's the whole operation. The ingester fetches the text, chunks it by its own structure (one
segment = one chunk, Lesson 1.2), normalizes it (Lesson 1.3), and stores it; `index` embeds only
the new chunks (idempotent, Lesson 2.2). No new code — adding a book is *data*, not *logic*, which
is the config-driven rule (Lesson 5.3) paying off.

> **A gotcha worth knowing** (from the config comment): a Sefaria ref must resolve to a flat
> `chapters: [int, …]` shape — verify with `GET /api/shape/<title>`. Whole-book refs with nested
> parshiyot won't ingest; you point at the *node* (e.g. `"Torah Ohr, Toldot"`), not the umbrella.

---

## The adapter path: a source Sefaria doesn't have

When a text isn't on Sefaria, you can't just add a string — you need an *adapter* that knows how
to fetch and walk that source's API. maayan has one for chabadlibrary.org:
[maayan/corpus/chabad.py](../../maayan/corpus/chabad.py), driven by `config.chabad_books` (a map of
book name → root section id) and `config.chabad_base_url`. Ingesting uses a different command:

```bash
uv run maayan ingest-chabad        # walks chabadlibrary.org's JSON API for Likutei Torah
make index
```

> ### Under the hood — why a separate adapter, and sentence-aware chunking
> chabadlibrary.org has a different API shape than Sefaria (a tree walked by section id,
> brotli-encoded JSON), so it needs its own fetch/parse code — but it produces the *same*
> `Chunk` model, so everything downstream (embed, index, retrieve, cite) is identical. One extra
> wrinkle: Likutei Torah sections can be very long, so the chabad ingester splits a long section
> at **sentence boundaries** into coherent passages (`config.chabad_chunk_chars`, default ~1000;
> refs get a `… §2` suffix) for retrieval precision — short sections stay whole. This is the
> chunking principle from Lesson 1.2 adapted to a source whose "natural unit" is sometimes too
> big to retrieve well. The rate-limited fetching uses the injected `Clock` (Lesson 5.4), so it's
> polite to the server and testable without waiting.

Both paths converge on the same store and the same collection — once ingested and indexed, a
chabad chunk is retrieved exactly like a sefaria one, distinguished only by its `source` tag.

---

## Hands-on

Qdrant up.

**1. Add a Sefaria book ad hoc.** Pick a Torah Ohr parsha you haven't ingested and add it:

```bash
uv run maayan ingest --book "Torah Ohr, Vayera"
make index
```

Then confirm it's searchable and tagged by its book:

```bash
uv run maayan search "אברהם" --book "Torah Ohr, Vayera" --k 3
```

You grew the corpus with zero code changes — just data.

**2. See the book counts.** Use the store's by-book counter:

```bash
uv run python - <<'PY'
from maayan.config import Settings
from maayan.corpus.store import ChunkStore
print(ChunkStore(Settings().db_path).counts_by_book())
PY
```

Your new book appears with its chunk count beside Tanya.

**3. Read the two ingest commands.** Skim the `ingest` and `ingest-chabad` commands in
[cli.py](../../maayan/cli.py). In one sentence: why does a non-Sefaria source need a *different
command* but produce the *same* `Chunk`? (Hint: different fetch, same downstream.)

**4. (Optional) Grow with chabad.** If you want Likutei Torah, run `uv run maayan ingest-chabad`
then `make index`. Note in the output how a long section becomes multiple `… §N` chunks — the
sentence-aware split from the box above.

---

## You should now be able to say…

- The two paths to grow the corpus: **a Sefaria book (config only, no code)** vs. **a non-Sefaria
  source (an adapter)** — and why the `sefaria`/`chabad` provenance split exists.
- That adding a Sefaria book is *data*, not *logic* (the config-driven rule), with the
  flat-`chapters`-shape gotcha.
- That the chabad adapter fetches differently but yields the **same `Chunk`**, with **sentence-
  aware sub-chunking** for long sections.
- That both converge on one store/collection, distinguished only by `source`.

Next: **[7.5 — The web UI as a thin layer](07-5-web-ui.md)** — the browser front end, and how its
routes wire to the services you've been driving from the CLI and nothing more.
