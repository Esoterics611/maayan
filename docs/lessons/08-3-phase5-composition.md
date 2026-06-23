# Lesson 8.3 — Phase 5: composition

> Module 8, Lesson 3 · ~20 min, hands-on at the terminal.
> The one question this answers: **how does maayan go from answering one question to producing a
> whole grounded document — a shiur outline, an essay — without the second half drifting into
> fabrication?**

Every generation you've seen produces **one** grounded passage: `ask` answers a question,
`develop` develops a seed. Both are the *same unit*: retrieve once → default-deny gate → one cited
block. Phase 5 ([BUILD_PLAN_PHASE5.md](../BUILD_PLAN_PHASE5.md)) asks: can we produce a structured
*document* — and the crucial insight is that the answer is **not a new generation engine.** It's an
orchestration layer that runs the unit you already trust, **once per section.**

---

## Why a document can't be one `ask`

A chat answer retrieves **once**, for **one** question. Try to write an essay that way and its
later sections drift far from what that single retrieval found — the model starts improvising,
exactly the failure RAG exists to prevent. The Phase 5 plan states it: "an essay's later half would
drift ungrounded."

So a composition **decomposes** the brief into an outline where **each section is its own
retrieval sub-question**, then **fills** each section using the existing grounded unit — each
section *independently* retrieved, gated, and cited. A long piece becomes many small grounded
answers, stitched in order, instead of one over-stretched retrieval.

---

## The spine: Brief → Composition → Sections

Open [maayan/compose/models.py](../../maayan/compose/models.py):

- **`Brief`** — the spec: a `title`, an `intent` ("what the piece should teach"), a
  `content_type` (`shiur_outline` / `essay` / `digest` — same engine, different *register*, so
  it's a config Literal, not new modules), optional `source_scope` (book/source filters), and a
  required `author`.
- **`Composition`** — the document: an ordered list of `Section`s, with a `status`
  (`proposed`/`approved`/`rejected`) — like a development, it's a *proposal* a human reviews.
- **`Section`** — a `heading` + the **retrieval sub-question** (`query`) that grounds it. The
  *outline* step fills `heading` + `query` (empty `text`); the *fill* step sets
  `text` / `cited_refs` / `grounded_in` / `supported`.

Two steps, two commands: `maayan compose` proposes the outline; `maayan compose-fill` grounds each
section. It's the develop→approve rhythm (Module 6) at document scale.

---

## The differentiator: default-deny *per section*

Here is what makes a *maayan* document generator different from any LLM that writes essays. Read
[BUILD_PLAN_PHASE5.md](../BUILD_PLAN_PHASE5.md) §0:

> When the corpus doesn't support a section, the gate at
> [rag.py:137](../../maayan/generate/rag.py) fires and the section becomes an **honest gap**
> ("the sources here don't reach this"), never fabricated prose.

That's the default-deny gate from Lesson 3.3 — *the exact same line of code* — now firing
**per section**. A `Section` carries `supported: bool`; when its sub-question doesn't clear the
threshold, `supported=False` and the section is marked an honest gap rather than filled with
invention. So a 12-section outline might come back with 9 grounded sections and 3 honest gaps —
and that's a *feature*. The plan puts it perfectly: "A piece with honest holes beats a confident
invention — for Torah that is the whole point."

> ### Under the hood — composition inherits every guarantee for free
> Because composition *reuses the unit* rather than reimplementing it, it inherits everything you
> learned: each section's fill is grounded and cited (Module 3), refuses per-section (3.3), draws
> on expert/derived chunks alongside text (Module 6), and respects source scope (Module 2.4). The
> orchestration layer adds *structure*; it adds no new way to fabricate. This is the same lesson as
> the thin UI (7.5): keep the trusted unit in one place, and build larger things by *calling* it,
> not by cloning it. A composition is a proposal with full provenance (author, brief, per-section
> grounded refs and gaps) — reviewable, like everything else.

---

## Hands-on

Qdrant up, full corpus indexed (more text → fewer gaps), OpenRouter key set.

**1. Propose an outline.** Give it a title and intent:

```bash
uv run maayan compose \
  --title "שלושת הלבושים של הנפש" \
  --intent "שיעור על מחשבה דיבור ומעשה ככלים של הנפש האלוקית" \
  --author "Your Name" \
  --type shiur_outline
```

Read the output: a numbered outline where **each section shows its retrieval sub-question**
(`↳ retrieval: …`). That per-section query is the seed of per-section grounding. Note the
`Composition <id>` and the `compose-fill` hint.

**2. Fill it — and hunt for the honest gaps.**

```bash
uv run maayan compose-fill <COMPOSITION_ID>
```

Each section is now grounded and cited *or* marked an honest gap. **Find a gap** (a section the
corpus couldn't support) — that's default-deny firing per section, refusing to fabricate that
piece. Contrast a grounded section (with `cited_refs`) against a gap. In a sentence: why is a
flagged gap more valuable, for Torah, than smooth invented prose?

**3. See it's the same gate.** Open [BUILD_PLAN_PHASE5.md](../BUILD_PLAN_PHASE5.md) §0 and find
the reference to `rag.py:137`. Confirm: the per-section refusal is the *same* default-deny line you
made open and close in Lesson 3.3. Composition didn't invent a new trust rule — it reused the one
you already proved.

---

## You should now be able to say…

- Why long-form **can't be one `ask`** (later sections drift), and that composition **decomposes**
  a brief into per-section retrieval sub-questions, then fills each with the existing grounded
  unit.
- The spine **Brief → Composition → Sections**, the outline/fill two-step, and that it's a
  reviewable proposal like a development.
- The differentiator: **default-deny per section** — unsupported sections become honest gaps
  (`supported=False`), never fabricated — reusing the *same* gate from Module 3.

Next: **[8.4 — When (and when not) to fine-tune](08-4-fine-tuning.md)** — the last lesson: why RAG
+ citations stays the backbone, and why fine-tuning is a later, register-not-correctness move.
