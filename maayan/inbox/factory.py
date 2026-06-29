"""Inbox service factory (DI seam) — wired to the same DB file as everything else."""

from __future__ import annotations

from maayan.clock import Clock, SystemClock
from maayan.config import Settings
from maayan.inbox.service import InboxService
from maayan.inbox.store import InboxStore


def build_inbox_service(settings: Settings, *, clock: Clock | None = None) -> InboxService:
    return InboxService(InboxStore(settings.db_path), clock or SystemClock())
