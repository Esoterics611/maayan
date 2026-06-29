"""An independent LLM judge for answer faithfulness (eval only).

The judge grades whether an answer's claims are supported by the sources it cites. It
is deliberately **separate from the runtime `verify` pass** (`generate/rag.py`): an
answer must not grade itself, and the judge should ideally be a *stronger* model than
the one under test (configurable via `eval_judge_model`). The verdict is a `Judgment`.

Everything is injected (the judge takes a `GenerationBackend`), so the answer harness
and its unit tests can swap a real model for a deterministic fake.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from maayan.config import Settings
from maayan.generate.base import GenerationBackend, Message
from maayan.generate.factory import build_generation_backend
from maayan.generate.rag import build_context, parse_unsupported
from maayan.retrieve.models import SearchResult

JUDGE_SYSTEM_PROMPT = (
    "You are an impartial grader checking whether an ANSWER is faithful to the numbered "
    "SOURCES it cites with [S#] tags. A claim is SUPPORTED if the cited source states or "
    "directly implies it; faithful paraphrase and translation are fine. A claim is "
    "UNSUPPORTED if it adds outside facts, overstates the source, or cites a source that "
    "does not back it. List each answer sentence that is unsupported, verbatim, one per "
    "line, and nothing else. If every claim is properly supported, output exactly: OK"
)


class Judgment(BaseModel):
    """A faithfulness verdict on one answer."""

    faithful: bool
    unsupported_claims: list[str]
    note: str | None = None


@runtime_checkable
class AnswerJudge(Protocol):
    """Grades an answer's faithfulness to its sources (DI seam)."""

    def judge(self, question: str, answer_text: str, sources: Sequence[SearchResult]) -> Judgment:
        ...


def build_judge_messages(
    question: str, answer_text: str, sources: Sequence[SearchResult]
) -> list[Message]:
    """Render the sources (same [S#] numbering the answer used), the question, the answer."""
    content = (
        f"{build_context(list(sources))}\n\n"
        f"QUESTION: {question}\n\n"
        f"ANSWER (cites sources by [S#]):\n{answer_text}"
    )
    return [Message(role="user", content=content)]


class LLMJudge:
    """Faithfulness judge backed by a generation model + a grading rubric prompt."""

    def __init__(
        self, backend: GenerationBackend, *, system_prompt: str = JUDGE_SYSTEM_PROMPT
    ) -> None:
        self._backend = backend
        self._system_prompt = system_prompt

    def judge(self, question: str, answer_text: str, sources: Sequence[SearchResult]) -> Judgment:
        reply = self._backend.generate(
            self._system_prompt, build_judge_messages(question, answer_text, sources)
        )
        unsupported = parse_unsupported(reply)  # "OK"/empty → [] ; else one claim per line
        return Judgment(faithful=not unsupported, unsupported_claims=unsupported)


def build_answer_judge(settings: Settings) -> LLMJudge:
    """Build the judge from config, overriding only the model when `eval_judge_model` is set.

    Respects the configured generation backend (openrouter/ollama) and swaps just the
    model id, so the judge can be a stronger/different model than the one under test
    without a second backend configuration.
    """
    if settings.eval_judge_model:
        field = "ollama_model" if settings.generation_backend == "ollama" else "openrouter_model"
        settings = settings.model_copy(update={field: settings.eval_judge_model})
    return LLMJudge(build_generation_backend(settings))
