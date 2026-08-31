[CmdletBinding()]
param(
    [string]$HarnessRoot = 'D:\Projects\ATS\tools\deepseek-harness',
    [string]$NodeRoot = 'D:\Projects\ATS\toolchains\node-v24.19.0-win-x64',
    [switch]$RequireToken = $false,
    [string]$Mode = 'AGGRESSIVE'
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$stateRoot = Join-Path $env:TEMP 'ats-a2-live-paper'
$stateFile = Join-Path $stateRoot 'processes.json'
$node = Join-Path $NodeRoot 'node.exe'
$corepack = Join-Path $NodeRoot 'corepack.cmd'
$harnessBin = Join-Path $HarnessRoot 'packages\examples\acp-demo\lib\bin.js'
$sessionId = [guid]::NewGuid().ToString()
$acceptancePath = Join-Path $repo 'data\runtime\pre_market_acceptance.json'

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " ATS A2 LIVE-PAPER MARKET-OPEN LAUNCHER (READ-ONLY MARKET DATA)" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " Execution Target : PaperBrokerAdapter (ONLY)" -ForegroundColor Green
Write-Host " Live Money       : DISABLED (STRICT INVARIANT)" -ForegroundColor Green
Write-Host " Real Orders      : 0 (IMPOSSIBLE)" -ForegroundColor Green
Write-Host " Harness          : ADVISORY_ONLY (GOVERNOR-GATED)" -ForegroundColor Green
Write-Host " Mode             : $Mode" -ForegroundColor Green
Write-Host "----------------------------------------------------------------" -ForegroundColor Gray

if (-not (Test-Path -LiteralPath $node)) { throw 'NODE_BINARY_MISSING' }
if ((& $node --version).Trim() -ne 'v24.19.0') { throw 'NODE_VERSION_MISMATCH' }
$pnpmJs = Join-Path $env:APPDATA 'npm\node_modules\pnpm\bin\pnpm.mjs'
if (-not (Test-Path -LiteralPath $pnpmJs)) { throw 'PNPM_BINARY_MISSING' }
if ((& $node $pnpmJs --version).Trim() -ne '11.9.0') { throw 'PNPM_VERSION_MISMATCH' }
if (-not (Test-Path -LiteralPath $harnessBin)) { throw 'HARNESS_BINARY_MISSING' }
if ((& git -C $HarnessRoot rev-parse HEAD).Trim() -ne 'b150a551b8d465e31e418e1b2eaf5e79bbb7d28e') { throw 'HARNESS_COMMIT_MISMATCH' }
$hasToken = -not [string]::IsNullOrWhiteSpace($env:ATS_UPSTOX_ACCESS_TOKEN)
if ($RequireToken -and -not $hasToken) { throw 'ATS_UPSTOX_ACCESS_TOKEN_REQUIRED_BUT_MISSING' }
$existing = @(Get-NetTCPConnection -State Listen -LocalPort 8000,3000 -ErrorAction SilentlyContinue)
if ($existing.Count -gt 0) { throw 'ATS_PORT_ALREADY_IN_USE' }
if (Test-Path -LiteralPath $stateFile) { throw 'ATS_STATE_FILE_ALREADY_EXISTS' }
if (-not (Test-Path -LiteralPath $acceptancePath)) { throw 'STAGE1_DURABLE_EVIDENCE_MISSING' }
$acceptance = Get-Content -LiteralPath $acceptancePath -Raw | ConvertFrom-Json
$today = (Get-Date).ToString('yyyy-MM-dd')
$head = (& git -C $repo rev-parse HEAD).Trim()
if ($acceptance.verdict -ne 'READY_FOR_A2_PAPER_SESSION') { throw 'STAGE1_NOT_READY' }
if ($acceptance.trading_date -ne $today) { throw 'STAGE1_EVIDENCE_NOT_TODAY' }
if ($acceptance.source_commit -ne $head) { throw 'STAGE1_HEAD_MISMATCH' }
$env:Path = $NodeRoot + [IO.Path]::PathSeparator + $env:Path
$env:NEXT_PUBLIC_API_BASE_URL = 'http://127.0.0.1:8000'
$env:ATS_A2_SESSION_ID = $sessionId
$env:ATS_A2_EVIDENCE_ROOT = Join-Path $repo 'data\runtime\sessions'
$env:ATS_A2_RUNTIME_CHECKPOINT_PATH = Join-Path $stateRoot 'runtime_checkpoint.json'
$env:ATS_A2_STAGE1_EVIDENCE_PATH = $acceptancePath
$env:ATS_SOURCE_COMMIT = $head
New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null

# 1. Launch Backend A2 Paper Session (serves /v1/* including runtime/harness/pipeline)
#    The backend manages the pinned DeepSeek Harness sidecar internally.
$backendArguments = @(
    'run', '--with', 'uvicorn==0.40.0', 'python', (Join-Path $repo 'scripts\run_a2_paper_session.py'),
    '--serve', '--host', '127.0.0.1', '--port', '8000', '--mode', $Mode
)
if ($RequireToken) { $backendArguments += '--require-token' }
$backend = Start-Process -FilePath 'uv' -ArgumentList $backendArguments -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput (Join-Path $stateRoot 'backend.out.log') `
  -RedirectStandardError (Join-Path $stateRoot 'backend.err.log')

# 2. Launch Next.js Control Center frontend
$pnpmJs = Join-Path $env:APPDATA 'npm\node_modules\pnpm\bin\pnpm.mjs'
$frontend = Start-Process -FilePath $node -ArgumentList @(
    $pnpmJs, '--filter', '@ats/control-center', 'exec', 'next', 'start', '-p', '3000', '-H', '127.0.0.1'
) -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput (Join-Path $stateRoot 'frontend.out.log') `
  -RedirectStandardError (Join-Path $stateRoot 'frontend.err.log')

@{
    backend = $backend.Id
    frontend = $frontend.Id
    started_at = (Get-Date).ToUniversalTime().ToString('o')
    execution_target = 'PAPER'
    live_money = 'DISABLED'
    real_orders_placed = 0
    session_id = $sessionId
    evidence_root = $env:ATS_A2_EVIDENCE_ROOT
    runtime_checkpoint_path = $env:ATS_A2_RUNTIME_CHECKPOINT_PATH
} | ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding utf8

$deadline = (Get-Date).AddSeconds(45)
do {
    Start-Sleep -Milliseconds 500
    $backendReady = $false
    $frontendReady = $false
    try { $backendReady = (Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health/live' -TimeoutSec 2).status -eq 'LIVE' } catch {}
    try { $frontendReady = (Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:3000/' -TimeoutSec 2).StatusCode -eq 200 } catch {}
} while ((-not $backendReady -or -not $frontendReady) -and (Get-Date) -lt $deadline)
if (-not $backendReady -or -not $frontendReady) { throw 'ATS_STARTUP_HEALTH_TIMEOUT' }

function Get-ListenerOwner([int]$Port) {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    if ($listeners.Count -ne 1) { throw "EXPECTED_ONE_LISTENER_ON_PORT_$Port" }
    return [int]$listeners[0].OwningProcess
}

try {
    @{
        backend = Get-ListenerOwner 8000
        frontend = Get-ListenerOwner 3000
        backend_launcher = $backend.Id
        frontend_launcher = $frontend.Id
        started_at = (Get-Date).ToUniversalTime().ToString('o')
        execution_target = 'PAPER'
        live_money = 'DISABLED'
        real_orders_placed = 0
        session_id = $sessionId
        evidence_root = $env:ATS_A2_EVIDENCE_ROOT
        runtime_checkpoint_path = $env:ATS_A2_RUNTIME_CHECKPOINT_PATH
    } | ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding utf8
} catch {
    Write-Warning "Listeners initializing..."
}

Write-Host "----------------------------------------------------------------" -ForegroundColor Gray
Write-Host " Control Center UI     : http://127.0.0.1:3000" -ForegroundColor Cyan
Write-Host " Runtime API           : http://127.0.0.1:8000/v1/runtime/status" -ForegroundColor Cyan
Write-Host " Harness API (Advisory): http://127.0.0.1:8000/v1/harness/status" -ForegroundColor Cyan
Write-Host " Pipeline Counters     : http://127.0.0.1:8000/v1/pipeline/counters" -ForegroundColor Cyan
Write-Host "----------------------------------------------------------------" -ForegroundColor Gray

& (Join-Path $PSScriptRoot 'check_ats_a2_live_paper.ps1') -StateFile $stateFile
