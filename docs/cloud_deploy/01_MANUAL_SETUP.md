# Companion: accounts & manual work — what *you* need to do

> This is the **human-only** checklist. Everything here needs your signup, your card, your
> browser, or your password — I can't do it for you. Each item says **when** you need it,
> **why**, and **exactly** what to do. Nothing else in the deploy is a surprise.

You don't need to do all of this today. Do **Section A now** (5 min, unblocks the public
URL later); do the rest at **Phase 2** ([03_DEPLOY_ORACLE.md](03_DEPLOY_ORACLE.md)).

Legend: 💳 needs a card (but **stays free**) · 🔑 produces a secret · ⏱️ rough time.

---

## A. Accounts to create (do these first)

### A1. Oracle Cloud — the free VM 💳 ⏱️ ~20 min
- **Why:** the always-free ARM VM that runs everything. Card is for identity verification
  only; **Always Free resources are never charged**. (Set your account to *Always Free* and
  don't manually upgrade and you cannot be billed.)
- **Do:**
  1. Sign up at <https://www.oracle.com/cloud/free/>. Pick a **home region** near you (this
     is permanent; pick well). Verify email + card.
  2. That's all for now — we create the actual VM together in Phase 2, because ARM capacity
     can require retrying across availability domains and it's easier to do live.
- **Heads-up:** "Out of host capacity" on the ARM shape is common in popular regions. Plan B
  is in the runbook (smaller shape / different AD / retry); a 1-OCPU/6-GB ARM still runs
  `bge-m3`.

### A2. Tailscale — private mesh + the public URL 🔑 ⏱️ ~10 min
- **Why:** gives the VM a private address for admin **and** a free public HTTPS URL via
  **Funnel** (`https://<machine>.<your-tailnet>.ts.net`) — no domain, no open ports.
- **Do:**
  1. Sign up at <https://tailscale.com/> (free Personal plan; Google/GitHub/Microsoft login
     is fine).
  2. Install the Tailscale client on **your laptop and/or phone** (the devices you'll use to
     reach the UI and SSH in).
  3. In the admin console (<https://login.tailscale.com/admin>), confirm **HTTPS
     certificates** and **Funnel** are available (both are on by default for Personal; we
     enable Funnel on the node in Phase 2).
- **Produces:** nothing to copy now — in Phase 2 you'll run `tailscale up` on the VM and
  approve it in this console.

### A3. OpenRouter — generation 🔑 💳 ⏱️ ~10 min
- **Why:** the one cloud call maayan makes (composing the final grounded answer). Free models
  exist, but a few cents of credit unlocks the better Hebrew-capable models.
- **Do:**
  1. Sign up at <https://openrouter.ai/>.
  2. Create an API key: **Keys → Create Key**. **Copy it now** — you can't see it again.
  3. (Recommended) Add a small credit balance and **set a monthly spend limit** in
     **Settings → Limits** — this is your guardrail against a runaway public URL.
- **Produces:** `OPENROUTER_API_KEY` (starts `sk-or-...`). You'll paste it into the VM's
  `.env` in Phase 2. **Never** commit it.

---

## B. On your laptop (you'll already have these)

### B1. An SSH key pair 🔑 ⏱️ ~2 min
- **Why:** how you log into the VM (and how Oracle attaches access at create time).
- **Do (only if you don't already have `~/.ssh/id_ed25519.pub`):**
  ```bash
  ssh-keygen -t ed25519 -C "maayan-oracle"
  cat ~/.ssh/id_ed25519.pub   # this is the PUBLIC key you paste into Oracle
  ```
- **Produces:** a **public** key you paste into the Oracle VM create form. The **private**
  key never leaves your laptop.

---

## C. Secrets you'll set on the VM (Phase 2, in `.env` — never committed)

| Variable | From | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | A3 | the only real secret; spend guardrail set in A3 |
| `AUTH_ENABLED=true` | — | turns on the login wall (built in Phase 1) |
| `SEED_ADMIN_USERNAME` / `SEED_ADMIN_PASSWORD` | you choose | first admin account, created once on boot; **change the password after first login**, then you can blank these |
| `UI_HOST=0.0.0.0` | — | bind for the container (kept off the public net by Funnel/firewall) |
| `QDRANT_URL=http://qdrant:6333` | — | service DNS inside compose |

> The first-admin seed (`SEED_ADMIN_*`) is the **only** account that exists at launch. You
> log in as that admin and create everyone else from the **Users** panel. Treat the seed
> password like a master key until you've rotated it.

---

## D. Decisions still yours to make later (not blocking)

- **Custom domain?** Funnel's `*.ts.net` URL is free and works for sharing now. If you want a
  branded URL (`ask.maayan.org`) for fundraising, buy a domain at any registrar and follow
  the domain path in [04_HOSTING_MIGRATION.md](04_HOSTING_MIGRATION.md) (Caddy + Let's
  Encrypt). 💳 (~$10–15/yr, the only non-free thing here, and optional.)
- **When to upgrade off Always Free** — only when you want local generation/GPU or more
  scale; covered in [04_HOSTING_MIGRATION.md](04_HOSTING_MIGRATION.md). Same Oracle account.

---

## Quick checklist (tick as you go)

- [ ] A1 Oracle Cloud account (Always Free), home region chosen
- [ ] A2 Tailscale account + client on your laptop/phone
- [ ] A3 OpenRouter account + API key copied + monthly spend limit set
- [ ] B1 SSH key pair on your laptop
- [ ] (Phase 2) VM created, `bootstrap.sh` run, `tailscale up` approved, Funnel on
- [ ] (Phase 2) `.env` filled with the secrets in Section C
- [ ] First admin login works → create your real users → rotate the seed password
