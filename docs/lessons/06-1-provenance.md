# Lesson 6.1 — Provenance & the source taxonomy

> Module 6, Lesson 1 · ~15 min read + a hands-on at the terminal.
> The one question this answers: **every chunk carries a `source` — what are the kinds, and why
> does the system insist on always knowing *who* made each piece of knowledge?**

You've reached the differentiator. Modules 0–5 built a *very good RAG system* — but other people
have built RAG. What makes maayan *yours* is the **capture loop**: a scholar's reasoning becomes
durable, retrievable, attributed knowledge in the same index as the printed text. The whole loop
rests on one field you met back in Lesson 1.2 — `Chunk.source` — so we start there.

---

## Why provenance is the foundation, not a detail

In Torah, *who said it* is inseparable from *what was said*. "The Alter Rebbe writes…" and "my
chavrusa suggested…" are different epistemic claims, and conflating them is a serious error. A
system that pools printed text and human conjecture into one undifferentiated blob would be
worse than useless — it would launder opinion as Torah.

So maayan refuses to forget where anything came from. **Every chunk carries a `source` tag**, and
retrieval, display, and the trust rules all key off it. This is also why printed text is
**immutable**: you never *edit* a `sefaria` chunk to add your insight — you add a *new* chunk
with *your* provenance beside it. The text stays the text; your contribution stays yours.

---

## The five sources

Open [docs/RUNBOOK.md](../RUNBOOK.md) §0 and read the provenance table. Five values:

| `source` | What it is | Who made it | Mutable? |
|---|---|---|---|
| `sefaria` | Printed text | Sefaria API (Tanya, Torah Or) | no — immutable |
| `chabad` | Printed text | chabadlibrary.org API (Likutei Torah) | no — immutable |
| `expert` | Your correction / **connection** / seed | **you** (named author) | it's yours |
| `derived` | An **approved** model development of a seed | the model, grounded in refs | gated by you |
| `term` | A lexicon entry (Holy Name / technical term) | **you** (named author) | yours |

The first two are *printed text* — pulled from external sources, never altered (the two
`sefaria`/`chabad` split exists only because Likutei Torah isn't on Sefaria; both are "the
text"). The last three are the loop: `expert` (what a scholar contributes, Lesson 6.2),
`derived` (what the model develops and a human approves, Lessons 6.3–6.4), and `term` (curated
lexicon entries, Lesson 6.5). **All five live in the same Qdrant collection and are retrieved
together** — but the system always knows, and shows, which is which.

> ### Under the hood — attribution is *enforced*, not requested
> It's not enough to *suggest* people attribute their work — the models make it structural. Open
> [capture/models.py](../../maayan/capture/models.py) and [lexicon/models.py](../../maayan/lexicon/models.py):
> both `Annotation` (a contribution) and `Term` have a `field_validator` on `author` that
> **rejects a blank author** — "no anonymous/default contributions." You *cannot* create an
> attributed-source chunk without saying who you are. Provenance isn't a nice-to-have logged off
> to the side; it's a precondition the type system refuses to skip. (The same care shows up in
> `derived`: a `Development` carries the seed's author, the model id, and the refs it was
> grounded on — full lineage, Lesson 6.4.)

---

## Retrieval growth, not model training

One more idea the RUNBOOK states and that reframes everything: when you "teach the Assistant,"
you are **inserting a new chunk into the knowledge base** — not retraining a model. The next
question simply *retrieves* your contribution alongside the text. That's why the whole loop runs
locally with no GPU training, and why it's instant: teaching = one more searchable, attributed
chunk. (Lesson 8.4 contrasts this with fine-tuning, and why retrieval-growth is the right
backbone.)

---

## Hands-on

1. **Read the taxonomy at the source.** Open [RUNBOOK §0](../RUNBOOK.md), read the five-row
   table and the paragraph under it ("retrieval growth, not model training"). Say each source's
   one-line meaning out loud.

2. **See which sources you have so far.** Every chunk in your store is tagged. Count them by
   source:

   ```bash
   uv run python - <<'PY'
   from maayan.config import Settings
   from maayan.corpus.store import ChunkStore
   print(ChunkStore(Settings().db_path).counts_by_source())
   PY
   ```

   Right now you'll likely see only `{'sefaria': N}` (and maybe `chabad`) — all printed text.
   By the end of this module you'll have added `expert`, `derived`, and `term` chunks and watched
   this dictionary grow. That growing dictionary *is* the loop.

3. **Find where the tag rides through the system.** Recall from Lesson 2.1 that the Qdrant
   payload includes `source`, and from Lesson 2.4 that `--source` filters on it. In one sentence:
   how does carrying `source` on every chunk let the system show provenance on an answer *and*
   let you boost human contributions in ranking (Module 7.2)?

4. **Confirm anonymity is impossible.** Try to break the attribution rule:

   ```bash
   uv run python - <<'PY'
   from maayan.capture.models import Annotation
   from datetime import datetime, UTC
   try:
       Annotation(id="x", session_id="s", timestamp=datetime.now(UTC),
                  author="   ", kind="connection", body="text")
   except Exception as e:
       print("rejected:", e)
   PY
   ```

   A blank author is rejected at construction. Provenance is not optional.

---

## You should now be able to say…

- Why provenance is foundational for Torah (who-said-it is inseparable from what-was-said), and
  why printed text is **immutable** — you add beside it, never edit it.
- The five `source` values, which are printed text vs. the capture loop, and that all five share
  one collection but stay distinguishable.
- That attribution is **enforced** by the models (author required), with full lineage on derived
  chunks.
- That teaching the system is **retrieval growth** (a new chunk), not model retraining.

Next: **[6.2 — Capture: an expert note becomes a retrievable chunk](06-2-capture.md)** — we make
the first non-printed chunk: take a scholar's connection and watch it become searchable knowledge
in the same index.
