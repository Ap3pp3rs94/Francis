param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [ValidateRange(5, 600)]
  [int]$ChildProofTimeoutSeconds = 240
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
    return @($Value | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  }

  $Single = [string]$Value
  if ([string]::IsNullOrWhiteSpace($Single)) {
    return @()
  }
  return @($Single)
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

  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
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

function Test-GovernanceDenied {
  param(
    [AllowNull()]
    [object]$Governance,
    [string[]]$FalseKeys
  )

  foreach ($Key in @($FalseKeys)) {
    if ([bool](Get-PropertyValue -Payload $Governance -Name $Key -Default $false)) {
      return $false
    }
  }
  return $true
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$SummonBlockersScript = Join-Path $PSScriptRoot 'lens-summon-anywhere-blockers-proof.ps1'
$SummonAuthorityBridgeScript = Join-Path $PSScriptRoot 'lens-summon-authority-blocker-proof.ps1'
foreach ($ScriptPath in @($SummonBlockersScript, $SummonAuthorityBridgeScript)) {
  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    throw "Required Lens proof script is missing: $ScriptPath"
  }
}

$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command powershell -ErrorAction Stop
}

$SummonResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $SummonBlockersScript -ScriptArgs @('-Mode', 'Status')
$SummonPayload = $SummonResult.payload
$SummonGovernance = Get-PropertyValue -Payload $SummonPayload -Name 'governance'
$SummonFamilies = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $SummonPayload -Name 'blocked_families' -Default @())
$SummonHandoffs = Get-PropertyValue -Payload $SummonPayload -Name 'blocked_family_handoffs' -Default @()
$SummonFirstHandoff = Get-PropertyValue -Payload $SummonPayload -Name 'first_blocker_family_handoff'

$AuthorityArgs = @('-Mode', 'Status')
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $AuthorityArgs += @('-DataDir', $DataDir)
}
$AuthorityResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $SummonAuthorityBridgeScript -ScriptArgs $AuthorityArgs
$AuthorityPayload = $AuthorityResult.payload
$AuthorityGovernance = Get-PropertyValue -Payload $AuthorityPayload -Name 'governance'
$AuthorityBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $AuthorityPayload -Name 'summon_authority_blockers' -Default @()
)
$AuthorityPreviousBindingHandoff = Get-PropertyValue -Payload $AuthorityPayload -Name 'previous_binding_handoff'
$AuthorityPreviousBindingBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'blockers' -Default @()
)
$ResidentHostFamilyBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonFirstHandoff -Name 'blockers' -Default @()
)
$ChildProofRuns = @(
  (New-ChildProofRunSummary -Name 'summon_anywhere_blockers' -Result $SummonResult),
  (New-ChildProofRunSummary -Name 'summon_authority_blocker' -Result $AuthorityResult)
)
$ChildProofTimeouts = @($ChildProofRuns | Where-Object { [bool]$_['timed_out'] } | ForEach-Object { [string]$_['name'] })

$ExpectedFamilies = @(
  'resident_host',
  'tray_presence',
  'overlay_window',
  'global_hotkey_binding',
  'summon_binding',
  'authority'
)
$FamilyChainObserved = (
  [int]$SummonResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'kind' -Default '') -eq 'lens.summon_anywhere_blockers.proof' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $SummonPayload -Name 'first_blocker_family_handoff_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'first_blocker_family' -Default '') -eq 'resident_host' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  @($SummonFamilies).Count -eq @($ExpectedFamilies).Count -and
  -not @(
    for ($Index = 0; $Index -lt @($ExpectedFamilies).Count; $Index += 1) {
      if ([string]$SummonFamilies[$Index] -ne [string]$ExpectedFamilies[$Index]) {
        [string]$ExpectedFamilies[$Index]
      }
    }
  )
)
$ResidentHostFamilyHandoffObserved = (
  [string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'id' -Default '') -eq 'resident_host' -and
  [string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'proof_script' -Default '') -eq 'scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'route' -Default '') -eq '/lens/host' -and
  [string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'readiness_route' -Default '') -eq '/lens/host/runtime-loop/readiness' -and
  [string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'next_step' -Default '') -eq 'run_resident_host_blocker_proof' -and
  [string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_host_runtime_blocker_boundary' -and
  [string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'authority_required' -Default '') -eq 'resident_runtime_execution_authority' -and
  -not [bool](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'would_mutate' -Default $true) -and
  $ResidentHostFamilyBlockers -contains 'local_process_launch_authority_not_granted'
)
$FinalAuthorityHandoffObserved = (
  [int]$AuthorityResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'kind' -Default '') -eq 'lens.summon_authority_blocker.proof' -and
  [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $AuthorityPayload -Name 'all_summon_blocker_families_consumed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $AuthorityPayload -Name 'handoff_aligned' -Default $false) -and
  [bool](Get-PropertyValue -Payload $AuthorityPayload -Name 'side_effects_denied' -Default $false) -and
  [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'previous_summon_blocker_family' -Default '') -eq 'summon_binding' -and
  [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'summon_authority_blocker_family' -Default '') -eq 'authority' -and
  [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'stage6_lens_completion_audit' -and
  [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'authority_required' -Default '') -eq 'summon_hotkey_overlay_and_process_authority' -and
  -not [bool](Get-PropertyValue -Payload $AuthorityPayload -Name 'authority_granted' -Default $true) -and
  $AuthorityBlockers -contains 'summon_authority_not_granted' -and
  $AuthorityBlockers -contains 'hotkey_registration_authority_not_granted' -and
  $AuthorityBlockers -contains 'overlay_control_authority_not_granted' -and
  $AuthorityBlockers -contains 'local_process_launch_authority_not_granted'
)
$FinalAuthorityPreviousHandoffReadbackObserved = (
  [bool](Get-PropertyValue -Payload $AuthorityPayload -Name 'previous_summon_binding_contract_readback_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'source' -Default '') -eq 'summon_anywhere_blockers.blocked_family_handoffs' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'status' -Default '') -eq 'contract_projected' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'contract_status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'proof_script' -Default '') -eq 'scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'previous_summon_blocker_family' -Default '') -eq 'global_hotkey_binding' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'summon_binding_blocker_family' -Default '') -eq 'summon_binding' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'next_summon_blocker_family' -Default '') -eq 'authority' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_authority_blocker_boundary' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'authority_required' -Default '') -eq 'summon_authority' -and
  -not [bool](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'would_mutate' -Default $true) -and
  $AuthorityPreviousBindingBlockers -contains 'lens_summon_binding_disabled_pending_authority' -and
  $AuthorityPreviousBindingBlockers -contains 'summon_authority_not_granted'
)
$FinalAuthorityHandoffObserved = $FinalAuthorityHandoffObserved -and $FinalAuthorityPreviousHandoffReadbackObserved

$DeniedKeys = @(
  'product_execution_authority',
  'execution_authority',
  'approval_decision_authority',
  'local_process_launch_authority',
  'process_supervision_authority',
  'process_restart_authority',
  'service_install_authority',
  'service_control_authority',
  'hotkey_registration_authority',
  'overlay_control_authority',
  'summon_authority',
  'capture_authority',
  'new_sensing_authority',
  'memory_write',
  'receipt_write_authority',
  'resident_claim_authority',
  'mutation_authority_granted'
)
$SideEffectsDenied = (
  [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $AuthorityGovernance -Name 'diagnostic_only' -Default $false) -and
  $ResidentHostFamilyHandoffObserved -and
  $FinalAuthorityPreviousHandoffReadbackObserved -and
  (Test-GovernanceDenied -Governance $SummonGovernance -FalseKeys $DeniedKeys) -and
  (Test-GovernanceDenied -Governance $AuthorityGovernance -FalseKeys $DeniedKeys)
)
$HandoffAligned = (
  $FamilyChainObserved -and
  $ResidentHostFamilyHandoffObserved -and
  $FinalAuthorityHandoffObserved -and
  [string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_host_runtime_blocker_boundary' -and
  [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'summon_next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers'
)

$Checks = @(
  (New-Check -Id 'summon_anywhere_family_chain' -Status $(if ($FamilyChainObserved) { 'family_chain_projected' } else { 'missing_or_unexpected' }) -Passed $FamilyChainObserved -Evidence 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status' -Reason 'The aggregate summon-anywhere blocker proof must project the six blocked families in order.'),
  (New-Check -Id 'resident_host_family_handoff' -Status $(if ($ResidentHostFamilyHandoffObserved) { 'resident_host_contract_ready' } else { 'missing_or_unexpected' }) -Passed $ResidentHostFamilyHandoffObserved -Evidence 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status first_blocker_family_handoff' -Reason 'The family chain must reuse the resident-host family contract emitted by the aggregate blockers proof without rerunning the resident-host proof.'),
  (New-Check -Id 'final_summon_authority_handoff' -Status $(if ($FinalAuthorityHandoffObserved) { 'final_family_consumed' } else { 'missing_or_unexpected' }) -Passed $FinalAuthorityHandoffObserved -Evidence 'scripts/lens-summon-authority-blocker-proof.ps1 -Mode Status' -Reason 'The final summon blocker family must prove all summon blocker families are consumed without authority.'),
  (New-Check -Id 'final_summon_authority_contract_readback' -Status $(if ($FinalAuthorityPreviousHandoffReadbackObserved) { 'final_contract_readback_observed' } else { 'missing_or_unexpected' }) -Passed $FinalAuthorityPreviousHandoffReadbackObserved -Evidence 'scripts/lens-summon-authority-blocker-proof.ps1 -Mode Status previous_binding_handoff' -Reason 'The family-chain proof must preserve the final authority handoff through the bounded summon-binding contract without rerunning lower-family bridge proofs.'),
  (New-Check -Id 'handoff_alignment' -Status $(if ($HandoffAligned) { 'handoff_aligned' } else { 'handoff_mismatch' }) -Passed $HandoffAligned -Evidence 'summon family chain + resident-host handoff + final authority handoff' -Reason 'The family chain must have one coherent next audit handoff.'),
  (New-Check -Id 'side_effects_denied' -Status $(if ($SideEffectsDenied) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $SideEffectsDenied -Evidence 'summon family governance payloads plus bounded family contracts' -Reason 'This proof must remain diagnostic/readback only and grant no summon, hotkey, overlay, process, service, memory, approval-decision, receipt, or resident-claim authority.')
)
$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })
$RecommendedHandoffSource = 'summon_anywhere_family_chain_completion_audit_handoff'
$RecommendedNextSlice = 'run_stage6_lens_completion_audit_after_summon_anywhere_family_chain_readback'
$RecommendedProofScript = 'scripts/lens-stage6-completion-audit.ps1 -Mode Status'
$RecommendedHandoff = [ordered]@{
  id = 'stage6_lens_completion_audit'
  status = 'audit_needed'
  previous_next_smallest_truthful_gap = 'summon_anywhere_blockers'
  next_smallest_truthful_gap = 'stage6_lens_completion_audit'
  next_step = $RecommendedNextSlice
  proof_script = $RecommendedProofScript
  route = '/lens/status'
  readiness_route = '/lens/status'
  acceptance_criterion = 'summon_anywhere'
  blocker = 'summon_anywhere_blockers'
  requirement_state = 'summon_anywhere_family_chain_consumed_without_authority'
  authority_required = 'none_new_stage6_completion_audit'
  authority_granted = $false
  read_only_contract = $true
  diagnostic_only = $true
  would_execute = $false
  would_mutate = $false
  would_register_hotkey = $false
  would_control_overlay = $false
  would_launch_process = $false
  would_supervise_process = $false
  would_claim_resident = $false
  blocked_families = [string[]]@($SummonFamilies)
}

[ordered]@{
  ok = $ProofPassed
  kind = 'lens.summon_anywhere_family_chain.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  stage = 'Stage 6 / Lens MVP'
  stage_state = 'active'
  acceptance_criterion = 'summon_anywhere'
  summon_next_smallest_truthful_gap = 'summon_anywhere_blockers'
  next_smallest_truthful_gap = 'stage6_lens_completion_audit'
  recommended_handoff_source = $RecommendedHandoffSource
  recommended_next_slice = $RecommendedNextSlice
  recommended_proof_script = $RecommendedProofScript
  recommended_handoff = $RecommendedHandoff
  authority_required = [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'authority_required' -Default 'summon_hotkey_overlay_and_process_authority')
  authority_granted = [bool](Get-PropertyValue -Payload $AuthorityPayload -Name 'authority_granted' -Default $false)
  family_chain_observed = $FamilyChainObserved
  resident_host_family_handoff_observed = $ResidentHostFamilyHandoffObserved
  final_summon_authority_handoff_observed = $FinalAuthorityHandoffObserved
  final_summon_authority_contract_readback_observed = $FinalAuthorityPreviousHandoffReadbackObserved
  all_summon_blocker_families_consumed = $HandoffAligned
  handoff_aligned = $HandoffAligned
  side_effects_denied = $SideEffectsDenied
  child_proof_timeout_seconds = $ChildProofTimeoutSeconds
  child_proof_timeouts = [string[]]@($ChildProofTimeouts)
  child_proof_runs = @($ChildProofRuns)
  blocked_families = [string[]]@($SummonFamilies)
  blocked_family_handoffs = @($SummonHandoffs)
  first_blocker_family = [string](Get-PropertyValue -Payload $SummonPayload -Name 'first_blocker_family' -Default '')
  first_blocker_family_handoff = $SummonFirstHandoff
  resident_host = [ordered]@{
    handoff_source = 'summon_anywhere_blockers_first_family_handoff'
    id = [string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'id' -Default '')
    status = [string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'status' -Default '')
    proof_script = [string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'proof_script' -Default '')
    route = [string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'route' -Default '')
    readiness_route = [string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'readiness_route' -Default '')
    next_step = [string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'next_step' -Default '')
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'next_smallest_truthful_gap' -Default '')
    authority_required = [string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'authority_required' -Default '')
    authority_granted = [bool](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'authority_granted' -Default $false)
    read_only_contract = [bool](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'read_only_contract' -Default $false)
    diagnostic_only = [bool](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'diagnostic_only' -Default $false)
    would_execute = [bool](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'would_execute' -Default $false)
    would_mutate = [bool](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'would_mutate' -Default $false)
    blockers = [string[]]@($ResidentHostFamilyBlockers)
  }
  final_authority = [ordered]@{
    previous_summon_blocker_family = [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'previous_summon_blocker_family' -Default '')
    summon_authority_blocker_family = [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'summon_authority_blocker_family' -Default '')
    next_summon_blocker_family = [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'next_summon_blocker_family' -Default '')
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'next_smallest_truthful_gap' -Default '')
    authority_required = [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'authority_required' -Default 'summon_hotkey_overlay_and_process_authority')
    authority_granted = [bool](Get-PropertyValue -Payload $AuthorityPayload -Name 'authority_granted' -Default $false)
    all_summon_blocker_families_consumed = [bool](Get-PropertyValue -Payload $AuthorityPayload -Name 'all_summon_blocker_families_consumed' -Default $false)
    previous_summon_binding_contract_observed = [bool](Get-PropertyValue -Payload $AuthorityPayload -Name 'previous_summon_binding_contract_observed' -Default $false)
    previous_summon_binding_contract_readback_observed = [bool](Get-PropertyValue -Payload $AuthorityPayload -Name 'previous_summon_binding_contract_readback_observed' -Default $false)
    previous_binding_handoff = [ordered]@{
      source = [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'source' -Default '')
      status = [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'status' -Default 'missing')
      contract_status = [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'contract_status' -Default '')
      proof_script = [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'proof_script' -Default '')
      previous_summon_blocker_family = [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'previous_summon_blocker_family' -Default '')
      summon_binding_blocker_family = [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'summon_binding_blocker_family' -Default '')
      next_summon_blocker_family = [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'next_summon_blocker_family' -Default '')
      next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'next_smallest_truthful_gap' -Default '')
      authority_required = [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'authority_required' -Default '')
      authority_granted = [bool](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'authority_granted' -Default $false)
      read_only_contract = [bool](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'read_only_contract' -Default $false)
      diagnostic_only = [bool](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'diagnostic_only' -Default $false)
      would_execute = [bool](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'would_execute' -Default $false)
      would_mutate = [bool](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'would_mutate' -Default $false)
      handoff_aligned = [bool](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'handoff_aligned' -Default $false)
      side_effects_denied = [bool](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'side_effects_denied' -Default $false)
      blockers = [string[]]@($AuthorityPreviousBindingBlockers)
    }
    blockers = [string[]]@($AuthorityBlockers)
  }
  checks = @($Checks)
  evidence = @(
    'scripts/lens-summon-anywhere-family-chain-proof.ps1 -Mode Status',
    'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status',
    'scripts/lens-summon-authority-blocker-proof.ps1 -Mode Status',
    'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status first_blocker_family_handoff',
    'docs/canonical/ROADMAP.md#4.12'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_summon_anywhere_blockers_proof = $true
    wraps_summon_authority_blocker_proof = $true
    uses_summon_anywhere_family_handoff_contract = $ResidentHostFamilyHandoffObserved
    final_authority_previous_contract_readback = $FinalAuthorityPreviousHandoffReadbackObserved
    read_only_contract = $true
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
    tray_registration_authority = $false
    tray_icon_authority = $false
    notification_authority = $false
    hotkey_registration_authority = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'The Stage 6 summon-anywhere blocker chain is proven as one diagnostic handoff: the resident_host family points to the runtime blocker, the final authority proof consumes all summon families, and the next truthful handoff is the Stage 6 completion audit without granting product execution or resident authority.'
} | ConvertTo-Json -Depth 8

exit $(if ($ProofPassed) { 0 } else { 1 })
