[CmdletBinding()]
param([string]$StateFile = (Join-Path $env:TEMP 'ats-a2-paper-session\processes.json'))

$ErrorActionPreference = 'Stop'
$result = [ordered]@{
    status = 'NOT_READY'
    backend = 'OFFLINE'
    frontend = 'OFFLINE'
    harness = 'OFFLINE'
    session_state = 'UNKNOWN'
    execution_target = 'PAPER'
    live_money = 'DISABLED'
    real_orders_placed = 0
}

if (Test-Path -LiteralPath $StateFile) {
    $state = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
    foreach ($name in @('backend', 'frontend', 'harness')) {
        if ($null -ne (Get-Process -Id ([int]$state.$name) -ErrorAction SilentlyContinue)) {
            $result[$name] = 'PROCESS_RUNNING'
        }
    }
}

try {
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health/live' -TimeoutSec 3
    if ($health.status -eq 'LIVE') { $result.backend = 'HEALTHY' }
} catch {}

try {
    $runtime = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/v1/runtime/status' -TimeoutSec 3
    if ($null -ne $runtime) {
        $result.session_state = $runtime.session.phase
    }
} catch {}

try {
    $response = Invoke-WebRequest -Uri 'http://127.0.0.1:3000' -TimeoutSec 5 -UseBasicParsing
    if ($response.StatusCode -eq 200) { $result.frontend = 'HEALTHY' }
} catch {}

try {
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 3
    if ($health.status -eq 'HEALTHY') { $result.harness = 'HEALTHY' }
} catch {}

if ($result.backend -eq 'HEALTHY' -and $result.frontend -eq 'HEALTHY' -and $result.harness -eq 'HEALTHY') {
    $result.status = 'READY'
} elseif ($result.backend -ne 'OFFLINE' -or $result.frontend -ne 'OFFLINE' -or $result.harness -ne 'OFFLINE') {
    $result.status = 'DEGRADED'
}

$result | ConvertTo-Json -Compress
