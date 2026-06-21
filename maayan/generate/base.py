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


class Message(BaseModel):
    role: Role
    content: str


@runtime_checkable
class GenerationBackend(Protocol):
    """Produces a completion from a system prompt and a message list."""

    def generate(self, system: str, messages: Sequence[Message]) -> str:
        ...
