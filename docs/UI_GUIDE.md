# maayan — User guide to the app (web + mobile)

> How to **use** maayan from the browser — on a laptop or as an installed phone app.
> The UI is a thin face over the same services the CLI uses, so everything here is the
> same capture loop, the same grounding, the same default-deny.
>
> The one rule that governs the whole app: **nothing enters your Knowledge base without
> your review.** Voice, photos, and captured thoughts all land in a field for you to
> check first; printed text (Tanya / Torah Or / Likutei Torah) is **never** edited.

---

## 1. Open it

```bash
make up      # start the local vector DB (Qdrant)
make ui      # → http://127.0.0.1:8000
```

Open the printed URL in your browser. (On a phone on the same network, use the LAN/Tailscale
URL maayan prints, not `127.0.0.1`.)

**Install it on your phone (PWA).** In the phone browser, open the URL, then *Share → Add to
Home Screen* (iOS) or *⋮ → Install app* (Android). It launches full-screen like a native app
and keeps already-loaded reading available offline. Generation and capture still need the
server reachable.

**Login.** If the deployment has accounts turned on (`AUTH_ENABLED=true`), you'll hit a login
page first; your display name then auto-fills the **author** field on everything you save.

---

## 2. The layout

- **Header** — `☰` opens the topics/lexicon drawer (mobile); `📥` opens the **quick-capture
  inbox** (below).
- **Left drawer** — your **topic threads**, the **lexicon** (defined terms), and a
  **Knowledge base** health panel.
- **Center** — the conversation for the active thread, with the composer (Ask + the
  *Seed ▾ / Term ▾ / Compose ▾ / Shiur ▾* tools) underneath.
- **Bottom tab bar (mobile)** — Ask · Threads · Capture · Library.

Everything happens inside a **topic thread** — start or reopen one from the drawer first.

---

## 3. Ask, teach, grow (the capture loop)

- **Ask** — type a question (or dictate it, §5). You get a **grounded, cited** answer or an
  honest refusal when the corpus doesn't support one. Sources are badged
  **sefaria · expert · derived · term · shiur**; tap a ref to **read it in context** (§4).
- **Connect sources** — after an answer, tick **two or more** sources (e.g. a Tanya passage +
  a Likutei Torah passage), write the insight, and **Connect**. Saved as an `expert`
  connection spanning both refs; it surfaces on future questions. (Author required, remembered.)
- **Seed → Develop → Approve** — open *Seed ▾*, write seed knowledge + a *directive* (what the
  model should develop; kept out of the embedded text), **Plant seed**, then **Develop this**.
  Review the grounded proposal and **Approve** (indexed as a `derived` chunk) or **Reject**
  (indexed: nothing).
- **Define a term** — open *Term ▾* to register a Holy Name / technical term (canonical, type,
  definition, surface forms, gematria). It's badged **term**, shows in the lexicon, and is
  protected from abbreviation mangling.
- **Compose** — open *Compose ▾* to draft a grounded, section-by-section shiur outline; fill,
  review, export to Markdown, and optionally promote one section's connection into the corpus.
- **Retract** — the **Retract ✕** button on any *layered* source (expert/derived/term/shiur)
  removes it from the corpus (stays gone across a rebuild). Printed text is never retractable.

---

## 4. Read in context

Tap any source ref (in an answer or the lexicon) to open the **reader**: the cited segment
highlighted within its surrounding passage. From the reader head you can switch **light /
sepia / dark** and change **text size** (remembered). The **Library** tab browses every
indexed work → its sections → the reader.

---

## 5. Voice dictation (every field)

Tap the **🎤** next to any text field and speak instead of typing — built for Hebrew
(nikkud, gershayim) on a phone keyboard. It **listens continuously**, transcribing as you go
and riding through your natural pauses; **tap 🎤 again to stop.** The **עב / EN** toggle
switches the dictation language. Where the browser has no on-device speech (e.g. some iOS
Safari), it records and transcribes on the server instead — same result.

---

## 6. Photograph a page (OCR)

For a sefer that isn't in the corpus, tap **📷** (next to the 🎤 on the Seed and Term fields)
to photograph a page. The text is OCR'd and **dropped into the field for you to review** — it
is **never auto-ingested**; promote it through the normal Connect / Seed / Term gate like
anything else. OCR is off until an operator sets `OCR_BACKEND` (see the hosting guide); when
off, the button reports it.

---

## 7. Highlight-to-act

**Select text inside a source or the reader** and a small menu appears with three actions,
each wiring an existing flow:

- **Connect** — ticks the source you selected in; tick one more, write the insight, Connect.
- **Define term** — opens *Term ▾* pre-filled with the selection as the surface form.
- **Quote → seed** — drops the selection into the *Seed ▾* body to develop from.

On a phone this is a long-press select, then tap the action.

---

## 8. Quick-capture inbox

Tap **📥** in the header to capture a fleeting thought — typed or dictated — without
interrupting your learning. It parks **unsorted** (attached to no thread). Later, open the
inbox and **move** an item into a thread: it becomes a develop-able **seed** there, attributed
to you, and re-enters the normal loop. Captures are private notes until you move them; moving
is the review gate.

---

## 9. Shiur transcription

Open *Shiur ▾* to **record** or **upload** a recording. It transcribes asynchronously (a
progress bar polls the job), then drops you into **review**: edit segments, accept
lexicon-aware corrections, mark **reviewed**, then **approve**. Approval windows the transcript
into `shiur` chunks that are retrievable alongside the text — and a cited shiur source can
**play from its exact moment** in the recording.

---

## 10. The golden rule, restated

| Surface | Where it lands | What promotes it |
|---|---|---|
| Ask | nothing saved | — |
| Connect / Seed→Develop→Approve / Term | Knowledge base | your click |
| Voice / OCR / Inbox | a field or the inbox | your review, then Connect/Seed/Term/Move |
| Shiur | review queue | your **approve** |

You decide what your Assistant learns. The corpus's printed text is read-only; everything you
add is attributed and retractable.

See also: **[RUNBOOK.md](RUNBOOK.md)** (CLI walkthrough) · **[cloud_deploy/](cloud_deploy/README.md)**
(put it online).
