"""Generic paced-drip runner: draft items one at a time, spaced + retried.

Reused by the `populate` CLI for both lexicon terms and cross-text connections.
The only I/O here is the injected `Clock.sleep` — the actual drafting is a caller-
supplied `draft_one` callable (which retrieves, drafts, verifies, and persists a
single item via the existing populators). Retryable provider errors (429/5xx) are
absorbed with linear backoff; each item's drafts persist as they happen, so a run
that dies mid-way resumes cleanly on the next invocation.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

from pydantic import BaseModel, Field

from maayan.clock import Clock


class _Supported(Protocol):
    """A drafted suggestion exposes whether it is grounded/faithful enough to index."""

    supported: bool


class DripStats(BaseModel):
    """Tally of one drip run (crosses the drip → CLI boundary, so it's a model)."""

    attempted: int = 0
    drafted: int = 0
    supported: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)


async def run_drip[T](
    items: Sequence[T],
    draft_one: Callable[[T], Sequence[_Supported]],
    *,
    clock: Clock,
    pace: float,
    max_retries: int = 5,
    backoff: float = 30.0,
    on_result: Callable[[int, T, Sequence[_Supported]], None] | None = None,
    on_error: Callable[[int, T, Exception, int], None] | None = None,
) -> DripStats:
    """Draft each item with pacing + backoff; return the run tally.

    - `draft_one(item)` drafts and persists one item, returning its suggestion(s).
    - Between items we wait `pace`; after a retryable error we wait `backoff * attempt`
      (up to `max_retries`), all via the injected clock so tests never block.
    - `on_result` / `on_error` are progress hooks (e.g. logging), never control flow.
    """
    stats = DripStats()
    for idx, item in enumerate(items, 1):
        stats.attempted += 1
        for attempt in range(1, max_retries + 1):
            try:
                drafts = draft_one(item)
                for draft in drafts:
                    stats.drafted += 1
                    if draft.supported:
                        stats.supported += 1
                if on_result is not None:
                    on_result(idx, item, drafts)
                break
            except Exception as exc:
                if on_error is not None:
                    on_error(idx, item, exc, attempt)
                if attempt >= max_retries:
                    stats.failed += 1
                    stats.errors.append(f"{type(exc).__name__}: {exc}")
                else:
                    await clock.sleep(backoff * attempt)
        await clock.sleep(pace)
    return stats
