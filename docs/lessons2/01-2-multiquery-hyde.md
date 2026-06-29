# Lesson 1.2 — Multi-query & HyDE

> Module 1, Lesson 2 · ~15 min read + a hands-on (needs a backend for the live runs).
> The one question this answers: **how do we use the language model to turn one question into
> several good search queries — and why does searching with a *fake answer* work so well?**

Lesson 1.1 left us wanting several phrasings instead of one. The model that writes your answers
is also excellent at *rephrasing* and *imagining* — so we put it to work before retrieval, too.
Two techniques, both in `LLMQueryExpander` ([retrieve/expand.py](../../maayan/retrieve/expand.py)).

---

## Multi-query: rephrase the question several ways

The first technique is the simplest: ask the model for alternative search queries.

```python
MULTI_QUERY_SYSTEM_PROMPT = (
    "You help search a corpus of chassidus and Kabbalah ... write alternative search "
    "queries ... vary the wording and angle (synonyms, the underlying concept, related "
    "technical terms, Hebrew/English). ... output ONE query per line ... do not answer."
)
```

The expander sends your question, gets back a handful of lines, strips any bullets/numbering
(`_clean_lines`), and keeps up to `query_expand_variants` of them. Each line lands at a slightly
different point in vector space — a synonym here, the underlying concept there, the English
rendering — so together they cover more of the region where the answer lives.

The instruction "**do not answer the question**" matters: we want *queries*, not prose. (The
next technique deliberately does the opposite.)

---

## HyDE: search with a hypothetical answer

HyDE — **Hy**pothetical **D**ocument **E**mbeddings — is the clever one. Instead of searching
with the *question*, draft a short passage that would *answer* it, and search with **that**:

```python
HYDE_SYSTEM_PROMPT = (
    "... write a short, plausible passage (2-4 sentences) of the kind a source text might "
    "contain that would answer it — in the language of the question. This is a search aid, "
    "not an answer: do NOT add citations, and it is fine if some details are uncertain."
)
```

Why a *fake* answer beats the real question: retrieval matches **answer-shaped text against
answer-shaped text**. Your question ("what is the relationship between…?") is shaped nothing
like a source passage. A hypothetical answer is shaped *exactly* like one — same register, same
vocabulary, same concepts asserted rather than asked — so its embedding lands right in the
neighborhood of the genuine sources. It doesn't matter if the hypothetical is partly wrong;
we're not citing it, only using its *position in space* to find the real thing. The real
passages then get retrieved and become the only citable sources (default-deny still rules).

> ### Under the hood — two calls, by design
> `LLMQueryExpander.expand` makes up to **two** model calls: one for the reformulations, one
> for the HyDE passage. Each call has a single, clean job, which keeps parsing trivial and the
> prompts focused. That's part of the cost ladder we count in Lesson 3.1 — and why HyDE has its
> own toggle (`query_expand_hyde`) you can switch off when you want a cheaper expand.

---

## Hands-on

These call the model, so set a backend first (OpenRouter key or Ollama). See the variants the
model actually generates for one of your questions:

```bash
uv run python - <<'PY'
from maayan.config import Settings
from maayan.generate.factory import build_generation_backend
from maayan.retrieve.expand import LLMQueryExpander

backend = build_generation_backend(Settings())
ex = LLMQueryExpander(backend, variants=3, hyde=True)
out = ex.expand("מה הקשר בין צמצום לבריאת העולם")
for i, q in enumerate(out.queries):
    tag = "original" if i == 0 else ("HyDE" if i == len(out.queries) - 1 else "variant")
    print(f"[{tag:8}] {q}")
PY
```

Read them critically:
- Are the **variants** genuinely different angles, or near-duplicates? (If duplicative, your
  model is weak at this — lower `variants`, or lean on lexicon expansion in 1.3.)
- Is the **HyDE** passage source-shaped — does it *read like Tanya*, asserting rather than
  asking? That's the signal it'll retrieve well.

Then feel the payoff: search with the HyDE passage you just printed and compare to searching
with the bare question. The HyDE search should rank the real sources higher.

---

## You should now be able to say…

- **Multi-query**: ask the model for several rephrasings/angles; each is a different point in
  space; we keep up to `query_expand_variants`.
- **HyDE**: search with a hypothetical *answer*, because answer-shaped text matches the sources
  better than question-shaped text — and being partly wrong is fine, since we never cite it.
- Why the expander makes two clean model calls, and that HyDE is independently toggleable.

Next: **[1.3 — Lexicon-aware expansion](01-3-lexicon-expansion.md)** — the free, deterministic
widening that's uniquely yours.
