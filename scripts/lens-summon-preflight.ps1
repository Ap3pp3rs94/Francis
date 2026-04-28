[CmdletBinding()]
param(
  [ValidateSet('Status', 'Bind', 'Launch')]
  [string]$Mode = 'Status'
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

function Add-Check {
  param(
    [System.Collections.ArrayList]$Target,
    [string]$Id,
    [string]$Status,
    [string]$Reason,
    [string]$Evidence = ''
  )

  [void]$Target.Add([ordered]@{
      id = $Id
      status = $Status
      reason = $Reason
      evidence = $Evidence
    })
}

function Get-BoolProperty {
  param(
    [object]$Payload,
    [string]$Name,
    [bool]$Default = $false
  )

  if ($null -eq $Payload) {
    return $Default
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property) {
    return $Default
  }
  if ($Property.Value -is [bool]) {
    return [bool]$Property.Value
  }
  $Value = [string]$Property.Value
  if ([string]::IsNullOrWhiteSpace($Value)) {
    return $Default
  }
  return $Value.ToLowerInvariant() -eq 'true'
}

function Get-StringProperty {
  param(
    [object]$Payload,
    [string]$Name,
    [string]$Default = ''
  )

  if ($null -eq $Payload) {
    return $Default
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) {
    return $Default
  }
  $Value = [string]$Property.Value
  if ([string]::IsNullOrWhiteSpace($Value)) {
    return $Default
  }
  return $Value
}

$ModeName = $Mode.ToLowerInvariant()
$ConfigPath = Join-Path $RepoRoot 'config\runtime\lens\summon.json'
$ConfigExists = Test-Path -LiteralPath $ConfigPath -PathType Leaf
$Config = $null
$ConfigError = ''
if ($ConfigExists) {
  try {
    $Config = Get-Content -LiteralPath $ConfigPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $ConfigError = [string]$_.Exception.Message
  }
}

$SummonName = Get-StringProperty -Payload $Config -Name 'summon_name' -Default 'Francis Lens Summon'
$GlobalHotkey = Get-StringProperty -Payload $Config -Name 'global_hotkey' -Default ''
$BindingScope = Get-StringProperty -Payload $Config -Name 'binding_scope' -Default 'global'
$PaletteRoute = Get-StringProperty -Payload $Config -Name 'palette_route' -Default '/lens/status'
$HostPreflight = Get-StringProperty -Payload $Config -Name 'host_preflight' -Default 'scripts/lens-host-preflight.ps1'
$HostStatusRunner = Get-StringProperty -Payload $Config -Name 'host_status_runner' -Default 'scripts/lens-host.ps1'
$BlockedReason = Get-StringProperty -Payload $Config -Name 'blocked_reason' -Default 'lens_summon_binding_not_implemented'
$Enabled = Get-BoolProperty -Payload $Config -Name 'enabled' -Default $false
$BindingEnabled = Get-BoolProperty -Payload $Config -Name 'binding_enabled' -Default $false
$RegisterHotkey = Get-BoolProperty -Payload $Config -Name 'register_hotkey' -Default $false
$StartupRegister = Get-BoolProperty -Payload $Config -Name 'startup_register' -Default $false
$OverlayRequired = Get-BoolProperty -Payload $Config -Name 'overlay_required' -Default $true
$TrayRequired = Get-BoolProperty -Payload $Config -Name 'tray_required' -Default $true
$SummonAuthority = Get-BoolProperty -Payload $Config -Name 'summon_authority' -Default $false
$HotkeyRegistrationAuthority = Get-BoolProperty -Payload $Config -Name 'hotkey_registration_authority' -Default $false
$OverlayControlAuthority = Get-BoolProperty -Payload $Config -Name 'overlay_control_authority' -Default $false
$LocalProcessLaunchAuthority = Get-BoolProperty -Payload $Config -Name 'local_process_launch_authority' -Default $false

$HostPreflightPath = Join-Path $RepoRoot $HostPreflight
$HostPreflightExists = Test-Path -LiteralPath $HostPreflightPath -PathType Leaf
$HostStatusRunnerPath = Join-Path $RepoRoot $HostStatusRunner
$HostStatusRunnerExists = Test-Path -LiteralPath $HostStatusRunnerPath -PathType Leaf

$Checks = [System.Collections.ArrayList]::new()
Add-Check -Target $Checks -Id 'runtime_root' -Status 'ready' -Reason 'runtime root accepted' -Evidence $RepoRoot
Add-Check -Target $Checks -Id 'summon_config' -Status $(if ($ConfigExists -and -not $ConfigError) { 'present_disabled' } elseif ($ConfigExists) { 'invalid' } else { 'missing' }) -Reason $(if ($ConfigError) { $ConfigError } elseif ($ConfigExists) { 'disabled summon config is present' } else { 'summon config is missing' }) -Evidence 'config/runtime/lens/summon.json'
Add-Check -Target $Checks -Id 'hotkey_declared' -Status $(if ($GlobalHotkey) { 'declared' } else { 'missing' }) -Reason $(if ($GlobalHotkey) { 'global hotkey intent is declared but not bound' } else { 'global hotkey intent is missing' }) -Evidence $GlobalHotkey
Add-Check -Target $Checks -Id 'binding_enabled' -Status $(if ($BindingEnabled) { 'enabled' } else { 'disabled' }) -Reason 'global binding remains disabled until resident Lens host exists' -Evidence $BindingScope
Add-Check -Target $Checks -Id 'register_hotkey' -Status $(if ($RegisterHotkey) { 'would_register' } else { 'disabled' }) -Reason 'hotkey registration remains disabled' -Evidence 'register_hotkey'
Add-Check -Target $Checks -Id 'startup_registration' -Status $(if ($StartupRegister) { 'would_register' } else { 'disabled' }) -Reason 'startup hotkey registration remains disabled' -Evidence 'startup_register'
Add-Check -Target $Checks -Id 'host_preflight' -Status $(if ($HostPreflightExists) { 'present' } else { 'missing' }) -Reason $(if ($HostPreflightExists) { 'host lifecycle preflight is present' } else { 'host lifecycle preflight is missing' }) -Evidence $HostPreflight
Add-Check -Target $Checks -Id 'host_status_runner' -Status $(if ($HostStatusRunnerExists) { 'present' } else { 'missing' }) -Reason $(if ($HostStatusRunnerExists) { 'host status runner is present' } else { 'host status runner is missing' }) -Evidence $HostStatusRunner
Add-Check -Target $Checks -Id 'palette_route' -Status 'declared' -Reason 'summon target route is declared for later UI/host binding' -Evidence $PaletteRoute
Add-Check -Target $Checks -Id 'overlay_window' -Status $(if ($OverlayRequired) { 'missing' } else { 'not_required' }) -Reason 'resident overlay window is not implemented' -Evidence 'overlay_required'
Add-Check -Target $Checks -Id 'tray_presence' -Status $(if ($TrayRequired) { 'missing' } else { 'not_required' }) -Reason 'tray or equivalent presence is not implemented' -Evidence 'tray_required'
Add-Check -Target $Checks -Id 'summon_authority' -Status $(if ($SummonAuthority) { 'allowed' } else { 'blocked' }) -Reason 'summon authority is not granted by this Stage 6 preflight' -Evidence 'summon_authority'
Add-Check -Target $Checks -Id 'hotkey_registration_authority' -Status $(if ($HotkeyRegistrationAuthority) { 'allowed' } else { 'blocked' }) -Reason 'hotkey registration authority is not granted' -Evidence 'hotkey_registration_authority'

$Blockers = [System.Collections.ArrayList]::new()
if ($BlockedReason) { [void]$Blockers.Add($BlockedReason) }
if (-not $ConfigExists) { [void]$Blockers.Add('lens_summon_config_missing') }
if ($ConfigError) { [void]$Blockers.Add('lens_summon_config_invalid') }
if (-not $GlobalHotkey) { [void]$Blockers.Add('global_hotkey_not_declared') }
if (-not $BindingEnabled) { [void]$Blockers.Add('global_hotkey_binding_disabled') }
if (-not $RegisterHotkey) { [void]$Blockers.Add('global_hotkey_registration_disabled') }
if (-not $HostPreflightExists) { [void]$Blockers.Add('lens_host_lifecycle_preflight_missing') }
if (-not $HostStatusRunnerExists) { [void]$Blockers.Add('lens_host_status_runner_missing') }
if ($OverlayRequired) { [void]$Blockers.Add('overlay_window_missing') }
if ($TrayRequired) { [void]$Blockers.Add('tray_host_missing') }
if (-not $SummonAuthority) { [void]$Blockers.Add('summon_authority_not_granted') }
if (-not $HotkeyRegistrationAuthority) { [void]$Blockers.Add('hotkey_registration_authority_not_granted') }
if (-not $OverlayControlAuthority) { [void]$Blockers.Add('overlay_control_authority_not_granted') }
if (-not $LocalProcessLaunchAuthority) { [void]$Blockers.Add('local_process_launch_authority_not_granted') }

$Ready = $Blockers.Count -eq 0
$Payload = [ordered]@{
  ok = $true
  kind = 'lens.summon.preflight'
  status = if ($Ready) { 'ready' } else { 'blocked' }
  mode = $ModeName
  ready = $Ready
  repo_root = $RepoRoot
  summon_name = $SummonName
  config_path = 'config/runtime/lens/summon.json'
  global_hotkey = $GlobalHotkey
  binding_scope = $BindingScope
  palette_route = $PaletteRoute
  checks = $Checks
  blockers = $Blockers
  binding = [ordered]@{
    enabled = $Enabled
    binding_enabled = $BindingEnabled
    register_hotkey = $RegisterHotkey
    startup_register = $StartupRegister
    host_preflight = $HostPreflight
    host_status_runner = $HostStatusRunner
  }
  governance = [ordered]@{
    read_only_contract = $true
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = $false
    hotkey_registration_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Lens summon preflight is read-only; global hotkey binding and summon launch remain blocked.'
}

if ($Mode -eq 'Status') {
  $Payload | ConvertTo-Json -Depth 8
  exit 0
}

$Payload.ok = $false
$Payload.status = 'refused'
$Payload.error = 'lens_summon_action_not_authorized'
$Payload.message = 'Lens summon actions are not authorized by this preflight; use Status for read-only inspection.'
$Payload | ConvertTo-Json -Depth 8
exit 2
