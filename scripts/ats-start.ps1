# Hardened ats-start entrypoint (paper forward only).
# Delegates session-state + Stage-1 decisions to the Python source of truth
# (backend/src/ats/trading_runtime/startup.py) so PowerShell never duplicates
# date/calendar logic. Normal operational states exit 0 with human-readable
# output; only genuine safety failures exit non-zero. No raw `throw` for
# market-not-open / closed / weekend / holiday / waiting states.
[CmdletBinding()]
param(
    [string]$EvidencePath = '',
    [string]$LockPath = '',
    [switch]$NoOpen
)

$ErrorActionPreference = 'Continue'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

Write-Host 'ATS pre-flight' -ForegroundColor Cyan

$token = $env:ATS_UPSTOX_ACCESS_TOKEN
if ([string]::IsNullOrWhiteSpace($token)) {
    $userToken = [Environment]::GetEnvironmentVariable('ATS_UPSTOX_ACCESS_TOKEN', 'User')
    if (-not [string]::IsNullOrWhiteSpace($userToken)) {
        $env:ATS_UPSTOX_ACCESS_TOKEN = $userToken
        $token = $userToken
    }
}
if ([string]::IsNullOrWhiteSpace($token)) {
    Write-Host '  Upstox token       MISSING' -ForegroundColor Red
    Write-Host '  Remediation        : complete Upstox OAuth, export ATS_UPSTOX_ACCESS_TOKEN, then re-run ats-start.' -ForegroundColor Yellow
    Write-Host '  Authentication is never bypassed.' -ForegroundColor Yellow
    exit 2
}
Write-Host '  Upstox token       PRESENT (protected)' -ForegroundColor Green
Write-Host '  PaperBrokerAdapter ONLY' -ForegroundColor Green
Write-Host '  Live money         DISABLED (STRICT INVARIANT)' -ForegroundColor Green
Write-Host '  Real orders        0 (IMPOSSIBLE)' -ForegroundColor Green

$startupArgs = @('run', '--directory', $repo, 'python', '-m', 'ats.trading_runtime.startup')
if ($EvidencePath -ne '') { $startupArgs += @('--evidence-path', $EvidencePath) }
if ($LockPath -ne '') { $startupArgs += @('--lock-path', $LockPath) }

& uv @startupArgs
$code = $LASTEXITCODE
if ($code -eq 0) {
    Write-Host 'ats-start finished with an operational status (see above).' -ForegroundColor Cyan
    exit 0
}
if ($code -eq 2) {
    Write-Host 'ats-start stopped: Upstox authorization missing. See remediation above.' -ForegroundColor Red
    exit 2
}
if ($code -eq 3) {
    Write-Host 'ats-start refused: PAPER-only invariant violated. Live writes are prohibited.' -ForegroundColor Red
    exit 3
}
Write-Host 'ats-start failed closed on Stage-1 evidence. Inspect the reason above.' -ForegroundColor Red
exit 4
