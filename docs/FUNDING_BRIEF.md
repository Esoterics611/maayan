# maayan — Run Brief & Funding Ask

**maayan** (מעיין, "wellspring") is a grounded retrieval system over chassidus /
Kabbalah primary texts. It answers questions **only** from retrieved source
passages, with inline citations, and **refuses** when the sources don't support an
answer — it never answers from a model's own memory. An expert-in-the-loop step
turns a scholar's corrections and cross-text connections into new retrievable
knowledge.

This brief covers one unit of work — the **automated knowledge-population run** and
the **benchmark** that measures it — with the real costs, deliverables, and the ask.

---

## Two-phase plan (why we're not spending yet)

The work is split to de-risk spend:

1. **Bootstrap — now, $0.** Build and validate the entire pipeline (populators,
   approval gate, benchmark harness) on **free open models**. Proves the machinery
   end-to-end at zero model cost and produces a first, lower-quality knowledge layer.
2. **Production run — after funding.** Re-run the *identical* pipeline on **top
   models** (Claude Opus 4.8 / GLM-5.2) across the full corpus. Same code, stronger
   drafter → the publishable knowledge base and benchmark result.

Nothing in the code changes between phases — only the model behind one config
switch. Cost is the sole variable. Every dollar raised goes to the production
result, not to proving the machinery works.

---

## Current state (already built, unfunded)

- **Live retrieval index: 4,241 source passages** — Tanya (Likkutei Amarim, all 53
  chapters) + Torah Ohr (every parsha of Bereishis and Shemos), Hebrew + English.
- **Full pipeline built and tested:** hybrid retrieval, grounded generation with
  citation + honest refusal, the expert capture loop, and two **auto-populators** —
  a strong model *drafts* (a) term/concept definitions and (b) cross-text
  connections, each grounded in retrieved sources, cited, run through a faithfulness
  check, and **held behind an expert approval gate** before anything is indexed.
  Nothing is self-trusted.
- **Not yet ingested: Likutei Torah** — not available on Sefaria; needs a separate
  text source + ingestion adapter. This is the main corpus-expansion line item.

---

## Cost of one full populate run (Tanya + Torah Ohr)

Scope: ~40 curated core terms + mined technical terms + cross-text connections —
roughly **200 terms + 100 connections**. Each item = **2 model calls** (a grounded
draft + a faithfulness check).

| Drafter | Price (in / out per 1M tokens) | Full run | Throughput |
|---|---|---|---|
| Free open model (Llama-3.3-70B, Qwen3-80B, …) | $0 | **$0** | ~50 calls/day → multi-day drip |
| GLM-5.2 (z.ai) | $0.93 / $3.00 | **~$3–5** | one session |
| Claude Opus 4.8 | ~$5 / $25 | **~$15–25** | one session |

Compute is **not** the constraint — even the top-model run is tens of dollars. The
real costs are corpus acquisition and expert time (see the ask).

---

## The benchmark

A blinded head-to-head that answers one question: **does a grounded system over
primary texts beat a frontier model answering from memory, on this domain?**

- **Arm A — maayan:** answers built only from retrieved, cited passages.
- **Arm B — frontier model, closed-book:** same questions, no retrieval, no web.
- **Grader:** a frontier model scores both answers against the expert's gold answer
  and a rubric, **blinded** — answer order randomized, identities hidden — to remove
  self-preference.
- **Ablation:** maayan on raw text only vs. maayan + the auto-populated knowledge
  layer. Isolates exactly what the population run adds.
- **Gold set:** ~60 questions written by the **domain expert**, weighted toward the
  texts where a from-memory model is weakest, with a control stratum.

---

## Deliverables

1. A populated, **expert-approved** knowledge layer (defined terms + cited
   cross-text connections), retrievable alongside the source text.
2. A run report: drafted vs. faithfulness-passed vs. expert-approved counts, with
   before/after coverage.
3. The benchmark harness + a results table (answer accuracy, citation faithfulness,
   refusal correctness) with significance.
4. An academic write-up — methods, results, a qualitative appendix contrasting a
   from-memory attribution error against a grounded citation, and limitations —
   delivered as a Hebrew/RTL-ready PDF.

---

## Business value

- **Trust by construction.** Every answer traces to a printed source and refuses
  when unsupported. In a domain where a wrong attribution is a real failure, that
  guarantee *is* the product.
- **A compounding asset.** The expert-approved term + connection layer is
  proprietary, grows with every use, and is the moat — not the model, which is
  swappable by design.
- **Expert leverage.** One scholar's review is amplified across the whole corpus;
  the capture loop banks each correction permanently instead of losing it.
- **Evidence, not assertion.** The benchmark yields a defensible number on where
  grounded-open beats frontier-closed — the basis for the raise and for adoption.

---

## The ask

Funds the production run and the corpus expansion that make it publishable:

| Line item | Estimate |
|---|---|
| Likutei Torah — text acquisition + ingestion adapter | data + dev (your rates) |
| Top-model populate over the full corpus (Opus 4.8 / GLM-5.2) | $50–500 |
| Benchmark grading (frontier judge, multi-run) | $20–50 |
| Expert honorarium — 60 gold questions + draft review/approval | expert hours |

The compute is a rounding error. The raise is for **corpus and expert time** — the
two inputs that make the result real. The free-model bootstrap has already absorbed
all the build risk.
