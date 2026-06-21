"""Injectable clock abstraction.

House rule: no `time.sleep` in business logic. Anything that needs the current
time or needs to wait takes a `Clock` by dependency injection. Tests inject a
`FakeClock` so they never actually sleep.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Time source + async waiting, injected everywhere instead of `time`/`asyncio.sleep`."""

    def now(self) -> datetime:
        """Current timezone-aware UTC time."""
        ...

    def monotonic(self) -> float:
        """Monotonic seconds, for measuring elapsed intervals (e.g. rate limiting)."""
        ...

    async def sleep(self, seconds: float) -> None:
        """Asynchronously wait for `seconds`."""
        ...


class SystemClock:
    """Real clock backed by the system + asyncio event loop."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()

    async def sleep(self, seconds: float) -> None:
        if seconds > 0:
            await asyncio.sleep(seconds)


class FakeClock:
    """Deterministic clock for tests. Advances only when `sleep` is called; never blocks."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 1, 1, tzinfo=UTC)
        self._mono = 0.0
        self.slept: list[float] = []

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._mono

    async def sleep(self, seconds: float) -> None:
        # Record and advance virtual time without actually waiting.
        self.slept.append(seconds)
        self._mono += max(seconds, 0.0)
