#!/usr/bin/env python3
"""Assemble the individual lesson files into one PDF-ready Markdown document.

Reads ``docs/lessons/0N-*.md`` (the per-lesson files), and emits a single
self-contained ``docs/CURRICULUM_FULL.md`` that carries its own layout so it can be
converted straight to a properly-formatted PDF:

  * an inline ``<style>`` block (fonts tuned for Hebrew+nikkud, page size/margins,
    branding colours, page-break rules) — so the file is self-contained,
  * a branded **maayan.ai** title page,
  * a clickable **table of contents** (module + lesson, anchored),
  * each module as a chapter and **each lesson on its own page** (CSS page breaks),
  * lesson body transforms: heading levels demoted one step so the module/lesson
    hierarchy is clean, and relative/anchor links flattened to plain text (only
    ``http(s)`` links stay clickable) so the PDF has no dead internal links.

Re-run after editing any lesson:  ``python docs/build_curriculum.py``

Convert to PDF with any HTML/CSS-based engine (they handle Hebrew bidi correctly;
a LaTeX/pdflatex path would not). For example:

    md-to-pdf docs/CURRICULUM_FULL.md                 # npm i -g md-to-pdf
    pandoc docs/CURRICULUM_FULL.md -o curriculum.pdf --pdf-engine=weasyprint
    weasyprint <(pandoc docs/CURRICULUM_FULL.md -t html5) curriculum.pdf
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path

LESSONS_DIR = Path(__file__).parent / "lessons"
OUTPUT = Path(__file__).parent / "CURRICULUM_FULL.md"

# Module number -> (title, one-line goal). Titles mirror docs/CURRICULUM.md.
MODULES: dict[int, tuple[str, str]] = {
    0: ("Orientation: the whole loop in your hands",
        "See the entire system work once, end to end, and hold a mental map before zooming in."),
    1: ("Turning text into searchable meaning (embeddings & chunking)",
        "Understand the “R” inputs — how text becomes numbers a computer can compare, "
        "and why you chunk it the way you do."),
    2: ("Finding the right passages (vector DB & hybrid search)",
        "Understand where chunks live and how a query pulls back the relevant few."),
    3: ("The trust core (generation, grounding, default-deny)",
        "Understand how retrieved passages become a cited answer, and how the system refuses "
        "rather than fabricate."),
    4: ("Knowing if it's actually good (evaluation)",
        "Replace “it feels right” with numbers."),
    5: ("How it's built to last (the engineering spine)",
        "Understand the house rules that make the system testable, swappable, and trustworthy."),
    6: ("The differentiator (the capture & develop loop)",
        "Understand how a scholar's reasoning becomes durable, retrievable, attributed knowledge."),
    7: ("Running it for real (operating & tuning)",
        "Confidently operate, tune, and feed the system day to day."),
    8: ("The horizon (extending it well)",
        "See where this goes next and how to add capability without breaking the guarantees."),
}

# maayan brand palette.
INK = "#15323b"        # near-black text
TEAL = "#0f766e"       # primary (wellspring)
DEEP = "#0b3b46"       # module headings
ACCENT = "#b45309"     # warm accent (callout border)
MUTED = "#5b6b70"

STYLE = f"""<style>
@page {{
  size: A4;
  margin: 22mm 20mm 20mm 20mm;
}}
:root {{ --ink: {INK}; --teal: {TEAL}; --deep: {DEEP}; --accent: {ACCENT}; --muted: {MUTED}; }}

/* Force a white page + dark text so the document reads correctly regardless of the
   viewer's theme (a dark-mode previewer otherwise shows dark text on black). */
html {{ background: #ffffff; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
body {{
  /* FreeSerif & Noto carry full Hebrew + nikkud; the browser/UBA handles bidi. */
  font-family: "FreeSerif", "Noto Serif Hebrew", "Noto Serif", "DejaVu Serif", Georgia, serif;
  font-size: 11.5pt;
  line-height: 1.5;
  background: #ffffff;
  color: var(--ink);
  max-width: 46rem;
  margin: 0 auto;
  padding: 1rem;
}}

h1, h2, h3, h4 {{ line-height: 1.25; break-after: avoid; }}
h1 {{ color: var(--deep); font-size: 25pt; margin: 0 0 .2em; }}
h2 {{ color: var(--teal); font-size: 18pt; border-bottom: 2px solid var(--teal); padding-bottom: .15em; }}
h3 {{ color: var(--deep); font-size: 13.5pt; }}
h4 {{ color: var(--muted); font-size: 12pt; text-transform: none; }}

p, li {{ orphans: 2; widows: 2; }}
a {{ color: var(--teal); text-decoration: none; }}

/* "Under the hood" / aside callouts (lesson blockquotes). */
blockquote {{
  border-left: 3px solid var(--accent);
  background: #fbf6ee;
  margin: 1em 0;
  padding: .5em 1em;
  color: #3a3a3a;
  break-inside: avoid;
}}
blockquote h3, blockquote h4 {{ color: var(--accent); margin-top: .2em; }}

code {{
  font-family: "DejaVu Sans Mono", "Courier New", monospace;
  font-size: 9.5pt;
  background: #eef4f3;
  color: #143230;            /* dark — readable inline code */
  padding: .08em .3em;
  border-radius: 3px;
}}
pre {{
  background: #f4f7f7;
  border: 1px solid #d8e3e1;
  border-radius: 5px;
  padding: .7em .9em;
  overflow-wrap: break-word;
  white-space: pre-wrap;
  break-inside: avoid;
  font-size: 9.5pt;
}}
pre code {{ background: none; padding: 0; font-size: 9.5pt; color: #1b2b2b; }}

/* Override any injected syntax-highlight theme (e.g. md-to-pdf's highlight.js),
   which defaults to pale, low-contrast text. Force dark base + a readable palette. */
pre code, pre code.hljs, .hljs {{ color: #1b2b2b !important; background: transparent !important; }}
.hljs-comment, .hljs-quote {{ color: #5c6770 !important; font-style: italic; }}
.hljs-string, .hljs-attr, .hljs-addition {{ color: #0a6b3a !important; }}     /* green */
.hljs-keyword, .hljs-selector-tag, .hljs-literal, .hljs-built_in,
.hljs-type, .hljs-deletion {{ color: #a3192e !important; }}                    /* red  */
.hljs-number, .hljs-meta, .hljs-link, .hljs-symbol {{ color: #0b4f9e !important; }}  /* blue */
.hljs-title, .hljs-section, .hljs-name, .hljs-function,
.hljs-class .hljs-title, .hljs-variable {{ color: #5a2ca0 !important; }}        /* purple */

table {{ border-collapse: collapse; width: 100%; font-size: 10.5pt; break-inside: avoid; }}
th, td {{ border: 1px solid #cdd9d7; padding: .35em .55em; text-align: left; vertical-align: top; }}
th {{ background: #e8f1ef; color: var(--deep); }}

hr {{ border: none; border-top: 1px solid #d8e3e1; margin: 1.4em 0; }}

.page-break {{ break-before: page; page-break-before: always; }}

/* Title page. */
.title-page {{ text-align: center; padding-top: 22vh; }}
.title-page .mark {{ font-size: 64pt; color: var(--teal); margin: 0; line-height: 1; }}
.title-page .wordmark {{ font-size: 30pt; letter-spacing: .06em; color: var(--deep); margin: .1em 0 0; }}
.title-page .tagline {{ font-size: 15pt; color: var(--ink); margin: 1.2em auto .2em; max-width: 32rem; }}
.title-page .sub {{ font-size: 12pt; color: var(--muted); }}
.title-page .brand {{ margin-top: 3.5em; font-size: 13pt; color: var(--teal); letter-spacing: .12em; }}
.title-page .meta {{ font-size: 10pt; color: var(--muted); margin-top: .3em; }}

/* Table of contents. */
.toc h1 {{ font-size: 20pt; color: var(--deep); }}
.toc ul {{ list-style: none; padding-left: 0; }}
.toc .mod {{ font-weight: bold; color: var(--deep); margin-top: .7em; }}
.toc .les {{ padding-left: 1.4rem; color: var(--ink); }}
.toc a {{ color: inherit; }}

.module-goal {{ color: var(--muted); font-style: italic; margin: .2em 0 1.2em; }}
</style>
"""

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^(?P<bq>>*\s*)(?P<hashes>#{1,6})(?P<rest>\s.*)$")
# Markdown link whose target is NOT an http(s) URL -> keep only the visible text.
_REL_LINK = re.compile(r"\[([^\]]+)\]\((?!https?://)[^)]*\)")


def clean_label(text: str) -> str:
    """Make a heading safe as raw-HTML TOC link text: drop md emphasis, escape & < >."""
    text = re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"\1", text)  # *italic* / **bold** -> plain
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return text


def slug_module(n: int) -> str:
    return f"module-{n}"


def slug_lesson(stem: str) -> str:
    # "03-2-grounded-prompt" -> "lesson-3-2"
    a, b, *_ = stem.split("-")
    return f"lesson-{int(a)}-{int(b)}"


def lesson_number(stem: str) -> str:
    a, b, *_ = stem.split("-")
    return f"{int(a)}.{int(b)}"


def transform_body(text: str) -> tuple[str, str]:
    """Demote headings by one level and flatten relative links. Returns (title, body).

    The first heading line is the lesson's ``# Lesson X.Y — Title``; we capture its
    text for the TOC, then demote it (and every other heading) one step so it nests
    under the module H1. Code fences are left untouched.
    """
    out: list[str] = []
    title = ""
    in_fence = False
    for line in text.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue

        m = _HEADING.match(line)
        if m:
            rest = m.group("rest").strip()
            if not title and rest.lower().startswith("lesson"):
                title = rest
            hashes = m.group("hashes")
            if len(hashes) < 6:
                hashes += "#"  # demote one level (cap at h6)
            line = f"{m.group('bq')}{hashes}{m.group('rest')}"
        line = _REL_LINK.sub(r"\1", line)
        out.append(line)
    return title, "\n".join(out).strip()


def main() -> None:
    files = sorted(p for p in LESSONS_DIR.glob("[0-9][0-9]-*.md"))
    if not files:
        raise SystemExit(f"No lesson files found in {LESSONS_DIR}")

    # Group lessons by module number.
    by_module: dict[int, list[Path]] = {}
    for f in files:
        by_module.setdefault(int(f.stem[:2]), []).append(f)

    today = datetime.date.today().isoformat()
    parts: list[str] = [STYLE]

    # --- Title page -------------------------------------------------------
    parts.append(
        '<div class="title-page">\n'
        '<p class="mark">מעיין</p>\n'
        '<p class="wordmark">maayan</p>\n'
        '<p class="tagline">Learning maayan — a hands-on path through RAG</p>\n'
        '<p class="sub">A self-study curriculum for the owner of an esoteric-Torah '
        "Retrieval-Augmented Generation system.</p>\n"
        '<p class="brand">maayan.ai</p>\n'
        f'<p class="meta">Modules 0–8 &middot; {len(files)} lessons &middot; {today}</p>\n'
        "</div>\n"
    )
    parts.append('<div class="page-break"></div>\n')

    # --- Table of contents ------------------------------------------------
    # Heading is explicit HTML (not markdown) so it renders even in parsers that keep
    # the content of a raw <div> block verbatim.
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
        parts.append('<div class="page-break"></div>\n')
        parts.append(f'<a id="{slug_module(n)}"></a>\n')
        parts.append(f"# Module {n} — {title}\n")
        parts.append(f'<p class="module-goal">{goal}</p>')
        for f in by_module[n]:
            _, body = transform_body(f.read_text(encoding="utf-8"))
            parts.append('<div class="page-break"></div>\n')
            parts.append(f'<a id="{slug_lesson(f.stem)}"></a>\n')
            parts.append(body)

    OUTPUT.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}  ({len(files)} lessons across {len(by_module)} modules)")


if __name__ == "__main__":
    main()
