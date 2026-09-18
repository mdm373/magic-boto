# Deploying to Lightsail

`deploy\lightsail\deploy.ps1` is the one-shot entry point — run it from your Windows dev machine,
in the repo root:

```powershell
.\deploy\lightsail\deploy.ps1 -SshHost rundotgames -Domain rundotgames.xyz -AdminIp 203.0.113.7
```

It reads your local `.env` (repo root — real secrets included) and fails immediately, before
touching the server at all, if that file doesn't exist. Otherwise it copies both `install.sh` and
`.env` to `-SshHost` via `scp` and runs `install.sh` there with `sudo`. `install.sh` is
self-contained: it clones the repo to `-RemotePath` (default `~/magic-boto`) if it isn't there
yet, or `git pull`s it if it is, installs whatever OS packages are missing (certbot, Docker, `jq`,
`envsubst`, `openssl` — **not** nginx; see below), then hands off to `bootstrap.sh` from that same
clone, passing along the copied `.env`. So this works on a genuinely fresh box — nothing needs to
be pre-cloned, nothing needs to be manually edited on the server. Re-running it after a code
change, a secrets change, an IP change, or a fresh `keycloak/realm-import/realm-export.json`
export is the same one command — everything downstream is idempotent, and your local `.env` stays
the single source of truth (each run overwrites the server's copy with it, then layers the
deploy-topology values on top — see below).

## Layout

- **`deploy/lightsail/install.sh`** — clones/pulls the repo (when run standalone — see below),
  installs OS packages (only what's missing), then execs `bootstrap.sh` with whatever args it
  wasn't itself (`--repo-url`, `--repo-path` are consumed here; everything else is forwarded).
- **`deploy/lightsail/bootstrap.sh`** — the actual per-deploy work: `.env` upserts, a temporary
  self-signed cert if none exists yet, `docker compose up` with the prod overlay, migrations,
  Keycloak realm client-secret checks, certbot.
- **`deploy/lightsail/nginx/`** — `templates/nginx.conf.template` (rendered by `render-and-run.sh`
  via `envsubst` at container start) and the entrypoint script itself. This is ingress — see
  below.
- **`deploy/lightsail/postgres/init-keycloak-db.sh`** — creates Keycloak's database inside the
  shared Postgres instance on first init (see "Fitting a 512MB instance").
- **`deploy/lightsail/deploy.ps1`** — the Windows-side one-shot wrapper described above.

You can skip `deploy.ps1` and run directly on the server instead — either from inside an existing
clone (`sudo ./deploy/lightsail/install.sh --domain ... --admin-ip ...`, which then just installs
packages and hands off, no cloning involved since it detects it's already inside one), or as a
single fetched file on a fresh box (`sudo bash install.sh --repo-path ~/magic-boto --domain ...
--admin-ip ...`, which clones first). Same end result either way. Without `deploy.ps1` there's no
automatic `.env` push, though: either place a real `.env` in the repo yourself first, or pass
`--env-file /path/to/your.env`.

## nginx runs in Docker, not natively

Ingress is the `nginx` service in `docker-compose.prod.yml`, not an apt-installed system nginx —
there's no reason to install and maintain a native nginx just to proxy into a stack that's
otherwise entirely Docker, and it keeps `install.sh` simpler (one less package whose config lives
outside the repo). It reaches every backend by compose service name over the Docker network
(`tools_mcp`, `keycloak`, `keycloak_public_proxy`, `flower`, `postgres`) rather than via the
127.0.0.1-bound host ports in `docker-compose.yml` (those stay published for local host-side
convenience — DBeaver, MCP Inspector, etc. — orthogonal to this).

**Certs are still managed by a native certbot**, using the webroot method (`--webroot`, not the
`--nginx` plugin — there's no system nginx for that plugin to edit) with `--deploy-hook` reloading
the dockerized nginx (`docker compose exec nginx nginx -s reload`) instead of `systemctl`. That
hook is saved into certbot's renewal config, so it also covers the systemd-timer-driven
auto-renewals weeks from now, not just the run that issues the cert.

One bootstrapping wrinkle worth knowing about: nginx won't start at all with its
`ssl_certificate` directives pointing at files that don't exist, but certbot's webroot method
needs nginx already up and serving port 80 to complete the HTTP-01 challenge. `bootstrap.sh`
breaks that cycle by dropping a temporary self-signed cert at the same path
(`/etc/letsencrypt/live/magicboto/`) before nginx's first start; certbot then overwrites those
same files with the real cert (`--cert-name magicboto` pins the path) and the deploy-hook reloads
nginx to pick it up. This step is a no-op once a real cert exists.

## What it assumes about the instance

A plain Debian Lightsail instance (built against Debian 13/trixie; nothing here is
version-specific beyond what `apt`/`get.docker.com` support). `-RepoUrl` defaults to the public
HTTPS clone URL, so the clone/pull step needs no credentials on the box; only override it with an
SSH remote if you fork this to a private repo (then a deploy key needs to already be loaded
there).

One thing worth checking on a very recent Debian release: `install.sh` installs Docker via
`get.docker.com`, which needs Docker's own apt repo to have a component published for that exact
codename. Docker sometimes lags a release or two behind the newest Debian codename landing in
their repo — if `install.sh` fails at the Docker step, that's the first thing to check
(`curl -fsSL https://get.docker.com | sh` run by hand will say so directly). certbot comes from
Debian's own repo, so it's not at risk here the same way.

**First time only**: DNS — A records for `magicboto-mcp.<domain>`, `magicboto-keycloak.<domain>`,
`magicboto-keycloak-admin.<domain>`, and `magicboto-flower.<domain>` pointing at the instance —
needs to be in place before certbot can issue for them. And a real local `.env`, since that's
what gets pushed:

```powershell
Copy-Item .env.example .env
# fill in: POSTGRES_PASSWORD, KEYCLOAK_ADMIN_PASSWORD, KEYCLOAK_DB_PASSWORD, ANTHROPIC_API_KEY, etc.
.\deploy\lightsail\deploy.ps1 -SshHost rundotgames -Domain rundotgames.xyz -AdminIp 203.0.113.7
```

`deploy.ps1` checks for this file before doing anything else — no server round-trip just to find
out secrets aren't set. `bootstrap.sh` (whether reached via `deploy.ps1`'s `--env-file`, or run
directly on the server against a `.env` you placed there yourself) never falls back to
`.env.example`'s defaults (blank `ANTHROPIC_API_KEY`, `POSTGRES_PASSWORD=magicboto`,
`KEYCLOAK_ADMIN_PASSWORD=admin`) — it fails outright if neither is available. That matters beyond
just "secrets should be real": Postgres/Keycloak's DB only apply their password env vars when the
data volume is first initialized, so a `docker compose up` that ran even once on placeholder
values would keep those credentials baked into the volume regardless of what `.env` says
afterward, until the volume is dropped or `.env` is put back to match. Refusing to proceed
without real secrets avoids ever getting into that state.

## Subdomains

Every HTTP surface rides nginx's port 443 (routed by `server_name`/SNI) — no extra HTTP ports to
open. Only Postgres needs a dedicated port, since raw TCP can't be routed by hostname.

| Subdomain | Backend | Access |
|---|---|---|
| `magicboto-mcp.<domain>` | `tools_mcp` :8765 | public |
| `magicboto-keycloak.<domain>` | `keycloak_public_proxy` :8181 | public |
| `magicboto-keycloak-admin.<domain>` | `keycloak` :8180 | `-AdminIp` only |
| `magicboto-flower.<domain>` | `flower` :5555 | `-AdminIp` only |
| Postgres, `-PostgresPort` (default 55432) | `postgres` :5432 (both app + Keycloak DBs) | `-AdminIp` only |

MCP Inspector isn't routed publicly — it stays loopback-only; use an SSH tunnel
(`ssh -L 6274:localhost:6274 <host>`) when you need it.

**Access control lives entirely in nginx**, via `allow <ip>; deny all;` on the admin
server/stream blocks — open 443 and the Postgres port in the Lightsail firewall once and never
touch it again. Changing who's allowed in is `-AdminIp` on the next `deploy.ps1` run — it's baked
into the `nginx` container's environment, so a normal `docker compose up -d` (which `bootstrap.sh`
always does) recreates it with the new value; no separate reload step needed for that.

## Fitting a 512MB instance

This started life on a 512MB Lightsail instance, which isn't enough for this stack at any
service's stock settings — the tuning below is a documented concession, not the default posture
you'd want on a box with real headroom:

- **`tools_api` and `mcp_inspector` don't run in prod at all** (`bootstrap.sh`'s explicit service
  list omits them). Nothing routes to `tools_api` and nothing calls it internally either — it's a
  full Python process for zero benefit here. `mcp_inspector` is debug-only.
- **Keycloak shares the app's Postgres instance** instead of running its own — see
  `deploy/lightsail/postgres/init-keycloak-db.sh` and `docker-compose.prod.yml`. A second full
  Postgres process was the single biggest avoidable cost after Keycloak's own JVM.
- **Both Postgres and Keycloak are tuned down explicitly** (`shared_buffers`, `max_connections`,
  and an explicit `-Xmx` on Keycloak's JVM) rather than left on defaults sized for a box with
  actual RAM to spare.
- **Every prod service has a `mem_limit`**, including `nginx` itself (a lightweight addition —
  Alpine nginx is a handful of MB) — a backstop, not the primary fix: if the tuning above is still
  wrong somewhere, one container gets OOM-killed and restarts instead of the whole instance
  locking up (which is what happened before any of this was in place).
- **`install.sh` provisions a 1G swapfile** (idempotent, low `vm.swappiness` so it's a backstop
  rather than the default). Expect the instance to lean on it sometimes rather than have
  comfortable headroom — that's the honest tradeoff of fitting this stack in 512MB. If it's still
  too tight in practice, the next lever is shrinking Keycloak's heap further, or moving Keycloak
  off this instance entirely.
- None of this touches local dev — `docker-compose.yml` (the base file) is untouched, so
  `docker compose up` without `-f docker-compose.prod.yml` still runs the full, untuned service
  set including `tools_api`, `mcp_inspector`, and Keycloak's own separate Postgres.

## Keycloak realm & client secrets

First boot imports `keycloak/realm-import/realm-export.json` if present (see
`keycloak/realm-import/README.md` for how to (re-)export it) — but only into an **empty** realm
database, so this is a one-time seed per fresh database, not a sync (in prod that's the
`keycloak` database inside the shared `postgres` instance/`tools_db_postgres_data` volume; in
local dev it's still the separate `keycloak_postgres_data` volume).

Keycloak's partial export masks confidential client secrets as the literal string `**********`.
`bootstrap.sh` checks each of `magic-boto-claude-connector` and `magic-boto-tools-api` after
import and regenerates a real secret via Keycloak's admin API for any still carrying that
placeholder — never touching one that already has a real value, so re-running never rotates (and
breaks) a secret you've already used. Results land in `.keycloak-client-secrets` at the repo root
(`chmod 600`, gitignored). `magic-boto-claude-connector`'s secret is what you paste into Claude.ai's
own "Add custom connector" form (Client ID `magic-boto-claude-connector`, issuer
`https://magicboto-keycloak.<domain>/realms/magic-boto`); `magic-boto-tools-api`'s isn't consumed
anywhere in this app today (`tools_mcp` only verifies bearer tokens, never acts as an OAuth
client — see `tools_api/app/mcp_tooling/auth/`) but is rotated anyway for hygiene.

## Ongoing

- **Redeploying, changing your IP, or picking up a new realm export**: re-run
  `.\deploy\lightsail\deploy.ps1` with the same (or updated) flags. Idempotent — safe to run as
  often as you like.
- **Backups**: `tools_db_postgres_data` (holds both the app and Keycloak databases in prod) is a
  Docker volume on the instance — Lightsail doesn't back it up for you. `pg_dump` on a schedule,
  or a Lightsail disk snapshot, is on you.
- **Cert renewal**: certbot's own systemd timer (`certbot.timer`) handles this automatically once
  the first `certbot certonly` run (inside `bootstrap.sh`) has completed — see "nginx runs in
  Docker, not natively" above for how the reload is wired.
