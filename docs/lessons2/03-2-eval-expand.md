# Lesson 3.2 — Measuring the lift with `eval-expand`

> Module 3, Lesson 2 · ~12 min read + a hands-on.
> The one question this answers: **how do I prove query expansion actually retrieves better —
> with numbers — and learn when it helps and when it doesn't?**

Course 1, Module 4 taught you to replace "it feels right" with hit@k / recall@k / MRR over a gold
set. Prompt 31 adds a command that points that same machinery at one question: **does expansion
retrieve better than no expansion?** Never enable a mode on vibes — measure it.

---

## What `eval-expand` does

`make eval-expand` (the `eval-expand` CLI command) runs your gold set through the retriever
**twice** — once with expansion off, once on — and prints the two side by side:

```
uv run maayan eval-expand
# or, where expansion should help most:
uv run maayan eval-expand --crosstext
```

Under the hood it reuses Course 1's `run_eval` harness ([eval/harness.py](../../maayan/eval/harness.py)),
because `MultiQueryRetriever` *is* a `Retrieving` (Lesson 1.4) and plugs straight in. It builds
two retrievers via the factory — `expand=False` and `expand=True` — shares one embedder, and
labels the rows `no-expand` vs `expand`. If a generation backend is configured it uses the full
lexicon+LLM expansion; if not, it falls back to **lexicon-only** and tells you so (so you can run
it offline).

You read the same columns as Course 1: `hit@k`, `recall@k`, `MRR`, and the default-deny gate
rates (`answ` / `refus`).

---

## Reading the result — and when expansion helps

The number to watch is **recall@k**: of the passages a question *should* retrieve, how many did
it? Expansion's whole job is to stop relevant sources slipping past `top_k`, so recall is where
the lift shows up.

- **Conceptual & cross-text questions** (answers spread across books, phrased unlike the ask) →
  expansion usually lifts recall and MRR. This is the case Module 1 was built for; `--crosstext`
  targets it directly.
- **Single-passage factual questions** → little or no lift; the one query already found the one
  source. Expansion can't help where there's nothing extra to find.
- **Watch the gate rates.** `relevance = max` across variants means expansion's `answ` rate can
  only rise or hold (more chances to clear the bar) — but confirm `refus` on negatives stays
  high. If expansion starts answering questions it should refuse, that's over-expansion (Lesson
  4.2), and the table is how you'd catch it.

The decision rule: **enable expansion globally only if `eval-expand` shows a real recall lift on
your gold set without hurting the refusal rate.** That's enabling on numbers, not vibes.

> ### Under the hood — same harness, honest comparison
> Because both rows come from the identical `run_eval` over the identical gold set and embedder,
> the only variable is expansion. That's a clean A/B. If you change `query_expand_variants` or
> toggle `query_expand_hyde` in `.env` and re-run, you're now A/B-testing *those* — the harness
> turns every knob in Module 4 into something you can justify with a number.

---

## Hands-on

**1. Run the comparison** on your retrieval gold set, then the cross-text one:

```bash
uv run maayan eval-expand
uv run maayan eval-expand --crosstext
```

Compare the `no-expand` and `expand` rows. Where is recall@k higher? Is the cross-text lift
bigger than the plain one? (It should be.)

**2. A/B a knob.** Set `QUERY_EXPAND_HYDE=false` in `.env`, re-run `eval-expand --crosstext`, and
compare to the HyDE-on numbers. Does HyDE earn its extra call on *your* corpus? Now you're tuning
with evidence — exactly the muscle Module 4 builds.

---

## You should now be able to say…

- What `eval-expand` does: A/B the retriever (expansion off vs on) over your gold set, reusing
  Course 1's harness because the multi-query retriever is a drop-in `Retrieving`.
- That **recall@k** is the lift to watch, expansion helps most on **conceptual/cross-text**
  questions, and the gate rates guard against over-expansion.
- The rule: enable expansion globally only on a measured recall lift that doesn't hurt refusal.

Next: **[4.1 — The knobs, and recipes](04-1-knobs-and-recipes.md)** — turn what you've measured
into settings.
