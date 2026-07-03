# UI Execution & E2E Plan — Phase 7: *Surfacing the Living Apparatus*

> **The third UI document, and the operational one.**
> [BUILD_PLAN_PHASE7.md](BUILD_PLAN_PHASE7.md) says *what* to build.
> [UI_SPEC_PHASE7.md](UI_SPEC_PHASE7.md) says how the panels should *feel* (the daf idiom).
> This document is the bridge to a **running, testable** UI: a complete audit of every
> capability the backend has against whether a scholar can reach it in the browser, the
> ordered work to close the gaps, and a **step-by-step end-to-end test protocol** the Rav
> can follow with nothing but a browser.
>
> The governing question, asked from the scholar's chair, not the shell:
> **"Everything maayan can do — can I get to it here, and is it honest about what it is?"**

Status date: **2026-07-03.** Branch: `prompt39-chavrusa-agent`.
Backend green: 437 tests, mypy strict clean, ruff clean.

---

## 0. Method

The audit cross-references three enumerations of the *actual* code (not the plan):

- **Every CLI command** — `maayan …` (43 commands across the root app + `graph`,
  `inquiries`, `user` sub-apps).
- **Every HTTP route** — the 60+ endpoints registered in `maayan/ui/app.py`.
- **Every UI affordance** — the `fetch()` calls, `onclick` handlers, and `window.*`
  exports in `maayan/ui/static/index.html`.

A capability is **surfaced** only if a scholar, using the browser, can trigger it without
touching a terminal. "There is a route for it" is *not* surfaced — the button has to
exist and be wired.

---

## 1. The surface audit

### 1.1 Surfaced and reachable — the scholar's working set

| Capability | How the scholar reaches it | Backend |
|---|---|---|
| **Ask** (grounded, cited answer; refusal gate) | Composer → **Ask** | `/ask`, `/threads/{id}/ask` |
| **Chavrusa study loop** (multi-hop) ✨ | Composer → **חברותא ●** toggle, then Ask | `/ask {agent:true}` → `agent.study` |
| **Study trace** (the stepper: how it studied) ✨ | **כיצד נלמד? ▸** on a chavrusa answer; `#trace=<id>` | `/api/traces/{id}` |
| **Topic threads** (context-carrying) | Left drawer list · tab **Threads** | `/threads`, `/threads/{id}` |
| **Seed knowledge** | Composer → **Seed ▾** | `/threads/{id}/seed` |
| **Develop a seed** → approve/reject | **Develop this →** in a thread; Approve/Reject | `/threads/{id}/develop`, `/developments/{id}/…` |
| **Teach a connection** (annotate) | Tick ≥2 sources → **Connect selected →** | `/annotate` |
| **Define a term / Holy Name** | Composer → **Term ▾**; Lexicon list in drawer | `/terms` |
| **Compose a grounded document** | Composer → **Compose ▾** (fill / approve / reject / promote / export) | `/compose`, `/compositions/…` |
| **Retract a layered chunk** | **Retract ✕** on an expert/derived/term/shiur source | `/retract` |
| **Margins / apparatus** (the daf) | **גליון ▸** on a source card and in the reader | `/api/apparatus` |
| **Via-line** (graph-expansion provenance) | Auto on expanded sources (`↳ via …`) | in `/ask` results |
| **Inquiry queue — שאלות לרב** | Left drawer panel + **↻ generate** · answer · dismiss · harvest line | `/api/inquiries…` |
| **Knowledge-base stats** | Left drawer **Knowledge base** panel | `/stats` |
| **Library + source-in-context reader** | Tab **Library**; ref click-through | `/api/library`, `/api/source` |
| **Shiur transcription** | Composer → **Shiur ▾** (upload → transcribe → review → approve) | `/api/audio…`, `/api/transcripts…` |
| **Play a cited shiur from its moment** | **▶ mm:ss** on a shiur source | `/api/audio/{id}/file` |
| **OCR a page → review field** | **📷** on Seed / Term inputs | `/api/ocr` |
| **Quick-capture inbox** | Header **📥** | `/api/inbox`, `/api/inbox/{id}/move` |
| **Auth: login / logout / user admin** | `/login`; user management (when `AUTH_ENABLED`) | `/api/login`, `/api/users…` |

✨ = closed in this branch (Prompt 39 wiring; see §2.1).

### 1.2 Not surfaced — **should be** (work items)

| Capability | Today | Decision |
|---|---|---|
| **Retraction ledger** (the audit trail: who retracted what, when, why) ✨ | *(now surfaced)* the stats-panel count is a click-through to a read-only ledger overlay | **Done** (§2.2). It is a trust-core surface — the scholar can now *see* what left the corpus and why. |

### 1.3 Not surfaced — **intentionally CLI** (operator / pipeline, documented)

These are correctly *absent* from the scholar's browser. Each is either a long-running
build job, a lab instrument, or a batch drafting run that a browser is the wrong host
for. The principle (from UI_SPEC §0): *dashboards, pipelines, and eval artifacts live in
the CLI; the UI is a study surface, not an admin console.*

| CLI command(s) | Why it stays in the CLI |
|---|---|
| `ingest`, `ingest-chabad`, `index`, `populate`, `bench` | Corpus build + bootstrap: long, resource-heavy, run once by the operator. A browser button that blocks for minutes is a footgun. |
| `eval`, `eval-expand` | The benchmark harness. Emits date-stamped JSON/markdown artifacts for trend analysis — a lab instrument, not a study surface. |
| `graph backfill · ingest-links · pasuk-join · stats · add · approve · retract · list · show` | Graph **management**. The graph is surfaced to the scholar **read-only** through **margins** (approved edges) and **via-lines**. Proposed-edge *review* is designed to route through the **inquiry panel** (UI_SPEC §4.5), not a separate graph console. Bulk link ingestion is a paced network job. |
| `lexicon-suggest · -review · -approve · -reject` | Batch term drafting from the corpus (populate-style, model-in-the-loop, paced). The scholar's **gate** on missing terms is surfaced via `undergrounded_term` inquiry cards → the add-term flow. |
| `connectors-suggest · -review · -approve · -reject` | Same pattern for connections. |
| `search` | Raw retrieval with no generation. The **Ask** flow shows the same retrieved sources with an answer on top — it supersedes `search` for the scholar; `search` remains a debugging lens. |
| `session`, `annotate`, `apparatus`, `transcribe`, `inquiries …` (CLI forms) | Each has a first-class UI surface (above). The CLI forms exist for scripting/automation. |
| `user create-admin`, `version` | One-time bootstrap / trivia. |

### 1.4 Not surfaced — **not yet built** (future prompts, will surface then)

| Feature | Prompt | Planned surface (UI_SPEC) |
|---|---|---|
| Study-program sweep → proposed edges at scale | 40 | `proposed_relation` cards in the inquiry panel |
| Sugya pages + chazarah due-markers | 41 | Reader page view + 🕯 markers in margins/inquiries |
| Parent context + gated summaries | 42 | `⌄ summary` chip + **ירד לאותיות ▸** descend affordance |

---

## 2. The ordered work list

Process top-to-bottom. Each item names its **done-when**.

### 2.1 ✅ Wire the chavrusa agent into the UI *(done, verified)*

The keystone gap: the agent had a service, a store, `/api/traces/{id}`, and a trace
viewer — but nothing in the Ask flow could invoke it or hand back a trace id. Closed:

- `AskRequest.agent: bool`, `AskResponse.trace_id: str | None` (`maayan/ui/models.py`).
- `/ask` branches to `agent.study()` when `agent:true`; **the refusal gate is unchanged**
  (a refused seed reaches no model and yields no trace); `503` if the agent is unwired,
  never a fabricated answer (`maayan/ui/app.py`).
- `AgentService` injected in `create_app` and built in `cli.ui()`.
- UI: a **חברותא ○/●** toggle in the composer routes Ask to the study loop (outside
  threads, mirroring `ask --agent`); the answer grows a **כיצד נלמד? ▸** link opening
  the existing trace stepper.

**Done-when:** ✅ typecheck + lint clean; agent/UI test suites green; smoke test confirms
`agent:true → study() called, trace_id returned`, `agent:false → plain ask`,
`unconfigured → 503`.

### 2.2 ✅ Surface the retraction ledger *(done, verified)*

The stats-panel retractions count is now a click-through (`openRetractions()`) to a
read-only overlay listing each retraction (ref, source, author, reason) from
`GET /retractions`. Each ref opens in the reader; the empty state is a statement, not an
error ("שום דבר לא נמחק — the corpus is whole"). No new write path; read-only.

**Done-when:** ✅ full suite green (437); ruff + mypy clean; the inline UI JS parses clean
(`node --check`).

### 2.3 ⬜ From-the-scholar's-chair review pass

Open every surface in a browser and check, per UI_SPEC's five rules: every assertion
answers *who says?* and *show me* in one glance/tap; no dead onclick; RTL correct;
disabled/empty states degrade to a line inside the panel, never a broken screen. Fix
what the pass turns up. **Done-when:** the §3 protocol runs clean, top to bottom.

### 2.4 ⬜ Then: the remaining plan prompts (40 → 41 → 42)

Only after the UI is coherent and testable. Each ships its UI surface per UI_SPEC §9.

---

## 3. End-to-end test protocol (browser only)

A scripted walkthrough that exercises **every surfaced capability** in §1.1–1.2. Follow
it in order; each step names what you do and **what you should see**. Where a step needs
data or a flag, the prerequisite is called out.

### 3.0 Prerequisites (one-time)

```bash
make up                                   # local Qdrant
uv sync --extra ml --extra ui             # models + web deps
make ingest                               # pull + chunk the corpus
make index                                # embed + upsert
maayan graph backfill                     # lift expert connections → typed edges
maayan graph ingest-links --book "Tanya, Part I; Likkutei Amarim" --limit 20
maayan graph pasuk-join                   # deterministic cross-work edges
```

Flags for a *full* exercise (in `.env`) — the UI degrades gracefully without them, but
these light up the graph-dependent surfaces:

```
GRAPH_EXPAND_ENABLED=true     # via-lines on answers
ASK_LOG_ENABLED=true          # refused-question inquiries (default true)
# AGENT_ENABLED gates the CLI/default; the חברותא toggle works regardless (agent is always wired in ui()).
```

Launch: `make ui` → open the printed URL.

### 3.1 Ask — the trust core

1. Ask a question the corpus supports (e.g. **מהי נפש הבהמית**). → A grounded answer with
   inline `[S#]` citations; a source list below; cited sources marked **✦**.
2. Ask something clearly outside the corpus (e.g. *"מתכון לחלה"*). → A **refusal**, no
   fabricated sources. *This is the default-deny gate; it must never answer from memory.*

### 3.2 Chavrusa — the study loop *(§2.1)*

3. Toggle **חברותא ○ → ●** (a toast confirms). Ask **מהי עבודת הבירורים?**
   → A grounded answer; the answer header reads **latest answer · חברותא**; a
   **כיצד נלמד? ▸** link appears.
4. Click **כיצד נלמד? ▸**. → The trace stepper overlay: numbered steps
   (🔍 חיפש / 📖 פתח / 🕸 הלך בגרף / 📚 בדק מונח / ✔ סיכם), each with its digest, and a
   budget footer (`hops · chunks · calls`). A force-conclude, if any, shows
   **⏸ הגיע לגבול** honestly.
5. Toggle **חברותא ● → ○** off. Confirm plain Ask returns (no trace link).

### 3.3 Margins — the daf *(Prompt 36)*

6. On any source card, click **גליון ▸**. → The apparatus sheet: פסוקים / קשרים / מונחים /
   שכבת הרב groups. Each edge shows its evidence badge + author; each item is a
   click-through. An unannotated ref shows the **empty state**, not an error.

### 3.4 Via-line — provenance as a thread *(Prompt 35; needs `GRAPH_EXPAND_ENABLED`)*

7. Ask a question whose answer pulls an expert-connected passage. → At least one source
   grows a **↳ via `<rel_type>` <badge> (author) from <seed ref>** line. Seed hits have
   none — the absence is the design.

### 3.5 Teach — the capture loop (the point of the system)

8. Tick **two** sources → write an insight → **Connect selected →**. → "Connected ✓ —
   saved to the Knowledge base." Re-ask a related question later; the connection surfaces.
9. **Seed ▾** → plant a seed (author required + sticky) → in the thread, **Develop this
   →** → **Approve**. → The development becomes retrievable, cited on future asks.
10. **Term ▾** → define a term (canonical + surface forms + definition + author) → it
    appears in the **Lexicon** drawer list and is matched in margins.
11. On an expert/derived/term/shiur source, **Retract ✕** (author + reason). → "Retracted
    ✓"; the stats retractions count increments.

### 3.6 Retraction ledger *(§2.2 — after that item ships)*

12. Click the retractions count in the **Knowledge base** panel. → A read-only ledger
    lists each retraction with ref, author, and reason (including the one from step 11).

### 3.7 Inquiry queue — שאלות לרב *(Prompt 37)*

13. Click **↻** on the שאלות לרב panel to generate. → Prioritized cards, each a question
    to the Rav with its **priority math printed**; a harvest line at the foot.
14. **ענה ✓** on a card → it deep-links into the resolving flow; answering records a
    resolution and collapses the card. **דחה ✗** dismisses (first-class).

### 3.8 Compose — grounded documents

15. **Compose ▾** → a brief → **fill**. → Each section is grounded with citations or
    shows an **honest gap**. Approve / reject sections; **promote** a section's
    connection; **export**.

### 3.9 Library, shiur, OCR, inbox

16. Tab **Library** → open a book → read a source in context (RTL, nikkud preserved).
17. **Shiur ▾** → upload audio → transcribe → review segments → approve. → Approved
    segments become retrievable; a cited shiur source plays from its moment (**▶**).
18. **📷** on a capture field → photograph a page → text lands in the field for review
    (never auto-ingested).
19. Header **📥** → quick-capture a note → move it into a flow.

### 3.10 Auth *(only if `AUTH_ENABLED=true`)*

20. Log in; confirm panels are gated and the author chip is the logged-in user (sticky).
    Admin: create / disable / enable a user; change a password.

**Pass = every step's "should see" holds, no console errors, RTL correct throughout.**

---

## 4. What is deliberately *not* in the UI (the honest ledger)

So the exclusions are a decision on record, not an oversight:

- **No pipeline/build buttons** (`ingest`, `index`, `populate`, `bench`) — operator CLI;
  a browser is the wrong host for a multi-minute job.
- **No eval/benchmark surface** (`eval`, `eval-expand`) — a lab instrument; its output is
  trendable artifacts, per UI_SPEC §0 ("no dashboards").
- **No graph console** — the graph is *read* through margins + via-lines; it is *managed*
  and *reviewed* through the CLI and (for gating) the inquiry panel. No node-canvas
  visualization (UI_SPEC §0: the daf renders its citation network as margins, not a map).
- **No batch-drafting surfaces** (`lexicon-suggest`, `connectors-suggest`) — the scholar
  gates through the inquiry queue, one prioritized door; the drafting runs are operator
  jobs.
- **No raw `search`** — the Ask flow supersedes it.

Future prompts (40–42) will add their surfaces (§1.4) when built; until then their
absence is *not-yet*, not *won't*.

---

*The test of this UI is the test of the phase: sit in the scholar's chair, open the
browser, and reach — with no terminal — everything maayan knows how to do, each surface
honest about who said it and how it is known. This document is green when §3 runs clean
top to bottom.*
