"""Thread service factory (DI at the edge)."""

from __future__ import annotations

from maayan.clock import SystemClock
from maayan.config import Settings
from maayan.threads.service import ThreadService
from maayan.threads.store import ThreadStore


def build_thread_service(settings: Settings) -> ThreadService:
    """Assemble a ThreadService wired to the same DB file as the rest."""
    return ThreadService(ThreadStore(settings.db_path), SystemClock())
