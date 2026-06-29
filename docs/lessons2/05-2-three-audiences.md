# Lesson 5.2 — Explaining it to three audiences

> Module 5, Lesson 2 · ~12 min read + a writing exercise.
> The one question this answers: **how do I explain what this does to a scholar, an engineer,
> and a skeptic — bringing out what each cares about, without over-claiming?**

The demo (5.1) shows; this lesson tells. The same system needs three different framings,
because three audiences value three different things. Get the framing wrong and a true
description still falls flat.

---

## To a scholar (a posek, a mashpia, a talmid chacham)

**What they care about:** faithfulness to the sources, and whether this respects the way Torah
is learned.

**The framing:** *"It's a tireless chavrusa that has read the whole corpus. You ask, and it pulls
the relevant mekoros, lays out how they fit — which builds on which, where there's a tension —
and then explains, citing every source. And it will tell you plainly when the texts it has don't
answer your question, rather than make something up."*

**Bring out:** the **study map** (this is the chavrusa move — "it's being mevarer the sugya before
answering"), the **citations** on every claim, and the **refusal**. Show that expert connections
you capture become part of what it knows (the loop from Course 1).

**Never over-claim:** it is not a posek; it does not *know* Torah, it *retrieves and relates* what
you've indexed; it can still be wrong and must be checked. Say this plainly — a scholar's trust is
earned by your honesty about limits, and the system's own refusal behavior backs you up.

---

## To an engineer

**What they care about:** the architecture, and whether it's sound or hand-wavy.

**The framing:** *"It's RAG with an intelligence layer: **expand → retrieve → fuse → reason →
verify**. Query expansion (multi-query + HyDE + a deterministic lexicon pass) widens retrieval and
RRF-fuses the hits; a two-stage generate (analyze the sources into a study map, then synthesize)
replaces the single shot; an optional verify pass flags unsupported claims. All of it sits behind
two protocols — `Retrieving` and `GenerationBackend` — so the multi-query retriever is a drop-in
and the cloud/local model swap is unchanged."*

**Bring out:** that everything is **off by default and config-gated** (zero risk to baseline);
that the **default-deny gate runs before any model call** (enforced in code, not just prompt);
that it's **typed, DI'd, and tested with the network/models mocked**; and that the lift is
**measured** (`eval-expand`), not asserted.

**Never over-claim:** it's **not agentic** — there's no retrieve→reason→retrieve loop yet (Lesson
5.3). Say so; engineers respect a clean scope boundary far more than a vague "it reasons."

---

## To a skeptic (a funder, a gabbai, a "isn't this just ChatGPT?" relative)

**What they care about:** can it be trusted, and what's the catch.

**The framing:** *"Unlike a chatbot, it can only answer from a specific library of texts, it shows
you exactly which passages it used, and — the important part — it refuses when those texts don't
cover your question instead of inventing an answer. The recent upgrade made it *reason over* those
sources rather than just find them, but the refusal rule is unchanged."*

**Bring out:** the **refusal** (do the Beat-5 demo live — nothing convinces a skeptic like watching
it decline to answer), and the **citations** (every claim is checkable against a real source).

**Never over-claim:** don't promise it's always right; promise it's always **grounded and
checkable**, and that a human stays in the loop (it flags doubt, it doesn't auto-correct itself).
"Trustworthy because it shows its work and knows what it doesn't know" beats "it's smart."

---

## The through-line

Notice the same two facts anchor all three pitches: **it's grounded (citations) and it's honest
(refusal).** The intelligence layer is the exciting part, but trust is the *foundation* you sell
to every audience. Lead exciting, land on trustworthy.

## Hands-on

Write **three one-paragraph pitches** — scholar, engineer, skeptic — for *your* project in *your*
words, using the framings above as scaffolding. Then read each aloud and cut every sentence that
over-claims. Keep them in your back pocket; you'll give one of these three talks far more often
than you'll give the demo.

---

## You should now be able to say…

- The one thing each audience cares about (faithfulness / architecture / trust) and the framing
  that leads with it.
- What to **bring out** for each (study map / the protocol pipeline / the refusal) and the
  specific thing to **never over-claim** to each.
- The through-line: grounded + honest is the foundation you sell to everyone.

Next: **[5.3 — The horizon: the reusable pattern](05-3-the-horizon.md)** — carry this beyond
maayan.
