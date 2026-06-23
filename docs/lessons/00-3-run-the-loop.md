# Lesson 0.3 — Run it once, all the way

> Module 0, Lesson 3 · ~30–45 min, mostly hands-on · **this one you do at the terminal.**
> The one question this answers: **what does the whole pipeline actually feel like when it
> runs — including the moment it refuses?**

This is the keystone of Module 0. Everything in the rest of the curriculum refers back to
what you see here. Go slowly and actually run each step.

---

## Before you start

You need the repo set up with the embedding extra and the database running. If you've done
the [RUNBOOK §2](../RUNBOOK.md) setup already, skip to Step 1. Otherwise, from the repo root:

```bash
uv sync --extra ml --extra ui     # core + the embedding model deps + web UI
cp .env.example .env               # then open .env and set OPENROUTER_API_KEY=sk-or-...
make up                            # start the local Qdrant database (Docker) on :6333
```

> **No OpenRouter key yet?** You can still do most of this lesson. **Retrieval** (`search`)
> and the **refusal** path need no key — only a *grounded answer* (`ask` when sources are
> found) calls the cloud model. So you'll be able to see retrieval and a refusal regardless;
> the grounded-answer step (4) is the only one that needs the key.
>
> **No Docker?** Set `QDRANT_URL=:memory:` in `.env` to run the database in-process
> (it won't persist between commands, so do Steps 1–5 in one session, or use a file path —
> see RUNBOOK troubleshooting).

---

## Step 1 — Ingest a small slice of text

A full ingest pulls a *lot* over the network. For learning, grab just two chapters of Tanya
so everything is fast:

```bash
uv run maayan ingest --book "Tanya, Part I; Likkutei Amarim" --limit 2
```

**What just happened (Module 1 territory):** the ingester fetched the text, split it into
**chunks** by its own structure (one segment = one chunk), normalized the Hebrew (markup
out, nikkud kept), and saved the chunks to a local SQLite file. No embeddings yet — just the
raw text, chunked and stored.

---

## Step 2 — Index it (embed + store as vectors)

```bash
make index
```

> The first time you ever run this, it downloads the `bge-m3` embedding model (~2.3 GB).
> That's a one-time cost; later runs are fast.

**What just happened (Modules 1–2):** each chunk's text was turned into vectors — lists of
numbers that capture its meaning — and those were stored in the Qdrant database, ready to
search. Re-running `make index` now would do almost nothing, because indexing is
*idempotent*: it only embeds what's new. (Try it — run `make index` again and watch it find
nothing to do.)

---

## Step 3 — Retrieve (no model, no key) — *this is the "R"*

Now ask the database to find relevant passages. This is pure retrieval — no answer is
written, no cloud call happens:

```bash
uv run maayan search "שתי הנפשות" --book "Tanya" --k 3
```

You'll get back up to 3 passages, each with its `ref`, a `(lang/source)` tag, and a
relevance score. **Read them.** Notice that it found passages about the *two souls* even
though matching is by *meaning*, not exact words. That's the embedding from Step 2 doing its
job.

Try one more, in your own words:

```bash
uv run maayan search "ההבדל בין צדיק לבינוני" --book "Tanya" --k 3
```

> ### Under the hood — what is that score?
> Each result's score is roughly *how close, in meaning-space, the passage is to your
> question.* Higher = more relevant. Behind it, your question was embedded into the same kind
> of vector as the chunks, and the database found the nearest ones — by **meaning** (dense
> search) and **wording** (sparse search) together. The exact mechanism is Module 2; for now,
> just internalize: **a number that says how well this passage matches.** Remember it — the
> refusal in Step 5 hinges on it.

---

## Step 4 — Generate a grounded, cited answer — *the "A" + "G"* (needs a key)

Now the full thing. Ask a question the two chapters you ingested can actually answer:

```bash
uv run maayan ask "מה ההבדל בין צדיק לבינוני?"
```

You'll see three things:

1. **An answer** — composed in Hebrew, from the retrieved passages.
2. **A Sources list** — the refs it drew on, with cited ones marked. *Every claim traces to
   a source.* Spot-check one: find a citation (either a `[S#]` tag inside the answer text, or
   a marked ref in the Sources list) and match it back to the passage it came from.
3. **A Session id** — a handle for this exchange (it matters later, in the capture loop).

**What just happened:** retrieval ran (like Step 3), the passages were handed to the cloud
model with a strict instruction to answer *only* from them and cite each claim, and the
answer came back grounded. That instruction-and-grounding is Module 3.

---

## Step 5 — Watch it refuse — *the trust core*

Now the most important moment in the whole curriculum. Ask something your little corpus has
**no basis** to answer — use one of the questions you wrote in Lesson 0.1, or this:

```bash
uv run maayan ask "מהי נקודת הרתיחה של מים?"
```

*(That's "what is the boiling point of water?" — nothing in Tanya speaks to it.)*

Instead of inventing an answer, the system **refuses**: it prints `[refused]` followed by
the `DEFAULT_REFUSAL` text you found back in Lesson 0.1, and — this is the key — **it never
called the cloud model at all.**

Look closely at the output: under the refusal it prints **"(Closest, but below the relevance
threshold:)"** and lists a few passages. That's the gate showing its work — those *are* the
nearest passages retrieval could find, and the system is telling you, in plain text, "these
were the best I had, and none of them cleared the bar, so I will not answer." You're watching
the default-deny rule happen on screen.

> ### Under the hood — refusal is decided *before* the model is ever asked
> Open [maayan/generate/rag.py](../../maayan/generate/rag.py) and find the `ask` method.
> Near the top of it is the **default-deny gate** (look for the comment "DEFAULT-DENY"). In
> plain terms it says: *if there are no results, or the best relevance score is below
> `score_threshold`, return the refusal now — before building any prompt or calling the
> model.* That's what "enforced in code, not the prompt" means: the honesty isn't a polite
> request to the model, it's a locked door the model never gets to walk through. The score
> from Step 3 is exactly what this gate checks.

**Prove it to yourself** (optional but worth it): the threshold is a config knob. Open
[maayan/config.py](../../maayan/config.py) and find `score_threshold` (it's also settable as
`SCORE_THRESHOLD` in `.env`). Set it very low — say `0.0` — re-run the boiling-point
question, and watch the gate open: now it tries to answer from irrelevant passages, and the
result is exactly the kind of forced, ungrounded answer the gate exists to prevent. **Set it
back** when you're done. You just felt, in one knob, why the gate matters.

---

## What you just saw, mapped to the picture

```
Step 1 INGEST → Step 2 EMBED+INDEX → Step 3 RETRIEVE → Step 4/5 GENERATE-or-REFUSE
 corpus/         embed/ + index/      retrieve/         generate/
```

You pushed a real question through every box in the Lesson 0.2 diagram — and you saw the two
outcomes that define the system: a **grounded, cited answer** when the texts support it, and
an **honest refusal** when they don't.

The one box you *haven't* exercised yet is the **capture loop** (`capture/`) — turning a
scholar's correction into new searchable knowledge. That's the heart of Module 6, and now
you have a Session id (from Step 4) ready for it.

---

## Hands-on (record your answers — they anchor later modules)

1. **Contrast Step 4 and Step 5.** In one or two sentences: what was different about the two
   questions that made one get an answer and the other get a refusal? (Hint: it's not the
   topic — it's what retrieval found.)

2. **Read your own citations.** From Step 4, pick one cited source and open the actual ref
   (you can `search` for its text). Does the answer's claim honestly reflect what the source
   says? This habit — checking the citation — is the whole reason the system exists.

3. **The threshold experiment.** If you did the optional `score_threshold` change, write down
   what the boiling-point question returned at `0.0` vs. the normal value. What does that tell
   you about *why* the number isn't just `0`?

4. **One question that surprised you.** Ask one thing you genuinely wondered about the two
   Tanya chapters. Did it answer or refuse? Was that the *right* call? Note it.

If anything errored, the [RUNBOOK troubleshooting section](../RUNBOOK.md) covers the common
cases (missing key, threshold too high, no Docker).

---

## You should now be able to say…

- The full path a question travels: ingest → embed → index → retrieve → generate/refuse.
- The practical difference between **retrieval** (Step 3, no model) and **generation**
  (Step 4, the model).
- *Why* the system refused in Step 5 — the **default-deny gate** checks the relevance score
  and stops before the model is ever called.
- What `score_threshold` does, and why it isn't zero.

**That's Module 0.** You've seen the whole loop and met the idea that defines it. From here,
Module 1 opens the first box — how text becomes searchable *meaning* in the first place.

When you're ready, ask me to **build out Module 1**.
