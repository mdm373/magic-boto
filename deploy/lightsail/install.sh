#!/usr/bin/env bash
# One-time (idempotent) OS package setup for a magic-boto Lightsail host: clones the repo if it
# isn't already there (or pulls latest if it is, when running standalone — see below), then
# installs nginx, certbot (+ its nginx plugin), Docker, and the small utilities bootstrap.sh
# needs (jq, envsubst). Run as root, from inside an existing clone:
#
#   sudo ./deploy/lightsail/install.sh
#
# ...or fetch just this one file onto a totally fresh box and run it standalone — it clones the
# repo itself before doing anything else (this is what deploy.ps1 does under the hood):
#
#   sudo bash install.sh --repo-path ~/magic-boto --domain rundotgames.xyz --admin-ip 203.0.113.7
#
# --repo-url defaults to the public HTTPS clone URL, so no server-side credentials are needed for
# that step; pass an SSH remote instead if you fork this to a private repo (needs a deploy key
# already loaded on the box). Every argument other than --repo-url/--repo-path is forwarded to
# bootstrap.sh, which runs immediately after — so this is a genuine one-shot either way, not just
# from deploy.ps1.
#
# Kept as a separate script from bootstrap.sh because they change at different rates: this one is
# OS-package (and clone) setup you'll rarely touch again once the box is provisioned;
# bootstrap.sh is the per-deploy app work and takes --domain/--admin-ip every run.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi

REPO_URL="https://github.com/mdm373/magic-boto.git"
REPO_PATH="${HOME}/magic-boto"
BOOTSTRAP_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-url) REPO_URL="$2"; shift 2 ;;
    --repo-path) REPO_PATH="$2"; shift 2 ;;
    *) BOOTSTRAP_ARGS+=("$1"); shift ;;
  esac
done

apt-get update -qq

echo "==> git"
command -v git >/dev/null 2>&1 || apt-get install -y git

# Are we already running from inside a clone (the normal case: someone's own checkout) vs.
# standalone (this one file fetched onto a fresh box, e.g. scp'd by deploy.ps1)? Only the latter
# needs to actually manage a clone.
SELF_REPO_ROOT=""
if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
  SELF_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi

if [[ -n "$SELF_REPO_ROOT" && -d "${SELF_REPO_ROOT}/.git" && -f "${SELF_REPO_ROOT}/deploy/lightsail/bootstrap.sh" ]]; then
  REPO_ROOT="$SELF_REPO_ROOT"
else
  if [[ ! -d "${REPO_PATH}/.git" ]]; then
    echo "==> Cloning ${REPO_URL} into ${REPO_PATH}"
    git clone "$REPO_URL" "$REPO_PATH"
  else
    echo "==> ${REPO_PATH} already cloned — pulling latest"
    git -C "$REPO_PATH" pull
  fi
  REPO_ROOT="$REPO_PATH"
fi

echo "==> nginx"
command -v nginx >/dev/null 2>&1 || apt-get install -y nginx

echo "==> certbot"
command -v certbot >/dev/null 2>&1 || apt-get install -y certbot python3-certbot-nginx

echo "==> docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "Docker is installed but the compose (v2) plugin isn't — install docker-compose-plugin." >&2
  exit 1
fi

echo "==> jq, gettext-base (envsubst)"
command -v jq >/dev/null 2>&1 || apt-get install -y jq
command -v envsubst >/dev/null 2>&1 || apt-get install -y gettext-base

echo "==> Done. Repo at ${REPO_ROOT}"

if [[ ${#BOOTSTRAP_ARGS[@]} -gt 0 ]]; then
  echo "==> Handing off to bootstrap.sh ${BOOTSTRAP_ARGS[*]}"
  exec "${REPO_ROOT}/deploy/lightsail/bootstrap.sh" "${BOOTSTRAP_ARGS[@]}"
else
  echo "Run ${REPO_ROOT}/deploy/lightsail/bootstrap.sh next (or re-run this with --domain/--admin-ip to chain it)."
fi
