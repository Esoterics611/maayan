# academy_deploy — Maavar + Maayan academy infrastructure

> ⚠️ **Scope:** this folder is the **Next.js membership academy** (Maavar = tech
> English; Maayan academy = separate educational site). It is **not** the Python
> `maayan` RAG that owns this repo. It lives here as the long-term infrastructure
> track so research + configs stay versioned alongside the project they support.
> The repo-root `docker-compose.yml` (Qdrant) is unrelated — don't confuse them.

## Contents

| File | What |
|---|---|
| [HOSTING_RESEARCH.md](HOSTING_RESEARCH.md) | Full 2026 research: hosting, DB, Israeli payments, marketing, recommended stack + costs. **Start here.** |
| [DEPLOY.md](DEPLOY.md) | Step-by-step: short-term Vercel track + long-term Oracle VPS track + migration ladder. |
| [PRISMA_DB.md](PRISMA_DB.md) | Connection strings per host + the **capacity-safe booking transaction** (the race-condition-proof pattern). |
| [config/schema.prisma](config/schema.prisma) | Data layer: User/Role RBAC, Course/Class/Booking, Plan/Membership/PaymentEvent + Auth.js adapter models. |
| [config/docker-compose.yml](config/docker-compose.yml) | Two Next.js apps + Postgres + Caddy on one VPS. |
| [config/Caddyfile](config/Caddyfile) | Auto-HTTPS reverse proxy for both subdomains. |
| [config/init-databases.sql](config/init-databases.sql) | Creates the second app DB on first Postgres init. |
| [config/.env.example](config/.env.example) | All required secrets/vars. |
| [config/cardcom-webhook.ts](config/cardcom-webhook.ts) | Cardcom recurring-membership webhook handler (Next.js route). |

## TL;DR recommendation

- **Host:** Oracle Always Free VPS (2 OCPU/12 GB — halved in 2026) + Caddy +
  Docker. Zero-ops alternative: Railway ~$5–10/mo.
- **DB:** Postgres from day one (self-hosted in Docker or **Neon** free). Never file
  SQLite in prod. Booking needs real transactions → no D1/edge-libSQL.
- **Payments:** **Cardcom** (Israeli recurring + installments/tashlumim + Hebrew tax
  invoices). Not Stripe/MoR for Israeli B2C.
- **Email:** Resend (transactional) + Brevo (marketing).
- **Combine** Maavar + Maayan on one host + one Postgres instance, **separate DBs**.
- **Short-term Vercel** points at the **same Neon DB** → later host swap, no data
  migration.

Cost: **~$0 + processor fees** (0–50 students) → **~$35–60/mo** (200+).
