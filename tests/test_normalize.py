"""Unit tests for the Hebrew/text normalizer (pure functions, no I/O)."""

from __future__ import annotations

from maayan.corpus.normalize import (
    expand_rashei_teivot,
    normalize_text,
    normalize_whitespace,
    strip_markup,
)


def test_strip_markup_keeps_inner_text_and_nikkud() -> None:
    raw = "<b>תַּנְיָא</b> [בְּסוֹף פֶּרֶק]"
    out = strip_markup(raw)
    assert out == "תַּנְיָא [בְּסוֹף פֶּרֶק]"
    # Nikkud (combining marks) preserved.
    assert "ַ" in out  # patach


def test_strip_markup_drops_footnotes_with_content() -> None:
    raw = 'a word<sup class="footnote-marker">1</sup><i class="footnote">a note</i> next'
    assert strip_markup(raw) == "a word next"


def test_strip_markup_drops_empty_vilna_page_markers() -> None:
    raw = '<i data-overlay="Vilna Pages" data-value="[מ: כד כסלו]"></i> טֶקְסְט'
    assert strip_markup(raw).strip() == "טֶקְסְט"


def test_strip_markup_unescapes_entities() -> None:
    assert strip_markup("&quot;hi&quot; &amp; there") == '"hi" & there'


def test_normalize_whitespace_collapses_runs() -> None:
    assert normalize_whitespace("a\n\n  b\t c ") == "a b c"
    # Non-breaking space is collapsed too.
    assert normalize_whitespace("a  b") == "a b"


def test_normalize_text_pipeline() -> None:
    raw = '  <b>שָׁלוֹם</b>\n\n<sup class="footnote-marker">*</sup><i class="footnote">x</i>  עוֹלָם  '
    assert normalize_text(raw) == "שָׁלוֹם עוֹלָם"


def test_rashei_teivot_hook_is_noop_by_default() -> None:
    assert expand_rashei_teivot("וכו׳", enabled=False) == "וכו׳"
    # Even enabled it is currently a documented no-op (table not implemented yet).
    assert expand_rashei_teivot("וכו׳", enabled=True) == "וכו׳"
