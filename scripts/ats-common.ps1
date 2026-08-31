Set-StrictMode -Version Latest

$script:AtsRepo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script:AtsStateRoot = Join-Path $env:TEMP 'ats-a2-live-paper'
$script:AtsStateFile = Join-Path $script:AtsStateRoot 'processes.json'
$script:AtsNodeRoot = 'D:\Projects\ATS\toolchains\node-v24.19.0-win-x64'
$script:AtsHarnessRoot = 'D:\Projects\ATS\tools\deepseek-harness'
$script:AtsHarnessCommit = 'b150a551b8d465e31e418e1b2eaf5e79bbb7d28e'
$script:AtsRuntimeBase = 'a7658c8e95c560f1d50cf81afe8068cd8481a983'
$script:AtsReleaseAnchors = @(
    $script:AtsRuntimeBase,
    '956b861', # integrated ATS UX5 tip
    '015feee'  # one-command launcher foundation
)

function Get-AtsUserEnvironmentValue([string]$Name) {
    $value = [Environment]::GetEnvironmentVariable($Name, 'Process')
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = [Environment]::GetEnvironmentVariable($Name, 'User')
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            [Environment]::SetEnvironmentVariable($Name, $value, 'Process')
        }
    }
    return $value
}

function Assert-AtsReleaseTruth {
    $branch = (& git -C $script:AtsRepo branch --show-current).Trim()
    if ($branch -ne 'eng/final-a2-integration') { throw "ATS_RELEASE_BRANCH_MISMATCH: $branch" }
    foreach ($anchor in $script:AtsReleaseAnchors) {
        & git -C $script:AtsRepo merge-base --is-ancestor $anchor HEAD
        if ($LASTEXITCODE -ne 0) { throw "ATS_RELEASE_ANCHOR_MISSING: $anchor" }
    }
    $dirty = @(& git -C $script:AtsRepo status --porcelain=v1)
    $unexpected = @($dirty | Where-Object { $_ -notmatch 'frontend/apps/control-center/next-env\.d\.ts' -and $_ -notmatch 'scripts/' -and $_ -notmatch 'tests/' -and $_ -notmatch 'FINAL_REPORT_' })
    if ($unexpected.Count -gt 0) { throw "ATS_UNEXPLAINED_DIRTY_STATE: $($unexpected -join '; ')" }
    $nextEnvDiff = @($dirty | Where-Object { $_ -match '^ M frontend/apps/control-center/next-env\.d\.ts$' })
    if ($nextEnvDiff.Count -gt 0) {
        $diff = (& git -C $script:AtsRepo diff -- frontend/apps/control-center/next-env.d.ts) -join "`n"
        if ($diff -notmatch '\.next/dev/types/routes\.d\.ts' -or $diff -notmatch '\.next/types/routes\.d\.ts') {
            throw 'ATS_NEXT_ENV_DIRTY_STATE_NOT_RECOGNIZED'
        }
    }
}

$script:AtsPnpmJs = Join-Path $env:APPDATA 'npm\node_modules\pnpm\bin\pnpm.mjs'

function Assert-AtsToolchain {
    $node = Join-Path $script:AtsNodeRoot 'node.exe'
    if (-not (Test-Path -LiteralPath $node)) { throw 'ATS_NODE_24_19_0_MISSING' }
    if ((& $node --version).Trim() -ne 'v24.19.0') { throw 'ATS_NODE_VERSION_MISMATCH' }

    # Ensure ATS child processes use the validated Node 24.19.0 directory first on PATH
    if ($env:Path -notlike "$($script:AtsNodeRoot)*") {
        $env:Path = $script:AtsNodeRoot + [IO.Path]::PathSeparator + $env:Path
    }

    if (-not (Test-Path -LiteralPath $script:AtsPnpmJs)) { throw 'ATS_PNPM_11_9_0_MISSING' }
    $pnpmVersion = (& $node $script:AtsPnpmJs --version).Trim()
    if ($pnpmVersion -ne '11.9.0') { throw 'ATS_PNPM_VERSION_MISMATCH' }

    if ($null -eq (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'ATS_UV_MISSING' }
    if ((& uv run --directory $script:AtsRepo python --version 2>&1) -notmatch 'Python 3\.11\.15') { throw 'ATS_PYTHON_VERSION_MISMATCH' }
}

function Assert-AtsHarness {
    $actual = (& git -C $script:AtsHarnessRoot rev-parse HEAD).Trim()
    if ($actual -ne $script:AtsHarnessCommit) { throw "ATS_HARNESS_PIN_MISMATCH: $actual" }
    $binary = Join-Path $script:AtsHarnessRoot 'packages\examples\acp-demo\lib\bin.js'
    if (-not (Test-Path -LiteralPath $binary)) { throw 'ATS_HARNESS_BINARY_MISSING' }
}

function Assert-AtsOllama([int]$StartupTimeoutSec = 30) {
    $ollama = Get-Command ollama.exe -ErrorAction SilentlyContinue
    if ($null -eq $ollama) { throw 'ATS_OLLAMA_MISSING' }

    $tags = $null
    try { $tags = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 -ErrorAction Stop } catch {}
    if ($null -eq $tags) {
        # Do not create a second Ollama owner. An existing unhealthy process gets
        # the same bounded recovery window and then fails closed for the operator.
        $owners = @(Get-Process -Name 'ollama' -ErrorAction SilentlyContinue)
        if ($owners.Count -eq 0) {
            Write-Host '  Ollama service     starting local server' -ForegroundColor Yellow
            Start-Process -FilePath $ollama.Source -ArgumentList @('serve') -WindowStyle Hidden | Out-Null
        }

        $deadline = (Get-Date).AddSeconds($StartupTimeoutSec)
        do {
            Start-Sleep -Milliseconds 500
            try { $tags = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 -ErrorAction Stop } catch { $tags = $null }
        } while ($null -eq $tags -and (Get-Date) -lt $deadline)
    }
    if ($null -eq $tags) { throw 'ATS_OLLAMA_OFFLINE' }

    $models = @($tags.models | ForEach-Object { $_.name })
    foreach ($required in @('qwen3:14b', 'qwen2.5:14b')) {
        if ($required -notin $models) { throw "ATS_OLLAMA_MODEL_MISSING: $required" }
    }
}

function Get-AtsChromePath {
    $candidates = @(
        (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe'),
        (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe')
    )
    return $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

function Invoke-AtsJson([string]$Path, [int]$TimeoutSec = 4) {
    try { return Invoke-RestMethod -Uri "http://127.0.0.1:8000$Path" -TimeoutSec $TimeoutSec -ErrorAction Stop } catch { return $null }
}

function Test-AtsStackRunning {
    $runtime = Invoke-AtsJson '/v1/runtime/status' 2
    try { $frontend = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:3000/' -TimeoutSec 2 -ErrorAction Stop } catch { $frontend = $null }
    return $null -ne $runtime -and $null -ne $frontend -and $frontend.StatusCode -eq 200
}
