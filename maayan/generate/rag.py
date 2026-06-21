"""Grounded, cited RAG with default-deny.

The default-deny rule is enforced in *code*, not just the prompt: if retrieval
returns nothing, or nothing above the relevance threshold, the service returns a
refusal **without calling the model**. When sources exist, the model is instructed
to answer only from them and cite every claim; the model never answers from memory.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from maayan.generate.base import GenerationBackend, Message
from maayan.retrieve.models import SearchResult
from maayan.retrieve.retriever import Retrieving

DEFAULT_SYSTEM_PROMPT = (
    "You are a careful study assistant for chassidus and Kabbalah (p'nimiyus haTorah). "
    "Answer ONLY from the numbered sources provided by the user. Rules:\n"
    "1. Use only what is in the sources. Never add outside facts, and never invent or "
    "guess mekoros (citations/sources).\n"
    "2. Cite the source for every claim using its bracket tag right after the claim, "
    "e.g. [S1]; combine as [S1][S3] when needed.\n"
    "3. If the sources do not contain enough to answer, say so plainly and do not "
    "speculate.\n"
    "4. Answer in the language of the question (Hebrew or English), staying faithful to "
    "the sources' meaning."
)

DEFAULT_REFUSAL = (
    "I don't have a source for this in the indexed corpus, so I can't answer it. "
    "Try rephrasing, or ingest the relevant text first."
)

_TAG = re.compile(r"\[S(\d+)\]")


class Answer(BaseModel):
    """Result of a RAG ask: the text, whether it was grounded, cited refs, sources."""

    question: str
    text: str
    grounded: bool
    cited_refs: list[str]
    sources: list[SearchResult]


def build_context(sources: list[SearchResult]) -> str:
    """Render retrieved sources as a numbered, citable block."""
    lines = ["SOURCES:"]
    for i, s in enumerate(sources, 1):
        lines.append(f"[S{i}] ({s.ref}) {s.text}")
    return "\n".join(lines)


def extract_cited_refs(text: str, sources: list[SearchResult]) -> list[str]:
    """Resolve [S#] tags (and any literal refs) in the answer to source refs, in order."""
    cited: list[str] = []
    for m in _TAG.finditer(text):
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(sources):
            ref = sources[idx].ref
            if ref not in cited:
                cited.append(ref)
    # Also catch refs the model wrote out literally.
    for s in sources:
        if s.ref and s.ref in text and s.ref not in cited:
            cited.append(s.ref)
    return cited


class RAGService:
    """Retrieve → (default-deny gate) → grounded, cited generation."""

    def __init__(
        self,
        retriever: Retrieving,
        backend: GenerationBackend,
        *,
        score_threshold: float = 0.4,
        top_k: int | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        refusal_text: str = DEFAULT_REFUSAL,
    ) -> None:
        self._retriever = retriever
        self._backend = backend
        self._score_threshold = score_threshold
        self._top_k = top_k
        self._system_prompt = system_prompt
        self._refusal_text = refusal_text

    def ask(
        self,
        question: str,
        *,
        k: int | None = None,
        book: str | None = None,
        source: str | None = None,
    ) -> Answer:
        retrieval = self._retriever.retrieve(
            question, k=k or self._top_k, book=book, source=source
        )
        sources = retrieval.results

        # DEFAULT-DENY: refuse without calling the model when nothing supports an answer.
        if not sources or retrieval.relevance < self._score_threshold:
            return Answer(
                question=question,
                text=self._refusal_text,
                grounded=False,
                cited_refs=[],
                sources=sources,
            )

        context = build_context(sources)
        messages = [
            Message(
                role="user",
                content=(
                    f"{context}\n\nQuestion: {question}\n\n"
                    "Answer, citing each claim by its source tag."
                ),
            )
        ]
        text = self._backend.generate(self._system_prompt, messages)
        return Answer(
            question=question,
            text=text,
            grounded=True,
            cited_refs=extract_cited_refs(text, sources),
            sources=sources,
        )
