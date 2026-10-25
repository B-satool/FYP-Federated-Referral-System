#!/usr/bin/env bash
# One-command deployment on a fresh Ubuntu server (e.g. Oracle Cloud Always Free).
# Run from the repository folder on the server:   bash scripts/deploy-server.sh
# Optional: SITE_HOST=my.domain.example bash scripts/deploy-server.sh   (default: <public-ip>.sslip.io)
# Re-running is safe: it keeps the existing .env and data, rebuilds and restarts.
set -euo pipefail
cd "$(dirname "$0")/.."

say() { printf '\n==> %s\n' "$*"; }

if ! command -v docker >/dev/null 2>&1; then
  say "Installing Docker"
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
fi
DOCKER="docker"; docker info >/dev/null 2>&1 || DOCKER="sudo docker"

say "Opening ports 80 and 443 in the server firewall"
for port in 80 443; do
  sudo iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 1 -p tcp --dport "$port" -j ACCEPT
done
if command -v netfilter-persistent >/dev/null 2>&1; then sudo netfilter-persistent save >/dev/null || true; fi

if [ ! -f .env ]; then
  say "Creating .env with strong random secrets"
  ip="$(curl -fsS https://api.ipify.org)"
  host="${SITE_HOST:-${ip//./-}.sslip.io}"
  rnd() { openssl rand -hex 24; }
  cat > .env <<EOF
SITE_HOST=${host}
POSTGRES_SUPERUSER_PASSWORD=$(rnd)
CENTRAL_DB_PASSWORD=$(rnd)
DRALI_DB_PASSWORD=$(rnd)
CHUGHTAI_DB_PASSWORD=$(rnd)
ZIAUDDIN_DB_PASSWORD=$(rnd)
AKUH_DB_PASSWORD=$(rnd)
KEYCLOAK_DB_PASSWORD=$(rnd)
KEYCLOAK_ADMIN_PASSWORD=$(rnd)
# Password for the synthetic demo accounts (change for anything beyond a supervised demo)
DEMO_USER_PASSWORD=${DEMO_USER_PASSWORD:-demo1234}
CENTRAL_CLIENT_SECRET=$(rnd)
DRALI_CLIENT_SECRET=$(rnd)
CHUGHTAI_CLIENT_SECRET=$(rnd)
ZIAUDDIN_CLIENT_SECRET=$(rnd)
AKUH_CLIENT_SECRET=$(rnd)
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=
LLM_MODEL=claude-opus-5-5
EXTRACTION_MODE=auto
DOCUMENT_RETENTION_DAYS=365
EOF
  chmod 600 .env
fi
host="$(grep '^SITE_HOST=' .env | cut -d= -f2)"

say "Building and starting (first run takes 10-15 minutes)"
COMPOSE="$DOCKER compose -f docker-compose.yml -f docker-compose.prod.yml"
$COMPOSE up -d --build

say "Waiting for services to become healthy"
for _ in $(seq 1 90); do
  if ! $COMPOSE ps --format '{{.Health}}' | grep -Eq 'starting|unhealthy'; then break; fi
  sleep 5
done
$COMPOSE ps

if [ "$($COMPOSE exec -T postgres psql -U postgres -d central_db -tAc 'select count(*) from patient_links' 2>/dev/null || echo 0)" = "0" ]; then
  say "Loading synthetic demo data"
  for svc in drali chughtai ziauddin akuh central; do $COMPOSE exec -T "$svc" python -m app.seed --reset --yes; done
fi

say "Done. Open:  https://${host}"
echo "Keycloak admin console: https://${host}/auth/admin  (user: admin, password: KEYCLOAK_ADMIN_PASSWORD in .env)"
echo "If the page does not load within a few minutes, check the cloud firewall allows TCP 80 and 443 (see docs/deploy-cloud.md)."
