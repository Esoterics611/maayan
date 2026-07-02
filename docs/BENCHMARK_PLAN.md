# Benchmark Plan — grounded maayan vs. frontier closed-book

Companion to [FUNDING_BRIEF.md](FUNDING_BRIEF.md) and
[POPULATE_REPORT.md](POPULATE_REPORT.md). This is the plan you act on: **you write
the gold questions; I build the missing harness, run every rung, capture results, and
write the paper.**

---

## 1. Objective & hypothesis

**Question:** on chassidus / Kabbalah primary texts, does a grounded system that
answers only from retrieved, cited passages beat a frontier model answering from
memory — and how much does the expert-approved synthetic layer (terms + connections)
add on top of raw text?

**Hypotheses:**
- **H1** maayan (grounded) ≥ frontier closed-book on *citation faithfulness* and
  *correct refusal*, and competitive-or-better on *answer accuracy*, precisely where
  a from-memory model is weakest (specific ma'amarim, exact attributions).
- **H2** maayan + synthetic layer > maayan text-only (the populate run adds real value).

---

## 2. What's already in place

- **Corpus:** Tanya (Likkutei Amarim, 53 ch) + Torah Ohr (all Bereishis/Shemos
  parshiyos) — 4,269 live passages.
- **Synthetic layer (bootstrap):** 16 terms (`source="term"`) + 12 cross-text
  connections (`source="expert"`), all grounded/cited/expert-gated. Free-model run;
  a top-model rerun is the funded upgrade.
- **Eval harness (reuse):** retrieval `hit@k`/`recall@k`/`MRR` (`maayan eval`),
  answer quality — citations + faithfulness via an LLM judge (`maayan eval --answer`,
  `EVAL_JUDGE_MODEL`), cross-text `book-diversity@k` (`eval --crosstext`), query-
  expansion compare (`eval-expand`), and the reasoning toggle (`RAG_REASONING_ENABLED`).
- **Ablation lever (reuse):** retrieval already accepts a `source` filter, so
  "text-only" = retrieve `source="sefaria"` only; "+synthetic" = retrieve all.

**To build (I do this):** (a) a `answer` field + gold answers in the gold set,
(b) a **closed-book Arm-B runner** (frontier model, no retrieval/web), (c) a
**blinded pairwise judge** harness, (d) ablation wiring to pass the source filter
through the answer harness.

---

## 3. Design

Two arms, plus an ablation inside Arm A:

- **Arm A — maayan (grounded):** answer built only from retrieved, cited passages;
  default-deny refusal in force. Two sub-conditions for the ablation:
  - **A-text:** retrieve `source="sefaria"` only.
  - **A-synth:** retrieve all (text + terms + connections).
- **Arm B — frontier closed-book:** same question, no retrieval, no web, no tools.

The tuned maayan recipe (see Rung 1) is fixed before any head-to-head so we compare
"maayan at its best" against the frontier baseline.

---

## 4. The gold set — **your deliverable**

~60 expert-authored questions, stratified. Extends the existing schema with a gold
**answer** and a **stratum** tag. Template (drop into `eval/benchmark_goldset.yaml`):

```yaml
examples:
  - question: "…"                     # the question, as a learner would ask it
    stratum: "torah_ohr"              # torah_ohr | tanya_control | cross_text | negative
    expected_refs:                    # chapter/os-level refs that should ground it
      - "Torah Ohr, Miketz 5:11"
    answer: |                         # YOUR gold answer — what a correct, sourced reply says
      …a few sentences, with the mekoros…
    note: "optional grader hint"
  # negative (tests the refusal gate): no refs, should_refuse
  - question: "…a question the corpus does NOT answer…"
    stratum: "negative"
    should_refuse: true
    expected_refs: []
```

**Stratification (guidance):**
- **~30 Torah Ohr–heavy** — where a from-memory model is weakest (this is the case
  for grounding).
- **~15 Tanya control** — a from-memory model is *strongest* here (honest control).
- **~10 cross-text** — answer needs ≥2 books; tests co-retrieval + connections.
- **~5 negatives** — corpus genuinely can't answer; correct behavior is refusal.

Write for the texts we actually have (Tanya + Torah Ohr). Hold Likutei Torah
questions until it's ingested.

---

## 5. Grading protocol (blinded)

- **Grader:** a strong frontier model (funded — paid OpenRouter / Anthropic), **not**
  either model under test, to avoid self-preference.
- **Blinding:** the two answers are presented as "Answer 1 / Answer 2" in **randomized
  order**, identities hidden. The grader never learns which is maayan.
- **Rubric (per question, scored 1–5):** faithfulness to sources, factual accuracy vs.
  the gold answer, citation correctness, and — for negatives — whether the model
  correctly refused. Plus a forced **pairwise preference** (which answer is better).
- **Anti-leakage:** the maayan+synthetic ablation guards against "the gain is just
  smuggled-in frontier knowledge" — A-text vs A-synth isolates the synthetic layer's
  contribution independent of the grader.

---

## 6. Metrics captured

Per arm / sub-condition, over the gold set:
- Answer accuracy (mean rubric score vs. gold).
- Citation faithfulness (% cited claims supported by the cited source).
- Refusal correctness (negatives: refused / total).
- Cross-text recall (cross-text stratum: answers citing ≥2 books).
- Pairwise win-rate A vs B (blinded), with a significance test (bootstrap CI /
  sign test over questions).
- Ablation delta: A-synth − A-text on every metric above.

---

## 7. Run sequence (rungs)

| Rung | What | Reuses / builds | Cost |
|---|---|---|---|
| **0** | First reasoning numbers: `eval --answer` reasoning off vs on, distinct judge | reuse | judge calls |
| **1** | Tuning sweep: `SCORE_THRESHOLD`, `TOP_K`, `RERANK_ENABLED`, `QUERY_EXPAND_ENABLED`, `RAG_REASONING_ENABLED` → pin best `.env` | reuse | judge calls |
| **2** | Ablation A-text vs A-synth on the tuned recipe | build (source-filter wiring) | judge calls |
| **3** | Head-to-head A vs B (closed-book), blinded grader | build (Arm-B runner + pairwise judge) | **frontier grader (funded)** |
| **4** | Significance + result tables | build (aggregation) | — |
| **5** | Paper: methods, results, qualitative appendix (a hallucinated mekor vs. a grounded citation), limitations → PDF | `md-to-pdf` skill | — |

Rungs 0–2 can run now on a free/local judge (with caveats noted in the writeup);
Rung 3's frontier grader is a funded line item (ties back to the brief). All model
ids, the pinned `.env`, and RNG seeds are recorded for reproducibility.

---

## 8. Division of labor

- **You:** author `eval/benchmark_goldset.yaml` (~60 questions per §4). That's the
  one human input the whole study hinges on.
- **Me:** build the four missing harness pieces (§2), run rungs 0–5, capture every
  number, and write the paper.

---

## 9. Honesty caveats (stated up front in the paper)

- The benchmarked synthetic layer is currently the **free-model bootstrap** (16 terms
  + 12 connections, Torah-Ohr-heavy, no Tanya-spanning connections yet). Numbers will
  be labeled as such; the top-model rerun is a separate, stronger condition.
- Corpus is Tanya + Torah Ohr only; claims are scoped to it.
- The grader is an LLM; blinding + the ablation are the guardrails, not a claim of
  perfect objectivity. Gold answers are the expert's, hand-curated, not authoritative.
