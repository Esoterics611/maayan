"""Auto-populate the lexicon — Claude-as-builder, expert-as-gate.

The point of maayan's capture loop is that nothing enters retrieval untrusted. This
module keeps that contract while letting a strong model do the *drafting*:

1. **Mine** candidate terms from the indexed corpus (gershayim tokens like ע״ב, חב״ד)
   and/or take a curated **seed pack** of Names / sefirot / partzufim / core concepts.
2. For each, **retrieve** the passages that use it and have the model write a
   definition **only from those sources, with [S#] citations** — never from its own
   parametric knowledge. Ungrounded or unsupported drafts are flagged, not indexed.
3. The draft lands in the :class:`SuggestionStore` as ``pending``. An expert
   **approves** it, and only then does it become a real ``Term`` (indexed via
   :class:`~maayan.lexicon.service.TermService`) with the *human approver* as author.

Everything is injected (retriever, generation backend, clock), so unit tests run with
no network and no real models. The drafting model is chosen at the edge (factory):
set ``lexicon_draft_model`` to the OpenRouter Claude slug to draft with Claude while
maayan's own answers stay on free Qwen.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from maayan.clock import Clock
from maayan.corpus.models import Chunk
from maayan.corpus.normalize import fold_surface
from maayan.generate.base import GenerationBackend, Message
from maayan.generate.rag import (
    VERIFY_SYSTEM_PROMPT,
    build_context,
    build_verify_messages,
    extract_cited_refs,
    parse_unsupported,
)
from maayan.lexicon.models import Term, TermType
from maayan.lexicon.service import TermService
from maayan.retrieve.models import SearchResult
from maayan.retrieve.retriever import Retrieving

Origin = Literal["seed", "mined"]
Status = Literal["pending", "approved", "rejected"]

# Hebrew nikkud/te'amim — stripped before mining so vowelized text matches.
_NIKKUD = re.compile(r"[֑-ׇ]")
# A gershayim "term" token: Hebrew letters, the double-gershayim (or ASCII "), then
# more Hebrew letters — ע״ב, ס״ג, מ״ה, ב״ן, חב״ד, רמ״ח. The single geresh ׳ (which
# marks ordinary abbreviations like וכו׳) is deliberately excluded — those are
# rashei-teivot, not terms.
_GERSHAYIM_TOKEN = re.compile(r"[א-ת]+[\"״][א-ת]+")

LEXICON_DRAFT_SYSTEM_PROMPT = (
    "You are a careful lexicographer for chassidus and Kabbalah (p'nimiyus haTorah). "
    "Define the given TERM strictly from the numbered SOURCES the user provides. Rules:\n"
    "1. Use ONLY what the sources say. Never add outside facts, gematrias, or related "
    "terms that are not present in the sources, and never invent mekoros.\n"
    "2. Cite each statement with its [S#] tag.\n"
    "3. Keep it to 1-3 sentences, in the language of the sources.\n"
    "4. If the sources do not actually define or use this term, reply with exactly: "
    "INSUFFICIENT"
)


class TermCandidate(BaseModel):
    """A term mined from the corpus, before any definition is drafted."""

    surface: str  # most common raw surface form (e.g. 'ע"ב')
    folded: str  # tolerant key (gershayim/nikkud-insensitive)
    count: int  # total occurrences across the corpus
    example_refs: list[str] = Field(default_factory=list)


class SeedTerm(BaseModel):
    """A curated term to define from the corpus (surface forms only — no facts)."""

    canonical: str
    surface_forms: list[str] = Field(default_factory=list)
    term_type: TermType = "concept"
    related_terms: list[str] = Field(default_factory=list)
    gematria: int | None = None
    sacred: bool = False


class TermSuggestion(BaseModel):
    """A model-drafted, corpus-grounded term awaiting expert approval."""

    id: str
    canonical: str
    surface_forms: list[str] = Field(default_factory=list)
    term_type: TermType = "concept"
    definition: str = ""
    source_refs: list[str] = Field(default_factory=list)  # corpus refs the draft cited
    related_terms: list[str] = Field(default_factory=list)
    gematria: int | None = None
    sacred: bool = False
    origin: Origin = "mined"
    model: str = ""  # the drafting model id (provenance / audit)
    supported: bool = False  # grounded in sources AND passed the faithfulness check
    unsupported_claims: list[str] = Field(default_factory=list)
    status: Status = "pending"
    created_at: datetime


@runtime_checkable
class SuggestionStoring(Protocol):
    """The review-queue persistence the populator depends on (SuggestionStore satisfies it)."""

    def create(self, suggestion: TermSuggestion) -> TermSuggestion:
        ...

    def get(self, suggestion_id: str) -> TermSuggestion | None:
        ...

    def list(self, *, status: str | None = None) -> list[TermSuggestion]:
        ...

    def set_status(self, suggestion_id: str, status: str) -> None:
        ...


# --- mining ------------------------------------------------------------------

def mine_term_candidates(
    chunks: Iterable[Chunk],
    *,
    min_count: int = 3,
    top_n: int = 50,
    max_examples: int = 3,
) -> list[TermCandidate]:
    """Find gershayim-bearing terms in Hebrew corpus chunks, ranked by frequency.

    Tokens are folded (gershayim/nikkud-insensitive) so ע״ב, ע"ב and עב count as one;
    the most common raw spelling is kept as the candidate's display surface.
    """
    counts: dict[str, int] = {}
    surfaces: dict[str, dict[str, int]] = {}
    refs: dict[str, list[str]] = {}
    for chunk in chunks:
        if chunk.lang != "he":
            continue
        text = _NIKKUD.sub("", chunk.text)
        seen_here: set[str] = set()
        for match in _GERSHAYIM_TOKEN.finditer(text):
            raw = match.group(0)
            folded = fold_surface(raw)
            if not folded:
                continue
            counts[folded] = counts.get(folded, 0) + 1
            surfaces.setdefault(folded, {})
            surfaces[folded][raw] = surfaces[folded].get(raw, 0) + 1
            if folded not in seen_here:
                bucket = refs.setdefault(folded, [])
                if len(bucket) < max_examples:
                    bucket.append(chunk.ref)
                seen_here.add(folded)

    candidates: list[TermCandidate] = []
    for folded, n in counts.items():
        if n < min_count:
            continue
        representative = max(surfaces[folded].items(), key=lambda kv: kv[1])[0]
        candidates.append(
            TermCandidate(
                surface=representative, folded=folded, count=n, example_refs=refs.get(folded, [])
            )
        )
    candidates.sort(key=lambda c: (-c.count, c.folded))
    return candidates[:top_n]


# A small, hand-vetted seed pack so the important entities are covered regardless of
# what mining surfaces. These give NAMES ONLY — the definitions are still drafted from
# the corpus and gated, so no chassidus *fact* is seeded, only what a term is called.
SEED_TERMS: list[SeedTerm] = [
    SeedTerm(
        canonical='ע"ב (Name of 72 / Ab)', surface_forms=['ע"ב', "עב"],
        term_type="expansion", related_terms=['ס"ג', 'מ"ה', 'ב"ן'], gematria=72, sacred=True,
    ),
    SeedTerm(
        canonical='ס"ג (Name of 63 / Sag)', surface_forms=['ס"ג', "סג"],
        term_type="expansion", related_terms=['ע"ב', 'מ"ה', 'ב"ן'], gematria=63, sacred=True,
    ),
    SeedTerm(
        canonical='מ"ה (Name of 45 / Mah)', surface_forms=['מ"ה', "מה"],
        term_type="expansion", related_terms=['ע"ב', 'ס"ג', 'ב"ן'], gematria=45, sacred=True,
    ),
    SeedTerm(
        canonical='ב"ן (Name of 52 / Ban)', surface_forms=['ב"ן', "בן"],
        term_type="expansion", related_terms=['ע"ב', 'ס"ג', 'מ"ה'], gematria=52, sacred=True,
    ),
    SeedTerm(canonical="כתר", surface_forms=["כתר"], term_type="sefirah"),
    SeedTerm(canonical="חכמה", surface_forms=["חכמה"], term_type="sefirah"),
    SeedTerm(canonical="בינה", surface_forms=["בינה"], term_type="sefirah"),
    SeedTerm(canonical="דעת", surface_forms=["דעת"], term_type="sefirah"),
    SeedTerm(canonical="חסד", surface_forms=["חסד"], term_type="sefirah"),
    SeedTerm(canonical="גבורה", surface_forms=["גבורה"], term_type="sefirah"),
    SeedTerm(canonical="תפארת", surface_forms=["תפארת"], term_type="sefirah"),
    SeedTerm(canonical="נצח", surface_forms=["נצח"], term_type="sefirah"),
    SeedTerm(canonical="הוד", surface_forms=["הוד"], term_type="sefirah"),
    SeedTerm(canonical="יסוד", surface_forms=["יסוד"], term_type="sefirah"),
    SeedTerm(canonical="מלכות", surface_forms=["מלכות"], term_type="sefirah"),
    SeedTerm(canonical="אריך אנפין", surface_forms=["אריך אנפין", 'א"א'], term_type="partzuf"),
    SeedTerm(canonical="אבא", surface_forms=["אבא"], term_type="partzuf"),
    SeedTerm(canonical="אמא", surface_forms=["אמא"], term_type="partzuf"),
    SeedTerm(canonical="זעיר אנפין", surface_forms=["זעיר אנפין", 'ז"א'], term_type="partzuf"),
    SeedTerm(canonical="נוקבא", surface_forms=["נוקבא"], term_type="partzuf"),
    SeedTerm(canonical="צמצום", surface_forms=["צמצום"], term_type="concept"),
    SeedTerm(canonical="ביטול", surface_forms=["ביטול"], term_type="concept"),
    SeedTerm(canonical="מסירות נפש", surface_forms=["מסירות נפש"], term_type="concept"),
    SeedTerm(canonical="אהבה בתענוגים", surface_forms=["אהבה בתענוגים"], term_type="concept"),
    SeedTerm(canonical="אתכפיא", surface_forms=["אתכפיא"], term_type="concept"),
    SeedTerm(canonical="אתהפכא", surface_forms=["אתהפכא"], term_type="concept"),
    SeedTerm(canonical="קליפת נוגה", surface_forms=["קליפת נוגה"], term_type="concept"),
]


def _draft_user_content(
    canonical: str, surface_forms: Sequence[str], sources: list[SearchResult]
) -> str:
    forms = ", ".join(surface_forms) if surface_forms else canonical
    return (
        f"{build_context(sources)}\n\n"
        f"TERM: {canonical}\n"
        f"Surface forms: {forms}\n\n"
        "Write the definition now, citing each statement by its [S#] tag. "
        "If the sources do not define or use this term, reply with exactly: INSUFFICIENT"
    )


class LexiconDrafter:
    """Drafts a corpus-grounded definition for one term (DI seam for the model)."""

    def __init__(
        self,
        retriever: Retrieving,
        backend: GenerationBackend,
        clock: Clock,
        *,
        model: str,
        top_k: int = 6,
        score_threshold: float = 0.4,
        verify: bool = True,
        system_prompt: str = LEXICON_DRAFT_SYSTEM_PROMPT,
        verify_prompt: str = VERIFY_SYSTEM_PROMPT,
    ) -> None:
        self._retriever = retriever
        self._backend = backend
        self._clock = clock
        self._model = model
        self._top_k = top_k
        self._score_threshold = score_threshold
        self._verify = verify
        self._system_prompt = system_prompt
        self._verify_prompt = verify_prompt

    def draft(
        self,
        *,
        canonical: str,
        surface_forms: Sequence[str] = (),
        term_type: TermType = "concept",
        origin: Origin = "mined",
        related_terms: Sequence[str] = (),
        gematria: int | None = None,
        sacred: bool = False,
    ) -> TermSuggestion:
        """Retrieve grounding sources, draft a cited definition, verify, return a suggestion.

        A suggestion is marked ``supported`` only if the corpus actually grounds it: the
        draft cites at least one retrieved source and the faithfulness pass flags nothing.
        Ungrounded terms (nothing relevant retrieved, or the model says INSUFFICIENT) come
        back unsupported with an empty definition — they are recorded but not indexable.
        """
        query = surface_forms[0] if surface_forms else canonical

        def _mk(
            *, definition: str, source_refs: list[str], supported: bool, unsupported: list[str]
        ) -> TermSuggestion:
            return TermSuggestion(
                id=str(uuid.uuid4()),
                canonical=canonical,
                surface_forms=list(surface_forms),
                term_type=term_type,
                definition=definition,
                source_refs=source_refs,
                related_terms=list(related_terms),
                gematria=gematria,
                sacred=sacred,
                origin=origin,
                model=self._model,
                supported=supported,
                unsupported_claims=unsupported,
                status="pending",
                created_at=self._clock.now(),
            )

        retrieval = self._retriever.retrieve(query, k=self._top_k)
        sources = retrieval.results
        if not sources or retrieval.relevance < self._score_threshold:
            return _mk(definition="", source_refs=[], supported=False, unsupported=[])

        reply = self._backend.generate(
            self._system_prompt,
            [Message(role="user", content=_draft_user_content(canonical, surface_forms, sources))],
        )
        text = reply.strip()
        if not text or text.upper().startswith("INSUFFICIENT"):
            return _mk(definition="", source_refs=[], supported=False, unsupported=[])

        cited = extract_cited_refs(reply, sources)
        unsupported: list[str] = []
        if self._verify:
            verdict = self._backend.generate(
                self._verify_prompt, build_verify_messages(reply, sources)
            )
            unsupported = parse_unsupported(verdict)
        supported = bool(cited) and not unsupported
        return _mk(definition=text, source_refs=cited, supported=supported, unsupported=unsupported)


class LexiconPopulator:
    """Drive the draft → review → approve loop. Approval is the only path to indexing."""

    def __init__(
        self,
        drafter: LexiconDrafter,
        store: SuggestionStoring,
        term_service: TermService,
    ) -> None:
        self._drafter = drafter
        self._store = store
        self._terms = term_service

    def _already_known(self, surface_forms: Sequence[str], canonical: str) -> bool:
        for form in (canonical, *surface_forms):
            if self._terms.find_by_surface_form(form):
                return True
        return False

    def suggest_from_seed(
        self, seeds: Sequence[SeedTerm] = tuple(SEED_TERMS), *, persist_unsupported: bool = False
    ) -> list[TermSuggestion]:
        """Draft definitions for the seed pack; queue the supported ones for review."""
        out: list[TermSuggestion] = []
        for seed in seeds:
            if self._already_known(seed.surface_forms, seed.canonical):
                continue
            sug = self._drafter.draft(
                canonical=seed.canonical,
                surface_forms=seed.surface_forms,
                term_type=seed.term_type,
                origin="seed",
                related_terms=seed.related_terms,
                gematria=seed.gematria,
                sacred=seed.sacred,
            )
            out.append(sug)
            if sug.supported or persist_unsupported:
                self._store.create(sug)
        return out

    def suggest_from_candidates(
        self, candidates: Sequence[TermCandidate], *, persist_unsupported: bool = False
    ) -> list[TermSuggestion]:
        """Draft definitions for mined candidates; queue the supported ones for review."""
        out: list[TermSuggestion] = []
        for cand in candidates:
            if self._already_known([cand.surface], cand.surface):
                continue
            sug = self._drafter.draft(
                canonical=cand.surface, surface_forms=[cand.surface], origin="mined"
            )
            out.append(sug)
            if sug.supported or persist_unsupported:
                self._store.create(sug)
        return out

    def list_pending(self) -> list[TermSuggestion]:
        return self._store.list(status="pending")

    def approve(self, suggestion_id: str, *, author: str) -> Term:
        """Promote a pending draft to a real, indexed Term (author = the human approver)."""
        sug = self._store.get(suggestion_id)
        if sug is None:
            raise ValueError(f"No suggestion {suggestion_id!r}")
        if not sug.supported:
            raise ValueError("Refusing to index an unsupported (ungrounded) suggestion")
        term = self._terms.add_term(
            canonical=sug.canonical,
            definition=sug.definition,
            author=author,
            surface_forms=sug.surface_forms,
            term_type=sug.term_type,
            related_terms=sug.related_terms,
            source_refs=sug.source_refs,
            gematria=sug.gematria,
            sacred=sug.sacred,
        )
        self._store.set_status(suggestion_id, "approved")
        return term

    def reject(self, suggestion_id: str) -> None:
        self._store.set_status(suggestion_id, "rejected")
