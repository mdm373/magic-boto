<#
.SYNOPSIS
    Deploy-FlyApp: create (or update) a Fly.io app, with an optional single volume. Shared by
    deploy scripts (postgres/deploy.ps1, redis/deploy.ps1, authelia/deploy.ps1) so the
    create/update logic lives in one place.

.DESCRIPTION
    Idempotent — safe to re-run. Creates the Fly app (and volume, if -VolumeName is given) only
    if they don't already exist, optionally pushes secrets (never written into fly.toml), then
    deploys.

    Dot-source this file from a deploy script, then call Deploy-FlyApp. From a script under a
    sibling directory (e.g. postgres/):

        . (Join-Path $PSScriptRoot "..\scripts\fly-deploy.ps1")
        Deploy-FlyApp -AppName $AppName -Region $Region -VolumeName "magic_boto_db_data" `
            -VolumeSizeGb $VolumeSizeGb -WorkingDir $PSScriptRoot `
            -ConfigPath (Join-Path $PSScriptRoot "fly.toml") `
            -Secrets @{ POSTGRES_USER = $pgUser; POSTGRES_PASSWORD = $pgPassword }

    Print your own "Done, reachable at ..." line after calling this — reachability (flycast-only,
    a public domain, etc.) differs per app, so this function stays silent on that.

    Requires the `fly` CLI (flyctl) on PATH and you logged in (`fly auth login`).
#>

function Deploy-FlyApp {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [string]$AppName,
        [Parameter(Mandatory)] [string]$Region,
        [string]$VolumeName,
        [int]$VolumeSizeGb,
        [Parameter(Mandatory)] [string]$WorkingDir,
        [Parameter(Mandatory)] [string]$ConfigPath,
        [hashtable]$Secrets
    )

    $ErrorActionPreference = "Stop"

    Write-Host "==> Checking for existing app '$AppName'" -ForegroundColor Cyan
    fly status -a $AppName *> $null
    $appExists = ($LASTEXITCODE -eq 0)

    if (-not $appExists) {
        Write-Host "==> Creating app '$AppName'" -ForegroundColor Cyan
        fly apps create $AppName
        if ($LASTEXITCODE -ne 0) { Write-Error "fly apps create failed."; exit $LASTEXITCODE }
    } else {
        Write-Host "==> App '$AppName' already exists, skipping create" -ForegroundColor DarkGray
    }

    if ($VolumeName) {
        Write-Host "==> Checking for existing volume '$VolumeName'" -ForegroundColor Cyan
        $volumeList = fly volumes list -a $AppName --json | ConvertFrom-Json
        $volumeExists = $volumeList | Where-Object { $_.Name -eq $VolumeName }

        if (-not $volumeExists) {
            Write-Host "==> Creating ${VolumeSizeGb}GB volume in $Region" -ForegroundColor Cyan
            fly volumes create $VolumeName -a $AppName --region $Region --size $VolumeSizeGb --yes
            if ($LASTEXITCODE -ne 0) { Write-Error "fly volumes create failed."; exit $LASTEXITCODE }
        } else {
            Write-Host "==> Volume already exists, skipping create" -ForegroundColor DarkGray
        }
    }

    if ($Secrets) {
        Write-Host "==> Setting secrets ($($Secrets.Keys -join ', '))" -ForegroundColor Cyan
        # @(...) forces an array even with exactly one entry — without it, a single-item pipeline
        # result collapses to a scalar string, and splatting a string via @var sends it character
        # by character instead of as one argument.
        $secretArgs = @($Secrets.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" })
        fly secrets set -a $AppName @secretArgs --stage
        if ($LASTEXITCODE -ne 0) { Write-Error "fly secrets set failed."; exit $LASTEXITCODE }
    }

    Write-Host "==> Deploying" -ForegroundColor Cyan
    fly deploy $WorkingDir -a $AppName --config $ConfigPath
    if ($LASTEXITCODE -ne 0) { Write-Error "fly deploy failed."; exit $LASTEXITCODE }
}
