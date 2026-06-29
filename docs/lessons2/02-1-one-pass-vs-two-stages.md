# Lesson 2.1 — One pass vs. two stages

> Module 2, Lesson 1 · ~12 min read + a hands-on (needs a backend).
> The one question this answers: **what changes when the model *thinks before it writes* — and
> why does splitting one generation into two raise the quality of the answer?**

Module 1 got the right sources in front of the model. Module 2 is about what the model *does*
with them. The single-shot system did one thing: sources in, answer out. The reasoning path
does two — and the split is the point.

---

## The shape change

Open `RAGService.ask` in [generate/rag.py](../../maayan/generate/rag.py). With reasoning on,
the body branches:

```python
if self._reasoning:
    reasoning_text = self._backend.generate(self._analyze_prompt, build_analyze_messages(sources, question))
    user_content   = self._synthesis_user_content(question, sources, reasoning_text, context_turns)
else:
    user_content   = self._answer_user_content(question, sources, context_turns)
text = self._backend.generate(self._system_prompt, [Message(role="user", content=user_content)])
```

- **Stage 1 — ANALYZE.** A first model call reads the numbered sources and produces a *study
  map* (Lesson 2.2): each source's claim, then how they relate.
- **Stage 2 — SYNTHESIZE.** A second call writes the answer, but now it's handed the sources
  **and** the study map, with instructions to *weave* (Lesson 2.3).

Single-shot is still the default (the `else` branch is byte-for-byte the Course 1 path). Turning
on `--reason` just inserts Stage 1 and feeds its output into Stage 2.

---

## Why two passes beat one

It's the same reason a person outlines before writing, or a chavrusa lays out the sugya before
drawing a conclusion. Asking a model to *understand* and *compose* in a single step makes it do
both at once, and it tends to shortchange the first — producing a tour of the sources
("Source 1 says X; Source 2 says Y") instead of an argument that uses them.

Separating the steps:

- **Forces structure first.** Stage 1's only job is to map the terrain — claims, agreements,
  tensions — with nothing else competing for attention. A better map means a better answer.
- **Gives Stage 2 a scaffold.** The synthesizer isn't staring at raw quotes; it's working from
  an explicit relational map, so it can *connect* rather than *list*.
- **Makes the reasoning inspectable.** The study map is returned to you (`Answer.reasoning`), so
  you can see *why* the answer says what it does — and catch a bad answer at its root (a wrong
  map) instead of guessing.

The cost is one extra model call per ask (Lesson 3.1 counts the whole ladder). That's the trade:
more tokens, a better and more transparent answer. You decide per question, per corpus.

---

## Hands-on

Backend required. Use a conceptual question with several relevant sources.

**1. Compare the shapes directly.**

```bash
uv run maayan ask "מה הקשר בין צמצום לבריאת העולם"                       # one pass
uv run maayan ask "מה הקשר בין צמצום לבריאת העולם" --reason             # two stages
```

Read both answers side by side. The single-pass one often *enumerates* sources; the reasoned
one more often *integrates* them ("X grounds Y, though Z qualifies it"). Note which you'd rather
hand a student.

**2. Confirm it's two calls.** A quick offline proof that reasoning adds exactly one generation,
using a fake retriever + a backend that counts calls:

```bash
uv run python - <<'PY'
from maayan.generate.rag import RAGService
from maayan.retrieve.models import RetrievalResult, SearchResult

class FakeRetriever:
    def retrieve(self, q, *, k=None, book=None, source=None):
        r = SearchResult(ref="Tanya 1:1", text="…", score=0.5, lang="he", source="sefaria", payload={"ref":"Tanya 1:1"})
        return RetrievalResult(results=[r], relevance=0.9)

class Counter:
    def __init__(self): self.n = 0
    def generate(self, system, messages): self.n += 1; return "answer [S1]."

for reasoning in (False, True):
    b = Counter()
    RAGService(FakeRetriever(), b, score_threshold=0.4, reasoning=reasoning).ask("q")
    print(f"reasoning={reasoning}: {b.n} model call(s)")
PY
```

You'll see `1` then `2`. That single extra call is the whole price of Stage 1.

---

## You should now be able to say…

- The two-stage shape: **ANALYZE** (sources → study map) then **SYNTHESIZE** (sources + map →
  answer), versus the single-shot default.
- *Why* two passes beat one: structure-first produces integration instead of enumeration, and
  the map makes the reasoning inspectable.
- The cost: exactly one extra model call, paid only when you opt in.

Next: **[2.2 — The study map](02-2-the-study-map.md)** — what Stage 1 actually produces, and why
it's the most chassidus-shaped move in the system.
