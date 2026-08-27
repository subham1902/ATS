[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ats-common.ps1')
$chrome = Get-AtsChromePath
if ([string]::IsNullOrWhiteSpace($chrome)) { throw 'ATS_CHROME_MISSING' }
Start-Process -FilePath $chrome -ArgumentList @('--new-window', 'http://127.0.0.1:3000/', 'http://127.0.0.1:3000/operator-intelligence') | Out-Null
Start-Process -FilePath $chrome -ArgumentList @('--new-window', 'http://127.0.0.1:3000/harness') | Out-Null
Write-Host 'Opened ATS Operations and Harness windows in Chrome.' -ForegroundColor Green
