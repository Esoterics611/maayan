"""Tests for the health probes (A6). No Qdrant, no models, no provider calls."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from maayan.config import Settings
from maayan.embed.base import Embedding
from maayan.health.models import ComponentHealth, HealthReport, format_report
from maayan.health.service import (
    EmbedderProbe,
    GenerationProbe,
    HealthService,
    QdrantProbe,
)


class _Index:
    def __init__(self, result: object) -> None:
        self._result = result

    def count(self) -> int:
        if isinstance(self._result, Exception):
            raise self._result
        return int(self._result)  # type: ignore[arg-type]


def _qdrant(result: object) -> ComponentHealth:
    return QdrantProbe(_Index(result), collection="maayan").check()  # type: ignore[arg-type]


def test_qdrant_reports_the_point_count_when_healthy() -> None:
    health = _qdrant(8764)
    assert health.status == "ok" and health.ok
    assert "8764" in health.detail and "maayan" in health.detail
    assert health.latency_ms is not None


def test_an_empty_collection_is_degraded_not_ok() -> None:
    """Retrieval against an empty index succeeds and returns nothing — the worst failure."""
    health = _qdrant(0)
    assert health.status == "degraded" and not health.ok
    assert "maayan index" in health.detail  # tells you what to actually do


def test_an_unreachable_qdrant_is_reported_not_raised() -> None:
    health = _qdrant(ConnectionError("connection refused"))
    assert health.status == "down"
    assert "ConnectionError" in health.detail and "connection refused" in health.detail


class _Embedder:
    def __init__(self, embedding: Embedding | Exception) -> None:
        self._embedding = embedding

    @property
    def dim(self) -> int:
        return 3

    def embed(self, texts: Any) -> list[Embedding]:
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> Embedding:
        if isinstance(self._embedding, Exception):
            raise self._embedding
        return self._embedding


def _embedder_probe(embedder: Any) -> ComponentHealth:
    return EmbedderProbe(embedder, model="bge-m3", probe_text="בדיקה").check()


def test_embedder_probe_reports_dim_and_sparse_terms() -> None:
    health = _embedder_probe(
        _Embedder(Embedding(dense=[0.1, 0.2, 0.3], sparse_indices=[7, 9], sparse_values=[1.0, 2.0]))
    )
    assert health.status == "ok"
    assert "dim 3" in health.detail and "2 sparse terms" in health.detail


def test_a_missing_embedder_is_skipped_not_ok_and_not_down() -> None:
    """A check that was never run must never be reported as a pass."""
    health = _embedder_probe(None)
    assert health.status == "skipped"
    assert health.ok  # skipped does not fail the overall report ...
    assert "not loaded" in health.detail  # ... but it says so plainly


def test_a_broken_embedder_is_down() -> None:
    health = _embedder_probe(_Embedder(RuntimeError("CUDA out of memory")))
    assert health.status == "down" and "CUDA out of memory" in health.detail


def test_an_empty_dense_vector_is_degraded() -> None:
    health = _embedder_probe(_Embedder(Embedding(dense=[], sparse_indices=[], sparse_values=[])))
    assert health.status == "degraded"


def _generation(settings: Settings, handler: Any) -> ComponentHealth:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return GenerationProbe(settings, client=client).check()


OPENROUTER = Settings(generation_backend="openrouter", openrouter_api_key=SecretStr("k"))


def test_generation_probe_never_calls_a_completion_endpoint() -> None:
    """Asking 'are you alive?' must not bill tokens."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"data": []})

    assert _generation(OPENROUTER, handler).status == "ok"
    assert seen and all(url.endswith("/models") for url in seen)
    assert not any("chat" in url or "completion" in url for url in seen)


def test_a_missing_api_key_is_down_before_any_request() -> None:
    """No key means every grounded answer fails at the last step — say so up front."""
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
        raise AssertionError("no request should be made without a key")

    health = _generation(
        Settings(generation_backend="openrouter", openrouter_api_key=SecretStr("")), handler
    )
    assert health.status == "down" and "OPENROUTER_API_KEY" in health.detail


def test_the_api_key_never_appears_in_the_report() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    settings = Settings(
        generation_backend="openrouter", openrouter_api_key=SecretStr("sk-secret-value")
    )
    health = _generation(settings, handler)
    assert health.status == "down"
    assert "sk-secret-value" not in health.detail
    assert "sk-secret-value" not in format_report(HealthReport(components=[health]))


def test_provider_errors_and_timeouts_are_reported_not_raised() -> None:
    def http_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream down")

    assert _generation(OPENROUTER, http_error).status == "down"

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    assert _generation(OPENROUTER, timeout).status == "down"


def test_ollama_is_probed_locally_with_no_auth_header() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"models": []})

    health = _generation(Settings(generation_backend="ollama"), handler)
    assert health.status == "ok" and "ollama" in health.detail
    assert str(captured[0].url).endswith("/api/tags")
    assert "authorization" not in {k.lower() for k in captured[0].headers}


class _Probe:
    def __init__(self, health: ComponentHealth) -> None:
        self._health = health

    def check(self) -> ComponentHealth:
        return self._health


@pytest.mark.parametrize(
    ("statuses", "overall", "ok"),
    [
        (["ok", "ok"], "ok", True),
        (["ok", "skipped"], "ok", True),
        (["ok", "degraded"], "degraded", False),
        (["degraded", "down"], "down", False),
    ],
)
def test_overall_status_takes_the_worst_component(
    statuses: list[str], overall: str, ok: bool
) -> None:
    report = HealthService(
        [_Probe(ComponentHealth(name=s, status=s)) for s in statuses]  # type: ignore[arg-type,list-item]
    ).check()
    assert report.status == overall
    assert report.ok is ok


def test_format_report_shows_every_component_and_the_verdict() -> None:
    report = HealthReport(
        components=[
            ComponentHealth(name="qdrant", status="ok", detail="8764 points", latency_ms=12.0),
            ComponentHealth(name="generation", status="down", detail="no key"),
        ]
    )
    text = format_report(report)
    assert "qdrant" in text and "8764 points" in text
    assert "generation" in text and "no key" in text
    assert "overall: DOWN" in text


# -- the HTTP surface ---------------------------------------------------------
def test_health_route_returns_the_report_when_wired() -> None:
    from fastapi.testclient import TestClient

    from maayan.ui.app import create_app
    from tests import test_ui as ui

    service = HealthService(
        [
            _Probe(ComponentHealth(name="qdrant", status="ok", detail="8764 points")),
            _Probe(ComponentHealth(name="generation", status="down", detail="no key")),
        ]
    )
    app = create_app(  # type: ignore[arg-type]
        ui.FakeRag(ui._answer(True)), ui.FakeCapture(), ui._StubThreads(), ui._StubDevelop(),
        ui._StubTerms(), ui._StubRetract(), ui._StubStats(), ui._StubCompose(),
        health=service,
    )
    client = TestClient(app)
    body = client.get("/api/health").json()
    names = [c["name"] for c in body["components"]]
    assert names == ["qdrant", "generation"]
    assert body["components"][1]["status"] == "down"


def test_health_route_is_inert_rather_than_wrong_when_unwired() -> None:
    """An unconfigured health check must 503, never report a cheerful 'ok'."""
    from tests.test_ui import _client

    client, _rag, _capture = _client()
    response = client.get("/api/health")
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]
