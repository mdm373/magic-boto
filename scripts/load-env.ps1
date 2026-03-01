# Load repo root .env into the current process. Dot-source from other scripts:
#   $RepoRoot = (Get-Item $PSScriptRoot).Parent.FullName   # when called from repo/scripts
#   . (Join-Path $RepoRoot "scripts\load-env.ps1")
# Or from a subproject: $RepoRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName then . (Join-Path $RepoRoot "scripts\load-env.ps1")

$ErrorActionPreference = "Stop"
$RepoRoot = (Get-Item $PSScriptRoot).Parent.FullName
$EnvFile = Join-Path $RepoRoot ".env"
if (-not (Test-Path $EnvFile)) {
    return
}
Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        $key = $matches[1].Trim()
        $val = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($key, $val, "Process")
    }
}
