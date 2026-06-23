"""SQLite persistence for users + sessions (same DB file as the rest of maayan).

New tables only (`IF NOT EXISTS`), so this layers onto an existing DB without touching
chunks/threads/etc. Pure persistence — no clock, no hashing; timestamps and password
hashes arrive already set on the models (the service owns the Clock + hashing).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import cast

from maayan.users.models import Role, Session, User

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    role          TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    created_by    TEXT
);
CREATE TABLE IF NOT EXISTS user_sessions (
    token      TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id);
"""


class UserStore:
    """Stores user accounts and their active sessions."""

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: shared safely across FastAPI worker threads
        # (Python 3.12 sqlite3 is serialized). See threads/store.py.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- users ---------------------------------------------------------------
    def create_user(self, user: User) -> User:
        self._conn.execute(
            "INSERT INTO users "
            "(id, username, display_name, role, password_hash, active, created_at, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user.id,
                user.username,
                user.display_name,
                user.role,
                user.password_hash,
                int(user.active),
                user.created_at.isoformat(),
                user.created_by,
            ),
        )
        self._conn.commit()
        return user

    def get_by_username(self, username: str) -> User | None:
        row = self._conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return self._row_to_user(row) if row else None

    def get_by_id(self, user_id: str) -> User | None:
        row = self._conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._row_to_user(row) if row else None

    def list_users(self) -> list[User]:
        rows = self._conn.execute("SELECT * FROM users ORDER BY created_at ASC")
        return [self._row_to_user(r) for r in rows]

    def count(self) -> int:
        """Total number of users (for the stats dashboard / bootstrap checks)."""
        return int(self._conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"])

    def set_active(self, user_id: str, active: bool) -> None:
        self._conn.execute(
            "UPDATE users SET active = ? WHERE id = ?", (int(active), user_id)
        )
        self._conn.commit()

    def set_password_hash(self, user_id: str, password_hash: str) -> None:
        self._conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
        )
        self._conn.commit()

    # -- sessions ------------------------------------------------------------
    def create_session(self, session: Session) -> Session:
        self._conn.execute(
            "INSERT INTO user_sessions (token, user_id, created_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (
                session.token,
                session.user_id,
                session.created_at.isoformat(),
                session.expires_at.isoformat(),
            ),
        )
        self._conn.commit()
        return session

    def get_session(self, token: str) -> Session | None:
        row = self._conn.execute(
            "SELECT * FROM user_sessions WHERE token = ?", (token,)
        ).fetchone()
        if row is None:
            return None
        return Session(
            token=row["token"],
            user_id=row["user_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]),
        )

    def delete_session(self, token: str) -> None:
        self._conn.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
        self._conn.commit()

    def delete_sessions_for_user(self, user_id: str) -> None:
        self._conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        self._conn.commit()

    def _row_to_user(self, row: sqlite3.Row) -> User:
        return User(
            id=row["id"],
            username=row["username"],
            display_name=row["display_name"],
            role=cast(Role, row["role"]),
            password_hash=row["password_hash"],
            active=bool(row["active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            created_by=row["created_by"],
        )
