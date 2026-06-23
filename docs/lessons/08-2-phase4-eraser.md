# Lesson 8.2 — Phase 4: the eraser & measurement

> Module 8, Lesson 2 · ~20 min, hands-on at the terminal.
> The one question this answers: **a scholar will eventually index something wrong — how does the
> system let them *remove* it without betraying the provenance everything else rests on?**

Module 6 gave you three ways to *add* knowledge (annotate, develop→approve, add-term). But for a
long time maayan had no way to *remove* any of it. [BUILD_PLAN_PHASE4.md](../BUILD_PLAN_PHASE4.md)
names this exactly: "There is no eraser… once a chunk is indexed it is permanent." For a system
whose entire value is *accumulated, trusted* knowledge, that's the first necessary gap to close —
because a scholar *will* index a wrong connection, a typo'd term, or approve a development they
later reconsider. This lesson is the eraser, and the measurement that came with it.

---

## Why deleting is hard *here*

In most systems, "delete the row" is trivial. In maayan it's delicate, because the whole system
runs on provenance (Lesson 6.1) and on printed text being **immutable**. A naive `DELETE` would
violate both: it would erase the audit trail, and nothing would stop someone from "deleting" a
verse of Tanya. So a retraction must satisfy two constraints the rest of the system also obeys:

1. **Printed text is untouchable.** You can retract `expert` / `derived` / `term` chunks — *your*
   layered knowledge — but never `sefaria` / `chabad`.
2. **Removal itself carries provenance.** Who removed it, when, and why must be recorded. A silent
   delete is exactly the kind of unattributed change the system forbids everywhere else.

---

## How retraction works

Open [maayan/retract/models.py](../../maayan/retract/models.py) and
[service.py](../../maayan/retract/service.py). A `Retraction` is, in the model's own words, "NOT a
silent delete: it is an attributed, timestamped audit record (who retracted, when, why)." The
`retract` method does six things (read the service docstring):

1. **Resolve** the chunk (by stable id or by ref).
2. **Reject printed text in code** — `sefaria`/`chabad` raise; immutability is enforced, not
   requested.
3. **Delete the point from Qdrant** — it's gone from retrieval immediately.
4. **Tombstone the corpus chunk** (`mark_retracted`, Lesson 2.2's store) so `index --rebuild`
   never re-embeds it — the removal survives a full rebuild.
5. **Cascade** — a retracted `derived` chunk flips its `Development` to status `"retracted"`; a
   `term` chunk marks its `Term` retracted. Related records stay consistent.
6. **Record the `Retraction`** — an attributed, timestamped audit row.

> ### Under the hood — correction = retract + re-add (no in-place edit)
> Notice there is no "edit" operation. The service docstring explains why: chunk ids are
> content-derived and idempotent (Lesson 1.2), so there's no meaningful in-place mutation. To
> *correct* a mistake you **retract the wrong chunk** (reason: "superseded") and **add the right
> one** through the existing capture / develop / add-term loops. This is the same discipline as
> printed text: you never overwrite, you supersede — and the supersession is itself provenanced.
> An audit trail you can't rewrite is exactly what makes accumulated knowledge trustworthy over
> years.

---

## The other half of Phase 4: measuring the cross-text claim

Phase 4 named a second gap (read [BUILD_PLAN_PHASE4.md](../BUILD_PLAN_PHASE4.md) §0): "Phase 3's
headline is unmeasured." The marquee feature — connecting passages *across* books (Tanya ↔ Torah
Or ↔ Likutei Torah) — was shipped with a Tanya-only gold set, so the cross-text claim had no
honest number behind it. The fix was a dedicated cross-text gold set and metric (you met it in
Lesson 4.3): `maayan eval --crosstext`, which measures book-diversity@k — whether a question whose
answer spans two books actually retrieves passages from *both*. The lesson generalizes a Module 4
principle: **a new capability needs its own ruler.** Shipping a feature and measuring it are two
different acts of discipline, and Phase 4 did the second.

---

## Hands-on

Qdrant up. You'll need a layered-knowledge chunk to retract — use one you made in Module 6 (an
`expert`, `derived`, or `term` chunk), or make a throwaway one.

**1. Retract a piece of your own knowledge.** Using its ref or chunk id:

```bash
uv run maayan retract "<ref-or-chunk-id>" --author "Your Name" --reason "superseded"
```

It confirms the chunk is "Gone from retrieval and skipped by `index --rebuild`." Now search for it
(`--source expert`/`derived`/`term`) — it no longer comes back. The eraser works.

**2. Confirm printed text is untouchable.** Try to retract a verse of Tanya:

```bash
uv run maayan retract "Tanya, Part I; Likkutei Amarim 1" --author "Your Name" --reason "test"
```

It refuses — printed text is immutable, enforced in code. That refusal is the same family of
guarantee as default-deny: a rule the system won't let you talk it out of.

**3. Read the audit trail.** Retractions are recorded, not silent:

```bash
uv run maayan retractions
```

Your retraction appears with who/when/why. In one sentence: why is a *recorded* removal more
trustworthy than a clean delete?

**4. Measure the cross-text headline.** If you've ingested more than one book:

```bash
uv run maayan eval --crosstext
```

Read book-diversity@k. This is the number that was missing when the feature first shipped — the
measurement catching up to the claim.

---

## You should now be able to say…

- Why an **eraser** was the first necessary Phase 4 gap, and the two constraints it must honor
  (printed text immutable; removal provenanced).
- The six steps of `retract` (resolve → reject printed → delete point → tombstone → cascade →
  record), and that **correction = retract + re-add**, never in-place edit.
- That Phase 4 also **measured** the previously-unmeasured cross-text claim with its own gold set
  (`--crosstext`) — a new capability needs its own ruler.

Next: **[8.3 — Phase 5: composition](08-3-phase5-composition.md)** — from grounded *answers* to
grounded *documents*, by running the unit you already trust once per section.
