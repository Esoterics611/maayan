# Lesson 0.1 — What RAG is, and the problem it solves

> Module 0, Lesson 1 · ~15 min read + a short hands-on · no setup required.
> The one question this answers: **why does this system exist at all, instead of just
> asking a chatbot?**

---

## Start with the failure you're trying to avoid

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

> ### Under the hood — why does it invent?
> An LLM is, mechanically, a very sophisticated *next-word predictor*. It was trained on a
> huge amount of text and learned the patterns of how language flows. It does **not** have a
> database of facts it looks things up in. When you ask it for a source, it doesn't *retrieve*
> a source — it *generates* the most statistically plausible-looking source-shaped string.
> Usually that's wrong. The fabrication isn't a bug you can scold out of it; it's what the
> machine fundamentally does. This is why "please don't hallucinate" in a prompt never fully
> works — and why maayan enforces honesty in *code* instead (you'll see that in Lesson 0.3).

---

## Three ways to answer a question (only one is good enough)

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

## The twist that makes it trustworthy

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

## Where this lives in your system

Open [docs/OVERVIEW.md](../OVERVIEW.md) and read the section **"What exists today"** (the
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

## Hands-on

You don't need anything running for this one — it's about seeing the idea in your own repo.

1. **Read the refusal in its own words.** Open [maayan/generate/rag.py](../../maayan/generate/rag.py)
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

## You should now be able to say…

- Why an LLM alone can't be trusted for citations (it generates plausible text, it doesn't
  look facts up).
- What the three letters R-A-G actually stand for, and the order they happen in.
- Why **refusal** is a feature, not a flaw — and that maayan enforces it in code, not just
  by asking the model nicely.

Next: **[0.2 — The maayan thesis in one picture](00-2-maayan-thesis.md)** — the full
pipeline, stage by stage, and the loop that makes this system yours.
