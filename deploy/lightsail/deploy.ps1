<#
.SYNOPSIS
    One-shot magic-boto deploy: copies install.sh to the Lightsail host and runs it there — it
    clones (or pulls) the repo itself, installs OS packages, then hands off to bootstrap.sh.

.DESCRIPTION
    Run from anywhere on your Windows dev machine (e.g. .\deploy\lightsail\deploy.ps1 from the
    repo root). Works on a totally fresh box — it doesn't require the repo to already be cloned
    on the server. Needs an SSH destination it can reach non-interactively (host alias from
    ~/.ssh/config, or user@host) with `scp` support. -RepoUrl defaults to the public HTTPS clone
    URL, so no server-side credentials are needed for that; pass an SSH remote instead if you
    fork this to a private repo (needs a deploy key already loaded on the box) — see
    docs/LIGHTSAIL-DEPLOY.md.

.PARAMETER SshHost
    SSH destination for the server, e.g. an alias from your ~/.ssh/config.

.PARAMETER Domain
    Root domain to deploy under, e.g. rundotgames.xyz. Derives the magicboto-* subdomains — see
    docs/LIGHTSAIL-DEPLOY.md.

.PARAMETER AdminIp
    IP (or small CIDR) nginx restricts the admin surfaces (Keycloak admin, Flower, Postgres) to.

.PARAMETER RemotePath
    Where the repo should live on the server. Cloned here if not already present; pulled if it
    is.

.PARAMETER RepoUrl
    Git remote to clone from when the server doesn't have the repo yet.

.EXAMPLE
    .\deploy\lightsail\deploy.ps1 -SshHost rundotgames -Domain rundotgames.xyz -AdminIp 203.0.113.7
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$SshHost,
    [Parameter(Mandatory)] [string]$Domain,
    [Parameter(Mandatory)] [string]$AdminIp,
    [string]$RemotePath = "~/magic-boto",
    [string]$RepoUrl = "https://github.com/mdm373/magic-boto.git",
    [int]$PostgresAppPort = 55432,
    [int]$PostgresKeycloakPort = 55433,
    [string]$CertbotEmail = ""
)

$ErrorActionPreference = "Stop"

foreach ($tool in @("ssh", "scp")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Error "$tool not found on PATH."
        exit 1
    }
}

$certbotArg = if ($CertbotEmail) { " --certbot-email '$CertbotEmail'" } else { "" }

# install.sh is self-contained (it clones/pulls the repo itself when run standalone, then execs
# the freshly-fetched bootstrap.sh) — so all deploy.ps1 needs to do is get that one file onto the
# box and run it. No dependency on the server already having a clone.
$localInstallScript = Join-Path $PSScriptRoot "install.sh"
$remoteInstallPath = "/tmp/magic-boto-install.sh"

Write-Host "==> Copying install.sh to ${SshHost}:${remoteInstallPath}" -ForegroundColor Cyan
scp $localInstallScript "${SshHost}:${remoteInstallPath}"

$remoteCommand = "sudo bash $remoteInstallPath --repo-url '$RepoUrl' --repo-path '$RemotePath' " +
    "--domain '$Domain' --admin-ip '$AdminIp' " +
    "--postgres-app-port $PostgresAppPort --postgres-keycloak-port $PostgresKeycloakPort$certbotArg"

Write-Host "==> Deploying magic-boto to $SshHost ($Domain)" -ForegroundColor Cyan
ssh -t $SshHost $remoteCommand

if ($LASTEXITCODE -ne 0) {
    Write-Error "Remote deploy failed (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}

Write-Host "==> Deploy finished." -ForegroundColor Green
