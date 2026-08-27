[CmdletBinding()]
param(
    [string]$HarnessRoot = 'D:\Projects\ATS\tools\deepseek-harness',
    [string]$NodeRoot = 'D:\Projects\ATS\tools\node-v24.19.0-win-x64',
    [switch]$RequireToken = $false
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$stateRoot = Join-Path $env:TEMP 'ats-a2-paper-session'
$stateFile = Join-Path $stateRoot 'processes.json'
$node = Join-Path $NodeRoot 'node.exe'
$corepack = Join-Path $NodeRoot 'corepack.cmd'
$harnessBin = Join-Path $HarnessRoot 'packages\examples\acp-demo\lib\bin.js'

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " ATS A2 AUTONOMOUS PAPER SESSION LAUNCHER" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " Execution Target : PaperBrokerAdapter (ONLY)" -ForegroundColor Green
Write-Host " Live Money       : DISABLED (STRICT INVARIANT)" -ForegroundColor Green
Write-Host " Real Orders      : 0 (IMPOSSIBLE)" -ForegroundColor Green
Write-Host "----------------------------------------------------------------" -ForegroundColor Gray

# 1. Environment and tool verification
if ((& $node --version) -ne 'v24.19.0') { throw 'NODE_VERSION_MISMATCH' }
if ((& $corepack pnpm --version) -ne '11.9.0') { throw 'PNPM_VERSION_MISMATCH' }
if (-not (Test-Path -LiteralPath $harnessBin)) { throw 'HARNESS_BINARY_MISSING' }

# 2. Token verification without printing
$hasToken = -not [string]::IsNullOrWhiteSpace($env:ATS_UPSTOX_ACCESS_TOKEN)
if ($RequireToken -and -not $hasToken) {
    throw 'ATS_UPSTOX_ACCESS_TOKEN_REQUIRED_BUT_MISSING'
}
Write-Host " Upstox Access Token : $(if ($hasToken) { 'PRESENT (PROTECTED)' } else { 'OPTIONAL (TEST MODE)' })" -ForegroundColor Yellow

$env:Path = $NodeRoot + [IO.Path]::PathSeparator + $env:Path
$env:NEXT_PUBLIC_API_BASE_URL = 'http://127.0.0.1:8000'
New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null

# 3. Launch Backend with A2 Paper Session
$backend = Start-Process -FilePath 'uv' -ArgumentList @(
    'run', '--with', 'uvicorn==0.40.0', 'python', (Join-Path $repo 'scripts\run_a2_paper_session.py'),
    '--serve', '--host', '127.0.0.1', '--port', '8000'
) -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput (Join-Path $stateRoot 'backend.out.log') `
  -RedirectStandardError (Join-Path $stateRoot 'backend.err.log')

# 4. Launch Next.js Control Center frontend
$frontend = Start-Process -FilePath $corepack -ArgumentList @(
    'pnpm', '--filter', '@ats/control-center', 'exec', 'next', 'dev', '-p', '3000'
) -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput (Join-Path $stateRoot 'frontend.out.log') `
  -RedirectStandardError (Join-Path $stateRoot 'frontend.err.log')

# 5. Launch Intelligence Harness sidecar (Advisory only)
$harness = Start-Process -FilePath 'uv' -ArgumentList @(
    'run', 'python', (Join-Path $repo 'scripts\run_harness_sidecar.py'),
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
Write-Host " Operator Intelligence : http://127.0.0.1:3000/operator-intelligence" -ForegroundColor Cyan
Write-Host " Runtime API           : http://127.0.0.1:8000/v1/runtime/status" -ForegroundColor Cyan
Write-Host " Harness Sidecar (Adv) : http://127.0.0.1:8765/health" -ForegroundColor Cyan
Write-Host "----------------------------------------------------------------" -ForegroundColor Gray

& (Join-Path $PSScriptRoot 'check_a2_paper_session.ps1') -StateFile $stateFile
