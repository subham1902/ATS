[CmdletBinding()]
param(
    [string]$StateFile = (Join-Path $env:TEMP 'ats-a2-live-paper\processes.json')
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $StateFile)) {
    Write-Warning "State file not found: $StateFile (nothing to stop?)"
    exit 0
}

$state = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json

$ids = @(
    if ($state.backend_launcher) { [int]$state.backend_launcher }
    if ($state.frontend_launcher) { [int]$state.frontend_launcher }
    if ($state.harness_launcher) { [int]$state.harness_launcher }
    if ($state.backend) { [int]$state.backend }
    if ($state.frontend) { [int]$state.frontend }
    if ($state.harness) { [int]$state.harness }
) | Sort-Object -Unique

foreach ($pid_ in $ids) {
    try {
        $proc = Get-Process -Id $pid_ -ErrorAction SilentlyContinue
        if ($proc) {
            $proc | Stop-Process -Force
            Write-Host "Stopped PID $pid_" -ForegroundColor Yellow
        }
    } catch {
        Write-Warning "Failed to stop PID ${pid_}: $_"
    }
}

# Best-effort port-based cleanup of stray listeners (backend 8000, frontend 3000, harness 8765)
foreach ($port in @(8000, 3000, 8765)) {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
    foreach ($l in $listeners) {
        try {
            $p = Get-Process -Id $l.OwningProcess -ErrorAction SilentlyContinue
            if ($p) { $p | Stop-Process -Force; Write-Host "Stopped stray listener on port $port (PID $($l.OwningProcess))" -ForegroundColor Yellow }
        } catch { Write-Warning "Could not stop listener on port $port" }
    }
}

Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue
Write-Host "ATS A2 LIVE-PAPER stack stopped." -ForegroundColor Green
