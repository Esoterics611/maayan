# maayan — Teaching walkthrough (UI, step by step) + golden questions

> The click-by-click companion to the reference guide. Where **[UI_GUIDE.md](UI_GUIDE.md)**
> *describes* each surface and **[RUNBOOK.md](RUNBOOK.md)** does it from the CLI, this doc
> walks you **in order** through (A) teaching the Assistant in the browser and (B) building
> and measuring your **golden questions & answers**.
>
> The one rule under all of it: **nothing enters the Knowledge base without your review.**
> Printed text (Tanya / Torah Or / Likutei Torah) is read-only; everything you add is
> attributed to you and **retractable**.

---

## 0. Before you start (one-time)

```bash
make up      # local Qdrant (vector DB)
make ui      # → http://127.0.0.1:8000
```

- **Log in** as your account (auth is on). Your **display name auto-fills the `author`
  field** on everything you save — no need to retype it.
- **Corpus check** — the drawer's *Knowledge base* panel (or `uv run maayan stats`) should
  show **~8,760 chunks**: Tanya (1,394) + Torah Or + **Likutei Torah (4,491)** + your
  expert/term layers. If Likutei Torah is missing, see RUNBOOK §3.
- **Everything happens inside a topic thread.** Open or start one from the left drawer first.

### Voice on this box — set the Whisper model before recording a shiur
The default `WHISPER_MODEL=large-v3` (~3 GB in float16) is **too big to sit next to bge-m3
on the 4 GB card** — a long recording will likely CUDA-OOM. For reliable shiur transcription
here, put this in `.env` **before** you record:

```dotenv
WHISPER_MODEL=medium      # fits alongside bge-m3 on the 4GB card; still strong on Hebrew
# (bump back to large-v3 only if you move embeddings to CPU or use a bigger GPU)
```

Short field dictation (the 🎤 on any input) uses the **browser's** on-device speech when
available and only falls back to server Whisper when it can't — so this mainly matters for
**long shiur audio**, not quick dictation.

---

## Part A — The teaching loop, click by click

Each step ends with **✓ confirm it learned** so you can see the Knowledge base actually grow.

### A1. Ask (nothing is saved yet)
1. In the thread composer, type a question (or tap **🎤** to dictate) and **Ask**.
2. You get a **grounded, cited** answer — or an **honest refusal** when the corpus doesn't
   support one. Sources are badged **sefaria · chabad · expert · derived · term · shiur**.
3. Tap any source ref to **read it in context** (the reader opens on the cited segment).

> Asking never writes to the Knowledge base. It's how you surface the real refs you'll teach
> *from* in the next steps.

### A2. Connect — the core move (Tanya ↔ Likutei Torah)
This is where most of your learning lives: a connection is one `expert` chunk whose refs span
two works.
1. Ask something that pulls sources from **both** books (e.g. *"אהבת עולם ואהבה בתענוגים"*).
2. Under the answer, **tick two or more sources** — e.g. one **Tanya** passage + one
   **Likutei Torah** passage.
3. Write the insight in the **Connect** box and press **Connect selected →**.
4. **✓ confirm it learned:** re-ask the topic — your connection now appears with an
   `expert` badge (and, with `EXPERT_BOOST` set, ranks above raw text). Or from the CLI:
   `uv run maayan search "<topic>" --source expert`.

> Shortcut: **highlight text** inside a source and choose **Connect** from the pop-up to tick
> that source in without scrolling.

### A3. Seed → Develop → Approve (let the model draft, you gate it)
1. Open **Seed ▾** in the composer. Write **seed knowledge** + a **directive** (what the model
   should develop — the directive is kept *out* of the embedded text). Press **Plant seed**.
2. Press **Develop this**. The model returns a **grounded, cited** proposal — or an honest
   refusal if the sources don't reach.
3. **Approve** → indexed as a `derived` chunk. **Reject** → nothing is indexed.
4. **✓ confirm it learned:** the approved development surfaces on future asks with a `derived`
   badge.

### A4. Define a term (protect a Holy Name / technical term)
1. Open **Term ▾**. Enter the **canonical** form, **type**, **definition**, **surface forms**,
   and (optional) **gematria**. Save.
2. It's badged **term**, appears in the drawer **lexicon**, and is protected from
   abbreviation-mangling in retrieval.
3. **✓ confirm it learned:** `uv run maayan search '<surface form>' --source term`.

### A5. Shiur transcription — teach from a recording (voice)
1. Open **Shiur ▾** → **record** in-browser or **upload** an audio file.
2. It transcribes **asynchronously** — a progress bar polls the job.
3. You're dropped into **review**: edit segments, accept lexicon-aware corrections, then mark
   **reviewed**.
4. Press **approve** → the transcript is windowed into `shiur` chunks, retrievable alongside
   the text. A cited shiur source can **play from its exact moment** in the recording.
5. **✓ confirm it learned:** ask a question the shiur answers — a `shiur`-badged source appears.

### A6. Capture without interrupting — inbox, OCR, highlight
- **📥 Inbox** (header): jot or dictate a fleeting thought; it parks **unsorted**. Later
  **move** it into a thread — it becomes a develop-able **seed** there.
- **📷 OCR** (on Seed/Term fields): photograph a page not in the corpus; the text drops into
  the field **for your review** — never auto-ingested. (Off until `OCR_BACKEND` is set.)
- **Highlight-to-act**: select text in a source → **Connect / Define term / Quote → seed**.

### A7. Retract — fix a mistake (the eraser)
- Any **layered** source card (expert / derived / term / shiur) carries **Retract ✕**. It
  removes the chunk from retrieval, is provenanced (who/why), and **survives a rebuild**.
- Printed text (sefaria / chabad) has no Retract button — it's read-only, enforced in code.
- To correct: **retract + re-add** through the normal loop (there's no in-place edit).

---

## Part B — Golden questions & answers

"Golden questions" are the evaluation set that tells you whether teaching is actually helping.
In maayan they come from **two directions**, and the flywheel is the point.

### B1. The flywheel — teaching *auto-builds* your gold set
`captured_goldset_enabled=true` (default): **every gated approval** — a Connect, an approved
Develop, a new Term, or an answered inquiry — **auto-drafts a deterministic regression
example**. A retraction removes its example. So as you do Part A, your captured gold set grows
by itself. Trendable reports:

```bash
uv run maayan eval --captured        # scores the auto-captured examples (date-stamped JSON in eval/captured_reports/)
```

### B2. Answer inquiries in the UI — "שאלות לרב" (questions to the Rav)
The right drawer has an **inquiry queue** — the system's own list of where it's weak (refused
questions, low-confidence answers), each card printing its **priority** math so the queue
earns your time honestly.

1. Press **↻** to (re)generate the queue.
2. On a card:
   - **שאל שוב** (ask again) — re-runs a refused question into the Ask box so you can **teach
     from it** (do A2/A3/A4 to create the missing knowledge).
   - **ענה ✓** (answer) — after you've taught, record **what resolved it** (a connection/term/
     chunk id + a word). This marks it answered and feeds the day's **harvest** line.
   - **דחה ✗** (dismiss) — carries the same weight as answering; use it when the question isn't
     worth teaching.

> The loop: the queue tells you *what* to teach next → you teach it (Part A) → you record the
> resolution → the captured gold set gains a regression example. Weak spots become tests.

### B3. Hand-curated gold set — for benchmark rigor
For a stable, authoritative benchmark, edit the YAML gold sets directly (there is **no UI
editor** — this is deliberate; gold is curated, not clicked):

| File | Measures | Run |
|---|---|---|
| `eval/goldset.yaml` | retrieval hit@k / recall@k / MRR **and** answer quality | `uv run maayan eval` · `eval --answer` |
| `eval/crosstext_goldset.yaml` | book-diversity across Tanya/Torah Or/Likutei Torah | `uv run maayan eval --crosstext` |
| `eval/develop_goldset.yaml` | develop-step grounding / honest-refusal | `uv run maayan eval --develop` |

**Format** (positive case = a question + the ref(s) that *should* retrieve; negative case =
`should_refuse: true` with empty refs, which tests the default-deny gate):

```yaml
examples:
  - question: "מהן שתי הנפשות של האדם?"
    expected_refs: ["Tanya, Part I; Likkutei Amarim 1", "Tanya, Part I; Likkutei Amarim 2"]
    note: two souls — divine and animal

  - question: "<a question the corpus should NOT answer>"
    expected_refs: []
    should_refuse: true
```

- Refs are **chapter-level**; a metric matches any segment within (`…1` matches `…1:13`).
- Now that **Likutei Torah is indexed**, `crosstext_goldset.yaml` can finally exercise all
  three works — add cross-text questions there to measure co-retrieval.
- `eval --answer` scores **citations + faithfulness with an LLM judge** against the retrieved
  sources (there is no hand-written "ideal answer" field — grounding is judged, not matched).

### B4. Read the numbers
```bash
uv run maayan eval                 # retrieval + the default-deny gate
uv run maayan eval --answer        # answer citations + faithfulness (LLM judge)
uv run maayan eval --crosstext     # cross-text co-retrieval / coverage@k
uv run maayan eval --develop       # develop grounding / refusal-rate
uv run maayan eval-expand          # recall@k / MRR lift WITH vs WITHOUT query expansion
uv run maayan eval --captured      # regression score over the auto-captured flywheel
```
Eval runs from the **terminal**, not the UI. Curate gold → teach → re-run → watch the numbers
move.

---

## The whole loop in one line

**Ask** (find refs) → **Connect / Seed→Develop→Approve / Term / Shiur** (teach) → the approval
**auto-captures a gold example** → **inquiry queue** tells you what's still weak → curate
`eval/*.yaml` for rigor → **`maayan eval`** proves it. Everything you add is attributed and
retractable; the printed text never changes.

See also: **[UI_GUIDE.md](UI_GUIDE.md)** (feature reference) · **[RUNBOOK.md](RUNBOOK.md)**
(CLI walkthrough) · **[TEACHING.md](TEACHING.md)** (why the loop is shaped this way).
