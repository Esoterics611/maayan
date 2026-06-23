# Lesson 8.4 — When (and when not) to fine-tune

> Module 8, Lesson 4 · ~15 min read, no setup required.
> The one question this answers: **everyone asks "should we fine-tune a model on the Torah?" —
> what's the honest answer, and why is it "not yet, and not for the reason you think"?**

This is the final lesson, and it's a lesson in restraint — fitting, since restraint is a theme
you've met all through maayan (the rashei-teivot hook it won't implement, the gate that refuses,
the human approval before derived corpus). Fine-tuning is the most-requested "next step" for any
domain LLM. maayan's design takes a clear, deliberate position on it, and understanding that
position is understanding what kind of system this is.

---

## The two things people conflate

"Fine-tune a model on chassidus" usually bundles two hopes that are actually separate:

1. **"It will know more Torah"** — i.e. fix *correctness* / coverage.
2. **"It will sound more like a maggid shiur"** — i.e. fix *fluency / register*.

The maayan thesis (and [BUILD_PLAN.md](../BUILD_PLAN.md) §5) is blunt about which one fine-tuning
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

## Why RAG stays the backbone

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

## When it *does* eventually make sense

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

> ### Under the hood — the higher-value "next layer" is your shiurim
> [BUILD_PLAN.md](../BUILD_PLAN.md) §5 points at the real leverage: "Add your shiurim. Your
> transcribed… material is exactly the high-value expert layer — it ingests through the same
> `Chunk` model with `source="expert"` (or `"shiur"`)." That's the move that compounds: transcribed
> Torah enters the *same* loop as everything else — chunked, embedded, retrieved, cited, refusable,
> retractable. It grows *correctness and coverage* (the thing fine-tuning can't), with full
> provenance, today. The horizon isn't a bigger model; it's a richer corpus and more captured
> reasoning, run through the loop you now understand end to end.

---

## Hands-on

No terminal — this one is reflection, the right note to end on.

1. **Make the argument in your own words.** In three sentences: why would fine-tuning a model on
   Tanya *not* fix the fabrication problem from Lesson 0.1 — and what would it actually change?

2. **Name the prerequisite.** What has to exist *before* fine-tuning is even worth considering, and
   which part of maayan produces it? (Hint: Module 6.)

3. **Plan the real next step.** If you wanted maayan to *know more* tomorrow, what would you do —
   and which `source` would those chunks carry? Sketch it: it's the capture loop and corpus growth
   (Modules 6–7), not a training run.

---

## You should now be able to say…

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
