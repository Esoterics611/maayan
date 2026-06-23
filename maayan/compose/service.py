"""CompositionService: a brief → a proposed, grounded multi-section document.

This module ships the SCAFFOLDING (Prompt 20): brief → proposed OUTLINE. The outline
is STRUCTURAL, not cited — the backend proposes an ordered list of teachable section
headings, each with a retrieval sub-question, in the brief's register/lang. The fill
step (Prompt 21) grounds each section under the same default-deny discipline as `ask`.

Reuses the injected backend + the propose→review shape of `DevelopmentService`; it is
an orchestration layer, NOT a new generation engine. All collaborators are injected.
"""

from __future__ import annotations

import re
import uuid
from typing import Protocol

from maayan.capture.models import Annotation
from maayan.capture.service import CaptureService
from maayan.clock import Clock
from maayan.compose.assemble import assemble_markdown
from maayan.compose.models import Brief, Composition, Section
from maayan.compose.store import CompositionStore
from maayan.config import Settings
from maayan.generate.base import GenerationBackend, Message
from maayan.generate.rag import build_context, extract_cited_refs
from maayan.retrieve.retriever import Retrieving
from maayan.threads.service import ThreadService

DEFAULT_OUTLINE_SYSTEM_PROMPT = (
    "You are helping a Torah scholar plan a structured piece grounded in chassidus / "
    "Kabbalah sources. Propose an OUTLINE only — an ordered list of teachable section "
    "headings, each paired with a retrieval query that will fetch the sources to ground "
    "that section. Rules:\n"
    "1. The outline is STRUCTURAL, not cited — do NOT write the content, only the heading "
    "and the retrieval query per section.\n"
    "2. Order the sections so they build teachably toward the brief's intent.\n"
    "3. Write in the brief's language and register.\n"
    "4. Output EXACTLY one section per line, in the form:  N. <heading> :: <retrieval query>\n"
    "   Nothing else — no preamble, no commentary."
)

DEFAULT_SECTION_SYSTEM_PROMPT = (
    "You are writing ONE section of a Torah study piece (chassidus / p'nimiyus haTorah), "
    "grounded ONLY in the numbered SOURCES the user provides. Rules:\n"
    "1. Use only what is in the SOURCES. Never add outside facts and never invent or guess "
    "mekoros (citations).\n"
    "2. For a shiur outline, write concise, teachable points — not a flowing essay.\n"
    "3. Cite the source for every claim with its bracket tag right after the claim, e.g. "
    "[S1]; combine as [S1][S3] when needed.\n"
    "4. EXPERT FRAMEWORKS (if any) are the author's lens: you may ATTRIBUTE them but NEVER "
    "cite them as a retrieved source and never treat them as evidence.\n"
    "5. If the sources are thin for this section, say so plainly rather than forcing it.\n"
    "6. Write in the section's language, faithful to the sources' meaning."
)

DEFAULT_SECTION_GAP_TEXT = (
    "— The sources here don't reach this. The corpus is silent on this section, so it is "
    "left as an honest gap rather than filled with ungrounded prose. —"
)

DEFAULT_TRANSITION_SYSTEM_PROMPT = (
    "You write a SINGLE short connective sentence that bridges two sections of a Torah "
    "study piece. It is CONNECTIVE GLUE ONLY: introduce NO new claim, cite NO source, and "
    "add NO content beyond linking the prior point to the next. Write in the same language."
)

# Each outline line: optional list marker, a heading, "::", a retrieval query.
_LINE = re.compile(r"^\s*(?:\d+[.)]\s*|[-*]\s*)?(?P<heading>.+?)\s*::\s*(?P<query>.+?)\s*$")


def parse_outline(raw: str) -> list[Section]:
    """Parse the backend's outline into Sections (heading + query, empty text).

    Accepts numbered/bulleted lines of the form ``<heading> :: <query>``. A line with no
    ``::`` separator falls back to using its whole text as both heading and query, so a
    less-compliant model still yields a usable (if blunt) section rather than nothing.
    """
    sections: list[Section] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _LINE.match(stripped)
        if match:
            heading = match.group("heading").strip()
            query = match.group("query").strip()
        else:
            heading = re.sub(r"^\s*(?:\d+[.)]\s*|[-*]\s*)", "", stripped).strip()
            query = heading
        if heading:
            sections.append(Section(heading=heading, query=query))
    return sections


def build_outline_messages(brief: Brief, max_sections: int) -> list[Message]:
    """Compose the outline prompt from the brief (frameworks attributed, never cited)."""
    lines = [
        f"BRIEF — {brief.content_type}",
        f"Title: {brief.title}",
        f"Intent: {brief.intent}",
        f"Language/register: {brief.lang}",
    ]
    if brief.seed_frameworks:
        lines.append(
            "Expert frameworks to honor (attribute, never cite as a source): "
            + "; ".join(brief.seed_frameworks)
        )
    lines.append(
        f"\nPropose at most {max_sections} sections as 'N. <heading> :: <retrieval query>', "
        "one per line. Outline only — no content."
    )
    return [Message(role="user", content="\n".join(lines))]


def build_section_messages(section: Section, brief: Brief, sources_block: str) -> list[Message]:
    """Compose one section's fill prompt: frameworks (non-citable) then citable SOURCES."""
    lines = [f"SECTION HEADING: {section.heading}", f"FOCUS: {section.query}"]
    if brief.seed_frameworks:
        lines.append(
            "EXPERT FRAMEWORKS (attribute, do NOT cite as a retrieved source): "
            + "; ".join(brief.seed_frameworks)
        )
    lines.append(
        f"\n{sources_block}\n\n"
        f"Write this section ({brief.content_type}, language {brief.lang}), grounding every "
        "claim ONLY in the numbered sources and citing each with its [S#] tag. Do not cite "
        "the frameworks. If the sources don't support this section, say so plainly."
    )
    return [Message(role="user", content="\n".join(lines))]


class Composing(Protocol):
    """The methods the UI/CLI depend on (DI seam, mirrors `Developing`)."""

    def propose_outline(self, brief: Brief) -> Composition: ...
    def fill(self, composition_id: str) -> Composition: ...
    def approve(self, composition_id: str) -> Composition: ...
    def reject(self, composition_id: str) -> Composition: ...
    def assemble(self, composition_id: str) -> str: ...
    def promote_connection(
        self, composition_id: str, section_index: int, *, author: str, insight: str
    ) -> Annotation: ...
    def get_composition(self, composition_id: str) -> Composition | None: ...
    def list_compositions(self) -> list[Composition]: ...


class CompositionService:
    """Brief → proposed outline → per-section grounded fill → assemble / review / promote."""

    def __init__(
        self,
        retriever: Retrieving,
        backend: GenerationBackend,
        store: CompositionStore,
        threads: ThreadService,
        clock: Clock,
        settings: Settings,
        capture: CaptureService | None = None,
        *,
        outline_system_prompt: str = DEFAULT_OUTLINE_SYSTEM_PROMPT,
        section_system_prompt: str = DEFAULT_SECTION_SYSTEM_PROMPT,
        transition_system_prompt: str = DEFAULT_TRANSITION_SYSTEM_PROMPT,
        gap_text: str = DEFAULT_SECTION_GAP_TEXT,
    ) -> None:
        self._retriever = retriever
        self._backend = backend
        self._store = store
        self._threads = threads
        self._clock = clock
        self._settings = settings
        self._capture = capture
        self._outline_system_prompt = outline_system_prompt
        self._section_system_prompt = section_system_prompt
        self._transition_system_prompt = transition_system_prompt
        self._gap_text = gap_text

    def propose_outline(self, brief: Brief) -> Composition:
        """Turn a brief into a proposed outline (structural, not cited), and persist it.

        Bounded by `target_sections` and `compose_max_sections` (the tighter wins). If the
        brief lives in a thread, a "composition" turn is appended.
        """
        bound = self._settings.compose_max_sections
        if brief.target_sections is not None:
            bound = max(1, min(brief.target_sections, bound))

        messages = build_outline_messages(brief, bound)
        raw = self._backend.generate(self._outline_system_prompt, messages)
        sections = parse_outline(raw)[:bound]

        composition = Composition(
            id=str(uuid.uuid4()),
            brief_id=brief.id,
            thread_id=brief.thread_id,
            status="proposed",
            sections=sections,
            model=self._settings.generation_model,
            created_at=self._clock.now(),
        )
        self._store.save_brief(brief)
        self._store.save_composition(composition)
        if brief.thread_id:
            self._threads.add_turn(
                brief.thread_id,
                turn_type="composition",
                author=brief.author,
                text=f"{brief.title} — outline ({len(sections)} sections)",
                record_id=composition.id,
            )
        # Quick-draft mode: fill immediately. Otherwise the expert edits/approves first.
        if self._settings.compose_auto_outline:
            return self.fill(composition.id)
        return composition

    def fill(self, composition_id: str) -> Composition:
        """Fill each section with a grounded, cited passage — or an honest gap.

        Default-deny runs PER SECTION, enforced in code: a section whose query retrieves
        nothing above `score_threshold` becomes a gap with NO backend call. Supported
        sections reuse `build_context`/`extract_cited_refs` verbatim and cite ONLY
        retrieved sources; the brief's seed frameworks are attributed, never cited.
        """
        composition = self._require(composition_id)
        brief = self._store.get_brief(composition.brief_id)
        if brief is None:
            raise ValueError(f"Brief {composition.brief_id!r} for composition not found.")

        filled: list[Section] = [
            self._fill_section(section, brief) for section in composition.sections
        ]
        updated = composition.model_copy(update={"sections": filled})
        return self._store.save_composition(updated)

    def _fill_section(self, section: Section, brief: Brief) -> Section:
        retrieval = self._retriever.retrieve(
            section.query,
            k=self._settings.compose_section_top_k,
            book=brief.source_scope.book,
            source=brief.source_scope.source,
        )
        sources = retrieval.results

        # DEFAULT-DENY per section: an unsupported section is a gap, with NO model call.
        if not sources or retrieval.relevance < self._settings.score_threshold:
            return section.model_copy(update={
                "supported": False, "text": self._gap_text, "cited_refs": [], "grounded_in": [],
            })

        messages = build_section_messages(section, brief, build_context(sources))
        text = self._backend.generate(self._section_system_prompt, messages)
        return section.model_copy(update={
            "supported": True,
            "text": text,
            "cited_refs": extract_cited_refs(text, sources),
            "grounded_in": [s.ref for s in sources],
        })

    # -- review ---------------------------------------------------------------
    def approve(self, composition_id: str) -> Composition:
        """Approve a composition. Does NOT bulk-index the prose (that pollutes retrieval).

        The loop-worthy knowledge is the *connections* a composition surfaces — promote
        those one at a time via `promote_connection`, not the wall of prose.
        """
        approved = self._require(composition_id).model_copy(update={"status": "approved"})
        return self._store.save_composition(approved)

    def reject(self, composition_id: str) -> Composition:
        """Reject a composition. Changes nothing in the corpus."""
        rejected = self._require(composition_id).model_copy(update={"status": "rejected"})
        return self._store.save_composition(rejected)

    def promote_connection(
        self, composition_id: str, section_index: int, *, author: str, insight: str
    ) -> Annotation:
        """Promote ONE section's connection back into the corpus via the capture loop.

        A section's `grounded_in` refs (a cross-text bridge) plus the expert's insight
        become a `source="expert"` connection chunk through the EXISTING `CaptureService`
        (Prompt 5) — one connection at a time, never the whole essay re-ingested.
        """
        if self._capture is None:
            raise ValueError("Promotion needs a CaptureService (not wired into this instance).")
        composition = self._require(composition_id)
        if not 0 <= section_index < len(composition.sections):
            raise ValueError(f"Section {section_index} out of range for this composition.")
        section = composition.sections[section_index]
        return self._capture.add_annotation(
            composition_id,
            author=author,
            kind="connection",
            body=insight,
            linked_refs=section.grounded_in,
        )

    # -- export ---------------------------------------------------------------
    def assemble(self, composition_id: str) -> str:
        """Render the composition to a finished markdown document (deterministic)."""
        composition = self._require(composition_id)
        brief = self._store.get_brief(composition.brief_id)
        if brief is None:
            raise ValueError(f"Brief {composition.brief_id!r} for composition not found.")
        transitions: list[str] = []
        if self._settings.compose_transitions:
            transitions = self._build_transitions(composition)
        return assemble_markdown(composition, brief, transitions=transitions)

    def _build_transitions(self, composition: Composition) -> list[str]:
        """Connective glue before each supported section after the first (no new claims)."""
        transitions = [""] * len(composition.sections)
        prev_heading: str | None = None
        for i, section in enumerate(composition.sections):
            if section.supported and prev_heading is not None:
                messages = [Message(
                    role="user",
                    content=(
                        f"Bridge from the section '{prev_heading}' to the section "
                        f"'{section.heading}' in one connective sentence. No new claims, "
                        "no citations."
                    ),
                )]
                transitions[i] = self._backend.generate(self._transition_system_prompt, messages)
            if section.supported:
                prev_heading = section.heading
        return transitions

    def get_composition(self, composition_id: str) -> Composition | None:
        return self._store.get_composition(composition_id)

    def list_compositions(self) -> list[Composition]:
        return self._store.list_compositions()

    def _require(self, composition_id: str) -> Composition:
        composition = self._store.get_composition(composition_id)
        if composition is None:
            raise ValueError(f"Composition {composition_id!r} not found.")
        return composition
