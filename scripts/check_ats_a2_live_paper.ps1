[CmdletBinding()]
param(
    [string]$StateFile = (Join-Path $env:TEMP 'ats-a2-live-paper\processes.json')
)

$ErrorActionPreference = 'Continue'
$base = 'http://127.0.0.1:8000'

function Invoke-Json([string]$Path) {
    try {
        $resp = Invoke-RestMethod -Uri "$base$Path" -TimeoutSec 5 -ErrorAction Stop
        return $resp
    } catch {
        Write-Warning "GET $Path failed: $_"
        return $null
    }
}

Write-Host "== ATS A2 LIVE-PAPER INVARIANT CHECK ==" -ForegroundColor Cyan

$runtime = Invoke-Json '/v1/runtime/status'
$harness = Invoke-Json '/v1/harness/status'
$pipeline = Invoke-Json '/v1/pipeline/counters'
$health = Invoke-Json '/health/live'

$failures = @()

if ($null -eq $runtime) { $failures += 'RUNTIME_STATUS_UNREACHABLE' }
else {
    $realOrders = try { [int]$runtime.pnl.realized } catch { 0 }
    if ($runtime.session.phase -eq 'CLOSED') { Write-Host "MARKET CLOSED (acceptable pre-open) — phase=$($runtime.session.phase)" -ForegroundColor Yellow }
    if ($runtime.session.can_enter -and $runtime.session.phase -ne 'CLOSED') { Write-Host "SESSION OPEN can_enter=$($runtime.session.can_enter)" -ForegroundColor Green }
}

if ($null -eq $harness) { $failures += 'HARNESS_STATUS_UNREACHABLE' }
else {
    Write-Host "HARNESS state=$($harness.harness.state) active_sessions=$($harness.harness.active_sessions) live_money=$($harness.harness.live_money) execution_target=$($harness.harness.execution_target) real_orders_placed=$($harness.harness.real_orders_placed)" -ForegroundColor Green
    if ($harness.harness.live_money -ne 'DISABLED') { $failures += 'LIVE_MONEY_NOT_DISABLED' }
    if ($harness.harness.execution_target -ne 'PAPER') { $failures += 'EXECUTION_TARGET_NOT_PAPER' }
    if ([int]$harness.harness.real_orders_placed -ne 0) { $failures += 'REAL_ORDERS_PLACED' }
    if ($harness.safety.REAL_ORDER_AUTHORITY -ne 'NONE') { $failures += 'REAL_ORDER_AUTHORITY_NONZERO' }
}

if ($null -eq $pipeline) { $failures += 'PIPELINE_COUNTERS_UNREACHABLE' }
else {
    Write-Host "PIPELINE attached=$($pipeline.attached) nifty_last=$($pipeline.nifty_last) banknifty_last=$($pipeline.banknifty_last) candidates_qualified=$($pipeline.candidates_qualified)" -ForegroundColor Green
}

if ($null -eq $health) { $failures += 'HEALTH_UNREACHABLE' }
else { Write-Host "HEALTH live=$($health.status) ready=$($health.ready)" -ForegroundColor Green }

if ($failures.Count -eq 0) {
    Write-Host "ALL INVARIANTS HOLD: PAPER + LIVE_MONEY_DISABLED + REAL_ORDERS_0 + HARNESS_ADVISORY_ONLY" -ForegroundColor Green
    exit 0
} else {
    Write-Host "INVARIANT FAILURES: $($failures -join ', ')" -ForegroundColor Red
    exit 1
}
