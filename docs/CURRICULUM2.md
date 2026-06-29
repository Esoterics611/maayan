# Course 2 — The Intelligence Layer: from lookup to reasoning

> A second self-study curriculum for the owner of this system. Course 1 taught you the
> RAG pipeline end to end — how a question becomes a grounded, cited answer, and how the
> capture loop makes the corpus yours. **This course is about the upgrade we just shipped
> (Prompt 31): the layer that makes the system *reason* instead of merely *look up*.**
> Same house: every concept anchored to a real file and a command you can run.

## Why this course exists

After Course 1 you had a faithful, cited, refusing RAG system — but under the hood every
"smart" verb (`ask`, `develop`, threads) was the **same single shot**: embed the question
once → search once → one model call → answer. That's a very good *lookup* system. It is not
yet *thinking*. Prompt 31 added three moves that close that gap:

1. **Ask better** — expand one question into several retrieval queries and fuse the hits
   (query intelligence).
2. **Think before answering** — analyze the sources into a study map, then synthesize a
   woven, cited answer (reasoning & synthesis).
3. **Check yourself** — flag any answer sentence its sources don't support (verification).

This course teaches each move from the ground up, then turns to the parts you actually asked
for: how to **tune and play** with it, how to **prove** it's better (not just fancier), how
to **demo** it, and how to carry the pattern into **future** projects.

## How to use this

- **Order matters, but Course 1 is the prerequisite.** You should already be comfortable
  with embeddings, hybrid/RRF search, the default-deny gate, and DI (Course 1, Modules 1–5).
  We lean on all of it.
- **Three things per lesson, same as before:** the *idea*, the *anchor* (where it lives in
  your code), and the *hands-on* (something to run). Do the hands-on — that's where it sticks.
- **Everything new is OFF by default.** You enable it per-call (`--expand --reason`) or in
  `.env`. So you can run every lesson against your live system without changing its default
  behavior.
- **Pace:** one module per sitting. Modules 0–2 are the "what we built"; Modules 3–5 are
  "run it, tune it, show it, reuse it."

## What you'll be able to do by the end

Explain *why* a verbatim query under-retrieves and how expansion fixes it; read a study map
and judge a synthesized answer; count what each mode costs in model calls and decide when
it's worth it; measure the retrieval lift with numbers; tune the knobs and even the prompts
with intent; give a crisp five-minute demo to a scholar, an engineer, or a skeptic; and reuse
the **expand → retrieve → fuse → reason → verify** pattern in any future RAG you build.

## Prerequisites

Course 1 (or equivalent comfort with this repo). The system set up and indexed per
[RUNBOOK](RUNBOOK.md). For the reasoning hands-ons you'll want a working generation backend
(OpenRouter key or local Ollama); the retrieval/expansion hands-ons run on lexicon-only
expansion with no backend at all.

---

## Module 0 — From lookup to reasoning (orientation)

*Goal: see, in your own terminal, the difference between the old single-shot answer and the
new reasoning answer — and hold a map of the three moves before we open each box.*

- **0.1 — The ceiling we hit.** What "fancy lookup" actually means in the code: one query,
  one search, one model call (`retrieve/retriever.py`, `generate/rag.py`). Why that caps
  intelligence for *conceptual* Torah questions, where the answer's wording rarely matches the
  question's. Anchor: the original single-shot `ask`. Hands-on: ask a conceptual question and
  read the sources it did (and didn't) find.
- **0.2 — The three moves (the map).** Expand, reason, verify — what each adds, and the one
  thing none of them touch (default-deny). The shape of the upgraded `ask`. Anchor:
  `CURRICULUM2.md` ↔ the two commits (31a/31b). Hands-on: skim the new config flags.
- **0.3 — Feel the difference.** Run the *same* question three ways: plain, `--expand`, then
  `--expand --reason --show-reasoning`. Watch the sources improve and the study map appear.
  Hands-on: three `maayan ask` runs side by side.

---

## Module 1 — Asking better (query intelligence)

*Goal: understand why one verbatim query is a weak net, and exactly how maayan widens it —
deterministically with your lexicon, and generatively with reformulations + HyDE — then fuses
the results.*

- **1.1 — Why a verbatim query under-retrieves.** The vocabulary-mismatch problem: a
  conceptual question and the source that answers it often share *no words*. Why embedding the
  raw question once leaves good sources unfound. Anchor: the single `embed_query` call in
  `retrieve/retriever.py`. Hands-on: a question that misses an obviously-relevant source.
- **1.2 — Multi-query & HyDE.** Two generative ways to widen the net: ask the model for
  several rephrasings/sub-angles, and ask it to draft a *hypothetical source passage* (HyDE)
  and search with that. Why a fake answer makes a great query. Anchor: `LLMQueryExpander` in
  `retrieve/expand.py`. Hands-on: print the variants the model generates for one question.
- **1.3 — Lexicon-aware expansion (no model needed).** The cheap, deterministic expander that
  reuses your curated `TermStore`: when a registered term appears in the query, inject its
  canonical form and related terms. Free, fast, always-on, and uniquely yours. Anchor:
  `LexiconExpander`. Hands-on: expand a query containing a term you've defined.
- **1.4 — Fusing the nets: RRF + the drop-in retriever.** How several result lists become one
  ranking (Reciprocal Rank Fusion, revisited from Course 1 2.3), why `relevance = max` keeps
  the refusal gate honest, and how `MultiQueryRetriever` slots in behind the `Retrieving`
  protocol so nothing downstream changes. Anchor: `retrieve/fuse.py`,
  `MultiQueryRetriever`, `retrieve/factory.py`. Hands-on: watch a fused result appear that
  neither single query surfaced.

---

## Module 2 — Thinking before answering (reasoning & synthesis)

*Goal: understand the two-stage answer — analyze the sources into a study map, then weave a
grounded answer from it — why that suits chassidus specifically, and how the trust core stays
intact.*

- **2.1 — One pass vs. two stages.** The shape change: instead of "sources in → prose out,"
  the model first reads the sources, *then* writes. Why splitting analysis from composition
  raises quality. Anchor: the `reasoning` branch in `RAGService.ask`. Hands-on: run with
  `--reason` and compare to plain.
- **2.2 — The study map.** What ANALYZE produces: each source's claim in one line, then where
  sources *agree*, *build* on each other, and *conflict*. Why this map is exactly the move a
  chavrusa makes — and why it's the most chassidus-shaped part of the whole system. Anchor:
  `ANALYZE_SYSTEM_PROMPT`, `build_analyze_messages`. Hands-on: read a study map with
  `--show-reasoning`.
- **2.3 — Synthesis: weave, don't list.** How the second stage turns the map + sources into a
  single coherent, cited answer — and the prompt discipline that keeps it grounded (cite only
  `[S#]`, never the map). Anchor: `_synthesis_user_content`. Hands-on: inspect the exact
  prompt the synthesis stage receives.
- **2.4 — Checking yourself, and the rule that didn't change.** The optional verify pass that
  flags unsupported sentences — and the non-negotiable invariant that survived every change:
  **default-deny still fires before any model call.** Anchor: `VERIFY_SYSTEM_PROMPT`,
  `parse_unsupported`, the gate in `ask`. Hands-on: force a refusal with all flags on and
  confirm the model is never called.

---

## Module 3 — Proving the lift (evaluation & cost)

*Goal: replace "this feels smarter" with numbers and a clear sense of what each mode costs.*

- **3.1 — The cost ladder.** Count the model calls: plain (1), +verify (2), +reasoning (3),
  +expansion (up to +2). Why everything is off by default, and how to choose a mode for a
  situation. Anchor: the `generate()` calls in `ask` and `LLMQueryExpander`. Hands-on: a
  recording backend that counts calls per mode.
- **3.2 — Measuring retrieval with `eval-expand`.** Run the harness with expansion off vs. on,
  read recall@k / MRR / gate rates, and learn when expansion helps (conceptual, cross-text)
  and when it doesn't. Anchor: `cli.py eval-expand`, `eval/harness.py`. Hands-on:
  `make eval-expand` and `make eval-expand ARGS='--crosstext'`.

---

## Module 4 — Tuning & playing (making it yours)

*Goal: confidently turn the knobs — and even edit the prompts — to fit your corpus, your
model, and your taste, without breaking the guarantees.*

- **4.1 — The knobs, and recipes.** A tour of every new setting (`QUERY_EXPAND_*`,
  `RAG_REASONING_ENABLED`, `ANSWER_VERIFY_ENABLED`) and four ready-made recipes:
  cheap-and-fast, lexicon-only, deep-and-thorough, local-model. Anchor: `config.py`,
  `.env.example`. Hands-on: set a recipe in `.env` and feel it.
- **4.2 — Editing the prompts (and diagnosing failures).** The analyze/synthesis/verify
  prompts are injectable, not hardcoded — how to change them safely, plus the common failure
  modes (over-expansion drowning the signal, a verbose study map, a verifier that flags
  everything) and how to spot and fix each. Anchor: the prompt constants in `generate/rag.py`,
  the expander constructors. Hands-on: inject a custom analyze prompt and compare maps.

---

## Module 5 — Demoing & explaining (telling the story)

*Goal: show this to other people and have it land — whether they're a scholar, an engineer, or
a skeptic — and know how to carry the pattern forward.*

- **5.1 — The five-minute demo.** An exact script: what to type, in what order, and what to
  point at — building to the two payoff moments (the study map; the connection it surfaced).
  Includes the all-important refusal. Hands-on: rehearse the script end to end.
- **5.2 — Explaining it to three audiences.** The same system framed for a *scholar* (a tireless
  chavrusa that never invents a mekor), an *engineer* (expand→fuse→reason→verify, all behind
  protocols), and a *skeptic* (where it refuses, and what it will and won't claim). What to
  bring out, and what to never over-claim. Hands-on: write your own one-paragraph pitch for each.
- **5.3 — The horizon: the reusable pattern.** Lift the pattern off this corpus — the
  expand→retrieve→fuse→reason→verify loop applies to any RAG — and look squarely at what's
  deliberately *not* here yet (agentic multi-hop and why it needs a richer backend contract).
  Anchor: the `Retrieving` / `GenerationBackend` protocols. Hands-on: sketch where you'd add a
  retrieve→reason→retrieve loop.

---

> **Built this course?** Re-assemble the single PDF-ready document any time with
> `python docs/build_curriculum2.py`, then convert with `md-to-pdf docs/CURRICULUM2_FULL.md`.
