"""OpenRouterBackend forwards the max_tokens cap to the API call (no network).

The 64k default reservation is what 402s on low balances and what some free
endpoints reject; the backend must pass the configured cap through.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from maayan.generate.base import Message


class _RecordingCompletions:
    def __init__(self, rec: dict[str, Any]) -> None:
        self._rec = rec

    def create(self, **kwargs: Any) -> Any:
        self._rec.update(kwargs)
        msg = SimpleNamespace(content="ok")
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    rec: dict[str, Any] = {"init": {}}

    def _fake_openai(*_args: Any, **init_kwargs: Any) -> Any:
        rec["init"] = init_kwargs
        completions = _RecordingCompletions(rec)
        return SimpleNamespace(chat=SimpleNamespace(completions=completions))

    monkeypatch.setattr("openai.OpenAI", _fake_openai)
    return rec


def test_max_tokens_is_forwarded(recorded: dict[str, Any]) -> None:
    from maayan.generate.openrouter import OpenRouterBackend

    backend = OpenRouterBackend("k", model="m", max_tokens=1234)
    out = backend.generate("sys", [Message(role="user", content="hi")])

    assert out == "ok"
    assert recorded["model"] == "m"
    assert recorded["max_tokens"] == 1234


def test_max_tokens_defaults_to_none(recorded: dict[str, Any]) -> None:
    from maayan.generate.openrouter import OpenRouterBackend

    backend = OpenRouterBackend("k", model="m")
    backend.generate("sys", [Message(role="user", content="hi")])

    assert recorded["max_tokens"] is None


def test_retries_and_timeout_forwarded_to_client(recorded: dict[str, Any]) -> None:
    from maayan.generate.openrouter import OpenRouterBackend

    OpenRouterBackend("k", model="m", timeout=99.0, max_retries=7)

    assert recorded["init"]["max_retries"] == 7
    assert recorded["init"]["timeout"] == 99.0
