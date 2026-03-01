# Configure ChatRaw default chat model via its API so you don't have to set it in the UI.
# Run from repo root after: docker compose up -d
# Requires: .env with CHATRAW_DEFAULT_MODEL_ID (optional; default below).
# The API URL is fixed for the Docker stack: UI container calls the api service at http://api:8000/openapi/v1.

$ErrorActionPreference = "Stop"
$RepoRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
. (Join-Path $RepoRoot "scripts\load-env.ps1")

$baseUrl = if ($env:UI_BASE_URL) { $env:UI_BASE_URL.TrimEnd('/') } else { "http://localhost:8080" }
$apiUrl = if ($env:OPENAPI_BASE_URL) { $env:OPENAPI_BASE_URL.TrimEnd('/') } else { "http://api:8000/openapi/v1" }
$modelId = [Environment]::GetEnvironmentVariable("CHATRAW_DEFAULT_MODEL_ID", "Process")
if (-not $modelId) { $modelId = "default" }

$body = @{
    id              = "default-chat"
    name            = "Magic Boto"
    api_key         = ""
    api_url         = $apiUrl
    model_id        = $modelId
    context_length  = 32768
    max_output      = 4096
    type            = "chat"
    capability      = @{ vision = $false; reasoning = $false; tools = $true }
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "$baseUrl/api/models" -Method Post -Body $body -ContentType "application/json"
    Write-Host "ChatRaw default chat model set: api_url=$apiUrl, model_id=$modelId"
} catch {
    Write-Error "Failed to configure ChatRaw. Is the UI running? (docker compose up -d). Error: $_"
    exit 1
}
