[CmdletBinding()]
param([ValidateSet('SAFE','NORMAL','AGGRESSIVE')][string]$Mode = 'AGGRESSIVE')

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repo ".venv\Scripts\python.exe"

Write-Host "======================================================================"
Write-Host "  ATS CONNECTED PRE-MARKET READINESS CHECKER"
Write-Host "======================================================================"

$env:PYTHONPATH = Join-Path $repo 'backend\src'
& $python -m ats.trading_runtime.readiness_cli --mode $Mode
$readinessExit = $LASTEXITCODE

if ($readinessExit -eq 0) {
    Write-Host "======================================================================"
    Write-Host "STATUS VERDICT: READY_FOR_A2_PAPER_SESSION"
    exit 0
} elseif ($readinessExit -eq 2) {
    Write-Host "======================================================================"
    Write-Host "STATUS VERDICT: READY_WITH_WARNINGS"
    exit 2
} elseif ($readinessExit -eq 3) {
    Write-Host "======================================================================"
    Write-Host "STATUS VERDICT: BLOCKED_RECONCILIATION_REQUIRED"
    exit 3
} else {
    Write-Host "======================================================================"
    Write-Host "STATUS VERDICT: BLOCKED_READINESS_FAILED"
    exit 1
}
