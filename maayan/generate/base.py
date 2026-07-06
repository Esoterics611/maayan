"""Generation backend interface.

A `GenerationBackend` turns a system prompt + messages into text. OpenRouter (cloud)
and, later, Ollama (local) both implement it; the RAG service depends only on this
protocol, so the backend is swapped via config with no other code changes.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

Role = Literal["system", "user", "assistant"]


class GenerationError(RuntimeError):
    """A generation backend failed to produce a completion.

    Raised for upstream/provider errors, timeouts, or an empty response (e.g.
    OpenRouter returning HTTP 200 with ``choices: null`` on a transient upstream
    hiccup). Carries a user-facing message so the UI can surface a retryable
    notice instead of an opaque 500. `retryable` hints that simply asking again
    is likely to succeed (the transient case).
    """

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class Message(BaseModel):
    role: Role
    content: str


@runtime_checkable
class GenerationBackend(Protocol):
    """Produces a completion from a system prompt and a message list."""

    def generate(self, system: str, messages: Sequence[Message]) -> str:
        ...
