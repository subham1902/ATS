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
$acceptancePath = Join-Path $repo 'data\runtime\pre_market_acceptance.json'
$acceptanceDir = Split-Path -Parent $acceptancePath
New-Item -ItemType Directory -Force -Path $acceptanceDir | Out-Null

if ($readinessExit -eq 0) {
    $acceptance = [ordered]@{
        schema_version = '1.0'
        verdict = 'READY_FOR_A2_PAPER_SESSION'
        checked_at = (Get-Date).ToUniversalTime().ToString('o')
        trading_date = (Get-Date).ToString('yyyy-MM-dd')
        source_commit = (& git -C $repo rev-parse HEAD).Trim()
        mode = $Mode
        live_money = 'DISABLED'
        execution_target = 'PAPER'
        real_broker_authority = $false
    }
    $canonical = $acceptance | ConvertTo-Json -Compress
    $acceptance['record_sha256'] = [Convert]::ToHexString(
        [Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($canonical))
    ).ToLowerInvariant()
    $acceptance | ConvertTo-Json | Set-Content -LiteralPath $acceptancePath -Encoding utf8
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
