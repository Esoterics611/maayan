"""FastAPI app for the local chat + capture UI.

Thin layer: route handlers wire HTTP to the existing `RAGService` and
`CaptureService` and contain no business logic. Both services are injected into
`create_app`, so tests pass mocks and `maayan ui` passes the real (heavy) ones.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from maayan.capture.service import CaptureService
from maayan.generate.rag import RAGService
from maayan.ui.models import (
    AnnotateRequest,
    AnnotateResponse,
    AnnotationOut,
    AskRequest,
    AskResponse,
    SessionResponse,
    SourceOut,
)

_STATIC = Path(__file__).parent / "static"


def create_app(rag: RAGService, capture: CaptureService) -> FastAPI:
    app = FastAPI(title="maayan", docs_url="/docs")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_STATIC / "index.html")

    @app.get("/kinds")
    def kinds() -> list[str]:
        return list(capture.allowed_kinds)

    @app.post("/ask")
    def ask(req: AskRequest) -> AskResponse:
        answer = rag.ask(req.question, k=req.k)
        session = capture.start_session(answer)  # so the answer can be annotated
        cited = set(answer.cited_refs)
        return AskResponse(
            session_id=session.id,
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

    @app.post("/annotate")
    def annotate(req: AnnotateRequest) -> AnnotateResponse:
        try:
            ann = capture.add_annotation(
                req.session_id, author=req.author, kind=req.kind, body=req.body,
                linked_refs=req.linked_refs, move=req.move,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return AnnotateResponse(
            annotation_id=ann.id, session_id=ann.session_id, kind=ann.kind,
            author=ann.author, linked_refs=ann.linked_refs,
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
                )
                for a in annotations
            ],
        )

    return app
