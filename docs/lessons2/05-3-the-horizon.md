# Lesson 5.3 — The horizon: the reusable pattern

> Module 5, Lesson 3 · ~12 min read + a design sketch.
> The one question this answers: **what did I really build that I can reuse anywhere — and
> what's the honest next step beyond it?**

You set out to make the system "more intelligent, not just a fancy lookup." You did. This final
lesson lifts the result off *this* corpus so you can carry it into future projects — and names,
squarely, the one big thing deliberately left for next time.

---

## The pattern, abstracted

Strip away the Torah specifics and what you built is a general recipe for turning any retrieval
system into a reasoning one:

```
EXPAND   — ask the question several ways (rephrase, hypothesize, inject domain vocabulary)
RETRIEVE — run each query through your existing search
FUSE     — merge the hit-lists by rank (RRF), keeping an absolute relevance signal for gating
REASON   — analyze the retrieved evidence into a structured map, THEN compose from the map
VERIFY   — check the output's claims against the evidence; surface doubt, don't auto-fix
```

None of this is Torah-specific. The *lexicon* expander is the one domain-flavored piece — and the
lesson there generalizes too: **any structured domain knowledge you already have (a glossary, a
taxonomy, a synonym list) can deterministically widen retrieval for free.** Wherever you build a
RAG next — case law, medicine, a codebase, internal docs — this five-step loop applies, and the
three trust rules (ground every claim, refuse without evidence, keep the human in the loop) port
unchanged.

That's the real takeaway of Course 2: not five features, but a **repeatable way to add
intelligence to retrieval without sacrificing trust.**

---

## What's deliberately not here: agentic multi-hop

There's a ceiling we *didn't* break, on purpose. Every answer still does **one** retrieval pass
(now widened, but one). It cannot notice mid-answer that "these sources cover X but the question
also needs Y" and **go look again**. That loop — retrieve → reason → *decide more is needed* →
retrieve again → synthesize — is **agentic multi-hop**, and it's the natural next rung.

Why it was left out is itself worth understanding. Multi-hop needs the model to *act*, not just
emit text: to decide "I need more" and issue a follow-up query. That requires a richer
`GenerationBackend` contract — structured output or tool-calling — instead of today's clean
string-in/string-out. Adding it touches the one protocol we kept stable all course. So it's not a
tweak; it's a deliberate next project, with its own design and its own risks (loops that don't
terminate, runaway cost). Knowing *why* a feature is out of scope is as much engineering maturity
as knowing how to build one.

The protocols you have are already the seam where it'll attach: `Retrieving` (you'd call it in a
loop) and `GenerationBackend` (you'd extend it to return a decision, not just prose). The system
was built to grow here.

---

## Honest limits to carry forward

Say these out loud so you never oversell:

- It **retrieves and relates**; it does not *know*. A missing source is a missing answer.
- Reasoning can **manufacture connections**; the study map makes them auditable, but a human must
  still audit.
- Verify **flags**, it doesn't **fix**; and on a weak model it can mis-flag.
- More intelligence costs **more model calls** (up to 5); spend them where they earn it.

These aren't apologies — they're the boundary that makes the trustworthy core trustworthy.

---

## Hands-on

**Sketch the next rung.** On paper, design a minimal agentic loop for maayan:
1. After the study map, what *question* would the model ask itself to decide "do I have enough?"
2. What would the follow-up query be, and how would you feed its results back (RRF again?)?
3. What would you add to `GenerationBackend` so it can return *"need more: <query>"* vs. *"ready
   to answer"* — and where would you cap the number of hops?

You don't have to build it. Sketching it proves you understand both the pattern you completed and
the seam where it extends — which is exactly the understanding this course set out to give you.

---

## You should now be able to say…

- The reusable, domain-agnostic pattern: **expand → retrieve → fuse → reason → verify**, plus the
  three portable trust rules.
- What agentic **multi-hop** is, why it's the next rung, and *why* it was deliberately scoped out
  (it needs a richer backend contract — the one protocol kept stable).
- The honest limits of what you built — and that naming them is what keeps the core trustworthy.

---

*End of Course 2. You can now explain, run, tune, demo, and extend the intelligence layer — and
carry its pattern into whatever you build next. The wellspring runs deeper.*
