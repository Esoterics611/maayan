"""Pydantic models for user accounts + sessions.

`User` carries the password hash and stays server-side; `UserOut` is the safe projection
that crosses the HTTP boundary (CLAUDE.md rule 1: typed models, never loose dicts). A
`Session` is an opaque server-side token bound to a user, so logout/disable revokes access
immediately.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Role = Literal["admin", "member"]


class User(BaseModel):
    """A user account. `password_hash` is the self-describing pbkdf2 string (never sent out)."""

    id: str
    username: str
    display_name: str
    role: Role
    password_hash: str
    active: bool = True
    created_at: datetime
    created_by: str | None = None

    def to_out(self) -> UserOut:
        """Project to the client-safe view (drops the password hash)."""
        return UserOut(
            id=self.id,
            username=self.username,
            display_name=self.display_name,
            role=self.role,
            active=self.active,
            created_at=self.created_at,
            created_by=self.created_by,
        )


class UserOut(BaseModel):
    """Safe projection of a `User` — everything except the password hash."""

    id: str
    username: str
    display_name: str
    role: Role
    active: bool
    created_at: datetime
    created_by: str | None = None


class Session(BaseModel):
    """An opaque session token bound to a user, with an absolute expiry."""

    token: str
    user_id: str
    created_at: datetime
    expires_at: datetime
