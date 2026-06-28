# Build Plan — Phase 6: Mobile + Voice (the capture loop, spoken)

> Status as of 2026-06-28. Phases 1–5 are built, tested (199 passing), and the
> web UI is fully wired (`maayan ui`). This phase makes maayan a **mobile,
> voice-first** tool: a scholar learns, speaks, records a shiur — and that becomes
> retrievable knowledge in the same index. Voice is the natural input for Hebrew
> on a phone; typing nikkud on a touch keyboard is the thing that kills adoption.

---

## 0. Where we are (the gap that was closed first)

- **Code**: complete, `make test` green (199), `make typecheck`/`make lint` clean.
- **Corpus**: 4,240 chunks ingested in SQLite (Tanya Part I + Torah Ohr). Likutei
  Torah still pending its Chabad-library adapter (separate, already scaffolded).
- **Models**: `bge-m3` cached locally (4.3 GB); **CUDA GPU available** — this is
  what makes local Whisper transcription viable below.
- **The only runtime gap to "test in the UI"**: the 4,240 chunks were never
  embedded into a *running* Qdrant. Once Qdrant is up and `make index` runs, the
  UI is fully usable. (See the operator steps handed off separately.)

This GPU + local-first posture is the reason Phase 6 recommends **local Whisper**.

---

## 1. Thesis: why mobile + voice is the right next investment

maayan's whole point is the **capture loop** — an expert's corrections and
connections become retrievable knowledge. Today that loop is typed, at a desk.
Three frictions block the people who actually have the knowledge:

1. **Hebrew typing on mobile is miserable** (nikkud, gershayim, RTL). Voice fixes it.
2. **The richest knowledge is spoken** — a shiur is an hour of connections that
   never get captured. The data model already anticipates this: `Chunk.source`
   includes `"shiur"`. Phase 6 finally produces those chunks.
3. **Learning happens away from the desk** — on a couch, in shul, on a walk. A
   phone that can *listen, capture a connection, and ask* meets the scholar there.

So Phase 6 = (a) make the existing UI a real mobile app, (b) make voice a
first-class input everywhere, and (c) build the shiur → transcript → knowledge
pipeline. All of it reuses the existing services and the same Qdrant collection.

---

## 2. Architecture additions (honoring the house rules)

New work mirrors the existing patterns — typed pydantic models across boundaries,
DI for swappable backends, config-driven, network/models mocked in tests.

### New modules
```
maayan/
  transcribe/      Transcriber protocol + WhisperTranscriber (local) + Cloud impl,
                   factory, models.  Mirrors generate/ exactly.        (Phase 6c)
  audio/           AudioAsset store (file on disk + row in SQLite),
                   upload handling, ffmpeg normalize.                   (Phase 6c)
  shiur/           Transcript → review/approve → shiur Chunks.
                   Reuses the develop/approve gate pattern.             (Phase 6c)
  ocr/             (optional) OCRer protocol for page-photo capture.    (Phase 6d)
```

### New typed models (pydantic, like everything else)
- `AudioAsset` — `id, owner, filename, path, duration_s, sample_rate, created_at, sha256`.
- `Transcript` — `id, audio_id, lang, backend, model, status, segments[]`.
- `TranscriptSegment` — `idx, start_s, end_s, speaker?, text, edited_text?`.
  Timestamps are the spine: a citation to a shiur chunk can deep-link to audio.
- `TranscriptionJob` — `id, audio_id, status (queued|running|done|error), progress`.
  Async because transcription is slow (see §6c on the job model — no `time.sleep`).

### New config (`config.py`, all defaulted, swappable)
```
transcribe_backend: "whisper" | "cloud"        (default "whisper")
whisper_model:      "large-v3"                  (best Hebrew; "medium" for speed)
whisper_device:     "auto" | "cuda" | "cpu"
whisper_compute_type: "float16" | "int8"        (int8 for CPU)
transcribe_lang:    "he"                         (auto-detect fallback)
transcribe_diarize: false                        (speaker labels for shiur Q&A)
audio_dir:          "data/audio"
ocr_backend:        "none" | "tesseract" | "cloud"
```

### Backend swap (why DI matters again)
`transcribe/` defines a `Transcriber` protocol with one method, roughly:
`transcribe(audio_path, lang) -> Transcript`. `WhisperTranscriber` (local,
`faster-whisper`) and `CloudTranscriber` (ElevenLabs Scribe / AssemblyAI / Deepgram)
both implement it; `TRANSCRIBE_BACKEND` selects which is injected — no other code
changes. Same pattern as OpenRouter ↔ Ollama.

---

## 3. Transcription backend decision

**Recommendation: local `faster-whisper` `large-v3` on the existing CUDA GPU**,
behind the `Transcriber` protocol so a cloud backend can be swapped per the house
rules.

| Option | Hebrew | Cost | Privacy | Notes |
|---|---|---|---|---|
| **faster-whisper large-v3 (local)** ✅ | Good | Free | Local-first | Uses the GPU we already have; aligns with the whole project's local posture. CTranslate2 backend = fast. |
| whisper.cpp | Good | Free | Local | Better if no GPU / for a future on-device build. |
| ElevenLabs Scribe (cloud) | Very good | $/min | Cloud | Strong Hebrew + diarization; good swap-in for quality A/B. |
| AssemblyAI / Deepgram | Fair–good | $/min | Cloud | Diarization, word timestamps, streaming. |

**Hebrew-specific quality levers (where maayan can beat raw Whisper):**
- **Lexicon-aware post-processing** — we *already* have a lexicon of terms / Holy
  Names / rashei-teivot. Use it to correct ASR output (Whisper mangles ע"ב, הוי',
  partzufim). This turns an existing feature into a transcription accelerator.
- **Diarization** for shiurim with Q&A (separate the maggid shiur from questioners).
- **Word-level timestamps** so a corrected term keeps its audio anchor.

---

## 4. Phase 6a — Mobile foundation (responsive + installable PWA)

**Goal:** the existing UI becomes a proper mobile app you install to the home
screen. No native rewrite; no app store.

- **PWA**: add `manifest.webmanifest` (name, icons, theme, `display: standalone`)
  and a service worker (cache the shell + static assets; offline-tolerant reads).
  Result: "Add to Home Screen" → looks and launches like an app.
- **Responsive redesign** of `index.html`: the current 3-pane desktop layout
  (sidebar + thread + composer) collapses on phones into:
  - a bottom tab bar: **Ask · Threads · Capture · Library**,
  - the sidebar (threads/lexicon/stats) becomes a slide-over drawer,
  - the composer becomes a sticky bottom bar with a mic button (see 6b).
- **RTL + nikkud typography pass** (see 6e) so Hebrew reads well on small screens.

**DoD:** installs to a phone home screen; usable one-handed in portrait; all
existing flows (ask, seed→develop→approve, connect, term, compose) reachable.

> Optional later: wrap the PWA in **Capacitor** for a true native shell (App
> Store/Play, native mic, background recording, push). Only if a store presence or
> background audio is needed — the PWA covers 90% first.

---

## 5. Phase 6b — Voice as input everywhere (quick win, no backend)

**Goal:** speak instead of type, immediately, before the heavy shiur pipeline.

- **Dictation buttons** (🎤) on every text input: the **Ask** box, the **Seed**
  body, the **Connection** insight, the **Term** definition.
- v1 uses the browser **Web Speech API** (`webkitSpeechRecognition`, `lang=he-IL`)
  — zero backend, works in Chrome/Android today. Graceful fallback: if unsupported,
  the same button records audio and routes to the server Whisper endpoint (6c).
- **Voice ask**: hold-to-talk → transcript fills the Ask box → submit. The whole
  RAG path (retrieval, citations, refusal gate) is unchanged.

**DoD:** every capture field has a working mic affordance; a Hebrew question can be
asked entirely by voice on Android Chrome.

---

## 6. Phase 6c — The shiur pipeline (the big one)

**Goal:** record or upload a shiur → transcribe → expert reviews/corrects →
becomes `source="shiur"` chunks in the same Qdrant collection, retrievable next to
Tanya and Torah Ohr. This realizes the `"shiur"` source the data model promised.

**Flow:**
1. **Record / upload** (`audio/`): MediaRecorder in the PWA for in-app recording,
   plus a file upload for existing recordings. Normalize with ffmpeg (mono, 16 kHz).
   Store the file under `audio_dir`, a row in `audio_assets`, sha256 for idempotency.
2. **Transcribe** (`transcribe/`): a `TranscriptionJob` runs the injected
   `Transcriber`. **Async, no `time.sleep`** — kick off via FastAPI `BackgroundTasks`
   (v1) writing progress to the job row; UI polls `/jobs/{id}`. (A real queue can
   come later; the job model keeps the contract.)
3. **Review** (`shiur/`): a transcript-review screen — segments with timestamps,
   inline-editable text, a play-from-here control, lexicon-suggested term fixes,
   optional speaker labels. This is the human gate (same philosophy as develop
   approve/reject). Nothing enters the corpus unreviewed.
4. **Chunk + ingest**: approved transcript → chunks (segment- or topic-windowed,
   reusing `corpus/chunker.py` conventions), `source="shiur"`, `ref` like
   `"Shiur: <title> @ 12:34"`, metadata carries `audio_id` + `start_s/end_s`.
   Embed + upsert through the **existing** index pipeline.
5. **Cited audio**: when a shiur chunk is cited in an answer, the UI offers
   "▶ play from 12:34" using the stored timestamp.

**DoD:** upload a Hebrew shiur recording → get a reviewable transcript → approve →
ask a question whose answer cites the shiur with a working play-from-timestamp.

---

## 7. Phase 6d — Beyond typing: more capture surfaces

Ideas, roughly in value order — pick per appetite:

- **Photo → OCR capture** (`ocr/`): snap a page of a sefer not on Sefaria → Hebrew
  OCR (Tesseract `heb`, or a cloud vision API) → becomes a quotable source or a
  connection target. Huge for texts that aren't digitized.
- **Highlight-to-act on mobile**: long-press select inside a source → context menu:
  *Connect · Define term · Quote into seed*. (Desktop already has a hint of this for
  terms; make it a first-class mobile gesture.)
- **Voice connection / voice seed**: speak the insight that links two ticked
  sources; transcript fills the connection body.
- **Voice term definitions**: dictate a Holy-Name / concept definition into the
  lexicon — the lexicon then improves future transcription (closes a second loop).
- **Quick-capture inbox**: a one-tap "capture a thought" (voice or text) that lands
  in an unsorted inbox to triage into a thread later — meets the scholar mid-learning.
- **Share-target**: register as an Android share target so audio/text/images shared
  from other apps land straight in maayan's capture inbox.

---

## 8. Phase 6e — Viewing / reading experience

Long Torah-learning sessions need a real reading surface, not just search results.

- **RTL/nikkud typography**: a proper Hebrew serif (e.g. Frank Ruehl / Taamey),
  larger line-height, correct bidi for mixed He/En, selectable text.
- **Reading modes**: light / sepia / dark; adjustable font size; a distraction-free
  full-screen reader for a single source or a composed shiur.
- **Source-in-context**: tap a citation → open the full perek/os with the cited
  segment highlighted, instead of just the snippet. (We have `section_path`.)
- **Sefer browser**: browse the corpus as a book (Tanya by chapter, Torah Ohr by
  parsha) — not only via search. Read → tap to ask → tap to connect.
- **Tablet split view**: question + answer on one side, full sources on the other.
- **Inline expandable citations** in answers (tap ✦ to expand the source inline).

---

## 9. Sequencing (quick wins first, heavy last)

1. **6a PWA + responsive** — high value, no new deps. Makes it "an app" today.
2. **6b browser dictation** — high value, ~no backend. Voice input immediately.
3. **6e typography/reading** — cheap polish that makes daily use pleasant.
4. **6c shiur pipeline** — the flagship; biggest build (audio store + Whisper +
   async jobs + review UI + ingest). Do after the cheap wins land.
5. **6d OCR / extra capture surfaces** — additive, pick by appetite.

Each sub-phase ships under the existing Definition of Done: `make test` (network +
models mocked — mock the `Transcriber`/`OCRer`, never call real Whisper/cloud in
unit tests), `make typecheck`, `make lint`, new tunables in `config.py`.

---

## 10. Risks / open questions

- **Hebrew ASR accuracy** on real shiur audio (room noise, fast speech, Yiddish
  loanwords). Mitigation: the review gate + lexicon post-processing; A/B a cloud
  backend via the protocol.
- **Async transcription** must stay true to the no-`time.sleep` rule — the job
  model + polling is the contract; a heavier worker/queue is an internal swap.
- **Storage growth**: audio is large. Decide retention (keep source audio vs only
  transcript + timestamps). `audio_dir` is config-driven so it can move to a volume.
- **PWA mic limits**: background recording is restricted in browsers; if recording
  long shiurim with the screen off matters, that's the trigger for the Capacitor wrap.
- **Auth**: voice/audio endpoints must sit behind the same auth wall when
  `AUTH_ENABLED=true`; uploads are owned by the logged-in user.
- **Licensing**: shiur audio is the expert's own content (fine); OCR'd printed
  seforim carry their own copyright — keep that to personal/non-commercial like the
  Sefaria CC-BY-NC posture.

---

# The prompts

> Continue the sequence: Phases 1–5 were Prompts 0–22, so Phase 6 is **Prompts
> 23–30**. Run them one at a time. **Every prompt follows [CLAUDE.md](../CLAUDE.md)**
> — typed + `mypy --strict`, dependency injection, config-driven, no secrets,
> default-deny, tests mock network + models (mock the `Transcriber`/`OCRer`; never
> call real Whisper or a cloud ASR in unit tests). Let `make test` / `typecheck` /
> `lint` pass before moving to the next. New audio/transcription endpoints sit
> behind the same auth wall when `AUTH_ENABLED=true`.

Order: **23 → 24 → 29** are the cheap, high-value wins (PWA, voice input, reading).
**25 → 26 → 27 → 28** are the shiur pipeline (build in order; each depends on the
prior). **30** is additive — do it whenever.

---

### Prompt 23 — PWA shell + responsive mobile layout (6a)

```
Make the existing web UI an installable, mobile-first PWA. Follow CLAUDE.md. This is
FRONTEND + thin static-serving only — no business-logic changes, no new services. All
existing routes and flows must keep working unchanged.

Context: maayan/ui/static/index.html is a single-page app with a 3-pane desktop layout
(aside sidebar + thread turns + composer). On a phone it's unusable. Make it install to
the home screen and reflow for one-handed portrait use, without a native rewrite.

Requirements:
- PWA assets under maayan/ui/static/: manifest.webmanifest (name "maayan · מעיין",
  short_name "maayan", display "standalone", theme/background from the existing palette,
  icons 192/512 — generate simple placeholder icons committed to the repo) and a service
  worker sw.js that precaches the app shell + static assets and serves cache-first for
  GET of static files only (NEVER cache /api, /ask, /threads/* POSTs or any mutation).
  Link the manifest + register the SW from index.html (guarded: no-op if unsupported).
- Routes (thin, in maayan/ui/app.py): serve /manifest.webmanifest and /sw.js with correct
  content-types from the static dir. /sw.js must be served from the app root scope.
- Responsive redesign of index.html (CSS only; keep the existing JS/handlers/IDs intact):
    - <=720px: the aside (threads / lexicon / knowledge base) becomes a slide-over drawer
      toggled by a hamburger in the header; the main turns area is full-width.
    - A bottom tab bar (Ask · Threads · Capture · Library) that scrolls/expands the
      relevant region — Ask focuses the composer, Threads opens the drawer, Capture opens
      the seed/term/compose tools, Library is a placeholder anchor for Prompt 29.
    - Sticky bottom composer with large touch targets; inputs >=16px to stop iOS zoom.
    - Keep RTL/dir="auto" behavior; nothing regresses on desktop (>720px unchanged).
- Tests (maayan/ui test, network mocked as today): /manifest.webmanifest and /sw.js return
  200 with the right content-type; index.html references both; existing UI tests still pass.

Show: load the UI on a phone-width viewport, install to home screen, and run an existing
flow (ask within a thread) end to end.
```

---

### Prompt 24 — Voice input everywhere (browser dictation) (6b)

```
Add a microphone (dictation) affordance to every capture field so Hebrew can be entered by
voice. Follow CLAUDE.md. FRONTEND-only in this prompt (no backend); the server-Whisper
fallback is wired in Prompt 26 once the Transcriber exists.

Context: typing nikkud/gershayim on a touch keyboard is the main adoption blocker. The
browser Web Speech API (webkitSpeechRecognition) supports he-IL on Chrome/Android today.

Requirements:
- A reusable mic button (🎤) attached to: the Ask input (#q), the Seed body (#seedBody),
  the Connection insight (#connectBody), and the Term definition (#termDef). Hold-to-talk
  or tap-to-toggle; visible recording state; appends/streams the recognized text into the
  field; lang defaults to "he-IL" with an easy switch to "en-US".
- Feature-detect: if Web Speech is unavailable, the button enters a "record" state that
  captures audio via MediaRecorder and stashes the Blob plus a callback that POSTs to the
  (Prompt 26) /api/transcribe endpoint — but in THIS prompt that path is stubbed to show a
  clear "server transcription coming in Prompt 26" toast, so nothing is half-broken.
- No new Python routes or services here. Keep all existing IDs/handlers; the mic only fills
  inputs the existing code already reads.
- Tests: this is browser-API UI; assert the buttons render next to each field and that the
  graceful-fallback branch exists (DOM/string assertions in the UI test are enough — do not
  attempt to drive real speech recognition).

Show: dictate a Hebrew question into the Ask box on Android Chrome and submit it; the RAG
path (retrieval, citations, refusal gate) is unchanged.
```

---

### Prompt 25 — Transcriber protocol + Whisper backend + audio store (6c.1)

```
Build the transcription spine: a swappable Transcriber and an audio asset store. Follow
CLAUDE.md. Mirror the generate/ pattern EXACTLY (protocol + factory + DI + config select);
do not bake any model choice into logic. No UI yet (Prompt 26 adds endpoints).

Context: realize Chunk.source="shiur". A shiur recording must become a transcript with
timestamps that a human later reviews (Prompt 27) and approves into the corpus (Prompt 28).

Requirements:
- New module maayan/transcribe/. Pydantic models (maayan/transcribe/models.py):
    - TranscriptSegment: idx, start_s, end_s, speaker: str | None = None, text,
      edited_text: str | None = None.
    - Transcript: id, audio_id, lang, backend, model, status
      (Literal["raw","reviewed","approved","rejected"], default "raw"),
      segments: list[TranscriptSegment], created_at.
- A Transcriber protocol (maayan/transcribe/base.py): transcribe(audio_path: Path,
  lang: str | None) -> Transcript. A FakeTranscriber (deterministic, for tests, like
  embed/fake.py) and a WhisperTranscriber (faster-whisper; word/segment timestamps;
  device/compute from config) under the `ml` extra — import lazily so core stays light.
- A factory build_transcriber(settings) selecting "whisper" | "fake" | "cloud" (leave
  "cloud" raising NotImplementedError with a clear message — it's a documented swap point).
- New module maayan/audio/: AudioAsset model (id, owner, filename, path, duration_s,
  sample_rate, sha256, created_at) + AudioStore (SQLite, same DB, idempotent migration).
  store_file(...) normalizes to mono 16kHz via ffmpeg (shell out; skip+warn if ffmpeg
  missing), computes sha256 for idempotency (same audio re-upload returns the existing row).
- Config (config.py, all defaulted): transcribe_backend ("whisper"), whisper_model
  ("large-v3"), whisper_device ("auto"), whisper_compute_type ("float16"), transcribe_lang
  ("he"), transcribe_diarize (false), audio_dir ("data/audio").
- CLI: `maayan transcribe <audio_path> [--lang he]` → store the asset, run the injected
  transcriber, print segments with timestamps. Uses build_transcriber/_cfg() at the edge.
- Tests (mock with FakeTranscriber; NO real Whisper, NO network): transcribe round-trips a
  Transcript with ordered segments + timestamps; AudioStore is idempotent by sha256;
  factory selects backends by config; missing ffmpeg degrades gracefully.

Show: `maayan transcribe sample.wav` with the fake backend prints timestamped segments;
note the one-line config flip to real Whisper.
```

---

### Prompt 26 — Async transcription jobs + upload/record endpoints (6c.2)

```
Wire audio in from the (PWA) UI and run transcription asynchronously. Follow CLAUDE.md.
NO time.sleep anywhere — waiting/polling uses the injected Clock; the long-running job runs
off the request thread and reports progress via a status row the UI polls.

Context: transcription of a full shiur is slow. The contract is a TranscriptionJob the UI
can poll; a heavier worker/queue can swap in later behind the same model.

Requirements:
- TranscriptionJob model (maayan/transcribe/models.py): id, audio_id, status
  (Literal["queued","running","done","error"]), progress: float = 0.0, transcript_id:
  str | None, error: str | None, created_at, updated_at. A JobStore (SQLite, migration).
- Thin routes (maayan/ui/app.py; behind auth when enabled; uploads owned by the logged-in
  user — owner from request.state.user, else "local"):
    - POST /api/audio (multipart) → store via AudioStore, return AudioAsset.
    - POST /api/audio/{audio_id}/transcribe → create a queued TranscriptionJob, kick off
      the work via FastAPI BackgroundTasks (inject the Transcriber), return the job.
    - GET /api/jobs/{job_id} → current TranscriptionJob (poll target).
    - GET /api/transcripts/{transcript_id} → the Transcript.
  Route handlers stay thin; the job-running logic lives in a TranscriptionService
  (collaborators injected: transcriber, audio store, job store, clock).
- UI: a Capture → "Record / upload shiur" panel using MediaRecorder (in-app recording) and
  a file picker; on submit it POSTs the audio, then polls GET /api/jobs/{id} (via Clock-free
  setTimeout in the browser) showing progress; on done it opens the transcript (Prompt 27).
  This also satisfies the Prompt 24 server-fallback stub.
- Wire all new services into create_app() and the cli.py `ui` command (DI at the edge).
- Tests (FakeTranscriber; TestClient; no real models/network): upload returns an asset;
  transcribe creates a job that reaches status "done" with a transcript_id; polling returns
  terminal state; an errored transcription sets status "error" + message; auth-required when
  AUTH_ENABLED=true.

Show: upload a short clip in the UI, watch the job progress to done, and see the raw
transcript appear.
```

---

### Prompt 27 — Transcript review + lexicon-aware correction (6c.3)

```
Build the human review gate for a transcript — the spoken analogue of the develop
approve/reject gate. Follow CLAUDE.md. Nothing enters the corpus unreviewed.

Context: raw ASR mangles Hebrew technical terms / Holy Names (ע"ב, הוי', partzufim). We
ALREADY have a lexicon (TermService) — use its surface_forms to suggest corrections,
turning an existing feature into a transcription accelerator.

Requirements:
- TranscriptionService.suggest_corrections(transcript) -> Transcript: for each segment,
  use the injected TermService surface_forms (gershayim/quote/nikkud-insensitive, the SAME
  matching the lexicon already uses) to propose normalized term spellings; record them as
  suggestions WITHOUT overwriting text (the human decides). No new matching engine — reuse
  the lexicon's normalization.
- Editing API (thin routes; auth-aware):
    - PATCH /api/transcripts/{id}/segments/{idx} → set edited_text (and speaker), revalidate.
    - POST /api/transcripts/{id}/review → mark status "reviewed".
  Editing logic lives in TranscriptionService; routes stay thin.
- UI: a transcript review screen — segments listed with [start–end] timestamps, inline
  editable text, lexicon suggestions shown as one-tap accepts, optional speaker label,
  and a "▶ play from here" control that seeks the stored audio to start_s. A "Define as
  term" shortcut on selected text reuses the existing Term flow (closes the loop: a term
  defined now improves the next transcript).
- Tests (mock TermService + transcriber): suggestions match known surface_forms and never
  silently overwrite; PATCH persists edited_text; review flips status to "reviewed";
  unknown segments yield no false suggestions.

Show: review a transcript, accept a lexicon suggestion for a Holy Name, edit one segment,
play from a timestamp, and mark it reviewed.
```

---

### Prompt 28 — Approve transcript → shiur chunks → index (6c.4)

```
Turn an approved transcript into retrievable shiur chunks in the SAME Qdrant collection.
Follow CLAUDE.md. Reuse the existing corpus chunker conventions and the index pipeline
VERBATIM — do not build a parallel ingest path. This closes the voice capture loop.

Context: Chunk.source already reserves "shiur". Approval is the gate (like develop.approve);
only approved transcripts produce corpus, and printed text stays immutable.

Requirements:
- TranscriptionService.approve(transcript_id) -> list[Chunk]: gate on status (must be
  "reviewed"); window segments into coherent chunks (segment- or topic-windowed, honoring
  the existing chabad_chunk_chars-style sentence/size conventions in corpus/chunker.py);
  each Chunk: source="shiur", lang detected (reuse detect_lang), ref like
  "Shiur: <title> @ MM:SS", text = edited_text or text, metadata carries audio_id,
  start_s, end_s, speaker, author (the reviewer — REQUIRED, never default, as Prompt 9).
  Set transcript status "approved" (and a reject(id) → "rejected" for symmetry).
- Embed + upsert through the EXISTING embed + index pipeline (no new embedder/index code);
  shiur chunks become retrievable alongside sefaria/expert/derived/term. A shiur_boost
  config (default 1.0), parallel to expert_boost/derived_boost/term_boost, applied in the
  same retrieval place — do not special-case retrieval logic elsewhere.
- UI: an Approve/Reject control on the reviewed transcript; on approve, show the resulting
  chunk count and refresh stats. In an answer, a cited shiur source shows a "▶ play from
  MM:SS" control using its metadata timestamps.
- Stats: include shiur chunks in chunks_by_source so the Knowledge base panel reflects them.
- Tests (in-memory Qdrant + fake embedder, as the index/retrieve tests do): approve gates on
  "reviewed"; produces source="shiur" chunks with audio_id + timestamps + author; chunks
  embed/upsert and are retrievable; a question can cite a shiur chunk; reject sets status.

Show: approve a reviewed shiur, then ask a question whose answer cites the shiur with a
working play-from-timestamp.
```

---

### Prompt 29 — Reading / viewing experience (6e)

```
Give maayan a real reading surface for long learning sessions, not just search results.
Follow CLAUDE.md. Mostly FRONTEND, plus one thin read-only route for source-in-context.

Requirements:
- Typography: a Hebrew serif suited to nikkud (e.g. Frank Ruehl / Taamey — bundle or
  webfont), larger line-height, correct bidi for mixed He/En, selectable text. Reading
  modes: light / sepia / dark + adjustable font size, persisted in localStorage.
- Source-in-context: tapping a citation opens the FULL section (perek/os) with the cited
  segment highlighted, not just the snippet. Add a thin GET /api/source?ref=... (or reuse
  the store) returning the section's chunks by section_path; logic stays in the existing
  ChunkStore/retriever — the route is a thin read.
- Library tab (from Prompt 23): a "sefer browser" — browse the corpus as a book (Tanya by
  chapter, Torah Ohr by parsha, shiurim by title) from existing chunk metadata; read →
  tap to ask → tap to connect. Read-only; no new write paths.
- Distraction-free full-screen reader for a single source or a composed shiur (reuse the
  compose export markdown rendering).
- Tests: /api/source returns a section's chunks ordered by section_path; the Library list
  groups by book/source from existing data; reading-mode toggles persist (DOM assertions).

Show: tap a citation in an answer to read it in full context, switch to sepia, and browse
Tanya by chapter in the Library tab.
```

---

### Prompt 30 — Beyond typing: OCR capture + highlight-to-act + quick-capture inbox (6d)

```
Add non-typing capture surfaces. Follow CLAUDE.md. Additive — each piece is independent;
ship what earns its keep. Mirror the Transcriber DI pattern for OCR.

Requirements:
- OCR (maayan/ocr/): an OCRer protocol ocr(image_path, lang) -> str with a FakeOCRer (tests)
  and a TesseractOCRer (lang "heb", lazy import, `ml`/system dep) + a factory selecting
  "none" | "tesseract" | "cloud" (cloud raises NotImplementedError as a documented swap).
  Config: ocr_backend ("none"). Route POST /api/ocr (multipart image, auth-aware) → text,
  which the UI drops into a source-quote or a connection/seed body for review (never
  auto-ingested — same human gate).
- Highlight-to-act on mobile: long-press select inside a source → context menu Connect /
  Define term / Quote into seed, wiring the EXISTING annotate/term/seed flows (no new
  services). Make the desktop term-prefill gesture a first-class mobile gesture.
- Quick-capture inbox: a one-tap "capture a thought" (voice via Prompt 24/26, or text) that
  lands in an unsorted inbox (reuse CaptureService with a nullable thread, or a light inbox
  table) to triage into a thread later. List + "move to thread" action.
- Tests (FakeOCRer; mock services): /api/ocr returns text and never auto-ingests; inbox items
  persist and move into a thread; highlight-to-act calls the existing endpoints.

Show: photograph a page of a sefer not on Sefaria, OCR it, and promote a connection from it
into the corpus through the normal review gate.
```

---

## Checkpoints (per the house Definition of Done)

After each prompt: `make test` (transcriber/OCRer mocked — no real Whisper/cloud), then
`make typecheck`, then `make lint`; new tunables land in `config.py`; no hardcoded
models/URLs/keys. Re-check the standing invariants: **default-deny is never bypassed**
(shiur chunks are retrieved like any other and still gated), **printed text stays
immutable** (shiur/expert/derived/term only layer on top), **author is required + sticky**
on every human contribution, and **auth-aware** routes when `AUTH_ENABLED=true`.
