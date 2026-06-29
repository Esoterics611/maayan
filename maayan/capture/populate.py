"""Auto-populate cross-text connections — Claude-as-builder, expert-as-gate.

The mirror of :mod:`maayan.lexicon.populate`, for the headline of the corpus: a single
idea spanning Tanya, Torah Ohr and Likutei Torah. The loop:

1. **Mine** candidate connections: run conceptual probe queries through the retriever
   and pair results that come from DIFFERENT books (a cross-text co-retrieval).
2. For each pair, have the model **state the connection grounded ONLY in the two
   sources, citing both [S#] ends** — never from its own knowledge. A draft counts as
   supported only if it actually draws on ≥2 distinct books and the faithfulness pass
   flags nothing.
3. The draft lands in the :class:`ConnectionSuggestionStore` as ``pending``. An expert
   **approves** it, and only then does it become an indexed ``Annotation`` of
   ``kind="connection"`` (via :class:`~maayan.capture.service.CaptureService`) —
   retrievable alongside the very sources it connects. This is roadmap item #3
   (connection capture) realized as an offline builder feeding the human-review gate.

Everything is injected (retriever, backend, clock, capture service), so unit tests run
with no network and no real models. The drafting model is swapped at the edge (the same
``lexicon_draft_model`` knob), so Claude drafts while maayan's answers stay on Qwen.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from maayan.capture.models import Annotation
from maayan.capture.service import CaptureService
from maayan.clock import Clock
from maayan.generate.base import GenerationBackend, Message
from maayan.generate.rag import (
    VERIFY_SYSTEM_PROMPT,
    build_context,
    build_verify_messages,
    extract_cited_refs,
    parse_unsupported,
)
from maayan.retrieve.models import SearchResult
from maayan.retrieve.retriever import Retrieving

Status = Literal["pending", "approved", "rejected"]

# Connections are recorded under this sentinel session id (they don't arise from a user
# Q&A session). `save_annotation` has no session FK, so no session row is required; the
# id travels in the connection chunk's metadata as provenance.
BUILDER_SESSION_ID = "connector-builder"

# Curated layers must not be connected to each other — we connect printed text only.
_NON_PRINTED_SOURCES = frozenset({"term", "expert", "derived"})

CONNECTION_DRAFT_SYSTEM_PROMPT = (
    "You are a careful study assistant for chassidus and Kabbalah (p'nimiyus haTorah). "
    "You are given numbered SOURCES from DIFFERENT works. State the conceptual CONNECTION "
    "between them — how the ideas relate (they agree, one builds on the other, or they "
    "illuminate each other) — grounded ONLY in the sources. Rules:\n"
    "1. Use ONLY what the sources say; add no outside facts and invent no mekoros.\n"
    "2. Cite each end by its [S#] tag; your statement must draw on at least two sources.\n"
    "3. Keep it to 1-3 sentences, in the language of the sources.\n"
    "4. If the sources are NOT actually related, reply with exactly: INSUFFICIENT"
)


def book_of(result: SearchResult) -> str:
    """The work a result belongs to: its payload book, else the ref prefix (before ',')."""
    book = result.payload.get("book")
    if isinstance(book, str) and book:
        return book
    return result.ref.split(",")[0].split(";")[0].strip() or result.ref


class ConnectionEnd(BaseModel):
    """One end of a candidate connection (a retrieved source, with its book)."""

    ref: str
    book: str
    text: str


class ConnectionCandidate(BaseModel):
    """A cross-text co-retrieval: ≥2 sources from different books, before drafting."""

    query: str  # the probe that surfaced them
    ends: list[ConnectionEnd]


class ConnectionSuggestion(BaseModel):
    """A model-drafted, both-ends-grounded connection awaiting expert approval."""

    id: str
    query: str
    refs: list[str] = Field(default_factory=list)  # the ends' refs
    books: list[str] = Field(default_factory=list)
    statement: str = ""
    source_refs: list[str] = Field(default_factory=list)  # ends the draft actually cited
    model: str = ""
    supported: bool = False  # draws on ≥2 distinct books AND passed the faithfulness check
    unsupported_claims: list[str] = Field(default_factory=list)
    status: Status = "pending"
    created_at: datetime


@runtime_checkable
class ConnectionSuggestionStoring(Protocol):
    """The review-queue persistence the populator depends on (the store satisfies it)."""

    def create(self, suggestion: ConnectionSuggestion) -> ConnectionSuggestion:
        ...

    def get(self, suggestion_id: str) -> ConnectionSuggestion | None:
        ...

    def list(self, *, status: str | None = None) -> list[ConnectionSuggestion]:
        ...

    def set_status(self, suggestion_id: str, status: str) -> None:
        ...


# A small seed of conceptual probes whose answers should span ≥2 of the three works.
# Used when the CLI isn't pointed at the cross-text gold set.
CONNECTION_PROBES: list[str] = [
    "ענין הביטול לאלוקות בעבודת ה'",
    "מהי אהבה בתענוגים ומה מקורה בנפש",
    "מהי הנפש הבהמית וכיצד מבררים אותה",
    "ענין הצמצום והעלם האור",
    "אתכפיא ואתהפכא בעבודת הבירורים",
    "ענין מסירות נפש ואהבה מסותרת",
    "יחוד קודשא בריך הוא ושכינתיה",
    "ענין התשובה ועבודת הבינוני",
]


def _ends_from_results(a: SearchResult, b: SearchResult) -> list[ConnectionEnd]:
    return [
        ConnectionEnd(ref=a.ref, book=book_of(a), text=a.text),
        ConnectionEnd(ref=b.ref, book=book_of(b), text=b.text),
    ]


def mine_connection_candidates(
    retriever: Retrieving,
    probes: Sequence[str] = tuple(CONNECTION_PROBES),
    *,
    k: int = 8,
    max_per_probe: int = 2,
    max_total: int = 50,
) -> list[ConnectionCandidate]:
    """Probe the retriever and pair top results that span different books (deduped)."""
    seen: set[frozenset[str]] = set()
    out: list[ConnectionCandidate] = []
    for probe in probes:
        retrieved = retriever.retrieve(probe, k=k).results
        results = [r for r in retrieved if r.source not in _NON_PRINTED_SOURCES]
        pairs = [
            (a, b)
            for i, a in enumerate(results)
            for b in results[i + 1 :]
            if book_of(a) != book_of(b)
        ]
        added = 0
        for a, b in pairs:
            key = frozenset({a.ref, b.ref})
            if key in seen:
                continue
            seen.add(key)
            out.append(ConnectionCandidate(query=probe, ends=_ends_from_results(a, b)))
            added += 1
            if len(out) >= max_total:
                return out
            if added >= max_per_probe:
                break
    return out


def _connection_user_content(sources: list[SearchResult]) -> str:
    return (
        f"{build_context(sources)}\n\n"
        "State the connection between these sources now, citing each end by its [S#] tag. "
        "If they are not actually related, reply with exactly: INSUFFICIENT"
    )


class ConnectionDrafter:
    """Drafts a connection statement grounded in the candidate's two ends (DI seam)."""

    def __init__(
        self,
        backend: GenerationBackend,
        clock: Clock,
        *,
        model: str,
        verify: bool = True,
        system_prompt: str = CONNECTION_DRAFT_SYSTEM_PROMPT,
        verify_prompt: str = VERIFY_SYSTEM_PROMPT,
    ) -> None:
        self._backend = backend
        self._clock = clock
        self._model = model
        self._verify = verify
        self._system_prompt = system_prompt
        self._verify_prompt = verify_prompt

    def draft(self, candidate: ConnectionCandidate) -> ConnectionSuggestion:
        """Draft a cited connection, verify it, and mark it supported only if cross-text.

        Supported requires the statement to actually cite ends from ≥2 distinct books and
        the faithfulness pass to flag nothing — a one-sided "connection" is not one.
        """
        ends = candidate.ends
        sources = [
            SearchResult(
                ref=e.ref, text=e.text, score=0.0, lang="", source="", payload={"ref": e.ref}
            )
            for e in ends
        ]
        ref_to_book = {e.ref: e.book for e in ends}

        def _mk(
            *, statement: str, source_refs: list[str], supported: bool, unsupported: list[str]
        ) -> ConnectionSuggestion:
            return ConnectionSuggestion(
                id=str(uuid.uuid4()),
                query=candidate.query,
                refs=[e.ref for e in ends],
                books=[e.book for e in ends],
                statement=statement,
                source_refs=source_refs,
                model=self._model,
                supported=supported,
                unsupported_claims=unsupported,
                status="pending",
                created_at=self._clock.now(),
            )

        reply = self._backend.generate(
            self._system_prompt, [Message(role="user", content=_connection_user_content(sources))]
        )
        text = reply.strip()
        if not text or text.upper().startswith("INSUFFICIENT"):
            return _mk(statement="", source_refs=[], supported=False, unsupported=[])

        cited = extract_cited_refs(reply, sources)
        unsupported: list[str] = []
        if self._verify:
            verdict = self._backend.generate(
                self._verify_prompt, build_verify_messages(reply, sources)
            )
            unsupported = parse_unsupported(verdict)
        cited_books = {ref_to_book[r] for r in cited if r in ref_to_book}
        supported = len(cited_books) >= 2 and not unsupported
        return _mk(statement=text, source_refs=cited, supported=supported, unsupported=unsupported)


class ConnectionPopulator:
    """Drive the draft → review → approve loop for cross-text connections."""

    def __init__(
        self,
        drafter: ConnectionDrafter,
        store: ConnectionSuggestionStoring,
        capture: CaptureService,
        *,
        session_id: str = BUILDER_SESSION_ID,
    ) -> None:
        self._drafter = drafter
        self._store = store
        self._capture = capture
        self._session_id = session_id

    def suggest(
        self, candidates: Sequence[ConnectionCandidate], *, persist_unsupported: bool = False
    ) -> list[ConnectionSuggestion]:
        """Draft each candidate; queue the supported (cross-text, faithful) ones for review."""
        out: list[ConnectionSuggestion] = []
        for cand in candidates:
            sug = self._drafter.draft(cand)
            out.append(sug)
            if sug.supported or persist_unsupported:
                self._store.create(sug)
        return out

    def list_pending(self) -> list[ConnectionSuggestion]:
        return self._store.list(status="pending")

    def approve(self, suggestion_id: str, *, author: str) -> Annotation:
        """Promote a pending connection to an indexed expert ``connection`` annotation."""
        sug = self._store.get(suggestion_id)
        if sug is None:
            raise ValueError(f"No connection suggestion {suggestion_id!r}")
        if not sug.supported:
            raise ValueError("Refusing to index an unsupported (not cross-text) connection")
        annotation = self._capture.add_annotation(
            self._session_id,
            author=author,
            kind="connection",
            body=sug.statement,
            linked_refs=sug.refs,
            move="cross-text",
        )
        self._store.set_status(suggestion_id, "approved")
        return annotation

    def reject(self, suggestion_id: str) -> None:
        self._store.set_status(suggestion_id, "rejected")
