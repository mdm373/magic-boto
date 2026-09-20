<#
.SYNOPSIS
    Create (or update) the Fly.io Redis app for magic-boto: app, volume, deploy.

.DESCRIPTION
    Idempotent — safe to re-run (see scripts/fly-deploy.ps1). Deploys redis/fly.toml +
    redis/Dockerfile (redis:7-alpine with AOF persistence to the mounted volume, same image
    family docker-compose.yml runs locally).

    No secrets to push — this Redis has no password, same as the local Compose service; its only
    protection is Fly's private network (.internal/WireGuard), same as how magic-boto-db is reached.

    Requires the `fly` CLI (flyctl) on PATH and you logged in (`fly auth login`).

.PARAMETER Region
    Fly region for the app and volume (they must match).

.PARAMETER VolumeSizeGb
    Size of the persistent volume in GB. Growing later is easy; shrinking is not — start small.

.EXAMPLE
    .\redis\deploy.ps1
.EXAMPLE
    .\redis\deploy.ps1 -Region sea -VolumeSizeGb 3
#>
[CmdletBinding()]
param(
    [string]$Region = "iad",
    [int]$VolumeSizeGb = 1
)

$ErrorActionPreference = "Stop"

# Not a parameter, deliberately — see postgres/deploy.ps1's $AppName comment; an overridable name
# risks silently breaking any future cross-app reference to "magic-boto-redis". If the name is
# taken on your Fly account, edit this constant (and grep the repo for other references) instead.
$AppName = "magic-boto-redis"

. (Join-Path $PSScriptRoot "..\scripts\fly-deploy.ps1")

Deploy-FlyApp -AppName $AppName -Region $Region -VolumeName "magic_boto_redis_data" `
    -VolumeSizeGb $VolumeSizeGb -WorkingDir $PSScriptRoot `
    -ConfigPath (Join-Path $PSScriptRoot "fly.toml")

Write-Host "==> Done. Reachable from other apps in this org at ${AppName}.internal:6379 (private network only)." -ForegroundColor Green
