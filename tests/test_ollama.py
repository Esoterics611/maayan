"""Tests for the local Ollama backend (Prompt 8) — network mocked with respx.

OpenRouter is the default; Ollama is the offline backup. These verify request
construction + reply parsing and the config-driven factory switch — no real model.
"""

from __future__ import annotations

import json

import httpx
import respx

from maayan.config import Settings
from maayan.generate.base import GenerationBackend, Message
from maayan.generate.factory import build_generation_backend
from maayan.generate.ollama import OllamaBackend

BASE = "http://localhost:11434"


@respx.mock
def test_ollama_builds_chat_request_and_parses_reply() -> None:
    route = respx.post(f"{BASE}/api/chat").mock(
        return_value=httpx.Response(
            200, json={"message": {"role": "assistant", "content": "תשובה מבוססת [S1]"}}
        )
    )
    backend = OllamaBackend(base_url=BASE, model="qwen2.5:7b-instruct")
    out = backend.generate("system rules", [Message(role="user", content="שאלה")])

    assert out == "תשובה מבוססת [S1]"
    sent = json.loads(route.calls[0].request.content)
    assert sent["model"] == "qwen2.5:7b-instruct"
    assert sent["stream"] is False  # non-streaming, single response
    assert sent["options"]["temperature"] == 0.2
    # System prompt first, then the messages — same shape as OpenRouter.
    assert sent["messages"][0] == {"role": "system", "content": "system rules"}
    assert sent["messages"][1] == {"role": "user", "content": "שאלה"}


@respx.mock
def test_ollama_missing_content_is_empty_string() -> None:
    respx.post(f"{BASE}/api/chat").mock(return_value=httpx.Response(200, json={}))
    backend = OllamaBackend(base_url=BASE)
    assert backend.generate("s", [Message(role="user", content="q")]) == ""


def test_factory_selects_ollama_from_config() -> None:
    backend = build_generation_backend(
        Settings(generation_backend="ollama", ollama_model="qwen2.5:7b-instruct")
    )
    assert isinstance(backend, OllamaBackend)
    assert isinstance(backend, GenerationBackend)  # satisfies the protocol


def test_generation_model_reports_ollama_model_when_selected() -> None:
    settings = Settings(generation_backend="ollama", ollama_model="qwen2.5:7b-instruct")
    assert settings.generation_model == "qwen2.5:7b-instruct"
