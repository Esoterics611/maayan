# Lesson 7.5 — The web UI as a thin layer

> Module 7, Lesson 5 · ~15 min, hands-on in the browser.
> The one question this answers: **what does the web UI add to the system — and why is the
> honest answer "almost nothing but a face"?**

You've operated maayan entirely from the CLI. There's also a browser UI, and this lesson is about
seeing that it is — deliberately — a *thin layer*: it wires HTTP routes to the exact same services
you've been calling, and holds **no business logic of its own**. That thinness is a feature. It
means everything you learned (grounding, default-deny, the capture loop) holds identically in the
browser, because it's the same code underneath.

---

## Routes in, services out

Open [maayan/ui/app.py](../../maayan/ui/app.py) and read `create_app`. Two things jump out.

First, **its parameters are all services**, injected:

```python
def create_app(rag, capture, threads, develop, terms, retraction, stats, compose, *, context_turns=6):
```

That's the dependency-injection rule (Lesson 5.1) at the UI edge: the app is *handed* the same
`RAGService`, `CaptureService`, `ThreadService`, `DevelopmentService`, `TermService`, etc. that
the CLI builds. The web layer constructs none of them.

Second, **each route is a one-liner that calls a service**. The `/ask` route, in full:

```python
@app.post("/ask")
def ask(req: AskRequest) -> AskResponse:
    answer = rag.ask(req.question, k=req.k)
    session = capture.start_session(answer)
    return _answer_to_response(answer, session.id)
```

That's it — call `rag.ask`, record the session (so it can be annotated), shape the response. No
grounding logic, no gate, no prompt-building: all of that lives in `RAGService` (Module 3) and is
*reused*. The routes map cleanly onto everything you've learned:

| Route | Service call | Lesson |
|---|---|---|
| `POST /ask` | `rag.ask(...)` | Module 3 |
| `POST /annotate` | `capture.add_annotation(...)` | 6.2 |
| `POST /threads`, `/threads/{id}/ask` | `threads…`, `ask_in_thread` | 6.5, 3.4 |
| `POST /threads/{id}/seed`, `/develop` | seed + `develop.develop(...)` | 6.3 |
| `POST /developments/{id}/approve`/`reject` | `develop.approve/reject` | 6.4 |
| `GET`/`POST /terms` | `terms…` | 6.5 |

The whole capture loop you ran on the command line is available as HTTP, because the UI is just a
different *doorway* to the same rooms.

> ### Under the hood — why "thin" is the right design
> Because the routes hold no logic, three things follow for free. (1) **The guarantees are
> identical** — default-deny refuses in the browser because it's the same `RAGService.ask`; the
> UI can't accidentally weaken it. (2) **It's testable the same way** — `tests/test_ui.py` injects
> *fake* services into `create_app` and asserts on responses, no server or network needed (Lesson
> 5.4 again). (3) **No drift** — there's no second implementation of "how to answer" to keep in
> sync with the CLI. A fat UI that re-implemented grounding would be a second place for bugs and a
> second place for the trust rules to rot. maayan keeps the logic in one place and gives it two
> faces.

Launch it with `make ui` (needs the `ui` extra from Lesson 7.1).

---

## Hands-on — do the full loop in the browser

You need the `ui` extra, Qdrant up, corpus indexed, and (for grounded answers) an OpenRouter key.

```bash
uv run pip --version >/dev/null 2>&1   # ensure env is synced; else: uv sync --extra ml --extra ui
make ui                                 # serves the local app (FastAPI/uvicorn)
```

Open the printed URL in your browser, then:

1. **Ask and watch grounding + refusal — in the UI.** Ask a question the corpus supports (you get
   a cited answer) and then one it can't (you get the refusal). Same two behaviors as the CLI,
   same gate — confirm the refusal happens here too. That's the thin layer faithfully exposing
   Module 3.

2. **Teach a connection in the browser.** From an answer, add an annotation (a `connection`, your
   name, the linked refs). This is the `/annotate` route → `capture.add_annotation` — the *exact*
   loop from Lesson 6.2, now point-and-click. Then ask again and see it surface.

3. **Confirm it's the same code.** Open `/docs` (FastAPI's auto API docs) at the served URL.
   Match three routes to the service methods in the table above. In one sentence: what business
   logic lives in `ui/app.py`? (Answer: none — it delegates.)

4. **Find the test that proves thinness.** Open [tests/test_ui.py](../../tests/test_ui.py). Note
   that it injects fakes into `create_app` — the same DI move as `tests/test_rag.py` (Lesson 5.4).
   That's only possible because the UI takes services in.

---

## You should now be able to say…

- That the web UI is a **thin layer**: `create_app` takes the services injected and each route is
  a one-line delegation — **no business logic** of its own.
- That this means the **trust guarantees and the full capture loop hold identically** in the
  browser, because it's the same code underneath.
- Why thinness is deliberate: identical guarantees, same testability (inject fakes), and no logic
  drift between CLI and UI.

**That's Module 7 — running it for real.** You can now set it up (7.1), tune the knobs with
evidence (7.2), choose and swap the backend (7.3), grow the corpus (7.4), and operate it from the
browser (7.5). You're no longer just understanding maayan — you're running and owning it.

Next: **Module 8** — the horizon: using eval to justify a real change, the Phase 4 eraser and
Phase 5 composition layer, and when (and when not) to fine-tune. When you're ready, ask me to
**build out Module 8**.
