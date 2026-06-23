# Lesson 5.4 — The Clock, and testing without the network

> Module 5, Lesson 4 · ~20 min, hands-on at the terminal.
> The one question this answers: **why is there no `time.sleep` in the code, and how does the
> whole test suite run with no network calls and no 2 GB model downloads?**

This lesson ties the engineering spine together. You've seen DI (5.1), typed boundaries (5.2),
and config (5.3). Here's the last house rule — the injectable **Clock** — and then the payoff
all four rules were building toward: a test suite that's **fast, deterministic, and offline**,
which is what lets every change ship with tests (house rule #7).

---

## The Clock: no `time.sleep` in logic

From [CLAUDE.md](../../CLAUDE.md), house rule #2:

> **No `time.sleep` in business logic.** Use the injectable `Clock`. Any waiting/backoff is
> `async` and driven by the injected clock so tests never actually sleep.

Open [maayan/clock.py](../../maayan/clock.py). It's three small pieces:

- **`Clock`** — a protocol: `now()` (current UTC time), `monotonic()` (elapsed-time measurement,
  e.g. rate limiting), and `async sleep(seconds)`.
- **`SystemClock`** — the real one: `datetime.now(UTC)`, `time.monotonic()`,
  `asyncio.sleep()`. Used in production.
- **`FakeClock`** — the test one: `sleep()` **records** the duration and advances *virtual* time
  without ever blocking. It "advances only when `sleep` is called; never blocks."

Why bother? Because code that calls `time.sleep(30)` directly is **untestable** — a test of it
would take 30 real seconds. By taking a `Clock` by injection (the DI rule again), the same
waiting/backoff logic runs instantly under `FakeClock` in tests, and you can even *assert* on
what it tried to wait (`fake.slept == [30.0]`). Time becomes a dependency you control, not a
wall you hit. (You met this need concretely with the chabad ingester's rate-limiting in earlier
phases — that's where a real wait exists, and the Clock is how it's tested without waiting.)

---

## The payoff: the test suite is offline by construction

Now the part where all four house rules cash out. From CLAUDE.md, house rule #7: unit tests
**mock the network and the models** — no real OpenRouter, Sefaria, or model downloads — and use
ephemeral/in-memory Qdrant. Run them:

```bash
make test
```

It's fast, and it touches *nothing* external. That's only possible because of the rules you've
learned. Here's the mapping, made concrete in real test files:

| To avoid… | The test injects… | Seen in |
|---|---|---|
| downloading bge-m3 (2 GB) | `HashingEmbedder` (deterministic, instant) | `tests/test_index.py`, `tests/test_retrieve.py` |
| running Docker / a real DB | `QdrantClient(location=":memory:")`, `ChunkStore(":memory:")` | `tests/test_index.py`, `tests/test_retrieve.py` |
| calling the cloud model | a fake `GenerationBackend` (`RecordingBackend`) | `tests/test_rag.py` |
| a real HTTP call to Ollama | `respx` mocking the endpoint | `tests/test_ollama.py` |
| real wall-clock waiting | `FakeClock` | wherever waiting exists |

Every one of those is an *injected* fake satisfying the *same protocol* as the real thing
(5.1), carrying *typed* data (5.2), selected without touching logic (5.3). The house rules
aren't four separate ideas — they're one idea (substitutable, typed, edge-constructed
collaborators) that happens to pay off as testability.

---

## The test that proves the system's central promise

Open [tests/test_rag.py](../../tests/test_rag.py) and read
`test_empty_retrieval_refuses_without_calling_model`:

```python
def test_empty_retrieval_refuses_without_calling_model() -> None:
    backend = RecordingBackend()
    rag = RAGService(FakeRetriever([], relevance=0.0), backend, score_threshold=0.4)
    answer = rag.ask("שאלה כלשהי")
    assert answer.grounded is False
    assert backend.calls == []   # default-deny: model never called
```

Sit with that last line. `RecordingBackend` records every call to `generate`. The assertion
`backend.calls == []` is a **machine-checked proof** of the most important claim in the whole
system — the default-deny gate from Lesson 3.3 — *"the model is never called when there's no
source."* Not a comment, not a hope: a test that fails the build if the gate ever regresses.

And it's only writable because of DI: you can hand `RAGService` a fake backend and a fake
retriever and *watch* whether the door stayed shut. Trust, made testable. The companion tests in
the same file prove the rest of Module 3 the same way — context never bypasses the gate, only
retrieved refs get cited, sources land in the prompt. The trust core has a test for each
promise.

---

## Hands-on

1. **Run the suite.** `make test`. Note how quickly it finishes and that your network/Docker
   are irrelevant to it. (If you want, disconnect from the internet and run it again — it
   passes.)

2. **Read the proof.** Open `tests/test_rag.py`. Find the two refusal tests
   (`...refuses_without_calling_model`). Identify the fake backend and the assertion that proves
   the model wasn't called. In one sentence: which house rule (5.1) makes this test *possible* to
   write?

3. **Meet the fakes.** In `tests/test_index.py`, find `QdrantClient(location=":memory:")` and
   `HashingEmbedder`. Confirm: this test exercises the *real* indexing pipeline (`index_chunks`)
   with *fake* collaborators — same logic, no downloads, no Docker. That's the pattern
   everywhere.

4. **Feel the Clock idea.** In `clock.py`, read `FakeClock.sleep`. It appends to `self.slept` and
   bumps virtual time. Write down: how would you test that some backoff logic "waited 1s, then
   2s, then 4s" *without your test taking 7 seconds*? (Answer: assert on `fake.slept`.)

---

## You should now be able to say…

- House rule #2: **no `time.sleep` in logic** — waiting takes an injected `Clock`, so
  `FakeClock` makes time-dependent code instant and assertable.
- Why `make test` is **fast, deterministic, and offline**: every external thing (model, DB,
  cloud, HTTP, time) is an injected fake satisfying the real protocol.
- That the house rules are one idea — substitutable, typed, edge-constructed collaborators — and
  that testability is its payoff.
- That the default-deny promise is **machine-proven** by `backend.calls == []`.

**That's Module 5 — the engineering spine.** You now understand *why* maayan is built the way it
is: DI (5.1), typed boundaries (5.2), config (5.3), and the Clock + offline tests (5.4) together
make the system swappable, auditable, and trustworthy — so you can change it without fear.

Next: **Module 6** — the differentiator. We open the capture & develop loop: how a scholar's
reasoning becomes durable, retrievable, attributed knowledge. When you're ready, ask me to
**build out Module 6**.
