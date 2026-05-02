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
  [int]$SupervisorRunSeconds = 20
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

function Invoke-JsonScript {
  param(
    [Parameter(Mandatory = $true)]
    [string]$PowerShellPath,

    [Parameter(Mandatory = $true)]
    [string]$ScriptPath,

    [string[]]$ScriptArgs = @()
  )

  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
    }
  }

  $Output = & $PowerShellPath -NoProfile -ExecutionPolicy Bypass -File $ScriptPath @ScriptArgs 2>&1
  $ExitCode = $LASTEXITCODE
  $Text = ($Output | ForEach-Object { [string]$_ }) -join "`n"
  $Payload = $null
  try {
    $Payload = $Text | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $Payload = $null
  }

  return [ordered]@{
    exit_code = $ExitCode
    payload = $Payload
    output = $Text
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
$PersistentSupervisionPlanScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-plan.ps1'
$PersistentSupervisionEnablementAuthorityProofScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-enablement-authority-proof.ps1'
$PersistentSupervisionExecutionAuthorityProofScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-execution-authority-proof.ps1'

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
$ProcessSupervisionBoundaryResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $ProcessSupervisionBoundaryScript -ScriptArgs @(
  '-Mode', 'Status',
  '-StartupTimeoutSeconds', [string]$StartupTimeoutSeconds,
  '-ForegroundRunSeconds', '2',
  '-HostLaunchRunSeconds', [string]$HostLaunchRunSeconds,
  '-SupervisorRunSeconds', [string]$SupervisorRunSeconds
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
} elseif ($ResidentRuntimeResidentClaimBoundaryObserved) {
  'stage6_lens_completion_audit'
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
  next_smallest_truthful_gap = $NextSmallestTruthfulGap
  next_smallest_truthful_gap_basis = if ($NextSmallestTruthfulGap -eq 'stage6_lens_completion_audit') {
    'The audit consumes the resident-runtime resident-claim boundary proof: the sixth authority family is now read back as blocked and non-mutating, so the next bounded step is a Stage 6 closure audit/readiness review rather than Stage 7 transition.'
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
  } elseif ($NextSmallestTruthfulGap -eq 'persistent_supervision_resident_claim_authority_boundary') {
    'The audit now consumes the persistent-supervision execution authority proof: the bounded execution grant is readable and reaches the execution route, while persistent supervision remains non-mutating and blocked at resident-claim/runtime readiness.'
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
  evidence = @(
    'docs/canonical/ROADMAP.md#4.12',
    'docs/operations/COMPLETION_LEDGER.md',
    'scripts/lens-stage6-checkpoint.ps1 -Mode Status',
    'scripts/lens-resident-runtime-boundary-proof.ps1 -Mode Status',
    'scripts/lens-process-supervision-authority-boundary-proof.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-plan.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-execution-authority-proof.ps1 -Mode Status',
    '/lens/host/persistent-supervision/enablement',
    '/lens/host/persistent-supervision/enablement/execution',
    '/lens/host/persistent-supervision/enablement/execution/readiness',
    '/lens/status',
    '/lens/resident-surface',
    '/lens/resident-surface/activation',
    '/lens/host/supervision/authority/readiness',
    'scripts/lens-resident-runtime-authority-blockers-proof.ps1 -Mode Status',
    'scripts/lens-resident-runtime-resident-claim-boundary-proof.ps1 -Mode Status'
  )
  governance = [ordered]@{
    read_only_contract = $true
    diagnostic_only = $true
    checkpoint_readback = $true
    process_supervision_authority_boundary_readback = $ProcessSupervisionBoundaryObserved
    persistent_supervision_plan_readback = $PersistentSupervisionPlanObserved
    persistent_supervision_enablement_authority_proof_readback = $PersistentSupervisionEnablementAuthorityProofObserved
    persistent_supervision_execution_authority_proof_readback = $PersistentSupervisionExecutionAuthorityProofObserved
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
