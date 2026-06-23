# maayan — Cloud Deploy plan

> Get maayan **off the laptop** onto a **free, always-on host**, reachable at a
> **public URL with login**, where the **same backend** serves the web UI and the
> CLI (over SSH). Built free first; designed to **scale up with fundraising** on the
> **same account**.

This folder is the **living plan**. It is broken into ordered, self-contained pieces so
a future Claude Code session can pick up any one and run it. **Read this index first,
then execute the phases in order.** Every code phase must follow
[CLAUDE.md](../../CLAUDE.md) (typed + `mypy --strict`, DI, config-driven, no secrets,
default-deny, tests mock network/models).

---

## The decisions (locked with the steward)

| Decision | Choice | Why |
|---|---|---|
| **Host** | Oracle Cloud **Always Free** (ARM Ampere A1 VM) | Up to 4 OCPU / 24 GB / 200 GB, free *forever*; native SSH; runs `bge-m3` + Qdrant unchanged; upgrades to paid on the **same account** when fundraising lands. |
| **Access** | **Public URL + login** (multi-user) | The steward wants to share a link; anyone with the URL + their password gets in. |
| **Auth model** | **Per-user accounts; admin creates users in the UI** | Roles `admin` / `member`; first admin seeded via CLI; no open self-signup; logged-in name auto-fills the `author` field. |
| **Public exposure** | **Tailscale Funnel** (free `*.ts.net` HTTPS), domain later | Free public HTTPS with **zero open firewall ports** and no domain purchase; a custom domain is a later upgrade ([04](04_HOSTING_MIGRATION.md)). |
| **Generation** | Stays **OpenRouter** (cloud API) | No local GPU on the free tier; swappable to local Ollama once on a paid GPU shape. |

### Why this shape (the constraint that drives everything)
`bge-m3` embeddings run **in-process** via `torch`/FlagEmbedding — **~3–4 GB RAM** and a
**~2.3 GB** one-time model download. That rules out tiny PaaS free tiers (Render 512 MB,
Fly 256 MB) and is why we need a real **VM with real RAM** — which Oracle Always Free
gives away. Generation is just an API call; Qdrant is a container with a volume; the whole
knowledge layer is **one SQLite file**. So "the same backend for UI and CLI" is literally:
one container, one Qdrant, one SQLite, one model cache — the UI calls it over HTTP, you
call it over SSH.

---

## Phases (execute top to bottom)

### Phase 0 — Plan & manual setup *(this folder; done)*
- This index + the companion **[01_MANUAL_SETUP.md](01_MANUAL_SETUP.md)** — **everything
  *you* must do by hand** (accounts, keys, signups). Skim it now; you don't need to *do* it
  until Phase 2.

### Phase 1 — Local user management ⭐ *(first build; this session)*
- Build **auth + multi-user locally** and prove it with tests **before** anything goes
  public. Spec: **[02_USER_MANAGEMENT.md](02_USER_MANAGEMENT.md)**.
- Outcome: `AUTH_ENABLED=true` puts a login wall in front of the whole UI; an admin can
  create/disable users from a **Users** panel; logged-in identity flows into `author`.
- Crucially **`auth_enabled` defaults to `false`**, so your local workflow and the existing
  test suite are unchanged until you opt in.

### Phase 2 — Provision the free host *(you + me)*
- Follow **[03_DEPLOY_ORACLE.md](03_DEPLOY_ORACLE.md)**: create the Oracle Always Free VM,
  run `deploy/bootstrap.sh`, join Tailscale, turn on Funnel for the public URL.
- The account/console steps are **yours** (can't be automated — see
  [01_MANUAL_SETUP.md](01_MANUAL_SETUP.md)); the on-VM steps are one script.

### Phase 3 — Ship the container *(deploy artifacts)*
- `Dockerfile`, `docker-compose.prod.yml` (with `AUTH_ENABLED=true`), `.env.prod.example`,
  the `deploy/` scripts, and the `maayan` CLI-over-SSH wrapper. Built and verified locally
  first, then run on the VM. (Tracked as a build task; spec lives in
  [03_DEPLOY_ORACLE.md](03_DEPLOY_ORACLE.md).)

### Operating it — day to day *(local QA now, and on the VM)*
- **[06_OPERATOR_MANUAL.md](06_OPERATOR_MANUAL.md)**: bring the backend up, verify health,
  log in, watch logs, back up, stop. Use this to **QA locally before deploying**.

### Phase 4 — Scale up with fundraising *(future sessions)*
- **[04_HOSTING_MIGRATION.md](04_HOSTING_MIGRATION.md)**: paid VM / GPU for local
  generation + reranker, managed Qdrant, object-storage backups, a custom domain, CI/CD,
  spend guardrails — each as a **copy-paste prompt** for a future session.

### Ongoing — Near-term backlog *(while you do the curriculum)*
- **[05_NEXT_STEPS.md](05_NEXT_STEPS.md)**: the system's near-term needs (distilled from the
  Phase 4/5 "deliberately NOT in this phase" lists + what hosting surfaces), prioritized.

---

## What's done vs. pending (update as you go)

- [x] Phase 0 — plan + manual-setup companion written
- [ ] Phase 1 — local user management (in progress)
- [ ] Phase 2 — Oracle VM provisioned + Tailscale Funnel public URL
- [ ] Phase 3 — container shipped, UI + CLI-over-SSH live on the VM
- [ ] Phase 4 — scale-up items (as fundraising allows)

## A note on honesty about what I can and can't do
I can write and test **all the code and artifacts**, and drive every on-VM step. I
**cannot** create your Oracle/Tailscale/OpenRouter accounts or pass Oracle's card
verification — those need you. [01_MANUAL_SETUP.md](01_MANUAL_SETUP.md) is the exact,
ordered list of those human-only steps so nothing is a surprise.
