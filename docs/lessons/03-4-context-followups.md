# Lesson 3.4 — Context-aware follow-ups without losing grounding

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

## The tension, stated plainly

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

## How it's built

Three pieces in [maayan/generate/rag.py](../../maayan/generate/rag.py):

1. **`ContextTurn`** ([rag.py:44](../../maayan/generate/rag.py)) — a tiny model (`speaker`,
   `text`) for one prior turn. Its docstring says it outright: "This block is NEVER citable —
   only retrieved sources are."

2. **`build_conversation`** ([rag.py:75](../../maayan/generate/rag.py)) — renders prior turns
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

## The two guarantees that survive

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

> ### Under the hood — why `ContextTurn` is its own little model
> Its docstring notes it's "decoupled from `threads.ThreadTurn` on purpose: the generator must
> not depend on the thread layer." Persistent topic *threads* (storing and replaying turns) are a
> Module 6 feature; the thread flow maps a stored `ThreadTurn` down to a `ContextTurn` when it
> calls `ask`. The generator only knows the small, citation-free `ContextTurn` — so the trust
> core stays independent of the (later, optional) conversation-storage machinery. Clean layering:
> the generator depends *down* on a minimal type, never *up* on the feature that uses it.

---

## Hands-on

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

## You should now be able to say…

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
