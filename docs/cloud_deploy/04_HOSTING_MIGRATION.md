# Phase 4 — Scale up with fundraising

> The free deploy (Phases 1–3) gets maayan public and usable at **$0**. This doc is the
> **upgrade path** for when fundraising lands — each step is a self-contained, copy-paste
> prompt for a future Claude Code session. The architecture was built for this: generation,
> vectors, storage, and auth are all behind interfaces or config, so each can move
> independently **without rewrites**.

The guiding principle: **stay on the same Oracle account** (Always Free → pay-as-you-go is a
billing flip, not a migration) and **change one layer at a time**, proving it with the eval
harness before the next.

---

## B1 — More capacity (bigger VM)
*When:* the free shape feels tight (slow indexing, many concurrent users).
*What:* resize the VM / move to a paid Ampere or x86 shape on the same account; nothing in
the app changes. Cost: a few $/mo for a small paid shape.

```
We're moving maayan to a larger Oracle shape on the same account. No app changes expected —
verify docker-compose.prod.yml still comes up, the bge-m3 model cache volume persists, and
`maayan stats` + a sample `maayan ask` work. Document the resize in docs/cloud_deploy/03.
```

## B2 — Local generation on a GPU (privacy + zero per-call cost)
*When:* OpenRouter spend matters, or full privacy is wanted.
*What:* move to a GPU shape, run Ollama, flip the backend by config — the `GenerationBackend`
protocol already supports this (`GENERATION_BACKEND=ollama`).

```
Switch maayan's generation backend to local Ollama on a GPU host. Follow CLAUDE.md. Use the
existing GenerationBackend protocol + OllamaBackend (no logic changes outside config/wiring):
add ollama to docker-compose.prod.yml (GPU runtime), pull an open instruct model, set
GENERATION_BACKEND=ollama + OLLAMA_MODEL, and re-run the eval harness (make eval) to compare
Hebrew answer quality vs OpenRouter. Document the tradeoff and the rollback (flip the env).
```

## C1 — Managed vector DB (Qdrant Cloud)
*When:* you want vectors off the VM (durability, easier scaling).
*What:* point `QDRANT_URL`/`QDRANT_API_KEY` at a Qdrant Cloud cluster (free 1 GB tier exists);
the client and collection code are unchanged.

```
Migrate maayan's vectors from the in-VM Qdrant container to a managed Qdrant Cloud cluster.
Follow CLAUDE.md. This is config-only: set QDRANT_URL/QDRANT_API_KEY to the cluster, remove
the qdrant service from docker-compose.prod.yml, and re-index (`maayan index --rebuild`).
Verify retrieval parity with `make eval` before and after. Document in docs/cloud_deploy.
```

## C2 — Real multi-user hardening + custom domain
*When:* sharing beyond a trusted few; fundraising wants a branded URL.
*What:* a custom domain with Caddy + Let's Encrypt in front of the app; server-side
author-from-session enforcement; password-reset flow; audit of admin actions.

```
Harden maayan's auth for public multi-user use and add a custom domain. Follow CLAUDE.md.
(1) Add a Caddy reverse proxy service to docker-compose.prod.yml with automatic HTTPS for
<DOMAIN>, proxying to the app; keep Funnel as a fallback. (2) Enforce author server-side from
the session (don't trust client-sent author when auth_enabled). (3) Add a self-serve password
change + admin password reset already-stubbed routes into the UI. (4) Add a simple admin
audit log (who created/disabled whom). Tests for each. Update docs/cloud_deploy/02 + 03.
```

## D1 — Backups & restore drills (managed object storage)
*When:* the knowledge base is irreplaceable (it is, once experts contribute).
*What:* scheduled off-VM backups of the SQLite file (and optionally Qdrant snapshots) to
object storage (Oracle Object Storage Always Free, or S3/B2), plus a tested restore.

```
Add automated, off-VM backups for maayan. Follow CLAUDE.md. A nightly job (systemd timer or
cron in the compose stack) uploads data/maayan.sqlite3 (and a Qdrant snapshot) to object
storage with rotation/retention. Provide a one-command restore and document a restore DRILL
in docs/cloud_deploy/03 (§Backups). Secrets via env only. Test the backup/restore logic with
a temp dir + a fake uploader (no network).
```

## D2 — CI/CD deploy + spend/abuse guardrails
*When:* updates are frequent and the public URL needs protection.
*What:* GitHub Actions to build/push the image and deploy on the VM; OpenRouter spend caps +
per-user rate limiting in the app; basic observability.

```
Add CI/CD and guardrails for the public maayan deploy. Follow CLAUDE.md. (1) A GitHub Actions
workflow that, on main, builds the image and triggers a pull+restart on the VM (over Tailscale
SSH). (2) Per-user rate limiting on /ask + /compose and a configurable daily generation cap
(config-driven, default-deny when exceeded — reuse the refusal path). (3) Minimal request/cost
logging (no secrets). Tests for the limiter (FakeClock) and the deploy workflow's smoke step.
Document in docs/cloud_deploy.
```

---

## Cost ladder (rough, USD/mo)
| Stage | Setup | ~Cost |
|---|---|---|
| Free (Phases 1–3) | Oracle Always Free + Funnel + OpenRouter pay-go | **$0** + a few ¢/answer |
| + custom domain | C2 | +~$1/mo (domain ~$12/yr) |
| + bigger VM | B1 | +~$5–20 |
| + GPU / local gen | B2 | +$ varies (or saves OpenRouter $) |
| + managed Qdrant | C1 | $0 on free tier, then usage |

Every rung is **independent** and **reversible by config** — that is the payoff of the
DI/protocol/config-driven architecture in [CLAUDE.md](../../CLAUDE.md).
