# maayan — UI review & redesign requirements: the teaching loop, made visible

> **Status:** requirements + phased plan. Phase 1 is implemented on the
> `ui-teaching-loop-redesign` branch; Phases 2–3 are specified here for later work.
>
> **Scope:** the web/PWA UI (`maayan/ui/`) around the **teaching loop** (ask → teach →
> gate → retrieve) and **golden questions & answers** (the eval flywheel). Retrieval,
> generation, and the gates themselves are out of scope — this is about how a scholar
> *experiences* them.

---

## 1. Who the user is, and what the UI must do for them

The primary user is a **talmid chochom / Rav** — deeply expert in the material, *not* a
software person. He will never run `uv run maayan eval`. He teaches in Hebrew, thinks in
mekoros, and his time is the scarcest resource in the system. Secondary users are
students/family members with accounts, asking questions and capturing thoughts.

The product's core claim (CLAUDE.md: "the capture loop is the point") translates into
three UI jobs:

1. **Make teaching effortless** — every correction/connection should take seconds, in
   Hebrew, by voice if wanted, with zero re-typing of identity or context.
2. **Make judgment central** — everything the machine proposes (developments, drafted
   relations, transcripts, sugya pages, summaries) waits for *his* click. The UI must
   collect those judgments in one place, not scatter them.
3. **Make learning visible** — after he teaches, the UI must *show* that the system
   learned: the new chunk surfacing in retrieval, the gold set growing, the weak-spot
   queue shrinking. Today this feedback is nearly absent; that is the single biggest
   gap this redesign closes.

---

## 2. Review of the current UI (findings, severity-ranked)

Method: walked every flow in `index.html` (1,449 lines) + `app.py` (908 lines) against
the documented loop (TEACHING_WALKTHROUGH.md) from the scholar's perspective.

### P0 — The loop's feedback half is invisible

- **The flywheel is silent.** Every gated approval (Connect, approved Develop, Term,
  answered inquiry) already drafts a regression example (`maayan/eval/captured.py` is
  wired into all UI factories) — but the UI never says so. The scholar's teaching builds
  a gold set he cannot see, cannot count, and cannot watch improve. The one loop-closing
  moment — "your correction is now a permanent test" — never appears on screen.
- **"Did it learn?" requires manual re-asking.** The walkthrough's every step ends with
  "✓ confirm it learned" — done by hand, re-asking the question and eyeballing badges.
  There is no verify affordance, though a retrieval-only check is cheap and the expert
  chunk's ref is known at save time.
- **Golden questions have no surface at all.** `eval/*.yaml`, captured examples,
  date-stamped reports, deltas — all terminal-only. The person whose teaching the
  numbers measure can't see the numbers.

### P0 — Review (the gates) is scattered across six surfaces

- Proposed **developments**: approve/reject buttons appear only inside the owning
  thread's transcript — there is no cross-thread list of what awaits judgment.
- Proposed **relations** from study programs (Prompt 40 — the machine explicitly built
  to convert model-hours into *proposed* knowledge at corpus scale) have **no UI
  review surface whatsoever**; approval is CLI-only (`maayan graph approve`).
- **Sugya pages** (Prompt 41) and **summaries** (Prompt 42): proposed→approved gates,
  CLI-only.
- **Transcripts** live in the Shiur box, **inquiries** in the sidebar, **inbox** in a
  header overlay. Six places to check; no total count anywhere; nothing tells the
  scholar "you have 12 items waiting."

### P1 — Copy is either jargon or noise; guidance lives outside the app

- The header tagline — *"your Assistant for Tanya · Torah Or · Likutei Torah — grounded
  in the Knowledge base you build (ask · teach · connect · develop)"* — is a soup of
  words that explains nothing, and is hidden on mobile anyway.
- Button labels are developer vocabulary: **Seed ▾**, **Term ▾**, **Compose ▾** — the
  scholar has to already know the system to know what they mean. Tooltips carry the
  real meaning, invisible on touch devices.
- The click-by-click guidance exists — as a Markdown file in the repo
  (TEACHING_WALKTHROUGH.md). None of it is in the app. Empty states say "Pick or start
  a topic to begin." and stop; they teach nothing about the loop.
- After an answer arrives there is no cue for the *next* move (tick sources →
  connect); after a refusal there is no path from "the corpus can't answer" to "so
  teach it," even though refusals already feed the inquiry queue silently.

### P1 — The most sacred actions run through `window.prompt()`

- Recording **what resolved an inquiry** — the moment the loop closes — is a bare
  `prompt('מה נוצר מהתשובה? …')`.
- **Retracting knowledge** (the audited eraser) asks for author and reason in two
  chained `prompt()`s; **promote connection** in Compose is another `prompt()`.
  These are the highest-ceremony actions in the system rendered with the
  lowest-ceremony widget the browser has. No validation, no context shown, no undo.

### P1 — The answer is transient and lives in the wrong place

- The latest answer renders inside the **composer** area (`#answerSources`), not in
  the thread transcript. Switching threads or reloading discards it — along with the
  tick-to-connect checkboxes. The thread shows the Q/A text but the sources
  (the raw material for teaching) exist only in that ephemeral block.

### P2 — Form sprawl, identity noise, sidebar cramming

- Five toggle boxes stack beneath the composer; opening several at once yields a wall
  of forms. The mobile "Capture" tab just scrolls to the Seed box.
- An **Author** field appears in five places even when auth has already established
  identity (auto-filled + readonly, but still occupying a row of every form).
- The inquiry queue — conceptually a primary surface ("what to teach next") — is
  squeezed into the 260 px sidebar with monospace priority math; answered/dismissed
  affordances are 12 px ghost buttons.
- Minor: `alert()` for errors; no loading skeletons; no keyboard shortcuts for
  approve/reject; badge grammar (●◆⚙◐◌) documented in code comments but never
  explained to the user anywhere in the UI.

### What is already right (keep, don't regress)

- The **glyph/badge evidence grammar** (expert ● / curated ◆ / deterministic ⚙ /
  derived ◐ / bootstrap ◌) is consistent and honest — extend it, never fork it.
- **Priority math printed on inquiry cards** ("an opaque queue would spend his trust
  along with his time") — keep the honesty, improve the presentation.
- Hebrew-first naming of scholar-facing concepts (שאלות לרב, גליון, חברותא) is the
  right voice. The reader, margins-as-daf, highlight-to-act, voice-everywhere are
  genuinely good and stay as-is.
- The single-file, no-framework, no-CDN architecture (PWA + CSP-friendly) stays.

---

## 3. Patterns adopted from top-rated systems

| System | Pattern we adopt | Where |
|---|---|---|
| **Perplexity** | Numbered inline citations bound to a sources rail; refusal states that propose a next action | Answer card (Phase 2), refusal → teach path (Phase 1) |
| **Anki** | One daily review queue with counts; "N left today"; spaced re-review surfaced as due items | Review workbench; chazarah re_review inquiries land in the same queue |
| **Label Studio / Prodigy** | A unified annotation/review inbox: one item at a time, evidence inline, one-key accept/reject, session progress | Review workbench (הכרעות) |
| **Braintrust / LangSmith** | Golden datasets as a first-class screen: examples with provenance, run history, deltas vs previous run | Gold panel (שאלות זהב) |
| **Duolingo** | The day's progress rendered as encouragement, not telemetry | Harvest line ("היום נענו…") kept and promoted into the workbench header |
| **Notion AI / Docs suggesting mode** | Machine output is visually a *suggestion* until a human accepts | Already the system's semantics; the UI now gives suggestions one consistent card + badge + accept/reject anatomy |
| **ChatGPT/Claude apps** | First-run guidance inside the product; empty states that teach; microcopy that names the next action | Onboarding strip, empty states, next-step hints |

---

## 4. Copywriting requirements (the words are part of the interface)

**C1. Header.** Replace the tagline soup with a single quiet line naming what the user
can *do*, plus a persistent **? מדריך** (guide) button. Proposed copy:

> **מעיין · maayan** — שאל, לַמֵּד, והמעיין גדל · *ask · teach · it grows*

**C2. Every panel opens with one plain sentence** stating what it is and what will
happen — in the panel, not a tooltip. Bilingual where the concept is scholar-facing
(Hebrew leads), English for mechanics.

**C3. Buttons are verb-first and outcome-honest.** "Plant seed" → **"לַמֵּד → שמור
כזרע" / "Save seed"** with the sub-line "the model will develop it; nothing is indexed
until you approve." No naked "Seed ▾" / "Term ▾": each toggle gains a short
plain-language descriptor.

**C4. Every save confirms with consequences, not status codes.** After Connect:
*"נשמר ✓ החיבור נכנס למאגר — וגם נוסף כשאלת-זהב (מבחן קבוע). בדוק שהוא עולה →"*.
The confirmation always names (a) what entered the Knowledge base, (b) that a gold
example was captured, (c) the one-click verify.

**C5. Empty states teach.** Every empty list states what would fill it and offers the
first action. The empty thread state carries the four-step loop (see G1).

**C6. The evidence-glyph legend appears in the UI** (guide overlay + title attributes):
● expert · ◆ curated · ⚙ deterministic · ◐ derived-approved · ◌ bootstrap.

**C7. Refusals speak the loop.** A refusal is not a dead end; copy: *"אין למעיין מקורות
לשאלה זו — עדיין. השאלה נרשמה בשאלות לרב; אפשר ללמד אותה עכשיו:"* with direct
buttons into Seed (pre-filled with the question) and the guide.

## 5. Guidance requirements (instructions built into the UI)

**G1. The loop strip.** On an empty thread (and from the ? button any time), show the
four steps as a compact horizontal strip, each step one line + one example:
**1 שאל** (ask; nothing is saved) → **2 לַמֵּד** (connect ticked sources / seed / term /
shiur) → **3 הכרע** (approve or reject what the machine proposes) → **4 רְאֵה**
(watch it surface: badges, gold set, harvest). Dismissible; remembered in
localStorage; never blocks input.

**G2. The guide overlay (? מדריך).** An in-app, offline copy of the walkthrough's
Part A: the loop diagram, what each badge/glyph means, what each teach mode does, and
the golden-questions story in one screen. No external links required to learn the app.

**G3. Next-step hints are contextual and single.** Exactly one hint under the current
focus: after a grounded answer → "tick two sources and write the link between them";
after ticking one source → "one more"; after Connect → the C4 confirmation; after
planting a seed → "עכשיו: פתח → הכרע" pointing at Develop. Hints are plain text (the
`hint` style), never modal, never toast-spam.

**G4. Counts drive attention.** The header shows a single ⚖️ badge with the total
awaiting judgment (developments + relations + transcripts + open inquiries + inbox).
One number, one place to go.

---

## 6. Redesign requirements

### R1 — Information architecture: four destinations

```
┌ header: מעיין · maayan   [⚖️ הכרעות (12)] [🏅 זהב] [📥] [?] [user ▾] ┐
│ sidebar: topics · lexicon · knowledge-base health                    │
│ center:  the active thread (ask + teach)                            │
└ mobile tabs: לימוד Study · הכרעות Review · זהב Gold · ספרייה Library ┘
```

- **Study** (existing center) — ask, read, teach in a thread.
- **הכרעות / Review** — the unified gates workbench (R3).
- **זהב / Gold** — the golden-questions panel (R4).
- **Library** — existing reader/browser, unchanged.
- The inquiry queue moves out of the sidebar into the Review workbench; the sidebar
  keeps a one-line pointer with the open count.

### R2 — The teach surface (composer) is one coherent unit

- One **לַמֵּד Teach** control with four labeled modes — **חיבור Connect · זרע Seed ·
  מונח Term · שיעור Shiur** — replacing the row of five toggles (Compose moves under a
  secondary "עוד more" since it produces documents, not knowledge). Only one mode's
  form is open at a time; each form opens with its C2 sentence.
- Author rows disappear whenever identity is known (auth on); a signed-in line in the
  form footer ("נשמר בשם: הרב …") replaces them. With auth off, one author field per
  form remains (it is provenance, non-negotiable).
- All `prompt()`/`alert()` flows become proper in-app modals with context, validation,
  and a cancel that does nothing (R6: retract, inquiry resolution, promote).

### R3 — The Review workbench (הכרעות): one queue for every gate

- **One overlay/screen listing everything with status `proposed`/`open`, grouped by
  kind**, newest first, each rendered with the same card anatomy:
  *what it is (badge + glyph) · the proposed text/edge · its evidence (cited refs,
  confidence, via) · who/what proposed it · [✓ approve] [✗ reject] [→ open in context]*.
- Phase 1 kinds: **developments** (proposed, across all threads), **graph relations**
  (proposed — first-ever UI for study-program output), **inquiries** (open; answer/
  dismiss with the modal from R6), **inbox** (move-to-thread). Phase 2 adds transcripts,
  sugya pages, summaries as their list APIs are wired.
- Header shows counts per kind + the day's **harvest** line (moved from sidebar).
- Keyboard: `j/k` move, `a` approve, `x` reject, `Enter` open. (Phase 2.)
- Approving a relation requires/uses the signed-in author (the graph gate is
  attributed); with auth off it asks once and remembers, as elsewhere.

### R4 — The Gold panel (שאלות זהב): golden questions become a place

- Shows the **captured gold set** (the flywheel): total, split by origin
  (connection/development/term/inquiry), the newest examples with their question +
  expected refs + origin badge, and retracted ones greyed (hygiene visible).
- Shows the **latest captured-eval report** (date, hit@k / recall / MRR + the delta
  line vs the previous run) read from `captured_reports/` — *display only* in
  Phase 1; a "run now" button is Phase 3 (long-running job UX).
- Names the **curated YAML sets** (goldset / crosstext / develop) and says honestly
  that gold is edited in files, not clicked (per-set counts: Phase 2).
- Copy anchors the concept: *"כל אישור שלך הופך למבחן קבוע — זו הדרך לדעת שהלימוד
  באמת עוזר."*

### R5 — Learning feedback: teach → see it learned

- Every gated save (Connect, Approve development, Term, answered inquiry) confirms
  with the C4 pattern **including the captured-gold line** and a **בדוק ✓ verify**
  affordance.
- **Verify** runs retrieval-only (no model call, no gate bypass) for the question and
  reports whether the just-created chunk surfaces: *"עלה במקום 2 מתוך 8 ✓"* or an
  honest *"עדיין לא עולה בחיפוש הזה"*. Endpoint: `GET /api/verify` (below).
- Refusals render the C7 teach-path block instead of a bare refusal line.

### R6 — Modals replace prompt()/alert()

One small modal helper (same overlay pattern as the reader) serving: inquiry
resolution (with the inquiry text visible + what-was-created field), retract (target
ref shown, reason field, author auto), promote-connection (section shown, insight
field). Errors render inline in the modal, never `alert()`.

### R7 — Answer persistence (Phase 2)

Sources render as part of the thread turn (persisted server-side on the ask turn), so
switching threads/reloading keeps the teachable material; the composer block becomes a
view of the latest turn rather than a separate transient area. Inline `[S#]` citation
markers in the answer text link to their source cards, Perplexity-style.

### R8 — Mobile parity

The four destinations map to the tab bar (Study/Review/Gold/Library). The Review
workbench and Gold panel are full-screen sheets on narrow viewports. Touch targets
≥ 40 px for approve/reject. Everything else inherits the existing responsive behavior.

### R9 — Visual system

Keep the parchment palette and quiet typography. New components reuse existing
classes (`.src`, `.badge`, `.margin-*`, overlay/reader chrome). The one new color
token: a gold accent (`--gold`) for the Gold panel + captured-example badge, used
nowhere else so it stays meaningful. Count badges use the accent, not red — this is
study, not an alarm.

---

## 7. API additions (thin routes over existing services — house rules apply)

| Route | Backing | Notes |
|---|---|---|
| `GET /api/review/queue` | `DevelopmentService.list_developments(status="proposed")` (new thin method over the store) + `GraphStore.list_relations(status="proposed")` + `InquiryStore.list(status="open")` + `InboxService.list_open()` | One response model, per-kind lists + counts; kinds whose service isn't injected return empty (inert, like every optional wire) |
| `POST /api/relations/{id}/approve` | `GraphStore.approve(id, author=…)` | author from auth user, else body |
| `POST /api/relations/{id}/reject` | `GraphStore.mark_retracted(id)` | mirrors `maayan graph retract` |
| `GET /api/goldset` | `CapturedGoldsetStore.list_examples()` + `load_previous_report(dir)` | read-only; store injected via `create_app(captured=…)` |
| `GET /api/verify?question=&ref=` | injected `Retrieving.retrieve()` | retrieval-only; returns found/rank/top refs; never calls the model |

All new payloads are pydantic models in `ui/models.py`; all new services are optional
`create_app` params defaulting to `None` (routes 503 when absent) — identical to the
existing pattern. Every route ships with tests (mocked services), mypy-strict, ruff.

## 8. Phasing

- **Phase 1 (this branch):** copy + guidance overhaul (C1–C7, G1–G4) · Review
  workbench with developments/relations/inquiries/inbox (R3) · Gold panel read-only
  (R4) · verify + teach feedback (R5) · modals (R6) · header IA (R1) · API rows above.
- **Phase 2:** teach-control consolidation to a single mode switcher (R2 full) ·
  answer persistence + inline `[S#]` citations (R7) · transcripts/sugya/summaries into
  the queue · keyboard shortcuts · mobile tab remap (R8).
- **Phase 3:** run-eval-from-UI with background job + trend sparkline over report
  history · per-example drill-down (which gold examples regressed).

## 9. Acceptance criteria (Phase 1)

1. A signed-in scholar can, without leaving the browser or reading any doc: see how
   many items await judgment, open one list, and approve/reject a proposed development
   *and* a proposed graph relation.
2. After making a Connect, the confirmation names the gold capture and one click shows
   whether the connection surfaces in retrieval for that question.
3. The Gold panel shows the captured set's size, origins, newest examples, and the
   latest eval report's scores if any exist.
4. A refused answer offers a teach path (pre-filled seed) in one click.
5. No `window.prompt`/`alert` remains in the teaching loop.
6. The four-step loop strip renders on an empty thread; the guide opens from the
   header; both are dismissible/reopenable.
7. `make test`, `make typecheck`, `make lint` all pass; new routes have tests with
   mocked services.
