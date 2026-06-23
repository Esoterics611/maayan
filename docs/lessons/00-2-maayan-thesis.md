# Lesson 0.2 — The maayan thesis in one picture

> Module 0, Lesson 2 · ~15 min read + a short hands-on · no setup required.
> The one question this answers: **what are all the moving parts, and how do they fit
> together?**

---

## The whole system as one sentence

> maayan **ingests** your texts, **embeds** them into searchable meaning, **indexes** them
> in a local database, **retrieves** the relevant passages for a question, **generates** a
> grounded and cited answer (or refuses) — and then **captures** how a scholar corrects and
> connects sources, feeding that back in as new searchable knowledge.

Read that twice. Every folder in `maayan/` is one of those verbs. Once you can see the
pipeline, the codebase stops being a maze and becomes a straight line.

---

## The pipeline, stage by stage

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

## The one thing that flows through all of it: the *chunk*

Every stage above passes the same object down the line — a **chunk**: one natural unit of
text (a Tanya chapter segment, a passage of Likutei Torah) plus its identity. If you
understand the chunk, you understand the spine of the whole system.

> ### Under the hood — what's in a chunk
> A `Chunk` carries: `ref` (its canonical citation, e.g. *"Tanya, Chapter 1:3"* — which
> doubles as the human-readable source line), `book`, `text` (the Hebrew/English itself),
> `lang`, and — crucially — `source`: *where this knowledge came from*. `source="sefaria"`
> is printed text; `source="expert"` is a scholar's contribution; `source="derived"` is
> something the model developed and a human approved. Same database, same retrieval — but the
> system always knows, and shows, the provenance. That `source` field is the seed of the
> entire "capture loop" idea. You'll work with the chunk directly in Module 1.

---

## The loop is the point (everything else is plumbing)

Steps ingest → generate are "just" a good RAG system — impressive, but other people have
built RAG. What makes maayan *yours* is the **capture loop**:

A scholar reads an answer, corrects it or draws a connection the printed texts don't make
explicit — and that contribution gets folded back in as a new, **attributed**, searchable
chunk. The next question can retrieve it *alongside* the printed text. Over time the system
accumulates not just texts, but **the reasoning that links them** — which today lives only
in a few people's heads.

[docs/OVERVIEW.md](../OVERVIEW.md) says it well: "The texts are common property; what is
scarce, and what we are trying to preserve, is the expert's reasoning over them." Hold onto
that — it's the *why* behind Modules 6 and 8.

---

## What runs where (and why it matters)

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

## Hands-on

1. **Match folders to the pipeline.** In a terminal at the repo root, list the modules:

   ```bash
   ls maayan/
   ```

   For each of these — `corpus`, `embed`, `index`, `retrieve`, `generate`, `capture` — say
   out loud which pipeline verb it is. (Answer key is the table above. The extra folders you
   see — `develop`, `threads`, `lexicon`, `eval`, `ui` — are later additions; you'll meet
   each in its module.)

2. **Find the house rule that enforces refusal.** Open [CLAUDE.md](../../CLAUDE.md) and read
   the **"House rules"** list. One rule is titled *"Default-deny on generation."* Read it.
   That single rule is the contract behind the refusal you found in Lesson 0.1 — and it says
   the rule is enforced *in code, not just in the prompt*. (Why that phrasing matters is the
   heart of Lesson 0.3.)

3. **Draw it from memory.** Close this file and, on paper or in a note, draw the pipeline:
   six boxes left to right, plus the capture loop curving back. If you can reproduce it, you
   own the map.

---

## You should now be able to say…

- The six stages of the pipeline, in order, and which folder each lives in.
- What a *chunk* is and why its `source` field matters.
- Why the **capture loop** — not the RAG plumbing — is what makes this system valuable.
- What runs locally vs. in the cloud, and why that's a deliberate choice.

Next: **[0.3 — Run it once, all the way](00-3-run-the-loop.md)** — you'll push a real
question through every box above and watch it both *answer* and *refuse*.
