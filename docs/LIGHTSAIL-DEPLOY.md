# Deploying to Lightsail

`deploy\lightsail\deploy.ps1` is the one-shot entry point — run it from your Windows dev machine,
in the repo root:

```powershell
.\deploy\lightsail\deploy.ps1 -SshHost rundotgames -Domain rundotgames.xyz -AdminIp 203.0.113.7
```

It copies `install.sh` to `-SshHost` via `scp` and runs it there with `sudo`. `install.sh` is
self-contained: it clones the repo to `-RemotePath` (default `~/magic-boto`) if it isn't there
yet, or `git pull`s it if it is, installs whatever OS packages are missing (nginx, certbot +
plugin, Docker, `jq`, `envsubst`), then hands off to `bootstrap.sh` from that same clone. So this
works on a genuinely fresh box — nothing needs to be pre-cloned. Re-running it after a code
change, an IP change, or a fresh `keycloak/realm-import/realm-export.json` export is the same one
command — everything downstream is idempotent.

## Layout

- **`deploy/lightsail/install.sh`** — clones/pulls the repo (when run standalone — see below),
  installs OS packages (only what's missing), then execs `bootstrap.sh` with whatever args it
  wasn't itself (`--repo-url`, `--repo-path` are consumed here; everything else is forwarded).
- **`deploy/lightsail/bootstrap.sh`** — the actual per-deploy work: `.env` upserts, `docker
  compose up` with the prod overlay, migrations, Keycloak realm client-secret checks, nginx config
  render + reload, certbot.
- **`deploy/lightsail/deploy.ps1`** — the Windows-side one-shot wrapper described above.

You can skip `deploy.ps1` and run directly on the server instead — either from inside an existing
clone (`sudo ./deploy/lightsail/install.sh --domain ... --admin-ip ...`, which then just installs
packages and hands off, no cloning involved since it detects it's already inside one), or as a
single fetched file on a fresh box (`sudo bash install.sh --repo-path ~/magic-boto --domain ...
--admin-ip ...`, which clones first). Same end result either way.

## What it assumes about the instance

A plain Debian 12 Lightsail instance, possibly already serving other sites via nginx —
`bootstrap.sh` only ever touches `/etc/nginx/conf.d/magicboto.conf` and
`/etc/nginx/stream.conf.d/magicboto-postgres.conf`, and appends a `stream {}` include to
`nginx.conf` if one isn't already there. It never touches other vhosts. `-RepoUrl` defaults to
the public HTTPS clone URL, so the clone/pull step needs no credentials on the box; only override
it with an SSH remote if you fork this to a private repo (then a deploy key needs to already be
loaded there).

**First time only**: DNS — A records for `magicboto-mcp.<domain>`, `magicboto-keycloak.<domain>`,
`magicboto-keycloak-admin.<domain>`, and `magicboto-flower.<domain>` pointing at the instance —
needs to be in place before certbot can issue for them. `.env` also needs real secrets before
`docker compose` ever runs — `deploy.ps1`/`bootstrap.sh` set the deploy-topology values (domains,
admin IP, ports) but deliberately refuse to invent passwords or API keys. So the very first run
stops on purpose, right after creating `.env` from `.env.example`:

```bash
.\deploy\lightsail\deploy.ps1 -SshHost rundotgames -Domain rundotgames.xyz -AdminIp 203.0.113.7
# ...
# Created .env from .env.example. Fill in real secrets (POSTGRES_PASSWORD, KEYCLOAK_ADMIN_PASSWORD,
# KEYCLOAK_DB_PASSWORD, ANTHROPIC_API_KEY, etc.), then re-run.
```

```bash
# on the server
cd ~/magic-boto
nano .env
# fill in: POSTGRES_PASSWORD, KEYCLOAK_ADMIN_PASSWORD, KEYCLOAK_DB_PASSWORD, ANTHROPIC_API_KEY, etc.
```

Then re-run `deploy.ps1` (or `bootstrap.sh` directly on the box) — this time it proceeds past the
`.env` check and actually brings the stack up. This ordering matters beyond just "fill in secrets
eventually": Postgres/Keycloak's DB only apply their password env vars when the data volume is
first initialized, so a `docker compose up` that ran once on placeholder values would keep those
credentials baked into the volume even after `.env` is fixed, until the volume is dropped or
`.env` is put back to match. Stopping before the first `up` ever happens avoids that entirely.

## Subdomains

Every HTTP surface rides the box's existing port 443 (nginx routes by `server_name`/SNI, same as
whatever else that nginx already serves) — no extra HTTP ports to open. Only Postgres needs
dedicated ports, since raw TCP can't be routed by hostname.

| Subdomain | Backend | Access |
|---|---|---|
| `magicboto-mcp.<domain>` | `tools_mcp` :8765 | public |
| `magicboto-keycloak.<domain>` | `keycloak_public_proxy` :8181 | public |
| `magicboto-keycloak-admin.<domain>` | `keycloak` :8180 | `-AdminIp` only |
| `magicboto-flower.<domain>` | `flower` :5555 | `-AdminIp` only |
| Postgres app DB, `-PostgresAppPort` (default 55432) | `postgres` :5432 | `-AdminIp` only |
| Postgres Keycloak DB, `-PostgresKeycloakPort` (default 55433) | `keycloak_postgres` :5433 | `-AdminIp` only |

MCP Inspector isn't routed publicly — it stays loopback-only; use an SSH tunnel
(`ssh -L 6274:localhost:6274 <host>`) when you need it.

Every service's port in `docker-compose.yml` is `127.0.0.1`-bound. nginx reaches them all via
`localhost` since it's native on the same host; loopback binding is what stops anything *outside*
the host from reaching them directly, regardless of the nginx config.

**Access control lives entirely in nginx**, via `allow <ip>; deny all;` on the admin
server/stream blocks — open 443 and the two Postgres ports in the Lightsail firewall once and
never touch it again. Changing who's allowed in is `-AdminIp` on the next `deploy.ps1` run, not a
console trip.

## Keycloak realm & client secrets

First boot imports `keycloak/realm-import/realm-export.json` if present (see
`keycloak/realm-import/README.md` for how to (re-)export it) — but only into an **empty**
`keycloak_postgres_data` volume, so this is a one-time seed per fresh volume, not a sync.

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
- **Backups**: `tools_db_postgres_data` and `keycloak_postgres_data` are Docker volumes on the
  instance — Lightsail doesn't back these up for you. `pg_dump` on a schedule, or a Lightsail disk
  snapshot, is on you.
- **Cert renewal**: certbot's own systemd timer (`certbot.timer`) handles this automatically once
  the first `certbot --nginx` run (inside `bootstrap.sh`) has completed.
