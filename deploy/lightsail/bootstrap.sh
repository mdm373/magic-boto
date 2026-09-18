#!/usr/bin/env bash
# Bootstraps (or re-syncs) magic-boto on this host for a given root domain. Run ON THE SERVER,
# from a clone of this repo, as root, after deploy/lightsail/install.sh has set up certbot/docker:
#
#   sudo ./deploy/lightsail/bootstrap.sh --domain rundotgames.xyz --admin-ip 203.0.113.7
#
# Or run deploy/lightsail/deploy.ps1 from your dev machine, which does `git pull` + install.sh +
# this over SSH in one shot.
#
# nginx itself runs as a compose service (docker-compose.prod.yml, deploy/lightsail/nginx/), not
# natively — only certbot (the ACME client) runs on the host, using the webroot method rather
# than its nginx plugin, since there's no system nginx for that plugin to manage.
#
# Safe to re-run: every step here is idempotent (.env upserts, `docker compose up`, Keycloak
# client secret checks, certbot). Bash, not PowerShell, because this runs on the Linux deploy
# target, not the Windows dev machine (AGENTS.md's platform note is about the repo's own dev
# tooling, not servers it gets deployed to).
set -euo pipefail

DOMAIN=""
ADMIN_ALLOWED_IP=""
POSTGRES_PUBLIC_PORT="55432"
CERTBOT_EMAIL=""
ENV_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --admin-ip) ADMIN_ALLOWED_IP="$2"; shift 2 ;;
    --postgres-port) POSTGRES_PUBLIC_PORT="$2"; shift 2 ;;
    --certbot-email) CERTBOT_EMAIL="$2"; shift 2 ;;
    --env-file) ENV_FILE="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$DOMAIN" || -z "$ADMIN_ALLOWED_IP" ]]; then
  cat >&2 <<'USAGE'
Usage: bootstrap.sh --domain <root domain> --admin-ip <ip or CIDR>
                     [--postgres-port N] [--certbot-email you@example.com] [--env-file path]

Example: --domain rundotgames.xyz derives magicboto-mcp.rundotgames.xyz,
magicboto-keycloak.rundotgames.xyz, magicboto-keycloak-admin.rundotgames.xyz, and
magicboto-flower.rundotgames.xyz. All four need DNS A records pointing at this host before
certbot can issue for them.
USAGE
  exit 1
fi

if [[ $EUID -ne 0 ]]; then
  echo "Run as root (sudo) — writes /etc/letsencrypt and /var/www/certbot." >&2
  exit 1
fi

MCP_DOMAIN="magicboto-mcp.${DOMAIN}"
KEYCLOAK_DOMAIN="magicboto-keycloak.${DOMAIN}"
KEYCLOAK_ADMIN_DOMAIN="magicboto-keycloak-admin.${DOMAIN}"
FLOWER_DOMAIN="magicboto-flower.${DOMAIN}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

echo "==> Repo:    $REPO_ROOT"
echo "==> Domains: $MCP_DOMAIN, $KEYCLOAK_DOMAIN, $KEYCLOAK_ADMIN_DOMAIN, $FLOWER_DOMAIN"
echo "==> Admin IP: $ADMIN_ALLOWED_IP"

# ---- prerequisite checks -----------------------------------------------------------------
# install.sh owns actually installing these; this just fails fast with a clear pointer
# if it hasn't been run (or the box has drifted). nginx itself isn't checked here — it's a
# compose service (docker-compose.prod.yml), not a host package.
for cmd in docker certbot jq envsubst openssl; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing '$cmd'. Run deploy/lightsail/install.sh first." >&2
    exit 1
  fi
done
docker compose version >/dev/null 2>&1 || { echo "docker compose (v2 plugin) not found. Run deploy/lightsail/install.sh first." >&2; exit 1; }

# ---- .env ---------------------------------------------------------------------------------
# Never falls back to .env.example's defaults — those are blank (ANTHROPIC_API_KEY) or
# well-known (POSTGRES_PASSWORD=magicboto, KEYCLOAK_ADMIN_PASSWORD=admin), and Postgres/
# Keycloak's DB only apply their password env vars when the data volume is first initialized, so
# letting `docker compose up` run even once on defaults means those defaults are what the running
# containers keep even after .env is fixed, until the volume is dropped or .env is made to match.
# --env-file (deploy.ps1 passes your local .env here) is copied over unconditionally, since it's
# the actual source of truth; without it, an existing .env here is used as-is (the direct-on-
# -server path); with neither, this stops rather than inventing one.
if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "--env-file '${ENV_FILE}' not found." >&2
    exit 1
  fi
  cp "$ENV_FILE" .env
elif [[ ! -f .env ]]; then
  echo "No .env here and no --env-file given. Copy a real .env (with actual secrets, not .env.example's defaults) into place first, or run via deploy.ps1, which pushes your local one automatically." >&2
  exit 1
fi

# Self-heal CRLF line endings — a .env saved by a Windows editor breaks `source` below
# (`$'\r': command not found`).
sed -i 's/\r$//' .env

set_env_var() {
  local key="$1" value="$2"
  if grep -qE "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    echo "${key}=${value}" >> .env
  fi
}

set_env_var MCP_DOMAIN "$MCP_DOMAIN"
set_env_var KEYCLOAK_DOMAIN "$KEYCLOAK_DOMAIN"
set_env_var KEYCLOAK_ADMIN_DOMAIN "$KEYCLOAK_ADMIN_DOMAIN"
set_env_var FLOWER_DOMAIN "$FLOWER_DOMAIN"
set_env_var ADMIN_ALLOWED_IP "$ADMIN_ALLOWED_IP"
set_env_var POSTGRES_PUBLIC_PORT "$POSTGRES_PUBLIC_PORT"
set_env_var KEYCLOAK_ISSUER_URL "https://${KEYCLOAK_DOMAIN}/realms/magic-boto"
set_env_var TOOLS_MCP_RESOURCE_SERVER_URL "https://${MCP_DOMAIN}"

set -a
# shellcheck disable=SC1091
source .env
set +a

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

# ---- nginx: placeholder cert --------------------------------------------------------------
# nginx (a compose service — see deploy/lightsail/nginx/) won't even start with its
# ssl_certificate directives pointing at files that don't exist, but certbot's webroot method
# needs nginx already up and serving port 80 to complete the HTTP-01 challenge. Standard fix:
# drop a temporary self-signed cert at the exact path the template references before nginx's
# first start, then certbot (below, after the stack is up) overwrites it in place with the real
# one — same filenames, so nginx just needs a reload afterward, not a restart. No-op once a real
# cert exists (subsequent runs skip straight past this).
CERT_DIR="/etc/letsencrypt/live/magicboto"
if [[ ! -f "${CERT_DIR}/fullchain.pem" ]]; then
  echo "==> No cert yet — dropping a temporary self-signed one so nginx can start"
  mkdir -p "$CERT_DIR"
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout "${CERT_DIR}/privkey.pem" -out "${CERT_DIR}/fullchain.pem" \
    -subj "/CN=${MCP_DOMAIN}" >/dev/null 2>&1
fi
mkdir -p /var/www/certbot

# ---- app stack ----------------------------------------------------------------------------
# tools_api, mcp_inspector, and keycloak_postgres deliberately aren't in this list:
#  - tools_api: nothing routes to it (nginx only reaches tools_mcp and keycloak_public_proxy) and
#    nothing internally calls it either (tools_mcp never does — same DB, no HTTP dependency
#    between them), so on a memory-constrained instance it's a full extra Python process for
#    nothing.
#  - mcp_inspector: debug-only; use an SSH tunnel when you need it.
#  - keycloak_postgres: docker-compose.prod.yml points Keycloak at a database inside the shared
#    `postgres` instance instead (see deploy/lightsail/postgres/init-keycloak-db.sh) — a whole
#    second Postgres process is the single biggest memory cost this avoids. Its depends_on is
#    overridden there too, so Compose won't auto-start it to satisfy the base file's dependency.
# All three still run locally via plain `docker compose up` (no -f docker-compose.prod.yml),
# since local dev isn't memory-constrained and docker-compose.yml is untouched.
PROD_SERVICES=(postgres redis tools_mcp tools_celery_worker flower keycloak keycloak_public_proxy nginx)

echo "==> Bringing up the compose stack"
"${COMPOSE[@]}" up -d --build "${PROD_SERVICES[@]}"

echo "==> Waiting for postgres"
until "${COMPOSE[@]}" exec -T postgres pg_isready -U "${POSTGRES_USER:-magicboto}" >/dev/null 2>&1; do
  sleep 2
done

echo "==> Running migrations"
# Via tools_mcp, not tools_api — same image/code, and tools_mcp is the one actually running here.
"${COMPOSE[@]}" exec -T tools_mcp uv run invoke migrate

# ---- keycloak: realm client secrets ----------------------------------------------------------
# keycloak/realm-import/realm-export.json ships client "secret" fields masked as "**********"
# (Keycloak's own export behavior) — import sets that literal string as the client's actual
# secret, which is predictable and useless as a credential. Nothing in tools_api/tools_mcp
# consumes a client secret itself (the MCP server only verifies bearer tokens — see
# tools_api/app/mcp_tooling/auth/); the only place a secret is needed is pasted into Claude.ai's
# own "Add custom connector" form for the magic-boto-claude-connector client. So: check each
# client's live secret against Keycloak, and regenerate via the admin API only if it's still the
# placeholder — never on a client that already has a real one, so re-running this script doesn't
# rotate (and break) a secret you've already pasted into Claude.
KC_BASE="http://127.0.0.1:${KEYCLOAK_LOCAL_PORT:-8180}"
KC_REALM="magic-boto"
SECRETS_FILE="${REPO_ROOT}/.keycloak-client-secrets"

echo "==> Waiting for Keycloak"
until curl -sf "${KC_BASE}/realms/master/.well-known/openid-configuration" >/dev/null 2>&1; do
  sleep 3
done

echo "==> Checking realm '${KC_REALM}' client secrets"
KC_ADMIN_TOKEN=$(curl -sf \
  -d "client_id=admin-cli" \
  -d "username=${KEYCLOAK_ADMIN:-admin}" \
  -d "password=${KEYCLOAK_ADMIN_PASSWORD:-admin}" \
  -d "grant_type=password" \
  "${KC_BASE}/realms/master/protocol/openid-connect/token" | jq -r '.access_token // empty')

if [[ -z "$KC_ADMIN_TOKEN" ]]; then
  echo "Could not get a Keycloak admin token — check KEYCLOAK_ADMIN/KEYCLOAK_ADMIN_PASSWORD in .env." >&2
  exit 1
fi

: > "$SECRETS_FILE"
chmod 600 "$SECRETS_FILE"

rotate_client_secret_if_placeholder() {
  local client_id="$1"
  local kc_id current
  kc_id=$(curl -sf -H "Authorization: Bearer ${KC_ADMIN_TOKEN}" \
    "${KC_BASE}/admin/realms/${KC_REALM}/clients?clientId=${client_id}" | jq -r '.[0].id // empty')
  if [[ -z "$kc_id" ]]; then
    echo "    '${client_id}' not found in realm '${KC_REALM}' (no realm-export.json imported yet?) — skipping"
    return
  fi
  current=$(curl -sf -H "Authorization: Bearer ${KC_ADMIN_TOKEN}" \
    "${KC_BASE}/admin/realms/${KC_REALM}/clients/${kc_id}/client-secret" | jq -r '.value // empty')
  if [[ -z "$current" || "$current" == "**********" ]]; then
    echo "    Regenerating secret for ${client_id} (exported value was the placeholder)"
    current=$(curl -sf -X POST -H "Authorization: Bearer ${KC_ADMIN_TOKEN}" \
      "${KC_BASE}/admin/realms/${KC_REALM}/clients/${kc_id}/client-secret" | jq -r '.value')
  else
    echo "    ${client_id} already has a real secret — leaving it alone"
  fi
  echo "${client_id}=${current}" >> "$SECRETS_FILE"
}

rotate_client_secret_if_placeholder "magic-boto-claude-connector"
rotate_client_secret_if_placeholder "magic-boto-tools-api"

# ---- certbot --------------------------------------------------------------------------------
# Webroot, not the nginx plugin — there's no system nginx for that plugin to edit/reload, it's a
# compose service. --cert-name magicboto pins the live directory to the same path the placeholder
# cert used above (and that the nginx template references), so this overwrites it in place rather
# than certbot picking a name from whichever -d happens to be first. The deploy-hook (saved into
# certbot's renewal config, so this also covers the systemd-timer-driven auto-renewals weeks from
# now, not just this run) reloads nginx inside its container — graceful, no downtime, and no
# `systemctl` involved since nginx isn't a system service here.
echo "==> Requesting/renewing certificate (webroot)"
CERTBOT_ARGS=(certonly --webroot -w /var/www/certbot --cert-name magicboto --non-interactive --agree-tos
  -d "$MCP_DOMAIN" -d "$KEYCLOAK_DOMAIN" -d "$KEYCLOAK_ADMIN_DOMAIN" -d "$FLOWER_DOMAIN"
  --deploy-hook "docker compose -f ${REPO_ROOT}/docker-compose.yml -f ${REPO_ROOT}/docker-compose.prod.yml exec nginx nginx -s reload")
if [[ -n "$CERTBOT_EMAIL" ]]; then
  CERTBOT_ARGS+=(-m "$CERTBOT_EMAIL")
else
  CERTBOT_ARGS+=(--register-unsafely-without-email)
fi
certbot "${CERTBOT_ARGS[@]}"

echo
echo "==> Done."
echo "MCP:               https://${MCP_DOMAIN}/mcp"
echo "Keycloak (public): https://${KEYCLOAK_DOMAIN}"
echo "Keycloak (admin):  https://${KEYCLOAK_ADMIN_DOMAIN}  (restricted to ${ADMIN_ALLOWED_IP})"
echo "Flower:            https://${FLOWER_DOMAIN}  (restricted to ${ADMIN_ALLOWED_IP})"
echo "Postgres:          psql -h ${DOMAIN} -p ${POSTGRES_PUBLIC_PORT} -d magicboto (or -d keycloak)  (restricted to ${ADMIN_ALLOWED_IP})"
echo
echo "Open these once in the Lightsail firewall, then never touch it again: 443, ${POSTGRES_PUBLIC_PORT}"
echo
echo "Keycloak client secrets: ${SECRETS_FILE} (chmod 600, gitignored)"
echo "  magic-boto-claude-connector's secret goes into Claude.ai's own 'Add custom connector' form"
echo "  (Client ID magic-boto-claude-connector, issuer https://${KEYCLOAK_DOMAIN}/realms/magic-boto)."
echo "  magic-boto-tools-api's isn't used by this app today — kept for the record."
