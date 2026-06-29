#!/usr/bin/env python3
"""Assemble the Course 2 lesson files into one PDF-ready Markdown document.

Mirrors ``build_curriculum.py`` exactly — it **reuses** that script's shared
machinery (the self-contained ``<style>`` block, heading-demotion, link-flattening,
and slug helpers) so the two courses render identically — but points at the Course 2
lessons under ``docs/lessons2/`` and emits ``docs/CURRICULUM2_FULL.md`` with its own
title page and module map.

Re-run after editing any Course 2 lesson:  ``python docs/build_curriculum2.py``

Convert to PDF with any HTML/CSS-based engine (Hebrew bidi handled correctly):

    md-to-pdf docs/CURRICULUM2_FULL.md                 # npm i -g md-to-pdf
    pandoc docs/CURRICULUM2_FULL.md -o curriculum2.pdf --pdf-engine=weasyprint
"""

from __future__ import annotations

import datetime
from pathlib import Path

# Reuse Course 1's styling + transforms (this script lives beside it in docs/).
from build_curriculum import STYLE, clean_label, slug_lesson, slug_module, transform_body

LESSONS_DIR = Path(__file__).parent / "lessons2"
OUTPUT = Path(__file__).parent / "CURRICULUM2_FULL.md"

# Module number -> (title, one-line goal). Titles mirror docs/CURRICULUM2.md.
MODULES: dict[int, tuple[str, str]] = {
    0: ("From lookup to reasoning (orientation)",
        "See, in your own terminal, the difference between the old single-shot answer and the "
        "new reasoning answer — and hold a map of the three moves before we open each box."),
    1: ("Asking better (query intelligence)",
        "Understand why one verbatim query is a weak net, and exactly how maayan widens it — "
        "deterministically with your lexicon, and generatively with reformulations + HyDE — "
        "then fuses the results."),
    2: ("Thinking before answering (reasoning & synthesis)",
        "Understand the two-stage answer — analyze the sources into a study map, then weave a "
        "grounded answer from it — why it suits chassidus, and how the trust core stays intact."),
    3: ("Proving the lift (evaluation & cost)",
        "Replace “this feels smarter” with numbers and a clear sense of what each mode costs."),
    4: ("Tuning & playing (making it yours)",
        "Confidently turn the knobs — and even edit the prompts — to fit your corpus, your "
        "model, and your taste, without breaking the guarantees."),
    5: ("Demoing & explaining (telling the story)",
        "Show this to other people and have it land — scholar, engineer, or skeptic — and know "
        "how to carry the pattern forward."),
}


def main() -> None:
    files = sorted(p for p in LESSONS_DIR.glob("[0-9][0-9]-*.md"))
    if not files:
        raise SystemExit(f"No lesson files found in {LESSONS_DIR}")

    by_module: dict[int, list[Path]] = {}
    for f in files:
        by_module.setdefault(int(f.stem[:2]), []).append(f)

    today = datetime.date.today().isoformat()
    lo, hi = min(by_module), max(by_module)
    parts: list[str] = [STYLE]

    # --- Title page -------------------------------------------------------
    parts.append(
        '<div class="title-page">\n'
        '<p class="mark">מעיין</p>\n'
        '<p class="wordmark">maayan</p>\n'
        '<p class="tagline">Course 2 — The Intelligence Layer: from lookup to reasoning</p>\n'
        '<p class="sub">How the upgrade works, how to run and tune it, how to demo it, and how '
        "to reuse the pattern — a second self-study curriculum for the owner of this system.</p>\n"
        '<p class="brand">maayan.ai</p>\n'
        f'<p class="meta">Modules {lo}–{hi} &middot; {len(files)} lessons &middot; {today}</p>\n'
        "</div>\n"
    )

    # --- Table of contents ------------------------------------------------
    toc = ['<div class="toc">', "<h1>Contents</h1>", "<ul>"]
    for n in sorted(by_module):
        title, _ = MODULES[n]
        toc.append(
            f'<li class="mod"><a href="#{slug_module(n)}">'
            f"Module {n} — {clean_label(title)}</a></li>"
        )
        for f in by_module[n]:
            les_title, _ = transform_body(f.read_text(encoding="utf-8"))
            les_title = clean_label(les_title or f.stem)
            toc.append(f'<li class="les"><a href="#{slug_lesson(f.stem)}">{les_title}</a></li>')
    toc.append("</ul>\n</div>")
    parts.append("\n".join(toc))

    # --- Modules & lessons ------------------------------------------------
    for n in sorted(by_module):
        title, goal = MODULES[n]
        parts.append(f'<h1 id="{slug_module(n)}">Module {n} — {title}</h1>')
        parts.append(f'<p class="module-goal">{goal}</p>')
        for f in by_module[n]:
            _, body = transform_body(f.read_text(encoding="utf-8"))
            parts.append(f'<a id="{slug_lesson(f.stem)}"></a>\n')
            parts.append(body)

    OUTPUT.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}  ({len(files)} lessons across {len(by_module)} modules)")


if __name__ == "__main__":
    main()
