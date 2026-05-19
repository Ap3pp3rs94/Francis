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
  if ($IsWindows -or $env:OS -eq 'Windows_NT') {
    try {
      & taskkill.exe /F /T /PID $Process.Id | Out-Null
      return
    } catch {
    }
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
  $ScriptName = [IO.Path]::GetFileNameWithoutExtension($ScriptPath)
  $ProofCaptureRoot = Join-Path $RepoRoot 'data/test_runs/lens-stage6-completion-audit'
  New-Item -ItemType Directory -Path $ProofCaptureRoot -Force | Out-Null
  $CaptureId = [Guid]::NewGuid().ToString('N')
  $StdoutPath = Join-Path $ProofCaptureRoot "$ScriptName-$CaptureId.stdout.json"
  $StderrPath = Join-Path $ProofCaptureRoot "$ScriptName-$CaptureId.stderr.txt"
  $StartInfo.RedirectStandardOutput = $false
  $StartInfo.RedirectStandardError = $false
  $StartInfo.RedirectStandardInput = $false
  $StartInfo.Arguments = '-NoProfile -ExecutionPolicy Bypass -Command ' + (
    Quote-ProcessArgument -Value (
      '& ' + (Quote-ProcessArgument -Value $PowerShellPath) + ' ' + ($ArgumentParts -join ' ') +
      ' > ' + (Quote-ProcessArgument -Value $StdoutPath) +
      ' 2> ' + (Quote-ProcessArgument -Value $StderrPath)
    )
  )
  $StartInfo.FileName = $PowerShellPath

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

  $Text = ''
  if (Test-Path -LiteralPath $StdoutPath -PathType Leaf) {
    $Text = [IO.File]::ReadAllText($StdoutPath)
  }
  $ErrorText = ''
  if (Test-Path -LiteralPath $StderrPath -PathType Leaf) {
    $ErrorText = [IO.File]::ReadAllText($StderrPath)
  }
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
$ResidentSupervisionPersistenceBoundaryProofScript = Join-Path $PSScriptRoot 'lens-resident-supervision-persistence-boundary-proof.ps1'
$HostSupervisionAuthorityRequestProofScript = Join-Path $PSScriptRoot 'lens-host-supervision-authority-request-proof.ps1'
$PersistentSupervisionPlanScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-plan.ps1'
$PersistentSupervisionPrerequisitesProofScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-prerequisites-proof.ps1'
$PersistentSupervisionServiceInstallPlanProofScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-service-install-plan-proof.ps1'
$PersistentSupervisionEnablementAuthorityProofScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-enablement-authority-proof.ps1'
$PersistentSupervisionExecutionAuthorityProofScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-execution-authority-proof.ps1'
$PersistentSupervisionResidentClaimBoundaryProofScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-resident-claim-boundary-proof.ps1'
$PersistentSupervisionEnablementTransitionPlanProofScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-enablement-transition-plan-proof.ps1'
$Stage6PrerequisiteBringupPlanScript = Join-Path $PSScriptRoot 'lens-stage6-prerequisite-bringup-plan.ps1'
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
$ChildStartupTimeoutSeconds = [Math]::Max($StartupTimeoutSeconds, 30)
$ChildHostLaunchRunSeconds = [Math]::Max($HostLaunchRunSeconds, 5)

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
) -TimeoutSeconds ([Math]::Max($ChildProofTimeoutSeconds, 240))
$SummonAuthorityBlockerProof = $SummonAuthorityBlockerProofResult.payload
$SummonAnywhereFamilyChainProofChildTimeoutSeconds = [Math]::Max($ChildProofTimeoutSeconds, 240)
$SummonAnywhereFamilyChainProofChildProofCount = 2
$SummonAnywhereFamilyChainProofTimeoutSeconds = (
  $SummonAnywhereFamilyChainProofChildTimeoutSeconds * $SummonAnywhereFamilyChainProofChildProofCount
) + 60
$SummonAnywhereFamilyChainProofResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $SummonAnywhereFamilyChainProofScript -ScriptArgs @(
  '-Mode', 'Status',
  '-ChildProofTimeoutSeconds', [string]$SummonAnywhereFamilyChainProofChildTimeoutSeconds
) -TimeoutSeconds $SummonAnywhereFamilyChainProofTimeoutSeconds
$SummonAnywhereFamilyChainProof = $SummonAnywhereFamilyChainProofResult.payload
$ResidentHostRuntimeBoundaryProofResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $ResidentHostRuntimeBoundaryProofScript -ScriptArgs @(
  '-Mode', 'Status',
  '-ForegroundRunSeconds', '2',
  '-HostLaunchRunSeconds', [string]$ChildHostLaunchRunSeconds
)
$ResidentHostRuntimeBoundaryProof = $ResidentHostRuntimeBoundaryProofResult.payload
$ResidentHostRuntimeBoundaryProofBlockers = ConvertTo-StringArray -Value $ResidentHostRuntimeBoundaryProof.blockers
$ResidentHostRuntimeBoundaryProofRecommendedHandoff = $ResidentHostRuntimeBoundaryProof.recommended_handoff
$ResidentHostRuntimeBoundaryProofObserved = (
  [int]$ResidentHostRuntimeBoundaryProofResult.exit_code -eq 0 -and
  [string]$ResidentHostRuntimeBoundaryProof.kind -eq 'lens.resident_host.runtime_blocker_boundary.proof' -and
  [bool]$ResidentHostRuntimeBoundaryProof.ok -and
  [string]$ResidentHostRuntimeBoundaryProof.status -eq 'proof_passed' -and
  [string]$ResidentHostRuntimeBoundaryProof.previous_next_smallest_truthful_gap -eq 'resident_host_runtime_blocker_boundary' -and
  [string]$ResidentHostRuntimeBoundaryProof.next_smallest_truthful_gap -eq 'resident_host_process_not_supervised' -and
  [string]$ResidentHostRuntimeBoundaryProof.authority_required -eq 'process_supervision_authority' -and
  -not [bool]$ResidentHostRuntimeBoundaryProof.authority_granted -and
  [string]$ResidentHostRuntimeBoundaryProofRecommendedHandoff.authority_required -eq 'process_supervision_authority' -and
  -not [bool]$ResidentHostRuntimeBoundaryProofRecommendedHandoff.authority_granted
)
$ProcessSupervisionBoundaryResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $ProcessSupervisionBoundaryScript -ScriptArgs @(
  '-Mode', 'Status',
  '-StartupTimeoutSeconds', [string]$ChildStartupTimeoutSeconds,
  '-ForegroundRunSeconds', '2',
  '-HostLaunchRunSeconds', [string]$ChildHostLaunchRunSeconds,
  '-SupervisorRunSeconds', [string]$SupervisorRunSeconds,
  '-ChildProofTimeoutSeconds', [string]$ChildProofTimeoutSeconds
)
$ProcessSupervisionBoundary = $ProcessSupervisionBoundaryResult.payload
$ProcessSupervisionBoundaryBlockers = ConvertTo-StringArray -Value $ProcessSupervisionBoundary.blockers
$ProcessSupervisionBoundaryObserved = (
  [int]$ProcessSupervisionBoundaryResult.exit_code -eq 0 -and
  [string]$ProcessSupervisionBoundary.kind -eq 'lens.process_supervision_authority_boundary.proof' -and
  [bool]$ProcessSupervisionBoundary.ok -and
  [string]$ProcessSupervisionBoundary.authority_required -eq 'process_supervision_and_service_control' -and
  -not [bool]$ProcessSupervisionBoundary.authority_granted -and
  [string]$ProcessSupervisionBoundary.process_supervision_authority_required -eq 'process_supervision_authority' -and
  -not [bool]$ProcessSupervisionBoundary.process_supervision_authority_granted -and
  [string]$ProcessSupervisionBoundary.process_restart_authority_required -eq 'process_restart_authority' -and
  -not [bool]$ProcessSupervisionBoundary.process_restart_authority_granted -and
  [string]$ProcessSupervisionBoundary.service_install_authority_required -eq 'service_install_authority' -and
  -not [bool]$ProcessSupervisionBoundary.service_install_authority_granted -and
  [string]$ProcessSupervisionBoundary.service_control_authority_required -eq 'service_control_authority' -and
  -not [bool]$ProcessSupervisionBoundary.service_control_authority_granted -and
  [bool]$ProcessSupervisionBoundary.process_supervision_boundary_observed -and
  [bool]$ProcessSupervisionBoundary.service_activation_plan_observed
)
$ResidentHostProcessSupervisionBlockerProofResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $ResidentHostProcessSupervisionBlockerProofScript -ScriptArgs @(
  '-Mode', 'Status',
  '-StartupTimeoutSeconds', [string]$ChildStartupTimeoutSeconds,
  '-ForegroundRunSeconds', '2',
  '-HostLaunchRunSeconds', [string]$ChildHostLaunchRunSeconds,
  '-SupervisorRunSeconds', [string]$SupervisorRunSeconds,
  '-ChildProofTimeoutSeconds', [string]$ChildProofTimeoutSeconds
)
$ResidentHostProcessSupervisionBlockerProof = $ResidentHostProcessSupervisionBlockerProofResult.payload
$ResidentHostProcessSupervisionBlockerProofBlockers = ConvertTo-StringArray -Value $ResidentHostProcessSupervisionBlockerProof.blockers
$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff = $ResidentHostProcessSupervisionBlockerProof.recommended_handoff
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
  [string]$ResidentHostProcessSupervisionBlockerProof.authority_required -eq 'none_new_stage6_completion_audit' -and
  -not [bool]$ResidentHostProcessSupervisionBlockerProof.authority_granted -and
  [string]$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff.authority_required -eq 'none_new_stage6_completion_audit' -and
  -not [bool]$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff.authority_granted -and
  $ResidentHostProcessSupervisionBlockerProofBlockers -contains 'resident_host_process_not_supervised' -and
  $ResidentHostProcessSupervisionBlockerProofBlockers -contains 'process_supervision_authority_not_granted' -and
  $ResidentHostProcessSupervisionBlockerProofBlockers -contains 'process_restart_authority_not_granted' -and
  $ResidentHostProcessSupervisionBlockerProofBlockers -contains 'service_install_authority_not_granted' -and
  $ResidentHostProcessSupervisionBlockerProofBlockers -contains 'service_control_authority_not_granted'
)
$ResidentSupervisionPersistenceBoundaryProofOuterTimeoutSeconds = [Math]::Min($ChildProofTimeoutSeconds, 240)
$ResidentSupervisionPersistenceBoundaryProofChildTimeoutSeconds = [Math]::Min($ChildProofTimeoutSeconds, 180)
$ResidentSupervisionPersistenceBoundaryProofResult = Invoke-JsonScript `
  -PowerShellPath $PowerShell.Source `
  -ScriptPath $ResidentSupervisionPersistenceBoundaryProofScript `
  -ScriptArgs @(
    '-Mode',
    'Status',
    '-ForegroundRunSeconds',
    '3',
    '-HostLaunchRunSeconds',
    '8',
    '-ResidentCandidateRunSeconds',
    '8',
    '-ChildProofTimeoutSeconds',
    [string]$ResidentSupervisionPersistenceBoundaryProofChildTimeoutSeconds
  ) `
  -TimeoutSeconds $ResidentSupervisionPersistenceBoundaryProofOuterTimeoutSeconds
$ResidentSupervisionPersistenceBoundaryProof = $ResidentSupervisionPersistenceBoundaryProofResult.payload
$ResidentSupervisionPersistenceBoundaryProofBlockers = ConvertTo-StringArray -Value $ResidentSupervisionPersistenceBoundaryProof.blockers
$ResidentSupervisionPersistenceBoundaryProofGovernance = $ResidentSupervisionPersistenceBoundaryProof.governance
$ResidentSupervisionPersistenceBoundaryProofObserved = (
  [int]$ResidentSupervisionPersistenceBoundaryProofResult.exit_code -eq 0 -and
  [string]$ResidentSupervisionPersistenceBoundaryProof.kind -eq 'lens.resident_supervision.persistence_boundary.proof' -and
  [bool]$ResidentSupervisionPersistenceBoundaryProof.ok -and
  [string]$ResidentSupervisionPersistenceBoundaryProof.status -eq 'proof_passed' -and
  [string]$ResidentSupervisionPersistenceBoundaryProof.acceptance_criterion -eq 'system_resident_presence' -and
  [string]$ResidentSupervisionPersistenceBoundaryProof.previous_next_smallest_truthful_gap -eq 'resident_host_process_not_supervised' -and
  [string]$ResidentSupervisionPersistenceBoundaryProof.consumed_resident_candidate_next_smallest_truthful_gap -eq 'resident_supervision_not_persistent' -and
  [string]$ResidentSupervisionPersistenceBoundaryProof.route_next_smallest_truthful_gap -eq 'persistent_supervision_authority_not_granted' -and
  [string]$ResidentSupervisionPersistenceBoundaryProof.next_smallest_truthful_gap -eq 'persistent_supervision_authority_not_granted' -and
  [string]$ResidentSupervisionPersistenceBoundaryProof.recommended_next_slice -eq 'prove_persistent_supervision_enablement_authority_after_candidate_handoff' -and
  [string]$ResidentSupervisionPersistenceBoundaryProof.recommended_proof_script -eq 'scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status' -and
  [string]$ResidentSupervisionPersistenceBoundaryProof.recommended_route -eq '/lens/host/persistent-supervision/enablement/authority' -and
  [string]$ResidentSupervisionPersistenceBoundaryProof.recommended_readiness_route -eq '/lens/host/persistent-supervision/enablement/authority/readiness' -and
  [bool]$ResidentSupervisionPersistenceBoundaryProof.resident_candidate_boundary_proof_observed -and
  [bool]$ResidentSupervisionPersistenceBoundaryProof.persistent_supervision_plan_candidate_readback_observed -and
  [bool]$ResidentSupervisionPersistenceBoundaryProof.persistent_supervision_enablement_candidate_readback_observed -and
  [bool]$ResidentSupervisionPersistenceBoundaryProof.resident_dependency_candidate_readback_observed -and
  [bool]$ResidentSupervisionPersistenceBoundaryProof.route_blocking_preserved -and
  [bool]$ResidentSupervisionPersistenceBoundaryProof.side_effects_bounded -and
  [bool]$ResidentSupervisionPersistenceBoundaryProof.resident_runtime_candidate_supervised -and
  -not [bool]$ResidentSupervisionPersistenceBoundaryProof.resident_supervised_runtime -and
  [string]$ResidentSupervisionPersistenceBoundaryProof.resident_host_process_requirement_state -eq 'resident_candidate_observed_not_persistent' -and
  [string]$ResidentSupervisionPersistenceBoundaryProof.resident_host_process_blocker -eq 'resident_supervision_not_persistent' -and
  [string]$ResidentSupervisionPersistenceBoundaryProof.authority_required -eq 'persistent_process_supervision_authority' -and
  -not [bool]$ResidentSupervisionPersistenceBoundaryProof.authority_granted -and
  $ResidentSupervisionPersistenceBoundaryProofBlockers -contains 'resident_supervision_not_persistent' -and
  $ResidentSupervisionPersistenceBoundaryProofBlockers -contains 'persistent_supervision_authority_not_granted' -and
  $ResidentSupervisionPersistenceBoundaryProofBlockers -contains 'persistent_process_supervision_authority_required' -and
  [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.diagnostic_only -and
  [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.route_readback_contract -and
  [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.wraps_resident_host_runtime_boundary_proof -and
  [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.wraps_persistent_supervision_plan_route -and
  [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.wraps_persistent_supervision_enablement_route -and
  [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.bounded_local_process_launch -and
  [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.temporary_runtime_state_write -and
  -not [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.product_execution_authority -and
  -not [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.execution_authority -and
  -not [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.approval_decision_authority -and
  -not [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.api_local_process_launch_authority -and
  -not [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.process_supervision_authority -and
  -not [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.process_restart_authority -and
  -not [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.service_install_authority -and
  -not [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.service_control_authority -and
  -not [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.memory_write -and
  -not [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.receipt_write_authority -and
  -not [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.resident_claim_authority -and
  -not [bool]$ResidentSupervisionPersistenceBoundaryProofGovernance.mutation_authority_granted
)
$HostSupervisionAuthorityRequestProofResult = Invoke-JsonScript `
  -PowerShellPath $PowerShell.Source `
  -ScriptPath $HostSupervisionAuthorityRequestProofScript `
  -ScriptArgs @('-Mode', 'Status')
$HostSupervisionAuthorityRequestProof = $HostSupervisionAuthorityRequestProofResult.payload
$HostSupervisionAuthorityRequestProofBlockers = ConvertTo-StringArray -Value $HostSupervisionAuthorityRequestProof.blockers
$HostSupervisionAuthorityRequestProofGovernance = $HostSupervisionAuthorityRequestProof.governance
$HostSupervisionAuthorityRequestProofRuntimeFiles = $HostSupervisionAuthorityRequestProof.runtime_files
$HostSupervisionAuthorityRequestProofObserved = (
  [int]$HostSupervisionAuthorityRequestProofResult.exit_code -eq 0 -and
  [string]$HostSupervisionAuthorityRequestProof.kind -eq 'lens.host.supervision_authority_exact_approval_request.proof' -and
  [bool]$HostSupervisionAuthorityRequestProof.ok -and
  [string]$HostSupervisionAuthorityRequestProof.status -eq 'proof_passed' -and
  [bool]$HostSupervisionAuthorityRequestProof.authority_granted -and
  [bool]$HostSupervisionAuthorityRequestProof.grant_applied -and
  -not [bool]$HostSupervisionAuthorityRequestProof.executed -and
  -not [bool]$HostSupervisionAuthorityRequestProof.supervision_ready -and
  -not [bool]$HostSupervisionAuthorityRequestProof.resident_claim_allowed -and
  [bool]$HostSupervisionAuthorityRequestProof.process_supervision_authority -and
  [bool]$HostSupervisionAuthorityRequestProof.process_restart_authority -and
  [bool]$HostSupervisionAuthorityRequestProof.service_install_authority -and
  [bool]$HostSupervisionAuthorityRequestProof.service_control_authority -and
  [bool]$HostSupervisionAuthorityRequestProof.receipt_write_authority -and
  [bool]$HostSupervisionAuthorityRequestProof.resident_claim_authority -and
  -not [bool]$HostSupervisionAuthorityRequestProof.memory_write -and
  [string]$HostSupervisionAuthorityRequestProof.next_smallest_truthful_gap -eq 'persistent_supervision_required_prerequisites_missing' -and
  $HostSupervisionAuthorityRequestProofBlockers -contains 'persistent_supervision_required_prerequisites_missing' -and
  -not [bool]$HostSupervisionAuthorityRequestProofRuntimeFiles.lens_host_status -and
  -not [bool]$HostSupervisionAuthorityRequestProofRuntimeFiles.lens_host_pid -and
  -not [bool]$HostSupervisionAuthorityRequestProofRuntimeFiles.lens_host_supervisor_status -and
  [bool]$HostSupervisionAuthorityRequestProofGovernance.diagnostic_only -and
  [bool]$HostSupervisionAuthorityRequestProofGovernance.api_route_proof -and
  [bool]$HostSupervisionAuthorityRequestProofGovernance.approval_request_write -and
  [bool]$HostSupervisionAuthorityRequestProofGovernance.test_fixture_approval_decisions -and
  -not [bool]$HostSupervisionAuthorityRequestProofGovernance.approval_decision_authority -and
  -not [bool]$HostSupervisionAuthorityRequestProofGovernance.execution_authority -and
  -not [bool]$HostSupervisionAuthorityRequestProofGovernance.local_process_launch_authority -and
  -not [bool]$HostSupervisionAuthorityRequestProofGovernance.persistent_supervision_enablement_authority -and
  -not [bool]$HostSupervisionAuthorityRequestProofGovernance.service_config_write_authority -and
  -not [bool]$HostSupervisionAuthorityRequestProofGovernance.persistent_supervision_execution_authority -and
  -not [bool]$HostSupervisionAuthorityRequestProofGovernance.memory_write -and
  -not [bool]$HostSupervisionAuthorityRequestProofGovernance.mutation_authority_granted
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
$PersistentSupervisionPrerequisitesProofChildTimeoutSeconds = [Math]::Min($ChildProofTimeoutSeconds, 240)
$PersistentSupervisionPrerequisitesProofTimeoutSeconds = (
  $PersistentSupervisionPrerequisitesProofChildTimeoutSeconds
) + 60
$PersistentSupervisionPrerequisitesProofResult = Invoke-JsonScript `
  -PowerShellPath $PowerShell.Source `
  -ScriptPath $PersistentSupervisionPrerequisitesProofScript `
  -ScriptArgs @(
    '-Mode',
    'Status',
    '-ChildProofTimeoutSeconds',
    [string]$PersistentSupervisionPrerequisitesProofChildTimeoutSeconds
  ) `
  -TimeoutSeconds $PersistentSupervisionPrerequisitesProofTimeoutSeconds
$PersistentSupervisionPrerequisitesProof = $PersistentSupervisionPrerequisitesProofResult.payload
$PersistentSupervisionPrerequisitesProofGovernance = $PersistentSupervisionPrerequisitesProof.governance
$PersistentSupervisionPrerequisitesRequiredBeforeEnable = ConvertTo-StringArray -Value $PersistentSupervisionPrerequisitesProof.required_before_enable
$PersistentSupervisionPrerequisitesMissingRequiredBeforeEnable = ConvertTo-StringArray -Value $PersistentSupervisionPrerequisitesProof.missing_required_before_enable
$PersistentSupervisionPrerequisitesFirstMissingRequiredBeforeEnable = [string]$PersistentSupervisionPrerequisitesProof.first_missing_required_before_enable
$PersistentSupervisionPrerequisitesFirstMissingRequirementHandoff = $PersistentSupervisionPrerequisitesProof.first_missing_requirement_handoff
$PersistentSupervisionPrerequisitesProofObserved = (
  [int]$PersistentSupervisionPrerequisitesProofResult.exit_code -eq 0 -and
  [string]$PersistentSupervisionPrerequisitesProof.kind -eq 'lens.persistent_supervision.prerequisites.proof' -and
  [bool]$PersistentSupervisionPrerequisitesProof.ok -and
  [string]$PersistentSupervisionPrerequisitesProof.status -eq 'proof_passed' -and
  [string]$PersistentSupervisionPrerequisitesProof.acceptance_criterion -eq 'system_resident_presence' -and
  [string]$PersistentSupervisionPrerequisitesProof.plan_route -eq '/lens/host/persistent-supervision' -and
  [string]$PersistentSupervisionPrerequisitesProof.enablement_route -eq '/lens/host/persistent-supervision/enablement' -and
  [string]$PersistentSupervisionPrerequisitesProof.route_next_smallest_truthful_gap -eq 'persistent_supervision_authority_not_granted' -and
  [string]$PersistentSupervisionPrerequisitesProof.guard_next_smallest_truthful_gap -eq 'persistent_supervision_required_prerequisites_missing' -and
  [string]$PersistentSupervisionPrerequisitesProof.summon_family_contract_next_smallest_truthful_gap -eq 'persistent_supervision_required_prerequisites_missing' -and
  [string]$PersistentSupervisionPrerequisitesProof.next_smallest_truthful_gap -eq 'persistent_supervision_required_prerequisites_missing' -and
  [string]$PersistentSupervisionPrerequisitesProof.authority_required -eq 'resident_host_process_tray_hotkey_overlay_and_summon_prerequisites' -and
  -not [bool]$PersistentSupervisionPrerequisitesProof.authority_granted -and
  [bool]$PersistentSupervisionPrerequisitesProof.persistent_supervision_plan_readback_observed -and
  [bool]$PersistentSupervisionPrerequisitesProof.persistent_supervision_enablement_readback_observed -and
  [bool]$PersistentSupervisionPrerequisitesProof.required_before_enable_observed -and
  [bool]$PersistentSupervisionPrerequisitesProof.missing_required_before_enable_observed -and
  [bool]$PersistentSupervisionPrerequisitesProof.required_before_enable_guard_observed -and
  [bool]$PersistentSupervisionPrerequisitesProof.dependency_readback_observed -and
  [bool]$PersistentSupervisionPrerequisitesProof.summon_family_contract_observed -and
  [bool]$PersistentSupervisionPrerequisitesProof.prerequisites_mapped_to_summon_family_contract -and
  [bool]$PersistentSupervisionPrerequisitesProof.first_missing_requirement_proof_observed -and
  [bool]$PersistentSupervisionPrerequisitesProof.first_missing_requirement_side_effects_bounded -and
  [bool]$PersistentSupervisionPrerequisitesProof.lens_status_operator_readback_observed -and
  [bool]$PersistentSupervisionPrerequisitesProof.side_effects_denied -and
  [bool]$PersistentSupervisionPrerequisitesProof.side_effects_bounded -and
  $PersistentSupervisionPrerequisitesRequiredBeforeEnable -contains 'resident_host_process' -and
  $PersistentSupervisionPrerequisitesRequiredBeforeEnable -contains 'tray_presence' -and
  $PersistentSupervisionPrerequisitesRequiredBeforeEnable -contains 'global_hotkey_binding' -and
  $PersistentSupervisionPrerequisitesRequiredBeforeEnable -contains 'overlay_window' -and
  $PersistentSupervisionPrerequisitesRequiredBeforeEnable -contains 'summon_binding' -and
  $PersistentSupervisionPrerequisitesMissingRequiredBeforeEnable -contains 'resident_host_process' -and
  $PersistentSupervisionPrerequisitesMissingRequiredBeforeEnable -contains 'tray_presence' -and
  $PersistentSupervisionPrerequisitesMissingRequiredBeforeEnable -contains 'global_hotkey_binding' -and
  $PersistentSupervisionPrerequisitesMissingRequiredBeforeEnable -contains 'overlay_window' -and
  $PersistentSupervisionPrerequisitesMissingRequiredBeforeEnable -contains 'summon_binding' -and
  [bool]$PersistentSupervisionPrerequisitesProofGovernance.diagnostic_only -and
  -not [bool]$PersistentSupervisionPrerequisitesProofGovernance.read_only_contract -and
  [bool]$PersistentSupervisionPrerequisitesProofGovernance.route_readback_contract -and
  [bool]$PersistentSupervisionPrerequisitesProofGovernance.wraps_persistent_supervision_plan_route -and
  [bool]$PersistentSupervisionPrerequisitesProofGovernance.wraps_persistent_supervision_enablement_route -and
  [bool]$PersistentSupervisionPrerequisitesProofGovernance.wraps_lens_status -and
  [bool]$PersistentSupervisionPrerequisitesProofGovernance.uses_summon_family_contract_readback -and
  -not [bool]$PersistentSupervisionPrerequisitesProofGovernance.wraps_summon_anywhere_family_chain_proof -and
  [bool]$PersistentSupervisionPrerequisitesProofGovernance.wraps_first_missing_requirement_proof -and
  [bool]$PersistentSupervisionPrerequisitesProofGovernance.bounded_local_process_launch -and
  [bool]$PersistentSupervisionPrerequisitesProofGovernance.bounded_process_launch -and
  [bool]$PersistentSupervisionPrerequisitesProofGovernance.temporary_runtime_state_write -and
  -not [bool]$PersistentSupervisionPrerequisitesProofGovernance.product_execution_authority -and
  -not [bool]$PersistentSupervisionPrerequisitesProofGovernance.execution_authority -and
  -not [bool]$PersistentSupervisionPrerequisitesProofGovernance.approval_decision_authority -and
  [bool]$PersistentSupervisionPrerequisitesProofGovernance.local_process_launch_authority -and
  -not [bool]$PersistentSupervisionPrerequisitesProofGovernance.api_local_process_launch_authority -and
  -not [bool]$PersistentSupervisionPrerequisitesProofGovernance.process_supervision_authority -and
  -not [bool]$PersistentSupervisionPrerequisitesProofGovernance.persistent_supervision_enablement_authority -and
  -not [bool]$PersistentSupervisionPrerequisitesProofGovernance.persistent_supervision_execution_authority -and
  -not [bool]$PersistentSupervisionPrerequisitesProofGovernance.service_config_write_authority -and
  -not [bool]$PersistentSupervisionPrerequisitesProofGovernance.summon_authority -and
  -not [bool]$PersistentSupervisionPrerequisitesProofGovernance.memory_write -and
  -not [bool]$PersistentSupervisionPrerequisitesProofGovernance.resident_claim_authority -and
  -not [bool]$PersistentSupervisionPrerequisitesProofGovernance.mutation_authority_granted
)
$Stage6PrerequisiteBringupPlanResult = Invoke-JsonScript `
  -PowerShellPath $PowerShell.Source `
  -ScriptPath $Stage6PrerequisiteBringupPlanScript `
  -ScriptArgs @('-Mode', 'Status')
$Stage6PrerequisiteBringupPlan = $Stage6PrerequisiteBringupPlanResult.payload
$Stage6PrerequisiteBringupPlanGovernance = $Stage6PrerequisiteBringupPlan.governance
$Stage6PrerequisiteBringupPlanRequiredBeforeEnable = ConvertTo-StringArray -Value $Stage6PrerequisiteBringupPlan.required_before_enable
$Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable = ConvertTo-StringArray -Value $Stage6PrerequisiteBringupPlan.missing_required_before_enable
$Stage6PrerequisiteBringupPlanNextOperatorAction = $Stage6PrerequisiteBringupPlan.next_operator_action
$Stage6PrerequisiteBringupPlanNextOperatorCommand = $Stage6PrerequisiteBringupPlan.next_operator_command
$Stage6PrerequisiteBringupPlanCommandAvailability = $Stage6PrerequisiteBringupPlan.operator_sequence_command_availability
$Stage6PrerequisiteBringupPlanAllowedFirstMissingTruthfulGaps = @(
  'resident_host_process_not_supervised',
  'resident_supervision_not_persistent'
)
$Stage6PrerequisiteBringupPlanRequiredBeforeEnableContractObserved = (
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'resident_host_process' -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'tray_presence' -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'global_hotkey_binding' -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'overlay_window' -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'summon_binding'
)
$Stage6PrerequisiteBringupPlanReadOnlyGovernanceObserved = (
  [bool]$Stage6PrerequisiteBringupPlanGovernance.read_only_contract -and
  [bool]$Stage6PrerequisiteBringupPlanGovernance.diagnostic_only -and
  [bool]$Stage6PrerequisiteBringupPlanGovernance.plan_only -and
  [bool]$Stage6PrerequisiteBringupPlanGovernance.requires_explicit_operator_execution -and
  [bool]$Stage6PrerequisiteBringupPlanGovernance.request_next_mode_available -and
  [bool]$Stage6PrerequisiteBringupPlanGovernance.grant_next_mode_available -and
  [bool]$Stage6PrerequisiteBringupPlanGovernance.execute_next_mode_available -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.run_mode_available -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.approval_request_write -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.authority_grant_receipt_write -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.execution_receipt_write -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.would_execute -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.would_mutate -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.execution_authority -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.local_process_launch_authority -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.process_supervision_authority -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.service_install_authority -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.service_control_authority -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.tray_registration_authority -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.hotkey_registration_authority -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.overlay_control_authority -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.summon_authority -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.memory_write -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.receipt_write_authority -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.resident_claim_authority -and
  -not [bool]$Stage6PrerequisiteBringupPlanGovernance.mutation_authority_granted
)
$Stage6PrerequisiteBringupPlanMissingPrerequisitesObserved = (
  [string]$Stage6PrerequisiteBringupPlan.status -eq 'blocked' -and
  [string]$Stage6PrerequisiteBringupPlan.current_truthful_gap -eq 'persistent_supervision_required_prerequisites_missing' -and
  [string]$Stage6PrerequisiteBringupPlan.current_truthful_gap_basis -eq 'missing_required_before_enable' -and
  [string]$Stage6PrerequisiteBringupPlan.current_first_missing_requirement -eq 'resident_host_process' -and
  $Stage6PrerequisiteBringupPlanAllowedFirstMissingTruthfulGaps -contains [string]$Stage6PrerequisiteBringupPlan.current_first_missing_truthful_gap -and
  -not [bool]$Stage6PrerequisiteBringupPlan.required_before_enable_ready -and
  [string]$Stage6PrerequisiteBringupPlan.next_operator_action_requirement -eq 'resident_host_process' -and
  [string]$Stage6PrerequisiteBringupPlanNextOperatorAction.id -eq 'request_resident_runtime_execution_authority' -and
  [string]$Stage6PrerequisiteBringupPlanNextOperatorAction.route -eq '/lens/resident-runtime/authority-grant/request' -and
  [string]$Stage6PrerequisiteBringupPlanNextOperatorAction.approval_action -eq 'lens.resident_runtime.execution_authority' -and
  -not [bool]$Stage6PrerequisiteBringupPlanNextOperatorAction.script_would_execute -and
  -not [bool]$Stage6PrerequisiteBringupPlanNextOperatorAction.script_would_mutate -and
  [string]$Stage6PrerequisiteBringupPlanNextOperatorCommand.mode -eq 'RequestNext' -and
  [bool]$Stage6PrerequisiteBringupPlanNextOperatorCommand.requires_confirmation -and
  -not [bool]$Stage6PrerequisiteBringupPlanNextOperatorCommand.requires_approval_id -and
  [int]$Stage6PrerequisiteBringupPlanCommandAvailability.available_now_count -eq 1 -and
  [int]$Stage6PrerequisiteBringupPlanCommandAvailability.preview_only_count -eq 4 -and
  [bool]$Stage6PrerequisiteBringupPlanCommandAvailability.truthful -and
  $Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable -contains 'resident_host_process' -and
  $Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable -contains 'tray_presence' -and
  $Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable -contains 'global_hotkey_binding' -and
  $Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable -contains 'overlay_window' -and
  $Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable -contains 'summon_binding'
)
$Stage6PrerequisiteBringupPlanAppliedEnablementObserved = (
  [string]$Stage6PrerequisiteBringupPlan.status -eq 'persistent_supervision_enablement_applied' -and
  [string]$Stage6PrerequisiteBringupPlan.current_truthful_gap -eq 'persistent_supervision_execution_boundary' -and
  [string]$Stage6PrerequisiteBringupPlan.current_truthful_gap_basis -eq 'persistent_supervision_enablement_execution_receipt.post_plan.next_smallest_truthful_gap' -and
  [string]$Stage6PrerequisiteBringupPlan.current_first_missing_requirement -eq '' -and
  [string]$Stage6PrerequisiteBringupPlan.current_first_missing_truthful_gap -eq '' -and
  [bool]$Stage6PrerequisiteBringupPlan.required_before_enable_ready -and
  @($Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable).Count -eq 0 -and
  [string]$Stage6PrerequisiteBringupPlan.next_operator_action_requirement -eq 'persistent_supervision_enablement_receipt' -and
  [string]$Stage6PrerequisiteBringupPlanNextOperatorAction.id -eq 'review_persistent_supervision_enablement_receipt' -and
  [string]$Stage6PrerequisiteBringupPlanNextOperatorAction.route -eq '/lens/host/persistent-supervision/enablement/executions' -and
  [string]$Stage6PrerequisiteBringupPlanNextOperatorAction.method -eq 'GET' -and
  -not [bool]$Stage6PrerequisiteBringupPlanNextOperatorAction.operator_supplied_values_required -and
  -not [bool]$Stage6PrerequisiteBringupPlanNextOperatorAction.script_would_execute -and
  -not [bool]$Stage6PrerequisiteBringupPlanNextOperatorAction.script_would_mutate -and
  [string]$Stage6PrerequisiteBringupPlanNextOperatorCommand.mode -eq 'Status' -and
  -not [bool]$Stage6PrerequisiteBringupPlanNextOperatorCommand.requires_confirmation -and
  -not [bool]$Stage6PrerequisiteBringupPlanNextOperatorCommand.requires_approval_id -and
  [int]$Stage6PrerequisiteBringupPlanCommandAvailability.available_now_count -eq 1 -and
  [int]$Stage6PrerequisiteBringupPlanCommandAvailability.preview_only_count -eq 0 -and
  [bool]$Stage6PrerequisiteBringupPlanCommandAvailability.truthful
)
$Stage6PrerequisiteBringupPlanObserved = (
  [int]$Stage6PrerequisiteBringupPlanResult.exit_code -eq 0 -and
  [string]$Stage6PrerequisiteBringupPlan.kind -eq 'lens.stage6.prerequisite_bringup.plan' -and
  [bool]$Stage6PrerequisiteBringupPlan.ok -and
  [string]$Stage6PrerequisiteBringupPlan.stage_state -eq 'active' -and
  -not [bool]$Stage6PrerequisiteBringupPlan.ready_to_close -and
  [string]$Stage6PrerequisiteBringupPlan.acceptance_criterion -eq 'system_resident_presence' -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnableContractObserved -and
  $Stage6PrerequisiteBringupPlanReadOnlyGovernanceObserved -and
  ($Stage6PrerequisiteBringupPlanMissingPrerequisitesObserved -or $Stage6PrerequisiteBringupPlanAppliedEnablementObserved)
)
$PersistentSupervisionServiceInstallPlanProofResult = Invoke-JsonScript `
  -PowerShellPath $PowerShell.Source `
  -ScriptPath $PersistentSupervisionServiceInstallPlanProofScript `
  -ScriptArgs @('-Mode', 'Status')
$PersistentSupervisionServiceInstallPlanProof = $PersistentSupervisionServiceInstallPlanProofResult.payload
$PersistentSupervisionServiceInstallPlanProofGovernance = $PersistentSupervisionServiceInstallPlanProof.governance
$PersistentSupervisionServiceInstallPlanProofBlockedBy = ConvertTo-StringArray -Value $PersistentSupervisionServiceInstallPlanProof.blocked_by
$PersistentSupervisionServiceInstallPlanProofRequiredBeforeEnable = ConvertTo-StringArray -Value $PersistentSupervisionServiceInstallPlanProof.required_before_enable
$PersistentSupervisionServiceInstallPlanProofWindowsServiceSupported = [bool]$PersistentSupervisionServiceInstallPlanProof.windows_service_supported
$PersistentSupervisionServiceInstallPlanProofWindowsPlanObserved = (
  $PersistentSupervisionServiceInstallPlanProofWindowsServiceSupported -and
  [string]$PersistentSupervisionServiceInstallPlanProof.service_plan_status -eq 'blocked' -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProof.service_plan_ready -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProof.service_plan_would_install -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProof.service_plan_would_start -and
  $PersistentSupervisionServiceInstallPlanProofBlockedBy -contains 'installable_false' -and
  $PersistentSupervisionServiceInstallPlanProofBlockedBy -contains 'install_authority_false' -and
  $PersistentSupervisionServiceInstallPlanProofBlockedBy -contains 'service_install_authority_false' -and
  $PersistentSupervisionServiceInstallPlanProofBlockedBy -contains 'service_control_authority_false' -and
  [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.wraps_service_install_plan
)
$PersistentSupervisionServiceInstallPlanProofUnsupportedPlatformObserved = (
  -not $PersistentSupervisionServiceInstallPlanProofWindowsServiceSupported -and
  [string]$PersistentSupervisionServiceInstallPlanProof.service_plan_status -eq 'unsupported_platform' -and
  $PersistentSupervisionServiceInstallPlanProofBlockedBy -contains 'unsupported_platform' -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.wraps_service_install_plan
)
$PersistentSupervisionServiceInstallPlanProofObserved = (
  [int]$PersistentSupervisionServiceInstallPlanProofResult.exit_code -eq 0 -and
  [string]$PersistentSupervisionServiceInstallPlanProof.kind -eq 'lens.host.persistent_supervision_service_install_plan.proof' -and
  [bool]$PersistentSupervisionServiceInstallPlanProof.ok -and
  [string]$PersistentSupervisionServiceInstallPlanProof.status -eq 'proof_passed' -and
  [string]$PersistentSupervisionServiceInstallPlanProof.service_config -eq 'config/runtime/services/lens-host.json' -and
  [string]$PersistentSupervisionServiceInstallPlanProof.service_install_script -eq 'scripts/service-install.ps1' -and
  [string]$PersistentSupervisionServiceInstallPlanProof.service_name -eq 'Francis-LensHost' -and
  (
    $PersistentSupervisionServiceInstallPlanProofWindowsPlanObserved -or
    $PersistentSupervisionServiceInstallPlanProofUnsupportedPlatformObserved
  ) -and
  [bool]$PersistentSupervisionServiceInstallPlanProof.process_supervision_enabled -and
  [bool]$PersistentSupervisionServiceInstallPlanProof.persistent_supervision_enabled -and
  [bool]$PersistentSupervisionServiceInstallPlanProof.persistent_supervision_config_gate_enabled -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProof.persistent_supervision_enablement_disabled -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProof.installable -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProof.install_authority -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProof.service_install_authority -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProof.service_control_authority -and
  [string]$PersistentSupervisionServiceInstallPlanProof.authority_required -eq 'install_service_install_and_service_control_authority' -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProof.authority_granted -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProof.wrapper_created_by_proof -and
  [string]$PersistentSupervisionServiceInstallPlanProof.next_smallest_truthful_gap -eq 'persistent_supervision_required_prerequisites_missing' -and
  $PersistentSupervisionServiceInstallPlanProofRequiredBeforeEnable -contains 'resident_host_process' -and
  $PersistentSupervisionServiceInstallPlanProofRequiredBeforeEnable -contains 'tray_presence' -and
  $PersistentSupervisionServiceInstallPlanProofRequiredBeforeEnable -contains 'global_hotkey_binding' -and
  $PersistentSupervisionServiceInstallPlanProofRequiredBeforeEnable -contains 'overlay_window' -and
  $PersistentSupervisionServiceInstallPlanProofRequiredBeforeEnable -contains 'summon_binding' -and
  [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.diagnostic_only -and
  [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.read_only_contract -and
  [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.service_config_readback -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.execution_authority -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.approval_decision_authority -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.local_process_launch_authority -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.process_supervision_authority -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.process_restart_authority -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.service_install_authority -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.service_control_authority -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.persistent_supervision_enablement_authority -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.persistent_supervision_execution_authority -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.service_config_write_authority -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.memory_write -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.receipt_write_authority -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.resident_claim_authority -and
  -not [bool]$PersistentSupervisionServiceInstallPlanProofGovernance.mutation_authority_granted
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
  $PersistentSupervisionResidentClaimBoundaryBlockers -contains 'persistent_supervision_required_prerequisites_missing' -and
  $PersistentSupervisionResidentClaimBoundaryBlockers -contains 'resident_claim_authority_not_granted' -and
  [string]$PersistentSupervisionResidentClaimBoundaryProof.next_smallest_truthful_gap -eq 'stage6_lens_completion_audit'
)
$PersistentSupervisionEnablementTransitionPlanProofSiblingChildProofCount = 3
$PersistentSupervisionEnablementTransitionPlanProofTimeoutSeconds = (
  ($ChildProofTimeoutSeconds * $PersistentSupervisionEnablementTransitionPlanProofSiblingChildProofCount)
) + 60
$PersistentSupervisionEnablementTransitionPlanProofResult = Invoke-JsonScript `
  -PowerShellPath $PowerShell.Source `
  -ScriptPath $PersistentSupervisionEnablementTransitionPlanProofScript `
  -ScriptArgs @('-Mode', 'Status', '-ChildProofTimeoutSeconds', [string]$ChildProofTimeoutSeconds) `
  -TimeoutSeconds $PersistentSupervisionEnablementTransitionPlanProofTimeoutSeconds
$PersistentSupervisionEnablementTransitionPlanProof = $PersistentSupervisionEnablementTransitionPlanProofResult.payload
$PersistentSupervisionEnablementTransitionPlanProofBlockers = ConvertTo-StringArray -Value $PersistentSupervisionEnablementTransitionPlanProof.blockers
$PersistentSupervisionEnablementTransitionPlanProofRequiredBeforeEnable = ConvertTo-StringArray -Value (
  $PersistentSupervisionEnablementTransitionPlanProof.required_before_enable
)
$PersistentSupervisionEnablementTransitionPlanProofDisabledConfigToggles = ConvertTo-StringArray -Value (
  $PersistentSupervisionEnablementTransitionPlanProof.disabled_config_toggles
)
$PersistentSupervisionEnablementTransitionPlanProofEnabledConfigToggles = ConvertTo-StringArray -Value (
  $PersistentSupervisionEnablementTransitionPlanProof.enabled_config_toggles
)
$PersistentSupervisionEnablementTransitionPlanProofServicePlanBlockedBy = ConvertTo-StringArray -Value (
  $PersistentSupervisionEnablementTransitionPlanProof.service_plan_blocked_by
)
$PersistentSupervisionEnablementTransitionPlanProofGovernance = $PersistentSupervisionEnablementTransitionPlanProof.governance
$PersistentSupervisionEnablementTransitionPlanProofObserved = (
  [int]$PersistentSupervisionEnablementTransitionPlanProofResult.exit_code -eq 0 -and
  [string]$PersistentSupervisionEnablementTransitionPlanProof.kind -eq 'lens.host.persistent_supervision_enablement_transition_plan.proof' -and
  [bool]$PersistentSupervisionEnablementTransitionPlanProof.ok -and
  [string]$PersistentSupervisionEnablementTransitionPlanProof.status -eq 'proof_passed' -and
  [bool]$PersistentSupervisionEnablementTransitionPlanProof.transition_plan_observed -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProof.transition_plan_ready -and
  [bool]$PersistentSupervisionEnablementTransitionPlanProof.persistent_supervision_config_gate_enabled -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProof.persistent_supervision_enablement_disabled -and
  [bool]$PersistentSupervisionEnablementTransitionPlanProof.persistent_supervision_prerequisites_readback_observed -and
  [bool]$PersistentSupervisionEnablementTransitionPlanProof.persistent_supervision_required_prerequisites_guard_observed -and
  [bool]$PersistentSupervisionEnablementTransitionPlanProof.persistent_supervision_service_install_plan_proof_observed -and
  [bool]$PersistentSupervisionEnablementTransitionPlanProof.persistent_supervision_resident_claim_boundary_observed -and
  [bool]$PersistentSupervisionEnablementTransitionPlanProof.persistent_supervision_plan_observed -and
  [bool]$PersistentSupervisionEnablementTransitionPlanProof.side_effects_denied -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProof.applied -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProof.executed -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProof.service_config_updated -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_update_service_config -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_enable_process_supervision -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_enable_persistent_supervision -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_install_service -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_start_service -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_supervise_process -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_restart_process -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_write_receipt -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_write_memory -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_claim_resident -and
  $PersistentSupervisionEnablementTransitionPlanProofRequiredBeforeEnable -contains 'resident_host_process' -and
  $PersistentSupervisionEnablementTransitionPlanProofRequiredBeforeEnable -contains 'tray_presence' -and
  $PersistentSupervisionEnablementTransitionPlanProofRequiredBeforeEnable -contains 'global_hotkey_binding' -and
  $PersistentSupervisionEnablementTransitionPlanProofRequiredBeforeEnable -contains 'overlay_window' -and
  $PersistentSupervisionEnablementTransitionPlanProofRequiredBeforeEnable -contains 'summon_binding' -and
  $PersistentSupervisionEnablementTransitionPlanProofEnabledConfigToggles -contains 'process_supervision_enabled' -and
  $PersistentSupervisionEnablementTransitionPlanProofEnabledConfigToggles -contains 'persistent_supervision_enabled' -and
  [string]$PersistentSupervisionEnablementTransitionPlanProof.next_smallest_truthful_gap -eq 'persistent_supervision_required_prerequisites_missing' -and
  [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.diagnostic_only -and
  [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.read_only_transition_plan -and
  [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.uses_persistent_supervision_plan_prerequisite_readback -and
  [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.wraps_existing_service_install_plan_proof -and
  [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.wraps_existing_resident_claim_boundary_proof -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.product_execution_authority -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.execution_authority -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.approval_decision_authority -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.local_process_launch_authority -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.process_supervision_authority -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.process_restart_authority -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.service_install_authority -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.service_control_authority -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.persistent_supervision_enablement_authority -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.persistent_supervision_execution_authority -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.service_config_write_authority -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.receipt_write_authority -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.memory_write -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.resident_claim_authority -and
  -not [bool]$PersistentSupervisionEnablementTransitionPlanProofGovernance.mutation_authority_granted
)
$ChildProofRuns = @(
  New-ChildProofRunSummary -Name 'summon_anywhere_blockers' -Result $SummonAnywhereBlockersProofResult
  New-ChildProofRunSummary -Name 'summon_authority_blocker' -Result $SummonAuthorityBlockerProofResult
  New-ChildProofRunSummary -Name 'summon_anywhere_family_chain' -Result $SummonAnywhereFamilyChainProofResult
  New-ChildProofRunSummary -Name 'resident_host_runtime_boundary' -Result $ResidentHostRuntimeBoundaryProofResult
  New-ChildProofRunSummary -Name 'process_supervision_boundary' -Result $ProcessSupervisionBoundaryResult
  New-ChildProofRunSummary -Name 'resident_host_process_supervision_blocker' -Result $ResidentHostProcessSupervisionBlockerProofResult
  New-ChildProofRunSummary -Name 'resident_supervision_persistence_boundary' -Result $ResidentSupervisionPersistenceBoundaryProofResult
  New-ChildProofRunSummary -Name 'host_supervision_authority_request' -Result $HostSupervisionAuthorityRequestProofResult
  New-ChildProofRunSummary -Name 'persistent_supervision_plan' -Result $PersistentSupervisionPlanResult
  New-ChildProofRunSummary -Name 'persistent_supervision_prerequisites' -Result $PersistentSupervisionPrerequisitesProofResult
  New-ChildProofRunSummary -Name 'stage6_prerequisite_bringup_plan' -Result $Stage6PrerequisiteBringupPlanResult
  New-ChildProofRunSummary -Name 'persistent_supervision_service_install_plan' -Result $PersistentSupervisionServiceInstallPlanProofResult
  New-ChildProofRunSummary -Name 'persistent_supervision_enablement_authority' -Result $PersistentSupervisionEnablementAuthorityProofResult
  New-ChildProofRunSummary -Name 'persistent_supervision_execution_authority' -Result $PersistentSupervisionExecutionAuthorityProofResult
  New-ChildProofRunSummary -Name 'persistent_supervision_resident_claim_boundary' -Result $PersistentSupervisionResidentClaimBoundaryProofResult
  New-ChildProofRunSummary -Name 'persistent_supervision_enablement_transition_plan' -Result $PersistentSupervisionEnablementTransitionPlanProofResult
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
  [string]$PersistentSupervisionEnablementDenial.authority_required -eq 'persistent_supervision_enablement_authority' -and
  -not [bool]$PersistentSupervisionEnablementDenial.authority_granted -and
  -not [bool]$PersistentSupervisionEnablementDenial.enablement_ready -and
  -not [bool]$PersistentSupervisionEnablementDenial.resident_claim_allowed -and
  -not [bool]$PersistentSupervisionEnablementDenial.service_config_updated -and
  -not [bool]$PersistentSupervisionEnablementDenial.authority_grant_active -and
  $PersistentSupervisionEnablementDenialBlockers -contains 'persistent_supervision_enablement_authority_not_granted' -and
  [string]$PersistentSupervisionEnablementDenial.service_config_write_authority_required -eq 'service_config_write_authority' -and
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
  [string]$PersistentSupervisionEnablementExecutionDenial.enablement_authority_required -eq 'persistent_supervision_enablement_authority' -and
  -not [bool]$PersistentSupervisionEnablementExecutionDenial.enablement_authority_granted -and
  -not [bool]$PersistentSupervisionEnablementExecutionDenial.persistent_supervision_enablement_allowed -and
  -not [bool]$PersistentSupervisionEnablementExecutionDenial.service_config_updated -and
  -not [bool]$PersistentSupervisionEnablementExecutionDenial.resident_claim_allowed -and
  $PersistentSupervisionEnablementExecutionDenialBlockers -contains 'approval_id_required' -and
  $PersistentSupervisionEnablementExecutionDenialBlockers -contains 'persistent_supervision_enablement_authority_not_granted' -and
  [string]$PersistentSupervisionEnablementExecutionDenial.service_config_write_authority_required -eq 'service_config_write_authority' -and
  $PersistentSupervisionEnablementExecutionDenialBlockers -contains 'service_config_write_authority_not_granted' -and
  [string]$PersistentSupervisionEnablementExecutionDenial.persistent_supervision_execution_authority_required -eq 'persistent_supervision_execution_authority' -and
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
$CheckpointSummonEnablementGateAuthorityBlockers = @(
  $CheckpointSummonEnablementGateHandoffBlockers | Where-Object { [string]$_ -like '*_authority_not_granted' }
)
$CheckpointSummonEnablementGateSummonBindingBlockerObserved = (
  $CheckpointSummonEnablementGateHandoffFamilies -contains 'summon_binding' -and
  $CheckpointSummonEnablementGateHandoffBlockers -contains 'summon_binding_missing'
)
$CheckpointSummonEnablementGateSummonRuntimeReadbackObserved = (
  $CheckpointSummonEnablementGateHandoffFamilies -contains 'summon_anywhere' -and
  $CheckpointSummonEnablementGateHandoffBlockers -contains 'summon_anywhere_runtime_readback'
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
  $CheckpointSummonEnablementGateHandoffFamilies -contains 'authority' -and
  ($CheckpointSummonEnablementGateSummonBindingBlockerObserved -or $CheckpointSummonEnablementGateSummonRuntimeReadbackObserved) -and
  [string]$CheckpointSummonEnablementGateHandoff.first_blocker_family -eq 'resident_host' -and
  [string]$CheckpointSummonEnablementGateFirstFamilyHandoff.id -eq 'resident_host' -and
  [string]$CheckpointSummonEnablementGateFirstFamilyHandoff.status -eq 'blocked' -and
  [string]$CheckpointSummonEnablementGateFirstFamilyHandoff.proof_script -eq 'scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status' -and
  [string]$CheckpointSummonEnablementGateFirstFamilyHandoff.route -eq '/lens/host' -and
  [string]$CheckpointSummonEnablementGateFirstFamilyHandoff.readiness_route -eq '/lens/host/runtime-loop/readiness' -and
  [string]$CheckpointSummonEnablementGateFirstFamilyHandoff.next_step -eq 'run_resident_host_blocker_proof' -and
  [string]$CheckpointSummonEnablementGateFirstFamilyHandoff.next_smallest_truthful_gap -eq 'resident_host_runtime_blocker_boundary' -and
  [string]$CheckpointSummonEnablementGateFirstFamilyHandoff.authority_required -eq 'resident_runtime_execution_authority' -and
  $CheckpointSummonEnablementGateFirstFamilyHandoffBlockers -contains 'lens_host_persistent_supervision_prerequisites_pending' -and
  $CheckpointSummonEnablementGateFirstFamilyHandoffBlockers -contains 'local_process_launch_authority_not_granted' -and
  -not [bool]$CheckpointSummonEnablementGateFirstFamilyHandoff.authority_granted -and
  [bool]$CheckpointSummonEnablementGateFirstFamilyHandoff.read_only_contract -and
  [bool]$CheckpointSummonEnablementGateFirstFamilyHandoff.diagnostic_only -and
  -not [bool]$CheckpointSummonEnablementGateFirstFamilyHandoff.would_execute -and
  -not [bool]$CheckpointSummonEnablementGateFirstFamilyHandoff.would_mutate -and
  [string]$CheckpointSummonEnablementGateHandoff.next_smallest_truthful_gap -eq 'summon_anywhere_blockers' -and
  $CheckpointSummonEnablementGateHandoffEvidence -contains '/lens/status' -and
  @($CheckpointSummonEnablementGateAuthorityBlockers).Count -gt 0 -and
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
$ResidentRuntimeAuthorityGrantReadiness = $Checkpoint.resident_runtime_authority_grant_readiness_audit
$ResidentRuntimeAuthorityGrantReadinessBlockedRequirements = ConvertTo-StringArray -Value $ResidentRuntimeAuthorityGrantReadiness.blocked_requirements
$ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirement = [string]$ResidentRuntimeAuthorityGrantReadiness.first_blocked_requirement
$ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirementHandoff = $ResidentRuntimeAuthorityGrantReadiness.first_blocked_requirement_handoff
$ResidentRuntimeAuthorityGrantReadinessBlockedRequirementHandoffs = @(
  $ResidentRuntimeAuthorityGrantReadiness.blocked_requirement_handoffs
)
$ResidentRuntimeAuthorityGrantReadinessHandoffObserved = (
  [bool]$ResidentRuntimeAuthorityGrantReadiness.ok -and
  [string]$ResidentRuntimeAuthorityGrantReadiness.status -eq 'blocked' -and
  [string]$ResidentRuntimeAuthorityGrantReadiness.audit_status -eq 'complete' -and
  -not [bool]$ResidentRuntimeAuthorityGrantReadiness.ready -and
  [bool]$ResidentRuntimeAuthorityGrantReadiness.operator_surface_readback_ready -and
  $ResidentRuntimeAuthorityGrantReadinessBlockedRequirements -contains 'exact_resident_runtime_execution_authority_approval' -and
  $ResidentRuntimeAuthorityGrantReadinessBlockedRequirements -contains 'resident_runtime_execution_authority' -and
  $ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirement -eq 'exact_resident_runtime_execution_authority_approval' -and
  [string]$ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirementHandoff.id -eq 'exact_resident_runtime_execution_authority_approval' -and
  [string]$ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirementHandoff.route -eq '/lens/resident-runtime/authority-grant/requests' -and
  [string]$ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirementHandoff.readiness_route -eq '/lens/resident-runtime/authority-grant/readiness' -and
  [string]$ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirementHandoff.request_route -eq '/lens/resident-runtime/authority-grant/request' -and
  [string]$ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirementHandoff.requests_route -eq '/lens/resident-runtime/authority-grant/requests' -and
  [string]$ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirementHandoff.grant_route -eq '/lens/resident-runtime/authority-grant' -and
  [string]$ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirementHandoff.grants_route -eq '/lens/resident-runtime/authority-grant/grants' -and
  [string]$ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirementHandoff.denials_route -eq '/lens/resident-runtime/authority-grant/denials' -and
  [string]$ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirementHandoff.approval_action -eq 'lens.resident_runtime.execution_authority' -and
  [string]$ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirementHandoff.next_step -eq 'create_or_select_exact_approved_resident_runtime_execution_authority_request' -and
  [string]$ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirementHandoff.authority_required -eq 'operator_approval' -and
  -not [bool]$ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirementHandoff.authority_granted -and
  -not [bool]$ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirementHandoff.would_execute -and
  -not [bool]$ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirementHandoff.would_mutate -and
  [string]$ResidentRuntimeAuthorityGrantReadiness.next_smallest_truthful_gap -eq 'approve_resident_runtime_execution_authority_grant_receipt'
)
$ResidentRuntimeBoundary = $Checkpoint.resident_runtime_authority_boundary
$ResidentRuntimeBoundaryBlockers = ConvertTo-StringArray -Value $ResidentRuntimeBoundary.blockers
$ResidentRuntimeBoundaryObserved = (
  [bool]$ResidentRuntimeBoundary.ok -and
  [string]$ResidentRuntimeBoundary.status -ne 'missing' -and
  -not [bool]$ResidentRuntimeBoundary.applied -and
  -not [bool]$ResidentRuntimeBoundary.executed -and
  [string]$ResidentRuntimeBoundary.resident_runtime_execution_authority_required -eq 'resident_runtime_execution_authority' -and
  $ResidentRuntimeBoundaryBlockers -contains 'resident_runtime_execution_authority_not_granted' -and
  [string]$ResidentRuntimeBoundary.local_process_launch_authority_required -eq 'local_process_launch_authority' -and
  $ResidentRuntimeBoundaryBlockers -contains 'local_process_launch_authority_not_granted' -and
  [string]$ResidentRuntimeBoundary.process_supervision_authority_required -eq 'process_supervision_authority' -and
  $ResidentRuntimeBoundaryBlockers -contains 'process_supervision_authority_not_granted' -and
  [string]$ResidentRuntimeBoundary.service_control_authority_required -eq 'service_control_authority' -and
  $ResidentRuntimeBoundaryBlockers -contains 'service_control_authority_not_granted' -and
  [string]$ResidentRuntimeBoundary.tray_registration_authority_required -eq 'tray_registration_authority' -and
  $ResidentRuntimeBoundaryBlockers -contains 'tray_registration_authority_not_granted' -and
  [string]$ResidentRuntimeBoundary.overlay_control_authority_required -eq 'overlay_control_authority' -and
  $ResidentRuntimeBoundaryBlockers -contains 'overlay_control_authority_not_granted' -and
  [string]$ResidentRuntimeBoundary.resident_claim_authority_required -eq 'resident_claim_authority' -and
  $ResidentRuntimeBoundaryBlockers -contains 'resident_claim_authority_not_granted'
)
$ResidentRuntimeGrantedBoundaryProof = $Checkpoint.resident_runtime_granted_boundary_proof
$ResidentRuntimeGrantedBoundaryProofBlockers = ConvertTo-StringArray -Value $ResidentRuntimeGrantedBoundaryProof.blockers
$ResidentRuntimeGrantedBoundaryProofObserved = (
  [bool]$ResidentRuntimeGrantedBoundaryProof.ok -and
  [string]$ResidentRuntimeGrantedBoundaryProof.status -eq 'proof_passed' -and
  [string]$ResidentRuntimeGrantedBoundaryProof.authority_required -eq 'resident_runtime_execution_authority' -and
  [bool]$ResidentRuntimeGrantedBoundaryProof.authority_granted -and
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
  [string]$ResidentRuntimeProcessSupervisionBoundaryProof.authority_required -eq 'process_supervision_authority' -and
  -not [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.authority_granted -and
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
  [string]$ResidentRuntimeServiceControlBoundaryProof.authority_required -eq 'service_control_authority' -and
  -not [bool]$ResidentRuntimeServiceControlBoundaryProof.authority_granted -and
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
  [string]$ResidentRuntimeTrayPresenceBoundaryProof.authority_required -eq 'tray_presence_authority' -and
  -not [bool]$ResidentRuntimeTrayPresenceBoundaryProof.authority_granted -and
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
  [string]$ResidentRuntimeHotkeySummonBoundaryProof.authority_required -eq 'hotkey_registration_and_summon_authority' -and
  -not [bool]$ResidentRuntimeHotkeySummonBoundaryProof.authority_granted -and
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
  [string]$ResidentRuntimeOverlayWindowBoundaryProof.authority_required -eq 'overlay_control_window_management_capture_authority' -and
  -not [bool]$ResidentRuntimeOverlayWindowBoundaryProof.authority_granted -and
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
  [string]$ResidentRuntimeResidentClaimBoundaryProof.authority_required -eq 'resident_claim_authority' -and
  -not [bool]$ResidentRuntimeResidentClaimBoundaryProof.authority_granted -and
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
  $CommandPaletteOsBindingCandidateBlockers -contains 'lens_summon_binding_disabled_pending_authority' -and
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
  $CommandPaletteOsBindingSummonBlockers -contains 'lens_summon_binding_disabled_pending_authority' -and
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
  [string]$OsBindingAuthorityRequestReadback.authority_required -eq 'os_level_command_palette_binding_authority' -and
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
$SummonAnywhereBlockersProofAuthorityRequestReadback = $SummonAnywhereBlockersProof.os_binding_authority_request_readback
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
  [string]$SummonAnywhereBlockersProofAuthorityRequestReadback.authority_required -eq 'os_level_command_palette_binding_authority' -and
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
  $SummonAnywhereBlockersProofSummonBlockers -contains 'lens_summon_binding_disabled_pending_authority' -and
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
  [string]$SummonAuthorityBlockerProof.authority_required -eq 'summon_hotkey_overlay_and_process_authority' -and
  -not [bool]$SummonAuthorityBlockerProof.authority_granted -and
  [bool]$SummonAuthorityBlockerProof.summon_authority_family_observed -and
  [bool]$SummonAuthorityBlockerProof.previous_summon_binding_contract_observed -and
  [bool]$SummonAuthorityBlockerProof.previous_summon_binding_contract_readback_observed -and
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
  $DirectSummonPreflightBindingBlockers -contains 'lens_summon_binding_disabled_pending_authority' -and
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
  $SummonAuthorityBoundaryBindingBlockers -contains 'lens_summon_binding_disabled_pending_authority' -and
  $SummonAuthorityBoundaryBindingBlockers -contains 'summon_authority_not_granted' -and
  $SummonAuthorityBoundaryAuthorityBlockers -contains 'summon_authority_not_granted' -and
  $SummonAuthorityBoundaryAuthorityBlockers -contains 'hotkey_registration_authority_not_granted' -and
  $SummonAuthorityBoundaryAuthorityBlockers -contains 'overlay_control_authority_not_granted' -and
  $SummonAuthorityBoundaryAuthorityBlockers -contains 'local_process_launch_authority_not_granted' -and
  [bool]$SummonAuthorityBlockerProofGovernance.diagnostic_only -and
  [bool]$SummonAuthorityBlockerProofGovernance.wraps_summon_anywhere_blockers_proof -and
  -not [bool]$SummonAuthorityBlockerProofGovernance.wraps_summon_binding_blocker_proof -and
  [bool]$SummonAuthorityBlockerProofGovernance.uses_summon_binding_family_contract_readback -and
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
$SummonAnywhereFamilyChainProofRecommendedHandoff = $SummonAnywhereFamilyChainProof.recommended_handoff
$SummonAnywhereFamilyChainProofResidentHost = $SummonAnywhereFamilyChainProof.resident_host
$SummonAnywhereFamilyChainProofFinalAuthority = $SummonAnywhereFamilyChainProof.final_authority
$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding = $SummonAnywhereFamilyChainProofFinalAuthority.previous_binding_handoff
$SummonAnywhereFamilyChainProofBlockedFamilies = ConvertTo-StringArray -Value $SummonAnywhereFamilyChainProof.blocked_families
$SummonAnywhereFamilyChainProofResidentHostBlockers = ConvertTo-StringArray -Value (
  $SummonAnywhereFamilyChainProofResidentHost.blockers
)
$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBindingBlockers = ConvertTo-StringArray -Value (
  $SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.blockers
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
  [string]$SummonAnywhereFamilyChainProof.recommended_handoff_source -eq 'summon_anywhere_family_chain_completion_audit_handoff' -and
  [string]$SummonAnywhereFamilyChainProof.recommended_next_slice -eq 'run_stage6_lens_completion_audit_after_summon_anywhere_family_chain_readback' -and
  [string]$SummonAnywhereFamilyChainProof.recommended_proof_script -eq 'scripts/lens-stage6-completion-audit.ps1 -Mode Status' -and
  [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.id -eq 'stage6_lens_completion_audit' -and
  [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.status -eq 'audit_needed' -and
  [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.previous_next_smallest_truthful_gap -eq 'summon_anywhere_blockers' -and
  [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.next_smallest_truthful_gap -eq 'stage6_lens_completion_audit' -and
  [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.next_step -eq 'run_stage6_lens_completion_audit_after_summon_anywhere_family_chain_readback' -and
  [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.proof_script -eq 'scripts/lens-stage6-completion-audit.ps1 -Mode Status' -and
  [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.authority_required -eq 'none_new_stage6_completion_audit' -and
  -not [bool]$SummonAnywhereFamilyChainProofRecommendedHandoff.authority_granted -and
  [bool]$SummonAnywhereFamilyChainProofRecommendedHandoff.read_only_contract -and
  [bool]$SummonAnywhereFamilyChainProofRecommendedHandoff.diagnostic_only -and
  -not [bool]$SummonAnywhereFamilyChainProofRecommendedHandoff.would_execute -and
  -not [bool]$SummonAnywhereFamilyChainProofRecommendedHandoff.would_mutate -and
  [string]$SummonAnywhereFamilyChainProof.authority_required -eq 'summon_hotkey_overlay_and_process_authority' -and
  -not [bool]$SummonAnywhereFamilyChainProof.authority_granted -and
  [bool]$SummonAnywhereFamilyChainProof.family_chain_observed -and
  [bool]$SummonAnywhereFamilyChainProof.resident_host_family_handoff_observed -and
  [bool]$SummonAnywhereFamilyChainProof.final_summon_authority_handoff_observed -and
  [bool]$SummonAnywhereFamilyChainProof.final_summon_authority_contract_readback_observed -and
  [bool]$SummonAnywhereFamilyChainProof.all_summon_blocker_families_consumed -and
  [bool]$SummonAnywhereFamilyChainProof.handoff_aligned -and
  [bool]$SummonAnywhereFamilyChainProof.side_effects_denied -and
  [string]$SummonAnywhereFamilyChainProof.first_blocker_family -eq 'resident_host' -and
  $SummonAnywhereFamilyChainBlockedFamiliesAligned -and
  [string]$SummonAnywhereFamilyChainProofResidentHost.handoff_source -eq 'summon_anywhere_blockers_first_family_handoff' -and
  [string]$SummonAnywhereFamilyChainProofResidentHost.id -eq 'resident_host' -and
  [string]$SummonAnywhereFamilyChainProofResidentHost.status -eq 'blocked' -and
  [string]$SummonAnywhereFamilyChainProofResidentHost.proof_script -eq 'scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status' -and
  [string]$SummonAnywhereFamilyChainProofResidentHost.route -eq '/lens/host' -and
  [string]$SummonAnywhereFamilyChainProofResidentHost.readiness_route -eq '/lens/host/runtime-loop/readiness' -and
  [string]$SummonAnywhereFamilyChainProofResidentHost.next_step -eq 'run_resident_host_blocker_proof' -and
  [string]$SummonAnywhereFamilyChainProofResidentHost.next_smallest_truthful_gap -eq 'resident_host_runtime_blocker_boundary' -and
  [string]$SummonAnywhereFamilyChainProofResidentHost.authority_required -eq 'resident_runtime_execution_authority' -and
  -not [bool]$SummonAnywhereFamilyChainProofResidentHost.authority_granted -and
  [bool]$SummonAnywhereFamilyChainProofResidentHost.read_only_contract -and
  [bool]$SummonAnywhereFamilyChainProofResidentHost.diagnostic_only -and
  -not [bool]$SummonAnywhereFamilyChainProofResidentHost.would_execute -and
  -not [bool]$SummonAnywhereFamilyChainProofResidentHost.would_mutate -and
  $SummonAnywhereFamilyChainProofResidentHostBlockers -contains 'local_process_launch_authority_not_granted' -and
  [string]$SummonAnywhereFamilyChainProofFinalAuthority.previous_summon_blocker_family -eq 'summon_binding' -and
  [string]$SummonAnywhereFamilyChainProofFinalAuthority.summon_authority_blocker_family -eq 'authority' -and
  [string]$SummonAnywhereFamilyChainProofFinalAuthority.next_summon_blocker_family -eq 'stage6_lens_completion_audit' -and
  [string]$SummonAnywhereFamilyChainProofFinalAuthority.next_smallest_truthful_gap -eq 'stage6_lens_completion_audit' -and
  [string]$SummonAnywhereFamilyChainProofFinalAuthority.authority_required -eq 'summon_hotkey_overlay_and_process_authority' -and
  -not [bool]$SummonAnywhereFamilyChainProofFinalAuthority.authority_granted -and
  [bool]$SummonAnywhereFamilyChainProofFinalAuthority.all_summon_blocker_families_consumed -and
  [bool]$SummonAnywhereFamilyChainProofFinalAuthority.previous_summon_binding_contract_observed -and
  [bool]$SummonAnywhereFamilyChainProofFinalAuthority.previous_summon_binding_contract_readback_observed -and
  [string]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.source -eq 'summon_anywhere_blockers.blocked_family_handoffs' -and
  [string]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.status -eq 'contract_projected' -and
  [string]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.contract_status -eq 'blocked' -and
  [string]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.proof_script -eq 'scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status' -and
  [string]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.previous_summon_blocker_family -eq 'global_hotkey_binding' -and
  [string]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.summon_binding_blocker_family -eq 'summon_binding' -and
  [string]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.next_summon_blocker_family -eq 'authority' -and
  [string]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.next_smallest_truthful_gap -eq 'summon_authority_blocker_boundary' -and
  [string]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.authority_required -eq 'summon_authority' -and
  -not [bool]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.authority_granted -and
  [bool]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.read_only_contract -and
  [bool]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.diagnostic_only -and
  -not [bool]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.would_execute -and
  -not [bool]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.would_mutate -and
  $SummonAnywhereFamilyChainProofFinalAuthorityPreviousBindingBlockers -contains 'lens_summon_binding_disabled_pending_authority' -and
  $SummonAnywhereFamilyChainProofFinalAuthorityPreviousBindingBlockers -contains 'summon_authority_not_granted' -and
  $SummonAnywhereFamilyChainProofFinalAuthorityBlockers -contains 'summon_authority_not_granted' -and
  [bool]$SummonAnywhereFamilyChainProofGovernance.diagnostic_only -and
  [bool]$SummonAnywhereFamilyChainProofGovernance.wraps_summon_anywhere_blockers_proof -and
  [bool]$SummonAnywhereFamilyChainProofGovernance.uses_summon_anywhere_family_handoff_contract -and
  [bool]$SummonAnywhereFamilyChainProofGovernance.wraps_summon_authority_blocker_proof -and
  [bool]$SummonAnywhereFamilyChainProofGovernance.final_authority_previous_contract_readback -and
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
$Stage6CompletionEvidenceReviewed = (
  $ResidentRuntimeResidentClaimBoundaryObserved -and
  $PersistentSupervisionResidentClaimBoundaryObserved -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  $ResidentSupervisionPersistenceBoundaryProofObserved -and
  $HostSupervisionAuthorityReadinessHandoffObserved -and
  $HostSupervisionAuthorityRequestProofObserved -and
  $PersistentSupervisionPrerequisitesProofObserved -and
  $CommandPaletteShellBridgeObserved -and
  $CommandPaletteOsBindingObserved -and
  $OsBindingAuthorityRequestReadbackObserved -and
  $SummonAnywhereBlockersProofObserved -and
  $CheckpointSummonEnablementGateHandoffObserved -and
  $SummonAuthorityBlockerProofObserved -and
  $SummonAnywhereFamilyChainProofObserved
)
$Stage6CompletionReviewed = (
  $Stage6CompletionEvidenceReviewed -and
  $Stage6PrerequisiteBringupPlanObserved -and
  $PersistentSupervisionEnablementTransitionPlanProofObserved
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
  -not $ResidentSupervisionPersistenceBoundaryProofObserved
) {
  'resident_supervision_persistence_boundary_proof_readback'
} elseif (
  $PersistentSupervisionEnablementDenialObserved -and
  $PersistentSupervisionEnablementExecutionDenialObserved -and
  $PersistentSupervisionResidentClaimBoundaryObserved -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  $ResidentSupervisionPersistenceBoundaryProofObserved -and
  -not $HostSupervisionAuthorityReadinessHandoffObserved
) {
  'resident_host_supervision_authority_readiness_handoff'
} elseif (
  $PersistentSupervisionEnablementDenialObserved -and
  $PersistentSupervisionEnablementExecutionDenialObserved -and
  $PersistentSupervisionResidentClaimBoundaryObserved -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  $ResidentSupervisionPersistenceBoundaryProofObserved -and
  $HostSupervisionAuthorityReadinessHandoffObserved -and
  -not $HostSupervisionAuthorityRequestProofObserved
) {
  'host_supervision_authority_exact_approval_request'
} elseif (
  $PersistentSupervisionEnablementDenialObserved -and
  $PersistentSupervisionEnablementExecutionDenialObserved -and
  $PersistentSupervisionResidentClaimBoundaryObserved -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  $ResidentSupervisionPersistenceBoundaryProofObserved -and
  $HostSupervisionAuthorityReadinessHandoffObserved -and
  $HostSupervisionAuthorityRequestProofObserved -and
  -not $PersistentSupervisionPrerequisitesProofObserved
) {
  'persistent_supervision_prerequisites_proof_readback'
} elseif (
  $PersistentSupervisionEnablementDenialObserved -and
  $PersistentSupervisionEnablementExecutionDenialObserved -and
  $PersistentSupervisionResidentClaimBoundaryObserved -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  $HostSupervisionAuthorityReadinessHandoffObserved -and
  $HostSupervisionAuthorityRequestProofObserved -and
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
  $Stage6CompletionEvidenceReviewed -and
  -not $ReadyToClose -and
  $BlockedCriterionIds -contains 'summon_anywhere' -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  $HostSupervisionAuthorityReadinessHandoffObserved -and
  $HostSupervisionAuthorityRequestProofObserved -and
  $PersistentSupervisionPrerequisitesProofObserved -and
  -not $Stage6PrerequisiteBringupPlanObserved
) {
  'stage6_prerequisite_bringup_plan_readback'
} elseif (
  $Stage6CompletionEvidenceReviewed -and
  -not $ReadyToClose -and
  $BlockedCriterionIds -contains 'summon_anywhere' -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  $HostSupervisionAuthorityReadinessHandoffObserved -and
  $HostSupervisionAuthorityRequestProofObserved -and
  $PersistentSupervisionPrerequisitesProofObserved -and
  $Stage6PrerequisiteBringupPlanObserved -and
  -not $PersistentSupervisionServiceInstallPlanProofObserved
) {
  'persistent_supervision_service_install_plan_proof_readback'
} elseif (
  $Stage6CompletionEvidenceReviewed -and
  -not $ReadyToClose -and
  $BlockedCriterionIds -contains 'summon_anywhere' -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  $HostSupervisionAuthorityReadinessHandoffObserved -and
  $HostSupervisionAuthorityRequestProofObserved -and
  $PersistentSupervisionPrerequisitesProofObserved -and
  $Stage6PrerequisiteBringupPlanObserved -and
  $PersistentSupervisionServiceInstallPlanProofObserved -and
  $PersistentSupervisionEnablementAuthorityProofObserved -and
  $PersistentSupervisionExecutionAuthorityProofObserved -and
  $PersistentSupervisionResidentClaimBoundaryObserved -and
  -not $PersistentSupervisionEnablementTransitionPlanProofObserved
) {
  'persistent_supervision_enablement_transition_plan_proof_readback'
} elseif (
  $Stage6CompletionReviewed -and
  -not $ReadyToClose -and
  $BlockedCriterionIds -contains 'summon_anywhere' -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  $HostSupervisionAuthorityReadinessHandoffObserved -and
  $HostSupervisionAuthorityRequestProofObserved -and
  $PersistentSupervisionPrerequisitesProofObserved -and
  $PersistentSupervisionServiceInstallPlanProofObserved -and
  $PersistentSupervisionEnablementAuthorityProofObserved -and
  $PersistentSupervisionExecutionAuthorityProofObserved -and
  $PersistentSupervisionResidentClaimBoundaryObserved -and
  $PersistentSupervisionEnablementTransitionPlanProofObserved -and
  -not $Stage6PrerequisiteBringupPlanAppliedEnablementObserved -and
  [string]$PersistentSupervisionPrerequisitesProof.next_smallest_truthful_gap -eq 'persistent_supervision_required_prerequisites_missing'
) {
  'persistent_supervision_required_prerequisites_missing'
} elseif (
  $Stage6CompletionReviewed -and
  -not $ReadyToClose -and
  $BlockedCriterionIds -contains 'summon_anywhere' -and
  $ResidentSupervisionPersistenceBoundaryProofObserved -and
  $PersistentSupervisionExecutionAuthorityProofObserved -and
  -not $PersistentSupervisionResidentClaimBoundaryObserved -and
  [string]$PersistentSupervisionExecutionAuthorityProof.next_smallest_truthful_gap -eq 'persistent_supervision_resident_claim_authority_boundary' -and
  $PersistentSupervisionExecutionAuthorityProofBlockers -contains 'resident_claim_authority_not_granted'
) {
  'persistent_supervision_resident_claim_authority_boundary'
} elseif (
  $Stage6CompletionReviewed -and
  -not $ReadyToClose -and
  $BlockedCriterionIds -contains 'summon_anywhere' -and
  $ResidentSupervisionPersistenceBoundaryProofObserved -and
  $PersistentSupervisionEnablementAuthorityProofObserved -and
  -not $PersistentSupervisionExecutionAuthorityProofObserved -and
  [string]$PersistentSupervisionEnablementAuthorityProof.next_smallest_truthful_gap -eq 'persistent_supervision_execution_authority_or_resident_claim_boundary' -and
  $PersistentSupervisionEnablementAuthorityProofBlockers -contains 'persistent_supervision_execution_authority_not_granted'
) {
  'persistent_supervision_execution_authority_or_resident_claim_boundary'
} elseif (
  $Stage6CompletionReviewed -and
  -not $ReadyToClose -and
  $BlockedCriterionIds -contains 'summon_anywhere' -and
  $ResidentSupervisionPersistenceBoundaryProofObserved -and
  -not $PersistentSupervisionEnablementAuthorityProofObserved -and
  [string]$ResidentSupervisionPersistenceBoundaryProof.next_smallest_truthful_gap -eq 'persistent_supervision_authority_not_granted' -and
  [string]$ResidentSupervisionPersistenceBoundaryProof.route_next_smallest_truthful_gap -eq 'persistent_supervision_authority_not_granted'
) {
  'persistent_supervision_authority_not_granted'
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

$RecommendedHandoffSource = ''
$RecommendedNextSlice = ''
$RecommendedProofScript = ''
$RecommendedAuthorityRequired = ''
$RecommendedHandoff = [ordered]@{}
$Stage6PrerequisiteBringupPlanNextOperatorActionId = [string]$Stage6PrerequisiteBringupPlanNextOperatorAction.id
$Stage6PrerequisiteBringupPlanRecommendedNextSlice = 'run_stage6_prerequisite_bringup_plan_status'
if (-not [string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupPlanNextOperatorActionId)) {
  $Stage6PrerequisiteBringupPlanRecommendedNextSlice = "run_stage6_prerequisite_bringup_$Stage6PrerequisiteBringupPlanNextOperatorActionId"
}
$Stage6PrerequisiteBringupPlanRecommendedAuthorityRequired = 'none_readback_only'
if (
  [bool]$Stage6PrerequisiteBringupPlanNextOperatorCommand.requires_approval_id -or
  [bool]$Stage6PrerequisiteBringupPlanNextOperatorCommand.requires_confirmation -or
  [bool]$Stage6PrerequisiteBringupPlanNextOperatorAction.operator_supplied_values_required
) {
  $Stage6PrerequisiteBringupPlanNextOperatorAuthority = [string]$Stage6PrerequisiteBringupPlanNextOperatorAction.approval_action
  if ([string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupPlanNextOperatorAuthority)) {
    $Stage6PrerequisiteBringupPlanNextOperatorAuthority = 'operator_supplied_authority'
  }
  $Stage6PrerequisiteBringupPlanRecommendedAuthorityRequired = $Stage6PrerequisiteBringupPlanNextOperatorAuthority
}
if (
  $NextSmallestTruthfulGap -eq 'summon_anywhere_blockers' -and
  $Stage6PrerequisiteBringupPlanObserved -and
  $SummonAnywhereBlockersProofObserved -and
  $SummonAnywhereFamilyChainProofObserved
) {
  $RecommendedHandoffSource = 'stage6_prerequisite_bringup_operator_plan'
  $RecommendedHandoff = [ordered]@{
    status = 'blocked'
    previous_next_smallest_truthful_gap = 'summon_anywhere_blockers'
    consumed_summon_anywhere_next_smallest_truthful_gap = [string]$SummonAnywhereBlockersProof.next_smallest_truthful_gap
    consumed_family_chain_next_smallest_truthful_gap = [string]$SummonAnywhereFamilyChainProof.next_smallest_truthful_gap
    next_smallest_truthful_gap = [string]$Stage6PrerequisiteBringupPlan.current_truthful_gap
    next_step = $Stage6PrerequisiteBringupPlanRecommendedNextSlice
    proof_script = 'scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status'
    route = [string]$Stage6PrerequisiteBringupPlanNextOperatorAction.route
    operator_plan_script = 'scripts/lens-stage6-prerequisite-bringup-plan.ps1'
    closure_next_smallest_truthful_gap = [string]$Stage6PrerequisiteBringupPlan.closure_next_smallest_truthful_gap
    persistent_supervision_next_smallest_truthful_gap = [string]$Stage6PrerequisiteBringupPlan.persistent_supervision_next_smallest_truthful_gap
    bringup_plan_status = [string]$Stage6PrerequisiteBringupPlan.status
    bringup_plan_current_truthful_gap = [string]$Stage6PrerequisiteBringupPlan.current_truthful_gap
    bringup_plan_current_truthful_gap_basis = [string]$Stage6PrerequisiteBringupPlan.current_truthful_gap_basis
    next_operator_action_requirement = [string]$Stage6PrerequisiteBringupPlan.next_operator_action_requirement
    next_operator_action = $Stage6PrerequisiteBringupPlanNextOperatorAction
    next_operator_command = $Stage6PrerequisiteBringupPlanNextOperatorCommand
    operator_sequence_command_availability = $Stage6PrerequisiteBringupPlanCommandAvailability
    authority_required = $Stage6PrerequisiteBringupPlanRecommendedAuthorityRequired
    authority_granted = $false
    operator_supplied_values_required = [bool]$Stage6PrerequisiteBringupPlanNextOperatorAction.operator_supplied_values_required
    requires_confirmation = [bool]$Stage6PrerequisiteBringupPlanNextOperatorCommand.requires_confirmation
    requires_approval_id = [bool]$Stage6PrerequisiteBringupPlanNextOperatorCommand.requires_approval_id
    requires_operator_approval_decision = [bool]$Stage6PrerequisiteBringupPlanNextOperatorCommand.requires_operator_approval_decision
    read_only_contract = [bool]$Stage6PrerequisiteBringupPlanGovernance.read_only_contract
    diagnostic_only = [bool]$Stage6PrerequisiteBringupPlanGovernance.diagnostic_only
    would_execute = [bool]$Stage6PrerequisiteBringupPlanGovernance.would_execute
    would_mutate = [bool]$Stage6PrerequisiteBringupPlanGovernance.would_mutate
    would_request_authority = [bool]$Stage6PrerequisiteBringupPlanGovernance.would_request_authority
    would_grant_authority = [bool]$Stage6PrerequisiteBringupPlanGovernance.would_grant_authority
    would_write_memory = [bool]$Stage6PrerequisiteBringupPlanGovernance.memory_write
    would_decide_approval = [bool]$Stage6PrerequisiteBringupPlanGovernance.approval_decision_authority
    would_supervise_process = [bool]$Stage6PrerequisiteBringupPlanGovernance.process_supervision_authority
    blocker_families = [string[]]@(ConvertTo-StringArray -Value $SummonAnywhereBlockersProof.blocked_families)
    blockers = [string[]]@($Blockers)
  }
  $RecommendedNextSlice = [string]$RecommendedHandoff.next_step
  $RecommendedProofScript = [string]$RecommendedHandoff.proof_script
  $RecommendedAuthorityRequired = [string]$RecommendedHandoff.authority_required
} elseif (
  $NextSmallestTruthfulGap -eq 'persistent_supervision_enablement_authority_not_granted' -and
  $PersistentSupervisionEnablementDenialObserved -and
  $PersistentSupervisionEnablementExecutionDenialObserved
) {
  $RecommendedHandoffSource = 'persistent_supervision_enablement_authority_denial_handoff'
  $RecommendedHandoff = [ordered]@{
    status = 'blocked'
    previous_next_smallest_truthful_gap = 'persistent_supervision_authority_not_granted'
    consumed_audit_next_smallest_truthful_gap = 'persistent_supervision_enablement_denial_boundary'
    next_smallest_truthful_gap = 'persistent_supervision_enablement_authority_not_granted'
    next_step = 'prove_persistent_supervision_enablement_authority_after_candidate_handoff'
    proof_script = 'scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status'
    route = '/lens/host/persistent-supervision/enablement'
    request_route = '/lens/host/persistent-supervision/enablement/authority/request'
    grant_route = '/lens/host/persistent-supervision/enablement/authority/grant'
    readiness_route = '/lens/host/persistent-supervision/enablement/authority/readiness'
    execution_readiness_route = '/lens/host/persistent-supervision/enablement/execution/readiness'
    authority_required = 'persistent_supervision_enablement_authority'
    authority_granted = $false
    enablement_denial_observed = $PersistentSupervisionEnablementDenialObserved
    execution_denial_observed = $PersistentSupervisionEnablementExecutionDenialObserved
    persistent_supervision_enablement_authority = [bool]$PersistentSupervisionEnablementDenial.persistent_supervision_enablement_authority
    service_config_write_authority = [bool]$PersistentSupervisionEnablementDenial.service_config_write_authority
    persistent_supervision_execution_authority = [bool]$PersistentSupervisionEnablementExecutionDenial.persistent_supervision_execution_authority
    receipt_write_authority = [bool]$PersistentSupervisionEnablementExecutionDenial.receipt_write_authority
    resident_claim_authority = [bool]$PersistentSupervisionEnablementExecutionDenial.resident_claim_authority
    resident_claim_allowed = [bool]$PersistentSupervisionEnablementExecutionDenial.resident_claim_allowed
    service_config_updated = [bool]$PersistentSupervisionEnablementDenial.service_config_updated
    applied = [bool]$PersistentSupervisionEnablementDenial.applied
    executed = [bool]$PersistentSupervisionEnablementExecutionDenial.executed
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
    blockers = [string[]]@($PersistentSupervisionEnablementDenialBlockers + $PersistentSupervisionEnablementExecutionDenialBlockers | Select-Object -Unique)
  }
  $RecommendedNextSlice = [string]$RecommendedHandoff.next_step
  $RecommendedProofScript = [string]$RecommendedHandoff.proof_script
  $RecommendedAuthorityRequired = [string]$RecommendedHandoff.authority_required
} elseif (
  $NextSmallestTruthfulGap -eq 'persistent_supervision_resident_claim_authority_boundary' -and
  $PersistentSupervisionExecutionAuthorityProofObserved
) {
  $RecommendedHandoffSource = 'persistent_supervision_execution_authority_handoff'
  $RecommendedHandoff = [ordered]@{
    status = 'blocked'
    previous_next_smallest_truthful_gap = [string]$PersistentSupervisionExecutionAuthorityProof.previous_next_smallest_truthful_gap
    consumed_audit_next_smallest_truthful_gap = 'persistent_supervision_execution_authority_or_resident_claim_boundary'
    next_smallest_truthful_gap = [string]$PersistentSupervisionExecutionAuthorityProof.next_smallest_truthful_gap
    next_step = [string]$PersistentSupervisionExecutionAuthorityProof.recommended_next_slice
    proof_script = [string]$PersistentSupervisionExecutionAuthorityProof.recommended_proof_script
    route = [string]$PersistentSupervisionExecutionAuthorityProof.persistent_supervision_execution_route
    readiness_route = [string]$PersistentSupervisionExecutionAuthorityProof.persistent_supervision_execution_readiness_route
    authority_required = [string]$PersistentSupervisionExecutionAuthorityProof.handoff.authority_required
    authority_granted = $false
    persistent_supervision_enablement_authority = [bool]$PersistentSupervisionExecutionAuthorityProof.persistent_supervision_enablement_authority
    service_config_write_authority = [bool]$PersistentSupervisionExecutionAuthorityProof.service_config_write_authority
    persistent_supervision_execution_authority = [bool]$PersistentSupervisionExecutionAuthorityProof.persistent_supervision_execution_authority
    receipt_write_authority = [bool]$PersistentSupervisionExecutionAuthorityProof.receipt_write_authority
    resident_claim_allowed = [bool]$PersistentSupervisionExecutionAuthorityProof.resident_claim_allowed
    grant_applied = [bool]$PersistentSupervisionExecutionAuthorityProof.grant_applied
    enablement_applied = [bool]$PersistentSupervisionExecutionAuthorityProof.enablement_applied
    applied = [bool]$PersistentSupervisionExecutionAuthorityProof.applied
    executed = [bool]$PersistentSupervisionExecutionAuthorityProof.executed
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
    blockers = [string[]]@($PersistentSupervisionExecutionAuthorityProofBlockers)
  }
  $RecommendedNextSlice = [string]$RecommendedHandoff.next_step
  $RecommendedProofScript = [string]$RecommendedHandoff.proof_script
  $RecommendedAuthorityRequired = [string]$RecommendedHandoff.authority_required
} elseif (
  $NextSmallestTruthfulGap -eq 'persistent_supervision_execution_authority_or_resident_claim_boundary' -and
  $PersistentSupervisionEnablementAuthorityProofObserved
) {
  $RecommendedHandoffSource = 'persistent_supervision_enablement_authority_handoff'
  $RecommendedHandoff = [ordered]@{
    status = 'blocked'
    previous_next_smallest_truthful_gap = [string]$PersistentSupervisionEnablementAuthorityProof.previous_next_smallest_truthful_gap
    consumed_audit_next_smallest_truthful_gap = 'persistent_supervision_authority_not_granted'
    next_smallest_truthful_gap = [string]$PersistentSupervisionEnablementAuthorityProof.next_smallest_truthful_gap
    next_step = [string]$PersistentSupervisionEnablementAuthorityProof.recommended_next_slice
    proof_script = [string]$PersistentSupervisionEnablementAuthorityProof.recommended_proof_script
    route = [string]$PersistentSupervisionEnablementAuthorityProof.persistent_supervision_enablement_route
    readiness_route = [string]$PersistentSupervisionEnablementAuthorityProof.persistent_supervision_execution_readiness_route
    authority_required = [string]$PersistentSupervisionEnablementAuthorityProof.handoff.authority_required
    authority_granted = $false
    persistent_supervision_enablement_authority = [bool]$PersistentSupervisionEnablementAuthorityProof.persistent_supervision_enablement_authority
    service_config_write_authority = [bool]$PersistentSupervisionEnablementAuthorityProof.service_config_write_authority
    persistent_supervision_execution_authority = [bool]$PersistentSupervisionEnablementAuthorityProof.persistent_supervision_execution_authority
    resident_claim_allowed = [bool]$PersistentSupervisionEnablementAuthorityProof.resident_claim_allowed
    grant_applied = [bool]$PersistentSupervisionEnablementAuthorityProof.grant_applied
    enablement_applied = [bool]$PersistentSupervisionEnablementAuthorityProof.enablement_applied
    executed = [bool]$PersistentSupervisionEnablementAuthorityProof.executed
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
    blockers = [string[]]@($PersistentSupervisionEnablementAuthorityProofBlockers)
  }
  $RecommendedNextSlice = [string]$RecommendedHandoff.next_step
  $RecommendedProofScript = [string]$RecommendedHandoff.proof_script
  $RecommendedAuthorityRequired = [string]$RecommendedHandoff.authority_required
} elseif (
  $NextSmallestTruthfulGap -eq 'persistent_supervision_authority_not_granted' -and
  $ResidentSupervisionPersistenceBoundaryProofObserved
) {
  $RecommendedHandoffSource = 'resident_supervision_persistence_boundary_handoff'
  $RecommendedHandoff = [ordered]@{
    status = 'blocked'
    previous_next_smallest_truthful_gap = [string]$ResidentSupervisionPersistenceBoundaryProof.previous_next_smallest_truthful_gap
    consumed_resident_candidate_next_smallest_truthful_gap = [string]$ResidentSupervisionPersistenceBoundaryProof.consumed_resident_candidate_next_smallest_truthful_gap
    route_next_smallest_truthful_gap = [string]$ResidentSupervisionPersistenceBoundaryProof.route_next_smallest_truthful_gap
    next_smallest_truthful_gap = [string]$ResidentSupervisionPersistenceBoundaryProof.next_smallest_truthful_gap
    next_step = 'review_persistent_supervision_authority_without_runtime_start'
    proof_script = 'scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status'
    route = [string]$ResidentSupervisionPersistenceBoundaryProof.plan_route
    enablement_route = [string]$ResidentSupervisionPersistenceBoundaryProof.enablement_route
    authority_required = [string]$ResidentSupervisionPersistenceBoundaryProof.authority_required
    authority_granted = $false
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
    resident_runtime_candidate_supervised = [bool]$ResidentSupervisionPersistenceBoundaryProof.resident_runtime_candidate_supervised
    resident_supervised_runtime = [bool]$ResidentSupervisionPersistenceBoundaryProof.resident_supervised_runtime
    resident_host_process_requirement_state = [string]$ResidentSupervisionPersistenceBoundaryProof.resident_host_process_requirement_state
    resident_host_process_blocker = [string]$ResidentSupervisionPersistenceBoundaryProof.resident_host_process_blocker
  }
  $RecommendedNextSlice = [string]$RecommendedHandoff.next_step
  $RecommendedProofScript = [string]$RecommendedHandoff.proof_script
  $RecommendedAuthorityRequired = [string]$RecommendedHandoff.authority_required
} elseif (
  $NextSmallestTruthfulGap -eq 'persistent_supervision_required_prerequisites_missing' -and
  $ResidentHostProcessSupervisionBlockerProofObserved -and
  $PersistentSupervisionPrerequisitesProofObserved -and
  $Stage6PrerequisiteBringupPlanObserved
) {
  $RecommendedHandoffSource = 'stage6_prerequisite_bringup_operator_plan'
  $RecommendedHandoff = [ordered]@{
    status = 'blocked'
    previous_next_smallest_truthful_gap = [string]$ResidentHostProcessSupervisionBlockerProof.previous_next_smallest_truthful_gap
    consumed_process_supervision_next_smallest_truthful_gap = [string]$ResidentHostProcessSupervisionBlockerProof.next_smallest_truthful_gap
    next_smallest_truthful_gap = 'persistent_supervision_required_prerequisites_missing'
    next_step = 'run_stage6_prerequisite_bringup_request_next_for_resident_host_process'
    proof_script = 'scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status'
    route = '/lens/host/persistent-supervision'
    readiness_route = '/lens/host/persistent-supervision/enablement'
    operator_plan_script = 'scripts/lens-stage6-prerequisite-bringup-plan.ps1'
    next_operator_action_requirement = [string]$Stage6PrerequisiteBringupPlan.next_operator_action_requirement
    next_operator_action = $Stage6PrerequisiteBringupPlanNextOperatorAction
    next_operator_command = $Stage6PrerequisiteBringupPlanNextOperatorCommand
    operator_sequence_command_availability = $Stage6PrerequisiteBringupPlanCommandAvailability
    process_supervision_route = [string]$ResidentHostProcessSupervisionBlockerProof.recommended_handoff.route
    process_supervision_readiness_route = [string]$ResidentHostProcessSupervisionBlockerProof.recommended_handoff.readiness_route
    authority_required = 'resident_host_process_tray_hotkey_overlay_and_summon_prerequisites'
    authority_granted = $false
    process_supervision_boundary_observed = [bool]$ResidentHostProcessSupervisionBlockerProof.process_supervision_boundary_observed
    process_supervision_handoff_consumed = [bool]$ResidentHostProcessSupervisionBlockerProof.handoff_consumed
    resident_host_process_state = [string]$ResidentHostProcessSupervisionBlockerProof.resident_host_process_state
    resident_host_process_blocker = [string]$ResidentHostProcessSupervisionBlockerProof.resident_host_process_blocker
    process_supervision_ready = [bool]$ResidentHostProcessSupervisionBlockerProof.process_supervision_ready
    service_activation_ready = [bool]$ResidentHostProcessSupervisionBlockerProof.service_activation_ready
    supervision_ready = [bool]$ResidentHostProcessSupervisionBlockerProof.supervision_ready
    resident_host_supervised = [bool]$ResidentHostProcessSupervisionBlockerProof.resident_host_supervised
    service_installed = [bool]$ResidentHostProcessSupervisionBlockerProof.service_installed
    service_managed = [bool]$ResidentHostProcessSupervisionBlockerProof.service_managed
    first_missing_required_before_enable = $PersistentSupervisionPrerequisitesFirstMissingRequiredBeforeEnable
    first_missing_requirement_handoff = $PersistentSupervisionPrerequisitesFirstMissingRequirementHandoff
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
    would_supervise_process = [bool]$ResidentHostProcessSupervisionBlockerProof.would_supervise_process
    would_restart_process = [bool]$ResidentHostProcessSupervisionBlockerProof.would_restart_process
    would_install_service = [bool]$ResidentHostProcessSupervisionBlockerProof.would_install_service
    would_start_service = [bool]$ResidentHostProcessSupervisionBlockerProof.would_start_service
    would_write_memory = [bool]$ResidentHostProcessSupervisionBlockerProof.would_write_memory
    would_decide_approval = [bool]$ResidentHostProcessSupervisionBlockerProof.would_decide_approval
    blockers = [string[]]@($ResidentHostProcessSupervisionBlockerProofBlockers)
  }
  $RecommendedNextSlice = [string]$RecommendedHandoff.next_step
  $RecommendedProofScript = [string]$RecommendedHandoff.proof_script
  $RecommendedAuthorityRequired = [string]$RecommendedHandoff.authority_required
} elseif (
  $NextSmallestTruthfulGap -eq 'persistent_supervision_required_prerequisites_missing' -and
  $PersistentSupervisionPrerequisitesProofObserved
) {
  $RecommendedHandoffSource = 'persistent_supervision_prerequisites_first_missing_requirement_handoff'
  $RecommendedHandoff = $PersistentSupervisionPrerequisitesProof.first_missing_requirement_handoff
  $RecommendedNextSlice = [string]$RecommendedHandoff.next_step
  $RecommendedProofScript = [string]$RecommendedHandoff.proof_script
  $RecommendedAuthorityRequired = [string]$RecommendedHandoff.authority_required
}

$RecommendedAuthorityGranted = [bool]$RecommendedHandoff.authority_granted

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
  requested_startup_timeout_seconds = $StartupTimeoutSeconds
  child_startup_timeout_seconds = $ChildStartupTimeoutSeconds
  requested_child_host_launch_run_seconds = $HostLaunchRunSeconds
  child_host_launch_run_seconds = $ChildHostLaunchRunSeconds
  child_proof_timeout_seconds = $ChildProofTimeoutSeconds
  child_proof_timeouts = [string[]]@($ChildProofTimeouts)
  child_proof_runs = @($ChildProofRuns)
  next_smallest_truthful_gap = $NextSmallestTruthfulGap
  recommended_handoff_source = $RecommendedHandoffSource
  recommended_next_slice = $RecommendedNextSlice
  recommended_proof_script = $RecommendedProofScript
  authority_required = $RecommendedAuthorityRequired
  authority_granted = $RecommendedAuthorityGranted
  recommended_handoff = $RecommendedHandoff
  persistent_supervision_first_missing_required_before_enable = $PersistentSupervisionPrerequisitesFirstMissingRequiredBeforeEnable
  persistent_supervision_first_missing_requirement_handoff = $PersistentSupervisionPrerequisitesFirstMissingRequirementHandoff
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
  } elseif ($NextSmallestTruthfulGap -eq 'resident_supervision_persistence_boundary_proof_readback') {
    'The audit must consume the resident-supervision persistence boundary proof before treating a bounded supervised candidate as promoted through persistent-supervision plan and enablement readback.'
  } elseif ($NextSmallestTruthfulGap -eq 'resident_host_supervision_authority_readiness_handoff') {
    'The audit must consume the host supervision authority readiness handoff before treating exact approval-request review as an audited resident-host supervision blocker.'
  } elseif ($NextSmallestTruthfulGap -eq 'host_supervision_authority_exact_approval_request') {
    'The completion audit has consumed the resident-host process-supervision handoff and now reads back the exact host-supervision authority approval request as the first concrete blocker for summon-anywhere resident-host supervision.'
  } elseif ($NextSmallestTruthfulGap -eq 'persistent_supervision_prerequisites_proof_readback') {
    'The audit must consume the persistent-supervision prerequisite proof before treating persistent supervision enablement blockers as fully mapped to the Stage 6 summon-anywhere blocker family chain.'
  } elseif ($NextSmallestTruthfulGap -eq 'stage6_prerequisite_bringup_plan_readback') {
    'The completion audit must observe the Stage 6 prerequisite bring-up operator plan before recommending the next governed prerequisite action.'
  } elseif ($NextSmallestTruthfulGap -eq 'persistent_supervision_service_install_plan_proof_readback') {
    'The audit must consume the persistent-supervision service-install plan proof before treating disabled Lens host service configuration as audited Stage 6 enablement evidence.'
  } elseif ($NextSmallestTruthfulGap -eq 'persistent_supervision_enablement_transition_plan_proof_readback') {
    'The audit must consume the persistent-supervision enablement transition-plan proof before treating prerequisite, service-plan, authority-chain, disabled-config, and side-effect readback as one audited Stage 6 handoff.'
  } elseif ($NextSmallestTruthfulGap -eq 'persistent_supervision_required_prerequisites_missing') {
    'The completion audit consumes the resident-host process-supervision handoff proof, resident-supervision persistence boundary proof, persistent-supervision prerequisite guard proof, service-install plan proof, persistent-supervision authority proof chain, resident-claim boundary proof, and persistent-supervision enablement transition-plan proof. Persistent supervision remains blocked because resident-host process, tray, global hotkey, overlay, and summon-binding prerequisites are still missing; the next concrete handoff is the persistent-supervision prerequisite chain rather than the already-consumed resident-host runtime boundary. No runtime launch, service-config mutation, memory write, or resident claim is made.'
  } elseif ($NextSmallestTruthfulGap -eq 'persistent_supervision_enablement_disabled') {
    'The completion audit consumes the host-supervision approval proof, the persistent-supervision prerequisite proof, the service-install plan proof, the persistent-supervision authority proof chain, and the persistent-supervision enablement transition-plan proof: prerequisites, disabled service plan, enablement authority, execution authority, resident-claim boundary, disabled config toggles, and side-effect denial are all read back as bounded and non-mutating. The remaining product gap is that persistent supervision enablement is still disabled, with no runtime launch, service-config mutation, memory write, or resident claim.'
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
    'The audit consumes the resident-supervision persistence boundary proof: a bounded resident candidate has been promoted through persistent-supervision plan and enablement readback, and the remaining handoff is explicit persistent process supervision authority rather than another bounded supervisor proof. Stage 6 still cannot close because summon-anywhere, helpful-not-noisy, and system-resident presence remain blocked.'
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
  resident_supervision_persistence_boundary_proof_observed = $ResidentSupervisionPersistenceBoundaryProofObserved
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
    resident_supervision_persistence_boundary = [string[]]@(
      $ResidentSupervisionPersistenceBoundaryProofBlockers | Where-Object {
        $_ -match 'resident_supervision|persistent_supervision|persistent_process'
      } | Sort-Object -Unique
    )
    host_supervision_authority_readiness_handoff = [string[]]@(
      $HostSupervisionAuthorityReadinessBlockedRequirements | Where-Object {
        $_ -match 'approval|authority|supervision'
      } | Sort-Object -Unique
    )
    host_supervision_authority_request_proof = [string[]]@(
      $HostSupervisionAuthorityRequestProofBlockers | Where-Object {
        $_ -match 'persistent_supervision|process_supervision|authority|supervision'
      } | Sort-Object -Unique
    )
    helpful_not_noisy_runtime_authority_readiness_handoff = [string[]]@(
      $ResidentRuntimeAuthorityGrantReadinessBlockedRequirements | Where-Object {
        $_ -match 'approval|authority|runtime|resident|summon|tray|overlay|supervision|scope|posture'
      } | Sort-Object -Unique
    )
    service_activation = [string[]]@(
      $ProcessSupervisionBoundaryBlockers | Where-Object { $_ -match 'service_' } | Sort-Object -Unique
    )
    persistent_supervision = [string[]]@(
      $PersistentSupervisionPlanBlockers | Where-Object { $_ -match 'persistent_supervision|process_supervision|process_restart|service_|receipt_write|resident_claim' } | Sort-Object -Unique
    )
    persistent_supervision_service_install_plan = [string[]]@(
      $PersistentSupervisionServiceInstallPlanProofBlockedBy | Where-Object { $_ -match 'install|service_control|authority' } | Sort-Object -Unique
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
    persistent_supervision_enablement_transition_plan = [string[]]@(
      $PersistentSupervisionEnablementTransitionPlanProofBlockers | Where-Object { $_ -match 'persistent_supervision|process_supervision|service_|authority|resident_claim|unsupported_platform' } | Sort-Object -Unique
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
    resident_runtime_execution_authority_required = [string]$ResidentRuntimeBoundary.resident_runtime_execution_authority_required
    resident_runtime_execution_authority = [bool]$ResidentRuntimeBoundary.resident_runtime_execution_authority
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority_required = [string]$ResidentRuntimeBoundary.local_process_launch_authority_required
    local_process_launch_authority = $false
    process_supervision_authority_required = [string]$ResidentRuntimeBoundary.process_supervision_authority_required
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority_required = [string]$ResidentRuntimeBoundary.service_control_authority_required
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority_required = [string]$ResidentRuntimeBoundary.tray_registration_authority_required
    tray_registration_authority = $false
    overlay_control_authority_required = [string]$ResidentRuntimeBoundary.overlay_control_authority_required
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority_required = [string]$ResidentRuntimeBoundary.resident_claim_authority_required
    resident_claim_authority = $false
    blockers = [string[]]@($ResidentRuntimeBoundaryBlockers)
  }
  resident_runtime_granted_boundary_proof = [ordered]@{
    status = if ($ResidentRuntimeGrantedBoundaryProofObserved) { [string]$ResidentRuntimeGrantedBoundaryProof.status } else { 'missing_or_failed' }
    ok = $ResidentRuntimeGrantedBoundaryProofObserved
    exit_code = [int]$ResidentRuntimeGrantedBoundaryProof.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $ResidentRuntimeGrantedBoundaryProof.evidence)
    authority_required = [string]$ResidentRuntimeGrantedBoundaryProof.authority_required
    authority_granted = [bool]$ResidentRuntimeGrantedBoundaryProof.authority_granted
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
    authority_required = [string]$ResidentRuntimeAuthorityBlockersProof.authority_required
    authority_granted = [bool]$ResidentRuntimeAuthorityBlockersProof.authority_granted
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
    authority_required = [string]$ResidentRuntimeProcessSupervisionBoundaryProof.authority_required
    authority_granted = [bool]$ResidentRuntimeProcessSupervisionBoundaryProof.authority_granted
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
    authority_required = [string]$ResidentRuntimeServiceControlBoundaryProof.authority_required
    authority_granted = [bool]$ResidentRuntimeServiceControlBoundaryProof.authority_granted
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
    authority_required = [string]$ResidentRuntimeTrayPresenceBoundaryProof.authority_required
    authority_granted = [bool]$ResidentRuntimeTrayPresenceBoundaryProof.authority_granted
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
    authority_required = [string]$ResidentRuntimeHotkeySummonBoundaryProof.authority_required
    authority_granted = [bool]$ResidentRuntimeHotkeySummonBoundaryProof.authority_granted
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
    authority_required = [string]$ResidentRuntimeOverlayWindowBoundaryProof.authority_required
    authority_granted = [bool]$ResidentRuntimeOverlayWindowBoundaryProof.authority_granted
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
    authority_required = [string]$ResidentRuntimeResidentClaimBoundaryProof.authority_required
    authority_granted = [bool]$ResidentRuntimeResidentClaimBoundaryProof.authority_granted
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
    authority_required = [string]$OsBindingAuthorityRequestReadback.authority_required
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
    authority_required = [string]$SummonAuthorityBlockerProof.authority_required
    authority_granted = [bool]$SummonAuthorityBlockerProof.authority_granted
    summon_authority_family_observed = [bool]$SummonAuthorityBlockerProof.summon_authority_family_observed
    previous_summon_binding_contract_observed = [bool]$SummonAuthorityBlockerProof.previous_summon_binding_contract_observed
    previous_summon_binding_contract_readback_observed = [bool]$SummonAuthorityBlockerProof.previous_summon_binding_contract_readback_observed
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
      uses_summon_binding_family_contract_readback = [bool]$SummonAuthorityBlockerProofGovernance.uses_summon_binding_family_contract_readback
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
    recommended_handoff_source = [string]$SummonAnywhereFamilyChainProof.recommended_handoff_source
    recommended_next_slice = [string]$SummonAnywhereFamilyChainProof.recommended_next_slice
    recommended_proof_script = [string]$SummonAnywhereFamilyChainProof.recommended_proof_script
    recommended_handoff = [ordered]@{
      id = [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.id
      status = [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.status
      previous_next_smallest_truthful_gap = [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.previous_next_smallest_truthful_gap
      next_smallest_truthful_gap = [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.next_smallest_truthful_gap
      next_step = [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.next_step
      proof_script = [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.proof_script
      route = [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.route
      readiness_route = [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.readiness_route
      acceptance_criterion = [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.acceptance_criterion
      blocker = [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.blocker
      requirement_state = [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.requirement_state
      authority_required = [string]$SummonAnywhereFamilyChainProofRecommendedHandoff.authority_required
      authority_granted = [bool]$SummonAnywhereFamilyChainProofRecommendedHandoff.authority_granted
      read_only_contract = [bool]$SummonAnywhereFamilyChainProofRecommendedHandoff.read_only_contract
      diagnostic_only = [bool]$SummonAnywhereFamilyChainProofRecommendedHandoff.diagnostic_only
      would_execute = [bool]$SummonAnywhereFamilyChainProofRecommendedHandoff.would_execute
      would_mutate = [bool]$SummonAnywhereFamilyChainProofRecommendedHandoff.would_mutate
      would_register_hotkey = [bool]$SummonAnywhereFamilyChainProofRecommendedHandoff.would_register_hotkey
      would_control_overlay = [bool]$SummonAnywhereFamilyChainProofRecommendedHandoff.would_control_overlay
      would_launch_process = [bool]$SummonAnywhereFamilyChainProofRecommendedHandoff.would_launch_process
      would_supervise_process = [bool]$SummonAnywhereFamilyChainProofRecommendedHandoff.would_supervise_process
      would_claim_resident = [bool]$SummonAnywhereFamilyChainProofRecommendedHandoff.would_claim_resident
      blocked_families = [string[]]@(ConvertTo-StringArray -Value $SummonAnywhereFamilyChainProofRecommendedHandoff.blocked_families)
    }
    authority_required = [string]$SummonAnywhereFamilyChainProof.authority_required
    authority_granted = [bool]$SummonAnywhereFamilyChainProof.authority_granted
    family_chain_observed = [bool]$SummonAnywhereFamilyChainProof.family_chain_observed
    resident_host_family_handoff_observed = [bool]$SummonAnywhereFamilyChainProof.resident_host_family_handoff_observed
    final_summon_authority_handoff_observed = [bool]$SummonAnywhereFamilyChainProof.final_summon_authority_handoff_observed
    final_summon_authority_contract_readback_observed = [bool]$SummonAnywhereFamilyChainProof.final_summon_authority_contract_readback_observed
    all_summon_blocker_families_consumed = [bool]$SummonAnywhereFamilyChainProof.all_summon_blocker_families_consumed
    handoff_aligned = [bool]$SummonAnywhereFamilyChainProof.handoff_aligned
    side_effects_denied = [bool]$SummonAnywhereFamilyChainProof.side_effects_denied
    child_proof_timeout_seconds = [int]$SummonAnywhereFamilyChainProof.child_proof_timeout_seconds
    child_proof_timeouts = [string[]]@(ConvertTo-StringArray -Value $SummonAnywhereFamilyChainProof.child_proof_timeouts)
    child_proof_runs = @($SummonAnywhereFamilyChainProof.child_proof_runs)
    blocked_families = [string[]]@($SummonAnywhereFamilyChainProofBlockedFamilies)
    blocked_family_handoffs = @($SummonAnywhereFamilyChainProof.blocked_family_handoffs)
    first_blocker_family = [string]$SummonAnywhereFamilyChainProof.first_blocker_family
    first_blocker_family_handoff = $SummonAnywhereFamilyChainProof.first_blocker_family_handoff
    resident_host = [ordered]@{
      handoff_source = [string]$SummonAnywhereFamilyChainProofResidentHost.handoff_source
      id = [string]$SummonAnywhereFamilyChainProofResidentHost.id
      status = [string]$SummonAnywhereFamilyChainProofResidentHost.status
      proof_script = [string]$SummonAnywhereFamilyChainProofResidentHost.proof_script
      route = [string]$SummonAnywhereFamilyChainProofResidentHost.route
      readiness_route = [string]$SummonAnywhereFamilyChainProofResidentHost.readiness_route
      next_step = [string]$SummonAnywhereFamilyChainProofResidentHost.next_step
      next_smallest_truthful_gap = [string]$SummonAnywhereFamilyChainProofResidentHost.next_smallest_truthful_gap
      authority_required = [string]$SummonAnywhereFamilyChainProofResidentHost.authority_required
      authority_granted = [bool]$SummonAnywhereFamilyChainProofResidentHost.authority_granted
      read_only_contract = [bool]$SummonAnywhereFamilyChainProofResidentHost.read_only_contract
      diagnostic_only = [bool]$SummonAnywhereFamilyChainProofResidentHost.diagnostic_only
      would_execute = [bool]$SummonAnywhereFamilyChainProofResidentHost.would_execute
      would_mutate = [bool]$SummonAnywhereFamilyChainProofResidentHost.would_mutate
      blockers = [string[]]@($SummonAnywhereFamilyChainProofResidentHostBlockers)
    }
    final_authority = [ordered]@{
      previous_summon_blocker_family = [string]$SummonAnywhereFamilyChainProofFinalAuthority.previous_summon_blocker_family
      summon_authority_blocker_family = [string]$SummonAnywhereFamilyChainProofFinalAuthority.summon_authority_blocker_family
      next_summon_blocker_family = [string]$SummonAnywhereFamilyChainProofFinalAuthority.next_summon_blocker_family
      next_smallest_truthful_gap = [string]$SummonAnywhereFamilyChainProofFinalAuthority.next_smallest_truthful_gap
      authority_required = [string]$SummonAnywhereFamilyChainProofFinalAuthority.authority_required
      authority_granted = [bool]$SummonAnywhereFamilyChainProofFinalAuthority.authority_granted
      all_summon_blocker_families_consumed = [bool]$SummonAnywhereFamilyChainProofFinalAuthority.all_summon_blocker_families_consumed
      previous_summon_binding_contract_observed = [bool]$SummonAnywhereFamilyChainProofFinalAuthority.previous_summon_binding_contract_observed
      previous_summon_binding_contract_readback_observed = [bool]$SummonAnywhereFamilyChainProofFinalAuthority.previous_summon_binding_contract_readback_observed
      previous_binding_handoff = [ordered]@{
        source = [string]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.source
        status = [string]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.status
        contract_status = [string]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.contract_status
        proof_script = [string]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.proof_script
        previous_summon_blocker_family = [string]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.previous_summon_blocker_family
        summon_binding_blocker_family = [string]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.summon_binding_blocker_family
        next_summon_blocker_family = [string]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.next_summon_blocker_family
        next_smallest_truthful_gap = [string]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.next_smallest_truthful_gap
        authority_required = [string]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.authority_required
        authority_granted = [bool]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.authority_granted
        read_only_contract = [bool]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.read_only_contract
        diagnostic_only = [bool]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.diagnostic_only
        would_execute = [bool]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.would_execute
        would_mutate = [bool]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.would_mutate
        handoff_aligned = [bool]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.handoff_aligned
        side_effects_denied = [bool]$SummonAnywhereFamilyChainProofFinalAuthorityPreviousBinding.side_effects_denied
        blockers = [string[]]@($SummonAnywhereFamilyChainProofFinalAuthorityPreviousBindingBlockers)
      }
      blockers = [string[]]@($SummonAnywhereFamilyChainProofFinalAuthorityBlockers)
    }
    governance = [ordered]@{
      diagnostic_only = [bool]$SummonAnywhereFamilyChainProofGovernance.diagnostic_only
      wraps_summon_anywhere_blockers_proof = [bool]$SummonAnywhereFamilyChainProofGovernance.wraps_summon_anywhere_blockers_proof
      uses_summon_anywhere_family_handoff_contract = [bool]$SummonAnywhereFamilyChainProofGovernance.uses_summon_anywhere_family_handoff_contract
      wraps_summon_authority_blocker_proof = [bool]$SummonAnywhereFamilyChainProofGovernance.wraps_summon_authority_blocker_proof
      final_authority_previous_contract_readback = [bool]$SummonAnywhereFamilyChainProofGovernance.final_authority_previous_contract_readback
      read_only_contract = [bool]$SummonAnywhereFamilyChainProofGovernance.read_only_contract
      bounded_local_process_launch = [bool]$SummonAnywhereFamilyChainProofGovernance.bounded_local_process_launch
      temporary_runtime_state_write = [bool]$SummonAnywhereFamilyChainProofGovernance.temporary_runtime_state_write
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
    authority_required = [string]$ResidentHostRuntimeBoundaryProof.authority_required
    authority_granted = [bool]$ResidentHostRuntimeBoundaryProof.authority_granted
    recommended_handoff = [ordered]@{
      id = [string]$ResidentHostRuntimeBoundaryProofRecommendedHandoff.id
      status = [string]$ResidentHostRuntimeBoundaryProofRecommendedHandoff.status
      next_smallest_truthful_gap = [string]$ResidentHostRuntimeBoundaryProofRecommendedHandoff.next_smallest_truthful_gap
      authority_required = [string]$ResidentHostRuntimeBoundaryProofRecommendedHandoff.authority_required
      authority_granted = [bool]$ResidentHostRuntimeBoundaryProofRecommendedHandoff.authority_granted
    }
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
    authority_required = [string]$ProcessSupervisionBoundary.authority_required
    authority_granted = [bool]$ProcessSupervisionBoundary.authority_granted
    process_supervision_authority_required = [string]$ProcessSupervisionBoundary.process_supervision_authority_required
    process_supervision_authority_granted = [bool]$ProcessSupervisionBoundary.process_supervision_authority_granted
    process_restart_authority_required = [string]$ProcessSupervisionBoundary.process_restart_authority_required
    process_restart_authority_granted = [bool]$ProcessSupervisionBoundary.process_restart_authority_granted
    service_install_authority_required = [string]$ProcessSupervisionBoundary.service_install_authority_required
    service_install_authority_granted = [bool]$ProcessSupervisionBoundary.service_install_authority_granted
    service_control_authority_required = [string]$ProcessSupervisionBoundary.service_control_authority_required
    service_control_authority_granted = [bool]$ProcessSupervisionBoundary.service_control_authority_granted
    stage6_checkpoint_observed = [bool]$ProcessSupervisionBoundary.stage6_checkpoint_observed
    resident_overlay_activation_boundary_observed = [bool]$ProcessSupervisionBoundary.resident_overlay_activation_boundary_observed
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
    authority_required = [string]$ResidentHostProcessSupervisionBlockerProof.authority_required
    authority_granted = [bool]$ResidentHostProcessSupervisionBlockerProof.authority_granted
    recommended_handoff = [ordered]@{
      id = [string]$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff.id
      status = [string]$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff.status
      next_step = [string]$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff.next_step
      proof_script = [string]$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff.proof_script
      route = [string]$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff.route
      authority_required = [string]$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff.authority_required
      authority_granted = [bool]$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff.authority_granted
      read_only_contract = [bool]$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff.read_only_contract
      diagnostic_only = [bool]$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff.diagnostic_only
      would_execute = [bool]$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff.would_execute
      would_mutate = [bool]$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff.would_mutate
      would_supervise_process = [bool]$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff.would_supervise_process
      would_restart_process = [bool]$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff.would_restart_process
      would_install_service = [bool]$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff.would_install_service
      would_start_service = [bool]$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff.would_start_service
      would_claim_resident = [bool]$ResidentHostProcessSupervisionBlockerProofRecommendedHandoff.would_claim_resident
    }
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
  resident_supervision_persistence_boundary_proof = [ordered]@{
    status = if ($ResidentSupervisionPersistenceBoundaryProofObserved) { [string]$ResidentSupervisionPersistenceBoundaryProof.status } else { 'missing_or_failed' }
    ok = $ResidentSupervisionPersistenceBoundaryProofObserved
    exit_code = [int]$ResidentSupervisionPersistenceBoundaryProofResult.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $ResidentSupervisionPersistenceBoundaryProof.evidence)
    acceptance_criterion = [string]$ResidentSupervisionPersistenceBoundaryProof.acceptance_criterion
    previous_next_smallest_truthful_gap = [string]$ResidentSupervisionPersistenceBoundaryProof.previous_next_smallest_truthful_gap
    consumed_resident_candidate_next_smallest_truthful_gap = [string]$ResidentSupervisionPersistenceBoundaryProof.consumed_resident_candidate_next_smallest_truthful_gap
    route_next_smallest_truthful_gap = [string]$ResidentSupervisionPersistenceBoundaryProof.route_next_smallest_truthful_gap
    next_smallest_truthful_gap = [string]$ResidentSupervisionPersistenceBoundaryProof.next_smallest_truthful_gap
    recommended_next_slice = [string]$ResidentSupervisionPersistenceBoundaryProof.recommended_next_slice
    recommended_proof_script = [string]$ResidentSupervisionPersistenceBoundaryProof.recommended_proof_script
    recommended_route = [string]$ResidentSupervisionPersistenceBoundaryProof.recommended_route
    recommended_readiness_route = [string]$ResidentSupervisionPersistenceBoundaryProof.recommended_readiness_route
    resident_candidate_boundary_proof_observed = [bool]$ResidentSupervisionPersistenceBoundaryProof.resident_candidate_boundary_proof_observed
    persistent_supervision_plan_candidate_readback_observed = [bool]$ResidentSupervisionPersistenceBoundaryProof.persistent_supervision_plan_candidate_readback_observed
    persistent_supervision_enablement_candidate_readback_observed = [bool]$ResidentSupervisionPersistenceBoundaryProof.persistent_supervision_enablement_candidate_readback_observed
    resident_dependency_candidate_readback_observed = [bool]$ResidentSupervisionPersistenceBoundaryProof.resident_dependency_candidate_readback_observed
    route_blocking_preserved = [bool]$ResidentSupervisionPersistenceBoundaryProof.route_blocking_preserved
    side_effects_bounded = [bool]$ResidentSupervisionPersistenceBoundaryProof.side_effects_bounded
    resident_runtime_candidate_supervised = [bool]$ResidentSupervisionPersistenceBoundaryProof.resident_runtime_candidate_supervised
    resident_supervised_runtime = [bool]$ResidentSupervisionPersistenceBoundaryProof.resident_supervised_runtime
    resident_host_process_requirement_state = [string]$ResidentSupervisionPersistenceBoundaryProof.resident_host_process_requirement_state
    resident_host_process_blocker = [string]$ResidentSupervisionPersistenceBoundaryProof.resident_host_process_blocker
    authority_required = [string]$ResidentSupervisionPersistenceBoundaryProof.authority_required
    authority_granted = [bool]$ResidentSupervisionPersistenceBoundaryProof.authority_granted
    plan_route = [string]$ResidentSupervisionPersistenceBoundaryProof.plan_route
    enablement_route = [string]$ResidentSupervisionPersistenceBoundaryProof.enablement_route
    checks = @($ResidentSupervisionPersistenceBoundaryProof.checks)
    blockers = [string[]]@($ResidentSupervisionPersistenceBoundaryProofBlockers)
    proof = $ResidentSupervisionPersistenceBoundaryProof.proof
    handoff = $ResidentSupervisionPersistenceBoundaryProof.handoff
    governance = $ResidentSupervisionPersistenceBoundaryProofGovernance
  }
  host_supervision_authority_request_proof = [ordered]@{
    status = if ($HostSupervisionAuthorityRequestProofObserved) { [string]$HostSupervisionAuthorityRequestProof.status } else { 'missing_or_failed' }
    ok = $HostSupervisionAuthorityRequestProofObserved
    exit_code = [int]$HostSupervisionAuthorityRequestProofResult.exit_code
    evidence = @(
      'scripts/lens-host-supervision-authority-request-proof.ps1 -Mode Status',
      '/lens/host/supervision/authority/readiness',
      '/lens/host/supervision/authority/request',
      '/lens/host/supervision/authority',
      '/lens/host/supervision/authority/grants',
      '/lens/host/persistent-supervision/enablement',
      '/lens/status'
    )
    host_supervision_authority_approval_id = [string]$HostSupervisionAuthorityRequestProof.host_supervision_authority_approval_id
    host_supervision_authority_grant_receipt_id = [string]$HostSupervisionAuthorityRequestProof.host_supervision_authority_grant_receipt_id
    authority_granted = [bool]$HostSupervisionAuthorityRequestProof.authority_granted
    grant_applied = [bool]$HostSupervisionAuthorityRequestProof.grant_applied
    executed = [bool]$HostSupervisionAuthorityRequestProof.executed
    supervision_ready = [bool]$HostSupervisionAuthorityRequestProof.supervision_ready
    resident_claim_allowed = [bool]$HostSupervisionAuthorityRequestProof.resident_claim_allowed
    process_supervision_authority = [bool]$HostSupervisionAuthorityRequestProof.process_supervision_authority
    process_restart_authority = [bool]$HostSupervisionAuthorityRequestProof.process_restart_authority
    service_install_authority = [bool]$HostSupervisionAuthorityRequestProof.service_install_authority
    service_control_authority = [bool]$HostSupervisionAuthorityRequestProof.service_control_authority
    receipt_write_authority = [bool]$HostSupervisionAuthorityRequestProof.receipt_write_authority
    resident_claim_authority = [bool]$HostSupervisionAuthorityRequestProof.resident_claim_authority
    memory_write = [bool]$HostSupervisionAuthorityRequestProof.memory_write
    runtime_files = $HostSupervisionAuthorityRequestProofRuntimeFiles
    blockers = [string[]]@($HostSupervisionAuthorityRequestProofBlockers)
    next_smallest_truthful_gap = [string]$HostSupervisionAuthorityRequestProof.next_smallest_truthful_gap
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
  persistent_supervision_prerequisites_proof = [ordered]@{
    status = if ($PersistentSupervisionPrerequisitesProofObserved) { [string]$PersistentSupervisionPrerequisitesProof.status } else { 'missing_or_failed' }
    ok = $PersistentSupervisionPrerequisitesProofObserved
    exit_code = [int]$PersistentSupervisionPrerequisitesProofResult.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $PersistentSupervisionPrerequisitesProof.evidence)
    acceptance_criterion = [string]$PersistentSupervisionPrerequisitesProof.acceptance_criterion
    plan_route = [string]$PersistentSupervisionPrerequisitesProof.plan_route
    enablement_route = [string]$PersistentSupervisionPrerequisitesProof.enablement_route
    route_next_smallest_truthful_gap = [string]$PersistentSupervisionPrerequisitesProof.route_next_smallest_truthful_gap
    guard_next_smallest_truthful_gap = [string]$PersistentSupervisionPrerequisitesProof.guard_next_smallest_truthful_gap
    summon_family_contract_next_smallest_truthful_gap = [string]$PersistentSupervisionPrerequisitesProof.summon_family_contract_next_smallest_truthful_gap
    next_smallest_truthful_gap = [string]$PersistentSupervisionPrerequisitesProof.next_smallest_truthful_gap
    authority_required = [string]$PersistentSupervisionPrerequisitesProof.authority_required
    authority_granted = [bool]$PersistentSupervisionPrerequisitesProof.authority_granted
    persistent_supervision_plan_readback_observed = [bool]$PersistentSupervisionPrerequisitesProof.persistent_supervision_plan_readback_observed
    persistent_supervision_enablement_readback_observed = [bool]$PersistentSupervisionPrerequisitesProof.persistent_supervision_enablement_readback_observed
    required_before_enable_observed = [bool]$PersistentSupervisionPrerequisitesProof.required_before_enable_observed
    missing_required_before_enable_observed = [bool]$PersistentSupervisionPrerequisitesProof.missing_required_before_enable_observed
    required_before_enable_guard_observed = [bool]$PersistentSupervisionPrerequisitesProof.required_before_enable_guard_observed
    dependency_readback_observed = [bool]$PersistentSupervisionPrerequisitesProof.dependency_readback_observed
    summon_family_contract_observed = [bool]$PersistentSupervisionPrerequisitesProof.summon_family_contract_observed
    prerequisites_mapped_to_summon_family_contract = [bool]$PersistentSupervisionPrerequisitesProof.prerequisites_mapped_to_summon_family_contract
    first_missing_requirement_proof_observed = [bool]$PersistentSupervisionPrerequisitesProof.first_missing_requirement_proof_observed
    first_missing_requirement_side_effects_bounded = [bool]$PersistentSupervisionPrerequisitesProof.first_missing_requirement_side_effects_bounded
    lens_status_operator_readback_observed = [bool]$PersistentSupervisionPrerequisitesProof.lens_status_operator_readback_observed
    side_effects_denied = [bool]$PersistentSupervisionPrerequisitesProof.side_effects_denied
    side_effects_bounded = [bool]$PersistentSupervisionPrerequisitesProof.side_effects_bounded
    required_before_enable = [string[]]@($PersistentSupervisionPrerequisitesRequiredBeforeEnable)
    missing_required_before_enable = [string[]]@($PersistentSupervisionPrerequisitesMissingRequiredBeforeEnable)
    first_missing_required_before_enable = $PersistentSupervisionPrerequisitesFirstMissingRequiredBeforeEnable
    first_missing_requirement_handoff = $PersistentSupervisionPrerequisitesFirstMissingRequirementHandoff
    dependency_readback = @($PersistentSupervisionPrerequisitesProof.dependency_readback)
    summon_family_contract = $PersistentSupervisionPrerequisitesProof.summon_family_contract
    first_missing_requirement_proof = $PersistentSupervisionPrerequisitesProof.first_missing_requirement_proof
    route_readback = $PersistentSupervisionPrerequisitesProof.route_readback
    guard_readback = $PersistentSupervisionPrerequisitesProof.guard_readback
    checks = @($PersistentSupervisionPrerequisitesProof.checks)
    governance = $PersistentSupervisionPrerequisitesProofGovernance
  }
  persistent_supervision_service_install_plan_proof = [ordered]@{
    status = if ($PersistentSupervisionServiceInstallPlanProofObserved) { [string]$PersistentSupervisionServiceInstallPlanProof.status } else { 'missing_or_failed' }
    ok = $PersistentSupervisionServiceInstallPlanProofObserved
    exit_code = [int]$PersistentSupervisionServiceInstallPlanProofResult.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $PersistentSupervisionServiceInstallPlanProof.evidence)
    service_config = [string]$PersistentSupervisionServiceInstallPlanProof.service_config
    service_install_script = [string]$PersistentSupervisionServiceInstallPlanProof.service_install_script
    windows_service_supported = [bool]$PersistentSupervisionServiceInstallPlanProof.windows_service_supported
    service_install_plan_supported = [bool]$PersistentSupervisionServiceInstallPlanProof.service_install_plan_supported
    service_install_report = [string]$PersistentSupervisionServiceInstallPlanProof.service_install_report
    service_name = [string]$PersistentSupervisionServiceInstallPlanProof.service_name
    service_plan_status = [string]$PersistentSupervisionServiceInstallPlanProof.service_plan_status
    service_plan_ready = [bool]$PersistentSupervisionServiceInstallPlanProof.service_plan_ready
    service_plan_would_install = [bool]$PersistentSupervisionServiceInstallPlanProof.service_plan_would_install
    service_plan_would_start = [bool]$PersistentSupervisionServiceInstallPlanProof.service_plan_would_start
    process_supervision_enabled = [bool]$PersistentSupervisionServiceInstallPlanProof.process_supervision_enabled
    persistent_supervision_enabled = [bool]$PersistentSupervisionServiceInstallPlanProof.persistent_supervision_enabled
    persistent_supervision_config_gate_enabled = [bool]$PersistentSupervisionServiceInstallPlanProof.persistent_supervision_config_gate_enabled
    persistent_supervision_enablement_disabled = [bool]$PersistentSupervisionServiceInstallPlanProof.persistent_supervision_enablement_disabled
    installable = [bool]$PersistentSupervisionServiceInstallPlanProof.installable
    install_authority = [bool]$PersistentSupervisionServiceInstallPlanProof.install_authority
    service_install_authority = [bool]$PersistentSupervisionServiceInstallPlanProof.service_install_authority
    service_control_authority = [bool]$PersistentSupervisionServiceInstallPlanProof.service_control_authority
    authority_required = [string]$PersistentSupervisionServiceInstallPlanProof.authority_required
    authority_granted = [bool]$PersistentSupervisionServiceInstallPlanProof.authority_granted
    wrapper_created_by_proof = [bool]$PersistentSupervisionServiceInstallPlanProof.wrapper_created_by_proof
    blocked_by = [string[]]@($PersistentSupervisionServiceInstallPlanProofBlockedBy)
    required_before_enable = [string[]]@($PersistentSupervisionServiceInstallPlanProofRequiredBeforeEnable)
    checks = @($PersistentSupervisionServiceInstallPlanProof.checks)
    governance = $PersistentSupervisionServiceInstallPlanProofGovernance
    next_smallest_truthful_gap = [string]$PersistentSupervisionServiceInstallPlanProof.next_smallest_truthful_gap
  }
  persistent_supervision_enablement_denial_boundary = [ordered]@{
    status = if ($PersistentSupervisionEnablementDenialObserved) { [string]$PersistentSupervisionEnablementDenial.status } else { 'missing_or_failed' }
    ok = $PersistentSupervisionEnablementDenialObserved
    evidence = [string[]]@(ConvertTo-StringArray -Value $PersistentSupervisionEnablementDenial.evidence)
    boundary_ready = [bool]$PersistentSupervisionEnablementDenial.boundary_ready
    applied = [bool]$PersistentSupervisionEnablementDenial.applied
    executed = [bool]$PersistentSupervisionEnablementDenial.executed
    authority_required = [string]$PersistentSupervisionEnablementDenial.authority_required
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
    service_config_write_authority_required = [string]$PersistentSupervisionEnablementDenial.service_config_write_authority_required
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
    enablement_authority_required = [string]$PersistentSupervisionEnablementExecutionDenial.enablement_authority_required
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
    service_config_write_authority_required = [string]$PersistentSupervisionEnablementExecutionDenial.service_config_write_authority_required
    service_config_write_authority = $false
    persistent_supervision_execution_authority_required = [string]$PersistentSupervisionEnablementExecutionDenial.persistent_supervision_execution_authority_required
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
    authority_required = [string]$PersistentSupervisionEnablementAuthorityProof.authority_required
    authority_granted = [bool]$PersistentSupervisionEnablementAuthorityProof.authority_granted
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
    authority_required = [string]$PersistentSupervisionExecutionAuthorityProof.authority_required
    authority_granted = [bool]$PersistentSupervisionExecutionAuthorityProof.authority_granted
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
    authority_required = [string]$PersistentSupervisionResidentClaimBoundaryProof.authority_required
    authority_granted = [bool]$PersistentSupervisionResidentClaimBoundaryProof.authority_granted
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
  persistent_supervision_enablement_transition_plan_proof = [ordered]@{
    status = if ($PersistentSupervisionEnablementTransitionPlanProofObserved) { [string]$PersistentSupervisionEnablementTransitionPlanProof.status } else { 'missing_or_failed' }
    ok = $PersistentSupervisionEnablementTransitionPlanProofObserved
    exit_code = [int]$PersistentSupervisionEnablementTransitionPlanProofResult.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $PersistentSupervisionEnablementTransitionPlanProof.evidence)
    transition_plan_observed = [bool]$PersistentSupervisionEnablementTransitionPlanProof.transition_plan_observed
    transition_plan_ready = [bool]$PersistentSupervisionEnablementTransitionPlanProof.transition_plan_ready
    persistent_supervision_config_gate_enabled = [bool]$PersistentSupervisionEnablementTransitionPlanProof.persistent_supervision_config_gate_enabled
    persistent_supervision_enablement_disabled = [bool]$PersistentSupervisionEnablementTransitionPlanProof.persistent_supervision_enablement_disabled
    persistent_supervision_prerequisites_readback_observed = [bool]$PersistentSupervisionEnablementTransitionPlanProof.persistent_supervision_prerequisites_readback_observed
    persistent_supervision_required_prerequisites_guard_observed = [bool]$PersistentSupervisionEnablementTransitionPlanProof.persistent_supervision_required_prerequisites_guard_observed
    persistent_supervision_service_install_plan_proof_observed = [bool]$PersistentSupervisionEnablementTransitionPlanProof.persistent_supervision_service_install_plan_proof_observed
    persistent_supervision_resident_claim_boundary_observed = [bool]$PersistentSupervisionEnablementTransitionPlanProof.persistent_supervision_resident_claim_boundary_observed
    persistent_supervision_plan_observed = [bool]$PersistentSupervisionEnablementTransitionPlanProof.persistent_supervision_plan_observed
    windows_service_supported = [bool]$PersistentSupervisionEnablementTransitionPlanProof.windows_service_supported
    service_install_plan_supported = [bool]$PersistentSupervisionEnablementTransitionPlanProof.service_install_plan_supported
    service_plan_status = [string]$PersistentSupervisionEnablementTransitionPlanProof.service_plan_status
    service_plan_blocked_by = [string[]]@($PersistentSupervisionEnablementTransitionPlanProofServicePlanBlockedBy)
    required_before_enable = [string[]]@($PersistentSupervisionEnablementTransitionPlanProofRequiredBeforeEnable)
    enabled_config_toggles = [string[]]@($PersistentSupervisionEnablementTransitionPlanProofEnabledConfigToggles)
    disabled_config_toggles = [string[]]@($PersistentSupervisionEnablementTransitionPlanProofDisabledConfigToggles)
    authority_chain = $PersistentSupervisionEnablementTransitionPlanProof.authority_chain
    side_effects_denied = [bool]$PersistentSupervisionEnablementTransitionPlanProof.side_effects_denied
    applied = [bool]$PersistentSupervisionEnablementTransitionPlanProof.applied
    executed = [bool]$PersistentSupervisionEnablementTransitionPlanProof.executed
    service_config_updated = [bool]$PersistentSupervisionEnablementTransitionPlanProof.service_config_updated
    would_update_service_config = [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_update_service_config
    would_enable_process_supervision = [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_enable_process_supervision
    would_enable_persistent_supervision = [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_enable_persistent_supervision
    would_install_service = [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_install_service
    would_start_service = [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_start_service
    would_supervise_process = [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_supervise_process
    would_restart_process = [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_restart_process
    would_write_receipt = [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_write_receipt
    would_write_memory = [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_write_memory
    would_claim_resident = [bool]$PersistentSupervisionEnablementTransitionPlanProof.would_claim_resident
    transition_plan = @($PersistentSupervisionEnablementTransitionPlanProof.transition_plan)
    checks = @($PersistentSupervisionEnablementTransitionPlanProof.checks)
    blockers = [string[]]@($PersistentSupervisionEnablementTransitionPlanProofBlockers)
    governance = $PersistentSupervisionEnablementTransitionPlanProofGovernance
    next_smallest_truthful_gap = [string]$PersistentSupervisionEnablementTransitionPlanProof.next_smallest_truthful_gap
  }
  stage6_prerequisite_bringup_plan = [ordered]@{
    status = if ($Stage6PrerequisiteBringupPlanObserved) { [string]$Stage6PrerequisiteBringupPlan.status } else { 'missing_or_failed' }
    ok = $Stage6PrerequisiteBringupPlanObserved
    missing_prerequisites_readback = $Stage6PrerequisiteBringupPlanMissingPrerequisitesObserved
    applied_enablement_readback = $Stage6PrerequisiteBringupPlanAppliedEnablementObserved
    read_only_governance_readback = $Stage6PrerequisiteBringupPlanReadOnlyGovernanceObserved
    exit_code = [int]$Stage6PrerequisiteBringupPlanResult.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value $Stage6PrerequisiteBringupPlan.evidence)
    current_truthful_gap = [string]$Stage6PrerequisiteBringupPlan.current_truthful_gap
    current_truthful_gap_basis = [string]$Stage6PrerequisiteBringupPlan.current_truthful_gap_basis
    current_first_missing_requirement = [string]$Stage6PrerequisiteBringupPlan.current_first_missing_requirement
    current_first_missing_truthful_gap = [string]$Stage6PrerequisiteBringupPlan.current_first_missing_truthful_gap
    required_before_enable = [string[]]@($Stage6PrerequisiteBringupPlanRequiredBeforeEnable)
    missing_required_before_enable = [string[]]@($Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable)
    required_before_enable_ready = [bool]$Stage6PrerequisiteBringupPlan.required_before_enable_ready
    next_operator_action_requirement = [string]$Stage6PrerequisiteBringupPlan.next_operator_action_requirement
    next_operator_action = $Stage6PrerequisiteBringupPlanNextOperatorAction
    next_operator_command = $Stage6PrerequisiteBringupPlanNextOperatorCommand
    operator_sequence_command_availability = $Stage6PrerequisiteBringupPlanCommandAvailability
    checks = @($Stage6PrerequisiteBringupPlan.checks)
    governance = $Stage6PrerequisiteBringupPlanGovernance
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
    'scripts/lens-host-supervision-authority-request-proof.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-plan.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status',
    'scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-service-install-plan-proof.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-execution-authority-proof.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-enablement-transition-plan-proof.ps1 -Mode Status',
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
  helpful_not_noisy_runtime_authority_readiness_handoff = [ordered]@{
    status = [string]$ResidentRuntimeAuthorityGrantReadiness.status
    audit_status = [string]$ResidentRuntimeAuthorityGrantReadiness.audit_status
    ok = [bool]$ResidentRuntimeAuthorityGrantReadiness.ok
    ready = [bool]$ResidentRuntimeAuthorityGrantReadiness.ready
    readback_ready = [bool]$ResidentRuntimeAuthorityGrantReadiness.operator_surface_readback_ready
    handoff_observed = $ResidentRuntimeAuthorityGrantReadinessHandoffObserved
    first_blocked_requirement = $ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirement
    first_blocked_requirement_handoff = $ResidentRuntimeAuthorityGrantReadinessFirstBlockedRequirementHandoff
    blocked_requirements = $ResidentRuntimeAuthorityGrantReadinessBlockedRequirements
    blocked_requirement_handoffs = $ResidentRuntimeAuthorityGrantReadinessBlockedRequirementHandoffs
    next_smallest_truthful_gap = [string]$ResidentRuntimeAuthorityGrantReadiness.next_smallest_truthful_gap
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
    resident_supervision_persistence_boundary_proof_readback = $ResidentSupervisionPersistenceBoundaryProofObserved
    resident_host_supervision_authority_readiness_handoff_readback = $HostSupervisionAuthorityReadinessHandoffObserved
    host_supervision_authority_request_proof_readback = $HostSupervisionAuthorityRequestProofObserved
    helpful_not_noisy_runtime_authority_readiness_handoff_readback = $ResidentRuntimeAuthorityGrantReadinessHandoffObserved
    persistent_supervision_plan_readback = $PersistentSupervisionPlanObserved
    persistent_supervision_prerequisites_proof_readback = $PersistentSupervisionPrerequisitesProofObserved
    stage6_prerequisite_bringup_plan_readback = $Stage6PrerequisiteBringupPlanObserved
    stage6_prerequisite_bringup_plan_missing_prerequisites_readback = $Stage6PrerequisiteBringupPlanMissingPrerequisitesObserved
    stage6_prerequisite_bringup_plan_applied_enablement_readback = $Stage6PrerequisiteBringupPlanAppliedEnablementObserved
    persistent_supervision_service_install_plan_proof_readback = $PersistentSupervisionServiceInstallPlanProofObserved
    persistent_supervision_enablement_authority_proof_readback = $PersistentSupervisionEnablementAuthorityProofObserved
    persistent_supervision_execution_authority_proof_readback = $PersistentSupervisionExecutionAuthorityProofObserved
    persistent_supervision_resident_claim_boundary_proof_readback = $PersistentSupervisionResidentClaimBoundaryObserved
    persistent_supervision_enablement_transition_plan_proof_readback = $PersistentSupervisionEnablementTransitionPlanProofObserved
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

$Payload | ConvertTo-Json -Depth 12
exit 0
