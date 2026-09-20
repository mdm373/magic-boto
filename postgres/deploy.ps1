<#
.SYNOPSIS
    Create (or update) the Fly.io Postgres app for magic-boto: app, volume, secrets, deploy.

.DESCRIPTION
    Idempotent — safe to re-run (see scripts/fly-deploy.ps1). Pushes POSTGRES_USER/PASSWORD from
    your local .env as Fly secrets (never written into fly.toml), and deploys postgres/fly.toml +
    postgres/Dockerfile (the same Dockerfile docker-compose.yml builds locally, so both stacks
    run the same Postgres image).

    Database names (magicboto_api, magicboto_authelia) live in fly.toml, not here — they're
    fixed by the Fly topology (one instance holding both), not local-dev secrets.

    Requires the `fly` CLI (flyctl) on PATH and you logged in (`fly auth login`).

.PARAMETER Region
    Fly region for the app and volume (they must match).

.PARAMETER VolumeSizeGb
    Size of the persistent volume in GB. Growing later is easy; shrinking is not — start small.

.PARAMETER EnvFile
    Local .env to read POSTGRES_USER/PASSWORD from. Defaults to the repo root .env.

.EXAMPLE
    .\postgres\deploy.ps1
.EXAMPLE
    .\postgres\deploy.ps1 -Region sea -VolumeSizeGb 3
#>
[CmdletBinding()]
param(
    [string]$Region = "iad",
    [int]$VolumeSizeGb = 1,
    [string]$EnvFile = (Join-Path $PSScriptRoot "..\.env")
)

$ErrorActionPreference = "Stop"

# Not a parameter, deliberately: other apps (authelia/fly.toml, its docstrings) hardcode
# "magic-boto-db.internal" to reach this instance — an overridable name here would silently break
# that cross-app routing. If "magic-boto-db" is taken on your Fly account, edit this constant AND
# every place that references it (grep the repo for "magic-boto-db"), don't pass a parameter.
$AppName = "magic-boto-db"

if (-not (Test-Path $EnvFile)) {
    Write-Error "No .env at $EnvFile — copy .env.example and fill in POSTGRES_USER/PASSWORD first."
    exit 1
}

. (Join-Path $PSScriptRoot "..\scripts\get-env-value.ps1")
. (Join-Path $PSScriptRoot "..\scripts\fly-deploy.ps1")

$pgUser = Get-EnvValue -EnvFile $EnvFile -Name "POSTGRES_USER" -Default "magicboto"
$pgPassword = Get-EnvValue -EnvFile $EnvFile -Name "POSTGRES_PASSWORD" -Default "magicboto"

Deploy-FlyApp -AppName $AppName -Region $Region -VolumeName "magic_boto_db_data" `
    -VolumeSizeGb $VolumeSizeGb -WorkingDir $PSScriptRoot `
    -ConfigPath (Join-Path $PSScriptRoot "fly.toml") `
    -Secrets @{ POSTGRES_USER = $pgUser; POSTGRES_PASSWORD = $pgPassword }

# init-db.sh (see postgres/Dockerfile) only runs once, on a brand-new volume — it never re-runs
# on a redeploy against an already-initialized one, so a sibling database added to fly.toml after
# the volume already existed would otherwise silently never get created. `createdb` here is
# idempotent in effect (best-effort: it errors "already exists" on every later run, which we
# don't treat as fatal) and runs on every deploy regardless of volume age.
$flyTomlContent = Get-Content (Join-Path $PSScriptRoot "fly.toml") -Raw
if ($flyTomlContent -match 'AUTHELIA_DB_NAME\s*=\s*"([^"]+)"') {
    $autheliaDbName = $Matches[1]
    Write-Host "==> Ensuring database '$autheliaDbName' exists" -ForegroundColor Cyan
    try { fly ssh console -a $AppName -C "createdb -U $pgUser $autheliaDbName" } catch {}
}

Write-Host "==> Done. Reachable from other apps in this org at ${AppName}.internal:5432 (private network only)." -ForegroundColor Green
exit 0
