# Lesson 0.2 — The three moves (the map)

> Module 0, Lesson 2 · ~10 min read + a config skim.
> The one question this answers: **what exactly did Prompt 31 add, and how do the pieces fit
> together into the upgraded `ask`?**

Before we zoom into each technique, hold the whole picture. Prompt 31 inserts three moves
around the engine you already have. Here's the new shape, with the old one shown for contrast:

```
OLD:  question ─────────────► embed once ► search ► [gate] ► generate ──────────────► answer

NEW:  question ► EXPAND ► embed each ► search each ► FUSE ► [gate] ► ANALYZE ► SYNTHESIZE ► VERIFY ► answer
                 (1)                                          (2)         (2)        (3)
```

Three moves, numbered to the modules that teach them.

---

## Move 1 — Expand (ask better) · Module 1

Instead of one query, produce several and fuse the results:

- **Lexicon expansion** — deterministic, no model call: if a curated term appears in the
  question, inject its canonical form and related terms.
- **Multi-query** — ask the model for a few rephrasings and sub-angles.
- **HyDE** — ask the model to draft a *hypothetical source passage*, and search with that.

All the resulting hit-lists are merged with **Reciprocal Rank Fusion** (RRF). A passage found
by several queries rises; the net is wider, so good sources stop slipping through.

## Move 2 — Reason (think before answering) · Module 2

Split the single generation into two stages:

- **Analyze** — read the numbered sources and produce a **study map**: each source's claim,
  then where they agree, build, and conflict.
- **Synthesize** — write one woven, cited answer *from* that map, instead of summarizing
  sources one by one.

## Move 3 — Verify (check yourself) · Module 2.4

After the answer is written, optionally ask the model to flag any sentence its cited sources
don't actually support. Flag-only — it never silently rewrites your answer.

---

## The one thing none of them touch

The **default-deny gate** sits exactly where it always did — *after* retrieval, *before* any
generation. Expansion feeds it more candidates but doesn't lower the bar; reasoning and verify
happen only *after* the gate has decided to answer. If retrieval finds nothing relevant, the
system still refuses **without calling the model at all** — same as Course 1. We prove this in
Lesson 2.4.

That's the design rule of the whole upgrade: **add intelligence around the trust core, never
through it.**

---

## Everything is off by default

Each move is gated by config and defaults to **off**, so your system behaves exactly as it did
after Course 1 until you opt in — per call with flags, or globally in `.env`.

## Hands-on

Skim the new settings so the names are familiar when we use them. Open
[.env.example](../../.env.example) and find the two new blocks, or list them from config:

```bash
uv run python - <<'PY'
from maayan.config import Settings
s = Settings()
for k in ("query_expand_enabled", "query_expand_lexicon", "query_expand_hyde",
          "query_expand_variants", "query_expand_max_queries",
          "rag_reasoning_enabled", "answer_verify_enabled"):
    print(f"{k:28} = {getattr(s, k)!r}")
PY
```

Note they're all `False`/defaults — the system is in its Course-1 behavior right now. Map each
name to a move: the `query_expand_*` family is **Move 1**, `rag_reasoning_enabled` is **Move
2**, `answer_verify_enabled` is **Move 3**.

---

## You should now be able to say…

- The new pipeline shape: **expand → fuse → [gate] → analyze → synthesize → verify**.
- Which move each config family controls, and that all default to **off**.
- The governing rule: intelligence is added **around** the default-deny trust core, never
  through it — retrieval still gates before any model call.

Next: **[0.3 — Feel the difference](00-3-feel-the-difference.md)** — run the same question
three ways and watch the upgrade happen.
