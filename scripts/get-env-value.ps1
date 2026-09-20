<#
.SYNOPSIS
    Get-EnvValue: read a single KEY=value out of a .env-style file. Shared by deploy scripts
    (e.g. postgres/deploy.ps1, redis/deploy.ps1) so the parsing logic lives in one place.

.DESCRIPTION
    Dot-source this file from a deploy script, then call Get-EnvValue. From a script under a
    sibling directory (e.g. postgres/):

        . (Join-Path $PSScriptRoot "..\scripts\get-env-value.ps1")
        $pgUser = Get-EnvValue -EnvFile $EnvFile -Name "POSTGRES_USER" -Default "magicboto"

    Matches the last non-commented "NAME=value" line for $Name; returns $Default if absent.
#>

function Get-EnvValue {
    param(
        [Parameter(Mandatory)] [string]$EnvFile,
        [Parameter(Mandatory)] [string]$Name,
        [string]$Default
    )
    $line = Get-Content $EnvFile | Where-Object { $_ -match "^\s*$Name\s*=" } | Select-Object -Last 1
    if (-not $line) { return $Default }
    return ($line -split "=", 2)[1].Trim()
}
