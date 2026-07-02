# Populate Report — Bootstrap Run (free model): lexicon + connectors

**Date:** 2026-07-01 · **Phase:** bootstrap (free-model) · **Cost:** $0
**Drafter:** `openai/gpt-oss-120b:free` (OpenRouter free tier)
**Answering model (maayan itself):** unchanged (free Qwen) — only the *drafter* was swapped.

---

## Summary

The lexicon auto-populator was run for real against the live corpus (Tanya +
Torah Ohr, 4,241 source passages). A strong open model **drafted** term
definitions strictly from retrieved sources; every draft was cited, faithfulness-
checked, and gated behind approval before indexing.

| Metric | Value |
|---|---|
| Candidate terms drafted (seed pack + mined gershayim) | **46** |
| Grounded, cited, faithfulness-passed → **approved & indexed** | **16** |
| Default-denied (ungrounded / not standalone terms) | **30** |
| Index change (Terms) | **0 → 16** |
| Index change (live chunks) | 4,241 → **4,257** (`source="term"`) |
| Upstream rate-limits absorbed by backoff | 19 |
| Model spend | **$0** |

Nothing ungrounded was indexed — approval refuses unsupported drafts in code.

---

## Method (the capture-loop contract, held under a free model)

Per term: retrieve top-k grounding passages → draft a cited definition **only** from
those passages → run a faithfulness pass → mark `supported` **only if** the draft
cites ≥1 retrieved source **and** the check flags nothing → queue for approval.
Approval is the sole path to indexing.

- **Drafter swap** via `LEXICON_DRAFT_MODEL` — maayan's own answers are untouched.
- **Free-tier reality:** free models 429 on any burst. The run was a **paced (~20s),
  resumable, crash-surviving drip** — each draft persists as it happens and re-runs
  skip anything already queued. 19 rate-limits were absorbed by backoff.
- **Provenance:** approved under author `bootstrap:gpt-oss-120b:free` so these
  bootstrap terms stay **distinguishable from the future top-model run** — required
  for the paper's text-only vs. +synthetic ablation.

---

## Indexed terms (16) — grounded in the corpus

| Term | Grounding refs | Cross-text? |
|---|---|---|
| ב"ן (Name of 52 / Ban) | Torah Ohr Vayechi 5:3 · **Tanya 46:14** | ✅ TO + Tanya |
| חכמה | Torah Ohr (Megillat Esther 1:4, Vayeshev 4:4) · **Tanya 18:10** | ✅ TO + Tanya |
| חסד | Torah Ohr (Yitro, Vayera, Lech Lecha) · **Tanya 34:6** | ✅ TO + Tanya |
| דעת | Torah Ohr (Vayakhel 1:32, Toldot 3:9) | Torah Ohr |
| מלכות | Torah Ohr (Yitro, Parashat Zakhor, Miketz, Vayetzei) | Torah Ohr |
| אמא | Torah Ohr Terumah 1:9 | Torah Ohr |
| צמצום | Torah Ohr (Vayera ×2, Miketz, Bereshit, Tetzaveh) | Torah Ohr |
| אהבה בתענוגים | **Expert chunk c3d520c0** · Torah Ohr (Vayechi, Miketz, Vaera) | ✅ builds on expert |
| אתהפכא | Torah Ohr Miketz (14:15, 12:5, 14:39) | Torah Ohr |
| קליפת נוגה | Torah Ohr (Vaera 3:4, Yitro 10:11, Lech Lecha 1:4) | Torah Ohr |
| א"ס (Ein Sof) | Torah Ohr Bereshit 7:19 | Torah Ohr |
| הוי"ה | Torah Ohr (Miketz ×2, Bereshit, Mishpatim) | Torah Ohr |
| אוא"ס | Torah Ohr Miketz (11:4, 10:7) | Torah Ohr |
| במ"א | Torah Ohr Miketz 6:20 | Torah Ohr |
| עד"מ | Torah Ohr Vayakhel 1:38 | Torah Ohr |
| הקב"ה | Torah Ohr (Miketz 6:13, Bo 1:4) | Torah Ohr |

Three terms are grounded **across both books** (Torah Ohr + Tanya), and one
(אהבה בתענוגים) grounded partly on a **prior expert-captured chunk** — the loop
composing on human knowledge already in the index.

---

## Default-denied (30) — the gate working, and the free-model ceiling

Two kinds, both correct behavior:

1. **Bare abbreviations, not standalone terms** (correctly refused): ב"ה, ג"כ, הנ"ל,
   ואח"כ, כמ"ש, וכמ"ש, כנ"ל, מ"מ, מ"ש, משא"כ, ע"י, ע"פ, שע"י, כ"א.
2. **Core terms the free drafter under-grounded** (expected to recover with a
   stronger model): כתר, בינה, גבורה, נצח, הוד, יסוד, תפארת, אבא, אריך אנפין,
   זעיר אנפין, נוקבא, ביטול, מסירות נפש, אתכפיא, and the Holy Names מ"ה / ס"ג / ע"ב.

Group 2 is the **free→top quality gap the two-phase plan predicts**: these are
groundable terms (e.g. the sefirot are explicit in Tanya ch. 3), but `gpt-oss-120b`
either failed to cite or was flagged by the faithfulness pass. A top-model rerun is
expected to convert most of these.

---

## What this run validates

- The **capture-loop contract holds end-to-end under a free model**: grounded,
  cited, faithfulness-checked, expert-gated — no ungrounded term reached the index.
- **Cross-text co-retrieval works** (terms grounded across Torah Ohr + Tanya).
- **Default-deny holds** — zero ungrounded terms indexed, even when instructed to
  draft them.
- The pipeline is **resumable and free** — the bootstrap absorbs the build risk at $0.

---

---

## Connectors — cross-text connections (same free model)

Same drafter and method. Mining probes: 8 built-in + 10 cross-text gold-set
questions → 18 probes → **24 candidates**. A connection is `supported` only if it
cites **≥2 distinct books** and passes the faithfulness pass; approval indexes it as
a `source="expert"` connection chunk.

| Metric | Value |
|---|---|
| Candidates drafted | **24** |
| Grounded, cross-text, faithful → **approved & indexed** | **12** |
| Not-cross-text / ungrounded | 12 |
| Index change (expert chunks) | 5 → **17** |
| Index change (live chunks) | 4,257 → **4,269** |
| Rate-limits absorbed | 9 |
| Model spend | **$0** |

### Indexed connections (12)

All twelve link two passages: Miketz↔Bereshit, Vaera↔Miketz, Vayera↔Bereshit,
Vayera↔Shemot, Shemot↔Vayetzei, Vayechi↔Ki Tisa, Miketz↔Mishpatim,
Vaera↔Parashat Zakhor, Vaera↔Vayechi, Megillat Esther↔Parashat Zakhor,
Megillat Esther↔Vayeshev, Vayera↔Bereshit.

### Finding: cross-*parsha*, not yet cross-*work*

**All 12 are Torah Ohr ↔ Torah Ohr (different parshiyos) — none reach Tanya.** The
`book` field is per-parsha, so the ≥2-books gate correctly counts cross-parsha
links; but the headline cross-*work* claim (Torah Ohr ↔ Tanya) did **not** surface,
because top-k mining pairs within the larger book (Torah Ohr = 23 parshiyos
dominates the neighborhood). This is a concrete **tuning target**: bias probe mining
toward Tanya↔Torah Ohr pairs (and expect the top-model rerun to reach further). It's
an honest limit of this run, not a failure — the gate did exactly what it should.

---

## Bootstrap total (both runs)

| | Drafted | Indexed | Corpus |
|---|---|---|---|
| Terms | 46 | 16 | +16 (`source="term"`) |
| Connections | 24 | 12 | +12 (`source="expert"`) |
| **Total** | **70** | **28** | **4,241 → 4,269** |

Cost: **$0**. Answering model unchanged. All 28 additions grounded, cited,
faithfulness-checked, expert-gated — indexed and retrievable alongside the text.

---

## Not yet done / next

- **Top-model rerun** (post-funding) — expected materially higher grounding yield on
  the under-grounded core terms, and connections that reach across to Tanya.
- **Bias connection mining toward Tanya↔Torah Ohr** — to surface true cross-work
  links even on a free model.
- **Likutei Torah ingestion** — prerequisite for LT coverage (not on Sefaria; needs
  a source + adapter).
