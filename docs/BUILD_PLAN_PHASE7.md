# Build Plan — Phase 7: The Living Apparatus

> **From a grounded index to a beis medrash with memory.** Status as of 2026-07-02:
> Phases 1–6 built and green; query intelligence + reasoning (Prompt 31), answer eval
> (Prompt 32), the free-model bootstrap populate, and the benchmark harness are all in.
> This phase is the answer to an honest dissatisfaction: **the mission is a harness in
> which good models continuously turn expert learning into real knowledge — and what
> we have, for all its breadth, is a trustworthy lookup system with capture surfaces.**
> Phase 7 is depth, not breadth: structure, agency, and expert leverage.

---

## 0. The honest assessment (why this phase exists)

What is genuinely strong — and must not be weakened by anything below:

- **The trust core.** Grounded-only answers, inline citations, default-deny enforced in
  code, an immutable printed layer, provenance and retraction on everything human. This
  is rarer than it sounds and it is the foundation everything below builds on.
- **The gates.** Nothing model-drafted reaches the index unreviewed. The bootstrap
  populate proved the gates hold even under a weak free model (16/46 terms approved,
  zero ungrounded indexed).
- **The engineering discipline.** DI, typed boundaries, config-driven, mocked tests.
  Swapping models is one config line. This is what makes a *harness* possible at all.

Where the current system falls short of the mission — three structural gaps:

1. **Knowledge is flat.** A connection is a prose chunk with an untyped `linked_refs`
   list. A term is a chunk. Nothing relates to anything except through embedding
   similarity. Expert knowledge accumulates as a *pile*, not a *structure* — so it
   cannot compose, cannot be walked, cannot be checked for contradiction, and cannot
   answer the question a beis medrash answers constantly: *who else speaks about this,
   and how?*

2. **The harness caps the model.** Every smart verb is a fixed shallow pipeline
   (retrieve once → synthesize once). A frontier model dropped into today's harness can
   write nicer prose — it cannot *study*: follow a mareh makom, open the next chapter,
   check a term, revise its search. The whole point of "a harness for future good
   models" is that model improvements convert into knowledge improvements **with no
   code changes**. Today the conversion ratio is fixed and low.

3. **Expert attention is spent, not invested.** The scholar's hour is the scarcest
   resource in the system, and the system does nothing to aim it. Review is a flat
   queue of binary gates. Refused questions — the system's own confessions of
   ignorance — are thrown away. An approved correction improves retrieval once but
   never becomes a regression test. The system never *asks* the one question whose
   answer would unlock the most.

Phase 7 closes these three gaps, in that order of leverage.

---

## 1. What best-in-class looks like — lessons taken from other fields

The user asked for the deepest patterns from elsewhere. These are the ones that
transfer, and what each one buys us:

| Field / system | The pattern | What maayan takes from it |
|---|---|---|
| **The daf itself** (Mesoras HaShas, Ein Mishpat) | Every passage carries its margins: who cites it, where it's codified, what argues | The **Apparatus view** — per-ref margins, machine-assembled, human-gated (Prompt 36) |
| **Legal citators** (Shepard's, KeyCite) | Citations are *typed*: followed / distinguished / overruled — the type is the value | **Typed relations**, not prose links: quotes / explains / is-mashal-for / argues-with / develops (Prompt 33) |
| **Sefaria's link graph** | Millions of curated intertextual links already exist as data | **Ingest curated edges, don't re-derive them with a model** (Prompt 34) |
| **Tanach as primary key** | Chassidus quotes pesukim constantly; two ma'amarim on the same pasuk are joined *deterministically* | **Pasuk-anchored edges at $0**, no model in the loop (Prompt 34) |
| **Genome curation** (UniProt, GO evidence codes) | Automated annotation at scale + curator review; every assertion tagged with *how it is known* | **Evidence codes** on every layered assertion: expert / curated / deterministic / derived-approved / bootstrap (Prompt 33) |
| **Zettelkasten** | Atomic notes compound through dense links, not folders | Expert chunks are already atomic; the graph gives them backlinks so they compound |
| **Mathlib / Lean** | The corpus grows because every submission is *machine-checked*; the checker, not the prover, is the asset | **Verifiers are the harness.** Strong checking (citation verify, faithfulness, graph consistency) is what lets us safely accept more from stronger models |
| **Wikipedia** | Talk-page churn consolidates into a curated article; versioned, attributed | **Sugya pages** — consolidation of many contributions into one reviewed, versioned topic page (Prompt 41) |
| **Community Notes** | Surface for review exactly where raters *disagree* | **Contradiction-driven inquiry** — conflicts in the graph become questions for the Rav (Prompt 37) |
| **Anki / spaced repetition** | Memory that schedules its own review | **Chazarah scheduling** — aging, low-evidence knowledge resurfaces for re-review (Prompt 41) |
| **SWE-agent / ACI research** | Agent output quality is a function of *action-space design*, not prompt cleverness | The **chavrusa agent**: a small, safe, typed tool space + hard budgets; capability lives in tools + verifiers (Prompt 39) |
| **Every serious codebase** | Every bug fix ships with a test | **The eval flywheel** — every approved correction auto-drafts an eval case (Prompt 38) |

### The design credo

> **Typed knowledge + strong verifiers + bounded agency + a human gate
> = a harness in which a better model converts directly into more approved knowledge.**

Put capability in the *data structures, the action space, and the checkers* — never in
prompt cleverness. Then "swap the drafter" (already one config line) is the entire
upgrade path, and the trust core never moves.

### North-star metrics (how we know the harness is good)

| Metric | Definition | Instrument |
|---|---|---|
| **Model elasticity** | Δ approved-knowledge yield when only the model improves (free → top), same code | Rerun populate/study programs after a drafter swap; we already hold the free-tier baseline (16/46 terms, 12/24 connections) |
| **Expert leverage** | Approved knowledge items per expert-hour | Gate telemetry (timestamps already exist on every approval) |
| **Compounding rate** | % of newly approved items grounded partly on *prior* expert/derived/sugya chunks | Provenance scan at approval time (the bootstrap run already produced one such case — אהבה בתענוגים) |
| **Benchmark win-rate** | The existing [BENCHMARK_PLAN](BENCHMARK_PLAN.md) numbers, now with graph and agent conditions | Rungs below, §5 |

---

## 2. What we deliberately stop doing

Depth requires saying no. For the duration of Phase 7:

- **No new UI surfaces.** The PWA, reader, OCR, inbox, compose are done enough;
  maintenance only. New UI in this phase is limited to panels that expose Phase 7 data
  (apparatus, inquiry queue, traces).
- **Deployment stays parked** (per the standing decision). Local-first until the
  intelligence justifies hosting.
- **No multi-user / social features.** One scholar, deeply served, is the proof.
- **No fine-tuning, ever, in this phase.** The moat is the gated corpus + the harness,
  not weights.

---

## 3. Architecture additions

New modules follow every house rule (typed pydantic boundaries, DI, config-driven,
`Clock` for all waiting, mocked tests, gates on every write path):

```
maayan/
  graph/       Concept + typed Relation models, GraphStore (SQLite), backfill,
               Sefaria-links + pasuk-anchor ingestion, graph expansion for retrieval.
  inquiry/     AskLog (question/refusal telemetry) + InquiryItem queue + generators
               + ranking. "The talmid asks."
  agent/       StudyAction / StudyStep / StudyTrace + the bounded chavrusa loop
               + StudyProgram sweeps.
  consolidate/ SugyaPage models + clustering + versioned gate + chazarah scheduler.
```

Extended: `eval/` (captured goldset, graph/agent conditions), `retrieve/` (graph
expansion behind the existing `Retrieving` protocol), `ui/` (thin panels only).

Every new tunable lands in `config.py`; every new write path has an approval gate and
integrates with `retract/`; every model-facing feature works identically under the
`FakeBackend`/fake stores in tests.

---

## 4. The prompts

> Continue the sequence: Prompts 33–42. Run one at a time; `make test`,
> `make typecheck`, `make lint` green before the next. **Every prompt follows
> [CLAUDE.md](../CLAUDE.md).** Standing invariants re-checked at every checkpoint:
> default-deny is never bypassed or weakened; printed text stays immutable; author is
> required + sticky on every human contribution; nothing model-drafted is indexed
> without an approval gate; auth-aware routes when `AUTH_ENABLED=true`; no
> `time.sleep` — the injected `Clock` drives all pacing.

---

### Prompt 33 — The graph spine: concepts + typed relations (`maayan/graph/`)

```
Build the knowledge-graph spine: typed, provenanced, gated relations between refs and
concepts. Follow CLAUDE.md. This is the structural upgrade the whole phase stands on —
model it carefully, keep it small.

Context: today a connection is a prose chunk with an untyped linked_refs list
(maayan/capture/models.py). That knowledge cannot compose, be walked, or be checked.
Legal citators (Shepard's/KeyCite) prove the pattern: the TYPE of a citation edge is
most of its value. Genome curation (UniProt) proves the other half: every assertion
carries an EVIDENCE CODE for how it is known.

Requirements:
- New module maayan/graph/. Pydantic models (graph/models.py):
    - Concept: id, canonical (str), aliases (list[str]), kind
      (Literal["sefirah","partzuf","olam","name","avodah","concept"]), term_id
      (str | None — link into the existing lexicon), author, created_at.
    - Endpoint: a tagged union — either a ref (canonical Sefaria/chabad ref string) or
      a concept_id. Model it explicitly (discriminated pydantic union), not a bare str.
    - Relation: id, subject (Endpoint), object (Endpoint), rel_type
      (Literal["quotes","quotes_pasuk","explains","is_mashal_for","corresponds_to",
      "argues_with","develops","parallels","defines","connects"]), evidence
      (Literal["expert","curated","deterministic","derived_approved","derived_bootstrap"]),
      confidence (float 0–1), status (Literal["proposed","approved","retracted"]),
      author, source_chunk_id (str | None — the prose chunk this edge was lifted from),
      note (str | None), created_at.
- GraphStore (SQLite, same DB, idempotent migration): CRUD + dedupe — a second insert of
  (subject, object, rel_type) updates evidence/confidence rather than duplicating.
  Queries: relations_for(endpoint), neighbors(endpoint, types?, status="approved"),
  counts by type/evidence/status.
- Gates, exactly like every other layer: relations are created "proposed";
  approve(relation_id, author) is the only path to "approved"; retraction goes through
  the EXISTING retract service semantics (audited: who/when/why) — extend it, do not
  fork it. Only "approved" relations are ever used by retrieval or views.
- Backfill: `maayan graph backfill` lifts every existing expert connection chunk into
  relations — each pair of linked_refs becomes one "connects" relation, evidence
  "expert" (or "derived_bootstrap" when the author starts with "bootstrap:"),
  source_chunk_id set, author preserved, status "approved" (they already passed a
  human/faithfulness gate). Idempotent — rerun changes nothing. The prose chunks stay;
  the edge is an additional, structured view of the same knowledge.
- CLI: `maayan graph add|approve|list|show --ref <ref>` and `maayan graph backfill`.
  Construction at the edge (cli.py) as always.
- Config: no magic numbers — any thresholds/defaults land in config.py.
- Tests: store CRUD + dedupe; the discriminated Endpoint union round-trips; backfill
  maps a known connection chunk correctly and is idempotent; only approved relations
  come back from neighbors(); retraction is audited.

Show: `maayan graph backfill` then `maayan graph show --ref "Tanya, Part I; Likkutei
Amarim 18"` listing the typed, attributed edges that today are buried in prose.
```

---

### Prompt 34 — Deterministic edges at $0: Sefaria links + pasuk anchors

```
Bootstrap the graph with thousands of CURATED and DETERMINISTIC edges — no model calls,
no spend. Follow CLAUDE.md. Two sources: Sefaria's own link data, and the pasuk as a
natural join key.

Context: Sefaria maintains a curated intertextual link graph (its /api/links/{ref}
endpoint returns links for a ref — commentary, citation, midrash). Our corpus books are
on Sefaria, so their links to Tanach/Zohar/etc. already exist as human-curated data.
Ingesting them beats re-deriving them with any model. Second: chassidic texts quote
pesukim constantly — two passages anchored to the same pasuk are related by
construction. VERIFY the current API response shape against the live endpoint for one
ref before coding the parser; then mock everything in tests.

Requirements:
- maayan/graph/links.py: a SefariaLinksClient (httpx, injected, rate-limited via the
  injected Clock — mirror the existing Sefaria ingester's pacing pattern). For each
  sefaria chunk ref in the corpus, fetch links; keep links whose category/type indicate
  citation/quotation (document the kept categories in config: sefaria_link_categories).
- Edge mapping: our-ref → linked-ref becomes a Relation: rel_type "quotes_pasuk" when
  the target is a Tanach ref, else "quotes"; evidence "curated"; confidence 1.0; status
  "approved" (curated human data passes the gate by policy — record author "sefaria:links").
  Targets outside the corpus are still stored (the endpoint is a ref string — it need
  not resolve to a local chunk); they become anchors.
- Pasuk join: after ingestion, any two corpus refs sharing a quotes_pasuk target gain a
  "parallels" relation, evidence "deterministic", author "system:pasuk-join",
  status "approved", note carrying the shared pasuk. Dedupe via the store. This is the
  cross-WORK linking the bootstrap populate could not reach (Tanya ↔ Torah Ohr through
  a shared pasuk) — at zero model cost.
- Resumable + idempotent: a cursor table like the populate drip; re-run skips fetched
  refs; `--limit` for sampling.
- CLI: `maayan graph ingest-links [--book ...] [--limit N]` and the join runs at the
  end (or `maayan graph pasuk-join` separately).
- Config: enable flag, rate, categories. NO network in tests — fixture payloads
  captured from one real response.
- Tests: parser handles the fixture payload + an empty/malformed payload; mapping rules
  (Tanach → quotes_pasuk); the pasuk join produces the expected parallels edge from two
  fixtures sharing a target; idempotency.

Show: after `maayan graph ingest-links --book "Tanya, Part I; Likkutei Amarim"
--limit 5`, `maayan graph show --ref` lists curated quotes_pasuk edges, and one
pasuk-join parallels edge connects two corpus passages across works.
```

---

### Prompt 35 — Graph-aware retrieval (the index learns to walk)

```
Let retrieval follow approved edges — hybrid search finds the entry points, the graph
widens the grounding. Follow CLAUDEmd. The trust core does NOT move: default-deny is
decided on the seed retrieval alone; the graph can enrich a supported answer, never
rescue a refusal.

Context: GraphRAG systems show the pattern — vector search for recall, graph expansion
for structure. Our version is small and honest: one hop along approved relations from
the top seed hits.

Requirements:
- A GraphExpandingRetriever implementing the existing Retrieving protocol (mirror how
  MultiQueryRetriever slots into retrieve/factory.py — nothing downstream changes):
  1. Run the inner retriever (whatever the factory built: plain or multi-query).
  2. Apply the default-deny decision EXACTLY as today, using only these seed scores.
  3. If (and only if) the gate passes: for the top GRAPH_EXPAND_SEEDS hits, fetch
     approved relations via GraphStore.neighbors(); resolve neighbor refs to chunks
     (existing store); also expand from Concepts the lexicon detects in the query.
  4. Budget: at most GRAPH_EXPAND_LIMIT added chunks; expanded hits carry a via
     field (the Relation that brought them: type + author) in the retrieval result
     model; rerank the merged set if RERANK_ENABLED, else append after seeds.
- Config: GRAPH_EXPAND_ENABLED (default false), GRAPH_EXPAND_SEEDS, GRAPH_EXPAND_LIMIT,
  optional per-rel_type weights later — do not build weights speculatively.
- Provenance in answers: an expanded source cited in an answer shows its route in the
  UI/CLI source line — e.g. "↳ via connects (R. Ginsburgh) from Tanya 18". The scholar
  must always see WHY a source appeared.
- Eval: extend the crosstext harness with a --graph toggle reporting
  book-diversity/coverage with expansion off vs on; add the third ablation condition to
  the benchmark wiring (A-graph: text + synthetic + graph) so BENCHMARK_PLAN rung 2 can
  run A-text vs A-synth vs A-graph.
- Tests (in-memory qdrant + fake embedder + seeded GraphStore): a query whose seed hits
  one endpoint retrieves the far side of an approved edge; a below-threshold query
  refuses WITHOUT touching the graph (assert no store call — inject a spy); budget
  respected; via provenance present; only approved relations expand.

Show: a question about a Tanya concept whose answer now also cites the Torah Ohr
passage an expert connected — with the "via" line showing whose teaching routed it.
```

---

### Prompt 36 — The margins: an apparatus for every source

```
Give every source its margins — the daf pattern (Mesoras HaShas): standing on any
passage, see everything the system knows AROUND it. Follow CLAUDE.md. Read-only
composition of existing data; no new write paths.

Requirements:
- An ApparatusService (injected stores; no logic in routes): for a canonical ref,
  assemble a typed Apparatus model:
    - relations: approved edges touching this ref, grouped by rel_type, each with
      author + evidence + the far endpoint (resolved to a snippet when it's a corpus
      chunk, else the bare ref — e.g. a pasuk anchor);
    - terms: lexicon terms whose surface forms appear in this chunk's text (reuse the
      lexicon's existing matching — no new matcher);
    - expert layer: expert/derived/term/shiur/sugya chunks whose linked_refs or
      metadata reference this ref;
    - developments: developments grounded on this ref (existing store query).
- Thin routes: GET /api/apparatus?ref=... (auth-aware). CLI: `maayan apparatus <ref>`.
- UI (panel only, per §2): a "margins ▸" affordance on source cards and in the
  source-in-context reader opening the apparatus panel; every item click-through
  (open the source, the term, the connection). RTL-correct.
- Tests (fake stores): a ref with seeded edges/terms/expert chunks assembles the full
  apparatus; an unknown ref returns an empty apparatus (not an error); grouping by
  rel_type; auth behavior.

Show: open Tanya ch. 18 in the reader → margins list its pasuk anchors, the expert
connection to Likutei Torah, the terms defined in it, and the shiur segment that
discusses it. One screen = what the beis medrash knows about this daf.
```

---

### Prompt 37 — The talmid asks: the inquiry queue (active learning)

```
Invert the beis medrash: the system generates targeted questions for the scholar, so
the expert hour lands where it unlocks the most. Follow CLAUDE.md. This is the
highest-leverage feature in the phase — the scarce resource is the Rav's attention.

Context: today refused questions evaporate, the populate deny-list (30 known-missing
core terms) sits in a report, and low-evidence bootstrap edges are indistinguishable
from expert ones at review time. Community Notes teaches the pattern: route human
attention to exactly where the signal conflicts or is missing.

Requirements:
- First, telemetry (the raw material): an AskLog (maayan/inquiry/log.py, SQLite) —
  every ask records question, refused (bool), top score, session/thread id, timestamp.
  Config: ASK_LOG_ENABLED (default true). No new PII (user field mirrors existing auth).
- InquiryItem model: id, kind (Literal["refused_question","undergrounded_term",
  "low_evidence_relation","contradiction","re_review"]), title, detail, payload
  (typed per-kind pydantic models, discriminated union — NOT a loose dict), priority
  (float), status (Literal["open","answered","dismissed"]), created_at, answered_at,
  resolution (str | None).
- Generators (each independent, each tested):
  a. refused_question: cluster AskLog refusals (near-duplicate by normalized text is
     enough for v1) → one item per cluster with the count as priority signal.
  b. undergrounded_term: lexicon populate deny-list entries that look like real terms
     (the existing populate store has them) — "the corpus may support כתר; the free
     drafter failed. Confirm or dismiss."
  c. low_evidence_relation: approved relations with evidence "derived_bootstrap" or
     confidence below INQUIRY_CONFIDENCE_THRESHOLD.
  d. contradiction (v1, honest + simple): two approved relations sharing both endpoints
     with rel_types {argues_with} vs {explains|develops|parallels} — surface, don't judge.
- Ranking: priority = config-weighted blend (weights in config.py, documented); ties
  by recency. Keep it transparent — print the components.
- Answering closes loops: each item deep-links into the EXISTING flow that resolves it
  (annotate / add-term / approve / retract). Marking answered records what was created
  (chunk/term/relation id) in resolution. Dismissed is a first-class outcome.
- CLI: `maayan inquiries [--kind ...]`, `maayan inquiries generate`. UI: a
  "שאלות לרב" panel listing open items by priority with one-tap deep links.
- Tests (fake stores/clock): each generator from seeded data; ranking math; dedupe
  (regenerating doesn't duplicate open items); answer/dismiss transitions; the
  refused-question path from an AskLog row to an open item.

Show: after a day of use, `maayan inquiries` lists: "3 learners asked about ביטול —
the corpus refused every time", "כתר was deniable by the free drafter — confirm?",
"bootstrap edge Miketz↔Mishpatim has no expert review". The Rav answers one; it
becomes an expert chunk AND the item closes with its resolution recorded.
```

---

### Prompt 38 — The eval flywheel: every approval becomes a test

```
Make the eval set grow by itself: every gated approval auto-drafts a regression
example. Follow CLAUDE.md. The software rule "every bug fix ships with a test" applied
to knowledge: every correction ships with an eval case.

Context: the benchmark gold set (BENCHMARK_PLAN §4) is the expert's hand-written exam —
it stays. This is the other half: a machine-grown regression suite so improvements are
provable and regressions visible, without waiting on anyone.

Requirements:
- CapturedExample model: id, question, expected_refs (list[str]), gold_answer (str —
  the approved body), stratum "captured", origin (typed: kind + source id), created_at.
  A CapturedGoldsetStore (SQLite).
- Deterministic drafting on approval (NO model calls — templates only, v1):
    - approved connection → question from its linked refs/topic ("מה הקשר בין X ל-Y?"),
      expected_refs = the linked refs, gold_answer = the connection body;
    - approved development → question = the seed's directive (it already reads as an
      instruction), expected_refs = the development's grounded refs;
    - approved term → "מהו {canonical}?", expected_refs = the definition's grounding;
    - answered inquiry → its question + what the resolution created.
  Hook into the existing approval paths via a small injected recorder — do not scatter
  logic through services.
- `maayan eval --captured`: run the EXISTING retrieval harness over the captured set;
  JSON report out (date-stamped) so runs are trendable; print deltas vs the previous
  report when one exists.
- Dedupe + hygiene: identical questions update rather than duplicate; retracting the
  origin retracts the example (subscribe to the retract flow).
- Config: CAPTURED_GOLDSET_ENABLED (default true).
- Tests: each approval kind drafts the expected example; retraction removes it;
  eval --captured runs over in-memory qdrant with seeded examples; trend delta math.

Show: approve one connection, then `maayan eval --captured` — the suite is one example
larger and the connection's retrievability is now a permanent regression check.
```

---

### Prompt 39 — The chavrusa agent: a bounded multi-hop study loop

```
Give the model the ability to STUDY — retrieve, read, follow a mareh makom, look up a
term, search again — inside hard guardrails. Follow CLAUDE.md. This is the harness
centerpiece: the action space and verifiers are fixed and safe; a better model simply
studies better. Course 2 (5.3) named this exactly: multi-hop needs a richer contract —
build that contract, not a framework.

Requirements:
- New module maayan/agent/. Typed protocol (models.py):
    - StudyAction: discriminated union — Search(query), OpenSection(ref),
      WalkGraph(ref), LookupTerm(term), Conclude(). No other verbs.
    - StudyStep: the action + a compact typed result digest (hits with scores, section
      text refs, edges, term) + tokens/calls spent.
    - StudyTrace: id, question, steps (list[StudyStep]), final RAGAnswer, budgets
      (hops used/max, chunks gathered/max, model calls used/max), created_at.
- The loop (agent/service.py, all collaborators injected):
  1. Seed retrieval + the default-deny gate EXACTLY as today — a refusal never reaches
     the model. (Reuse the existing gate; do not reimplement it.)
  2. Up to AGENT_MAX_HOPS: present the working set + a compact action menu to the
     GenerationBackend; the model replies with ONE action as constrained JSON. Parse +
     validate against the union; one malformed reply gets one repair retry, then the
     loop force-concludes with what it has. No tool-calling API dependency — plain
     completion + strict parsing keeps every backend (OpenRouter/Ollama) eligible.
  3. Execute the action via EXISTING services (retriever, chunk store, GraphStore,
     lexicon). Search results below threshold add nothing (the gate's semantics apply
     to increments too). Every gathered chunk joins the working set up to
     AGENT_MAX_CHUNKS.
  4. Conclude: run the EXISTING analyze→synthesize path over the final working set,
     then the EXISTING citation-verify pass. The answer format, citations, and refusal
     honesty are unchanged from `ask --reason`.
- Budgets in config: AGENT_ENABLED (default false), AGENT_MAX_HOPS (default 4),
  AGENT_MAX_CHUNKS, AGENT_MAX_CALLS. Exceeding any budget force-concludes.
- Persistence + surfaces: StudyTraces stored (SQLite); `maayan ask --agent
  [--show-trace]`; a thin GET /api/traces/{id}; UI renders the trace as study steps
  ("searched… → opened Tanya 19 → followed the connection to Torah Ohr Vayera…").
  The trace is itself teaching material — a record of how the sugya was worked.
- Tests (scripted fake backend, in-memory qdrant, seeded graph): a deterministic
  3-hop path (search → walk_graph → conclude) produces an answer citing a chunk only
  reachable via the walk; every budget cap force-concludes; a refused seed never calls
  the backend (spy); malformed action → one retry → force-conclude; trace persisted
  with correct step accounting.

Show: `maayan ask --agent --show-trace "מהי עבודת הבירורים?"` — watch it search, open
a chapter, follow an expert edge, and synthesize — then the same command after swapping
the model in .env, to see the SAME harness study better. That delta is the product.
```

---

### Prompt 40 — Study programs: the sweep

```
Run the chavrusa over a whole sefer, unit by unit, drafting apparatus for the gates —
the machine that converts model-hours into proposed knowledge at corpus scale. Follow
CLAUDE.md. Reuse the populate drip's pacing/resumability pattern (maayan/populate/) —
do not build a second job engine.

Requirements:
- StudyProgram model: id, book, task (Literal["relations","terms","mashal"]), cursor
  (unit index), status (Literal["running","paused","done","error"]), counts (drafted /
  passed_checks / queued), started_at, updated_at. A ProgramStore (SQLite).
- Per unit (a chapter/section from the existing corpus store, in canonical order):
  a bounded agent task — "given this unit + co-retrieved corpus context, propose typed
  relations (subject=this unit) / term usages / mashal-nimshal candidates, each with
  the exact grounding refs". Every proposal runs the EXISTING faithfulness check, then
  lands as status="proposed" relations or inquiry items. NOTHING is auto-approved —
  the gate stays human.
- Pacing: the drip pattern — paced via the injected Clock (free-tier 429s absorbed by
  the existing backoff), resumable from cursor after crash, `--units N` for sampling.
- Report artifact: `maayan study report <program_id>` emits a POPULATE_REPORT-style
  markdown (per-unit drafted/passed/queued, evidence histogram, spend) — the document
  the funding brief's production run is judged by.
- CLI: `maayan study run --book "Tanya, Part I; Likkutei Amarim" --task relations
  [--units N]`, `maayan study status`, `maayan study report <id>`.
- Config: drafter model override for programs (mirror LEXICON_DRAFT_MODEL), pace,
  budgets per unit.
- Tests (fake backend + fake clock): a 3-unit program drafts proposals that appear as
  "proposed" relations; resumability (kill after unit 1, rerun continues at 2);
  faithfulness-failed proposals are counted but not queued; no gate bypass (assert
  nothing lands "approved"); report math.

Show: `maayan study run --task relations --units 3` on Tanya → `maayan graph list
--status proposed` shows typed, cited candidate edges awaiting the Rav — and
`maayan study report` gives the honest drafted/passed/queued funnel.
```

---

### Prompt 41 — Chazarah: consolidation + memory hygiene

```
Knowledge that compounds needs review of itself: consolidate many contributions into
curated sugya pages, and schedule re-review of aging, low-evidence knowledge. Follow
CLAUDE.md. Wikipedia's talk-page→article loop + Anki's scheduling, behind our gates.

Requirements:
- Sugya pages (maayan/consolidate/):
    - Clustering (deterministic, no model): group approved expert/derived chunks +
      relations by shared Concept/term + graph adjacency (connected components over
      approved edges, min size from config).
    - Drafting: for one cluster, run the grounded unit per section (reuse the compose
      pattern: sources → connections → open questions), every line cited from the
      cluster's chunks; honest gaps allowed. Output: a SugyaPage model (concept, title,
      sections, cited refs, version int, status proposed|approved|superseded, author).
    - Gate + versioning: approve indexes it as source="sugya" chunk(s) retrievable like
      everything else; approving version N+1 supersedes N — N's chunks retract through
      the EXISTING retract flow (audited), the page history is kept.
- Chazarah scheduler: a pass (CLI `maayan chazarah`, Clock-driven, no daemon) that
  queues inquiry re_review items for: evidence="derived_bootstrap" items older than
  CHAZARAH_BOOTSTRAP_DAYS, approved items never retrieved in any logged ask (join
  AskLog↔citations), and confidence below threshold. Spaced-repetition-style: each
  re-review confirmation multiplies the item's next-review interval (factor in config).
- CLI: `maayan sugya draft --concept <id>`, `sugya approve|reject <id>`, `sugya list`,
  `maayan chazarah`. UI: sugya pages render in the reader (they're chunks + a page view).
- Tests (fakes throughout): clustering determinism on a seeded graph; drafted page
  cites only cluster refs; version supersede retracts exactly the old chunks (audited);
  scheduler intervals with FakeClock; never-retrieved detection.

Show: draft the ביטול sugya from its cluster, approve it, then ask about ביטול — the
answer cites the sugya page alongside the sources it was distilled from. Run
`maayan chazarah` and see a year-old bootstrap edge come up for its re-review.
```

---

### Prompt 42 — Structural depth: parent context + gated summaries

```
Respect the shape of a ma'amar: passages are citation units, but understanding needs
the flow around them. Follow CLAUDE.md. Two additions, both behind gates, neither
touching printed text.

Requirements:
- Parent-context answering: at generation time, each retrieved hit may carry a window
  of its neighboring passages from the same section (existing section_path ordering) up
  to PARENT_CONTEXT_CHARS (default 0 = off). The window goes into the model's context
  BUT citation stays the exact retrieved passage — assert this invariant in tests (the
  cited ref must be the hit, never a neighbor). Wire through the existing RAG prompt
  builder; no retrieval changes.
- Gated section summaries (RAPTOR-lite, exactly one level): `maayan summarize --book X
  [--units N]` drafts a grounded summary per chapter/section (drip-paced, faithfulness-
  checked, proposed→approved gate like develop), indexed as source="summary" chunks
  whose metadata carries the parent ref + child ref list. Retrievable like everything
  else — a conceptual query can land on a chapter summary and the apparatus/margins
  lead down into the passages. Summary chunks are retractable; printed text untouched.
- Config: PARENT_CONTEXT_CHARS, SUMMARY_* (model override, pace), summary_boost
  (default 1.0) parallel to the existing boosts.
- Eval: rerun `maayan eval` + `eval --captured` with summaries on/off; record the
  numbers in the phase report.
- Tests: window construction honors section order + char budget; citation integrity
  invariant; summary drafting gates + indexes with parent metadata; boost applied in
  the same place as the existing boosts (no special-cased retrieval logic).

Show: a conceptual question that previously scattered across passages now retrieves a
chapter summary whose margins open into the exact osiyos — and the citations still
point at real printed text.
```

---

## 5. Sequencing + benchmark integration

Two tracks can interleave after Prompt 33; nothing else crosses.

| Order | Prompts | Track | Why this order |
|---|---|---|---|
| 1 | **33 → 34 → 35** | Structure | The graph spine, then thousands of free curated/deterministic edges, then retrieval that uses them. **Benchmark checkpoint:** run BENCHMARK_PLAN rungs 0–2 with the new **A-graph** condition — the first hard number on what structure buys. |
| 2 | **37 → 38** | Expert leverage | Can start right after 33. The inquiry queue starts banking the Rav's attention immediately; the flywheel makes every approval a test. |
| 3 | **36** | Structure | The margins view — after 34 there is enough graph data to make it sing. |
| 4 | **39 → 40** | Agency | The chavrusa agent, then the sweep. **Benchmark checkpoint:** add an **A-agent** condition; measure elasticity by swapping the drafter free→top on a 3-unit sweep. |
| 5 | **41 → 42** | Compounding | Consolidation and structural depth pay off most once the graph + programs have generated volume. |

Per the house Definition of Done at every step: `make test` (all backends/stores
faked), `make typecheck`, `make lint`, tunables in `config.py`. Standing invariants
re-checked at every checkpoint (§4 header).

---

## 6. Execution protocol — which model does what

The rule this phase runs on: **spend the top model where the verifier is weak and the
blast radius is high; spend lesser models where the verifier is strong and the spec is
already written.** Prompts 33–42 carry their own verifiers (requirements + tests + the
DoD gate), so execution is delegated. Judgment is not.

| Lane | Model | The work |
|---|---|---|
| **Execution** | Sonnet (Haiku for mechanical chores: backfills, fixtures, doc regeneration) | Run each prompt verbatim, one per session, one per branch. |
| **Judgment** | Fable / top model | Plan authoring + repair, the Prompt 33 vocabulary review, PR review of trust-core surfaces, reading the benchmark checkpoints, everything in §7. |
| **Runtime** | OpenRouter config (drafter/judge model settings) | The models *inside* maayan (populate, study programs, grading) — a config switch and a separate budget; never conflate with dev-session spend. |

Cadence, per prompt:

1. **Fresh session on the execution model**, branch `promptNN-<slug>`, the prompt
   pasted verbatim from this document. The prompt plus CLAUDE.md is the whole
   contract; a fresh session per prompt prevents drift.
2. **DoD before handoff**: `make test`, `make typecheck`, `make lint` green. A Stop
   hook in `.claude/settings.json` runs lint + typecheck automatically whenever
   Python files changed, so a session cannot end on a red branch silently.
3. **Top-model review before merge** — `/code-review` at high effort; `ultra` for
   Prompts 35 and 39, which touch the trust core directly.
4. **The reviewer's checklist, every PR** (these are the failures a lesser model most
   plausibly introduces, and no test fully catches):
   - default-deny is not bypassed or weakened — a refusal never reaches a model;
   - no write path skips its gate or drops author/provenance;
   - printed text stays immutable; retraction is integrated and audited, not forked;
   - new tunables in `config.py`; nothing hardcoded; no secrets in code or logs;
   - tests mock network/models; all waiting runs on the injected `Clock`.
5. **When execution stalls, fix the prompt, not the code.** Bring the failure to a
   top-model session, amend the prompt here, rerun. The plan stays the source of
   truth and the fix is reusable.
6. **The one exception in the execution lane**: Prompt 33's `RelationType` and
   `Concept.kind` vocabularies are schema — the expensive kind of mistake. The
   top-model ontology session (§7, ask 1) reviews them before that PR merges.

---

## 7. After the harness: the top-model program

What to hand a frontier model (Opus-class or better) once Prompts 33–42 are green —
tasks where top-model judgment is the actual input, in order:

1. **Design review of the ontology, with the Rav.** Before the sweep, one session:
   the relation-type vocabulary and Concept kinds of Prompt 33, reviewed by a top model
   *together with the scholar* against real examples from the corpus. This is the schema
   the next decade of knowledge lands in — schema mistakes are the expensive ones, and
   this is judgment work, not typing work.

2. **The Great Sweep.** Run the study programs (Prompt 40) over the full corpus —
   Tanya, Torah Ohr, Likutei Torah — with the top drafter: typed relations, term
   usages, mashal tags, contradiction candidates, all through the faithfulness checks
   into the gates, with the inquiry queue rationing the Rav's review to the
   highest-value items. Deliverable: the first machine-drafted, human-gated mareh-mekomos
   apparatus for chassidus — and the measured **elasticity number** (free-model funnel
   vs top-model funnel, same code) that headlines the funding story.

3. **Bikores: the adversarial audit.** A *different* frontier model (uncorrelated
   errors) red-teams every approved item: hunt misattributions, flattened machlokes,
   meshalim assigned to the wrong nimshal, over-claimed connections. Output: retraction
   proposals with evidence, routed through the inquiry queue. A knowledge base you have
   paid a strong adversary to attack is a different class of asset from one you have
   merely built.

4. **The synthesis exam.** The benchmark's ultimate form: (a) run the full
   BENCHMARK_PLAN head-to-head with the agent + graph conditions against the frontier
   closed-book arm, on the Rav's gold questions; (b) ask the top model, inside the
   harness, to produce a genuinely new sugya page on a topic the Rav names — and have
   the Rav grade it as he would a talmid's chazarah. Then write the paper: methods,
   the elasticity curve, the win-rates, the qualitative appendix (a hallucinated mekor
   vs. a grounded citation), limitations. That paper is the raise.

5. **The harness critique (ACI review).** Finally, the recursive step: have the top
   model work inside the harness for a sustained session and then report — as an
   engineer — where the action space bound it: the tool it reached for that didn't
   exist, the budget that cut a real line of inquiry, the verifier that rejected a
   correct move. That report is the Phase 8 plan. A harness for future models must be
   iterated *with* future models; this is how the loop closes on the harness itself.

---

*The mission, restated as engineering: the printed texts are common property; the
scholar's reasoning is scarce; and the harness's job is to make one hour of that
reasoning permanent, structured, checkable, and compounding — under gates strong
enough that we can safely accept more and more of the work from better and better
models. Phase 7 is that harness.*
