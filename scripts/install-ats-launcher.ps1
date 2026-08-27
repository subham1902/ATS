[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$target = Join-Path $env:LOCALAPPDATA 'ATS\bin'
New-Item -ItemType Directory -Force -Path $target | Out-Null
[Environment]::SetEnvironmentVariable('ATS_RELEASE_ROOT', $repo, 'User')
foreach ($name in @('ats-start', 'ats-status', 'ats-stop', 'ats-open')) {
    Copy-Item -LiteralPath (Join-Path $repo "launcher\$name.cmd") -Destination (Join-Path $target "$name.cmd") -Force
}
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$parts = @($userPath -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
if ($target -notin $parts) {
    [Environment]::SetEnvironmentVariable('Path', (($parts + $target) -join ';'), 'User')
}
Write-Host "Installed ATS launchers for current user: $target" -ForegroundColor Green
Write-Host 'Open a new terminal and run: ats-start' -ForegroundColor Cyan
