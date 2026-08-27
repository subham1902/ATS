[CmdletBinding()]
param()
$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'ats-common.ps1')

$runtime = Invoke-AtsJson '/v1/runtime/status'
$system = Invoke-AtsJson '/v1/system'
$harness = Invoke-AtsJson '/v1/harness/status'
$pipeline = Invoke-AtsJson '/v1/pipeline/counters'
$health = Invoke-AtsJson '/health/live'
try { $ollama = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3; $modelNames = @($ollama.models.name) } catch { $modelNames = @() }

function Show([string]$Name, [object]$Value) { Write-Host ('{0,-24}{1}' -f $Name, $(if ($null -eq $Value -or "$Value" -eq '') { 'UNKNOWN' } else { "$Value" })) }
$session = if ($null -ne $runtime) { $runtime.session.phase } else { 'UNKNOWN' }
$market = if ($session -eq 'ENTRY_ALLOWED') { 'OPEN' } elseif ($session -eq 'CLOSED') { 'CLOSED' } else { $session }
$feed = if ($session -eq 'CLOSED') { 'CLOSED_SESSION_EXPECTED' } elseif ($null -ne $pipeline -and $pipeline.connection_state -eq 'LIVE' -and [int]$pipeline.fresh_messages -gt 0) { 'FRESH' } else { 'STALE/UNKNOWN' }
$pnl = if ($runtime) { [decimal]$runtime.pnl.realized + [decimal]$runtime.pnl.unrealized } else { $null }

Show 'ATS' $(if ($null -ne $health -and $health.status -eq 'LIVE') { 'READY' } else { 'OFFLINE' })
Show 'SYSTEM' $(if ($null -ne $system) { $system.system_state } else { 'UNKNOWN' })
Show 'MARKET' $market
Show 'SESSION' $session
Show 'FEED' $feed
Show 'EXECUTION' $(if ($null -ne $harness) { $harness.harness.execution_target } else { 'UNKNOWN' })
Show 'LIVE MONEY' $(if ($null -ne $harness) { $harness.harness.live_money } else { 'UNKNOWN' })
Write-Host ''
Show 'UPSTOX' $(if ($null -ne $runtime) { 'READ_ONLY CONFIGURED' } else { 'OFFLINE' })
Show 'SUBSCRIPTIONS' $(if ($null -ne $pipeline -and $pipeline.PSObject.Properties.Name -contains 'subscription_count' -and $pipeline.subscription_count) { $pipeline.subscription_count } elseif ($session -eq 'CLOSED') { '0 (CLOSED)' } else { 'UNKNOWN' })
Show 'PAPERBROKER' $(if ($null -ne $runtime -and $runtime.broker_healthy) { 'HEALTHY' } else { 'OFFLINE/DEGRADED' })
Show 'PORTFOLIO BRAIN' $(if ($null -ne $runtime) { 'ATTACHED' } else { 'UNKNOWN' })
Show 'A04' $(if ($null -ne $runtime) { 'FINAL AUTHORITY' } else { 'UNKNOWN' })
Write-Host ''
Show 'HARNESS' $(if ($null -ne $harness) { $harness.harness.state } else { 'OFFLINE' })
Show 'LOCAL LLM' $(if ('qwen3:14b' -in $modelNames) { 'qwen3:14b READY' } else { 'OFFLINE' })
Show 'ACTIVE AGENTS' $(if ($null -ne $harness) { $harness.harness.active_sessions } else { 0 })
Write-Host ''
Show 'CAPITAL' $(if ($null -ne $runtime) { $runtime.capital.total } else { 'UNKNOWN' })
Show 'P&L' $pnl
Show 'POSITIONS' $(if ($null -ne $runtime) { $runtime.open_positions.Count } else { 0 })
Show 'OPPORTUNITIES' $(if ($null -ne $pipeline) { $pipeline.candidates_qualified } else { 0 })
Show 'REAL ORDERS' $(if ($null -ne $harness) { $harness.harness.real_orders_placed } else { 'UNKNOWN' })

$unsafe = $null -eq $harness -or $harness.harness.execution_target -ne 'PAPER' -or $harness.harness.live_money -ne 'DISABLED' -or [int]$harness.harness.real_orders_placed -ne 0
if ($unsafe) { Write-Host "`nSAFETY INVARIANT FAILURE" -ForegroundColor Red; exit 1 }
exit 0
