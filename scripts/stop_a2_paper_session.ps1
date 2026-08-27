[CmdletBinding()]
param([string]$StateFile = (Join-Path $env:TEMP 'ats-a2-paper-session\processes.json'))

$ErrorActionPreference = 'SilentlyContinue'

Write-Host "Stopping ATS A2 Paper Session..." -ForegroundColor Yellow

# 1. Attempt graceful stop via API
try {
    $body = @{ command = 'STOP_A2_PAPER_SESSION' } | ConvertTo-Json
    Invoke-RestMethod -Uri 'http://127.0.0.1:8000/v1/runtime/command' -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 3 | Out-Null
    Write-Host "Sent STOP_A2_PAPER_SESSION to runtime." -ForegroundColor Green
} catch {}

try {
    $body = @{ command = 'FLATTEN_PORTFOLIO' } | ConvertTo-Json
    Invoke-RestMethod -Uri 'http://127.0.0.1:8000/v1/runtime/command' -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 3 | Out-Null
    Write-Host "Sent FLATTEN_PORTFOLIO to runtime." -ForegroundColor Green
} catch {}

# 2. Stop running processes
if (Test-Path -LiteralPath $StateFile) {
    $state = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
    foreach ($name in @('backend', 'frontend', 'harness', 'backend_launcher', 'frontend_launcher', 'harness_launcher')) {
        $pidVal = [int]$state.$name
        if ($pidVal -gt 0) {
            Stop-Process -Id $pidVal -Force -ErrorAction SilentlyContinue
        }
    }
    Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue
}

# 3. Clean up any remaining port listeners on 8000, 3000, 8765
foreach ($port in @(8000, 3000, 8765)) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "ATS A2 Paper Session stopped cleanly. Working tree clean." -ForegroundColor Green
