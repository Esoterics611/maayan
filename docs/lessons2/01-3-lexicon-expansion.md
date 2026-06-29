# Lesson 1.3 — Lexicon-aware expansion (no model needed)

> Module 1, Lesson 3 · ~12 min read + a hands-on (no backend required).
> The one question this answers: **how does maayan use the lexicon *you* curated to widen a
> query for free — and why is this the most "yours" part of the whole upgrade?**

The generative expanders (1.2) are powerful but cost model calls and depend on the model's
quality. There's a second, complementary expander that costs **nothing** and gets *better the
more you teach the system*: `LexiconExpander`
([retrieve/expand.py](../../maayan/retrieve/expand.py)).

---

## The idea: inject curated vocabulary on a match

Recall the lexicon from Course 1 (Module 6): you defined **terms** — Holy Names, sefiros,
technical concepts — each with a canonical form, surface variants, related terms, and a
definition, stored in `TermStore` and indexed as `source="term"` chunks. The lexicon expander
puts that knowledge to a new use:

> When a registered term appears in the question, append one extra query that augments the
> question with that term's **canonical form** and **related terms**.

So if you've defined `ע"ב` (Name of 72) with related terms `ס"ג / מ"ה / ב"ן`, then asking about
`ע"ב` automatically also searches for the whole family — pulling in passages that discuss the
siblings, which a scholar would absolutely want, but which your raw query never named.

---

## How the match works (and why it's safe)

It reuses the exact tolerant matching the lexicon already uses — `fold_surface` from
`corpus/normalize.py` (Course 1, 1.3): drop nikkud, strip gershayim/quotes, casefold. So
`ע"ב`, `ע״ב`, and `עב` all match the same term, regardless of how you typed the question.

```python
folded_query = fold_surface(query)
for term in self._terms.list_terms():
    if term.retracted:
        continue                      # never resurface a retracted term
    forms = term.surface_forms or [term.canonical]
    if any(fold_surface(f) in folded_query for f in forms):
        additions.append(term.canonical)
        additions.extend(term.related_terms)
```

Three things worth noticing, each deliberate:

- **Deterministic.** Same query + same lexicon → same expansion, every time. No model, no
  randomness, no latency. It's the cheapest possible way to widen the net.
- **Retracted terms are skipped.** If you tombstoned a term (Course 1, Phase 4), it won't sneak
  back in through expansion. The eraser stays erased.
- **It compounds with your work.** Every term you add to the lexicon makes *every future query*
  that mentions it a little smarter. The capture loop now improves retrieval, not just the
  answer corpus — a quiet but real payoff.

> ### Under the hood — a clean DI seam
> `LexiconExpander` doesn't depend on the concrete `TermStore`; it takes anything satisfying the
> tiny `TermSource` protocol (`list_terms() -> list[Term]`). That's why the test can hand it a
> fake list and why you could back it with a different store later — the same dependency-
> injection discipline from Course 1, Module 5.

---

## Hands-on

No backend needed — this is pure Python over your SQLite lexicon.

**1. Expand a query that mentions a term you've defined.** Substitute a real term/surface form
from your lexicon:

```bash
uv run python - <<'PY'
from maayan.config import Settings
from maayan.lexicon.store import TermStore
from maayan.retrieve.expand import LexiconExpander

s = Settings()
ex = LexiconExpander(TermStore(s.db_path))
out = ex.expand('מהו ע"ב')          # <- use a surface form you actually defined
for q in out.queries:
    print(repr(q))
PY
```

If the term matched, you'll see a second query carrying its canonical form and related terms. If
nothing expanded, either the term isn't in your lexicon or its surface forms don't fold to match
— a good prompt to go define/improve it (and a reminder of why curation pays off here).

**2. Prove the payoff loop.** Define a new term with a couple of related terms
(`maayan term add …`, Course 1), then re-run step 1 with a query naming it. The expansion grows
the moment you teach it. *That* is the capture loop feeding retrieval.

---

## You should now be able to say…

- What `LexiconExpander` does: on a folded-surface match, inject the term's canonical + related
  terms as an extra query — deterministically, with no model call.
- Why it's safe (skips retracted terms) and tolerant (reuses `fold_surface`).
- Why it's the most *yours* expander: every lexicon entry you curate makes future retrieval
  smarter — the capture loop now improves search, not just the answer corpus.

Next: **[1.4 — Fusing the nets: RRF + the drop-in retriever](01-4-rrf-and-multiquery.md)** — how
all these queries become one ranked list without changing anything downstream.
