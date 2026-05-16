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
$ResidentHostBridgeScript = Join-Path $PSScriptRoot 'lens-summon-resident-host-blocker-proof.ps1'
$SummonAuthorityBridgeScript = Join-Path $PSScriptRoot 'lens-summon-authority-blocker-proof.ps1'
foreach ($ScriptPath in @($SummonBlockersScript, $ResidentHostBridgeScript, $SummonAuthorityBridgeScript)) {
  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    throw "Required Lens proof script is missing: $ScriptPath"
  }
}

$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command powershell -ErrorAction Stop
}

$ResidentHostBridgeForegroundRunSeconds = 2
$ResidentHostBridgeHostLaunchRunSeconds = 3
$ResidentHostBridgeSupervisorRunSeconds = 8

$SummonResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $SummonBlockersScript -ScriptArgs @('-Mode', 'Status')
$SummonPayload = $SummonResult.payload
$SummonGovernance = Get-PropertyValue -Payload $SummonPayload -Name 'governance'
$SummonFamilies = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $SummonPayload -Name 'blocked_families' -Default @())
$SummonHandoffs = Get-PropertyValue -Payload $SummonPayload -Name 'blocked_family_handoffs' -Default @()
$SummonFirstHandoff = Get-PropertyValue -Payload $SummonPayload -Name 'first_blocker_family_handoff'

$ResidentHostResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $ResidentHostBridgeScript -ScriptArgs @(
  '-Mode', 'Status',
  '-ConsumeProcessSupervisionHandoff',
  '-ForegroundRunSeconds', [string]$ResidentHostBridgeForegroundRunSeconds,
  '-HostLaunchRunSeconds', [string]$ResidentHostBridgeHostLaunchRunSeconds,
  '-SupervisorRunSeconds', [string]$ResidentHostBridgeSupervisorRunSeconds
)
$ResidentHostPayload = $ResidentHostResult.payload
$ResidentHostGovernance = Get-PropertyValue -Payload $ResidentHostPayload -Name 'governance'
$ResidentHostRuntimeBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $ResidentHostPayload -Name 'resident_host_runtime_blockers' -Default @()
)
$ResidentHostSurfaceBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $ResidentHostPayload -Name 'resident_host_surface_blockers' -Default @()
)
$ResidentHostProcessSupervisionHandoff = Get-PropertyValue -Payload $ResidentHostPayload -Name 'resident_host_process_supervision_handoff'
$ResidentHostProcessSupervisionHandoffRecommendedHandoff = Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoff -Name 'recommended_handoff'

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
$AuthorityPreviousGlobalHotkeyBridge = Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'previous_global_hotkey_bridge'
$AuthorityPreviousOverlayWindowBridge = Get-PropertyValue -Payload $AuthorityPreviousGlobalHotkeyBridge -Name 'previous_overlay_window_bridge'
$AuthorityPreviousTrayPresenceBridge = Get-PropertyValue -Payload $AuthorityPreviousOverlayWindowBridge -Name 'previous_tray_presence_bridge'
$AuthorityPreviousResidentHostBridge = Get-PropertyValue -Payload $AuthorityPreviousTrayPresenceBridge -Name 'previous_resident_host_bridge'
$AuthorityPreviousResidentHostProcessHandoff = Get-PropertyValue -Payload $AuthorityPreviousResidentHostBridge -Name 'process_supervision_handoff'
$AuthorityPreviousResidentHostProcessRecommendedHandoff = Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessHandoff -Name 'recommended_handoff'
$ChildProofRuns = @(
  (New-ChildProofRunSummary -Name 'summon_anywhere_blockers' -Result $SummonResult),
  (New-ChildProofRunSummary -Name 'summon_resident_host_blocker' -Result $ResidentHostResult),
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
  [int]$ResidentHostResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $ResidentHostPayload -Name 'kind' -Default '') -eq 'lens.summon_resident_host_blocker.proof' -and
  [string](Get-PropertyValue -Payload $ResidentHostPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $ResidentHostPayload -Name 'summon_first_family_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentHostPayload -Name 'resident_host_lifecycle_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentHostPayload -Name 'resident_host_process_supervision_handoff_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentHostPayload -Name 'handoff_aligned' -Default $false) -and
  [string](Get-PropertyValue -Payload $ResidentHostPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'stage6_lens_completion_audit' -and
  [string](Get-PropertyValue -Payload $ResidentHostPayload -Name 'authority_required' -Default '') -eq 'none_new_stage6_completion_audit' -and
  -not [bool](Get-PropertyValue -Payload $ResidentHostPayload -Name 'authority_granted' -Default $true) -and
  [string](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoff -Name 'authority_required' -Default '') -eq 'none_new_stage6_completion_audit' -and
  -not [bool](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoff -Name 'authority_granted' -Default $true) -and
  [string](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoffRecommendedHandoff -Name 'authority_required' -Default '') -eq 'none_new_stage6_completion_audit' -and
  -not [bool](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoffRecommendedHandoff -Name 'authority_granted' -Default $true) -and
  (
    $ResidentHostRuntimeBlockers -contains 'lens_host_runtime_not_implemented' -or
    $ResidentHostRuntimeBlockers -contains 'lens_host_persistent_supervision_prerequisites_pending'
  ) -and
  $ResidentHostSurfaceBlockers -contains 'tray_host_missing' -and
  $ResidentHostSurfaceBlockers -contains 'overlay_window_missing' -and
  $ResidentHostSurfaceBlockers -contains 'global_hotkey_binding_missing' -and
  $ResidentHostSurfaceBlockers -contains 'summon_binding_missing'
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
  [bool](Get-PropertyValue -Payload $AuthorityPayload -Name 'previous_summon_binding_bridge_handoff_readback_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'previous_summon_blocker_family' -Default '') -eq 'global_hotkey_binding' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'summon_binding_blocker_family' -Default '') -eq 'summon_binding' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'next_summon_blocker_family' -Default '') -eq 'authority' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_authority_blocker_boundary' -and
  [bool](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'previous_global_hotkey_bridge_handoff_readback_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousGlobalHotkeyBridge -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousGlobalHotkeyBridge -Name 'next_summon_blocker_family' -Default '') -eq 'summon_binding' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousGlobalHotkeyBridge -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_binding_blocker_boundary' -and
  [bool](Get-PropertyValue -Payload $AuthorityPreviousGlobalHotkeyBridge -Name 'previous_overlay_window_bridge_handoff_readback_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousOverlayWindowBridge -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousOverlayWindowBridge -Name 'next_summon_blocker_family' -Default '') -eq 'global_hotkey_binding' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousOverlayWindowBridge -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_global_hotkey_binding_blocker_boundary' -and
  [bool](Get-PropertyValue -Payload $AuthorityPreviousOverlayWindowBridge -Name 'previous_tray_presence_bridge_resident_host_readback_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousTrayPresenceBridge -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousTrayPresenceBridge -Name 'next_summon_blocker_family' -Default '') -eq 'overlay_window' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousTrayPresenceBridge -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_overlay_window_blocker_boundary' -and
  [bool](Get-PropertyValue -Payload $AuthorityPreviousTrayPresenceBridge -Name 'previous_resident_host_bridge_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousResidentHostBridge -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousResidentHostBridge -Name 'first_summon_blocker_family' -Default '') -eq 'resident_host' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousResidentHostBridge -Name 'summon_next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousResidentHostBridge -Name 'next_smallest_truthful_gap' -Default '') -eq 'stage6_lens_completion_audit' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousResidentHostBridge -Name 'authority_required' -Default '') -eq 'none_new_stage6_completion_audit' -and
  -not [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostBridge -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostBridge -Name 'process_supervision_handoff_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessHandoff -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'stage6_lens_completion_audit' -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessHandoff -Name 'authority_required' -Default '') -eq 'none_new_stage6_completion_audit' -and
  -not [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessHandoff -Name 'authority_granted' -Default $true) -and
  [string](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'authority_required' -Default '') -eq 'none_new_stage6_completion_audit' -and
  -not [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'would_mutate' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'would_supervise_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'would_restart_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'would_install_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'would_start_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'would_claim_resident' -Default $true)
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
  [bool](Get-PropertyValue -Payload $ResidentHostGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $AuthorityGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentHostGovernance -Name 'bounded_local_process_launch' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentHostGovernance -Name 'temporary_runtime_state_write' -Default $false) -and
  (Test-GovernanceDenied -Governance $SummonGovernance -FalseKeys $DeniedKeys) -and
  (Test-GovernanceDenied -Governance $ResidentHostGovernance -FalseKeys $DeniedKeys) -and
  (Test-GovernanceDenied -Governance $AuthorityGovernance -FalseKeys $DeniedKeys)
)
$HandoffAligned = (
  $FamilyChainObserved -and
  $ResidentHostFamilyHandoffObserved -and
  $FinalAuthorityHandoffObserved -and
  [string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_host_runtime_blocker_boundary' -and
  [string](Get-PropertyValue -Payload $ResidentHostPayload -Name 'summon_next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'summon_next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers'
)

$Checks = @(
  (New-Check -Id 'summon_anywhere_family_chain' -Status $(if ($FamilyChainObserved) { 'family_chain_projected' } else { 'missing_or_unexpected' }) -Passed $FamilyChainObserved -Evidence 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status' -Reason 'The aggregate summon-anywhere blocker proof must project the six blocked families in order.'),
  (New-Check -Id 'resident_host_family_handoff' -Status $(if ($ResidentHostFamilyHandoffObserved) { 'resident_host_handoff_ready' } else { 'missing_or_unexpected' }) -Passed $ResidentHostFamilyHandoffObserved -Evidence 'scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status -ConsumeProcessSupervisionHandoff' -Reason 'The first summon family must consume the resident-host process-supervision handoff without claiming execution.'),
  (New-Check -Id 'final_summon_authority_handoff' -Status $(if ($FinalAuthorityHandoffObserved) { 'final_family_consumed' } else { 'missing_or_unexpected' }) -Passed $FinalAuthorityHandoffObserved -Evidence 'scripts/lens-summon-authority-blocker-proof.ps1 -Mode Status' -Reason 'The final summon blocker family must prove all summon blocker families are consumed without authority.'),
  (New-Check -Id 'final_summon_authority_handoff_readback' -Status $(if ($FinalAuthorityPreviousHandoffReadbackObserved) { 'final_handoff_readback_observed' } else { 'missing_or_unexpected' }) -Passed $FinalAuthorityPreviousHandoffReadbackObserved -Evidence 'scripts/lens-summon-authority-blocker-proof.ps1 -Mode Status previous_binding_handoff' -Reason 'The family-chain proof must preserve the final authority handoff readback through summon-binding, global-hotkey, overlay, tray, resident-host, and process-supervision proofs.'),
  (New-Check -Id 'handoff_alignment' -Status $(if ($HandoffAligned) { 'handoff_aligned' } else { 'handoff_mismatch' }) -Passed $HandoffAligned -Evidence 'summon family chain + resident-host handoff + final authority handoff' -Reason 'The family chain must have one coherent next audit handoff.'),
  (New-Check -Id 'side_effects_denied' -Status $(if ($SideEffectsDenied) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $SideEffectsDenied -Evidence 'summon family governance payloads' -Reason 'This proof must remain diagnostic/readback only and grant no summon, hotkey, overlay, process, service, memory, approval-decision, receipt, or resident-claim authority.')
)
$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

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
  authority_required = [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'authority_required' -Default 'summon_hotkey_overlay_and_process_authority')
  authority_granted = [bool](Get-PropertyValue -Payload $AuthorityPayload -Name 'authority_granted' -Default $false)
  family_chain_observed = $FamilyChainObserved
  resident_host_family_handoff_observed = $ResidentHostFamilyHandoffObserved
  final_summon_authority_handoff_observed = $FinalAuthorityHandoffObserved
  final_summon_authority_handoff_readback_observed = $FinalAuthorityPreviousHandoffReadbackObserved
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
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $ResidentHostPayload -Name 'next_smallest_truthful_gap' -Default '')
    lifecycle_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $ResidentHostPayload -Name 'resident_host_lifecycle_next_smallest_truthful_gap' -Default '')
    process_supervision_handoff_observed = [bool](Get-PropertyValue -Payload $ResidentHostPayload -Name 'resident_host_process_supervision_handoff_observed' -Default $false)
    authority_required = [string](Get-PropertyValue -Payload $ResidentHostPayload -Name 'authority_required' -Default 'none_new_stage6_completion_audit')
    authority_granted = [bool](Get-PropertyValue -Payload $ResidentHostPayload -Name 'authority_granted' -Default $false)
    process_supervision_handoff = [ordered]@{
      status = [string](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoff -Name 'status' -Default '')
      next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoff -Name 'next_smallest_truthful_gap' -Default '')
      authority_required = [string](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoff -Name 'authority_required' -Default '')
      authority_granted = [bool](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoff -Name 'authority_granted' -Default $false)
      recommended_handoff = [ordered]@{
        authority_required = [string](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoffRecommendedHandoff -Name 'authority_required' -Default '')
        authority_granted = [bool](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoffRecommendedHandoff -Name 'authority_granted' -Default $false)
        read_only_contract = [bool](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoffRecommendedHandoff -Name 'read_only_contract' -Default $false)
        diagnostic_only = [bool](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoffRecommendedHandoff -Name 'diagnostic_only' -Default $false)
        would_execute = [bool](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoffRecommendedHandoff -Name 'would_execute' -Default $false)
        would_mutate = [bool](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoffRecommendedHandoff -Name 'would_mutate' -Default $false)
        would_supervise_process = [bool](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoffRecommendedHandoff -Name 'would_supervise_process' -Default $false)
        would_restart_process = [bool](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoffRecommendedHandoff -Name 'would_restart_process' -Default $false)
        would_install_service = [bool](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoffRecommendedHandoff -Name 'would_install_service' -Default $false)
        would_start_service = [bool](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoffRecommendedHandoff -Name 'would_start_service' -Default $false)
        would_claim_resident = [bool](Get-PropertyValue -Payload $ResidentHostProcessSupervisionHandoffRecommendedHandoff -Name 'would_claim_resident' -Default $false)
      }
    }
    runtime_blockers = [string[]]@($ResidentHostRuntimeBlockers)
    surface_blockers = [string[]]@($ResidentHostSurfaceBlockers)
  }
  final_authority = [ordered]@{
    previous_summon_blocker_family = [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'previous_summon_blocker_family' -Default '')
    summon_authority_blocker_family = [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'summon_authority_blocker_family' -Default '')
    next_summon_blocker_family = [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'next_summon_blocker_family' -Default '')
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'next_smallest_truthful_gap' -Default '')
    authority_required = [string](Get-PropertyValue -Payload $AuthorityPayload -Name 'authority_required' -Default 'summon_hotkey_overlay_and_process_authority')
    authority_granted = [bool](Get-PropertyValue -Payload $AuthorityPayload -Name 'authority_granted' -Default $false)
    all_summon_blocker_families_consumed = [bool](Get-PropertyValue -Payload $AuthorityPayload -Name 'all_summon_blocker_families_consumed' -Default $false)
    previous_summon_binding_bridge_handoff_readback_observed = [bool](Get-PropertyValue -Payload $AuthorityPayload -Name 'previous_summon_binding_bridge_handoff_readback_observed' -Default $false)
    previous_binding_handoff = [ordered]@{
      status = [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'status' -Default 'missing')
      previous_summon_blocker_family = [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'previous_summon_blocker_family' -Default '')
      summon_binding_blocker_family = [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'summon_binding_blocker_family' -Default '')
      next_summon_blocker_family = [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'next_summon_blocker_family' -Default '')
      next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'next_smallest_truthful_gap' -Default '')
      handoff_aligned = [bool](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'handoff_aligned' -Default $false)
      side_effects_denied = [bool](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'side_effects_denied' -Default $false)
      previous_global_hotkey_bridge_handoff_readback_observed = [bool](Get-PropertyValue -Payload $AuthorityPreviousBindingHandoff -Name 'previous_global_hotkey_bridge_handoff_readback_observed' -Default $false)
      previous_global_hotkey_bridge = [ordered]@{
        status = [string](Get-PropertyValue -Payload $AuthorityPreviousGlobalHotkeyBridge -Name 'status' -Default 'missing')
        next_summon_blocker_family = [string](Get-PropertyValue -Payload $AuthorityPreviousGlobalHotkeyBridge -Name 'next_summon_blocker_family' -Default '')
        next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $AuthorityPreviousGlobalHotkeyBridge -Name 'next_smallest_truthful_gap' -Default '')
        previous_overlay_window_bridge_handoff_readback_observed = [bool](Get-PropertyValue -Payload $AuthorityPreviousGlobalHotkeyBridge -Name 'previous_overlay_window_bridge_handoff_readback_observed' -Default $false)
        previous_overlay_window_bridge = [ordered]@{
          status = [string](Get-PropertyValue -Payload $AuthorityPreviousOverlayWindowBridge -Name 'status' -Default 'missing')
          next_summon_blocker_family = [string](Get-PropertyValue -Payload $AuthorityPreviousOverlayWindowBridge -Name 'next_summon_blocker_family' -Default '')
          next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $AuthorityPreviousOverlayWindowBridge -Name 'next_smallest_truthful_gap' -Default '')
          previous_tray_presence_bridge_resident_host_readback_observed = [bool](Get-PropertyValue -Payload $AuthorityPreviousOverlayWindowBridge -Name 'previous_tray_presence_bridge_resident_host_readback_observed' -Default $false)
          previous_tray_presence_bridge = [ordered]@{
            status = [string](Get-PropertyValue -Payload $AuthorityPreviousTrayPresenceBridge -Name 'status' -Default 'missing')
            next_summon_blocker_family = [string](Get-PropertyValue -Payload $AuthorityPreviousTrayPresenceBridge -Name 'next_summon_blocker_family' -Default '')
            next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $AuthorityPreviousTrayPresenceBridge -Name 'next_smallest_truthful_gap' -Default '')
            previous_resident_host_bridge_observed = [bool](Get-PropertyValue -Payload $AuthorityPreviousTrayPresenceBridge -Name 'previous_resident_host_bridge_observed' -Default $false)
            previous_resident_host_bridge = [ordered]@{
              status = [string](Get-PropertyValue -Payload $AuthorityPreviousResidentHostBridge -Name 'status' -Default 'missing')
              first_summon_blocker_family = [string](Get-PropertyValue -Payload $AuthorityPreviousResidentHostBridge -Name 'first_summon_blocker_family' -Default '')
              summon_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $AuthorityPreviousResidentHostBridge -Name 'summon_next_smallest_truthful_gap' -Default '')
              next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $AuthorityPreviousResidentHostBridge -Name 'next_smallest_truthful_gap' -Default '')
              authority_required = [string](Get-PropertyValue -Payload $AuthorityPreviousResidentHostBridge -Name 'authority_required' -Default '')
              authority_granted = [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostBridge -Name 'authority_granted' -Default $false)
              process_supervision_handoff_observed = [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostBridge -Name 'process_supervision_handoff_observed' -Default $false)
              process_supervision_handoff = [ordered]@{
                status = [string](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessHandoff -Name 'status' -Default 'missing')
                next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessHandoff -Name 'next_smallest_truthful_gap' -Default '')
                authority_required = [string](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessHandoff -Name 'authority_required' -Default '')
                authority_granted = [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessHandoff -Name 'authority_granted' -Default $false)
                recommended_handoff = [ordered]@{
                  authority_required = [string](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'authority_required' -Default '')
                  authority_granted = [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'authority_granted' -Default $false)
                  read_only_contract = [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'read_only_contract' -Default $false)
                  diagnostic_only = [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'diagnostic_only' -Default $false)
                  would_execute = [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'would_execute' -Default $false)
                  would_mutate = [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'would_mutate' -Default $false)
                  would_supervise_process = [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'would_supervise_process' -Default $false)
                  would_restart_process = [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'would_restart_process' -Default $false)
                  would_install_service = [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'would_install_service' -Default $false)
                  would_start_service = [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'would_start_service' -Default $false)
                  would_claim_resident = [bool](Get-PropertyValue -Payload $AuthorityPreviousResidentHostProcessRecommendedHandoff -Name 'would_claim_resident' -Default $false)
                }
              }
            }
          }
        }
      }
    }
    blockers = [string[]]@($AuthorityBlockers)
  }
  checks = @($Checks)
  evidence = @(
    'scripts/lens-summon-anywhere-family-chain-proof.ps1 -Mode Status',
    'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status',
    'scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status -ConsumeProcessSupervisionHandoff',
    'scripts/lens-summon-authority-blocker-proof.ps1 -Mode Status',
    'docs/canonical/ROADMAP.md#4.12'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_summon_anywhere_blockers_proof = $true
    wraps_summon_resident_host_blocker_proof = $true
    wraps_summon_authority_blocker_proof = $true
    final_authority_previous_handoff_readback = $FinalAuthorityPreviousHandoffReadbackObserved
    read_only_contract = $true
    bounded_local_process_launch = [bool](Get-PropertyValue -Payload $ResidentHostGovernance -Name 'bounded_local_process_launch' -Default $false)
    temporary_runtime_state_write = [bool](Get-PropertyValue -Payload $ResidentHostGovernance -Name 'temporary_runtime_state_write' -Default $false)
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
