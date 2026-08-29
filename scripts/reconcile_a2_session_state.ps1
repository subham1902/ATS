[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$ArchiveStale
)

$ErrorActionPreference = 'Stop'
if ($Check -eq $ArchiveStale) { throw 'SELECT_EXACTLY_ONE_OF_CHECK_OR_ARCHIVE_STALE' }
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
$env:PYTHONPATH = Join-Path $repo 'backend\src'
$argument = if ($Check) { '--check' } else { '--archive-stale' }
& $python -m ats.trading_runtime.session_reconciliation_cli $argument
exit $LASTEXITCODE
