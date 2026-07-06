"""Opt-in logging setup.

The library emits no logs by default — imports stay quiet and the test suite isn't noisy.
The CLI entrypoints call `configure_logging` so operational diagnostics (e.g. the compose
fill gate decisions from R1) surface in the server/console output. Idempotent, so repeated
calls (or a reload) don't stack handlers.
"""

from __future__ import annotations

import logging

_configured = False


def configure_logging(level: str = "INFO") -> None:
    """Attach a stream handler to the top-level ``maayan`` logger (once)."""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log = logging.getLogger("maayan")
    log.setLevel(level.upper())
    log.addHandler(handler)
    log.propagate = False  # our own handler prints; don't double via the root logger
    _configured = True
