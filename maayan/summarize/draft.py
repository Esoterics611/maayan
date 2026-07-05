"""Draft a grounded summary for one section (Prompt 42).

The section's own passages ARE the sources — a summary compresses them, it does not
retrieve. The model is told to summarize strictly from the numbered SOURCES and cite
each claim [S#]; the faithfulness pass (the same one the populators use) flags anything
unsupported. A summary is a PROPOSAL — it indexes nothing until approved.
"""

from __future__ import annotations

from collections.abc import Sequence

from maayan.clock import Clock
from maayan.corpus.models import Chunk
from maayan.generate.base import GenerationBackend, Message
from maayan.generate.rag import (
    VERIFY_SYSTEM_PROMPT,
    build_context,
    build_verify_messages,
    extract_cited_refs,
    parse_unsupported,
)
from maayan.retrieve.models import SearchResult
from maayan.summarize.models import Summary, summary_id

SUMMARY_DRAFT_SYSTEM_PROMPT = (
    "You are a careful study assistant for chassidus and Kabbalah (p'nimiyus haTorah). "
    "Summarize the section given as numbered SOURCES into a short, faithful conceptual "
    "overview. Rules:\n"
    "1. Use ONLY what the sources say; add no outside facts and invent no mekoros.\n"
    "2. Cite each claim with its [S#] tag.\n"
    "3. Keep it to 2-4 sentences, in the language of the sources.\n"
    "4. If the sources are too thin to summarize, reply with exactly: INSUFFICIENT"
)


def _child_sources(children: Sequence[Chunk]) -> list[SearchResult]:
    return [
        SearchResult(
            ref=c.ref, text=c.text, score=0.0, lang=c.lang, source=c.source,
            payload={"ref": c.ref},
        )
        for c in children
    ]


class SummaryDrafter:
    """Draft a corpus-grounded summary for one section (DI seam for the model)."""

    def __init__(
        self,
        backend: GenerationBackend,
        clock: Clock,
        *,
        model: str,
        verify: bool = True,
        system_prompt: str = SUMMARY_DRAFT_SYSTEM_PROMPT,
        verify_prompt: str = VERIFY_SYSTEM_PROMPT,
    ) -> None:
        self._backend = backend
        self._clock = clock
        self._model = model
        self._verify = verify
        self._system_prompt = system_prompt
        self._verify_prompt = verify_prompt

    def draft(
        self, *, book: str, parent_ref: str, parent_label: str, children: Sequence[Chunk]
    ) -> Summary:
        """Summarize `children` (the section's passages); verify; return the proposal."""
        sources = _child_sources(children)

        def _mk(
            *, text: str, cited: list[str], supported: bool, unsupported: list[str]
        ) -> Summary:
            return Summary(
                id=summary_id(parent_ref),
                book=book,
                parent_ref=parent_ref,
                parent_label=parent_label,
                child_refs=[c.ref for c in children],
                text=text,
                cited_refs=cited,
                model=self._model,
                supported=supported,
                unsupported_claims=unsupported,
                status="proposed",
                created_at=self._clock.now(),
            )

        if not sources:
            return _mk(text="", cited=[], supported=False, unsupported=[])

        content = (
            f"{build_context(sources)}\n\n"
            "Write the summary now, citing each claim by its [S#] tag. "
            "If the sources are too thin, reply with exactly: INSUFFICIENT"
        )
        reply = self._backend.generate(self._system_prompt, [Message(role="user", content=content)])
        text = reply.strip()
        if not text or text.upper().startswith("INSUFFICIENT"):
            return _mk(text="", cited=[], supported=False, unsupported=[])

        cited = extract_cited_refs(reply, sources)
        unsupported: list[str] = []
        if self._verify:
            verdict = self._backend.generate(
                self._verify_prompt, build_verify_messages(reply, sources)
            )
            unsupported = parse_unsupported(verdict)
        supported = bool(cited) and not unsupported
        return _mk(text=text, cited=cited, supported=supported, unsupported=unsupported)
