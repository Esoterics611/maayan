"""Hebrew/text normalization for ingested segments.

Pure, testable functions. The job: strip Sefaria's editorial markup/HTML and
normalize whitespace, while **keeping nikkud** (vowel points) intact — they are
part of the text for chassidus/Kabbalah.

There is a deliberate, documented hook for *rashei-teivot* (abbreviation)
expansion (`expand_rashei_teivot`). It is a no-op for now — do not implement it
speculatively; wire real expansion in later behind `enabled=True`.
"""

from __future__ import annotations

import html
import re

# Sefaria wraps translator/editor apparatus in specific tags. We drop these
# *with their content* because they are editorial, not source text:
#   - footnote markers:  <sup class="footnote-marker">...</sup>
#   - footnote bodies:   <i class="footnote">...</i>
# Vilna page markers (<i data-overlay=...></i>) are empty and fall out with the
# generic tag strip below.
_FOOTNOTE_MARKER = re.compile(r'<sup\b[^>]*class="[^"]*footnote-marker[^"]*"[^>]*>.*?</sup>', re.S)
_FOOTNOTE_BODY = re.compile(r'<i\b[^>]*class="[^"]*footnote[^"]*"[^>]*>.*?</i>', re.S)
_ANY_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


def strip_markup(raw: str) -> str:
    """Remove HTML/editorial markup, keep the underlying text. Keeps nikkud."""
    text = _FOOTNOTE_MARKER.sub("", raw)
    text = _FOOTNOTE_BODY.sub("", text)
    text = _ANY_TAG.sub("", text)
    text = html.unescape(text)
    return text


def normalize_whitespace(text: str) -> str:
    """Collapse all runs of (unicode) whitespace to a single space and trim."""
    return _WHITESPACE.sub(" ", text).strip()


def expand_rashei_teivot(text: str, *, enabled: bool = False) -> str:
    """Hook for expanding rashei-teivot (Hebrew abbreviations), e.g. וכו׳, ית׳.

    Intentionally a no-op until a vetted expansion table exists. Kept as a single
    chokepoint so it can be turned on (config-driven) without touching callers.
    """
    if not enabled:
        return text
    # Future: apply abbreviation-expansion table here.
    return text


def normalize_text(raw: str, *, expand_abbreviations: bool = False) -> str:
    """Full normalization pipeline for one segment of text.

    strip markup → unescape entities → collapse whitespace → (optional) expand
    rashei-teivot. Nikkud is preserved throughout.
    """
    text = strip_markup(raw)
    text = normalize_whitespace(text)
    text = expand_rashei_teivot(text, enabled=expand_abbreviations)
    return text
