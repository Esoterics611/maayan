# Lesson 4.1 — The knobs, and recipes

> Module 4, Lesson 1 · ~12 min read + a hands-on.
> The one question this answers: **what does every new setting do, and what are some good
> ready-made combinations for different situations?**

Everything in Course 2 is config-driven (the house rule from Course 1, Module 5 — nothing
hardcoded). Here's the full panel of new dials and four recipes that combine them well. All live
in [config.py](../../maayan/config.py) and [.env.example](../../.env.example).

---

## The dials

| Setting | Default | What it does |
|---|---|---|
| `QUERY_EXPAND_ENABLED` | `false` | Master switch for Move 1. Off → plain Course-1 retrieval. |
| `QUERY_EXPAND_LEXICON` | `true` | Include the free, deterministic lexicon expander (when expand on). |
| `QUERY_EXPAND_HYDE` | `true` | Add the HyDE hypothetical-passage query (1 model call; needs a backend). |
| `QUERY_EXPAND_VARIANTS` | `3` | How many LLM reformulations to request (`0` = none; needs a backend). |
| `QUERY_EXPAND_MAX_QUERIES` | `6` | Hard cap on total queries after dedupe (incl. the original). |
| `RAG_REASONING_ENABLED` | `false` | Master switch for Move 2 (analyze → synthesize). |
| `ANSWER_VERIFY_ENABLED` | `false` | Master switch for Move 3 (flag unsupported claims). |

Two interactions worth internalizing:

- **`MAX_QUERIES` is your spend cap on width.** Lexicon + variants + HyDE + original can exceed
  it; the cap (after dedupe) keeps any one ask from ballooning into many retrievals.
- **Expansion with `variants=0` + `hyde=false` = lexicon-only**, which costs **zero model
  calls** (Lesson 3.1). That's how you get "free" widening even with a backend configured.

---

## Four recipes

Set these in `.env` (CLI flags override per-call when you want to deviate).

**1. Cheap & fast** — wider net, one generation, minimal extra cost:
```
QUERY_EXPAND_ENABLED=true
QUERY_EXPAND_VARIANTS=2
QUERY_EXPAND_HYDE=false
RAG_REASONING_ENABLED=false
ANSWER_VERIFY_ENABLED=false
```

**2. Lexicon-only** — zero added model calls; leans entirely on your curated terms:
```
QUERY_EXPAND_ENABLED=true
QUERY_EXPAND_LEXICON=true
QUERY_EXPAND_VARIANTS=0
QUERY_EXPAND_HYDE=false
```

**3. Deep & thorough** — the full chavrusa, for questions you'll act on or publish:
```
QUERY_EXPAND_ENABLED=true
QUERY_EXPAND_VARIANTS=4
QUERY_EXPAND_HYDE=true
RAG_REASONING_ENABLED=true
ANSWER_VERIFY_ENABLED=true
```

**4. Local model (Ollama)** — private/offline; keep it lean because small models tire:
```
GENERATION_BACKEND=ollama
OLLAMA_MODEL=qwen2.5:7b-instruct
QUERY_EXPAND_ENABLED=true
QUERY_EXPAND_VARIANTS=2
RAG_REASONING_ENABLED=true     # try it; if study maps are thin, set false
```
A smaller local model writes weaker reformulations and thinner study maps, especially in Hebrew
(the same tradeoff Course 1 flagged for the Ollama swap). Measure with `eval-expand` and trust
the numbers, not the recipe.

---

## Hands-on

**1. Apply a recipe and feel it.** Put **Recipe 1** in `.env`, then run a normal `ask` (no
flags) and confirm it now expands by default:

```bash
uv run maayan ask "מה הקשר בין צמצום לבריאת העולם"   # uses .env defaults now
```

**2. Override per call.** With Recipe 1 still in `.env`, force the full treatment on one
question without editing config:

```bash
uv run maayan ask "..." --reason --verify --show-reasoning
```

Flags beat `.env`. That's your everyday workflow: a sensible default in `.env`, the big guns on
demand.

**3. Justify it.** Before committing a recipe globally, run `eval-expand` (Lesson 3.2) under it.
Keep the recipe only if the numbers agree.

---

## You should now be able to say…

- What every new dial does, and the two key interactions (`MAX_QUERIES` as a width cap;
  `variants=0 + hyde=false` = free lexicon-only expansion).
- Four working recipes and the situation each fits.
- The workflow: a default recipe in `.env`, per-call flag overrides, and `eval-expand` to justify
  going global.

Next: **[4.2 — Editing the prompts (and diagnosing failures)](04-2-prompts-and-failures.md)**.
