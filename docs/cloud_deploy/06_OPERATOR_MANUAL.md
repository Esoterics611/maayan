# Operator manual — run the maayan backend

> For the **admin operator**: bring the backend up, confirm it's healthy, log in, watch
> logs, and stop it. Same stack runs locally (for QA) and on the VM — only a couple of env
> values differ (called out inline). Do your **QA locally with this manual first**, then
> deploy with [03_DEPLOY_ORACLE.md](03_DEPLOY_ORACLE.md).

The backend is two containers from [docker-compose.prod.yml](../../docker-compose.prod.yml):
**`qdrant`** (vector store, persistent volume) and **`app`** (`maayan ui` — the FastAPI UI
*and* the CLI target). The UI and the CLI hit the **same** container → same Qdrant, same
SQLite, same model cache.

---

## 0. Prerequisites
- **Docker** + the compose plugin (`docker compose version`).
- This repo checked out; you are in its root.
- An **OpenRouter API key** — ⚠️ **required for the backend to even start**: `maayan ui`
  builds the generation backend at boot and the `app` container **exits** if the key is
  missing. For auth-only QA you can set *any* non-empty placeholder to boot the UI; real
  answers need a real key. (Or run fully local with `GENERATION_BACKEND=ollama`.)
- Disk/RAM: first real index downloads **bge-m3 (~2.3 GB)**; ~16 GB RAM is comfortable.

---

## 1. One-time setup — the `.env`
The `app` container reads `./.env` (never committed). Create it from the template:
```bash
cp .env.prod.example .env
```
Then edit `.env`:

| Setting | Local QA | On the VM |
|---|---|---|
| `OPENROUTER_API_KEY` | your key (**required to boot**; placeholder ok for auth-only QA) | your key |
| `AUTH_ENABLED` | `true` | `true` |
| `AUTH_COOKIE_SECURE` | **`false`** (you browse over `http://localhost`) | **`true`** (HTTPS via Funnel) |
| `SEED_ADMIN_USERNAME` | `admin` | `admin` |
| `SEED_ADMIN_PASSWORD` | a password you choose (≥8 chars) | a strong password |

> ⚠️ **The #1 gotcha:** if `AUTH_COOKIE_SECURE=true` but you open the UI over plain
> `http://…`, the login cookie is silently dropped and you'll bounce back to the login page.
> Local QA is over http → set it **false**. The VM is HTTPS → keep it **true**.

---

## 2. Bring the backend up
```bash
make prod-up        # = docker compose -f docker-compose.prod.yml up -d --build
```
- First run **builds the image** (slow: torch + deps) and starts both containers.
- On startup the `app` seeds the first admin from `SEED_ADMIN_*` (once), then serves the UI.
- `qdrant` must report healthy before `app` starts (compose waits automatically).

## 3. Verify it's healthy
```bash
docker compose -f docker-compose.prod.yml ps          # both services 'running'; app shows (healthy) after warm-up
curl -fsS http://localhost:8000/healthz               # -> {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/   # -> 303 (redirect to /login = auth wall is ON)
```
> The `app` health goes `(health: starting)` until the embedder is ready. With the real
> `bge-m3` model the very first boot can sit in `starting` while it downloads (~2.3 GB) —
> that's expected; watch the logs.

## 4. Log in + create your users
1. Open **http://localhost:8000** (VM: your `https://<machine>.<tailnet>.ts.net`).
2. Log in as the seed admin (`SEED_ADMIN_USERNAME` / `SEED_ADMIN_PASSWORD`).
3. Top-right → **Users** → add your real users (member or admin). Then change the seed
   admin's password and you may blank `SEED_ADMIN_*` in `.env`.

Manage users from the CLI too (handy if you're ever locked out):
```bash
# Local QA: run CLI inside the app container (same backend as the UI):
docker compose -f docker-compose.prod.yml exec app uv run maayan user list
docker compose -f docker-compose.prod.yml exec app uv run maayan user create-admin --username root
# On the VM (bootstrap.sh installs this wrapper): just `maayan user list`, `maayan user passwd <u>`, …
```

## 5. Seed the corpus (so answers have something to ground in)
```bash
M="docker compose -f docker-compose.prod.yml exec app uv run maayan"   # local QA shorthand
$M ingest --all
$M index            # FIRST run downloads bge-m3 (~2.3 GB) — for a long run use: ... exec app sh -c 'uv run maayan index'
$M stats            # confirm chunks landed
$M ask "מהי נפש הבהמית"   # end-to-end smoke (needs OPENROUTER_API_KEY)
```
On the VM these are simply `maayan ingest --all`, `maayan index` (run `index` under `tmux`).

## 6. Watch logs
```bash
make prod-logs                                              # follow BOTH services
docker compose -f docker-compose.prod.yml logs -f app       # app only
docker compose -f docker-compose.prod.yml logs -f qdrant    # qdrant only
docker compose -f docker-compose.prod.yml logs --tail=100 app   # last 100 lines, no follow
```
What healthy startup looks like in `app`: a line `maayan UI → http://0.0.0.0:8000  [auth: login required]`,
then uvicorn `Application startup complete`. Login failures log as `POST /api/login 401`.

## 7. Stop / restart / update
```bash
make prod-down                          # stop both (DATA PERSISTS in named volumes)
make prod-up                            # start again
git pull && make prod-up                # deploy an update (rebuilds the image)
docker compose -f docker-compose.prod.yml restart app   # restart just the app
```

## 8. Backups (the data is one SQLite file + the Qdrant volume)
```bash
docker compose -f docker-compose.prod.yml cp app:/app/data/maayan.sqlite3 ./backup-$(date +%F).sqlite3
```
Qdrant vectors are re-derivable with `maayan index --rebuild`, so the SQLite file is the
irreplaceable part. Copy backups off the machine periodically.

---

## Troubleshooting
| Symptom | Fix |
|---|---|
| `app` exits at boot; logs `OPENROUTER_API_KEY is not set` | Set `OPENROUTER_API_KEY` in `.env` (any non-empty value boots the UI; real answers need a real key), then `make prod-up`. |
| Login bounces back to `/login` | `AUTH_COOKIE_SECURE=true` but you're on http → set `false` for local QA; `make prod-up`. |
| `/` returns 200 not 303 | `AUTH_ENABLED` isn't `true` in `.env` → set it, `make prod-up`. |
| `app` stuck `(health: starting)` | First boot downloading bge-m3 — `make prod-logs` to watch; healthcheck has a 10-min grace. |
| `app` exits / "Qdrant is not reachable" | `qdrant` not healthy yet → `docker compose -f docker-compose.prod.yml ps`; check `logs qdrant`. |
| Locked out (no admin) | `… exec app uv run maayan user create-admin --username root` (or `user passwd <u>`). |
| Port 8000 in use | something else is bound; stop it, or change the host port in `docker-compose.prod.yml`. |

## Quick reference
```bash
make prod-up        # build + start
make prod-logs      # watch logs
make prod-down      # stop (data persists)
curl localhost:8000/healthz                     # liveness
docker compose -f docker-compose.prod.yml ps    # status/health
docker compose -f docker-compose.prod.yml exec app uv run maayan <cmd>   # CLI on the same backend
```

---

> **Validated against the built image:** the production image boots `maayan ui`, seeds the
> admin from `SEED_ADMIN_*`, and the auth flow checks out end-to-end — `/healthz` 200,
> logged-out `/` → 303 `/login`, seed-admin login, `/api/me`, admin-only `/api/users`, and
> admin **create-user** all succeed; a wrong password is 401. (Smoke run used the hashing
> embedder to skip the 2.3 GB bge-m3 download; the real stack uses bge-m3 by default.)

