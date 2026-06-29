# Populating maayan's lexicon & connectors — end-to-end runbook

This is the hands-on guide for the two **auto-populators** built in Phase 3: the
**lexicon** (technical terms / Holy Names) and the **connectors** (cross-text
connections spanning Tanya ↔ Torah Ohr ↔ Likutei Torah). Follow it top to bottom the
first time; after that, use the [quick reference](#command-quick-reference).

---

## What these do — and the trust model

Both populators run the same loop, and both keep maayan's core promise (**nothing
enters retrieval untrusted**):

```
mine/seed  →  Claude DRAFTS from retrieved corpus sources (cited [S#])  →  faithfulness check  →  YOU approve  →  indexed
              └── only from the sources, never from Claude's own memory ──┘                        └── author = you ──┘
```

- **Claude drafts, the corpus grounds, you gate.** A draft is only eligible for
  approval if it (a) cites real retrieved sources and (b) passes the faithfulness
  verifier. Ungrounded / uncited / unfaithful drafts are marked **unsupported** and
  `approve` refuses to index them.
- **All model calls go through OpenRouter.** maayan's own answers stay on free Qwen;
  the *drafting* model is swapped via one config knob (`LEXICON_DRAFT_MODEL`) so you can
  draft with Claude Opus 4.8.
- **Approval is the only path to the index.** Drafts sit in a review queue
  (`pending`) until you approve them. The indexed term/connection is attributed to
  **you** (the human approver), with the corpus refs carried as provenance.

---

## 0. Prerequisites (one-time)

```bash
# 1. Heavy ML deps (bge-m3 embedder) — needed for real retrieval/indexing
uv sync --extra ml

# 2. Start local Qdrant
make up

# 3. Confirm the corpus is already ingested + indexed (you have ~4.8MB of chunks).
#    This should return Hebrew hits from Tanya / Torah Ohr / Likutei Torah:
uv run maayan search "ביטול"
```

Then edit **`.env`** and add the drafting model (everything else is already set):

```ini
# The model that DRAFTS lexicon/connector definitions. Blank = use the free Qwen
# generation model. Set it to the OpenRouter Claude Opus slug to draft with Claude.
# ↳ Verify the exact slug at https://openrouter.ai/models  (likely the line below)
LEXICON_DRAFT_MODEL=anthropic/claude-opus-4.8
```

> **💡 Cost-free dry run first.** Leave `LEXICON_DRAFT_MODEL` **blank** for your very
> first pass — the populator then drafts with the free Qwen model, so you can watch the
> whole mine → draft → review → approve flow at no cost. Once you're happy with the
> mechanics, set it to the Claude slug and re-run for publishable quality. (Approving a
> Qwen-drafted entry still works; just reject and re-draft with Claude if you prefer.)

---

## 1. Lexicon populator — step by step

### 1.1 Draft the curated seed pack into the review queue

The seed pack is ~27 hand-picked entities (the Names ע״ב/ס״ג/מ״ה/ב״ן, the ten sefirot,
the partzufim, core concepts like צמצום / ביטול / אהבה בתענוגים). Their **definitions
are drafted from your corpus**, not from the seed.

```bash
uv run maayan lexicon-suggest --seed
```

Expected output (counts depend on your corpus):

```
Drafting seed-pack terms…
Drafted 27 term(s): 21 grounded & queued, 6 skipped (ungrounded).
Review: `maayan lexicon-review`, then `maayan lexicon-approve <id> --author ...`.
```

> "Skipped (ungrounded)" = the corpus didn't actually define that term well enough, or
> the draft failed the faithfulness check. That's the gate working — not an error.

### 1.2 Review the drafts and their mekoros

```bash
uv run maayan lexicon-review
```

```
21 pending suggestion(s):
  3f2a…  · צמצום [concept]  (drafted by anthropic/claude-opus-4.8)
      צמצום הוא העלם והסתר האור האין סוף כדי לאפשר מציאות נבראים [S2]…
      ↳ grounds: Torah Ohr, Bereshit 1, Likutei Torah, Devarim
  …
```

Read each one as a scholar: is the definition faithful to the cited mekoros?

### 1.3 Approve the good ones (this indexes them)

```bash
uv run maayan lexicon-approve 3f2a… --author "Ronnie Rendel"
```

```
Approved → indexed term <id> — צמצום by Ronnie Rendel.
It will now surface in retrieval (search --source term).
```

Reject the ones you don't want (no model calls; just marks it rejected):

```bash
uv run maayan lexicon-reject <id>
```

### 1.4 (Optional) Add corpus-mined candidates

Beyond the seed pack, mine gershayim terms (ע״ב, חב״ד, רמ״ח…) straight from the text,
ranked by frequency:

```bash
uv run maayan lexicon-suggest --no-seed --mine --limit 20
uv run maayan lexicon-review      # review + approve as above
```

### 1.5 Verify the lexicon is live

```bash
uv run maayan terms                       # lists curated terms
uv run maayan search "יחוד מה ובן" --source term   # term chunks now retrievable
```

---

## 2. Connector populator — step by step

Connections are the corpus's headline: one idea across two works. The populator probes
the retriever, **pairs results from different books**, and has Claude state the
connection **grounded in both ends, citing both [S#]**.

### 2.1 Draft connections into the review queue

```bash
# Uses a built-in set of conceptual probes (bittul, tzimtzum, animal soul, …)
uv run maayan connectors-suggest --limit 15

# …or probe with your cross-text gold-set questions instead:
uv run maayan connectors-suggest --from-goldset --limit 15
```

```
Mined 18 cross-text candidate(s); drafting…
Drafted 18 connection(s): 11 grounded & queued, 7 skipped (not cross-text / ungrounded).
Review: `maayan connectors-review`, then `connectors-approve <id> --author ...`.
```

> A draft is only "supported" if it actually cites ends from **≥2 distinct books** and
> passes the faithfulness check — a one-sided "connection" is rejected automatically.

### 2.2 Review, approve, reject

```bash
uv run maayan connectors-review
```

```
11 pending connection(s):
  9c1b…  · Tanya ↔ Torah Ohr  (drafted by anthropic/claude-opus-4.8)
      שני המקורות מבארים את ענין הביטול: בתניא כאהבה מסותרת [S1], ובתורה אור… [S2].
      ↳ grounds: Tanya, Part I; Likkutei Amarim 19, Torah Ohr, Bereshit 2
```

```bash
uv run maayan connectors-approve 9c1b… --author "Ronnie Rendel"
uv run maayan connectors-reject  <id>
```

### 2.3 Verify the connections are live

```bash
uv run maayan search "ביטול" --source expert    # connection chunks now retrievable
```

Approved connections are indexed as `source="expert"`, `kind="connection"` chunks
(recorded under a synthetic `connector-builder` session), so they co-retrieve with the
very sources they tie together.

---

## 3. Confirm it actually helps retrieval (optional but recommended)

The lexicon feeds **query expansion**; the term/connection chunks get **source
boosts**. To see the lift, turn expansion on and compare:

```bash
# in .env
QUERY_EXPAND_ENABLED=true       # lexicon-driven query expansion
TERM_BOOST=1.5                  # nudge curated terms up in ranking (tune to taste)
EXPERT_BOOST=1.5                # …and the connection/expert chunks

# then:
make eval-expand                # retrieval recall@k / MRR, expansion off vs on
make eval-expand ARGS='--crosstext'   # the cross-text co-retrieval metric
```

---

## 4. What I verified for you, vs what needs your live run

| Checked, green ✔ | How |
|---|---|
| `ruff` clean, `mypy --strict` clean (119 files) | `make lint`, `make typecheck` |
| Full test suite (332 tests, incl. 25 new for the populators) | `make test` |
| All 8 CLI commands register | `maayan --help` |
| Read-only paths run against your real DB | `maayan lexicon-review`, `maayan connectors-review` → "No pending …" |
| Mining, grounding gate, faithfulness gate, cross-text gate, approval → index | unit tests (mocked model) |

| Needs your live run (real OpenRouter calls) | Why I didn't run it |
|---|---|
| `lexicon-suggest`, `connectors-suggest` | spends OpenRouter credits; drafting quality is yours to judge |
| `*-approve` | indexing is a real, expert-gated decision — your call |

---

## 5. Follow-up roadmap (documented — for after you've populated)

Once you've populated and tuned, this is the path to the benchmark study (see also
`docs/BUILD_PLAN_PHASE6.md` and the project memory):

- **3.0 — First reasoning numbers.** `make eval-answer` with `RAG_REASONING_ENABLED=false`
  vs `true` (set `EVAL_JUDGE_MODEL` to a *different* model so the judge isn't
  self-grading). Tells you whether Prompt 31's reasoning helps the maayan pipeline.
- **3.2 — Tuning sweep.** Sweep `SCORE_THRESHOLD`, `TOP_K`, `RERANK_ENABLED`,
  `QUERY_EXPAND_ENABLED`, `RAG_REASONING_ENABLED` with the eval harnesses; pin the best
  `.env` recipe — this is "maayan at its best" for the benchmark.
- **3.3 — Benchmark harness.** Arm A = tuned maayan (free Qwen). Arm B = Claude Opus
  4.8 **closed-book** (no web search). Claude Opus 4.8 also **grades** both answers
  against your gold + a rubric — **blinded** (Answer 1/2 randomized, identity hidden) to
  defuse self-preference. Plus the **maayan-text-only vs maayan+synthetic ablation** so
  the gain isn't smuggled-in Claude knowledge.
- **3.4 — Gold set.** ~60 expert-authored questions, stratified: Likutei Torah / Torah
  Ohr heavy (where Claude is weakest from memory), with Tanya as a control stratum.
- **3.5 — Academic report.** Markdown → PDF via the `md-to-pdf` skill (Hebrew/RTL +
  nikkud): methods, results tables, significance, a qualitative appendix (a hallucinated
  mekor vs maayan's grounded citation), limitations.

Then the bigger rungs: roadmap **#1 agentic multi-hop** (retrieve→reason→retrieve).

---

## Cost & safety notes

- `*-suggest` makes **real OpenRouter calls** (~1–2 per term/connection, plus a verify
  pass). Use `--limit` to cap, and the free-model dry run (§0) to rehearse at no cost.
- `*-review` and `*-reject` load **no models** and touch only SQLite — free and instant.
- Nothing is indexed until **you** `*-approve`. Approval refuses unsupported drafts in
  code, so an ungrounded definition can't slip into retrieval even if you try.
- Drafts persist in the review queue across runs (SQLite, same DB) — you can suggest
  today and approve tomorrow.

---

## Command quick reference

```bash
# Lexicon (terms / Holy Names)
maayan lexicon-suggest [--seed] [--mine] [--limit N] [--model SLUG] [--include-unsupported]
maayan lexicon-review
maayan lexicon-approve <id> --author "Your Name"
maayan lexicon-reject  <id>

# Connectors (cross-text connections)
maayan connectors-suggest [--from-goldset] [--limit N] [--k N] [--model SLUG] [--include-unsupported]
maayan connectors-review
maayan connectors-approve <id> --author "Your Name"
maayan connectors-reject  <id>

# Verify
maayan terms
maayan search "<query>" --source term      # curated terms
maayan search "<query>" --source expert    # connections (+ other expert chunks)
```
