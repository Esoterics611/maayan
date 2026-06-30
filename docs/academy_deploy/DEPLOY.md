# Academy deployment guide

Two tracks. They share the **same Neon/Postgres data and the same app code** — only
the host differs, so moving between them is a host swap, never a migration.

---

## A. Short-term: Vercel (disposable, fast)

1. Create a **Neon** project + database (free tier). Copy the **pooled** connection
   string and the **direct** string.
2. In Vercel project settings → Environment Variables, set:
   - `DATABASE_URL` = Neon **pooled** URL (`...-pooler.neon.tech/...?pgbouncer=true&connection_limit=1`)
   - `DIRECT_URL` = Neon **direct** URL
   - `AUTH_SECRET`, `AUTH_URL` (= your Vercel domain), `RESEND_API_KEY`,
     `CARDCOM_*` (see `config/.env.example`)
3. `npx prisma migrate deploy` runs against `DIRECT_URL` (add to the build step or run once locally).
4. `git push` → Vercel builds the Next.js app. Done.
5. **Commercial note:** a paid membership site needs **Vercel Pro** ($20/mo);
   Hobby's Fair-Use bans revenue projects. Stay on Hobby only while pre-launch/staging.

> Because the data lives in Neon, when you later move to the VPS (Track B) you keep
> the same `DATABASE_URL` and just stop deploying to Vercel. Nothing to export.

---

## B. Long-term: Oracle Always Free VPS (lowest cost, $0)

**One-paragraph version:** Provision a 2 OCPU / 12 GB Ampere A1 Ubuntu instance,
open ports 80/443, install Docker + Compose, copy the `config/` folder, fill `.env`,
`docker compose up -d`. Caddy gets HTTPS automatically for `maavar.<domain>` and
`maayan.<domain>`; Postgres + both Next.js apps run as containers; a cron `pg_dump`
backs up to Oracle Object Storage (200 GB free). One VM, $0.

**Steps:**

1. **Instance:** OCI console → Compute → Instance → Ampere A1, Ubuntu 22.04/24.04,
   **2 OCPU / 12 GB** (the 2026 free cap). Add your SSH key. Note the public IP.
2. **Networking:** in the instance's VCN security list (and `ufw`), allow inbound
   **80** and **443**. Leave 5432 closed — Postgres is internal to compose only.
3. **DNS:** A-records `maavar` and `maayan` (and apex) → the public IP.
4. **Host setup:**
   ```bash
   sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin
   sudo usermod -aG docker $USER && newgrp docker
   ```
5. **Deploy:**
   ```bash
   # copy this docs/academy_deploy/config folder to the VPS, then:
   cd config
   cp .env.example .env && nano .env          # fill ROOT_DOMAIN + all secrets
   docker compose up -d --build
   docker compose exec maavar npx prisma migrate deploy
   docker compose exec maayan npx prisma migrate deploy
   ```
6. **Backups (cron):**
   ```bash
   0 3 * * * docker compose -f /home/ubuntu/config/docker-compose.yml exec -T \
     postgres pg_dump -U academy maavar | gzip > /backups/maavar_$(date +\%F).sql.gz
   # repeat for maayan; then sync /backups to Object Storage via oci-cli or rclone
   ```

**Cardcom:** set the recurring callback URL in the Cardcom dashboard to
`https://maavar.<domain>/api/webhooks/cardcom?secret=<CARDCOM_WEBHOOK_SECRET>`
(handler in `config/cardcom-webhook.ts`).

---

## C. When to graduate VPS → managed (no rewrite)

Same Docker image; change only `DATABASE_URL` and where the container runs.

1. Restore the latest `pg_dump` into **Neon** (or you were already on Neon from
   Track A — then skip this).
2. Move the app container to **Railway/Render** (`railway up` / connect repo), or
   keep it on the VPS and just point at Neon.
3. Put **Cloudflare (free)** in front for CDN + DDoS. DNS-only cutover, zero
   downtime.

Cost ladder: $0 (Oracle+self-host PG) → ~$10 (Railway) → ~$35–60 (Railway/Render +
Neon Launch) as students grow 0–50 → 50–200 → 200+.
