# Lesson 4.3 — Gold sets & honest measurement

> Module 4, Lesson 3 · ~20 min read + a hands-on you'll actually edit a file for.
> The one question this answers: **the metrics are only as trustworthy as the gold set behind
> them — so what makes a *good* gold case, and how do I add one?**

A gold set is the ruler you measure retrieval with. A bent ruler gives confident, precise,
*wrong* readings. This lesson is about keeping the ruler straight: what a good case looks like,
why negative cases are not optional, and the special gold set that measures the cross-text
claim. Then you'll add a case and re-run.

---

## What makes a good positive case

A positive case is `{question, expected_refs}`. Three properties separate a useful one from a
misleading one:

1. **The question is real.** Phrase it the way a person would actually ask — in Hebrew, with
   natural wording — not as a keyword-stuffed query reverse-engineered from the source. The
   whole point is to test retrieval against *genuine* questions.
2. **The expected refs are right and complete.** List the chapter(s) that truly answer it. If
   two chapters bear on it, list both — otherwise `recall@k` will punish retrieval for finding a
   legitimately-relevant passage you forgot to credit. (Remember chapter-level refs are fine;
   prefix matching handles segments — Lesson 4.1.)
3. **It tests *one* thing.** A question whose answer is scattered across ten chapters measures
   nothing clearly. Prefer cases with a crisp, locatable answer.

The danger to avoid: writing the question *after* looking at the passage, using its exact words.
That measures keyword overlap, not retrieval — and bge-m3 would "pass" for the wrong reason. Ask
the question first, then find its home.

---

## Why negative cases are not optional

Here's the subtle one. If your gold set contains *only* answerable questions, you can score a
perfect 1.0 on every ranking metric — with a system that **never refuses anything.** Ranking
metrics literally cannot see over-confidence, because they only ever ask answerable questions.

So a gold set that doesn't test refusal is measuring half the system and calling it whole. That's
why maayan's gold set includes **negative cases**:

```yaml
- question: "מהי נקודת הרתיחה של מים?"     # boiling point of water — not in Tanya
  should_refuse: true
  expected_refs: []
```

`should_refuse: true` with empty refs says: *the correct behavior here is to refuse.* These are
excluded from hit@k / recall@k and instead drive the `refused` rate from Lesson 4.2. A good gold
set deliberately includes questions the corpus *can't* answer — adjacent-but-absent topics, an
un-ingested text, a different discipline — so the gate is measured, not assumed. Read the header
comment in [eval/goldset.yaml](../../eval/goldset.yaml); it spells this out.

> ### Under the hood — the gold set measures two systems at once
> `GoldExample` ([goldset.py](../../maayan/eval/goldset.py)) carries `should_refuse` precisely so
> one file can score both halves: positives test *retrieval ranking*, negatives test *the
> default-deny gate*. When you add cases, you're improving one or the other — be conscious of
> which. A corpus with great recall and a gate that never refuses is not trustworthy; the
> negative cases are what keep you honest about that.

---

## The cross-text gold set (a different question entirely)

There's a second gold set: [eval/crosstext_goldset.yaml](../../eval/crosstext_goldset.yaml), run
with `uv run maayan eval --crosstext`. It measures something the main metrics don't: whether a
question whose answer spans **two or more books** actually pulls passages from *both*, rather than
burying one book under the other. (Its metric is book-diversity@k; it exists because the
cross-text "connect these sources" claim — Phase 4, Prompt 18 — needs its own honest measurement,
not a borrowed one.) The lesson generalizes: **a new capability needs its own gold set.** You
can't measure a new claim with the old ruler. (There's a third, `--develop`, for the develop step
— that's Module 6's territory.)

---

## Hands-on

Full Tanya indexed (Lesson 4.2 prerequisite). You're going to edit the gold set.

**1. Add a positive case.** Open [eval/goldset.yaml](../../eval/goldset.yaml). Think of a genuine
question about Tanya Part I — ask it in your own words *first* — then find the chapter that
answers it. Add an entry under `examples:` (mind the indentation):

```yaml
  - question: "כיצד התורה והמצוות מלבישים את האור האין סוף?"
    expected_refs: ["Tanya, Part I; Likkutei Amarim 4"]
    note: my first gold case
```

Re-run and find your case's effect:

```bash
uv run maayan eval
```

Did the aggregate metrics shift slightly? (With ~50 cases, one case moves the average a little.)
More importantly: confirm it *ran* (the question count went up by one). If retrieval found your
chapter, you wrote a case the system passes; if not, you've either found a real retrieval weakness
or mis-attributed the chapter — both are worth investigating. *That* is the gold set working.

**2. Add a negative case — and watch the gate get measured.** Add a question the corpus genuinely
can't answer:

```yaml
  - question: "מהו דין מוקצה בשבת?"          # a halachic question — not in Tanya
    should_refuse: true
    expected_refs: []
```

Re-run. The negative count goes up by one, and the `refused (of negatives)` rate now includes
your case. If it's *not* refused, your gate is too loose for this corpus — exactly the kind of
finding ranking metrics would have hidden.

**3. Tie it to a real decision (preview of Module 8).** With your two new cases in place, run
`uv run maayan eval --compare`. You now have a slightly richer ruler. Imagine you were deciding
whether to enable rerank: which column would you watch, and what change would justify the switch?
Write down your answer — Module 8.1 is exactly this move.

> When you're done experimenting, you can keep your good cases (they make the gold set better!)
> or `git checkout eval/goldset.yaml` to revert. Better gold = more trustworthy numbers, so
> well-written cases are a genuine contribution.

---

## You should now be able to say…

- What makes a **good positive case** (real question, correct *and complete* refs, tests one
  thing) and the trap of writing the question from the passage's words.
- Why **negative cases** are essential — ranking metrics are blind to over-confidence; only
  `should_refuse` cases measure the gate.
- Why a new capability (cross-text co-retrieval, the develop step) needs **its own gold set**.
- How to add a case and read its effect.

**That's Module 4.** You can now measure retrieval honestly: the metrics (4.1), how to run and
read the harness including the gate rates (4.2), and how to keep the ruler straight (4.3). You've
finished the *universal* RAG half of the curriculum (Modules 0–4) — you can explain and measure
any RAG system.

Next: **Module 5** turns to *this* system's engineering spine — the house rules (dependency
injection, typed boundaries, config-driven, the Clock) that let you change maayan without fear.
When you're ready, ask me to **build out Module 5**.
