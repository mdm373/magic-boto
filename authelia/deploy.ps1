<#
.SYNOPSIS
    Create (or update) the Fly.io Authelia app for magic-boto: app, public IP, secrets, deploy.

.DESCRIPTION
    Idempotent — safe to re-run (see scripts/fly-deploy.ps1). Runs authelia/generate-secrets.ps1
    itself first (idempotent too — only fills in what's missing, and will prompt for your admin
    username/email/password on a fresh setup), so this is a true one-shot: a fresh clone with
    just .env.example copied to .env needs nothing else before running this.

    Pushes AUTHELIA_ADMIN_USERNAME/EMAIL from .env, plus AUTHELIA_STORAGE_POSTGRES_USERNAME/
    PASSWORD (reusing the shared magic-boto-db instance's credentials, stored in .env as
    POSTGRES_USER/PASSWORD — see postgres/init-db.sh, but pushed under Authelia's own expected
    env-var names), as ordinary Fly secrets (env vars) — these are short, single-line values,
    safe to pass as CLI arguments. Everything else generate-secrets.ps1 generated — the OIDC
    issuer's private key, session/storage/HMAC secrets, and the client-secret/admin-password
    hashes — is read straight off disk from authelia/.secrets/ at deploy time via
    authelia/fly.toml's [[files]] `local_path` entries (feeding both Authelia's own `_FILE`
    env-var config and authelia/docker-entrypoint.sh's template substitution), never passed as a
    CLI argument or Fly secret: some of these are multi-line (the PEM), and PowerShell's argument
    marshaling to flyctl.exe corrupts multi-line values passed that way — the Machine then hangs
    at boot instead of failing cleanly. No volume: state lives in the magicboto_authelia database
    on magic-boto-db, not on this app's own disk.

    Requires the `fly` CLI (flyctl) on PATH and you logged in (`fly auth login`).

.PARAMETER Region
    Fly region for the app (should match the Postgres app's region for lower latency).

.PARAMETER EnvFile
    Local .env to read secrets from. Defaults to the repo root .env.

.EXAMPLE
    .\authelia\deploy.ps1
.EXAMPLE
    .\authelia\deploy.ps1 -Region sea
#>
[CmdletBinding()]
param(
    [string]$Region = "iad",
    [string]$EnvFile = (Join-Path $PSScriptRoot "..\.env")
)

$ErrorActionPreference = "Stop"

# Not a parameter, deliberately: authelia/fly.toml hardcodes AUTHELIA_PUBLIC_DOMAIN/URL as
# "magic-boto-authelia.fly.dev" and Claude's connector config points at that exact domain — an
# overridable app name here would silently break both. If the name is taken on your Fly account,
# edit this constant AND authelia/fly.toml's AUTHELIA_PUBLIC_DOMAIN/URL together, don't pass a
# parameter.
$AppName = "magic-boto-authelia"

if (-not (Test-Path $EnvFile)) {
    Write-Error "No .env at $EnvFile — copy .env.example to .env first (needs POSTGRES_USER/PASSWORD for the shared instance)."
    exit 1
}

& (Join-Path $PSScriptRoot "generate-secrets.ps1") -EnvFile $EnvFile
if ($LASTEXITCODE -ne 0) { Write-Error "generate-secrets.ps1 failed."; exit $LASTEXITCODE }

$SecretsDir = Join-Path $PSScriptRoot ".secrets"

. (Join-Path $PSScriptRoot "..\scripts\get-env-value.ps1")
. (Join-Path $PSScriptRoot "..\scripts\fly-deploy.ps1")

function Get-RequiredEnvValue {
    param([Parameter(Mandatory)] [string]$Name)
    $value = Get-EnvValue -EnvFile $EnvFile -Name $Name
    if (-not $value) { Write-Error "$Name is still not set in $EnvFile after generate-secrets.ps1 — something went wrong."; exit 1 }
    return $value
}

function Assert-SecretFileExists {
    param([Parameter(Mandatory)] [string]$Path)
    if (-not (Test-Path $Path)) { Write-Error "$Path is missing after generate-secrets.ps1 — something went wrong."; exit 1 }
}

# These are read directly by authelia/fly.toml's [[files]] local_path entries at `fly deploy`
# time, not passed through here — just confirm they exist before we bother deploying.
foreach ($name in @("oidc-issuer.pem", "claude-connector-client-secret-hash.txt", "admin-password-hash.txt", "session-secret.txt", "storage-encryption-key.txt", "oidc-hmac-secret.txt")) {
    Assert-SecretFileExists (Join-Path $SecretsDir $name)
}

Write-Host "==> Checking for existing app '$AppName'" -ForegroundColor Cyan
fly status -a $AppName *> $null
$appExistedBefore = ($LASTEXITCODE -eq 0)

Deploy-FlyApp -AppName $AppName -Region $Region -WorkingDir $PSScriptRoot `
    -ConfigPath (Join-Path $PSScriptRoot "fly.toml") `
    -Secrets @{
        AUTHELIA_ADMIN_USERNAME           = Get-RequiredEnvValue "AUTHELIA_ADMIN_USERNAME"
        AUTHELIA_ADMIN_EMAIL              = Get-RequiredEnvValue "AUTHELIA_ADMIN_EMAIL"
        AUTHELIA_STORAGE_POSTGRES_USERNAME = Get-EnvValue -EnvFile $EnvFile -Name "POSTGRES_USER" -Default "magicboto"
        AUTHELIA_STORAGE_POSTGRES_PASSWORD = Get-EnvValue -EnvFile $EnvFile -Name "POSTGRES_PASSWORD" -Default "magicboto"
    }

if (-not $appExistedBefore) {
    Write-Host "==> Allocating public IPs" -ForegroundColor Cyan
    fly ips allocate-v4 --shared -a $AppName
    if ($LASTEXITCODE -ne 0) { Write-Error "fly ips allocate-v4 failed."; exit $LASTEXITCODE }
    fly ips allocate-v6 -a $AppName
    if ($LASTEXITCODE -ne 0) { Write-Error "fly ips allocate-v6 failed."; exit $LASTEXITCODE }
}

Write-Host "==> Done." -ForegroundColor Green
Write-Host "    https://${AppName}.fly.dev" -ForegroundColor Green
