"""User/auth service: account creation, authentication, sessions.

All collaborators injected (store, clock, settings) per CLAUDE.md — no time/secrets read
inline in logic; the Clock drives session expiry so tests are deterministic. The store
holds bytes; this service owns hashing (via maayan.users.hashing) and policy (min password
length, uniqueness, active checks, seed admin).
"""

from __future__ import annotations

import secrets
import uuid
from datetime import timedelta

from maayan.clock import Clock
from maayan.config import Settings
from maayan.users.hashing import hash_password, verify_password
from maayan.users.models import Role, Session, User, UserOut
from maayan.users.store import UserStore

MIN_PASSWORD_LEN = 8


class UserService:
    """Authentication + user management. Off unless `settings.auth_enabled`."""

    def __init__(self, store: UserStore, clock: Clock, settings: Settings) -> None:
        self._store = store
        self._clock = clock
        self._settings = settings

    # -- account management --------------------------------------------------
    def create_user(
        self,
        *,
        username: str,
        password: str,
        display_name: str = "",
        role: Role = "member",
        created_by: str | None = None,
    ) -> UserOut:
        """Create a user. Raises ValueError on blank/duplicate username or weak password."""
        username = username.strip()
        display_name = display_name.strip() or username
        if not username:
            raise ValueError("username must not be blank")
        if len(password) < MIN_PASSWORD_LEN:
            raise ValueError(f"password must be at least {MIN_PASSWORD_LEN} characters")
        if self._store.get_by_username(username) is not None:
            raise ValueError(f"username already exists: {username}")
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            display_name=display_name,
            role=role,
            password_hash=hash_password(password, iterations=self._settings.pbkdf2_iterations),
            active=True,
            created_at=self._clock.now(),
            created_by=created_by,
        )
        self._store.create_user(user)
        return user.to_out()

    def list_users(self) -> list[UserOut]:
        return [u.to_out() for u in self._store.list_users()]

    def set_active(self, user_id: str, active: bool) -> UserOut:
        user = self._store.get_by_id(user_id)
        if user is None:
            raise ValueError("user not found")
        self._store.set_active(user_id, active)
        if not active:
            self._store.delete_sessions_for_user(user_id)  # revoke access immediately
        refreshed = self._store.get_by_id(user_id)
        assert refreshed is not None  # just updated it
        return refreshed.to_out()

    def change_password(self, user_id: str, new_password: str) -> None:
        if len(new_password) < MIN_PASSWORD_LEN:
            raise ValueError(f"password must be at least {MIN_PASSWORD_LEN} characters")
        if self._store.get_by_id(user_id) is None:
            raise ValueError("user not found")
        self._store.set_password_hash(
            user_id, hash_password(new_password, iterations=self._settings.pbkdf2_iterations)
        )
        self._store.delete_sessions_for_user(user_id)  # force re-login everywhere

    # -- authentication / sessions ------------------------------------------
    def authenticate(self, username: str, password: str) -> User | None:
        user = self._store.get_by_username(username.strip())
        if user is None or not user.active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def login(self, username: str, password: str) -> Session | None:
        """Authenticate and mint a session. None if credentials are bad/disabled."""
        user = self.authenticate(username, password)
        if user is None:
            return None
        now = self._clock.now()
        session = Session(
            token=secrets.token_urlsafe(32),
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(hours=self._settings.session_ttl_hours),
        )
        return self._store.create_session(session)

    def current_user(self, token: str | None) -> User | None:
        """Resolve the active user behind a session token, or None (expired/disabled/unknown)."""
        if not token:
            return None
        session = self._store.get_session(token)
        if session is None:
            return None
        if session.expires_at <= self._clock.now():
            self._store.delete_session(token)
            return None
        user = self._store.get_by_id(session.user_id)
        if user is None or not user.active:
            return None
        return user

    def logout(self, token: str | None) -> None:
        if token:
            self._store.delete_session(token)

    # -- bootstrap -----------------------------------------------------------
    def ensure_seed_admin(self) -> UserOut | None:
        """Seed the configured first admin once. No-op if unset or already present."""
        username = self._settings.seed_admin_username.strip()
        password = self._settings.seed_admin_password.get_secret_value()
        if not username or not password:
            return None
        if self._store.get_by_username(username) is not None:
            return None
        return self.create_user(
            username=username,
            password=password,
            display_name=username,
            role="admin",
            created_by="seed",
        )
