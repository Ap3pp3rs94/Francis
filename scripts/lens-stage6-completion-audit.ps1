param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status'
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

if (-not (Test-Path -LiteralPath $CheckpointScript)) {
  throw "Stage 6 checkpoint script is missing: $CheckpointScript"
}

$PowerShell = (Get-Command pwsh -ErrorAction SilentlyContinue)
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command powershell -ErrorAction Stop
}

$CheckpointJson = & $PowerShell.Source -NoProfile -ExecutionPolicy Bypass -File $CheckpointScript -Mode Status
if ($LASTEXITCODE -ne 0) {
  throw "Stage 6 checkpoint failed with exit code $LASTEXITCODE"
}

$Checkpoint = ($CheckpointJson | Out-String | ConvertFrom-Json)
$ProcessSupervisionBoundaryResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $ProcessSupervisionBoundaryScript -ScriptArgs @(
  '-Mode', 'Status',
  '-StartupTimeoutSeconds', '30',
  '-ForegroundRunSeconds', '2',
  '-HostLaunchRunSeconds', '3',
  '-SupervisorRunSeconds', '20'
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
$Criteria = @($Checkpoint.criteria)
$ReadyCriteria = @($Criteria | Where-Object { [bool]$_.ready })
$BlockedCriteria = @($Criteria | Where-Object { -not [bool]$_.ready })
$Blockers = ConvertTo-StringArray -Value $Checkpoint.blockers
$ReadyToClose = [bool]$Checkpoint.ready_to_close
$BlockedCriterionIds = @($BlockedCriteria | ForEach-Object { [string]$_.id })
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

$NextSmallestTruthfulGap = if ($ReadyToClose) {
  'stage6_ledger_closure'
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
  next_smallest_truthful_gap_basis = if ($NextSmallestTruthfulGap -eq 'resident_supervision_not_persistent') {
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
    process_supervision = [string[]]@(
      $ProcessSupervisionBoundaryBlockers | Where-Object {
        $_ -match 'process_supervision|process_restart|resident_host_process|resident_supervision'
      } | Sort-Object -Unique
    )
    service_activation = [string[]]@(
      $ProcessSupervisionBoundaryBlockers | Where-Object { $_ -match 'service_' } | Sort-Object -Unique
    )
    authority = [string[]]@(
      $Blockers | Where-Object { $_ -match 'authority|not_granted|not_authorized' } | Sort-Object -Unique
    )
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
  evidence = @(
    'docs/canonical/ROADMAP.md#4.12',
    'docs/operations/COMPLETION_LEDGER.md',
    'scripts/lens-stage6-checkpoint.ps1 -Mode Status',
    'scripts/lens-process-supervision-authority-boundary-proof.ps1 -Mode Status',
    '/lens/status',
    '/lens/resident-surface',
    '/lens/resident-surface/activation',
    '/lens/host/supervision/authority/readiness'
  )
  governance = [ordered]@{
    read_only_contract = $true
    diagnostic_only = $true
    checkpoint_readback = $true
    process_supervision_authority_boundary_readback = $ProcessSupervisionBoundaryObserved
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
