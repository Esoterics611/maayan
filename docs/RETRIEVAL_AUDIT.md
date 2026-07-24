# Retrieval audit — findings, fixes, and how to re-measure

maayan's claim is that answers are grounded only in retrieved, cited sources and that
it refuses honestly when nothing supports them. That claim is exactly as strong as
retrieval. This is the record of the first rigorous audit of it: what was measured,
what turned out to be true, what was fixed, and which commands reproduce the numbers.

Corpus at audit time: 8,764 chunks — Tanya Part I (Likkutei Amarim), Torah Ohr
(24 parshiyot, via Sefaria), Likutei Torah (41 sections, via Chabad Library), plus
19 expert / 16 term / 2 derived chunks.

---

## Headline

On the authored gold set (42 positive questions, 10 negative), before → after:

| | answers positives | refuses negatives | hit@10 | recall@10 | MRR |
|---|---|---|---|---|---|
| **before** | 1.00 | **0.30** | 0.524 | 0.484 | 0.274 |
| **after** | 1.00 | **0.80** | **0.857** | **0.810** | **0.559** |

On twelve blatantly off-topic control queries (never in any gold file), refusal went
**0.67 → 1.00**. Answer rate on real questions never moved off 1.00 — the system did
not become more reluctant, it became more discriminating.

---

## What was actually wrong

### 1. The corpus was in two lexical spaces (the big one)

Tanya is stored fully vocalized — 697 of 697 Hebrew chunks carry nikkud. Every other
book is plain: 0 of the other 7,171. Queries are always typed without nikkud.

bge-m3 tokenizes nikkud as separate subword pieces, so the *same* Tanya passage
yields 64 sparse terms vocalized versus 38 plain, sharing only 7–15 of them — Jaccard
**0.08–0.17**. Tanya's indexed vectors and the queries meant to find them were
effectively in different vocabularies, and Tanya is what the gold set is written
against.

Folding nikkud on the way *into* the embedder (stored text keeps its nikkud):

| branch | MRR | hit@3 | recall@10 |
|---|---|---|---|
| dense | 0.386 → **0.678** | 0.452 → **0.810** | 0.599 → **0.798** |
| sparse | 0.120 → **0.453** | 0.190 → **0.571** | 0.202 → **0.571** |
| hybrid | 0.274 → **0.583** | 0.310 → **0.738** | 0.484 → **0.810** |

A control arm — folded *query* against the *unfolded* index — scored identically to
before on every metric, which localizes the entire defect to the index side and is
why `EMBED_FOLD_NIKKUD=true` is safe to default on before a re-index.

Gershayim/geresh are deliberately **not** folded: they mark rashei-teivot, and
stripping them merges distinct forms (ע״ב → עב) rather than aligning them.

### 2. The gate was far too permissive, not too aggressive

The gate was `top dense cosine >= 0.45`. Measured against 42 positives and 22
negatives (10 authored + 12 off-topic controls), it answered **50%** of the negatives:
"explain the theory of general relativity" scored 0.500, "מה שלומך היום" 0.520,
"python list comprehension syntax" 0.451.

The cause is structural. Over ~9k passages the maximum cosine is a max over noise:
*something* always scores 0.43+. bge-m3 cosine occupies a narrow band (~0.37–0.65)
for everything, so no single absolute cutoff separates.

Two changes, both measured:

- **Pool instead of peak.** Mean cosine over the top `GATE_POOL` hits is a much
  lower-variance estimate of how much relevant material exists (AUC 0.946 → 0.968).
- **Let the lexical branch vote.** `dense_mean + 3·sparse_mean` reaches AUC **0.988**
  on the folded index and, at 0.795, answers 100% of positives while refusing 91% of
  all negatives. This also fixes the failure the item was raised for: a strong
  exact-term match with mediocre cosine is now carried by the branch that sees the term.

Hypotheses that were **wrong** and got dropped: contrast/margin signals. "On-topic
queries have a peaked score distribution, off-topic ones are flat" sounded right and
is false here — `dense_z` scored AUC 0.63, `dense_ratio` 0.77, both far below plain
`dense_top` at 0.95. Peakedness measures nothing useful on this corpus.

### 3. `query_expand_enabled` meant two different things

Expansion is only as strong as what the factory hands `build_retriever`: with no
`backend`, `CompositeExpander` degrades to lexicon-only — no LLM reformulations, no
HyDE. Only `cli.ask` passed one. Compose `fill`, develop, the lexicon populator and
the study-program drafter all ran weaker retrieval under the same config, silently.

### 4. The reranker was broken, not merely off

`RERANK_ENABLED=true` raised `AttributeError` on every retrieval: FlagEmbedding's
`FlagReranker` calls `tokenizer.prepare_for_model`, which transformers 5 removed. The
embedder uses a different code path, so nothing surfaced it — the reranker is off by
default, so no test and no default path ever ran it.

### 5. What was fine

- **Corpus coverage.** Sefaria: 3,346/3,346 segments, exact per book. Likutei Torah:
  all 41 top-level sections the Chabad Library root lists. Store 8,764 == Qdrant 8,764.
  A suspected missing פרשה שופטים turned out not to exist upstream either.
- **Sparse vectors are indexed and do reach fusion.** The R4 worry was that they were
  "carried and ignored"; the truth was the opposite — they were fully weighted and
  *actively harmful*, because of finding #1.

---

## Standing tools (run these; don't eyeball retrieval again)

```bash
maayan inspect "<query>"        # per-branch scores + the gate decision, in seconds
maayan coverage [--remote]      # store vs index vs source must reconcile; non-zero exit on drift
maayan eval                     # hit@k / recall@k / MRR + gate rates on the authored gold set
maayan eval --lexical           # precision@k / recall@k against corpus-derived ground truth
maayan eval --lexical --rebuild # regenerate the lexical cases after a corpus change
```

`maayan inspect` exists so the question that started this audit ("why did this
refuse?") never again costs an investigation. It shows the query as actually sent,
the dense / sparse / fused / rerank rankings side by side, which branches contain each
ref, the absolute gate signals, and the decision with its threshold.

### Baselines to regress against

Recorded on the folded index, `GATE_SIGNAL=hybrid_pool`, threshold 0.795:

```
maayan eval        hit@1 0.381  hit@3 0.714  hit@5 0.786  hit@10 0.857
                   recall@10 0.810   MRR 0.559
                   answered 1.000 (of 42 positives)   refused 0.800 (of 10 negatives)

maayan eval --lexical   precision@1 0.800  precision@3 0.693  precision@10 0.580
                        25 terms, 1,987 verified occurrences
```

---

## Config that matters

| setting | default | why |
|---|---|---|
| `EMBED_FOLD_NIKKUD` | `true` | Finding #1. Changing it requires a re-index. |
| `GATE_SIGNAL` | `hybrid_pool` | Finding #2. `dense_top` restores the old behavior exactly. |
| `GATE_HYBRID_THRESHOLD` | `0.795` | Threshold for `hybrid_pool`. **Not** on the cosine scale. |
| `GATE_SPARSE_WEIGHT` | `3.0` | Puts sparse (~0.05–0.15) on par with cosine (~0.40–0.65). |
| `GATE_POOL` | `10` | Depth the mean signals average over. |
| `SCORE_THRESHOLD` | `0.45` | **Used only when `GATE_SIGNAL=dense_top`.** |

Each gate carries its own threshold and `Settings.effective_score_threshold` is the
single accessor, because reusing one gate's number for the other silently disables the
gate in one direction. That footgun is real: introducing the property immediately
broke 18 tests that had been assuming `score_threshold` was universal.

---

## Still open

- **Hybrid finds more but ranks worse.** Even after the fold, dense-only beats hybrid
  on MRR (0.678 vs 0.583) while hybrid wins on hit@10 (0.857 vs 0.833) and recall@10
  (0.810 vs 0.798). Grounding wants recall, so hybrid stays the default — but a
  weighted fusion (rather than Qdrant's fixed server-side RRF, k=2) is untested and
  might get both.
- **Rashei-teivot expansion** is still unimplemented and still unproven. The nikkud
  fold was the demonstrable win; whether an abbreviation table moves recall has not
  been measured, so per CLAUDE.md it stays unbuilt.
- **Parent-context quality.** Wiring it into compose/fill closed a real inconsistency
  with `ask`, but its effect is on section prose, not on the gap rate — parent context
  attaches *after* the gate, so it cannot change how often compose refuses. Measuring
  the prose effect needs the LLM-judge harness.
- **Indexing throughput.** A full `index --rebuild` ran at roughly 20 chunks/min on
  this box (Quadro T1000, `EMBED_BATCH_SIZE=8`), which projects to ~7 hours — slower
  than the 2h CPU figure in the runbook. GPU memory sat at 1.4GB of 4GB, so the batch
  size looks like the limiter and is worth raising before the next full re-index.
- **Gold set size.** 42 positives and 22 negatives is enough to see effects this large
  and not enough to tune finely. The thresholds here are honest fits to a small
  sample; treat them as good starting points, not settled constants.
