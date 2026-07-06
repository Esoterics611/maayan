"""OpenRouterBackend forwards the max_tokens cap to the API call (no network).

The 64k default reservation is what 402s on low balances and what some free
endpoints reject; the backend must pass the configured cap through.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from maayan.generate.base import GenerationError, Message


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


# --- resilience to OpenRouter's "HTTP 200 with choices=null" transient hiccup -----------
#
# OpenRouter can return a 200 whose body has no choices (an upstream provider blip). The
# SDK doesn't treat that as an error, so blindly indexing choices[0] used to crash the whole
# request with a TypeError → opaque 500. The backend now re-issues once, then raises a clean
# GenerationError the UI can surface with a retry.


class _QueuedCompletions:
    """Returns queued responses in order; raises queued exceptions; repeats the last one."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = responses
        self.calls = 0

    def create(self, **_kwargs: Any) -> Any:
        item = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        if isinstance(item, Exception):
            raise item
        return item


def _ok(content: str = "ok") -> Any:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _empty(detail: str | None = None) -> Any:
    ns: Any = SimpleNamespace(choices=None)
    if detail is not None:
        ns.error = {"message": detail}
    return ns


def _backend_with(monkeypatch: pytest.MonkeyPatch, responses: list[Any]) -> Any:
    comp = _QueuedCompletions(responses)

    def _fake_openai(*_args: Any, **_kwargs: Any) -> Any:
        return SimpleNamespace(chat=SimpleNamespace(completions=comp))

    monkeypatch.setattr("openai.OpenAI", _fake_openai)
    from maayan.generate.openrouter import OpenRouterBackend

    return OpenRouterBackend("k", model="m"), comp


def test_empty_choices_retries_once_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    backend, comp = _backend_with(monkeypatch, [_empty(), _ok("recovered")])

    out = backend.generate("sys", [Message(role="user", content="hi")])

    assert out == "recovered"
    assert comp.calls == 2  # re-issued once after the null-choices hiccup


def test_persistent_empty_choices_raises_generation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend, comp = _backend_with(monkeypatch, [_empty("upstream busy")])

    with pytest.raises(GenerationError) as excinfo:
        backend.generate("sys", [Message(role="user", content="hi")])

    assert "upstream busy" in str(excinfo.value)  # provider detail surfaced
    assert excinfo.value.retryable is True
    assert comp.calls == 2  # tried twice, then gave up


def test_sdk_error_wrapped_as_generation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from openai import OpenAIError

    backend, comp = _backend_with(monkeypatch, [OpenAIError("boom")])

    with pytest.raises(GenerationError) as excinfo:
        backend.generate("sys", [Message(role="user", content="hi")])

    assert "boom" in str(excinfo.value)
    assert comp.calls == 1  # SDK errors aren't re-issued (the SDK does its own retries)
