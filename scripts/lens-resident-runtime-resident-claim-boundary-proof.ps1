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
$OverlayWindowScript = Join-Path $PSScriptRoot 'lens-resident-runtime-overlay-window-boundary-proof.ps1'
foreach ($ScriptPath in @($AuthorityScript, $OverlayWindowScript)) {
  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) { throw "Required Lens proof script is missing: $ScriptPath" }
}

$AuthorityArgs = @('-Mode', $Mode)
$OverlayWindowArgs = @('-Mode', $Mode)
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $AuthorityArgs += @('-DataDir', $DataDir)
  $OverlayWindowArgs += @('-DataDir', $DataDir)
}

$AuthorityResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $AuthorityScript -ScriptArgs $AuthorityArgs
$OverlayWindowResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $OverlayWindowScript -ScriptArgs $OverlayWindowArgs
$Authority = Get-PropertyValue -Payload $AuthorityResult -Name 'payload'
$OverlayWindow = Get-PropertyValue -Payload $OverlayWindowResult -Name 'payload'
$Groups = Get-PropertyValue -Payload $Authority -Name 'authority_blocker_groups'
$ResidentClaimGroup = Get-PropertyValue -Payload $Groups -Name 'resident_claim'
$ResidentClaimBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ResidentClaimGroup -Name 'blockers' -Default @())
$ResidentClaimRequiredBefore = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ResidentClaimGroup -Name 'required_before' -Default @())
$AuthorityGovernance = Get-PropertyValue -Payload $Authority -Name 'governance'
$AuthorityBoundary = Get-PropertyValue -Payload $Authority -Name 'boundary_proof'
$RemainingFamilies = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Authority -Name 'remaining_authority_families' -Default @())

$AuthorityObserved = [int](Get-PropertyValue -Payload $AuthorityResult -Name 'exit_code' -Default -1) -eq 0 -and [string](Get-PropertyValue -Payload $Authority -Name 'status' -Default '') -eq 'proof_passed' -and [bool](Get-PropertyValue -Payload $Authority -Name 'ok' -Default $false)
$OverlayWindowObserved = [int](Get-PropertyValue -Payload $OverlayWindowResult -Name 'exit_code' -Default -1) -eq 0 -and [string](Get-PropertyValue -Payload $OverlayWindow -Name 'kind' -Default '') -eq 'lens.resident_runtime.overlay_window_boundary.proof' -and [string](Get-PropertyValue -Payload $OverlayWindow -Name 'status' -Default '') -eq 'proof_passed' -and [bool](Get-PropertyValue -Payload $OverlayWindow -Name 'ok' -Default $false) -and [string](Get-PropertyValue -Payload $OverlayWindow -Name 'authority_family' -Default '') -eq 'overlay_window' -and [string](Get-PropertyValue -Payload $OverlayWindow -Name 'next_authority_family' -Default '') -eq 'resident_claim' -and [bool](Get-PropertyValue -Payload $OverlayWindow -Name 'fifth_authority_family_consumed' -Default $false) -and [bool](Get-PropertyValue -Payload $OverlayWindow -Name 'side_effects_denied' -Default $false)
$ResidentClaimFamilyObserved = $AuthorityObserved -and $OverlayWindowObserved -and [string](Get-PropertyValue -Payload $ResidentClaimGroup -Name 'id' -Default '') -eq 'resident_claim' -and [string](Get-PropertyValue -Payload $ResidentClaimGroup -Name 'status' -Default '') -eq 'blocked' -and -not [bool](Get-PropertyValue -Payload $ResidentClaimGroup -Name 'ready' -Default $true) -and -not [bool](Get-PropertyValue -Payload $ResidentClaimGroup -Name 'authority_granted' -Default $true) -and -not [bool](Get-PropertyValue -Payload $ResidentClaimGroup -Name 'would_execute' -Default $true) -and [string](Get-PropertyValue -Payload $ResidentClaimGroup -Name 'route' -Default '') -eq '/lens/resident-runtime/plan' -and $ResidentClaimBlockers -contains 'resident_claim_authority_not_granted' -and $ResidentClaimBlockers -contains 'resident_surface_runtime_missing'
$SideEffectsDenied = $ResidentClaimFamilyObserved -and -not [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_launch_process' -Default $true) -and -not [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_supervise_process' -Default $true) -and -not [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_start_service' -Default $true) -and -not [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_register_tray' -Default $true) -and -not [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_register_hotkey' -Default $true) -and -not [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_open_overlay' -Default $true) -and -not [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_write_memory' -Default $true) -and -not [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_claim_resident' -Default $true)
$AuthorityBoundaryObserved = $SideEffectsDenied -and [bool](Get-PropertyValue -Payload $AuthorityGovernance -Name 'diagnostic_only' -Default $false) -and -not [bool](Get-PropertyValue -Payload $AuthorityGovernance -Name 'execution_authority' -Default $true) -and -not [bool](Get-PropertyValue -Payload $AuthorityGovernance -Name 'memory_write' -Default $true) -and -not [bool](Get-PropertyValue -Payload $AuthorityGovernance -Name 'resident_claim_authority' -Default $true)

$Checks = @(
  (New-Check -Id 'resident_runtime_authority_blockers_proof' -Status $(if ($AuthorityObserved) { 'proof_observed' } else { 'missing_or_failed' }) -Passed $AuthorityObserved -Evidence 'scripts/lens-resident-runtime-authority-blockers-proof.ps1 -Mode Status' -Reason 'Authority blocker families must be observable before resident-claim can be consumed.')
  (New-Check -Id 'previous_overlay_window_family' -Status $(if ($OverlayWindowObserved) { 'blocked' } else { 'missing_or_unexpected' }) -Passed $OverlayWindowObserved -Evidence 'scripts/lens-resident-runtime-overlay-window-boundary-proof.ps1 -Mode Status' -Reason 'Overlay window must remain blocked before resident claim is treated as the final boundary.')
  (New-Check -Id 'resident_claim_family' -Status $(if ($ResidentClaimFamilyObserved) { 'blocked' } else { 'missing_or_unexpected' }) -Passed $ResidentClaimFamilyObserved -Evidence '/lens/resident-runtime/plan' -Reason 'Resident claim authority must remain blocked until a supervised resident runtime can be truthfully claimed.')
  (New-Check -Id 'resident_claim_side_effects_denied' -Status $(if ($SideEffectsDenied) { 'denied_no_resident_claim' } else { 'unexpected_side_effect' }) -Passed $SideEffectsDenied -Evidence 'resident_runtime_boundary_proof.would_*' -Reason 'The proof must not launch, supervise, control service/tray/hotkey/overlay surfaces, write memory, or claim residency.')
  (New-Check -Id 'authority_boundary' -Status $(if ($AuthorityBoundaryObserved) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $AuthorityBoundaryObserved -Evidence 'authority_blockers.governance' -Reason 'This proof must not grant execution, approval-decision, memory, resident-claim, or mutation authority.')
)
$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

[ordered]@{
  ok = $ProofPassed; kind = 'lens.resident_runtime.resident_claim_boundary.proof'; status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }; mode = $Mode.ToLowerInvariant(); repo_root = $RepoRoot
  authority_family = 'resident_claim'; previous_authority_family = 'overlay_window'; next_authority_family = ''
  resident_claim_boundary_observed = $ResidentClaimFamilyObserved; previous_overlay_window_family_observed = $OverlayWindowObserved; authority_blockers_proof_observed = $AuthorityObserved; side_effects_denied = $SideEffectsDenied; sixth_authority_family_consumed = $ResidentClaimFamilyObserved
  local_process_launch_authority = $false; process_supervision_authority = $false; process_restart_authority = $false; service_install_authority = $false; service_control_authority = $false; tray_registration_authority = $false; tray_icon_authority = $false; notification_authority = $false; summon_authority = $false; hotkey_registration_authority = $false; overlay_control_authority = $false; window_management_authority = $false; capture_authority = $false; new_sensing_authority = $false; resident_claim_authority = $false
  would_launch_process = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_launch_process' -Default $false); would_supervise_process = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_supervise_process' -Default $false); would_restart_process = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_restart_process' -Default $false); would_install_service = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_install_service' -Default $false); would_start_service = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_start_service' -Default $false); would_register_tray = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_register_tray' -Default $false); would_register_hotkey = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_register_hotkey' -Default $false); would_open_overlay = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_open_overlay' -Default $false); would_write_memory = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_write_memory' -Default $false); would_claim_resident = [bool](Get-PropertyValue -Payload $AuthorityBoundary -Name 'would_claim_resident' -Default $false)
  resident_claim = [ordered]@{ status = [string](Get-PropertyValue -Payload $ResidentClaimGroup -Name 'status' -Default 'missing'); ready = [bool](Get-PropertyValue -Payload $ResidentClaimGroup -Name 'ready' -Default $false); authority_granted = [bool](Get-PropertyValue -Payload $ResidentClaimGroup -Name 'authority_granted' -Default $false); would_execute = [bool](Get-PropertyValue -Payload $ResidentClaimGroup -Name 'would_execute' -Default $false); route = [string](Get-PropertyValue -Payload $ResidentClaimGroup -Name 'route' -Default ''); evidence = [string[]]@(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ResidentClaimGroup -Name 'evidence' -Default @())); required_before = [string[]]@($ResidentClaimRequiredBefore); blockers = [string[]]@($ResidentClaimBlockers) }
  checks = @($Checks); blockers = [string[]]@($ResidentClaimBlockers); remaining_authority_families = [string[]]@($RemainingFamilies); remaining_authority_families_after_this_boundary = [string[]]@(); next_smallest_truthful_gap = 'stage6_lens_completion_audit'; evidence = @('scripts/lens-resident-runtime-authority-blockers-proof.ps1 -Mode Status', 'scripts/lens-resident-runtime-overlay-window-boundary-proof.ps1 -Mode Status', '/lens/resident-runtime/plan', '/lens/resident-runtime/execute')
  governance = [ordered]@{ diagnostic_only = $true; wraps_existing_authority_blockers_proof = $true; overlay_window_boundary_readback = $OverlayWindowObserved; product_execution_authority = $false; execution_authority = $false; approval_decision_authority = $false; local_process_launch_authority = $false; process_supervision_authority = $false; process_restart_authority = $false; service_install_authority = $false; service_control_authority = $false; tray_registration_authority = $false; tray_icon_authority = $false; notification_authority = $false; summon_authority = $false; hotkey_registration_authority = $false; overlay_control_authority = $false; window_management_authority = $false; capture_authority = $false; new_sensing_authority = $false; memory_write = $false; receipt_write_authority = $false; resident_claim_authority = $false; mutation_authority_granted = $false }
  message = 'The resident runtime resident-claim authority family is consumed as a readback boundary: resident claim remains blocked because there is no supervised resident runtime, and no process, service, tray, hotkey, overlay, memory, approval-decision, or resident-claim side effect is produced.'
} | ConvertTo-Json -Depth 8

exit $(if ($ProofPassed) { 0 } else { 1 })
