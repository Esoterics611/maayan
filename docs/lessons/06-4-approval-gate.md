# Lesson 6.4 — The approval gate → derived corpus

> Module 6, Lesson 4 · ~20 min, hands-on at the terminal.
> The one question this answers: **why is a model's development only a *proposal* until a human
> approves it — and what exactly happens, with what lineage, when you say yes?**

In Lesson 6.3 the develop step produced a grounded `Development` — but it stopped at
`status="proposed"` and was *not* indexed. This lesson is the gate between "the model suggested
this" and "this is now part of our knowledge." It's a small amount of code with a large amount of
principle: **model output is a proposal until a human approves it.**

---

## Why a human gate at all

The develop step is already grounded and cited (Lesson 6.3) — so why not index it automatically?
Because "grounded in the sources" and "correct, worthy Torah" are not the same thing. A
development can cite real passages and still:

- misread what they say,
- draw a connection that's technically supported but not *right*,
- or phrase something in a way a scholar wouldn't endorse.

Grounding prevents *fabrication*; it does not guarantee *quality*. The only judge of quality is a
person. So maayan treats every development as a **proposal** and inserts a human approval gate
before it becomes retrievable knowledge. This is the same philosophy as default-deny (Module 3),
moved one level up: the system is conservative about what it lets become "truth," and it puts a
human in the loop at the decision that matters.

---

## Approve vs. reject

Open [maayan/develop/service.py](../../maayan/develop/service.py) and read the two methods:

```python
def approve(self, development_id):
    dev = self._require(development_id)
    if not dev.grounded:
        raise ValueError("Cannot approve an ungrounded development (it was a refusal).")
    approved = dev.model_copy(update={"status": "approved"})
    self._store.save_development(approved)
    self._index_derived(approved)        # ← now it becomes corpus
    return approved

def reject(self, development_id):
    rejected = ... model_copy(update={"status": "rejected"})
    self._store.save_development(rejected)
    return rejected                       # ← indexes NOTHING; corpus unchanged
```

Three things to notice:

1. **Approve indexes; reject does not.** `approve` calls `_index_derived`; `reject` touches the
   index not at all ("Indexes nothing — the corpus is unchanged"). The default state is *not in
   the corpus*; approval is the deliberate act that admits it.
2. **You cannot approve a refusal.** If `grounded=False` (the develop step refused, Lesson 6.3),
   `approve` raises. There's nothing to admit — the system already said the corpus doesn't support
   it. The gate can't be tricked into indexing an ungrounded claim.
3. **Approval creates a `derived` chunk.** `_index_derived` calls `development_to_chunk` →
   `source="derived"` → persists it (marked indexed) and embeds + upserts it into the same Qdrant
   collection. Now it's retrievable, beside the text and the expert chunks — the fifth source
   from Lesson 6.1, finally created.

> ### Under the hood — full lineage travels with the derived chunk
> Re-read the `Development` model ([develop/models.py](../../maayan/develop/models.py)). An
> approved development carries everything needed to answer "where did this come from?": `seed_id`
> (which seed), `author` (whose seed — carried so the derived chunk attributes the human, not the
> model), `model` (which model generated it), `thread_id` (which line of inquiry), `cited_refs`
> (what it cited), and `grounded_in` (what was retrieved for it). So a `derived` chunk is never
> an orphan claim — it's a fully traceable artifact: *this human's seed, developed by this model,
> grounded in these refs, approved.* That lineage is what lets you trust a derived chunk the way
> you trust a cited answer — you can always walk it back to its sources and its author.

---

## Hands-on — approve, then re-ask

Continue from Lesson 6.3 (you have a grounded `Development` with `status=proposed`).

**1. Approve it.** Use the development id from the develop output:

```bash
uv run maayan approve <DEVELOPMENT_ID>
```

It flips to `approved` and indexes a `derived` chunk. (Had you wanted to discard it instead:
`uv run maayan reject <DEVELOPMENT_ID>` — which would index nothing.)

**2. Watch the corpus grow a `derived` source.** Re-run the counter:

```bash
uv run python - <<'PY'
from maayan.config import Settings
from maayan.corpus.store import ChunkStore
print(ChunkStore(Settings().db_path).counts_by_source())
PY
```

You should now see `derived` in the dictionary, beside `sefaria` and `expert`. All five-ish
sources of Lesson 6.1 are becoming real in your own store.

**3. Re-ask and see it retrieved.** Search just the derived source, then ask a question the
development bears on:

```bash
uv run maayan search "עבודת הבינוני בשלושת הלבושים" --source derived --k 5
uv run maayan ask "כיצד פועלים שלושת הלבושים בעבודת הבינוני?"
```

Your approved development can now surface as a source — *grown from a scholar's seed, grounded in
the corpus, approved by a human, and retrieved like any other chunk.* That full circle — seed →
develop → approve → retrieved — is the capture loop at its richest.

**4. Try to approve a refusal (and watch it refuse you).** If you produced an ungrounded
development in Lesson 6.3, try `uv run maayan approve <ITS_ID>`. It errors: you can't approve
what was never grounded. The gate protects the corpus from ungrounded claims by construction.

---

## You should now be able to say…

- Why model output is a **proposal until a human approves** it — grounding prevents fabrication,
  but only a person judges quality.
- That **approve** indexes a `derived` chunk while **reject** changes nothing, and that an
  **ungrounded** development *cannot* be approved.
- That an approved `derived` chunk carries **full lineage** (seed, author, model, thread, cited
  and grounded-in refs) — a traceable artifact, not an orphan claim.
- That the full loop is **seed → develop → approve → retrieved**.

Next: **[6.5 — Threads & the term lexicon](06-5-threads-and-lexicon.md)** — the two supporting
structures: persistent topic threads that hold a line of inquiry together, and the lexicon that
protects Holy Names from being mangled.
