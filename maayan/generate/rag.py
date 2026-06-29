"""Grounded, cited RAG with default-deny.

The default-deny rule is enforced in *code*, not just the prompt: if retrieval
returns nothing, or nothing above the relevance threshold, the service returns a
refusal **without calling the model**. When sources exist, the model is instructed
to answer only from them and cite every claim; the model never answers from memory.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

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
    "the sources' meaning.\n"
    "5. A 'Conversation so far' block may precede the sources. Use it ONLY to interpret "
    "the current question (e.g. resolve a pronoun or an elliptical follow-up). Never cite "
    "it and never treat it as a source — cite only the numbered SOURCES."
)

DEFAULT_REFUSAL = (
    "I don't have a source for this in the indexed corpus, so I can't answer it. "
    "Try rephrasing, or ingest the relevant text first."
)

# Stage 1 of the reasoning path: read the sources and build a compact "study map" the
# synthesis stage weaves from. This is analysis, NOT the answer — it stays faithful to
# the sources and is what turns "list the quotes" into "see how they fit together".
ANALYZE_SYSTEM_PROMPT = (
    "You are a careful study assistant for chassidus and Kabbalah (p'nimiyus haTorah). "
    "Read the numbered SOURCES and produce a concise STUDY MAP that will guide answering "
    "the question. Rules:\n"
    "1. For each source, one line: its tag then its core claim in your words, e.g. "
    "'[S1] — ...'. Use ONLY what the source says; add no outside facts.\n"
    "2. Then, briefly: where sources AGREE, where one BUILDS ON another, and any "
    "TENSION/disagreement between them. Refer to sources by their [S#] tags.\n"
    "3. Do NOT answer the question yet and do not invent mekoros. Keep it tight."
)

# Stage 3 (optional): check the produced answer's claims against their cited sources.
VERIFY_SYSTEM_PROMPT = (
    "You are a citation checker. You are given numbered SOURCES and an ANSWER that cites "
    "them with [S#] tags. List any sentence in the answer whose claim is NOT supported by "
    "the source(s) it cites (or that cites nothing for a factual claim). Output each such "
    "sentence verbatim, one per line, and nothing else. If every claim is properly "
    "supported, output exactly: OK"
)

_TAG = re.compile(r"\[S(\d+)\]")


class ContextTurn(BaseModel):
    """A prior conversation turn passed to `ask` for interpretation only.

    Decoupled from `threads.ThreadTurn` on purpose: the generator must not depend on
    the thread layer. The thread flow maps `ThreadTurn` → `ContextTurn`. `speaker` is
    a display label (e.g. the turn type or author); `text` is the snapshot. This block
    is NEVER citable — only retrieved sources are.
    """

    speaker: str
    text: str


class Answer(BaseModel):
    """Result of a RAG ask: the text, whether it was grounded, cited refs, sources.

    `reasoning` is the study map from the two-stage (analyze→synthesize) path, or None
    in single-pass mode. `unsupported_claims` holds answer sentences the optional
    verify pass flagged as not supported by their cited sources (empty when verify is
    off or everything checked out).
    """

    question: str
    text: str
    grounded: bool
    cited_refs: list[str]
    sources: list[SearchResult]
    reasoning: str | None = None
    unsupported_claims: list[str] = []


def build_context(sources: list[SearchResult]) -> str:
    """Render retrieved sources as a numbered, citable block."""
    lines = ["SOURCES:"]
    for i, s in enumerate(sources, 1):
        lines.append(f"[S{i}] ({s.ref}) {s.text}")
    return "\n".join(lines)


def build_conversation(turns: Sequence[ContextTurn]) -> str:
    """Render prior turns as an explicitly NON-citable context block."""
    lines = ["CONVERSATION SO FAR (for context only — do NOT cite any of this):"]
    for t in turns:
        lines.append(f"({t.speaker}) {t.text}")
    return "\n".join(lines)


def build_analyze_messages(sources: list[SearchResult], question: str) -> list[Message]:
    """Stage-1 prompt: the sources + the question to orient the study map."""
    content = (
        f"{build_context(sources)}\n\n"
        f"QUESTION (orient the map toward answering this): {question}\n\n"
        "Produce the STUDY MAP now."
    )
    return [Message(role="user", content=content)]


def build_verify_messages(answer_text: str, sources: list[SearchResult]) -> list[Message]:
    """Stage-3 prompt: the sources + the produced answer to check claim support."""
    content = f"{build_context(sources)}\n\nANSWER:\n{answer_text}"
    return [Message(role="user", content=content)]


def parse_unsupported(reply: str) -> list[str]:
    """Parse the verifier reply into flagged sentences ('OK'/empty → none)."""
    stripped = reply.strip()
    if not stripped or stripped.upper() == "OK":
        return []
    return [line.strip() for line in stripped.splitlines() if line.strip()]


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
        reasoning: bool = False,
        verify: bool = False,
        analyze_prompt: str = ANALYZE_SYSTEM_PROMPT,
        verify_prompt: str = VERIFY_SYSTEM_PROMPT,
    ) -> None:
        self._retriever = retriever
        self._backend = backend
        self._score_threshold = score_threshold
        self._top_k = top_k
        self._system_prompt = system_prompt
        self._refusal_text = refusal_text
        self._reasoning = reasoning
        self._verify = verify
        self._analyze_prompt = analyze_prompt
        self._verify_prompt = verify_prompt

    def ask(
        self,
        question: str,
        *,
        k: int | None = None,
        book: str | None = None,
        source: str | None = None,
        context_turns: Sequence[ContextTurn] = (),
    ) -> Answer:
        # Retrieval ALWAYS runs fresh on the current question only — the conversation
        # context never feeds retrieval, so grounding can't drift onto prior turns.
        retrieval = self._retriever.retrieve(
            question, k=k or self._top_k, book=book, source=source
        )
        sources = retrieval.results

        # DEFAULT-DENY: refuse without calling the model when nothing supports an answer.
        # Enforced before any prompt is built, so context can never trigger a model call.
        if not sources or retrieval.relevance < self._score_threshold:
            return Answer(
                question=question,
                text=self._refusal_text,
                grounded=False,
                cited_refs=[],
                sources=sources,
            )

        # Two-stage when reasoning is on: first ANALYZE the sources into a study map,
        # then SYNTHESIZE the answer from sources + map. Single pass otherwise.
        reasoning_text: str | None = None
        if self._reasoning:
            reasoning_text = self._backend.generate(
                self._analyze_prompt, build_analyze_messages(sources, question)
            )
            user_content = self._synthesis_user_content(
                question, sources, reasoning_text, context_turns
            )
        else:
            user_content = self._answer_user_content(question, sources, context_turns)

        text = self._backend.generate(
            self._system_prompt, [Message(role="user", content=user_content)]
        )

        # Optional faithfulness pass: flag answer sentences not supported by their
        # cited sources. Flag-only — we never silently edit the answer.
        unsupported: list[str] = []
        if self._verify:
            verdict = self._backend.generate(
                self._verify_prompt, build_verify_messages(text, sources)
            )
            unsupported = parse_unsupported(verdict)

        return Answer(
            question=question,
            text=text,
            grounded=True,
            cited_refs=extract_cited_refs(text, sources),
            sources=sources,
            reasoning=reasoning_text,
            unsupported_claims=unsupported,
        )

    # -- prompt assembly -----------------------------------------------------
    @staticmethod
    def _answer_user_content(
        question: str,
        sources: list[SearchResult],
        context_turns: Sequence[ContextTurn],
    ) -> str:
        # Conversation context (if any) goes BEFORE the sources and is labelled
        # non-citable; the sources are the only citable block.
        blocks: list[str] = []
        if context_turns:
            blocks.append(build_conversation(context_turns))
        blocks.append(build_context(sources))
        blocks.append(
            f"Question: {question}\n\n"
            "Answer, citing each claim ONLY by its [S#] source tag. "
            "Do not cite the conversation above."
        )
        return "\n\n".join(blocks)

    @staticmethod
    def _synthesis_user_content(
        question: str,
        sources: list[SearchResult],
        study_map: str,
        context_turns: Sequence[ContextTurn],
    ) -> str:
        blocks: list[str] = []
        if context_turns:
            blocks.append(build_conversation(context_turns))
        blocks.append(build_context(sources))
        blocks.append(
            "STUDY MAP (your own analysis of the sources — use it to organize and "
            "connect, but cite ONLY the [S#] sources, never the map):\n" + study_map
        )
        blocks.append(
            f"Question: {question}\n\n"
            "Using the study map, weave the sources into a single coherent answer "
            "(connect them — do not just list them). Cite each claim ONLY by its [S#] "
            "source tag. Do not cite the conversation or the study map."
        )
        return "\n\n".join(blocks)
