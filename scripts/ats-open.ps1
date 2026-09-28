[CmdletBinding()]
param()
$scriptDir = $PSScriptRoot
$operatorScript = Join-Path $scriptDir 'ats-operator.ps1'
& $operatorScript -Action Open
exit $LASTEXITCODE
