[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(5, 60)]
  [int]$StartupTimeoutSeconds = 30,

  [ValidateRange(2, 30)]
  [int]$ForegroundRunSeconds = 2,

  [ValidateRange(2, 30)]
  [int]$HostLaunchRunSeconds = 3,

  [ValidateRange(3, 30)]
  [int]$SupervisorRunSeconds = 20,

  [ValidateRange(30, 600)]
  [int]$ChildProofTimeoutSeconds = 360
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

function Get-PowerShellPath {
  try {
    $Current = Get-Process -Id $PID -ErrorAction Stop
    if (-not [string]::IsNullOrWhiteSpace([string]$Current.Path)) {
      return [string]$Current.Path
    }
  } catch {
  }

  $Pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
  if ($null -ne $Pwsh) {
    return [string]$Pwsh.Source
  }
  $WindowsPowerShell = Get-Command powershell -ErrorAction SilentlyContinue
  if ($null -ne $WindowsPowerShell) {
    return [string]$WindowsPowerShell.Source
  }
  return ''
}

function Get-PropertyValue {
  param(
    [object]$Payload,
    [string]$Name,
    [object]$Default = $null
  )

  if ($null -eq $Payload) {
    return $Default
  }
  if ($Payload -is [System.Collections.IDictionary]) {
    if ($Payload.Contains($Name) -and $null -ne $Payload[$Name]) {
      return $Payload[$Name]
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
  param([object]$Value)

  if ($null -eq $Value) {
    return @()
  }
  if ($Value -is [string]) {
    if ([string]::IsNullOrWhiteSpace($Value)) {
      return @()
    }
    return @($Value)
  }
  if ($Value -is [System.Array]) {
    return @($Value | ForEach-Object {
        $Item = [string]$_
        if (-not [string]::IsNullOrWhiteSpace($Item)) {
          $Item
        }
      })
  }
  $SingleValue = [string]$Value
  if ([string]::IsNullOrWhiteSpace($SingleValue)) {
    return @()
  }
  return @($SingleValue)
}

function Quote-ProcessArgument {
  param([string]$Value)

  if ($null -eq $Value) {
    return '""'
  }
  return '"' + ($Value -replace '"', '\"') + '"'
}

function Stop-ProcessTree {
  param([System.Diagnostics.Process]$Process)

  if ($null -eq $Process -or $Process.HasExited) {
    return
  }
  try {
    $Process.Kill($true)
  } catch {
    try {
      $Process.Kill()
    } catch {
    }
  }
}

function Invoke-JsonScript {
  param(
    [string]$PowerShellPath,
    [string]$ScriptPath,
    [string[]]$ScriptArgs = @(),
    [int]$TimeoutSeconds = $ChildProofTimeoutSeconds
  )

  if ([string]::IsNullOrWhiteSpace($PowerShellPath) -or -not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
      error = 'script_unavailable'
      timed_out = $false
      timeout_seconds = $TimeoutSeconds
      duration_ms = 0
    }
  }

  $ArgumentParts = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    (Quote-ProcessArgument -Value $ScriptPath)
  )
  foreach ($Arg in $ScriptArgs) {
    $ArgumentParts += (Quote-ProcessArgument -Value $Arg)
  }

  $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
  $StartInfo.FileName = $PowerShellPath
  $StartInfo.Arguments = $ArgumentParts -join ' '
  $StartInfo.WorkingDirectory = $RepoRoot
  $StartInfo.UseShellExecute = $false
  $StartInfo.CreateNoWindow = $true
  $StartInfo.RedirectStandardOutput = $true
  $StartInfo.RedirectStandardError = $true

  $Process = [System.Diagnostics.Process]::new()
  $Process.StartInfo = $StartInfo
  $Started = $false
  $Timer = [System.Diagnostics.Stopwatch]::StartNew()
  try {
    $Started = $Process.Start()
  } catch {
    $Timer.Stop()
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
      error = [string]$_.Exception.Message
      timed_out = $false
      timeout_seconds = $TimeoutSeconds
      duration_ms = [int]$Timer.ElapsedMilliseconds
    }
  }
  if (-not $Started) {
    $Timer.Stop()
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
      error = 'process_not_started'
      timed_out = $false
      timeout_seconds = $TimeoutSeconds
      duration_ms = [int]$Timer.ElapsedMilliseconds
    }
  }

  $StdoutTask = $Process.StandardOutput.ReadToEndAsync()
  $StderrTask = $Process.StandardError.ReadToEndAsync()
  $Exited = $Process.WaitForExit($TimeoutSeconds * 1000)
  if (-not $Exited) {
    Stop-ProcessTree -Process $Process
    [void]$Process.WaitForExit(5000)
    $Timer.Stop()
    return [ordered]@{
      exit_code = 124
      payload = $null
      output = ''
      error = 'timeout'
      timed_out = $true
      timeout_seconds = $TimeoutSeconds
      duration_ms = [int]$Timer.ElapsedMilliseconds
    }
  }

  $Text = $StdoutTask.GetAwaiter().GetResult()
  $ErrorText = $StderrTask.GetAwaiter().GetResult()
  $Timer.Stop()
  $Payload = $null
  try {
    $Payload = $Text | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $Payload = $null
  }

  return [ordered]@{
    exit_code = [int]$Process.ExitCode
    payload = $Payload
    output = $Text
    error = $ErrorText
    timed_out = $false
    timeout_seconds = $TimeoutSeconds
    duration_ms = [int]$Timer.ElapsedMilliseconds
  }
}

function Invoke-JsonScriptWithProofRetry {
  param(
    [string]$PowerShellPath,
    [string]$ScriptPath,
    [string[]]$ScriptArgs = @(),
    [string]$ExpectedKind,
    [int]$Attempts = 2,
    [int]$TimeoutSeconds = $ChildProofTimeoutSeconds
  )

  $LastProof = $null
  for ($Attempt = 1; $Attempt -le $Attempts; $Attempt++) {
    $Result = @(Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $ScriptPath -ScriptArgs $ScriptArgs -TimeoutSeconds $TimeoutSeconds)
    $Proof = if ($Result.Count -gt 0) { $Result[-1] } else { $null }
    $LastProof = $Proof

    $ExitCode = -1
    $Payload = $null
    if ($Proof -is [System.Collections.IDictionary]) {
      if ($Proof.Contains('exit_code') -and $null -ne $Proof['exit_code']) {
        $ExitCode = [int]$Proof['exit_code']
      }
      if ($Proof.Contains('payload') -and $null -ne $Proof['payload']) {
        $Payload = $Proof['payload']
      }
    }

    if (
      $ExitCode -eq 0 -and
      [string](Get-PropertyValue -Payload $Payload -Name 'kind' -Default '') -eq $ExpectedKind -and
      [string](Get-PropertyValue -Payload $Payload -Name 'status' -Default '') -eq 'proof_passed'
    ) {
      return $Proof
    }
    if ([bool](Get-PropertyValue -Payload $Proof -Name 'timed_out' -Default $false)) {
      return $Proof
    }
    if ($Attempt -lt $Attempts) {
      Start-Sleep -Milliseconds 750
    }
  }
  return $LastProof
}

function New-ChildProofRunSummary {
  param(
    [string]$Name,
    [object]$Result
  )

  return [ordered]@{
    name = $Name
    exit_code = [int](Get-PropertyValue -Payload $Result -Name 'exit_code' -Default -1)
    timed_out = [bool](Get-PropertyValue -Payload $Result -Name 'timed_out' -Default $false)
    timeout_seconds = [int](Get-PropertyValue -Payload $Result -Name 'timeout_seconds' -Default $ChildProofTimeoutSeconds)
    duration_ms = [int](Get-PropertyValue -Payload $Result -Name 'duration_ms' -Default 0)
    error = [string](Get-PropertyValue -Payload $Result -Name 'error' -Default '')
  }
}

function New-Check {
  param(
    [string]$Id,
    [string]$Status,
    [bool]$Passed,
    [string]$Evidence,
    [string]$Reason
  )

  return [ordered]@{
    id = $Id
    status = $Status
    passed = $Passed
    evidence = $Evidence
    reason = $Reason
  }
}

function Get-CriterionById {
  param(
    [object[]]$Criteria,
    [string]$Id
  )

  foreach ($Criterion in @($Criteria)) {
    if ([string](Get-PropertyValue -Payload $Criterion -Name 'id' -Default '') -eq $Id) {
      return $Criterion
    }
  }
  return $null
}

$PowerShellPath = Get-PowerShellPath
$Stage6CheckpointPath = Join-Path $PSScriptRoot 'lens-stage6-checkpoint.ps1'
$HostSupervisionProofPath = Join-Path $PSScriptRoot 'lens-host-supervision-proof.ps1'

$CheckpointResult = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $Stage6CheckpointPath -ScriptArgs @(
  '-Mode', 'Status',
  '-StartupTimeoutSeconds', [string]$StartupTimeoutSeconds,
  '-HostLaunchRunSeconds', [string]$HostLaunchRunSeconds,
  '-SupervisorRunSeconds', [string]$SupervisorRunSeconds
)
$HostSupervisionResult = Invoke-JsonScriptWithProofRetry -PowerShellPath $PowerShellPath -ScriptPath $HostSupervisionProofPath -ScriptArgs @(
  '-Mode', 'Status',
  '-ForegroundRunSeconds', [string]$ForegroundRunSeconds,
  '-HostLaunchRunSeconds', [string]$HostLaunchRunSeconds
) -ExpectedKind 'lens.host.supervision_readiness_proof'
$ChildProofRuns = @(
  (New-ChildProofRunSummary -Name 'stage6_checkpoint' -Result $CheckpointResult),
  (New-ChildProofRunSummary -Name 'host_supervision' -Result $HostSupervisionResult)
)
$ChildProofTimeouts = @($ChildProofRuns | Where-Object { [bool]$_['timed_out'] } | ForEach-Object { [string]$_['name'] })

$CheckpointPayload = Get-PropertyValue -Payload $CheckpointResult -Name 'payload'
$HostSupervisionPayload = Get-PropertyValue -Payload $HostSupervisionResult -Name 'payload'
$CheckpointGovernance = Get-PropertyValue -Payload $CheckpointPayload -Name 'governance'
$HostSupervisionGovernance = Get-PropertyValue -Payload $HostSupervisionPayload -Name 'governance'
$CheckpointCriteria = @(Get-PropertyValue -Payload $CheckpointPayload -Name 'criteria' -Default @())
$SystemResidentCriterion = Get-CriterionById -Criteria $CheckpointCriteria -Id 'system_resident_presence'
$ActivationBoundaryProof = Get-PropertyValue -Payload $CheckpointPayload -Name 'resident_overlay_activation_boundary_proof'
$HostSupervisionProof = Get-PropertyValue -Payload $HostSupervisionPayload -Name 'proof'
$ServicePlanBlockedBy = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_plan_blocked_by' -Default @())

$CheckpointObserved = (
  [int](Get-PropertyValue -Payload $CheckpointResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $CheckpointPayload -Name 'kind' -Default '') -eq 'lens.stage6.checkpoint' -and
  [string](Get-PropertyValue -Payload $CheckpointPayload -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $CheckpointPayload -Name 'stage_state' -Default '') -eq 'active' -and
  -not [bool](Get-PropertyValue -Payload $CheckpointPayload -Name 'ready_to_close' -Default $true) -and
  [string](Get-PropertyValue -Payload $SystemResidentCriterion -Name 'status' -Default '') -eq 'resident_overlay_activation_boundary_observed' -and
  [bool](Get-PropertyValue -Payload $ActivationBoundaryProof -Name 'ok' -Default $false)
)
$HostSupervisionObserved = (
  [int](Get-PropertyValue -Payload $HostSupervisionResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'kind' -Default '') -eq 'lens.host.supervision_readiness_proof' -and
  [string](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'supervision_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'ready_for_resident_claim' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'resident_claim_allowed' -Default $true)
)
$ProcessSupervisionDenied = (
  $HostSupervisionObserved -and
  [string](Get-PropertyValue -Payload $HostSupervisionProof -Name 'process_supervision_status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'supervised' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'process_supervision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'process_restart_authority' -Default $true)
)
$ServiceActivationPlanBlocked = (
  $HostSupervisionObserved -and
  [string](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_plan_status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_plan_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_plan_would_install' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_plan_would_start' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'service_installed' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'service_managed' -Default $true) -and
  $ServicePlanBlockedBy -contains 'service_install_authority_false' -and
  $ServicePlanBlockedBy -contains 'service_control_authority_false'
)
$AuthorityBoundary = (
  $CheckpointObserved -and
  $HostSupervisionObserved -and
  [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostSupervisionGovernance -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'resident_overlay_activation_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'process_restart_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'process_supervision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'service_install_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionGovernance -Name 'service_install_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionGovernance -Name 'service_control_authority' -Default $true)
)

$Checks = @(
  (New-Check -Id 'stage6_checkpoint_activation_boundary' -Status $(if ($CheckpointObserved) { 'activation_boundary_checkpointed' } else { 'failed' }) -Passed $CheckpointObserved -Evidence 'scripts/lens-stage6-checkpoint.ps1 -Mode Status' -Reason 'The latest Stage 6 checkpoint must already consume the overlay activation boundary proof.')
  (New-Check -Id 'host_supervision_boundary' -Status $(if ($HostSupervisionObserved) { 'supervision_blocked' } else { 'failed' }) -Passed $HostSupervisionObserved -Evidence 'scripts/lens-host-supervision-proof.ps1 -Mode Status' -Reason 'The host supervision proof must remain observable and blocked.')
  (New-Check -Id 'process_supervision_denied' -Status $(if ($ProcessSupervisionDenied) { 'blocked' } else { 'unexpected_authority' }) -Passed $ProcessSupervisionDenied -Evidence 'process_supervision_authority + process_restart_authority' -Reason 'Resident process supervision and restart authority remain denied.')
  (New-Check -Id 'service_activation_plan_blocked' -Status $(if ($ServiceActivationPlanBlocked) { 'blocked_no_service_activation' } else { 'unexpected_service_activation' }) -Passed $ServiceActivationPlanBlocked -Evidence 'service_plan' -Reason 'The service plan does not install, start, or manage a resident host service.')
  (New-Check -Id 'authority_boundary' -Status $(if ($AuthorityBoundary) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $AuthorityBoundary -Evidence 'checkpoint.governance + host_supervision.governance' -Reason 'The proof chain must not grant execution, approval, memory, resident activation, process supervision, service, tray, hotkey, overlay, summon, or capture authority.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })
$AllBlockers = @(
  (ConvertTo-StringArray -Value (Get-PropertyValue -Payload $CheckpointPayload -Name 'blockers' -Default @())) +
  (ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostSupervisionPayload -Name 'blockers' -Default @())) +
  @(
    'process_supervision_authority_not_granted',
    'process_restart_authority_not_granted',
    'service_install_authority_not_granted',
    'service_control_authority_not_granted',
    'resident_host_process_not_supervised',
    'resident_supervision_disabled'
  ) | Sort-Object -Unique
)
$AllBlockers = @($AllBlockers | Where-Object {
    $_ -ne 'operator_experience_proof_missing' -and $_ -ne 'live_operator_experience_proof_missing'
  })

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.process_supervision_authority_boundary.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  startup_timeout_seconds = $StartupTimeoutSeconds
  foreground_run_seconds = $ForegroundRunSeconds
  host_launch_run_seconds = $HostLaunchRunSeconds
  supervisor_run_seconds = $SupervisorRunSeconds
  child_proof_timeout_seconds = $ChildProofTimeoutSeconds
  child_proof_timeouts = [string[]]@($ChildProofTimeouts)
  child_proof_runs = @($ChildProofRuns)
  stage6_checkpoint_observed = $CheckpointObserved
  host_supervision_boundary_observed = $HostSupervisionObserved
  process_supervision_boundary_observed = $ProcessSupervisionDenied
  service_activation_plan_observed = $ServiceActivationPlanBlocked
  bounded_local_process_launch_observed = [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'bounded_host_launch_observed' -Default $false)
  supervision_ready = $false
  ready_for_resident_claim = $false
  resident_claim_allowed = $false
  resident_host_process = $false
  resident_host_supervised = $false
  service_installed = $false
  service_managed = $false
  process_supervision_ready = $false
  service_activation_ready = $false
  tray_presence = $false
  global_hotkey_bound = $false
  overlay_window = $false
  summon_anywhere = $false
  would_supervise_process = $false
  would_restart_process = $false
  would_install_service = $false
  would_start_service = $false
  would_write_wrapper = $false
  would_write_memory = $false
  would_decide_approval = $false
  checks = @($Checks)
  blockers = @($AllBlockers)
  proof = [ordered]@{
    checkpoint_status = [string](Get-PropertyValue -Payload $CheckpointPayload -Name 'status' -Default '')
    checkpoint_stage_state = [string](Get-PropertyValue -Payload $CheckpointPayload -Name 'stage_state' -Default '')
    checkpoint_system_resident_status = [string](Get-PropertyValue -Payload $SystemResidentCriterion -Name 'status' -Default '')
    checkpoint_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $CheckpointPayload -Name 'next_smallest_truthful_gap' -Default '')
    activation_boundary_status = [string](Get-PropertyValue -Payload $ActivationBoundaryProof -Name 'status' -Default '')
    activation_boundary_ok = [bool](Get-PropertyValue -Payload $ActivationBoundaryProof -Name 'ok' -Default $false)
    host_supervision_status = [string](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'status' -Default '')
    host_supervision_ready = [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'supervision_ready' -Default $false)
    host_ready_for_resident_claim = [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'ready_for_resident_claim' -Default $false)
    process_supervision_status = [string](Get-PropertyValue -Payload $HostSupervisionProof -Name 'process_supervision_status' -Default '')
    service_control_status = [string](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_control_status' -Default '')
    service_plan_status = [string](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_plan_status' -Default '')
    service_plan_ready = [bool](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_plan_ready' -Default $false)
    service_plan_would_install = [bool](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_plan_would_install' -Default $false)
    service_plan_would_start = [bool](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_plan_would_start' -Default $false)
    service_plan_blocked_by = $ServicePlanBlockedBy
    service_status = [string](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_status' -Default '')
  }
  next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $CheckpointPayload -Name 'next_smallest_truthful_gap' -Default 'supervised_resident_host_runtime_authority_grant_readiness_audit')
  governance = [ordered]@{
    diagnostic_only = $true
    checkpoint_readback = $CheckpointObserved
    live_http_readback = [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'live_http_readback' -Default $false)
    temporary_api_process = [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'temporary_api_process' -Default $false)
    bounded_host_launch = [bool](Get-PropertyValue -Payload $HostSupervisionGovernance -Name 'bounded_host_launch' -Default $false)
    bounded_process_launch = [bool](Get-PropertyValue -Payload $HostSupervisionGovernance -Name 'bounded_process_launch' -Default $false)
    bounded_supervisor_observation = [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'bounded_supervisor_observation' -Default $false)
    resident_overlay_activation_boundary_observed = [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'resident_overlay_activation_boundary_observed' -Default $false)
    resident_host_supervision_authority_denial_boundary_observed = [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'resident_host_supervision_authority_denial_boundary_observed' -Default $false)
    resident_host_supervision_authority_denial_receipt_readback_observed = [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'resident_host_supervision_authority_denial_receipt_readback_observed' -Default $false)
    resident_host_supervision_authority_grant_receipt_readback_observed = [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'resident_host_supervision_authority_grant_receipt_readback_observed' -Default $false)
    resident_host_supervision_authority_readiness_audit_observed = [bool](Get-PropertyValue -Payload $CheckpointGovernance -Name 'resident_host_supervision_authority_readiness_audit_observed' -Default $false)
    temporary_runtime_state_write = $true
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    resident_overlay_activation_authority = $false
    process_restart_authority = $false
    process_supervision_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = [bool](Get-PropertyValue -Payload $HostSupervisionGovernance -Name 'local_process_launch_authority' -Default $false)
    api_local_process_launch_authority = $false
    activation_local_process_launch_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    tray_icon_authority = $false
    receipt_write_authority = $false
    denial_receipt_write_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Stage 6 process supervision authority remains a boundary: checkpointed overlay activation proof and host supervision proof are observable, but Francis does not supervise, restart, install, start, or manage a resident Lens host service.'
}

$Payload | ConvertTo-Json -Depth 10
if ($ProofPassed) {
  exit 0
}
exit 1
