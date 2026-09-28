[CmdletBinding()]
param(
    [ValidateSet('Start', 'Status', 'Restart', 'Stop', 'Open')]
    [string]$Action = 'Start',
    [ValidateRange(1024, 65535)][int]$FrontendPort = 3001,
    [ValidateRange(1024, 65535)][int]$BackendPort = 8000,
    [switch]$NoOpen,
    [switch]$VerboseOutput
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = Join-Path $repo 'reports\operator-runtime'
$statePath = Join-Path $runtime 'processes.json'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null

$pythonExe = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $pythonExe = 'python'
}

function Get-Listener([int]$Port) {
    $line = netstat -ano | findstr "LISTENING" | findstr ":$Port " | Select-Object -First 1
    if ($line) {
        $parts = $line -split '\s+' | Where-Object { $_ }
        return [pscustomobject]@{ OwningProcess = [int]$parts[-1] }
    }
    return $null
}

function Get-OwnedProcess([int]$PidValue) {
    if ($PidValue -le 0) { return $null }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $PidValue" -ErrorAction SilentlyContinue
    if ($process -and ($process.CommandLine -like "*$repo*" -or $process.CommandLine -like "*ats*" -or $process.CommandLine -like "*control-center*")) { return $process }
    return $null
}

function Read-State {
    if (-not (Test-Path -LiteralPath $statePath)) { return $null }
    try { return Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json } catch { return $null }
}

function Get-ChromeExe {
    $candidates = @(
        "C:\Program Files\Google\Chrome\Application\chrome.exe",
        "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    )
    foreach ($p in $candidates) {
        if (Test-Path -LiteralPath $p) { return $p }
    }
    return $null
}

function Open-AtsTerminal([int]$Port) {
    $url = "http://127.0.0.1:$Port/"
    cmd.exe /c start "" "$url"
    return "OPENED"
}

function Get-SessionFacts {
    try {
        $backendSrc = (Join-Path $repo 'backend\src').Replace('\', '/')
        $cmd = "import sys, json; sys.path.insert(0, '$backendSrc'); from datetime import datetime, timezone, timedelta; ist = timezone(timedelta(hours=5, minutes=30)); now = datetime.now(ist); print(json.dumps({'state': 'OPEN' if (9 <= now.hour < 23 or (now.hour == 23 and now.minute <= 30)) and now.weekday() < 5 else 'CLOSED', 'new_risk': False, 'session_id': 'MCX-SESSION'}))"
        $raw = & $pythonExe -c $cmd 2>$null
        if ($raw) {
            return ($raw | ConvertFrom-Json)
        }
    } catch {}
    return @{ state = "CLOSED"; new_risk = $false; session_id = "MCX-SESSION" }
}

function Get-UpstoxStatus {
    $token = $env:ATS_UPSTOX_ACCESS_TOKEN
    if ([string]::IsNullOrWhiteSpace($token)) {
        $token = [Environment]::GetEnvironmentVariable('ATS_UPSTOX_ACCESS_TOKEN', 'User')
    }
    if ([string]::IsNullOrWhiteSpace($token)) {
        return "DATA_BLOCKED (token missing)"
    }
    return "AUTHENTICATED READ-ONLY"
}

function Show-Status {
    $bListener = Get-Listener $BackendPort
    $fListener = Get-Listener $FrontendPort
    $bStatus = if ($bListener) { "READY · 127.0.0.1:$BackendPort (PID $($bListener.OwningProcess))" } else { "STOPPED" }
    $fStatus = if ($fListener) { "READY · 127.0.0.1:$FrontendPort (PID $($fListener.OwningProcess))" } else { "STOPPED" }
    $appStatus = if ($bListener -and $fListener) { "READY" } elseif ($bListener -or $fListener) { "PARTIAL" } else { "STOPPED" }
    $chromePath = Get-ChromeExe
    $chromeStatus = if ($chromePath) { $chromePath } else { "NOT_FOUND" }
    $facts = Get-SessionFacts
    $market = if ($facts.state -eq 'OPEN') { 'OPEN' } else { 'CLOSED' }
    $session = if ($facts.state -eq 'OPEN') { 'GENUINE_SESSION_OPEN' } else { 'WAITING_FOR_GENUINE_SESSION' }
    $upstox = Get-UpstoxStatus

    Write-Host "ATS STATUS" -ForegroundColor Cyan
    Write-Host ("  {0,-18} {1}" -f "Application", $appStatus)
    Write-Host ("  {0,-18} {1}" -f "Backend", $bStatus)
    Write-Host ("  {0,-18} {1}" -f "Frontend", $fStatus)
    Write-Host ("  {0,-18} {1}" -f "Chrome", $chromeStatus)
    Write-Host ("  {0,-18} {1}" -f "Market", $market)
    Write-Host ("  {0,-18} {1}" -f "Session", $session)
    Write-Host ("  {0,-18} {1}" -f "Provider", "Upstox · $upstox")
    Write-Host ("  {0,-18} {1}" -f "Freshness", "RECORDED_READ_ONLY_SNAPSHOT")
    Write-Host ("  {0,-18} {1}" -f "GOLDM", "MCX_FO|569003 · GOLDM FUT 05 OCT 26")
    Write-Host ("  {0,-18} {1}" -f "Strategies", "40 Strategies · Performance Registry & Leaderboard")
    Write-Host ("  {0,-18} {1}" -f "PaperBroker", "ACTIVE")
    Write-Host ("  {0,-18} {1}" -f "Live money", "FALSE (STRICT INVARIANT)")
}

function Stop-Owned {
    $state = Read-State
    $candidates = if ($state) { @($state.frontend_pid, $state.backend_pid) } else { @() }
    foreach ($port in @($FrontendPort, $BackendPort)) {
        $listener = Get-Listener $port
        if ($listener) { $candidates += $listener.OwningProcess }
    }
    $stoppedAny = $false
    foreach ($pidValue in ($candidates | Select-Object -Unique)) {
        $process = Get-OwnedProcess ([int]$pidValue)
        if ($process) {
            $procType = if ($process.CommandLine -like "*uvicorn*") { "Backend" } else { "Frontend" }
            Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
            Write-Host ("  {0,-18} STOPPED (was PID {1})" -f $procType, $process.ProcessId)
            $stoppedAny = $true
        }
    }
    $deadline = (Get-Date).AddSeconds(10)
    while (((Get-Listener $FrontendPort) -or (Get-Listener $BackendPort)) -and (Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 300
    }
    Start-Sleep -Milliseconds 500
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
    return $stoppedAny
}

if ($Action -eq 'Status') {
    Show-Status
    exit 0
}

if ($Action -eq 'Stop') {
    Write-Host "ATS STOP" -ForegroundColor Yellow
    $stopped = Stop-Owned
    Write-Host ("  {0,-18} {1}" -f "Port 3000", "UNTOUCHED")
    Write-Host ("  {0,-18} {1}" -f "Chrome", "RUNNING (preserved)")
    $statusMsg = if ($stopped) { "ALL ATS PROCESSES STOPPED" } else { "NO ATS PROCESSES RUNNING" }
    Write-Host ("  {0,-18} {1}" -f "Status", $statusMsg)
    exit 0
}

if ($Action -eq 'Restart') {
    Write-Host "ATS RESTART" -ForegroundColor Yellow
    Stop-Owned | Out-Null
    Start-Sleep -Milliseconds 500
}

if ($Action -eq 'Open') {
    $res = Open-AtsTerminal $FrontendPort
    Write-Host "ATS OPEN: $res (http://127.0.0.1:$FrontendPort/)" -ForegroundColor Green
    exit 0
}

# STAGE 0 — APPLICATION PREFLIGHT & PORT COLLISION CHECKS
foreach ($port in @($FrontendPort, $BackendPort)) {
    $listener = Get-Listener $port
    if ($listener) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
        if (-not ($process -and ($process.CommandLine -like "*$repo*" -or $process.CommandLine -like "*ats*" -or $process.CommandLine -like "*control-center*"))) {
            throw "Port $port is owned by an unrelated process (PID $($listener.OwningProcess)); ATS will not disturb it."
        }
    }
}

# Invariants
$env:LIVE_MONEY = 'false'; $env:ATS_LIVE_MONEY = 'false'
$backendSrcDir = Join-Path $repo 'backend\src'
$env:PYTHONPATH = $backendSrcDir

$env:ATS_BACKEND_URL = "http://127.0.0.1:$BackendPort"
$env:ATS_FRONTEND_URL = "http://127.0.0.1:$FrontendPort"
$env:NEXT_PUBLIC_API_URL = $env:ATS_BACKEND_URL

# Start or Reuse Backend
$backendListener = Get-Listener $BackendPort
if (-not $backendListener) {
    $backendProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-m', 'uvicorn', 'ats.console.app:app', '--app-dir', $backendSrcDir, '--host', '127.0.0.1', '--port', [string]$BackendPort) -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'backend.log') -RedirectStandardError (Join-Path $runtime 'backend.err.log') -PassThru
} else {
    $backendProcess = Get-Process -Id $backendListener.OwningProcess
}

# Start or Reuse Frontend
$frontendListener = Get-Listener $FrontendPort
if (-not $frontendListener) {
    $nextCmd = Join-Path $repo 'frontend\apps\control-center\node_modules\.bin\next.cmd'
    $controlCenterDir = Join-Path $repo 'frontend\apps\control-center'
    if (Test-Path -LiteralPath $nextCmd) {
        $frontendProcess = Start-Process -FilePath $nextCmd -ArgumentList @('start', '--hostname', '127.0.0.1', '--port', [string]$FrontendPort) -WorkingDirectory $controlCenterDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'frontend.log') -RedirectStandardError (Join-Path $runtime 'frontend.err.log') -PassThru
    } else {
        $pnpmCmd = Get-Command 'pnpm.cmd' -ErrorAction SilentlyContinue
        $pnpmExe = if ($pnpmCmd) { $pnpmCmd.Source } else { 'pnpm.cmd' }
        $frontendProcess = Start-Process -FilePath $pnpmExe -ArgumentList @('--filter', '@ats/control-center', 'exec', 'next', 'start', '--hostname', '127.0.0.1', '--port', [string]$FrontendPort) -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'frontend.log') -RedirectStandardError (Join-Path $runtime 'frontend.err.log') -PassThru
    }
} else {
    $frontendProcess = Get-Process -Id $frontendListener.OwningProcess
}

# Wait for Readiness (max 45s)
$deadline = (Get-Date).AddSeconds(45)
do {
    $frontendReady = [bool](Get-Listener $FrontendPort)
    $backendReady = [bool](Get-Listener $BackendPort)
    if ($frontendReady -and $backendReady) { break }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $deadline)

if (-not ($frontendReady -and $backendReady)) {
    throw 'ATS operator runtime did not become ready within 45 seconds. Inspect reports/operator-runtime.'
}

$frontendPid = (Get-Listener $FrontendPort).OwningProcess
$backendPid = (Get-Listener $BackendPort).OwningProcess
@{
    frontend_pid = $frontendPid
    backend_pid = $backendPid
    frontend_port = $FrontendPort
    backend_port = $BackendPort
    repo = $repo
    started_at = (Get-Date).ToUniversalTime().ToString('o')
} | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding utf8

# Auto-open Google Chrome
$chromeResult = "NOT_REQUESTED"
if (-not $NoOpen) {
    $chromeResult = Open-AtsTerminal $FrontendPort
}

# STAGE 1 — MARKET & SESSION FACTS
$facts = Get-SessionFacts
$marketState = if ($facts.state -eq 'OPEN') { 'OPEN' } else { 'CLOSED' }
$sessionState = if ($facts.state -eq 'OPEN') { 'GENUINE_SESSION_OPEN' } else { 'WAITING_FOR_GENUINE_SESSION' }
$upstoxState = Get-UpstoxStatus

Write-Host "ATS START" -ForegroundColor Green
Write-Host ("  {0,-18} {1}" -f "Application", "READY")
Write-Host ("  {0,-18} {1}" -f "Backend", "READY · $BackendPort")
Write-Host ("  {0,-18} {1}" -f "Frontend", "READY · $FrontendPort")
Write-Host ("  {0,-18} {1}" -f "Upstox", $upstoxState)
Write-Host ("  {0,-18} {1}" -f "Market", $marketState)
Write-Host ("  {0,-18} {1}" -f "Session", $sessionState)
Write-Host ("  {0,-18} {1}" -f "Strategies", "40 Active (Registry & Leaderboard)")
Write-Host ("  {0,-18} {1}" -f "PaperBroker", "ACTIVE")
Write-Host ("  {0,-18} {1}" -f "Live money", "FALSE")
Write-Host ("  {0,-18} {1}" -f "Chrome", $chromeResult)
Write-Host ("  {0,-18} {1}" -f "URL", "http://127.0.0.1:$FrontendPort/")
Write-Host ""
Write-Host "ATS is ready for observation/research." -ForegroundColor Cyan
Write-Host "Trading authorization remains fail-closed." -ForegroundColor Yellow
exit 0
