"""Tests for the auth / user-management layer.

No network, no models — stdlib hashing + temp SQLite + FastAPI TestClient. Covers hashing,
the store, the service (auth/sessions/seed), and the UI auth routes (login wall, admin-only
user CRUD, and the auth-disabled no-regression path).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from maayan.clock import SystemClock
from maayan.config import Settings
from maayan.ui.app import create_app
from maayan.users.hashing import hash_password, verify_password
from maayan.users.models import Session, User
from maayan.users.service import UserService
from maayan.users.store import UserStore


class _MovableClock:
    """A Clock whose `now()` only moves when the test advances it (for expiry tests)."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return 0.0

    async def sleep(self, seconds: float) -> None:
        return None

    def advance(self, **kw: float) -> None:
        self._now = self._now + timedelta(**kw)


def _settings(tmp_path: Path) -> Settings:
    # Low iteration count keeps hashing fast in tests; real default is 240k.
    return Settings(db_path=str(tmp_path / "u.sqlite3"), pbkdf2_iterations=1000)


def _svc(tmp_path: Path, clock: object | None = None) -> UserService:
    s = _settings(tmp_path)
    return UserService(UserStore(s.db_path), clock or SystemClock(), s)  # type: ignore[arg-type]


# -- hashing -----------------------------------------------------------------
def test_hash_verify_roundtrip() -> None:
    h = hash_password("secret123", iterations=1000)
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)


def test_hash_is_salted() -> None:
    a = hash_password("same-password", iterations=1000)
    b = hash_password("same-password", iterations=1000)
    assert a != b
    assert verify_password("same-password", a)
    assert verify_password("same-password", b)


def test_verify_rejects_malformed() -> None:
    assert not verify_password("x", "not-a-valid-hash")
    assert not verify_password("x", "")


# -- store -------------------------------------------------------------------
def test_store_user_roundtrip(tmp_path: Path) -> None:
    store = UserStore(str(tmp_path / "u.sqlite3"))
    store.create_user(
        User(
            id="1", username="ann", display_name="Ann", role="admin",
            password_hash="h", created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    got = store.get_by_username("ann")
    assert got is not None and got.id == "1"
    assert store.get_by_id("1") is not None
    assert store.get_by_username("nobody") is None
    assert store.count() == 1
    assert [u.id for u in store.list_users()] == ["1"]


def test_store_sessions(tmp_path: Path) -> None:
    store = UserStore(str(tmp_path / "u.sqlite3"))
    store.create_session(
        Session(
            token="t", user_id="1",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            expires_at=datetime(2026, 1, 8, tzinfo=UTC),
        )
    )
    got = store.get_session("t")
    assert got is not None and got.user_id == "1"
    store.delete_session("t")
    assert store.get_session("t") is None


# -- service -----------------------------------------------------------------
def test_create_user_validations(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    svc.create_user(username="ann", password="password1", role="admin")
    with pytest.raises(ValueError):
        svc.create_user(username="ann", password="password1")  # duplicate
    with pytest.raises(ValueError):
        svc.create_user(username="  ", password="password1")  # blank
    with pytest.raises(ValueError):
        svc.create_user(username="bob", password="short")  # too weak


def test_authenticate_and_login(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    svc.create_user(username="ann", password="password1")
    assert svc.authenticate("ann", "password1") is not None
    assert svc.authenticate("ann", "nope") is None
    sess = svc.login("ann", "password1")
    assert sess is not None
    assert svc.current_user(sess.token) is not None
    assert svc.login("ann", "nope") is None


def test_session_expiry(tmp_path: Path) -> None:
    clock = _MovableClock()
    svc = _svc(tmp_path, clock)
    svc.create_user(username="ann", password="password1")
    sess = svc.login("ann", "password1")
    assert sess is not None
    assert svc.current_user(sess.token) is not None
    clock.advance(hours=24 * 8)  # past the 7-day TTL
    assert svc.current_user(sess.token) is None


def test_disable_revokes_access(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    out = svc.create_user(username="ann", password="password1")
    sess = svc.login("ann", "password1")
    assert sess is not None
    svc.set_active(out.id, False)
    assert svc.current_user(sess.token) is None
    assert svc.authenticate("ann", "password1") is None


def test_change_password_revokes_and_rotates(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    out = svc.create_user(username="ann", password="password1")
    sess = svc.login("ann", "password1")
    assert sess is not None
    svc.change_password(out.id, "password2")
    assert svc.current_user(sess.token) is None
    assert svc.authenticate("ann", "password2") is not None


def test_seed_admin_idempotent(tmp_path: Path) -> None:
    s = Settings(
        db_path=str(tmp_path / "u.sqlite3"), pbkdf2_iterations=1000,
        seed_admin_username="root", seed_admin_password="rootpass1",
    )
    svc = UserService(UserStore(s.db_path), SystemClock(), s)
    first = svc.ensure_seed_admin()
    assert first is not None and first.role == "admin"
    assert svc.ensure_seed_admin() is None  # already present
    assert len(svc.list_users()) == 1


# -- UI auth routes ----------------------------------------------------------
def _app(tmp_path: Path, *, auth_enabled: bool = True) -> tuple[object, UserService]:
    s = _settings(tmp_path)
    svc = UserService(UserStore(s.db_path), SystemClock(), s)
    svc.create_user(username="admin", password="adminpass1", display_name="Admin", role="admin")
    svc.create_user(username="member", password="memberpass1", display_name="Mem", role="member")
    app = create_app(  # type: ignore[arg-type]
        None, None, None, None, None, None, None, None,
        users=svc, auth_enabled=auth_enabled,
    )
    return app, svc


def test_protected_requires_login(tmp_path: Path) -> None:
    app, _ = _app(tmp_path)
    client = TestClient(app)  # type: ignore[arg-type]
    assert client.get("/api/me").status_code == 401
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_login_then_access(tmp_path: Path) -> None:
    app, _ = _app(tmp_path)
    client = TestClient(app)  # type: ignore[arg-type]
    r = client.post("/api/login", json={"username": "admin", "password": "adminpass1"})
    assert r.status_code == 200
    assert r.json()["user"]["username"] == "admin"
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["user"]["role"] == "admin"


def test_bad_login_rejected(tmp_path: Path) -> None:
    app, _ = _app(tmp_path)
    client = TestClient(app)  # type: ignore[arg-type]
    assert client.post("/api/login", json={"username": "admin", "password": "x"}).status_code == 401


def test_users_endpoint_is_admin_only(tmp_path: Path) -> None:
    app, _ = _app(tmp_path)
    member = TestClient(app)  # type: ignore[arg-type]
    member.post("/api/login", json={"username": "member", "password": "memberpass1"})
    assert member.get("/api/users").status_code == 403
    admin = TestClient(app)  # type: ignore[arg-type]
    admin.post("/api/login", json={"username": "admin", "password": "adminpass1"})
    assert admin.get("/api/users").status_code == 200


def test_admin_creates_user(tmp_path: Path) -> None:
    app, svc = _app(tmp_path)
    client = TestClient(app)  # type: ignore[arg-type]
    client.post("/api/login", json={"username": "admin", "password": "adminpass1"})
    r = client.post(
        "/api/users",
        json={"username": "newbie", "password": "newpass12", "role": "member"},
    )
    assert r.status_code == 200
    assert any(u.username == "newbie" for u in svc.list_users())


def test_logout_clears_session(tmp_path: Path) -> None:
    app, _ = _app(tmp_path)
    client = TestClient(app)  # type: ignore[arg-type]
    client.post("/api/login", json={"username": "admin", "password": "adminpass1"})
    assert client.get("/api/me").status_code == 200
    client.post("/api/logout")
    assert client.get("/api/me").status_code == 401


def test_auth_disabled_is_no_regression(tmp_path: Path) -> None:
    app, _ = _app(tmp_path, auth_enabled=False)
    client = TestClient(app)  # type: ignore[arg-type]
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json() == {"auth_enabled": False, "user": None}
    assert client.get("/", follow_redirects=False).status_code == 200
