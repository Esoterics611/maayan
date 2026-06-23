# Lesson 3.2 — The grounded prompt & citations

> Module 3, Lesson 2 · ~20 min read + a hands-on at the terminal.
> The one question this answers: **how do retrieved passages actually get handed to the model
> so that the answer is forced to come *from them* — and how does each `[S#]` in the answer
> turn back into a real citation?**

In Lesson 3.1 you saw the box the model lives behind. Now we open the call itself. This is the
"A" in RAG — *Augmented*: the model isn't asked your question cold; it's handed the retrieved
sources and told to answer **only** from them, citing each claim. This lesson is how that
hand-off is built, in [maayan/generate/rag.py](../../maayan/generate/rag.py).

---

## Sources become a numbered, citable block

When retrieval returns its passages, the RAG service turns them into a block the model can
quote *by number*. Read `build_context` ([rag.py:67](../../maayan/generate/rag.py)):

```python
def build_context(sources):
    lines = ["SOURCES:"]
    for i, s in enumerate(sources, 1):
        lines.append(f"[S{i}] ({s.ref}) {s.text}")
    return "\n".join(lines)
```

So the model literally sees:

```
SOURCES:
[S1] (Tanya, Part I; Likkutei Amarim 1:2) ...the text of that passage...
[S2] (Tanya, Part I; Likkutei Amarim 2:1) ...the text of that passage...
```

Two things are doing quiet work here. First, each source gets a **handle** — `[S1]`, `[S2]` —
that the model can cite cheaply, the way you'd say "see source 1" instead of rewriting the
whole passage. Second, the handle carries the **real `ref`** right next to it. The model cites
by tag; the system already knows the tag maps to *"Tanya, Part I; Likkutei Amarim 1:2"*. The
citation is grounded before the model writes a word, because the `ref` rode in with the source
(remember: `ref` is both identity and citation, Lesson 1.2).

---

## The instructions that make it grounded

A numbered block isn't enough — the model has to be *told* to obey it. Read
`DEFAULT_SYSTEM_PROMPT` ([rag.py:20](../../maayan/generate/rag.py)). In plain terms, its rules
are:

1. **Use only the sources.** No outside facts. Never invent or guess mekoros.
2. **Cite every claim** with its bracket tag right after it, e.g. `[S1]`, or `[S1][S3]`.
3. **If the sources don't suffice, say so** — don't speculate.
4. **Answer in the language of the question**, faithful to the sources.
5. (A conversation block, if present, is for *interpretation only* — never cite it. That's
   Lesson 3.4.)

Then `ask` assembles the final message: the sources block, plus the question with a reminder to
"cite each claim ONLY by its `[S#]` source tag," and sends it through the backend (Lesson 3.1).

> ### A crucial caveat — the prompt is the *softer* half
> Notice these are *instructions* to the model. A good model follows them; but instructions
> alone are exactly the "please don't hallucinate" approach Lesson 0.1 warned about — they
> reduce fabrication, they don't *guarantee* it. The hard guarantee — that the system won't
> answer when there's no real source — is **not** in this prompt. It's a gate in code that runs
> *before* this prompt is ever built. That's the entire subject of the next lesson. For now,
> hold the split: the prompt shapes *how* it answers; the gate (3.3) decides *whether* it
> answers at all.

---

## From `[S#]` back to a citation

After the model replies, the service has to figure out *which* sources it actually leaned on,
so the UI/CLI can mark them. Read `extract_cited_refs`
([rag.py:83](../../maayan/generate/rag.py)):

- It scans the answer for `[S#]` tags (the regex `_TAG`), maps each number back to that
  source's `ref`, and collects them in order, de-duplicated.
- As a safety net, it also catches any `ref` the model wrote out *literally* in prose.

The result is `Answer.cited_refs` — the concrete list of sources the answer rests on. The CLI
then prints the full `Sources:` list and marks the cited ones with `*`. So the chain is
airtight and inspectable: **retrieved `ref` → `[S#]` handle → model cites `[S#]` → resolved
back to `ref` → shown to you.** Every claim has a traceable home.

---

## Hands-on

You need a working `ask` (Qdrant up, corpus indexed, and an OpenRouter key — this step calls
the model). Ask something your two Tanya chapters can answer:

```bash
uv run maayan ask "מה ההבדל בין צדיק לבינוני?"
```

1. **Match every `[S#]` to its source.** In the answer text, find the `[S#]` tags. In the
   `Sources:` list below, the cited ones are marked `*`. Pick one tag — say `[S2]` — and
   confirm it lines up with the 2nd source. Then open that source's text (`uv run maayan search`
   its ref, or recall it) and check: **does the claim the tag is attached to actually say what
   the source says?** This habit *is* the system's reason to exist.

2. **Find an uncited source.** Usually not every retrieved source gets cited — some were
   retrieved but didn't make it into the answer (marked `[ ]`, no `*`). That's fine and honest:
   retrieval offers candidates; the model uses what it needs. Note one.

3. **See the block the model saw.** Reconstruct the `SOURCES:` block yourself to demystify it:

   ```bash
   uv run python - <<'PY'
   from maayan.config import Settings
   from maayan.retrieve.factory import build_retriever
   from maayan.generate.rag import build_context
   r = build_retriever(Settings())
   sources = r.retrieve("מה ההבדל בין צדיק לבינוני?", k=3, book="Tanya").results
   print(build_context(sources))
   PY
   ```

   This prints the exact numbered, citable block that gets handed to the model. Notice the
   `[S#]` tag and the `(ref)` sitting together on each line — that adjacency is what makes a
   citation cheap and grounded.

4. **Read the contract.** Open `DEFAULT_SYSTEM_PROMPT` in `rag.py` and read rule 1 and rule 3
   aloud. In your own words, what is the model being *forbidden* to do?

---

## You should now be able to say…

- How retrieved sources become a **numbered `[S#]` block** (`build_context`), each tag carrying
  its real `ref`.
- What the **system prompt** instructs (answer only from sources, cite every claim, refuse to
  speculate) — and that this is the *soft* half of the guarantee.
- How `extract_cited_refs` resolves `[S#]` tags back to refs, completing a traceable chain from
  retrieval to displayed citation.

Next: **[3.3 — Default-deny: the rule that lives in code, not the prompt](03-3-default-deny.md)** —
the hard guarantee. We'll meet the gate that refuses *before* the model is ever called, and you'll
make it open and close with one knob.
