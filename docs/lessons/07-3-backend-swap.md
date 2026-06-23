# Lesson 7.3 — Choosing & swapping the generation backend

> Module 7, Lesson 3 · ~15 min read + an optional hands-on swap.
> The one question this answers: **cloud or local for generation — how do I decide, and how do I
> actually flip it?**

In Lesson 3.1 you saw *why* the generation backend is swappable (the `GenerationBackend` protocol
+ DI). This lesson is the operator's side: *which* to run, the trade-offs, and the literal steps
to switch — proving the architecture's promise that no other code changes.

---

## The decision, in one table

| | OpenRouter (cloud, default) | Ollama (local) |
|---|---|---|
| **Quality** | stronger models, better Hebrew | smaller models, weaker — esp. Hebrew |
| **Privacy** | question leaves your machine | fully offline; nothing leaves |
| **Cost** | per-call (API) | free after download |
| **Setup** | an API key | install Ollama + pull a model |
| **Default model** | `qwen/qwen-2.5-72b-instruct` | `qwen2.5:7b-instruct` |

[CLAUDE.md](../../CLAUDE.md) states the trade-off bluntly: Ollama is "offline + private + free,
but smaller models are weaker, especially on Hebrew." There's no universally right answer —
choose by what you're optimizing. Drafting offline on a plane, or working with sensitive
material? Local. Want the best Hebrew composition and don't mind a cloud call? Cloud.

**The part that doesn't change either way:** RAG, citations, and default-deny are the backbone
*regardless* of backend (Lesson 3.1's "trust guarantees live outside the box"). A local model
might write a clumsier answer, but it still can't cite a source that wasn't retrieved, and it
still refuses when there's nothing. You're choosing the *writer*, not the *rules*.

---

## How to swap (two config lines)

This is the whole switch, and it's the proof of Lesson 3.1:

```bash
# 1. install Ollama and pull an open instruct model (one-time)
ollama pull qwen2.5:7b-instruct

# 2. point maayan at it — in .env:
GENERATION_BACKEND=ollama
OLLAMA_MODEL=qwen2.5:7b-instruct       # (the default; shown for clarity)
```

That's it. `build_generation_backend` (Lesson 3.1) reads `generation_backend` and constructs
`OllamaBackend` instead of `OpenRouterBackend`. Retrieval, grounding, citation extraction, the
default-deny gate, the CLI, the UI — **none of them change**. You can flip back by setting
`GENERATION_BACKEND=openrouter`. The relevant knobs:

| Knob | Cloud | Local |
|---|---|---|
| `generation_backend` | `openrouter` | `ollama` |
| model | `openrouter_model` | `ollama_model` |
| endpoint | `openrouter_base_url` | `ollama_base_url` (`http://localhost:11434`) |

> ### Under the hood — same protocol, different transport
> Recall the two implementations (Lesson 3.1): `OllamaBackend` POSTs to a local
> `/api/chat` endpoint; `OpenRouterBackend` uses the OpenAI client against OpenRouter's URL. Both
> satisfy `generate(system, messages) -> str`. The `generation_model` helper property on
> `Settings` even returns the right model id for whichever backend is active, so display code
> ("answer by <model>") works unchanged. This is dependency injection earning its keep
> operationally: a capability swap is a config edit, because the seam was a protocol from day one.

The [RUNBOOK troubleshooting](../RUNBOOK.md) section covers the common local-backend snags
(Ollama not running, model not pulled, slower responses).

---

## Hands-on

The decision matters more than the mechanics here, so this one is read-and-reason, with an
optional real swap.

1. **Make the call for your situation.** Given how *you* use maayan — sensitivity of material,
   internet availability, how much Hebrew quality matters — which backend fits? Write one
   sentence justifying it against the table.

2. **Find the swap point in code.** Open [generate/factory.py](../../maayan/generate/factory.py).
   Locate the `if backend == "ollama":` branch. Confirm: this *one function* is the only place
   that decides cloud vs. local. Everything downstream is backend-agnostic.

3. **(Optional) Actually swap.** If you have Ollama installed: `ollama pull qwen2.5:7b-instruct`,
   set `GENERATION_BACKEND=ollama` in `.env`, and re-run a question you asked before:

   ```bash
   uv run maayan ask "מה ההבדל בין צדיק לבינוני?"
   ```

   Compare the answer's quality to the cloud version. Note that it still cites real refs and would
   still refuse an unsupported question — the rules held; only the writer changed. Set it back
   when done.

---

## You should now be able to say…

- The cloud-vs-local trade-off (quality vs. privacy/cost/offline) and that there's no universal
  right answer — choose by what you optimize.
- That the **trust guarantees (RAG, citations, default-deny) hold regardless of backend** — you
  swap the writer, not the rules.
- The exact swap: `GENERATION_BACKEND` (+ model/endpoint) in `.env`, with **no other code
  change** — the operational proof of Lesson 3.1's DI design.

Next: **[7.4 — Growing the corpus](07-4-growing-the-corpus.md)** — adding more text, whether it's
on Sefaria (config) or somewhere else entirely (the chabad adapter).
