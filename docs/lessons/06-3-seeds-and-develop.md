# Lesson 6.3 — Seeds vs. corrections, and the develop step

> Module 6, Lesson 3 · ~25 min, hands-on at the terminal.
> The one question this answers: **what if a scholar has a half-formed idea — knowledge plus
> "now work this out from the texts"? How does the system develop it without fabricating?**

Lesson 6.2's contributions were *finished* thoughts — a correction, a connection — that go
straight into the index. But sometimes a scholar has something looser: a framework, often drawn
from texts *outside* this corpus, plus an instruction: "develop this from the sources we have."
That's a **seed**, and the **develop** step is how maayan grows it — under the very same
default-deny discipline you learned in Module 3.

---

## A seed = knowledge + a directive (kept apart)

Look again at `Annotation` in [capture/models.py](../../maayan/capture/models.py). Two fields
make a contribution a seed:

- **`directive`** — the "now develop X" instruction (e.g. "trace how this plays out across the
  three garments").
- **`opens_aspect`** — marks it as a seed that leads a new line of inquiry.

The crucial design choice is that the **`directive` is kept separate from the `body`**. Read the
field comment: the directive "is kept SEPARATE from `body` so it never pollutes the
embedded/retrievable text." The `body` is *knowledge* (it gets embedded and is retrievable); the
`directive` is an *instruction to the model* (it never becomes searchable text). Mixing them
would poison retrieval with imperative noise. Two different things, two different fields.

---

## The develop step mirrors RAG — same gate, new verb

Open [maayan/develop/service.py](../../maayan/develop/service.py). Read the module docstring:
"The shape mirrors `RAGService` on purpose — same default-deny discipline, same citation hygiene,
a new verb." The `develop` method:

1. **Retrieves fresh** on the seed (`body` + `directive` together — that's `_build_query`).
2. **DEFAULT-DENY gate** — *the same gate from Lesson 3.3*: if `relevance < score_threshold`,
   it returns a refusal `Development` with **no model call**. Read it
   ([service.py](../../maayan/develop/service.py)): `if not sources or retrieval.relevance <
   self._settings.score_threshold:` → refuse. The corpus simply doesn't support the seed, and the
   system says so honestly.
3. **Otherwise the model develops it** — and here's the citation hygiene: the prompt puts the
   **SEED as a non-citable framework** ("attribute it, never cite it as a source") and the
   retrieved **SOURCES as the only citable evidence**. The development cites **only** retrieved
   sources, never the seed.

If that structure feels familiar, it should — it's exactly the grounded-prompt + default-deny
pattern of Module 3, pointed at a seed instead of a question. The seed plays the role the
*conversation context* played in Lesson 3.4: it shapes *what* gets developed, but it can't be
cited and can't open the gate.

> ### Under the hood — an honest refusal is a *result*, not an error
> Read the `Development` model ([develop/models.py](../../maayan/develop/models.py)). It carries
> `grounded: bool` — and `grounded=False` means "the develop step honestly refused because the
> corpus doesn't support the seed." A refusal isn't a crash or an empty string; it's a
> first-class, persisted outcome with its own provenance (`model=""` records that no model was
> called). The system would rather tell you "I can't ground this seed in what we have — ingest
> more text or refine the seed" than force a connection that isn't there. That's the trust core,
> reused: even *creative* development refuses rather than fabricates.

And — important — a development is a **PROPOSAL** (`status="proposed"`), persisted and appended to
its thread, but **not yet corpus**. It is not indexed and not retrievable until a human approves
it. That gate is Lesson 6.4.

---

## Hands-on — plant a seed and develop it

Qdrant up, full Tanya indexed (so there's something to ground in), OpenRouter key set.

**1. Get a session, then plant a seed on it.** Ask, note the `Session:` id, then annotate with a
`--directive` and `--opens-aspect`:

```bash
uv run maayan ask "מהם שלושת הלבושים של הנפש?"
# → Session: <SESSION_ID>

uv run maayan annotate \
  --session <SESSION_ID> \
  --author "Your Name" \
  --kind addition \
  --opens-aspect \
  --body "הלבושים מחשבה דיבור ומעשה הם שלושה כלים לאותה נפש." \
  --directive "פתח כיצד שלושת הלבושים פועלים בעבודת הבינוני."
```

Note the printed contribution id, and the line confirming the **directive is kept out of the
embedded text**. That id is your *seed id*.

**2. Develop the seed.** Hand the seed to the develop step:

```bash
uv run maayan develop --seed <CONTRIBUTION_ID>
```

Read the output: a developed passage, a **"Grounded in:"** list (the refs retrieved for it), a
**"Cited:"** list (the refs it actually cited), and a `Development … (status=proposed)` line with
**"A proposal — not indexed as corpus yet."** plus an `Approve it: maayan approve <id>` hint. Note
that **every citation is a corpus ref**, never your seed — confirm the seed text isn't cited.

**3. Force an honest refusal.** Now plant a seed the corpus *can't* support (e.g. a directive
about a topic absent from Tanya) and develop it:

```bash
# annotate a seed whose directive is off-corpus, grab its id, then:
uv run maayan develop --seed <OFF_CORPUS_SEED_ID>
```

You'll get `[refused]` with the develop-refusal text — and, as in Module 3, **no model was
called** (the `Development` records `model=""`). The creative step refuses just like the answer
step does. That symmetry is the whole point: maayan grounds or refuses, never fabricates,
*everywhere*.

---

## You should now be able to say…

- What distinguishes a **seed** from a correction/connection: a `directive` (kept separate from
  `body`, so it never pollutes retrievable text) and `opens_aspect`.
- That **develop mirrors RAG**: retrieve → same default-deny gate → grounded, cited generation,
  with the seed as non-citable framework and only sources citable.
- That an **honest refusal is a first-class result** (`grounded=False`, `model=""`) — the corpus
  didn't support the seed, and no model was called.
- That a development is a **proposal**, not yet corpus, until approved.

Next: **[6.4 — The approval gate → derived corpus](06-4-approval-gate.md)** — why a model's
development stays a proposal until a human says yes, and what happens to lineage when you approve.
