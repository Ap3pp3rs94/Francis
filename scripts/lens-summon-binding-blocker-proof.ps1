param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$DataDir = ''
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

$SummonBlockersScript = Join-Path $PSScriptRoot 'lens-summon-anywhere-blockers-proof.ps1'
$GlobalHotkeyBridgeScript = Join-Path $PSScriptRoot 'lens-summon-global-hotkey-binding-blocker-proof.ps1'
$SummonPreflightScript = Join-Path $PSScriptRoot 'lens-summon-preflight.ps1'
foreach ($ScriptPath in @($SummonBlockersScript, $GlobalHotkeyBridgeScript, $SummonPreflightScript)) {
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
$SummonBlockerGroups = Get-PropertyValue -Payload $SummonPayload -Name 'blocker_groups'
$SummonBlockedFamilies = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPayload -Name 'blocked_families' -Default @()
)
$SummonBindingBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonBlockerGroups -Name 'summon_binding' -Default @()
)
$SummonGovernance = Get-PropertyValue -Payload $SummonPayload -Name 'governance'

$GlobalHotkeyBridgeArgs = @('-Mode', 'Status')
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $GlobalHotkeyBridgeArgs += @('-DataDir', $DataDir)
}
$GlobalHotkeyBridgeResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $GlobalHotkeyBridgeScript -ScriptArgs $GlobalHotkeyBridgeArgs
$GlobalHotkeyBridgePayload = $GlobalHotkeyBridgeResult.payload
$GlobalHotkeyBridgeGovernance = Get-PropertyValue -Payload $GlobalHotkeyBridgePayload -Name 'governance'

$SummonPreflightResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $SummonPreflightScript -ScriptArgs @('-Mode', 'Status')
$SummonPreflightPayload = $SummonPreflightResult.payload
$SummonPreflightGovernance = Get-PropertyValue -Payload $SummonPreflightPayload -Name 'governance'
$SummonPreflightGroups = Get-PropertyValue -Payload $SummonPreflightPayload -Name 'blocker_groups'
$SummonPreflightBindingBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPreflightGroups -Name 'summon_binding' -Default @()
)
$SummonPreflightAuthorityBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPreflightGroups -Name 'authority' -Default @()
)
$SummonPreflightBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPreflightPayload -Name 'blockers' -Default @()
)
$SummonPreflightRequiredBefore = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPreflightPayload -Name 'required_before_enable' -Default @()
)
$SummonBinding = Get-PropertyValue -Payload $SummonPreflightPayload -Name 'binding'

$SummonBindingFamilyObserved = (
  [int]$SummonResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'kind' -Default '') -eq 'lens.summon_anywhere_blockers.proof' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'acceptance_criterion' -Default '') -eq 'summon_anywhere' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  @($SummonBlockedFamilies).Count -ge 5 -and
  [string]$SummonBlockedFamilies[3] -eq 'global_hotkey_binding' -and
  [string]$SummonBlockedFamilies[4] -eq 'summon_binding' -and
  $SummonBindingBlockers -contains 'lens_summon_binding_not_implemented' -and
  $SummonBindingBlockers -contains 'summon_authority_not_granted'
)
$PreviousGlobalHotkeyBridgeObserved = (
  [int]$GlobalHotkeyBridgeResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $GlobalHotkeyBridgePayload -Name 'kind' -Default '') -eq 'lens.summon_global_hotkey_binding_blocker.proof' -and
  [string](Get-PropertyValue -Payload $GlobalHotkeyBridgePayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $GlobalHotkeyBridgePayload -Name 'summon_global_hotkey_family_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $GlobalHotkeyBridgePayload -Name 'hotkey_summon_boundary_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $GlobalHotkeyBridgePayload -Name 'handoff_aligned' -Default $false) -and
  [bool](Get-PropertyValue -Payload $GlobalHotkeyBridgePayload -Name 'side_effects_denied' -Default $false) -and
  [string](Get-PropertyValue -Payload $GlobalHotkeyBridgePayload -Name 'next_summon_blocker_family' -Default '') -eq 'summon_binding' -and
  [string](Get-PropertyValue -Payload $GlobalHotkeyBridgePayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_binding_blocker_boundary'
)
$SummonPreflightObserved = (
  [int]$SummonPreflightResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'kind' -Default '') -eq 'lens.summon.preflight' -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'ready' -Default $true) -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'acceptance_criterion' -Default '') -eq 'summon_anywhere' -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'global_hotkey' -Default '') -eq 'Ctrl+Alt+Space' -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'binding_scope' -Default '') -eq 'global' -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'palette_route' -Default '') -eq '/lens/status' -and
  -not [bool](Get-PropertyValue -Payload $SummonBinding -Name 'enabled' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonBinding -Name 'binding_enabled' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonBinding -Name 'register_hotkey' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonBinding -Name 'startup_register' -Default $true) -and
  $SummonPreflightBindingBlockers -contains 'lens_summon_binding_not_implemented' -and
  $SummonPreflightBindingBlockers -contains 'summon_authority_not_granted' -and
  $SummonPreflightBlockers -contains 'lens_summon_binding_not_implemented' -and
  $SummonPreflightBlockers -contains 'summon_authority_not_granted'
)
$HandoffAligned = (
  $SummonBindingFamilyObserved -and
  $PreviousGlobalHotkeyBridgeObserved -and
  $SummonPreflightObserved -and
  $SummonBindingBlockers -contains 'lens_summon_binding_not_implemented' -and
  $SummonBindingBlockers -contains 'summon_authority_not_granted' -and
  $SummonPreflightBindingBlockers -contains 'lens_summon_binding_not_implemented' -and
  $SummonPreflightBindingBlockers -contains 'summon_authority_not_granted' -and
  $SummonPreflightRequiredBefore -contains 'summon_binding'
)
$SideEffectsDenied = (
  [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $GlobalHotkeyBridgeGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'read_only_contract' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $GlobalHotkeyBridgeGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $GlobalHotkeyBridgeGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $GlobalHotkeyBridgeGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $GlobalHotkeyBridgeGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $GlobalHotkeyBridgeGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $GlobalHotkeyBridgeGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'capture_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'new_sensing_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'mutation_authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $GlobalHotkeyBridgeGovernance -Name 'mutation_authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'mutation_authority_granted' -Default $true)
)

$Checks = @(
  (New-Check -Id 'summon_binding_family' -Status $(if ($SummonBindingFamilyObserved) { 'fifth_family_projected' } else { 'missing_or_unexpected' }) -Passed $SummonBindingFamilyObserved -Evidence 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status' -Reason 'The summon-anywhere blocker proof must keep summon_binding as the fifth blocked acceptance family after global_hotkey_binding.'),
  (New-Check -Id 'previous_global_hotkey_bridge' -Status $(if ($PreviousGlobalHotkeyBridgeObserved) { 'previous_family_observed' } else { 'missing_or_unexpected' }) -Passed $PreviousGlobalHotkeyBridgeObserved -Evidence 'scripts/lens-summon-global-hotkey-binding-blocker-proof.ps1 -Mode Status' -Reason 'The summon-binding handoff should preserve the previous global-hotkey bridge context before moving to the fifth blocker family.'),
  (New-Check -Id 'summon_preflight_binding' -Status $(if ($SummonPreflightObserved) { 'blocked_readback_ready' } else { 'missing_or_unexpected' }) -Passed $SummonPreflightObserved -Evidence 'scripts/lens-summon-preflight.ps1 -Mode Status' -Reason 'The direct summon preflight must remain blocked by missing summon binding and missing summon authority.'),
  (New-Check -Id 'handoff_alignment' -Status $(if ($HandoffAligned) { 'handoff_aligned' } else { 'handoff_mismatch' }) -Passed $HandoffAligned -Evidence 'summon_binding blocker group + summon preflight blocker group' -Reason 'The summon_binding blocker must map to direct summon preflight without changing authority.'),
  (New-Check -Id 'side_effects_denied' -Status $(if ($SideEffectsDenied) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $SideEffectsDenied -Evidence 'summon, global-hotkey bridge, and summon preflight governance payloads' -Reason 'The bridge proof must remain diagnostic/readback only and grant no summon, hotkey, overlay, process, memory, approval-decision, sensing, capture, or resident authority.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.summon_binding_blocker.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  stage = 'Stage 6 / Lens MVP'
  stage_state = 'active'
  acceptance_criterion = 'summon_anywhere'
  previous_summon_blocker_family = 'global_hotkey_binding'
  summon_binding_blocker_family = 'summon_binding'
  fifth_summon_blocker_family = 'summon_binding'
  next_summon_blocker_family = 'authority'
  summon_next_smallest_truthful_gap = 'summon_anywhere_blockers'
  direct_summon_preflight_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'next_smallest_truthful_gap' -Default '')
  next_smallest_truthful_gap = 'summon_authority_blocker_boundary'
  summon_binding_family_observed = $SummonBindingFamilyObserved
  previous_global_hotkey_bridge_observed = $PreviousGlobalHotkeyBridgeObserved
  summon_preflight_observed = $SummonPreflightObserved
  handoff_aligned = $HandoffAligned
  side_effects_denied = $SideEffectsDenied
  summon_binding_blockers = [string[]]@($SummonBindingBlockers)
  direct_summon_preflight_binding_blockers = [string[]]@($SummonPreflightBindingBlockers)
  direct_summon_preflight_authority_blockers = [string[]]@($SummonPreflightAuthorityBlockers)
  summon_preflight_boundary = [ordered]@{
    status = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'status' -Default 'missing')
    ready = [bool](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'ready' -Default $false)
    summon_name = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'summon_name' -Default '')
    config_path = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'config_path' -Default '')
    global_hotkey = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'global_hotkey' -Default '')
    binding_scope = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'binding_scope' -Default '')
    palette_route = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'palette_route' -Default '')
    required_before_enable = [string[]]@($SummonPreflightRequiredBefore)
    binding_enabled = [bool](Get-PropertyValue -Payload $SummonBinding -Name 'binding_enabled' -Default $false)
    register_hotkey = [bool](Get-PropertyValue -Payload $SummonBinding -Name 'register_hotkey' -Default $false)
    startup_register = [bool](Get-PropertyValue -Payload $SummonBinding -Name 'startup_register' -Default $false)
    blockers = [string[]]@($SummonPreflightBlockers)
    summon_binding_blockers = [string[]]@($SummonPreflightBindingBlockers)
    authority_blockers = [string[]]@($SummonPreflightAuthorityBlockers)
  }
  checks = @($Checks)
  evidence = @(
    'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status',
    'scripts/lens-summon-global-hotkey-binding-blocker-proof.ps1 -Mode Status',
    'scripts/lens-summon-preflight.ps1 -Mode Status',
    'config/runtime/lens/summon.json',
    '/lens/summon'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_summon_anywhere_blockers_proof = $true
    wraps_summon_global_hotkey_binding_blocker_proof = $true
    wraps_summon_preflight = $true
    read_only_contract = $true
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
  message = 'The Stage 6 summon-anywhere fifth blocker family is summon_binding, and this handoff consumes the direct summon preflight without granting summon, hotkey, overlay, process, memory, approval-decision, sensing, capture, or resident authority.'
}

$Payload | ConvertTo-Json -Depth 8
exit $(if ($ProofPassed) { 0 } else { 1 })
