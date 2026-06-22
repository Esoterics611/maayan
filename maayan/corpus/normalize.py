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
from collections.abc import Mapping

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

# Hebrew nikkud (vowel points) + te'amim (cantillation). Stripped only for *matching*
# surface forms — never from stored corpus text (CLAUDE.md: keep nikkud in the corpus).
_NIKKUD = re.compile(r"[֑-ׇ]")
# Gershayim ״ / geresh ׳ and the prime/double-prime + ASCII quotes that stand in for them.
_QUOTE_MARKS = ("״", "׳", "″", "′", '"', "'")


def fold_surface(s: str) -> str:
    """Fold a Hebrew surface form for tolerant matching.

    Drops nikkud/te'amim, removes gershayim/geresh/quote marks, collapses whitespace
    and casefolds — so 'ע״ב' (gershayim), 'ע"ב' (ASCII quote) and 'עב' all compare
    equal. Used to find a term in running text and to build the protected-terms set;
    it never touches stored corpus text.
    """
    s = _NIKKUD.sub("", s)
    for mark in _QUOTE_MARKS:
        s = s.replace(mark, "")
    return _WHITESPACE.sub(" ", s).strip().casefold()


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


def expand_rashei_teivot(
    text: str,
    *,
    enabled: bool = False,
    expansions: Mapping[str, str] | None = None,
    protected: frozenset[str] = frozenset(),
) -> str:
    """Hook for expanding rashei-teivot (Hebrew abbreviations), e.g. וכו׳, ית׳.

    Deliberately NOT a guesser: it only applies an explicit `expansions` table (empty
    by default → no-op, per CLAUDE.md). `protected` is a set of *folded* surface forms
    (see `fold_surface`) — typically the lexicon's terms / Holy Names — that must NEVER
    be expanded even if they appear in the table. A single chokepoint so real expansion
    can be turned on (config-driven) without touching callers, and so registered terms
    are structurally safe from being mangled.
    """
    if not enabled or not expansions:
        return text
    for abbr, full in expansions.items():
        if fold_surface(abbr) in protected:
            continue  # never expand a registered term / Holy Name
        text = text.replace(abbr, full)
    return text


def normalize_text(
    raw: str,
    *,
    expand_abbreviations: bool = False,
    expansions: Mapping[str, str] | None = None,
    protected: frozenset[str] = frozenset(),
) -> str:
    """Full normalization pipeline for one segment of text.

    strip markup → unescape entities → collapse whitespace → (optional) expand
    rashei-teivot (never expanding `protected` terms). Nikkud is preserved throughout.
    """
    text = strip_markup(raw)
    text = normalize_whitespace(text)
    text = expand_rashei_teivot(
        text, enabled=expand_abbreviations, expansions=expansions, protected=protected
    )
    return text
