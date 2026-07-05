"""Parent-context windows (Prompt 42): the flow around a citation unit.

A retrieved passage is the citation unit, but understanding it often needs the passages
around it in the same section. At generation time we may attach a bounded window of a
hit's neighbors (same `section_path` parent, in the book's order) to feed the model —
but the window is NEVER citable: the citation always stays the exact retrieved passage.
This module only *builds* the window; `RAGService` decides when to use it, and
`build_context` renders it as an explicitly non-citable block.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from maayan.corpus.store import ChunkStore

if TYPE_CHECKING:
    from maayan.config import Settings


class ParentContextProvider(Protocol):
    """The one read `RAGService` needs to build a hit's window (DI seam)."""

    def window(self, ref: str, lang: str, *, max_chars: int) -> str:
        ...


class SectionWindowProvider:
    """Builds a hit's window from its section, expanding outward within a char budget."""

    def __init__(self, chunks: ChunkStore) -> None:
        self._chunks = chunks

    def window(self, ref: str, lang: str, *, max_chars: int) -> str:
        """Neighbors of `ref` in its section (order preserved), excluding the hit itself.

        Expands symmetrically outward from the hit, newest neighbor last, until the
        character budget is spent. Returns "" when off (`max_chars <= 0`), the ref is
        unknown, or it stands alone in its section.
        """
        if max_chars <= 0:
            return ""
        section = self._chunks.get_section(ref, lang=lang or None, include_retracted=False)
        refs = [c.ref for c in section]
        if ref not in refs:
            return ""
        anchor = refs.index(ref)
        chosen: list[int] = []
        budget = max_chars
        lo, hi = anchor - 1, anchor + 1
        # Alternate outward (before, after, before, …) so context stays balanced.
        take_before = True
        while (lo >= 0 or hi < len(section)) and budget > 0:
            idx = -1
            if take_before and lo >= 0:
                idx, lo = lo, lo - 1
            elif hi < len(section):
                idx, hi = hi, hi + 1
            elif lo >= 0:
                idx, lo = lo, lo - 1
            take_before = not take_before
            if idx < 0:
                continue
            text = section[idx].text.strip()
            if not text:
                continue
            budget -= len(text)
            chosen.append(idx)
        if not chosen:
            return ""
        # Emit in the section's natural order, not the outward-expansion order.
        return "\n".join(section[i].text.strip() for i in sorted(chosen))


def build_parent_context(settings: Settings) -> ParentContextProvider | None:
    """A section-window provider when parent-context is enabled, else None (off)."""
    if settings.parent_context_chars <= 0:
        return None
    return SectionWindowProvider(ChunkStore(settings.db_path))
