# Lesson 5.1 — Dependency injection: why nothing constructs its own collaborators

> Module 5, Lesson 1 · ~20 min read + a hands-on tracing one command.
> The one question this answers: **why does the business logic never build its own embedder,
> database, or model — and what does "passing them in" actually buy me?**

You've crossed into the second half of the curriculum. Modules 0–4 were *RAG, universal*. From
here it's *this* system — the engineering discipline that lets you change maayan without fear.
And the keystone of that discipline is **dependency injection (DI)**. You've already seen its
payoff three times (the swappable backend in 3.1, the fakeable embedder in 1.1, the in-memory
database in 2.1); this lesson names the pattern and shows you the seam.

---

## The rule, stated plainly

From [CLAUDE.md](../../CLAUDE.md), house rule #3:

> Services — embedder, Qdrant client, generation backend, clock, settings — are **passed in**,
> never constructed inside business logic. Construction happens at the edges (`cli.py`, the UI
> route wiring, tests).

That's the whole idea: **logic depends on interfaces; construction lives at the edges.** A
class that does real work (like `RAGService`) never says `OpenRouterBackend(...)`. It is
*handed* something that satisfies the `GenerationBackend` protocol and uses it. Who built it,
and which concrete type it is, is decided elsewhere — at the program's edge.

---

## What "the edge" looks like

Open [maayan/cli.py](../../maayan/cli.py) and read the `ask` command. Notice the shape — it's
the same every time:

```python
settings  = _cfg()                                   # 1. resolve config
embedder  = build_embedder(settings)                 # 2. build concrete services
retriever = build_retriever(settings, embedder=embedder)
backend   = build_generation_backend(settings)
rag = RAGService(retriever, backend, score_threshold=settings.score_threshold)  # 3. inject
... rag.ask(question, ...)                            # 4. run logic
```

The CLI is a **wiring harness**, nothing more — the file's own docstring says it "stays a thin
layer… No business logic lives here." It reads config, calls the `build_*` factories to
construct the real embedder / retriever / backend, and *injects* them into `RAGService`. The
service then just… uses what it was given. Every entrypoint (CLI command, UI route, test) does
this same construct-at-the-edge, inject-into-logic dance.

> ### Under the hood — the protocols are the seams
> Go back and notice how many *protocols* you've met: `Embedder` (1.1), `GenerationBackend`
> (3.1), `Reranker` (2.4), `Retrieving` (2.3), `Clock` (5.4). Each is a small interface that
> says "anything shaped like this will do." The business logic depends only on these shapes.
> The `build_*` factories (`build_embedder`, `build_generation_backend`, …) are the only places
> that name concrete classes, and they pick based on `Settings`. So the dependency graph points
> *inward* to interfaces, and construction sits *outward* at the edges. That's DI in one
> sentence.

---

## The three things DI buys you (you've already used all three)

This isn't architecture for its own sake. Every house value you've seen so far *is* DI paying
off:

| Benefit | Where you saw it | Why DI makes it free |
|---|---|---|
| **Swap** implementations by config | OpenRouter ↔ Ollama (3.1); server/in-memory Qdrant (2.1) | logic depends on the protocol, so the concrete type can change |
| **Test** with fakes — no network, no models | `FakeRetriever` + `RecordingBackend` (5.4) | inject a fake that satisfies the same protocol |
| **Reuse** a costly object across services | one embedder shared by retriever *and* capture in `ask` | the edge builds it once and hands it to both |

That third one is visible right in the `ask` command: `embedder = build_embedder(settings)` is
built **once** and passed to both `build_retriever(...)` and (later) the capture service. If
each service constructed its own embedder, you'd load bge-m3 twice. Because construction is at
the edge, the edge can be smart about sharing.

---

## Why this matters *here* specifically

maayan makes promises: it can run fully local (privacy), it refuses to fabricate (trust), and
every change ships with tests (the house rules). **None of those are achievable without DI.**
You can't swap to a local model if `RAGService` hardcodes OpenRouter. You can't *prove*
default-deny never calls the model (the test you'll read in 5.4) if you can't inject a fake
backend and assert it was never called. DI isn't decoration — it's the mechanism that makes the
system's guarantees *testable and swappable* instead of merely promised.

---

## Hands-on

Trace one `ask` from the edge to the logic. No need to run anything — follow the code.

1. **Find the construction.** In [cli.py](../../maayan/cli.py), in the `ask` command, list the
   four things that get built before `RAGService` is created (config, embedder, retriever,
   backend). These are the *dependencies*.

2. **Find the injection.** Locate the line `RAGService(retriever, backend, ...)`. The retriever
   and backend are *passed in*. Now open [rag.py](../../maayan/generate/rag.py) and read
   `RAGService.__init__` — confirm it just **stores** what it's handed (`self._backend = backend`)
   and never constructs anything itself.

3. **Prove the negative.** Search `rag.py` for `build_`, `OpenRouter`, and `Qdrant`. You won't
   find them. The logic file names *no* concrete collaborator and *no* factory — only protocols.
   That absence is the whole pattern.

4. **Spot the reuse.** Back in `ask`, find where the single `embedder` is handed to more than
   one consumer. Why would building it twice be wasteful? (Recall what loading bge-m3 costs from
   Lesson 0.3.)

---

## You should now be able to say…

- The DI rule: **logic depends on protocols; construction happens at the edges** (cli.py, UI
  wiring, tests).
- That `cli.py` is a thin wiring harness — build with factories, inject into services, run.
- The three payoffs — **swap, test, reuse** — and that each house guarantee you've seen relies
  on them.
- Why the logic files name no concrete collaborator (only protocols), and why that's the point.

Next: **[5.2 — Typed throughout, pydantic at every boundary](05-2-typed-pydantic.md)** — the
other half of "change without fear": every datum crossing a module boundary is a typed model,
checked by `mypy --strict`.
