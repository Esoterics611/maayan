# maayan — Runbook: start the backend, build your Knowledge base, verify it learned

This is the end-to-end walkthrough: bring up the backend, ingest the texts, ask
across them, **teach the Assistant a connection**, and **confirm it learned**. Every
command is copy-pasteable. New to the design? Read [TEACHING.md](TEACHING.md) after.

---

## 0. The two things, named accurately

- **The Assistant** — what you chat with. It's a *retrieval-augmented assistant*: an
  LLM (OpenRouter by default) wrapped by retrieval + a default-deny gate. **Teaching
  it never trains or fine-tunes the model** — the weights never change.
- **The Knowledge base** — where your teaching goes. It's the local **Qdrant vector
  index** of text chunks, each tagged by provenance:

  | `source` | What it is | Where it comes from |
  |---|---|---|
  | `sefaria` | Printed text | Sefaria API (Tanya, Torah Or) |
  | `chabad`  | Printed text | chabadlibrary.org API (Likutei Torah) |
  | `expert`  | Your correction/**connection**/seed | you (named author) |
  | `derived` | An **approved** model development of a seed | the model, grounded in refs |
  | `term`    | A lexicon entry (Holy Name / technical term) | you (named author) |

  When you "teach the Assistant," you **insert a new chunk into the Knowledge base**,
  which it then retrieves on future questions. That's the whole loop — retrieval
  growth, not model training, which is why it runs locally with no GPU training.

## 1. What's in the corpus (and where it comes from)

| Work | Source | How it's fetched | Notes |
|---|---|---|---|
| **Tanya, Part I (Likkutei Amarim)** | Sefaria | `maayan ingest` (depth-2 shape) | 53 chapters, he+en |
| **Torah Or** | Sefaria (`Torah Ohr, <parsha>`) | `maayan ingest` | 24 parsha nodes, each depth-2 |
| **Likutei Torah** | **chabadlibrary.org** (not on Sefaria) | `maayan ingest-chabad` | Hebrew; walked via its JSON API |

**Why two sources.** Tanya + Torah Or are on Sefaria. **Likutei Torah is not on
Sefaria at all** (and the Hebrew Wikisource copy is an empty stub), so we pull it from
chabadlibrary.org's JSON API. See [§8 How it works](#8-how-it-works-under-the-hood).

**Licensing.** Sefaria text is CC-BY-NC (attribute Sefaria; personal/non-commercial).
The Alter Rebbe's works are public-domain by age; the chabadlibrary.org *digital
edition* is fetched for personal Torah study — revisit before any redistribution.

---

## 2. One-time setup

```bash
# Dependencies (core + embeddings + UI)
uv sync --extra ml --extra ui

# Config: set your OpenRouter key (generation only; ingest/index/search need no key)
cp .env.example .env          # then edit: OPENROUTER_API_KEY=sk-or-...

# Start the local vector DB (Qdrant in Docker) — this is "the backend"
make up                       # Qdrant on :6333  (no Docker? set QDRANT_URL=:memory: or a path)
```

## 3. Build the Knowledge base (ingest → index)

```bash
# 3a. Ingest the Sefaria texts: Tanya + all 24 Torah Or parshiyot (config.books).
make ingest                   # = maayan ingest --all
#   Quick sample instead (2 chapters of one book):
#   uv run maayan ingest --book "Tanya, Part I; Likkutei Amarim" --limit 2

# 3b. Ingest Likutei Torah from chabadlibrary.org (config.chabad_books).
uv run maayan ingest-chabad --all
#   Quick sample (first 10 leaf pages):  uv run maayan ingest-chabad --all --limit 10

# 3c. Embed everything + upsert into Qdrant (downloads bge-m3 ~2.3GB on first run).
make index                    # incremental; add --rebuild to re-embed everything
```

> First `ingest --all` + `ingest-chabad --all` pull a lot over the network (rate-limited
> via the injected Clock). Use `--limit` while you're trying things out, then do a full
> run once. Re-running is **idempotent** (stable chunk ids → upsert, never duplicate).

## 4. Verify the Knowledge base loaded

```bash
# Each book is retrievable; --source filters by provenance.
uv run maayan search "שתי הנפשות"                    --book "Tanya"           --k 3
uv run maayan search "שבת"                            --book "Torah Ohr"        --k 3
uv run maayan search "ראו כי ה' נתן לכם השבת"          --source chabad           --k 3
```

Each result prints its `(lang/source)` and a provenance line, so you can see which
book and source each hit came from.

## 5. Use it — ask across the texts

```bash
uv run maayan ask "מה ההבדל בין צדיק לבינוני?"
#   → a grounded answer; Sources list (cited ones marked *); a Session id.
#   Because all three works are indexed, an answer can cite Tanya AND Torah Or AND
#   Likutei Torah together — that's cross-text co-retrieval, for free.
```

Or run the web UI and do it in the browser:

```bash
make ui            # → http://127.0.0.1:8000   (ask · teach · connect · develop)
```

> Using the app (web + installable phone PWA — voice, OCR, highlight-to-act, inbox,
> reader, shiur transcription): **[UI_GUIDE.md](UI_GUIDE.md)**.

## 6. Teach the Assistant a connection — and confirm it learned

This is the core of your plan: *most of the learning is the Tanya ↔ Likutei Torah
connections.* A connection is one `expert` chunk whose `linked_refs` span both books.

```bash
# 6a. Ask something so you have real refs to connect, and a Session id.
uv run maayan ask "אהבת עולם ואהבה בתענוגים"
#   → note the SESSION_ID it prints, and the refs in the Sources list.

# 6b. Teach the connection. --author is REQUIRED (provenance). Refs contain commas,
#     so pass each with a repeatable --ref (never a comma-split).
uv run maayan annotate --session <SESSION_ID> --author "R. Ginsburgh" \
    --kind connection \
    --body "אהבת עולם בתניא היא היסוד לאהבה בתענוגים שמבוארת בלקוטי תורה" \
    --ref "Tanya, Part I; Likkutei Amarim 18" \
    --ref "Likutei Torah, פרשה ויקרא, א א"
#   → indexed immediately as a source="expert" connection chunk.

# 6c. CONFIRM IT LEARNED: search the topic and filter to your taught knowledge.
uv run maayan search "אהבת עולם אהבה בתענוגים" --source expert
#   → your connection surfaces, and the line:
#       ↳ expert connection by R. Ginsburgh; connects Tanya, Part I; Likkutei Amarim 18,
#         Likutei Torah, פרשה ויקרא, א א
#   That bridge across the two books is what the Assistant now retrieves.

# 6d. Prefer your reviewed knowledge in ranking (optional): set EXPERT_BOOST=3 in .env,
#     then re-ask — the connection ranks above raw text.
```

**In the web UI** (`make ui`) this is one click: ask, then **tick two or more sources**
under the answer (e.g. one Tanya + one Likutei Torah), write the insight in the
*Connect* box, and press **Connect selected →**. It posts the same `expert` connection
(author sticky) and surfaces on future questions. The *Seed ▾* composer and
**develop** flow are there too — see §7.

## 7. Grow knowledge: seed → develop → approve; define terms

```bash
# Seed (knowledge + a directive the model develops), then develop + approve.
uv run maayan ask "אהבה בתענוגים" --topic "ahava b'ta'anugim"   # starts a thread
uv run maayan annotate --session <SESSION_ID> --author "R. Ginsburgh" \
    --kind connection --opens-aspect \
    --body 'אהבה בתענוגים היא גילוי שם ע"ב' --directive "מצא היכן זה נרמז בתניא"
uv run maayan develop --seed <CONTRIBUTION_ID>     # grounded+cited proposal, or honest refusal
uv run maayan approve <DEVELOPMENT_ID>             # → indexed as source="derived"

# Define a Holy Name / term so it's never mangled and its definition is retrievable.
uv run maayan add-term --canonical 'ע"ב (Name of 72)' \
    --definition 'the Ab expansion of Havayah, gematria 72' \
    --type expansion --gematria 72 --surface 'ע"ב' --surface 'עב' --author "R. Ginsburgh"
uv run maayan search 'יחוד מ"ה וב"ן' --source term
```

## 7b. Correcting a mistake — retract (the eraser)

You *will* index a wrong connection, a typo'd term, or a development you later
reconsider. Layered knowledge (`expert` / `derived` / `term`) is **retractable** —
printed text (`sefaria` / `chabad`) never is. Retraction is provenanced (who / when /
why), removes the chunk from retrieval, and **survives `index --rebuild`** (it is not
re-embedded). There is no in-place edit: **to correct, retract + re-add.**

```bash
# Retract by ref (or by chunk id). --author is REQUIRED; --reason is recorded.
uv run maayan retract "Expert · connection · 1a2b3c4d" \
    --author "R. Ginsburgh" --reason "wrong connection — supersede"
# Re-add the corrected knowledge through the normal loop (annotate / develop / add-term).
uv run maayan annotate --session <SESSION_ID> --author "R. Ginsburgh" \
    --kind connection --body '<the corrected insight>' --ref '<ref>' --ref '<ref>'

uv run maayan retractions          # the audit log: who retracted what, when, and why
```

In the UI, expert/derived/term source cards carry a small **Retract ✕** affordance
(printed-text cards do not). Attempting to retract printed text is refused, in code.

## 8. Measure it

```bash
uv run maayan eval                # retrieval: hit@k / recall@k / MRR + default-deny gate
uv run maayan eval --develop      # develop step: develop-rate / refusal-rate / grounding
uv run maayan eval --crosstext    # cross-text: book-diversity / coverage@k across the 3 books
```

## 8b. See the corpus — `maayan stats`

```bash
uv run maayan stats               # chunks by source/book, contributions by author,
                                  # developments by status, retractions, threads, terms
```

The steward's dashboard: what's in the Knowledge base, what's been retracted, and how
it's growing — the information you need to decide what to retract next. Also at
`GET /stats` in the UI.

## 9. Compose a shiur outline — a grounded document, section by section

A composition turns one brief into a structured document by running the grounded unit
(retrieve → default-deny → cited block) **once per section**. Where the corpus is
silent, the section is an **honest gap**, never fabricated. Approval does **not**
re-ingest the prose — instead you **promote a connection** back through the capture loop.

```bash
# 9a. Brief → a proposed outline (each section is a heading + a retrieval sub-question).
uv run maayan compose --title "בירור הנפש הבהמית" \
    --intent "שיעור המראה כיצד מבררים את הנפש הבהמית, מתניא ומתורה אור" \
    --type shiur_outline --author "R. Ginsburgh"
#   → prints the outline + a COMPOSITION_ID. (Set COMPOSE_AUTO_OUTLINE=true to fill at once.)

# 9b. Fill each section — grounded + cited, or an honest gap where the sources don't reach.
uv run maayan compose-fill <COMPOSITION_ID>

# 9c. Review + export to markdown (title, sections, gap flags, a provenance footer).
uv run maayan compose-approve <COMPOSITION_ID>     # or: compose-reject
uv run maayan compose-export  <COMPOSITION_ID> --out shiur.md

# 9d. Feed the corpus the RIGHT way: promote ONE section's connection (not the prose).
uv run maayan compose-promote <COMPOSITION_ID> --section 2 \
    --author "R. Ginsburgh" --insight "שתי הסוגיות נפגשות בענין הביטול"
#   → a source="expert" connection chunk, linking that section's grounded refs. Retrievable.

uv run maayan compositions          # list      ·   uv run maayan composition <id>   # show
```

In the UI, the **Compose** panel does the same: write a brief, edit/approve the outline,
Fill, see per-section citations and gap badges, Approve/Reject/Export, and promote a
connection.

---

## How it works under the hood

- **Sefaria (Tanya, Torah Or).** The ingester reads each book's *shape* (a flat list
  of chapter lengths — "depth-2"), then fetches each chapter and chunks it one
  segment per `Chunk`. Torah Or is listed per-parsha in `config.books` because each
  parsha (`Torah Ohr, Bo`, …) is its own depth-2 node.
- **Likutei Torah (chabadlibrary.org).** `maayan/corpus/chabad.py` talks to the
  site's JSON API: `GET api/main?path=<section_id>` returns either a section's
  children or a leaf page's HTML. We walk **book → parshiyot → sections**, strip the
  HTML with the same normalizer as Sefaria (markup out, **nikkud kept**). A section
  runs ~2–3k chars with no internal paragraph breaks, so it is split at **sentence
  boundaries** into coherent passages of ≤ `CHABAD_CHUNK_CHARS` (default 1000), each a
  chunk cited as `… §N` and traceable (via `metadata.section_id`) to its source
  section. Set `CHABAD_CHUNK_CHARS=0` for one chunk per whole section. Responses are
  brotli-encoded, so `brotli` is a dependency. Book → root-section-id mapping lives in
  `config.chabad_books` (`{"Likutei Torah": 4000000000}`); find other ids by walking
  from the root call.
- **Everything lands in one Qdrant collection.** Retrieval (hybrid dense+sparse RRF)
  treats all sources together; `source` only changes badges, optional boosts
  (`EXPERT_BOOST`/`DERIVED_BOOST`/`TERM_BOOST`), and the `--source` filter. Printed
  text (`sefaria`/`chabad`) is never edited — your `expert`/`derived`/`term`
  knowledge layers on top as new chunks.

## Troubleshooting

- **`ask` 401 / missing key** — set `OPENROUTER_API_KEY` in `.env`. Retrieval and the
  refusal path need no key.
- **Everything refuses** — tune `SCORE_THRESHOLD` (bge-m3 cosine clusters narrowly);
  enable the reranker (`RERANK_ENABLED=true`) to sharpen the gate.
- **chabad ingest looks slow** — it walks the tree page by page, rate-limited. Use
  `--limit` for a sample; the full pull is a one-time cost (idempotent thereafter).
- **No Docker** — `QDRANT_URL=:memory:` (ephemeral) or a local path (persistent).
- **Local/offline generation** — set `GENERATION_BACKEND=ollama` + `OLLAMA_MODEL`
  (`ollama pull qwen2.5:7b-instruct`). It's the backup; OpenRouter is the default and
  is stronger on Hebrew.
