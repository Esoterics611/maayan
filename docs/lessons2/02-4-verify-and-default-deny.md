# Lesson 2.4 — Checking yourself, and the rule that didn't change

> Module 2, Lesson 4 · ~12 min read + a hands-on (no backend required for the key proof).
> The one question this answers: **how does the optional verify pass catch unsupported claims —
> and how do we *know* that all this new intelligence never weakened the refusal guarantee?**

Two ideas close Module 2: a new safety net (verification), and the old safety net we must prove
is still intact (default-deny). The second matters more than the first.

---

## Verification: flag what the sources don't support

Reasoning and synthesis make the answer better-organized — but the model can still overstate.
The optional **verify** pass (Move 3) is a final, separate check:

```python
VERIFY_SYSTEM_PROMPT = (
    "You are a citation checker. You are given numbered SOURCES and an ANSWER that cites them "
    "with [S#] tags. List any sentence ... NOT supported by the source(s) it cites ... one per "
    "line ... If every claim is properly supported, output exactly: OK"
)
```

After the answer is written, `ask` makes one more model call (`build_verify_messages` hands it
the sources + the answer), and `parse_unsupported` turns the reply into a list:

```python
def parse_unsupported(reply: str) -> list[str]:
    stripped = reply.strip()
    if not stripped or stripped.upper() == "OK":
        return []
    return [line.strip() for line in stripped.splitlines() if line.strip()]
```

Those land on `Answer.unsupported_claims`, and the CLI prints them under a **⚠ Claims not
clearly supported…** heading. Crucially, it's **flag-only** — the system never silently rewrites
your answer. It surfaces doubt for *you* to judge; it doesn't act on your behalf. That fits the
whole project's stance: the human stays in the loop.

This is a different kind of grounding than the prompt-level "cite your sources." The prompt
*asks* the model to be faithful; verify *checks* whether it was — with fresh eyes, in a separate
call that only sees the sources and the finished answer. Belt, meet suspenders.

---

## The rule that did not change: default-deny

Now the important part. We added expansion, two-stage reasoning, and verification — up to five
model calls (Lesson 3.1). Through all of it, **the refusal gate sits exactly where it always
did**, and still fires *before any model call*. Look at the top of `ask`:

```python
retrieval = self._retriever.retrieve(question, ...)
sources = retrieval.results
if not sources or retrieval.relevance < self._score_threshold:
    return Answer(..., grounded=False, text=self._refusal_text)   # NO model call
# only past here do analyze / synthesize / verify ever run
```

Read the order carefully: retrieve → check `relevance` against the threshold → **return the
refusal without generating** if it doesn't clear. Expansion feeds this gate a (possibly wider)
candidate set and a `relevance = max` across variants — but it cannot *lower* the threshold.
Reasoning and verify live entirely *after* the gate. So the guarantee from Course 1 holds
verbatim: **if retrieval finds nothing relevant, the model is never called, in any mode.**

This was a design rule, not an accident: *add intelligence around the trust core, never through
it.* It's why the new behavior could ship default-off with zero risk to the system's defining
promise.

---

## Hands-on

**1. Prove default-deny holds with everything on — no backend needed.** Force empty retrieval and
confirm the model is never touched, even with reasoning *and* verify enabled:

```bash
uv run python - <<'PY'
from maayan.generate.rag import RAGService
from maayan.retrieve.models import RetrievalResult

class EmptyRetriever:
    def retrieve(self, q, *, k=None, book=None, source=None):
        return RetrievalResult(results=[], relevance=0.0)

class Boom:
    def generate(self, system, messages):
        raise AssertionError("model was called — default-deny FAILED")

ans = RAGService(EmptyRetriever(), Boom(), score_threshold=0.4,
                 reasoning=True, verify=True).ask("a question with no sources")
print("grounded:", ans.grounded)          # False
print("text    :", ans.text)              # the refusal
print("no exception raised → model was NEVER called ✓")
PY
```

The `Boom` backend raises if touched; it isn't. That's the guarantee, demonstrated in code —
the same proof the test suite makes (`test_reasoning_default_deny_makes_no_calls`).

**2. See verify flag something (backend required).** Run a `--reason --verify` answer on a hard
question; if the model overstates anywhere, you'll see the ⚠ list. On a well-supported answer,
you'll see nothing — `OK` parses to an empty list.

---

## You should now be able to say…

- What verify does: a separate, final model call that flags unsupported sentences (`OK` → none),
  flag-only — never rewriting your answer.
- Why default-deny is **unchanged**: the gate runs before any model call, expansion can't lower
  the threshold, reasoning/verify run only after — so "no source → no model call" still holds in
  every mode.
- The governing principle of the whole upgrade: **intelligence around the trust core, never
  through it.**

Next: **[3.1 — The cost ladder](03-1-cost-ladder.md)** — what all this intelligence actually
costs, and how to decide when to spend it.
