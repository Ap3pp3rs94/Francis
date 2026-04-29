[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status'
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

function Get-PowerShellPath {
  try {
    $Current = Get-Process -Id $PID -ErrorAction Stop
    if (-not [string]::IsNullOrWhiteSpace([string]$Current.Path)) {
      return [string]$Current.Path
    }
  } catch {
  }

  $Pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
  if ($null -ne $Pwsh) {
    return [string]$Pwsh.Source
  }
  $WindowsPowerShell = Get-Command powershell -ErrorAction SilentlyContinue
  if ($null -ne $WindowsPowerShell) {
    return [string]$WindowsPowerShell.Source
  }
  return ''
}

function Get-PropertyValue {
  param(
    [object]$Payload,
    [string]$Name,
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
  param([object]$Value)

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
  $SingleValue = [string]$Value
  if ([string]::IsNullOrWhiteSpace($SingleValue)) {
    return @()
  }
  return @($SingleValue)
}

function Invoke-JsonScript {
  param(
    [string]$PowerShellPath,
    [string]$ScriptPath,
    [string[]]$ScriptArgs = @()
  )

  if ([string]::IsNullOrWhiteSpace($PowerShellPath) -or -not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
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

$PowerShellPath = Get-PowerShellPath
$HostPreflightPath = Join-Path $PSScriptRoot 'lens-host-preflight.ps1'
$SupervisionProofPath = Join-Path $PSScriptRoot 'lens-host-supervision-proof.ps1'
$TrayPreflightPath = Join-Path $PSScriptRoot 'lens-tray-preflight.ps1'
$OverlayPreflightPath = Join-Path $PSScriptRoot 'lens-overlay-preflight.ps1'
$SummonPreflightPath = Join-Path $PSScriptRoot 'lens-summon-preflight.ps1'

$HostPreflight = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $HostPreflightPath -ScriptArgs @('-Mode', 'Status')
$TrayPreflight = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $TrayPreflightPath -ScriptArgs @('-Mode', 'Status')
$OverlayPreflight = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $OverlayPreflightPath -ScriptArgs @('-Mode', 'Status')
$SummonPreflight = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $SummonPreflightPath -ScriptArgs @('-Mode', 'Status')

$HostPayload = Get-PropertyValue -Payload $HostPreflight -Name 'payload'
$TrayPayload = Get-PropertyValue -Payload $TrayPreflight -Name 'payload'
$OverlayPayload = Get-PropertyValue -Payload $OverlayPreflight -Name 'payload'
$SummonPayload = Get-PropertyValue -Payload $SummonPreflight -Name 'payload'

$Tray = Get-PropertyValue -Payload $TrayPayload -Name 'tray'
$Overlay = Get-PropertyValue -Payload $OverlayPayload -Name 'overlay'
$Binding = Get-PropertyValue -Payload $SummonPayload -Name 'binding'
$HostGovernance = Get-PropertyValue -Payload $HostPayload -Name 'governance'
$TrayGovernance = Get-PropertyValue -Payload $TrayPayload -Name 'governance'
$OverlayGovernance = Get-PropertyValue -Payload $OverlayPayload -Name 'governance'
$SummonGovernance = Get-PropertyValue -Payload $SummonPayload -Name 'governance'

$HostLifecycleBlocked = (
  [int](Get-PropertyValue -Payload $HostPreflight -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $HostPayload -Name 'kind' -Default '') -eq 'lens.host.lifecycle_preflight' -and
  [string](Get-PropertyValue -Payload $HostPayload -Name 'status' -Default '') -eq 'blocked'
)
$SupervisionProofAvailable = Test-Path -LiteralPath $SupervisionProofPath -PathType Leaf
$TrayBlocked = (
  [int](Get-PropertyValue -Payload $TrayPreflight -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $TrayPayload -Name 'kind' -Default '') -eq 'lens.tray.preflight' -and
  [string](Get-PropertyValue -Payload $TrayPayload -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $TrayPayload -Name 'ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Tray -Name 'tray_host_enabled' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Tray -Name 'tray_icon_enabled' -Default $true)
)
$OverlayBlocked = (
  [int](Get-PropertyValue -Payload $OverlayPreflight -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $OverlayPayload -Name 'kind' -Default '') -eq 'lens.overlay.preflight' -and
  [string](Get-PropertyValue -Payload $OverlayPayload -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $OverlayPayload -Name 'ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Overlay -Name 'window_enabled' -Default $true)
)
$SummonBlocked = (
  [int](Get-PropertyValue -Payload $SummonPreflight -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'kind' -Default '') -eq 'lens.summon.preflight' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $SummonPayload -Name 'ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Binding -Name 'binding_enabled' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Binding -Name 'register_hotkey' -Default $true)
)
$AuthorityDenied = (
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'service_install_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayGovernance -Name 'tray_icon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayGovernance -Name 'window_management_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'hotkey_registration_authority' -Default $true)
)
$ResidentClaimBlocked = $HostLifecycleBlocked -and $TrayBlocked -and $OverlayBlocked -and $SummonBlocked -and $AuthorityDenied

$Checks = @(
  (New-Check -Id 'host_lifecycle_boundary' -Status $(if ($HostLifecycleBlocked) { 'blocked_readback_ready' } else { 'failed' }) -Passed $HostLifecycleBlocked -Evidence 'scripts/lens-host-preflight.ps1 -Mode Status' -Reason 'Host lifecycle must be readable and blocked before resident surface work.')
  (New-Check -Id 'supervision_proof_available' -Status $(if ($SupervisionProofAvailable) { 'available' } else { 'missing' }) -Passed $SupervisionProofAvailable -Evidence 'scripts/lens-host-supervision-proof.ps1' -Reason 'The separate foreground/supervision proof remains the bounded process-readiness evidence.')
  (New-Check -Id 'tray_presence_preflight' -Status $(if ($TrayBlocked) { 'blocked_disabled' } else { 'failed' }) -Passed $TrayBlocked -Evidence 'scripts/lens-tray-preflight.ps1 -Mode Status' -Reason 'Tray presence config must be readable, disabled, and blocked.')
  (New-Check -Id 'overlay_window_preflight' -Status $(if ($OverlayBlocked) { 'blocked_disabled' } else { 'failed' }) -Passed $OverlayBlocked -Evidence 'scripts/lens-overlay-preflight.ps1 -Mode Status' -Reason 'Overlay window config must be readable, disabled, and blocked.')
  (New-Check -Id 'summon_binding_preflight' -Status $(if ($SummonBlocked) { 'blocked_disabled' } else { 'failed' }) -Passed $SummonBlocked -Evidence 'scripts/lens-summon-preflight.ps1 -Mode Status' -Reason 'Summon binding config must be readable, declared, disabled, and blocked.')
  (New-Check -Id 'authority_boundary' -Status $(if ($AuthorityDenied) { 'blocked' } else { 'unexpected_authority' }) -Passed $AuthorityDenied -Evidence 'preflight.governance' -Reason 'Resident surface proof must not grant service, tray, overlay, hotkey, or summon authority.')
  (New-Check -Id 'resident_claim_boundary' -Status $(if ($ResidentClaimBlocked) { 'blocked' } else { 'unexpected_claim' }) -Passed $ResidentClaimBlocked -Evidence 'resident surface flags' -Reason 'Resident claim remains blocked until a real resident surface exists.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })
$AllBlockers = @(
  (ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostPayload -Name 'blockers' -Default @())) +
  (ConvertTo-StringArray -Value (Get-PropertyValue -Payload $TrayPayload -Name 'blockers' -Default @())) +
  (ConvertTo-StringArray -Value (Get-PropertyValue -Payload $OverlayPayload -Name 'blockers' -Default @())) +
  (ConvertTo-StringArray -Value (Get-PropertyValue -Payload $SummonPayload -Name 'blockers' -Default @())) +
  @(
    'resident_surface_missing',
    'tray_presence_missing',
    'overlay_window_missing',
    'summon_anywhere_missing',
    'operator_experience_proof_missing'
  ) | Sort-Object -Unique
)

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.resident_surface.readiness_proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  resident_surface_ready = $false
  ready_for_lens_resident_claim = $false
  resident_claim_allowed = $false
  resident_host_process = $false
  tray_presence = $false
  tray_icon = $false
  overlay_window = $false
  global_hotkey_bound = $false
  summon_anywhere = $false
  operator_experience_proof = $false
  checks = @($Checks)
  blockers = @($AllBlockers)
  proof = [ordered]@{
    host_lifecycle_status = [string](Get-PropertyValue -Payload $HostPayload -Name 'status' -Default '')
    supervision_proof_available = $SupervisionProofAvailable
    tray_status = [string](Get-PropertyValue -Payload $TrayPayload -Name 'status' -Default '')
    overlay_status = [string](Get-PropertyValue -Payload $OverlayPayload -Name 'status' -Default '')
    summon_status = [string](Get-PropertyValue -Payload $SummonPayload -Name 'status' -Default '')
    tray_host_enabled = [bool](Get-PropertyValue -Payload $Tray -Name 'tray_host_enabled' -Default $false)
    tray_icon_enabled = [bool](Get-PropertyValue -Payload $Tray -Name 'tray_icon_enabled' -Default $false)
    overlay_window_enabled = [bool](Get-PropertyValue -Payload $Overlay -Name 'window_enabled' -Default $false)
    overlay_focus_supported = [bool](Get-PropertyValue -Payload $Overlay -Name 'focus_supported' -Default $false)
    global_hotkey = [string](Get-PropertyValue -Payload $SummonPayload -Name 'global_hotkey' -Default '')
    summon_binding_enabled = [bool](Get-PropertyValue -Payload $Binding -Name 'binding_enabled' -Default $false)
    hotkey_registration_enabled = [bool](Get-PropertyValue -Payload $Binding -Name 'register_hotkey' -Default $false)
    tray_blockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $TrayPayload -Name 'blockers' -Default @())
    overlay_blockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $OverlayPayload -Name 'blockers' -Default @())
    summon_blockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $SummonPayload -Name 'blockers' -Default @())
  }
  next_smallest_truthful_gap = 'resident_surface_activation_boundary_or_live_operator_experience_proof'
  governance = [ordered]@{
    read_only_contract = $true
    diagnostic_only = $true
    bounded_foreground_session = $false
    temporary_runtime_state_write = $false
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    window_management_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = $false
    api_local_process_launch_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    tray_icon_authority = $false
    notification_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Lens resident surface readiness is observable and still blocked; this proof does not register tray presence, bind a hotkey, open an overlay, spawn a foreground host, or claim summon-anywhere behavior.'
}

$Payload | ConvertTo-Json -Depth 10
if ($ProofPassed) {
  exit 0
}
exit 1
