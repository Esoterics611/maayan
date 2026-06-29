# Lesson 0.3 — Feel the difference

> Module 0, Lesson 3 · ~15 min, mostly hands-on (needs a generation backend).
> The one question this answers: **what does the upgrade actually feel like — same question,
> old way vs. new way?**

Concepts land harder once you've seen them. Before we open any box, run one question three ways
and watch each move switch on. Keep this terminal session; we'll refer back to it.

> **Backend note.** The `--reason` runs make real model calls, so you need OpenRouter
> (`OPENROUTER_API_KEY`) or local Ollama configured. The `--expand` retrieval effect you can
> also see in `search`-style output with no backend, via lexicon-only expansion (Lesson 1.3).

---

## The three runs

Pick the conceptual question you used in Lesson 0.1. Run these in order.

**Run A — plain (Course 1 behavior):**

```bash
uv run maayan ask "מה הקשר בין צמצום לבריאת העולם"
```

This is single-shot: one query, one answer. Note the **Sources** list and the answer's shape.

**Run B — add expansion:**

```bash
uv run maayan ask "מה הקשר בין צמצום לבריאת העולם" --expand
```

`--expand` turns on Move 1. Look at the **Sources** list now: it's the RRF-fusion of several
queries (lexicon + reformulations + HyDE). Did a source appear that Run A missed? Did the order
shift toward more obviously-relevant passages?

**Run C — add reasoning, and reveal the study map:**

```bash
uv run maayan ask "מה הקשר בין צמצום לבריאת העולם" --expand --reason --show-reasoning
```

`--reason` turns on Move 2; `--show-reasoning` prints the **study map** the model built before
writing. Read the map first: one line per source, then the agreements/tensions. Then read the
answer — notice it now *weaves* the sources (following the map) rather than listing them.

---

## What you just saw

| Run | Flags | What changed |
|---|---|---|
| A | *(none)* | The baseline: one query, one generation. |
| B | `--expand` | A wider, fused candidate set — better/more sources, often a different #1. |
| C | `--expand --reason --show-reasoning` | A two-stage answer: an explicit study map, then a woven, cited synthesis. |

Add `--verify` to Run C and you'll also get a **⚠ Claims not clearly supported…** section if the
model finds any unsupported sentence — Move 3.

> ### Under the hood — flags vs. `.env`
> The `--expand/--reason/--verify` flags are *per-call overrides*. With no flag, each mode falls
> back to its config default (`QUERY_EXPAND_ENABLED`, etc.). So you can leave the system in
> Course-1 mode globally and opt into intelligence only when you want it — or flip the `.env`
> switches once you've decided (Module 4) that a mode earns its cost (Module 3).

---

## Hands-on

1. Do the three runs above on **two** different questions: one conceptual (where you expect a
   big difference) and one whose answer is a single well-known passage (where you might not).
   Expansion and reasoning help most on the conceptual one — start noticing *when* the upgrade
   pays off. That instinct is what Module 3 makes quantitative.
2. Run C once more with `--no-reason` but keep `--expand`. Confirm the study map disappears but
   the fused sources remain — the two moves are independent.

---

## You should now be able to say…

- What each flag does to a live `ask`, and that they compose independently.
- The difference you can *see*: expansion changes the **sources**; reasoning changes the
  **answer's shape** (and reveals a study map); verify adds a **flag list**.
- That flags are per-call overrides of the `.env` defaults — opt in without changing the
  system's resting behavior.

Next: **[1.1 — Why a verbatim query under-retrieves](01-1-verbatim-underretrieves.md)** — open
the first box.
