[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(5, 60)]
  [int]$StartupTimeoutSeconds = 20,

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

function Get-PowerShellPath {
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
    [AllowNull()]
    [object]$Payload,
    [string]$Name,
    [AllowNull()]
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
  param(
    [AllowNull()]
    [object]$Value
  )

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
    [Parameter(Mandatory = $true)]
    [string]$PowerShellPath,

    [Parameter(Mandatory = $true)]
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
    [Parameter(Mandatory = $true)]
    [string]$PowerShellPath,

    [Parameter(Mandatory = $true)]
    [string]$ScriptPath,

    [string[]]$ScriptArgs = @(),

    [Parameter(Mandatory = $true)]
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

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$RuntimeBoundaryScript = Join-Path $PSScriptRoot 'lens-resident-host-runtime-boundary-proof.ps1'
$ProcessBoundaryScript = Join-Path $PSScriptRoot 'lens-process-supervision-authority-boundary-proof.ps1'
$PowerShellPath = Get-PowerShellPath

$RuntimeResult = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $RuntimeBoundaryScript -ScriptArgs @(
  '-Mode', 'Status',
  '-ForegroundRunSeconds', [string]$ForegroundRunSeconds,
  '-HostLaunchRunSeconds', [string]$HostLaunchRunSeconds
)
$ProcessResult = Invoke-JsonScriptWithProofRetry -PowerShellPath $PowerShellPath -ScriptPath $ProcessBoundaryScript -ScriptArgs @(
  '-Mode', 'Status',
  '-StartupTimeoutSeconds', [string]$StartupTimeoutSeconds,
  '-ForegroundRunSeconds', [string]$ForegroundRunSeconds,
  '-HostLaunchRunSeconds', [string]$HostLaunchRunSeconds,
  '-SupervisorRunSeconds', [string]$SupervisorRunSeconds,
  '-ChildProofTimeoutSeconds', [string]$ChildProofTimeoutSeconds
) -ExpectedKind 'lens.process_supervision_authority_boundary.proof'
$ChildProofRuns = @(
  (New-ChildProofRunSummary -Name 'resident_host_runtime_boundary' -Result $RuntimeResult),
  (New-ChildProofRunSummary -Name 'process_supervision_boundary' -Result $ProcessResult)
)
$ChildProofTimeouts = @($ChildProofRuns | Where-Object { [bool]$_['timed_out'] } | ForEach-Object { [string]$_['name'] })

$RuntimePayload = Get-PropertyValue -Payload $RuntimeResult -Name 'payload'
$ProcessPayload = Get-PropertyValue -Payload $ProcessResult -Name 'payload'
$RuntimeGovernance = Get-PropertyValue -Payload $RuntimePayload -Name 'governance'
$ProcessGovernance = Get-PropertyValue -Payload $ProcessPayload -Name 'governance'
$RuntimeBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $RuntimePayload -Name 'blockers' -Default @())
$ProcessBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ProcessPayload -Name 'blockers' -Default @())

$RuntimeHandoffObserved = (
  [int](Get-PropertyValue -Payload $RuntimeResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $RuntimePayload -Name 'kind' -Default '') -eq 'lens.resident_host.runtime_blocker_boundary.proof' -and
  [string](Get-PropertyValue -Payload $RuntimePayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $RuntimePayload -Name 'runtime_boundary_blocked' -Default $false) -and
  [bool](Get-PropertyValue -Payload $RuntimePayload -Name 'process_supervision_handoff_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $RuntimePayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_host_process_not_supervised' -and
  [string](Get-PropertyValue -Payload $RuntimePayload -Name 'resident_host_process_blocker' -Default '') -eq 'resident_host_process_not_supervised'
)
$ProcessBoundaryObserved = (
  [int](Get-PropertyValue -Payload $ProcessResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $ProcessPayload -Name 'kind' -Default '') -eq 'lens.process_supervision_authority_boundary.proof' -and
  [string](Get-PropertyValue -Payload $ProcessPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $ProcessPayload -Name 'process_supervision_boundary_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ProcessPayload -Name 'service_activation_plan_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $ProcessPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'stage6_lens_completion_audit'
)
$HandoffConsumed = (
  $RuntimeHandoffObserved -and
  $ProcessBoundaryObserved -and
  $RuntimeBlockers -contains 'resident_host_process_not_supervised' -and
  $ProcessBlockers -contains 'resident_host_process_not_supervised' -and
  $ProcessBlockers -contains 'process_supervision_authority_not_granted' -and
  $ProcessBlockers -contains 'process_restart_authority_not_granted' -and
  $ProcessBlockers -contains 'service_install_authority_not_granted' -and
  $ProcessBlockers -contains 'service_control_authority_not_granted'
)
$AuthorityDenied = (
  [bool](Get-PropertyValue -Payload $RuntimeGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ProcessGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $RuntimeGovernance -Name 'bounded_local_process_launch' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ProcessGovernance -Name 'bounded_host_launch' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ProcessGovernance -Name 'bounded_process_launch' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $RuntimeGovernance -Name 'product_execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ProcessGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ProcessGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ProcessGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ProcessGovernance -Name 'process_supervision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ProcessGovernance -Name 'process_restart_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ProcessGovernance -Name 'service_install_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ProcessGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ProcessGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ProcessGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ProcessGovernance -Name 'capture_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ProcessGovernance -Name 'new_sensing_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ProcessGovernance -Name 'mutation_authority_granted' -Default $true)
)

$Checks = @(
  (New-Check -Id 'resident_host_process_handoff' -Status $(if ($RuntimeHandoffObserved) { 'process_blocker_handoff_observed' } else { 'missing_or_unexpected' }) -Passed $RuntimeHandoffObserved -Evidence 'scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status' -Reason 'The resident-host runtime boundary must hand off to resident_host_process_not_supervised.'),
  (New-Check -Id 'process_supervision_boundary' -Status $(if ($ProcessBoundaryObserved) { 'process_supervision_blocked' } else { 'missing_or_unexpected' }) -Passed $ProcessBoundaryObserved -Evidence 'scripts/lens-process-supervision-authority-boundary-proof.ps1 -Mode Status' -Reason 'The process-supervision authority boundary must consume the unsupervised process blocker and return to Stage 6 completion audit.'),
  (New-Check -Id 'handoff_consumed' -Status $(if ($HandoffConsumed) { 'blocker_consumed' } else { 'handoff_mismatch' }) -Passed $HandoffConsumed -Evidence 'resident-host runtime blockers + process-supervision blockers' -Reason 'The same unsupervised resident-host process blocker must be preserved across both proof payloads.'),
  (New-Check -Id 'authority_denied' -Status $(if ($AuthorityDenied) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $AuthorityDenied -Evidence 'runtime boundary governance + process-supervision governance' -Reason 'The composed proof may launch bounded diagnostics but must not grant product execution, process supervision, restart, service, summon, memory, approval, capture, sensing, or mutation authority.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })
$BlockerBag = @()
$BlockerBag += @($RuntimeBlockers)
$BlockerBag += @($ProcessBlockers)
$BlockerBag += @(
  'resident_host_process_not_supervised',
  'process_supervision_authority_not_granted',
  'process_restart_authority_not_granted',
  'service_install_authority_not_granted',
  'service_control_authority_not_granted'
)
$AllBlockers = [string[]]@($BlockerBag | Sort-Object -Unique)

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.resident_host.process_supervision_blocker.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  stage = 'Stage 6 / Lens MVP'
  stage_state = 'active'
  acceptance_criterion = 'summon_anywhere'
  previous_next_smallest_truthful_gap = 'resident_host_process_not_supervised'
  next_smallest_truthful_gap = 'stage6_lens_completion_audit'
  resident_host_process_handoff_observed = $RuntimeHandoffObserved
  process_supervision_boundary_observed = $ProcessBoundaryObserved
  handoff_consumed = $HandoffConsumed
  authority_denied = $AuthorityDenied
  startup_timeout_seconds = $StartupTimeoutSeconds
  foreground_run_seconds = $ForegroundRunSeconds
  host_launch_run_seconds = $HostLaunchRunSeconds
  supervisor_run_seconds = $SupervisorRunSeconds
  child_proof_timeout_seconds = $ChildProofTimeoutSeconds
  child_proof_timeouts = [string[]]@($ChildProofTimeouts)
  child_proof_runs = @($ChildProofRuns)
  resident_host_process_state = [string](Get-PropertyValue -Payload $RuntimePayload -Name 'resident_host_process_state' -Default '')
  resident_host_process_blocker = [string](Get-PropertyValue -Payload $RuntimePayload -Name 'resident_host_process_blocker' -Default '')
  supervision_ready = $false
  ready_for_resident_claim = $false
  resident_claim_allowed = $false
  resident_host_supervised = $false
  service_installed = $false
  service_managed = $false
  process_supervision_ready = $false
  service_activation_ready = $false
  would_supervise_process = $false
  would_restart_process = $false
  would_install_service = $false
  would_start_service = $false
  would_write_memory = $false
  would_decide_approval = $false
  checks = @($Checks)
  blockers = $AllBlockers
  proof = [ordered]@{
    runtime_boundary_status = [string](Get-PropertyValue -Payload $RuntimePayload -Name 'status' -Default '')
    runtime_boundary_next_gap = [string](Get-PropertyValue -Payload $RuntimePayload -Name 'next_smallest_truthful_gap' -Default '')
    runtime_boundary_process_state = [string](Get-PropertyValue -Payload $RuntimePayload -Name 'resident_host_process_state' -Default '')
    process_boundary_status = [string](Get-PropertyValue -Payload $ProcessPayload -Name 'status' -Default '')
    process_boundary_next_gap = [string](Get-PropertyValue -Payload $ProcessPayload -Name 'next_smallest_truthful_gap' -Default '')
    process_boundary_observed = [bool](Get-PropertyValue -Payload $ProcessPayload -Name 'process_supervision_boundary_observed' -Default $false)
    service_activation_plan_observed = [bool](Get-PropertyValue -Payload $ProcessPayload -Name 'service_activation_plan_observed' -Default $false)
    bounded_local_process_launch_observed = [bool](Get-PropertyValue -Payload $ProcessPayload -Name 'bounded_local_process_launch_observed' -Default $false)
    process_supervision_ready = [bool](Get-PropertyValue -Payload $ProcessPayload -Name 'process_supervision_ready' -Default $false)
    service_activation_ready = [bool](Get-PropertyValue -Payload $ProcessPayload -Name 'service_activation_ready' -Default $false)
  }
  evidence = @(
    'scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status',
    'scripts/lens-process-supervision-authority-boundary-proof.ps1 -Mode Status',
    'scripts/lens-host-supervision-proof.ps1 -Mode Status',
    'scripts/lens-stage6-completion-audit.ps1 -Mode Status'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_resident_host_runtime_boundary_proof = $true
    wraps_process_supervision_authority_boundary_proof = $true
    bounded_local_process_launch = $true
    temporary_runtime_state_write = $true
    local_process_launch_authority = $true
    api_local_process_launch_authority = $false
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'The resident-host process-supervision handoff is consumed as a diagnostic proof: the runtime boundary points to resident_host_process_not_supervised, and the existing process-supervision boundary preserves that blocker while denying supervision, restart, service, memory, approval, summon, and resident-claim authority.'
}

$Payload | ConvertTo-Json -Depth 10
exit $(if ($ProofPassed) { 0 } else { 1 })
