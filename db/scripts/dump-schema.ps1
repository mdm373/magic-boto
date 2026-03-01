# Dump the current database schema (no data) to db/schema.sql.
# Run from repo root: .\db\scripts\dump-schema.ps1
# Requires: pg_dump on PATH; .env at repo root (or load-db-env.ps1 will warn).

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "load-db-env.ps1")

$DbDir      = Split-Path -Parent $PSScriptRoot
$SchemaFile = Join-Path $DbDir "schema.sql"
Write-Host "Dumping schema to $SchemaFile ..."
$env:PGCLIENTENCODING = "UTF8"
&  C:\Progra~1\PostgreSQL\16\bin\pg_dump -s -f $SchemaFile
if ($LASTEXITCODE -ne 0) {
    Write-Error "pg_dump failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
Write-Host "Done. Schema written to $SchemaFile"
