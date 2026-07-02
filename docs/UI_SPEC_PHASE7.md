# UI Spec — Phase 7 Companion: *Rendering the Living Apparatus*

> Companion to [BUILD_PLAN_PHASE7.md](BUILD_PLAN_PHASE7.md). That plan is deliberately
> austere about UI (§2: *"No new UI surfaces… New UI in this phase is limited to panels
> that expose Phase 7 data"*). This spec takes that constraint seriously — and then asks
> the harder question: **what should those panels feel like, so that the structure,
> agency, and expert leverage Phase 7 builds are *legible* to the one scholar the whole
> system serves?**
>
> The answer this spec commits to: **the UI's design language is the daf.** Chassidus
> already solved this interface problem five hundred years ago — a central text
> surrounded by margins that carry everything known *about* it, each marginal note
> typed, attributed, and pointing somewhere. Phase 7's data model (typed relations,
> evidence codes, provenance, gates) is a daf apparatus in software. The UI should look
> like what it is.

---

## 0. Scope and non-scope

**In scope** (each maps to a Phase 7 prompt; nothing here invents a write path or a
surface the plan didn't authorize):

| Panel / component | Prompt | Where it lives |
|---|---|---|
| The **Margins panel** (apparatus) | 36 | Reader + source cards (existing surfaces) |
| The **via-line** (expansion provenance) | 35 | Answer source lists (existing surface) |
| **שאלות לרב** — the Inquiry panel | 37 | New panel, PWA nav |
| The **Study Trace** view | 39 | New panel, reachable from an agent answer |
| **Proposed-edge review**, via inquiry deep links | 40 | Inside the Inquiry panel (no separate surface) |
| **Sugya pages** in the reader | 41 | Existing reader (they are chunks + a page view) |
| **Summary hits** + descend affordance | 42 | Answer source lists + margins |
| **Chazarah due-markers** | 41 | Margins + inquiry items (no new surface) |

**Out of scope, explicitly** (mirroring the plan's §2 discipline):

- No graph *visualization* — no force-directed node canvas, no "knowledge map." The daf
  never drew its citation network as a picture; it rendered it as **margins on the text
  you are actually reading**. A graph canvas is a demo feature; margins are a study
  feature. (Revisit in Phase 8 if the scholar asks.)
- No dashboards, analytics pages, or admin consoles. The north-star metrics live in CLI
  reports and JSON artifacts; the UI's only metric surface is the small "harvest line"
  in the inquiry panel (§4.4), which exists to close a feedback loop, not to chart.
- No new editing/composition surfaces. Every resolution flow **deep-links into the
  existing** annotate / add-term / approve / retract flows. The inquiry panel is a
  router of attention, never a second editor.
- No notifications, no realtime. The scholar opens the panel; the panel is current.

House rules apply to UI code as to everything else: routes stay thin, all assembly in
injected services, every panel works against fake stores in tests, auth-aware when
`AUTH_ENABLED=true`, all feature panels appear only when their config flag is on
(`GRAPH_EXPAND_ENABLED`, `AGENT_ENABLED`, …) — **a disabled feature leaves no dead UI**.

---

## 1. The design language: five rules

Everything below derives from these. When a detailed decision isn't specified, resolve
it by these rules.

### Rule 1 — The text is the center; knowledge is marginal.

Printed text renders largest, calmest, and immutable-looking (no hover affordances *on*
the text itself). Everything Phase 7 adds — edges, terms, expert layers, summaries —
renders *around* text, visually subordinate, in the margins idiom. The user should
never wonder which words are Torah and which are apparatus.

### Rule 2 — Evidence is a visual grammar, not a footnote.

The five evidence codes (Prompt 33) get one fixed badge treatment, used **identically
everywhere** an assertion appears — margins, inquiry cards, trace steps, source lines:

| Evidence | Badge | Rendering rule |
|---|---|---|
| `expert` | ● solid + author name | The gold standard; always shows *who* |
| `curated` | ◆ outlined, "Sefaria" | Human-curated upstream data |
| `deterministic` | ⚙ dotted | Machine-derived by construction (pasuk join); no author pretense |
| `derived_approved` | ◐ half-fill + approving author | Model-drafted, human-gated |
| `derived_bootstrap` | ◌ hollow, amber tint | The weakest tier; visually *asks* for review |

Shape + glyph carry the distinction, color only reinforces (accessibility; also the
amber tint on `derived_bootstrap` is the one deliberate emotional cue in the system —
it should look faintly *unfinished*, because it is). Every badge is tappable → the
assertion's full provenance (author, date, source chunk, confidence).

### Rule 3 — Every assertion answers "who says?" in one glance, and "show me" in one tap.

Author + evidence on the same line as the claim, always. Every ref, term, edge, and
chunk mentioned anywhere is a click-through to its source. There are no dead ends: a
margins item opens the far source *with its own margins*; study is walking.

### Rule 4 — The gate is a ritual, rendered once, reused everywhere.

One shared `<GateActions>` component: **אשר** (approve) / **דחה** (dismiss/reject),
plus the sticky author chip, plus — critically — a one-line preview of **what approving
will create** ("→ relation `parallels`, evidence `derived_approved`" / "→ expert chunk +
1 captured eval example"). The scholar should never approve into the dark. Approving
and dismissing are both first-class, equally easy; the UI must never nudge toward
approval (the gates are the asset; a gate that flatters the drafter is broken).

### Rule 5 — RTL-first; Hebrew is the primary language of the interface.

Panels are designed in RTL and mirrored to LTR, not vice versa. Labels the scholar
reads repeatedly are Hebrew (שאלות לרב, אשר, דחה, מקבילות, חזרה); developer-facing
strings (evidence codes, rel_types in detail views) stay in English as codes.
Directional glyphs (the ↳ via-arrow, the trace stepper) flip with direction. All ASCII
mockups below are drawn LTR for this document's legibility — **production is the
mirror**.

---

## 2. The Margins panel (Prompt 36) — the daf, realized

The flagship. On any source card and in the source-in-context reader, a **"margins ▸"
affordance** (Hebrew: **גליון ▸**) opens the apparatus.

**Layout is responsive to the metaphor:**

- **Wide screens:** the apparatus opens as a literal side margin column next to the
  passage — the reader becomes a daf. Text center, margins at the side, each group a
  labeled block like a classical apparatus (מסורת הש״ס on one side, the expert layer
  on the other, if width allows two columns).
- **PWA / narrow:** a bottom sheet sliding over the reader, same groups, one column.

**Content = the `Apparatus` model, grouped, in this fixed order** (order encodes the
system's values — anchors first, the scholar's own layer most prominent):

```
┌─ Tanya, Part I; Likkutei Amarim 18 ──────────── [גליון ▾] ─┐
│                                                             │
│  פסוקים (anchors)                                           │
│   ◆ quotes_pasuk → Devarim 30:14        (Sefaria)          │
│   ⚙ parallels → Torah Ohr, Vayera 14a   via shared pasuk   │
│                                                             │
│  קשרים (relations, grouped by type)                         │
│   ● connects → Likutei Torah, Re'eh 27b  (R. Ginsburgh)     │
│   ◐ explains → Tanya ch. 19              (approved: Rav)    │
│   ◌ develops → Miketz ma'amar     🕯 chazarah due           │
│                                                             │
│  מונחים (terms found in this passage)                       │
│   אהבה מסותרת · חכמה · ביטול                                 │
│                                                             │
│  שכבת הרב (expert layer: chunks referencing this ref)       │
│   ● "ההבדל בין אהבה מסותרת ל…"  (R. Ginsburgh, correction)  │
│   🎙 shiur segment 2024-11-03 @ 14:20                        │
│                                                             │
│  סוגיות · סיכומים (pages & summaries citing this ref)        │
│   📄 sugya: ביטול (v2)   ·   ⌄ chapter summary               │
└─────────────────────────────────────────────────────────────┘
```

Details that matter:

- **Empty apparatus is a statement, not an error**: an unknown or unannotated ref shows
  the empty groups with a single quiet line — *"הגליון עדיין ריק"* — and (when the
  inquiry system is live) a one-tap "שאל את הרב על מקור זה" that files an inquiry-style
  annotation entry via the existing capture flow. Silence is data.
- **Far endpoints outside the corpus** (pasuk anchors, refs not yet ingested) render as
  bare refs with an "outside the corpus" tint — still real, just not walkable. Tapping
  one shows the ref and its Sefaria link.
- **Counts on the affordance**: the collapsed "גליון ▸" chip shows a small count badge
  (`גליון · 7`) so a richly-annotated passage is visibly *alive* in lists — the
  compounding of the corpus becomes something you can see while scrolling.
- The chazarah due-marker (🕯, §6) appears inline on aging items — the margins are where
  the scholar naturally re-encounters old knowledge; that's exactly where re-review
  should be offered.

---

## 3. The via-line (Prompt 35) — provenance as a thread

When graph expansion contributes a source to an answer, its source line grows a second
line — the **via-line** — set smaller, indented, with the turn-arrow:

```
[3] Torah Ohr, Vayera 14a                                 score 0.71
     ↳ via connects ● (R. Ginsburgh) from Tanya 18
```

- The via-line names the **rel_type, evidence badge, author, and the seed ref** — the
  four facts the plan demands ("The scholar must always see WHY a source appeared").
- Tapping the via-line opens the **relation detail** (full provenance, source chunk,
  confidence) — not the far source; the source title above it already does that. The
  two taps do different jobs.
- Seed hits have no via-line. The absence is the design: unmarked = found by search,
  marked = brought by knowledge. Over time the scholar reads answer source lists as a
  ratio — *how much of this answer did the accumulated layer contribute?* — which is
  the compounding-rate metric made felt, without a dashboard.
- When a via-line's relation is `derived_bootstrap` (◌ amber), the answer is visibly
  standing partly on unreviewed ground. This is honest and intended.

---

## 4. שאלות לרב — the Inquiry panel (Prompt 37)

The highest-leverage feature gets the most careful panel. It is **the talmid's raised
hand**: a prioritized list of questions the *system* is asking the *scholar*.

### 4.1 Framing

Every item renders as a question addressed to the Rav, in natural Hebrew, never as a
database row. The generators' kinds map to voices:

| kind | The card's voice (examples from the plan) |
|---|---|
| `refused_question` | *"3 לומדים שאלו על **ביטול** — המערכת סירבה בכל פעם."* |
| `undergrounded_term` | *"ייתכן שהקורפוס תומך ב**כתר** — המנסח החינמי נכשל. לאשר או לדחות?"* |
| `low_evidence_relation` | *"הקשר Miketz ↔ Mishpatim מקורו ב-bootstrap וטרם נבדק."* |
| `contradiction` | *"שני קשרים סותרים על אותם מקורות: `argues_with` מול `explains` — מי צודק?"* |
| `re_review` | *"🕯 חזרה: קשר בן שנה, evidence ◌, לא אוחזר מעולם. עדיין נכון?"* |

### 4.2 Anatomy of a card

```
┌──────────────────────────────────────────────────────────┐
│ ？ refused_question                        priority 8.4  │
│                                                          │
│ 3 לומדים שאלו על ביטול — המערכת סירבה בכל פעם.            │
│   "מהו ביטול במקום?"  ·  "ביטול ושפלות"  ·  +1           │
│                                                          │
│ priority = 3×refusals(2.4) + recency(1.0) + kind(5.0)    │
│                                                          │
│ [ ענה → annotate ]   [ דחה ]                              │
└──────────────────────────────────────────────────────────┘
```

- **The priority math is printed on the card** (the plan: *"Keep it transparent —
  print the components"*), in small type. The scholar can disagree with the ranking
  and say so; an opaque queue would spend his trust along with his time.
- **One primary action per kind**, deep-linking into the existing resolving flow:
  refused → annotate/compose pre-filled with the clustered question; undergrounded
  term → the add-term flow pre-filled; low-evidence relation / contradiction → the
  relation detail with `<GateActions>`; re_review → confirm/retract on the item.
- **דחה (dismiss) is first-class**, same visual weight. A dismissal records the
  resolution and teaches the queue.
- **Resolution is shown after the fact**: an answered card collapses to a single-line
  receipt — *"נענה → expert chunk `exp_9f2` + eval example"* — before leaving the open
  list. The scholar sees his hour crystallize into artifacts.

### 4.3 Ordering and grouping

One list, strictly by priority (ties by recency), with kind filter chips across the
top (matching `maayan inquiries --kind`). No pagination ceremonies; the queue should
feel *short* — if it's long, the ranking has failed at its one job.

### 4.4 The harvest line

A single fixed line at the panel's foot — the only metric in the entire UI:

> **היום: 4 נענו → 2 חיבורים, 1 מונח, 3 דוגמאות מבחן.**
> *(Today: 4 answered → 2 connections, 1 term, 3 eval examples.)*

This is the expert-leverage metric (approved knowledge per expert-hour) rendered as
immediate, personal feedback: *this session mattered, and here is what it made
permanent.* It is deliberately not a chart, has no history view, and resets daily.

### 4.5 Review of proposed edges (Prompt 40's gate)

Study-program output (`status="proposed"` relations) enters review **through this same
panel** — a `proposed_relation`-flavored card (rendered from the `low_evidence_relation`
machinery + deep link) showing: the drafted edge, its exact grounding refs (each a
click-through), the faithfulness-check result, and `<GateActions>` with the creation
preview ("אשר → relation `explains`, evidence `derived_approved`"). No separate "review
console" exists or is needed; rationing the Rav's attention through one prioritized
door is the design.

---

## 5. The Study Trace (Prompt 39) — the chavrusa's notebook

When an answer was produced by the agent (`ask --agent`), the answer view gains one
affordance: **"כיצד נלמד? ▸"** (*how was this studied?*). It opens the trace, rendered
as a vertical stepper — a shiur transcript, not a debug log:

```
  מהי עבודת הבירורים?
  ────────────────────
  ① 🔍 חיפש  "עבודת הבירורים"
        → 4 sources (top: Tanya 37, 0.78)
  ② 📖 פתח   Tanya, Part I; Likkutei Amarim 37
  ③ 🕸 הלך בגרף  from Tanya 37
        → ● connects (R. Ginsburgh) → Torah Ohr, Vayigash
  ④ 📚 בדק מונח  "בירור"
  ⑤ ✔ סיכם   — 6 sources in hand
  ────────────────────
  budgets: hops 4/4 · chunks 6/12 · calls 5/6
```

- **Each step is expandable** to its compact typed digest (hits + scores, edges
  followed, the term found). Collapsed, the trace reads in five seconds; expanded, it
  teaches.
- **Citations link back to steps**: in the answer above the trace, each citation
  number carries a faint step marker (e.g. `[4]³` — source 4 arrived at step ③).
  Tap it to highlight that step. The reader can see *which hop earned which mekor* —
  the trace as teaching material, exactly as the plan intends.
- **Budget exhaustion is shown honestly**: a force-conclude renders as
  *"⏸ הגיע לגבול הצעדים — סיכם עם מה שנאסף"*, never disguised as a natural conclusion.
  When the scholar sees a budget cut a real line of inquiry, that observation is
  Phase-8 input (plan §7.5) — the UI's honesty here feeds the harness critique.
- A refusal shows **no trace affordance at all** — the gate fired before any model was
  called, and the UI must not imply otherwise.
- Traces are shareable/linkable (`GET /api/traces/{id}` already exists): a trace URL
  is how the scholar shows a talmid *how the system worked a sugya*.

---

## 6. Sugya pages, summaries, and chazarah in the reader (Prompts 41–42)

### Sugya pages

A sugya page renders **in the existing reader** as a curated article with three
distinguishing marks:

1. A **header plaque**: concept, version chip (`v2`), status, approving author, and a
   discreet history link — tapping it lists superseded versions (read-only; version N
   opens with a "superseded by v2" banner). Wikipedia's versioned-article pattern, one
   level deep.
2. **Every line cited**: section text renders with its citation refs inline, each a
   click-through; the page's cited-refs set doubles as its margins.
3. **Honest gaps render as gaps**: the "open questions" section is styled as questions
   (？), not padded prose — and each open question carries a one-tap "file as inquiry"
   affordance, feeding the queue. The sugya page and the inquiry queue are two ends of
   one loop and the UI should make that loop walkable.

When an *answer* cites a sugya chunk, its source line carries a `📄 sugya` chip so the
scholar sees distilled knowledge being retrieved alongside the sources it came from.

### Summary hits (Prompt 42)

A summary chunk in a source list gets a `⌄ summary` chip and one extra affordance:
**"ירד לאותיות ▸"** (*descend to the osiyos*) — expanding the child-ref list from its
metadata, each a click-through to the exact passage, each with its own margins. The
bird's-eye row and the ground truth stay one tap apart; citation integrity (citations
always point at real printed text) is never blurred by the UI.

### Chazarah due-markers

No chazarah surface exists. Instead, items due for re-review carry the 🕯 marker in the
two places the scholar already looks — the margins panel and the inquiry queue (as
`re_review` cards). Confirming a re-review shows the spaced-repetition consequence
plainly: *"אושר · חזרה הבאה בעוד ~6 חודשים"*. Memory hygiene rendered as a habit, not
a chore-list.

---

## 7. States, degradation, and flags

| Condition | UI behavior |
|---|---|
| `GRAPH_EXPAND_ENABLED=false` (default) | No via-lines anywhere; margins still work (they read the store directly) |
| `AGENT_ENABLED=false` (default) | No trace affordance; `ask` UI unchanged |
| Empty graph (pre-backfill) | Margins render empty-state (§2); nothing errors |
| `ASK_LOG_ENABLED=false` | Inquiry panel hides the refused-question section only |
| `AUTH_ENABLED=true` | All panels behind the existing login; author chip = logged-in user, sticky |
| Store/service failure | Panels degrade to a one-line error *inside the panel*; the reader and answer flow never break because an apparatus call failed |

Loading: margins and inquiry load on open (no prefetch on every card render); a
skeleton of the group headers, never a spinner over the text.

---

## 8. Component inventory (build once, reuse everywhere)

| Component | Used by | Notes |
|---|---|---|
| `EvidenceBadge` | margins, via-lines, inquiry, trace, sugya | The Rule-2 grammar; one implementation |
| `RefLink` | everywhere | Canonical ref → click-through; out-of-corpus tint |
| `ViaLine` | answer sources, trace steps | ↳ + rel_type + badge + author + seed |
| `GateActions` | inquiry cards, relation detail, sugya approve | אשר/דחה + sticky author + creation preview |
| `MarginsPanel` | reader, source cards | Side column ↔ bottom sheet responsive |
| `InquiryCard` | inquiry panel | Kind voice + printed priority math + deep link |
| `TraceStepper` | trace view | Collapsible steps + budget footer |
| `ChazarahMark` | margins, inquiry | 🕯 + next-interval tooltip |

Routes stay thin (`/api/apparatus`, `/api/traces/{id}`, inquiry endpoints); **all
composition happens in the already-planned services**. UI tests: render each component
against fake payloads (empty / full / degraded); RTL snapshot for margins and inquiry;
the citation-integrity invariant of Prompt 42 gets a UI assertion too (a summary hit's
citation link never targets a neighbor).

---

## 9. Sequencing (rides the plan's §5, adds nothing)

| Plan step | UI deliverable shipped with it |
|---|---|
| 33–34 | None (CLI only). `EvidenceBadge`/`RefLink` may be built here as groundwork |
| 35 | `ViaLine` in answer sources |
| 37–38 | Inquiry panel + `GateActions` + harvest line |
| 36 | `MarginsPanel` (after 34, so the margins have something to show) |
| 39–40 | `TraceStepper`; proposed-edge cards in the inquiry panel |
| 41–42 | Sugya page view, summary descend, `ChazarahMark` |

---

*The test of this UI is the same as the test of the phase: open Tanya chapter 18 and
see, on one screen, what the beis medrash knows about this daf — who anchors it, who
argues, what the Rav corrected, what the machine proposes and honestly marks as
unproven, and what question, answered next, would teach the system the most.*
