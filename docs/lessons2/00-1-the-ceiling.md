# Lesson 0.1 — The ceiling we hit

> Module 0, Lesson 1 · ~12 min read + a short hands-on.
> The one question this answers: **what does "it's just a fancy lookup system" actually
> mean in the code — and why does it cap how intelligent the answers can be?**

By the end of Course 1 you had something genuinely good: a system that retrieves the right
passages, answers only from them, cites every claim, and refuses when it has no source. That
is a faithful **lookup** system. This lesson is about the wall it hits — and why that wall is
exactly where Course 2 begins.

---

## What "single shot" means, concretely

Trace one `ask` as it worked before Prompt 31. It is three steps, each done **once**:

1. **Embed the question once.** The retriever calls `embed_query(question)` a single time and
   searches with that one vector. See `retrieve/retriever.py` — one query in, one ranked list
   out.
2. **Gate once.** The default-deny check compares the top relevance to `score_threshold`. If
   nothing clears it, refuse. (This part is sacred — we keep it untouched all course.)
3. **Generate once.** `generate/rag.py` builds one prompt — *here are the numbered sources,
   answer and cite* — and makes a single model call. Sources in, prose out.

```
question ──► embed once ──► search once ──► [gate] ──► one model call ──► answer
```

There is no step where the system *reconsiders* the question, *re-reads* the sources, or
*checks* its own answer. It finds and it reports. That's lookup.

---

## Why lookup hits a ceiling on Torah questions

Lookup works beautifully when the question shares words with the answer. It struggles exactly
where chassidus lives: **conceptual** questions whose answer is phrased nothing like the ask.

- You ask about *the relationship between ביטול and רצוא ושוב*. The source that answers it may
  never use the word "relationship," may discuss the two ideas chapters apart, and may name
  them with abbreviations or synonyms. One embedding of your exact phrasing can sail right past
  it.
- Even when retrieval finds good passages, a single generation pass tends to **summarize each
  source in turn** rather than show how they *fit* — which agrees with which, which builds on
  which, where they're in tension. But "how the sources fit" *is* the substance of learning
  chassidus. Lookup gives you the quotes; it doesn't give you the *shiur*.
- And nothing checks whether each `[S#]` the model attached actually supports the sentence it's
  attached to. The grounding is enforced by *prompt*, not *proof*.

None of these are bugs. They're the ceiling of the single-shot shape. To go higher you change
the *shape*: ask in more than one way, think before answering, and verify after. That's
Modules 1, 2, and 2.4 respectively.

---

## Hands-on

Pick a **conceptual** question from your own corpus — one whose answer you know lives in the
text but is phrased differently from how you'd ask. (If you're unsure, something like
`"מה הקשר בין צמצום לבריאת העולם"` over Tanya/Torah Ohr.)

**1. See what one query retrieves.** No backend needed — just retrieval:

```bash
uv run maayan search "מה הקשר בין צמצום לבריאת העולם" --k 8
```

Read the eight refs. Are the passages you'd *expect* a scholar to cite all there? Often one or
two obvious ones are missing — not because they're irrelevant, but because your phrasing didn't
land near them in vector space. **Write down a ref you expected but didn't see.** We'll watch
it reappear in Lesson 1.4.

**2. See the single-shot answer** (needs a backend — OpenRouter key or local Ollama; skip if
you have neither):

```bash
uv run maayan ask "מה הקשר בין צמצום לבריאת העולם"
```

Read the answer. Notice its *shape*: does it weave the sources into one argument, or list them
("Source 1 says…, Source 2 says…")? Note that too — Lesson 2.1 changes it.

---

## You should now be able to say…

- What "single shot" means precisely: **embed once → search once → generate once**, with no
  reconsidering, re-reading, or checking.
- Why that ceiling bites hardest on **conceptual** questions, where the answer's wording
  differs from the question's.
- The three shape-changes that lift it — **ask better, think before answering, check yourself**
  — and that none of them touch the refusal gate.

Next: **[0.2 — The three moves (the map)](00-2-the-three-moves.md)** — a bird's-eye view of
everything we added, before we open each box.
