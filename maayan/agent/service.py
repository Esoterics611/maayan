"""The bounded chavrusa loop (Prompt 39).

The trust core does not move an inch:

1. The seed retrieval + default-deny gate run EXACTLY as today (`gate_refuses`
   — the same function `RAGService.ask` calls). A refusal never reaches the
   model, and no trace is persisted for it (nothing was studied).
2. Each hop, the model picks ONE action as constrained JSON from a closed menu;
   one malformed reply earns one repair retry, then the loop force-concludes
   with what it has. Plain completion + strict parsing — no tool-calling API —
   keeps every backend (OpenRouter/Ollama/fake) eligible.
3. Actions execute through EXISTING services only: the retriever, the chunk
   store, the graph store (approved edges), the lexicon. Search increments obey
   the gate's semantics: results below threshold add nothing.
4. Conclude runs `RAGService.synthesize` — the EXACT analyze→synthesize (+
   verify) path of `ask --reason` — over the working set. Answer format,
   citations, and refusal honesty are unchanged.

Budgets (hops / chunks / model calls) are hard; exceeding any force-concludes,
and the trace says so plainly.
"""

from __future__ import annotations

import json
import re
import uuid

from pydantic import TypeAdapter, ValidationError

from maayan.agent.models import (
    BudgetState,
    ConcludeAction,
    EdgeDigest,
    HitDigest,
    LookupTermAction,
    OpenSectionAction,
    SearchAction,
    StepDigest,
    StudyAction,
    StudyStep,
    StudyTrace,
    WalkGraphAction,
)
from maayan.agent.store import TraceStore
from maayan.capture.convert import detect_lang
from maayan.clock import Clock
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.generate.base import GenerationBackend, Message
from maayan.generate.rag import DEFAULT_REFUSAL, Answer, RAGService, gate_refuses
from maayan.graph.models import RefEndpoint
from maayan.graph.store import GraphStore
from maayan.index.qdrant import chunk_payload
from maayan.lexicon.store import TermStore
from maayan.retrieve.models import SearchResult, Via
from maayan.retrieve.retriever import Retrieving

_ACTION = TypeAdapter[StudyAction](StudyAction)
_JSON_BLOB = re.compile(r"\{.*\}", re.DOTALL)

AGENT_SYSTEM_PROMPT = (
    "You are a chavrusa studying a question over a corpus of chassidus and Kabbalah "
    "(p'nimiyus haTorah). Each turn you take EXACTLY ONE action from this menu, "
    "replying with one JSON object and nothing else:\n"
    '  {"verb": "search", "query": "<retrieval query, any language>"}\n'
    '  {"verb": "open_section", "ref": "<canonical ref to read>"}\n'
    '  {"verb": "walk_graph", "ref": "<a ref from the working set — follow its known '
    "connections>\"}\n"
    '  {"verb": "lookup_term", "term": "<a technical term to check in the lexicon>"}\n'
    '  {"verb": "conclude"}\n'
    "Study like a chavrusa: revise your search when results miss, follow a mareh makom "
    "(open_section / walk_graph), check unfamiliar terms — and conclude as soon as the "
    "working set can support a grounded, cited answer."
)

_REPAIR_MESSAGE = (
    "Your previous reply was not a single valid action JSON. Reply with EXACTLY one "
    "JSON object from the menu, and nothing else."
)


class AgentService:
    """Runs the study loop; every collaborator is injected."""

    def __init__(
        self,
        retriever: Retrieving,
        rag: RAGService,
        backend: GenerationBackend,
        chunks: ChunkStore,
        graph: GraphStore,
        terms: TermStore,
        traces: TraceStore,
        clock: Clock,
        *,
        score_threshold: float,
        max_hops: int,
        max_chunks: int,
        max_calls: int,
        refusal_text: str = DEFAULT_REFUSAL,
    ) -> None:
        self._retriever = retriever
        self._rag = rag
        self._backend = backend
        self._chunks = chunks
        self._graph = graph
        self._terms = terms
        self._traces = traces
        self._clock = clock
        self._threshold = score_threshold
        self._max_hops = max_hops
        self._max_chunks = max_chunks
        self._max_calls = max_calls
        self._refusal_text = refusal_text

    def study(self, question: str, *, k: int | None = None) -> StudyTrace:
        """Seed → gate → up to max_hops actions → conclude. Returns the full trace."""
        budgets = BudgetState(
            hops_max=self._max_hops, chunks_max=self._max_chunks, calls_max=self._max_calls
        )
        seed = self._retriever.retrieve(question, k=k)

        # THE gate, decided on the seed alone — a refusal never reaches the model,
        # and no trace is persisted (the UI must not imply any study happened).
        if gate_refuses(seed.results, seed.relevance, self._threshold):
            refusal = Answer(
                question=question, text=self._refusal_text, grounded=False,
                cited_refs=[], sources=seed.results, relevance=seed.relevance,
            )
            return StudyTrace(
                id=str(uuid.uuid4()), question=question, steps=[], answer=refusal,
                budgets=budgets, created_at=self._clock.now(),
            )

        working: list[SearchResult] = []
        self._merge(working, seed.results, budgets)
        lang = detect_lang(question)
        steps: list[StudyStep] = []
        forced_note: str | None = None

        while budgets.hops_used < self._max_hops:
            if budgets.calls_used >= self._max_calls:
                budgets.exhausted = "calls"
                break
            action, calls_spent, parse_note = self._choose_action(
                question, working, steps, budgets
            )
            budgets.calls_used += calls_spent
            budgets.hops_used += 1
            if action is None:
                # One repair retry already happened — force-conclude, honestly.
                forced_note = parse_note or "malformed action"
                steps.append(StudyStep(
                    action=ConcludeAction(),
                    digest=StepDigest(note=f"forced: {forced_note}"),
                    calls_spent=calls_spent,
                ))
                break
            if isinstance(action, ConcludeAction):
                steps.append(StudyStep(
                    action=action, digest=StepDigest(), calls_spent=calls_spent
                ))
                break
            digest = self._execute(action, working, budgets, lang)
            steps.append(StudyStep(action=action, digest=digest, calls_spent=calls_spent))
        else:
            budgets.exhausted = "hops"

        forced = budgets.exhausted is not None or forced_note is not None

        # Conclude: the EXISTING analyze→synthesize (+ verify) path over the
        # working set — same prompts, citations, and honesty as `ask --reason`.
        answer = self._rag.synthesize(question, working, relevance=seed.relevance)
        budgets.calls_used += self._rag.synthesis_calls

        trace = StudyTrace(
            id=str(uuid.uuid4()), question=question, steps=steps, answer=answer,
            budgets=budgets, forced=forced, created_at=self._clock.now(),
        )
        self._traces.save(trace)
        return trace

    # -- choosing ------------------------------------------------------------------
    def _choose_action(
        self,
        question: str,
        working: list[SearchResult],
        steps: list[StudyStep],
        budgets: BudgetState,
    ) -> tuple[StudyAction | None, int, str | None]:
        """One backend call (+ at most one repair retry) → a validated action."""
        content = self._menu_content(question, working, steps, budgets)
        messages = [Message(role="user", content=content)]
        reply = self._backend.generate(AGENT_SYSTEM_PROMPT, messages)
        action = _parse_action(reply)
        if action is not None:
            return action, 1, None
        if budgets.calls_used + 1 >= self._max_calls:
            return None, 1, "malformed action (no budget left to repair)"
        retry = self._backend.generate(
            AGENT_SYSTEM_PROMPT,
            [*messages, Message(role="assistant", content=reply),
             Message(role="user", content=_REPAIR_MESSAGE)],
        )
        action = _parse_action(retry)
        if action is not None:
            return action, 2, None
        return None, 2, "malformed action twice"

    def _menu_content(
        self,
        question: str,
        working: list[SearchResult],
        steps: list[StudyStep],
        budgets: BudgetState,
    ) -> str:
        lines = [f"QUESTION: {question}", ""]
        lines.append(
            f"BUDGETS: hops {budgets.hops_used}/{budgets.hops_max} · "
            f"chunks {budgets.chunks_used}/{budgets.chunks_max} · "
            f"calls {budgets.calls_used}/{budgets.calls_max}"
        )
        lines.append("")
        lines.append(f"WORKING SET ({len(working)} sources):")
        for i, hit in enumerate(working, 1):
            first = hit.text.strip().splitlines()[0][:90] if hit.text.strip() else ""
            lines.append(f"  [{i}] {hit.ref} — {first}")
        if steps:
            lines.append("")
            lines.append("ACTIONS SO FAR:")
            for step in steps:
                note = f" → {step.digest.note}" if step.digest.note else ""
                added = f" (+{step.digest.added_chunks})" if step.digest.added_chunks else ""
                lines.append(f"  {step.action.verb}{added}{note}")
        lines.append("")
        lines.append("Choose your next action (one JSON object only).")
        return "\n".join(lines)

    # -- executing -------------------------------------------------------------------
    def _execute(
        self,
        action: SearchAction | OpenSectionAction | WalkGraphAction | LookupTermAction,
        working: list[SearchResult],
        budgets: BudgetState,
        lang: str,
    ) -> StepDigest:
        if isinstance(action, SearchAction):
            return self._do_search(action, working, budgets)
        if isinstance(action, OpenSectionAction):
            return self._do_open(action, working, budgets)
        if isinstance(action, WalkGraphAction):
            return self._do_walk(action, working, budgets, lang)
        return self._do_lookup(action, working, budgets)

    def _do_search(
        self, action: SearchAction, working: list[SearchResult], budgets: BudgetState
    ) -> StepDigest:
        result = self._retriever.retrieve(action.query)
        digest = StepDigest(
            hits=[HitDigest(ref=r.ref, score=r.score, source=r.source) for r in result.results]
        )
        # The gate's semantics apply to increments too: below threshold adds nothing.
        if gate_refuses(result.results, result.relevance, self._threshold):
            digest.note = "below threshold — nothing added"
            return digest
        digest.added_chunks = self._merge(working, result.results, budgets)
        if digest.added_chunks == 0 and budgets.chunks_used >= self._max_chunks:
            digest.note = "chunk budget full"
        return digest

    def _do_open(
        self, action: OpenSectionAction, working: list[SearchResult], budgets: BudgetState
    ) -> StepDigest:
        chunk = self._preferred(
            self._chunks.get_by_ref(action.ref, include_retracted=False), "he"
        )
        if chunk is None:
            return StepDigest(note=f"ref not in the corpus: {action.ref}")
        added = self._merge(working, [_chunk_result(chunk)], budgets)
        return StepDigest(
            refs_opened=[chunk.ref],
            added_chunks=added,
            note=None if added else "already in the working set (or budget full)",
        )

    def _do_walk(
        self,
        action: WalkGraphAction,
        working: list[SearchResult],
        budgets: BudgetState,
        lang: str,
    ) -> StepDigest:
        steps = self._graph.neighbors(RefEndpoint(ref=action.ref))  # approved only
        digest = StepDigest()
        gathered: list[SearchResult] = []
        for step in steps:
            far = step.endpoint
            if not isinstance(far, RefEndpoint):
                continue
            relation = step.relation
            digest.edges.append(EdgeDigest(
                rel_type=relation.rel_type, far=far.ref,
                author=relation.author, evidence=relation.evidence,
            ))
            chunk = self._preferred(
                self._chunks.get_by_ref(far.ref, include_retracted=False), lang
            )
            if chunk is not None:
                hit = _chunk_result(chunk)
                hit.via = Via(
                    rel_type=relation.rel_type, evidence=relation.evidence,
                    author=relation.author, seed_ref=action.ref,
                    relation_id=relation.id, note=relation.note,
                )
                gathered.append(hit)
        if not digest.edges:
            digest.note = "no approved edges from this ref"
        digest.added_chunks = self._merge(working, gathered, budgets)
        return digest

    def _do_lookup(
        self, action: LookupTermAction, working: list[SearchResult], budgets: BudgetState
    ) -> StepDigest:
        matches = self._terms.find_by_surface_form(action.term)
        live = [t for t in matches if not t.retracted]
        if not live:
            return StepDigest(note=f"no lexicon entry for {action.term!r}")
        term = live[0]
        digest = StepDigest(term=term.canonical)
        chunk = self._preferred(
            self._chunks.get_by_ref(f"Term · {term.canonical}", include_retracted=False), "he"
        )
        if chunk is not None:
            digest.added_chunks = self._merge(working, [_chunk_result(chunk)], budgets)
        else:
            digest.note = "term found but its chunk is not indexed"
        return digest

    # -- shared -----------------------------------------------------------------------
    def _merge(
        self, working: list[SearchResult], new: list[SearchResult], budgets: BudgetState
    ) -> int:
        """Add unseen results up to the chunk budget; returns how many joined."""
        seen = {hit.ref for hit in working}
        added = 0
        for hit in new:
            if budgets.chunks_used >= self._max_chunks:
                break
            if hit.ref in seen:
                continue
            working.append(hit)
            seen.add(hit.ref)
            budgets.chunks_used += 1
            added += 1
        return added

    @staticmethod
    def _preferred(chunks: list[Chunk], lang: str) -> Chunk | None:
        for chunk in chunks:
            if chunk.lang == lang:
                return chunk
        return chunks[0] if chunks else None


def _chunk_result(chunk: Chunk) -> SearchResult:
    """A deliberately-opened chunk as a working-set entry (score 0: not ranked)."""
    return SearchResult(
        ref=chunk.ref, text=chunk.text, score=0.0, lang=chunk.lang,
        source=chunk.source, payload=chunk_payload(chunk),
    )


def _parse_action(reply: str) -> StudyAction | None:
    """Strictly parse ONE action from a completion; None on anything malformed."""
    blob = _JSON_BLOB.search(reply)
    if blob is None:
        return None
    try:
        data = json.loads(blob.group(0))
    except json.JSONDecodeError:
        return None
    try:
        return _ACTION.validate_python(data)
    except ValidationError:
        return None
