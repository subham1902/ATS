[CmdletBinding()]
param([string]$StateFile = (Join-Path $env:TEMP 'ats-pre-market-stack\processes.json'))

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $StateFile)) {
    Write-Output '{"status":"STOPPED","reason":"NO_STATE_FILE"}'
    exit 0
}
$state = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
$rootIds = @(
    foreach ($name in @(
        'backend', 'frontend', 'harness',
        'backend_launcher', 'frontend_launcher', 'harness_launcher'
    )) {
        if ($state.PSObject.Properties.Name -contains $name) { [int]$state.$name }
    }
)
$processes = @(Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId)
$ownedIds = [System.Collections.Generic.List[int]]::new()
$frontier = @($rootIds)
while ($frontier.Count -gt 0) {
    $children = @(
        $processes |
            Where-Object { $_.ParentProcessId -in $frontier } |
            ForEach-Object { [int]$_.ProcessId }
    )
    foreach ($processId in $children) {
        if (-not $ownedIds.Contains($processId)) { $ownedIds.Add($processId) }
    }
    $frontier = $children
}
foreach ($processId in @($ownedIds.ToArray(); $rootIds)) {
    if ($null -ne (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
}
Remove-Item -LiteralPath $StateFile -Force
Write-Output '{"status":"STOPPED","real_orders_placed":0}'
