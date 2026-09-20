<#
.SYNOPSIS
    Create (or update) the Fly.io tools_api app for magic-boto: build the UI, app, public IP,
    secrets, deploy (which runs migrations via fly.toml's release_command).

.DESCRIPTION
    Idempotent — safe to re-run. Builds tools-ui first (npm install + npm run build), which
    writes into tools_api/app/mcp_tooling/ui_dist/ — the same directory local dev populates via
    docker-compose.yml's bind mount, but there is no bind mount on Fly, so this script has to
    produce it on disk before `fly deploy` uploads the build context. No Dockerfile change is
    needed for this: the freshly-built ui_dist is just an ordinary directory the existing
    `COPY . .` picks up.

    Deploys two process groups (see fly.toml): "mcp" (public, auth-gated — TOOLS_MCP_AUTH_ENABLED
    is on, checking bearer tokens against the deployed Authelia instance) and "worker" (Celery,
    no public or private service at all — outbound-only to Postgres/Redis). Every deploy runs
    `uv run invoke migrate` first via fly.toml's `release_command`, aborting the deploy (keeping
    the previous release live) if migrations fail.

    Pushes POSTGRES_USER/PASSWORD (reusing the shared magic-boto-db instance's credentials — see
    postgres/init-db.sh) and ANTHROPIC_API_KEY (required for tag sweep/audit, run by the worker)
    as Fly secrets. Everything else (Postgres/Redis/Authelia addresses, OIDC audience, MCP
    host/port) is plain, non-secret config in fly.toml's [env].

    Requires the `fly` CLI (flyctl) on PATH and you logged in (`fly auth login`), and `npm` on
    PATH to build tools-ui.

.PARAMETER Region
    Fly region for the app (should match magic-boto-db's region for lower latency).

.PARAMETER EnvFile
    Local .env to read secrets from. Defaults to the repo root .env.

.PARAMETER VolumeSizeGb
    Size of the "mcp" process group's card-image cache volume (see fly.toml's [[mounts]]). Growing
    later is easy; shrinking is not — start small.

.EXAMPLE
    .\tools_api\deploy.ps1
.EXAMPLE
    .\tools_api\deploy.ps1 -Region sea
#>
[CmdletBinding()]
param(
    [string]$Region = "iad",
    [string]$EnvFile = (Join-Path $PSScriptRoot "..\.env"),
    [int]$VolumeSizeGb = 2
)

$ErrorActionPreference = "Stop"

$AppName = "magic-boto-tools-api"

if (-not (Test-Path $EnvFile)) {
    Write-Error "No .env at $EnvFile — copy .env.example and fill in POSTGRES_USER/PASSWORD/ANTHROPIC_API_KEY first."
    exit 1
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Error "npm not found on PATH — install Node.js to build tools-ui before deploying."
    exit 1
}

. (Join-Path $PSScriptRoot "..\scripts\get-env-value.ps1")
. (Join-Path $PSScriptRoot "..\scripts\fly-deploy.ps1")

$pgUser = Get-EnvValue -EnvFile $EnvFile -Name "POSTGRES_USER" -Default "magicboto"
$pgPassword = Get-EnvValue -EnvFile $EnvFile -Name "POSTGRES_PASSWORD" -Default "magicboto"
$anthropicApiKey = Get-EnvValue -EnvFile $EnvFile -Name "ANTHROPIC_API_KEY"
if (-not $anthropicApiKey) {
    Write-Error "ANTHROPIC_API_KEY is not set in $EnvFile — required for the worker's tag sweep/audit tasks."
    exit 1
}

$toolsUiDir = Join-Path $PSScriptRoot "..\tools-ui"
Write-Host "==> Building tools-ui" -ForegroundColor Cyan
Push-Location $toolsUiDir
try {
    npm install
    if ($LASTEXITCODE -ne 0) { Write-Error "npm install failed."; exit $LASTEXITCODE }
    npm run build
    if ($LASTEXITCODE -ne 0) { Write-Error "npm run build failed."; exit $LASTEXITCODE }
} finally {
    Pop-Location
}

Write-Host "==> Checking for existing app '$AppName'" -ForegroundColor Cyan
fly status -a $AppName *> $null
$appExistedBefore = ($LASTEXITCODE -eq 0)

Deploy-FlyApp -AppName $AppName -Region $Region -VolumeName "magic_boto_tools_cache" `
    -VolumeSizeGb $VolumeSizeGb -WorkingDir $PSScriptRoot `
    -ConfigPath (Join-Path $PSScriptRoot "fly.toml") `
    -Secrets @{
        POSTGRES_USER     = $pgUser
        POSTGRES_PASSWORD = $pgPassword
        ANTHROPIC_API_KEY = $anthropicApiKey
    }

if (-not $appExistedBefore) {
    Write-Host "==> Allocating public IPs" -ForegroundColor Cyan
    fly ips allocate-v4 --shared -a $AppName
    if ($LASTEXITCODE -ne 0) { Write-Error "fly ips allocate-v4 failed."; exit $LASTEXITCODE }
    fly ips allocate-v6 -a $AppName
    if ($LASTEXITCODE -ne 0) { Write-Error "fly ips allocate-v6 failed."; exit $LASTEXITCODE }
} else {
    Write-Host "==> App already existed, skipping public IP allocation (run 'fly ips list -a $AppName' to check)" -ForegroundColor DarkGray
}

Write-Host "==> Done." -ForegroundColor Green
Write-Host "    MCP (Streamable HTTP, auth required): https://${AppName}.fly.dev/mcp" -ForegroundColor Green
exit 0
