# Load repo .env into the current process and set PG* from POSTGRES_* so psql/pg_dump need no connection args.
# Run from repo root: . .\db\scripts\load-db-env.ps1   (dot-source so vars stay in your session)
# Then: psql   or   pg_dump -s -f db/schema.sql

$ErrorActionPreference = "Stop"
$RepoRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
. (Join-Path $RepoRoot "scripts\load-env.ps1")
$EnvFile = Join-Path $RepoRoot ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Warning "No .env at repo root. Copy .env.example to .env first."
    return
}
# Set PG* from POSTGRES_* so psql/pg_dump use these with no connection args (single source of truth)
$env:PGHOST     = if ($env:POSTGRES_HOST) { $env:POSTGRES_HOST } else { "localhost" }
$env:PGPORT     = if ($env:POSTGRES_PORT) { $env:POSTGRES_PORT } else { "5432" }
$env:PGUSER     = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "magicboto" }
$env:PGDATABASE = if ($env:POSTGRES_DB)   { $env:POSTGRES_DB }   else { "magicboto" }
$env:PGPASSWORD = if ($env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD } else { "magicboto" }
Write-Host "DB env loaded (PGHOST=$env:PGHOST, PGDATABASE=$env:PGDATABASE)."