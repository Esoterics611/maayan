# Lesson 5.3 — Config-driven everything

> Module 5, Lesson 3 · ~15 min read + a hands-on at the terminal.
> The one question this answers: **where do all the tunable numbers live, and why is there a
> rule that *none* of them may be written into the logic?**

You've now turned a dozen knobs across this curriculum: `score_threshold`, `top_k`,
`embed_model`, `rerank_enabled`, the boosts, `generation_backend`. Every one of them came from
the same place. This lesson is that place — `Settings` — and the house rule that keeps it the
*single* source of truth. It's short, because the idea is simple; but the discipline is what
makes the whole system tunable.

---

## The rule

From [CLAUDE.md](../../CLAUDE.md), house rule #4:

> **Config-driven.** Model names, collection names, top-k, thresholds, base URLs, the corpus
> book list — all come from `maayan/config.py` (`Settings`). Nothing is hardcoded in logic.

Open [maayan/config.py](../../maayan/config.py). Its docstring restates it: "All tunables live
here… Nothing in the codebase may hardcode model names, collection names, URLs, top-k,
thresholds, etc." `Settings` is a `pydantic-settings` model — every knob is a typed field with
a default, and it loads overrides from the environment / `.env`.

---

## One place, three ways to set it

Because `Settings` is a pydantic-settings model, the same field can be set three ways, in
increasing specificity:

1. **The default in `config.py`** — e.g. `score_threshold: float = Field(default=0.45)`.
2. **An environment variable / `.env`** — `SCORE_THRESHOLD=0.6` overrides the default. (This is
   why every "set a knob for one run" hands-on used an env var: `SCORE_THRESHOLD=0.0 uv run …`.)
3. **A per-call override at the edge** — e.g. `settings.model_copy(update={...})`, which is how
   `--mock` swaps in the embedded Qdrant and hashing embedder (you saw `_cfg()` do this in 5.1).

What you *won't* find is a fourth way: a number written directly into a logic file. There's no
`if relevance < 0.45` buried in `rag.py` — it's `self._score_threshold`, injected from
`settings.score_threshold`. Search for it and you'll see the threshold travels from `Settings`
→ the CLI edge → `RAGService`. The logic never names the number.

> ### Under the hood — config meets DI
> Notice the docstring's careful wording: `get_settings()` is "a cached convenience for
> entrypoints (CLI / UI), not for use inside library functions." Library code doesn't *reach
> out* and grab global config; it receives the specific values it needs, injected (Lesson 5.1).
> `get_settings()` lives only at the edges. So config and DI are the same discipline from two
> angles: **all tunables in one typed place, and that place is read at the edge and injected
> inward** — never grabbed from a global deep inside the logic. That's what makes a knob both
> discoverable (it's in `config.py`) and testable (a test injects its own `Settings`).

---

## Why this is non-negotiable

Three concrete payoffs you've already depended on:

- **Tunability.** You changed retrieval behavior in Module 4 by setting `SCORE_THRESHOLD` — no
  code edit, no redeploy. Every knob being external is what made "tune with the eval harness"
  possible.
- **No secrets in code.** API keys are config fields too — but `SecretStr`, read from env, never
  hardcoded, never logged (house rule #5). Centralizing config is also how secrets stay *out* of
  the source.
- **One audit surface.** Want to know everything that can change the system's behavior? Read one
  file. New tunable? It goes in `config.py` — that's literally in the "definition of done."

The anti-pattern this forbids is the magic number scattered through logic: a `0.45` here, a
`"BAAI/bge-m3"` there, a `top=8` somewhere else. Those are invisible, un-tunable, and impossible
to audit. maayan refuses them on principle.

---

## Hands-on

1. **Trace a knob home.** Pick one you've used — say `score_threshold`. Find its definition in
   [config.py](../../maayan/config.py) (read its description — it's a good one). Then find where
   it's *injected*: search `cli.py` for `score_threshold` and confirm it's passed into
   `RAGService(...)`. The number lives in config; the logic receives it.

2. **List the surface.** Skim `config.py` top to bottom. In ~30 seconds you can see *every*
   behavior-affecting knob in the system — generation backend & model, embedder, Qdrant URL &
   collection, top-k, threshold, boosts, rerank, the book lists, eval paths. That single-file
   readability is the rule paying off.

3. **Override without editing code.** Prove a knob is external by changing behavior with an env
   var only (you did this in 4.2; do it deliberately now):

   ```bash
   uv run maayan eval                       # baseline threshold (0.45)
   SCORE_THRESHOLD=0.7 uv run maayan eval    # stricter gate — no code changed
   ```

   The gate's `refused` rate moves, and you never opened an editor. That's config-driven
   behavior.

4. **Find a secret done right.** Locate `openrouter_api_key` in `config.py`. Note its type
   (`SecretStr`) and that it's read from env. In one sentence: why is centralizing config also
   the thing that keeps the key out of the codebase and the logs?

---

## You should now be able to say…

- House rule #4: **all tunables live in `Settings` (`config.py`); nothing hardcoded in logic.**
- The three ways a knob is set (default → env/`.env` → per-call override) and that logic never
  names the raw number.
- How config and DI are the same discipline: tunables centralized, read at the edge, injected
  inward (and `get_settings()` is edge-only).
- Why this gives tunability, secret-safety, and a single audit surface.

Next: **[5.4 — The Clock, and testing without the network](05-4-clock-and-testing.md)** — the
last house rule (no `time.sleep` in logic) and how all of these rules together let the test
suite run with no network and no real models.
