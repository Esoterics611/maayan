# Lesson 3.1 — The cost ladder

> Module 3, Lesson 1 · ~10 min read + a hands-on (no backend required).
> The one question this answers: **what does each mode actually cost in model calls, and how do
> I decide when the intelligence is worth it?**

Every new move buys quality with model calls (tokens, latency, and — on a cloud backend —
money). Knowing the exact price is what lets you choose modes with intent instead of leaving
everything maxed "to be safe." Here's the whole ladder.

---

## Counting the calls

A single `ask` makes generation calls in up to three places:

| Stage | When | Calls |
|---|---|---|
| **Expansion** (`LLMQueryExpander`) | `--expand` with a backend | up to **2** — one for reformulations (`variants>0`), one for HyDE (`hyde=true`) |
| **Answer** | always (single-pass) **or** | **1** synthesize |
| → split into **analyze + synthesize** | `--reason` | **2** instead of 1 |
| **Verify** | `--verify` | **1** |

So the ladder, cheapest to dearest:

```
plain ............................. 1 call
plain + verify .................... 2 calls
reason ............................ 2 calls   (analyze + synthesize)
reason + verify ................... 3 calls
expand + reason + verify .......... up to 5 calls  (2 expand + 2 reason + 1 verify)
```

Two things to note. **Lexicon expansion is free** — it's deterministic, zero model calls — so
`--expand` with `variants=0, hyde=false` adds *nothing* to the bill while still widening the net
with your terms (the "lexicon-only" recipe in Lesson 4.1). And **expansion calls are cheap
calls**: short prompts, short outputs. The expensive call is usually synthesis over many
sources.

---

## Choosing a mode

A rule of thumb, by situation:

- **Browsing / quick lookups, or a factual question with one obvious source** → plain (or
  expand-lexicon-only). Reasoning adds little when there's nothing to *relate*.
- **A real conceptual question you'll act on** → `--expand --reason`. This is the sweet spot:
  better sources, a woven answer, ~4 calls.
- **Something you'll quote to others / publish** → add `--verify`. Pay the extra call to catch
  an overstatement before a person relies on it.
- **A weak/local model** → keep `variants` low and consider skipping reason (small models
  produce thin study maps — Lesson 4.1).

The point of off-by-default is precisely this: you spend calls where they earn their keep, and
the system's resting cost is exactly Course 1's.

---

## Hands-on

No backend needed — count calls with a counting fake across the ladder:

```bash
uv run python - <<'PY'
from maayan.generate.rag import RAGService
from maayan.retrieve.models import RetrievalResult, SearchResult

class FakeRetriever:
    def retrieve(self, q, *, k=None, book=None, source=None):
        r = SearchResult(ref="Tanya 1:1", text="…", score=0.5, lang="he", source="sefaria", payload={"ref":"Tanya 1:1"})
        return RetrievalResult(results=[r], relevance=0.9)

class Counter:
    def __init__(self): self.n=0
    def generate(self, system, messages): self.n+=1; return "OK" if "citation checker" in system else "answer [S1]."

for label, kw in [("plain", {}), ("verify", {"verify":True}),
                  ("reason", {"reasoning":True}), ("reason+verify", {"reasoning":True,"verify":True})]:
    b = Counter()
    RAGService(FakeRetriever(), b, score_threshold=0.4, **kw).ask("q")
    print(f"{label:14} → {b.n} call(s)")
PY
```

(This counts the *answer-side* ladder; expansion adds up to 2 more at retrieval time, which you
saw generated in Lesson 1.2.) Match the output to the table above.

---

## You should now be able to say…

- The model-call cost of each mode, end to end (1 → up to 5), and that **lexicon expansion is
  free**.
- That expansion calls are cheap and synthesis is the costly one.
- A situational rule for choosing a mode — and why off-by-default lets you spend calls only
  where they pay.

Next: **[3.2 — Measuring the lift with `eval-expand`](03-2-eval-expand.md)** — proving expansion
helps with numbers, not vibes.
