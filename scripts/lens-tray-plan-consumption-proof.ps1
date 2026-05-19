[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status'
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

function Get-PowerShellPath {
  $Candidates = @('pwsh', 'powershell')
  foreach ($Candidate in $Candidates) {
    $Command = Get-Command $Candidate -ErrorAction SilentlyContinue
    if ($null -ne $Command) {
      return $Command.Source
    }
  }
  throw 'PowerShell executable not found.'
}

function Get-PropertyValue {
  param(
    [AllowNull()][object]$Payload,
    [string]$Name,
    [object]$Default = $null
  )

  if ($null -eq $Payload) {
    return $Default
  }
  if ($Payload -is [System.Collections.IDictionary] -and $Payload.Contains($Name)) {
    $Value = $Payload[$Name]
    if ($null -ne $Value) {
      return $Value
    }
    return $Default
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) {
    return $Default
  }
  return $Property.Value
}

function ConvertTo-StringArray {
  param([AllowNull()][object]$Value)

  if ($null -eq $Value) {
    return @()
  }
  if ($Value -is [System.Array]) {
    return @($Value | ForEach-Object { [string]$_ })
  }
  return @([string]$Value)
}

function Invoke-JsonScript {
  param(
    [string]$PowerShellPath,
    [string]$ScriptPath,
    [string[]]$ArgumentList,
    [string]$DataRootEnv,
    [string]$RunRoot,
    [string]$Name
  )

  $StdOutPath = Join-Path $RunRoot ($Name + '.stdout.txt')
  $StdErrPath = Join-Path $RunRoot ($Name + '.stderr.txt')
  $PreviousDataRoot = $env:FRANCIS_DATA_DIR
  if (-not [string]::IsNullOrWhiteSpace($DataRootEnv)) {
    $env:FRANCIS_DATA_DIR = $DataRootEnv
  }
  try {
    $ProcessArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ScriptPath) + $ArgumentList
    & $PowerShellPath @ProcessArgs 1> $StdOutPath 2> $StdErrPath
    $ExitCode = if ($null -ne $LASTEXITCODE) { [int]$LASTEXITCODE } else { 0 }
  } finally {
    if ($null -eq $PreviousDataRoot) {
      Remove-Item Env:\FRANCIS_DATA_DIR -ErrorAction SilentlyContinue
    } else {
      $env:FRANCIS_DATA_DIR = $PreviousDataRoot
    }
  }

  $StdOut = ''
  $StdErr = ''
  if (Test-Path -LiteralPath $StdOutPath -PathType Leaf) {
    $RawStdOut = Get-Content -LiteralPath $StdOutPath -Raw -ErrorAction SilentlyContinue
    if ($null -ne $RawStdOut) {
      $StdOut = ([string]$RawStdOut).Trim()
    }
  }
  if (Test-Path -LiteralPath $StdErrPath -PathType Leaf) {
    $RawStdErr = Get-Content -LiteralPath $StdErrPath -Raw -ErrorAction SilentlyContinue
    if ($null -ne $RawStdErr) {
      $StdErr = ([string]$RawStdErr).Trim()
    }
  }

  $Payload = $null
  $ParseError = ''
  if (-not [string]::IsNullOrWhiteSpace($StdOut)) {
    try {
      $Payload = $StdOut | ConvertFrom-Json -ErrorAction Stop
    } catch {
      $ParseError = $_.Exception.Message
    }
  }

  return [ordered]@{
    exit_code = $ExitCode
    stdout = $StdOut
    stderr = $StdErr
    payload = $Payload
    parse_error = $ParseError
  }
}

function Test-SafeTempPath {
  param([string]$Path)

  $TempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
  $Resolved = [System.IO.Path]::GetFullPath($Path)
  return $Resolved.StartsWith($TempRoot, [System.StringComparison]::OrdinalIgnoreCase)
}

function Write-ProofTrayRuntimeState {
  param(
    [string]$DataRoot,
    [int]$ProcessId
  )

  $RuntimeRoot = Join-Path $DataRoot 'runtime/lens-tray'
  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  Set-Content -LiteralPath (Join-Path $RuntimeRoot 'lens-tray.pid') -Value ([string]$ProcessId) -Encoding utf8
  $Payload = [ordered]@{
    kind = 'lens.tray.runtime_state'
    status = 'tray_running'
    pid = $ProcessId
    tray_icon_visible = $true
    presence_name = 'Francis Lens Tray Presence'
    proof_only = $true
    os_tray_registered = $false
    updated_at = [DateTimeOffset]::UtcNow.ToString('o')
    message = 'Synthetic tray runtime readback bound to the live proof process; no OS tray icon was registered.'
  }
  $Payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $RuntimeRoot 'status.json') -Encoding utf8
  return $Payload
}

$PowerShellPath = Get-PowerShellPath
$HostSupervisorPath = Join-Path $PSScriptRoot 'lens-host-supervisor.ps1'
$TrayPresencePath = Join-Path $PSScriptRoot 'lens-tray-presence.ps1'
$PlanPath = Join-Path $PSScriptRoot 'lens-persistent-supervision-plan.ps1'
$DataRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('francis-lens-tray-plan-consumption-proof-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null

$StartResult = $null
$TrayRuntimeState = $null
$TrayPresenceResult = $null
$PlanResult = $null
$StopResult = $null
$DataRootRemoved = $false

try {
  $StartResult = Invoke-JsonScript `
    -PowerShellPath $PowerShellPath `
    -ScriptPath $HostSupervisorPath `
    -ArgumentList @('-Mode', 'StartResident', '-DataDir', $DataRoot) `
    -DataRootEnv '' `
    -RunRoot $DataRoot `
    -Name 'start-resident'

  $TrayRuntimeState = Write-ProofTrayRuntimeState -DataRoot $DataRoot -ProcessId $PID

  $TrayPresenceResult = Invoke-JsonScript `
    -PowerShellPath $PowerShellPath `
    -ScriptPath $TrayPresencePath `
    -ArgumentList @('-Mode', 'Status', '-DataDir', $DataRoot) `
    -DataRootEnv '' `
    -RunRoot $DataRoot `
    -Name 'tray-presence'

  $PlanResult = Invoke-JsonScript `
    -PowerShellPath $PowerShellPath `
    -ScriptPath $PlanPath `
    -ArgumentList @('-Mode', 'Status') `
    -DataRootEnv $DataRoot `
    -RunRoot $DataRoot `
    -Name 'persistent-supervision-plan'
} finally {
  try {
    $StopResult = Invoke-JsonScript `
      -PowerShellPath $PowerShellPath `
      -ScriptPath $HostSupervisorPath `
      -ArgumentList @('-Mode', 'StopResident', '-DataDir', $DataRoot) `
      -DataRootEnv '' `
      -RunRoot $DataRoot `
      -Name 'stop-resident'
  } catch {
    $StopResult = [ordered]@{
      exit_code = 1
      stdout = ''
      stderr = $_.Exception.Message
      payload = $null
      parse_error = ''
    }
  }

  if (Test-SafeTempPath -Path $DataRoot) {
    Remove-Item -LiteralPath $DataRoot -Recurse -Force -ErrorAction SilentlyContinue
    $DataRootRemoved = -not (Test-Path -LiteralPath $DataRoot)
  }
}

$StartPayload = Get-PropertyValue -Payload $StartResult -Name 'payload'
$TrayPresencePayload = Get-PropertyValue -Payload $TrayPresenceResult -Name 'payload'
$PlanPayload = Get-PropertyValue -Payload $PlanResult -Name 'payload'
$StopPayload = Get-PropertyValue -Payload $StopResult -Name 'payload'

$Dependencies = @(Get-PropertyValue -Payload $PlanPayload -Name 'enablement_dependency_readback' -Default @())
$ResidentDependency = @($Dependencies | Where-Object { [string](Get-PropertyValue -Payload $_ -Name 'id' -Default '') -eq 'resident_host_process' } | Select-Object -First 1)
$TrayDependency = @($Dependencies | Where-Object { [string](Get-PropertyValue -Payload $_ -Name 'id' -Default '') -eq 'tray_presence' } | Select-Object -First 1)
$PlanHandoff = Get-PropertyValue -Payload $PlanPayload -Name 'first_missing_requirement_handoff'
$MissingRequired = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $PlanPayload -Name 'missing_required_before_enable' -Default @())
$FirstMissing = [string](Get-PropertyValue -Payload $PlanPayload -Name 'first_missing_required_before_enable' -Default '')
$StartGovernance = Get-PropertyValue -Payload $StartPayload -Name 'governance'
$PlanGovernance = Get-PropertyValue -Payload $PlanPayload -Name 'governance'
$TrayPresenceGovernance = Get-PropertyValue -Payload $TrayPresencePayload -Name 'governance'

$LiveResidentHostObserved = (
  [int](Get-PropertyValue -Payload $StartResult -Name 'exit_code' -Default 1) -eq 0 -and
  [string](Get-PropertyValue -Payload $StartPayload -Name 'status' -Default '') -in @('resident_supervision_started', 'resident_supervision_already_running') -and
  [bool](Get-PropertyValue -Payload $StartPayload -Name 'resident_host_process' -Default $false) -and
  [bool](Get-PropertyValue -Payload $StartPayload -Name 'resident_supervised_runtime' -Default $false)
)

$ResidentDependencyReady = (
  $ResidentDependency.Count -gt 0 -and
  [bool](Get-PropertyValue -Payload $ResidentDependency[0] -Name 'ready' -Default $false) -and
  [string](Get-PropertyValue -Payload $ResidentDependency[0] -Name 'status' -Default '') -eq 'ready' -and
  [bool](Get-PropertyValue -Payload $ResidentDependency[0] -Name 'resident_supervised_runtime' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentDependency[0] -Name 'process_alive' -Default $false)
)

$TrayPresenceObserved = (
  [int](Get-PropertyValue -Payload $TrayPresenceResult -Name 'exit_code' -Default 1) -eq 0 -and
  [string](Get-PropertyValue -Payload $TrayPresencePayload -Name 'status' -Default '') -eq 'running' -and
  [bool](Get-PropertyValue -Payload $TrayPresencePayload -Name 'tray_presence' -Default $false) -and
  [bool](Get-PropertyValue -Payload $TrayPresencePayload -Name 'ready' -Default $false)
)

$TrayDependencyReady = (
  $TrayDependency.Count -gt 0 -and
  [bool](Get-PropertyValue -Payload $TrayDependency[0] -Name 'ready' -Default $false) -and
  [string](Get-PropertyValue -Payload $TrayDependency[0] -Name 'status' -Default '') -eq 'ready' -and
  [string](Get-PropertyValue -Payload $TrayDependency[0] -Name 'tray_presence_source' -Default '') -eq 'live_runtime_readback' -and
  [bool](Get-PropertyValue -Payload $TrayDependency[0] -Name 'tray_runtime_ready' -Default $false) -and
  [bool](Get-PropertyValue -Payload $TrayDependency[0] -Name 'tray_runtime_process_alive' -Default $false) -and
  [bool](Get-PropertyValue -Payload $TrayDependency[0] -Name 'tray_runtime_icon_visible' -Default $false)
)

$PlanConsumedTrayRuntime = (
  [int](Get-PropertyValue -Payload $PlanResult -Name 'exit_code' -Default 1) -eq 0 -and
  [string](Get-PropertyValue -Payload $PlanPayload -Name 'status' -Default '') -eq 'blocked' -and
  $ResidentDependencyReady -and
  $TrayDependencyReady -and
  $FirstMissing -eq 'global_hotkey_binding' -and
  -not ($MissingRequired -contains 'resident_host_process') -and
  -not ($MissingRequired -contains 'tray_presence')
)

$StopObserved = (
  [int](Get-PropertyValue -Payload $StopResult -Name 'exit_code' -Default 1) -eq 0 -and
  [string](Get-PropertyValue -Payload $StopPayload -Name 'status' -Default '') -eq 'resident_supervision_stopped' -and
  -not [bool](Get-PropertyValue -Payload $StopPayload -Name 'resident_host_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $StopPayload -Name 'resident_supervised_runtime' -Default $true)
)

$SideEffectsBounded = (
  [bool](Get-PropertyValue -Payload $StartGovernance -Name 'local_process_launch_authority' -Default $false) -and
  [bool](Get-PropertyValue -Payload $StartGovernance -Name 'process_supervision_authority' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $StartGovernance -Name 'process_restart_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $StartGovernance -Name 'service_install_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $StartGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $StartGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $StartGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $StartGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $StartGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $StartGovernance -Name 'resident_claim_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $StartGovernance -Name 'memory_write' -Default $true) -and
  [bool](Get-PropertyValue -Payload $TrayPresenceGovernance -Name 'read_only_contract' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $TrayPresenceGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayPresenceGovernance -Name 'tray_icon_authority' -Default $true) -and
  [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'read_only_contract' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'mutation_authority_granted' -Default $true)
)

$ProofPassed = $LiveResidentHostObserved -and $TrayPresenceObserved -and $PlanConsumedTrayRuntime -and $StopObserved -and $SideEffectsBounded -and $DataRootRemoved
$NextGap = if ($PlanConsumedTrayRuntime) { 'global_hotkey_binding' } elseif ($ResidentDependencyReady) { 'tray_presence' } else { 'resident_host_process' }
$RecommendedSlice = if ($PlanConsumedTrayRuntime) {
  'resolve_global_hotkey_binding_before_persistent_supervision_enablement'
} elseif ($ResidentDependencyReady) {
  'debug_tray_runtime_plan_consumption_readback'
} else {
  'debug_resident_host_plan_consumption_readback'
}
$RecommendedHandoff = $null
$RecommendedHandoffSource = $null
$RecommendedProofScript = $null
if ($PlanConsumedTrayRuntime -and $null -ne $PlanHandoff) {
  $RecommendedHandoff = $PlanHandoff
  $RecommendedHandoffSource = 'plan_first_missing_requirement_handoff'
  $RecommendedProofScript = [string](Get-PropertyValue -Payload $PlanHandoff -Name 'proof_script' -Default '')
  if ([string]::IsNullOrWhiteSpace($RecommendedProofScript)) {
    $RecommendedProofScript = [string](Get-PropertyValue -Payload $PlanHandoff -Name 'preflight_script' -Default '')
  }
  if ([string]::IsNullOrWhiteSpace($RecommendedProofScript)) {
    $RecommendedProofScript = $null
  }
}

$Payload = [ordered]@{
  kind = 'lens.tray_runtime.plan_consumption_proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  ok = $ProofPassed
  mode = $Mode.ToLowerInvariant()
  stage = 'Stage 6 / Lens MVP'
  stage_state = 'active'
  ready_to_close = $false
  data_root_removed = $DataRootRemoved
  live_resident_host_observed = $LiveResidentHostObserved
  synthetic_tray_runtime_readback_observed = $TrayPresenceObserved
  persistent_supervision_plan_consumed_tray_runtime = $PlanConsumedTrayRuntime
  resident_dependency_ready = $ResidentDependencyReady
  tray_dependency_ready = $TrayDependencyReady
  first_missing_required_before_enable = $FirstMissing
  missing_required_before_enable = $MissingRequired
  next_smallest_truthful_gap = $NextGap
  recommended_next_slice = $RecommendedSlice
  recommended_handoff_source = $RecommendedHandoffSource
  recommended_proof_script = $RecommendedProofScript
  recommended_handoff = $RecommendedHandoff
  stop_observed = $StopObserved
  side_effects_bounded = $SideEffectsBounded
  proof_scope = [ordered]@{
    synthetic_tray_runtime_readback = $true
    os_tray_registered = $false
    tray_icon_claim_source = 'proof_runtime_readback'
    persistent_supervision_enabled = $false
    global_hotkey_registered = $false
    overlay_opened = $false
    summon_binding_enabled = $false
  }
  start_resident = [ordered]@{
    exit_code = [int](Get-PropertyValue -Payload $StartResult -Name 'exit_code' -Default 1)
    status = [string](Get-PropertyValue -Payload $StartPayload -Name 'status' -Default '')
    resident_host_process = [bool](Get-PropertyValue -Payload $StartPayload -Name 'resident_host_process' -Default $false)
    resident_supervised_runtime = [bool](Get-PropertyValue -Payload $StartPayload -Name 'resident_supervised_runtime' -Default $false)
    supervisor_pid = [int](Get-PropertyValue -Payload $StartPayload -Name 'supervisor_pid' -Default 0)
    host_pid = [int](Get-PropertyValue -Payload (Get-PropertyValue -Payload $StartPayload -Name 'host_readback') -Name 'pid' -Default 0)
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $StartPayload -Name 'next_smallest_truthful_gap' -Default '')
    parse_error = [string](Get-PropertyValue -Payload $StartResult -Name 'parse_error' -Default '')
    stderr = [string](Get-PropertyValue -Payload $StartResult -Name 'stderr' -Default '')
  }
  tray_runtime_state = [ordered]@{
    kind = [string](Get-PropertyValue -Payload $TrayRuntimeState -Name 'kind' -Default '')
    status = [string](Get-PropertyValue -Payload $TrayRuntimeState -Name 'status' -Default '')
    pid = [int](Get-PropertyValue -Payload $TrayRuntimeState -Name 'pid' -Default 0)
    tray_icon_visible = [bool](Get-PropertyValue -Payload $TrayRuntimeState -Name 'tray_icon_visible' -Default $false)
    proof_only = [bool](Get-PropertyValue -Payload $TrayRuntimeState -Name 'proof_only' -Default $false)
    os_tray_registered = [bool](Get-PropertyValue -Payload $TrayRuntimeState -Name 'os_tray_registered' -Default $true)
  }
  tray_presence = [ordered]@{
    exit_code = [int](Get-PropertyValue -Payload $TrayPresenceResult -Name 'exit_code' -Default 1)
    status = [string](Get-PropertyValue -Payload $TrayPresencePayload -Name 'status' -Default '')
    ready = [bool](Get-PropertyValue -Payload $TrayPresencePayload -Name 'ready' -Default $false)
    tray_presence = [bool](Get-PropertyValue -Payload $TrayPresencePayload -Name 'tray_presence' -Default $false)
    parse_error = [string](Get-PropertyValue -Payload $TrayPresenceResult -Name 'parse_error' -Default '')
    stderr = [string](Get-PropertyValue -Payload $TrayPresenceResult -Name 'stderr' -Default '')
  }
  persistent_supervision_plan = [ordered]@{
    exit_code = [int](Get-PropertyValue -Payload $PlanResult -Name 'exit_code' -Default 1)
    status = [string](Get-PropertyValue -Payload $PlanPayload -Name 'status' -Default '')
    required_before_enable_ready = [bool](Get-PropertyValue -Payload $PlanPayload -Name 'required_before_enable_ready' -Default $false)
    first_missing_required_before_enable = $FirstMissing
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $PlanPayload -Name 'next_smallest_truthful_gap' -Default '')
    parse_error = [string](Get-PropertyValue -Payload $PlanResult -Name 'parse_error' -Default '')
    stderr = [string](Get-PropertyValue -Payload $PlanResult -Name 'stderr' -Default '')
  }
  resident_dependency = if ($ResidentDependency.Count -gt 0) { $ResidentDependency[0] } else { $null }
  tray_dependency = if ($TrayDependency.Count -gt 0) { $TrayDependency[0] } else { $null }
  plan_first_missing_requirement_handoff = $PlanHandoff
  stop_resident = [ordered]@{
    exit_code = [int](Get-PropertyValue -Payload $StopResult -Name 'exit_code' -Default 1)
    status = [string](Get-PropertyValue -Payload $StopPayload -Name 'status' -Default '')
    resident_host_process = [bool](Get-PropertyValue -Payload $StopPayload -Name 'resident_host_process' -Default $true)
    resident_supervised_runtime = [bool](Get-PropertyValue -Payload $StopPayload -Name 'resident_supervised_runtime' -Default $true)
    parse_error = [string](Get-PropertyValue -Payload $StopResult -Name 'parse_error' -Default '')
    stderr = [string](Get-PropertyValue -Payload $StopResult -Name 'stderr' -Default '')
  }
  governance = [ordered]@{
    diagnostic_only = $false
    read_only_contract = $false
    temporary_runtime_state_write = $true
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    local_process_launch_authority = $true
    process_supervision_authority = $true
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    tray_registration_authority = $false
    tray_icon_authority = $false
    hotkey_registration_authority = $false
    overlay_control_authority = $false
    window_management_authority = $false
    summon_authority = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    mutation_authority_granted = $false
  }
}

$Payload | ConvertTo-Json -Depth 12
if ($ProofPassed) {
  exit 0
}
exit 1
