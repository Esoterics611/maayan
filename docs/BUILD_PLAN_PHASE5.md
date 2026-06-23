# maayan — Build Plan, Phase 5: Composition — from grounded answers to grounded documents

> Companion to [BUILD_PLAN.md](BUILD_PLAN.md) (Prompts 0–8),
> [BUILD_PLAN_PHASE2.md](BUILD_PLAN_PHASE2.md) (9–16), and
> [BUILD_PLAN_PHASE4.md](BUILD_PLAN_PHASE4.md) (17–19). This continues the sequence as
> **Prompts 20–22**.
>
> **Every prompt must follow [CLAUDE.md](../CLAUDE.md)** — typed + `mypy --strict`,
> dependency injection, config-driven, no secrets, default-deny, tests mock network +
> models, ephemeral/in-memory Qdrant for index/retrieve tests. Run them one at a time;
> let `make test`/`typecheck`/`lint` pass before moving on.

---

## 0. Why this phase exists (the shift)

Phases 1–4 generate **one grounded passage at a time**: `RAGService.ask`
([rag.py](../maayan/generate/rag.py)) answers a question; `DevelopmentService.develop`
([develop/service.py](../maayan/develop/service.py)) develops a seed under a directive.
Both are the *same unit*: retrieve once → default-deny gate → one cited block → (for
develop) a reviewable proposal.

The next capability is **going beyond chat to producing a structured document** — a
shiur/class outline, an essay, a digest — from a single prompt. The crucial realization:
this is **not a new generation engine**. It is an orchestration layer that runs the unit
we already have **once per section**, so a long piece is grounded section-by-section
rather than from one over-stretched retrieval.

### Why long-form can't be one `ask`

A chat answer retrieves **once** for **one** question; an essay's later half would drift
ungrounded. So a composition **decomposes** the brief into an outline (each section = its
own retrieval sub-question), then **fills** each section with the existing grounded unit —
each section independently retrieved, gated, and cited.

### The differentiator: default-deny *per section*

This is what makes a *maayan* document generator different from generic LLM writing. When
the corpus doesn't support a section, the gate at
[rag.py:137](../maayan/generate/rag.py:137) fires and the section becomes an **honest gap**
("the sources here don't reach this"), never fabricated prose. A piece with honest holes
beats a confident invention — for Torah that is the whole point.

## 1. Decisions already made (build to these)

- **Primary content type: the shiur / class outline.** Design around it first — ordered,
  teachable points, each grounded in source(s), for a scholar to teach from. Essay and
  digest are the same engine with a different register; build the type as a config-driven
  `Literal`, ship `shiur_outline` first, leave the others as registers.
- **Outline gate is config-toggleable** (mirror `develop_auto_approve`): `compose_auto_outline`
  (default `false`). When `false`, the proposed outline is returned for the expert to
  **edit/reorder/approve** before any section is filled — the human controls coverage.
  When `true`, the model's outline is filled immediately (quick drafts). Build both.
- **Default-deny is per section, enforced in code** — not just the prompt — exactly as in
  `ask`/`develop`. An unsupported section is a gap, with **no model call** for it.
- **Compositions are human-facing artifacts, reviewed like developments.** propose →
  (approve | reject); export to markdown with a provenance footer.
- **Approval does NOT bulk-index the prose.** Re-ingesting a whole essay as one chunk
  pollutes retrieval. The loop-worthy knowledge a composition surfaces is the *connections*
  between passages — those flow back through the existing `expert`/`derived` chunk types
  (Phase 2), one connection at a time, not as a wall of prose.
- **Reuse, don't reinvent.** The injected `Retriever` + `GenerationBackend`, the
  default-deny gate, and `build_context` / `extract_cited_refs`
  ([rag.py:67](../maayan/generate/rag.py:67), [:83](../maayan/generate/rag.py:83)) are used
  verbatim. The propose→review shape copies `DevelopmentService`.

## 2. New data model (the spine for this phase)

Pydantic models (CLAUDE.md rule 1); SQLite via idempotent migrations (follow the `indexed`
column pattern). A composition may live in a thread — extend the `ThreadTurn` `turn_type`
literal with `"composition"` (additive, migration-safe).

- **`Brief`** (the prompt/spec): `id, title, intent` (what the piece should do),
  `content_type` (`Literal["shiur_outline","essay","digest","other"]`, default
  `"shiur_outline"`), `lang`, `target_sections: int | None`, `source_scope`
  (optional book/source filters passed straight to the retriever),
  `seed_frameworks: list[str] = []` (expert frameworks to attribute, never cite),
  `author` (**required** — blank rejected, as in Prompt 9), `thread_id: str | None`.
- **`Section`**: `heading, query` (the retrieval sub-question), `text`,
  `cited_refs: list[str]`, `grounded_in: list[str]`, `supported: bool`.
- **`Composition`** (mirrors `Development`): `id, brief_id, thread_id, status`
  (`"proposed" | "approved" | "rejected"`), `sections: list[Section]`, `model`,
  `created_at`. Aggregate `cited_refs` / `grounded_in` derive from the sections.

## 3. Invariants to re-check at every step (don't regress)

- Default-deny enforced in code — for `ask`, follow-ups, `develop`, **and every section**.
- Citations only ever reference retrieved sources; seed frameworks and the outline are
  attributed but never cited. Transitions introduce **no new claims**.
- Printed text immutable; composition prose is an artifact, not a corpus chunk. Only
  surfaced *connections* flow back, via the existing expert/derived loop.
- Provenance travels with every artifact (author, brief, per-section grounded refs, gaps).
- Typed + `mypy --strict`, DI, config-driven, secrets only via env, tests mock
  network/models, ephemeral Qdrant for retrieve tests.

---

# The prompts

Paste each block as-is into a fresh Claude Code session at the repo root.

---

### Prompt 20 — Brief + outline (the scaffolding, with a config-gated approval)

```
Add a Composition layer that turns a single brief into a grounded multi-section document.
This prompt builds the SCAFFOLDING only (brief → proposed outline); Prompt 21 fills it.
Follow CLAUDE.md. Reuse the existing retriever/backend and the propose→review shape of
DevelopmentService — do not build a new generation engine.

Context: ask/develop already generate ONE grounded, cited passage. A document is the same
unit run once per section. The first content type is the shiur/class outline: ordered,
teachable points. Build the type as a config Literal and ship shiur_outline first.

Requirements:
- New module maayan/compose/. Pydantic models (maayan/compose/models.py):
    - Brief: id, title, intent, content_type (Literal["shiur_outline","essay","digest",
      "other"], default "shiur_outline"), lang (reuse corpus Lang/detect_lang), 
      target_sections: int | None = None, source_scope (optional book/source filters),
      seed_frameworks: list[str] = [], author (REQUIRED — blank rejected, as Prompt 9),
      thread_id: str | None = None.
    - Section: heading, query (the retrieval sub-question for this section), text="",
      cited_refs: list[str] = [], grounded_in: list[str] = [], supported: bool = False.
    - Composition: id, brief_id, thread_id, status (Literal["proposed","approved",
      "rejected"]), sections: list[Section], model, created_at.
- A CompositionService (all collaborators injected: backend, store, threads, clock,
  settings) with propose_outline(brief) -> Composition: the backend proposes an ordered
  list of section headings + a retrieval query per section, in the brief's register/lang,
  bounded by target_sections/compose_max_sections. The OUTLINE IS STRUCTURAL, NOT CITED —
  sections come back with heading+query and empty text. Persist the Composition
  (status="proposed"); if brief.thread_id, append a "composition" turn (extend the
  ThreadTurn turn_type literal additively + migration-safe).
- Config: compose_auto_outline (default false), compose_max_sections (default 8). When
  compose_auto_outline is true, downstream fill (Prompt 21) runs immediately; when false,
  the outline is returned for the expert to edit/approve first. Add a CompositionStore
  (SQLite, same DB; idempotent migration).
- CLI: `maayan compose --title ... --intent ... --type shiur_outline --author "..."`
  prints the proposed outline (numbered headings + each section's query). Author required.
- Tests (mock backend; no network/models): propose_outline returns N sections within the
  bound; headings/queries parse from the backend output; blank author rejected; the
  composition persists and round-trips; a thread brief appends a "composition" turn.

Show a proposed shiur outline (5–6 sections) for a sample brief when done.
```

---

### Prompt 21 — Per-section grounded fill (default-deny per section)

```
Fill each outline section with a grounded, cited passage — or an honest gap. Follow
CLAUDE.md. This is the heart of the phase: the default-deny gate runs PER SECTION, so the
document is grounded section-by-section and never padded where the corpus is silent.

Requirements:
- CompositionService.fill(composition_id) -> Composition: for each Section, in order:
    1. Retrieve fresh on Section.query via the injected retriever (config:
       compose_section_top_k; pass through Brief.source_scope filters).
    2. DEFAULT-DENY, enforced in code: if no results or relevance < score_threshold, mark
       the section supported=False with an honest gap text ("the sources here don't reach
       this") and make NO backend call for it.
    3. Otherwise generate the section with the backend, reusing build_context and
       extract_cited_refs from maayan/generate/rag.py VERBATIM; set supported=True,
       text, cited_refs (only retrieved sources), grounded_in. Brief.seed_frameworks are
       passed as ATTRIBUTED, non-citable context (like the develop SEED) — never cited.
- A compose system prompt (config-overridable, in maayan/compose/) tuned to the register:
  for shiur_outline, concise teachable points; cite every claim by [S#]; never invent
  mekoros; if the section's sources are thin, say so rather than force it.
- Aggregate composition.cited_refs / grounded_in from the filled sections. Persist the
  filled Composition (still status="proposed"). If compose_auto_outline was true, the
  caller fills right after propose_outline; otherwise fill runs on an approved outline.
- CLI: `maayan compose-fill <composition_id>` prints the filled document — each section's
  heading, text, its citations, and a clear marker on gap sections.
- Tests (mock retriever + backend): (a) a below-threshold section => gap, supported=False,
  NO backend call for it; (b) a supported section cites only retrieved refs and records
  grounded_in; (c) a mixed composition (some gaps, some grounded) aggregates correctly;
  (d) seed_frameworks appear as non-citable context, never in cited_refs.

Demo: fill the Prompt 20 shiur outline and show a document with most sections grounded+cited
and at least one honest gap where the corpus is silent.
```

---

### Prompt 22 — Assemble, review, export (+ UI + docs)

```
Assemble the filled sections into a finished document, make it reviewable, and export it.
Follow CLAUDE.md. Thin route handlers; logic stays in CompositionService.

Requirements:
- Assembly: render the Composition to a single markdown document — title, then each
  section (heading + text), gap sections clearly flagged as honest gaps, and a provenance
  FOOTER listing every cited ref, the grounded_in set, the brief's author, and the model.
  Optional connective transitions behind a config flag (compose_transitions, default
  false); when on, transitions are CONNECTIVE GLUE ONLY — the prompt forbids any new claim
  in a transition. Deterministic given the same Composition.
- Review: CompositionService.approve(id) / reject(id) set status. Approve does NOT bulk-
  index the prose (that would pollute retrieval). Instead, document + expose a
  "promote a connection" path: a section's grounded_in refs can be turned into an
  expert/derived connection through the EXISTING capture loop (Prompt 5/13) — one
  connection at a time, not a wall of prose. reject() changes nothing in the corpus.
- Export: `maayan compose-export <id> --out <file.md>` writes the assembled markdown.
  Also `maayan compositions` (list) and `maayan composition <id>` (show).
- UI: a "Compose" panel (maayan/ui) — a brief form (title / intent / type / author sticky,
  as Prompt 9); shows the proposed outline (editable + Approve when compose_auto_outline is
  false); a Fill button; renders the filled document with per-section citations and gap
  badges (distinct from sefaria/expert/derived/term badges); Approve / Reject / Export
  buttons. New thin FastAPI routes wiring CompositionService (+ ThreadService when a
  composition lives in a thread). No logic in handlers.
- Docs: README §8 add a Phase 5 section (Prompts 20–22). docs/RUNBOOK.md add a
  §"Compose a shiur outline" walkthrough (brief → outline → fill → export). docs/TEACHING.md
  add a short note: a composition is a grounded draft with honest gaps, and the way it feeds
  the corpus is by promoting its connections, never by re-ingesting its prose.
- Tests: assembly is deterministic and includes the provenance footer + gap honesty;
  export writes the markdown; approve/reject transitions; promote-connection reuses the
  capture loop; UI routes happy-path + the gap/reject paths (mocked services, no network).

Demo (browser): write a brief for a shiur outline, edit the proposed outline, fill it, see
grounded sections with citations and an honest gap, approve, export the markdown, and
promote one of its cross-text connections back into the corpus.
```

---

## 4. Suggested order & checkpoints

20 → 21 → 22, in sequence (each depends on the previous).

- **After 20:** a brief produces an editable, config-gated outline — the scaffolding and
  the human-in-the-loop control are in place.
- **After 21:** the document fills section-by-section, grounded and cited, refusing per
  section. This is the heart — run it on a real three-book index and confirm at least one
  honest gap appears rather than fabrication.
- **After 22:** compositions are reviewable, exportable markdown, and their connections feed
  the corpus through the existing loop. Update README/RUNBOOK/TEACHING and tick the phase.

## 5. What is deliberately NOT in this phase

- **Re-ingesting composition prose as corpus** — excluded by design; only surfaced
  connections flow back, through the existing expert/derived loop.
- **Essay / digest as bespoke pipelines** — they're registers of the same engine; ship
  `shiur_outline` first and add the others as `content_type` values, not new modules.
- **Multi-pass "editing"/revision agents** — keep one outline→fill→assemble pass. Revision
  is the expert editing the outline or promoting/retracting connections, not an autonomous
  rewrite loop.
- **Templated formatting / export to PDF/docx** — markdown export is enough; richer formats
  are a downstream concern, not a grounding concern.
