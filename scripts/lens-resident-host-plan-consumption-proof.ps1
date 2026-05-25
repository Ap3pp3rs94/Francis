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

function Remove-ProofDataRoot {
  param(
    [string]$Path,
    [int]$MaxAttempts = 30,
    [int]$DelayMilliseconds = 100
  )

  if (-not (Test-SafeTempPath -Path $Path)) {
    return $false
  }

  for ($Attempt = 0; $Attempt -lt $MaxAttempts; $Attempt += 1) {
    try {
      if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
      }
    } catch {
    }

    if (-not (Test-Path -LiteralPath $Path)) {
      return $true
    }

    Start-Sleep -Milliseconds $DelayMilliseconds
  }

  return -not (Test-Path -LiteralPath $Path)
}

$PowerShellPath = Get-PowerShellPath
$HostSupervisorPath = Join-Path $PSScriptRoot 'lens-host-supervisor.ps1'
$PlanPath = Join-Path $PSScriptRoot 'lens-persistent-supervision-plan.ps1'
$DataRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('francis-lens-plan-consumption-proof-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null

$StartResult = $null
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
    $DataRootRemoved = Remove-ProofDataRoot -Path $DataRoot
  }
}

$StartPayload = Get-PropertyValue -Payload $StartResult -Name 'payload'
$PlanPayload = Get-PropertyValue -Payload $PlanResult -Name 'payload'
$StopPayload = Get-PropertyValue -Payload $StopResult -Name 'payload'

$Dependencies = @(Get-PropertyValue -Payload $PlanPayload -Name 'enablement_dependency_readback' -Default @())
$ResidentDependency = @($Dependencies | Where-Object { [string](Get-PropertyValue -Payload $_ -Name 'id' -Default '') -eq 'resident_host_process' } | Select-Object -First 1)
$PlanHandoff = Get-PropertyValue -Payload $PlanPayload -Name 'first_missing_requirement_handoff'
$MissingRequired = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $PlanPayload -Name 'missing_required_before_enable' -Default @())
$FirstMissing = [string](Get-PropertyValue -Payload $PlanPayload -Name 'first_missing_required_before_enable' -Default '')
$StartGovernance = Get-PropertyValue -Payload $StartPayload -Name 'governance'
$PlanGovernance = Get-PropertyValue -Payload $PlanPayload -Name 'governance'

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

$PlanConsumedLiveResidentHost = (
  [int](Get-PropertyValue -Payload $PlanResult -Name 'exit_code' -Default 1) -eq 0 -and
  [string](Get-PropertyValue -Payload $PlanPayload -Name 'status' -Default '') -eq 'blocked' -and
  $ResidentDependencyReady -and
  $FirstMissing -eq 'tray_presence' -and
  -not ($MissingRequired -contains 'resident_host_process')
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
  [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'read_only_contract' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'mutation_authority_granted' -Default $true)
)

$ProofPassed = $LiveResidentHostObserved -and $PlanConsumedLiveResidentHost -and $StopObserved -and $SideEffectsBounded -and $DataRootRemoved
$NextGap = if ($PlanConsumedLiveResidentHost) { 'tray_presence' } else { 'resident_host_process_not_consumed_by_plan' }
$RecommendedSlice = if ($PlanConsumedLiveResidentHost) {
  'resolve_tray_presence_before_persistent_supervision_enablement'
} else {
  'debug_resident_host_plan_consumption_readback'
}
$RecommendedHandoff = $null
$RecommendedHandoffSource = $null
$RecommendedProofScript = $null
if ($PlanConsumedLiveResidentHost -and $null -ne $PlanHandoff) {
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
  kind = 'lens.resident_host.plan_consumption_proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  ok = $ProofPassed
  mode = $Mode.ToLowerInvariant()
  stage = 'Stage 6 / Lens MVP'
  stage_state = 'active'
  ready_to_close = $false
  data_root_removed = $DataRootRemoved
  live_resident_host_observed = $LiveResidentHostObserved
  persistent_supervision_plan_consumed_live_resident_host = $PlanConsumedLiveResidentHost
  resident_dependency_ready = $ResidentDependencyReady
  first_missing_required_before_enable = $FirstMissing
  missing_required_before_enable = $MissingRequired
  next_smallest_truthful_gap = $NextGap
  recommended_next_slice = $RecommendedSlice
  recommended_handoff_source = $RecommendedHandoffSource
  recommended_proof_script = $RecommendedProofScript
  recommended_handoff = $RecommendedHandoff
  stop_observed = $StopObserved
  side_effects_bounded = $SideEffectsBounded
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
