[CmdletBinding()]
param(
    [switch]$NoOpen
)
$scriptDir = $PSScriptRoot
$operatorScript = Join-Path $scriptDir 'ats-operator.ps1'
if ($NoOpen) {
    & $operatorScript -Action Restart -NoOpen
} else {
    & $operatorScript -Action Restart
}
exit $LASTEXITCODE
