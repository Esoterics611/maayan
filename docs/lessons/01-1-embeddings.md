# Lesson 1.1 — Embeddings & vector space

> Module 1, Lesson 1 · ~20 min read + a hands-on at the terminal.
> The one question this answers: **how does a computer tell that two pieces of Torah are
> about the same thing — even when they share no words?**

In Module 0 you watched `search` find passages about the *two souls* without you typing the
exact words from the text. That worked because of the idea in this lesson. It is the "R" in
RAG, one layer down: before you can *retrieve* by meaning, you have to *turn meaning into
something a computer can measure.* That something is an **embedding**.

---

## The problem: a computer can't read Hebrew (or anything)

A computer compares numbers, not ideas. It has no notion that *נפש הבהמית* (the animal soul)
and *נפש האלקית* (the divine soul) are related, while *נפש הבהמית* and "the boiling point of
water" are not. To it, those are just strings of bytes. Keyword search (Lesson 0.1, Option B)
papers over this by matching *characters* — which is why it breaks the moment the wording
changes, a synonym appears, or the question is phrased differently than the source.

We need a way to put **meaning itself** into a form the computer can do arithmetic on. That
is exactly what an embedding model does.

---

## What an embedding is

> An **embedding** is a piece of text turned into a list of numbers (a **vector**),
> positioned so that *similar meaning lands nearby* and *different meaning lands far apart.*

Picture every passage as a point in space. Not 2-D space — a space with **1024 dimensions**
(that's the size bge-m3 uses; you can't picture it, but the math works the same as on a
sheet of paper). Passages about the divine soul cluster in one region; passages about
*tzimtzum* cluster in another; a sentence about the stock market lands somewhere else
entirely. "Related" becomes a thing you can *measure* — the distance, or angle, between two
points.

That's the whole trick. Once meaning is a position in space:

- "Find passages about this question" becomes "find the points nearest this question's point."
- "Are these two ideas related?" becomes "how small is the angle between their vectors?"

The model that does the placing — that reads Hebrew and decides *where in the space* a
passage belongs — is the **embedding model**. maayan uses one called **`bge-m3`**, which is
multilingual and handles Hebrew well. It runs **on your machine** (recall the "what runs
where" table from Lesson 0.2 — embedding is local).

> ### Under the hood — how does it know where to put things?
> `bge-m3` is a neural network trained on an enormous amount of multilingual text. During
> training it saw words and passages in context, over and over, and adjusted itself until
> text that *behaves similarly* (appears in similar contexts, gets used in similar ways)
> ended up with similar vectors. Nobody handed it a dictionary of "soul ≈ neshama"; it
> learned the geometry from usage. This is why it can match a question to a passage that
> never repeats your words: it's comparing *positions*, which encode meaning, not spelling.

---

## Two kinds of vector, from one model

Here's a subtlety that matters for your system. `bge-m3` produces **two** representations of
each passage in a single pass:

| Vector | What it captures | Good at | Blind to |
|---|---|---|---|
| **Dense** | *Meaning* — the 1024-number position-in-space | synonyms, paraphrase, cross-language | exact rare words, names |
| **Sparse** | *Wording* — which specific terms appear, and how important each is | a precise term, an unusual word, a name | meaning when the words differ |

The **dense** vector is the "meaning-space position" we just described. The **sparse**
vector is closer to a smart keyword signal: a long list that is mostly zeros, with a weight
on each term that actually appears (hence "sparse" — almost empty). It shines exactly where
dense vectors are weak: a specific, rare term like a particular sefer's name or a technical
word that *must* match.

Neither is enough alone. Dense can drift toward "vaguely related"; sparse can miss a
paraphrase completely. **Using both** — which is why maayan stores both — lets a question
match on meaning *and* on wording. Combining them is the subject of Module 2 (it's called
*hybrid search*); for now just hold that one model hands you two complementary signals, and
that's deliberate.

---

## Where this lives in your system

Open [maayan/embed/base.py](../../maayan/embed/base.py) and read the two small classes:

- **`Embedding`** — the data that comes out: `dense` (a list of 1024 floats),
  `sparse_indices` + `sparse_values` (the parallel lists that *are* the sparse vector — an
  index says *which* term, a value says *how strongly*). That's a passage's meaning and
  wording, as numbers.
- **`Embedder`** — a *protocol* (an interface): anything that can `embed(texts)`,
  `embed_query(text)`, and report its `dim` counts as an embedder. The real one is
  [`BGEM3Embedder`](../../maayan/embed/bgem3.py); there's also a fake, dependency-free
  [`HashingEmbedder`](../../maayan/embed/fake.py) used in tests.

> ### Under the hood — why a *protocol*, and why a fake?
> Notice nothing in retrieval says "use bge-m3." It says "use *an* `Embedder`," and
> [factory.py](../../maayan/embed/factory.py) picks the concrete one from config
> (`embed_backend`). That's the dependency-injection house rule (Module 5) showing up early:
> because the embedder is swappable, tests can inject `HashingEmbedder` — which fakes vectors
> from token hashes, instantly, with no 2 GB model download — and exercise the whole pipeline
> offline. The fake is **not** semantically meaningful (it only knows shared tokens, not
> meaning); it exists so tests are fast and the network stays mocked, per the house rules. You
> never use it for real retrieval.

Two config knobs worth knowing (in [maayan/config.py](../../maayan/config.py)):
`embed_model` (`BAAI/bge-m3`) and `embed_dim` (`1024`). They're config, not hardcoded —
that's the rule.

---

## Hands-on

Let's *see* meaning become distance. This loads `bge-m3` (already downloaded in Lesson 0.2)
and compares four Hebrew phrases — two about the soul, one about boiling water, one about the
stock market. From the repo root:

```bash
uv run python - <<'PY'
import itertools, math
from maayan.config import Settings
from maayan.embed.factory import build_embedder

emb = build_embedder(Settings())          # bge-m3, local (loads once, ~10s on CPU)
phrases = {
    "two-souls":    "שתי הנפשות שיש בכל איש מישראל",
    "animal-soul":  "נפש הבהמית שמקורה מקליפת נוגה",
    "boiling-water":"נקודת הרתיחה של מים היא מאה מעלות צלזיוס",
    "stock-market": "מדד המניות עלה היום בבורסה",
}
vecs = {k: e.dense for k, e in zip(phrases, emb.embed(list(phrases.values())))}

def cosine(a, b):                          # +1 = same direction (meaning), 0 = unrelated
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
    return dot / (na * nb)

for x, y in itertools.combinations(phrases, 2):
    print(f"{cosine(vecs[x], vecs[y]):+.3f}   {x:<14} ⇄ {y}")
PY
```

**Read the numbers.** The score is *cosine similarity* — roughly "how close in
meaning-space," from +1 (same direction) down toward 0 (unrelated). You should see
`two-souls ⇄ animal-soul` score clearly **higher** than `animal-soul ⇄ stock-market`, even
though those soul phrases don't repeat each other's words. That gap *is* the embedding doing
its job — the same job that made `search` work in Module 0.

1. **Which pair scored highest? Lowest?** Write them down. Did the ranking match your own
   sense of which phrases are "about the same thing"?

2. **Add your own pair.** Edit the snippet: add a phrase you'd expect to be close to
   `two-souls` (say, something about *neshama* or *Israel*) and one you'd expect to be far.
   Re-run. Were you right? Where the model surprised you is where you're learning what it
   keys on.

3. **(Optional) Feel the difference a real model makes.** Re-run with the *fake* embedder:
   put `EMBED_BACKEND=hashing` in front of the command
   (`EMBED_BACKEND=hashing uv run python - <<'PY' ... PY`). It runs instantly and the
   soul-pair may still score high — but only because those phrases happen to share tokens,
   *not* because it understands them. Change a phrase to a synonym with no shared words and
   watch the fake fall apart while bge-m3 wouldn't. That contrast is *why* you run a real
   embedding model.

---

## You should now be able to say…

- What an embedding is: text → a vector, placed so **similar meaning = nearby**.
- Why this beats keyword matching: it compares *positions* (meaning), not characters.
- The difference between the **dense** vector (meaning) and the **sparse** vector (wording),
  and that `bge-m3` produces both in one pass — which is what later enables *hybrid* search.
- Where it lives: the `Embedder` protocol and `Embedding` model in `maayan/embed/`, with a
  real bge-m3 implementation and a fake for tests.

Next: **[1.2 — Chunking: the unit of retrieval](01-2-chunking.md)** — *what* gets embedded.
You don't embed a whole book; you embed one natural unit at a time. We'll see why, and why
maayan refuses to chop text into arbitrary windows.
