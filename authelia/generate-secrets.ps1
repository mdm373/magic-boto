<#
.SYNOPSIS
    Generate every secret authelia/configuration.yml and authelia/users_database.yml need into
    authelia/.secrets/. Only your non-secret admin identity (username/email) goes to .env.

.DESCRIPTION
    Idempotent — safe to re-run. The generated internal secrets (session/storage/HMAC/reset-
    password) and the connector client secrets (Claude, Muse) only fill in once, never regenerate.
    Your admin username/email/password are different: always prompted, so you can change them
    later — leave a prompt blank (or pass its parameter as "") and it keeps the current value
    unchanged.

    Uses `docker run` against the exact Authelia image tag authelia/Dockerfile builds from, so
    the generated hashes are always produced by the same version that verifies them — no local
    install of the `authelia` CLI needed.

    Written to authelia/.secrets/ (gitignored — configuration.yml/users_database.yml read these
    via the `secret` template function, never `env`, and Compose/Fly deliver them as files, never
    env vars):
      - session-secret.txt, storage-encryption-key.txt, oidc-hmac-secret.txt,
        reset-password-jwt-secret.txt: random strings Authelia uses internally (session cookies,
        DB encryption, request object signing, identity-validation tokens) — you never need to
        know these values.
      - claude-connector-client-secret.txt (+ ...-hash.txt): the client secret for Claude's MCP
        connector. Give Claude the plaintext file's contents when configuring the connector.
      - muse-connector-client-secret.txt (+ ...-hash.txt): the client secret for Muse's MCP
        connector. Give Muse the plaintext file's contents when configuring the connector.
      - admin-password.txt (+ ...-hash.txt): your login password for Authelia's portal.
      - oidc-issuer.pem: an RSA keypair for OIDC token signing.

    Written to .env — not secret, just your login identity:
      - AUTHELIA_ADMIN_USERNAME / AUTHELIA_ADMIN_EMAIL

.PARAMETER EnvFile
    Local .env to read/append (for the admin username/email only). Defaults to the repo root .env.

.PARAMETER AdminUsername
    Skips the username prompt if given. Ignored (falls through to the prompt) if empty.

.PARAMETER AdminEmail
    Skips the email prompt if given. Ignored (falls through to the prompt) if empty.

.EXAMPLE
    .\authelia\generate-secrets.ps1
.EXAMPLE
    .\authelia\generate-secrets.ps1 -AdminUsername mark -AdminEmail mark@example.com
#>
[CmdletBinding()]
param(
    [string]$EnvFile = (Join-Path $PSScriptRoot "..\.env"),
    [string]$AdminUsername,
    [string]$AdminEmail
)

$ErrorActionPreference = "Stop"
$AutheliaImage = "authelia/authelia:4.38"
$SecretsDir = Join-Path $PSScriptRoot ".secrets"

if (-not (Test-Path $EnvFile)) {
    Write-Error "No .env at $EnvFile — copy .env.example first."
    exit 1
}

New-Item -ItemType Directory -Force -Path $SecretsDir | Out-Null

. (Join-Path $PSScriptRoot "..\scripts\get-env-value.ps1")

# Add-Content doesn't insert a leading newline on its own — if the file's last line has no
# trailing newline, the first append would land on the same line as existing content. Fix that
# up once, unconditionally, before any Add-Content call below.
$existingContent = Get-Content -Raw -Path $EnvFile -ErrorAction SilentlyContinue
if ($existingContent -and $existingContent -notmatch "(`r`n|`n)$") {
    Add-Content -Path $EnvFile -Value ""
}

function Set-EnvValue {
    param([Parameter(Mandatory)] [string]$Name, [Parameter(Mandatory)] [string]$Value)
    $lines = @(Get-Content -Path $EnvFile -ErrorAction SilentlyContinue)
    $pattern = "^\s*$([regex]::Escape($Name))\s*="
    $matchIndex = $null
    for ($i = $lines.Count - 1; $i -ge 0; $i--) {
        if ($lines[$i] -match $pattern) { $matchIndex = $i; break }
    }
    if ($null -ne $matchIndex) {
        $lines[$matchIndex] = "$Name=$Value"
        Set-Content -Path $EnvFile -Value $lines
    } else {
        Add-Content -Path $EnvFile -Value "$Name=$Value"
    }
    Write-Host "==> Wrote $Name to .env" -ForegroundColor Green
}

function Get-CryptoOutput {
    param([Parameter(Mandatory)] [string[]]$Arguments)
    docker run --rm $AutheliaImage authelia crypto @Arguments
}

function Get-MatchValue {
    param([Parameter(Mandatory)] [string[]]$Lines, [Parameter(Mandatory)] [string]$Pattern)
    ($Lines | Select-String -Pattern $Pattern).Matches[0].Groups[1].Value.Trim()
}

# `authelia crypto rand`/`hash generate` print labeled lines ("Random Value: <value>",
# "Random Password: <value>", "Digest: <value>"), not bare values.
function New-RandomSecret {
    $output = Get-CryptoOutput @("rand", "--length", "64", "--charset", "alphanumeric")
    Get-MatchValue -Lines $output -Pattern "Random Value: (.+)"
}

function New-PasswordAndHash {
    # `--random` prints both a random plaintext and its digest in one call — the only way to get
    # a plaintext/hash pair that's guaranteed to match.
    $output = Get-CryptoOutput @("hash", "generate", "pbkdf2", "--variant", "sha512", "--random", "--random.length", "72", "--random.charset", "alphanumeric")
    return @{
        Password = Get-MatchValue -Lines $output -Pattern "Random Password: (.+)"
        Hash     = Get-MatchValue -Lines $output -Pattern "Digest: (.+)"
    }
}

function New-PasswordHash {
    param([Parameter(Mandatory)] [string]$Password)
    $output = Get-CryptoOutput @("hash", "generate", "pbkdf2", "--variant", "sha512", "--password", $Password)
    Get-MatchValue -Lines $output -Pattern "Digest: (.+)"
}

function ConvertFrom-SecureStringPlain {
    param([Parameter(Mandatory)] [System.Security.SecureString]$Secure)
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try { [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

function Read-AdminPassword {
    param([bool]$HasExisting)
    $suffix = if ($HasExisting) { " [blank to keep current]" } else { "" }
    while ($true) {
        $first = Read-Host "Admin password$suffix" -AsSecureString
        $plain1 = ConvertFrom-SecureStringPlain $first
        if (-not $plain1) {
            if ($HasExisting) { return $null }
            Write-Host "A password is required for first-time setup." -ForegroundColor Red
            continue
        }
        $second = Read-Host "Confirm admin password" -AsSecureString
        $plain2 = ConvertFrom-SecureStringPlain $second
        if ($plain1 -eq $plain2) { return $plain1 }
        Write-Host "Passwords didn't match — try again." -ForegroundColor Red
    }
}

# A secret whose value never needs to leave this machine (session/storage/HMAC secrets) — one
# random-value file, generated only if missing.
function Set-RandomSecretFile {
    param([Parameter(Mandatory)] [string]$FileName)
    $path = Join-Path $SecretsDir $FileName
    if (Test-Path $path) {
        Write-Host "==> $path already exists, skipping" -ForegroundColor DarkGray
        return
    }
    Set-Content -Path $path -Value (New-RandomSecret) -NoNewline
    Write-Host "==> Wrote $path" -ForegroundColor Green
}

# A secret with both a plaintext form (for you/Claude to use) and a hash (for Authelia to check
# against) — generated together via $Generate only if the hash file is missing.
function Set-SecretPairIfMissing {
    param(
        [Parameter(Mandatory)] [string]$PlaintextFileName,
        [Parameter(Mandatory)] [string]$HashFileName,
        [Parameter(Mandatory)] [scriptblock]$Generate
    )
    $hashPath = Join-Path $SecretsDir $HashFileName
    if (Test-Path $hashPath) {
        Write-Host "==> $hashPath already exists, skipping" -ForegroundColor DarkGray
        return $null
    }
    $pair = & $Generate
    Set-Content -Path (Join-Path $SecretsDir $PlaintextFileName) -Value $pair.Password -NoNewline
    Set-Content -Path $hashPath -Value $pair.Hash -NoNewline
    Write-Host "==> Wrote $hashPath" -ForegroundColor Green
    return $pair
}

Set-RandomSecretFile -FileName "session-secret.txt"
Set-RandomSecretFile -FileName "storage-encryption-key.txt"
Set-RandomSecretFile -FileName "oidc-hmac-secret.txt"
Set-RandomSecretFile -FileName "reset-password-jwt-secret.txt"

$currentUsername = Get-EnvValue -EnvFile $EnvFile -Name "AUTHELIA_ADMIN_USERNAME"
if (-not $AdminUsername) {
    $suffix = if ($currentUsername) { " [blank to keep current]" } else { "" }
    $AdminUsername = Read-Host "Admin username$suffix"
}
if ($AdminUsername) {
    Set-EnvValue -Name "AUTHELIA_ADMIN_USERNAME" -Value $AdminUsername
} elseif ($currentUsername) {
    Write-Host "==> Keeping existing AUTHELIA_ADMIN_USERNAME" -ForegroundColor DarkGray
} else {
    Write-Error "Admin username is required."
    exit 1
}

$currentEmail = Get-EnvValue -EnvFile $EnvFile -Name "AUTHELIA_ADMIN_EMAIL"
if (-not $AdminEmail) {
    $suffix = if ($currentEmail) { " [blank to keep current]" } else { "" }
    $AdminEmail = Read-Host "Admin email$suffix"
}
if ($AdminEmail) {
    Set-EnvValue -Name "AUTHELIA_ADMIN_EMAIL" -Value $AdminEmail
} elseif ($currentEmail) {
    Write-Host "==> Keeping existing AUTHELIA_ADMIN_EMAIL" -ForegroundColor DarkGray
} else {
    Write-Error "Admin email is required."
    exit 1
}

$client = Set-SecretPairIfMissing -PlaintextFileName "claude-connector-client-secret.txt" `
    -HashFileName "claude-connector-client-secret-hash.txt" -Generate { New-PasswordAndHash }
if ($client) {
    Write-Host "==> Paste this into Claude's MCP connector config as the client secret: $($client.Password)" -ForegroundColor Yellow
}

$museClient = Set-SecretPairIfMissing -PlaintextFileName "muse-connector-client-secret.txt" `
    -HashFileName "muse-connector-client-secret-hash.txt" -Generate { New-PasswordAndHash }
if ($museClient) {
    Write-Host "==> Paste this into Muse's MCP connector config as the client secret: $($museClient.Password)" -ForegroundColor Yellow
}

$adminPasswordHashPath = Join-Path $SecretsDir "admin-password-hash.txt"
$newAdminPassword = Read-AdminPassword -HasExisting (Test-Path $adminPasswordHashPath)
if ($newAdminPassword) {
    Set-Content -Path (Join-Path $SecretsDir "admin-password.txt") -Value $newAdminPassword -NoNewline
    Set-Content -Path $adminPasswordHashPath -Value (New-PasswordHash -Password $newAdminPassword) -NoNewline
    Write-Host "==> Wrote $adminPasswordHashPath" -ForegroundColor Green
} else {
    Write-Host "==> Keeping existing admin password" -ForegroundColor DarkGray
}

$pemPath = Join-Path $SecretsDir "oidc-issuer.pem"
if (Test-Path $pemPath) {
    Write-Host "==> $pemPath already exists, skipping" -ForegroundColor DarkGray
} else {
    docker run --rm -v "${SecretsDir}:/output" $AutheliaImage authelia crypto pair rsa generate --directory /output --bits 2048
    if ($LASTEXITCODE -ne 0) { Write-Error "authelia crypto pair rsa generate failed."; exit $LASTEXITCODE }
    Move-Item (Join-Path $SecretsDir "private.pem") $pemPath
    Remove-Item (Join-Path $SecretsDir "public.pem") -ErrorAction SilentlyContinue
    Write-Host "==> Generated $pemPath" -ForegroundColor Green
}

Write-Host "==> Done. Review .env and authelia\.secrets\, then run docker compose up (local) or authelia\deploy.ps1 (Fly)." -ForegroundColor Green
exit 0
