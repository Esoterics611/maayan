# Lesson 4.2 — Editing the prompts (and diagnosing failures)

> Module 4, Lesson 2 · ~14 min read + a hands-on.
> The one question this answers: **the analyze/synthesis/verify prompts are just strings — how
> do I safely change them to fit my taste, and how do I recognize and fix the common failure
> modes?**

The deepest tuning isn't a config number — it's the *prompts*. maayan keeps them injectable, not
hardcoded, exactly so you can shape the model's behavior without forking the logic. This lesson
shows how, and catalogs what goes wrong.

---

## The prompts are injectable, by design

Every reasoning prompt is a constructor argument with a sensible default. `RAGService` takes
`analyze_prompt=` and `verify_prompt=` (defaulting to `ANALYZE_SYSTEM_PROMPT` /
`VERIFY_SYSTEM_PROMPT` in [generate/rag.py](../../maayan/generate/rag.py)); the expanders take
`multi_query_system_prompt=` / `hyde_system_prompt=`. So you override a prompt by *passing a
different string* — never by editing library code:

```python
rag = RAGService(retriever, backend, score_threshold=0.45,
                 reasoning=True,
                 analyze_prompt=MY_ANALYZE_PROMPT)   # your wording, same machinery
```

This is the DI house rule (Course 1, Module 5) doing real work: behavior is data you inject, so
you can experiment freely and A/B the result with `eval`-style runs, with zero risk to the
defaults everyone else uses.

When you edit a prompt, **keep the contract**: the analyze prompt must still say *only the
sources, refer by [S#], don't answer yet*; the verify prompt must still emit `OK` or one
sentence per line (that's what `parse_unsupported` expects). Change the *style* and *emphasis*,
not the *interface*.

---

## The failure catalog

Three things go wrong in practice. Each has a tell and a fix.

**1. Over-expansion drowns the signal.** Too many/too-broad queries pull in loosely-related
passages; RRF's consensus reward then floats generic chunks to the top, and `eval-expand` shows
recall flat or the refusal rate dropping.
- *Tell:* sources drift off-topic; `eval-expand` refusal rate falls on negatives.
- *Fix:* lower `QUERY_EXPAND_VARIANTS`, lower `QUERY_EXPAND_MAX_QUERIES`, or tighten the
  multi-query prompt to demand *on-topic* rephrasings only.

**2. The study map argues instead of mapping.** A weak or over-eager model starts answering in
Stage 1 — the map editorializes, or asserts connections the sources don't support.
- *Tell:* `--show-reasoning` shows a map that reads like a mini-essay, or claims tensions/links
  you can't find in the sources.
- *Fix:* strengthen "do NOT answer yet" and "use ONLY what the source says" in the analyze
  prompt; on a small local model, consider turning reasoning off (Lesson 4.1).

**3. The verifier flags everything (or nothing).** Some models are trigger-happy citation
checkers; others rubber-stamp.
- *Tell:* every answer shows a long ⚠ list (false alarms), or a clearly-overstated answer shows
  none.
- *Fix:* in the verify prompt, sharpen what "supported" means (e.g. "a claim is supported if the
  cited source states or directly implies it; minor paraphrase is fine"); or accept that on a
  weak model, verify is noise and leave it off.

A fourth, quieter one: **forced connections.** Reasoning's superpower — relating sources — is
also its temptation; the model may manufacture a link to seem insightful. The study map makes
this *visible* (you can read the claimed connection and check it), which is the best defense.
Trust the map you can audit over an answer you can't.

> ### Under the hood — why flag-only verify is the safe default
> Note we never let verify *rewrite* the answer (Lesson 2.4). A model confident enough to flag a
> claim is not necessarily right that it's unsupported — so we surface the doubt to you rather
> than act on it. If you ever wanted auto-correction, that's a *new* feature with its own risks,
> not a tweak to this one.

---

## Hands-on

**1. Inject a custom analyze prompt and compare maps.** Try making the map terser:

```bash
uv run python - <<'PY'
from maayan.config import Settings
from maayan.generate.factory import build_generation_backend
from maayan.retrieve.factory import build_retriever
from maayan.generate.rag import RAGService

TERSE = ("Produce a STUDY MAP: one line per source as '[S#] — claim' (max 12 words each), "
         "then a single line naming the key agreement and the key tension by [S#]. "
         "Use ONLY the sources. Do not answer the question.")

s = Settings(); backend = build_generation_backend(s)
r = build_retriever(s)
for label, prompt in [("default", None), ("terse", TERSE)]:
    rag = RAGService(r, backend, score_threshold=s.score_threshold, reasoning=True,
                     **({} if prompt is None else {"analyze_prompt": prompt}))
    ans = rag.ask("מה הקשר בין צמצום לבריאת העולם")
    print(f"\n=== {label} map ===\n{ans.reasoning}")
PY
```

Read both maps. Which scaffolds a better answer for *your* taste? That judgment, made on your own
corpus, is the real tuning.

**2. Provoke a failure on purpose.** Crank `QUERY_EXPAND_VARIANTS=8` and re-run
`eval-expand --crosstext`. Watch whether recall actually keeps rising or whether the refusal rate
starts slipping — see over-expansion in your own numbers, then dial back.

---

## You should now be able to say…

- That every reasoning/expansion prompt is **injectable** (a constructor arg), so you tune
  behavior by passing strings — never editing logic — while keeping each prompt's *contract*.
- The failure catalog and each one's tell + fix: over-expansion, an arguing study map, a
  mis-calibrated verifier, and forced connections.
- Why flag-only verify is the safe default, and why an auditable study map is your best defense
  against manufactured connections.

Next: **[5.1 — The five-minute demo](05-1-the-demo.md)** — now show it to someone.
