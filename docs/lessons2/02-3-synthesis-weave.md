# Lesson 2.3 — Synthesis: weave, don't list

> Module 2, Lesson 3 · ~12 min read + a hands-on (needs a backend).
> The one question this answers: **how does Stage 2 turn the study map and the sources into a
> single woven answer — while keeping every claim grounded and cited?**

Stage 1 built the map (2.2). Stage 2 writes the answer from it. The whole design goal of this
stage is one word: **weave** — connect the sources into one argument, rather than narrate them
one at a time.

---

## What the synthesizer receives

The system prompt for Stage 2 is the *same* grounded-answer prompt from Course 1
(`DEFAULT_SYSTEM_PROMPT`: answer only from the numbered sources, cite every claim with `[S#]`,
refuse if unsupported). What's new is the **user message**, assembled by
`_synthesis_user_content` ([generate/rag.py](../../maayan/generate/rag.py)):

```python
blocks = [ (conversation, if any),
           build_context(sources),                       # the numbered [S#] sources
           "STUDY MAP (your own analysis ... use it to organize and connect, "
           "but cite ONLY the [S#] sources, never the map):\n" + study_map,
           f"Question: {question}\n\n"
           "Using the study map, weave the sources into a single coherent answer "
           "(connect them — do not just list them). Cite each claim ONLY by its [S#] tag. "
           "Do not cite the conversation or the study map." ]
```

So the synthesizer sees three things: the **sources** (citable), the **study map** (its
scaffold, *not* citable), and an instruction to **weave and cite**. The map tells it *how the
pieces connect*; the sources are what it's allowed to stand on.

---

## The two disciplines that keep it honest

This stage adds connective intelligence **without loosening grounding**. Two rules do that:

1. **Cite only `[S#]` sources — never the map.** The study map is the model's own words; letting
   it be cited would let the model cite *itself*. The prompt forbids it explicitly, and citation
   extraction (`extract_cited_refs`, unchanged from Course 1) only resolves `[S#]` tags back to
   real source refs. So "weave" never becomes "embellish."
2. **Same refusal rule inside the prompt.** The synthesis system prompt still says: if the
   sources don't support it, say so. Reasoning makes the answer *better-organized*, not
   *bolder*. (And the hard, code-level default-deny gate already fired before we ever got here —
   Lesson 2.4.)

The result: the answer reads like a connected explanation — "X establishes the principle [S1],
which Y extends to creation [S3], resolving the difficulty Z raised [S2]" — while every clause
still traces to a real mekor.

> ### Under the hood — why reuse the Course 1 system prompt?
> Stage 2 deliberately keeps `DEFAULT_SYSTEM_PROMPT` rather than inventing a new one. The
> grounding/citation/refusal *rules* should be identical whether or not reasoning is on — only
> the *material* differs (now there's a study map to weave from). Reusing the prompt guarantees
> the trust contract doesn't drift between modes. It also means the single-pass path and the
> synthesis path cite identically, so `cited_refs` means the same thing everywhere.

---

## Hands-on

Backend required.

**1. Inspect the exact synthesis prompt.** See precisely what Stage 2 is handed (sources + map +
instruction), using a backend that records its calls:

```bash
uv run python - <<'PY'
from maayan.generate.rag import RAGService
from maayan.retrieve.models import RetrievalResult, SearchResult

class FakeRetriever:
    def retrieve(self, q, *, k=None, book=None, source=None):
        rs = [SearchResult(ref=f"Tanya 1:{i}", text=f"source text {i}", score=0.5,
                           lang="he", source="sefaria", payload={"ref": f"Tanya 1:{i}"}) for i in (1,2)]
        return RetrievalResult(results=rs, relevance=0.9)

class Recorder:
    def __init__(self): self.calls=[]
    def generate(self, system, messages):
        self.calls.append(messages[0].content)
        return "STUDY MAP: [S1] …; [S2] builds on [S1]." if "STUDY MAP" in system else "Woven answer [S1][S2]."

b = Recorder()
RAGService(FakeRetriever(), b, score_threshold=0.4, reasoning=True).ask("the question")
print(b.calls[1])      # the SYNTHESIS user message
PY
```

Find the three blocks in the printed message: `SOURCES:` (the `[S#]` list), `STUDY MAP (...)`
(the scaffold), and the `Question: … weave …` instruction. That's the entire contract Stage 2
works under.

**2. Judge a real weave.** Run a live `--reason` answer and check: does every factual clause
carry a `[S#]`? Does it *connect* sources (using words like "therefore," "extends," "however")
rather than list them? Those two together — grounded *and* woven — are the bar this stage aims
for.

---

## You should now be able to say…

- What Stage 2 receives: sources (citable) + study map (scaffold, not citable) + a weave-and-
  cite instruction.
- The two disciplines that keep "weave" honest: cite only `[S#]`, and keep Course 1's refusal
  rule — reasoning improves organization, not boldness.
- Why Stage 2 reuses the Course 1 system prompt: so the grounding contract never drifts between
  single-pass and reasoning modes.

Next: **[2.4 — Checking yourself, and the rule that didn't change](02-4-verify-and-default-deny.md)**.
