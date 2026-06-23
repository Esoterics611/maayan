# Lesson 6.5 — Threads & the term lexicon

> Module 6, Lesson 5 · ~20 min, hands-on at the terminal.
> The one question this answers: **what holds a multi-step line of inquiry together over time,
> and how does the system protect a Holy Name from being treated as an abbreviation to expand?**

Two supporting structures finish the capture loop. **Threads** give a line of inquiry a spine —
so an ask, a seed, and its development read as one evolving conversation rather than scattered
records. The **lexicon** lets you define Holy Names and technical terms as first-class entities,
and — closing a loop opened back in Lesson 1.3 — *protects* them from the abbreviation expander.
Neither is the headline feature; both are what make the loop livable.

---

## Threads: a reopenable line of inquiry

Open [maayan/threads/models.py](../../maayan/threads/models.py). A **`Thread`** is "a single line
of inquiry that accumulates over many turns" — a reopenable, listable topic. A **`ThreadTurn`** is
one ordered event in it, and its `turn_type` is exactly the vocabulary of this module:

| `turn_type` | What it records |
|---|---|
| `ask` | a grounded RAG answer (Module 3) |
| `seed` | an expert contribution that opens an aspect (6.3) |
| `development` | a model development of a seed (6.3) |
| `refinement` | a follow-up note |
| `composition` | a composed document section (Module 8.3) |

So a thread literally narrates the loop: *ask → seed → development → (approve) → refinement.* You
saw threads created implicitly already — `maayan ask --topic`/`--thread` (Lesson 3.4) and `maayan
develop` (which records the seed as the opening turn, then appends the development). The
[ThreadService](../../maayan/threads/service.py) is small: `start_thread`, `add_turn`,
`get_thread_with_turns`, `list_threads`.

> ### Under the hood — threads feed context, but never grounding
> Recall Lesson 3.4: prior turns *interpret* a follow-up but are never citable. Threads are where
> those prior turns live. Read [threads/flow.py](../../maayan/threads/flow.py): `to_context_turns`
> maps persisted `ThreadTurn`s down to the citation-free `ContextTurn`s the generator accepts, and
> `ask_in_thread` feeds only the last `max_context_turns` as context. So a thread makes the
> conversation *persistent and reopenable* without ever weakening the trust core — retrieval still
> runs on the current question, default-deny still fires first. The `ThreadTurn` → `ContextTurn`
> mapping is the clean seam (Lesson 3.4's "decoupled on purpose") that keeps the generator
> independent of the thread layer.

---

## The lexicon: terms as entities, and Holy Names protected

Open [maayan/lexicon/models.py](../../maayan/lexicon/models.py). A **`Term`** is a curated entity:
a `canonical` display form, `surface_forms` (variants to match), a `term_type`
(`name`/`sefirah`/`partzuf`/`expansion`/`concept`/`other`), a `definition`, optional `gematria`
and `related_terms`, a required `author`, and a `sacred` flag marking a **Holy Name**. Defining
one (`maayan add-term`) creates a `source="term"` chunk (Lesson 6.1) — so a term's *meaning*
becomes retrievable, just like expert and derived knowledge.

But the lexicon does something the other sources don't, and it's the payoff of a thread left
hanging since Lesson 1.3. Recall: the normalizer has a `expand_rashei_teivot` hook that can expand
abbreviations, and it carries a `protected` set of folded surface forms it will **never** expand.
Where does that set come from? **The lexicon.**

Read `protected_terms` in [lexicon/service.py](../../maayan/lexicon/service.py): it returns the
folded surface forms of every registered term, to be used as the expander's deny-list. So a token
like **ע״ב** — which *looks* like rashei-teivot but is actually the *Ab* expansion of the
Tetragrammaton (gematria 72), a Holy Name — once registered as a term, becomes **structurally
unexpandable**. The model header in [lexicon/models.py](../../maayan/lexicon/models.py) says it
exactly: these "carry gershayim and *look* like rashei-teivot, but they are terms… not
abbreviations to expand."

> ### Under the hood — three lessons converge here
> This single mechanism ties together: (1) Lesson 1.3's `fold_surface` (terms are matched
> gershayim/nikkud-insensitively, so `ע״ב` / `ע"ב` / `עב` all register the same), (2) Lesson
> 1.3's `protected` parameter on `expand_rashei_teivot` (the deny-list), and (3) this module's
> provenance (`source="term"`, `author` required, `sacred` flag). The result: a Holy Name can be
> *defined* (its meaning retrievable) and *protected* (its form inviolable) at once. That's the
> system taking *sheimos* seriously — not as a guideline, but as a structural guarantee.

---

## Hands-on

Qdrant up, corpus indexed.

**1. Define a term — and protect a Holy Name.** Register a term with surface forms and the
`--sacred` flag:

```bash
uv run maayan add-term \
  --canonical 'ע"ב (שם הע"ב / Ab)' \
  --definition "מילוי שם הוי' ביודי\"ן, גימטריא 72 — מדרגת החכמה." \
  --author "Your Name" \
  --type expansion \
  --surface 'ע"ב' --surface 'עב' \
  --gematria 72 \
  --sacred
```

It prints the term id and **"Surface forms (protected from expansion): …"**. You've added a
`term` chunk *and* a protected form in one move.

**2. Confirm it's retrievable and protected.** Search the term source, then verify the protected
set includes your form:

```bash
uv run maayan search "שם הע\"ב חכמה" --source term --k 5
uv run python - <<'PY'
from maayan.config import Settings
from maayan.lexicon.factory import build_term_service
print("protected surface forms:", build_term_service(Settings()).protected_terms())
PY
```

Your folded surface forms appear in the protected set — these are exactly what
`expand_rashei_teivot` (Lesson 1.3) refuses to touch. The term is *defined* (retrievable) and
*inviolable* (protected) at once.

**3. See a thread narrate the loop.** If you ran the develop flow in Lessons 6.3–6.4, list your
threads and open one:

```bash
uv run maayan threads
uv run maayan thread <THREAD_ID>
```

Read the ordered turns: `seed → development → …`. The thread tells the story of how a piece of
knowledge grew. In one sentence: how does `to_context_turns` let a later `--thread` ask use this
history *without* making any of it citable?

---

## You should now be able to say…

- What a **Thread** / **ThreadTurn** is, the five turn types, and that threads feed *context*
  (via `to_context_turns`) but never *grounding*.
- What a lexicon **`Term`** is, that it becomes a `source="term"` chunk, and that the `sacred`
  flag marks a Holy Name.
- How the lexicon supplies the **`protected` deny-list** that makes Holy Names structurally
  unexpandable — closing the loop from Lesson 1.3.

**That's Module 6 — the differentiator.** You've run the full capture loop: provenance (6.1),
capturing a connection (6.2), seeding and developing (6.3), the human approval gate to derived
corpus (6.4), and the threads + lexicon that hold it together (6.5). This is the part that makes
maayan more than a search engine — it accumulates *reasoning*, attributed and retrievable.

Next: **Module 7** — running it for real: setup, the knobs that matter, swapping the backend,
growing the corpus, and the web UI. When you're ready, ask me to **build out Module 7**.
