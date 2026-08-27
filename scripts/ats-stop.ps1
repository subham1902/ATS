[CmdletBinding()]
param()
$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'ats-common.ps1')

if ($null -ne (Invoke-AtsJson '/v1/runtime/status' 2)) {
    try {
        Invoke-RestMethod -Uri 'http://127.0.0.1:8000/v1/runtime/command' -Method Post -ContentType 'application/json' -Body '{"command":"PAUSE_NEW_ENTRIES"}' -TimeoutSec 4 | Out-Null
        Write-Host 'Paused new entries.' -ForegroundColor Green
    } catch { Write-Warning 'Could not pause new entries before shutdown.' }
    try {
        Invoke-RestMethod -Uri 'http://127.0.0.1:8000/v1/runtime/command' -Method Post -ContentType 'application/json' -Body '{"command":"STOP_A2_PAPER_SESSION"}' -TimeoutSec 8 | Out-Null
        Write-Host 'Runtime stopped; shutdown policy flattened paper positions if required.' -ForegroundColor Green
    } catch { Write-Warning 'Runtime graceful stop unavailable; proceeding with owned process cleanup.' }
}
& (Join-Path $PSScriptRoot 'stop_ats_a2_live_paper.ps1') -StateFile $script:AtsStateFile
