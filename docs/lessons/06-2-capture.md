# Lesson 6.2 — Capture: an expert note becomes a retrievable chunk

> Module 6, Lesson 2 · ~25 min, hands-on at the terminal.
> The one question this answers: **how does a scholar's correction or connection actually become
> a searchable chunk that future questions retrieve — closing the loop?**

This is the lesson where the loop *closes* for the first time. In Lesson 0.3 you got a `Session`
id from every `ask` and were told it "matters later." Later is now. We'll take a real
contribution, attach it to a session, and watch it become an `expert` chunk that surfaces in
retrieval beside the printed text. The capture loop is the point of the whole system — and it's
about to run in your hands.

---

## The two records: Session and Contribution

Open [maayan/capture/models.py](../../maayan/capture/models.py). Two models:

- **`Session`** — a recorded `ask`: the question, the refs retrieved, the answer text. Every
  `ask` you run creates one (the CLI prints its id). It's the *anchor* a scholar reacts to.
- **`Annotation`** (a.k.a. `Contribution`) — an expert's note *on* a session: an `author`
  (required), a `kind` (`correction` / `connection` / `addition` / `objection`), a `body` (the
  knowledge itself), optional `linked_refs` (sources it ties together), and a free `move` tag
  (e.g. `"pasuk->concept"`).

The most valuable `kind` is usually `connection` — the cross-text link that the printed texts
don't make explicit and that today lives only in a scholar's head. "This passage in Tanya is the
root of that idea in Likutei Torah" is exactly the reasoning maayan exists to preserve.

---

## What `add_annotation` does — the loop, in four steps

Open [maayan/capture/service.py](../../maayan/capture/service.py) and read `add_annotation`. It
does four things, and the module docstring lists them as the loop:

1. **Validate + persist** the contribution (unknown `kind` rejected against the config-driven
   `allowed_kinds`; blank `author` rejected by the model).
2. **Convert it to chunk(s)** — `annotation_to_chunks` turns the note into one or more `Chunk`s
   with `source="expert"`.
3. **Persist those chunks** to the corpus store, **marked indexed** (so a future
   `index --rebuild` keeps them — they're real corpus now).
4. **Embed + upsert** them into the **same Qdrant collection** as the printed text.

After step 4, the contribution is retrievable. The next `ask` or `search` can pull it back
*alongside* Tanya — ranked by the same hybrid search, citable by the same `ref`. That's the loop:
a scholar's reasoning went in as words and came out as a searchable, attributed chunk. Nothing
was retrained; one chunk was added (Lesson 6.1).

> ### Under the hood — same collection, same retrieval, on purpose
> Notice `add_annotation` calls the *same* `self._index.upsert_chunks` you met in the indexing
> pipeline (Lesson 2.2), into the *same* collection. There is no separate "expert store" that
> retrieval has to also-check. An `expert` chunk is a first-class citizen of the index — which
> is precisely why tomorrow's question retrieves it without any special handling. The only thing
> that distinguishes it is its `source` tag (for display/provenance) and, optionally, a ranking
> boost (Module 7.2). All collaborators are injected (it shares the one embedder built in `ask`,
> per Lesson 5.1).

---

## Hands-on — close the loop yourself

Qdrant up, corpus indexed, OpenRouter key set. Follow [RUNBOOK §6](../RUNBOOK.md) if you want the
fuller walkthrough; here's the spine.

**1. Get a session to annotate.** Ask something, and note the `Session:` id it prints:

```bash
uv run maayan ask "מהי נפש הבהמית?"
# → ... Session: <SESSION_ID>
```

**2. Teach a connection.** Attach a contribution to that session. Use a real connection in your
own words, attributed to you, linking the sources it bridges:

```bash
uv run maayan annotate \
  --session <SESSION_ID> \
  --author "Your Name" \
  --kind connection \
  --body "נפש הבהמית שבתניא היא שורש המידות שמבוארות בהרחבה בלקוטי תורה — וזהו הקשר." \
  --ref "Tanya, Part I; Likkutei Amarim 1"
```

It prints `Recorded annotation … (connection) by Your Name.` and **"Indexed as an expert chunk —
it will now surface in retrieval."** The loop just closed.

**3. Prove it's retrievable.** Search for your idea — and filter to *only* expert sources to see
it isolated from the printed text:

```bash
uv run maayan search "נפש הבהמית שורש המידות" --source expert --k 5
```

Your contribution comes back, tagged `(he/expert)`. Now drop the filter and search again — it's
ranked *alongside* Tanya. You taught the system something, and it retrieved it. That's the
differentiator working.

**4. Watch the source counts grow.** Re-run the counter from Lesson 6.1:

```bash
uv run python - <<'PY'
from maayan.config import Settings
from maayan.corpus.store import ChunkStore
print(ChunkStore(Settings().db_path).counts_by_source())
PY
```

You now have an `expert` count where before there was only `sefaria`. Each contribution moves
that number.

---

## You should now be able to say…

- The two capture records — **`Session`** (the recorded ask) and **`Annotation`/`Contribution`**
  (an attributed note on it) — and the four `kind`s.
- The four steps of `add_annotation` (validate → convert → persist → embed+upsert) and that the
  result is a `source="expert"` chunk in the **same** collection as printed text.
- Why that means future questions retrieve a scholar's contribution with no special handling —
  the loop is retrieval growth.
- How to teach a connection and confirm it surfaces (`--source expert`).

Next: **[6.3 — Seeds vs. corrections, and the develop step](06-3-seeds-and-develop.md)** — not
every contribution is a finished thought. Some are *seeds*: knowledge plus a directive for the
model to develop, grounded in the corpus or honestly refused.
