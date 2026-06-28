"""FastAPI app for the local chat + capture UI.

Thin layer: route handlers wire HTTP to the existing services (`RAGService`,
`CaptureService`, `ThreadService`, `DevelopmentService`) and contain no business
logic. All services are injected into `create_app`, so tests pass mocks and
`maayan ui` passes the real (heavy) ones.

Phase 2 adds the thread-centric loop: list/create threads, ask-in-thread,
seed → develop → approve/reject — each a thin route over a service.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from maayan.audio.models import AudioAsset
from maayan.capture.convert import detect_lang
from maayan.capture.models import Annotation
from maayan.capture.service import CaptureService
from maayan.compose.models import Brief, Composition, SourceScope
from maayan.compose.service import Composing
from maayan.corpus.store import ChunkStore
from maayan.develop.models import Development
from maayan.develop.service import DevelopmentService
from maayan.generate.rag import Answer, RAGService
from maayan.inbox.models import InboxItem
from maayan.inbox.service import InboxService
from maayan.lexicon.models import TermType
from maayan.lexicon.service import TermService
from maayan.ocr.base import OCRer
from maayan.retract.service import Retracting
from maayan.retrieve.models import SearchResult
from maayan.stats.models import Stats
from maayan.stats.service import Statsing
from maayan.threads.flow import ask_in_thread
from maayan.threads.models import Thread, ThreadTurn
from maayan.threads.service import ThreadService
from maayan.transcribe.models import Transcript, TranscriptionJob
from maayan.transcribe.service import TranscriptionService
from maayan.ui.models import (
    AnnotateRequest,
    AnnotateResponse,
    AnnotationOut,
    ApproveTranscriptRequest,
    ApproveTranscriptResponse,
    AskInThreadRequest,
    AskRequest,
    AskResponse,
    CaptureThoughtRequest,
    ComposeRequest,
    CompositionResponse,
    CreateThreadRequest,
    CreateUserRequest,
    DevelopmentResponse,
    DevelopRequest,
    ExportResponse,
    InboxItemOut,
    LibraryEntry,
    LibraryResponse,
    LoginRequest,
    MeResponse,
    MoveInboxRequest,
    OcrResponse,
    PromoteRequest,
    RetractRequest,
    RetractResponse,
    SectionEntry,
    SectionOut,
    SectionsResponse,
    SeedRequest,
    SeedResponse,
    SessionResponse,
    SetActiveRequest,
    SetPasswordRequest,
    SourceContextChunk,
    SourceContextResponse,
    SourceOut,
    TermRequest,
    TermResponse,
    ThreadDetailResponse,
    ThreadOut,
    TurnOut,
    UpdateSegmentRequest,
)
from maayan.users.models import User, UserOut
from maayan.users.service import UserService

_STATIC = Path(__file__).parent / "static"


def _source_out(s: SearchResult, *, cited: bool) -> SourceOut:
    meta = s.payload.get("metadata") or {} if isinstance(s.payload, dict) else {}
    is_shiur = s.source == "shiur"
    return SourceOut(
        ref=s.ref, text=s.text, lang=s.lang, source=s.source, score=s.score, cited=cited,
        audio_id=meta.get("audio_id") if is_shiur else None,
        start_s=meta.get("start_s") if is_shiur else None,
    )


def _answer_to_response(answer: Answer, session_id: str) -> AskResponse:
    cited = set(answer.cited_refs)
    return AskResponse(
        session_id=session_id,
        question=answer.question,
        answer=answer.text,
        grounded=answer.grounded,
        cited_refs=answer.cited_refs,
        sources=[_source_out(s, cited=s.ref in cited) for s in answer.sources],
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
    users: UserService | None = None,
    transcription: TranscriptionService | None = None,
    chunks: ChunkStore | None = None,
    ocr: OCRer | None = None,
    inbox: InboxService | None = None,
    ocr_lang: str = "heb",
    context_turns: int = 6,
    auth_enabled: bool = False,
    session_cookie_name: str = "maayan_session",
    cookie_secure: bool = False,
    cookie_max_age: int = 604_800,
) -> FastAPI:
    app = FastAPI(title="maayan", docs_url="/docs")

    if auth_enabled and users is None:
        raise ValueError("auth_enabled requires a UserService to be injected")

    def _user_service() -> UserService:
        if users is None:  # auth wiring absent (auth disabled) — these routes are inert
            raise HTTPException(status_code=503, detail="auth not configured")
        return users

    def _transcription() -> TranscriptionService:
        if transcription is None:  # transcription wiring absent — routes are inert
            raise HTTPException(status_code=503, detail="transcription not configured")
        return transcription

    def _chunks_store() -> ChunkStore:
        if chunks is None:  # reader/library wiring absent — routes are inert
            raise HTTPException(status_code=503, detail="library not configured")
        return chunks

    def _ocr() -> OCRer:
        if ocr is None:  # OCR disabled (ocr_backend="none") — route is inert
            raise HTTPException(status_code=503, detail="ocr not configured")
        return ocr

    def _inbox() -> InboxService:
        if inbox is None:  # inbox wiring absent — routes are inert
            raise HTTPException(status_code=503, detail="inbox not configured")
        return inbox

    def _require_admin(request: Request) -> User:
        user: User | None = getattr(request.state, "user", None)
        if user is None or user.role != "admin":
            raise HTTPException(status_code=403, detail="admin only")
        return user

    # Auth wall: when enabled, every request outside the allowlist needs a valid session.
    # When disabled, this is a no-op (attaches user=None) so local dev/tests are unchanged.
    @app.middleware("http")
    async def _auth_guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.user = None
        if not auth_enabled or users is None:
            return await call_next(request)
        path = request.url.path
        # PWA shell assets carry no user data and must load on the login page (and
        # let the service worker update without a session), so they bypass the wall.
        if path in {
            "/login", "/api/login", "/healthz",
            "/manifest.webmanifest", "/sw.js", "/icon-192.png", "/icon-512.png",
        }:
            return await call_next(request)
        user = users.current_user(request.cookies.get(session_cookie_name))
        if user is None:
            if path.startswith("/api/"):
                return JSONResponse({"detail": "authentication required"}, status_code=401)
            return RedirectResponse(url="/login", status_code=303)
        request.state.user = user
        return await call_next(request)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_STATIC / "index.html")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    # -- PWA shell (installable, offline-tolerant reads) ---------------------
    @app.get("/manifest.webmanifest")
    def manifest() -> FileResponse:
        return FileResponse(
            _STATIC / "manifest.webmanifest", media_type="application/manifest+json"
        )

    @app.get("/sw.js")
    def service_worker() -> FileResponse:
        # Served from the app root so its scope covers the whole site.
        return FileResponse(
            _STATIC / "sw.js",
            media_type="text/javascript",
            headers={"Service-Worker-Allowed": "/"},
        )

    @app.get("/icon-192.png")
    def icon_192() -> FileResponse:
        return FileResponse(_STATIC / "icon-192.png", media_type="image/png")

    @app.get("/icon-512.png")
    def icon_512() -> FileResponse:
        return FileResponse(_STATIC / "icon-512.png", media_type="image/png")

    # -- auth / users -------------------------------------------------------
    @app.get("/login")
    def login_page() -> FileResponse:
        return FileResponse(_STATIC / "login.html")

    @app.post("/api/login")
    def api_login(req: LoginRequest, response: Response) -> MeResponse:
        svc = _user_service()
        session = svc.login(req.username, req.password)
        if session is None:
            raise HTTPException(status_code=401, detail="invalid username or password")
        response.set_cookie(
            key=session_cookie_name, value=session.token, httponly=True,
            secure=cookie_secure, samesite="lax", max_age=cookie_max_age, path="/",
        )
        user = svc.current_user(session.token)
        return MeResponse(auth_enabled=auth_enabled, user=user.to_out() if user else None)

    @app.post("/api/logout")
    def api_logout(request: Request, response: Response) -> dict[str, str]:
        _user_service().logout(request.cookies.get(session_cookie_name))
        response.delete_cookie(session_cookie_name, path="/")
        return {"status": "ok"}

    @app.get("/api/me")
    def api_me(request: Request) -> MeResponse:
        user: User | None = getattr(request.state, "user", None)
        return MeResponse(auth_enabled=auth_enabled, user=user.to_out() if user else None)

    @app.get("/api/users")
    def api_list_users(request: Request) -> list[UserOut]:
        _require_admin(request)
        return _user_service().list_users()

    @app.post("/api/users")
    def api_create_user(req: CreateUserRequest, request: Request) -> UserOut:
        admin = _require_admin(request)
        try:
            return _user_service().create_user(
                username=req.username, password=req.password,
                display_name=req.display_name, role=req.role, created_by=admin.username,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/users/{user_id}/active")
    def api_set_active(user_id: str, req: SetActiveRequest, request: Request) -> UserOut:
        _require_admin(request)
        try:
            return _user_service().set_active(user_id, req.active)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/users/{user_id}/password")
    def api_set_password(
        user_id: str, req: SetPasswordRequest, request: Request
    ) -> dict[str, str]:
        _require_admin(request)
        try:
            _user_service().change_password(user_id, req.password)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok"}

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

    # -- shiur transcription (audio → async job → transcript) ---------------
    @app.post("/api/audio")
    async def upload_audio(request: Request, file: UploadFile = File(...)) -> AudioAsset:
        svc = _transcription()
        user: User | None = getattr(request.state, "user", None)
        owner = user.username if user else "local"  # uploads owned by the logged-in user
        suffix = Path(file.filename or "").suffix or ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name
        try:
            return svc.store_audio(tmp_path, owner=owner, original_filename=file.filename)
        finally:
            os.unlink(tmp_path)

    @app.post("/api/audio/{audio_id}/transcribe")
    def start_transcription(
        audio_id: str, background_tasks: BackgroundTasks
    ) -> TranscriptionJob:
        svc = _transcription()
        if svc.get_audio(audio_id) is None:
            raise HTTPException(status_code=404, detail="audio not found")
        job = svc.enqueue(audio_id)
        # Off the request thread; the UI polls /api/jobs/{id}. No blocking wait here.
        background_tasks.add_task(svc.run_job, job.id)
        return job

    @app.get("/api/audio/{audio_id}/file")
    def get_audio_file(audio_id: str) -> FileResponse:
        asset = _transcription().get_audio(audio_id)
        if asset is None or not Path(asset.path).exists():
            raise HTTPException(status_code=404, detail="audio not found")
        return FileResponse(asset.path)  # lets "▶ play from here" seek the recording

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> TranscriptionJob:
        job = _transcription().get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job

    # -- transcript review (the human gate; lexicon-assisted) ---------------
    @app.get("/api/transcripts/{transcript_id}")
    def get_transcript(transcript_id: str) -> Transcript:
        svc = _transcription()
        transcript = svc.get_transcript(transcript_id)
        if transcript is None:
            raise HTTPException(status_code=404, detail="transcript not found")
        return svc.suggest_corrections(transcript)  # enrich with lexicon suggestions

    @app.patch("/api/transcripts/{transcript_id}/segments/{idx}")
    def edit_segment(
        transcript_id: str, idx: int, req: UpdateSegmentRequest
    ) -> Transcript:
        svc = _transcription()
        try:
            updated = svc.update_segment(
                transcript_id, idx, edited_text=req.edited_text, speaker=req.speaker
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return svc.suggest_corrections(updated)  # revalidate after the edit

    @app.post("/api/transcripts/{transcript_id}/review")
    def review_transcript(transcript_id: str) -> Transcript:
        svc = _transcription()
        try:
            reviewed = svc.mark_reviewed(transcript_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return svc.suggest_corrections(reviewed)

    @app.post("/api/transcripts/{transcript_id}/approve")
    def approve_transcript(
        transcript_id: str, req: ApproveTranscriptRequest, request: Request
    ) -> ApproveTranscriptResponse:
        svc = _transcription()
        user: User | None = getattr(request.state, "user", None)
        author = user.display_name if user else req.author  # reviewer = provenance
        try:
            chunks = svc.approve(transcript_id, author=author)
        except ValueError as exc:
            code = 404 if "not found" in str(exc) else 400
            raise HTTPException(status_code=code, detail=str(exc)) from exc
        return ApproveTranscriptResponse(
            transcript_id=transcript_id, status="approved",
            chunk_count=len(chunks), refs=[c.ref for c in chunks],
        )

    @app.post("/api/transcripts/{transcript_id}/reject")
    def reject_transcript(transcript_id: str) -> Transcript:
        svc = _transcription()
        try:
            rejected = svc.reject(transcript_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return svc.suggest_corrections(rejected)

    # -- reading / library (source-in-context + sefer browser) --------------
    @app.get("/api/source")
    def source_in_context(ref: str, lang: str | None = None) -> SourceContextResponse:
        section = _chunks_store().get_section(ref, lang=lang)
        if not section:
            raise HTTPException(status_code=404, detail="ref not found")
        anchor = section[0]
        label = " · ".join(anchor.section_path[:-1]) or anchor.book
        return SourceContextResponse(
            ref=ref, label=label, book=anchor.book,
            chunks=[
                SourceContextChunk(
                    ref=c.ref, lang=c.lang, text=c.text, source=c.source, cited=c.ref == ref
                )
                for c in section
            ],
        )

    @app.get("/api/library")
    def library() -> LibraryResponse:
        return LibraryResponse(
            entries=[
                LibraryEntry(book=b, source=s, count=n)
                for (b, s, n) in _chunks_store().library_index()
            ]
        )

    @app.get("/api/library/sections")
    def library_sections(book: str) -> SectionsResponse:
        return SectionsResponse(
            book=book,
            sections=[
                SectionEntry(label=label, ref=ref, lang=lang)
                for (label, ref, lang) in _chunks_store().list_sections(book)
            ],
        )

    # -- OCR capture (photograph a page → text → review field; never auto-ingested) --
    @app.post("/api/ocr")
    async def ocr_image(
        request: Request, lang: str | None = None, file: UploadFile = File(...)
    ) -> OcrResponse:
        ocrer = _ocr()
        language = lang or ocr_lang
        suffix = Path(file.filename or "").suffix or ".png"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name
        try:
            text = ocrer.ocr(Path(tmp_path), language)
        finally:
            os.unlink(tmp_path)
        # Text is returned for the human to review + drop into a capture field — the
        # same gate as every contribution. Nothing is embedded or indexed here.
        return OcrResponse(text=text, lang=language)

    # -- quick-capture inbox (park a thought → triage into a thread later) ---------
    def _inbox_out(item: InboxItem) -> InboxItemOut:
        return InboxItemOut(
            id=item.id, author=item.author, text=item.text,
            created_at=item.created_at.isoformat(), status=item.status,
            thread_id=item.thread_id, record_id=item.record_id,
        )

    @app.post("/api/inbox")
    def capture_thought(req: CaptureThoughtRequest, request: Request) -> InboxItemOut:
        user: User | None = getattr(request.state, "user", None)
        author = user.display_name if user else req.author  # logged-in identity = provenance
        try:
            return _inbox_out(_inbox().capture(text=req.text, author=author))
        except ValueError as exc:  # blank author/text
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/inbox")
    def list_inbox() -> list[InboxItemOut]:
        return [_inbox_out(i) for i in _inbox().list_open()]

    @app.post("/api/inbox/{item_id}/move")
    def move_inbox_item(
        item_id: str, req: MoveInboxRequest
    ) -> InboxItemOut:
        svc = _inbox()
        item = svc.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="inbox item not found")
        if threads.get_thread_with_turns(req.thread_id) is None:
            raise HTTPException(status_code=404, detail="Thread not found")
        # Reuse the EXISTING seed flow: the parked thought becomes a develop-able seed
        # on the thread, attributed to its original author (provenance is sticky).
        try:
            seed: Annotation = capture.add_annotation(
                req.thread_id, author=item.author, kind=req.kind, body=item.text,
                directive=req.directive, opens_aspect=True,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        threads.add_turn(
            req.thread_id, turn_type="seed", author=seed.author, text=seed.body,
            record_id=seed.id,
        )
        return _inbox_out(svc.mark_moved(item_id, thread_id=req.thread_id, record_id=seed.id))

    return app
