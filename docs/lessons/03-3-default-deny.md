# Lesson 3.3 — Default-deny: the rule that lives in code, not the prompt

> Module 3, Lesson 3 · ~20 min, hands-on at the terminal.
> The one question this answers: **what actually stops the system from answering when it has no
> source — and why is that a line of code instead of a polite instruction to the model?**

This is the most important lesson in the curriculum. Everything else — embeddings, hybrid
search, citations — serves *this*: a tool you can trust because it knows when to stay silent.
You watched it happen in Lesson 0.3 (the boiling-point question). Now you'll understand exactly
how, and you'll operate the gate yourself.

---

## Why the prompt is not enough

In Lesson 3.2 the system prompt told the model: "if the sources don't suffice, say so; don't
speculate." That's good hygiene. But it's a *request*, and Lesson 0.1 taught us the hard truth:
a language model is a fluent next-word predictor that fabricates with confidence. Lean on the
prompt alone and you're trusting the very faculty that invents mekoros to police itself. Some
days it will. The day it doesn't, you get a beautiful, cited, **fabricated** answer — the worst
possible failure for Torah.

So maayan does not rely on asking nicely. It makes the dangerous case *structurally
impossible*: when nothing supports an answer, **the model is never called at all.**

---

## The gate

Open [maayan/generate/rag.py](../../maayan/generate/rag.py) and read the `ask` method. The very
first thing it does after retrieval — [rag.py:137](../../maayan/generate/rag.py), under the
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

> ### Under the hood — why `relevance` and not the RRF `score`?
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

## Refusal shows its work

When the gate fires, the CLI doesn't just say "no." Look at the `ask` command's output path: it
prints `[refused]`, the refusal text, **and** "(Closest, but below the relevance threshold:)"
followed by the few nearest passages it *did* find. That transparency matters: the system is
telling you, in plain text, "here are the best I had, none cleared the bar, so I won't answer."
You can see the gate's reasoning, not just its verdict — and you keep a `Session` id either way,
so even a refusal is something you can later annotate (Module 6).

---

## Hands-on

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

## You should now be able to say…

- Why the prompt's "don't speculate" is insufficient, and why default-deny is enforced in
  **code** instead.
- Exactly what the gate checks (`not sources` or `relevance < score_threshold`) and that it
  returns **before the model is ever called**.
- Why it must use the **absolute** `relevance`, not the RRF rank score — and how that ties back
  to Lesson 2.3.
- What `score_threshold` does, why it isn't zero, and that it's tuned with the eval harness.

Next: **[3.4 — Context-aware follow-ups without losing grounding](03-4-context-followups.md)** —
how a conversation can help *interpret* a question without ever becoming a citable source, and
without weakening the gate you just met.
