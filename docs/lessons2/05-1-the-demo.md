# Lesson 5.1 — The five-minute demo

> Module 5, Lesson 1 · ~12 min read + a rehearsal.
> The one question this answers: **if I have five minutes and someone's attention, exactly what
> do I type, and what do I point at, to make the upgrade land?**

A demo is a story with a payoff. The story here is "it stopped being a search box and started
learning like a chavrusa." Below is an exact script — commands in order, and the one line to say
at each beat. Rehearse it until it's muscle memory; nothing kills a demo like fumbling syntax.

---

## Before they arrive (setup)

- Qdrant up, corpus indexed, a working backend. Pick **one conceptual question** you know your
  corpus answers well, and **one question you know it can't** (for the refusal beat).
- Have the terminal font large. Pre-type nothing — typing live is part of the credibility.

---

## The script (≈5 minutes)

**Beat 1 — the baseline (45 sec).** Set the "before."
> "Here's the old way — one search, one answer."
```bash
uv run maayan ask "<your conceptual question>"
```
Point at the **Sources** list and the answer. Say: *"Good, grounded, cited. But it's a lookup —
it found passages and reported them."*

**Beat 2 — ask better (60 sec).** Show retrieval getting smarter.
> "Now let it ask the question several ways and fuse the results."
```bash
uv run maayan ask "<same question>" --expand
```
Point at a source in the list that **wasn't** there in Beat 1. Say: *"It rephrased the question,
even imagined a source passage, and searched with all of them. That source it just found? My
original wording missed it."*

**Beat 3 — the payoff: it thinks (90 sec).** This is the moment.
> "Now watch it study the sources before answering."
```bash
uv run maayan ask "<same question>" --expand --reason --show-reasoning
```
**Read the study map aloud** — one source's claim, then "this builds on that, but this is in
tension." Say: *"That's not the answer yet — that's it laying out the sugya, the way a chavrusa
would. Now the answer is built from that map."* Point at where the answer **connects** sources
rather than listing them.

**Beat 4 — the connection (30 sec).** If the study map surfaced a non-obvious link, dwell on it.
> "Notice it connected [S2] to [S1] — that's the kind of thing you'd capture and teach."
This is the "it found a chiddush" beat. It's the most impressive thing the system does; let it
breathe.

**Beat 5 — the honesty (45 sec).** Close on trust, not flash.
> "And it still refuses when it has no source."
```bash
uv run maayan ask "<a question your corpus can't answer>"
```
Point at the refusal. Say: *"No source, no answer — it never invents a mekor. All that
intelligence sits **around** that rule, never through it."*

---

## What to bring out (and what to skip)

- **Bring out:** the *new source* in Beat 2, the *study map* in Beat 3, the *connection* in Beat
  4, the *refusal* in Beat 5. Those four beats are the whole story.
- **Skip:** config flags, RRF math, model-call counts. Nobody watching a demo cares; it's noise
  against the story. (Save it for the engineer in Lesson 5.2.)
- **If a backend call is slow,** narrate it: "it's making a couple of model calls — rephrasing,
  then studying, then answering." Latency becomes evidence of work, not dead air.

> ### Under the hood — why `--show-reasoning` is the star
> The single most persuasive thing you can do is make the *thinking visible*. Anyone can claim an
> AI "reasons"; almost no one shows you the reasoning as an inspectable artifact you can check
> against the sources. The study map is your differentiator on screen — lead with it.

---

## Hands-on

Rehearse the full script end to end **twice**, out loud, on your own corpus. Time it. Then do it
once for a friend who knows nothing about the project and watch where their eyes light up (it'll
be Beat 3 or 4). Adjust which question you open with so those beats hit hardest.

---

## You should now be able to say…

- The five-beat arc: baseline → ask-better → it-thinks → the-connection → the-refusal.
- The four things to *point at*, and the things to *skip* (flags, math, costs).
- Why making the reasoning **visible** (`--show-reasoning`) is the most persuasive move you have.

Next: **[5.2 — Explaining it to three audiences](05-2-three-audiences.md)** — same system,
three framings.
