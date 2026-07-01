"""Paced-drip runner: pacing, backoff, retries, counts — all via FakeClock (no waits)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from maayan.clock import FakeClock
from maayan.populate.drip import run_drip


def _sug(supported: bool) -> Any:
    return SimpleNamespace(supported=supported)


async def test_paces_between_items_and_counts_supported() -> None:
    clock = FakeClock()
    stats = await run_drip(
        ["a", "b", "c"],
        lambda x: [_sug(x != "b")],
        clock=clock,
        pace=20,
        max_retries=5,
        backoff=30,
    )
    assert (stats.attempted, stats.drafted, stats.supported, stats.failed) == (3, 3, 2, 0)
    assert clock.slept == [20, 20, 20]  # one pace per item, no backoff


async def test_retries_with_linear_backoff_then_succeeds() -> None:
    clock = FakeClock()
    calls = {"n": 0}

    def draft_one(_: str) -> list[Any]:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("429")
        return [_sug(True)]

    stats = await run_drip(["only"], draft_one, clock=clock, pace=20, max_retries=5, backoff=30)
    assert (stats.supported, stats.failed) == (1, 0)
    assert clock.slept == [30, 60, 20]  # backoff 30, 60, then the pace


async def test_gives_up_after_max_retries_and_records_error() -> None:
    clock = FakeClock()

    def draft_one(_: str) -> list[Any]:
        raise RuntimeError("boom")

    stats = await run_drip(["x"], draft_one, clock=clock, pace=20, max_retries=3, backoff=30)
    assert (stats.failed, stats.drafted) == (1, 0)
    assert stats.errors and "RuntimeError" in stats.errors[0]
    assert clock.slept == [30, 60, 20]  # two backoffs, give up on 3rd, then pace


async def test_progress_hooks_fire() -> None:
    clock = FakeClock()
    results: list[tuple[int, str]] = []
    errors: list[tuple[int, str, int]] = []

    def draft_one(x: str) -> list[Any]:
        if x == "bad":
            raise RuntimeError("e")
        return [_sug(True)]

    await run_drip(
        ["good", "bad"],
        draft_one,
        clock=clock,
        pace=0,
        max_retries=2,
        backoff=1,
        on_result=lambda i, it, _s: results.append((i, it)),
        on_error=lambda i, it, _e, a: errors.append((i, it, a)),
    )
    assert results == [(1, "good")]
    assert (2, "bad", 1) in errors and (2, "bad", 2) in errors
