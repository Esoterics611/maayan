# maayan — A Beis Medrash with Memory

*An overview for supporters*

---

## What this is

In a beis medrash, the text on the page is only half of what is learned. The other
half is the reasoning around it — how a teacher connects one passage to another, the
correction he makes, the framework he brings from a text not on the table that
explains the one that is. That reasoning is rarely written down, and in p'nimiyus
haTorah — chassidus and Kabbalah — it is often what the meaning actually depends on.
The printed texts are available; the reasoning that links them is not.

**maayan** (מעיין, "wellspring") keeps both: the texts, and a faithful, attributed
record of how a scholar reasons over them — so that reasoning accumulates, and a
later question can draw on what has already been worked out, not only on what is
printed.

---

## What exists today

The system in place does four things, in order, for any question put to it.

1. **It holds the source texts.** It ingests Torah sources (the initial focus is
   Likutei Amarim — Tanya, Part I) from Sefaria, keeping each natural unit of the
   text — a chapter, a passage — as its own unit. The Hebrew is preserved as
   written, nikkud included.

2. **It finds the relevant passages.** Given a question, it retrieves the pieces of
   text that actually bear on it, searching by meaning and by wording together, in
   Hebrew. No keyword guessing on the part of the user.

3. **It answers only from what it found, with citations — or it declines.** An
   answer is composed strictly from the retrieved passages, and every claim points
   back to the source it came from. This is the part worth dwelling on: if the
   retrieved material does not actually support an answer, the system **refuses**,
   rather than inventing one. That refusal is built into the code, not just
   requested politely of the language model. The result is a tool that can be
   trusted not to fabricate — which, for Torah study, is the whole ballgame.

4. **It captures the scholar's contribution.** When an expert reads an answer and
   corrects it, or draws a connection the texts alone don't make explicit, that
   contribution is recorded — attributed to the person who made it — and folded back
   into the same body of searchable knowledge. The next question can retrieve it
   alongside the printed text.

That fourth step is the point of the whole project. Everything else is
infrastructure that makes it trustworthy. The texts are common property; what is
scarce, and what we are trying to preserve, is the expert's reasoning over them.

---

## The next phase: from a note that sits there, to knowledge that grows

Building and testing the capture step taught us something we hadn't planned for, and
it has reshaped the next phase of work.

When a scholar adds a contribution, he is usually not just correcting a sentence. He
is doing two things at once. He is **planting a piece of knowledge** — often a
framework drawn from texts outside the current corpus — and he is **giving a
direction**: *now find where this idea is hinted at in the text in front of us.*

A real example from our testing: a scholar noted that a certain concept
(*ahava b'ta'anugim*) is explained at length in one body of chassidic literature,
and then instructed — *find where this is alluded to in Tanya.* That is exactly how
learning happens in a beis medrash: the teacher supplies the framework and points the
student toward the text, and the student does the work of grounding it.

The current system stored that note but did nothing with the instruction. The next
phase makes the instruction something the system can actually carry out:

- The scholar **plants a seed**: a piece of knowledge plus a direction for developing it.

- The system **develops the seed** — it goes back to the actual texts, retrieves the
  passages that bear on the direction, and writes a grounded, cited elaboration that
  fulfills the instruction. The same discipline applies: it works only from the real
  sources, cites them, and honestly reports when the text does **not** support the
  connection.

- The scholar **reviews and approves** (or rejects). Nothing the system develops on
  its own becomes part of the permanent corpus until a human has approved it. Once
  approved, it becomes new, attributed knowledge that future questions can retrieve —
  with its full lineage attached: which scholar's seed it grew from, which passages
  it was grounded in.

- These exchanges accumulate as **topic threads** — a line of inquiry that builds over
  many turns and can be reopened later, so a subject deepens over time rather than
  starting over with each session.

Throughout, the printed text is never altered. The scholar's seeds and the developed
elaborations layer *on top* of the sources as clearly-labeled, separately-attributed
material. At any point you can see exactly what is printed text, what came from a named
expert, and what was developed from a seed and approved.

---

## What this becomes over time

Run this loop across many questions, many seeds, and many scholars, and what
accumulates is not just a pile of notes. It is a structured record of **how this body
of knowledge is learned** — which passages illuminate which, which outside frameworks
unlock which texts, where the genuine connections are and where they aren't. The
relationships between texts, which today live only in the minds of a handful of
people, become something durable that the next student can draw on.

A note on what to call it, since the question comes up: it is tempting to call this
"a model," but we would be careful with that word in front of technically literate
supporters. We are not training a machine on this material in the way that phrase
usually implies. What grows is a **living corpus** — the texts, plus the accumulated,
attributed, grounded reasoning over them, plus a faithful method for adding more. The
honest description is the most compelling one: a study system that builds a memory of
how a tradition is learned, one reviewed contribution at a time. Over enough
contributions, that memory does come to function as a map of the corpus's own internal
logic — but it earns that standing from real scholarship that has been checked, not
from a claim made on its behalf.

---

## Where it stands, and what support enables

The foundation is built and working: ingestion, retrieval, grounded and cited answers
with an enforced refusal when the texts don't support a claim, the expert capture loop,
a local web interface for asking and contributing, and a measurement harness that
scores retrieval quality against a hand-built answer key — so improvements are judged
by numbers, not impressions.

The next phase — the seed-develop-approve loop and persistent topic threads described
above — is planned in detail and ready to build. Support at this stage goes toward:

- Building out that loop and putting it in front of scholars to use in earnest.

- Expanding the corpus beyond the initial Tanya focus to the broader literature the
  connections actually reach into.

- The scholars' time — the contributions are the asset, and a knowledgeable reviewer's
  hours are what turn the system from a competent search tool into a genuine record of
  how this Torah is learned.

---

*Technical note: the system runs locally — the texts, the search, and all the
application code stay on the user's own machine; only the final composition of an
answer is sent to an outside service, and that piece is replaceable with a fully local
one. Source texts are used under Sefaria's CC-BY-NC license, for personal,
non-commercial study, with attribution.*
