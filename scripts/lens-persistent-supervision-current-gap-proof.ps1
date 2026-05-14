[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [ValidateRange(30, 240)]
  [int]$ChildProofTimeoutSeconds = 180
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

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
  $Text = [string]$Value
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return @()
  }
  return @($Text)
}

function Test-ContainsAll {
  param(
    [string[]]$Actual,
    [string[]]$Expected
  )

  foreach ($Item in $Expected) {
    if ($Actual -notcontains $Item) {
      return $false
    }
  }
  return $true
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

function Invoke-JsonProofScript {
  param(
    [string]$PowerShellPath,
    [string]$ScriptName,
    [int]$TimeoutSeconds = $ChildProofTimeoutSeconds
  )

  $ScriptPath = Join-Path $PSScriptRoot $ScriptName
  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    return [ordered]@{
      script = "scripts/$ScriptName"
      exit_code = 127
      duration_ms = 0
      payload = $null
      output = ''
      error = ''
      timed_out = $false
      timeout_seconds = $TimeoutSeconds
      parse_error = "missing_script: $ScriptPath"
    }
  }

  $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
  $StartInfo.FileName = $PowerShellPath
  $StartInfo.Arguments = (@(
      '-NoProfile',
      '-ExecutionPolicy',
      'Bypass',
      '-File',
      $ScriptPath,
      '-Mode',
      $Mode
    ) | ForEach-Object { Quote-ProcessArgument -Value $_ }) -join ' '
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
      script = "scripts/$ScriptName"
      exit_code = 1
      duration_ms = [int]$Timer.ElapsedMilliseconds
      payload = $null
      output = ''
      error = [string]$_.Exception.Message
      timed_out = $false
      timeout_seconds = $TimeoutSeconds
      parse_error = ''
    }
  }

  if (-not $Started) {
    $Timer.Stop()
    return [ordered]@{
      script = "scripts/$ScriptName"
      exit_code = 1
      duration_ms = [int]$Timer.ElapsedMilliseconds
      payload = $null
      output = ''
      error = 'process_start_returned_false'
      timed_out = $false
      timeout_seconds = $TimeoutSeconds
      parse_error = ''
    }
  }

  $TimedOut = $false
  $StdOutTask = $Process.StandardOutput.ReadToEndAsync()
  $StdErrTask = $Process.StandardError.ReadToEndAsync()
  if (-not $Process.WaitForExit($TimeoutSeconds * 1000)) {
    $TimedOut = $true
    Stop-ProcessTree -Process $Process
    try {
      $Process.WaitForExit(5000) | Out-Null
    } catch {
    }
  }
  $Timer.Stop()
  try {
    $StdOut = [string]$StdOutTask.GetAwaiter().GetResult()
  } catch {
    $StdOut = ''
  }
  try {
    $StdErr = [string]$StdErrTask.GetAwaiter().GetResult()
  } catch {
    $StdErr = ''
  }
  $Text = if ([string]::IsNullOrWhiteSpace($StdErr)) {
    $StdOut
  } elseif ([string]::IsNullOrWhiteSpace($StdOut)) {
    $StdErr
  } else {
    $StdOut.TrimEnd() + "`n" + $StdErr
  }
  $ExitCode = if ($TimedOut) { 124 } else { [int]$Process.ExitCode }
  $Payload = $null
  $ParseError = ''
  try {
    $Payload = $StdOut | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $ParseError = [string]$_.Exception.Message
  }

  return [ordered]@{
    script = "scripts/$ScriptName"
    exit_code = [int]$ExitCode
    duration_ms = [int]$Timer.ElapsedMilliseconds
    payload = $Payload
    output = $Text
    error = $StdErr
    timed_out = $TimedOut
    timeout_seconds = $TimeoutSeconds
    parse_error = $ParseError
  }
}

function New-ProofSummary {
  param(
    [object]$Result
  )

  $Payload = Get-PropertyValue -Payload $Result -Name 'payload'
  return [ordered]@{
    script = [string](Get-PropertyValue -Payload $Result -Name 'script' -Default '')
    exit_code = [int](Get-PropertyValue -Payload $Result -Name 'exit_code' -Default 1)
    duration_ms = [int](Get-PropertyValue -Payload $Result -Name 'duration_ms' -Default 0)
    kind = [string](Get-PropertyValue -Payload $Payload -Name 'kind' -Default '')
    status = [string](Get-PropertyValue -Payload $Payload -Name 'status' -Default '')
    ok = [bool](Get-PropertyValue -Payload $Payload -Name 'ok' -Default $false)
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $Payload -Name 'next_smallest_truthful_gap' -Default '')
    blockers = [string[]](ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Payload -Name 'blockers'))
    timed_out = [bool](Get-PropertyValue -Payload $Result -Name 'timed_out' -Default $false)
    timeout_seconds = [int](Get-PropertyValue -Payload $Result -Name 'timeout_seconds' -Default 0)
    parse_error = [string](Get-PropertyValue -Payload $Result -Name 'parse_error' -Default '')
  }
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command powershell -ErrorAction Stop
}

$PreviousDataDir = [string]$env:FRANCIS_DATA_DIR
$ProofDataRoot = $DataDir
if (-not [string]::IsNullOrWhiteSpace($ProofDataRoot)) {
  $ProofDataRoot = [System.IO.Path]::GetFullPath($ProofDataRoot)
  New-Item -ItemType Directory -Force -Path $ProofDataRoot | Out-Null
  $env:FRANCIS_DATA_DIR = $ProofDataRoot
}

$ExpectedMissingBeforeEnable = [string[]]@(
  'resident_host_process',
  'tray_presence',
  'global_hotkey_binding',
  'overlay_window',
  'summon_binding'
)

try {
  $PlanResult = Invoke-JsonProofScript -PowerShellPath $PowerShell.Source -ScriptName 'lens-persistent-supervision-plan.ps1'
  $EnablementResult = Invoke-JsonProofScript -PowerShellPath $PowerShell.Source -ScriptName 'lens-persistent-supervision-enablement-authority-proof.ps1'
  $ExecutionResult = Invoke-JsonProofScript -PowerShellPath $PowerShell.Source -ScriptName 'lens-persistent-supervision-execution-authority-proof.ps1'
  $ResidentClaimResult = Invoke-JsonProofScript -PowerShellPath $PowerShell.Source -ScriptName 'lens-persistent-supervision-resident-claim-boundary-proof.ps1'
} finally {
  if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
    if ([string]::IsNullOrWhiteSpace($PreviousDataDir)) {
      Remove-Item Env:\FRANCIS_DATA_DIR -ErrorAction SilentlyContinue
    } else {
      $env:FRANCIS_DATA_DIR = $PreviousDataDir
    }
  }
}

$Plan = Get-PropertyValue -Payload $PlanResult -Name 'payload'
$Enablement = Get-PropertyValue -Payload $EnablementResult -Name 'payload'
$Execution = Get-PropertyValue -Payload $ExecutionResult -Name 'payload'
$ResidentClaim = Get-PropertyValue -Payload $ResidentClaimResult -Name 'payload'

$PlanMissingBeforeEnable = [string[]](ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Plan -Name 'missing_required_before_enable'))
$FirstMissingHandoff = Get-PropertyValue -Payload $Plan -Name 'first_missing_requirement_handoff'
$FirstMissingId = [string](Get-PropertyValue -Payload $Plan -Name 'first_missing_required_before_enable' -Default '')
$PlanGovernance = Get-PropertyValue -Payload $Plan -Name 'governance'
$PlanNested = Get-PropertyValue -Payload $Plan -Name 'plan'

$PlanObserved = (
  [int](Get-PropertyValue -Payload $PlanResult -Name 'exit_code' -Default 1) -eq 0 -and
  [string](Get-PropertyValue -Payload $Plan -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_plan' -and
  [bool](Get-PropertyValue -Payload $Plan -Name 'ok' -Default $false) -and
  [string](Get-PropertyValue -Payload $Plan -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $Plan -Name 'persistent_supervision_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Plan -Name 'required_before_enable_ready' -Default $true) -and
  [string](Get-PropertyValue -Payload $Plan -Name 'next_smallest_truthful_gap' -Default '') -eq 'persistent_supervision_required_prerequisites_missing' -and
  (Test-ContainsAll -Actual $PlanMissingBeforeEnable -Expected $ExpectedMissingBeforeEnable)
)
$EnablementObserved = (
  [int](Get-PropertyValue -Payload $EnablementResult -Name 'exit_code' -Default 1) -eq 0 -and
  [string](Get-PropertyValue -Payload $Enablement -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_enablement_authority.proof' -and
  [bool](Get-PropertyValue -Payload $Enablement -Name 'ok' -Default $false) -and
  [string](Get-PropertyValue -Payload $Enablement -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $Enablement -Name 'next_smallest_truthful_gap' -Default '') -eq 'persistent_supervision_execution_authority_or_resident_claim_boundary'
)
$ExecutionObserved = (
  [int](Get-PropertyValue -Payload $ExecutionResult -Name 'exit_code' -Default 1) -eq 0 -and
  [string](Get-PropertyValue -Payload $Execution -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_execution_authority.proof' -and
  [bool](Get-PropertyValue -Payload $Execution -Name 'ok' -Default $false) -and
  [string](Get-PropertyValue -Payload $Execution -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $Execution -Name 'next_smallest_truthful_gap' -Default '') -eq 'persistent_supervision_resident_claim_authority_boundary'
)
$ResidentClaimBlockers = [string[]](ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ResidentClaim -Name 'blockers'))
$ResidentClaimObserved = (
  [int](Get-PropertyValue -Payload $ResidentClaimResult -Name 'exit_code' -Default 1) -eq 0 -and
  [string](Get-PropertyValue -Payload $ResidentClaim -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_resident_claim_boundary.proof' -and
  [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'ok' -Default $false) -and
  [string](Get-PropertyValue -Payload $ResidentClaim -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'final_persistent_supervision_authority_family_consumed' -Default $false) -and
  [string](Get-PropertyValue -Payload $ResidentClaim -Name 'next_smallest_truthful_gap' -Default '') -eq 'stage6_lens_completion_audit'
)
$AuthorityChainConsumed = $EnablementObserved -and $ExecutionObserved -and $ResidentClaimObserved
$CurrentGapObserved = (
  $PlanObserved -and
  $AuthorityChainConsumed -and
  $ResidentClaimBlockers -contains 'persistent_supervision_required_prerequisites_missing'
)
$FirstMissingProofScript = [string](Get-PropertyValue -Payload $FirstMissingHandoff -Name 'proof_script' -Default '')
$FirstMissingHandoffReady = (
  $CurrentGapObserved -and
  $FirstMissingId -eq 'resident_host_process' -and
  -not [string]::IsNullOrWhiteSpace($FirstMissingProofScript) -and
  $FirstMissingProofScript.StartsWith('scripts/lens-resident-') -and
  $FirstMissingProofScript.EndsWith('-proof.ps1 -Mode Status') -and
  [string](Get-PropertyValue -Payload $FirstMissingHandoff -Name 'route' -Default '') -eq '/lens/host' -and
  [string](Get-PropertyValue -Payload $FirstMissingHandoff -Name 'readiness_route' -Default '') -eq '/lens/host/runtime-loop/readiness' -and
  [bool](Get-PropertyValue -Payload $FirstMissingHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $FirstMissingHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $FirstMissingHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $FirstMissingHandoff -Name 'would_mutate' -Default $true)
)
$ProductSideEffectsDenied = (
  $CurrentGapObserved -and
  [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'read_only_contract' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'receipt_write_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'resident_claim_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PlanNested -Name 'would_install_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PlanNested -Name 'would_start_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PlanNested -Name 'would_supervise_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PlanNested -Name 'would_write_receipt' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PlanNested -Name 'would_write_memory' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PlanNested -Name 'would_claim_resident' -Default $true)
)

$Checks = @(
  (New-Check -Id 'persistent_supervision_plan_readback' -Status $(if ($PlanObserved) { 'required_prerequisites_missing' } else { 'missing_or_unexpected' }) -Passed $PlanObserved -Evidence 'scripts/lens-persistent-supervision-plan.ps1 -Mode Status' -Reason 'The current persistent-supervision plan must name the required-before-enable prerequisite gap.')
  (New-Check -Id 'enablement_authority_proof' -Status $(if ($EnablementObserved) { 'proof_passed' } else { 'missing_or_failed' }) -Passed $EnablementObserved -Evidence 'scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status' -Reason 'Enablement authority must be directly consumed before treating the remaining gap as prerequisites.')
  (New-Check -Id 'execution_authority_proof' -Status $(if ($ExecutionObserved) { 'proof_passed' } else { 'missing_or_failed' }) -Passed $ExecutionObserved -Evidence 'scripts/lens-persistent-supervision-execution-authority-proof.ps1 -Mode Status' -Reason 'Execution authority must be directly consumed before treating the remaining gap as prerequisites.')
  (New-Check -Id 'resident_claim_boundary_proof' -Status $(if ($ResidentClaimObserved) { 'proof_passed' } else { 'missing_or_failed' }) -Passed $ResidentClaimObserved -Evidence 'scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status' -Reason 'Resident-claim boundary readback must be consumed without claiming residency.')
  (New-Check -Id 'authority_chain_consumed' -Status $(if ($AuthorityChainConsumed) { 'consumed' } else { 'incomplete' }) -Passed $AuthorityChainConsumed -Evidence 'persistent supervision authority proof chain' -Reason 'The focused proof must consume the bounded authority chain without running the Stage 6 completion audit.')
  (New-Check -Id 'current_gap' -Status $(if ($CurrentGapObserved) { 'persistent_supervision_required_prerequisites_missing' } else { 'unknown_or_unexpected' }) -Passed $CurrentGapObserved -Evidence 'persistent_supervision_plan.next_smallest_truthful_gap' -Reason 'The current next gap must stay anchored to missing resident host, tray, hotkey, overlay, and summon prerequisites.')
  (New-Check -Id 'first_missing_requirement_handoff' -Status $(if ($FirstMissingHandoffReady) { 'resident_host_process_handoff_ready' } else { 'missing_or_unexpected' }) -Passed $FirstMissingHandoffReady -Evidence 'persistent_supervision_plan.first_missing_requirement_handoff' -Reason 'The first actionable handoff must remain the resident host runtime boundary proof.')
  (New-Check -Id 'product_side_effects_denied' -Status $(if ($ProductSideEffectsDenied) { 'product_read_only' } else { 'unexpected_product_mutation_authority' }) -Passed $ProductSideEffectsDenied -Evidence 'persistent_supervision_plan.governance' -Reason 'The focused proof must not claim product execution, service, memory, receipt, or resident-claim authority.')
)
$ProofPassed = -not @($Checks | Where-Object { -not [bool](Get-PropertyValue -Payload $_ -Name 'passed' -Default $false) })

$Handoff = [ordered]@{
  status = 'blocked'
  next_smallest_truthful_gap = 'persistent_supervision_required_prerequisites_missing'
  next_step = 'resolve_persistent_supervision_required_prerequisites_before_enablement'
  proof_script = 'scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status'
  route = '/lens/host/persistent-supervision'
  readiness_route = '/lens/host/persistent-supervision/enablement'
  authority_required = 'resident_host_process_tray_hotkey_overlay_and_summon_prerequisites'
  authority_granted = $false
  missing_required_before_enable = [string[]]$PlanMissingBeforeEnable
  first_missing_required_before_enable = $FirstMissingId
  first_missing_requirement_handoff = $FirstMissingHandoff
  read_only_contract = $true
  diagnostic_only = $true
  would_execute = $false
  would_mutate = $false
}

[ordered]@{
  ok = $ProofPassed
  kind = 'lens.host.persistent_supervision_current_gap.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  stage = 'Stage 6 / Lens MVP'
  repo_root = $RepoRoot
  data_root = [string](Get-PropertyValue -Payload $Plan -Name 'data_root' -Default $ProofDataRoot)
  persistent_supervision_plan_observed = $PlanObserved
  persistent_supervision_enablement_authority_proof_observed = $EnablementObserved
  persistent_supervision_execution_authority_proof_observed = $ExecutionObserved
  persistent_supervision_resident_claim_boundary_proof_observed = $ResidentClaimObserved
  persistent_supervision_authority_chain_consumed = $AuthorityChainConsumed
  persistent_supervision_current_gap_observed = $CurrentGapObserved
  next_smallest_truthful_gap = if ($CurrentGapObserved) { 'persistent_supervision_required_prerequisites_missing' } else { [string](Get-PropertyValue -Payload $Plan -Name 'next_smallest_truthful_gap' -Default '') }
  recommended_handoff_source = 'persistent_supervision_plan_first_missing_requirement_handoff'
  recommended_next_slice = 'resolve_persistent_supervision_required_prerequisites_before_enablement'
  recommended_proof_script = 'scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status'
  recommended_route = '/lens/host/persistent-supervision'
  recommended_readiness_route = '/lens/host/persistent-supervision/enablement'
  authority_required = 'resident_host_process_tray_hotkey_overlay_and_summon_prerequisites'
  authority_granted = $false
  missing_required_before_enable = [string[]]$PlanMissingBeforeEnable
  first_missing_required_before_enable = $FirstMissingId
  first_missing_requirement_handoff = $FirstMissingHandoff
  handoff = $Handoff
  authority_chain = [ordered]@{
    enablement_authority_consumed = $EnablementObserved
    execution_authority_consumed = $ExecutionObserved
    resident_claim_boundary_consumed = $ResidentClaimObserved
    final_authority_family_consumed = [bool](Get-PropertyValue -Payload $ResidentClaim -Name 'final_persistent_supervision_authority_family_consumed' -Default $false)
    next_audit_gap_after_authority_chain = 'stage6_lens_completion_audit'
  }
  persistent_supervision_plan_summary = (New-ProofSummary -Result $PlanResult)
  persistent_supervision_enablement_authority_summary = (New-ProofSummary -Result $EnablementResult)
  persistent_supervision_execution_authority_summary = (New-ProofSummary -Result $ExecutionResult)
  persistent_supervision_resident_claim_boundary_summary = (New-ProofSummary -Result $ResidentClaimResult)
  stage6_completion_audit_required = $true
  stage6_completion_audit_not_run = $true
  stage6_completion_audit_script = 'scripts/lens-stage6-completion-audit.ps1'
  checks = @($Checks)
  evidence = @(
    'scripts/lens-persistent-supervision-current-gap-proof.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-plan.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-execution-authority-proof.ps1 -Mode Status',
    'scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    product_read_only_contract = $true
    runs_child_proofs = $true
    child_proof_timeout_seconds = $ChildProofTimeoutSeconds
    child_proofs_use_test_fixture_approval_decisions = $true
    child_proofs_write_temp_fixture_receipts = $true
    stage6_completion_audit_not_run = $true
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
    product_receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
    would_execute_product_path = $false
    would_mutate_product_path = $false
  }
  message = 'The persistent-supervision authority proof chain is consumed, but the current truthful gap remains the required resident host, tray, hotkey, overlay, and summon prerequisites before enablement; the Stage 6 completion audit was not run.'
} | ConvertTo-Json -Depth 10

exit $(if ($ProofPassed) { 0 } else { 1 })
