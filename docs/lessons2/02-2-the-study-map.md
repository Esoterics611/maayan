# Lesson 2.2 — The study map

> Module 2, Lesson 2 · ~12 min read + a hands-on (needs a backend).
> The one question this answers: **what is the "study map" Stage 1 produces, and why is it the
> most chassidus-shaped part of the entire system?**

Stage 1 of the reasoning path has exactly one job: read the retrieved sources and lay out how
they relate. The artifact it produces — the **study map** — is small, but it's where "lookup"
becomes "learning."

---

## What ANALYZE is told to do

The prompt is deliberately narrow ([generate/rag.py](../../maayan/generate/rag.py)):

```python
ANALYZE_SYSTEM_PROMPT = (
    "... Read the numbered SOURCES and produce a concise STUDY MAP ...\n"
    "1. For each source, one line: its tag then its core claim in your words, e.g. '[S1] — ...'.
        Use ONLY what the source says; add no outside facts.\n"
    "2. Then, briefly: where sources AGREE, where one BUILDS ON another, and any TENSION/
        disagreement between them. Refer to sources by their [S#] tags.\n"
    "3. Do NOT answer the question yet and do not invent mekoros. Keep it tight."
)
```

Two parts: a one-line **claim per source**, then the **relationships** — agree / builds-on /
tension. The user message (`build_analyze_messages`) hands it the numbered sources *and* the
question, so the map is oriented toward what's being asked, not a generic summary.

Three guardrails are baked in, and they're the same trust rules as everywhere else: *only what
the source says*, *refer by [S#]*, *don't invent mekoros*, *don't answer yet*. The map is
analysis, not opinion.

---

## Why this is the chassidus move

Stop and notice what the second part of the map asks for: **where sources agree, where one
builds on another, and where they're in tension.** That is precisely the work of a chavrusa
learning a sugya — not "what does each source say" (a student can read), but "**how do they fit
together**." A maamar develops by building one source on another, resolving an apparent tension,
showing that two statements are really one idea at different levels. The study map makes the
system attempt *that* move explicitly, before it commits to an answer.

This is why reasoning matters more here than in a generic Q&A bot. For factual lookup, "how the
sources relate" is often trivial. For p'nimiyus haTorah, it's the whole game. The study map is
the system's first genuine attempt to *learn*, not just *retrieve* — and because it's returned
to you, you can judge that attempt directly.

> ### Under the hood — the map is never citable, and never the answer
> The study map is the model's *own* analysis, so the next stage is forbidden to cite it (Lesson
> 2.3): only the numbered `[S#]` sources are citable. And ANALYZE is told "do NOT answer the
> question yet" — if you ever see the map starting to *argue* rather than *map*, that's a prompt
> you can tighten (Lesson 4.2). Keeping the two stages cleanly separated is what makes each one
> good.

---

## Hands-on

Backend required.

**1. Read a study map.** Print it with `--show-reasoning`:

```bash
uv run maayan ask "מה הקשר בין צמצום לבריאת העולם" --reason --show-reasoning
```

The **Study map:** block prints before the answer. Read it as a scholar would:
- Is each `[S#]` claim *faithful* to that source (cross-check one against the **Sources** list)?
- Do the agreement/tension notes ring true, or is the model forcing a connection? (Forced
  connections are the failure mode to watch — Lesson 4.2.)

**2. See the map drive the answer.** Re-read the answer and find where it *follows* the map —
e.g., the map says "[S2] builds on [S1]," and the answer presents them in that order, connected.
When the answer is good, you can usually trace it back to a good map; when it's off, the map
usually shows you why. That traceability is the practical payoff of making reasoning explicit.

---

## You should now be able to say…

- What the study map contains: one faithful claim per source, then agreements / builds-on /
  tensions, oriented to the question.
- Why it's the most chassidus-shaped move: "how the sources fit" is the substance of learning
  p'nimiyus haTorah, and the map attempts exactly that.
- That the map is analysis (never citable, never the answer) and is returned to you so the
  reasoning is inspectable.

Next: **[2.3 — Synthesis: weave, don't list](02-3-synthesis-weave.md)** — turning the map into a
grounded answer.
