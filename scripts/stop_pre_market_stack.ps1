[CmdletBinding()]
param([string]$StateFile = (Join-Path $env:TEMP 'ats-pre-market-stack\processes.json'))

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $StateFile)) {
    Write-Output '{"status":"STOPPED","reason":"NO_STATE_FILE"}'
    exit 0
}
$state = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
foreach ($name in @('backend', 'frontend', 'harness')) {
    $processId = [int]$state.$name
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($null -ne $process) { Stop-Process -Id $processId -Force }
}
Remove-Item -LiteralPath $StateFile -Force
Write-Output '{"status":"STOPPED","real_orders_placed":0}'
