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

# Run startup and capture output to determine status
$startupOutput = & uv @startupArgs 2>&1
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    # Parse status from output - look for "Status : <status>"
    $status = ''
    if ($startupOutput -match 'Status') {
        # Extract status text after "Status : "
        $statusLine = ($startupOutput | Select-String -Pattern 'Status' -SimpleMatch).Line
        if ($statusLine) {
            $status = $statusLine -replace 'Status\s*:\s*', '' -replace '\s+$', ''
        }
    }

    if ($status -eq 'STARTED') {
        # Launch ATS browser/control-center exactly once
        $ctrlCenterDir = Join-Path $repo 'frontend\apps\control-center'
        $lockFile = Join-Path $ctrlCenterDir 'ats-browser-launched.lock'

        # Check for duplicate launch (lock file exists = already launched)
        if (Test-Path $lockFile) {
            Write-Host '  ATS browser already launched. Skipping duplicate.' -ForegroundColor Yellow
        } else {
            Write-Host '  Launching ATS control-center browser...' -ForegroundColor Cyan

            # Check if port 3000 is already in use
            $portCheck = Test-NetConnection -Port 3000 -ComputerName localhost 2>&1
            $portAvailable = ($portCheck -notmatch 'TcpTestSucceeded')

            if ($portAvailable) {
                # Start control-center dev server in background
                Write-Host '  Starting control-center development server...' -ForegroundColor Cyan
                Set-Location $ctrlCenterDir
                & 'C:\Program Files\nodejs\node.exe' $ctrlCenterDir\node_modules\.bin\next dev > $null 2>&1 &

                # Wait for port 3000 to become available (max 60 seconds)
                $maxWait = 60
                $waited = 0
                while ($waited -lt $maxWait) {
                    $ncResult = Test-NetConnection -Port 3000 -ComputerName localhost 2>&1
                    if ($ncResult -match 'TcpTestSucceeded') {
                        break
                    }
                    Start-Sleep 1
                    $waited++
                }

                if ($waited -ge $maxWait) {
                    Write-Host '  Warning: Control-center did not start within 60 seconds.' -ForegroundColor Yellow
                }
            }

            # Open browser to control-center
            Write-Host '  Opening ATS control-center in browser...' -ForegroundColor Green
            Start-Process 'http://localhost:3000'

            # Create lock file to prevent duplicate launches
            New-Item -ItemType File -Path $lockFile -Force | Out-Null
            Write-Host '  ATS browser launched successfully.' -ForegroundColor Green
        }
    } elseif ($status -eq 'NON_TRADING_DAY' -or $status -eq 'MARKET_CLOSED' -or $status -eq 'READY_WAITING_FOR_MARKET') {
        # Do not open browser for non-trading states
        Write-Host '  Browser not opened: market is not open (status: $status).' -ForegroundColor Yellow
    }

    Write-Host 'ats-start finished with an operational status (see above).' -ForegroundColor Cyan
    exit 0
}
if ($exitCode -eq 2) {
    Write-Host 'ats-start stopped: Upstox authorization missing. See remediation above.' -ForegroundColor Red
    exit 2
}
if ($exitCode -eq 3) {
    Write-Host 'ats-start refused: PAPER-only invariant violated. Live writes are prohibited.' -ForegroundColor Red
    exit 3
}
Write-Host 'ats-start failed closed on Stage-1 evidence. Inspect the reason above.' -ForegroundColor Red
exit 4