"""Smoke tests for the bootstrap skeleton (Prompt 0).

These assert the package imports, config loads from env, and the injectable
Clock behaves — without touching the network or any model.
"""

from __future__ import annotations

import asyncio

import maayan
from maayan.clock import FakeClock, SystemClock
from maayan.config import Settings


def test_package_imports() -> None:
    assert maayan.__version__


def test_settings_defaults_and_env(monkeypatch) -> None:
    # Defaults present.
    s = Settings(_env_file=None)
    assert s.collection_name == "maayan"
    assert s.embed_model == "BAAI/bge-m3"
    assert s.top_k > 0
    assert s.generation_backend in {"openrouter", "ollama"}

    # Env overrides; secrets are not exposed by repr.
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-secret")
    monkeypatch.setenv("TOP_K", "5")
    s2 = Settings(_env_file=None)
    assert s2.top_k == 5
    assert s2.openrouter_api_key.get_secret_value() == "sk-secret"
    assert "sk-secret" not in repr(s2)


def test_fake_clock_does_not_sleep() -> None:
    clock = FakeClock()
    start = clock.now()
    asyncio.run(clock.sleep(120.0))
    # Virtual time recorded, wall clock not advanced (test ran instantly).
    assert clock.slept == [120.0]
    assert clock.now() == start  # now() only moves if explicitly set
    assert clock.monotonic() == 120.0


def test_system_clock_is_timezone_aware() -> None:
    assert SystemClock().now().tzinfo is not None
