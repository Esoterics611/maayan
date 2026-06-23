# Phase 2/3 — Deploy to Oracle Always Free + Tailscale

> Stand maayan up on a free, always-on ARM VM: the **UI on a public URL with login**, the
> **CLI over SSH**, both hitting the **same backend** (one container, one Qdrant, one SQLite,
> one model cache). Do **Phase 1** ([02_USER_MANAGEMENT.md](02_USER_MANAGEMENT.md)) first —
> never expose a login-less UI.

Steps marked **(you)** are human-only (see [01_MANUAL_SETUP.md](01_MANUAL_SETUP.md)); the
rest are one script + a few commands we run together.

> **QA locally first.** Before provisioning anything, run the *same* stack on your laptop and
> exercise it with the **[Operator manual](06_OPERATOR_MANUAL.md)** (`make prod-up` → log in →
> watch logs). The only differences on the VM are `AUTH_COOKIE_SECURE=true` and that Tailscale
> provides the public HTTPS URL. Day-2 ops (logs, restart, backups) also live in the operator
> manual.

---

## 0. Prereqs
- Accounts from [01_MANUAL_SETUP.md](01_MANUAL_SETUP.md): Oracle, Tailscale, OpenRouter, SSH key.
- The deploy artifacts on this branch: `Dockerfile`, `docker-compose.prod.yml`,
  `.env.prod.example`, `deploy/bootstrap.sh`, `deploy/maayan` (CLI wrapper).

## 1. Create the VM **(you)**
1. Oracle console → **Compute → Instances → Create**.
2. Image: **Ubuntu 22.04/24.04 (aarch64)**. Shape: **Ampere A1 (VM.Standard.A1.Flex)** —
   start with **2 OCPU / 12 GB** (well within Always Free's 4/24; leaves headroom). A
   **1 OCPU / 6 GB** shape also runs `bge-m3` if capacity is tight.
3. Add your **SSH public key** (`~/.ssh/id_ed25519.pub`).
4. Networking: assign a public IPv4 (needed once, for the first SSH + Tailscale enrollment).
5. Create. Note the **public IP**.
   - **"Out of host capacity"** (common on ARM): retry, or switch the *availability domain*
     in the create form, or temporarily drop to 1 OCPU / 6 GB. As a last resort pick a less
     busy region (region is set at signup, so this is rare).

## 2. First SSH + bootstrap
```bash
ssh ubuntu@<PUBLIC_IP>            # 'ubuntu' is the default user on Oracle Ubuntu images
# on the VM:
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/Esoterics611/maayan.git /opt/maayan
cd /opt/maayan && git checkout cloud-deploy     # until merged to main
sudo bash deploy/bootstrap.sh
```
`bootstrap.sh` is idempotent and: installs Docker + the compose plugin + Tailscale; runs
`ufw` so **only SSH is open publicly** (8000 is never exposed to the internet); installs the
`maayan` CLI wrapper; and prints the next steps. It does **not** start anything that needs
secrets yet.

## 3. Join Tailscale + turn on the public URL **(you approve in browser)**
```bash
sudo tailscale up                 # prints a URL — open it, approve the node in your tailnet
sudo tailscale cert               # (one-time) provision the HTTPS cert for this node
sudo tailscale funnel 8000        # publish the UI publicly over HTTPS on *.ts.net
tailscale status                  # note this node's MagicDNS name
```
Your public URL is `https://<machine>.<your-tailnet>.ts.net`. Funnel terminates HTTPS and
forwards to the container on `localhost:8000`; **no firewall port is opened** for it.

## 4. Configure secrets + start
```bash
cd /opt/maayan
cp .env.prod.example .env
nano .env     # set OPENROUTER_API_KEY, AUTH_ENABLED=true, SEED_ADMIN_USERNAME/PASSWORD
make prod-up  # builds the image (first build is slow: torch + bge-m3 layers) and starts qdrant + app
```
On first start the app seeds the admin from `SEED_ADMIN_*`. Open the Funnel URL → log in as
that admin → **create your real users** in the Users panel → change the seed password (then
you can blank `SEED_ADMIN_*` in `.env`).

## 5. Seed the corpus (CLI over SSH — same backend)
```bash
# the wrapper proxies into the running app container (shares Qdrant + SQLite + model cache):
maayan ingest --all
tmux new -s index 'maayan index'   # first index downloads bge-m3 (~2.3 GB) — run detached
# ... reattach with `tmux attach -t index`; detach with Ctrl-b d
maayan stats                       # confirm chunks landed
maayan ask "מהי נפש הבהמית"        # smoke-test generation end-to-end
```
The browser UI and these SSH commands hit the **identical** backend — that's the whole point.

## 6. Day-2 operations
```bash
make prod-logs        # tail app + qdrant
make prod-down        # stop (data persists in the named volumes)
make prod-up          # restart
git pull && make prod-up   # deploy an update (rebuilds the image)
```

### Backups (do this once you have real knowledge in it)
The entire knowledge layer is **one SQLite file** + the **Qdrant volume**:
```bash
# SQLite (contributions, threads, users, etc.) — the irreplaceable part:
docker compose -f docker-compose.prod.yml cp app:/app/data/maayan.sqlite3 ./backup-$(date +%F).sqlite3
# Qdrant vectors are re-derivable from SQLite via `maayan index --rebuild`, but you can also
# snapshot the volume. Copy backups off the VM (scp) periodically.
```
Automated off-VM backups are a Phase-4 item ([04_HOSTING_MIGRATION.md](04_HOSTING_MIGRATION.md)).

---

## Troubleshooting
- **Build OOM** on a 6 GB shape: build with one job / add swap
  (`sudo fallocate -l 4G /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`), or
  build the image on a 12 GB shape.
- **First `index` is slow / looks hung:** it's downloading `bge-m3`. Watch `maayan` logs or
  `du -sh` the HF cache volume. Always run it under `tmux`.
- **Qdrant unhealthy:** `make prod-logs`; ensure the `app` env has
  `QDRANT_URL=http://qdrant:6333` (service DNS, not localhost).
- **Funnel shows nothing:** confirm `tailscale funnel status`, that the container is up
  (`make prod-logs`), and that Funnel is enabled for your tailnet in the admin console.
- **Locked out of the UI:** re-seed/reset an admin over SSH with
  `maayan user passwd <username>` or `maayan user create-admin --username <name>`.
