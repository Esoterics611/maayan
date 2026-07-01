"""Paced, resumable populate orchestration (the `maayan populate` drip).

Free generation endpoints rate-limit hard, so populate runs are driven as a paced
drip with backoff instead of a burst. The pacing/backoff is Clock-injected (house
rule: no `time.sleep`), so tests run instantly with a FakeClock.
"""

from maayan.populate.drip import DripStats, run_drip

__all__ = ["DripStats", "run_drip"]
