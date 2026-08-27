[CmdletBinding()]
param(
    [string]$HarnessRoot = 'D:\Projects\ATS\tools\deepseek-harness',
    [string]$NodeRoot = 'D:\Projects\ATS\tools\node-v24.19.0-win-x64'
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$stateRoot = Join-Path $env:TEMP 'ats-pre-market-stack'
$stateFile = Join-Path $stateRoot 'processes.json'
$node = Join-Path $NodeRoot 'node.exe'
$corepack = Join-Path $NodeRoot 'corepack.cmd'
$harnessBin = Join-Path $HarnessRoot 'packages\examples\acp-demo\lib\bin.js'

if ((& $node --version) -ne 'v24.19.0') { throw 'NODE_VERSION_MISMATCH' }
if ((& $corepack pnpm --version) -ne '11.9.0') { throw 'PNPM_VERSION_MISMATCH' }
if (-not (Test-Path -LiteralPath $harnessBin)) { throw 'HARNESS_BINARY_MISSING' }
$env:Path = $NodeRoot + [IO.Path]::PathSeparator + $env:Path
New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null

$backend = Start-Process -FilePath 'uv' -ArgumentList @(
    'run', '--with', 'uvicorn==0.40.0', 'python', '-m', 'uvicorn',
    'ats.api.app:app', '--host', '127.0.0.1', '--port', '8000'
) -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput (Join-Path $stateRoot 'backend.out.log') `
  -RedirectStandardError (Join-Path $stateRoot 'backend.err.log')

$frontend = Start-Process -FilePath $corepack -ArgumentList @(
    'pnpm', '--filter', '@ats/control-center', 'exec', 'next', 'dev', '-p', '3000'
) -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput (Join-Path $stateRoot 'frontend.out.log') `
  -RedirectStandardError (Join-Path $stateRoot 'frontend.err.log')

$harness = Start-Process -FilePath 'uv' -ArgumentList @(
    'run', 'python', (Join-Path $repo 'scripts\run_harness_sidecar.py'),
    '--harness-root', $HarnessRoot, '--node', $node
) -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput (Join-Path $stateRoot 'harness.out.log') `
  -RedirectStandardError (Join-Path $stateRoot 'harness.err.log')

@{
    backend = $backend.Id
    frontend = $frontend.Id
    harness = $harness.Id
    started_at = (Get-Date).ToUniversalTime().ToString('o')
} | ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding utf8

Start-Sleep -Seconds 6

function Get-ListenerOwner([int]$Port) {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    if ($listeners.Count -ne 1) { throw "EXPECTED_ONE_LISTENER_ON_PORT_$Port" }
    return [int]$listeners[0].OwningProcess
}

@{
    backend = Get-ListenerOwner 8000
    frontend = Get-ListenerOwner 3000
    harness = Get-ListenerOwner 8765
    backend_launcher = $backend.Id
    frontend_launcher = $frontend.Id
    harness_launcher = $harness.Id
    started_at = (Get-Date).ToUniversalTime().ToString('o')
} | ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding utf8

& (Join-Path $PSScriptRoot 'check_pre_market_stack.ps1') -StateFile $stateFile
