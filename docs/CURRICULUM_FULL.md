<style>
@page {
  size: A4;
  margin: 22mm 20mm 20mm 20mm;
}
:root { --ink: #15323b; --teal: #0f766e; --deep: #0b3b46; --accent: #b45309; --muted: #5b6b70; }

html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body {
  /* FreeSerif & Noto carry full Hebrew + nikkud; the browser/UBA handles bidi. */
  font-family: "FreeSerif", "Noto Serif Hebrew", "Noto Serif", "DejaVu Serif", Georgia, serif;
  font-size: 11.5pt;
  line-height: 1.5;
  color: var(--ink);
  max-width: 46rem;
  margin: 0 auto;
}

h1, h2, h3, h4 { line-height: 1.25; break-after: avoid; }
h1 { color: var(--deep); font-size: 25pt; margin: 0 0 .2em; }
h2 { color: var(--teal); font-size: 18pt; border-bottom: 2px solid var(--teal); padding-bottom: .15em; }
h3 { color: var(--deep); font-size: 13.5pt; }
h4 { color: var(--muted); font-size: 12pt; text-transform: none; }

p, li { orphans: 2; widows: 2; }
a { color: var(--teal); text-decoration: none; }

/* "Under the hood" / aside callouts (lesson blockquotes). */
blockquote {
  border-left: 3px solid var(--accent);
  background: #fbf6ee;
  margin: 1em 0;
  padding: .5em 1em;
  color: #3a3a3a;
  break-inside: avoid;
}
blockquote h3, blockquote h4 { color: var(--accent); margin-top: .2em; }

code {
  font-family: "DejaVu Sans Mono", "Courier New", monospace;
  font-size: 9.5pt;
  background: #eef4f3;
  padding: .08em .3em;
  border-radius: 3px;
}
pre {
  background: #f4f7f7;
  border: 1px solid #d8e3e1;
  border-radius: 5px;
  padding: .7em .9em;
  overflow-wrap: break-word;
  white-space: pre-wrap;
  break-inside: avoid;
  font-size: 9.5pt;
}
pre code { background: none; padding: 0; font-size: 9.5pt; }

table { border-collapse: collapse; width: 100%; font-size: 10.5pt; break-inside: avoid; }
th, td { border: 1px solid #cdd9d7; padding: .35em .55em; text-align: left; vertical-align: top; }
th { background: #e8f1ef; color: var(--deep); }

hr { border: none; border-top: 1px solid #d8e3e1; margin: 1.4em 0; }

.page-break { break-before: page; page-break-before: always; }

/* Title page. */
.title-page { text-align: center; padding-top: 22vh; }
.title-page .mark { font-size: 64pt; color: var(--teal); margin: 0; line-height: 1; }
.title-page .wordmark { font-size: 30pt; letter-spacing: .06em; color: var(--deep); margin: .1em 0 0; }
.title-page .tagline { font-size: 15pt; color: var(--ink); margin: 1.2em auto .2em; max-width: 32rem; }
.title-page .sub { font-size: 12pt; color: var(--muted); }
.title-page .brand { margin-top: 3.5em; font-size: 13pt; color: var(--teal); letter-spacing: .12em; }
.title-page .meta { font-size: 10pt; color: var(--muted); margin-top: .3em; }

/* Table of contents. */
.toc h1 { font-size: 20pt; color: var(--deep); }
.toc ul { list-style: none; padding-left: 0; }
.toc .mod { font-weight: bold; color: var(--deep); margin-top: .7em; }
.toc .les { padding-left: 1.4rem; color: var(--ink); }
.toc a { color: inherit; }

.module-goal { color: var(--muted); font-style: italic; margin: .2em 0 1.2em; }
</style>


<div class="title-page">
<p class="mark">מעיין</p>
<p class="wordmark">maayan</p>
<p class="tagline">Learning maayan — a hands-on path through RAG</p>
<p class="sub">A self-study curriculum for the owner of an esoteric-Torah Retrieval-Augmented Generation system.</p>
<p class="brand">maayan.ai</p>
<p class="meta">Modules 0–8 &middot; 35 lessons &middot; 2026-06-23</p>
</div>


<div class="page-break"></div>


<div class="toc">
<h1>Contents</h1>
<ul>
<li class="mod"><a href="#module-0">Module 0 — Orientation: the whole loop in your hands</a></li>
<li class="les"><a href="#lesson-0-1">Lesson 0.1 — What RAG is, and the problem it solves</a></li>
<li class="les"><a href="#lesson-0-2">Lesson 0.2 — The maayan thesis in one picture</a></li>
<li class="les"><a href="#lesson-0-3">Lesson 0.3 — Run it once, all the way</a></li>
<li class="mod"><a href="#module-1">Module 1 — Turning text into searchable meaning (embeddings &amp; chunking)</a></li>
<li class="les"><a href="#lesson-1-1">Lesson 1.1 — Embeddings &amp; vector space</a></li>
<li class="les"><a href="#lesson-1-2">Lesson 1.2 — Chunking: the unit of retrieval</a></li>
<li class="les"><a href="#lesson-1-3">Lesson 1.3 — Hebrew normalization (and what you deliberately don't do)</a></li>
<li class="mod"><a href="#module-2">Module 2 — Finding the right passages (vector DB &amp; hybrid search)</a></li>
<li class="les"><a href="#lesson-2-1">Lesson 2.1 — Vector databases &amp; the collection</a></li>
<li class="les"><a href="#lesson-2-2">Lesson 2.2 — The indexing pipeline</a></li>
<li class="les"><a href="#lesson-2-3">Lesson 2.3 — Hybrid retrieval &amp; fusion (RRF)</a></li>
<li class="les"><a href="#lesson-2-4">Lesson 2.4 — Reranking &amp; filters</a></li>
<li class="mod"><a href="#module-3">Module 3 — The trust core (generation, grounding, default-deny)</a></li>
<li class="les"><a href="#lesson-3-1">Lesson 3.1 — The generation backend (a swappable box)</a></li>
<li class="les"><a href="#lesson-3-2">Lesson 3.2 — The grounded prompt &amp; citations</a></li>
<li class="les"><a href="#lesson-3-3">Lesson 3.3 — Default-deny: the rule that lives in code, not the prompt</a></li>
<li class="les"><a href="#lesson-3-4">Lesson 3.4 — Context-aware follow-ups without losing grounding</a></li>
<li class="mod"><a href="#module-4">Module 4 — Knowing if it's actually good (evaluation)</a></li>
<li class="les"><a href="#lesson-4-1">Lesson 4.1 — Why eval exists, and the metrics</a></li>
<li class="les"><a href="#lesson-4-2">Lesson 4.2 — Running and reading the harness</a></li>
<li class="les"><a href="#lesson-4-3">Lesson 4.3 — Gold sets &amp; honest measurement</a></li>
<li class="mod"><a href="#module-5">Module 5 — How it's built to last (the engineering spine)</a></li>
<li class="les"><a href="#lesson-5-1">Lesson 5.1 — Dependency injection: why nothing constructs its own collaborators</a></li>
<li class="les"><a href="#lesson-5-2">Lesson 5.2 — Typed throughout, pydantic at every boundary</a></li>
<li class="les"><a href="#lesson-5-3">Lesson 5.3 — Config-driven everything</a></li>
<li class="les"><a href="#lesson-5-4">Lesson 5.4 — The Clock, and testing without the network</a></li>
<li class="mod"><a href="#module-6">Module 6 — The differentiator (the capture &amp; develop loop)</a></li>
<li class="les"><a href="#lesson-6-1">Lesson 6.1 — Provenance &amp; the source taxonomy</a></li>
<li class="les"><a href="#lesson-6-2">Lesson 6.2 — Capture: an expert note becomes a retrievable chunk</a></li>
<li class="les"><a href="#lesson-6-3">Lesson 6.3 — Seeds vs. corrections, and the develop step</a></li>
<li class="les"><a href="#lesson-6-4">Lesson 6.4 — The approval gate → derived corpus</a></li>
<li class="les"><a href="#lesson-6-5">Lesson 6.5 — Threads &amp; the term lexicon</a></li>
<li class="mod"><a href="#module-7">Module 7 — Running it for real (operating &amp; tuning)</a></li>
<li class="les"><a href="#lesson-7-1">Lesson 7.1 — Setup &amp; dependencies</a></li>
<li class="les"><a href="#lesson-7-2">Lesson 7.2 — The knobs that matter</a></li>
<li class="les"><a href="#lesson-7-3">Lesson 7.3 — Choosing &amp; swapping the generation backend</a></li>
<li class="les"><a href="#lesson-7-4">Lesson 7.4 — Growing the corpus</a></li>
<li class="les"><a href="#lesson-7-5">Lesson 7.5 — The web UI as a thin layer</a></li>
<li class="mod"><a href="#module-8">Module 8 — The horizon (extending it well)</a></li>
<li class="les"><a href="#lesson-8-1">Lesson 8.1 — Reading quality and improving it</a></li>
<li class="les"><a href="#lesson-8-2">Lesson 8.2 — Phase 4: the eraser &amp; measurement</a></li>
<li class="les"><a href="#lesson-8-3">Lesson 8.3 — Phase 5: composition</a></li>
<li class="les"><a href="#lesson-8-4">Lesson 8.4 — When (and when not) to fine-tune</a></li>
</ul>
</div>

<div class="page-break"></div>


<a id="module-0"></a>


# Module 0 — Orientation: the whole loop in your hands


<p class="module-goal">See the entire system work once, end to end, and hold a mental map before zooming in.</p>

<div class="page-break"></div>


<a id="lesson-0-1"></a>


## Lesson 0.1 — What RAG is, and the problem it solves

> Module 0, Lesson 1 · ~15 min read + a short hands-on · no setup required.
> The one question this answers: **why does this system exist at all, instead of just
> asking a chatbot?**

---

### Start with the failure you're trying to avoid

Imagine a chavrusa with a perfect memory of style but a shaky memory of fact. Ask him
anything and he answers immediately, fluently, in beautiful lashon — and he will *never*
say "I don't know." If he's unsure, he invents. He'll give you a maareh makom that sounds
exactly right — "Likutei Torah, Parshas Vayikra" — and it may be completely made up.

That chavrusa is a **large language model** (LLM) — the thing behind ChatGPT and the
"generation" step of maayan. It is astonishing at producing fluent, plausible text. But on
its own it has a fatal flaw for Torah study: **it fabricates sources with total
confidence.** In our world, inventing a mareh makom isn't a small error — it's the one
thing that makes a tool untrustworthy. If you can't trust a citation, you can't trust
anything it says.

So the whole problem this system solves is: **how do you get the fluency of that chavrusa
without the fabrication?**

> #### Under the hood — why does it invent?
> An LLM is, mechanically, a very sophisticated *next-word predictor*. It was trained on a
> huge amount of text and learned the patterns of how language flows. It does **not** have a
> database of facts it looks things up in. When you ask it for a source, it doesn't *retrieve*
> a source — it *generates* the most statistically plausible-looking source-shaped string.
> Usually that's wrong. The fabrication isn't a bug you can scold out of it; it's what the
> machine fundamentally does. This is why "please don't hallucinate" in a prompt never fully
> works — and why maayan enforces honesty in *code* instead (you'll see that in Lesson 0.3).

---

### Three ways to answer a question (only one is good enough)

**Option A — Ask the model alone.** Fluent, instant, and it fabricates mekoros. ✗

**Option B — Keyword search.** Like a search box over the texts. It can *find* passages
that contain your words, but it can't *answer* a question, can't handle synonyms or Hebrew
phrasing it didn't expect, and gives you a pile of results to sift yourself. It's honest but
not helpful. ✗

**Option C — Retrieval-Augmented Generation (RAG).** Do both, in order:

1. **Retrieve** the real passages that bear on the question — from your actual texts.
2. **Augment** the model: hand it *those passages* and nothing else.
3. **Generate** an answer that draws **only** from what you handed it, citing each claim.

That's the whole idea, and that's literally what the letters mean: **R**etrieval-**A**ugmented
**G**eneration. The model keeps its fluency, but it's no longer improvising from memory —
it's writing from sources you put in front of it, the way a talmid writes from the open
sefer on the table, not from what he half-remembers.

---

### The twist that makes it trustworthy

Here's the part most chatbots *don't* do, and the part maayan treats as sacred:

> **If retrieval finds nothing that actually supports an answer, the system refuses —
> it does not answer at all.**

No sources on the table → no answer. Not a guess, not a "well, generally speaking…" — a
plain "I don't have a source for this." That refusal is the feature, not a limitation. A
tool that knows when to stay silent is a tool you can trust when it *does* speak.

You'll meet the exact line of code that enforces this in Lesson 0.3. For now, just hold the
shape: **RAG = retrieve real sources → answer only from them, with citations → refuse when
there are none.**

---

### Where this lives in your system

Open docs/OVERVIEW.md and read the section **"What exists today"** (the
four numbered steps). Notice that those four steps *are* RAG:

| OVERVIEW step | RAG name | What it does |
|---|---|---|
| 1. It holds the source texts | (the corpus) | the texts, kept as natural units |
| 2. It finds the relevant passages | **Retrieval** | search by meaning, in Hebrew |
| 3. It answers only from what it found, with citations — or declines | **Augmented Generation + refusal** | the trust core |
| 4. It captures the scholar's contribution | (the loop) | what makes it *yours* — later modules |

Steps 1–3 are RAG, universal to any such system. Step 4 is maayan's own idea. This whole
first stretch of the curriculum (Modules 0–4) is about steps 1–3; Modules 5–8 are about
step 4 and running it all.

---

### Hands-on

You don't need anything running for this one — it's about seeing the idea in your own repo.

1. **Read the refusal in its own words.** Open maayan/generate/rag.py
   and find the text named `DEFAULT_REFUSAL` (near the top). Read it aloud. *That* string is
   what the system says when it has no source. You don't need to understand the surrounding
   code yet — just locate it. (Tip: search the file for `DEFAULT_REFUSAL`.)

2. **Name two questions you'd *want* it to refuse.** Write down two questions that your
   corpus (Tanya + Torah Or + Likutei Torah) genuinely has no basis to answer — e.g. a
   halachic question, or something about a text you haven't ingested. These are the cases
   where refusal is the *correct* answer. Keep this list; you'll test one in Lesson 0.3.

3. **One-sentence summary.** In your own words, finish this sentence: "RAG is better than
   asking a chatbot because ______, and it's better than keyword search because ______."

---

### You should now be able to say…

- Why an LLM alone can't be trusted for citations (it generates plausible text, it doesn't
  look facts up).
- What the three letters R-A-G actually stand for, and the order they happen in.
- Why **refusal** is a feature, not a flaw — and that maayan enforces it in code, not just
  by asking the model nicely.

Next: **0.2 — The maayan thesis in one picture** — the full
pipeline, stage by stage, and the loop that makes this system yours.

<div class="page-break"></div>


<a id="lesson-0-2"></a>


## Lesson 0.2 — The maayan thesis in one picture

> Module 0, Lesson 2 · ~15 min read + a short hands-on · no setup required.
> The one question this answers: **what are all the moving parts, and how do they fit
> together?**

---

### The whole system as one sentence

> maayan **ingests** your texts, **embeds** them into searchable meaning, **indexes** them
> in a local database, **retrieves** the relevant passages for a question, **generates** a
> grounded and cited answer (or refuses) — and then **captures** how a scholar corrects and
> connects sources, feeding that back in as new searchable knowledge.

Read that twice. Every folder in `maayan/` is one of those verbs. Once you can see the
pipeline, the codebase stops being a maze and becomes a straight line.

---

### The pipeline, stage by stage

```
        ┌─────────┐   ┌────────┐   ┌────────┐   ┌──────────┐   ┌──────────┐
TEXTS → │ INGEST  │ → │ EMBED  │ → │ INDEX  │ → │ RETRIEVE │ → │ GENERATE │ → ANSWER
        └─────────┘   └────────┘   └────────┘   └──────────┘   └──────────┘
         corpus/       embed/       index/       retrieve/      generate/
                                                                     │
                                        ┌────────────────────────────┘
                                        ▼
                                   ┌──────────┐
                          EXPERT → │ CAPTURE  │ ── becomes a new searchable chunk ──┐
                                   └──────────┘                                     │
                                    capture/                                        │
                                        └───────────────────────────────────────────┘
                                          (the loop: tomorrow's question retrieves it)
```

| Stage | Folder | In plain words | Curriculum module |
|---|---|---|---|
| **Ingest** | `corpus/` | Pull the texts, break them into natural units (a chapter, a passage) | Module 1 |
| **Embed** | `embed/` | Turn each passage into a list of numbers that captures its *meaning* | Module 1 |
| **Index** | `index/` | Store those number-vectors in a local database (Qdrant) you can search fast | Module 2 |
| **Retrieve** | `retrieve/` | Given a question, pull back the handful of passages that bear on it | Module 2 |
| **Generate** | `generate/` | Write a cited answer from *only* those passages — or refuse | Module 3 |
| **Capture** | `capture/` | Record a scholar's correction/connection as a new searchable chunk | Module 6 |

Two more folders are the *glue*: `config.py` (every tunable number lives here, never
hardcoded) and `cli.py` (the command-line entry that wires the pieces together). You'll meet
those properly in Module 5.

---

### The one thing that flows through all of it: the *chunk*

Every stage above passes the same object down the line — a **chunk**: one natural unit of
text (a Tanya chapter segment, a passage of Likutei Torah) plus its identity. If you
understand the chunk, you understand the spine of the whole system.

> #### Under the hood — what's in a chunk
> A `Chunk` carries: `ref` (its canonical citation, e.g. *"Tanya, Chapter 1:3"* — which
> doubles as the human-readable source line), `book`, `text` (the Hebrew/English itself),
> `lang`, and — crucially — `source`: *where this knowledge came from*. `source="sefaria"`
> is printed text; `source="expert"` is a scholar's contribution; `source="derived"` is
> something the model developed and a human approved. Same database, same retrieval — but the
> system always knows, and shows, the provenance. That `source` field is the seed of the
> entire "capture loop" idea. You'll work with the chunk directly in Module 1.

---

### The loop is the point (everything else is plumbing)

Steps ingest → generate are "just" a good RAG system — impressive, but other people have
built RAG. What makes maayan *yours* is the **capture loop**:

A scholar reads an answer, corrects it or draws a connection the printed texts don't make
explicit — and that contribution gets folded back in as a new, **attributed**, searchable
chunk. The next question can retrieve it *alongside* the printed text. Over time the system
accumulates not just texts, but **the reasoning that links them** — which today lives only
in a few people's heads.

docs/OVERVIEW.md says it well: "The texts are common property; what is
scarce, and what we are trying to preserve, is the expert's reasoning over them." Hold onto
that — it's the *why* behind Modules 6 and 8.

---

### What runs where (and why it matters)

Almost everything runs **on your machine**: the database, the embedding model, all the app
code, the web UI. Only **one** step reaches the cloud — the final generation call (composing
the answer), which goes to OpenRouter. And even that is swappable for a fully-local model
(Ollama). So your texts and your scholars' contributions never have to leave your laptop.

| Concern | Where it runs |
|---|---|
| Database, embeddings, retrieval, UI, all logic | **Local** |
| Final answer composition only | **Cloud** (OpenRouter) — or local Ollama |

This is a deliberate design value, not an accident. You'll see it pay off in Module 7 when we
swap the cloud model for a local one without changing a single line of logic.

---

### Hands-on

1. **Match folders to the pipeline.** In a terminal at the repo root, list the modules:

   ```bash
   ls maayan/
   ```

   For each of these — `corpus`, `embed`, `index`, `retrieve`, `generate`, `capture` — say
   out loud which pipeline verb it is. (Answer key is the table above. The extra folders you
   see — `develop`, `threads`, `lexicon`, `eval`, `ui` — are later additions; you'll meet
   each in its module.)

2. **Find the house rule that enforces refusal.** Open CLAUDE.md and read
   the **"House rules"** list. One rule is titled *"Default-deny on generation."* Read it.
   That single rule is the contract behind the refusal you found in Lesson 0.1 — and it says
   the rule is enforced *in code, not just in the prompt*. (Why that phrasing matters is the
   heart of Lesson 0.3.)

3. **Draw it from memory.** Close this file and, on paper or in a note, draw the pipeline:
   six boxes left to right, plus the capture loop curving back. If you can reproduce it, you
   own the map.

---

### You should now be able to say…

- The six stages of the pipeline, in order, and which folder each lives in.
- What a *chunk* is and why its `source` field matters.
- Why the **capture loop** — not the RAG plumbing — is what makes this system valuable.
- What runs locally vs. in the cloud, and why that's a deliberate choice.

Next: **0.3 — Run it once, all the way** — you'll push a real
question through every box above and watch it both *answer* and *refuse*.

<div class="page-break"></div>


<a id="lesson-0-3"></a>


## Lesson 0.3 — Run it once, all the way

> Module 0, Lesson 3 · ~30–45 min, mostly hands-on · **this one you do at the terminal.**
> The one question this answers: **what does the whole pipeline actually feel like when it
> runs — including the moment it refuses?**

This is the keystone of Module 0. Everything in the rest of the curriculum refers back to
what you see here. Go slowly and actually run each step.

---

### Before you start

You need the repo set up with the embedding extra and the database running. If you've done
the RUNBOOK §2 setup already, skip to Step 1. Otherwise, from the repo root:

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

### Step 1 — Ingest a small slice of text

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

### Step 2 — Index it (embed + store as vectors)

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

### Step 3 — Retrieve (no model, no key) — *this is the "R"*

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

> #### Under the hood — what is that score?
> Each result's score is roughly *how close, in meaning-space, the passage is to your
> question.* Higher = more relevant. Behind it, your question was embedded into the same kind
> of vector as the chunks, and the database found the nearest ones — by **meaning** (dense
> search) and **wording** (sparse search) together. The exact mechanism is Module 2; for now,
> just internalize: **a number that says how well this passage matches.** Remember it — the
> refusal in Step 5 hinges on it.

---

### Step 4 — Generate a grounded, cited answer — *the "A" + "G"* (needs a key)

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

### Step 5 — Watch it refuse — *the trust core*

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

> #### Under the hood — refusal is decided *before* the model is ever asked
> Open maayan/generate/rag.py and find the `ask` method.
> Near the top of it is the **default-deny gate** (look for the comment "DEFAULT-DENY"). In
> plain terms it says: *if there are no results, or the best relevance score is below
> `score_threshold`, return the refusal now — before building any prompt or calling the
> model.* That's what "enforced in code, not the prompt" means: the honesty isn't a polite
> request to the model, it's a locked door the model never gets to walk through. The score
> from Step 3 is exactly what this gate checks.

**Prove it to yourself** (optional but worth it): the threshold is a config knob. Open
maayan/config.py and find `score_threshold` (it's also settable as
`SCORE_THRESHOLD` in `.env`). Set it very low — say `0.0` — re-run the boiling-point
question, and watch the gate open: now it tries to answer from irrelevant passages, and the
result is exactly the kind of forced, ungrounded answer the gate exists to prevent. **Set it
back** when you're done. You just felt, in one knob, why the gate matters.

---

### What you just saw, mapped to the picture

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

### Hands-on (record your answers — they anchor later modules)

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

If anything errored, the RUNBOOK troubleshooting section covers the common
cases (missing key, threshold too high, no Docker).

---

### You should now be able to say…

- The full path a question travels: ingest → embed → index → retrieve → generate/refuse.
- The practical difference between **retrieval** (Step 3, no model) and **generation**
  (Step 4, the model).
- *Why* the system refused in Step 5 — the **default-deny gate** checks the relevance score
  and stops before the model is ever called.
- What `score_threshold` does, and why it isn't zero.

**That's Module 0.** You've seen the whole loop and met the idea that defines it. From here,
Module 1 opens the first box — how text becomes searchable *meaning* in the first place.

When you're ready, ask me to **build out Module 1**.

<div class="page-break"></div>


<a id="module-1"></a>


# Module 1 — Turning text into searchable meaning (embeddings & chunking)


<p class="module-goal">Understand the “R” inputs — how text becomes numbers a computer can compare, and why you chunk it the way you do.</p>

<div class="page-break"></div>


<a id="lesson-1-1"></a>


## Lesson 1.1 — Embeddings & vector space

> Module 1, Lesson 1 · ~20 min read + a hands-on at the terminal.
> The one question this answers: **how does a computer tell that two pieces of Torah are
> about the same thing — even when they share no words?**

In Module 0 you watched `search` find passages about the *two souls* without you typing the
exact words from the text. That worked because of the idea in this lesson. It is the "R" in
RAG, one layer down: before you can *retrieve* by meaning, you have to *turn meaning into
something a computer can measure.* That something is an **embedding**.

---

### The problem: a computer can't read Hebrew (or anything)

A computer compares numbers, not ideas. It has no notion that *נפש הבהמית* (the animal soul)
and *נפש האלקית* (the divine soul) are related, while *נפש הבהמית* and "the boiling point of
water" are not. To it, those are just strings of bytes. Keyword search (Lesson 0.1, Option B)
papers over this by matching *characters* — which is why it breaks the moment the wording
changes, a synonym appears, or the question is phrased differently than the source.

We need a way to put **meaning itself** into a form the computer can do arithmetic on. That
is exactly what an embedding model does.

---

### What an embedding is

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

> #### Under the hood — how does it know where to put things?
> `bge-m3` is a neural network trained on an enormous amount of multilingual text. During
> training it saw words and passages in context, over and over, and adjusted itself until
> text that *behaves similarly* (appears in similar contexts, gets used in similar ways)
> ended up with similar vectors. Nobody handed it a dictionary of "soul ≈ neshama"; it
> learned the geometry from usage. This is why it can match a question to a passage that
> never repeats your words: it's comparing *positions*, which encode meaning, not spelling.

---

### Two kinds of vector, from one model

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

### Where this lives in your system

Open maayan/embed/base.py and read the two small classes:

- **`Embedding`** — the data that comes out: `dense` (a list of 1024 floats),
  `sparse_indices` + `sparse_values` (the parallel lists that *are* the sparse vector — an
  index says *which* term, a value says *how strongly*). That's a passage's meaning and
  wording, as numbers.
- **`Embedder`** — a *protocol* (an interface): anything that can `embed(texts)`,
  `embed_query(text)`, and report its `dim` counts as an embedder. The real one is
  `BGEM3Embedder`; there's also a fake, dependency-free
  `HashingEmbedder` used in tests.

> #### Under the hood — why a *protocol*, and why a fake?
> Notice nothing in retrieval says "use bge-m3." It says "use *an* `Embedder`," and
> factory.py picks the concrete one from config
> (`embed_backend`). That's the dependency-injection house rule (Module 5) showing up early:
> because the embedder is swappable, tests can inject `HashingEmbedder` — which fakes vectors
> from token hashes, instantly, with no 2 GB model download — and exercise the whole pipeline
> offline. The fake is **not** semantically meaningful (it only knows shared tokens, not
> meaning); it exists so tests are fast and the network stays mocked, per the house rules. You
> never use it for real retrieval.

Two config knobs worth knowing (in maayan/config.py):
`embed_model` (`BAAI/bge-m3`) and `embed_dim` (`1024`). They're config, not hardcoded —
that's the rule.

---

### Hands-on

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

### You should now be able to say…

- What an embedding is: text → a vector, placed so **similar meaning = nearby**.
- Why this beats keyword matching: it compares *positions* (meaning), not characters.
- The difference between the **dense** vector (meaning) and the **sparse** vector (wording),
  and that `bge-m3` produces both in one pass — which is what later enables *hybrid* search.
- Where it lives: the `Embedder` protocol and `Embedding` model in `maayan/embed/`, with a
  real bge-m3 implementation and a fake for tests.

Next: **1.2 — Chunking: the unit of retrieval** — *what* gets embedded.
You don't embed a whole book; you embed one natural unit at a time. We'll see why, and why
maayan refuses to chop text into arbitrary windows.

<div class="page-break"></div>


<a id="lesson-1-2"></a>


## Lesson 1.2 — Chunking: the unit of retrieval

> Module 1, Lesson 2 · ~20 min read + a hands-on at the terminal.
> The one question this answers: **what, exactly, gets embedded and retrieved — a book? a
> sentence? — and who decides where one piece ends and the next begins?**

Lesson 1.1 turned *text* into a searchable vector. But text of what *size*? You don't embed
all of Tanya as one giant vector — you'd never be able to point at *which part* answered the
question. You embed **chunks**. Choosing what a chunk *is* turns out to be one of the most
consequential design decisions in any RAG system, and maayan makes a deliberate, opinionated
choice. This lesson is that choice.

---

### Why not just embed the whole book?

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

### The easy way (that maayan rejects)

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

### maayan's rule: one natural unit = one chunk

> **maayan chunks by the text's *own* structure. One segment — one pasuk / os / se'if /
> paragraph — becomes one chunk.** No fixed windows. The natural unit is preserved so that the
> chunk is both a coherent thought *and* a real, openable citation.

This is stated at the top of maayan/corpus/chunker.py:
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

### The `Chunk` — the spine of the whole system

You met the chunk in Lesson 0.2 as "the thing that flows through every stage." Here it is for
real. Open maayan/corpus/models.py and read the `Chunk`
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

> #### Under the hood — why re-ingesting never duplicates
> Look at `chunk_id` at the top of `models.py`. A chunk's id is a **deterministic** hash of
> `(source, ref, lang)` — feed the same three in, get the same id out, every time. So when you
> re-ingest Tanya, each chunk lands on the *same* id it had before and **overwrites in place**
> instead of creating a second copy. That's *idempotency*, and it's why the RUNBOOK
> can tell you to just re-run `ingest` without fear. (The store even resets a chunk's
> `indexed` flag if its text changed, so it gets re-embedded — that's Module 2.2.) The chunk
> is stored locally in SQLite by store.py; the id is the
> primary key.

---

### Hands-on

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

### You should now be able to say…

- Why you retrieve **passages, not whole books** (precision *and* citability), and the
  size trade-off a chunk has to balance.
- Why maayan chunks by the text's **own** structure (one segment = one chunk) instead of
  fixed token windows — and what fixed windows would break.
- The fields of a `Chunk`, especially that `ref` is both its identity *and* its citation, and
  that `source` carries provenance.
- Why re-ingesting is safe: the deterministic `chunk_id` makes it an **upsert**.

Next: **1.3 — Hebrew normalization (and what you deliberately don't do)** —
before a segment becomes a chunk, its text is cleaned. We'll see exactly what gets stripped,
what's protected (nikkud), and the one transformation maayan refuses to do automatically.

<div class="page-break"></div>


<a id="lesson-1-3"></a>


## Lesson 1.3 — Hebrew normalization (and what you deliberately *don't* do)

> Module 1, Lesson 3 · ~15 min read + a short hands-on.
> The one question this answers: **between fetching raw text from Sefaria and storing it as a
> chunk, what gets cleaned up — and what does maayan refuse to touch, on purpose?**

In Lesson 1.2 you saw `segment_to_chunks` call `normalize_text` before emitting a chunk. The
text that gets embedded and stored is the *normalized* text, never the raw fetch. This lesson
opens that one step. It's short, but it carries a real lesson about restraint: the most
important normalization decision maayan makes is a thing it **declines** to do.

---

### Why raw text needs cleaning

What Sefaria hands you isn't clean text — it's text wrapped in editorial markup. A single
segment might arrive looking like:

```html
  <b>תַּנְיָא</b> בְּסוֹף<sup class="footnote-marker">1</sup><i class="footnote">הערה של העורך</i> פֶּרֶק
```

If you embedded *that*, the vector would be polluted by HTML tags, a footnote number, and an
editor's note that isn't part of the source at all. So normalization does three jobs, in
order (read them in maayan/corpus/normalize.py, the
`normalize_text` function at the bottom):

1. **Strip markup** (`strip_markup`) — drop footnote markers *and their bodies* (editorial,
   not source), strip every remaining HTML tag, and unescape entities (`&quot;` → `"`). Empty
   Vilna page-markers fall away with the generic tag strip.
2. **Collapse whitespace** (`normalize_whitespace`) — runs of spaces, tabs, and newlines
   become a single space; trim the ends.
3. **(Optionally) expand abbreviations** — a hook that is **off by default** (the next
   section is all about why).

After this, the example above becomes exactly `תַּנְיָא בְּסוֹף פֶּרֶק` — clean source text,
ready to embed.

---

### What is protected: the nikkud

Look closely at that result: `תַּנְיָא` still has its vowel points. **Keeping nikkud is a
rule**, stated in CLAUDE.md and enforced here: normalization strips markup
but never strips the vowel/cantillation marks, because in chassidus and Kabbalah the
pointing is *part of the text* — it can carry meaning, not just pronunciation. A normalizer
that "helpfully" stripped nikkud would be quietly corrupting the source.

> #### Under the hood — then why is there a nikkud-stripper in the file?
> You'll spot `fold_surface`, which *does* drop nikkud, geresh/gershayim, and quote marks. It
> exists for **matching**, never for storage. When the system needs to ask "does the term
> *ע״ב* appear in this passage?", it folds both sides to a tolerant surface form so that
> `ע״ב`, `ע"ב`, and `עב` all compare equal — but the **stored** corpus text keeps every mark
> intact. The comment says it outright: it "never touches stored corpus text." Cleaning for
> *comparison* and cleaning for *storage* are two different jobs, and conflating them is how
> you lose data.

---

### The thing maayan refuses to do: expand rashei-teivot

Hebrew is full of **rashei-teivot** — abbreviations like *וכו׳* (etc.), *ית׳* (may He be
blessed), *רמב״ם* (Rambam). A naive system would "help" by expanding them automatically. maayan
**won't** — and the restraint is the point.

Find `expand_rashei_teivot` in `normalize.py`. It is a deliberate no-op:

- **Off by default.** With `enabled=False` (the default) it returns the text untouched.
- **Never a guesser.** Even when enabled, it only applies an *explicit* expansions table you
  provide. There is no built-in dictionary, no heuristic. An empty table → no change.
- **Protects registered terms.** It carries a `protected` set — folded surface forms of, e.g.,
  the lexicon's terms and Holy Names — that it will **never** expand, even if they appear in
  the table.

> #### Under the hood — why such caution about a "convenience"?
> Three reasons, escalating in seriousness. (1) **Ambiguity:** the same letters expand
> different ways in different contexts; an automatic guess will sometimes be wrong, and a
> wrong expansion silently changes what the source *says*. (2) **Trust:** this whole system
> exists so you can rely on its text and citations — a clever-but-wrong expansion is exactly
> the kind of invisible fabrication maayan refuses everywhere else. (3) **Holy Names:**
> some abbreviations stand for Names that must not be altered; the `protected` set makes that
> *structurally* impossible, not merely a guideline. So the feature is built as a single
> documented chokepoint that's **wired but inert** — real expansion can be turned on later,
> config-driven, behind an explicit table, without touching any caller. CLAUDE.md says it
> directly: "do not implement it speculatively." This is what disciplined restraint looks like
> in code.

---

### Hands-on

**1. Watch raw become clean — with nikkud surviving.** From the repo root:

```bash
uv run python - <<'PY'
from maayan.corpus.normalize import strip_markup, normalize_text
raw = '  <b>תַּנְיָא</b>\n\nבְּסוֹף<sup class="footnote-marker">1</sup><i class="footnote">הערה</i> פֶּרֶק  '
print("RAW:       ", repr(raw))
print("STRIPPED:  ", repr(strip_markup(raw)))     # markup + footnote gone
print("NORMALIZED:", repr(normalize_text(raw)))   # + whitespace collapsed
PY
```

Confirm three things in the output: the HTML tags are gone, the footnote *and its body* are
gone (not left as stray text), and the vowel points (e.g. the marks on תַּנְיָא) are still
there. That last one is the rule made visible.

**2. Watch an abbreviation *not* expand — even when you ask.**

```bash
uv run python - <<'PY'
from maayan.corpus.normalize import normalize_text
print(normalize_text("וְכוּ׳ עַד אֵין סוֹף", expand_abbreviations=True))
PY
```

It prints the phrase unchanged. You explicitly asked for expansion and it still didn't guess —
because there's no table, by design. That's the restraint from the section above, in one line.

**3. Read the contract in the tests.** Open
tests/test_normalize.py. Every behavior above is pinned by a
test: footnotes dropped with content, entities unescaped, whitespace collapsed, nikkud kept,
and the rashei-teivot hook a no-op even when enabled. Run them:

```bash
uv run pytest tests/test_normalize.py -v
```

The test names *are* the spec. When you wonder "what is normalization promised to do?", this
file answers it — and `make test` keeps those promises honest.

---

### You should now be able to say…

- The three steps of normalization (strip markup → collapse whitespace → optional expand),
  and that the text stored/embedded is always the *normalized* text.
- Why **nikkud is kept**, and why `fold_surface` strips it only for *matching*, never for
  storage.
- Why maayan **refuses to auto-expand rashei-teivot** — ambiguity, trust, and Holy Names —
  and how the hook is built to stay safely inert until explicitly turned on.
- That the test file is the executable spec for all of this.

**That's Module 1.** You now understand the "R" *inputs*: how text becomes a searchable
vector (1.1), what unit gets embedded and why (1.2), and how it's cleaned without being
corrupted (1.3). Those chunks-as-vectors are sitting in a database, waiting.

Next: **Module 2** opens that database — where the vectors live, and how a question pulls
back the relevant few. When you're ready, ask me to **build out Module 2**.

<div class="page-break"></div>


<a id="module-2"></a>


# Module 2 — Finding the right passages (vector DB & hybrid search)


<p class="module-goal">Understand where chunks live and how a query pulls back the relevant few.</p>

<div class="page-break"></div>


<a id="lesson-2-1"></a>


## Lesson 2.1 — Vector databases & the collection

> Module 2, Lesson 1 · ~15 min read + a hands-on at the terminal.
> The one question this answers: **once a passage is a vector, where does it actually live —
> and what gets stored next to it so the answer can cite it?**

Module 1 turned passages into vectors (dense + sparse) and decided what a passage *is* (a
chunk). This module is about the other half of the "R": **storing** those vectors somewhere
you can search fast, and **pulling back** the relevant few for a question. This lesson is the
storage. It's the box labeled `index/` in the Lesson 0.2 diagram.

---

### Why an ordinary database won't do

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

### What Qdrant stores: vectors **plus a payload**

Here's the part people miss. A vector database doesn't just store bare numbers. Each entry —
Qdrant calls it a **point** — carries two things:

1. **The vectors** — what you search *by*.
2. **A payload** — arbitrary data you search *for* and display. For maayan, the payload is
   everything you need to **cite and show** the result without a second lookup.

Open maayan/index/qdrant.py and read `chunk_payload`. The
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

### The collection: two named vectors in one place

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

> #### Under the hood — local, ephemeral, or server: one knob
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

### Hands-on

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

### You should now be able to say…

- Why retrieval needs a **vector database** (fast nearest-neighbor search), not a plain
  table.
- That each Qdrant **point** carries vectors *and* a **payload**, and that maayan's payload is
  exactly what's needed to cite + display a result.
- That the collection holds **two named vectors** (`dense`, `sparse`) per point, with cosine
  distance on the dense one — the setup that makes hybrid search possible.
- That `qdrant_url` selects server / in-memory / on-disk with no code change.

Next: **2.2 — The indexing pipeline** — how chunks actually get
*into* this collection, in batches, and why running it twice never creates a duplicate.

<div class="page-break"></div>


<a id="lesson-2-2"></a>


## Lesson 2.2 — The indexing pipeline

> Module 2, Lesson 2 · ~15 min read + a hands-on at the terminal.
> The one question this answers: **how do chunks actually get from SQLite into Qdrant — and
> why can I re-run it a hundred times without duplicating anything?**

You have chunks in SQLite (Module 1) and an empty collection waiting in Qdrant (Lesson 2.1).
The **indexing pipeline** is the conveyor belt between them: read chunks → embed them → upsert
them as points. It's small — one function — but it embodies two house values you'll see
everywhere: **idempotency** and **doing only the work that's needed.**

---

### The pipeline in one function

Open maayan/index/pipeline.py and read `index_chunks`. The
whole thing is a short loop:

```
chunks ← store.get_chunks(only_unindexed=True)      # what still needs doing
for each batch of chunks:
    embeddings ← embedder.embed([c.text ...])        # Module 1's bge-m3
    index.upsert_chunks(zip(chunks, embeddings))     # → Qdrant points
    store.mark_indexed([c.id ...])                   # remember we did these
return IndexResult(embedded, total_points)
```

Three deliberate moves hide in those lines:

1. **It works in batches** (`_batched`, size from `embed_batch_size`). Embedding is the
   expensive step; sending 16 passages to bge-m3 at once is far faster than 16 separate calls.
2. **It marks what it indexed.** After each batch is safely in Qdrant, `store.mark_indexed`
   flips those chunks' `indexed` flag to 1 in SQLite. The store now *remembers* they're done.
3. **It returns a typed result** (`IndexResult`), not a loose tuple — the boundary-is-a-model
   house rule again.

Notice what's *not* here: no model is constructed inside this function. The `store`,
`embedder`, and `index` are all **passed in** (injected). That's why the same pipeline runs
with real bge-m3 in production and the instant `HashingEmbedder` + in-memory Qdrant in tests.

---

### Incremental by default: only embed what's new

Look at the very first branch of `index_chunks`:

```python
if rebuild:
    index.recreate_collection()
    chunks = store.get_chunks()                 # everything
else:
    index.ensure_collection()
    chunks = store.get_chunks(only_unindexed=True)   # just the new/changed
```

The default path asks the store for **only the chunks not yet indexed**. So the *first*
`make index` embeds everything; the *second* finds nothing to do and is nearly instant. You
don't re-pay the embedding cost for text that hasn't changed. This is why the RUNBOOK
treats `index` as a thing you just run whenever — it's cheap when there's nothing new.

> #### Under the hood — how does a *changed* chunk get re-embedded?
> Two stable facts cooperate. (1) A chunk's id is deterministic (Lesson 1.2), so a re-ingest
> lands on the *same* row. (2) In store.py, `upsert_chunks`
> has a clever clause: on conflict it updates the row, and sets
> `indexed = CASE WHEN text changed THEN 0 ELSE indexed END`. So if you re-ingest and the
> text is *byte-identical*, `indexed` stays 1 and the next `index` skips it; if the text
> *changed*, `indexed` flips back to 0 and the next `index` re-embeds exactly that chunk.
> Incremental indexing is correct, not just fast — it never goes stale and never redoes
> settled work.

---

### Idempotency: why re-running never duplicates

This is the property worth internalizing. Run `index` once, twice, ten times — the collection
ends with the **same** points, never doubles. Two mechanisms guarantee it, one on each side:

| Side | Mechanism | Effect |
|---|---|---|
| Qdrant | `upsert_chunks` keys each point by the chunk's **stable id** | re-upserting an id **overwrites** that point, never appends |
| SQLite | the `indexed` flag + `only_unindexed` | a settled chunk isn't even *sent* to Qdrant again |

The id is the linchpin (you proved it deterministic in Lesson 1.2). Because the point id *is*
the chunk id, "insert this passage" and "I already have this passage" resolve to the same
point. There's no separate de-duplication step — idempotency falls out of using a meaningful,
stable id. (`--rebuild` is the deliberate escape hatch: it drops the whole collection first,
for when you change the embedding model or schema and *want* a clean re-embed.)

---

### Hands-on

Qdrant up, corpus indexed (Lesson 0.3). Let's *watch* incremental indexing and idempotency.

1. **Run it once more — and watch it find nothing.** You already indexed in Module 0. Run:

   ```bash
   uv run maayan index
   ```

   Read the output: `Chunks to index: 0` (or close to it) and `Embedded 0 chunks`. The point
   count is unchanged. Nothing was re-embedded, because nothing was unindexed. That's move #2
   from above, paying off.

2. **Re-ingest, then re-index — still no duplicates.** Re-ingest the same two chapters
   (identical text), then index again:

   ```bash
   uv run maayan ingest --book "Tanya, Part I; Likkutei Amarim" --limit 2
   uv run maayan index
   ```

   The ingest upserts the same ids (no new rows); the index again sees 0 unindexed. Confirm
   the collection's point count (from Lesson 2.1's snippet, or the line `index` prints) is
   **identical** to before. You just re-ran the whole front of the pipeline and changed
   nothing — that's idempotency.

3. **Force a full rebuild — same destination.** Now the escape hatch:

   ```bash
   uv run maayan index --rebuild
   ```

   This time it *does* re-embed everything (`Embedded N chunks`) — but the final point count
   lands on the **same N** as before. Same destination, more work. Write down when you'd
   actually want `--rebuild` (hint: you changed `embed_model`, or the collection schema).

---

### You should now be able to say…

- What the indexing pipeline does, in one breath: read chunks → embed in batches → upsert as
  points → mark indexed.
- Why it's **incremental** by default (only unindexed chunks) and how a *changed* chunk gets
  re-embedded (the `indexed`-reset clause in `upsert_chunks`).
- Why re-running is **idempotent** — stable point ids overwrite, and the `indexed` flag skips
  settled work — and what `--rebuild` is for.
- That every collaborator is injected, so the same pipeline runs in prod and in fast tests.

Next: **2.3 — Hybrid retrieval & fusion (RRF)** — the points are in the
collection; now a question goes in and the relevant few come back. We'll see how dense and
sparse searches are *fused*, and meet the two different scores that matter.

<div class="page-break"></div>


<a id="lesson-2-3"></a>


## Lesson 2.3 — Hybrid retrieval & fusion (RRF)

> Module 2, Lesson 3 · ~20 min read + a hands-on at the terminal.
> The one question this answers: **when I ask a question, how does the system combine
> "meaning" search and "wording" search into one ranked list — and what do the scores mean?**

This is the heart of the "R." Points are sitting in the collection (Lessons 2.1–2.2). Now a
question arrives. maayan runs **two** searches and **fuses** them, then hands back a ranked
list plus a number that decides — in Module 3 — whether to answer at all. Get this lesson and
you understand why retrieval returns what it does.

---

### Two weak signals, fused, beat one strong one

Recall the dense/sparse split from Lesson 1.1:

- **Dense** search finds passages that *mean* something similar — great for paraphrase and
  synonyms, but it can drift toward "vaguely on topic."
- **Sparse** search finds passages that share the actual *words* — great for a precise term
  or a name, but blind to rephrasing.

Each alone has a failure mode. The insight behind **hybrid search** is that their failure
modes are *different*, so combining them covers both. A passage that ranks high on *both*
meaning and wording is almost certainly what you want.

So maayan, given a query, embeds it once (dense + sparse, Lesson 1.1) and runs **both**
searches against the collection's two named vectors. Then it has to merge two ranked lists
into one. That merging is the interesting part.

---

### RRF: fuse by *rank*, not by score

You can't just add the dense and sparse scores together — they're on completely different
scales (cosine similarity vs. lexical weight), so one would swamp the other. The trick maayan
uses is **Reciprocal Rank Fusion (RRF)**, and it's beautifully simple:

> For each result, ignore its raw score and look only at its **position** in each list. A
> passage ranked #1 contributes `1/(k+1)`; #2 contributes `1/(k+2)`; and so on. Add up a
> passage's contributions across both lists. Highest total wins.

Because it uses *rank position* instead of raw score, RRF doesn't care that the two scales
differ. A passage near the top of *both* lists accumulates the most and rises; a passage that
only one method liked still gets some credit but ranks lower. Two weak agreeing signals beat
one strong lonely one.

This is wired in `QdrantIndex.query_hybrid` (qdrant.py): it
issues two `Prefetch`es (one `using="dense"`, one `using="sparse"`) and combines them with
`FusionQuery(fusion=Fusion.RRF)`. Qdrant does the fusion for you; the method just expresses
the recipe.

---

### The two scores — and why the difference is the whole ballgame

Open maayan/retrieve/models.py. There are **two** numbers,
and confusing them is the most common mistake in reading this system:

| Number | Where | What it is | What it can tell you |
|---|---|---|---|
| `SearchResult.score` | on each result | the **RRF fusion** value (rank-based) | *relative* order within this query's results |
| `RetrievalResult.relevance` | once, on the whole result | the **top dense cosine similarity** | *absolute* "is anything here actually relevant?" |

Read the docstring on `RetrievalResult` — it says it outright: the RRF `score` "only reflects
rank position and so cannot tell 'relevant' from 'best of irrelevant'." That's the key. RRF
will *always* rank something #1, even for a nonsense query — being best-of-the-batch says
nothing about whether the batch is any good. So RRF is great for **ordering** but useless for
the question Module 3 must answer: *should we answer at all, or refuse?*

That question needs an **absolute** measure, so the retriever computes one separately: the
cosine similarity of the single closest dense match (`query_dense(..., limit=1)`). That's
`relevance`. Look at retriever.py around the end of
`retrieve` — when hybrid is on, it runs a tiny extra dense-only query just to get this
absolute number. **`relevance` is the value the default-deny gate checks** (Module 3, Lesson
3.3). Hold that thread: the `score` you *see* in `search` output is not the number that
decides refusal.

> #### Under the hood — why ties are broken by `ref`
> RRF sums `1/(k+rank)`, which produces lots of *exactly equal* totals, and Qdrant returns
> tied points in arbitrary order. If the retriever sorted by score alone, the same query
> could rank differently run-to-run — and the eval harness (Module 4) would be
> non-reproducible. So `_rank_key` sorts by `(-score, ref)`: score descending, then the
> unique `ref` ascending as a deterministic tiebreaker. The embedder is already deterministic,
> so with this, the entire retrieve path is reproducible. Small detail, big payoff for trust.

---

### Hands-on

Qdrant up, corpus indexed. Let's read both scores.

**1. See the ranked list and its RRF scores.** The CLI shows `SearchResult.score` (the RRF
value) in brackets:

```bash
uv run maayan search "ההבדל בין צדיק לבינוני" --book "Tanya" --k 5
```

Each line is `[score] ref (lang/source)`. Read the scores top to bottom — they decrease.
Remember: these are **rank-based** fusion values. They tell you the *order*, not whether any
result is truly relevant.

**2. Watch `--k` change how much you get (not the order).** Run the same query with `--k 3`
then `--k 8`. The top results stay in the same order; `--k` just controls how far down the
list you see. (`top_k`, default 8, is the config default when you omit `--k`.)

**3. Now reveal the *other* number — the one that gates answers.** The CLI doesn't print
`relevance`, so peek at it directly:

```bash
uv run python - <<'PY'
from maayan.config import Settings
from maayan.retrieve.factory import build_retriever

r = build_retriever(Settings())
for q in ["ההבדל בין צדיק לבינוני", "מהי נקודת הרתיחה של מים"]:
    res = r.retrieve(q, k=3, book="Tanya")
    top = res.results[0].score if res.results else None
    print(f"relevance(abs)={res.relevance:.3f}  top RRF score={top}  ::  {q}")
PY
```

Compare the two questions. The on-topic one should have a **higher `relevance`** than the
boiling-point one — *even though both produce a ranked list with a #1 result and a non-trivial
RRF score.* That gap between "RRF always ranks something first" and "relevance knows it's
junk" is exactly the gap the refusal gate lives in. Write down both `relevance` values; recall
`score_threshold` defaults to `0.45` (Module 0) — which question would clear it?

---

### You should now be able to say…

- Why **hybrid** search (dense + sparse) beats either alone — their failure modes differ.
- What **RRF** does: fuse two lists by *rank position*, sidestepping incompatible score
  scales.
- The crucial difference between `score` (RRF, **relative** order) and `relevance` (top dense
  cosine, **absolute**) — and that `relevance` is what the refusal gate will check.
- Why ranking is made deterministic (tie-break by `ref`) and why that matters for eval.

Next: **2.4 — Reranking & filters** — an optional second pass
that re-reads the top candidates for sharper ordering, plus the `--book` / `--source` filters
you've been using.

<div class="page-break"></div>


<a id="lesson-2-4"></a>


## Lesson 2.4 — Reranking & filters

> Module 2, Lesson 4 · ~20 min read + a hands-on at the terminal.
> The one question this answers: **how do I sharpen the top results, and how do I restrict
> retrieval to a particular book or kind of source?**

Hybrid + RRF (Lesson 2.3) gives a good ranked list, fast. This lesson adds two refinements
that sit on top of it: an optional **reranker** that re-reads the best candidates for a
sharper order, and **filters** that narrow *what's eligible* in the first place. Both are
small, both are config-driven, and both close out the retrieval module.

---

### The speed/quality trade-off behind reranking

Hybrid search is a **bi-encoder** method: the query and each passage are embedded
*separately*, then compared by vector distance. That's what makes it fast — you embed the
passages once, at index time, and only the query at search time. But "compared separately"
also means the model never looks at the query and a passage *together*; it can miss subtle
relevance.

A **cross-encoder** reranker does the opposite: it takes `(query, passage)` as a *pair* and
reads them together, producing a far more discriminating relevance score. That's slower — it's
a fresh model pass per candidate — so you'd never run it over the whole corpus. The standard
pattern, which maayan follows, is **retrieve-then-rerank**:

> Use fast hybrid search to fetch a *pool* of candidates (say 30), then run the slow, accurate
> reranker on just those 30 to reorder the top few. Cheap where you can be, expensive only
> where it counts.

---

### How it's wired

Two files:

- maayan/retrieve/reranker.py — a `Reranker` *protocol*
  (`rerank(query, documents) -> list[float]`, higher = more relevant) and a concrete
  `BGEReranker` (`bge-reranker-v2-m3`). Like the embedder, it's behind a protocol so it can be
  `None` (off) in tests, or swapped.
- maayan/retrieve/retriever.py — the `Retriever`
  decides whether to use it.

Read the `retrieve` method. The relevant logic:

```python
pool = max(final_k, rerank_candidates) if reranker else final_k   # fetch more if reranking
... hybrid search returns `pool` candidates ...
if reranker is not None:
    raw_scores = reranker.rerank(query, [r.text for r in results])  # re-read each pair
    # the cross-encoder score replaces the RRF score, and …
    relevance = max(raw_scores)                                     # … also becomes the gate value
```

Two things to notice. First, when a reranker is present it fetches a **bigger pool**
(`rerank_candidates`, default 30) so there's something for it to reorder, then trims to your
`k` after. Second — important — when reranking is on, the **cross-encoder score becomes the
`relevance`** that the default-deny gate checks (Module 3), not the dense cosine from Lesson
2.3. The config docstring on `score_threshold` even notes that "enabling rerank sharpens
separation," which is why the threshold may want re-tuning when you turn rerank on. By default
**`rerank_enabled` is `false`** — it's an opt-in quality upgrade with a latency and
model-download cost.

> #### Under the hood — source boosts ride along here too
> The same `retrieve` method applies *source boosts* before/with ranking: `expert_boost`,
> `derived_boost`, `term_boost` (all default `1.0` = no effect). These multiply the score of
> chunks that came from a human expert, an approved development, or the curated lexicon — so
> that when a scholar's contribution is *as* relevant as printed text, it can be made to rank
> at or above it. That's a Module 6/7 concern (it only matters once you have non-`sefaria`
> chunks), but notice it lives right here in the retriever, as a clean multiplier. With the
> defaults at `1.0`, retrieval treats every source equally.

---

### Filters: narrowing what's eligible

Sometimes you don't want to reorder results — you want to *exclude* some entirely. That's a
**filter**, and it's a different mechanism from scoring: it constrains which points the search
is even allowed to consider. Read `_build_filter` in `retriever.py` — it builds a Qdrant
filter from three optional constraints:

| Filter | CLI flag | Effect |
|---|---|---|
| `book` | `--book "Tanya"` | only points whose payload `book` matches |
| `source` | `--source sefaria` | only that provenance (`sefaria`/`expert`/`derived`/`term`) |
| `langs` | (API) | only those languages |

You've already used `--book` since Module 0. The key idea: a filter is applied *inside* the
search (it's passed into each `Prefetch`), so it shapes the candidate pool **before** ranking
— not a post-hoc removal. Filtering by `--source` becomes especially meaningful in Module 6,
when the collection holds expert and derived chunks beside the printed text and you want to
ask "what did *I* contribute on this?" versus "what does the printed text say?"

---

### Hands-on

Qdrant up, corpus indexed.

**1. Use the filters you now understand.** Restrict by book, then by source:

```bash
uv run maayan search "שתי הנפשות" --book "Tanya" --k 5
uv run maayan search "שתי הנפשות" --book "Tanya" --source sefaria --k 5
```

Right now every chunk is `source=sefaria`, so the second command returns the same results —
but you've just written the query you'll use in Module 6 to separate printed text from your
own contributions. Note that the filter changes *what's eligible*, not the order of what's
left.

**2. Turn the reranker on and compare ordering.** This downloads `bge-reranker-v2-m3` the
first time (a one-time cost, like bge-m3) and is slower per query. Run the *same* query with
rerank off, then on, and compare the top few refs:

```bash
uv run maayan search "ההבדל בין צדיק לבינוני" --book "Tanya" --k 5
RERANK_ENABLED=true uv run maayan search "ההבדל בין צדיק לבינוני" --book "Tanya" --k 5
```

Did the order change? Often the reranker promotes a passage that's *genuinely* most on-point
above one that merely shared vocabulary. On a two-chapter corpus the effect may be small;
it grows with corpus size and query subtlety. Note what moved.

**3. See rerank change the *gate* number, not just the order.** Reuse the relevance snippet
from Lesson 2.3, once normally and once with `RERANK_ENABLED=true`:

```bash
RERANK_ENABLED=true uv run python - <<'PY'
from maayan.config import Settings
from maayan.retrieve.factory import build_retriever
r = build_retriever(Settings())
res = r.retrieve("ההבדל בין צדיק לבינוני", k=3, book="Tanya")
print(f"relevance (now a reranker score): {res.relevance:.3f}")
PY
```

The `relevance` is now the cross-encoder's score, not the dense cosine. That's why
`score_threshold` may need a different value when rerank is on — you've just seen the number
the gate reads come from a different source. (You'll tune this deliberately in Module 7.2.)

---

### You should now be able to say…

- The bi-encoder (fast, separate) vs. cross-encoder (slow, paired) trade-off, and the
  **retrieve-then-rerank** pattern that uses each where it fits.
- That rerank is **off by default**, fetches a larger candidate pool (`rerank_candidates`),
  and — when on — supplies the `relevance` value the refusal gate checks.
- That **filters** (`--book`, `--source`, langs) constrain *eligibility* before ranking, a
  different lever from scoring/boosts.
- That **source boosts** live in the retriever as score multipliers (default 1.0), ready for
  when the corpus holds more than printed text.

**That's Module 2.** You now know where vectors live (2.1), how they get there idempotently
(2.2), how a question fuses two searches into a ranked list with two distinct scores (2.3),
and how to sharpen and narrow that list (2.4). You also keep meeting one number — `relevance`
— that decides whether the system answers at all.

Next: **Module 3** is that decision. We open `generate/`: how retrieved passages become a
cited answer, and how the **default-deny gate** uses `relevance` to refuse rather than
fabricate. When you're ready, ask me to **build out Module 3**.

<div class="page-break"></div>


<a id="module-3"></a>


# Module 3 — The trust core (generation, grounding, default-deny)


<p class="module-goal">Understand how retrieved passages become a cited answer, and how the system refuses rather than fabricate.</p>

<div class="page-break"></div>


<a id="lesson-3-1"></a>


## Lesson 3.1 — The generation backend (a swappable box)

> Module 3, Lesson 1 · ~15 min read + a short hands-on.
> The one question this answers: **which part of the system actually talks to the language
> model, and why can I swap that model (cloud ↔ local) without touching anything else?**

We've reached the "G." Retrieval (Modules 1–2) hands us the relevant passages; now something
has to *compose* an answer from them. That composing is the one job that uses a large language
model, and — recall "what runs where" from Lesson 0.2 — it's the one step that may leave your
machine. Before we look at *how* the answer is grounded and cited (Lesson 3.2) or *how it
refuses* (3.3), we need to see the **box** that the model lives behind. Because maayan treats
it as exactly that: a box with one slot, interchangeable.

---

### One tiny interface, two implementations

Open maayan/generate/base.py. The entire contract for "a
thing that can talk to a language model" is this:

```python
class GenerationBackend(Protocol):
    def generate(self, system: str, messages: Sequence[Message]) -> str: ...
```

That's it. A backend takes a system prompt and a list of messages, and returns text. Anything
that can do that *is* a generation backend. There are two real ones:

| Backend | File | Runs | Default model |
|---|---|---|---|
| `OpenRouterBackend` | openrouter.py | **cloud** (OpenRouter) | `qwen/qwen-2.5-72b-instruct` |
| `OllamaBackend` | ollama.py | **local** (your machine) | `qwen2.5:7b-instruct` |

Open both. They look completely different inside — one uses the OpenAI client pointed at
OpenRouter's URL; the other POSTs to a local Ollama HTTP endpoint. But they expose the *exact
same* `generate(system, messages) -> str`. That sameness is the whole point.

---

### Why a *protocol*, and why it matters here

The RAG service (the thing you'll meet in 3.2–3.3) never says "call OpenRouter." It says "call
*a* `GenerationBackend`." Which concrete one it gets is decided once, at the edge, by config:

Open maayan/generate/factory.py. `build_generation_backend`
reads `generation_backend` (`"openrouter"` or `"ollama"`) and constructs the matching box. The
default is `openrouter`. Flip the config to `ollama` and **every other line of code stays the
same** — retrieval, grounding, citation extraction, the refusal gate, the CLI, the UI: none of
them know or care which model answered.

> #### Under the hood — this is dependency injection, early
> This is the clearest possible example of the house rule you'll study in Module 5:
> *construction happens at the edges; logic depends on interfaces.* The factory (an edge)
> builds the concrete backend; the `RAGService` (logic) is *handed* one. Because the seam is a
> protocol, three things become free: (1) **swap** cloud ↔ local by config; (2) **test**
> grounding and refusal with a fake backend that returns a canned string — no network, no key,
> per the house rules; (3) **add** a future backend (Anthropic, a different host) by writing
> one class and one factory branch, touching nothing else. Notice the factory also refuses to
> build OpenRouter without an API key, and the key is read from config as a `SecretStr` —
> never hardcoded, never logged (another house rule).

---

### The trade-off the box hides

The reason maayan bothers to make this swappable is a real tension, spelled out in
CLAUDE.md:

- **OpenRouter (cloud):** stronger models (esp. on Hebrew), nothing to run locally — but it's a
  network call to a third party, costs money, and your question leaves the machine.
- **Ollama (local):** fully offline, private, free — but smaller models are weaker, especially
  on Hebrew.

You don't have to choose forever. The architecture lets you run cloud today and flip to local
the day privacy or cost demands it. And — crucially — **the trust guarantees don't depend on
which you pick.** Grounding, citations, and default-deny (the rest of this module) sit *outside*
the box, in the RAG service. A weaker local model might write a clumsier answer, but it still
can't answer from sources that weren't retrieved, and it still refuses when there's nothing.
That's by design: the backbone is RAG, not the model.

---

### Hands-on

This lesson is about *seeing the seam*, not running a swap (that's Module 7.3).

1. **Confirm the shared shape.** Open `openrouter.py` and `ollama.py` side by side. Find the
   `generate(` method in each. Confirm they take the same arguments and return a `str`, despite
   doing entirely different things inside. That identical signature *is* the swap point.

2. **Find the one switch.** In config.py, find `generation_backend`
   (and notice the `generation_model` helper property next to it). This single field is the
   only thing that changes to move between cloud and local. Read its description.

3. **Trace who depends on what.** Search `rag.py` for the word `OpenRouter`. You won't find it —
   `RAGService` imports only `GenerationBackend` (the protocol). Write one sentence: *why is it
   important that the RAG logic never names a concrete backend?* (You're previewing the answer
   to Module 5.1.)

---

### You should now be able to say…

- That generation is isolated behind a one-method `GenerationBackend` protocol, with cloud
  (OpenRouter) and local (Ollama) implementations.
- That `generation_backend` in config selects which is injected, with **no other code change** —
  and that the API key is a secret read from config, never hardcoded.
- The cloud-vs-local trade-off (quality vs. privacy/cost/offline), and why the **trust
  guarantees live outside the box**, so they hold either way.

Next: **3.2 — The grounded prompt & citations** — now we look
*inside* the call: how retrieved sources become a numbered, citable block, and how every `[S#]`
in the answer resolves back to a real ref.

<div class="page-break"></div>


<a id="lesson-3-2"></a>


## Lesson 3.2 — The grounded prompt & citations

> Module 3, Lesson 2 · ~20 min read + a hands-on at the terminal.
> The one question this answers: **how do retrieved passages actually get handed to the model
> so that the answer is forced to come *from them* — and how does each `[S#]` in the answer
> turn back into a real citation?**

In Lesson 3.1 you saw the box the model lives behind. Now we open the call itself. This is the
"A" in RAG — *Augmented*: the model isn't asked your question cold; it's handed the retrieved
sources and told to answer **only** from them, citing each claim. This lesson is how that
hand-off is built, in maayan/generate/rag.py.

---

### Sources become a numbered, citable block

When retrieval returns its passages, the RAG service turns them into a block the model can
quote *by number*. Read `build_context` (rag.py:67):

```python
def build_context(sources):
    lines = ["SOURCES:"]
    for i, s in enumerate(sources, 1):
        lines.append(f"[S{i}] ({s.ref}) {s.text}")
    return "\n".join(lines)
```

So the model literally sees:

```
SOURCES:
[S1] (Tanya, Part I; Likkutei Amarim 1:2) ...the text of that passage...
[S2] (Tanya, Part I; Likkutei Amarim 2:1) ...the text of that passage...
```

Two things are doing quiet work here. First, each source gets a **handle** — `[S1]`, `[S2]` —
that the model can cite cheaply, the way you'd say "see source 1" instead of rewriting the
whole passage. Second, the handle carries the **real `ref`** right next to it. The model cites
by tag; the system already knows the tag maps to *"Tanya, Part I; Likkutei Amarim 1:2"*. The
citation is grounded before the model writes a word, because the `ref` rode in with the source
(remember: `ref` is both identity and citation, Lesson 1.2).

---

### The instructions that make it grounded

A numbered block isn't enough — the model has to be *told* to obey it. Read
`DEFAULT_SYSTEM_PROMPT` (rag.py:20). In plain terms, its rules
are:

1. **Use only the sources.** No outside facts. Never invent or guess mekoros.
2. **Cite every claim** with its bracket tag right after it, e.g. `[S1]`, or `[S1][S3]`.
3. **If the sources don't suffice, say so** — don't speculate.
4. **Answer in the language of the question**, faithful to the sources.
5. (A conversation block, if present, is for *interpretation only* — never cite it. That's
   Lesson 3.4.)

Then `ask` assembles the final message: the sources block, plus the question with a reminder to
"cite each claim ONLY by its `[S#]` source tag," and sends it through the backend (Lesson 3.1).

> #### A crucial caveat — the prompt is the *softer* half
> Notice these are *instructions* to the model. A good model follows them; but instructions
> alone are exactly the "please don't hallucinate" approach Lesson 0.1 warned about — they
> reduce fabrication, they don't *guarantee* it. The hard guarantee — that the system won't
> answer when there's no real source — is **not** in this prompt. It's a gate in code that runs
> *before* this prompt is ever built. That's the entire subject of the next lesson. For now,
> hold the split: the prompt shapes *how* it answers; the gate (3.3) decides *whether* it
> answers at all.

---

### From `[S#]` back to a citation

After the model replies, the service has to figure out *which* sources it actually leaned on,
so the UI/CLI can mark them. Read `extract_cited_refs`
(rag.py:83):

- It scans the answer for `[S#]` tags (the regex `_TAG`), maps each number back to that
  source's `ref`, and collects them in order, de-duplicated.
- As a safety net, it also catches any `ref` the model wrote out *literally* in prose.

The result is `Answer.cited_refs` — the concrete list of sources the answer rests on. The CLI
then prints the full `Sources:` list and marks the cited ones with `*`. So the chain is
airtight and inspectable: **retrieved `ref` → `[S#]` handle → model cites `[S#]` → resolved
back to `ref` → shown to you.** Every claim has a traceable home.

---

### Hands-on

You need a working `ask` (Qdrant up, corpus indexed, and an OpenRouter key — this step calls
the model). Ask something your two Tanya chapters can answer:

```bash
uv run maayan ask "מה ההבדל בין צדיק לבינוני?"
```

1. **Match every `[S#]` to its source.** In the answer text, find the `[S#]` tags. In the
   `Sources:` list below, the cited ones are marked `*`. Pick one tag — say `[S2]` — and
   confirm it lines up with the 2nd source. Then open that source's text (`uv run maayan search`
   its ref, or recall it) and check: **does the claim the tag is attached to actually say what
   the source says?** This habit *is* the system's reason to exist.

2. **Find an uncited source.** Usually not every retrieved source gets cited — some were
   retrieved but didn't make it into the answer (marked `[ ]`, no `*`). That's fine and honest:
   retrieval offers candidates; the model uses what it needs. Note one.

3. **See the block the model saw.** Reconstruct the `SOURCES:` block yourself to demystify it:

   ```bash
   uv run python - <<'PY'
   from maayan.config import Settings
   from maayan.retrieve.factory import build_retriever
   from maayan.generate.rag import build_context
   r = build_retriever(Settings())
   sources = r.retrieve("מה ההבדל בין צדיק לבינוני?", k=3, book="Tanya").results
   print(build_context(sources))
   PY
   ```

   This prints the exact numbered, citable block that gets handed to the model. Notice the
   `[S#]` tag and the `(ref)` sitting together on each line — that adjacency is what makes a
   citation cheap and grounded.

4. **Read the contract.** Open `DEFAULT_SYSTEM_PROMPT` in `rag.py` and read rule 1 and rule 3
   aloud. In your own words, what is the model being *forbidden* to do?

---

### You should now be able to say…

- How retrieved sources become a **numbered `[S#]` block** (`build_context`), each tag carrying
  its real `ref`.
- What the **system prompt** instructs (answer only from sources, cite every claim, refuse to
  speculate) — and that this is the *soft* half of the guarantee.
- How `extract_cited_refs` resolves `[S#]` tags back to refs, completing a traceable chain from
  retrieval to displayed citation.

Next: **3.3 — Default-deny: the rule that lives in code, not the prompt** —
the hard guarantee. We'll meet the gate that refuses *before* the model is ever called, and you'll
make it open and close with one knob.

<div class="page-break"></div>


<a id="lesson-3-3"></a>


## Lesson 3.3 — Default-deny: the rule that lives in code, not the prompt

> Module 3, Lesson 3 · ~20 min, hands-on at the terminal.
> The one question this answers: **what actually stops the system from answering when it has no
> source — and why is that a line of code instead of a polite instruction to the model?**

This is the most important lesson in the curriculum. Everything else — embeddings, hybrid
search, citations — serves *this*: a tool you can trust because it knows when to stay silent.
You watched it happen in Lesson 0.3 (the boiling-point question). Now you'll understand exactly
how, and you'll operate the gate yourself.

---

### Why the prompt is not enough

In Lesson 3.2 the system prompt told the model: "if the sources don't suffice, say so; don't
speculate." That's good hygiene. But it's a *request*, and Lesson 0.1 taught us the hard truth:
a language model is a fluent next-word predictor that fabricates with confidence. Lean on the
prompt alone and you're trusting the very faculty that invents mekoros to police itself. Some
days it will. The day it doesn't, you get a beautiful, cited, **fabricated** answer — the worst
possible failure for Torah.

So maayan does not rely on asking nicely. It makes the dangerous case *structurally
impossible*: when nothing supports an answer, **the model is never called at all.**

---

### The gate

Open maayan/generate/rag.py and read the `ask` method. The very
first thing it does after retrieval — rag.py:137, under the
comment `# DEFAULT-DENY` — is this:

```python
retrieval = self._retriever.retrieve(question, ...)
sources = retrieval.results

# DEFAULT-DENY: refuse without calling the model when nothing supports an answer.
if not sources or retrieval.relevance < self._score_threshold:
    return Answer(text=self._refusal_text, grounded=False, cited_refs=[], sources=sources)

# ... only past this point is a prompt built and the model called ...
```

Read it slowly, because every word is load-bearing:

- **`not sources`** — retrieval found literally nothing. Refuse.
- **`retrieval.relevance < self._score_threshold`** — this is the key. Remember from Lesson 2.3
  that `relevance` is the **absolute** measure (top dense cosine, or the reranker's score),
  *not* the RRF rank score. RRF always ranks something #1 even for nonsense; `relevance` is the
  number that can actually say "the best thing I found still isn't good enough." If it's below
  the threshold, refuse.
- **`return ... grounded=False`** — and here is the whole point: this `return` happens **before
  any prompt is built and before `self._backend.generate` is ever reached.** The model doesn't
  get a chance to improvise, because it isn't invoked.

That's what "enforced in code, not the prompt" means, made concrete. The honesty isn't a
sentence the model might ignore — it's a locked door the model never walks through. The comment
in the source says it exactly: refusal is decided "before any prompt is built, so context can
never trigger a model call."

> #### Under the hood — why `relevance` and not the RRF `score`?
> This is the subtle reason the two-scores distinction from Lesson 2.3 *mattered*. If the gate
> checked the RRF rank score, it would be fooled by every query: RRF dutifully assigns a decent
> rank score to "the best of a bad batch," so a nonsense question would sail through. The gate
> must ask an **absolute** question — "is the closest passage genuinely close?" — and only the
> dense-cosine (or reranker) `relevance` answers that. The design of the *retrieval* models was
> already serving *this* gate. That's the system being coherent end to end.

The threshold itself is `score_threshold` — config-driven (default `0.45`), passed into
`RAGService`. Not hardcoded, tunable per corpus (Module 7), and measured honestly with the eval
harness (Module 4).

---

### Refusal shows its work

When the gate fires, the CLI doesn't just say "no." Look at the `ask` command's output path: it
prints `[refused]`, the refusal text, **and** "(Closest, but below the relevance threshold:)"
followed by the few nearest passages it *did* find. That transparency matters: the system is
telling you, in plain text, "here are the best I had, none cleared the bar, so I won't answer."
You can see the gate's reasoning, not just its verdict — and you keep a `Session` id either way,
so even a refusal is something you can later annotate (Module 6).

---

### Hands-on

Qdrant up, corpus indexed. (Refusal needs **no** OpenRouter key — that's the point: the model
isn't called. Only the contrasting grounded answer needs a key.)

**1. Trigger a refusal.** Ask something your two Tanya chapters can't support:

```bash
uv run maayan ask "מהי נקודת הרתיחה של מים?"
```

You get `[refused]`, the refusal text, and the "(Closest, but below the relevance threshold:)"
list. Confirm: those closest passages exist (RRF found *something*), yet the system still
refused — because their `relevance` was below `0.45`. That's the gate distinguishing "best of
irrelevant" from "actually relevant."

**2. Open the gate with one knob, and feel why it isn't zero.** The threshold is config. Lower
it just for one run by setting the env var inline:

```bash
SCORE_THRESHOLD=0.0 uv run maayan ask "מהי נקודת הרתיחה של מים?"
```

Now the gate's condition can't be met (nothing is below 0.0), so it proceeds to call the model
— and you get a forced, ungrounded answer stitched from irrelevant passages. **That** is exactly
the failure the gate exists to prevent. Run it once to feel it, then leave the threshold alone
(the env var only affected that single command; your `.env`/default of `0.45` is untouched).

**3. Confirm the model was never called on the refusal.** Re-run step 1 **with no API key set**
(temporarily unset it, or just note you've never needed it for refusals). It still refuses,
cleanly. A system that needed the cloud model to tell you "I don't know" would be calling the
fabricator to ask permission not to fabricate. maayan doesn't — the door is locked in local
code.

**4. Find the threshold's home.** In `config.py`, read the `score_threshold` description. It
notes bge-m3 cosine "clusters in a narrow band," so the right value is corpus-specific and you
**tune it via the eval harness** — foreshadowing Module 4. Write down: what goes wrong if you
set it too high? Too low?

---

### You should now be able to say…

- Why the prompt's "don't speculate" is insufficient, and why default-deny is enforced in
  **code** instead.
- Exactly what the gate checks (`not sources` or `relevance < score_threshold`) and that it
  returns **before the model is ever called**.
- Why it must use the **absolute** `relevance`, not the RRF rank score — and how that ties back
  to Lesson 2.3.
- What `score_threshold` does, why it isn't zero, and that it's tuned with the eval harness.

Next: **3.4 — Context-aware follow-ups without losing grounding** —
how a conversation can help *interpret* a question without ever becoming a citable source, and
without weakening the gate you just met.

<div class="page-break"></div>


<a id="lesson-3-4"></a>


## Lesson 3.4 — Context-aware follow-ups without losing grounding

> Module 3, Lesson 4 · ~15 min read + a hands-on at the terminal.
> The one question this answers: **how can the system understand a follow-up like "and what is
> its source?" — which only makes sense in context — without letting that context sneak in as a
> fake citation or weaken the refusal gate?**

A real study session isn't one-shot. You ask, you get an answer, you follow up with a pronoun
("and *its* root?", "explain *that* further"). For the follow-up to make sense, the system needs
the prior turns. But prior turns are *conversation*, not *Torah* — they must never be cited, and
they must never trick the system into answering something the corpus doesn't support. This lesson
is how maayan threads that needle. It's the last piece of the trust core.

---

### The tension, stated plainly

Two desirable things pull against each other:

- **We want context** so "what is its source?" can resolve "its" to whatever the last turn was
  about.
- **We refuse to let context become grounding.** If the conversation itself could be cited, the
  system could "answer" a question using something it merely *said earlier* — a hall of mirrors,
  not a grounded answer. And if context fed retrieval, grounding could drift onto prior turns
  instead of the actual sources.

maayan resolves this with a strict rule: **context interprets the question; sources alone
answer it.**

---

### How it's built

Three pieces in maayan/generate/rag.py:

1. **`ContextTurn`** (rag.py:44) — a tiny model (`speaker`,
   `text`) for one prior turn. Its docstring says it outright: "This block is NEVER citable —
   only retrieved sources are."

2. **`build_conversation`** (rag.py:75) — renders prior turns
   under a header that *labels them non-citable*:

   ```
   CONVERSATION SO FAR (for context only — do NOT cite any of this):
   ```

   Contrast this with `build_context` from Lesson 3.2, whose header is `SOURCES:` and whose
   lines carry `[S#]` tags. The conversation block deliberately has **no** tags — there's
   nothing for the model to cite, by construction.

3. **`ask`** wires them in the right order: if there are `context_turns`, the conversation block
   goes **first**, then the `SOURCES:` block, then the question with the reminder "Do not cite
   the conversation above." System-prompt rule 5 (Lesson 3.2) reinforces it: use the
   conversation "ONLY to interpret the current question … never cite it."

---

### The two guarantees that survive

Read the top of `ask` carefully — two comments encode the discipline:

> **Retrieval always runs on the current question only.** The conversation context is *not* fed
> to the retriever. So grounding is computed fresh from the real question every time and can
> never drift onto prior turns.

> **Default-deny still runs first.** The gate from Lesson 3.3 sits *before* any prompt (including
> the conversation block) is built. So context "can never trigger a model call" — if the current
> question's retrieval doesn't clear `score_threshold`, the system refuses, conversation or not.

Put together: context can make the system *understand* you better, but it cannot make the system
*answer* something the corpus doesn't support, and it cannot become a citation. The follow-up
"and what is its source?" gets correctly interpreted — *and* if the corpus has no source for it,
you still get an honest refusal. The trust core is intact under conversation.

> #### Under the hood — why `ContextTurn` is its own little model
> Its docstring notes it's "decoupled from `threads.ThreadTurn` on purpose: the generator must
> not depend on the thread layer." Persistent topic *threads* (storing and replaying turns) are a
> Module 6 feature; the thread flow maps a stored `ThreadTurn` down to a `ContextTurn` when it
> calls `ask`. The generator only knows the small, citation-free `ContextTurn` — so the trust
> core stays independent of the (later, optional) conversation-storage machinery. Clean layering:
> the generator depends *down* on a minimal type, never *up* on the feature that uses it.

---

### Hands-on

Qdrant up, corpus indexed, OpenRouter key set (this calls the model). The simplest way to feed
context is a **topic thread** (Module 6 covers threads fully; here we just use one to carry the
conversation).

**1. Ask, then follow up with a pronoun.** Start a thread, note the printed `Thread:` id, then
ask a follow-up that *only* makes sense in context:

```bash
uv run maayan ask "מהי נפש הבהמית?" --topic "study of nefesh"
# → note the "Thread:  <id>" line in the output
uv run maayan ask "ומה מקורה?" --thread <id>     # "and what is ITS source?"
```

The follow-up has no noun — "its" can only resolve to *nefesh habehamis* via the prior turn. If
the answer correctly addresses the source/root of the animal soul, context did its job. Now check
the `Sources:` list on that second answer: the citations are **real refs from the corpus**, not
your first question. Context interpreted; sources grounded.

**2. Prove context can't override the gate.** In the same thread, ask a follow-up whose topic the
corpus can't support:

```bash
uv run maayan ask "ומה דעתו על נקודת הרתיחה?" --thread <id>    # "...on the boiling point?"
```

Even with rich context about nefesh, this refuses — because retrieval on *this* question finds
nothing above threshold, and the gate runs before the conversation block is ever assembled.
Context didn't lower the bar. That's guarantee #2 from above, on screen.

**3. Read the two headers side by side.** Open `build_context` and `build_conversation` in
`rag.py`. Note that one header invites citation (`SOURCES:` + `[S#]`) and the other forbids it
(`for context only — do NOT cite`). In a sentence: how does the *absence of `[S#]` tags* in the
conversation block make "don't cite this" not just a request but a structural fact?

---

### You should now be able to say…

- The rule that resolves the tension: **context interprets the question; only sources answer
  it.**
- The three pieces (`ContextTurn`, `build_conversation`, and `ask`'s ordering) and how the
  non-citable header + missing `[S#]` tags enforce "never cite the conversation."
- The two guarantees that survive conversation: retrieval runs on the **current question only**,
  and **default-deny runs first** — so context can't ground an answer or open the gate.

**That's Module 3 — the trust core.** You now understand the full "G": the swappable backend
(3.1), how sources become a cited answer (3.2), the default-deny gate that refuses in code (3.3),
and how conversation helps without compromising grounding (3.4). Together with Modules 1–2, you
can now explain *the entire path* from a question to a grounded, cited answer — or an honest
refusal.

Next: **Module 4** asks the uncomfortable question — *is it actually any good?* — and replaces
"it feels right" with numbers. When you're ready, ask me to **build out Module 4**.

<div class="page-break"></div>


<a id="module-4"></a>


# Module 4 — Knowing if it's actually good (evaluation)


<p class="module-goal">Replace “it feels right” with numbers.</p>

<div class="page-break"></div>


<a id="lesson-4-1"></a>


## Lesson 4.1 — Why eval exists, and the metrics

> Module 4, Lesson 1 · ~20 min read + a short hands-on.
> The one question this answers: **how do I know whether retrieval is actually *good*, instead
> of just trusting that it feels right?**

You can now explain the whole pipeline (Modules 0–3). But "I asked a few questions and the
answers looked fine" is not knowledge — it's a vibe. The moment you change a knob
(`score_threshold`, rerank on/off, a different embedding model) you need to answer: *did that
make retrieval better or worse?* You cannot answer that by eye. This module replaces the vibe
with **numbers**. This lesson is the numbers themselves.

---

### Why you can't just "look at the answers"

Three reasons eyeballing fails:

1. **It doesn't scale.** You can sanity-check 3 answers, not 50. Quality is a property of the
   *distribution* of questions, not a lucky example.
2. **It's not comparable.** "Variant A felt sharper than B" can't be defended or reproduced.
   To justify a change you need the same questions scored the same way, before and after.
3. **It hides the gate.** The most important behavior — *refusing* when it should — is
   invisible unless you deliberately test questions that *ought* to be refused.

So maayan ships an **eval harness**: a fixed set of questions with known-correct answers, run
through the real retriever, scored by standard metrics. Read the module header in
maayan/eval/harness.py — its whole reason for being is "so
model and chunking choices are justified with numbers, not vibes."

---

### The gold set: questions with known answers

Evaluation needs a ground truth to score against. That's the **gold set** — a hand-curated
list of cases. Open eval/goldset.yaml and read a few. Each case is a
`GoldExample` (goldset.py):

```yaml
- question: "מהן שתי הנפשות של האדם?"
  expected_refs: ["Tanya, Part I; Likkutei Amarim 1", "Tanya, Part I; Likkutei Amarim 2"]
  note: two souls — divine and animal
```

`expected_refs` is "if retrieval is working, *these* are the chapters it should pull back." The
gold set covers every chapter of Tanya Part I, plus a handful of **negative** cases (more on
those in Lesson 4.3). It's hand-made and editable — the file header says so: "better gold = more
trustworthy numbers."

> #### Under the hood — chapter-level gold, segment-level retrieval
> Your chunks are *segments* (`...Amarim 1:13`), but the gold refs are written at *chapter*
> granularity (`...Amarim 1`). How do they match? Read `ref_matches` in
> metrics.py: a retrieved ref counts if it equals the expected
> ref *or starts with it plus a colon*. So a chapter-level expectation matches any segment
> inside that chapter. This lets you write gold sets at the granularity you actually think in
> ("the answer is in chapter 1") without listing every segment.

---

### The three metrics, in plain language

All three live in metrics.py — pure, hand-checkable functions.
Each answers a different question about the ranked list retrieval returned:

| Metric | Plain-language question | How it's scored |
|---|---|---|
| **hit@k** | "Did *any* right answer show up in the top *k*?" | 1.0 if yes, 0.0 if no |
| **recall@k** | "Of *all* the right answers, what fraction did we find in the top *k*?" | found / expected |
| **MRR** | "How *high* was the first right answer?" | 1 / (rank of first hit) |

A worked example. Suppose for a question the expected chapters are `{1, 2}` and retrieval
returns, in order: `[5, 1, 9, 2, 7]`.

- **hit@3** = 1.0 — chapter 1 is within the top 3. (At least one right answer appeared.)
- **recall@3** = 0.5 — of the two expected (1 and 2), only chapter 1 is in the top 3. (2 is at
  rank 4.)
- **MRR** = 1/2 = 0.5 — the first correct answer (chapter 1) was at rank 2.

Each captures something the others miss: `hit@k` asks "did we get *anything* right?"; `recall@k`
asks "did we get it *all*?"; `MRR` rewards putting the right answer *near the top* (rank 1 beats
rank 5 even if both are a "hit"). Read together, they describe retrieval quality far better than
any single number — or any glance.

---

### Hands-on

No need to run the full harness yet (that's Lesson 4.2) — first, *trust the metrics by checking
them by hand.* They're pure functions:

```bash
uv run python - <<'PY'
from maayan.eval.metrics import hit_at_k, recall_at_k, mrr
retrieved = ["ch5", "ch1", "ch9", "ch2", "ch7"]   # ranked output
expected  = ["ch1", "ch2"]                          # gold answer
print("hit@3   :", hit_at_k(retrieved, expected, 3))    # 1.0
print("recall@3:", recall_at_k(retrieved, expected, 3)) # 0.5
print("MRR     :", mrr(retrieved, expected))            # 0.5
PY
```

1. **Confirm the worked example.** The output should match the numbers above. If you can
   predict them before running, you understand the metrics.

2. **Probe each metric's blind spot.** Change `retrieved` so that `hit@3` stays 1.0 but
   `recall@3` drops, then so that `recall@3` is 1.0 but `MRR` is low. Each edit teaches you what
   that metric does *not* see. (Hint: move the right answers around in the list.)

3. **See chapter-vs-segment matching.** Try `hit_at_k(["Tanya, Part I; Likkutei Amarim 1:13"],
   ["Tanya, Part I; Likkutei Amarim 1"], 5)`. It's 1.0 — a segment satisfies a chapter-level
   expectation. That's `ref_matches` doing its prefix trick.

---

### You should now be able to say…

- Why eyeballing answers can't tell you if retrieval is good (scale, comparability, the hidden
  gate).
- What a **gold set** is — `{question, expected_refs}` cases — and why gold refs can be written
  at chapter granularity (prefix matching).
- What **hit@k**, **recall@k**, and **MRR** each measure, and why you need all three.

Next: **4.2 — Running and reading the harness** — run these
metrics over the whole gold set with one command, and learn to read the table it prints,
including the default-deny gate rates.

<div class="page-break"></div>


<a id="lesson-4-2"></a>


## Lesson 4.2 — Running and reading the harness

> Module 4, Lesson 2 · ~20 min, hands-on at the terminal.
> The one question this answers: **how do I run the whole gold set through retrieval, and how do
> I read the table it gives back — including the line about refusals?**

Lesson 4.1 gave you the metrics and the gold set. Now you run them together with one command and
learn to *read* the result. This is the skill that turns "I changed a knob" into "I changed a
knob and recall@5 went from 0.71 to 0.78." Read the table well and you can tune the system with
intent (Module 7) instead of guessing.

---

### One command

```bash
uv run maayan eval
```

That's it. Under the hood (read `evaluate` in cli.py and `run_eval` in
harness.py) it: loads the gold set, runs **every** question
through the *real* retriever, scores each with hit@k / recall@k / MRR, and aggregates. It prints
the gold-set path, the active `score_threshold`, and a small table.

> **Prerequisite — index the full Tanya first.** The gold set covers all 53 chapters of Tanya
> Part I. If you only ingested two chapters back in Lesson 0.3, most questions can't be answered
> and your hit@k will look terrible — *correctly*, because the corpus doesn't contain the
> answers. For meaningful numbers, ingest the whole book first:
> ```bash
> uv run maayan ingest --book "Tanya, Part I; Likkutei Amarim"   # no --limit = all chapters
> make index
> ```
> (This is a bigger download than the two-chapter slice, but a one-time cost.)

---

### Reading the table

You'll get something shaped like this (your exact numbers will differ):

```
Gold set: eval/goldset.yaml (NN questions)
Default-deny gate threshold: 0.45

Gold set: NN questions (P positive, G negative)

   k |   hit@k | recall@k
------------------------------
   1 |   0.620 |    0.480
   3 |   0.840 |    0.690
   5 |   0.900 |    0.780
  10 |   0.960 |    0.870

MRR: 0.712

Default-deny gate (higher is better):
  answered (of positives): 0.940
  refused  (of negatives): 0.889
```

How to read it, line by line:

- **The k rows.** As `k` grows, `hit@k` and `recall@k` can only rise — you're allowing more
  results, so it gets easier to have caught the right ones. The *shape* matters: a high
  `hit@1` means the very top result is usually right; a big jump from `hit@1` to `hit@5` means
  the right answer is often present but not ranked first (a job for rerank — Module 2.4). The
  `eval_ks` shown (1, 3, 5, 10) are config (`eval_ks`).
- **MRR.** One summary number for "how high, on average, is the first correct answer." Closer to
  1.0 = right answers sit near the top.
- **The gate block — don't skip it.** This is the part eyeballing never showed you.

---

### The default-deny gate rates (the line that's really about trust)

Recall from Module 3 that the system's defining behavior is **refusing** when nothing supports
an answer. The harness measures that directly, against the same `score_threshold` the live
system uses (`run_eval` takes it as an argument — read the docstring: "the eval measures the
same decision the system makes at answer time"). Two rates, and **both want to be high**:

| Rate | What it measures | Failure it catches |
|---|---|---|
| **answered (of positives)** | fraction of answerable questions whose `relevance` ≥ threshold | **over-refusal** — the gate is too strict and refuses good questions |
| **refused (of negatives)** | fraction of unanswerable questions whose `relevance` < threshold | **under-refusal** — the gate is too loose and fabricates |

This is the central tension of `score_threshold`, now visible as a trade-off you can *see*:

- Raise the threshold → `refused` goes **up** (good, catches more junk) but `answered` goes
  **down** (bad, starts refusing real questions).
- Lower it → the reverse.

The "right" threshold is the one that keeps **both** rates high on *your* corpus. That's why
Module 3.3 said you tune the threshold "with the eval harness" — *this* is the instrument. You're
not guessing `0.45`; you're reading what it does to both rates and choosing.

> #### Under the hood — positives and negatives do different jobs
> `run_eval` splits the gold set: **positive** cases (those with `expected_refs`) drive
> hit@k / recall@k / MRR — ranking quality. **Negative** cases (`should_refuse: true`, empty
> refs) are *excluded* from ranking metrics and instead feed `refusal_rate` — gate quality. A
> positive also contributes to `answer_rate`. So one gold set measures two different things:
> *can it find the right passage?* and *does it know when there's no right passage?* Lesson 4.3
> is about writing both kinds well.

---

### Comparing variants (justifying a change)

The real power: run several configurations on the *same* gold set, side by side.

```bash
uv run maayan eval --compare
```

This uses `default_variants()` (hybrid k=10, hybrid k=5, dense-only k=10 — see
harness.py) and prints one row per variant with hit / recall /
MRR / answer / refusal. Now "hybrid beats dense-only" stops being folklore (Lesson 2.3) and
becomes a number you can point at. This is exactly how you'd justify turning rerank on, or
switching embedding models, in Module 8.1.

---

### Hands-on

Full Tanya indexed (see the prerequisite box).

1. **Run the baseline.** `uv run maayan eval`. Read every line. Which `k` gives `hit@k` ≥ 0.9?
   Is `hit@1` high (top result usually right) or is there a big climb to `hit@5` (right answer
   present but mis-ranked)? Write down what that shape implies.

2. **Read the gate rates aloud.** What fraction of answerable questions would the system answer,
   and what fraction of unanswerable ones would it refuse? If either is low, say which failure
   it is (over- or under-refusal).

3. **Watch the threshold trade-off directly.** Re-run with a stricter and a looser gate:

   ```bash
   SCORE_THRESHOLD=0.65 uv run maayan eval
   SCORE_THRESHOLD=0.25 uv run maayan eval
   ```

   Note how `answered` and `refused` move in *opposite* directions. You've just seen, in
   numbers, why the threshold is a balance and not a "bigger is better" knob.

4. **Compare variants.** `uv run maayan eval --compare`. Does hybrid beat dense-only on your
   corpus? By how much, at k=5? That delta is the kind of evidence Module 8 turns into a
   decision.

---

### You should now be able to say…

- How to run the harness (`maayan eval`) and what it does end to end.
- How to read the k-rows and MRR, and what the *shape* (hit@1 vs. hit@5) tells you.
- What the two **gate rates** mean, that both should be high, and how `score_threshold` trades
  them off — the instrument for tuning the gate.
- How `--compare` turns a configuration choice into a defensible number.

Next: **4.3 — Gold sets & honest measurement** — the numbers are only as
honest as the gold set behind them. We'll see what makes a good case, why negative cases matter,
and add one yourself.

<div class="page-break"></div>


<a id="lesson-4-3"></a>


## Lesson 4.3 — Gold sets & honest measurement

> Module 4, Lesson 3 · ~20 min read + a hands-on you'll actually edit a file for.
> The one question this answers: **the metrics are only as trustworthy as the gold set behind
> them — so what makes a *good* gold case, and how do I add one?**

A gold set is the ruler you measure retrieval with. A bent ruler gives confident, precise,
*wrong* readings. This lesson is about keeping the ruler straight: what a good case looks like,
why negative cases are not optional, and the special gold set that measures the cross-text
claim. Then you'll add a case and re-run.

---

### What makes a good positive case

A positive case is `{question, expected_refs}`. Three properties separate a useful one from a
misleading one:

1. **The question is real.** Phrase it the way a person would actually ask — in Hebrew, with
   natural wording — not as a keyword-stuffed query reverse-engineered from the source. The
   whole point is to test retrieval against *genuine* questions.
2. **The expected refs are right and complete.** List the chapter(s) that truly answer it. If
   two chapters bear on it, list both — otherwise `recall@k` will punish retrieval for finding a
   legitimately-relevant passage you forgot to credit. (Remember chapter-level refs are fine;
   prefix matching handles segments — Lesson 4.1.)
3. **It tests *one* thing.** A question whose answer is scattered across ten chapters measures
   nothing clearly. Prefer cases with a crisp, locatable answer.

The danger to avoid: writing the question *after* looking at the passage, using its exact words.
That measures keyword overlap, not retrieval — and bge-m3 would "pass" for the wrong reason. Ask
the question first, then find its home.

---

### Why negative cases are not optional

Here's the subtle one. If your gold set contains *only* answerable questions, you can score a
perfect 1.0 on every ranking metric — with a system that **never refuses anything.** Ranking
metrics literally cannot see over-confidence, because they only ever ask answerable questions.

So a gold set that doesn't test refusal is measuring half the system and calling it whole. That's
why maayan's gold set includes **negative cases**:

```yaml
- question: "מהי נקודת הרתיחה של מים?"     # boiling point of water — not in Tanya
  should_refuse: true
  expected_refs: []
```

`should_refuse: true` with empty refs says: *the correct behavior here is to refuse.* These are
excluded from hit@k / recall@k and instead drive the `refused` rate from Lesson 4.2. A good gold
set deliberately includes questions the corpus *can't* answer — adjacent-but-absent topics, an
un-ingested text, a different discipline — so the gate is measured, not assumed. Read the header
comment in eval/goldset.yaml; it spells this out.

> #### Under the hood — the gold set measures two systems at once
> `GoldExample` (goldset.py) carries `should_refuse` precisely so
> one file can score both halves: positives test *retrieval ranking*, negatives test *the
> default-deny gate*. When you add cases, you're improving one or the other — be conscious of
> which. A corpus with great recall and a gate that never refuses is not trustworthy; the
> negative cases are what keep you honest about that.

---

### The cross-text gold set (a different question entirely)

There's a second gold set: eval/crosstext_goldset.yaml, run
with `uv run maayan eval --crosstext`. It measures something the main metrics don't: whether a
question whose answer spans **two or more books** actually pulls passages from *both*, rather than
burying one book under the other. (Its metric is book-diversity@k; it exists because the
cross-text "connect these sources" claim — Phase 4, Prompt 18 — needs its own honest measurement,
not a borrowed one.) The lesson generalizes: **a new capability needs its own gold set.** You
can't measure a new claim with the old ruler. (There's a third, `--develop`, for the develop step
— that's Module 6's territory.)

---

### Hands-on

Full Tanya indexed (Lesson 4.2 prerequisite). You're going to edit the gold set.

**1. Add a positive case.** Open eval/goldset.yaml. Think of a genuine
question about Tanya Part I — ask it in your own words *first* — then find the chapter that
answers it. Add an entry under `examples:` (mind the indentation):

```yaml
  - question: "כיצד התורה והמצוות מלבישים את האור האין סוף?"
    expected_refs: ["Tanya, Part I; Likkutei Amarim 4"]
    note: my first gold case
```

Re-run and find your case's effect:

```bash
uv run maayan eval
```

Did the aggregate metrics shift slightly? (With ~50 cases, one case moves the average a little.)
More importantly: confirm it *ran* (the question count went up by one). If retrieval found your
chapter, you wrote a case the system passes; if not, you've either found a real retrieval weakness
or mis-attributed the chapter — both are worth investigating. *That* is the gold set working.

**2. Add a negative case — and watch the gate get measured.** Add a question the corpus genuinely
can't answer:

```yaml
  - question: "מהו דין מוקצה בשבת?"          # a halachic question — not in Tanya
    should_refuse: true
    expected_refs: []
```

Re-run. The negative count goes up by one, and the `refused (of negatives)` rate now includes
your case. If it's *not* refused, your gate is too loose for this corpus — exactly the kind of
finding ranking metrics would have hidden.

**3. Tie it to a real decision (preview of Module 8).** With your two new cases in place, run
`uv run maayan eval --compare`. You now have a slightly richer ruler. Imagine you were deciding
whether to enable rerank: which column would you watch, and what change would justify the switch?
Write down your answer — Module 8.1 is exactly this move.

> When you're done experimenting, you can keep your good cases (they make the gold set better!)
> or `git checkout eval/goldset.yaml` to revert. Better gold = more trustworthy numbers, so
> well-written cases are a genuine contribution.

---

### You should now be able to say…

- What makes a **good positive case** (real question, correct *and complete* refs, tests one
  thing) and the trap of writing the question from the passage's words.
- Why **negative cases** are essential — ranking metrics are blind to over-confidence; only
  `should_refuse` cases measure the gate.
- Why a new capability (cross-text co-retrieval, the develop step) needs **its own gold set**.
- How to add a case and read its effect.

**That's Module 4.** You can now measure retrieval honestly: the metrics (4.1), how to run and
read the harness including the gate rates (4.2), and how to keep the ruler straight (4.3). You've
finished the *universal* RAG half of the curriculum (Modules 0–4) — you can explain and measure
any RAG system.

Next: **Module 5** turns to *this* system's engineering spine — the house rules (dependency
injection, typed boundaries, config-driven, the Clock) that let you change maayan without fear.
When you're ready, ask me to **build out Module 5**.

<div class="page-break"></div>


<a id="module-5"></a>


# Module 5 — How it's built to last (the engineering spine)


<p class="module-goal">Understand the house rules that make the system testable, swappable, and trustworthy.</p>

<div class="page-break"></div>


<a id="lesson-5-1"></a>


## Lesson 5.1 — Dependency injection: why nothing constructs its own collaborators

> Module 5, Lesson 1 · ~20 min read + a hands-on tracing one command.
> The one question this answers: **why does the business logic never build its own embedder,
> database, or model — and what does "passing them in" actually buy me?**

You've crossed into the second half of the curriculum. Modules 0–4 were *RAG, universal*. From
here it's *this* system — the engineering discipline that lets you change maayan without fear.
And the keystone of that discipline is **dependency injection (DI)**. You've already seen its
payoff three times (the swappable backend in 3.1, the fakeable embedder in 1.1, the in-memory
database in 2.1); this lesson names the pattern and shows you the seam.

---

### The rule, stated plainly

From CLAUDE.md, house rule #3:

> Services — embedder, Qdrant client, generation backend, clock, settings — are **passed in**,
> never constructed inside business logic. Construction happens at the edges (`cli.py`, the UI
> route wiring, tests).

That's the whole idea: **logic depends on interfaces; construction lives at the edges.** A
class that does real work (like `RAGService`) never says `OpenRouterBackend(...)`. It is
*handed* something that satisfies the `GenerationBackend` protocol and uses it. Who built it,
and which concrete type it is, is decided elsewhere — at the program's edge.

---

### What "the edge" looks like

Open maayan/cli.py and read the `ask` command. Notice the shape — it's
the same every time:

```python
settings  = _cfg()                                   # 1. resolve config
embedder  = build_embedder(settings)                 # 2. build concrete services
retriever = build_retriever(settings, embedder=embedder)
backend   = build_generation_backend(settings)
rag = RAGService(retriever, backend, score_threshold=settings.score_threshold)  # 3. inject
... rag.ask(question, ...)                            # 4. run logic
```

The CLI is a **wiring harness**, nothing more — the file's own docstring says it "stays a thin
layer… No business logic lives here." It reads config, calls the `build_*` factories to
construct the real embedder / retriever / backend, and *injects* them into `RAGService`. The
service then just… uses what it was given. Every entrypoint (CLI command, UI route, test) does
this same construct-at-the-edge, inject-into-logic dance.

> #### Under the hood — the protocols are the seams
> Go back and notice how many *protocols* you've met: `Embedder` (1.1), `GenerationBackend`
> (3.1), `Reranker` (2.4), `Retrieving` (2.3), `Clock` (5.4). Each is a small interface that
> says "anything shaped like this will do." The business logic depends only on these shapes.
> The `build_*` factories (`build_embedder`, `build_generation_backend`, …) are the only places
> that name concrete classes, and they pick based on `Settings`. So the dependency graph points
> *inward* to interfaces, and construction sits *outward* at the edges. That's DI in one
> sentence.

---

### The three things DI buys you (you've already used all three)

This isn't architecture for its own sake. Every house value you've seen so far *is* DI paying
off:

| Benefit | Where you saw it | Why DI makes it free |
|---|---|---|
| **Swap** implementations by config | OpenRouter ↔ Ollama (3.1); server/in-memory Qdrant (2.1) | logic depends on the protocol, so the concrete type can change |
| **Test** with fakes — no network, no models | `FakeRetriever` + `RecordingBackend` (5.4) | inject a fake that satisfies the same protocol |
| **Reuse** a costly object across services | one embedder shared by retriever *and* capture in `ask` | the edge builds it once and hands it to both |

That third one is visible right in the `ask` command: `embedder = build_embedder(settings)` is
built **once** and passed to both `build_retriever(...)` and (later) the capture service. If
each service constructed its own embedder, you'd load bge-m3 twice. Because construction is at
the edge, the edge can be smart about sharing.

---

### Why this matters *here* specifically

maayan makes promises: it can run fully local (privacy), it refuses to fabricate (trust), and
every change ships with tests (the house rules). **None of those are achievable without DI.**
You can't swap to a local model if `RAGService` hardcodes OpenRouter. You can't *prove*
default-deny never calls the model (the test you'll read in 5.4) if you can't inject a fake
backend and assert it was never called. DI isn't decoration — it's the mechanism that makes the
system's guarantees *testable and swappable* instead of merely promised.

---

### Hands-on

Trace one `ask` from the edge to the logic. No need to run anything — follow the code.

1. **Find the construction.** In cli.py, in the `ask` command, list the
   four things that get built before `RAGService` is created (config, embedder, retriever,
   backend). These are the *dependencies*.

2. **Find the injection.** Locate the line `RAGService(retriever, backend, ...)`. The retriever
   and backend are *passed in*. Now open rag.py and read
   `RAGService.__init__` — confirm it just **stores** what it's handed (`self._backend = backend`)
   and never constructs anything itself.

3. **Prove the negative.** Search `rag.py` for `build_`, `OpenRouter`, and `Qdrant`. You won't
   find them. The logic file names *no* concrete collaborator and *no* factory — only protocols.
   That absence is the whole pattern.

4. **Spot the reuse.** Back in `ask`, find where the single `embedder` is handed to more than
   one consumer. Why would building it twice be wasteful? (Recall what loading bge-m3 costs from
   Lesson 0.3.)

---

### You should now be able to say…

- The DI rule: **logic depends on protocols; construction happens at the edges** (cli.py, UI
  wiring, tests).
- That `cli.py` is a thin wiring harness — build with factories, inject into services, run.
- The three payoffs — **swap, test, reuse** — and that each house guarantee you've seen relies
  on them.
- Why the logic files name no concrete collaborator (only protocols), and why that's the point.

Next: **5.2 — Typed throughout, pydantic at every boundary** — the
other half of "change without fear": every datum crossing a module boundary is a typed model,
checked by `mypy --strict`.

<div class="page-break"></div>


<a id="lesson-5-2"></a>


## Lesson 5.2 — Typed throughout, pydantic at every boundary

> Module 5, Lesson 2 · ~15 min read + a hands-on at the terminal.
> The one question this answers: **why is every piece of data that moves between modules a
> typed model instead of a plain dict — and what does `mypy --strict` actually catch?**

In 5.1, DI let you swap and fake collaborators. This lesson is the other guardrail that lets
you change code without fear: **types**. maayan is typed end to end and checked in strict mode,
and every datum that crosses a module boundary is a **pydantic model**, not a loose dict or
tuple. This is house rule #1, and once you feel it, you'll miss it everywhere else.

---

### The rule

From CLAUDE.md, house rule #1:

> **Typed throughout, mypy-clean.** `mypy` runs in strict mode. Every datum that crosses a
> module boundary is a **pydantic model**, not a loose dict/tuple.

Two halves. **Typed throughout** means function signatures declare what they take and return,
and a type checker verifies the whole graph hangs together. **Pydantic at the boundary** means
when data leaves one module for another, it travels as a *named, validated model* — `Chunk`,
`SearchResult`, `Embedding`, `Answer`, `RetrievalResult`, `GoldExample` — never an anonymous
`dict[str, Any]` that the receiver has to guess the shape of.

---

### Why a model and not a dict

You've already met the spine of models: `Chunk` (1.2), `Embedding` (1.1), `SearchResult` /
`RetrievalResult` (2.3), `Answer` / `ContextTurn` (3.2–3.4), `GoldExample` (4.1). Imagine the
alternative — passing a bare dict between modules:

```python
# the dict way (NOT how maayan does it):
result = {"ref": "...", "txt": "...", "score": 0.5}   # was it "txt" or "text"? str or float?
...
score = result["scor"]   # typo. KeyError at runtime, in production, on Shabbos.
```

Versus the model way (how it *is* done — see retrieve/models.py):

```python
class SearchResult(BaseModel):
    ref: str
    text: str
    score: float
    lang: str
    source: str
    payload: dict[str, Any]
```

Now the field is `text`, always; it's a `str`, always; `score` is a `float`, always. A typo
(`result.scor`) is caught by mypy *before the code runs*, not by a user hitting a `KeyError`.
And the model is **self-documenting**: you read `SearchResult` and you know exactly what a
result is, without spelunking through the code that produced it. The model *is* the contract
between the producer and every consumer.

> #### Under the hood — pydantic also *validates*
> A pydantic model isn't just a type hint; at construction it **checks** the data. Build a
> `SearchResult` with `score="high"` and it raises immediately, at the boundary, with a clear
> error — rather than letting a bad value flow three modules downstream and corrupt something
> subtle. So the boundary models do double duty: they're the *static* contract mypy verifies,
> and the *runtime* gate that rejects malformed data the moment it tries to cross. This is
> exactly why the house rule targets *boundaries* specifically — that's where data from the
> outside world (Sefaria, the model, the UI) enters and must be trusted.

---

### What `mypy --strict` buys you

Strict mode means mypy won't let you be vague: no implicit `Any`, no untyped function, no
silently-ignored `None`. Run it:

```bash
make typecheck
```

It checks the *entire* call graph for consistency. The practical payoff, in the context of
everything you've learned:

- **Refactor without fear.** Rename `SearchResult.text` and mypy lists every site that must
  change — across `retrieve`, `generate`, `cli`, `ui`. You're never hunting for a missed caller.
- **The protocols are enforced.** Remember the DI seams from 5.1 (`Embedder`,
  `GenerationBackend`, …)? mypy checks that every concrete implementation *actually* matches its
  protocol — so "drop-in replacement" is a guarantee, not a hope. A backend missing a method, or
  with the wrong signature, fails `make typecheck`.
- **`None` is handled on purpose.** Strict mode forces you to deal with the "what if it's
  missing?" case, which is exactly where sloppy code crashes.

This is why "definition of done" in CLAUDE.md includes `make typecheck` being clean, right next
to tests passing.

---

### Hands-on

1. **Run the checker.** From the repo root:

   ```bash
   make typecheck
   ```

   It should be clean (that's the standard the repo holds). Note that it checks *all* of
   `maayan/`, not just files you touched.

2. **Break it on purpose, then read the error.** Open retrieve/models.py
   and temporarily rename `SearchResult.text` to `txt`. Run `make typecheck` again. Read the
   errors: mypy points at *every* place that used `.text` — `build_context` in `rag.py`, the CLI
   printing, etc. That list is the exact blast radius of the change. **Revert** the rename
   (`git checkout maayan/retrieve/models.py`).

3. **See validation reject bad data.** At the runtime layer:

   ```bash
   uv run python - <<'PY'
   from maayan.retrieve.models import SearchResult
   try:
       SearchResult(ref="x", text="t", score="high", lang="he", source="sefaria", payload={})
   except Exception as e:
       print("rejected at the boundary:", type(e).__name__)
   PY
   ```

   `score="high"` is rejected immediately — the model won't let a malformed value cross. That's
   the runtime half of the guarantee.

---

### You should now be able to say…

- House rule #1: **typed throughout, mypy-strict, pydantic at every boundary** — and why
  boundaries specifically.
- Why a boundary **model** beats a bare dict (typo-proof, self-documenting, *validated*).
- What `mypy --strict` buys you: fearless refactors, enforced protocols, deliberate `None`
  handling — and that `make typecheck` clean is part of "done."

Next: **5.3 — Config-driven everything** — the third house rule: every
tunable number lives in one `Settings`, never hardcoded in logic.

<div class="page-break"></div>


<a id="lesson-5-3"></a>


## Lesson 5.3 — Config-driven everything

> Module 5, Lesson 3 · ~15 min read + a hands-on at the terminal.
> The one question this answers: **where do all the tunable numbers live, and why is there a
> rule that *none* of them may be written into the logic?**

You've now turned a dozen knobs across this curriculum: `score_threshold`, `top_k`,
`embed_model`, `rerank_enabled`, the boosts, `generation_backend`. Every one of them came from
the same place. This lesson is that place — `Settings` — and the house rule that keeps it the
*single* source of truth. It's short, because the idea is simple; but the discipline is what
makes the whole system tunable.

---

### The rule

From CLAUDE.md, house rule #4:

> **Config-driven.** Model names, collection names, top-k, thresholds, base URLs, the corpus
> book list — all come from `maayan/config.py` (`Settings`). Nothing is hardcoded in logic.

Open maayan/config.py. Its docstring restates it: "All tunables live
here… Nothing in the codebase may hardcode model names, collection names, URLs, top-k,
thresholds, etc." `Settings` is a `pydantic-settings` model — every knob is a typed field with
a default, and it loads overrides from the environment / `.env`.

---

### One place, three ways to set it

Because `Settings` is a pydantic-settings model, the same field can be set three ways, in
increasing specificity:

1. **The default in `config.py`** — e.g. `score_threshold: float = Field(default=0.45)`.
2. **An environment variable / `.env`** — `SCORE_THRESHOLD=0.6` overrides the default. (This is
   why every "set a knob for one run" hands-on used an env var: `SCORE_THRESHOLD=0.0 uv run …`.)
3. **A per-call override at the edge** — e.g. `settings.model_copy(update={...})`, which is how
   `--mock` swaps in the embedded Qdrant and hashing embedder (you saw `_cfg()` do this in 5.1).

What you *won't* find is a fourth way: a number written directly into a logic file. There's no
`if relevance < 0.45` buried in `rag.py` — it's `self._score_threshold`, injected from
`settings.score_threshold`. Search for it and you'll see the threshold travels from `Settings`
→ the CLI edge → `RAGService`. The logic never names the number.

> #### Under the hood — config meets DI
> Notice the docstring's careful wording: `get_settings()` is "a cached convenience for
> entrypoints (CLI / UI), not for use inside library functions." Library code doesn't *reach
> out* and grab global config; it receives the specific values it needs, injected (Lesson 5.1).
> `get_settings()` lives only at the edges. So config and DI are the same discipline from two
> angles: **all tunables in one typed place, and that place is read at the edge and injected
> inward** — never grabbed from a global deep inside the logic. That's what makes a knob both
> discoverable (it's in `config.py`) and testable (a test injects its own `Settings`).

---

### Why this is non-negotiable

Three concrete payoffs you've already depended on:

- **Tunability.** You changed retrieval behavior in Module 4 by setting `SCORE_THRESHOLD` — no
  code edit, no redeploy. Every knob being external is what made "tune with the eval harness"
  possible.
- **No secrets in code.** API keys are config fields too — but `SecretStr`, read from env, never
  hardcoded, never logged (house rule #5). Centralizing config is also how secrets stay *out* of
  the source.
- **One audit surface.** Want to know everything that can change the system's behavior? Read one
  file. New tunable? It goes in `config.py` — that's literally in the "definition of done."

The anti-pattern this forbids is the magic number scattered through logic: a `0.45` here, a
`"BAAI/bge-m3"` there, a `top=8` somewhere else. Those are invisible, un-tunable, and impossible
to audit. maayan refuses them on principle.

---

### Hands-on

1. **Trace a knob home.** Pick one you've used — say `score_threshold`. Find its definition in
   config.py (read its description — it's a good one). Then find where
   it's *injected*: search `cli.py` for `score_threshold` and confirm it's passed into
   `RAGService(...)`. The number lives in config; the logic receives it.

2. **List the surface.** Skim `config.py` top to bottom. In ~30 seconds you can see *every*
   behavior-affecting knob in the system — generation backend & model, embedder, Qdrant URL &
   collection, top-k, threshold, boosts, rerank, the book lists, eval paths. That single-file
   readability is the rule paying off.

3. **Override without editing code.** Prove a knob is external by changing behavior with an env
   var only (you did this in 4.2; do it deliberately now):

   ```bash
   uv run maayan eval                       # baseline threshold (0.45)
   SCORE_THRESHOLD=0.7 uv run maayan eval    # stricter gate — no code changed
   ```

   The gate's `refused` rate moves, and you never opened an editor. That's config-driven
   behavior.

4. **Find a secret done right.** Locate `openrouter_api_key` in `config.py`. Note its type
   (`SecretStr`) and that it's read from env. In one sentence: why is centralizing config also
   the thing that keeps the key out of the codebase and the logs?

---

### You should now be able to say…

- House rule #4: **all tunables live in `Settings` (`config.py`); nothing hardcoded in logic.**
- The three ways a knob is set (default → env/`.env` → per-call override) and that logic never
  names the raw number.
- How config and DI are the same discipline: tunables centralized, read at the edge, injected
  inward (and `get_settings()` is edge-only).
- Why this gives tunability, secret-safety, and a single audit surface.

Next: **5.4 — The Clock, and testing without the network** — the
last house rule (no `time.sleep` in logic) and how all of these rules together let the test
suite run with no network and no real models.

<div class="page-break"></div>


<a id="lesson-5-4"></a>


## Lesson 5.4 — The Clock, and testing without the network

> Module 5, Lesson 4 · ~20 min, hands-on at the terminal.
> The one question this answers: **why is there no `time.sleep` in the code, and how does the
> whole test suite run with no network calls and no 2 GB model downloads?**

This lesson ties the engineering spine together. You've seen DI (5.1), typed boundaries (5.2),
and config (5.3). Here's the last house rule — the injectable **Clock** — and then the payoff
all four rules were building toward: a test suite that's **fast, deterministic, and offline**,
which is what lets every change ship with tests (house rule #7).

---

### The Clock: no `time.sleep` in logic

From CLAUDE.md, house rule #2:

> **No `time.sleep` in business logic.** Use the injectable `Clock`. Any waiting/backoff is
> `async` and driven by the injected clock so tests never actually sleep.

Open maayan/clock.py. It's three small pieces:

- **`Clock`** — a protocol: `now()` (current UTC time), `monotonic()` (elapsed-time measurement,
  e.g. rate limiting), and `async sleep(seconds)`.
- **`SystemClock`** — the real one: `datetime.now(UTC)`, `time.monotonic()`,
  `asyncio.sleep()`. Used in production.
- **`FakeClock`** — the test one: `sleep()` **records** the duration and advances *virtual* time
  without ever blocking. It "advances only when `sleep` is called; never blocks."

Why bother? Because code that calls `time.sleep(30)` directly is **untestable** — a test of it
would take 30 real seconds. By taking a `Clock` by injection (the DI rule again), the same
waiting/backoff logic runs instantly under `FakeClock` in tests, and you can even *assert* on
what it tried to wait (`fake.slept == [30.0]`). Time becomes a dependency you control, not a
wall you hit. (You met this need concretely with the chabad ingester's rate-limiting in earlier
phases — that's where a real wait exists, and the Clock is how it's tested without waiting.)

---

### The payoff: the test suite is offline by construction

Now the part where all four house rules cash out. From CLAUDE.md, house rule #7: unit tests
**mock the network and the models** — no real OpenRouter, Sefaria, or model downloads — and use
ephemeral/in-memory Qdrant. Run them:

```bash
make test
```

It's fast, and it touches *nothing* external. That's only possible because of the rules you've
learned. Here's the mapping, made concrete in real test files:

| To avoid… | The test injects… | Seen in |
|---|---|---|
| downloading bge-m3 (2 GB) | `HashingEmbedder` (deterministic, instant) | `tests/test_index.py`, `tests/test_retrieve.py` |
| running Docker / a real DB | `QdrantClient(location=":memory:")`, `ChunkStore(":memory:")` | `tests/test_index.py`, `tests/test_retrieve.py` |
| calling the cloud model | a fake `GenerationBackend` (`RecordingBackend`) | `tests/test_rag.py` |
| a real HTTP call to Ollama | `respx` mocking the endpoint | `tests/test_ollama.py` |
| real wall-clock waiting | `FakeClock` | wherever waiting exists |

Every one of those is an *injected* fake satisfying the *same protocol* as the real thing
(5.1), carrying *typed* data (5.2), selected without touching logic (5.3). The house rules
aren't four separate ideas — they're one idea (substitutable, typed, edge-constructed
collaborators) that happens to pay off as testability.

---

### The test that proves the system's central promise

Open tests/test_rag.py and read
`test_empty_retrieval_refuses_without_calling_model`:

```python
def test_empty_retrieval_refuses_without_calling_model() -> None:
    backend = RecordingBackend()
    rag = RAGService(FakeRetriever([], relevance=0.0), backend, score_threshold=0.4)
    answer = rag.ask("שאלה כלשהי")
    assert answer.grounded is False
    assert backend.calls == []   # default-deny: model never called
```

Sit with that last line. `RecordingBackend` records every call to `generate`. The assertion
`backend.calls == []` is a **machine-checked proof** of the most important claim in the whole
system — the default-deny gate from Lesson 3.3 — *"the model is never called when there's no
source."* Not a comment, not a hope: a test that fails the build if the gate ever regresses.

And it's only writable because of DI: you can hand `RAGService` a fake backend and a fake
retriever and *watch* whether the door stayed shut. Trust, made testable. The companion tests in
the same file prove the rest of Module 3 the same way — context never bypasses the gate, only
retrieved refs get cited, sources land in the prompt. The trust core has a test for each
promise.

---

### Hands-on

1. **Run the suite.** `make test`. Note how quickly it finishes and that your network/Docker
   are irrelevant to it. (If you want, disconnect from the internet and run it again — it
   passes.)

2. **Read the proof.** Open `tests/test_rag.py`. Find the two refusal tests
   (`...refuses_without_calling_model`). Identify the fake backend and the assertion that proves
   the model wasn't called. In one sentence: which house rule (5.1) makes this test *possible* to
   write?

3. **Meet the fakes.** In `tests/test_index.py`, find `QdrantClient(location=":memory:")` and
   `HashingEmbedder`. Confirm: this test exercises the *real* indexing pipeline (`index_chunks`)
   with *fake* collaborators — same logic, no downloads, no Docker. That's the pattern
   everywhere.

4. **Feel the Clock idea.** In `clock.py`, read `FakeClock.sleep`. It appends to `self.slept` and
   bumps virtual time. Write down: how would you test that some backoff logic "waited 1s, then
   2s, then 4s" *without your test taking 7 seconds*? (Answer: assert on `fake.slept`.)

---

### You should now be able to say…

- House rule #2: **no `time.sleep` in logic** — waiting takes an injected `Clock`, so
  `FakeClock` makes time-dependent code instant and assertable.
- Why `make test` is **fast, deterministic, and offline**: every external thing (model, DB,
  cloud, HTTP, time) is an injected fake satisfying the real protocol.
- That the house rules are one idea — substitutable, typed, edge-constructed collaborators — and
  that testability is its payoff.
- That the default-deny promise is **machine-proven** by `backend.calls == []`.

**That's Module 5 — the engineering spine.** You now understand *why* maayan is built the way it
is: DI (5.1), typed boundaries (5.2), config (5.3), and the Clock + offline tests (5.4) together
make the system swappable, auditable, and trustworthy — so you can change it without fear.

Next: **Module 6** — the differentiator. We open the capture & develop loop: how a scholar's
reasoning becomes durable, retrievable, attributed knowledge. When you're ready, ask me to
**build out Module 6**.

<div class="page-break"></div>


<a id="module-6"></a>


# Module 6 — The differentiator (the capture & develop loop)


<p class="module-goal">Understand how a scholar's reasoning becomes durable, retrievable, attributed knowledge.</p>

<div class="page-break"></div>


<a id="lesson-6-1"></a>


## Lesson 6.1 — Provenance & the source taxonomy

> Module 6, Lesson 1 · ~15 min read + a hands-on at the terminal.
> The one question this answers: **every chunk carries a `source` — what are the kinds, and why
> does the system insist on always knowing *who* made each piece of knowledge?**

You've reached the differentiator. Modules 0–5 built a *very good RAG system* — but other people
have built RAG. What makes maayan *yours* is the **capture loop**: a scholar's reasoning becomes
durable, retrievable, attributed knowledge in the same index as the printed text. The whole loop
rests on one field you met back in Lesson 1.2 — `Chunk.source` — so we start there.

---

### Why provenance is the foundation, not a detail

In Torah, *who said it* is inseparable from *what was said*. "The Alter Rebbe writes…" and "my
chavrusa suggested…" are different epistemic claims, and conflating them is a serious error. A
system that pools printed text and human conjecture into one undifferentiated blob would be
worse than useless — it would launder opinion as Torah.

So maayan refuses to forget where anything came from. **Every chunk carries a `source` tag**, and
retrieval, display, and the trust rules all key off it. This is also why printed text is
**immutable**: you never *edit* a `sefaria` chunk to add your insight — you add a *new* chunk
with *your* provenance beside it. The text stays the text; your contribution stays yours.

---

### The five sources

Open docs/RUNBOOK.md §0 and read the provenance table. Five values:

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

> #### Under the hood — attribution is *enforced*, not requested
> It's not enough to *suggest* people attribute their work — the models make it structural. Open
> capture/models.py and lexicon/models.py:
> both `Annotation` (a contribution) and `Term` have a `field_validator` on `author` that
> **rejects a blank author** — "no anonymous/default contributions." You *cannot* create an
> attributed-source chunk without saying who you are. Provenance isn't a nice-to-have logged off
> to the side; it's a precondition the type system refuses to skip. (The same care shows up in
> `derived`: a `Development` carries the seed's author, the model id, and the refs it was
> grounded on — full lineage, Lesson 6.4.)

---

### Retrieval growth, not model training

One more idea the RUNBOOK states and that reframes everything: when you "teach the Assistant,"
you are **inserting a new chunk into the knowledge base** — not retraining a model. The next
question simply *retrieves* your contribution alongside the text. That's why the whole loop runs
locally with no GPU training, and why it's instant: teaching = one more searchable, attributed
chunk. (Lesson 8.4 contrasts this with fine-tuning, and why retrieval-growth is the right
backbone.)

---

### Hands-on

1. **Read the taxonomy at the source.** Open RUNBOOK §0, read the five-row
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

### You should now be able to say…

- Why provenance is foundational for Torah (who-said-it is inseparable from what-was-said), and
  why printed text is **immutable** — you add beside it, never edit it.
- The five `source` values, which are printed text vs. the capture loop, and that all five share
  one collection but stay distinguishable.
- That attribution is **enforced** by the models (author required), with full lineage on derived
  chunks.
- That teaching the system is **retrieval growth** (a new chunk), not model retraining.

Next: **6.2 — Capture: an expert note becomes a retrievable chunk** — we make
the first non-printed chunk: take a scholar's connection and watch it become searchable knowledge
in the same index.

<div class="page-break"></div>


<a id="lesson-6-2"></a>


## Lesson 6.2 — Capture: an expert note becomes a retrievable chunk

> Module 6, Lesson 2 · ~25 min, hands-on at the terminal.
> The one question this answers: **how does a scholar's correction or connection actually become
> a searchable chunk that future questions retrieve — closing the loop?**

This is the lesson where the loop *closes* for the first time. In Lesson 0.3 you got a `Session`
id from every `ask` and were told it "matters later." Later is now. We'll take a real
contribution, attach it to a session, and watch it become an `expert` chunk that surfaces in
retrieval beside the printed text. The capture loop is the point of the whole system — and it's
about to run in your hands.

---

### The two records: Session and Contribution

Open maayan/capture/models.py. Two models:

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

### What `add_annotation` does — the loop, in four steps

Open maayan/capture/service.py and read `add_annotation`. It
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

> #### Under the hood — same collection, same retrieval, on purpose
> Notice `add_annotation` calls the *same* `self._index.upsert_chunks` you met in the indexing
> pipeline (Lesson 2.2), into the *same* collection. There is no separate "expert store" that
> retrieval has to also-check. An `expert` chunk is a first-class citizen of the index — which
> is precisely why tomorrow's question retrieves it without any special handling. The only thing
> that distinguishes it is its `source` tag (for display/provenance) and, optionally, a ranking
> boost (Module 7.2). All collaborators are injected (it shares the one embedder built in `ask`,
> per Lesson 5.1).

---

### Hands-on — close the loop yourself

Qdrant up, corpus indexed, OpenRouter key set. Follow RUNBOOK §6 if you want the
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

### You should now be able to say…

- The two capture records — **`Session`** (the recorded ask) and **`Annotation`/`Contribution`**
  (an attributed note on it) — and the four `kind`s.
- The four steps of `add_annotation` (validate → convert → persist → embed+upsert) and that the
  result is a `source="expert"` chunk in the **same** collection as printed text.
- Why that means future questions retrieve a scholar's contribution with no special handling —
  the loop is retrieval growth.
- How to teach a connection and confirm it surfaces (`--source expert`).

Next: **6.3 — Seeds vs. corrections, and the develop step** — not
every contribution is a finished thought. Some are *seeds*: knowledge plus a directive for the
model to develop, grounded in the corpus or honestly refused.

<div class="page-break"></div>


<a id="lesson-6-3"></a>


## Lesson 6.3 — Seeds vs. corrections, and the develop step

> Module 6, Lesson 3 · ~25 min, hands-on at the terminal.
> The one question this answers: **what if a scholar has a half-formed idea — knowledge plus
> "now work this out from the texts"? How does the system develop it without fabricating?**

Lesson 6.2's contributions were *finished* thoughts — a correction, a connection — that go
straight into the index. But sometimes a scholar has something looser: a framework, often drawn
from texts *outside* this corpus, plus an instruction: "develop this from the sources we have."
That's a **seed**, and the **develop** step is how maayan grows it — under the very same
default-deny discipline you learned in Module 3.

---

### A seed = knowledge + a directive (kept apart)

Look again at `Annotation` in capture/models.py. Two fields
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

### The develop step mirrors RAG — same gate, new verb

Open maayan/develop/service.py. Read the module docstring:
"The shape mirrors `RAGService` on purpose — same default-deny discipline, same citation hygiene,
a new verb." The `develop` method:

1. **Retrieves fresh** on the seed (`body` + `directive` together — that's `_build_query`).
2. **DEFAULT-DENY gate** — *the same gate from Lesson 3.3*: if `relevance < score_threshold`,
   it returns a refusal `Development` with **no model call**. Read it
   (service.py): `if not sources or retrieval.relevance <
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

> #### Under the hood — an honest refusal is a *result*, not an error
> Read the `Development` model (develop/models.py). It carries
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

### Hands-on — plant a seed and develop it

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

### You should now be able to say…

- What distinguishes a **seed** from a correction/connection: a `directive` (kept separate from
  `body`, so it never pollutes retrievable text) and `opens_aspect`.
- That **develop mirrors RAG**: retrieve → same default-deny gate → grounded, cited generation,
  with the seed as non-citable framework and only sources citable.
- That an **honest refusal is a first-class result** (`grounded=False`, `model=""`) — the corpus
  didn't support the seed, and no model was called.
- That a development is a **proposal**, not yet corpus, until approved.

Next: **6.4 — The approval gate → derived corpus** — why a model's
development stays a proposal until a human says yes, and what happens to lineage when you approve.

<div class="page-break"></div>


<a id="lesson-6-4"></a>


## Lesson 6.4 — The approval gate → derived corpus

> Module 6, Lesson 4 · ~20 min, hands-on at the terminal.
> The one question this answers: **why is a model's development only a *proposal* until a human
> approves it — and what exactly happens, with what lineage, when you say yes?**

In Lesson 6.3 the develop step produced a grounded `Development` — but it stopped at
`status="proposed"` and was *not* indexed. This lesson is the gate between "the model suggested
this" and "this is now part of our knowledge." It's a small amount of code with a large amount of
principle: **model output is a proposal until a human approves it.**

---

### Why a human gate at all

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

### Approve vs. reject

Open maayan/develop/service.py and read the two methods:

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

> #### Under the hood — full lineage travels with the derived chunk
> Re-read the `Development` model (develop/models.py). An
> approved development carries everything needed to answer "where did this come from?": `seed_id`
> (which seed), `author` (whose seed — carried so the derived chunk attributes the human, not the
> model), `model` (which model generated it), `thread_id` (which line of inquiry), `cited_refs`
> (what it cited), and `grounded_in` (what was retrieved for it). So a `derived` chunk is never
> an orphan claim — it's a fully traceable artifact: *this human's seed, developed by this model,
> grounded in these refs, approved.* That lineage is what lets you trust a derived chunk the way
> you trust a cited answer — you can always walk it back to its sources and its author.

---

### Hands-on — approve, then re-ask

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

### You should now be able to say…

- Why model output is a **proposal until a human approves** it — grounding prevents fabrication,
  but only a person judges quality.
- That **approve** indexes a `derived` chunk while **reject** changes nothing, and that an
  **ungrounded** development *cannot* be approved.
- That an approved `derived` chunk carries **full lineage** (seed, author, model, thread, cited
  and grounded-in refs) — a traceable artifact, not an orphan claim.
- That the full loop is **seed → develop → approve → retrieved**.

Next: **6.5 — Threads & the term lexicon** — the two supporting
structures: persistent topic threads that hold a line of inquiry together, and the lexicon that
protects Holy Names from being mangled.

<div class="page-break"></div>


<a id="lesson-6-5"></a>


## Lesson 6.5 — Threads & the term lexicon

> Module 6, Lesson 5 · ~20 min, hands-on at the terminal.
> The one question this answers: **what holds a multi-step line of inquiry together over time,
> and how does the system protect a Holy Name from being treated as an abbreviation to expand?**

Two supporting structures finish the capture loop. **Threads** give a line of inquiry a spine —
so an ask, a seed, and its development read as one evolving conversation rather than scattered
records. The **lexicon** lets you define Holy Names and technical terms as first-class entities,
and — closing a loop opened back in Lesson 1.3 — *protects* them from the abbreviation expander.
Neither is the headline feature; both are what make the loop livable.

---

### Threads: a reopenable line of inquiry

Open maayan/threads/models.py. A **`Thread`** is "a single line
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
ThreadService is small: `start_thread`, `add_turn`,
`get_thread_with_turns`, `list_threads`.

> #### Under the hood — threads feed context, but never grounding
> Recall Lesson 3.4: prior turns *interpret* a follow-up but are never citable. Threads are where
> those prior turns live. Read threads/flow.py: `to_context_turns`
> maps persisted `ThreadTurn`s down to the citation-free `ContextTurn`s the generator accepts, and
> `ask_in_thread` feeds only the last `max_context_turns` as context. So a thread makes the
> conversation *persistent and reopenable* without ever weakening the trust core — retrieval still
> runs on the current question, default-deny still fires first. The `ThreadTurn` → `ContextTurn`
> mapping is the clean seam (Lesson 3.4's "decoupled on purpose") that keeps the generator
> independent of the thread layer.

---

### The lexicon: terms as entities, and Holy Names protected

Open maayan/lexicon/models.py. A **`Term`** is a curated entity:
a `canonical` display form, `surface_forms` (variants to match), a `term_type`
(`name`/`sefirah`/`partzuf`/`expansion`/`concept`/`other`), a `definition`, optional `gematria`
and `related_terms`, a required `author`, and a `sacred` flag marking a **Holy Name**. Defining
one (`maayan add-term`) creates a `source="term"` chunk (Lesson 6.1) — so a term's *meaning*
becomes retrievable, just like expert and derived knowledge.

But the lexicon does something the other sources don't, and it's the payoff of a thread left
hanging since Lesson 1.3. Recall: the normalizer has a `expand_rashei_teivot` hook that can expand
abbreviations, and it carries a `protected` set of folded surface forms it will **never** expand.
Where does that set come from? **The lexicon.**

Read `protected_terms` in lexicon/service.py: it returns the
folded surface forms of every registered term, to be used as the expander's deny-list. So a token
like **ע״ב** — which *looks* like rashei-teivot but is actually the *Ab* expansion of the
Tetragrammaton (gematria 72), a Holy Name — once registered as a term, becomes **structurally
unexpandable**. The model header in lexicon/models.py says it
exactly: these "carry gershayim and *look* like rashei-teivot, but they are terms… not
abbreviations to expand."

> #### Under the hood — three lessons converge here
> This single mechanism ties together: (1) Lesson 1.3's `fold_surface` (terms are matched
> gershayim/nikkud-insensitively, so `ע״ב` / `ע"ב` / `עב` all register the same), (2) Lesson
> 1.3's `protected` parameter on `expand_rashei_teivot` (the deny-list), and (3) this module's
> provenance (`source="term"`, `author` required, `sacred` flag). The result: a Holy Name can be
> *defined* (its meaning retrievable) and *protected* (its form inviolable) at once. That's the
> system taking *sheimos* seriously — not as a guideline, but as a structural guarantee.

---

### Hands-on

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

### You should now be able to say…

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

<div class="page-break"></div>


<a id="module-7"></a>


# Module 7 — Running it for real (operating & tuning)


<p class="module-goal">Confidently operate, tune, and feed the system day to day.</p>

<div class="page-break"></div>


<a id="lesson-7-1"></a>


## Lesson 7.1 — Setup & dependencies

> Module 7, Lesson 1 · ~15 min read + a hands-on at the terminal.
> The one question this answers: **what do I actually install and start to run maayan, and why
> are the heavy pieces optional?**

You've understood the system; now you operate it. Module 7 is the operator's manual — setup,
knobs, backend choice, growing the corpus, the UI. We start at the foundation: dependencies and
the local services. The guiding design idea here is **the heavy stuff is opt-in**, so the
skeleton and the tests stay fast (you felt this in Module 5 — tests need none of it).

---

### Three dependency tiers (and why)

Open pyproject.toml and find `[project.optional-dependencies]`. maayan
splits its dependencies into a fast core plus two **extras**:

| Install | Adds | Needed for |
|---|---|---|
| `uv sync` | core: pydantic, typer, httpx, qdrant-client, openai | skeleton, CLI, **all unit tests** |
| `uv sync --extra ml` | `FlagEmbedding`, `torch` | real embeddings/rerank (bge-m3) — Module 1 on |
| `uv sync --extra ui` | `fastapi`, `uvicorn` | the web UI — Lesson 7.5 |

The reason for the split (stated in CLAUDE.md "Dependencies"): `torch` +
`FlagEmbedding` are large and slow to install, and `fastapi` is only for the browser UI. Keeping
them as extras means a fresh checkout installs and *tests* in seconds — the unit tests mock the
models (Lesson 5.4), so they never need `ml` at all. You only pay for the heavy deps when you do
real retrieval. For day-to-day operation you'll want both extras:

```bash
uv sync --extra ml --extra ui
```

---

### The two local services you start

maayan is local-first (Lesson 0.2). Two things run on your machine:

1. **Qdrant** — the vector database (Lesson 2.1). Start/stop it with Docker:
   ```bash
   make up      # Qdrant on :6333
   make down    # stop it
   ```
   No Docker? Set `QDRANT_URL=:memory:` (ephemeral) or a local path (`QDRANT_URL=data/qdrant`)
   in `.env` — `build_qdrant_client` handles all three (Lesson 2.1). Or pass `--mock` for an
   offline, no-Docker run (Lesson 5.1).
2. **The embedding model** — `bge-m3`, downloaded on first `index` (~2.3 GB, one-time), then
   cached and run locally (Lesson 1.1).

The only thing *not* local is the generation call (Lesson 3.1) — and even that is swappable to
local Ollama (Lesson 7.3).

---

### Secrets: the `.env` file

The one credential you need (for cloud generation) is an OpenRouter key. It lives in `.env`,
never in code:

```bash
cp .env.example .env        # then edit: OPENROUTER_API_KEY=sk-or-...
```

Recall Lesson 5.3: every setting — including this key — is a `Settings` field, and the key is a
`SecretStr` read from env, never logged. `.env` overrides the defaults in `config.py`. (And
recall from Lesson 3.3: ingest, index, search, and *refusals* need **no** key — only a grounded
answer calls the cloud.)

> #### Under the hood — `uv` and reproducibility
> maayan uses `uv` (a fast Python package manager) with a lockfile, so `uv sync` reproduces the
> exact dependency set. `uv run <cmd>` runs inside that environment without you activating a
> venv — which is why every hands-on in this curriculum is `uv run maayan …`. The extras are
> *additive*: `uv sync --extra ml --extra ui` gives you core + both. There's no "did I activate
> the right environment?" failure mode.

RUNBOOK §2 is the authoritative, copy-pasteable version of all this — keep it
open while you operate.

---

### Hands-on

1. **Confirm your install.** From the repo root:

   ```bash
   uv run maayan version
   ```

   If that prints a version, your core install works. (It needs no models or Docker.)

2. **Check the two services.** Run `make up`, then confirm Qdrant is reachable — the CLI's
   `require_qdrant` (Lesson 5.1) will tell you fast if it isn't:

   ```bash
   uv run maayan search "test" --k 1
   ```

   If Qdrant is down, you'll get the "✗ Qdrant is not reachable… `make up`… or `--mock`"
   guidance. That fail-fast message *is* the operator UX.

3. **Read the source of truth.** Open RUNBOOK §2 and skim the setup block.
   Identify which step you'd skip if you only wanted to run unit tests (answer: the `ml`/`ui`
   extras, the key, and Qdrant — `make test` needs none of them).

4. **Locate the extras boundary.** In `pyproject.toml`, confirm `torch` is under `ml`, not core.
   In one sentence: why does that choice make the *test suite* fast?

---

### You should now be able to say…

- The three dependency tiers (core / `ml` / `ui`) and **why the heavy ones are optional** (fast
  skeleton + tests).
- The two local services — **Qdrant** (`make up`/`down`, or `:memory:`/path/`--mock`) and the
  **bge-m3** model (one-time download).
- That the OpenRouter key lives in **`.env`** as a secret, and which operations need no key at
  all.
- That RUNBOOK §2 is the authoritative setup reference.

Next: **7.2 — The knobs that matter** — now that it runs, the handful of
config knobs that actually change behavior, what each does, and when to reach for it.

<div class="page-break"></div>


<a id="lesson-7-2"></a>


## Lesson 7.2 — The knobs that matter

> Module 7, Lesson 2 · ~20 min, hands-on at the terminal.
> The one question this answers: **of all the settings in `config.py`, which ones actually change
> retrieval behavior — and how do I reach for the right one with intent?**

You've met most of these knobs in passing. This lesson collects the few that matter for tuning,
says what each *does to behavior*, and — crucially — pairs each with the eval harness (Module 4)
so you turn knobs with evidence, not vibes. All of them live in
maayan/config.py and are settable via env / `.env` (Lesson 5.3).

---

### The five knobs you'll actually touch

| Knob | Default | What it does | Reach for it when… |
|---|---|---|---|
| `score_threshold` | `0.45` | the default-deny bar (Lesson 3.3) | it refuses good questions (lower) or answers junk (raise) |
| `top_k` | `8` | how many candidates fused/returned | answers miss context (raise) or include noise (lower) |
| `rerank_enabled` | `false` | the cross-encoder second pass (Lesson 2.4) | ordering is off and you'll pay latency for quality |
| `expert_boost` / `derived_boost` / `term_boost` | `1.0` | rank multipliers per source (Lesson 2.4) | you want human/curated knowledge to outrank text |
| `embed_model` | `BAAI/bge-m3` | the embedder itself (Lesson 1.1) | you're evaluating a different model (rebuild needed) |

Two you'll rarely touch but should know: `rerank_candidates` (`30`, the pool the reranker
reorders) and `embed_dim` (`1024`, must match the model). Changing `embed_model` or `embed_dim`
requires `index --rebuild` (Lesson 2.2) — the vectors must be recomputed.

---

### `score_threshold`: the trust dial

This is the one you'll tune most, because it sets the answer/refuse balance. From Lesson 4.2 you
already know the trade-off as *numbers*:

- **Raise it** → more refusals. The `refused (of negatives)` rate goes up (catches more junk), but
  `answered (of positives)` goes down (starts refusing real questions). Over-strict.
- **Lower it** → the reverse. Risks fabrication on weak matches. Over-loose.

The config description spells out a subtlety: bge-m3 cosine "clusters in a narrow band," so the
useful range is corpus-specific — `0.45` is a *starting* point, not a law. And note (Lesson 2.4):
when `rerank_enabled` is on, `relevance` becomes the *reranker's* score, which separates good from
bad more sharply — so the threshold often wants re-tuning after you enable rerank. **The right way
to set it is the eval harness**, watching both gate rates.

---

### The source boosts: making human knowledge win

The boosts (`expert_boost`, `derived_boost`, `term_boost`) are the operator's lever over the
capture loop (Module 6). At the default `1.0`, an `expert` chunk competes with `sefaria` purely on
relevance. Set `expert_boost=1.2` and a scholar's contribution, when it's relevant, gets nudged
*above* the printed text — encoding the editorial choice "when my expert addressed this, prefer
their framing." This only matters once you have non-`sefaria` chunks; it's how you decide *how
loudly* the loop speaks. Use it deliberately — too high and human notes drown out the text they're
supposed to illuminate.

> #### Under the hood — why these are knobs and not constants
> Every one of these is a `Settings` field precisely so you can tune it per corpus *without
> touching logic* (Lesson 5.3) and *measure the effect* (Module 4). A different corpus (more
> books, a different language mix) has a different ideal threshold and top_k. Hardcoding any of
> them would freeze the system to one corpus. The combination — config-driven knobs + an eval
> harness that reads the same `score_threshold` the live system uses — is what makes tuning a
> *measurement*, not a guess.

---

### Hands-on — tune one knob with evidence

Full Tanya indexed (Lesson 4.2 prerequisite), so the gold set is meaningful.

**1. Establish a baseline.** `uv run maayan eval`. Write down `hit@5`, `MRR`, and both gate rates
at the default `score_threshold=0.45`.

**2. Move the trust dial and watch both rates.**

```bash
SCORE_THRESHOLD=0.60 uv run maayan eval     # stricter
SCORE_THRESHOLD=0.30 uv run maayan eval     # looser
```

Confirm `answered` and `refused` move in opposite directions (Lesson 4.2). Pick the value that
keeps **both** high on your corpus — that's your tuned threshold, chosen by evidence.

**3. Weigh rerank as a real decision.** Compare ordering quality with and without the second pass:

```bash
uv run maayan eval --compare                          # baseline variants
RERANK_ENABLED=true uv run maayan eval                # rerank on
```

Did `MRR` / `hit@1` improve enough to justify the added latency and model download? That cost/
benefit judgment — read off the numbers — is exactly how an operator decides to flip a knob
(Module 8.1 generalizes it).

**4. Feel a boost (preview).** If you created an `expert` chunk in Module 6, search a query it's
relevant to, then re-run with `EXPERT_BOOST=1.5 uv run maayan search "<that query>" --k 5`. Watch
your contribution climb the ranking. In a sentence: when would boosting *too* hard be a mistake?

---

### You should now be able to say…

- The five knobs that matter (`score_threshold`, `top_k`, `rerank_enabled`, the source boosts,
  `embed_model`) and what each does to behavior.
- That `score_threshold` is the **trust dial**, tuned via the **eval harness** by balancing the
  two gate rates — and that rerank shifts the number it reads.
- That the **boosts** are the operator's control over how loudly the capture loop ranks, default
  `1.0`.
- That `embed_model`/`embed_dim` changes require an `index --rebuild`.

Next: **7.3 — Choosing & swapping the generation backend** — the cloud↔
local decision you previewed in 3.1, now as an operational choice with a real swap.

<div class="page-break"></div>


<a id="lesson-7-3"></a>


## Lesson 7.3 — Choosing & swapping the generation backend

> Module 7, Lesson 3 · ~15 min read + an optional hands-on swap.
> The one question this answers: **cloud or local for generation — how do I decide, and how do I
> actually flip it?**

In Lesson 3.1 you saw *why* the generation backend is swappable (the `GenerationBackend` protocol
+ DI). This lesson is the operator's side: *which* to run, the trade-offs, and the literal steps
to switch — proving the architecture's promise that no other code changes.

---

### The decision, in one table

| | OpenRouter (cloud, default) | Ollama (local) |
|---|---|---|
| **Quality** | stronger models, better Hebrew | smaller models, weaker — esp. Hebrew |
| **Privacy** | question leaves your machine | fully offline; nothing leaves |
| **Cost** | per-call (API) | free after download |
| **Setup** | an API key | install Ollama + pull a model |
| **Default model** | `qwen/qwen-2.5-72b-instruct` | `qwen2.5:7b-instruct` |

CLAUDE.md states the trade-off bluntly: Ollama is "offline + private + free,
but smaller models are weaker, especially on Hebrew." There's no universally right answer —
choose by what you're optimizing. Drafting offline on a plane, or working with sensitive
material? Local. Want the best Hebrew composition and don't mind a cloud call? Cloud.

**The part that doesn't change either way:** RAG, citations, and default-deny are the backbone
*regardless* of backend (Lesson 3.1's "trust guarantees live outside the box"). A local model
might write a clumsier answer, but it still can't cite a source that wasn't retrieved, and it
still refuses when there's nothing. You're choosing the *writer*, not the *rules*.

---

### How to swap (two config lines)

This is the whole switch, and it's the proof of Lesson 3.1:

```bash
# 1. install Ollama and pull an open instruct model (one-time)
ollama pull qwen2.5:7b-instruct

# 2. point maayan at it — in .env:
GENERATION_BACKEND=ollama
OLLAMA_MODEL=qwen2.5:7b-instruct       # (the default; shown for clarity)
```

That's it. `build_generation_backend` (Lesson 3.1) reads `generation_backend` and constructs
`OllamaBackend` instead of `OpenRouterBackend`. Retrieval, grounding, citation extraction, the
default-deny gate, the CLI, the UI — **none of them change**. You can flip back by setting
`GENERATION_BACKEND=openrouter`. The relevant knobs:

| Knob | Cloud | Local |
|---|---|---|
| `generation_backend` | `openrouter` | `ollama` |
| model | `openrouter_model` | `ollama_model` |
| endpoint | `openrouter_base_url` | `ollama_base_url` (`http://localhost:11434`) |

> #### Under the hood — same protocol, different transport
> Recall the two implementations (Lesson 3.1): `OllamaBackend` POSTs to a local
> `/api/chat` endpoint; `OpenRouterBackend` uses the OpenAI client against OpenRouter's URL. Both
> satisfy `generate(system, messages) -> str`. The `generation_model` helper property on
> `Settings` even returns the right model id for whichever backend is active, so display code
> ("answer by <model>") works unchanged. This is dependency injection earning its keep
> operationally: a capability swap is a config edit, because the seam was a protocol from day one.

The RUNBOOK troubleshooting section covers the common local-backend snags
(Ollama not running, model not pulled, slower responses).

---

### Hands-on

The decision matters more than the mechanics here, so this one is read-and-reason, with an
optional real swap.

1. **Make the call for your situation.** Given how *you* use maayan — sensitivity of material,
   internet availability, how much Hebrew quality matters — which backend fits? Write one
   sentence justifying it against the table.

2. **Find the swap point in code.** Open generate/factory.py.
   Locate the `if backend == "ollama":` branch. Confirm: this *one function* is the only place
   that decides cloud vs. local. Everything downstream is backend-agnostic.

3. **(Optional) Actually swap.** If you have Ollama installed: `ollama pull qwen2.5:7b-instruct`,
   set `GENERATION_BACKEND=ollama` in `.env`, and re-run a question you asked before:

   ```bash
   uv run maayan ask "מה ההבדל בין צדיק לבינוני?"
   ```

   Compare the answer's quality to the cloud version. Note that it still cites real refs and would
   still refuse an unsupported question — the rules held; only the writer changed. Set it back
   when done.

---

### You should now be able to say…

- The cloud-vs-local trade-off (quality vs. privacy/cost/offline) and that there's no universal
  right answer — choose by what you optimize.
- That the **trust guarantees (RAG, citations, default-deny) hold regardless of backend** — you
  swap the writer, not the rules.
- The exact swap: `GENERATION_BACKEND` (+ model/endpoint) in `.env`, with **no other code
  change** — the operational proof of Lesson 3.1's DI design.

Next: **7.4 — Growing the corpus** — adding more text, whether it's
on Sefaria (config) or somewhere else entirely (the chabad adapter).

<div class="page-break"></div>


<a id="lesson-7-4"></a>


## Lesson 7.4 — Growing the corpus

> Module 7, Lesson 4 · ~20 min, hands-on at the terminal.
> The one question this answers: **how do I add more text to the system — both the easy case (it's
> on Sefaria) and the hard case (it isn't)?**

A RAG system is only as good as what it can retrieve. Eventually you'll want more than the
starter corpus. This lesson is how you grow it: the common path (a Sefaria book — pure config) and
the adapter path (a source Sefaria doesn't have). It also reinforces a theme from Module 5 — adding
a *Sefaria* book touches **no code**, because the book list is config.

---

### Two kinds of source

Recall the provenance taxonomy (Lesson 6.1): printed text is either `sefaria` or `chabad`. That
split exists for exactly this reason — **not everything is on Sefaria**. The flagship example is
in your corpus already: Likutei Torah isn't on Sefaria at all (the Hebrew Wikisource copy is an
empty stub), so it's pulled from chabadlibrary.org. So "grow the corpus" has two paths:

| Path | When | What you change |
|---|---|---|
| **Sefaria book** | the text is on Sefaria | add a string to `config.books` — **no code** |
| **Non-Sefaria** | it isn't (e.g. Likutei Torah) | use/extend the chabad adapter |

---

### The easy path: add a Sefaria book (config only)

Open config.py and find `books` — a `list[str]` of Sefaria refs (Tanya
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

### The adapter path: a source Sefaria doesn't have

When a text isn't on Sefaria, you can't just add a string — you need an *adapter* that knows how
to fetch and walk that source's API. maayan has one for chabadlibrary.org:
maayan/corpus/chabad.py, driven by `config.chabad_books` (a map of
book name → root section id) and `config.chabad_base_url`. Ingesting uses a different command:

```bash
uv run maayan ingest-chabad        # walks chabadlibrary.org's JSON API for Likutei Torah
make index
```

> #### Under the hood — why a separate adapter, and sentence-aware chunking
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

### Hands-on

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
cli.py. In one sentence: why does a non-Sefaria source need a *different
command* but produce the *same* `Chunk`? (Hint: different fetch, same downstream.)

**4. (Optional) Grow with chabad.** If you want Likutei Torah, run `uv run maayan ingest-chabad`
then `make index`. Note in the output how a long section becomes multiple `… §N` chunks — the
sentence-aware split from the box above.

---

### You should now be able to say…

- The two paths to grow the corpus: **a Sefaria book (config only, no code)** vs. **a non-Sefaria
  source (an adapter)** — and why the `sefaria`/`chabad` provenance split exists.
- That adding a Sefaria book is *data*, not *logic* (the config-driven rule), with the
  flat-`chapters`-shape gotcha.
- That the chabad adapter fetches differently but yields the **same `Chunk`**, with **sentence-
  aware sub-chunking** for long sections.
- That both converge on one store/collection, distinguished only by `source`.

Next: **7.5 — The web UI as a thin layer** — the browser front end, and how its
routes wire to the services you've been driving from the CLI and nothing more.

<div class="page-break"></div>


<a id="lesson-7-5"></a>


## Lesson 7.5 — The web UI as a thin layer

> Module 7, Lesson 5 · ~15 min, hands-on in the browser.
> The one question this answers: **what does the web UI add to the system — and why is the
> honest answer "almost nothing but a face"?**

You've operated maayan entirely from the CLI. There's also a browser UI, and this lesson is about
seeing that it is — deliberately — a *thin layer*: it wires HTTP routes to the exact same services
you've been calling, and holds **no business logic of its own**. That thinness is a feature. It
means everything you learned (grounding, default-deny, the capture loop) holds identically in the
browser, because it's the same code underneath.

---

### Routes in, services out

Open maayan/ui/app.py and read `create_app`. Two things jump out.

First, **its parameters are all services**, injected:

```python
def create_app(rag, capture, threads, develop, terms, retraction, stats, compose, *, context_turns=6):
```

That's the dependency-injection rule (Lesson 5.1) at the UI edge: the app is *handed* the same
`RAGService`, `CaptureService`, `ThreadService`, `DevelopmentService`, `TermService`, etc. that
the CLI builds. The web layer constructs none of them.

Second, **each route is a one-liner that calls a service**. The `/ask` route, in full:

```python
@app.post("/ask")
def ask(req: AskRequest) -> AskResponse:
    answer = rag.ask(req.question, k=req.k)
    session = capture.start_session(answer)
    return _answer_to_response(answer, session.id)
```

That's it — call `rag.ask`, record the session (so it can be annotated), shape the response. No
grounding logic, no gate, no prompt-building: all of that lives in `RAGService` (Module 3) and is
*reused*. The routes map cleanly onto everything you've learned:

| Route | Service call | Lesson |
|---|---|---|
| `POST /ask` | `rag.ask(...)` | Module 3 |
| `POST /annotate` | `capture.add_annotation(...)` | 6.2 |
| `POST /threads`, `/threads/{id}/ask` | `threads…`, `ask_in_thread` | 6.5, 3.4 |
| `POST /threads/{id}/seed`, `/develop` | seed + `develop.develop(...)` | 6.3 |
| `POST /developments/{id}/approve`/`reject` | `develop.approve/reject` | 6.4 |
| `GET`/`POST /terms` | `terms…` | 6.5 |

The whole capture loop you ran on the command line is available as HTTP, because the UI is just a
different *doorway* to the same rooms.

> #### Under the hood — why "thin" is the right design
> Because the routes hold no logic, three things follow for free. (1) **The guarantees are
> identical** — default-deny refuses in the browser because it's the same `RAGService.ask`; the
> UI can't accidentally weaken it. (2) **It's testable the same way** — `tests/test_ui.py` injects
> *fake* services into `create_app` and asserts on responses, no server or network needed (Lesson
> 5.4 again). (3) **No drift** — there's no second implementation of "how to answer" to keep in
> sync with the CLI. A fat UI that re-implemented grounding would be a second place for bugs and a
> second place for the trust rules to rot. maayan keeps the logic in one place and gives it two
> faces.

Launch it with `make ui` (needs the `ui` extra from Lesson 7.1).

---

### Hands-on — do the full loop in the browser

You need the `ui` extra, Qdrant up, corpus indexed, and (for grounded answers) an OpenRouter key.

```bash
uv run pip --version >/dev/null 2>&1   # ensure env is synced; else: uv sync --extra ml --extra ui
make ui                                 # serves the local app (FastAPI/uvicorn)
```

Open the printed URL in your browser, then:

1. **Ask and watch grounding + refusal — in the UI.** Ask a question the corpus supports (you get
   a cited answer) and then one it can't (you get the refusal). Same two behaviors as the CLI,
   same gate — confirm the refusal happens here too. That's the thin layer faithfully exposing
   Module 3.

2. **Teach a connection in the browser.** From an answer, add an annotation (a `connection`, your
   name, the linked refs). This is the `/annotate` route → `capture.add_annotation` — the *exact*
   loop from Lesson 6.2, now point-and-click. Then ask again and see it surface.

3. **Confirm it's the same code.** Open `/docs` (FastAPI's auto API docs) at the served URL.
   Match three routes to the service methods in the table above. In one sentence: what business
   logic lives in `ui/app.py`? (Answer: none — it delegates.)

4. **Find the test that proves thinness.** Open tests/test_ui.py. Note
   that it injects fakes into `create_app` — the same DI move as `tests/test_rag.py` (Lesson 5.4).
   That's only possible because the UI takes services in.

---

### You should now be able to say…

- That the web UI is a **thin layer**: `create_app` takes the services injected and each route is
  a one-line delegation — **no business logic** of its own.
- That this means the **trust guarantees and the full capture loop hold identically** in the
  browser, because it's the same code underneath.
- Why thinness is deliberate: identical guarantees, same testability (inject fakes), and no logic
  drift between CLI and UI.

**That's Module 7 — running it for real.** You can now set it up (7.1), tune the knobs with
evidence (7.2), choose and swap the backend (7.3), grow the corpus (7.4), and operate it from the
browser (7.5). You're no longer just understanding maayan — you're running and owning it.

Next: **Module 8** — the horizon: using eval to justify a real change, the Phase 4 eraser and
Phase 5 composition layer, and when (and when not) to fine-tune. When you're ready, ask me to
**build out Module 8**.

<div class="page-break"></div>


<a id="module-8"></a>


# Module 8 — The horizon (extending it well)


<p class="module-goal">See where this goes next and how to add capability without breaking the guarantees.</p>

<div class="page-break"></div>


<a id="lesson-8-1"></a>


## Lesson 8.1 — Reading quality and improving it

> Module 8, Lesson 1 · ~15 min read + a hands-on at the terminal.
> The one question this answers: **how do I turn "I wonder if this would be better" into a
> decision I can defend with numbers?**

You've reached the horizon — where maayan goes next, and how to extend it without breaking its
guarantees. This first lesson is the bridge from Module 4 (you *can* measure) to Module 7 (you
*can* tune) to a disciplined habit: **never change retrieval on a hunch; change it on a measured
delta.** It's a short lesson because you already have every tool. What's new is the *method*.

---

### The temptation, and the discipline

It's tempting to flip `rerank_enabled`, swap the embedding model, or re-chunk because a few
answers felt off. But "felt off" is the vibe Module 4 warned against. The discipline is a loop:

> **hypothesis → measure baseline → make the change → measure again → compare → decide.**

The eval harness exists precisely so this loop is one command at each step. BUILD_PLAN §5 says it
in plain words about the harness: a comparison mode so you can "justify model/chunking choices
with numbers instead of vibes." That sentence is this whole lesson.

---

### What you can justify this way

Three kinds of change, each a real decision an operator faces:

| Change | The hypothesis | Read it off… |
|---|---|---|
| **Enable rerank** | "ordering is off; a second pass will fix it" | `MRR` / `hit@1` up enough to justify latency? (7.2) |
| **Swap embedding model** | "a Hebrew-specialized model retrieves better" | `recall@k` across the gold set, after `index --rebuild` |
| **Re-tune `score_threshold`** | "it over-refuses / under-refuses" | the two gate rates balanced (4.2) |

The embedding-model case is worth dwelling on: the harness was *built* to make the embedder
swappable specifically so you can drop in `multilingual-e5-large` or a DICTA rabbinic-Hebrew model
and **measure** whether it helps your corpus — rather than assuming. A model being "better in
general" means nothing; better *on your gold set* is a number.

> #### Under the hood — the comparison is apples-to-apples by construction
> `maayan eval --compare` runs every variant against the *same* gold set with the *same* metrics
> (Module 4.2's `run_comparison`). And ranking is deterministic (the `_rank_key` tie-break by
> `ref`, Lesson 2.3), so a variant's score is reproducible run to run. That's what makes the delta
> trustworthy: nothing moved except the one knob you're testing. A change that doesn't move the
> numbers isn't worth its complexity; a change that moves them earns its place.

The honest part: sometimes you'll measure and find the change *doesn't* help — or helps one metric
and hurts another. That's not a failed experiment; that's the experiment doing its job. Better to
learn it from the table than to ship a regression on a feeling.

---

### Hands-on

Full Tanya indexed (so the gold set is meaningful).

1. **Run the comparison.** `uv run maayan eval --compare`. This is your menu of "what if" answers
   for the built-in variants (hybrid k=10 / k=5 / dense-only). Which wins at `k=5`? By how much?

2. **Frame one real decision.** Pick a change you might actually make (say, enabling rerank).
   Write the hypothesis in one sentence, then measure both sides:

   ```bash
   uv run maayan eval                       # baseline
   RERANK_ENABLED=true uv run maayan eval    # the change
   ```

   Record the deltas in `MRR` and `hit@1`. Now decide *and write down why* — "yes, MRR +0.06
   justifies the latency" or "no, +0.01 isn't worth the model download." That sentence is a
   defensible engineering decision, not a vibe.

3. **Find the seam for a model swap.** You won't download a new model now, but locate where you'd
   point it: `embed_model` in config.py, and recall it needs
   `index --rebuild` (7.2). In one sentence: why must you rebuild the index to fairly compare two
   embedding models?

---

### You should now be able to say…

- The improvement loop: **hypothesis → baseline → change → re-measure → compare → decide.**
- The three changes you can justify with numbers (rerank, embedding model, threshold) and which
  metric reads each.
- Why the comparison is apples-to-apples (same gold set, same metrics, deterministic ranking) —
  and that a null or negative result is a *successful* measurement.

Next: **8.2 — Phase 4: the eraser & measurement** — the ability to
*remove* knowledge (provenanced, never silent) and to measure the cross-text claim that earlier
went unmeasured.

<div class="page-break"></div>


<a id="lesson-8-2"></a>


## Lesson 8.2 — Phase 4: the eraser & measurement

> Module 8, Lesson 2 · ~20 min, hands-on at the terminal.
> The one question this answers: **a scholar will eventually index something wrong — how does the
> system let them *remove* it without betraying the provenance everything else rests on?**

Module 6 gave you three ways to *add* knowledge (annotate, develop→approve, add-term). But for a
long time maayan had no way to *remove* any of it. BUILD_PLAN_PHASE4.md
names this exactly: "There is no eraser… once a chunk is indexed it is permanent." For a system
whose entire value is *accumulated, trusted* knowledge, that's the first necessary gap to close —
because a scholar *will* index a wrong connection, a typo'd term, or approve a development they
later reconsider. This lesson is the eraser, and the measurement that came with it.

---

### Why deleting is hard *here*

In most systems, "delete the row" is trivial. In maayan it's delicate, because the whole system
runs on provenance (Lesson 6.1) and on printed text being **immutable**. A naive `DELETE` would
violate both: it would erase the audit trail, and nothing would stop someone from "deleting" a
verse of Tanya. So a retraction must satisfy two constraints the rest of the system also obeys:

1. **Printed text is untouchable.** You can retract `expert` / `derived` / `term` chunks — *your*
   layered knowledge — but never `sefaria` / `chabad`.
2. **Removal itself carries provenance.** Who removed it, when, and why must be recorded. A silent
   delete is exactly the kind of unattributed change the system forbids everywhere else.

---

### How retraction works

Open maayan/retract/models.py and
service.py. A `Retraction` is, in the model's own words, "NOT a
silent delete: it is an attributed, timestamped audit record (who retracted, when, why)." The
`retract` method does six things (read the service docstring):

1. **Resolve** the chunk (by stable id or by ref).
2. **Reject printed text in code** — `sefaria`/`chabad` raise; immutability is enforced, not
   requested.
3. **Delete the point from Qdrant** — it's gone from retrieval immediately.
4. **Tombstone the corpus chunk** (`mark_retracted`, Lesson 2.2's store) so `index --rebuild`
   never re-embeds it — the removal survives a full rebuild.
5. **Cascade** — a retracted `derived` chunk flips its `Development` to status `"retracted"`; a
   `term` chunk marks its `Term` retracted. Related records stay consistent.
6. **Record the `Retraction`** — an attributed, timestamped audit row.

> #### Under the hood — correction = retract + re-add (no in-place edit)
> Notice there is no "edit" operation. The service docstring explains why: chunk ids are
> content-derived and idempotent (Lesson 1.2), so there's no meaningful in-place mutation. To
> *correct* a mistake you **retract the wrong chunk** (reason: "superseded") and **add the right
> one** through the existing capture / develop / add-term loops. This is the same discipline as
> printed text: you never overwrite, you supersede — and the supersession is itself provenanced.
> An audit trail you can't rewrite is exactly what makes accumulated knowledge trustworthy over
> years.

---

### The other half of Phase 4: measuring the cross-text claim

Phase 4 named a second gap (read BUILD_PLAN_PHASE4.md §0): "Phase 3's
headline is unmeasured." The marquee feature — connecting passages *across* books (Tanya ↔ Torah
Or ↔ Likutei Torah) — was shipped with a Tanya-only gold set, so the cross-text claim had no
honest number behind it. The fix was a dedicated cross-text gold set and metric (you met it in
Lesson 4.3): `maayan eval --crosstext`, which measures book-diversity@k — whether a question whose
answer spans two books actually retrieves passages from *both*. The lesson generalizes a Module 4
principle: **a new capability needs its own ruler.** Shipping a feature and measuring it are two
different acts of discipline, and Phase 4 did the second.

---

### Hands-on

Qdrant up. You'll need a layered-knowledge chunk to retract — use one you made in Module 6 (an
`expert`, `derived`, or `term` chunk), or make a throwaway one.

**1. Retract a piece of your own knowledge.** Using its ref or chunk id:

```bash
uv run maayan retract "<ref-or-chunk-id>" --author "Your Name" --reason "superseded"
```

It confirms the chunk is "Gone from retrieval and skipped by `index --rebuild`." Now search for it
(`--source expert`/`derived`/`term`) — it no longer comes back. The eraser works.

**2. Confirm printed text is untouchable.** Try to retract a verse of Tanya:

```bash
uv run maayan retract "Tanya, Part I; Likkutei Amarim 1" --author "Your Name" --reason "test"
```

It refuses — printed text is immutable, enforced in code. That refusal is the same family of
guarantee as default-deny: a rule the system won't let you talk it out of.

**3. Read the audit trail.** Retractions are recorded, not silent:

```bash
uv run maayan retractions
```

Your retraction appears with who/when/why. In one sentence: why is a *recorded* removal more
trustworthy than a clean delete?

**4. Measure the cross-text headline.** If you've ingested more than one book:

```bash
uv run maayan eval --crosstext
```

Read book-diversity@k. This is the number that was missing when the feature first shipped — the
measurement catching up to the claim.

---

### You should now be able to say…

- Why an **eraser** was the first necessary Phase 4 gap, and the two constraints it must honor
  (printed text immutable; removal provenanced).
- The six steps of `retract` (resolve → reject printed → delete point → tombstone → cascade →
  record), and that **correction = retract + re-add**, never in-place edit.
- That Phase 4 also **measured** the previously-unmeasured cross-text claim with its own gold set
  (`--crosstext`) — a new capability needs its own ruler.

Next: **8.3 — Phase 5: composition** — from grounded *answers* to
grounded *documents*, by running the unit you already trust once per section.

<div class="page-break"></div>


<a id="lesson-8-3"></a>


## Lesson 8.3 — Phase 5: composition

> Module 8, Lesson 3 · ~20 min, hands-on at the terminal.
> The one question this answers: **how does maayan go from answering one question to producing a
> whole grounded document — a shiur outline, an essay — without the second half drifting into
> fabrication?**

Every generation you've seen produces **one** grounded passage: `ask` answers a question,
`develop` develops a seed. Both are the *same unit*: retrieve once → default-deny gate → one cited
block. Phase 5 (BUILD_PLAN_PHASE5.md) asks: can we produce a structured
*document* — and the crucial insight is that the answer is **not a new generation engine.** It's an
orchestration layer that runs the unit you already trust, **once per section.**

---

### Why a document can't be one `ask`

A chat answer retrieves **once**, for **one** question. Try to write an essay that way and its
later sections drift far from what that single retrieval found — the model starts improvising,
exactly the failure RAG exists to prevent. The Phase 5 plan states it: "an essay's later half would
drift ungrounded."

So a composition **decomposes** the brief into an outline where **each section is its own
retrieval sub-question**, then **fills** each section using the existing grounded unit — each
section *independently* retrieved, gated, and cited. A long piece becomes many small grounded
answers, stitched in order, instead of one over-stretched retrieval.

---

### The spine: Brief → Composition → Sections

Open maayan/compose/models.py:

- **`Brief`** — the spec: a `title`, an `intent` ("what the piece should teach"), a
  `content_type` (`shiur_outline` / `essay` / `digest` — same engine, different *register*, so
  it's a config Literal, not new modules), optional `source_scope` (book/source filters), and a
  required `author`.
- **`Composition`** — the document: an ordered list of `Section`s, with a `status`
  (`proposed`/`approved`/`rejected`) — like a development, it's a *proposal* a human reviews.
- **`Section`** — a `heading` + the **retrieval sub-question** (`query`) that grounds it. The
  *outline* step fills `heading` + `query` (empty `text`); the *fill* step sets
  `text` / `cited_refs` / `grounded_in` / `supported`.

Two steps, two commands: `maayan compose` proposes the outline; `maayan compose-fill` grounds each
section. It's the develop→approve rhythm (Module 6) at document scale.

---

### The differentiator: default-deny *per section*

Here is what makes a *maayan* document generator different from any LLM that writes essays. Read
BUILD_PLAN_PHASE5.md §0:

> When the corpus doesn't support a section, the gate at
> rag.py:137 fires and the section becomes an **honest gap**
> ("the sources here don't reach this"), never fabricated prose.

That's the default-deny gate from Lesson 3.3 — *the exact same line of code* — now firing
**per section**. A `Section` carries `supported: bool`; when its sub-question doesn't clear the
threshold, `supported=False` and the section is marked an honest gap rather than filled with
invention. So a 12-section outline might come back with 9 grounded sections and 3 honest gaps —
and that's a *feature*. The plan puts it perfectly: "A piece with honest holes beats a confident
invention — for Torah that is the whole point."

> #### Under the hood — composition inherits every guarantee for free
> Because composition *reuses the unit* rather than reimplementing it, it inherits everything you
> learned: each section's fill is grounded and cited (Module 3), refuses per-section (3.3), draws
> on expert/derived chunks alongside text (Module 6), and respects source scope (Module 2.4). The
> orchestration layer adds *structure*; it adds no new way to fabricate. This is the same lesson as
> the thin UI (7.5): keep the trusted unit in one place, and build larger things by *calling* it,
> not by cloning it. A composition is a proposal with full provenance (author, brief, per-section
> grounded refs and gaps) — reviewable, like everything else.

---

### Hands-on

Qdrant up, full corpus indexed (more text → fewer gaps), OpenRouter key set.

**1. Propose an outline.** Give it a title and intent:

```bash
uv run maayan compose \
  --title "שלושת הלבושים של הנפש" \
  --intent "שיעור על מחשבה דיבור ומעשה ככלים של הנפש האלוקית" \
  --author "Your Name" \
  --type shiur_outline
```

Read the output: a numbered outline where **each section shows its retrieval sub-question**
(`↳ retrieval: …`). That per-section query is the seed of per-section grounding. Note the
`Composition <id>` and the `compose-fill` hint.

**2. Fill it — and hunt for the honest gaps.**

```bash
uv run maayan compose-fill <COMPOSITION_ID>
```

Each section is now grounded and cited *or* marked an honest gap. **Find a gap** (a section the
corpus couldn't support) — that's default-deny firing per section, refusing to fabricate that
piece. Contrast a grounded section (with `cited_refs`) against a gap. In a sentence: why is a
flagged gap more valuable, for Torah, than smooth invented prose?

**3. See it's the same gate.** Open BUILD_PLAN_PHASE5.md §0 and find
the reference to `rag.py:137`. Confirm: the per-section refusal is the *same* default-deny line you
made open and close in Lesson 3.3. Composition didn't invent a new trust rule — it reused the one
you already proved.

---

### You should now be able to say…

- Why long-form **can't be one `ask`** (later sections drift), and that composition **decomposes**
  a brief into per-section retrieval sub-questions, then fills each with the existing grounded
  unit.
- The spine **Brief → Composition → Sections**, the outline/fill two-step, and that it's a
  reviewable proposal like a development.
- The differentiator: **default-deny per section** — unsupported sections become honest gaps
  (`supported=False`), never fabricated — reusing the *same* gate from Module 3.

Next: **8.4 — When (and when not) to fine-tune** — the last lesson: why RAG
+ citations stays the backbone, and why fine-tuning is a later, register-not-correctness move.

<div class="page-break"></div>


<a id="lesson-8-4"></a>


## Lesson 8.4 — When (and when not) to fine-tune

> Module 8, Lesson 4 · ~15 min read, no setup required.
> The one question this answers: **everyone asks "should we fine-tune a model on the Torah?" —
> what's the honest answer, and why is it "not yet, and not for the reason you think"?**

This is the final lesson, and it's a lesson in restraint — fitting, since restraint is a theme
you've met all through maayan (the rashei-teivot hook it won't implement, the gate that refuses,
the human approval before derived corpus). Fine-tuning is the most-requested "next step" for any
domain LLM. maayan's design takes a clear, deliberate position on it, and understanding that
position is understanding what kind of system this is.

---

### The two things people conflate

"Fine-tune a model on chassidus" usually bundles two hopes that are actually separate:

1. **"It will know more Torah"** — i.e. fix *correctness* / coverage.
2. **"It will sound more like a maggid shiur"** — i.e. fix *fluency / register*.

The maayan thesis (and BUILD_PLAN.md §5) is blunt about which one fine-tuning
actually addresses:

> Fine-tuning is later. Only once you have a meaningful volume of expert annotations does it make
> sense — and it **changes fluency/register, not correctness.** RAG with citations stays the
> backbone regardless.

Read that twice. Fine-tuning makes a model *write* differently; it does **not** make it *cite
reliably* or *stop fabricating.* Those are precisely the failures (Lesson 0.1) that RAG exists to
fix — by retrieving real sources and refusing without them. Bake Torah into the weights and you're
back to a model answering from a blurry internal memory, with no citation you can check and no
gate that refuses. You'd have traded the one thing that makes the system trustworthy for nicer
prose.

---

### Why RAG stays the backbone

Walk it through against what you now know:

| Goal | Fine-tuning | RAG (maayan) |
|---|---|---|
| Cite a real, checkable mareh makom | ✗ generates plausible-looking refs | ✓ cites retrieved chunks (Module 3) |
| Refuse when there's no source | ✗ no gate; answers from weights | ✓ default-deny in code (3.3) |
| Add new knowledge today | ✗ retrain | ✓ add a chunk; retrieved next query (6.1) |
| Attribute *whose* idea it is | ✗ melts into the weights | ✓ provenance on every chunk (6.1) |
| Remove a mistake | ✗ retrain to forget | ✓ provenanced retraction (8.2) |

Every column on the right is something you built and ran in this curriculum. Fine-tuning gives up
all of them to improve *register*. That's why the architecture is "RAG + citations as the
backbone, fine-tuning as a possible later flavoring" — never the reverse.

---

### When it *does* eventually make sense

The position isn't "never" — it's "later, for the right reason, after the right groundwork":

- **Volume first.** It only pays off "once you have a meaningful volume of expert annotations"
  (BUILD_PLAN §5). The capture loop (Module 6) is what *produces* that volume — every connection,
  seed, and approved development is training data accruing. So the loop comes first; fine-tuning,
  if ever, is downstream of it.
- **Register, declared as such.** If one day you fine-tune, do it to shift *how* answers read
  (the lashon, the flow of a maggid shiur), and keep RAG + citations + default-deny underneath
  unchanged. The fine-tuned model becomes a *better writer* slotted into the same trusted
  pipeline (recall the swappable backend, Lesson 3.1 — a fine-tuned model is just another
  `GenerationBackend`).
- **Measured, like everything.** You'd justify it the Module 8.1 way: does it improve answers on a
  gold set without degrading grounding? Numbers, not vibes.

> #### Under the hood — the higher-value "next layer" is your shiurim
> BUILD_PLAN.md §5 points at the real leverage: "Add your shiurim. Your
> transcribed… material is exactly the high-value expert layer — it ingests through the same
> `Chunk` model with `source="expert"` (or `"shiur"`)." That's the move that compounds: transcribed
> Torah enters the *same* loop as everything else — chunked, embedded, retrieved, cited, refusable,
> retractable. It grows *correctness and coverage* (the thing fine-tuning can't), with full
> provenance, today. The horizon isn't a bigger model; it's a richer corpus and more captured
> reasoning, run through the loop you now understand end to end.

---

### Hands-on

No terminal — this one is reflection, the right note to end on.

1. **Make the argument in your own words.** In three sentences: why would fine-tuning a model on
   Tanya *not* fix the fabrication problem from Lesson 0.1 — and what would it actually change?

2. **Name the prerequisite.** What has to exist *before* fine-tuning is even worth considering, and
   which part of maayan produces it? (Hint: Module 6.)

3. **Plan the real next step.** If you wanted maayan to *know more* tomorrow, what would you do —
   and which `source` would those chunks carry? Sketch it: it's the capture loop and corpus growth
   (Modules 6–7), not a training run.

---

### You should now be able to say…

- That fine-tuning changes **register/fluency, not correctness** — and so does **not** fix
  fabrication or give you checkable citations.
- Why **RAG + citations + default-deny stays the backbone** (cite, refuse, add, attribute, remove
  — all things weights can't do), with fine-tuning a possible later *flavoring*.
- When it could make sense (volume first, register declared, measured) — and that the higher-value
  next layer is **growing the corpus** (e.g. transcribed shiurim) through the same loop.

---

**That's the curriculum.** You started (Module 0) by watching a question become a grounded answer
or an honest refusal. You opened every box: embeddings and chunking (1), the vector DB and hybrid
search (2), the trust core of grounded generation and default-deny (3), evaluation (4), the
engineering spine that makes it all swappable and testable (5), the capture-and-develop loop that
makes it *yours* (6), operating and tuning it for real (7), and the horizon — improving,
correcting, composing, and the deliberate restraint on fine-tuning (8).

You can now explain how maayan works, reason about *why* it behaves as it does, operate the full
pipeline, tune it with intent, measure it honestly, and extend it without breaking its guarantees.
You own the wellspring. Go learn Torah with it.
