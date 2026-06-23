#!/usr/bin/env bash
# Bootstrap a fresh Oracle Cloud Ubuntu ARM VM for maayan. Idempotent — safe to re-run.
# Run from the repo root on the VM:   sudo bash deploy/bootstrap.sh
# See docs/cloud_deploy/03_DEPLOY_ORACLE.md for the full walkthrough.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$REPO_DIR/docker-compose.prod.yml"

log() { printf '\n\033[1;32m==>\033[0m %s\n' "$*"; }

if [[ $EUID -ne 0 ]]; then
  echo "run with sudo:  sudo bash deploy/bootstrap.sh" >&2
  exit 1
fi

log "Updating apt"
apt-get update -y

if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker (+ compose plugin)"
  curl -fsSL https://get.docker.com | sh
else
  log "Docker already installed — skipping"
fi

# Let the invoking (non-root) user run docker without sudo.
TARGET_USER="${SUDO_USER:-ubuntu}"
if id "$TARGET_USER" >/dev/null 2>&1; then
  usermod -aG docker "$TARGET_USER" || true
fi

if ! command -v tailscale >/dev/null 2>&1; then
  log "Installing Tailscale"
  curl -fsSL https://tailscale.com/install.sh | sh
else
  log "Tailscale already installed — skipping"
fi

log "Firewall (ufw): allow SSH only. The UI is published via Tailscale, NOT a public port."
if command -v ufw >/dev/null 2>&1; then
  ufw allow OpenSSH 2>/dev/null || ufw allow 22/tcp || true
  ufw --force enable || true
fi

log "Installing the 'maayan' CLI wrapper → /usr/local/bin/maayan"
install -m 0755 "$REPO_DIR/deploy/maayan" /usr/local/bin/maayan
sed -i "s|__COMPOSE_FILE__|$COMPOSE_FILE|g" /usr/local/bin/maayan

log "Bootstrap complete. Next steps:"
cat <<EOF
  1) sudo tailscale up                          # approve this node in your tailnet (browser)
  2) sudo tailscale cert && sudo tailscale funnel 8000   # publish the UI over public HTTPS
  3) cp "$REPO_DIR/.env.prod.example" "$REPO_DIR/.env"
     nano "$REPO_DIR/.env"                       # set OPENROUTER_API_KEY + SEED_ADMIN_PASSWORD
  4) (cd "$REPO_DIR" && docker compose -f docker-compose.prod.yml up -d --build)
  5) maayan ingest --all && tmux new -s idx 'maayan index'   # seed the corpus (CLI over SSH)
  6) open  https://<machine>.<your-tailnet>.ts.net   and log in as the seed admin

  Tip: log out/in (or run 'newgrp docker') so '$TARGET_USER' can use docker without sudo.
EOF
