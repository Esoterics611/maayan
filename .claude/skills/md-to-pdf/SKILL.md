---
name: md-to-pdf
description: Convert a Markdown file into a polished, print-ready PDF — handles Hebrew/RTL + nikkud, readable syntax-highlighted code, a white page background, page-per-chapter breaks, and removal of blank pages. Use when the user asks to turn an .md into a PDF, export docs to PDF, or "make a PDF" from markdown.
---

# Markdown → PDF

Produce a clean PDF from a single Markdown file using `md-to-pdf` (headless Chromium) with a
bundled stylesheet, then strip any blank pages. An HTML/CSS engine is used on purpose: it
renders mixed Hebrew/English (bidi) and nikkud correctly, where a LaTeX/pdflatex path would not.

## Quick run

```bash
bash .claude/skills/md-to-pdf/mdpdf.sh INPUT.md [OUTPUT.pdf]
```

`mdpdf.sh` finds node/Chromium, applies `style.css`, runs Chromium with `--no-sandbox`,
normalizes the output name, and runs `strip_blank_pages.py`.

## Prerequisites (install once)

- **node / npm** (the repo's nvm install is fine; the script adds nvm's bin to PATH).
- **md-to-pdf**, installed *skipping* its browser download (the bundled Chromium download is
  often blocked by sandboxes/firewalls):
  ```bash
  PUPPETEER_SKIP_DOWNLOAD=true npm i -g md-to-pdf
  ```
- **A Chromium for Puppeteer.** Snap works in WSL: `sudo apt-get install -y chromium-browser`
  (installs the chromium snap at `/snap/bin/chromium`). Point Puppeteer at it:
  `export PUPPETEER_EXECUTABLE_PATH=/snap/bin/chromium` (mdpdf.sh auto-detects it).
- **poppler-utils** for blank-page stripping: `sudo apt-get install -y poppler-utils`.

## What the bundled `style.css` encodes (hard-won)

- **Force a white `html`/`body` background + dark text.** Without it, a dark-mode previewer/PDF
  shows the colored text as *blue-on-black*. Set `printBackground: true` (mdpdf.sh does).
- **Hebrew + nikkud font stack:** `FreeSerif, "Noto Serif Hebrew", "Noto Serif", "DejaVu Serif"`.
  FreeSerif positions nikkud well and is usually preinstalled. The browser's Unicode bidi
  algorithm handles mixed LTR/RTL automatically — do **not** force `direction`/`unicode-bidi`.
- **Page breaks ride on headings** (`h1 { break-before: page }`), never on an empty `<div>`.
  An empty break-div renders as its **own blank page** in Chromium (this is the #1 cause of
  blank pages). To break before sections too, add `h2 { break-before: page; }`.
- **Override the syntax-highlight theme.** md-to-pdf injects highlight.js whose default base
  text is pale/low-contrast. `style.css` overrides `.hljs*` token classes with `!important`
  to a dark, readable palette.

## Blank-page stripping

`strip_blank_pages.py` keeps any page with even one character of text or any image, and drops
only fully-empty pages. Uses poppler (`qpdf` fast path if present). Run standalone too:

```bash
python3 .claude/skills/md-to-pdf/strip_blank_pages.py FILE.pdf [OUT.pdf]
```

## Gotchas

- **`md-to-pdf: command not found` / `Permission denied`** — the global bin symlink can lose
  its exec bit, or PATH lacks nvm's bin. mdpdf.sh handles both (PATH fix + `node …/cli.js`).
- **Chromium fails to launch** — pass `--no-sandbox` (mdpdf.sh does); a `dbus/UPower` warning
  on snap Chromium is harmless.
- **Self-contained Markdown** (already carries its own `<style>`, e.g. from the `combine-md`
  skill) converts fine; the bundled `style.css` is additive and the document's inline rules win.
