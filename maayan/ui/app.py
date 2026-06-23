"""FastAPI app for the local chat + capture UI.

Thin layer: route handlers wire HTTP to the existing services (`RAGService`,
`CaptureService`, `ThreadService`, `DevelopmentService`) and contain no business
logic. All services are injected into `create_app`, so tests pass mocks and
`maayan ui` passes the real (heavy) ones.

Phase 2 adds the thread-centric loop: list/create threads, ask-in-thread,
seed → develop → approve/reject — each a thin route over a service.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from maayan.capture.convert import detect_lang
from maayan.capture.models import Annotation
from maayan.capture.service import CaptureService
from maayan.compose.models import Brief, Composition, SourceScope
from maayan.compose.service import Composing
from maayan.develop.models import Development
from maayan.develop.service import DevelopmentService
from maayan.generate.rag import Answer, RAGService
from maayan.lexicon.models import TermType
from maayan.lexicon.service import TermService
from maayan.retract.service import Retracting
from maayan.stats.models import Stats
from maayan.stats.service import Statsing
from maayan.threads.flow import ask_in_thread
from maayan.threads.models import Thread, ThreadTurn
from maayan.threads.service import ThreadService
from maayan.ui.models import (
    AnnotateRequest,
    AnnotateResponse,
    AnnotationOut,
    AskInThreadRequest,
    AskRequest,
    AskResponse,
    ComposeRequest,
    CompositionResponse,
    CreateThreadRequest,
    DevelopmentResponse,
    DevelopRequest,
    ExportResponse,
    PromoteRequest,
    RetractRequest,
    RetractResponse,
    SectionOut,
    SeedRequest,
    SeedResponse,
    SessionResponse,
    SourceOut,
    TermRequest,
    TermResponse,
    ThreadDetailResponse,
    ThreadOut,
    TurnOut,
)

_STATIC = Path(__file__).parent / "static"


def _answer_to_response(answer: Answer, session_id: str) -> AskResponse:
    cited = set(answer.cited_refs)
    return AskResponse(
        session_id=session_id,
        question=answer.question,
        answer=answer.text,
        grounded=answer.grounded,
        cited_refs=answer.cited_refs,
        sources=[
            SourceOut(
                ref=s.ref, text=s.text, lang=s.lang, source=s.source,
                score=s.score, cited=s.ref in cited,
            )
            for s in answer.sources
        ],
    )


def _thread_out(thread: Thread) -> ThreadOut:
    return ThreadOut(
        id=thread.id, title=thread.title,
        created_at=thread.created_at.isoformat(), updated_at=thread.updated_at.isoformat(),
    )


def _composition_to_response(composition: Composition) -> CompositionResponse:
    return CompositionResponse(
        id=composition.id,
        brief_id=composition.brief_id,
        status=composition.status,
        model=composition.model,
        sections=[
            SectionOut(
                heading=s.heading, query=s.query, text=s.text, cited_refs=s.cited_refs,
                grounded_in=s.grounded_in, supported=s.supported,
            )
            for s in composition.sections
        ],
        cited_refs=composition.cited_refs,
        grounded_in=composition.grounded_in,
        supported_sections=composition.supported_sections,
        gap_sections=composition.gap_sections,
    )


def _development_to_response(dev: Development) -> DevelopmentResponse:
    return DevelopmentResponse(
        id=dev.id, status=dev.status, grounded=dev.grounded, text=dev.text,
        cited_refs=dev.cited_refs, grounded_in=dev.grounded_in, model=dev.model,
    )


def _turn_out(
    turn: ThreadTurn, *, develop: DevelopmentService, capture: CaptureService
) -> TurnOut:
    """Render a turn, enriching develop turns (status/citations) and seed turns (directive)."""
    out = TurnOut(
        id=turn.id, ordinal=turn.ordinal, turn_type=turn.turn_type,
        author=turn.author, text=turn.text, record_id=turn.record_id,
    )
    if turn.turn_type == "development" and turn.record_id:
        dev = develop.get_development(turn.record_id)
        if dev is not None:
            out.status, out.grounded = dev.status, dev.grounded
            out.cited_refs, out.grounded_in = dev.cited_refs, dev.grounded_in
    elif turn.turn_type == "seed" and turn.record_id:
        contribution = capture.get_annotation(turn.record_id)
        if contribution is not None:
            out.is_seed, out.directive = True, contribution.directive
    return out


def create_app(
    rag: RAGService,
    capture: CaptureService,
    threads: ThreadService,
    develop: DevelopmentService,
    terms: TermService,
    retraction: Retracting,
    stats: Statsing,
    compose: Composing,
    *,
    context_turns: int = 6,
) -> FastAPI:
    app = FastAPI(title="maayan", docs_url="/docs")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_STATIC / "index.html")

    @app.get("/kinds")
    def kinds() -> list[str]:
        return list(capture.allowed_kinds)

    # -- one-shot ask / annotate (kept; the thread flow is below) ------------
    @app.post("/ask")
    def ask(req: AskRequest) -> AskResponse:
        answer = rag.ask(req.question, k=req.k)
        session = capture.start_session(answer)  # so the answer can be annotated
        return _answer_to_response(answer, session.id)

    @app.post("/annotate")
    def annotate(req: AnnotateRequest) -> AnnotateResponse:
        try:
            ann = capture.add_annotation(
                req.session_id, author=req.author, kind=req.kind, body=req.body,
                linked_refs=req.linked_refs, move=req.move,
                directive=req.directive, opens_aspect=req.opens_aspect,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return AnnotateResponse(
            annotation_id=ann.id, session_id=ann.session_id, kind=ann.kind,
            author=ann.author, linked_refs=ann.linked_refs, opens_aspect=ann.opens_aspect,
        )

    @app.get("/session/{session_id}")
    def get_session(session_id: str) -> SessionResponse:
        s = capture.get_session(session_id)
        if s is None:
            raise HTTPException(status_code=404, detail="Session not found")
        annotations = capture.get_annotations(session_id)
        return SessionResponse(
            id=s.id, question=s.question, answer_text=s.answer_text,
            retrieved_refs=s.retrieved_refs,
            annotations=[
                AnnotationOut(
                    id=a.id, kind=a.kind, author=a.author, body=a.body,
                    linked_refs=a.linked_refs, move=a.move,
                    directive=a.directive, opens_aspect=a.opens_aspect,
                )
                for a in annotations
            ],
        )

    # -- topic threads ------------------------------------------------------
    @app.get("/threads")
    def list_threads() -> list[ThreadOut]:
        return [_thread_out(t) for t in threads.list_threads()]

    @app.post("/threads")
    def create_thread(req: CreateThreadRequest) -> ThreadOut:
        return _thread_out(threads.start_thread(req.title))

    @app.get("/threads/{thread_id}")
    def get_thread(thread_id: str) -> ThreadDetailResponse:
        detail = threads.get_thread_with_turns(thread_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Thread not found")
        return ThreadDetailResponse(
            thread=_thread_out(detail.thread),
            turns=[_turn_out(t, develop=develop, capture=capture) for t in detail.turns],
        )

    @app.post("/threads/{thread_id}/ask")
    def ask_in_thread_route(thread_id: str, req: AskInThreadRequest) -> AskResponse:
        if threads.get_thread_with_turns(thread_id) is None:
            raise HTTPException(status_code=404, detail="Thread not found")
        result = ask_in_thread(
            rag, threads, thread_id, req.question, max_context_turns=context_turns
        )
        session = capture.start_session(result.answer)  # keep the answer annotatable
        return _answer_to_response(result.answer, session.id)

    @app.post("/threads/{thread_id}/seed")
    def add_seed(thread_id: str, req: SeedRequest) -> SeedResponse:
        try:
            # The thread IS the conversational context for a thread seed (session_id).
            seed: Annotation = capture.add_annotation(
                thread_id, author=req.author, kind=req.kind, body=req.body,
                linked_refs=req.linked_refs, directive=req.directive, opens_aspect=True,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        threads.add_turn(
            thread_id, turn_type="seed", author=seed.author, text=seed.body,
            record_id=seed.id,
        )
        return SeedResponse(
            contribution_id=seed.id, author=seed.author, directive=seed.directive
        )

    @app.post("/threads/{thread_id}/develop")
    def develop_seed(thread_id: str, req: DevelopRequest) -> DevelopmentResponse:
        seed = capture.get_annotation(req.seed_id)
        if seed is None:
            raise HTTPException(status_code=404, detail="Seed not found")
        return _development_to_response(develop.develop(seed, thread_id=thread_id))

    @app.post("/developments/{development_id}/approve")
    def approve_development(development_id: str) -> DevelopmentResponse:
        try:
            return _development_to_response(develop.approve(development_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/developments/{development_id}/reject")
    def reject_development(development_id: str) -> DevelopmentResponse:
        try:
            return _development_to_response(develop.reject(development_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # -- lexicon (terms / Holy Names) ---------------------------------------
    @app.get("/terms")
    def list_terms() -> list[TermResponse]:
        return [
            TermResponse(id=t.id, canonical=t.canonical, term_type=t.term_type,
                         author=t.author, surface_forms=t.surface_forms)
            for t in terms.list_terms()
        ]

    @app.post("/terms")
    def add_term(req: TermRequest) -> TermResponse:
        try:
            term = terms.add_term(
                canonical=req.canonical, definition=req.definition, author=req.author,
                term_type=cast(TermType, req.term_type), surface_forms=req.surface_forms,
                related_terms=req.related_terms, source_refs=req.source_refs,
                gematria=req.gematria, sacred=req.sacred,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return TermResponse(
            id=term.id, canonical=term.canonical, term_type=term.term_type,
            author=term.author, surface_forms=term.surface_forms,
        )

    # -- retraction (the eraser) --------------------------------------------
    @app.post("/retract")
    def retract(req: RetractRequest) -> RetractResponse:
        try:
            r = retraction.retract(req.target, author=req.author, reason=req.reason)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RetractResponse(
            id=r.id, chunk_id=r.chunk_id, ref=r.ref, source=r.source,
            author=r.author, reason=r.reason,
        )

    @app.get("/retractions")
    def list_retractions() -> list[RetractResponse]:
        return [
            RetractResponse(
                id=r.id, chunk_id=r.chunk_id, ref=r.ref, source=r.source,
                author=r.author, reason=r.reason,
            )
            for r in retraction.list_retractions()
        ]

    # -- knowledge-base health ----------------------------------------------
    @app.get("/stats")
    def get_stats() -> Stats:
        return stats.collect()

    # -- composition (brief → outline → fill → review → export) -------------
    @app.post("/compose")
    def compose_outline(req: ComposeRequest) -> CompositionResponse:
        import uuid as _uuid

        try:
            brief = Brief(
                id=str(_uuid.uuid4()), title=req.title, intent=req.intent, author=req.author,
                content_type=req.content_type, lang=detect_lang(req.intent),
                target_sections=req.target_sections,
                source_scope=SourceScope(book=req.book), seed_frameworks=req.seed_frameworks,
                thread_id=req.thread_id,
            )
        except ValueError as exc:  # blank author / bad content_type
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _composition_to_response(compose.propose_outline(brief))

    @app.post("/compositions/{composition_id}/fill")
    def fill_composition(composition_id: str) -> CompositionResponse:
        try:
            return _composition_to_response(compose.fill(composition_id))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/compositions/{composition_id}/approve")
    def approve_composition(composition_id: str) -> CompositionResponse:
        try:
            return _composition_to_response(compose.approve(composition_id))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/compositions/{composition_id}/reject")
    def reject_composition(composition_id: str) -> CompositionResponse:
        try:
            return _composition_to_response(compose.reject(composition_id))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/compositions/{composition_id}/export")
    def export_composition(composition_id: str) -> ExportResponse:
        try:
            return ExportResponse(markdown=compose.assemble(composition_id))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/compositions/{composition_id}/promote")
    def promote_composition(composition_id: str, req: PromoteRequest) -> AnnotateResponse:
        try:
            ann = compose.promote_connection(
                composition_id, req.section_index, author=req.author, insight=req.insight
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return AnnotateResponse(
            annotation_id=ann.id, session_id=ann.session_id, kind=ann.kind,
            author=ann.author, linked_refs=ann.linked_refs, opens_aspect=ann.opens_aspect,
        )

    return app
