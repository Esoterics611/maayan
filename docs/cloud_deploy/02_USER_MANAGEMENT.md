# Phase 1 — Local user management (auth + multi-user)

> **Build this first, locally, with tests — before anything goes public.** A public URL with
> no login would let strangers read the scholar's knowledge base and burn OpenRouter spend.
> This is the auth layer Phase 4 of the original build plan deliberately deferred as "a
> deployment concern for if/when it leaves one machine"
> ([BUILD_PLAN_PHASE4.md](../BUILD_PLAN_PHASE4.md)). That time is now.

Follows [CLAUDE.md](../../CLAUDE.md): typed + `mypy --strict`, dependency injection,
config-driven, secrets only via env, tests mock network/models, in-memory SQLite for store
tests. **No new heavy dependencies** — password hashing uses the standard library.

## Decisions (locked)
- **Per-user accounts**; username + password. Roles **`admin`** and **`member`**.
- **Admin creates users in the UI** — no open self-registration.
- **First admin is seeded** once (CLI command, or `SEED_ADMIN_*` env on first boot).
- **Logged-in identity auto-fills the `author`** field that contributions/terms/compositions
  already require.
- **`auth_enabled` defaults to `false`** → local dev and the existing test suite are
  unchanged until you opt in. The deploy sets it `true`.

## The shape (mirrors existing modules)
A new `maayan/users/` module in the same style as `threads/`, `capture/`, etc.: pydantic
models, a SQLite store (new `IF NOT EXISTS` tables in the same DB file), an injected service,
and a `factory.py`. The UI gains a thin auth layer; no business logic in route handlers.

```
maayan/users/
  models.py    Role, User (with password_hash), UserOut (no hash), Session
  hashing.py   hash_password / verify_password  (stdlib hashlib.pbkdf2_hmac)
  store.py     UserStore — users + user_sessions tables (same DB; idempotent migration)
  service.py   UserService (store, clock, settings injected): login/session/CRUD/seed
  factory.py   build_user_service(settings)
```

### Data model
- `Role = Literal["admin", "member"]`.
- `User`: `id, username, display_name, role, password_hash, active: bool, created_at,
  created_by: str | None`. `password_hash` is a self-describing string
  `pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>` (no external lib).
- `UserOut`: the safe projection (everything **except** `password_hash`) — this is what
  crosses the HTTP boundary.
- `Session`: `token, user_id, created_at, expires_at`. Opaque random token (`secrets`),
  stored server-side so logout/disable revokes immediately.

### Config additions (`maayan/config.py`)
- `auth_enabled: bool = False`
- `session_ttl_hours: int = 168` (7 days)
- `session_cookie_name: str = "maayan_session"`
- `auth_cookie_secure: bool = False`  (set `true` in prod behind HTTPS)
- `pbkdf2_iterations: int = 240_000`
- `seed_admin_username: str = ""` and `seed_admin_password: SecretStr = ""` (optional
  headless first-admin seed; ignored if blank or the user already exists)

### Service surface (`UserService`)
- `create_user(username, password, display_name, role, created_by) -> UserOut`
  (unique username, non-blank, min password length).
- `authenticate(username, password) -> User | None` (must be `active` + hash verifies).
- `login(username, password) -> Session | None` (authenticate → mint a TTL session).
- `current_user(token) -> User | None` (valid, unexpired session → user).
- `logout(token) -> None`.
- `list_users() -> list[UserOut]`, `set_active(user_id, active)`,
  `change_password(user_id, new_password)`.
- `ensure_seed_admin() -> None` (idempotent; creates the configured admin if absent).

### UI integration (`maayan/ui/app.py`, thin)
- `create_app(...)` gains an injected `users: UserService` and reads `auth_enabled` from
  settings.
- **Auth middleware** (one `@app.middleware("http")`): when `auth_enabled`, every request
  except an allowlist (`/login`, `/api/login`, `/healthz`, login static assets) must carry a
  valid session cookie → sets `request.state.user`. HTML routes redirect to `/login`; API
  routes return `401`. When `auth_enabled` is `false`, a synthetic local user is attached, so
  dev/tests are untouched.
- **New routes:** `POST /api/login`, `POST /api/logout`, `GET /api/me`,
  `GET /api/users` (admin), `POST /api/users` (admin),
  `POST /api/users/{id}/active` (admin), `POST /api/users/{id}/password` (admin or self).
- **Login page:** `maayan/ui/static/login.html` served at `/login`.
- **Users panel:** in `index.html`, visible only when `GET /api/me` returns role `admin`:
  list users, create user, enable/disable, reset password.
- **Author auto-fill:** the UI prefills the existing `author` inputs from `/api/me`
  `display_name`. (Server-side author-from-session enforcement is a hardening item in
  [05_NEXT_STEPS.md](05_NEXT_STEPS.md).)

### CLI (`maayan/cli.py`)
- A `user` command group: `maayan user create-admin --username NAME` (prompts for password),
  `maayan user list`, `maayan user disable USERNAME`, `maayan user passwd USERNAME`.
- `ui()` builds + injects `UserService` and calls `ensure_seed_admin()` on startup.

### Tests (no network/models; in-memory SQLite)
- hashing: verify round-trips; wrong password fails; two hashes of the same password differ
  (random salt).
- store: create/list/get-by-username; session create/get/expiry/delete.
- service: create rejects blanks + duplicates; `authenticate` honors `active`; `login`
  mints a session; expired/disabled session → `current_user` is `None`; `ensure_seed_admin`
  is idempotent.
- routes (mock `UserService`): login sets cookie; protected route → `401` without cookie and
  `200` with; `/api/users` is admin-only (member → `403`); create-user happy path. Also: with
  `auth_enabled=false`, protected routes work with no cookie (no regression).

---

## Copy-paste prompt for a fresh session (if picking this up later)

```
Build a local user-management / auth layer for maayan. Follow CLAUDE.md (typed, mypy
--strict, DI, config-driven, secrets via env, tests mock network/models, in-memory SQLite
for store tests). NO new heavy dependencies — hash passwords with stdlib
hashlib.pbkdf2_hmac.

Model: per-user accounts (username+password), roles admin/member, ADMIN-CREATES-USERS (no
open signup), first admin seeded via CLI or SEED_ADMIN_* env. auth_enabled defaults to false
so existing dev/tests are unchanged.

Build exactly the module/config/UI/CLI/tests described in docs/cloud_deploy/02_USER_
MANAGEMENT.md (maayan/users/{models,hashing,store,service,factory}.py; config flags; an
auth middleware + login page + /api/login|logout|me + admin user-CRUD routes in
maayan/ui/app.py; a `maayan user` CLI group; full tests). When auth_enabled is true the whole
UI is behind login; an admin manages users from a Users panel; the logged-in name auto-fills
the author field.

Then run make test / typecheck / lint and show: a passing test run, `maayan user create-admin`
seeding an admin, and the login wall + Users panel working with `AUTH_ENABLED=true`.
```
