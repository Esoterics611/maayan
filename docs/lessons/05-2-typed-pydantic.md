# Lesson 5.2 — Typed throughout, pydantic at every boundary

> Module 5, Lesson 2 · ~15 min read + a hands-on at the terminal.
> The one question this answers: **why is every piece of data that moves between modules a
> typed model instead of a plain dict — and what does `mypy --strict` actually catch?**

In 5.1, DI let you swap and fake collaborators. This lesson is the other guardrail that lets
you change code without fear: **types**. maayan is typed end to end and checked in strict mode,
and every datum that crosses a module boundary is a **pydantic model**, not a loose dict or
tuple. This is house rule #1, and once you feel it, you'll miss it everywhere else.

---

## The rule

From [CLAUDE.md](../../CLAUDE.md), house rule #1:

> **Typed throughout, mypy-clean.** `mypy` runs in strict mode. Every datum that crosses a
> module boundary is a **pydantic model**, not a loose dict/tuple.

Two halves. **Typed throughout** means function signatures declare what they take and return,
and a type checker verifies the whole graph hangs together. **Pydantic at the boundary** means
when data leaves one module for another, it travels as a *named, validated model* — `Chunk`,
`SearchResult`, `Embedding`, `Answer`, `RetrievalResult`, `GoldExample` — never an anonymous
`dict[str, Any]` that the receiver has to guess the shape of.

---

## Why a model and not a dict

You've already met the spine of models: `Chunk` (1.2), `Embedding` (1.1), `SearchResult` /
`RetrievalResult` (2.3), `Answer` / `ContextTurn` (3.2–3.4), `GoldExample` (4.1). Imagine the
alternative — passing a bare dict between modules:

```python
# the dict way (NOT how maayan does it):
result = {"ref": "...", "txt": "...", "score": 0.5}   # was it "txt" or "text"? str or float?
...
score = result["scor"]   # typo. KeyError at runtime, in production, on Shabbos.
```

Versus the model way (how it *is* done — see [retrieve/models.py](../../maayan/retrieve/models.py)):

```python
class SearchResult(BaseModel):
    ref: str
    text: str
    score: float
    lang: str
    source: str
    payload: dict[str, Any]
```

Now the field is `text`, always; it's a `str`, always; `score` is a `float`, always. A typo
(`result.scor`) is caught by mypy *before the code runs*, not by a user hitting a `KeyError`.
And the model is **self-documenting**: you read `SearchResult` and you know exactly what a
result is, without spelunking through the code that produced it. The model *is* the contract
between the producer and every consumer.

> ### Under the hood — pydantic also *validates*
> A pydantic model isn't just a type hint; at construction it **checks** the data. Build a
> `SearchResult` with `score="high"` and it raises immediately, at the boundary, with a clear
> error — rather than letting a bad value flow three modules downstream and corrupt something
> subtle. So the boundary models do double duty: they're the *static* contract mypy verifies,
> and the *runtime* gate that rejects malformed data the moment it tries to cross. This is
> exactly why the house rule targets *boundaries* specifically — that's where data from the
> outside world (Sefaria, the model, the UI) enters and must be trusted.

---

## What `mypy --strict` buys you

Strict mode means mypy won't let you be vague: no implicit `Any`, no untyped function, no
silently-ignored `None`. Run it:

```bash
make typecheck
```

It checks the *entire* call graph for consistency. The practical payoff, in the context of
everything you've learned:

- **Refactor without fear.** Rename `SearchResult.text` and mypy lists every site that must
  change — across `retrieve`, `generate`, `cli`, `ui`. You're never hunting for a missed caller.
- **The protocols are enforced.** Remember the DI seams from 5.1 (`Embedder`,
  `GenerationBackend`, …)? mypy checks that every concrete implementation *actually* matches its
  protocol — so "drop-in replacement" is a guarantee, not a hope. A backend missing a method, or
  with the wrong signature, fails `make typecheck`.
- **`None` is handled on purpose.** Strict mode forces you to deal with the "what if it's
  missing?" case, which is exactly where sloppy code crashes.

This is why "definition of done" in CLAUDE.md includes `make typecheck` being clean, right next
to tests passing.

---

## Hands-on

1. **Run the checker.** From the repo root:

   ```bash
   make typecheck
   ```

   It should be clean (that's the standard the repo holds). Note that it checks *all* of
   `maayan/`, not just files you touched.

2. **Break it on purpose, then read the error.** Open [retrieve/models.py](../../maayan/retrieve/models.py)
   and temporarily rename `SearchResult.text` to `txt`. Run `make typecheck` again. Read the
   errors: mypy points at *every* place that used `.text` — `build_context` in `rag.py`, the CLI
   printing, etc. That list is the exact blast radius of the change. **Revert** the rename
   (`git checkout maayan/retrieve/models.py`).

3. **See validation reject bad data.** At the runtime layer:

   ```bash
   uv run python - <<'PY'
   from maayan.retrieve.models import SearchResult
   try:
       SearchResult(ref="x", text="t", score="high", lang="he", source="sefaria", payload={})
   except Exception as e:
       print("rejected at the boundary:", type(e).__name__)
   PY
   ```

   `score="high"` is rejected immediately — the model won't let a malformed value cross. That's
   the runtime half of the guarantee.

---

## You should now be able to say…

- House rule #1: **typed throughout, mypy-strict, pydantic at every boundary** — and why
  boundaries specifically.
- Why a boundary **model** beats a bare dict (typo-proof, self-documenting, *validated*).
- What `mypy --strict` buys you: fearless refactors, enforced protocols, deliberate `None`
  handling — and that `make typecheck` clean is part of "done."

Next: **[5.3 — Config-driven everything](05-3-config-driven.md)** — the third house rule: every
tunable number lives in one `Settings`, never hardcoded in logic.
