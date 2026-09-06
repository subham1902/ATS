# PAPER_FORWARD launcher invoked by ats-start (read-only market data).
# Preserves every trading-safety invariant: PaperBrokerAdapter only, live money
# DISABLED, real orders impossible, A04/risk gates untouched. Stage-1 date and
# calendar checks are enforced by ats.trading_runtime.startup (auto-refresh on
# trading days); this script only maps its explicit exit codes to
# human-readable output and proceeds to PaperForwardRunner eligibility.
[CmdletBinding()]
param(
    [string]$EvidencePath = '',
    [string]$LockPath = '',
    [string]$Mode = 'AGGRESSIVE'
)

$ErrorActionPreference = 'Continue'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

Write-Host '================================================================' -ForegroundColor Cyan
Write-Host ' ATS A2 LIVE-PAPER MARKET-OPEN LAUNCHER (READ-ONLY MARKET DATA)' -ForegroundColor Cyan
Write-Host '================================================================' -ForegroundColor Cyan
Write-Host ' Execution Target : PaperBrokerAdapter (ONLY)' -ForegroundColor Green
Write-Host ' Live Money       : DISABLED (STRICT INVARIANT)' -ForegroundColor Green
Write-Host ' Real Orders      : 0 (IMPOSSIBLE)' -ForegroundColor Green
Write-Host " Mode             : $Mode" -ForegroundColor Green
Write-Host '----------------------------------------------------------------' -ForegroundColor Gray

$startupArgs = @('run', '--directory', $repo, 'python', '-m', 'ats.trading_runtime.startup')
if ($EvidencePath -ne '') { $startupArgs += @('--evidence-path', $EvidencePath) }
if ($LockPath -ne '') { $startupArgs += @('--lock-path', $LockPath) }

& uv @startupArgs
$code = $LASTEXITCODE
if ($code -eq 0) {
    Write-Host '----------------------------------------------------------------' -ForegroundColor Gray
    Write-Host ' PAPER_FORWARD startup decision recorded above.' -ForegroundColor Cyan
    Write-Host ' When status is STARTED, construct PaperForwardRunner with' -ForegroundColor Cyan
    Write-Host ' execution_mode=PAPER (paper broker path only).' -ForegroundColor Cyan
    exit 0
}
if ($code -eq 2) {
    Write-Host 'Launcher stopped: ATS_UPSTOX_ACCESS_TOKEN missing. Export a fresh token and re-run ats-start.' -ForegroundColor Red
    exit 2
}
if ($code -eq 3) {
    Write-Host 'Launcher refused: PAPER-only invariant violated. Live broker writes stay disabled.' -ForegroundColor Red
    exit 3
}
Write-Host 'Launcher failed closed: Stage-1 evidence invalid and not safely regenerable.' -ForegroundColor Red
exit 4
