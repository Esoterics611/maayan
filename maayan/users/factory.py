"""User service factory (DI at the edge)."""

from __future__ import annotations

from maayan.clock import SystemClock
from maayan.config import Settings
from maayan.users.service import UserService
from maayan.users.store import UserStore


def build_user_service(settings: Settings) -> UserService:
    """Assemble a UserService wired to the same DB file as the rest."""
    return UserService(UserStore(settings.db_path), SystemClock(), settings)
