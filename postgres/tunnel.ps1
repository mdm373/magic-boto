<#
.SYNOPSIS
    Open a local TCP tunnel to the magic-boto-db Fly Postgres app via `fly proxy`.

.DESCRIPTION
    magic-boto-db has no public IP (see postgres/fly.toml) — reachable only from other Fly apps
    on the private network, or from your machine via `fly proxy`/WireGuard. This runs `fly proxy`
    in the foreground, forwarding a local port to the app's Postgres port. Leave it running in its
    own terminal; in another terminal, point psql/pg_restore/Invoke tasks at -LocalPort.

    Requires the `fly` CLI (flyctl) on PATH and you logged in (`fly auth login`).

.PARAMETER AppName
    Fly app name for the Postgres instance. Matches postgres/deploy.ps1's $AppName constant.

.PARAMETER LocalPort
    Local port to forward. Defaults to 15432, not 5432, so it doesn't collide with a locally
    running docker-compose Postgres on the standard port.

.PARAMETER RemotePort
    Remote port on the Fly app.

.EXAMPLE
    .\postgres\tunnel.ps1
.EXAMPLE
    .\postgres\tunnel.ps1 -LocalPort 5433
#>
[CmdletBinding()]
param(
    [string]$AppName = "magic-boto-db",
    [int]$LocalPort = 15432,
    [int]$RemotePort = 5432
)

$ErrorActionPreference = "Stop"

Write-Host "==> Tunneling localhost:$LocalPort -> ${AppName}:$RemotePort (Ctrl+C to stop)" -ForegroundColor Cyan
fly proxy "${LocalPort}:${RemotePort}" -a $AppName
