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

$AuthorityScript = Join-Path $PSScriptRoot 'lens-resident-runtime-authority-blockers-proof.ps1'
$HotkeyScript = Join-Path $PSScriptRoot 'lens-resident-runtime-hotkey-summon-boundary-proof.ps1'
$OverlayScript = Join-Path $PSScriptRoot 'lens-overlay-preflight.ps1'
foreach ($ScriptPath in @($AuthorityScript, $HotkeyScript, $OverlayScript)) {
  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) { throw "Required Lens proof script is missing: $ScriptPath" }
}

$AuthorityArgs = @('-Mode', $Mode)
$HotkeyArgs = @('-Mode', $Mode)
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $AuthorityArgs += @('-DataDir', $DataDir)
  $HotkeyArgs += @('-DataDir', $DataDir)
}

$AuthorityResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $AuthorityScript -ScriptArgs $AuthorityArgs
$HotkeyResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $HotkeyScript -ScriptArgs $HotkeyArgs
$OverlayResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $OverlayScript -ScriptArgs @('-Mode', 'Status')
$Authority = Get-PropertyValue -Payload $AuthorityResult -Name 'payload'
$Hotkey = Get-PropertyValue -Payload $HotkeyResult -Name 'payload'
$Overlay = Get-PropertyValue -Payload $OverlayResult -Name 'payload'
$Groups = Get-PropertyValue -Payload $Authority -Name 'authority_blocker_groups'
$OverlayGroup = Get-PropertyValue -Payload $Groups -Name 'overlay_window'
$OverlayBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $OverlayGroup -Name 'blockers' -Default @())
$OverlayRequiredBefore = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $OverlayGroup -Name 'required_before' -Default @())
$OverlayPreflightBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Overlay -Name 'blockers' -Default @())
$OverlayPreflightConfig = Get-PropertyValue -Payload $Overlay -Name 'overlay'
$AuthorityGovernance = Get-PropertyValue -Payload $Authority -Name 'governance'
$AuthorityBoundary = Get-PropertyValue -Payload $Authority -Name 'boundary_proof'
$OverlayGovernance = Get-PropertyValue -Payload $Overlay -Name 'governance'
$RemainingFamilies = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Authority -Name 'remaining_authority_families' -Default @())
$RemainingAfter = [string[]]@($RemainingFamilies | Where-Object { $_ -eq 'resident_claim' })

$AuthorityObserved = [int](Get-PropertyValue -Payload $AuthorityResult -Name 'exit_code' -Default -1) -eq 0 -and [string](Get-PropertyValue -Payload $Authority -Name 'status' -Default '') -eq 'proof_passed' -and [bool](Get-PropertyValue -Payload $Authority -Name 'ok' -Default $false)
$HotkeyObserved = [int](Get-PropertyValue -Payload $HotkeyResult -Name 'exit_code' -Default -1) -eq 0 -and [string](Get-PropertyValue -Payload $Hotkey -Name 'status' -Default '') -eq 'proof_passed' -and [bool](Get-PropertyValue -Payload $Hotkey -Name 'ok' -Default $false) -and [string](Get-PropertyValue -Payload $Hotkey -Name 'next_authority_family' -Default '') -eq 'overlay_window'
$OverlayPreflightObserved = [int](Get-PropertyValue -Payload $OverlayResult -Name 'exit_code' -Default -1) -eq 0 -and [string](Get-PropertyValue -Payload $Overlay -Name 'status' -Default '') -eq 'blocked' -and -not [bool](Get-PropertyValue -Payload $Overlay -Name 'ready' -Default $true) -and $OverlayPreflightBlockers -contains 'overlay_window_disabled' -and $OverlayPreflightBlockers -contains 'overlay_control_authority_not_granted' -and $OverlayPreflightBlockers -contains 'window_management_authority_not_granted' -and $OverlayPreflightBlockers -contains 'capture_authority_not_granted' -and [bool](Get-PropertyValue -Payload $OverlayGovernance -Name 'read_only_contract' -Default $false) -and -not [bool](Get-PropertyValue -Payload $OverlayGovernance -Name 'overlay_control_authority' -Default $true) -and -not [bool](Get-PropertyValue -Payload $OverlayGovernance -Name 'window_management_authority' -Default $true) -and -not [bool](Get-PropertyValue -Payload $OverlayGovernance -Name 'capture_authority' -Default $true)
$OverlayFamilyObserved = $AuthorityObserved -and $HotkeyObserved -and $OverlayPreflightObserved -and [string](Get-PropertyValue -Payload $OverlayGroup -Name 'id' -Default '') -eq 'overlay_window' -and [string](Get-PropertyValue -Payload $OverlayGroup -Name 'status' -Default '') -eq 'blocked' -and -not [bool](Get-PropertyValue -Payload $OverlayGroup -Name 'ready' -Default $true) -and -not [bool](Get-PropertyValue -Payload $OverlayGroup -Name 'authority_granted' -Default $true) -and -not [bool](Get-PropertyValue -Payload $OverlayGroup -Name 'would_execute' -Default $true) -and [string](Get-PropertyValue -Payload $OverlayGroup -Name 'route' -Default '') -eq '/lens/overlay' -and $OverlayBlockers -contains 'overlay_window_disabled' -and $OverlayBlockers -contains 'overlay_control_authority_not_granted' -and $OverlayBlockers -contains 'window_management_authority_not_granted' -and $OverlayBlockers -contains 'capture_authority_not_granted'
$SideEffectsDenied = $OverlayFamilyObserved -and -not [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_launch_process' -Default $true) -and -not [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_supervise_process' -Default $true) -and -not [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_start_service' -Default $true) -and -not [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_register_tray' -Default $true) -and -not [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_register_hotkey' -Default $true) -and -not [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_open_overlay' -Default $true) -and -not [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_write_memory' -Default $true) -and -not [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_claim_resident' -Default $true)
$AuthorityBoundaryObserved = $SideEffectsDenied -and [bool](Get-PropertyValue -Payload $AuthorityGovernance -Name 'diagnostic_only' -Default $false) -and -not [bool](Get-PropertyValue -Payload $AuthorityGovernance -Name 'overlay_control_authority' -Default $true) -and -not [bool](Get-PropertyValue -Payload $AuthorityGovernance -Name 'memory_write' -Default $true) -and -not [bool](Get-PropertyValue -Payload $AuthorityGovernance -Name 'resident_claim_authority' -Default $true)

$Checks = @(
  (New-Check -Id 'resident_runtime_authority_blockers_proof' -Status $(if ($AuthorityObserved) { 'proof_observed' } else { 'missing_or_failed' }) -Passed $AuthorityObserved -Evidence 'scripts/lens-resident-runtime-authority-blockers-proof.ps1 -Mode Status' -Reason 'Authority blocker families must be observable before overlay-window can be consumed.')
  (New-Check -Id 'previous_hotkey_summon_family' -Status $(if ($HotkeyObserved) { 'blocked' } else { 'missing_or_unexpected' }) -Passed $HotkeyObserved -Evidence 'scripts/lens-resident-runtime-hotkey-summon-boundary-proof.ps1 -Mode Status' -Reason 'Hotkey summon must remain blocked before overlay window is treated as next boundary.')
  (New-Check -Id 'overlay_preflight_readback' -Status $(if ($OverlayPreflightObserved) { 'blocked_readback_ready' } else { 'missing_or_unexpected' }) -Passed $OverlayPreflightObserved -Evidence 'scripts/lens-overlay-preflight.ps1 -Mode Status' -Reason 'Overlay preflight must remain read-only and blocked.')
  (New-Check -Id 'overlay_window_family' -Status $(if ($OverlayFamilyObserved) { 'blocked' } else { 'missing_or_unexpected' }) -Passed $OverlayFamilyObserved -Evidence '/lens/overlay' -Reason 'Overlay window, focus, dock, and capture authority must remain blocked.')
  (New-Check -Id 'overlay_window_side_effects_denied' -Status $(if ($SideEffectsDenied) { 'denied_no_overlay_window' } else { 'unexpected_side_effect' }) -Passed $SideEffectsDenied -Evidence 'resident_runtime_boundary_proof.would_*' -Reason 'The proof must not open overlay windows, bind hotkeys, control tray/services, write memory, or claim residency.')
  (New-Check -Id 'authority_boundary' -Status $(if ($AuthorityBoundaryObserved) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $AuthorityBoundaryObserved -Evidence 'authority_blockers.governance + overlay.preflight.governance' -Reason 'This proof must not grant overlay, execution, sensing, capture, memory, approval-decision, or resident-claim authority.')
)
$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

[ordered]@{
  ok = $ProofPassed; kind = 'lens.resident_runtime.overlay_window_boundary.proof'; status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }; mode = $Mode.ToLowerInvariant(); repo_root = $RepoRoot
  authority_family = 'overlay_window'; previous_authority_family = 'hotkey_summon'; next_authority_family = 'resident_claim'
  overlay_window_boundary_observed = $OverlayFamilyObserved; previous_hotkey_summon_family_observed = $HotkeyObserved; overlay_preflight_observed = $OverlayPreflightObserved; authority_blockers_proof_observed = $AuthorityObserved; side_effects_denied = $SideEffectsDenied; fifth_authority_family_consumed = $OverlayFamilyObserved
  local_process_launch_authority = $false; process_supervision_authority = $false; process_restart_authority = $false; service_install_authority = $false; service_control_authority = $false; tray_registration_authority = $false; tray_icon_authority = $false; notification_authority = $false; summon_authority = $false; hotkey_registration_authority = $false; overlay_control_authority = $false; window_management_authority = $false; capture_authority = $false; new_sensing_authority = $false; resident_claim_authority = $false
  would_launch_process = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_launch_process' -Default $false); would_supervise_process = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_supervise_process' -Default $false); would_restart_process = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_restart_process' -Default $false); would_install_service = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_install_service' -Default $false); would_start_service = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_start_service' -Default $false); would_register_tray = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_register_tray' -Default $false); would_register_hotkey = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_register_hotkey' -Default $false); would_open_overlay = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_open_overlay' -Default $false); would_write_memory = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_write_memory' -Default $false); would_claim_resident = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_claim_resident' -Default $false)
  overlay_window = [ordered]@{ status = [string](Get-PropertyValue -Payload $OverlayGroup -Name 'status' -Default 'missing'); ready = [bool](Get-PropertyValue -Payload $OverlayGroup -Name 'ready' -Default $false); authority_granted = [bool](Get-PropertyValue -Payload $OverlayGroup -Name 'authority_granted' -Default $false); would_execute = [bool](Get-PropertyValue -Payload $OverlayGroup -Name 'would_execute' -Default $false); route = [string](Get-PropertyValue -Payload $OverlayGroup -Name 'route' -Default ''); evidence = [string[]]@(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $OverlayGroup -Name 'evidence' -Default @())); required_before = [string[]]@($OverlayRequiredBefore); blockers = [string[]]@($OverlayBlockers) }
  overlay_preflight = [ordered]@{ status = [string](Get-PropertyValue -Payload $Overlay -Name 'status' -Default 'missing'); ready = [bool](Get-PropertyValue -Payload $Overlay -Name 'ready' -Default $false); overlay_name = [string](Get-PropertyValue -Payload $Overlay -Name 'overlay_name' -Default ''); config_path = [string](Get-PropertyValue -Payload $Overlay -Name 'config_path' -Default ''); overlay_scope = [string](Get-PropertyValue -Payload $Overlay -Name 'overlay_scope' -Default ''); window_enabled = [bool](Get-PropertyValue -Payload $OverlayPreflightConfig -Name 'window_enabled' -Default $false); always_on_top = [bool](Get-PropertyValue -Payload $OverlayPreflightConfig -Name 'always_on_top' -Default $false); required_before_enable = [string[]]@(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Overlay -Name 'required_before_enable' -Default @())); blockers = [string[]]@($OverlayPreflightBlockers) }
  checks = @($Checks); blockers = [string[]]@($OverlayBlockers); remaining_authority_families = [string[]]@($RemainingFamilies); remaining_authority_families_after_this_boundary = [string[]]@($RemainingAfter); next_smallest_truthful_gap = 'resident_runtime_resident_claim_authority_boundary'; evidence = @('scripts/lens-resident-runtime-authority-blockers-proof.ps1 -Mode Status', 'scripts/lens-resident-runtime-hotkey-summon-boundary-proof.ps1 -Mode Status', 'scripts/lens-overlay-preflight.ps1 -Mode Status', '/lens/overlay')
  governance = [ordered]@{ diagnostic_only = $true; wraps_existing_authority_blockers_proof = $true; hotkey_summon_boundary_readback = $HotkeyObserved; overlay_preflight_readback = $OverlayPreflightObserved; product_execution_authority = $false; execution_authority = $false; approval_decision_authority = $false; local_process_launch_authority = $false; process_supervision_authority = $false; process_restart_authority = $false; service_install_authority = $false; service_control_authority = $false; tray_registration_authority = $false; tray_icon_authority = $false; notification_authority = $false; summon_authority = $false; hotkey_registration_authority = $false; overlay_control_authority = $false; window_management_authority = $false; capture_authority = $false; new_sensing_authority = $false; memory_write = $false; receipt_write_authority = $false; resident_claim_authority = $false; mutation_authority_granted = $false }
  message = 'The resident runtime overlay-window authority family is consumed as a readback boundary: overlay window, focus, dock, capture, and window-management authority remain blocked and no overlay, process, tray, hotkey, memory, approval-decision, sensing, or resident-claim side effect is produced.'
} | ConvertTo-Json -Depth 8

exit $(if ($ProofPassed) { 0 } else { 1 })