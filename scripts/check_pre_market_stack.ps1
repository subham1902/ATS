# ATS Pre-Market Readiness Checker (Target Date: 2026-08-31)

$ErrorActionPreference = "Stop"
$repo = "D:\Projects\ATS\worktrees\final-a2-integration"
$python = Join-Path $repo ".venv\Scripts\python.exe"

Write-Host "======================================================================"
Write-Host "  ATS PRE-MARKET READINESS CHECKER - MONDAY 2026-08-31"
Write-Host "======================================================================"

$env:PYTHONPATH = $repo
& $python -m ats.trading_runtime.readiness_cli

if ($LASTEXITCODE -eq 0) {
    Write-Host "======================================================================"
    Write-Host "STATUS VERDICT: READY_FOR_A2_PAPER_SESSION"
    exit 0
} else {
    Write-Host "======================================================================"
    Write-Host "STATUS VERDICT: BLOCKED_READINESS_FAILED"
    exit 1
}
