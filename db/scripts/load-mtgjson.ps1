# Initial load of MTGJSON AllPrintings into Postgres from a local .psql file (or .zip / .gz).
# Run from repo root or from db/ with .env in repo root.
# Requires: psql on PATH, Postgres running (e.g. docker compose up -d).
# Loads into schema "mtgjson" so the catalog is separate from your tables. Preprocesses: id columns INT/INTEGER -> BIGINT.

$ErrorActionPreference = "Stop"

# Use shared env (POSTGRES_* / PG*) from load-db-env.ps1
$ScriptDir = Split-Path -Parent $PSScriptRoot
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
. (Join-Path $PSScriptRoot "load-db-env.ps1")

$workDir = Join-Path $RepoRoot "db\scripts"

# Prompt for path to .psql file or archive
Write-Host "Enter path to AllPrintings.psql, AllPrintings.psql.zip, or AllPrintings.psql.gz (local file):"
$inputPath = (Read-Host).Trim()
if ([string]::IsNullOrWhiteSpace($inputPath)) {
    Write-Error "No file path entered."
    exit 1
}
$inputPath = $inputPath -replace '"', ''
if (-not (Test-Path $inputPath)) {
    Write-Error "File not found: $inputPath"
    exit 1
}
$inputPath = (Resolve-Path $inputPath).Path

# Resolve to the actual .psql file (extract or decompress if needed)
$psqlPath = $null
$tempExtractDir = $null
$tempGzPath = $null

$ext = [System.IO.Path]::GetExtension($inputPath).ToLowerInvariant()
if ($ext -eq ".psql") {
    $psqlPath = $inputPath
}
elseif ($ext -eq ".zip") {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $tempExtractDir = Join-Path $workDir "mtgjson_extract"
    if (Test-Path $tempExtractDir) { Remove-Item $tempExtractDir -Recurse -Force }
    [System.IO.Compression.ZipFile]::ExtractToDirectory($inputPath, $tempExtractDir)
    $psqlFile = Get-ChildItem -Path $tempExtractDir -Filter "*.psql" -Recurse -File | Select-Object -First 1
    if (-not $psqlFile) {
        Write-Error "No .psql file found inside the zip."
        exit 1
    }
    $psqlPath = $psqlFile.FullName
}
elseif ($ext -eq ".gz") {
    Write-Host "Decompressing .gz..."
    $tempGzPath = Join-Path $workDir "AllPrintings.psql"
    $inStream = [System.IO.File]::OpenRead($inputPath)
    $gzip = [System.IO.Compression.GZipStream]::new($inStream, [System.IO.Compression.CompressionMode]::Decompress)
    $outStream = [System.IO.File]::Create($tempGzPath)
    $gzip.CopyTo($outStream)
    $outStream.Close()
    $gzip.Close()
    $inStream.Close()
    $psqlPath = $tempGzPath
}
else {
    Write-Error "Unsupported format. Use .psql, .zip, or .gz"
    exit 1
}

# Preprocess: run in mtgjson schema + INT/INTEGER -> BIGINT for id columns
$tempSql = Join-Path $workDir "AllPrintings_postgres.psql"
Write-Host "Preparing for Postgres (mtgjson schema + all INT/INTEGER -> BIGINT)..."
$content = [System.IO.File]::ReadAllText($psqlPath)
# Run entire dump under mtgjson schema so catalog is separate from your tables (e.g. public.inventory)
$schemaHeader = @"
CREATE SCHEMA IF NOT EXISTS mtgjson;
SET search_path TO mtgjson;

"@
$content = $schemaHeader + $content
# Upgrade all INTEGER/INT to BIGINT (dump has large values e.g. sheetTotalWeight that overflow int4)
$content = $content -replace '(?i)\bINTEGER\b', 'BIGINT'
$content = $content -replace '(?i)\bINT\b', 'BIGINT'
[System.IO.File]::WriteAllText($tempSql, $content)

# Cleanup extracted/decompressed temp (not the preprocessed file)
if ($tempExtractDir -and (Test-Path $tempExtractDir)) { Remove-Item $tempExtractDir -Recurse -Force -ErrorAction SilentlyContinue }
if ($tempGzPath -and (Test-Path $tempGzPath)) { Remove-Item $tempGzPath -Force -ErrorAction SilentlyContinue }

try {
    $env:PGCLIENTENCODING = "UTF8"
    Write-Host "Loading into Postgres ($env:PGHOST`:$env:PGPORT / $env:PGDATABASE)..."
    & psql -h $env:PGHOST -p $env:PGPORT -U $env:PGUSER -d $env:PGDATABASE -f $tempSql -v ON_ERROR_STOP=1
}
finally {
    $env:PGPASSWORD = $null
    $env:PGCLIENTENCODING = $null
    if (Test-Path $tempSql) { Remove-Item $tempSql -Force -ErrorAction SilentlyContinue }
}
$psqlExit = $LASTEXITCODE

if ($psqlExit -ne 0) { exit $psqlExit }
Write-Host "Initial load complete."
