param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(5, 60)]
  [int]$StartupTimeoutSeconds = 30,

  [ValidateRange(2, 30)]
  [int]$HostLaunchRunSeconds = 3,

  [ValidateRange(2, 30)]
  [int]$ResidentSurfaceForegroundRunSeconds = 15,

  [ValidateRange(3, 30)]
  [int]$SupervisorRunSeconds = 20,

  [ValidateRange(30, 600)]
  [int]$ChildProofTimeoutSeconds = 420
)

$ErrorActionPreference = 'Stop'

function ConvertTo-StringArray {
  param(
    [AllowNull()]
    [object]$Value
  )

  if ($null -eq $Value) {
    return @()
  }

  if ($Value -is [System.Array]) {
    return @($Value | ForEach-Object { [string]$_ })
  }

  return @([string]$Value)
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

function New-ChildProofRunSummary {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name,

    [Parameter(Mandatory = $true)]
    [object]$Result
  )

  return [ordered]@{
    name = $Name
    exit_code = [int]$Result.exit_code
    timed_out = [bool]$Result.timed_out
    timeout_seconds = [int]$Result.timeout_seconds
    duration_ms = [int]$Result.duration_ms
    error = [string]$Result.error
  }
}

function New-CriterionSummary {
  param(
    [Parameter(Mandatory = $true)]
    [object]$Criterion
  )

  return [ordered]@{
    id = [string]$Criterion.id
    label = [string]$Criterion.label
    status = [string]$Criterion.status
    ready = [bool]$Criterion.ready
    blockers = [string[]]@(ConvertTo-StringArray -Value $Criterion.blockers)
    evidence = [string[]]@(ConvertTo-StringArray -Value $Criterion.evidence)
    basis = [string]$Criterion.basis
  }
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$CheckpointScript = Join-Path $PSScriptRoot 'lens-stage6-checkpoint.ps1'
$ProcessSupervisionBoundaryScript = Join-Path $PSScriptRoot 'lens-process-supervision-authority-boundary-proof.ps1'
$ResidentHostRuntimeBoundaryProofScript = Join-Path $PSScriptRoot 'lens-resident-host-runtime-boundary-proof.ps1'
$ResidentHostProcessSupervisionBlockerProofScript = Join-Path $PSScriptRoot 'lens-resident-host-process-supervision-blocker-proof.ps1'
$PersistentSupervisionPlanScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-plan.ps1'
$PersistentSupervisionEnablementAuthorityProofScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-enablement-authority-proof.ps1'
$PersistentSupervisionExecutionAuthorityProofScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-execution-authority-proof.ps1'
$PersistentSupervisionResidentClaimBoundaryProofScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-resident-claim-boundary-proof.ps1'
$SummonAnywhereBlockersProofScript = Join-Path $PSScriptRoot 'lens-summon-anywhere-blockers-proof.ps1'
$SummonAuthorityBlockerProofScript = Join-Path $PSScriptRoot 'lens-summon-authority-blocker-proof.ps1'
$SummonAnywhereFamilyChainProofScript = Join-Path $PSScriptRoot 'lens-summon-anywhere-family-chain-proof.ps1'

if (-not (Test-Path -LiteralPath $CheckpointScript)) {
  throw "Stage 6 checkpoint script is missing: $CheckpointScript"
}

$PowerShell = (Get-Command pwsh -ErrorAction SilentlyContinue)
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command powershell -ErrorAction Stop
}

$CheckpointJson = & $PowerShell.Source -NoProfile -ExecutionPolicy Bypass -File $CheckpointScript -Mode Status `
  -StartupTimeoutSeconds $StartupTimeoutSeconds `
  -HostLaunchRunSeconds $HostLaunchRunSeconds `
  -ResidentSurfaceForegroundRunSeconds $ResidentSurfaceForegroundRunSeconds `
  -SupervisorRunSeconds $SupervisorRunSeconds
if ($LASTEXITCODE -ne 0) {
  throw "Stage 6 checkpoint failed with exit code $LASTEXITCODE"
}

$Checkpoint = ($CheckpointJson | Out-String | ConvertFrom-Json)
$SummonAnywhereBlockersProofResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $SummonAnywhereBlockersProofScript -ScriptArgs @(
  '-Mode', 'Status'
)
$SummonAnywhereBlockersProof = $SummonAnywhereBlockersProofResult.payload
$SummonAuthorityBlockerProofResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $SummonAuthorityBlockerProofScript -ScriptArgs @(
  '-Mode', 'Status'
)
$SummonAuthorityBlockerProof = $SummonAuthorityBlockerProofResult.payload
$SummonAnywhereFamilyChainProofResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $SummonAnywhereFamilyChainProofScript -ScriptArgs @(
  '-Mode', 'Status'
)
$SummonAnywhereFamilyChainProof = $SummonAnywhereFamilyChainProofResult.payload
$ResidentHostRuntimeBoundaryProofResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $ResidentHostRuntimeBoundaryProofScript -ScriptArgs @(
  '-Mode', 'Status',
  '-ForegroundRunSeconds', '2',
  '-HostLaunchRunSeconds', [string]$HostLaunchRunSeconds
)
$ResidentHostRuntimeBoundaryProof = $ResidentHostRuntimeBoundaryProofResult.payload
$ResidentHostRuntimeBoundaryProofBlockers = ConvertTo-StringArray -Value $ResidentHostRuntimeBoundaryProof.blockers
$ResidentHostRuntimeBoundaryProofObserved = (
  [int]$ResidentHostRuntimeBoundaryProofResult.exit_code -eq 0 -and
  [string]$ResidentHostRuntimeBoundaryProof.kind -eq 'lens.resident_host.runtime_blocker_boundary.proof' -and
  [bool]$ResidentHostRuntimeBoundaryProof.ok -and
  [string]$ResidentHostRuntimeBoundaryProof.status -eq 'proof_passed' -and
  [string]$ResidentHostRuntimeBoundaryProof.previous_next_smallest_truthful_gap -eq 'resident_host_runtime_blocker_boundary' -and
  [string]$ResidentHostRuntimeBoundaryProof.next_smallest_truthful_gap -eq 'resident_host_process_not_supervised' -and
  [bool]$ResidentHostRuntimeBoundaryProof.runtime_handoff_observed -and
  [bool]$ResidentHostRuntimeBoundaryProof.bounded_runtime_observed -and
  [bool]$ResidentHostRuntimeBoundaryProof.runtime_heartbeat_observed -and
  [bool]$ResidentHostRuntimeBoundaryProof.runtime_boundary_blocked -and
  [bool]$ResidentHostRuntimeBoundaryProof.process_supervision_handoff_observed -and
  [bool]$ResidentHostRuntimeBoundaryProof.side_effects_bounded -and
  $ResidentHostRuntimeBoundaryProofBlockers -contains 'resident_host_runtime_blocker_boundary_consumed' -and
  $ResidentHostRuntimeBoundaryProofBlockers -contains 'lens_host_runtime_not_implemented' -and
  $ResidentHostRuntimeBoundaryProofBlockers -contains 'resident_host_process_not_supervised' -and
  $ResidentHostRuntimeBoundaryProofBlockers -contains 'process_supervision_authority_not_granted' -and
  $ResidentHostRuntimeBoundaryProofBlockers -contains 'process_restart_authority_not_granted'
)
$ProcessSupervisionBoundaryResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $ProcessSupervisionBoundaryScript -ScriptArgs @(
  '-Mode', 'Status',
  '-StartupTimeoutSeconds', [string]$StartupTimeoutSeconds,
  '-ForegroundRunSeconds', '2',
  '-HostLaunchRunSeconds', [string]$HostLaunchRunSeconds,
  '-SupervisorRunSeconds', [string]$SupervisorRunSeconds,
  '-ChildProofTimeoutSeconds', [string]$ChildProofTimeoutSeconds
)
$ProcessSupervisionBoundary = $ProcessSupervisionBoundaryResult.payload
$ProcessSupervisionBoundaryBlockers = ConvertTo-StringArray -Value $ProcessSupervisionBoundary.blockers
$ProcessSupervisionBoundaryObserved = (
  [int]$ProcessSupervisionBoundaryResult.exit_code -eq 0 -and
  [string]$ProcessSupervisionBoundary.kind -eq 'lens.process_supervision_authority_boundary.proof' -and
  [bool]$ProcessSupervisionBoundary.ok -and
  [bool]$ProcessSupervisionBoundary.process_supervision_boundary_observed -and
  [bool]$ProcessSupervisionBoundary.service_activation_plan_observed
)
$ResidentHostProcessSupervisionBlockerProofResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $ResidentHostProcessSupervisionBlockerProofScript -ScriptArgs @(
  '-Mode', 'Status',
  '-StartupTimeoutSeconds', [string]$StartupTimeoutSeconds,
  '-ForegroundRunSeconds', '2',
  '-HostLaunchRunSeconds', [string]$HostLaunchRunSeconds,
  '-SupervisorRunSeconds', [string]$SupervisorRunSeconds,
  '-ChildProofTimeoutSeconds', [string]$ChildProofTimeoutSeconds
)
$ResidentHostProcessSupervisionBlockerProof = $ResidentHostProcessSupervisionBlockerProofResult.payload
$ResidentHostProcessSupervisionBlockerProofBlockers = ConvertTo-StringArray -Value $ResidentHostProcessSupervisionBlockerProof.blockers
$ResidentHostProcessSupervisionBlockerProofObserved = (
  [int]$ResidentHostProcessSupervisionBlockerProofResult.exit_code -eq 0 -and
  [string]$ResidentHostProcessSupervisionBlockerProof.kind -eq 'lens.resident_host.process_supervision_blocker.proof' -and
  [bool]$ResidentHostProcessSupervisionBlockerProof.ok -and
  [string]$ResidentHostProcessSupervisionBlockerProof.status -eq 'proof_passed' -and
  [string]$ResidentHostProcessSupervisionBlockerProof.previous_next_smallest_truthful_gap -eq 'resident_host_process_not_supervised' -and
  [string]$ResidentHostProcessSupervisionBlockerProof.next_smallest_truthful_gap -eq 'stage6_lens_completion_audit' -and
  [bool]$ResidentHostProcessSupervisionBlockerProof.resident_host_process_handoff_observed -and
  [bool]$ResidentHostProcessSupervisionBlockerProof.process_supervision_boundary_observed -and
  [bool]$ResidentHostProcessSupervisionBlockerProof.handoff_consumed -and
  [bool]$ResidentHostProcessSupervisionBlockerProof.authority_denied -and
  $ResidentHostProcessSupervisionBlockerProofBlockers -contains 'resident_host_process_not_supervised' -and
  $ResidentHostProcessSupervisionBlockerProofBlockers -contains 'process_supervision_authority_not_granted' -and
  $ResidentHostProcessSupervisionBlockerProofBlockers -contains 'process_restart_authority_not_granted' -and
  $ResidentHostProcessSupervisionBlockerProofBlockers -contains 'service_install_authority_not_granted' -and
  $ResidentHostProcessSupervisionBlockerProofBlockers -contains 'service_control_authority_not_granted'
)
$PersistentSupervisionPlanResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $PersistentSupervisionPlanScript -ScriptArgs @('-Mode', 'Status')
$PersistentSupervisionPlan = $PersistentSupervisionPlanResult.payload
$PersistentSupervisionPlanBlockers = ConvertTo-StringArray -Value $PersistentSupervisionPlan.blockers
$PersistentSupervisionPlanObserved = (
  [int]$PersistentSupervisionPlanResult.exit_code -eq 0 -and
  [string]$PersistentSupervisionPlan.kind -eq 'lens.host.persistent_supervision_plan' -and
  [bool]$PersistentSupervisionPlan.ok -and
  [bool]$PersistentSupervisionPlan.plan_available -and
  -not [bool]$PersistentSupervisionPlan.persistent_supervision_ready -and
  -not [bool]$PersistentSupervisionPlan.resident_claim_allowed
)
$PersistentSupervisionEnablementAuthorityProofResult = Invoke-JsonScript `
  -PowerShellPath $PowerShell.Source `
  -ScriptPath $PersistentSupervisionEnablementAuthorityProofScript `
  -ScriptArgs @('-Mode', 'Status')
$PersistentSupervisionEnablementAuthorityProof = $PersistentSupervisionEnablementAuthorityProofResult.payload
$PersistentSupervisionEnablementAuthorityProofBlockers = ConvertTo-StringArray -Value $PersistentSupervisionEnablementAuthorityProof.blockers
$PersistentSupervisionEnablementAuthorityProofObserved = (
  [int]$PersistentSupervisionEnablementAuthorityProofResult.exit_code -eq 0 -and
  [string]$PersistentSupervisionEnablementAuthorityProof.kind -eq 'lens.host.persistent_supervision_enablement_authority.proof' -and
  [bool]$PersistentSupervisionEnablementAuthorityProof.ok -and
  [string]$PersistentSupervisionEnablementAuthorityProof.status -eq 'proof_passed' -and
  [bool]$PersistentSupervisionEnablementAuthorityProof.persistent_supervision_enablement_authority -and
  -not [bool]$PersistentSupervisionEnablementAuthorityProof.service_config_write_authority -and
  -not [bool]$PersistentSupervisionEnablementAuthorityProof.persistent_supervision_execution_authority -and
  -not [bool]$PersistentSupervisionEnablementAuthorityProof.persistent_supervision_enablement_allowed -and
  -not [bool]$PersistentSupervisionEnablementAuthorityProof.resident_claim_allowed -and
  [bool]$PersistentSupervisionEnablementAuthorityProof.grant_applied -and
  -not [bool]$PersistentSupervisionEnablementAuthorityProof.enablement_applied -and
  -not [bool]$PersistentSupervisionEnablementAuthorityProof.executed -and
  -not [bool]$PersistentSupervisionEnablementAuthorityProof.service_config_updated -and
  -not [bool]$PersistentSupervisionEnablementAuthorityProof.would_update_service_config -and
  -not [bool]$PersistentSupervisionEnablementAuthorityProof.would_enable_process_supervision -and
  -not [bool]$PersistentSupervisionEnablementAuthorityProof.would_enable_persistent_supervision -and
  -not [bool]$PersistentSupervisionEnablementAuthorityProof.would_install_service -and
  -not [bool]$PersistentSupervisionEnablementAuthorityProof.would_start_service -and
  -not [bool]$PersistentSupervisionEnablementAuthorityProof.would_supervise_process -and
  -not [bool]$PersistentSupervisionEnablementAuthorityProof.would_restart_process -and
  -not [bool]$PersistentSupervisionEnablementAuthorityProof.would_write_memory -and
  -not [bool]$PersistentSupervisionEnablementAuthorityProof.would_claim_resident -and
  -not ($PersistentSupervisionEnablementAuthorityProofBlockers -contains 'persistent_supervision_enablement_authority_not_granted') -and
  $PersistentSupervisionEnablementAuthorityProofBlockers -contains 'service_config_write_authority_not_granted' -and
  $PersistentSupervisionEnablementAuthorityProofBlockers -contains 'persistent_supervision_execution_authority_not_granted' -and
  [string]$PersistentSupervisionEnablementAuthorityProof.next_smallest_truthful_gap -eq 'persistent_supervision_execution_authority_or_resident_claim_boundary'
)
$PersistentSupervisionExecutionAuthorityProofResult = Invoke-JsonScript `
  -PowerShellPath $PowerShell.Source `
  -ScriptPath $PersistentSupervisionExecutionAuthorityProofScript `
  -ScriptArgs @('-Mode', 'Status')
$PersistentSupervisionExecutionAuthorityProof = $PersistentSupervisionExecutionAuthorityProofResult.payload
$PersistentSupervisionExecutionAuthorityProofBlockers = ConvertTo-StringArray -Value $PersistentSupervisionExecutionAuthorityProof.blockers
$PersistentSupervisionExecutionAuthorityProofObserved = (
  [int]$PersistentSupervisionExecutionAuthorityProofResult.exit_code -eq 0 -and
  [string]$PersistentSupervisionExecutionAuthorityProof.kind -eq 'lens.host.persistent_supervision_execution_authority.proof' -and
  [bool]$PersistentSupervisionExecutionAuthorityProof.ok -and
  [string]$PersistentSupervisionExecutionAuthorityProof.status -eq 'proof_passed' -and
  [bool]$PersistentSupervisionExecutionAuthorityProof.persistent_supervision_enablement_authority -and
  [bool]$PersistentSupervisionExecutionAuthorityProof.service_config_write_authority -and
  [bool]$PersistentSupervisionExecutionAuthorityProof.persistent_supervision_execution_authority -and
  [bool]$PersistentSupervisionExecutionAuthorityProof.receipt_write_authority -and
  -not [bool]$PersistentSupervisionExecutionAuthorityProof.persistent_supervision_enablement_allowed -and
  -not [bool]$PersistentSupervisionExecutionAuthorityProof.resident_claim_allowed -and
  [bool]$PersistentSupervisionExecutionAuthorityProof.grant_applied -and
  -not [bool]$PersistentSupervisionExecutionAuthorityProof.enablement_applied -and
  -not [bool]$PersistentSupervisionExecutionAuthorityProof.applied -and
  -not [bool]$PersistentSupervisionExecutionAuthorityProof.executed -and
  -not [bool]$PersistentSupervisionExecutionAuthorityProof.service_config_updated -and
  -not [bool]$PersistentSupervisionExecutionAuthorityProof.would_update_service_config -and
  -not [bool]$PersistentSupervisionExecutionAuthorityProof.would_enable_persistent_supervision -and
  -not [bool]$PersistentSupervisionExecutionAuthorityProof.would_start_service -and
  -not [bool]$PersistentSupervisionExecutionAuthorityProof.would_supervise_process -and
  -not [bool]$PersistentSupervisionExecutionAuthorityProof.would_restart_process -and
  -not [bool]$PersistentSupervisionExecutionAuthorityProof.would_write_receipt -and
  -not [bool]$PersistentSupervisionExecutionAuthorityProof.would_write_memory -and
  -not [bool]$PersistentSupervisionExecutionAuthorityProof.would_claim_resident -and
  -not ($PersistentSupervisionExecutionAuthorityProofBlockers -contains 'service_config_write_authority_not_granted') -and
  -not ($PersistentSupervisionExecutionAuthorityProofBlockers -contains 'persistent_supervision_execution_authority_not_granted') -and
  -not ($PersistentSupervisionExecutionAuthorityProofBlockers -contains 'receipt_write_authority_not_granted') -and
  $PersistentSupervisionExecutionAuthorityProofBlockers -contains 'resident_claim_authority_not_granted' -and
  [string]$PersistentSupervisionExecutionAuthorityProof.next_smallest_truthful_gap -eq 'persistent_supervision_resident_claim_authority_boundary'
)
$PersistentSupervisionResidentClaimBoundaryProofResult = Invoke-JsonScript `
  -PowerShellPath $PowerShell.Source `
  -ScriptPath $PersistentSupervisionResidentClaimBoundaryProofScript `
  -ScriptArgs @('-Mode', 'Status')
$PersistentSupervisionResidentClaimBoundaryProof = $PersistentSupervisionResidentClaimBoundaryProofResult.payload
$PersistentSupervisionResidentClaimBoundaryBlockers = ConvertTo-StringArray -Value $PersistentSupervisionResidentClaimBoundaryProof.blockers
$PersistentSupervisionResidentClaimBoundaryObserved = (
  [int]$PersistentSupervisionResidentClaimBoundaryProofResult.exit_code -eq 0 -and
  [string]$PersistentSupervisionResidentClaimBoundaryProof.kind -eq 'lens.host.persistent_supervision_resident_claim_boundary.proof' -and
  [bool]$PersistentSupervisionResidentClaimBoundaryProof.ok -and
  [string]$PersistentSupervisionResidentClaimBoundaryProof.status -eq 'proof_passed' -and
  [string]$PersistentSupervisionResidentClaimBoundaryProof.authority_family -eq 'resident_claim' -and
  [string]$PersistentSupervisionResidentClaimBoundaryProof.previous_authority_family -eq 'persistent_supervision_execution' -and
  [string]$PersistentSupervisionResidentClaimBoundaryProof.next_authority_family -eq '' -and
  [bool]$PersistentSupervisionResidentClaimBoundaryProof.persistent_supervision_resident_claim_boundary_observed -and
  [bool]$PersistentSupervisionResidentClaimBoundaryProof.persistent_supervision_execution_authority_proof_observed -and
  [bool]$PersistentSupervisionResidentClaimBoundaryProof.persistent_supervision_plan_observed -and
  [bool]$PersistentSupervisionResidentClaimBoundaryProof.side_effects_denied -and
  [bool]$PersistentSupervisionResidentClaimBoundaryProof.final_persistent_supervision_authority_family_consumed -and
  [bool]$PersistentSupervisionResidentClaimBoundaryProof.persistent_supervision_enablement_authority -and
  [bool]$PersistentSupervisionResidentClaimBoundaryProof.service_config_write_authority -and
  [bool]$PersistentSupervisionResidentClaimBoundaryProof.persistent_supervision_execution_authority -and
  [bool]$PersistentSupervisionResidentClaimBoundaryProof.receipt_write_authority -and
  -not [bool]$PersistentSupervisionResidentClaimBoundaryProof.resident_claim_authority -and
  -not [bool]$PersistentSupervisionResidentClaimBoundaryProof.persistent_supervision_ready -and
  -not [bool]$PersistentSupervisionResidentClaimBoundaryProof.resident_claim_allowed -and
  -not [bool]$PersistentSupervisionResidentClaimBoundaryProof.applied -and
  -not [bool]$PersistentSupervisionResidentClaimBoundaryProof.executed -and
  -not [bool]$PersistentSupervisionResidentClaimBoundaryProof.service_config_updated -and
  -not [bool]$PersistentSupervisionResidentClaimBoundaryProof.would_update_service_config -and
  -not [bool]$PersistentSupervisionResidentClaimBoundaryProof.would_enable_persistent_supervision -and
  -not [bool]$PersistentSupervisionResidentClaimBoundaryProof.would_start_service -and
  -not [bool]$PersistentSupervisionResidentClaimBoundaryProof.would_supervise_process -and
  -not [bool]$PersistentSupervisionResidentClaimBoundaryProof.would_restart_process -and
  -not [bool]$PersistentSupervisionResidentClaimBoundaryProof.would_write_receipt -and
  -not [bool]$PersistentSupervisionResidentClaimBoundaryProof.would_write_memory -and
  -not [bool]$PersistentSupervisionResidentClaimBoundaryProof.would_claim_resident -and
  $PersistentSupervisionResidentClaimBoundaryBlockers -contains 'persistent_supervision_disabled' -and
  $PersistentSupervisionResidentClaimBoundaryBlockers -contains 'process_supervision_disabled' -and
  $PersistentSupervisionResidentClaimBoundaryBlockers -contains 'resident_claim_authority_not_granted' -and
  [string]$PersistentSupervisionResidentClaimBoundaryProof.next_smallest_truthful_gap -eq 'stage6_lens_completion_audit'
)
$ChildProofRuns = @(
  New-ChildProofRunSummary -Name 'summon_anywhere_blockers' -Result $SummonAnywhereBlockersProofResult
  New-ChildProofRunSummary -Name 'summon_authority_blocker' -Result $SummonAuthorityBlockerProofResult
  New-ChildProofRunSummary -Name 'summon_anywhere_family_chain' -Result $SummonAnywhereFamilyChainProofResult
  New-ChildProofRunSummary -Name 'resident_host_runtime_boundary' -Result $ResidentHostRuntimeBoundaryProofResult
  New-ChildProofRunSummary -Name 'process_supervision_boundary' -Result $ProcessSupervisionBoundaryResult
  New-ChildProofRunSummary -Name 'resident_host_process_supervision_blocker' -Result $ResidentHostProcessSupervisionBlockerProofResult
  New-ChildProofRunSummary -Name 'persistent_supervision_plan' -Result $PersistentSupervisionPlanResult
  New-ChildProofRunSummary -Name 'persistent_supervision_enablement_authority' -Result $PersistentSupervisionEnablementAuthorityProofResult
  New-ChildProofRunSummary -Name 'persistent_supervision_execution_authority' -Result $PersistentSupervisionExecutionAuthorityProofResult
  New-ChildProofRunSummary -Name 'persistent_supervision_resident_claim_boundary' -Result $PersistentSupervisionResidentClaimBoundaryProofResult
)
$ChildProofTimeouts = [string[]]@(
  $ChildProofRuns | Where-Object { [bool]$_.timed_out } | ForEach-Object { [string]$_.name }
)
$PersistentSupervisionEnablementDenial = $Checkpoint.persistent_supervision_enablement_denial_boundary
$PersistentSupervisionEnablementDenialBlockers = ConvertTo-StringArray -Value $PersistentSupervisionEnablementDenial.blockers
$PersistentSupervisionEnablementDenialObserved = (
  [bool]$PersistentSupervisionEnablementDenial.ok -and
  [string]$PersistentSupervisionEnablementDenial.status -eq 'blocked' -and
  [bool]$PersistentSupervisionEnablementDenial.boundary_ready -and
  -not [bool]$PersistentSupervisionEnablementDenial.applied -and
  -not [bool]$PersistentSupervisionEnablementDenial.executed -and
  -not [bool]$PersistentSupervisionEnablementDenial.authority_granted -and
  -not [bool]$PersistentSupervisionEnablementDenial.enablement_ready -and
  -not [bool]$PersistentSupervisionEnablementDenial.resident_claim_allowed -and
  -not [bool]$PersistentSupervisionEnablementDenial.service_config_updated -and
  -not [bool]$PersistentSupervisionEnablementDenial.authority_grant_active -and
  $PersistentSupervisionEnablementDenialBlockers -contains 'persistent_supervision_enablement_authority_not_granted' -and
  $PersistentSupervisionEnablementDenialBlockers -contains 'service_config_write_authority_not_granted'
)
$PersistentSupervisionEnablementExecutionDenial = $Checkpoint.persistent_supervision_enablement_execution_denial_boundary
$PersistentSupervisionEnablementExecutionDenialBlockers = ConvertTo-StringArray -Value $PersistentSupervisionEnablementExecutionDenial.blockers
$PersistentSupervisionEnablementExecutionDenialObserved = (
  [bool]$PersistentSupervisionEnablementExecutionDenial.ok -and
  [string]$PersistentSupervisionEnablementExecutionDenial.status -eq 'blocked' -and
  [bool]$PersistentSupervisionEnablementExecutionDenial.boundary_ready -and
  -not [bool]$PersistentSupervisionEnablementExecutionDenial.applied -and
  -not [bool]$PersistentSupervisionEnablementExecutionDenial.executed -and
  -not [bool]$PersistentSupervisionEnablementExecutionDenial.ready -and
  -not [bool]$PersistentSupervisionEnablementExecutionDenial.approval_ready -and
  -not [bool]$PersistentSupervisionEnablementExecutionDenial.enablement_authority_granted -and
  -not [bool]$PersistentSupervisionEnablementExecutionDenial.persistent_supervision_enablement_allowed -and
  -not [bool]$PersistentSupervisionEnablementExecutionDenial.service_config_updated -and
  -not [bool]$PersistentSupervisionEnablementExecutionDenial.resident_claim_allowed -and
  $PersistentSupervisionEnablementExecutionDenialBlockers -contains 'approval_id_required' -and
  $PersistentSupervisionEnablementExecutionDenialBlockers -contains 'persistent_supervision_enablement_authority_not_granted' -and
  $PersistentSupervisionEnablementExecutionDenialBlockers -contains 'service_config_write_authority_not_granted' -and
  $PersistentSupervisionEnablementExecutionDenialBlockers -contains 'persistent_supervision_execution_authority_not_granted'
)
$Criteria = @($Checkpoint.criteria)
$ReadyCriteria = @($Criteria | Where-Object { [bool]$_.ready })
$BlockedCriteria = @($Criteria | Where-Object { -not [bool]$_.ready })
$Blockers = ConvertTo-StringArray -Value $Checkpoint.blockers
$ReadyToClose = [bool]$Checkpoint.ready_to_close
$BlockedCriterionIds = @($BlockedCriteria | ForEach-Object { [string]$_.id })
$Stage6CompletionReviewed = $false
$Stage6AcceptanceNextGap = if ($BlockedCriterionIds -contains 'summon_anywhere') {
  'summon_anywhere_blockers'
} elseif ($BlockedCriterionIds -contains 'helpful_not_noisy') {
  'helpful_not_noisy_blockers'
} elseif ($BlockedCriterionIds -contains 'system_resident_presence') {
  'system_resident_presence_blockers'
} else {
  ''
}
$SummonEnablementGate = @(
  $Checkpoint.enablement_gates | Where-Object { [string]$_.id -eq 'summon_enablement_gate' } | Select-Object -First 1
)
$SummonAnywhereBlockerGroups = [ordered]@{
  resident_host = [string[]]@(ConvertTo-StringArray -Value $SummonEnablementGate.blocker_groups.resident_host)
  tray_presence = [string[]]@(ConvertTo-StringArray -Value $SummonEnablementGate.blocker_groups.tray_presence)
  overlay_window = [string[]]@(ConvertTo-StringArray -Value $SummonEnablementGate.blocker_groups.overlay_window)
  global_hotkey_binding = [string[]]@(ConvertTo-StringArray -Value $SummonEnablementGate.blocker_groups.global_hotkey_binding)
  summon_binding = [string[]]@(ConvertTo-StringArray -Value $SummonEnablementGate.blocker_groups.summon_binding)
  authority = [string[]]@(ConvertTo-StringArray -Value $SummonEnablementGate.blocker_groups.authority)
}
$SummonAnywhereBlockerFamilyOrder = @(
  'resident_host',
  'tray_presence',
  'overlay_window',
  'global_hotkey_binding',
  'summon_binding',
  'authority'
)
$SummonAnywhereBlockedFamilies = @(
  $SummonAnywhereBlockerFamilyOrder | Where-Object { @($SummonAnywhereBlockerGroups[$_]).Count -gt 0 }
)
$SummonAnywhereFirstBlockerFamily = if ($SummonAnywhereBlockedFamilies.Count -gt 0) {
  [string]$SummonAnywhereBlockedFamilies[0]
} else {
  ''
}
$CheckpointSummonEnablementGateHandoff = $Checkpoint.summon_enablement_gate_handoff
$CheckpointSummonEnablementGateHandoffEvidence = ConvertTo-StringArray -Value $CheckpointSummonEnablementGateHandoff.evidence
$CheckpointSummonEnablementGateHandoffBlockers = ConvertTo-StringArray -Value $CheckpointSummonEnablementGateHandoff.blockers
$CheckpointSummonEnablementGateHandoffFamilies = ConvertTo-StringArray -Value $CheckpointSummonEnablementGateHandoff.blocked_families
$CheckpointSummonEnablementGateFirstFamilyHandoff = $CheckpointSummonEnablementGateHandoff.first_blocker_family_handoff
$CheckpointSummonEnablementGateFirstFamilyHandoffBlockers = ConvertTo-StringArray -Value (
  $CheckpointSummonEnablementGateFirstFamilyHandoff.blockers
)
$CheckpointSummonEnablementGateFamilyHandoffs = @($CheckpointSummonEnablementGateHandoff.blocked_family_handoffs)
$CheckpointSummonEnablementGateFamilyHandoffIds = [string[]]@(
  $CheckpointSummonEnablementGateFamilyHandoffs | ForEach-Object { [string]$_.id }
)
$CheckpointSummonEnablementGateFamilyHandoffsAligned = (
  @($CheckpointSummonEnablementGateFamilyHandoffIds).Count -eq @($CheckpointSummonEnablementGateHandoffFamilies).Count
)
for ($Index = 0; $Index -lt @($CheckpointSummonEnablementGateHandoffFamilies).Count; $Index += 1) {
  if (
    @($CheckpointSummonEnablementGateFamilyHandoffIds).Count -le $Index -or
    [string]$CheckpointSummonEnablementGateFamilyHandoffIds[$Index] -ne [string]$CheckpointSummonEnablementGateHandoffFamilies[$Index]
  ) {
    $CheckpointSummonEnablementGateFamilyHandoffsAligned = $false
  }
}
$CheckpointSummonEnablementGateFamilyHandoffsBounded = $true
foreach ($Handoff in @($CheckpointSummonEnablementGateFamilyHandoffs)) {
  if (
    -not [bool]$Handoff.read_only_contract -or
    -not [bool]$Handoff.diagnostic_only -or
    [bool]$Handoff.authority_granted -or
    [bool]$Handoff.would_execute -or
    [bool]$Handoff.would_mutate
  ) {
    $CheckpointSummonEnablementGateFamilyHandoffsBounded = $false
  }
}
$CheckpointSummonEnablementGateHandoffObserved = (
  [bool]$CheckpointSummonEnablementGateHandoff.ok -and
  [string]$CheckpointSummonEnablementGateHandoff.status -eq 'blocked' -and
  -not [bool]$CheckpointSummonEnablementGateHandoff.ready -and
  -not [bool]$CheckpointSummonEnablementGateHandoff.summon_anywhere -and
  [bool]$CheckpointSummonEnablementGateHandoff.operator_surface_readback_ready -and
  [bool]$CheckpointSummonEnablementGateHandoff.handoff_observed -and
  $CheckpointSummonEnablementGateFamilyHandoffsAligned -and
  $CheckpointSummonEnablementGateFamilyHandoffsBounded -and
  $CheckpointSummonEnablementGateHandoffFamilies -contains 'resident_host' -and
  $CheckpointSummonEnablementGateHandoffFamilies -contains 'tray_presence' -and
  $CheckpointSummonEnablementGateHandoffFamilies -contains 'overlay_window' -and
  $CheckpointSummonEnablementGateHandoffFamilies -contains 'global_hotkey_binding' -and
  $CheckpointSummonEnablementGateHandoffFamilies -contains 'summon_binding' -and
  $CheckpointSummonEnablementGateHandoffFamilies -contains 'authority' -and
  [string]$CheckpointSummonEnablementGateHandoff.first_blocker_family -eq 'resident_host' -and
  [string]$CheckpointSummonEnablementGateFirstFamilyHandoff.id -eq 'resident_host' -and
  [string]$CheckpointSummonEnablementGateFirstFamilyHandoff.status -eq 'blocked' -and
  [string]$CheckpointSummonEnablementGateFirstFamilyHandoff.proof_script -eq 'scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status' -and
  [string]$CheckpointSummonEnablementGateFirstFamilyHandoff.route -eq '/lens/host' -and
  [string]$CheckpointSummonEnablementGateFirstFamilyHandoff.readiness_route -eq '/lens/host/runtime-loop/readiness' -and
  [string]$CheckpointSummonEnablementGateFirstFamilyHandoff.next_step -eq 'run_resident_host_blocker_proof' -and
  [string]$CheckpointSummonEnablementGateFirstFamilyHandoff.next_smallest_truthful_gap -eq 'resident_host_runtime_blocker_boundary' -and
  [string]$CheckpointSummonEnablementGateFirstFamilyHandoff.authority_required -eq 'resident_runtime_execution_authority' -and
  $CheckpointSummonEnablementGateFirstFamilyHandoffBlockers -contains 'lens_host_runtime_not_implemented' -and
  $CheckpointSummonEnablementGateFirstFamilyHandoffBlockers -contains 'local_process_launch_authority_not_granted' -and
  -not [bool]$CheckpointSummonEnablementGateFirstFamilyHandoff.authority_granted -and
  [bool]$CheckpointSummonEnablementGateFirstFamilyHandoff.read_only_contract -and
  [bool]$CheckpointSummonEnablementGateFirstFamilyHandoff.diagnostic_only -and
  -not [bool]$CheckpointSummonEnablementGateFirstFamilyHandoff.would_execute -and
  -not [bool]$CheckpointSummonEnablementGateFirstFamilyHandoff.would_mutate -and
  [string]$CheckpointSummonEnablementGateHandoff.next_smallest_truthful_gap -eq 'summon_anywhere_blockers' -and
  $CheckpointSummonEnablementGateHandoffEvidence -contains '/lens/status' -and
  $CheckpointSummonEnablementGateHandoffBlockers -contains 'summon_authority_not_granted' -and
  -not [bool]$CheckpointSummonEnablementGateHandoff.execution_authority -and
  -not [bool]$CheckpointSummonEnablementGateHandoff.approval_decision_authority -and
  -not [bool]$CheckpointSummonEnablementGateHandoff.local_process_launch_authority -and
  -not [bool]$CheckpointSummonEnablementGateHandoff.hotkey_registration_authority -and
  -not [bool]$CheckpointSummonEnablementGateHandoff.tray_registration_authority -and
  -not [bool]$CheckpointSummonEnablementGateHandoff.overlay_control_authority -and
  -not [bool]$CheckpointSummonEnablementGateHandoff.summon_authority -and
  -not [bool]$CheckpointSummonEnablementGateHandoff.memory_write -and
  -not [bool]$CheckpointSummonEnablementGateHandoff.receipt_write_authority -and
  -not [bool]$CheckpointSummonEnablementGateHandoff.resident_claim_authority
)
$HostSupervisorReadback = $Checkpoint.host_supervisor_readback
$HostSupervisorReadbackBlockers = ConvertTo-StringArray -Value $HostSupervisorReadback.blockers
$HostSupervisorReadbackObserved = (
  [bool]$HostSupervisorReadback.readback_ready -and
  -not [string]::IsNullOrWhiteSpace([string]$HostSupervisorReadback.freshness_status)
)
$HostSupervisorOwnedSession = $Checkpoint.host_supervisor_owned_session
$HostSupervisorOwnedSessionBlockers = ConvertTo-StringArray -Value $HostSupervisorOwnedSession.blockers
$HostSupervisorOwnedSessionObserved = (
  [string]$HostSupervisorOwnedSession.status -eq 'supervised_session_completed' -and
  [bool]$HostSupervisorOwnedSession.ok -and
  [bool]$HostSupervisorOwnedSession.bounded_supervised_session -and
  [bool]$HostSupervisorOwnedSession.bounded_supervisor_observed -and
  -not [bool]$HostSupervisorOwnedSession.resident_supervised_runtime -and
  -not [bool]$HostSupervisorOwnedSession.resident_claim_allowed
)
$HostSupervisionAuthorityReadiness = $Checkpoint.resident_host_supervision_authority_readiness_audit
$HostSupervisionAuthorityReadinessBlockedRequirements = ConvertTo-StringArray -Value $HostSupervisionAuthorityReadiness.blocked_requirements
$HostSupervisionAuthorityReadinessFirstBlockedRequirement = [string]$HostSupervisionAuthorityReadiness.first_blocked_requirement
$HostSupervisionAuthorityReadinessFirstBlockedRequirementHandoff = $HostSupervisionAuthorityReadiness.first_blocked_requirement_handoff
$HostSupervisionAuthorityReadinessRequestReadbackReady = [bool]$HostSupervisionAuthorityReadiness.request_readback_ready
$HostSupervisionAuthorityReadinessBlockedRequirementHandoffs = @(
  $HostSupervisionAuthorityReadiness.blocked_requirement_handoffs
)
$HostSupervisionAuthorityReadinessHandoffObserved = (
  [bool]$HostSupervisionAuthorityReadiness.ok -and
  [string]$HostSupervisionAuthorityReadiness.status -eq 'blocked' -and
  -not [bool]$HostSupervisionAuthorityReadiness.ready -and
  [bool]$HostSupervisionAuthorityReadiness.operator_surface_readback_ready -and
  $HostSupervisionAuthorityReadinessRequestReadbackReady -and
  $HostSupervisionAuthorityReadinessBlockedRequirements -notcontains 'host_supervision_authority_request_readback' -and
  $HostSupervisionAuthorityReadinessBlockedRequirements -contains 'exact_supervision_authority_approval' -and
  $HostSupervisionAuthorityReadinessFirstBlockedRequirement -eq 'exact_supervision_authority_approval' -and
  [string]$HostSupervisionAuthorityReadinessFirstBlockedRequirementHandoff.id -eq 'exact_supervision_authority_approval' -and
  [string]$HostSupervisionAuthorityReadinessFirstBlockedRequirementHandoff.route -eq '/lens/host/supervision/authority/requests' -and
  [string]$HostSupervisionAuthorityReadinessFirstBlockedRequirementHandoff.readiness_route -eq '/lens/host/supervision/authority/readiness' -and
  [string]$HostSupervisionAuthorityReadinessFirstBlockedRequirementHandoff.request_route -eq '/lens/host/supervision/authority/request' -and
  [string]$HostSupervisionAuthorityReadinessFirstBlockedRequirementHandoff.requests_route -eq '/lens/host/supervision/authority/requests' -and
  [string]$HostSupervisionAuthorityReadinessFirstBlockedRequirementHandoff.grant_route -eq '/lens/host/supervision/authority' -and
  [string]$HostSupervisionAuthorityReadinessFirstBlockedRequirementHandoff.grants_route -eq '/lens/host/supervision/authority/grants' -and
  [string]$HostSupervisionAuthorityReadinessFirstBlockedRequirementHandoff.denials_route -eq '/lens/host/supervision/authority/denials' -and
  [string]$HostSupervisionAuthorityReadinessFirstBlockedRequirementHandoff.approval_action -eq 'lens.host.supervision_authority' -and
  [string]$HostSupervisionAuthorityReadinessFirstBlockedRequirementHandoff.next_step -eq 'create_or_select_exact_approved_host_supervision_authority_request' -and
  [string]$HostSupervisionAuthorityReadinessFirstBlockedRequirementHandoff.authority_required -eq 'operator_approval' -and
  -not [bool]$HostSupervisionAuthorityReadinessFirstBlockedRequirementHandoff.authority_granted -and
  -not [bool]$HostSupervisionAuthorityReadinessFirstBlockedRequirementHandoff.would_execute -and
  -not [bool]$HostSupervisionAuthorityReadinessFirstBlockedRequirementHandoff.would_mutate -and
  [string]$HostSupervisionAuthorityReadiness.next_smallest_truthful_gap -eq 'host_supervision_authority_exact_approval_request'
)
$ResidentRuntimeBoundary = $Checkpoint.resident_runtime_authority_boundary
$ResidentRuntimeBoundaryBlockers = ConvertTo-StringArray -Value $ResidentRuntimeBoundary.blockers
$ResidentRuntimeBoundaryObserved = (
  [bool]$ResidentRuntimeBoundary.ok -and
  [string]$ResidentRuntimeBoundary.status -ne 'missing' -and
  -not [bool]$ResidentRuntimeBoundary.applied -and
  -not [bool]$ResidentRuntimeBoundary.executed -and
  $ResidentRuntimeBoundaryBlockers -contains 'local_process_launch_authority_not_granted' -and
  $ResidentRuntimeBoundaryBlockers -contains 'process_supervision_authority_not_granted' -and
  $ResidentRuntimeBoundaryBlockers -contains 'service_control_authority_not_granted' -and
  $ResidentRuntimeBoundaryBlockers -contains 'tray_registration_authority_not_granted' -and
  $ResidentRuntimeBoundaryBlockers -contains 'overlay_control_authority_not_granted' -and
  $ResidentRuntimeBoundaryBlockers -contains 'resident_claim_authority_not_granted'
)
$ResidentRuntimeGrantedBoundaryProof = $Checkpoint.resident_runtime_granted_boundary_proof
$ResidentRuntimeGrantedBoundaryProofBlockers = ConvertTo-StringArray -Value $ResidentRuntimeGrantedBoundaryProof.blockers
$ResidentRuntimeGrantedBoundaryProofObserved = (
  [bool]$ResidentRuntimeGrantedBoundaryProof.ok -and
  [string]$ResidentRuntimeGrantedBoundaryProof.status -eq 'proof_passed' -and
  [bool]$ResidentRuntimeGrantedBoundaryProof.resident_runtime_execution_authority -and
  -not [bool]$ResidentRuntimeGrantedBoundaryProof.applied -and
  -not [bool]$ResidentRuntimeGrantedBoundaryProof.executed -and
  -not [bool]$ResidentRuntimeGrantedBoundaryProof.runtime_ready -and
  -not [bool]$ResidentRuntimeGrantedBoundaryProof.resident_claim_allowed -and
  -not [bool]$ResidentRuntimeGrantedBoundaryProof.would_launch_process -and
  -not [bool]$ResidentRuntimeGrantedBoundaryProof.would_supervise_process -and
  -not [bool]$ResidentRuntimeGrantedBoundaryProof.would_start_service -and
  -not [bool]$ResidentRuntimeGrantedBoundaryProof.would_register_tray -and
  -not [bool]$ResidentRuntimeGrantedBoundaryProof.would_register_hotkey -and
  -not [bool]$ResidentRuntimeGrantedBoundaryProof.would_open_overlay -and
  -not [bool]$ResidentRuntimeGrantedBoundaryProof.would_write_memory -and
  -not [bool]$ResidentRuntimeGrantedBoundaryProof.would_claim_resident -and
  -not ($ResidentRuntimeGrantedBoundaryProofBlockers -contains 'resident_runtime_execution_authority_not_granted') -and
  $ResidentRuntimeGrantedBoundaryProofBlockers -contains 'process_supervision_authority_not_granted' -and
  $ResidentRuntimeGrantedBoundaryProofBlockers -contains 'service_control_authority_not_granted' -and
  $ResidentRuntimeGrantedBoundaryProofBlockers -contains 'tray_registration_authority_not_granted' -and
  $ResidentRuntimeGrantedBoundaryProofBlockers -contains 'hotkey_registration_authority_not_granted' -and
  $ResidentRuntimeGrantedBoundaryProofBlockers -contains 'overlay_control_authority_not_granted' -and
  $ResidentRuntimeGrantedBoundaryProofBlockers -contains 'resident_claim_authority_not_granted'
)
$ResidentRuntimeAuthorityBlockersProof = $Checkpoint.resident_runtime_authority_blockers_proof
$ResidentRuntimeAuthorityBlockerFamilies = ConvertTo-StringArray -Value $ResidentRuntimeAuthorityBlockersProof.remaining_authority_families
$ResidentRuntimeAuthorityBlockerGroups = $ResidentRuntimeAuthorityBlockersProof.authority_blocker_groups
$ResidentRuntimeAuthorityBlockersSummary = $ResidentRuntimeAuthorityBlockersProof.summary
$ResidentRuntimeAuthorityBlockersProofObserved = (
  [bool]$ResidentRuntimeAuthorityBlockersProof.ok -and
  [string]$ResidentRuntimeAuthorityBlockersProof.status -eq 'proof_passed' -and
  [string]$ResidentRuntimeAuthorityBlockersProof.next_smallest_truthful_gap -eq 'resident_runtime_process_supervision_authority_boundary' -and
  [bool]$ResidentRuntimeAuthorityBlockersSummary.combined_gap_split -and
  [int]$ResidentRuntimeAuthorityBlockersSummary.blocked_authority_family_total -eq 6 -and
  $ResidentRuntimeAuthorityBlockerFamilies -contains 'process_supervision' -and
  $ResidentRuntimeAuthorityBlockerFamilies -contains 'service_control' -and
  $ResidentRuntimeAuthorityBlockerFamilies -contains 'tray_presence' -and
  $ResidentRuntimeAuthorityBlockerFamilies -contains 'hotkey_summon' -and
  $ResidentRuntimeAuthorityBlockerFamilies -contains 'overlay_window' -and
  $ResidentRuntimeAuthorityBlockerFamilies -contains 'resident_claim'
)
$ResidentRuntimeProcessSupervisionBoundaryProof = $Checkpoint.resident_runtime_process_supervision_boundary_proof
$ResidentRuntimeProcessSupervisionBoundaryBlockers = ConvertTo-StringArray -Value $ResidentRuntimeProcessSupervisionBoundaryProof.blockers
$ResidentRuntimeProcessSupervisionBoundaryObserved = (
  [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.ok -and
  [string]$ResidentRuntimeProcessSupervisionBoundaryProof.status -eq 'proof_passed' -and
  [string]$ResidentRuntimeProcessSupervisionBoundaryProof.authority_family -eq 'process_supervision' -and
  [string]$ResidentRuntimeProcessSupervisionBoundaryProof.next_authority_family -eq 'service_control' -and
  [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.process_supervision_boundary_observed -and
  [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.authority_blockers_proof_observed -and
  [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.side_effects_denied -and
  [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.first_authority_family_consumed -and
  -not [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.local_process_launch_authority -and
  -not [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.process_supervision_authority -and
  -not [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.process_restart_authority -and
  -not [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.service_control_authority -and
  -not [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.resident_claim_authority -and
  -not [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.would_launch_process -and
  -not [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.would_supervise_process -and
  -not [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.would_restart_process -and
  -not [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.would_start_service -and
  -not [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.would_register_tray -and
  -not [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.would_register_hotkey -and
  -not [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.would_open_overlay -and
  -not [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.would_write_memory -and
  -not [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.would_claim_resident -and
  $ResidentRuntimeProcessSupervisionBoundaryBlockers -contains 'local_process_launch_authority_not_granted' -and
  $ResidentRuntimeProcessSupervisionBoundaryBlockers -contains 'process_supervision_authority_not_granted' -and
  $ResidentRuntimeProcessSupervisionBoundaryBlockers -contains 'process_restart_authority_not_granted' -and
  [string]$ResidentRuntimeProcessSupervisionBoundaryProof.next_smallest_truthful_gap -eq 'resident_runtime_service_control_authority_boundary'
)
$ResidentRuntimeServiceControlBoundaryProof = $Checkpoint.resident_runtime_service_control_boundary_proof
$ResidentRuntimeServiceControlBoundaryBlockers = ConvertTo-StringArray -Value $ResidentRuntimeServiceControlBoundaryProof.blockers
$ResidentRuntimeServiceControlBoundaryObserved = (
  [bool]$ResidentRuntimeServiceControlBoundaryProof.ok -and
  [string]$ResidentRuntimeServiceControlBoundaryProof.status -eq 'proof_passed' -and
  [string]$ResidentRuntimeServiceControlBoundaryProof.authority_family -eq 'service_control' -and
  [string]$ResidentRuntimeServiceControlBoundaryProof.previous_authority_family -eq 'process_supervision' -and
  [string]$ResidentRuntimeServiceControlBoundaryProof.next_authority_family -eq 'tray_presence' -and
  [bool]$ResidentRuntimeServiceControlBoundaryProof.service_control_boundary_observed -and
  [bool]$ResidentRuntimeServiceControlBoundaryProof.previous_process_supervision_family_observed -and
  [bool]$ResidentRuntimeServiceControlBoundaryProof.authority_blockers_proof_observed -and
  [bool]$ResidentRuntimeServiceControlBoundaryProof.side_effects_denied -and
  [bool]$ResidentRuntimeServiceControlBoundaryProof.second_authority_family_consumed -and
  -not [bool]$ResidentRuntimeServiceControlBoundaryProof.local_process_launch_authority -and
  -not [bool]$ResidentRuntimeServiceControlBoundaryProof.process_supervision_authority -and
  -not [bool]$ResidentRuntimeServiceControlBoundaryProof.process_restart_authority -and
  -not [bool]$ResidentRuntimeServiceControlBoundaryProof.service_install_authority -and
  -not [bool]$ResidentRuntimeServiceControlBoundaryProof.service_control_authority -and
  -not [bool]$ResidentRuntimeServiceControlBoundaryProof.resident_claim_authority -and
  -not [bool]$ResidentRuntimeServiceControlBoundaryProof.would_launch_process -and
  -not [bool]$ResidentRuntimeServiceControlBoundaryProof.would_supervise_process -and
  -not [bool]$ResidentRuntimeServiceControlBoundaryProof.would_restart_process -and
  -not [bool]$ResidentRuntimeServiceControlBoundaryProof.would_install_service -and
  -not [bool]$ResidentRuntimeServiceControlBoundaryProof.would_start_service -and
  -not [bool]$ResidentRuntimeServiceControlBoundaryProof.would_register_tray -and
  -not [bool]$ResidentRuntimeServiceControlBoundaryProof.would_register_hotkey -and
  -not [bool]$ResidentRuntimeServiceControlBoundaryProof.would_open_overlay -and
  -not [bool]$ResidentRuntimeServiceControlBoundaryProof.would_write_memory -and
  -not [bool]$ResidentRuntimeServiceControlBoundaryProof.would_claim_resident -and
  $ResidentRuntimeServiceControlBoundaryBlockers -contains 'service_install_authority_not_granted' -and
  $ResidentRuntimeServiceControlBoundaryBlockers -contains 'service_control_authority_not_granted' -and
  [string]$ResidentRuntimeServiceControlBoundaryProof.next_smallest_truthful_gap -eq 'resident_runtime_tray_presence_authority_boundary'
)
$ResidentRuntimeTrayPresenceBoundaryProof = $Checkpoint.resident_runtime_tray_presence_boundary_proof
$ResidentRuntimeTrayPresenceBoundaryBlockers = ConvertTo-StringArray -Value $ResidentRuntimeTrayPresenceBoundaryProof.blockers
$ResidentRuntimeTrayPresenceBoundaryObserved = (
  [bool]$ResidentRuntimeTrayPresenceBoundaryProof.ok -and
  [string]$ResidentRuntimeTrayPresenceBoundaryProof.status -eq 'proof_passed' -and
  [string]$ResidentRuntimeTrayPresenceBoundaryProof.authority_family -eq 'tray_presence' -and
  [string]$ResidentRuntimeTrayPresenceBoundaryProof.previous_authority_family -eq 'service_control' -and
  [string]$ResidentRuntimeTrayPresenceBoundaryProof.next_authority_family -eq 'hotkey_summon' -and
  [bool]$ResidentRuntimeTrayPresenceBoundaryProof.tray_presence_boundary_observed -and
  [bool]$ResidentRuntimeTrayPresenceBoundaryProof.previous_service_control_family_observed -and
  [bool]$ResidentRuntimeTrayPresenceBoundaryProof.tray_preflight_observed -and
  [bool]$ResidentRuntimeTrayPresenceBoundaryProof.authority_blockers_proof_observed -and
  [bool]$ResidentRuntimeTrayPresenceBoundaryProof.side_effects_denied -and
  [bool]$ResidentRuntimeTrayPresenceBoundaryProof.third_authority_family_consumed -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.local_process_launch_authority -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.process_supervision_authority -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.process_restart_authority -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.service_install_authority -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.service_control_authority -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.tray_registration_authority -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.tray_icon_authority -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.notification_authority -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.resident_claim_authority -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_launch_process -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_supervise_process -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_restart_process -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_install_service -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_start_service -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_register_tray -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_register_hotkey -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_open_overlay -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_write_memory -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_claim_resident -and
  $ResidentRuntimeTrayPresenceBoundaryBlockers -contains 'tray_registration_authority_not_granted' -and
  $ResidentRuntimeTrayPresenceBoundaryBlockers -contains 'tray_icon_authority_not_granted' -and
  $ResidentRuntimeTrayPresenceBoundaryBlockers -contains 'notification_authority_not_granted' -and
  [string]$ResidentRuntimeTrayPresenceBoundaryProof.next_smallest_truthful_gap -eq 'resident_runtime_hotkey_summon_authority_boundary'
)
$ResidentRuntimeHotkeySummonBoundaryProof = $Checkpoint.resident_runtime_hotkey_summon_boundary_proof
$ResidentRuntimeHotkeySummonBoundaryBlockers = ConvertTo-StringArray -Value $ResidentRuntimeHotkeySummonBoundaryProof.blockers
$ResidentRuntimeHotkeySummonBoundaryObserved = (
  [bool]$ResidentRuntimeHotkeySummonBoundaryProof.ok -and
  [string]$ResidentRuntimeHotkeySummonBoundaryProof.status -eq 'proof_passed' -and
  [string]$ResidentRuntimeHotkeySummonBoundaryProof.authority_family -eq 'hotkey_summon' -and
  [string]$ResidentRuntimeHotkeySummonBoundaryProof.previous_authority_family -eq 'tray_presence' -and
  [string]$ResidentRuntimeHotkeySummonBoundaryProof.next_authority_family -eq 'overlay_window' -and
  [bool]$ResidentRuntimeHotkeySummonBoundaryProof.hotkey_summon_boundary_observed -and
  [bool]$ResidentRuntimeHotkeySummonBoundaryProof.previous_tray_presence_family_observed -and
  [bool]$ResidentRuntimeHotkeySummonBoundaryProof.summon_preflight_observed -and
  [bool]$ResidentRuntimeHotkeySummonBoundaryProof.authority_blockers_proof_observed -and
  [bool]$ResidentRuntimeHotkeySummonBoundaryProof.side_effects_denied -and
  [bool]$ResidentRuntimeHotkeySummonBoundaryProof.fourth_authority_family_consumed -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.local_process_launch_authority -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.process_supervision_authority -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.process_restart_authority -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.service_install_authority -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.service_control_authority -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.tray_registration_authority -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.tray_icon_authority -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.notification_authority -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.summon_authority -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.hotkey_registration_authority -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.overlay_control_authority -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.resident_claim_authority -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_launch_process -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_supervise_process -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_restart_process -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_install_service -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_start_service -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_register_tray -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_register_hotkey -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_open_overlay -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_write_memory -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_claim_resident -and
  $ResidentRuntimeHotkeySummonBoundaryBlockers -contains 'global_hotkey_binding_disabled' -and
  $ResidentRuntimeHotkeySummonBoundaryBlockers -contains 'global_hotkey_registration_disabled' -and
  $ResidentRuntimeHotkeySummonBoundaryBlockers -contains 'hotkey_registration_authority_not_granted' -and
  $ResidentRuntimeHotkeySummonBoundaryBlockers -contains 'summon_authority_not_granted' -and
  [string]$ResidentRuntimeHotkeySummonBoundaryProof.next_smallest_truthful_gap -eq 'resident_runtime_overlay_window_authority_boundary'
)

$ResidentRuntimeOverlayWindowBoundaryProof = $Checkpoint.resident_runtime_overlay_window_boundary_proof
$ResidentRuntimeOverlayWindowBoundaryBlockers = ConvertTo-StringArray -Value $ResidentRuntimeOverlayWindowBoundaryProof.blockers
$ResidentRuntimeOverlayWindowBoundaryObserved = (
  [bool]$ResidentRuntimeOverlayWindowBoundaryProof.ok -and
  [string]$ResidentRuntimeOverlayWindowBoundaryProof.status -eq 'proof_passed' -and
  [string]$ResidentRuntimeOverlayWindowBoundaryProof.authority_family -eq 'overlay_window' -and
  [string]$ResidentRuntimeOverlayWindowBoundaryProof.previous_authority_family -eq 'hotkey_summon' -and
  [string]$ResidentRuntimeOverlayWindowBoundaryProof.next_authority_family -eq 'resident_claim' -and
  [bool]$ResidentRuntimeOverlayWindowBoundaryProof.overlay_window_boundary_observed -and
  [bool]$ResidentRuntimeOverlayWindowBoundaryProof.previous_hotkey_summon_family_observed -and
  [bool]$ResidentRuntimeOverlayWindowBoundaryProof.overlay_preflight_observed -and
  [bool]$ResidentRuntimeOverlayWindowBoundaryProof.authority_blockers_proof_observed -and
  [bool]$ResidentRuntimeOverlayWindowBoundaryProof.side_effects_denied -and
  [bool]$ResidentRuntimeOverlayWindowBoundaryProof.fifth_authority_family_consumed -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.local_process_launch_authority -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.process_supervision_authority -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.process_restart_authority -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.service_install_authority -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.service_control_authority -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.tray_registration_authority -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.tray_icon_authority -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.notification_authority -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.summon_authority -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.hotkey_registration_authority -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.overlay_control_authority -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.window_management_authority -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.capture_authority -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.new_sensing_authority -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.resident_claim_authority -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_launch_process -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_supervise_process -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_restart_process -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_install_service -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_start_service -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_register_tray -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_register_hotkey -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_open_overlay -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_write_memory -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_claim_resident -and
  $ResidentRuntimeOverlayWindowBoundaryBlockers -contains 'overlay_window_disabled' -and
  $ResidentRuntimeOverlayWindowBoundaryBlockers -contains 'overlay_control_authority_not_granted' -and
  $ResidentRuntimeOverlayWindowBoundaryBlockers -contains 'window_management_authority_not_granted' -and
  $ResidentRuntimeOverlayWindowBoundaryBlockers -contains 'capture_authority_not_granted' -and
  [string]$ResidentRuntimeOverlayWindowBoundaryProof.next_smallest_truthful_gap -eq 'resident_runtime_resident_claim_authority_boundary'
)

$ResidentRuntimeResidentClaimBoundaryProof = $Checkpoint.resident_runtime_resident_claim_boundary_proof
$ResidentRuntimeResidentClaimBoundaryBlockers = ConvertTo-StringArray -Value $ResidentRuntimeResidentClaimBoundaryProof.blockers
$ResidentRuntimeResidentClaimBoundaryObserved = (
  [bool]$ResidentRuntimeResidentClaimBoundaryProof.ok -and
  [string]$ResidentRuntimeResidentClaimBoundaryProof.status -eq 'proof_passed' -and
  [string]$ResidentRuntimeResidentClaimBoundaryProof.authority_family -eq 'resident_claim' -and
  [string]$ResidentRuntimeResidentClaimBoundaryProof.previous_authority_family -eq 'overlay_window' -and
  [string]$ResidentRuntimeResidentClaimBoundaryProof.next_authority_family -eq '' -and
  [bool]$ResidentRuntimeResidentClaimBoundaryProof.resident_claim_boundary_observed -and
  [bool]$ResidentRuntimeResidentClaimBoundaryProof.previous_overlay_window_family_observed -and
  [bool]$ResidentRuntimeResidentClaimBoundaryProof.authority_blockers_proof_observed -and
  [bool]$ResidentRuntimeResidentClaimBoundaryProof.side_effects_denied -and
  [bool]$ResidentRuntimeResidentClaimBoundaryProof.sixth_authority_family_consumed -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.local_process_launch_authority -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.process_supervision_authority -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.process_restart_authority -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.service_install_authority -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.service_control_authority -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.tray_registration_authority -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.tray_icon_authority -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.notification_authority -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.summon_authority -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.hotkey_registration_authority -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.overlay_control_authority -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.window_management_authority -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.capture_authority -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.new_sensing_authority -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.resident_claim_authority -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_launch_process -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_supervise_process -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_restart_process -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_install_service -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_start_service -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_register_tray -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_register_hotkey -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_open_overlay -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_write_memory -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_claim_resident -and
  $ResidentRuntimeResidentClaimBoundaryBlockers -contains 'resident_claim_authority_not_granted' -and
  $ResidentRuntimeResidentClaimBoundaryBlockers -contains 'resident_surface_runtime_missing' -and
  [string]$ResidentRuntimeResidentClaimBoundaryProof.next_smallest_truthful_gap -eq 'stage6_lens_completion_audit'
)
$CommandPaletteShellBridge = $Checkpoint.command_palette_shell_bridge
$CommandPaletteShellBridgeGovernance = $CommandPaletteShellBridge.governance
$CommandPaletteShellBridgeBlockers = ConvertTo-StringArray -Value $CommandPaletteShellBridge.blockers
$CommandPaletteShellBridgeObserved = (
  [bool]$CommandPaletteShellBridge.ok -and
  [string]$CommandPaletteShellBridge.status -eq 'blocked' -and
  [bool]$CommandPaletteShellBridge.readback_ready -and
  [string]$CommandPaletteShellBridge.availability -eq 'chat_ui_only' -and
  -not [bool]$CommandPaletteShellBridge.os_level_command_palette -and
  -not [bool]$CommandPaletteShellBridge.summon_anywhere -and
  [int]$CommandPaletteShellBridge.command_total -gt 0 -and
  [string]$CommandPaletteShellBridge.next_smallest_truthful_gap -eq 'os_level_command_palette_binding' -and
  -not [bool]$CommandPaletteShellBridgeGovernance.opens_palette -and
  -not [bool]$CommandPaletteShellBridgeGovernance.execution_authority -and
  -not [bool]$CommandPaletteShellBridgeGovernance.approval_decision_authority -and
  -not [bool]$CommandPaletteShellBridgeGovernance.memory_write -and
  -not [bool]$CommandPaletteShellBridgeGovernance.overlay_control_authority -and
  -not [bool]$CommandPaletteShellBridgeGovernance.summon_authority -and
  -not [bool]$CommandPaletteShellBridgeGovernance.hotkey_registration_authority -and
  -not [bool]$CommandPaletteShellBridgeGovernance.tray_registration_authority -and
  -not [bool]$CommandPaletteShellBridgeGovernance.local_process_launch_authority -and
  -not [bool]$CommandPaletteShellBridgeGovernance.mutation_authority_granted -and
  $CommandPaletteShellBridgeBlockers -contains 'os_level_command_palette_missing' -and
  $CommandPaletteShellBridgeBlockers -contains 'summon_anywhere_missing' -and
  $CommandPaletteShellBridgeBlockers -contains 'global_hotkey_binding_missing'
)
$CommandPaletteOsBindingProof = $Checkpoint.command_palette_os_binding_blockers_proof
$CommandPaletteOsBindingGroups = $CommandPaletteOsBindingProof.blocker_groups
$CommandPaletteOsBindingGovernance = $CommandPaletteOsBindingProof.governance
$CommandPaletteOsBindingFamilies = ConvertTo-StringArray -Value $CommandPaletteOsBindingProof.blocked_families
$CommandPaletteOsBindingPaletteBlockers = ConvertTo-StringArray -Value $CommandPaletteOsBindingGroups.palette_binding
$CommandPaletteOsBindingGlobalHotkeyBlockers = ConvertTo-StringArray -Value $CommandPaletteOsBindingGroups.global_hotkey_binding
$CommandPaletteOsBindingSummonBlockers = ConvertTo-StringArray -Value $CommandPaletteOsBindingGroups.summon_binding
$CommandPaletteOsBindingTrayBlockers = ConvertTo-StringArray -Value $CommandPaletteOsBindingGroups.tray_presence
$CommandPaletteOsBindingOverlayBlockers = ConvertTo-StringArray -Value $CommandPaletteOsBindingGroups.overlay_window
$CommandPaletteOsBindingAuthorityBlockers = ConvertTo-StringArray -Value $CommandPaletteOsBindingGroups.authority
$CommandPaletteOsBindingCandidate = $CommandPaletteOsBindingProof.os_binding_candidate
$CommandPaletteOsBindingCandidateRequiredAuthority = ConvertTo-StringArray -Value $CommandPaletteOsBindingCandidate.required_authority
$CommandPaletteOsBindingCandidateRequiredFamilies = ConvertTo-StringArray -Value $CommandPaletteOsBindingCandidate.required_preflight_families
$CommandPaletteOsBindingCandidateBlockers = ConvertTo-StringArray -Value $CommandPaletteOsBindingCandidate.blocked_by
$CommandPaletteOsBindingCandidateObserved = (
  [bool]$CommandPaletteOsBindingProof.os_binding_candidate_observed -and
  [string]$CommandPaletteOsBindingCandidate.kind -eq 'lens.command_palette.os_binding_candidate' -and
  [string]$CommandPaletteOsBindingCandidate.status -eq 'blocked' -and
  [string]$CommandPaletteOsBindingCandidate.candidate -eq 'global_hotkey_to_lens_command_palette_bridge' -and
  [string]$CommandPaletteOsBindingCandidate.trigger -eq 'Ctrl+Alt+Space' -and
  [string]$CommandPaletteOsBindingCandidate.binding_scope -eq 'global' -and
  [string]$CommandPaletteOsBindingCandidate.route -eq '/lens/status' -and
  [string]$CommandPaletteOsBindingCandidate.local_surface -eq 'chat_ui.command_palette' -and
  [string]$CommandPaletteOsBindingCandidate.bridge_script -eq 'scripts/lens-command-palette.ps1' -and
  [string]$CommandPaletteOsBindingCandidate.proof_script -eq 'scripts/lens-command-palette-os-binding-proof.ps1' -and
  [string]$CommandPaletteOsBindingCandidate.requires_approval_kind -eq 'lens.os_binding.command_palette_binding_authority' -and
  $CommandPaletteOsBindingCandidateRequiredAuthority -contains 'lens.os_binding.command_palette_binding_authority' -and
  $CommandPaletteOsBindingCandidateRequiredAuthority -contains 'hotkey_registration_authority' -and
  $CommandPaletteOsBindingCandidateRequiredAuthority -contains 'summon_authority' -and
  $CommandPaletteOsBindingCandidateRequiredAuthority -contains 'local_process_launch_authority' -and
  $CommandPaletteOsBindingCandidateRequiredFamilies -contains 'palette_binding' -and
  $CommandPaletteOsBindingCandidateRequiredFamilies -contains 'global_hotkey_binding' -and
  $CommandPaletteOsBindingCandidateRequiredFamilies -contains 'summon_binding' -and
  $CommandPaletteOsBindingCandidateRequiredFamilies -contains 'authority' -and
  $CommandPaletteOsBindingCandidateBlockers -contains 'os_level_command_palette_missing' -and
  $CommandPaletteOsBindingCandidateBlockers -contains 'global_hotkey_binding_disabled' -and
  $CommandPaletteOsBindingCandidateBlockers -contains 'lens_summon_binding_not_implemented' -and
  $CommandPaletteOsBindingCandidateBlockers -contains 'summon_authority_not_granted' -and
  $CommandPaletteOsBindingCandidateBlockers -contains 'hotkey_registration_authority_not_granted' -and
  $CommandPaletteOsBindingCandidateBlockers -contains 'local_process_launch_authority_not_granted' -and
  [string]$CommandPaletteOsBindingCandidate.current_authorized_effect -eq 'readback_only_status' -and
  [string]$CommandPaletteOsBindingCandidate.candidate_effect_if_authorized -eq 'open_lens_command_palette_from_governed_os_binding' -and
  -not [bool]$CommandPaletteOsBindingCandidate.open_mode_authorized -and
  [string]$CommandPaletteOsBindingCandidate.open_mode_refusal -eq 'lens_command_palette_open_not_authorized' -and
  -not [bool]$CommandPaletteOsBindingCandidate.would_register_hotkey_now -and
  -not [bool]$CommandPaletteOsBindingCandidate.would_open_palette_now -and
  -not [bool]$CommandPaletteOsBindingCandidate.would_summon_anywhere_now -and
  -not [bool]$CommandPaletteOsBindingCandidate.would_launch_process_now -and
  -not [bool]$CommandPaletteOsBindingCandidate.would_write_memory_now -and
  [string]$CommandPaletteOsBindingCandidate.next_smallest_truthful_gap -eq 'os_level_command_palette_binding'
)
$CommandPaletteOsBindingObserved = (
  [bool]$CommandPaletteOsBindingProof.ok -and
  [string]$CommandPaletteOsBindingProof.status -eq 'proof_passed' -and
  [int]$CommandPaletteOsBindingProof.exit_code -eq 0 -and
  [string]$CommandPaletteOsBindingProof.acceptance_criterion -eq 'summon_anywhere' -and
  [bool]$CommandPaletteOsBindingProof.os_level_command_palette_binding_observed -and
  [bool]$CommandPaletteOsBindingProof.summon_preflight_observed -and
  [bool]$CommandPaletteOsBindingProof.tray_preflight_observed -and
  [bool]$CommandPaletteOsBindingProof.overlay_preflight_observed -and
  $CommandPaletteOsBindingCandidateObserved -and
  [bool]$CommandPaletteOsBindingProof.side_effects_denied -and
  $CommandPaletteOsBindingFamilies -contains 'palette_binding' -and
  $CommandPaletteOsBindingFamilies -contains 'global_hotkey_binding' -and
  $CommandPaletteOsBindingFamilies -contains 'summon_binding' -and
  $CommandPaletteOsBindingFamilies -contains 'tray_presence' -and
  $CommandPaletteOsBindingFamilies -contains 'overlay_window' -and
  $CommandPaletteOsBindingFamilies -contains 'authority' -and
  [string]$CommandPaletteOsBindingProof.first_blocker_family -eq 'palette_binding' -and
  [string]$CommandPaletteOsBindingProof.next_smallest_truthful_gap -eq 'os_level_command_palette_binding' -and
  $CommandPaletteOsBindingPaletteBlockers -contains 'os_level_command_palette_missing' -and
  $CommandPaletteOsBindingPaletteBlockers -contains 'summon_anywhere_missing' -and
  $CommandPaletteOsBindingPaletteBlockers -contains 'global_hotkey_binding_missing' -and
  $CommandPaletteOsBindingGlobalHotkeyBlockers -contains 'global_hotkey_binding_disabled' -and
  $CommandPaletteOsBindingGlobalHotkeyBlockers -contains 'global_hotkey_registration_disabled' -and
  $CommandPaletteOsBindingGlobalHotkeyBlockers -contains 'hotkey_registration_authority_not_granted' -and
  $CommandPaletteOsBindingSummonBlockers -contains 'lens_summon_binding_not_implemented' -and
  $CommandPaletteOsBindingSummonBlockers -contains 'summon_authority_not_granted' -and
  $CommandPaletteOsBindingTrayBlockers -contains 'tray_host_disabled' -and
  $CommandPaletteOsBindingTrayBlockers -contains 'tray_registration_authority_not_granted' -and
  $CommandPaletteOsBindingOverlayBlockers -contains 'overlay_window_disabled' -and
  $CommandPaletteOsBindingOverlayBlockers -contains 'overlay_control_authority_not_granted' -and
  $CommandPaletteOsBindingAuthorityBlockers -contains 'summon_authority_not_granted' -and
  $CommandPaletteOsBindingAuthorityBlockers -contains 'local_process_launch_authority_not_granted' -and
  [bool]$CommandPaletteOsBindingGovernance.os_binding_candidate_boundary_readback -and
  [bool]$CommandPaletteOsBindingGovernance.read_only_contract -and
  [bool]$CommandPaletteOsBindingGovernance.diagnostic_only -and
  -not [bool]$CommandPaletteOsBindingGovernance.opens_palette -and
  -not [bool]$CommandPaletteOsBindingGovernance.execution_authority -and
  -not [bool]$CommandPaletteOsBindingGovernance.approval_decision_authority -and
  -not [bool]$CommandPaletteOsBindingGovernance.memory_write -and
  -not [bool]$CommandPaletteOsBindingGovernance.overlay_control_authority -and
  -not [bool]$CommandPaletteOsBindingGovernance.window_management_authority -and
  -not [bool]$CommandPaletteOsBindingGovernance.summon_authority -and
  -not [bool]$CommandPaletteOsBindingGovernance.hotkey_registration_authority -and
  -not [bool]$CommandPaletteOsBindingGovernance.tray_registration_authority -and
  -not [bool]$CommandPaletteOsBindingGovernance.local_process_launch_authority -and
  -not [bool]$CommandPaletteOsBindingGovernance.service_control_authority -and
  -not [bool]$CommandPaletteOsBindingGovernance.capture_authority -and
  -not [bool]$CommandPaletteOsBindingGovernance.new_sensing_authority -and
  -not [bool]$CommandPaletteOsBindingGovernance.mutation_authority_granted
)
$OsBindingAuthorityRequestReadback = $Checkpoint.os_binding_authority_request_readback
$OsBindingAuthorityRequestReadbackGovernance = $OsBindingAuthorityRequestReadback.governance
$OsBindingAuthorityRequestReadbackObserved = (
  [bool]$OsBindingAuthorityRequestReadback.ok -and
  [string]$OsBindingAuthorityRequestReadback.kind -eq 'lens.os_binding.command_palette_binding_authority.request_readback' -and
  [string]$OsBindingAuthorityRequestReadback.route -eq '/lens/os-binding/authority/requests' -and
  [string]$OsBindingAuthorityRequestReadback.authority_route -eq '/lens/os-binding/authority' -and
  [string]$OsBindingAuthorityRequestReadback.request_route -eq '/lens/os-binding/authority/request' -and
  [string]$OsBindingAuthorityRequestReadback.readiness_route -eq '/lens/os-binding/readiness' -and
  [string]$OsBindingAuthorityRequestReadback.plan_route -eq '/lens/os-binding/plan' -and
  [bool]$OsBindingAuthorityRequestReadback.stage6_criterion_readback_ready -and
  -not [bool]$OsBindingAuthorityRequestReadback.authority_granted -and
  -not [bool]$OsBindingAuthorityRequestReadback.os_level_command_palette_binding_authority -and
  -not [bool]$OsBindingAuthorityRequestReadback.os_level_command_palette -and
  -not [bool]$OsBindingAuthorityRequestReadback.summon_anywhere -and
  -not [bool]$OsBindingAuthorityRequestReadback.opens_palette -and
  -not [bool]$OsBindingAuthorityRequestReadback.registers_hotkey -and
  -not [bool]$OsBindingAuthorityRequestReadback.launches_process -and
  -not [bool]$OsBindingAuthorityRequestReadback.controls_overlay -and
  [bool]$OsBindingAuthorityRequestReadbackGovernance.read_only_contract -and
  -not [bool]$OsBindingAuthorityRequestReadbackGovernance.approval_request_write -and
  -not [bool]$OsBindingAuthorityRequestReadbackGovernance.execution_authority -and
  -not [bool]$OsBindingAuthorityRequestReadbackGovernance.approval_decision_authority -and
  -not [bool]$OsBindingAuthorityRequestReadbackGovernance.memory_write -and
  -not [bool]$OsBindingAuthorityRequestReadbackGovernance.resident_claim_authority
)
$SummonAnywhereBlockersProofGroups = $SummonAnywhereBlockersProof.blocker_groups
$SummonAnywhereBlockersProofGovernance = $SummonAnywhereBlockersProof.governance
$SummonAnywhereBlockersProofFamilies = ConvertTo-StringArray -Value $SummonAnywhereBlockersProof.blocked_families
$SummonAnywhereBlockersProofResidentHostBlockers = ConvertTo-StringArray -Value $SummonAnywhereBlockersProofGroups.resident_host
$SummonAnywhereBlockersProofTrayBlockers = ConvertTo-StringArray -Value $SummonAnywhereBlockersProofGroups.tray_presence
$SummonAnywhereBlockersProofOverlayBlockers = ConvertTo-StringArray -Value $SummonAnywhereBlockersProofGroups.overlay_window
$SummonAnywhereBlockersProofGlobalHotkeyBlockers = ConvertTo-StringArray -Value $SummonAnywhereBlockersProofGroups.global_hotkey_binding
$SummonAnywhereBlockersProofSummonBlockers = ConvertTo-StringArray -Value $SummonAnywhereBlockersProofGroups.summon_binding
$SummonAnywhereBlockersProofAuthorityBlockers = ConvertTo-StringArray -Value $SummonAnywhereBlockersProofGroups.authority
$SummonAnywhereBlockersProofFirstFamilyHandoff = $SummonAnywhereBlockersProof.first_blocker_family_handoff
$SummonAnywhereBlockersProofFirstFamilyHandoffBlockers = ConvertTo-StringArray -Value (
  $SummonAnywhereBlockersProofFirstFamilyHandoff.blockers
)
$SummonAnywhereBlockersProofFamilyHandoffs = @($SummonAnywhereBlockersProof.blocked_family_handoffs)
$SummonAnywhereBlockersProofFamilyHandoffIds = [string[]]@(
  $SummonAnywhereBlockersProofFamilyHandoffs | ForEach-Object { [string]$_.id }
)
$SummonAnywhereBlockersProofFamilyHandoffsAligned = (
  @($SummonAnywhereBlockersProofFamilyHandoffIds).Count -eq @($SummonAnywhereBlockersProofFamilies).Count
)
for ($Index = 0; $Index -lt @($SummonAnywhereBlockersProofFamilies).Count; $Index += 1) {
  if (
    @($SummonAnywhereBlockersProofFamilyHandoffIds).Count -le $Index -or
    [string]$SummonAnywhereBlockersProofFamilyHandoffIds[$Index] -ne [string]$SummonAnywhereBlockersProofFamilies[$Index]
  ) {
    $SummonAnywhereBlockersProofFamilyHandoffsAligned = $false
  }
}
$SummonAnywhereBlockersProofFamilyHandoffsBounded = $true
foreach ($Handoff in @($SummonAnywhereBlockersProofFamilyHandoffs)) {
  if (
    -not [bool]$Handoff.read_only_contract -or
    -not [bool]$Handoff.diagnostic_only -or
    [bool]$Handoff.authority_granted -or
    [bool]$Handoff.would_execute -or
    [bool]$Handoff.would_mutate
  ) {
    $SummonAnywhereBlockersProofFamilyHandoffsBounded = $false
  }
}
$SummonAnywhereBlockersProofFirstFamilyHandoffObserved = (
  [bool]$SummonAnywhereBlockersProof.first_blocker_family_handoff_observed -and
  [bool]$SummonAnywhereBlockersProofGovernance.first_blocker_family_handoff_readback -and
  $SummonAnywhereBlockersProofFamilyHandoffsAligned -and
  $SummonAnywhereBlockersProofFamilyHandoffsBounded -and
  [string]$SummonAnywhereBlockersProofFirstFamilyHandoff.id -eq 'resident_host' -and
  [string]$SummonAnywhereBlockersProofFirstFamilyHandoff.status -eq 'blocked' -and
  [string]$SummonAnywhereBlockersProofFirstFamilyHandoff.proof_script -eq 'scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status' -and
  [string]$SummonAnywhereBlockersProofFirstFamilyHandoff.route -eq '/lens/host' -and
  [string]$SummonAnywhereBlockersProofFirstFamilyHandoff.readiness_route -eq '/lens/host/runtime-loop/readiness' -and
  [string]$SummonAnywhereBlockersProofFirstFamilyHandoff.next_step -eq 'run_resident_host_blocker_proof' -and
  [string]$SummonAnywhereBlockersProofFirstFamilyHandoff.next_smallest_truthful_gap -eq 'resident_host_runtime_blocker_boundary' -and
  [string]$SummonAnywhereBlockersProofFirstFamilyHandoff.authority_required -eq 'resident_runtime_execution_authority' -and
  $SummonAnywhereBlockersProofFirstFamilyHandoffBlockers -contains 'local_process_launch_authority_not_granted' -and
  -not [bool]$SummonAnywhereBlockersProofFirstFamilyHandoff.authority_granted -and
  [bool]$SummonAnywhereBlockersProofFirstFamilyHandoff.read_only_contract -and
  [bool]$SummonAnywhereBlockersProofFirstFamilyHandoff.diagnostic_only -and
  -not [bool]$SummonAnywhereBlockersProofFirstFamilyHandoff.would_execute -and
  -not [bool]$SummonAnywhereBlockersProofFirstFamilyHandoff.would_mutate
)
$SummonAnywhereBlockersProofObserved = (
  [int]$SummonAnywhereBlockersProofResult.exit_code -eq 0 -and
  [bool]$SummonAnywhereBlockersProof.ok -and
  [string]$SummonAnywhereBlockersProof.kind -eq 'lens.summon_anywhere_blockers.proof' -and
  [string]$SummonAnywhereBlockersProof.status -eq 'proof_passed' -and
  [string]$SummonAnywhereBlockersProof.acceptance_criterion -eq 'summon_anywhere' -and
  [string]$SummonAnywhereBlockersProof.next_smallest_truthful_gap -eq 'summon_anywhere_blockers' -and
  [bool]$SummonAnywhereBlockersProof.summon_preflight_observed -and
  [bool]$SummonAnywhereBlockersProof.stage6_family_projection_observed -and
  [bool]$SummonAnywhereBlockersProof.side_effects_denied -and
  [bool]$SummonAnywhereBlockersProof.os_binding_authority_request_readback_observed -and
  $SummonAnywhereBlockersProofFirstFamilyHandoffObserved -and
  [string]$SummonAnywhereBlockersProof.first_blocker_family -eq 'resident_host' -and
  $SummonAnywhereBlockersProofFamilies -contains 'resident_host' -and
  $SummonAnywhereBlockersProofFamilies -contains 'tray_presence' -and
  $SummonAnywhereBlockersProofFamilies -contains 'overlay_window' -and
  $SummonAnywhereBlockersProofFamilies -contains 'global_hotkey_binding' -and
  $SummonAnywhereBlockersProofFamilies -contains 'summon_binding' -and
  $SummonAnywhereBlockersProofFamilies -contains 'authority' -and
  $SummonAnywhereBlockersProofResidentHostBlockers -contains 'local_process_launch_authority_not_granted' -and
  $SummonAnywhereBlockersProofTrayBlockers -contains 'tray_host_missing' -and
  $SummonAnywhereBlockersProofOverlayBlockers -contains 'overlay_window_missing' -and
  $SummonAnywhereBlockersProofGlobalHotkeyBlockers -contains 'global_hotkey_binding_disabled' -and
  $SummonAnywhereBlockersProofGlobalHotkeyBlockers -contains 'global_hotkey_registration_disabled' -and
  $SummonAnywhereBlockersProofGlobalHotkeyBlockers -contains 'hotkey_registration_authority_not_granted' -and
  $SummonAnywhereBlockersProofSummonBlockers -contains 'lens_summon_binding_not_implemented' -and
  $SummonAnywhereBlockersProofSummonBlockers -contains 'summon_authority_not_granted' -and
  $SummonAnywhereBlockersProofAuthorityBlockers -contains 'summon_authority_not_granted' -and
  $SummonAnywhereBlockersProofAuthorityBlockers -contains 'hotkey_registration_authority_not_granted' -and
  $SummonAnywhereBlockersProofAuthorityBlockers -contains 'overlay_control_authority_not_granted' -and
  $SummonAnywhereBlockersProofAuthorityBlockers -contains 'local_process_launch_authority_not_granted' -and
  [bool]$SummonAnywhereBlockersProofGovernance.diagnostic_only -and
  [bool]$SummonAnywhereBlockersProofGovernance.wraps_summon_preflight -and
  [bool]$SummonAnywhereBlockersProofGovernance.wraps_lens_status -and
  [bool]$SummonAnywhereBlockersProofGovernance.read_only_contract -and
  [bool]$SummonAnywhereBlockersProofGovernance.os_binding_authority_request_readback -and
  [bool]$SummonAnywhereBlockersProofGovernance.first_blocker_family_handoff_readback -and
  -not [bool]$SummonAnywhereBlockersProofGovernance.approval_request_write -and
  -not [bool]$SummonAnywhereBlockersProofGovernance.product_execution_authority -and
  -not [bool]$SummonAnywhereBlockersProofGovernance.execution_authority -and
  -not [bool]$SummonAnywhereBlockersProofGovernance.approval_decision_authority -and
  -not [bool]$SummonAnywhereBlockersProofGovernance.memory_write -and
  -not [bool]$SummonAnywhereBlockersProofGovernance.overlay_control_authority -and
  -not [bool]$SummonAnywhereBlockersProofGovernance.summon_authority -and
  -not [bool]$SummonAnywhereBlockersProofGovernance.local_process_launch_authority -and
  -not [bool]$SummonAnywhereBlockersProofGovernance.hotkey_registration_authority -and
  -not [bool]$SummonAnywhereBlockersProofGovernance.resident_claim_authority -and
  -not [bool]$SummonAnywhereBlockersProofGovernance.mutation_authority_granted
)
$SummonAuthorityBlockerProofGovernance = $SummonAuthorityBlockerProof.governance
$SummonAuthorityBoundary = $SummonAuthorityBlockerProof.summon_authority_boundary
$SummonAuthorityBlockers = ConvertTo-StringArray -Value $SummonAuthorityBlockerProof.summon_authority_blockers
$DirectSummonPreflightAuthorityBlockers = ConvertTo-StringArray -Value $SummonAuthorityBlockerProof.direct_summon_preflight_authority_blockers
$DirectSummonPreflightBindingBlockers = ConvertTo-StringArray -Value $SummonAuthorityBlockerProof.direct_summon_preflight_binding_blockers
$SummonAuthorityBoundaryRequiredBeforeEnable = ConvertTo-StringArray -Value $SummonAuthorityBoundary.required_before_enable
$SummonAuthorityBoundaryBlockers = ConvertTo-StringArray -Value $SummonAuthorityBoundary.blockers
$SummonAuthorityBoundaryBindingBlockers = ConvertTo-StringArray -Value $SummonAuthorityBoundary.summon_binding_blockers
$SummonAuthorityBoundaryAuthorityBlockers = ConvertTo-StringArray -Value $SummonAuthorityBoundary.authority_blockers
$SummonAuthorityBlockerProofObserved = (
  [int]$SummonAuthorityBlockerProofResult.exit_code -eq 0 -and
  [bool]$SummonAuthorityBlockerProof.ok -and
  [string]$SummonAuthorityBlockerProof.kind -eq 'lens.summon_authority_blocker.proof' -and
  [string]$SummonAuthorityBlockerProof.status -eq 'proof_passed' -and
  [string]$SummonAuthorityBlockerProof.acceptance_criterion -eq 'summon_anywhere' -and
  [string]$SummonAuthorityBlockerProof.previous_summon_blocker_family -eq 'summon_binding' -and
  [string]$SummonAuthorityBlockerProof.summon_authority_blocker_family -eq 'authority' -and
  [string]$SummonAuthorityBlockerProof.sixth_summon_blocker_family -eq 'authority' -and
  [string]$SummonAuthorityBlockerProof.next_summon_blocker_family -eq 'stage6_lens_completion_audit' -and
  [string]$SummonAuthorityBlockerProof.summon_next_smallest_truthful_gap -eq 'summon_anywhere_blockers' -and
  [string]$SummonAuthorityBlockerProof.previous_binding_next_smallest_truthful_gap -eq 'summon_authority_blocker_boundary' -and
  [string]$SummonAuthorityBlockerProof.direct_summon_preflight_next_smallest_truthful_gap -eq 'summon_anywhere_blockers' -and
  [string]$SummonAuthorityBlockerProof.next_smallest_truthful_gap -eq 'stage6_lens_completion_audit' -and
  [bool]$SummonAuthorityBlockerProof.summon_authority_family_observed -and
  [bool]$SummonAuthorityBlockerProof.previous_summon_binding_bridge_observed -and
  [bool]$SummonAuthorityBlockerProof.summon_preflight_authority_observed -and
  [bool]$SummonAuthorityBlockerProof.all_summon_blocker_families_consumed -and
  [bool]$SummonAuthorityBlockerProof.handoff_aligned -and
  [bool]$SummonAuthorityBlockerProof.side_effects_denied -and
  $SummonAuthorityBlockers -contains 'summon_authority_not_granted' -and
  $SummonAuthorityBlockers -contains 'hotkey_registration_authority_not_granted' -and
  $SummonAuthorityBlockers -contains 'overlay_control_authority_not_granted' -and
  $SummonAuthorityBlockers -contains 'local_process_launch_authority_not_granted' -and
  $DirectSummonPreflightAuthorityBlockers -contains 'summon_authority_not_granted' -and
  $DirectSummonPreflightAuthorityBlockers -contains 'hotkey_registration_authority_not_granted' -and
  $DirectSummonPreflightAuthorityBlockers -contains 'overlay_control_authority_not_granted' -and
  $DirectSummonPreflightAuthorityBlockers -contains 'local_process_launch_authority_not_granted' -and
  $DirectSummonPreflightBindingBlockers -contains 'lens_summon_binding_not_implemented' -and
  $DirectSummonPreflightBindingBlockers -contains 'summon_authority_not_granted' -and
  [string]$SummonAuthorityBoundary.status -eq 'blocked' -and
  -not [bool]$SummonAuthorityBoundary.ready -and
  [string]$SummonAuthorityBoundary.summon_name -eq 'Francis Lens Summon' -and
  [string]$SummonAuthorityBoundary.config_path -eq 'config/runtime/lens/summon.json' -and
  [string]$SummonAuthorityBoundary.global_hotkey -eq 'Ctrl+Alt+Space' -and
  [string]$SummonAuthorityBoundary.binding_scope -eq 'global' -and
  [string]$SummonAuthorityBoundary.palette_route -eq '/lens/status' -and
  $SummonAuthorityBoundaryRequiredBeforeEnable -contains 'resident_host_process' -and
  $SummonAuthorityBoundaryRequiredBeforeEnable -contains 'tray_presence' -and
  $SummonAuthorityBoundaryRequiredBeforeEnable -contains 'overlay_window' -and
  $SummonAuthorityBoundaryRequiredBeforeEnable -contains 'global_hotkey_binding' -and
  $SummonAuthorityBoundaryRequiredBeforeEnable -contains 'summon_binding' -and
  -not [bool]$SummonAuthorityBoundary.binding_enabled -and
  -not [bool]$SummonAuthorityBoundary.register_hotkey -and
  -not [bool]$SummonAuthorityBoundary.startup_register -and
  $SummonAuthorityBoundaryBlockers -contains 'summon_authority_not_granted' -and
  $SummonAuthorityBoundaryBlockers -contains 'hotkey_registration_authority_not_granted' -and
  $SummonAuthorityBoundaryBlockers -contains 'overlay_control_authority_not_granted' -and
  $SummonAuthorityBoundaryBlockers -contains 'local_process_launch_authority_not_granted' -and
  $SummonAuthorityBoundaryBindingBlockers -contains 'lens_summon_binding_not_implemented' -and
  $SummonAuthorityBoundaryBindingBlockers -contains 'summon_authority_not_granted' -and
  $SummonAuthorityBoundaryAuthorityBlockers -contains 'summon_authority_not_granted' -and
  $SummonAuthorityBoundaryAuthorityBlockers -contains 'hotkey_registration_authority_not_granted' -and
  $SummonAuthorityBoundaryAuthorityBlockers -contains 'overlay_control_authority_not_granted' -and
  $SummonAuthorityBoundaryAuthorityBlockers -contains 'local_process_launch_authority_not_granted' -and
  [bool]$SummonAuthorityBlockerProofGovernance.diagnostic_only -and
  [bool]$SummonAuthorityBlockerProofGovernance.wraps_summon_anywhere_blockers_proof -and
  [bool]$SummonAuthorityBlockerProofGovernance.wraps_summon_binding_blocker_proof -and
  [bool]$SummonAuthorityBlockerProofGovernance.wraps_summon_preflight -and
  [bool]$SummonAuthorityBlockerProofGovernance.read_only_contract -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.approval_request_write -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.resident_runtime_execution_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.product_execution_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.execution_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.approval_decision_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.local_process_launch_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.process_supervision_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.process_restart_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.service_install_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.service_control_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.tray_registration_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.tray_icon_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.notification_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.hotkey_registration_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.overlay_control_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.window_management_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.capture_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.new_sensing_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.summon_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.memory_write -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.receipt_write_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.resident_claim_authority -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.mutation_authority_granted
)
$SummonAnywhereFamilyChainProofGovernance = $SummonAnywhereFamilyChainProof.governance
$SummonAnywhereFamilyChainProofResidentHost = $SummonAnywhereFamilyChainProof.resident_host
$SummonAnywhereFamilyChainProofFinalAuthority = $SummonAnywhereFamilyChainProof.final_authority
$SummonAnywhereFamilyChainProofBlockedFamilies = ConvertTo-StringArray -Value $SummonAnywhereFamilyChainProof.blocked_families
$SummonAnywhereFamilyChainProofResidentHostRuntimeBlockers = ConvertTo-StringArray -Value (
  $SummonAnywhereFamilyChainProofResidentHost.runtime_blockers
)
$SummonAnywhereFamilyChainProofResidentHostSurfaceBlockers = ConvertTo-StringArray -Value (
  $SummonAnywhereFamilyChainProofResidentHost.surface_blockers
)
$SummonAnywhereFamilyChainProofFinalAuthorityBlockers = ConvertTo-StringArray -Value (
  $SummonAnywhereFamilyChainProofFinalAuthority.blockers
)
$ExpectedSummonAnywhereFamilyChain = @(
  'resident_host',
  'tray_presence',
  'overlay_window',
  'global_hotkey_binding',
  'summon_binding',
  'authority'
)
$SummonAnywhereFamilyChainBlockedFamiliesAligned = (
  @($SummonAnywhereFamilyChainProofBlockedFamilies).Count -eq @($ExpectedSummonAnywhereFamilyChain).Count
)
for ($Index = 0; $Index -lt @($ExpectedSummonAnywhereFamilyChain).Count; $Index += 1) {
  if (
    @($SummonAnywhereFamilyChainProofBlockedFamilies).Count -le $Index -or
    [string]$SummonAnywhereFamilyChainProofBlockedFamilies[$Index] -ne [string]$ExpectedSummonAnywhereFamilyChain[$Index]
  ) {
    $SummonAnywhereFamilyChainBlockedFamiliesAligned = $false
  }
}
$SummonAnywhereFamilyChainProofObserved = (
  [int]$SummonAnywhereFamilyChainProofResult.exit_code -eq 0 -and
  [bool]$SummonAnywhereFamilyChainProof.ok -and
  [string]$SummonAnywhereFamilyChainProof.kind -eq 'lens.summon_anywhere_family_chain.proof' -and
  [string]$SummonAnywhereFamilyChainProof.status -eq 'proof_passed' -and
  [string]$SummonAnywhereFamilyChainProof.acceptance_criterion -eq 'summon_anywhere' -and
  [string]$SummonAnywhereFamilyChainProof.summon_next_smallest_truthful_gap -eq 'summon_anywhere_blockers' -and
  [string]$SummonAnywhereFamilyChainProof.next_smallest_truthful_gap -eq 'stage6_lens_completion_audit' -and
  [bool]$SummonAnywhereFamilyChainProof.family_chain_observed -and
  [bool]$SummonAnywhereFamilyChainProof.resident_host_family_handoff_observed -and
  [bool]$SummonAnywhereFamilyChainProof.final_summon_authority_handoff_observed -and
  [bool]$SummonAnywhereFamilyChainProof.all_summon_blocker_families_consumed -and
  [bool]$SummonAnywhereFamilyChainProof.handoff_aligned -and
  [bool]$SummonAnywhereFamilyChainProof.side_effects_denied -and
  [string]$SummonAnywhereFamilyChainProof.first_blocker_family -eq 'resident_host' -and
  $SummonAnywhereFamilyChainBlockedFamiliesAligned -and
  [string]$SummonAnywhereFamilyChainProofResidentHost.next_smallest_truthful_gap -eq 'resident_host_runtime_blocker_boundary' -and
  [string]$SummonAnywhereFamilyChainProofResidentHost.lifecycle_next_smallest_truthful_gap -eq 'resident_host_runtime_blocker_boundary' -and
  $SummonAnywhereFamilyChainProofResidentHostRuntimeBlockers -contains 'lens_host_runtime_not_implemented' -and
  $SummonAnywhereFamilyChainProofResidentHostSurfaceBlockers -contains 'tray_host_missing' -and
  $SummonAnywhereFamilyChainProofResidentHostSurfaceBlockers -contains 'overlay_window_missing' -and
  $SummonAnywhereFamilyChainProofResidentHostSurfaceBlockers -contains 'global_hotkey_binding_missing' -and
  $SummonAnywhereFamilyChainProofResidentHostSurfaceBlockers -contains 'summon_binding_missing' -and
  [string]$SummonAnywhereFamilyChainProofFinalAuthority.previous_summon_blocker_family -eq 'summon_binding' -and
  [string]$SummonAnywhereFamilyChainProofFinalAuthority.summon_authority_blocker_family -eq 'authority' -and
  [string]$SummonAnywhereFamilyChainProofFinalAuthority.next_summon_blocker_family -eq 'stage6_lens_completion_audit' -and
  [string]$SummonAnywhereFamilyChainProofFinalAuthority.next_smallest_truthful_gap -eq 'stage6_lens_completion_audit' -and
  [bool]$SummonAnywhereFamilyChainProofFinalAuthority.all_summon_blocker_families_consumed -and
  $SummonAnywhereFamilyChainProofFinalAuthorityBlockers -contains 'summon_authority_not_granted' -and
  [bool]$SummonAnywhereFamilyChainProofGovernance.diagnostic_only -and
  [bool]$SummonAnywhereFamilyChainProofGovernance.wraps_summon_anywhere_blockers_proof -and
  [bool]$SummonAnywhereFamilyChainProofGovernance.wraps_summon_resident_host_blocker_proof -and
  [bool]$SummonAnywhereFamilyChainProofGovernance.wraps_summon_authority_blocker_proof -and
  [bool]$SummonAnywhereFamilyChainProofGovernance.read_only_contract -and
  -not [bool]$SummonAnywhereFamilyChainProofGovernance.bounded_local_process_launch -and
  -not [bool]$SummonAnywhereFamilyChainProofGovernance.temporary_runtime_state_write -and
  -not [bool]$SummonAnywhereFamilyChainProofGovernance.product_execution_authority -and
  -not [bool]$SummonAnywhereFamilyChainProofGovernance.execution_authority -and
  -not [bool]$SummonAnywhereFamilyChainProofGovernance.approval_decision_authority -and
  -not [bool]$SummonAnywhereFamilyChainProofGovernance.local_process_launch_authority -and
  -not [bool]$SummonAnywhereFamilyChainProofGovernance.process_supervision_authority -and
  -not [bool]$SummonAnywhereFamilyChainProofGovernance.service_control_authority -and
  -not [bool]$SummonAnywhereFamilyChainProofGovernance.hotkey_registration_authority -and
  -not [bool]$SummonAnywhereFamilyChainProofGovernance.overlay_control_authority -and
  -not [bool]$SummonAnywhereFamilyChainProofGovernance.summon_authority -and
  -not [bool]$SummonAnywhereFamilyChainProofGovernance.memory_write -and
  -not [bool]$SummonAnywhereFamilyChainProofGovernance.receipt_write_authority -and
  -not [bool]$SummonAnywhereFamilyChainProofGovernance.resident_claim_authority -and
  -not [bool]$SummonAnywhereFamilyChainProofGovernance.mutation_authority_granted
)
$Stage6CompletionReviewed = (
  $ResidentRuntimeResidentClaimBoundaryObserved -and
  $PersistentSupervisionResidentClaimBoundaryObserved -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  $HostSupervisionAuthorityReadinessHandoffObserved -and
  $CommandPaletteShellBridgeObserved -and
  $CommandPaletteOsBindingObserved -and
  $OsBindingAuthorityRequestReadbackObserved -and
  $SummonAnywhereBlockersProofObserved -and
  $CheckpointSummonEnablementGateHandoffObserved -and
  $SummonAuthorityBlockerProofObserved -and
  $SummonAnywhereFamilyChainProofObserved
)
$NextSmallestTruthfulGap = if ($ReadyToClose) {
  'stage6_ledger_closure'
} elseif (-not $ResidentRuntimeResidentClaimBoundaryObserved -and $ResidentRuntimeOverlayWindowBoundaryObserved) {
  'resident_runtime_resident_claim_authority_boundary'
} elseif (-not $ResidentRuntimeOverlayWindowBoundaryObserved -and $ResidentRuntimeHotkeySummonBoundaryObserved) {
  'resident_runtime_overlay_window_authority_boundary'
} elseif (-not $ResidentRuntimeHotkeySummonBoundaryObserved -and $ResidentRuntimeTrayPresenceBoundaryObserved) {
  'resident_runtime_hotkey_summon_authority_boundary'
} elseif (-not $ResidentRuntimeTrayPresenceBoundaryObserved -and $ResidentRuntimeServiceControlBoundaryObserved) {
  'resident_runtime_tray_presence_authority_boundary'
} elseif (-not $ResidentRuntimeServiceControlBoundaryObserved -and $ResidentRuntimeProcessSupervisionBoundaryObserved) {
  'resident_runtime_service_control_authority_boundary'
} elseif (-not $ResidentRuntimeProcessSupervisionBoundaryObserved -and $ResidentRuntimeAuthorityBlockersProofObserved) {
  'resident_runtime_process_supervision_authority_boundary'
} elseif (-not $ResidentRuntimeAuthorityBlockersProofObserved -and $ResidentRuntimeGrantedBoundaryProofObserved) {
  'supervised_resident_runtime_process_service_tray_hotkey_overlay_authority'
} elseif (-not $ResidentRuntimeGrantedBoundaryProofObserved -and $ResidentRuntimeBoundaryObserved) {
  'supervised_resident_runtime_execution_boundary'
} elseif (
  $PersistentSupervisionEnablementDenialObserved -and
  -not $PersistentSupervisionEnablementExecutionDenialObserved
) {
  'persistent_supervision_enablement_execution_denial_boundary'
} elseif (
  $PersistentSupervisionEnablementDenialObserved -and
  $PersistentSupervisionEnablementExecutionDenialObserved -and
  $PersistentSupervisionEnablementDenialBlockers -contains 'persistent_supervision_enablement_authority_not_granted' -and
  -not $PersistentSupervisionEnablementAuthorityProofObserved
) {
  'persistent_supervision_enablement_authority_not_granted'
} elseif (
  $PersistentSupervisionEnablementDenialObserved -and
  $PersistentSupervisionEnablementExecutionDenialObserved -and
  $PersistentSupervisionResidentClaimBoundaryObserved -and
  $ProcessSupervisionBoundaryObserved -and
  -not $ResidentHostProcessSupervisionBlockerProofObserved
) {
  'resident_host_process_supervision_handoff'
} elseif (
  $PersistentSupervisionEnablementDenialObserved -and
  $PersistentSupervisionEnablementExecutionDenialObserved -and
  $PersistentSupervisionResidentClaimBoundaryObserved -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  -not $HostSupervisionAuthorityReadinessHandoffObserved
) {
  'resident_host_supervision_authority_readiness_handoff'
} elseif (
  $PersistentSupervisionEnablementDenialObserved -and
  $PersistentSupervisionEnablementExecutionDenialObserved -and
  $PersistentSupervisionResidentClaimBoundaryObserved -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  $HostSupervisionAuthorityReadinessHandoffObserved -and
  -not $CommandPaletteShellBridgeObserved
) {
  'command_palette_shell_bridge_readback'
} elseif (
  $PersistentSupervisionEnablementDenialObserved -and
  $PersistentSupervisionEnablementExecutionDenialObserved -and
  $PersistentSupervisionResidentClaimBoundaryObserved -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  $HostSupervisionAuthorityReadinessHandoffObserved -and
  $CommandPaletteShellBridgeObserved -and
  -not $CommandPaletteOsBindingObserved
) {
  'command_palette_os_binding_blocker_proof'
} elseif (
  $PersistentSupervisionEnablementDenialObserved -and
  $PersistentSupervisionEnablementExecutionDenialObserved -and
  $PersistentSupervisionResidentClaimBoundaryObserved -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  $HostSupervisionAuthorityReadinessHandoffObserved -and
  $CommandPaletteShellBridgeObserved -and
  $CommandPaletteOsBindingObserved -and
  -not $OsBindingAuthorityRequestReadbackObserved
) {
  'os_binding_authority_request_readback'
} elseif (
  $PersistentSupervisionEnablementDenialObserved -and
  $PersistentSupervisionEnablementExecutionDenialObserved -and
  $PersistentSupervisionResidentClaimBoundaryObserved -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  $HostSupervisionAuthorityReadinessHandoffObserved -and
  $CommandPaletteShellBridgeObserved -and
  $CommandPaletteOsBindingObserved -and
  $OsBindingAuthorityRequestReadbackObserved -and
  -not $SummonAnywhereBlockersProofObserved
) {
  'summon_anywhere_blockers_proof_readback'
} elseif (
  $PersistentSupervisionEnablementDenialObserved -and
  $PersistentSupervisionEnablementExecutionDenialObserved -and
  $PersistentSupervisionResidentClaimBoundaryObserved -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  $HostSupervisionAuthorityReadinessHandoffObserved -and
  $CommandPaletteShellBridgeObserved -and
  $CommandPaletteOsBindingObserved -and
  $OsBindingAuthorityRequestReadbackObserved -and
  $SummonAnywhereBlockersProofObserved -and
  -not $CheckpointSummonEnablementGateHandoffObserved
) {
  'checkpoint_summon_enablement_gate_handoff'
} elseif (
  $PersistentSupervisionEnablementDenialObserved -and
  $PersistentSupervisionEnablementExecutionDenialObserved -and
  $PersistentSupervisionResidentClaimBoundaryObserved -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  $HostSupervisionAuthorityReadinessHandoffObserved -and
  $CommandPaletteShellBridgeObserved -and
  $CommandPaletteOsBindingObserved -and
  $OsBindingAuthorityRequestReadbackObserved -and
  $SummonAnywhereBlockersProofObserved -and
  $CheckpointSummonEnablementGateHandoffObserved -and
  -not $SummonAuthorityBlockerProofObserved
) {
  'summon_authority_blocker_proof_readback'
} elseif (
  $PersistentSupervisionEnablementDenialObserved -and
  $PersistentSupervisionEnablementExecutionDenialObserved -and
  $PersistentSupervisionResidentClaimBoundaryObserved -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  $HostSupervisionAuthorityReadinessHandoffObserved -and
  $CommandPaletteShellBridgeObserved -and
  $CommandPaletteOsBindingObserved -and
  $OsBindingAuthorityRequestReadbackObserved -and
  $SummonAnywhereBlockersProofObserved -and
  $CheckpointSummonEnablementGateHandoffObserved -and
  $SummonAuthorityBlockerProofObserved -and
  -not $SummonAnywhereFamilyChainProofObserved
) {
  'summon_anywhere_family_chain_proof_readback'
} elseif (
  $PersistentSupervisionEnablementDenialObserved -and
  $PersistentSupervisionEnablementExecutionDenialObserved -and
  $PersistentSupervisionResidentClaimBoundaryObserved
) {
  $Stage6AcceptanceNextGap
} elseif (
  $PersistentSupervisionEnablementDenialObserved -and
  $PersistentSupervisionEnablementExecutionDenialObserved -and
  $PersistentSupervisionExecutionAuthorityProofObserved
) {
  'persistent_supervision_resident_claim_authority_boundary'
} elseif (
  $PersistentSupervisionEnablementDenialObserved -and
  $PersistentSupervisionEnablementExecutionDenialObserved -and
  $PersistentSupervisionEnablementAuthorityProofObserved
) {
  'persistent_supervision_execution_authority_or_resident_claim_boundary'
} elseif (
  $PersistentSupervisionPlanObserved -and
  $PersistentSupervisionPlanBlockers -contains 'persistent_supervision_disabled'
) {
  'persistent_supervision_authority_not_granted'
} elseif (
  $HostSupervisorOwnedSessionObserved -and
  $HostSupervisorOwnedSessionBlockers -contains 'resident_supervision_not_persistent'
) {
  'resident_supervision_not_persistent'
} elseif ($ProcessSupervisionBoundaryObserved -and $ProcessSupervisionBoundaryBlockers -contains 'resident_host_process_not_supervised') {
  'resident_host_process_not_supervised'
} elseif ($BlockedCriterionIds -contains 'helpful_not_noisy' -and $Blockers -contains 'resident_surface_runtime_not_supervised') {
  'resident_surface_runtime_not_supervised'
} elseif ($BlockedCriterionIds -contains 'helpful_not_noisy' -and $Blockers -contains 'resident_surface_runtime_missing') {
  'resident_surface_runtime_missing'
} elseif ($BlockedCriterionIds -contains 'helpful_not_noisy' -and $Blockers -contains 'resident_surface_missing') {
  'resident_surface_missing'
} elseif ($BlockedCriterionIds -contains 'summon_anywhere') {
  'summon_anywhere_blockers'
} elseif ($BlockedCriterionIds -contains 'system_resident_presence') {
  'system_resident_presence_blockers'
} elseif ($Stage6CompletionReviewed -and -not [string]::IsNullOrWhiteSpace($Stage6AcceptanceNextGap)) {
  $Stage6AcceptanceNextGap
} else {
  'review_stage6_checkpoint_blockers'
}

$Payload = [ordered]@{
  ok = $true
  kind = 'lens.stage6.completion_audit'
  status = if ($ReadyToClose) { 'ready_to_close' } else { 'blocked' }
  audit_status = 'complete'
  mode = $Mode
  stage = [string]$Checkpoint.stage
  stage_state = if ($ReadyToClose) { 'closure_ready' } else { 'active' }
  stage_claim = [string]$Checkpoint.stage_claim
  repo_root = $RepoRoot
  ready_to_close = $ReadyToClose
  can_close_stage6 = $ReadyToClose
  transition_allowed = $ReadyToClose
  closure_decision = if ($ReadyToClose) { 'stage6_ready_for_ledger_closure' } else { 'do_not_close_stage6' }
  next_stage = 'Stage 7 / Telemetry'
  child_proof_timeout_seconds = $ChildProofTimeoutSeconds
  child_proof_timeouts = [string[]]@($ChildProofTimeouts)
  child_proof_runs = @($ChildProofRuns)
  next_smallest_truthful_gap = $NextSmallestTruthfulGap
  next_smallest_truthful_gap_basis = if ($NextSmallestTruthfulGap -eq 'stage6_lens_completion_audit') {
    'The audit consumes the resident-runtime resident-claim boundary proof and the persistent-supervision resident-claim boundary proof: both final authority families are now read back as blocked and non-mutating, so the next bounded step is a Stage 6 closure audit/readiness review rather than Stage 7 transition.'
  } elseif ($NextSmallestTruthfulGap -eq 'summon_anywhere_blockers') {
    'The completion audit has consumed the final resident-runtime and persistent-supervision authority-family proofs, and the first resident-host runtime boundary is now read back as consumed. Stage 6 still cannot close because summon-anywhere is blocked by process supervision plus grouped tray, overlay, global hotkey, summon binding, and authority behavior.'
  } elseif ($NextSmallestTruthfulGap -eq 'summon_anywhere_family_chain_proof_readback') {
    'The audit must consume the summon-anywhere family-chain proof before treating the grouped resident-host, tray, overlay, hotkey, summon-binding, and authority blockers as one audited handoff.'
  } elseif ($NextSmallestTruthfulGap -eq 'checkpoint_summon_enablement_gate_handoff') {
    'The audit must consume the checkpoint summon-enable gate handoff before treating summon-anywhere blocker families as fully audited through the checkpoint surface.'
  } elseif ($NextSmallestTruthfulGap -eq 'helpful_not_noisy_blockers') {
    'The completion audit has consumed the final authority-family proofs. Stage 6 still cannot close because helpful-not-noisy Lens behavior is limited to foreground/readback proof and lacks supervised resident runtime.'
  } elseif ($NextSmallestTruthfulGap -eq 'system_resident_presence_blockers') {
    'The completion audit has consumed the final authority-family proofs. Stage 6 still cannot close because system-resident presence is blocked by host, process, service, tray, hotkey, overlay, and resident-claim gaps.'
  } elseif ($NextSmallestTruthfulGap -eq 'resident_runtime_resident_claim_authority_boundary') {
    'The audit consumes the resident-runtime overlay-window boundary proof: the fifth authority family is now read back as blocked and non-mutating, so the next bounded family proof is resident claim.'
  } elseif ($NextSmallestTruthfulGap -eq 'resident_runtime_overlay_window_authority_boundary') {
    'The audit consumes the resident-runtime hotkey-summon boundary proof: the fourth authority family is now read back as blocked and non-mutating, so the next bounded family proof is overlay window.'
  } elseif ($NextSmallestTruthfulGap -eq 'resident_runtime_hotkey_summon_authority_boundary') {
    'The audit consumes the resident-runtime tray-presence boundary proof: the third authority family is now read back as blocked and non-mutating, so the next bounded family proof is hotkey summon.'
  } elseif ($NextSmallestTruthfulGap -eq 'resident_runtime_tray_presence_authority_boundary') {
    'The audit consumes the resident-runtime service-control boundary proof: the second authority family is now read back as blocked and non-mutating, so the next bounded family proof is tray presence.'
  } elseif ($NextSmallestTruthfulGap -eq 'resident_runtime_service_control_authority_boundary') {
    'The audit consumes the resident-runtime process-supervision boundary proof: the first authority family is now read back as blocked and non-mutating, so the next bounded family proof is service control.'
  } elseif ($NextSmallestTruthfulGap -eq 'resident_runtime_process_supervision_authority_boundary') {
    'The audit consumes the resident runtime authority blocker split proof: the previous combined process/service/tray/hotkey/overlay/resident-claim handoff is now grouped into explicit authority families, with process supervision as the first bounded boundary to resolve.'
  } elseif ($NextSmallestTruthfulGap -eq 'supervised_resident_runtime_process_service_tray_hotkey_overlay_authority') {
    'The audit consumes the granted resident runtime boundary proof: an exact resident runtime execution-authority grant reaches execution and is still denied without launching, supervising, controlling service/tray/hotkey/overlay surfaces, writing memory, or claiming a resident runtime.'
  } elseif ($NextSmallestTruthfulGap -eq 'supervised_resident_runtime_execution_boundary') {
    'The audit observes the resident runtime grant/readback spine and the resident runtime execute boundary; it now blocks on supervised process, service, tray, hotkey, overlay, receipt, and resident-claim authorities without launching or claiming a resident runtime.'
  } elseif ($NextSmallestTruthfulGap -eq 'persistent_supervision_enablement_authority_not_granted') {
    'The audit now consumes the persistent-supervision enablement denial boundary and execution denial boundary; it shows enablement is blocked by explicit enablement, service-config write, execution, and resident-claim authority, not by missing proof readback.'
  } elseif ($NextSmallestTruthfulGap -eq 'persistent_supervision_execution_authority_or_resident_claim_boundary') {
    'The audit now consumes the persistent-supervision enablement authority proof: the bounded enablement authority grant is readable, while service-config write, persistent execution, memory, runtime launch, and resident-claim authority remain denied.'
  } elseif ($NextSmallestTruthfulGap -eq 'resident_host_process_supervision_handoff') {
    'The audit must consume the resident-host process supervision handoff proof before treating resident-host process supervision as an acceptance blocker instead of a missing audit readback.'
  } elseif ($NextSmallestTruthfulGap -eq 'resident_host_supervision_authority_readiness_handoff') {
    'The audit must consume the host supervision authority readiness handoff before treating exact approval-request review as an audited resident-host supervision blocker.'
  } elseif ($NextSmallestTruthfulGap -eq 'command_palette_shell_bridge_readback') {
    'The audit must consume the Lens command-palette shell bridge before treating OS-level command palette and summon-anywhere behavior as acceptance blockers instead of missing audit readback.'
  } elseif ($NextSmallestTruthfulGap -eq 'command_palette_os_binding_blocker_proof') {
    'The audit must consume the command-palette OS-binding blocker proof before treating palette binding, global hotkey binding, summon binding, tray presence, overlay window, and authority as grouped summon-anywhere blockers.'
  } elseif ($NextSmallestTruthfulGap -eq 'os_binding_authority_request_readback') {
    'The audit must consume the OS-binding authority request readback before treating authority review visibility as part of the Stage 6 summon-anywhere blocker evidence.'
  } elseif ($NextSmallestTruthfulGap -eq 'summon_anywhere_blockers_proof_readback') {
    'The audit must consume the direct summon-anywhere blocker proof before treating grouped resident host, tray, overlay, global hotkey, summon binding, and authority blockers as audited Stage 6 evidence.'
  } elseif ($NextSmallestTruthfulGap -eq 'summon_authority_blocker_proof_readback') {
    'The audit must consume the summon authority blocker proof before treating the full summon-anywhere blocker chain, including the final authority family, as audited Stage 6 evidence.'
  } elseif ($NextSmallestTruthfulGap -eq 'persistent_supervision_resident_claim_authority_boundary') {
    'The audit now consumes the persistent-supervision execution authority proof: the bounded execution grant is readable and reaches the execution route, so the next bounded family proof is resident-claim/runtime readiness.'
  } elseif ($NextSmallestTruthfulGap -eq 'persistent_supervision_enablement_execution_denial_boundary') {
    'The checkpoint must observe the persistent-supervision execution denial boundary before the completion audit can make an authority-gap read.'
  } elseif ($NextSmallestTruthfulGap -eq 'persistent_supervision_authority_not_granted') {
    'The audit now has a persistent-supervision plan proof; it shows the blocker is explicit process-supervision, restart, service-control, receipt-write, and resident-claim authority, not another bounded supervisor proof.'
  } elseif ($NextSmallestTruthfulGap -eq 'resident_supervision_not_persistent') {
    'The checkpoint observed one bounded supervisor-owned host session, so the next blocker is persistent resident supervision rather than another bounded supervision proof.'
  } elseif ($NextSmallestTruthfulGap -eq 'resident_host_process_not_supervised') {
    'Process-supervision authority boundary proof still reports the host process as not supervised.'
  } else {
    'Derived from the current Stage 6 checkpoint blocker ordering.'
  }
  checkpoint_next_smallest_truthful_gap = [string]$Checkpoint.next_smallest_truthful_gap
  stage6_completion_reviewed = $Stage6CompletionReviewed
  remaining_stage6_acceptance_blockers = [string[]]@($BlockedCriterionIds)
  summon_anywhere_blocker_groups = $SummonAnywhereBlockerGroups
  summon_anywhere_blocked_families = [string[]]@($SummonAnywhereBlockedFamilies)
  summon_anywhere_first_blocker_family = $SummonAnywhereFirstBlockerFamily
  summon_anywhere_first_blocker_family_handoff_observed = $SummonAnywhereBlockersProofFirstFamilyHandoffObserved
  summon_anywhere_first_blocker_family_handoff = $SummonAnywhereBlockersProofFirstFamilyHandoff
  summon_anywhere_first_blocker_family_runtime_boundary_observed = $ResidentHostRuntimeBoundaryProofObserved
  summon_anywhere_first_blocker_family_runtime_boundary_next_smallest_truthful_gap = [string]$ResidentHostRuntimeBoundaryProof.next_smallest_truthful_gap
  summon_anywhere_blocker_family_handoffs = @($SummonAnywhereBlockersProofFamilyHandoffs)
  checkpoint_summon_enablement_gate_handoff_observed = $CheckpointSummonEnablementGateHandoffObserved
  checkpoint_summon_enablement_gate_handoff = [ordered]@{
    status = [string]$CheckpointSummonEnablementGateHandoff.status
    ok = $CheckpointSummonEnablementGateHandoffObserved
    ready = [bool]$CheckpointSummonEnablementGateHandoff.ready
    summon_anywhere = [bool]$CheckpointSummonEnablementGateHandoff.summon_anywhere
    operator_surface_readback_ready = [bool]$CheckpointSummonEnablementGateHandoff.operator_surface_readback_ready
    handoff_observed = [bool]$CheckpointSummonEnablementGateHandoff.handoff_observed
    first_blocker_family = [string]$CheckpointSummonEnablementGateHandoff.first_blocker_family
    first_blocker_family_handoff = $CheckpointSummonEnablementGateFirstFamilyHandoff
    blocked_families = [string[]]@($CheckpointSummonEnablementGateHandoffFamilies)
    blocked_family_handoffs = @($CheckpointSummonEnablementGateFamilyHandoffs)
    next_smallest_truthful_gap = [string]$CheckpointSummonEnablementGateHandoff.next_smallest_truthful_gap
    evidence = [string[]]@($CheckpointSummonEnablementGateHandoffEvidence)
    blockers = [string[]]@($CheckpointSummonEnablementGateHandoffBlockers)
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    summon_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
  }
  summary = [ordered]@{
    criteria_total = [int]$Checkpoint.summary.criteria_total
    ready_total = [int]$Checkpoint.summary.ready_total
    blocked_total = [int]$Checkpoint.summary.blocked_total
    blocker_total = [int]$Checkpoint.summary.blocker_total
    ready_criteria = [string[]]@($ReadyCriteria | ForEach-Object { [string]$_.id })
    blocked_criteria = [string[]]@($BlockedCriteria | ForEach-Object { [string]$_.id })
  }
  ready_criteria = @($ReadyCriteria | ForEach-Object { New-CriterionSummary -Criterion $_ })
  blocked_criteria = @($BlockedCriteria | ForEach-Object { New-CriterionSummary -Criterion $_ })
  closure_blockers = [ordered]@{
    acceptance_criteria = [string[]]@($BlockedCriteria | ForEach-Object { [string]$_.id })
    resident_surface = [string[]]@(
      $Blockers | Where-Object { $_ -match 'resident_surface|resident_overlay' } | Sort-Object -Unique
    )
    summon = [string[]]@($Blockers | Where-Object { $_ -match 'summon|hotkey|global_hotkey' } | Sort-Object -Unique)
    command_palette = [string[]]@(
      $CommandPaletteShellBridgeBlockers | Where-Object { $_ -match 'command_palette|summon|hotkey|global_hotkey' } | Sort-Object -Unique
    )
    command_palette_os_binding = [string[]]@(
      @(
        $CommandPaletteOsBindingPaletteBlockers
        $CommandPaletteOsBindingGlobalHotkeyBlockers
        $CommandPaletteOsBindingSummonBlockers
        $CommandPaletteOsBindingTrayBlockers
        $CommandPaletteOsBindingOverlayBlockers
        $CommandPaletteOsBindingAuthorityBlockers
      ) | Where-Object { $_ -match 'command_palette|summon|hotkey|global_hotkey|tray|overlay|authority|process_launch' } | Sort-Object -Unique
    )
    tray = [string[]]@($Blockers | Where-Object { $_ -match 'tray' } | Sort-Object -Unique)
    overlay = [string[]]@($Blockers | Where-Object { $_ -match 'overlay|window' } | Sort-Object -Unique)
    host_supervision = [string[]]@(
      $Blockers | Where-Object { $_ -match 'supervision|restart|service_' } | Sort-Object -Unique
    )
    host_supervisor_readback = [string[]]@(
      $HostSupervisorReadbackBlockers | Where-Object { $_ -match 'host_supervisor_readback' } | Sort-Object -Unique
    )
    process_supervision = [string[]]@(
      $ProcessSupervisionBoundaryBlockers | Where-Object {
        $_ -match 'process_supervision|process_restart|resident_host_process|resident_supervision'
      } | Sort-Object -Unique
    )
    resident_host_process_supervision_handoff = [string[]]@(
      $ResidentHostProcessSupervisionBlockerProofBlockers | Where-Object {
        $_ -match 'process_supervision|process_restart|resident_host_process|service_'
      } | Sort-Object -Unique
    )
    host_supervision_authority_readiness_handoff = [string[]]@(
      $HostSupervisionAuthorityReadinessBlockedRequirements | Where-Object {
        $_ -match 'approval|authority|supervision'
      } | Sort-Object -Unique
    )
    service_activation = [string[]]@(
      $ProcessSupervisionBoundaryBlockers | Where-Object { $_ -match 'service_' } | Sort-Object -Unique
    )
    persistent_supervision = [string[]]@(
      $PersistentSupervisionPlanBlockers | Where-Object { $_ -match 'persistent_supervision|process_supervision|process_restart|service_|receipt_write|resident_claim' } | Sort-Object -Unique
    )
    persistent_supervision_enablement = [string[]]@(
      $PersistentSupervisionEnablementDenialBlockers | Where-Object { $_ -match 'persistent_supervision|service_config|authority|execution|resident_claim|host_supervision' } | Sort-Object -Unique
    )
    persistent_supervision_enablement_execution = [string[]]@(
      $PersistentSupervisionEnablementExecutionDenialBlockers | Where-Object { $_ -match 'persistent_supervision|service_config|authority|execution|resident_claim|approval_id' } | Sort-Object -Unique
    )
    persistent_supervision_enablement_authority_proof = [string[]]@(
      $PersistentSupervisionEnablementAuthorityProofBlockers | Where-Object { $_ -match 'persistent_supervision|service_config|authority|execution|resident_claim|process_supervision' } | Sort-Object -Unique
    )
    persistent_supervision_execution_authority_proof = [string[]]@(
      $PersistentSupervisionExecutionAuthorityProofBlockers | Where-Object { $_ -match 'persistent_supervision|service_config|authority|execution|resident_claim|process_supervision|receipt_write' } | Sort-Object -Unique
    )
    persistent_supervision_resident_claim_boundary = [string[]]@(
      $PersistentSupervisionResidentClaimBoundaryBlockers | Where-Object { $_ -match 'persistent_supervision|service_config|authority|execution|resident_claim|process_supervision|receipt_write' } | Sort-Object -Unique
    )
    resident_runtime = [string[]]@(
      @(
        if ($ResidentRuntimeGrantedBoundaryProofObserved) {
          $ResidentRuntimeGrantedBoundaryProofBlockers
        } else {
          $ResidentRuntimeBoundaryBlockers
        }
      ) | Where-Object { $_ -match 'resident_runtime|process_supervision|process_restart|service_|tray|hotkey|overlay|resident_claim|receipt_write|local_process_launch' } | Sort-Object -Unique
    )
    resident_runtime_authority_families = [string[]]@($ResidentRuntimeAuthorityBlockerFamilies)
    resident_runtime_process_supervision = [string[]]@(
      ConvertTo-StringArray -Value $ResidentRuntimeAuthorityBlockerGroups.process_supervision.blockers
    )
    resident_runtime_process_supervision_boundary = [string[]]@($ResidentRuntimeProcessSupervisionBoundaryBlockers)
    resident_runtime_service_control = [string[]]@(
      ConvertTo-StringArray -Value $ResidentRuntimeAuthorityBlockerGroups.service_control.blockers
    )
    resident_runtime_service_control_boundary = [string[]]@($ResidentRuntimeServiceControlBoundaryBlockers)
    resident_runtime_tray_presence = [string[]]@(
      ConvertTo-StringArray -Value $ResidentRuntimeAuthorityBlockerGroups.tray_presence.blockers
    )
    resident_runtime_tray_presence_boundary = [string[]]@($ResidentRuntimeTrayPresenceBoundaryBlockers)
    resident_runtime_hotkey_summon = [string[]]@(
      ConvertTo-StringArray -Value $ResidentRuntimeAuthorityBlockerGroups.hotkey_summon.blockers
    )
    resident_runtime_hotkey_summon_boundary = [string[]]@($ResidentRuntimeHotkeySummonBoundaryBlockers)
    resident_runtime_overlay_window = [string[]]@(
      ConvertTo-StringArray -Value $ResidentRuntimeAuthorityBlockerGroups.overlay_window.blockers
    )
    resident_runtime_overlay_window_boundary = [string[]]@($ResidentRuntimeOverlayWindowBoundaryBlockers)
    resident_runtime_resident_claim = [string[]]@(
      ConvertTo-StringArray -Value $ResidentRuntimeAuthorityBlockerGroups.resident_claim.blockers
    )
    resident_runtime_resident_claim_boundary = [string[]]@($ResidentRuntimeResidentClaimBoundaryBlockers)
    authority = [string[]]@(
      $Blockers | Where-Object { $_ -match 'authority|not_granted|not_authorized' } | Sort-Object -Unique
    )
  }
  host_supervisor_readback = [ordered]@{
    status = if ($HostSupervisorReadbackObserved) { [string]$HostSupervisorReadback.status } else { 'missing_or_failed' }
    ok = $HostSupervisorReadbackObserved
    readback_ready = [bool]$HostSupervisorReadback.readback_ready
    runtime_state_path = [string]$HostSupervisorReadback.runtime_state_path
    state_exists = [bool]$HostSupervisorReadback.state_exists
    state_status = [string]$HostSupervisorReadback.state_status
    mode = [string]$HostSupervisorReadback.mode
    observed_pid = $HostSupervisorReadback.observed_pid
    observed_state = [string]$HostSupervisorReadback.observed_state
    updated_at = [string]$HostSupervisorReadback.updated_at
    state_age_seconds = $HostSupervisorReadback.state_age_seconds
    freshness_window_seconds = [int]$HostSupervisorReadback.freshness_window_seconds
    freshness_status = [string]$HostSupervisorReadback.freshness_status
    state_stale = [bool]$HostSupervisorReadback.state_stale
    fresh_readback = [bool]$HostSupervisorReadback.fresh_readback
    bounded_supervisor_observed = [bool]$HostSupervisorReadback.bounded_supervisor_observed
    supervised_session_completed = [bool]$HostSupervisorReadback.supervised_session_completed
    fresh_bounded_supervisor_observed = [bool]$HostSupervisorReadback.fresh_bounded_supervisor_observed
    fresh_supervised_session_completed = [bool]$HostSupervisorReadback.fresh_supervised_session_completed
    resident_supervised_runtime = $false
    resident_claim_allowed = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_control_authority = $false
    resident_claim_authority = $false
    blockers = [string[]]@($HostSupervisorReadbackBlockers)
  }
  resident_runtime_execution_boundary = [ordered]@{
    status = if ($ResidentRuntimeBoundaryObserved) { [string]$ResidentRuntimeBoundary.status } else { 'missing_or_failed' }
    ok = $ResidentRuntimeBoundaryObserved
    evidence = [string[]]@(ConvertTo-StringArray -Value $ResidentRuntimeBoundary.evidence)
    applied = [bool]$ResidentRuntimeBoundary.applied
    executed = [bool]$ResidentRuntimeBoundary.executed
    resident_runtime_execution_authority = [bool]$ResidentRuntimeBoundary.resident_runtime_execution_authority
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    blockers = [string[]]@($ResidentRuntimeBoundaryBlockers)
  }
  resident_runtime_granted_boundary_proof = [ordered]@{
    status = if ($ResidentRuntimeGrantedBoundaryProofObserved) { [string]$ResidentRuntimeGrantedBoundaryProof.status } else { 'missing_or_failed' }
    ok = $ResidentRuntimeGrantedBoundaryProofObserved
    exit_code = [int]$ResidentRuntimeGrantedBoundaryProof.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $ResidentRuntimeGrantedBoundaryProof.evidence)
    resident_runtime_execution_authority = [bool]$ResidentRuntimeGrantedBoundaryProof.resident_runtime_execution_authority
    runtime_ready = [bool]$ResidentRuntimeGrantedBoundaryProof.runtime_ready
    resident_claim_allowed = [bool]$ResidentRuntimeGrantedBoundaryProof.resident_claim_allowed
    applied = [bool]$ResidentRuntimeGrantedBoundaryProof.applied
    executed = [bool]$ResidentRuntimeGrantedBoundaryProof.executed
    would_launch_process = [bool]$ResidentRuntimeGrantedBoundaryProof.would_launch_process
    would_supervise_process = [bool]$ResidentRuntimeGrantedBoundaryProof.would_supervise_process
    would_restart_process = [bool]$ResidentRuntimeGrantedBoundaryProof.would_restart_process
    would_install_service = [bool]$ResidentRuntimeGrantedBoundaryProof.would_install_service
    would_start_service = [bool]$ResidentRuntimeGrantedBoundaryProof.would_start_service
    would_register_tray = [bool]$ResidentRuntimeGrantedBoundaryProof.would_register_tray
    would_register_hotkey = [bool]$ResidentRuntimeGrantedBoundaryProof.would_register_hotkey
    would_open_overlay = [bool]$ResidentRuntimeGrantedBoundaryProof.would_open_overlay
    would_write_memory = [bool]$ResidentRuntimeGrantedBoundaryProof.would_write_memory
    would_claim_resident = [bool]$ResidentRuntimeGrantedBoundaryProof.would_claim_resident
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    blockers = [string[]]@($ResidentRuntimeGrantedBoundaryProofBlockers)
    next_smallest_truthful_gap = [string]$ResidentRuntimeGrantedBoundaryProof.next_smallest_truthful_gap
  }
  resident_runtime_authority_blockers_proof = [ordered]@{
    status = if ($ResidentRuntimeAuthorityBlockersProofObserved) { [string]$ResidentRuntimeAuthorityBlockersProof.status } else { 'missing_or_failed' }
    ok = $ResidentRuntimeAuthorityBlockersProofObserved
    exit_code = [int]$ResidentRuntimeAuthorityBlockersProof.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $ResidentRuntimeAuthorityBlockersProof.evidence)
    next_smallest_truthful_gap = [string]$ResidentRuntimeAuthorityBlockersProof.next_smallest_truthful_gap
    remaining_authority_families = [string[]]@($ResidentRuntimeAuthorityBlockerFamilies)
    authority_blocker_groups = $ResidentRuntimeAuthorityBlockerGroups
    summary = $ResidentRuntimeAuthorityBlockersSummary
    diagnostic_only = [bool]$ResidentRuntimeAuthorityBlockersProof.governance.diagnostic_only
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    tray_registration_authority = $false
    hotkey_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
  }
  resident_runtime_process_supervision_boundary_proof = [ordered]@{
    status = if ($ResidentRuntimeProcessSupervisionBoundaryObserved) { [string]$ResidentRuntimeProcessSupervisionBoundaryProof.status } else { 'missing_or_failed' }
    ok = $ResidentRuntimeProcessSupervisionBoundaryObserved
    exit_code = [int]$ResidentRuntimeProcessSupervisionBoundaryProof.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $ResidentRuntimeProcessSupervisionBoundaryProof.evidence)
    authority_family = [string]$ResidentRuntimeProcessSupervisionBoundaryProof.authority_family
    next_authority_family = [string]$ResidentRuntimeProcessSupervisionBoundaryProof.next_authority_family
    process_supervision_boundary_observed = [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.process_supervision_boundary_observed
    authority_blockers_proof_observed = [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.authority_blockers_proof_observed
    side_effects_denied = [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.side_effects_denied
    first_authority_family_consumed = [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.first_authority_family_consumed
    process_supervision = $ResidentRuntimeProcessSupervisionBoundaryProof.process_supervision
    resident_runtime_execution_authority = [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.resident_runtime_execution_authority
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_control_authority = $false
    resident_claim_authority = $false
    would_launch_process = [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.would_launch_process
    would_supervise_process = [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.would_supervise_process
    would_restart_process = [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.would_restart_process
    would_start_service = [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.would_start_service
    would_register_tray = [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.would_register_tray
    would_register_hotkey = [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.would_register_hotkey
    would_open_overlay = [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.would_open_overlay
    would_write_memory = [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.would_write_memory
    would_claim_resident = [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.would_claim_resident
    blockers = [string[]]@($ResidentRuntimeProcessSupervisionBoundaryBlockers)
    next_smallest_truthful_gap = [string]$ResidentRuntimeProcessSupervisionBoundaryProof.next_smallest_truthful_gap
  }
  resident_runtime_service_control_boundary_proof = [ordered]@{
    status = if ($ResidentRuntimeServiceControlBoundaryObserved) { [string]$ResidentRuntimeServiceControlBoundaryProof.status } else { 'missing_or_failed' }
    ok = $ResidentRuntimeServiceControlBoundaryObserved
    exit_code = [int]$ResidentRuntimeServiceControlBoundaryProof.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $ResidentRuntimeServiceControlBoundaryProof.evidence)
    authority_family = [string]$ResidentRuntimeServiceControlBoundaryProof.authority_family
    previous_authority_family = [string]$ResidentRuntimeServiceControlBoundaryProof.previous_authority_family
    next_authority_family = [string]$ResidentRuntimeServiceControlBoundaryProof.next_authority_family
    service_control_boundary_observed = [bool]$ResidentRuntimeServiceControlBoundaryProof.service_control_boundary_observed
    previous_process_supervision_family_observed = [bool]$ResidentRuntimeServiceControlBoundaryProof.previous_process_supervision_family_observed
    authority_blockers_proof_observed = [bool]$ResidentRuntimeServiceControlBoundaryProof.authority_blockers_proof_observed
    side_effects_denied = [bool]$ResidentRuntimeServiceControlBoundaryProof.side_effects_denied
    second_authority_family_consumed = [bool]$ResidentRuntimeServiceControlBoundaryProof.second_authority_family_consumed
    service_control = $ResidentRuntimeServiceControlBoundaryProof.service_control
    resident_runtime_execution_authority = [bool]$ResidentRuntimeServiceControlBoundaryProof.resident_runtime_execution_authority
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    resident_claim_authority = $false
    would_launch_process = [bool]$ResidentRuntimeServiceControlBoundaryProof.would_launch_process
    would_supervise_process = [bool]$ResidentRuntimeServiceControlBoundaryProof.would_supervise_process
    would_restart_process = [bool]$ResidentRuntimeServiceControlBoundaryProof.would_restart_process
    would_install_service = [bool]$ResidentRuntimeServiceControlBoundaryProof.would_install_service
    would_start_service = [bool]$ResidentRuntimeServiceControlBoundaryProof.would_start_service
    would_register_tray = [bool]$ResidentRuntimeServiceControlBoundaryProof.would_register_tray
    would_register_hotkey = [bool]$ResidentRuntimeServiceControlBoundaryProof.would_register_hotkey
    would_open_overlay = [bool]$ResidentRuntimeServiceControlBoundaryProof.would_open_overlay
    would_write_memory = [bool]$ResidentRuntimeServiceControlBoundaryProof.would_write_memory
    would_claim_resident = [bool]$ResidentRuntimeServiceControlBoundaryProof.would_claim_resident
    blockers = [string[]]@($ResidentRuntimeServiceControlBoundaryBlockers)
    remaining_authority_families_after_this_boundary = [string[]]@(ConvertTo-StringArray -Value $ResidentRuntimeServiceControlBoundaryProof.remaining_authority_families_after_this_boundary)
    next_smallest_truthful_gap = [string]$ResidentRuntimeServiceControlBoundaryProof.next_smallest_truthful_gap
  }
  resident_runtime_tray_presence_boundary_proof = [ordered]@{
    status = if ($ResidentRuntimeTrayPresenceBoundaryObserved) { [string]$ResidentRuntimeTrayPresenceBoundaryProof.status } else { 'missing_or_failed' }
    ok = $ResidentRuntimeTrayPresenceBoundaryObserved
    exit_code = [int]$ResidentRuntimeTrayPresenceBoundaryProof.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $ResidentRuntimeTrayPresenceBoundaryProof.evidence)
    authority_family = [string]$ResidentRuntimeTrayPresenceBoundaryProof.authority_family
    previous_authority_family = [string]$ResidentRuntimeTrayPresenceBoundaryProof.previous_authority_family
    next_authority_family = [string]$ResidentRuntimeTrayPresenceBoundaryProof.next_authority_family
    tray_presence_boundary_observed = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.tray_presence_boundary_observed
    previous_service_control_family_observed = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.previous_service_control_family_observed
    tray_preflight_observed = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.tray_preflight_observed
    authority_blockers_proof_observed = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.authority_blockers_proof_observed
    side_effects_denied = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.side_effects_denied
    third_authority_family_consumed = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.third_authority_family_consumed
    tray_presence = $ResidentRuntimeTrayPresenceBoundaryProof.tray_presence
    tray_preflight = $ResidentRuntimeTrayPresenceBoundaryProof.tray_preflight
    resident_runtime_execution_authority = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.resident_runtime_execution_authority
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    tray_registration_authority = $false
    tray_icon_authority = $false
    notification_authority = $false
    resident_claim_authority = $false
    would_launch_process = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_launch_process
    would_supervise_process = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_supervise_process
    would_restart_process = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_restart_process
    would_install_service = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_install_service
    would_start_service = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_start_service
    would_register_tray = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_register_tray
    would_register_hotkey = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_register_hotkey
    would_open_overlay = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_open_overlay
    would_write_memory = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_write_memory
    would_claim_resident = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.would_claim_resident
    blockers = [string[]]@($ResidentRuntimeTrayPresenceBoundaryBlockers)
    remaining_authority_families_after_this_boundary = [string[]]@(ConvertTo-StringArray -Value $ResidentRuntimeTrayPresenceBoundaryProof.remaining_authority_families_after_this_boundary)
    next_smallest_truthful_gap = [string]$ResidentRuntimeTrayPresenceBoundaryProof.next_smallest_truthful_gap
  }
  resident_runtime_hotkey_summon_boundary_proof = [ordered]@{
    status = if ($ResidentRuntimeHotkeySummonBoundaryObserved) { [string]$ResidentRuntimeHotkeySummonBoundaryProof.status } else { 'missing_or_failed' }
    ok = $ResidentRuntimeHotkeySummonBoundaryObserved
    exit_code = [int]$ResidentRuntimeHotkeySummonBoundaryProof.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $ResidentRuntimeHotkeySummonBoundaryProof.evidence)
    authority_family = [string]$ResidentRuntimeHotkeySummonBoundaryProof.authority_family
    previous_authority_family = [string]$ResidentRuntimeHotkeySummonBoundaryProof.previous_authority_family
    next_authority_family = [string]$ResidentRuntimeHotkeySummonBoundaryProof.next_authority_family
    hotkey_summon_boundary_observed = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.hotkey_summon_boundary_observed
    previous_tray_presence_family_observed = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.previous_tray_presence_family_observed
    summon_preflight_observed = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.summon_preflight_observed
    authority_blockers_proof_observed = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.authority_blockers_proof_observed
    side_effects_denied = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.side_effects_denied
    fourth_authority_family_consumed = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.fourth_authority_family_consumed
    hotkey_summon = $ResidentRuntimeHotkeySummonBoundaryProof.hotkey_summon
    summon_preflight = $ResidentRuntimeHotkeySummonBoundaryProof.summon_preflight
    resident_runtime_execution_authority = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.resident_runtime_execution_authority
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    tray_registration_authority = $false
    tray_icon_authority = $false
    notification_authority = $false
    summon_authority = $false
    hotkey_registration_authority = $false
    overlay_control_authority = $false
    resident_claim_authority = $false
    would_launch_process = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_launch_process
    would_supervise_process = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_supervise_process
    would_restart_process = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_restart_process
    would_install_service = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_install_service
    would_start_service = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_start_service
    would_register_tray = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_register_tray
    would_register_hotkey = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_register_hotkey
    would_open_overlay = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_open_overlay
    would_write_memory = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_write_memory
    would_claim_resident = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.would_claim_resident
    blockers = [string[]]@($ResidentRuntimeHotkeySummonBoundaryBlockers)
    remaining_authority_families_after_this_boundary = [string[]]@(ConvertTo-StringArray -Value $ResidentRuntimeHotkeySummonBoundaryProof.remaining_authority_families_after_this_boundary)
    next_smallest_truthful_gap = [string]$ResidentRuntimeHotkeySummonBoundaryProof.next_smallest_truthful_gap
  }
  resident_runtime_overlay_window_boundary_proof = [ordered]@{
    status = if ($ResidentRuntimeOverlayWindowBoundaryObserved) { [string]$ResidentRuntimeOverlayWindowBoundaryProof.status } else { 'missing_or_failed' }
    ok = $ResidentRuntimeOverlayWindowBoundaryObserved
    exit_code = [int]$ResidentRuntimeOverlayWindowBoundaryProof.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $ResidentRuntimeOverlayWindowBoundaryProof.evidence)
    authority_family = [string]$ResidentRuntimeOverlayWindowBoundaryProof.authority_family
    previous_authority_family = [string]$ResidentRuntimeOverlayWindowBoundaryProof.previous_authority_family
    next_authority_family = [string]$ResidentRuntimeOverlayWindowBoundaryProof.next_authority_family
    overlay_window_boundary_observed = [bool]$ResidentRuntimeOverlayWindowBoundaryProof.overlay_window_boundary_observed
    previous_hotkey_summon_family_observed = [bool]$ResidentRuntimeOverlayWindowBoundaryProof.previous_hotkey_summon_family_observed
    overlay_preflight_observed = [bool]$ResidentRuntimeOverlayWindowBoundaryProof.overlay_preflight_observed
    authority_blockers_proof_observed = [bool]$ResidentRuntimeOverlayWindowBoundaryProof.authority_blockers_proof_observed
    side_effects_denied = [bool]$ResidentRuntimeOverlayWindowBoundaryProof.side_effects_denied
    fifth_authority_family_consumed = [bool]$ResidentRuntimeOverlayWindowBoundaryProof.fifth_authority_family_consumed
    overlay_window = $ResidentRuntimeOverlayWindowBoundaryProof.overlay_window
    overlay_preflight = $ResidentRuntimeOverlayWindowBoundaryProof.overlay_preflight
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    tray_registration_authority = $false
    tray_icon_authority = $false
    notification_authority = $false
    summon_authority = $false
    hotkey_registration_authority = $false
    overlay_control_authority = $false
    window_management_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    resident_claim_authority = $false
    would_launch_process = [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_launch_process
    would_supervise_process = [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_supervise_process
    would_restart_process = [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_restart_process
    would_install_service = [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_install_service
    would_start_service = [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_start_service
    would_register_tray = [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_register_tray
    would_register_hotkey = [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_register_hotkey
    would_open_overlay = [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_open_overlay
    would_write_memory = [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_write_memory
    would_claim_resident = [bool]$ResidentRuntimeOverlayWindowBoundaryProof.would_claim_resident
    blockers = [string[]]@($ResidentRuntimeOverlayWindowBoundaryBlockers)
    remaining_authority_families_after_this_boundary = [string[]]@(ConvertTo-StringArray -Value $ResidentRuntimeOverlayWindowBoundaryProof.remaining_authority_families_after_this_boundary)
    next_smallest_truthful_gap = [string]$ResidentRuntimeOverlayWindowBoundaryProof.next_smallest_truthful_gap
  }
  resident_runtime_resident_claim_boundary_proof = [ordered]@{
    status = if ($ResidentRuntimeResidentClaimBoundaryObserved) { [string]$ResidentRuntimeResidentClaimBoundaryProof.status } else { 'missing_or_failed' }
    ok = $ResidentRuntimeResidentClaimBoundaryObserved
    exit_code = [int]$ResidentRuntimeResidentClaimBoundaryProof.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $ResidentRuntimeResidentClaimBoundaryProof.evidence)
    authority_family = [string]$ResidentRuntimeResidentClaimBoundaryProof.authority_family
    previous_authority_family = [string]$ResidentRuntimeResidentClaimBoundaryProof.previous_authority_family
    next_authority_family = [string]$ResidentRuntimeResidentClaimBoundaryProof.next_authority_family
    resident_claim_boundary_observed = [bool]$ResidentRuntimeResidentClaimBoundaryProof.resident_claim_boundary_observed
    previous_overlay_window_family_observed = [bool]$ResidentRuntimeResidentClaimBoundaryProof.previous_overlay_window_family_observed
    authority_blockers_proof_observed = [bool]$ResidentRuntimeResidentClaimBoundaryProof.authority_blockers_proof_observed
    side_effects_denied = [bool]$ResidentRuntimeResidentClaimBoundaryProof.side_effects_denied
    sixth_authority_family_consumed = [bool]$ResidentRuntimeResidentClaimBoundaryProof.sixth_authority_family_consumed
    resident_claim = $ResidentRuntimeResidentClaimBoundaryProof.resident_claim
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    tray_registration_authority = $false
    tray_icon_authority = $false
    notification_authority = $false
    summon_authority = $false
    hotkey_registration_authority = $false
    overlay_control_authority = $false
    window_management_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    resident_claim_authority = $false
    would_launch_process = [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_launch_process
    would_supervise_process = [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_supervise_process
    would_restart_process = [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_restart_process
    would_install_service = [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_install_service
    would_start_service = [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_start_service
    would_register_tray = [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_register_tray
    would_register_hotkey = [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_register_hotkey
    would_open_overlay = [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_open_overlay
    would_write_memory = [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_write_memory
    would_claim_resident = [bool]$ResidentRuntimeResidentClaimBoundaryProof.would_claim_resident
    blockers = [string[]]@($ResidentRuntimeResidentClaimBoundaryBlockers)
    remaining_authority_families_after_this_boundary = [string[]]@(ConvertTo-StringArray -Value $ResidentRuntimeResidentClaimBoundaryProof.remaining_authority_families_after_this_boundary)
    next_smallest_truthful_gap = [string]$ResidentRuntimeResidentClaimBoundaryProof.next_smallest_truthful_gap
  }
  command_palette_shell_bridge = [ordered]@{
    status = if ($CommandPaletteShellBridgeObserved) { [string]$CommandPaletteShellBridge.status } else { 'missing_or_failed' }
    ok = $CommandPaletteShellBridgeObserved
    exit_code = [int]$CommandPaletteShellBridge.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $CommandPaletteShellBridge.evidence)
    readback_ready = [bool]$CommandPaletteShellBridge.readback_ready
    os_level_command_palette = [bool]$CommandPaletteShellBridge.os_level_command_palette
    summon_anywhere = [bool]$CommandPaletteShellBridge.summon_anywhere
    availability = [string]$CommandPaletteShellBridge.availability
    route = [string]$CommandPaletteShellBridge.route
    command_total = [int]$CommandPaletteShellBridge.command_total
    blockers = [string[]]@($CommandPaletteShellBridgeBlockers)
    next_smallest_truthful_gap = [string]$CommandPaletteShellBridge.next_smallest_truthful_gap
    governance = [ordered]@{
      read_only_contract = [bool]$CommandPaletteShellBridgeGovernance.read_only_contract
      opens_palette = [bool]$CommandPaletteShellBridgeGovernance.opens_palette
      execution_authority = $false
      approval_decision_authority = $false
      memory_write = $false
      overlay_control_authority = $false
      summon_authority = $false
      hotkey_registration_authority = $false
      tray_registration_authority = $false
      local_process_launch_authority = $false
      mutation_authority_granted = $false
    }
  }
  command_palette_os_binding_blockers_proof = [ordered]@{
    status = if ($CommandPaletteOsBindingObserved) { [string]$CommandPaletteOsBindingProof.status } else { 'missing_or_failed' }
    ok = $CommandPaletteOsBindingObserved
    exit_code = [int]$CommandPaletteOsBindingProof.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $CommandPaletteOsBindingProof.evidence)
    acceptance_criterion = [string]$CommandPaletteOsBindingProof.acceptance_criterion
    os_level_command_palette_binding_observed = [bool]$CommandPaletteOsBindingProof.os_level_command_palette_binding_observed
    summon_preflight_observed = [bool]$CommandPaletteOsBindingProof.summon_preflight_observed
    tray_preflight_observed = [bool]$CommandPaletteOsBindingProof.tray_preflight_observed
    overlay_preflight_observed = [bool]$CommandPaletteOsBindingProof.overlay_preflight_observed
    os_binding_candidate_observed = $CommandPaletteOsBindingCandidateObserved
    side_effects_denied = [bool]$CommandPaletteOsBindingProof.side_effects_denied
    blocked_families = [string[]]@($CommandPaletteOsBindingFamilies)
    first_blocker_family = [string]$CommandPaletteOsBindingProof.first_blocker_family
    next_smallest_truthful_gap = [string]$CommandPaletteOsBindingProof.next_smallest_truthful_gap
    blocker_groups = [ordered]@{
      palette_binding = [string[]]@($CommandPaletteOsBindingPaletteBlockers)
      global_hotkey_binding = [string[]]@($CommandPaletteOsBindingGlobalHotkeyBlockers)
      summon_binding = [string[]]@($CommandPaletteOsBindingSummonBlockers)
      tray_presence = [string[]]@($CommandPaletteOsBindingTrayBlockers)
      overlay_window = [string[]]@($CommandPaletteOsBindingOverlayBlockers)
      authority = [string[]]@($CommandPaletteOsBindingAuthorityBlockers)
    }
    command_palette = $CommandPaletteOsBindingProof.command_palette
    os_binding_candidate = $CommandPaletteOsBindingCandidate
    summon_preflight = $CommandPaletteOsBindingProof.summon_preflight
    tray_preflight = $CommandPaletteOsBindingProof.tray_preflight
    overlay_preflight = $CommandPaletteOsBindingProof.overlay_preflight
    governance = [ordered]@{
      diagnostic_only = [bool]$CommandPaletteOsBindingGovernance.diagnostic_only
      wraps_command_palette_shell_bridge = [bool]$CommandPaletteOsBindingGovernance.wraps_command_palette_shell_bridge
      wraps_summon_preflight = [bool]$CommandPaletteOsBindingGovernance.wraps_summon_preflight
      wraps_tray_preflight = [bool]$CommandPaletteOsBindingGovernance.wraps_tray_preflight
      wraps_overlay_preflight = [bool]$CommandPaletteOsBindingGovernance.wraps_overlay_preflight
      os_binding_candidate_boundary_readback = [bool]$CommandPaletteOsBindingGovernance.os_binding_candidate_boundary_readback
      read_only_contract = [bool]$CommandPaletteOsBindingGovernance.read_only_contract
      opens_palette = $false
      execution_authority = $false
      approval_decision_authority = $false
      memory_write = $false
      overlay_control_authority = $false
      window_management_authority = $false
      summon_authority = $false
      hotkey_registration_authority = $false
      tray_registration_authority = $false
      local_process_launch_authority = $false
      service_control_authority = $false
      capture_authority = $false
      new_sensing_authority = $false
      mutation_authority_granted = $false
    }
  }
  os_binding_authority_request_readback = [ordered]@{
    status = if ($OsBindingAuthorityRequestReadbackObserved) { [string]$OsBindingAuthorityRequestReadback.status } else { 'missing_or_failed' }
    ok = $OsBindingAuthorityRequestReadbackObserved
    evidence = [string[]]@(ConvertTo-StringArray -Value $OsBindingAuthorityRequestReadback.evidence)
    kind = [string]$OsBindingAuthorityRequestReadback.kind
    route = [string]$OsBindingAuthorityRequestReadback.route
    authority_route = [string]$OsBindingAuthorityRequestReadback.authority_route
    request_route = [string]$OsBindingAuthorityRequestReadback.request_route
    readiness_route = [string]$OsBindingAuthorityRequestReadback.readiness_route
    plan_route = [string]$OsBindingAuthorityRequestReadback.plan_route
    stage6_criterion_status = [string]$OsBindingAuthorityRequestReadback.stage6_criterion_status
    stage6_criterion_readback_ready = [bool]$OsBindingAuthorityRequestReadback.stage6_criterion_readback_ready
    pending_count = [int]$OsBindingAuthorityRequestReadback.pending_count
    approved_count = [int]$OsBindingAuthorityRequestReadback.approved_count
    rejected_count = [int]$OsBindingAuthorityRequestReadback.rejected_count
    emergency_count = [int]$OsBindingAuthorityRequestReadback.emergency_count
    total_count = [int]$OsBindingAuthorityRequestReadback.total_count
    authority_granted = [bool]$OsBindingAuthorityRequestReadback.authority_granted
    os_level_command_palette_binding_authority = [bool]$OsBindingAuthorityRequestReadback.os_level_command_palette_binding_authority
    os_level_command_palette = [bool]$OsBindingAuthorityRequestReadback.os_level_command_palette
    summon_anywhere = [bool]$OsBindingAuthorityRequestReadback.summon_anywhere
    opens_palette = [bool]$OsBindingAuthorityRequestReadback.opens_palette
    registers_hotkey = [bool]$OsBindingAuthorityRequestReadback.registers_hotkey
    launches_process = [bool]$OsBindingAuthorityRequestReadback.launches_process
    controls_overlay = [bool]$OsBindingAuthorityRequestReadback.controls_overlay
    governance = [ordered]@{
      read_only_contract = [bool]$OsBindingAuthorityRequestReadbackGovernance.read_only_contract
      approval_request_write = [bool]$OsBindingAuthorityRequestReadbackGovernance.approval_request_write
      execution_authority = $false
      approval_decision_authority = $false
      memory_write = $false
      resident_claim_authority = $false
    }
  }
  summon_anywhere_blockers_proof = [ordered]@{
    status = if ($SummonAnywhereBlockersProofObserved) { [string]$SummonAnywhereBlockersProof.status } else { 'missing_or_failed' }
    ok = $SummonAnywhereBlockersProofObserved
    exit_code = [int]$SummonAnywhereBlockersProofResult.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $SummonAnywhereBlockersProof.evidence)
    acceptance_criterion = [string]$SummonAnywhereBlockersProof.acceptance_criterion
    next_smallest_truthful_gap = [string]$SummonAnywhereBlockersProof.next_smallest_truthful_gap
    summon_preflight_observed = [bool]$SummonAnywhereBlockersProof.summon_preflight_observed
    stage6_family_projection_observed = [bool]$SummonAnywhereBlockersProof.stage6_family_projection_observed
    side_effects_denied = [bool]$SummonAnywhereBlockersProof.side_effects_denied
    os_binding_authority_request_readback_observed = [bool]$SummonAnywhereBlockersProof.os_binding_authority_request_readback_observed
    first_blocker_family_handoff_observed = $SummonAnywhereBlockersProofFirstFamilyHandoffObserved
    first_blocker_family = [string]$SummonAnywhereBlockersProof.first_blocker_family
    first_blocker_family_handoff = $SummonAnywhereBlockersProofFirstFamilyHandoff
    blocked_families = [string[]]@($SummonAnywhereBlockersProofFamilies)
    blocked_family_handoffs = @($SummonAnywhereBlockersProofFamilyHandoffs)
    blocker_groups = [ordered]@{
      resident_host = [string[]]@($SummonAnywhereBlockersProofResidentHostBlockers)
      tray_presence = [string[]]@($SummonAnywhereBlockersProofTrayBlockers)
      overlay_window = [string[]]@($SummonAnywhereBlockersProofOverlayBlockers)
      global_hotkey_binding = [string[]]@($SummonAnywhereBlockersProofGlobalHotkeyBlockers)
      summon_binding = [string[]]@($SummonAnywhereBlockersProofSummonBlockers)
      authority = [string[]]@($SummonAnywhereBlockersProofAuthorityBlockers)
    }
    lens_status_readback = $SummonAnywhereBlockersProof.lens_status_readback
    os_binding_authority_request_readback = $SummonAnywhereBlockersProof.os_binding_authority_request_readback
    summon_preflight = $SummonAnywhereBlockersProof.summon_preflight
    governance = [ordered]@{
      diagnostic_only = [bool]$SummonAnywhereBlockersProofGovernance.diagnostic_only
      wraps_summon_preflight = [bool]$SummonAnywhereBlockersProofGovernance.wraps_summon_preflight
      wraps_lens_status = [bool]$SummonAnywhereBlockersProofGovernance.wraps_lens_status
      read_only_contract = [bool]$SummonAnywhereBlockersProofGovernance.read_only_contract
      os_binding_authority_request_readback = [bool]$SummonAnywhereBlockersProofGovernance.os_binding_authority_request_readback
      first_blocker_family_handoff_readback = [bool]$SummonAnywhereBlockersProofGovernance.first_blocker_family_handoff_readback
      approval_request_write = $false
      product_execution_authority = $false
      execution_authority = $false
      approval_decision_authority = $false
      memory_write = $false
      overlay_control_authority = $false
      summon_authority = $false
      capture_authority = $false
      new_sensing_authority = $false
      local_process_launch_authority = $false
      hotkey_registration_authority = $false
      resident_claim_authority = $false
      mutation_authority_granted = $false
    }
  }
  summon_authority_blocker_proof = [ordered]@{
    status = if ($SummonAuthorityBlockerProofObserved) { [string]$SummonAuthorityBlockerProof.status } else { 'missing_or_failed' }
    ok = $SummonAuthorityBlockerProofObserved
    exit_code = [int]$SummonAuthorityBlockerProofResult.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $SummonAuthorityBlockerProof.evidence)
    acceptance_criterion = [string]$SummonAuthorityBlockerProof.acceptance_criterion
    previous_summon_blocker_family = [string]$SummonAuthorityBlockerProof.previous_summon_blocker_family
    summon_authority_blocker_family = [string]$SummonAuthorityBlockerProof.summon_authority_blocker_family
    sixth_summon_blocker_family = [string]$SummonAuthorityBlockerProof.sixth_summon_blocker_family
    next_summon_blocker_family = [string]$SummonAuthorityBlockerProof.next_summon_blocker_family
    summon_next_smallest_truthful_gap = [string]$SummonAuthorityBlockerProof.summon_next_smallest_truthful_gap
    previous_binding_next_smallest_truthful_gap = [string]$SummonAuthorityBlockerProof.previous_binding_next_smallest_truthful_gap
    direct_summon_preflight_next_smallest_truthful_gap = [string]$SummonAuthorityBlockerProof.direct_summon_preflight_next_smallest_truthful_gap
    next_smallest_truthful_gap = [string]$SummonAuthorityBlockerProof.next_smallest_truthful_gap
    summon_authority_family_observed = [bool]$SummonAuthorityBlockerProof.summon_authority_family_observed
    previous_summon_binding_bridge_observed = [bool]$SummonAuthorityBlockerProof.previous_summon_binding_bridge_observed
    summon_preflight_authority_observed = [bool]$SummonAuthorityBlockerProof.summon_preflight_authority_observed
    all_summon_blocker_families_consumed = [bool]$SummonAuthorityBlockerProof.all_summon_blocker_families_consumed
    handoff_aligned = [bool]$SummonAuthorityBlockerProof.handoff_aligned
    side_effects_denied = [bool]$SummonAuthorityBlockerProof.side_effects_denied
    summon_authority_blockers = [string[]]@($SummonAuthorityBlockers)
    direct_summon_preflight_authority_blockers = [string[]]@($DirectSummonPreflightAuthorityBlockers)
    direct_summon_preflight_binding_blockers = [string[]]@($DirectSummonPreflightBindingBlockers)
    summon_authority_boundary = [ordered]@{
      status = [string]$SummonAuthorityBoundary.status
      ready = [bool]$SummonAuthorityBoundary.ready
      summon_name = [string]$SummonAuthorityBoundary.summon_name
      config_path = [string]$SummonAuthorityBoundary.config_path
      global_hotkey = [string]$SummonAuthorityBoundary.global_hotkey
      binding_scope = [string]$SummonAuthorityBoundary.binding_scope
      palette_route = [string]$SummonAuthorityBoundary.palette_route
      required_before_enable = [string[]]@($SummonAuthorityBoundaryRequiredBeforeEnable)
      binding_enabled = [bool]$SummonAuthorityBoundary.binding_enabled
      register_hotkey = [bool]$SummonAuthorityBoundary.register_hotkey
      startup_register = [bool]$SummonAuthorityBoundary.startup_register
      blockers = [string[]]@($SummonAuthorityBoundaryBlockers)
      summon_binding_blockers = [string[]]@($SummonAuthorityBoundaryBindingBlockers)
      authority_blockers = [string[]]@($SummonAuthorityBoundaryAuthorityBlockers)
    }
    governance = [ordered]@{
      diagnostic_only = [bool]$SummonAuthorityBlockerProofGovernance.diagnostic_only
      wraps_summon_anywhere_blockers_proof = [bool]$SummonAuthorityBlockerProofGovernance.wraps_summon_anywhere_blockers_proof
      wraps_summon_binding_blocker_proof = [bool]$SummonAuthorityBlockerProofGovernance.wraps_summon_binding_blocker_proof
      wraps_summon_preflight = [bool]$SummonAuthorityBlockerProofGovernance.wraps_summon_preflight
      read_only_contract = [bool]$SummonAuthorityBlockerProofGovernance.read_only_contract
      approval_request_write = $false
      resident_runtime_execution_authority = $false
      product_execution_authority = $false
      execution_authority = $false
      approval_decision_authority = $false
      local_process_launch_authority = $false
      process_supervision_authority = $false
      process_restart_authority = $false
      service_install_authority = $false
      service_control_authority = $false
      tray_registration_authority = $false
      tray_icon_authority = $false
      notification_authority = $false
      hotkey_registration_authority = $false
      overlay_control_authority = $false
      window_management_authority = $false
      capture_authority = $false
      new_sensing_authority = $false
      summon_authority = $false
      memory_write = $false
      receipt_write_authority = $false
      resident_claim_authority = $false
      mutation_authority_granted = $false
    }
  }
  summon_anywhere_family_chain_proof = [ordered]@{
    status = if ($SummonAnywhereFamilyChainProofObserved) { [string]$SummonAnywhereFamilyChainProof.status } else { 'missing_or_failed' }
    ok = $SummonAnywhereFamilyChainProofObserved
    exit_code = [int]$SummonAnywhereFamilyChainProofResult.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $SummonAnywhereFamilyChainProof.evidence)
    acceptance_criterion = [string]$SummonAnywhereFamilyChainProof.acceptance_criterion
    summon_next_smallest_truthful_gap = [string]$SummonAnywhereFamilyChainProof.summon_next_smallest_truthful_gap
    next_smallest_truthful_gap = [string]$SummonAnywhereFamilyChainProof.next_smallest_truthful_gap
    family_chain_observed = [bool]$SummonAnywhereFamilyChainProof.family_chain_observed
    resident_host_family_handoff_observed = [bool]$SummonAnywhereFamilyChainProof.resident_host_family_handoff_observed
    final_summon_authority_handoff_observed = [bool]$SummonAnywhereFamilyChainProof.final_summon_authority_handoff_observed
    all_summon_blocker_families_consumed = [bool]$SummonAnywhereFamilyChainProof.all_summon_blocker_families_consumed
    handoff_aligned = [bool]$SummonAnywhereFamilyChainProof.handoff_aligned
    side_effects_denied = [bool]$SummonAnywhereFamilyChainProof.side_effects_denied
    blocked_families = [string[]]@($SummonAnywhereFamilyChainProofBlockedFamilies)
    blocked_family_handoffs = @($SummonAnywhereFamilyChainProof.blocked_family_handoffs)
    first_blocker_family = [string]$SummonAnywhereFamilyChainProof.first_blocker_family
    first_blocker_family_handoff = $SummonAnywhereFamilyChainProof.first_blocker_family_handoff
    resident_host = [ordered]@{
      next_smallest_truthful_gap = [string]$SummonAnywhereFamilyChainProofResidentHost.next_smallest_truthful_gap
      lifecycle_next_smallest_truthful_gap = [string]$SummonAnywhereFamilyChainProofResidentHost.lifecycle_next_smallest_truthful_gap
      runtime_blockers = [string[]]@($SummonAnywhereFamilyChainProofResidentHostRuntimeBlockers)
      surface_blockers = [string[]]@($SummonAnywhereFamilyChainProofResidentHostSurfaceBlockers)
    }
    final_authority = [ordered]@{
      previous_summon_blocker_family = [string]$SummonAnywhereFamilyChainProofFinalAuthority.previous_summon_blocker_family
      summon_authority_blocker_family = [string]$SummonAnywhereFamilyChainProofFinalAuthority.summon_authority_blocker_family
      next_summon_blocker_family = [string]$SummonAnywhereFamilyChainProofFinalAuthority.next_summon_blocker_family
      next_smallest_truthful_gap = [string]$SummonAnywhereFamilyChainProofFinalAuthority.next_smallest_truthful_gap
      all_summon_blocker_families_consumed = [bool]$SummonAnywhereFamilyChainProofFinalAuthority.all_summon_blocker_families_consumed
      blockers = [string[]]@($SummonAnywhereFamilyChainProofFinalAuthorityBlockers)
    }
    governance = [ordered]@{
      diagnostic_only = [bool]$SummonAnywhereFamilyChainProofGovernance.diagnostic_only
      wraps_summon_anywhere_blockers_proof = [bool]$SummonAnywhereFamilyChainProofGovernance.wraps_summon_anywhere_blockers_proof
      wraps_summon_resident_host_blocker_proof = [bool]$SummonAnywhereFamilyChainProofGovernance.wraps_summon_resident_host_blocker_proof
      wraps_summon_authority_blocker_proof = [bool]$SummonAnywhereFamilyChainProofGovernance.wraps_summon_authority_blocker_proof
      read_only_contract = [bool]$SummonAnywhereFamilyChainProofGovernance.read_only_contract
      bounded_local_process_launch = $false
      temporary_runtime_state_write = $false
      product_execution_authority = $false
      execution_authority = $false
      approval_decision_authority = $false
      local_process_launch_authority = $false
      process_supervision_authority = $false
      process_restart_authority = $false
      service_install_authority = $false
      service_control_authority = $false
      hotkey_registration_authority = $false
      overlay_control_authority = $false
      summon_authority = $false
      memory_write = $false
      receipt_write_authority = $false
      resident_claim_authority = $false
      mutation_authority_granted = $false
    }
  }
  resident_host_runtime_boundary_proof = [ordered]@{
    status = if ($ResidentHostRuntimeBoundaryProofObserved) { [string]$ResidentHostRuntimeBoundaryProof.status } else { 'missing_or_failed' }
    ok = $ResidentHostRuntimeBoundaryProofObserved
    exit_code = [int]$ResidentHostRuntimeBoundaryProofResult.exit_code
    evidence = [string[]]@(
      'scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status'
      (ConvertTo-StringArray -Value $ResidentHostRuntimeBoundaryProof.evidence)
    )
    previous_next_smallest_truthful_gap = [string]$ResidentHostRuntimeBoundaryProof.previous_next_smallest_truthful_gap
    next_smallest_truthful_gap = [string]$ResidentHostRuntimeBoundaryProof.next_smallest_truthful_gap
    runtime_handoff_observed = [bool]$ResidentHostRuntimeBoundaryProof.runtime_handoff_observed
    bounded_runtime_observed = [bool]$ResidentHostRuntimeBoundaryProof.bounded_runtime_observed
    runtime_heartbeat_observed = [bool]$ResidentHostRuntimeBoundaryProof.runtime_heartbeat_observed
    heartbeat_count = [int]$ResidentHostRuntimeBoundaryProof.heartbeat_count
    runtime_boundary_blocked = [bool]$ResidentHostRuntimeBoundaryProof.runtime_boundary_blocked
    process_supervision_handoff_observed = [bool]$ResidentHostRuntimeBoundaryProof.process_supervision_handoff_observed
    side_effects_bounded = [bool]$ResidentHostRuntimeBoundaryProof.side_effects_bounded
    resident_host_process_state = [string]$ResidentHostRuntimeBoundaryProof.resident_host_process_state
    resident_host_process_blocker = [string]$ResidentHostRuntimeBoundaryProof.resident_host_process_blocker
    resident_runtime_ready = [bool]$ResidentHostRuntimeBoundaryProof.resident_runtime_ready
    supervision_ready = [bool]$ResidentHostRuntimeBoundaryProof.supervision_ready
    ready_for_resident_claim = [bool]$ResidentHostRuntimeBoundaryProof.ready_for_resident_claim
    resident_claim_allowed = [bool]$ResidentHostRuntimeBoundaryProof.resident_claim_allowed
    resident_host_supervised = [bool]$ResidentHostRuntimeBoundaryProof.resident_host_supervised
    service_managed = [bool]$ResidentHostRuntimeBoundaryProof.service_managed
    tray_presence = [bool]$ResidentHostRuntimeBoundaryProof.tray_presence
    global_hotkey = [bool]$ResidentHostRuntimeBoundaryProof.global_hotkey
    overlay_window = [bool]$ResidentHostRuntimeBoundaryProof.overlay_window
    summon_anywhere = [bool]$ResidentHostRuntimeBoundaryProof.summon_anywhere
    blockers = [string[]]@($ResidentHostRuntimeBoundaryProofBlockers)
    governance = [ordered]@{
      diagnostic_only = [bool]$ResidentHostRuntimeBoundaryProof.governance.diagnostic_only
      wraps_summon_resident_host_blocker_proof = [bool]$ResidentHostRuntimeBoundaryProof.governance.wraps_summon_resident_host_blocker_proof
      wraps_host_supervision_proof = [bool]$ResidentHostRuntimeBoundaryProof.governance.wraps_host_supervision_proof
      bounded_local_process_launch = [bool]$ResidentHostRuntimeBoundaryProof.governance.bounded_local_process_launch
      temporary_runtime_state_write = [bool]$ResidentHostRuntimeBoundaryProof.governance.temporary_runtime_state_write
      product_execution_authority = $false
      execution_authority = $false
      approval_decision_authority = $false
      memory_write = $false
      api_local_process_launch_authority = $false
      process_supervision_authority = $false
      process_restart_authority = $false
      service_install_authority = $false
      service_control_authority = $false
      hotkey_registration_authority = $false
      tray_registration_authority = $false
      overlay_control_authority = $false
      summon_authority = $false
      resident_claim_authority = $false
      mutation_authority_granted = $false
    }
  }
  process_supervision_authority_boundary_proof = [ordered]@{
    status = if ($ProcessSupervisionBoundaryObserved) { [string]$ProcessSupervisionBoundary.status } else { 'missing_or_failed' }
    ok = $ProcessSupervisionBoundaryObserved
    exit_code = [int]$ProcessSupervisionBoundaryResult.exit_code
    evidence = @(
      'scripts/lens-process-supervision-authority-boundary-proof.ps1 -Mode Status',
      'scripts/lens-host-supervision-proof.ps1 -Mode Status'
    )
    stage6_checkpoint_observed = [bool]$ProcessSupervisionBoundary.stage6_checkpoint_observed
    host_supervision_boundary_observed = [bool]$ProcessSupervisionBoundary.host_supervision_boundary_observed
    process_supervision_boundary_observed = [bool]$ProcessSupervisionBoundary.process_supervision_boundary_observed
    service_activation_plan_observed = [bool]$ProcessSupervisionBoundary.service_activation_plan_observed
    bounded_local_process_launch_observed = [bool]$ProcessSupervisionBoundary.bounded_local_process_launch_observed
    supervision_ready = [bool]$ProcessSupervisionBoundary.supervision_ready
    ready_for_resident_claim = [bool]$ProcessSupervisionBoundary.ready_for_resident_claim
    resident_claim_allowed = [bool]$ProcessSupervisionBoundary.resident_claim_allowed
    resident_host_supervised = [bool]$ProcessSupervisionBoundary.resident_host_supervised
    service_installed = [bool]$ProcessSupervisionBoundary.service_installed
    service_managed = [bool]$ProcessSupervisionBoundary.service_managed
    process_supervision_ready = [bool]$ProcessSupervisionBoundary.process_supervision_ready
    service_activation_ready = [bool]$ProcessSupervisionBoundary.service_activation_ready
    would_supervise_process = [bool]$ProcessSupervisionBoundary.would_supervise_process
    would_restart_process = [bool]$ProcessSupervisionBoundary.would_restart_process
    would_install_service = [bool]$ProcessSupervisionBoundary.would_install_service
    would_start_service = [bool]$ProcessSupervisionBoundary.would_start_service
    would_write_memory = [bool]$ProcessSupervisionBoundary.would_write_memory
    would_decide_approval = [bool]$ProcessSupervisionBoundary.would_decide_approval
    blockers = [string[]]@($ProcessSupervisionBoundaryBlockers)
  }
  resident_host_process_supervision_blocker_proof = [ordered]@{
    status = if ($ResidentHostProcessSupervisionBlockerProofObserved) { [string]$ResidentHostProcessSupervisionBlockerProof.status } else { 'missing_or_failed' }
    ok = $ResidentHostProcessSupervisionBlockerProofObserved
    exit_code = [int]$ResidentHostProcessSupervisionBlockerProofResult.exit_code
    evidence = [string[]]@(
      'scripts/lens-resident-host-process-supervision-blocker-proof.ps1 -Mode Status'
      (ConvertTo-StringArray -Value $ResidentHostProcessSupervisionBlockerProof.evidence)
    )
    previous_next_smallest_truthful_gap = [string]$ResidentHostProcessSupervisionBlockerProof.previous_next_smallest_truthful_gap
    next_smallest_truthful_gap = [string]$ResidentHostProcessSupervisionBlockerProof.next_smallest_truthful_gap
    resident_host_process_handoff_observed = [bool]$ResidentHostProcessSupervisionBlockerProof.resident_host_process_handoff_observed
    process_supervision_boundary_observed = [bool]$ResidentHostProcessSupervisionBlockerProof.process_supervision_boundary_observed
    handoff_consumed = [bool]$ResidentHostProcessSupervisionBlockerProof.handoff_consumed
    authority_denied = [bool]$ResidentHostProcessSupervisionBlockerProof.authority_denied
    resident_host_process_state = [string]$ResidentHostProcessSupervisionBlockerProof.resident_host_process_state
    resident_host_process_blocker = [string]$ResidentHostProcessSupervisionBlockerProof.resident_host_process_blocker
    supervision_ready = [bool]$ResidentHostProcessSupervisionBlockerProof.supervision_ready
    ready_for_resident_claim = [bool]$ResidentHostProcessSupervisionBlockerProof.ready_for_resident_claim
    resident_claim_allowed = [bool]$ResidentHostProcessSupervisionBlockerProof.resident_claim_allowed
    resident_host_supervised = [bool]$ResidentHostProcessSupervisionBlockerProof.resident_host_supervised
    service_installed = [bool]$ResidentHostProcessSupervisionBlockerProof.service_installed
    service_managed = [bool]$ResidentHostProcessSupervisionBlockerProof.service_managed
    process_supervision_ready = [bool]$ResidentHostProcessSupervisionBlockerProof.process_supervision_ready
    service_activation_ready = [bool]$ResidentHostProcessSupervisionBlockerProof.service_activation_ready
    would_supervise_process = [bool]$ResidentHostProcessSupervisionBlockerProof.would_supervise_process
    would_restart_process = [bool]$ResidentHostProcessSupervisionBlockerProof.would_restart_process
    would_install_service = [bool]$ResidentHostProcessSupervisionBlockerProof.would_install_service
    would_start_service = [bool]$ResidentHostProcessSupervisionBlockerProof.would_start_service
    would_write_memory = [bool]$ResidentHostProcessSupervisionBlockerProof.would_write_memory
    would_decide_approval = [bool]$ResidentHostProcessSupervisionBlockerProof.would_decide_approval
    blockers = [string[]]@($ResidentHostProcessSupervisionBlockerProofBlockers)
  }
  persistent_supervision_plan = [ordered]@{
    status = if ($PersistentSupervisionPlanObserved) { [string]$PersistentSupervisionPlan.status } else { 'missing_or_failed' }
    ok = $PersistentSupervisionPlanObserved
    exit_code = [int]$PersistentSupervisionPlanResult.exit_code
    evidence = @('scripts/lens-persistent-supervision-plan.ps1 -Mode Status')
    plan_available = [bool]$PersistentSupervisionPlan.plan_available
    persistent_supervision_ready = [bool]$PersistentSupervisionPlan.persistent_supervision_ready
    resident_claim_allowed = [bool]$PersistentSupervisionPlan.resident_claim_allowed
    requirements_total = [int]$PersistentSupervisionPlan.requirements_total
    requirements_ready_total = [int]$PersistentSupervisionPlan.requirements_ready_total
    requirements_blocked_total = [int]$PersistentSupervisionPlan.requirements_blocked_total
    blocked_requirements = [string[]]@(ConvertTo-StringArray -Value $PersistentSupervisionPlan.blocked_requirements)
    blockers = [string[]]@($PersistentSupervisionPlanBlockers)
    would_install_service = [bool]$PersistentSupervisionPlan.plan.would_install_service
    would_start_service = [bool]$PersistentSupervisionPlan.plan.would_start_service
    would_restart_process = [bool]$PersistentSupervisionPlan.plan.would_restart_process
    would_supervise_process = [bool]$PersistentSupervisionPlan.plan.would_supervise_process
    would_write_receipt = [bool]$PersistentSupervisionPlan.plan.would_write_receipt
    would_write_memory = [bool]$PersistentSupervisionPlan.plan.would_write_memory
    would_claim_resident = [bool]$PersistentSupervisionPlan.plan.would_claim_resident
  }
  persistent_supervision_enablement_denial_boundary = [ordered]@{
    status = if ($PersistentSupervisionEnablementDenialObserved) { [string]$PersistentSupervisionEnablementDenial.status } else { 'missing_or_failed' }
    ok = $PersistentSupervisionEnablementDenialObserved
    evidence = [string[]]@(ConvertTo-StringArray -Value $PersistentSupervisionEnablementDenial.evidence)
    boundary_ready = [bool]$PersistentSupervisionEnablementDenial.boundary_ready
    applied = [bool]$PersistentSupervisionEnablementDenial.applied
    executed = [bool]$PersistentSupervisionEnablementDenial.executed
    authority_granted = [bool]$PersistentSupervisionEnablementDenial.authority_granted
    enablement_ready = [bool]$PersistentSupervisionEnablementDenial.enablement_ready
    resident_claim_allowed = [bool]$PersistentSupervisionEnablementDenial.resident_claim_allowed
    service_config_updated = [bool]$PersistentSupervisionEnablementDenial.service_config_updated
    authority_grant_active = [bool]$PersistentSupervisionEnablementDenial.authority_grant_active
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_config_write_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    denial_receipt_write_authority = $false
    resident_claim_authority = $false
    blockers = [string[]]@($PersistentSupervisionEnablementDenialBlockers)
  }
  persistent_supervision_enablement_execution_denial_boundary = [ordered]@{
    status = if ($PersistentSupervisionEnablementExecutionDenialObserved) { [string]$PersistentSupervisionEnablementExecutionDenial.status } else { 'missing_or_failed' }
    ok = $PersistentSupervisionEnablementExecutionDenialObserved
    evidence = [string[]]@(ConvertTo-StringArray -Value $PersistentSupervisionEnablementExecutionDenial.evidence)
    boundary_ready = [bool]$PersistentSupervisionEnablementExecutionDenial.boundary_ready
    applied = [bool]$PersistentSupervisionEnablementExecutionDenial.applied
    executed = [bool]$PersistentSupervisionEnablementExecutionDenial.executed
    ready = [bool]$PersistentSupervisionEnablementExecutionDenial.ready
    approval_ready = [bool]$PersistentSupervisionEnablementExecutionDenial.approval_ready
    enablement_authority_granted = [bool]$PersistentSupervisionEnablementExecutionDenial.enablement_authority_granted
    persistent_supervision_enablement_allowed = [bool]$PersistentSupervisionEnablementExecutionDenial.persistent_supervision_enablement_allowed
    service_config_updated = [bool]$PersistentSupervisionEnablementExecutionDenial.service_config_updated
    resident_claim_allowed = [bool]$PersistentSupervisionEnablementExecutionDenial.resident_claim_allowed
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    persistent_supervision_enablement_authority = $false
    service_config_write_authority = $false
    persistent_supervision_execution_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    denial_receipt_write_authority = $false
    resident_claim_authority = $false
    blockers = [string[]]@($PersistentSupervisionEnablementExecutionDenialBlockers)
  }
  persistent_supervision_enablement_authority_proof = [ordered]@{
    status = if ($PersistentSupervisionEnablementAuthorityProofObserved) { [string]$PersistentSupervisionEnablementAuthorityProof.status } else { 'missing_or_failed' }
    ok = $PersistentSupervisionEnablementAuthorityProofObserved
    exit_code = [int]$PersistentSupervisionEnablementAuthorityProofResult.exit_code
    evidence = @(
      'scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status',
      '/lens/host/persistent-supervision/enablement/authority',
      '/lens/host/persistent-supervision/enablement/authority/grants',
      '/lens/host/persistent-supervision/enablement/authority/readiness',
      '/lens/host/persistent-supervision/enablement',
      '/lens/status'
    )
    host_supervision_authority_grant_receipt_id = [string]$PersistentSupervisionEnablementAuthorityProof.host_supervision_authority_grant_receipt_id
    persistent_supervision_enablement_authority_grant_receipt_id = [string]$PersistentSupervisionEnablementAuthorityProof.persistent_supervision_enablement_authority_grant_receipt_id
    persistent_supervision_enablement_authority = [bool]$PersistentSupervisionEnablementAuthorityProof.persistent_supervision_enablement_authority
    service_config_write_authority = [bool]$PersistentSupervisionEnablementAuthorityProof.service_config_write_authority
    persistent_supervision_execution_authority = [bool]$PersistentSupervisionEnablementAuthorityProof.persistent_supervision_execution_authority
    persistent_supervision_enablement_allowed = [bool]$PersistentSupervisionEnablementAuthorityProof.persistent_supervision_enablement_allowed
    resident_claim_allowed = [bool]$PersistentSupervisionEnablementAuthorityProof.resident_claim_allowed
    grant_applied = [bool]$PersistentSupervisionEnablementAuthorityProof.grant_applied
    enablement_applied = [bool]$PersistentSupervisionEnablementAuthorityProof.enablement_applied
    executed = [bool]$PersistentSupervisionEnablementAuthorityProof.executed
    service_config_updated = [bool]$PersistentSupervisionEnablementAuthorityProof.service_config_updated
    would_update_service_config = [bool]$PersistentSupervisionEnablementAuthorityProof.would_update_service_config
    would_enable_process_supervision = [bool]$PersistentSupervisionEnablementAuthorityProof.would_enable_process_supervision
    would_enable_persistent_supervision = [bool]$PersistentSupervisionEnablementAuthorityProof.would_enable_persistent_supervision
    would_install_service = [bool]$PersistentSupervisionEnablementAuthorityProof.would_install_service
    would_start_service = [bool]$PersistentSupervisionEnablementAuthorityProof.would_start_service
    would_supervise_process = [bool]$PersistentSupervisionEnablementAuthorityProof.would_supervise_process
    would_restart_process = [bool]$PersistentSupervisionEnablementAuthorityProof.would_restart_process
    would_write_memory = [bool]$PersistentSupervisionEnablementAuthorityProof.would_write_memory
    would_claim_resident = [bool]$PersistentSupervisionEnablementAuthorityProof.would_claim_resident
    blockers = [string[]]@($PersistentSupervisionEnablementAuthorityProofBlockers)
    next_smallest_truthful_gap = [string]$PersistentSupervisionEnablementAuthorityProof.next_smallest_truthful_gap
  }
  persistent_supervision_execution_authority_proof = [ordered]@{
    status = if ($PersistentSupervisionExecutionAuthorityProofObserved) { [string]$PersistentSupervisionExecutionAuthorityProof.status } else { 'missing_or_failed' }
    ok = $PersistentSupervisionExecutionAuthorityProofObserved
    exit_code = [int]$PersistentSupervisionExecutionAuthorityProofResult.exit_code
    evidence = @(
      'scripts/lens-persistent-supervision-execution-authority-proof.ps1 -Mode Status',
      '/lens/host/persistent-supervision/enablement/execution/request',
      '/lens/host/persistent-supervision/enablement/execution/authority',
      '/lens/host/persistent-supervision/enablement/execution/authority/grants',
      '/lens/host/persistent-supervision/enablement/execution/readiness',
      '/lens/host/persistent-supervision/enablement/execution',
      '/lens/status'
    )
    host_supervision_authority_grant_receipt_id = [string]$PersistentSupervisionExecutionAuthorityProof.host_supervision_authority_grant_receipt_id
    persistent_supervision_enablement_authority_grant_receipt_id = [string]$PersistentSupervisionExecutionAuthorityProof.persistent_supervision_enablement_authority_grant_receipt_id
    persistent_supervision_execution_authority_grant_receipt_id = [string]$PersistentSupervisionExecutionAuthorityProof.persistent_supervision_execution_authority_grant_receipt_id
    persistent_supervision_enablement_authority = [bool]$PersistentSupervisionExecutionAuthorityProof.persistent_supervision_enablement_authority
    service_config_write_authority = [bool]$PersistentSupervisionExecutionAuthorityProof.service_config_write_authority
    persistent_supervision_execution_authority = [bool]$PersistentSupervisionExecutionAuthorityProof.persistent_supervision_execution_authority
    receipt_write_authority = [bool]$PersistentSupervisionExecutionAuthorityProof.receipt_write_authority
    persistent_supervision_enablement_allowed = [bool]$PersistentSupervisionExecutionAuthorityProof.persistent_supervision_enablement_allowed
    resident_claim_allowed = [bool]$PersistentSupervisionExecutionAuthorityProof.resident_claim_allowed
    grant_applied = [bool]$PersistentSupervisionExecutionAuthorityProof.grant_applied
    enablement_applied = [bool]$PersistentSupervisionExecutionAuthorityProof.enablement_applied
    applied = [bool]$PersistentSupervisionExecutionAuthorityProof.applied
    executed = [bool]$PersistentSupervisionExecutionAuthorityProof.executed
    service_config_updated = [bool]$PersistentSupervisionExecutionAuthorityProof.service_config_updated
    would_update_service_config = [bool]$PersistentSupervisionExecutionAuthorityProof.would_update_service_config
    would_enable_persistent_supervision = [bool]$PersistentSupervisionExecutionAuthorityProof.would_enable_persistent_supervision
    would_start_service = [bool]$PersistentSupervisionExecutionAuthorityProof.would_start_service
    would_supervise_process = [bool]$PersistentSupervisionExecutionAuthorityProof.would_supervise_process
    would_restart_process = [bool]$PersistentSupervisionExecutionAuthorityProof.would_restart_process
    would_write_receipt = [bool]$PersistentSupervisionExecutionAuthorityProof.would_write_receipt
    would_write_memory = [bool]$PersistentSupervisionExecutionAuthorityProof.would_write_memory
    would_claim_resident = [bool]$PersistentSupervisionExecutionAuthorityProof.would_claim_resident
    blockers = [string[]]@($PersistentSupervisionExecutionAuthorityProofBlockers)
    next_smallest_truthful_gap = [string]$PersistentSupervisionExecutionAuthorityProof.next_smallest_truthful_gap
  }
  persistent_supervision_resident_claim_boundary_proof = [ordered]@{
    status = if ($PersistentSupervisionResidentClaimBoundaryObserved) { [string]$PersistentSupervisionResidentClaimBoundaryProof.status } else { 'missing_or_failed' }
    ok = $PersistentSupervisionResidentClaimBoundaryObserved
    exit_code = [int]$PersistentSupervisionResidentClaimBoundaryProofResult.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $PersistentSupervisionResidentClaimBoundaryProof.evidence)
    authority_family = [string]$PersistentSupervisionResidentClaimBoundaryProof.authority_family
    previous_authority_family = [string]$PersistentSupervisionResidentClaimBoundaryProof.previous_authority_family
    next_authority_family = [string]$PersistentSupervisionResidentClaimBoundaryProof.next_authority_family
    persistent_supervision_resident_claim_boundary_observed = [bool]$PersistentSupervisionResidentClaimBoundaryProof.persistent_supervision_resident_claim_boundary_observed
    persistent_supervision_execution_authority_proof_observed = [bool]$PersistentSupervisionResidentClaimBoundaryProof.persistent_supervision_execution_authority_proof_observed
    persistent_supervision_plan_observed = [bool]$PersistentSupervisionResidentClaimBoundaryProof.persistent_supervision_plan_observed
    side_effects_denied = [bool]$PersistentSupervisionResidentClaimBoundaryProof.side_effects_denied
    final_persistent_supervision_authority_family_consumed = [bool]$PersistentSupervisionResidentClaimBoundaryProof.final_persistent_supervision_authority_family_consumed
    resident_claim = $PersistentSupervisionResidentClaimBoundaryProof.resident_claim
    persistent_supervision_enablement_authority = [bool]$PersistentSupervisionResidentClaimBoundaryProof.persistent_supervision_enablement_authority
    service_config_write_authority = [bool]$PersistentSupervisionResidentClaimBoundaryProof.service_config_write_authority
    persistent_supervision_execution_authority = [bool]$PersistentSupervisionResidentClaimBoundaryProof.persistent_supervision_execution_authority
    receipt_write_authority = [bool]$PersistentSupervisionResidentClaimBoundaryProof.receipt_write_authority
    resident_claim_authority = [bool]$PersistentSupervisionResidentClaimBoundaryProof.resident_claim_authority
    persistent_supervision_ready = [bool]$PersistentSupervisionResidentClaimBoundaryProof.persistent_supervision_ready
    resident_claim_allowed = [bool]$PersistentSupervisionResidentClaimBoundaryProof.resident_claim_allowed
    applied = [bool]$PersistentSupervisionResidentClaimBoundaryProof.applied
    executed = [bool]$PersistentSupervisionResidentClaimBoundaryProof.executed
    service_config_updated = [bool]$PersistentSupervisionResidentClaimBoundaryProof.service_config_updated
    would_update_service_config = [bool]$PersistentSupervisionResidentClaimBoundaryProof.would_update_service_config
    would_enable_persistent_supervision = [bool]$PersistentSupervisionResidentClaimBoundaryProof.would_enable_persistent_supervision
    would_start_service = [bool]$PersistentSupervisionResidentClaimBoundaryProof.would_start_service
    would_supervise_process = [bool]$PersistentSupervisionResidentClaimBoundaryProof.would_supervise_process
    would_restart_process = [bool]$PersistentSupervisionResidentClaimBoundaryProof.would_restart_process
    would_write_receipt = [bool]$PersistentSupervisionResidentClaimBoundaryProof.would_write_receipt
    would_write_memory = [bool]$PersistentSupervisionResidentClaimBoundaryProof.would_write_memory
    would_claim_resident = [bool]$PersistentSupervisionResidentClaimBoundaryProof.would_claim_resident
    blockers = [string[]]@($PersistentSupervisionResidentClaimBoundaryBlockers)
    remaining_authority_families_after_this_boundary = [string[]]@(ConvertTo-StringArray -Value $PersistentSupervisionResidentClaimBoundaryProof.remaining_authority_families_after_this_boundary)
    next_smallest_truthful_gap = [string]$PersistentSupervisionResidentClaimBoundaryProof.next_smallest_truthful_gap
  }
  evidence = @(
    'docs/canonical/ROADMAP.md#4.12',
    'docs/operations/COMPLETION_LEDGER.md',
    'scripts/lens-stage6-checkpoint.ps1 -Mode Status',
    'scripts/lens-command-palette.ps1 -Mode Status -StatusPath <checkpoint-lens-status>',
    'scripts/lens-resident-runtime-boundary-proof.ps1 -Mode Status',
    'scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status',
    'scripts/lens-process-supervision-authority-boundary-proof.ps1 -Mode Status',
    'scripts/lens-resident-host-process-supervision-blocker-proof.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-plan.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-execution-authority-proof.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status',
    'scripts/lens-command-palette-os-binding-proof.ps1 -Mode Status -StatusPath <checkpoint-lens-status>',
    'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status',
    'scripts/lens-summon-authority-blocker-proof.ps1 -Mode Status',
    '/lens/host/persistent-supervision/enablement',
    '/lens/host/persistent-supervision/enablement/execution',
    '/lens/host/persistent-supervision/enablement/execution/readiness',
    '/lens/status',
    '/lens/os-binding/authority/requests',
    '/lens/os-binding/authority/request',
    '/lens/resident-surface',
    '/lens/resident-surface/activation',
    '/lens/host/supervision/authority/readiness',
    'scripts/lens-resident-runtime-authority-blockers-proof.ps1 -Mode Status',
    'scripts/lens-resident-runtime-resident-claim-boundary-proof.ps1 -Mode Status'
  )
  resident_host_supervision_authority_readiness_handoff = [ordered]@{
    status = [string]$HostSupervisionAuthorityReadiness.status
    audit_status = [string]$HostSupervisionAuthorityReadiness.audit_status
    ok = [bool]$HostSupervisionAuthorityReadiness.ok
    ready = [bool]$HostSupervisionAuthorityReadiness.ready
    readback_ready = [bool]$HostSupervisionAuthorityReadiness.operator_surface_readback_ready
    request_readback_ready = $HostSupervisionAuthorityReadinessRequestReadbackReady
    handoff_observed = $HostSupervisionAuthorityReadinessHandoffObserved
    first_blocked_requirement = $HostSupervisionAuthorityReadinessFirstBlockedRequirement
    first_blocked_requirement_handoff = $HostSupervisionAuthorityReadinessFirstBlockedRequirementHandoff
    blocked_requirements = $HostSupervisionAuthorityReadinessBlockedRequirements
    blocked_requirement_handoffs = $HostSupervisionAuthorityReadinessBlockedRequirementHandoffs
    next_smallest_truthful_gap = [string]$HostSupervisionAuthorityReadiness.next_smallest_truthful_gap
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    memory_write = $false
    resident_claim_authority = $false
  }
  governance = [ordered]@{
    read_only_contract = $true
    diagnostic_only = $true
    checkpoint_readback = $true
    child_proof_timeout_readback = $true
    process_supervision_authority_boundary_readback = $ProcessSupervisionBoundaryObserved
    resident_host_process_supervision_blocker_proof_readback = $ResidentHostProcessSupervisionBlockerProofObserved
    resident_host_process_handoff_consumed = [bool]$ResidentHostProcessSupervisionBlockerProof.handoff_consumed
    resident_host_supervision_authority_readiness_handoff_readback = $HostSupervisionAuthorityReadinessHandoffObserved
    persistent_supervision_plan_readback = $PersistentSupervisionPlanObserved
    persistent_supervision_enablement_authority_proof_readback = $PersistentSupervisionEnablementAuthorityProofObserved
    persistent_supervision_execution_authority_proof_readback = $PersistentSupervisionExecutionAuthorityProofObserved
    persistent_supervision_resident_claim_boundary_proof_readback = $PersistentSupervisionResidentClaimBoundaryObserved
    persistent_supervision_enablement_denial_boundary_readback = $PersistentSupervisionEnablementDenialObserved
    persistent_supervision_enablement_execution_denial_boundary_readback = $PersistentSupervisionEnablementExecutionDenialObserved
    resident_runtime_granted_boundary_proof_readback = $ResidentRuntimeGrantedBoundaryProofObserved
    resident_runtime_authority_blockers_proof_readback = $ResidentRuntimeAuthorityBlockersProofObserved
    resident_runtime_process_supervision_boundary_proof_readback = $ResidentRuntimeProcessSupervisionBoundaryObserved
    resident_runtime_service_control_boundary_proof_readback = $ResidentRuntimeServiceControlBoundaryObserved
    resident_runtime_tray_presence_boundary_proof_readback = $ResidentRuntimeTrayPresenceBoundaryObserved
    resident_runtime_hotkey_summon_boundary_proof_readback = $ResidentRuntimeHotkeySummonBoundaryObserved
    resident_runtime_overlay_window_boundary_proof_readback = $ResidentRuntimeOverlayWindowBoundaryObserved
    resident_runtime_resident_claim_boundary_proof_readback = $ResidentRuntimeResidentClaimBoundaryObserved
    command_palette_shell_bridge_readback = $CommandPaletteShellBridgeObserved
    command_palette_os_binding_blockers_proof_readback = $CommandPaletteOsBindingObserved
    command_palette_os_binding_candidate_readback = $CommandPaletteOsBindingCandidateObserved
    os_binding_authority_request_readback = $OsBindingAuthorityRequestReadbackObserved
    summon_anywhere_blockers_proof_readback = $SummonAnywhereBlockersProofObserved
    summon_anywhere_first_blocker_family_handoff_readback = $SummonAnywhereBlockersProofFirstFamilyHandoffObserved
    resident_host_runtime_boundary_proof_readback = $ResidentHostRuntimeBoundaryProofObserved
    checkpoint_summon_enablement_gate_handoff_readback = $CheckpointSummonEnablementGateHandoffObserved
    summon_authority_blocker_proof_readback = $SummonAuthorityBlockerProofObserved
    summon_anywhere_family_chain_proof_readback = $SummonAnywhereFamilyChainProofObserved
    process_supervision_boundary_observed = [bool]$ProcessSupervisionBoundary.process_supervision_boundary_observed
    service_activation_plan_observed = [bool]$ProcessSupervisionBoundary.service_activation_plan_observed
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    resident_overlay_activation_authority = $false
    local_process_launch_authority = $false
    process_restart_authority = $false
    process_supervision_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    telemetry_authority = $false
    receipt_write_authority = $false
    denial_receipt_write_authority = $false
    mutation_authority_granted = $false
  }
}

$Payload | ConvertTo-Json -Depth 8
exit 0
