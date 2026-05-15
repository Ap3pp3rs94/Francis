param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',
  [string]$DataDir = ''
)

$ErrorActionPreference = 'Stop'

function Get-PropertyValue {
  param([object]$Payload, [string]$Name, [object]$Default = $null)
  if ($null -eq $Payload) { return $Default }
  if ($Payload -is [System.Collections.IDictionary]) {
    if ($Payload.Contains($Name) -and $null -ne $Payload[$Name]) { return $Payload[$Name] }
    return $Default
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) { return $Default }
  return $Property.Value
}

function ConvertTo-StringArray {
  param([object]$Value)
  if ($null -eq $Value) { return @() }
  if ($Value -is [System.Array]) {
    return @($Value | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  }
  $Text = [string]$Value
  if ([string]::IsNullOrWhiteSpace($Text)) { return @() }
  return @($Text)
}

function Invoke-JsonScript {
  param([string]$PowerShellPath, [string]$ScriptPath, [string[]]$ScriptArgs = @())
  $Output = & $PowerShellPath -NoProfile -ExecutionPolicy Bypass -File $ScriptPath @ScriptArgs 2>&1
  $ExitCode = $LASTEXITCODE
  $Text = ($Output | ForEach-Object { [string]$_ }) -join "`n"
  $Payload = $null
  try { $Payload = $Text | ConvertFrom-Json -ErrorAction Stop } catch { $Payload = $null }
  return [ordered]@{ exit_code = $ExitCode; payload = $Payload; output = $Text }
}

function New-Check {
  param([string]$Id, [string]$Status, [bool]$Passed, [string]$Evidence, [string]$Reason)
  return [ordered]@{ id = $Id; status = $Status; passed = $Passed; evidence = $Evidence; reason = $Reason }
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot
$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) { $PowerShell = Get-Command powershell -ErrorAction Stop }

$ExecutionAuthorityScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-execution-authority-proof.ps1'
$PersistentSupervisionPlanScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-plan.ps1'
foreach ($ScriptPath in @($ExecutionAuthorityScript, $PersistentSupervisionPlanScript)) {
  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) { throw "Required Lens proof script is missing: $ScriptPath" }
}

$PreviousDataDir = [string]$env:FRANCIS_DATA_DIR
$ProofDataDir = $DataDir
if ([string]::IsNullOrWhiteSpace($ProofDataDir)) {
  $ProofDataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-persistent-supervision-resident-claim-boundary-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}
$ProofDataDir = [System.IO.Path]::GetFullPath($ProofDataDir)

$ExecutionArgs = @('-Mode', $Mode, '-DataDir', $ProofDataDir)
$PlanArgs = @('-Mode', $Mode)
try {
  $env:FRANCIS_DATA_DIR = $ProofDataDir
  $ExecutionResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $ExecutionAuthorityScript -ScriptArgs $ExecutionArgs
  $PlanResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $PersistentSupervisionPlanScript -ScriptArgs $PlanArgs
} finally {
  if ([string]::IsNullOrWhiteSpace($PreviousDataDir)) {
    Remove-Item Env:\FRANCIS_DATA_DIR -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_DATA_DIR = $PreviousDataDir
  }
}

$Execution = Get-PropertyValue -Payload $ExecutionResult -Name 'payload'
$Plan = Get-PropertyValue -Payload $PlanResult -Name 'payload'
$ExecutionProof = Get-PropertyValue -Payload $Execution -Name 'proof'
$ExecutionGovernance = Get-PropertyValue -Payload $Execution -Name 'governance'
$ExecutionBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Execution -Name 'blockers' -Default @())
$PlanBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Plan -Name 'blockers' -Default @())
$CombinedBlockers = @($ExecutionBlockers + $PlanBlockers | Sort-Object -Unique)

$ExecutionAuthorityObserved = (
  [int](Get-PropertyValue -Payload $ExecutionResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $Execution -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_execution_authority.proof' -and
  [string](Get-PropertyValue -Payload $Execution -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $Execution -Name 'ok' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Execution -Name 'persistent_supervision_enablement_authority' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Execution -Name 'service_config_write_authority' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Execution -Name 'persistent_supervision_execution_authority' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Execution -Name 'receipt_write_authority' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Execution -Name 'resident_claim_allowed' -Default $true) -and
  [string](Get-PropertyValue -Payload $ExecutionProof -Name 'execution_denial_status' -Default '') -eq 'denied_no_resident_claim_authority' -and
  $ExecutionBlockers -contains 'resident_claim_authority_not_granted'
)
$PlanObserved = (
  [int](Get-PropertyValue -Payload $PlanResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $Plan -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_plan' -and
  [bool](Get-PropertyValue -Payload $Plan -Name 'ok' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Plan -Name 'plan_available' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Plan -Name 'persistent_supervision_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Plan -Name 'resident_claim_allowed' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Plan -Name 'required_before_enable_ready' -Default $true) -and
  $PlanBlockers -contains 'persistent_supervision_required_prerequisites_missing'
)
$ResidentClaimBoundaryObserved = (
  $ExecutionAuthorityObserved -and
  $PlanObserved -and
  $ExecutionBlockers -contains 'persistent_supervision_required_prerequisites_missing' -and
  $ExecutionBlockers -contains 'resident_claim_authority_not_granted' -and
  -not ($ExecutionBlockers -contains 'service_config_write_authority_not_granted') -and
  -not ($ExecutionBlockers -contains 'persistent_supervision_execution_authority_not_granted') -and
  -not ($ExecutionBlockers -contains 'receipt_write_authority_not_granted')
)
$SideEffectsDenied = (
  $ResidentClaimBoundaryObserved -and
  -not [bool](Get-PropertyValue -Payload $Execution -Name 'applied' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Execution -Name 'executed' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Execution -Name 'service_config_updated' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Execution -Name 'would_update_service_config' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Execution -Name 'would_enable_persistent_supervision' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Execution -Name 'would_start_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Execution -Name 'would_supervise_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Execution -Name 'would_restart_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Execution -Name 'would_write_receipt' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Execution -Name 'would_write_memory' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Execution -Name 'would_claim_resident' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload (Get-PropertyValue -Payload $Plan -Name 'plan') -Name 'would_install_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload (Get-PropertyValue -Payload $Plan -Name 'plan') -Name 'would_start_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload (Get-PropertyValue -Payload $Plan -Name 'plan') -Name 'would_write_memory' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload (Get-PropertyValue -Payload $Plan -Name 'plan') -Name 'would_claim_resident' -Default $true)
)
$AuthorityBoundaryObserved = (
  $SideEffectsDenied -and
  [bool](Get-PropertyValue -Payload $ExecutionGovernance -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ExecutionGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ExecutionGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ExecutionGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ExecutionGovernance -Name 'resident_claim_authority' -Default $true)
)

$Checks = @(
  (New-Check -Id 'persistent_supervision_execution_authority_proof' -Status $(if ($ExecutionAuthorityObserved) { 'proof_observed' } else { 'missing_or_failed' }) -Passed $ExecutionAuthorityObserved -Evidence 'scripts/lens-persistent-supervision-execution-authority-proof.ps1 -Mode Status' -Reason 'Persistent supervision execution authority must be proven before resident claim can be named as the remaining boundary.')
  (New-Check -Id 'persistent_supervision_plan_readback' -Status $(if ($PlanObserved) { 'blocked' } else { 'missing_or_unexpected' }) -Passed $PlanObserved -Evidence 'scripts/lens-persistent-supervision-plan.ps1 -Mode Status' -Reason 'The persistent supervision plan must remain blocked before any resident claim can be truthful.')
  (New-Check -Id 'resident_claim_boundary' -Status $(if ($ResidentClaimBoundaryObserved) { 'blocked' } else { 'missing_or_unexpected' }) -Passed $ResidentClaimBoundaryObserved -Evidence '/lens/host/persistent-supervision/enablement/execution' -Reason 'Execution authority must still stop at resident-claim/runtime readiness.')
  (New-Check -Id 'resident_claim_side_effects_denied' -Status $(if ($SideEffectsDenied) { 'denied_no_resident_claim' } else { 'unexpected_side_effect' }) -Passed $SideEffectsDenied -Evidence 'persistent_supervision_execution_proof.would_*' -Reason 'The proof must not update service config, start/supervise/restart a runtime, write memory, write receipts, or claim residency.')
  (New-Check -Id 'authority_boundary' -Status $(if ($AuthorityBoundaryObserved) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $AuthorityBoundaryObserved -Evidence 'persistent_supervision_execution_proof.governance' -Reason 'This proof must not grant product execution, approval-decision, memory, or resident-claim authority.')
)
$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

[ordered]@{
  ok = $ProofPassed
  kind = 'lens.host.persistent_supervision_resident_claim_boundary.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  data_root = $ProofDataDir
  authority_family = 'resident_claim'
  previous_authority_family = 'persistent_supervision_execution'
  next_authority_family = ''
  persistent_supervision_resident_claim_boundary_observed = $ResidentClaimBoundaryObserved
  persistent_supervision_execution_authority_proof_observed = $ExecutionAuthorityObserved
  persistent_supervision_plan_observed = $PlanObserved
  side_effects_denied = $SideEffectsDenied
  final_persistent_supervision_authority_family_consumed = $ResidentClaimBoundaryObserved
  persistent_supervision_enablement_authority = [bool](Get-PropertyValue -Payload $Execution -Name 'persistent_supervision_enablement_authority' -Default $false)
  service_config_write_authority = [bool](Get-PropertyValue -Payload $Execution -Name 'service_config_write_authority' -Default $false)
  persistent_supervision_execution_authority = [bool](Get-PropertyValue -Payload $Execution -Name 'persistent_supervision_execution_authority' -Default $false)
  receipt_write_authority = [bool](Get-PropertyValue -Payload $Execution -Name 'receipt_write_authority' -Default $false)
  resident_claim_authority = $false
  persistent_supervision_ready = [bool](Get-PropertyValue -Payload $Plan -Name 'persistent_supervision_ready' -Default $false)
  resident_claim_allowed = $false
  applied = [bool](Get-PropertyValue -Payload $Execution -Name 'applied' -Default $false)
  executed = [bool](Get-PropertyValue -Payload $Execution -Name 'executed' -Default $false)
  service_config_updated = [bool](Get-PropertyValue -Payload $Execution -Name 'service_config_updated' -Default $false)
  would_update_service_config = [bool](Get-PropertyValue -Payload $Execution -Name 'would_update_service_config' -Default $false)
  would_enable_persistent_supervision = [bool](Get-PropertyValue -Payload $Execution -Name 'would_enable_persistent_supervision' -Default $false)
  would_start_service = [bool](Get-PropertyValue -Payload $Execution -Name 'would_start_service' -Default $false)
  would_supervise_process = [bool](Get-PropertyValue -Payload $Execution -Name 'would_supervise_process' -Default $false)
  would_restart_process = [bool](Get-PropertyValue -Payload $Execution -Name 'would_restart_process' -Default $false)
  would_write_receipt = [bool](Get-PropertyValue -Payload $Execution -Name 'would_write_receipt' -Default $false)
  would_write_memory = [bool](Get-PropertyValue -Payload $Execution -Name 'would_write_memory' -Default $false)
  would_claim_resident = [bool](Get-PropertyValue -Payload $Execution -Name 'would_claim_resident' -Default $false)
  resident_claim = [ordered]@{
    status = 'blocked'
    ready = $false
    authority_granted = $false
    would_execute = $false
    route = '/lens/host/persistent-supervision/enablement/execution'
    evidence = @(
      '/lens/host/persistent-supervision/enablement/execution',
      '/lens/host/persistent-supervision/enablement/execution/readiness',
      'scripts/lens-persistent-supervision-plan.ps1 -Mode Status'
    )
    required_before = @(
      'resident_host_process',
      'tray_presence',
      'global_hotkey_binding',
      'overlay_window',
      'summon_binding',
      'resident_claim_authority'
    )
    blockers = [string[]]@($ExecutionBlockers)
  }
  checks = @($Checks)
  blockers = [string[]]@($CombinedBlockers)
  remaining_authority_families_after_this_boundary = [string[]]@()
  previous_next_smallest_truthful_gap = 'persistent_supervision_resident_claim_authority_boundary'
  next_smallest_truthful_gap = 'stage6_lens_completion_audit'
  recommended_next_slice = 'run_stage6_lens_completion_audit_after_resident_claim_boundary_readback'
  recommended_proof_script = 'scripts/lens-stage6-completion-audit.ps1 -Mode Status'
  recommended_handoff_source = 'persistent_supervision_resident_claim_boundary_handoff'
  authority_required = 'none_new_stage6_completion_audit'
  recommended_route = '/lens/host/persistent-supervision/enablement/execution'
  recommended_readiness_route = '/lens/host/persistent-supervision/enablement/execution/readiness'
  stage6_completion_audit_script = 'scripts/lens-stage6-completion-audit.ps1'
  persistent_supervision_execution_route = '/lens/host/persistent-supervision/enablement/execution'
  persistent_supervision_execution_readiness_route = '/lens/host/persistent-supervision/enablement/execution/readiness'
  persistent_supervision_plan_script = 'scripts/lens-persistent-supervision-plan.ps1'
  handoff = [ordered]@{
    recommended_handoff_source = 'persistent_supervision_resident_claim_boundary_handoff'
    status = 'audit_needed'
    previous_next_smallest_truthful_gap = 'persistent_supervision_resident_claim_authority_boundary'
    next_smallest_truthful_gap = 'stage6_lens_completion_audit'
    next_step = 'run_stage6_lens_completion_audit_after_resident_claim_boundary_readback'
    proof_script = 'scripts/lens-stage6-completion-audit.ps1 -Mode Status'
    route = '/lens/host/persistent-supervision/enablement/execution'
    readiness_route = '/lens/host/persistent-supervision/enablement/execution/readiness'
    authority_required = 'none_new_stage6_completion_audit'
    authority_granted = $false
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
  }
  evidence = @(
    'scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-execution-authority-proof.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-plan.ps1 -Mode Status',
    '/lens/host/persistent-supervision/enablement/execution',
    '/lens/host/persistent-supervision/enablement/execution/readiness',
    '/lens/status'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_existing_execution_authority_proof = $true
    persistent_supervision_plan_readback = $PlanObserved
    test_fixture_approval_decisions = $true
    test_fixture_authority_receipts = $true
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    service_config_write_authority = $false
    persistent_supervision_enablement_authority = $false
    persistent_supervision_execution_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'The persistent-supervision resident-claim boundary is consumed as diagnostic readback: execution authority is proven, but persistent supervision remains blocked by resident host, tray, hotkey, overlay, summon, and resident-claim authority without service config mutation, runtime launch, memory writes, receipts, or resident claim.'
} | ConvertTo-Json -Depth 8

exit $(if ($ProofPassed) { 0 } else { 1 })
