"""Draft typed edge proposals for one unit of a study program (Prompt 40).

The bounded per-unit task: given a unit (a section of the sefer) and the passages
co-retrieved around it, ask the drafting model for typed relations FROM this unit to
those passages — each with the exact grounding refs. Then, exactly as the lexicon and
connector populators do, run the EXISTING faithfulness check on each proposal's claim
against its grounding sources. Nothing is persisted or approved here; the drafter only
proposes. The trust discipline holds two ways:

* the object of a proposal must be one of the co-retrieved sources — the model cannot
  invent a mekor to point at;
* an ungrounded or unfaithful proposal comes back ``supported=False`` and is counted
  but never queued.

Everything is injected (retriever, backend, chunk store, clock), so tests run with no
network and no real models; the drafting model is swapped at the edge via the factory.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import get_args

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from maayan.agent.program_models import TASK_REL_TYPES, ProgramTask, RelationProposal, UnitDraft
from maayan.clock import Clock
from maayan.corpus.store import ChunkStore
from maayan.generate.base import GenerationBackend, Message
from maayan.generate.rag import (
    VERIFY_SYSTEM_PROMPT,
    build_context,
    build_verify_messages,
    parse_unsupported,
)
from maayan.graph.models import RelationType
from maayan.retrieve.models import SearchResult
from maayan.retrieve.retriever import Retrieving

_JSON_BLOB = re.compile(r"\{.*\}", re.DOTALL)
_TAG = re.compile(r"S(\d+)")

_KNOWN_REL_TYPES = frozenset(get_args(RelationType))

# The task framing shown to the drafter — one sentence per task, so the same JSON
# contract carries all three sweeps.
_TASK_INSTRUCTION: dict[ProgramTask, str] = {
    "relations": (
        "For THIS UNIT, propose typed relations to the numbered SOURCES: how the unit "
        "relates to each (it explains it, develops it, parallels it, corresponds to it, "
        "argues with it, quotes it, or connects to it)."
    ),
    "terms": (
        "For THIS UNIT, identify technical terms it uses or defines that a numbered "
        "SOURCE also grounds, as edges: use 'defines' when the unit itself defines the "
        "term, else 'connects'. The note must name the term."
    ),
    "mashal": (
        "For THIS UNIT, identify where it gives a MASHAL (analogy) for an idea stated in "
        "a numbered SOURCE — propose an 'is_mashal_for' edge from the unit to that source."
    ),
}


def _draft_system_prompt(task: ProgramTask) -> str:
    verbs = ", ".join(TASK_REL_TYPES[task])
    return (
        "You are a careful chavrusa studying chassidus and Kabbalah (p'nimiyus haTorah). "
        f"{_TASK_INSTRUCTION[task]}\n"
        "Reply with ONE JSON object and nothing else:\n"
        '  {"proposals": [{"object": "S2", "rel_type": "<one of: '
        f"{verbs}"
        '>", "note": "<the claim, in the language of the sources, citing [S#]>", '
        '"grounds": ["S2"]}]}\n'
        "Rules:\n"
        "1. 'object' and every entry of 'grounds' MUST be a source tag (S1, S2, …) from "
        "the numbered SOURCES — never invent a ref.\n"
        "2. Ground each proposal ONLY in what the sources and the unit actually say; add "
        "no outside facts and invent no mekoros.\n"
        "3. Propose only edges you can defend from the text. If none, reply with "
        '{"proposals": []}.'
    )


class _DraftedProposal(BaseModel):
    object: str = ""
    rel_type: str = ""
    note: str = ""
    grounds: list[str] = Field(default_factory=list)


class _DraftReply(BaseModel):
    proposals: list[_DraftedProposal] = Field(default_factory=list)


_REPLY = TypeAdapter[_DraftReply](_DraftReply)


class ProgramDrafter:
    """Draft + faithfulness-check typed edge proposals for a single unit (DI seam)."""

    def __init__(
        self,
        retriever: Retrieving,
        backend: GenerationBackend,
        chunks: ChunkStore,
        clock: Clock,
        *,
        model: str,
        k: int = 8,
        max_proposals: int = 6,
        verify: bool = True,
        verify_prompt: str = VERIFY_SYSTEM_PROMPT,
    ) -> None:
        self._retriever = retriever
        self._backend = backend
        self._chunks = chunks
        self._clock = clock
        self._model = model
        self._k = k
        self._max_proposals = max_proposals
        self._verify = verify
        self._verify_prompt = verify_prompt

    def draft_unit(self, unit_ref: str, task: ProgramTask) -> UnitDraft:
        """Retrieve context around the unit, draft edges, verify them, return the draft.

        No side effects: the runner persists the supported proposals as *proposed*
        relations. A unit with no gettable text, no co-retrieved context, or an
        unparseable reply yields an empty (but honest) draft.
        """
        section = self._chunks.get_section(unit_ref, lang="he", include_retracted=False)
        unit_refs = {c.ref for c in section} or {unit_ref}
        unit_text = "\n".join(c.text for c in section).strip()
        query = unit_text or unit_ref

        retrieval = self._retriever.retrieve(query, k=self._k)
        # Candidate objects: the co-retrieved corpus context, minus the unit's own
        # passages (an edge to oneself is not a proposal).
        candidates = [r for r in retrieval.results if r.ref not in unit_refs]
        if not candidates:
            return UnitDraft(proposals=[], model_calls=0)

        user = self._user_content(unit_text, candidates)
        reply = self._backend.generate(
            _draft_system_prompt(task), [Message(role="user", content=user)]
        )
        calls = 1
        parsed = _parse_reply(reply)

        by_tag = {f"S{i}": r for i, r in enumerate(candidates, 1)}
        by_ref = {r.ref: r for r in candidates}
        allowed = TASK_REL_TYPES[task]

        proposals: list[RelationProposal] = []
        for drafted in parsed[: self._max_proposals]:
            proposal = self._build_proposal(
                drafted, unit_ref, by_tag, by_ref, allowed
            )
            if proposal is None:
                continue
            calls += self._verify_proposal(proposal, by_ref)
            proposals.append(proposal)
        return UnitDraft(proposals=proposals, model_calls=calls)

    # -- internals ---------------------------------------------------------------
    def _user_content(self, unit_text: str, candidates: list[SearchResult]) -> str:
        return (
            f"THIS UNIT:\n{unit_text}\n\n"
            f"{build_context(candidates)}\n\n"
            "Propose the edges now, as the single JSON object described."
        )

    def _build_proposal(
        self,
        drafted: _DraftedProposal,
        unit_ref: str,
        by_tag: dict[str, SearchResult],
        by_ref: dict[str, SearchResult],
        allowed: tuple[str, ...],
    ) -> RelationProposal | None:
        rel_type = drafted.rel_type.strip()
        if rel_type not in allowed or rel_type not in _KNOWN_REL_TYPES:
            return None
        obj = _resolve(drafted.object, by_tag, by_ref)
        if obj is None or obj == unit_ref:
            return None
        grounds: list[str] = []
        for token in drafted.grounds:
            ref = _resolve(token, by_tag, by_ref)
            if ref is not None and ref not in grounds:
                grounds.append(ref)
        # An edge the drafter cannot ground in any retrieved source is not a proposal.
        if not grounds:
            return None
        return RelationProposal(
            subject_ref=unit_ref,
            object_ref=obj,
            rel_type=rel_type,
            note=drafted.note.strip(),
            grounds=grounds,
        )

    def _verify_proposal(
        self, proposal: RelationProposal, by_ref: dict[str, SearchResult]
    ) -> int:
        """Run the EXISTING faithfulness pass; set supported. Returns model calls spent."""
        if not self._verify:
            proposal.supported = True
            return 0
        sources = [by_ref[r] for r in proposal.grounds if r in by_ref]
        if not sources:
            proposal.supported = False
            return 0
        claim = proposal.note or f"{proposal.subject_ref} {proposal.rel_type} {proposal.object_ref}"
        verdict = self._backend.generate(
            self._verify_prompt, build_verify_messages(claim, sources)
        )
        unsupported = parse_unsupported(verdict)
        proposal.unsupported_claims = unsupported
        proposal.supported = not unsupported
        return 1


def _resolve(
    token: str, by_tag: dict[str, SearchResult], by_ref: dict[str, SearchResult]
) -> str | None:
    """Resolve an [S#] tag (or a literal ref) to a candidate source ref, else None."""
    cleaned = token.strip().strip("[]").strip()
    match = _TAG.fullmatch(cleaned)
    if match is not None:
        hit = by_tag.get(f"S{int(match.group(1))}")
        return hit.ref if hit is not None else None
    return cleaned if cleaned in by_ref else None


def _parse_reply(reply: str) -> Sequence[_DraftedProposal]:
    """Strictly parse the proposals list from a completion; empty on anything malformed."""
    blob = _JSON_BLOB.search(reply)
    if blob is None:
        return []
    try:
        data = json.loads(blob.group(0))
        return _REPLY.validate_python(data).proposals
    except (json.JSONDecodeError, ValidationError):
        return []
