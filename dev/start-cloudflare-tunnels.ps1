<#
.SYNOPSIS
    Starts Cloudflare quick tunnels for local Keycloak (via keycloak_public_proxy) and
    tools_mcp, so a real device (e.g. Claude mobile/desktop custom connector) can reach them
    over the internet without a public deployment.

.DESCRIPTION
    Requires `cloudflared` on PATH: winget install --id Cloudflare.cloudflared
    Tunnels are ephemeral — each run gets new random *.trycloudflare.com hostnames. Leave this
    script running for the duration of your test; Ctrl+C stops both tunnels.

    Tunnels the keycloak_public_proxy port (8181), never Keycloak's own port (8180) — that
    proxy blocks /admin* and /realms/master* so the admin console is never reachable through
    the tunnel. See docker-compose.yml / AGENTS.md for why.

.PARAMETER KeycloakProxyPort
    Local port of keycloak_public_proxy (KEYCLOAK_PUBLIC_LOCAL_PORT in .env). Default 8181.

.PARAMETER McpPort
    Local port of tools_mcp (TOOLS_MCP_LOCAL_PORT in .env). Default 8765.
#>

[CmdletBinding()]
param(
    [int]$KeycloakProxyPort = 8181,
    [int]$McpPort = 8765
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Error "cloudflared not found on PATH. Install with: winget install --id Cloudflare.cloudflared"
    exit 1
}

$logDir = Join-Path $PSScriptRoot ".tunnel-logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Start-QuickTunnel {
    param([int]$Port, [string]$Name)

    $outLog = Join-Path $logDir "$Name.out.log"
    $errLog = Join-Path $logDir "$Name.err.log"
    Remove-Item $outLog, $errLog -ErrorAction SilentlyContinue

    $proc = Start-Process -FilePath "cloudflared" `
        -ArgumentList "tunnel", "--url", "http://localhost:$Port" `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog `
        -NoNewWindow -PassThru

    [pscustomobject]@{ Process = $proc; OutLog = $outLog; ErrLog = $errLog }
}

function Wait-ForTunnelUrl {
    param([pscustomobject]$Tunnel, [int]$TimeoutSeconds = 30)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        foreach ($logPath in @($Tunnel.ErrLog, $Tunnel.OutLog)) {
            if (Test-Path $logPath) {
                $match = Select-String -Path $logPath -Pattern "https://[a-zA-Z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue |
                    Select-Object -First 1
                if ($match) {
                    return $match.Matches[0].Value
                }
            }
        }
        if ($Tunnel.Process.HasExited) {
            throw "cloudflared exited before a tunnel URL appeared; check $($Tunnel.ErrLog)"
        }
        Start-Sleep -Milliseconds 500
    }
    throw "Timed out waiting for tunnel URL; check $($Tunnel.ErrLog)"
}

Write-Host "Starting Cloudflare quick tunnels..." -ForegroundColor Cyan
$keycloakTunnel = Start-QuickTunnel -Port $KeycloakProxyPort -Name "keycloak"
$mcpTunnel = Start-QuickTunnel -Port $McpPort -Name "mcp"

try {
    $keycloakUrl = Wait-ForTunnelUrl -Tunnel $keycloakTunnel
    $mcpUrl = Wait-ForTunnelUrl -Tunnel $mcpTunnel

    Write-Host ""
    Write-Host "Keycloak (via keycloak_public_proxy): $keycloakUrl" -ForegroundColor Green
    Write-Host "tools_mcp:                            $mcpUrl" -ForegroundColor Green
    Write-Host ""
    Write-Host "Set these in .env, then: docker compose up -d keycloak tools_mcp" -ForegroundColor Yellow
    Write-Host "  TOOLS_MCP_AUTH_ENABLED=true"
    Write-Host "  KEYCLOAK_ISSUER_URL=$keycloakUrl/realms/magic-boto"
    Write-Host "  TOOLS_MCP_RESOURCE_SERVER_URL=$mcpUrl"
    Write-Host ""
    Write-Host "Claude custom connector MCP Server URL: $mcpUrl/mcp" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Tunnels running - press Ctrl+C to stop." -ForegroundColor Cyan

    while ($true) {
        Start-Sleep -Seconds 5
        if ($keycloakTunnel.Process.HasExited -or $mcpTunnel.Process.HasExited) {
            Write-Warning "A tunnel process exited unexpectedly; check logs in $logDir"
            break
        }
    }
}
finally {
    Write-Host "Stopping tunnels..." -ForegroundColor Cyan
    foreach ($tunnel in @($keycloakTunnel, $mcpTunnel)) {
        if ($tunnel -and -not $tunnel.Process.HasExited) {
            Stop-Process -Id $tunnel.Process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
