[CmdletBinding()]
param(
    [string]$HarnessRoot = 'D:\Projects\ATS\tools\deepseek-harness',
    [string]$NodeRoot = 'D:\Projects\ATS\toolchains\node-v24.19.0-win-x64',
    [switch]$RequireToken = $false
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$stateRoot = Join-Path $env:TEMP 'ats-a2-live-paper'
$stateFile = Join-Path $stateRoot 'processes.json'
$node = Join-Path $NodeRoot 'node.exe'
$corepack = Join-Path $NodeRoot 'corepack.cmd'

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " ATS A2 LIVE-PAPER MARKET-OPEN LAUNCHER (READ-ONLY MARKET DATA)" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " Execution Target : PaperBrokerAdapter (ONLY)" -ForegroundColor Green
Write-Host " Live Money       : DISABLED (STRICT INVARIANT)" -ForegroundColor Green
Write-Host " Real Orders      : 0 (IMPOSSIBLE)" -ForegroundColor Green
Write-Host " Harness          : ADVISORY_ONLY (GOVERNOR-GATED)" -ForegroundColor Green
Write-Host "----------------------------------------------------------------" -ForegroundColor Gray

if (-not (Test-Path -LiteralPath $node)) { throw 'NODE_BINARY_MISSING' }
$env:Path = $NodeRoot + [IO.Path]::PathSeparator + $env:Path
$env:NEXT_PUBLIC_API_BASE_URL = 'http://127.0.0.1:8000'
New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null

# 1. Launch Backend A2 Paper Session (serves /v1/* including runtime/harness/pipeline)
$backend = Start-Process -FilePath 'uv' -ArgumentList @(
    'run', '--with', 'uvicorn==0.40.0', 'python', (Join-Path $repo 'scripts\run_a2_paper_session.py'),
    '--serve', '--host', '127.0.0.1', '--port', '8000'
) -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput (Join-Path $stateRoot 'backend.out.log') `
  -RedirectStandardError (Join-Path $stateRoot 'backend.err.log')

# 2. Launch Next.js Control Center frontend
$frontend = Start-Process -FilePath $corepack -ArgumentList @(
    'pnpm', '--filter', '@ats/control-center', 'exec', 'next', 'dev', '-p', '3000'
) -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput (Join-Path $stateRoot 'frontend.out.log') `
  -RedirectStandardError (Join-Path $stateRoot 'frontend.err.log')

# 3. Launch pinned DeepSeek Harness sidecar (advisory-only) into the A2 stack
$harness = Start-Process -FilePath 'uv' -ArgumentList @(
    'run', 'python', (Join-Path $repo 'scripts\start_a2_harness.py'),
    '--harness-root', $HarnessRoot, '--node', $node
) -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput (Join-Path $stateRoot 'harness.out.log') `
  -RedirectStandardError (Join-Path $stateRoot 'harness.err.log')

@{
    backend = $backend.Id
    frontend = $frontend.Id
    harness = $harness.Id
    started_at = (Get-Date).ToUniversalTime().ToString('o')
    execution_target = 'PAPER'
    live_money = 'DISABLED'
    real_orders_placed = 0
} | ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding utf8

Start-Sleep -Seconds 6

function Get-ListenerOwner([int]$Port) {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    if ($listeners.Count -ne 1) { throw "EXPECTED_ONE_LISTENER_ON_PORT_$Port" }
    return [int]$listeners[0].OwningProcess
}

try {
    @{
        backend = Get-ListenerOwner 8000
        frontend = Get-ListenerOwner 3000
        harness = Get-ListenerOwner 8765
        backend_launcher = $backend.Id
        frontend_launcher = $frontend.Id
        harness_launcher = $harness.Id
        started_at = (Get-Date).ToUniversalTime().ToString('o')
        execution_target = 'PAPER'
        live_money = 'DISABLED'
        real_orders_placed = 0
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
