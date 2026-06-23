# maayan lessons

Full lessons for the [curriculum](../CURRICULUM.md). Each is self-contained: read it, then
do the hands-on at the bottom. Work through a module in order.

## One-file / PDF edition

All lessons are also assembled into a single, print-ready document,
[../CURRICULUM_FULL.md](../CURRICULUM_FULL.md) — branded title page, clickable table of
contents, and each lesson on its own page. Regenerate it after editing any lesson:

```bash
python docs/build_curriculum.py        # writes docs/CURRICULUM_FULL.md
```

Convert it to a PDF with any HTML/CSS-based engine (they render the Hebrew correctly; a
LaTeX/pdflatex path would not):

```bash
md-to-pdf docs/CURRICULUM_FULL.md                                   # npm i -g md-to-pdf
pandoc docs/CURRICULUM_FULL.md -o maayan-curriculum.pdf --pdf-engine=weasyprint
```

The layout (fonts tuned for Hebrew + nikkud, page size, page breaks, branding) is carried in
an inline `<style>` block, so the single `.md` is self-contained.

## Module 0 — Orientation: the whole loop in your hands

- [0.1 — What RAG is, and the problem it solves](00-1-what-is-rag.md)
- [0.2 — The maayan thesis in one picture](00-2-maayan-thesis.md)
- [0.3 — Run it once, all the way](00-3-run-the-loop.md)

## Module 1 — Turning text into searchable meaning (embeddings & chunking)

- [1.1 — Embeddings & vector space](01-1-embeddings.md)
- [1.2 — Chunking: the unit of retrieval](01-2-chunking.md)
- [1.3 — Hebrew normalization (and what you deliberately don't do)](01-3-normalization.md)

## Module 2 — Finding the right passages (vector DB & hybrid search)

- [2.1 — Vector databases & the collection](02-1-vector-db.md)
- [2.2 — The indexing pipeline](02-2-indexing-pipeline.md)
- [2.3 — Hybrid retrieval & fusion (RRF)](02-3-hybrid-rrf.md)
- [2.4 — Reranking & filters](02-4-rerank-and-filters.md)

## Module 3 — The trust core (generation, grounding, default-deny)

- [3.1 — The generation backend (a swappable box)](03-1-generation-backend.md)
- [3.2 — The grounded prompt & citations](03-2-grounded-prompt.md)
- [3.3 — Default-deny: the rule that lives in code, not the prompt](03-3-default-deny.md)
- [3.4 — Context-aware follow-ups without losing grounding](03-4-context-followups.md)

## Module 4 — Knowing if it's actually good (evaluation)

- [4.1 — Why eval exists, and the metrics](04-1-why-eval-metrics.md)
- [4.2 — Running and reading the harness](04-2-running-the-harness.md)
- [4.3 — Gold sets & honest measurement](04-3-gold-sets.md)

## Module 5 — How it's built to last (the engineering spine)

- [5.1 — Dependency injection: why nothing constructs its own collaborators](05-1-dependency-injection.md)
- [5.2 — Typed throughout, pydantic at every boundary](05-2-typed-pydantic.md)
- [5.3 — Config-driven everything](05-3-config-driven.md)
- [5.4 — The Clock, and testing without the network](05-4-clock-and-testing.md)

## Module 6 — The differentiator (the capture & develop loop)

- [6.1 — Provenance & the source taxonomy](06-1-provenance.md)
- [6.2 — Capture: an expert note becomes a retrievable chunk](06-2-capture.md)
- [6.3 — Seeds vs. corrections, and the develop step](06-3-seeds-and-develop.md)
- [6.4 — The approval gate → derived corpus](06-4-approval-gate.md)
- [6.5 — Threads & the term lexicon](06-5-threads-and-lexicon.md)

## Module 7 — Running it for real (operating & tuning)

- [7.1 — Setup & dependencies](07-1-setup-and-deps.md)
- [7.2 — The knobs that matter](07-2-the-knobs.md)
- [7.3 — Choosing & swapping the generation backend](07-3-backend-swap.md)
- [7.4 — Growing the corpus](07-4-growing-the-corpus.md)
- [7.5 — The web UI as a thin layer](07-5-web-ui.md)

## Module 8 — The horizon (extending it well)

- [8.1 — Reading quality and improving it](08-1-improving-quality.md)
- [8.2 — Phase 4: the eraser & measurement](08-2-phase4-eraser.md)
- [8.3 — Phase 5: composition](08-3-phase5-composition.md)
- [8.4 — When (and when not) to fine-tune](08-4-fine-tuning.md)

*That's the full curriculum — Modules 0–8.*
