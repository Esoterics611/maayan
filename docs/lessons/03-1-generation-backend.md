# Lesson 3.1 — The generation backend (a swappable box)

> Module 3, Lesson 1 · ~15 min read + a short hands-on.
> The one question this answers: **which part of the system actually talks to the language
> model, and why can I swap that model (cloud ↔ local) without touching anything else?**

We've reached the "G." Retrieval (Modules 1–2) hands us the relevant passages; now something
has to *compose* an answer from them. That composing is the one job that uses a large language
model, and — recall "what runs where" from Lesson 0.2 — it's the one step that may leave your
machine. Before we look at *how* the answer is grounded and cited (Lesson 3.2) or *how it
refuses* (3.3), we need to see the **box** that the model lives behind. Because maayan treats
it as exactly that: a box with one slot, interchangeable.

---

## One tiny interface, two implementations

Open [maayan/generate/base.py](../../maayan/generate/base.py). The entire contract for "a
thing that can talk to a language model" is this:

```python
class GenerationBackend(Protocol):
    def generate(self, system: str, messages: Sequence[Message]) -> str: ...
```

That's it. A backend takes a system prompt and a list of messages, and returns text. Anything
that can do that *is* a generation backend. There are two real ones:

| Backend | File | Runs | Default model |
|---|---|---|---|
| `OpenRouterBackend` | [openrouter.py](../../maayan/generate/openrouter.py) | **cloud** (OpenRouter) | `qwen/qwen-2.5-72b-instruct` |
| `OllamaBackend` | [ollama.py](../../maayan/generate/ollama.py) | **local** (your machine) | `qwen2.5:7b-instruct` |

Open both. They look completely different inside — one uses the OpenAI client pointed at
OpenRouter's URL; the other POSTs to a local Ollama HTTP endpoint. But they expose the *exact
same* `generate(system, messages) -> str`. That sameness is the whole point.

---

## Why a *protocol*, and why it matters here

The RAG service (the thing you'll meet in 3.2–3.3) never says "call OpenRouter." It says "call
*a* `GenerationBackend`." Which concrete one it gets is decided once, at the edge, by config:

Open [maayan/generate/factory.py](../../maayan/generate/factory.py). `build_generation_backend`
reads `generation_backend` (`"openrouter"` or `"ollama"`) and constructs the matching box. The
default is `openrouter`. Flip the config to `ollama` and **every other line of code stays the
same** — retrieval, grounding, citation extraction, the refusal gate, the CLI, the UI: none of
them know or care which model answered.

> ### Under the hood — this is dependency injection, early
> This is the clearest possible example of the house rule you'll study in Module 5:
> *construction happens at the edges; logic depends on interfaces.* The factory (an edge)
> builds the concrete backend; the `RAGService` (logic) is *handed* one. Because the seam is a
> protocol, three things become free: (1) **swap** cloud ↔ local by config; (2) **test**
> grounding and refusal with a fake backend that returns a canned string — no network, no key,
> per the house rules; (3) **add** a future backend (Anthropic, a different host) by writing
> one class and one factory branch, touching nothing else. Notice the factory also refuses to
> build OpenRouter without an API key, and the key is read from config as a `SecretStr` —
> never hardcoded, never logged (another house rule).

---

## The trade-off the box hides

The reason maayan bothers to make this swappable is a real tension, spelled out in
[CLAUDE.md](../../CLAUDE.md):

- **OpenRouter (cloud):** stronger models (esp. on Hebrew), nothing to run locally — but it's a
  network call to a third party, costs money, and your question leaves the machine.
- **Ollama (local):** fully offline, private, free — but smaller models are weaker, especially
  on Hebrew.

You don't have to choose forever. The architecture lets you run cloud today and flip to local
the day privacy or cost demands it. And — crucially — **the trust guarantees don't depend on
which you pick.** Grounding, citations, and default-deny (the rest of this module) sit *outside*
the box, in the RAG service. A weaker local model might write a clumsier answer, but it still
can't answer from sources that weren't retrieved, and it still refuses when there's nothing.
That's by design: the backbone is RAG, not the model.

---

## Hands-on

This lesson is about *seeing the seam*, not running a swap (that's Module 7.3).

1. **Confirm the shared shape.** Open `openrouter.py` and `ollama.py` side by side. Find the
   `generate(` method in each. Confirm they take the same arguments and return a `str`, despite
   doing entirely different things inside. That identical signature *is* the swap point.

2. **Find the one switch.** In [config.py](../../maayan/config.py), find `generation_backend`
   (and notice the `generation_model` helper property next to it). This single field is the
   only thing that changes to move between cloud and local. Read its description.

3. **Trace who depends on what.** Search `rag.py` for the word `OpenRouter`. You won't find it —
   `RAGService` imports only `GenerationBackend` (the protocol). Write one sentence: *why is it
   important that the RAG logic never names a concrete backend?* (You're previewing the answer
   to Module 5.1.)

---

## You should now be able to say…

- That generation is isolated behind a one-method `GenerationBackend` protocol, with cloud
  (OpenRouter) and local (Ollama) implementations.
- That `generation_backend` in config selects which is injected, with **no other code change** —
  and that the API key is a secret read from config, never hardcoded.
- The cloud-vs-local trade-off (quality vs. privacy/cost/offline), and why the **trust
  guarantees live outside the box**, so they hold either way.

Next: **[3.2 — The grounded prompt & citations](03-2-grounded-prompt.md)** — now we look
*inside* the call: how retrieved sources become a numbered, citable block, and how every `[S#]`
in the answer resolves back to a real ref.
