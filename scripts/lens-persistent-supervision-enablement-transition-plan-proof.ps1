param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',
  [string]$DataDir = '',

  [ValidateRange(30, 600)]
  [int]$ChildProofTimeoutSeconds = 240
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

function Test-StringArrayExact {
  param([string[]]$Actual, [string[]]$Expected)
  if (@($Actual).Count -ne @($Expected).Count) { return $false }
  for ($Index = 0; $Index -lt @($Expected).Count; $Index++) {
    if ([string]$Actual[$Index] -ne [string]$Expected[$Index]) { return $false }
  }
  return $true
}

function Quote-ProcessArgument {
  param([string]$Value)
  if ($null -eq $Value) { return '""' }
  return '"' + ($Value -replace '"', '\"') + '"'
}

function Stop-ProcessTree {
  param([System.Diagnostics.Process]$Process)
  if ($null -eq $Process -or $Process.HasExited) { return }
  try {
    $Process.Kill($true)
  } catch {
    try { $Process.Kill() } catch {}
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
  try { $Payload = $Text | ConvertFrom-Json -ErrorAction Stop } catch { $Payload = $null }
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

function New-Check {
  param([string]$Id, [string]$Status, [bool]$Passed, [string]$Evidence, [string]$Reason)
  return [ordered]@{ id = $Id; status = $Status; passed = $Passed; evidence = $Evidence; reason = $Reason }
}

function New-TransitionStep {
  param(
    [string]$Id,
    [string]$Label,
    [string]$Status,
    [bool]$Ready,
    [string]$Evidence,
    [string[]]$Blockers = @(),
    [string]$NextStep = ''
  )
  return [ordered]@{
    id = $Id
    label = $Label
    status = $Status
    ready = $Ready
    evidence = $Evidence
    blockers = [string[]]@($Blockers)
    next_step = $NextStep
    would_execute = $false
    would_mutate = $false
  }
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

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot
$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) { $PowerShell = Get-Command powershell -ErrorAction Stop }

$ServicePlanProofScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-service-install-plan-proof.ps1'
$ResidentClaimBoundaryProofScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-resident-claim-boundary-proof.ps1'
$PersistentSupervisionPlanScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-plan.ps1'
foreach ($ScriptPath in @(
    $ServicePlanProofScript,
    $ResidentClaimBoundaryProofScript,
    $PersistentSupervisionPlanScript
  )) {
  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    throw "Required Lens proof script is missing: $ScriptPath"
  }
}

$PreviousDataDir = [string]$env:FRANCIS_DATA_DIR
$ProofDataDir = $DataDir
if ([string]::IsNullOrWhiteSpace($ProofDataDir)) {
  $ProofDataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-persistent-supervision-enablement-transition-plan-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}
$ProofDataDir = [System.IO.Path]::GetFullPath($ProofDataDir)

try {
  $env:FRANCIS_DATA_DIR = $ProofDataDir
  $ServicePlanResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $ServicePlanProofScript -ScriptArgs @('-Mode', $Mode) -TimeoutSeconds $ChildProofTimeoutSeconds
  $ResidentClaimResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $ResidentClaimBoundaryProofScript -ScriptArgs @('-Mode', $Mode, '-DataDir', $ProofDataDir) -TimeoutSeconds $ChildProofTimeoutSeconds
  $PlanResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $PersistentSupervisionPlanScript -ScriptArgs @('-Mode', $Mode) -TimeoutSeconds $ChildProofTimeoutSeconds
} finally {
  if ([string]::IsNullOrWhiteSpace($PreviousDataDir)) {
    Remove-Item Env:\FRANCIS_DATA_DIR -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_DATA_DIR = $PreviousDataDir
  }
}
$ChildProofRuns = @(
  (New-ChildProofRunSummary -Name 'service_install_plan' -Result $ServicePlanResult),
  (New-ChildProofRunSummary -Name 'resident_claim_boundary' -Result $ResidentClaimResult),
  (New-ChildProofRunSummary -Name 'persistent_supervision_plan' -Result $PlanResult)
)
$ChildProofTimeouts = @($ChildProofRuns | Where-Object { [bool]$_['timed_out'] } | ForEach-Object { [string]$_['name'] })

$ServicePlan = Get-PropertyValue -Payload $ServicePlanResult -Name 'payload'
$ResidentClaim = Get-PropertyValue -Payload $ResidentClaimResult -Name 'payload'
$Plan = Get-PropertyValue -Payload $PlanResult -Name 'payload'
$ServiceBlockedBy = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ServicePlan -Name 'blocked_by' -Default @())
$PlanBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Plan -Name 'blockers' -Default @())
$ResidentClaimBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ResidentClaim -Name 'blockers' -Default @())
$RequiredBeforeEnable = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Plan -Name 'required_before_enable' -Default @())
$MissingRequiredBeforeEnable = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Plan -Name 'missing_required_before_enable' -Default @())
$PlanRequirements = @(Get-PropertyValue -Payload $Plan -Name 'requirements' -Default @())
$ExpectedRequiredBeforeEnable = @(
  'resident_host_process',
  'tray_presence',
  'global_hotkey_binding',
  'overlay_window',
  'summon_binding'
)
$EnabledConfigToggles = [string[]]@(
  $PlanRequirements | Where-Object {
    [string](Get-PropertyValue -Payload $_ -Name 'id' -Default '') -in @('process_supervision_enabled', 'persistent_supervision_enabled') -and
    [bool](Get-PropertyValue -Payload $_ -Name 'ready' -Default $false)
  } | ForEach-Object { [string](Get-PropertyValue -Payload $_ -Name 'id' -Default '') }
)

$WindowsServiceSupported = [bool](Get-PropertyValue -Payload $ServicePlan -Name 'windows_service_supported' -Default $false)
$ServicePlanStatus = [string](Get-PropertyValue -Payload $ServicePlan -Name 'service_plan_status' -Default '')
$WindowsServicePlanObserved = (
  $WindowsServiceSupported -and
  $ServicePlanStatus -eq 'blocked' -and
  $ServiceBlockedBy -contains 'installable_false' -and
  $ServiceBlockedBy -contains 'install_authority_false' -and
  $ServiceBlockedBy -contains 'service_install_authority_false' -and
  $ServiceBlockedBy -contains 'service_control_authority_false'
)
$UnsupportedServicePlanObserved = (
  -not $WindowsServiceSupported -and
  $ServicePlanStatus -eq 'unsupported_platform' -and
  $ServiceBlockedBy -contains 'unsupported_platform'
)
$ServicePlanObserved = (
  [int](Get-PropertyValue -Payload $ServicePlanResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $ServicePlan -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_service_install_plan.proof' -and
  [string](Get-PropertyValue -Payload $ServicePlan -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $ServicePlan -Name 'ok' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ServicePlan -Name 'persistent_supervision_config_gate_enabled' -Default $false) -and
  ($WindowsServicePlanObserved -or $UnsupportedServicePlanObserved)
)

$ResidentClaimObserved = (
  [int](Get-PropertyValue -Payload $ResidentClaimResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $ResidentClaim -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_resident_claim_boundary.proof' -and
  [string](Get-PropertyValue -Payload $ResidentClaim -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'ok' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'final_persistent_supervision_authority_family_consumed' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'resident_claim_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'service_config_updated' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'executed' -Default $true)
)

$PlanObserved = (
  [int](Get-PropertyValue -Payload $PlanResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $Plan -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_plan' -and
  [string](Get-PropertyValue -Payload $Plan -Name 'status' -Default '') -eq 'blocked' -and
  [bool](Get-PropertyValue -Payload $Plan -Name 'ok' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Plan -Name 'authority_grant_active' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Plan -Name 'required_before_enable_ready' -Default $true) -and
  [string](Get-PropertyValue -Payload $Plan -Name 'next_smallest_truthful_gap' -Default '') -eq 'persistent_supervision_required_prerequisites_missing' -and
  $PlanBlockers -contains 'persistent_supervision_required_prerequisites_missing'
)
$RequiredPrerequisiteGuardObserved = (
  $PlanObserved -and
  (Test-StringArrayExact -Actual $RequiredBeforeEnable -Expected $ExpectedRequiredBeforeEnable) -and
  (Test-StringArrayExact -Actual $MissingRequiredBeforeEnable -Expected $ExpectedRequiredBeforeEnable)
)

$SideEffectsDenied = (
  $ResidentClaimObserved -and
  -not [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'applied' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'would_update_service_config' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'would_enable_persistent_supervision' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'would_start_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'would_supervise_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'would_restart_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'would_write_receipt' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'would_write_memory' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'would_claim_resident' -Default $true)
)

$Checks = @(
  (New-Check -Id 'persistent_supervision_prerequisites_readback' -Status $(if ($RequiredPrerequisiteGuardObserved) { 'readback_ready' } else { 'missing_or_failed' }) -Passed $RequiredPrerequisiteGuardObserved -Evidence 'scripts/lens-persistent-supervision-plan.ps1 -Mode Status required_before_enable' -Reason 'Persistent supervision enablement must name route-bound prerequisites before transition planning can be trusted.')
  (New-Check -Id 'service_install_plan_boundary' -Status $(if ($ServicePlanObserved) { $ServicePlanStatus } else { 'missing_or_failed' }) -Passed $ServicePlanObserved -Evidence 'scripts/lens-persistent-supervision-service-install-plan-proof.ps1 -Mode Status' -Reason 'The transition plan must preserve Windows service plan truth without claiming a service plan on unsupported platforms.')
  (New-Check -Id 'persistent_supervision_authority_chain' -Status $(if ($ResidentClaimObserved) { 'resident_claim_boundary_observed' } else { 'missing_or_failed' }) -Passed $ResidentClaimObserved -Evidence 'scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status' -Reason 'The transition plan must consume the bounded authority chain before naming disabled enablement as the remaining product gap.')
  (New-Check -Id 'required_prerequisite_guard_readback' -Status $(if ($PlanObserved) { 'blocked_prerequisites' } else { 'missing_or_unexpected' }) -Passed $PlanObserved -Evidence 'scripts/lens-persistent-supervision-plan.ps1 -Mode Status' -Reason 'After bounded authority readback, the plan must still block on resident host, tray, hotkey, overlay, and summon prerequisites.')
  (New-Check -Id 'transition_side_effects_denied' -Status $(if ($SideEffectsDenied) { 'no_side_effects' } else { 'unexpected_side_effect' }) -Passed $SideEffectsDenied -Evidence 'persistent_supervision_resident_claim_boundary.would_*' -Reason 'The transition plan proof must not mutate service config, start a runtime, write receipts, write memory, or claim residency.')
  (New-Check -Id 'child_proof_timeouts' -Status $(if (-not @($ChildProofTimeouts)) { 'none' } else { 'timed_out' }) -Passed (-not @($ChildProofTimeouts)) -Evidence 'child_proof_runs' -Reason 'The transition plan proof must bound every nested proof instead of hanging inside the Stage 6 completion audit.')
)
$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })
$CombinedBlockers = @()
$CombinedBlockers += @($PlanBlockers)
$CombinedBlockers += @($ResidentClaimBlockers)
$CombinedBlockers += @($ServiceBlockedBy)
$CombinedBlockers += @('persistent_supervision_required_prerequisites_missing')

$TransitionSteps = @(
  (New-TransitionStep -Id 'read_required_prerequisites' -Label 'Read persistent-supervision prerequisites' -Status $(if ($RequiredPrerequisiteGuardObserved) { 'readback_ready' } else { 'blocked' }) -Ready $RequiredPrerequisiteGuardObserved -Evidence 'scripts/lens-persistent-supervision-plan.ps1 -Mode Status required_before_enable' -Blockers @() -NextStep 'verify_service_install_plan_boundary')
  (New-TransitionStep -Id 'verify_service_install_plan_boundary' -Label 'Verify service-install plan boundary' -Status $(if ($ServicePlanObserved) { $ServicePlanStatus } else { 'blocked' }) -Ready $ServicePlanObserved -Evidence 'scripts/lens-persistent-supervision-service-install-plan-proof.ps1 -Mode Status' -Blockers $ServiceBlockedBy -NextStep 'consume_persistent_supervision_authority_chain')
  (New-TransitionStep -Id 'consume_persistent_supervision_authority_chain' -Label 'Consume bounded persistent-supervision authority chain' -Status $(if ($ResidentClaimObserved) { 'resident_claim_boundary_observed' } else { 'blocked' }) -Ready $ResidentClaimObserved -Evidence 'scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status' -Blockers $ResidentClaimBlockers -NextStep 'verify_required_prerequisite_guard')
  (New-TransitionStep -Id 'verify_required_prerequisite_guard' -Label 'Verify resident prerequisite guard' -Status $(if ($PlanObserved) { 'blocked_prerequisites' } else { 'blocked' }) -Ready $PlanObserved -Evidence 'scripts/lens-persistent-supervision-plan.ps1 -Mode Status' -Blockers $PlanBlockers -NextStep 'keep_runtime_mutation_denied')
  (New-TransitionStep -Id 'keep_runtime_mutation_denied' -Label 'Keep runtime mutation and resident claim denied' -Status $(if ($SideEffectsDenied) { 'no_side_effects' } else { 'blocked' }) -Ready $SideEffectsDenied -Evidence 'persistent_supervision_resident_claim_boundary.would_*' -Blockers @('resident_claim_authority_not_granted') -NextStep 'return_to_stage6_completion_audit')
)

[ordered]@{
  ok = $ProofPassed
  kind = 'lens.host.persistent_supervision_enablement_transition_plan.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  data_root = $ProofDataDir
  child_proof_timeout_seconds = $ChildProofTimeoutSeconds
  child_proof_timeouts = [string[]]@($ChildProofTimeouts)
  child_proof_runs = @($ChildProofRuns)
  transition_plan_observed = $ProofPassed
  transition_plan_ready = $false
  persistent_supervision_config_gate_enabled = $ServicePlanObserved
  persistent_supervision_enablement_disabled = $false
  persistent_supervision_prerequisites_readback_observed = $RequiredPrerequisiteGuardObserved
  persistent_supervision_required_prerequisites_guard_observed = $RequiredPrerequisiteGuardObserved
  persistent_supervision_service_install_plan_proof_observed = $ServicePlanObserved
  persistent_supervision_resident_claim_boundary_observed = $ResidentClaimObserved
  persistent_supervision_plan_observed = $PlanObserved
  windows_service_supported = $WindowsServiceSupported
  service_install_plan_supported = [bool](Get-PropertyValue -Payload $ServicePlan -Name 'service_install_plan_supported' -Default $false)
  service_plan_status = $ServicePlanStatus
  service_plan_blocked_by = [string[]]@($ServiceBlockedBy)
  required_before_enable = [string[]]@($RequiredBeforeEnable)
  enabled_config_toggles = [string[]]@($EnabledConfigToggles)
  disabled_config_toggles = [string[]]@()
  authority_chain = [ordered]@{
    host_supervision_authority = $true
    persistent_supervision_enablement_authority = [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'persistent_supervision_enablement_authority' -Default $false)
    service_config_write_authority = [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'service_config_write_authority' -Default $false)
    persistent_supervision_execution_authority = [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'persistent_supervision_execution_authority' -Default $false)
    receipt_write_authority = [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'receipt_write_authority' -Default $false)
    resident_claim_authority = $false
    final_authority_family_consumed = [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'final_persistent_supervision_authority_family_consumed' -Default $false)
  }
  side_effects_denied = $SideEffectsDenied
  applied = $false
  executed = $false
  service_config_updated = $false
  would_update_service_config = $false
  would_enable_process_supervision = $false
  would_enable_persistent_supervision = $false
  would_install_service = $false
  would_start_service = $false
  would_supervise_process = $false
  would_restart_process = $false
  would_write_receipt = $false
  would_write_memory = $false
  would_claim_resident = $false
  transition_plan = @($TransitionSteps)
  checks = @($Checks)
  blockers = [string[]]@($CombinedBlockers | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Sort-Object -Unique)
  next_smallest_truthful_gap = 'persistent_supervision_required_prerequisites_missing'
  evidence = @(
    'scripts/lens-persistent-supervision-enablement-transition-plan-proof.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-plan.ps1 -Mode Status required_before_enable',
    'scripts/lens-persistent-supervision-service-install-plan-proof.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-plan.ps1 -Mode Status'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    read_only_transition_plan = $true
    uses_persistent_supervision_plan_prerequisite_readback = $RequiredPrerequisiteGuardObserved
    wraps_existing_service_install_plan_proof = $true
    wraps_existing_resident_claim_boundary_proof = $true
    test_fixture_approval_requests = $true
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
    persistent_supervision_enablement_authority = $false
    persistent_supervision_execution_authority = $false
    service_config_write_authority = $false
    receipt_write_authority = $false
    memory_write = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'The persistent-supervision enablement transition plan is readable and bounded: prerequisites, service-install plan truth, authority-chain receipts, enabled config gate, and resident-claim denial are composed into one non-mutating handoff. The remaining product gap is the missing resident host, tray, hotkey, overlay, and summon prerequisite chain.'
} | ConvertTo-Json -Depth 10

exit $(if ($ProofPassed) { 0 } else { 1 })
