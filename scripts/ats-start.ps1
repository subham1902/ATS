[CmdletBinding()]
param([switch]$NoOpen)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ats-common.ps1')

Write-Host 'ATS pre-flight' -ForegroundColor Cyan
Assert-AtsReleaseTruth
Assert-AtsToolchain
Assert-AtsHarness
$token = Get-AtsUserEnvironmentValue 'ATS_UPSTOX_ACCESS_TOKEN'
if ([string]::IsNullOrWhiteSpace($token)) { throw 'ATS_UPSTOX_ACCESS_TOKEN_MISSING' }
Write-Host '  Upstox token       PRESENT (protected)' -ForegroundColor Green
Assert-AtsOllama
Write-Host '  Ollama models      qwen3:14b + qwen2.5:14b READY' -ForegroundColor Green

if (-not (Test-Path -LiteralPath (Join-Path $script:AtsRepo 'frontend\apps\control-center\.next\BUILD_ID'))) {
    Write-Host '  Control Center     building production assets' -ForegroundColor Yellow
    $env:Path = $script:AtsNodeRoot + [IO.Path]::PathSeparator + $env:Path
    & (Join-Path $script:AtsNodeRoot 'corepack.cmd') pnpm --dir $script:AtsRepo --filter '@ats/control-center' build
    if ($LASTEXITCODE -ne 0) { throw 'ATS_CONTROL_CENTER_BUILD_FAILED' }
}

if (Test-AtsStackRunning) {
    Write-Host 'ATS is already running; duplicate startup prevented.' -ForegroundColor Yellow
} else {
    if (Test-Path -LiteralPath $script:AtsStateFile) {
        throw "ATS_STALE_STATE_REQUIRES_ATS_STOP: $script:AtsStateFile"
    }
    & (Join-Path $PSScriptRoot 'start_ats_a2_live_paper.ps1') -RequireToken -NodeRoot $script:AtsNodeRoot -HarnessRoot $script:AtsHarnessRoot
    if ($LASTEXITCODE -ne 0) { throw 'ATS_STACK_START_FAILED' }
}

& uv run --directory $script:AtsRepo python (Join-Path $PSScriptRoot 'run_market_open_a2_acceptance.py')
if ($LASTEXITCODE -ne 0) { throw 'ATS_READ_ONLY_MARKET_ACCEPTANCE_FAILED' }
& (Join-Path $PSScriptRoot 'ats-status.ps1')
if (-not $NoOpen) { & (Join-Path $PSScriptRoot 'ats-open.ps1') }
