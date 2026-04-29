[CmdletBinding()]
param(
  [ValidateSet('Status', 'Register', 'Show')]
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

function Get-StringListProperty {
  param(
    [object]$Payload,
    [string]$Name
  )

  $Items = [System.Collections.ArrayList]::new()
  if ($null -eq $Payload) {
    return @($Items.ToArray())
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) {
    return @($Items.ToArray())
  }

  if ($Property.Value -is [System.Array]) {
    foreach ($Item in $Property.Value) {
      $Value = [string]$Item
      if (-not [string]::IsNullOrWhiteSpace($Value)) {
        [void]$Items.Add($Value)
      }
    }
    return @($Items.ToArray())
  }

  $SingleValue = [string]$Property.Value
  if (-not [string]::IsNullOrWhiteSpace($SingleValue)) {
    [void]$Items.Add($SingleValue)
  }
  return @($Items.ToArray())
}

$ModeName = $Mode.ToLowerInvariant()
$ConfigPath = Join-Path $RepoRoot 'config\runtime\lens\tray.json'
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

$PresenceName = Get-StringProperty -Payload $Config -Name 'presence_name' -Default 'Francis Lens Tray Presence'
$TrayScope = Get-StringProperty -Payload $Config -Name 'tray_scope' -Default 'user_session'
$StatusRoute = Get-StringProperty -Payload $Config -Name 'status_route' -Default '/lens/host'
$LensStatusRoute = Get-StringProperty -Payload $Config -Name 'lens_status_route' -Default '/lens/status'
$HostPreflight = Get-StringProperty -Payload $Config -Name 'host_preflight' -Default 'scripts/lens-host-preflight.ps1'
$HostStatusRunner = Get-StringProperty -Payload $Config -Name 'host_status_runner' -Default 'scripts/lens-host.ps1'
$SummonPreflight = Get-StringProperty -Payload $Config -Name 'summon_preflight' -Default 'scripts/lens-summon-preflight.ps1'
$SummonConfig = Get-StringProperty -Payload $Config -Name 'summon_config' -Default 'config/runtime/lens/summon.json'
$BlockedReason = Get-StringProperty -Payload $Config -Name 'blocked_reason' -Default 'lens_tray_presence_not_implemented'
$Enabled = Get-BoolProperty -Payload $Config -Name 'enabled' -Default $false
$TrayHostEnabled = Get-BoolProperty -Payload $Config -Name 'tray_host_enabled' -Default $false
$TrayIconEnabled = Get-BoolProperty -Payload $Config -Name 'tray_icon_enabled' -Default $false
$StartupRegister = Get-BoolProperty -Payload $Config -Name 'startup_register' -Default $false
$NotificationSupported = Get-BoolProperty -Payload $Config -Name 'notification_supported' -Default $false
$TrayRegistrationAuthority = Get-BoolProperty -Payload $Config -Name 'tray_registration_authority' -Default $false
$TrayIconAuthority = Get-BoolProperty -Payload $Config -Name 'tray_icon_authority' -Default $false
$NotificationAuthority = Get-BoolProperty -Payload $Config -Name 'notification_authority' -Default $false
$OverlayControlAuthority = Get-BoolProperty -Payload $Config -Name 'overlay_control_authority' -Default $false
$LocalProcessLaunchAuthority = Get-BoolProperty -Payload $Config -Name 'local_process_launch_authority' -Default $false
$ServiceControlAuthority = Get-BoolProperty -Payload $Config -Name 'service_control_authority' -Default $false
$SummonAuthority = Get-BoolProperty -Payload $Config -Name 'summon_authority' -Default $false
$RequiredBeforeEnable = Get-StringListProperty -Payload $Config -Name 'required_before_enable'

$HostPreflightExists = Test-Path -LiteralPath (Join-Path $RepoRoot $HostPreflight) -PathType Leaf
$HostStatusRunnerExists = Test-Path -LiteralPath (Join-Path $RepoRoot $HostStatusRunner) -PathType Leaf
$SummonPreflightExists = Test-Path -LiteralPath (Join-Path $RepoRoot $SummonPreflight) -PathType Leaf
$SummonConfigExists = Test-Path -LiteralPath (Join-Path $RepoRoot $SummonConfig) -PathType Leaf
$RuntimeStatePath = Join-Path $RepoRoot 'data\runtime\lens-host\status.json'
$PidPath = Join-Path $RepoRoot 'data\runtime\lens-host\lens-host.pid'
$RuntimeStateExists = Test-Path -LiteralPath $RuntimeStatePath -PathType Leaf
$PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf

$Checks = [System.Collections.ArrayList]::new()
Add-Check -Target $Checks -Id 'runtime_root' -Status 'ready' -Reason 'runtime root accepted' -Evidence $RepoRoot
Add-Check -Target $Checks -Id 'tray_config' -Status $(if ($ConfigExists -and -not $ConfigError) { 'present_disabled' } elseif ($ConfigExists) { 'invalid' } else { 'missing' }) -Reason $(if ($ConfigError) { $ConfigError } elseif ($ConfigExists) { 'disabled tray presence config is present' } else { 'tray presence config is missing' }) -Evidence 'config/runtime/lens/tray.json'
Add-Check -Target $Checks -Id 'tray_host_enabled' -Status $(if ($TrayHostEnabled) { 'enabled' } else { 'disabled' }) -Reason 'tray host remains disabled until resident host exists' -Evidence $TrayScope
Add-Check -Target $Checks -Id 'tray_icon_enabled' -Status $(if ($TrayIconEnabled) { 'enabled' } else { 'disabled' }) -Reason 'tray icon remains disabled until tray host authority exists' -Evidence 'tray_icon_enabled'
Add-Check -Target $Checks -Id 'startup_registration' -Status $(if ($StartupRegister) { 'would_register' } else { 'disabled' }) -Reason 'startup tray registration remains disabled' -Evidence 'startup_register'
Add-Check -Target $Checks -Id 'notifications' -Status $(if ($NotificationSupported) { 'declared' } else { 'disabled' }) -Reason 'tray notifications are not implemented' -Evidence 'notification_supported'
Add-Check -Target $Checks -Id 'host_preflight' -Status $(if ($HostPreflightExists) { 'present' } else { 'missing' }) -Reason $(if ($HostPreflightExists) { 'host lifecycle preflight is present' } else { 'host lifecycle preflight is missing' }) -Evidence $HostPreflight
Add-Check -Target $Checks -Id 'host_status_runner' -Status $(if ($HostStatusRunnerExists) { 'present' } else { 'missing' }) -Reason $(if ($HostStatusRunnerExists) { 'host status runner is present' } else { 'host status runner is missing' }) -Evidence $HostStatusRunner
Add-Check -Target $Checks -Id 'summon_preflight' -Status $(if ($SummonPreflightExists) { 'present' } else { 'missing' }) -Reason $(if ($SummonPreflightExists) { 'summon preflight is present' } else { 'summon preflight is missing' }) -Evidence $SummonPreflight
Add-Check -Target $Checks -Id 'summon_config' -Status $(if ($SummonConfigExists) { 'present' } else { 'missing' }) -Reason $(if ($SummonConfigExists) { 'summon config is present' } else { 'summon config is missing' }) -Evidence $SummonConfig
Add-Check -Target $Checks -Id 'runtime_state' -Status $(if ($RuntimeStateExists -or $PidPresent) { 'state_present' } else { 'missing' }) -Reason 'resident host runtime state is not present' -Evidence 'data/runtime/lens-host'
Add-Check -Target $Checks -Id 'tray_registration_authority' -Status $(if ($TrayRegistrationAuthority) { 'allowed' } else { 'blocked' }) -Reason 'tray registration authority is not granted' -Evidence 'tray_registration_authority'
Add-Check -Target $Checks -Id 'tray_icon_authority' -Status $(if ($TrayIconAuthority) { 'allowed' } else { 'blocked' }) -Reason 'tray icon authority is not granted' -Evidence 'tray_icon_authority'

$Blockers = [System.Collections.ArrayList]::new()
if ($BlockedReason) { [void]$Blockers.Add($BlockedReason) }
if (-not $ConfigExists) { [void]$Blockers.Add('lens_tray_config_missing') }
if ($ConfigError) { [void]$Blockers.Add('lens_tray_config_invalid') }
if (-not $TrayHostEnabled) { [void]$Blockers.Add('tray_host_disabled') }
if (-not $TrayIconEnabled) { [void]$Blockers.Add('tray_icon_disabled') }
if (-not $StartupRegister) { [void]$Blockers.Add('tray_startup_registration_disabled') }
if (-not $HostPreflightExists) { [void]$Blockers.Add('lens_host_lifecycle_preflight_missing') }
if (-not $HostStatusRunnerExists) { [void]$Blockers.Add('lens_host_status_runner_missing') }
if (-not $SummonPreflightExists) { [void]$Blockers.Add('lens_summon_preflight_missing') }
if (-not $SummonConfigExists) { [void]$Blockers.Add('lens_summon_config_missing') }
if (-not $RuntimeStateExists -and -not $PidPresent) { [void]$Blockers.Add('resident_host_process_missing') }
if (-not $TrayRegistrationAuthority) { [void]$Blockers.Add('tray_registration_authority_not_granted') }
if (-not $TrayIconAuthority) { [void]$Blockers.Add('tray_icon_authority_not_granted') }
if (-not $NotificationAuthority) { [void]$Blockers.Add('notification_authority_not_granted') }
if (-not $OverlayControlAuthority) { [void]$Blockers.Add('overlay_control_authority_not_granted') }
if (-not $LocalProcessLaunchAuthority) { [void]$Blockers.Add('local_process_launch_authority_not_granted') }
if (-not $ServiceControlAuthority) { [void]$Blockers.Add('service_control_authority_not_granted') }
if (-not $SummonAuthority) { [void]$Blockers.Add('summon_authority_not_granted') }

$Ready = $Blockers.Count -eq 0
$Payload = [ordered]@{
  ok = $true
  kind = 'lens.tray.preflight'
  status = if ($Ready) { 'ready' } else { 'blocked' }
  mode = $ModeName
  ready = $Ready
  repo_root = $RepoRoot
  presence_name = $PresenceName
  config_path = 'config/runtime/lens/tray.json'
  required_before_enable = @($RequiredBeforeEnable)
  tray_scope = $TrayScope
  status_route = $StatusRoute
  lens_status_route = $LensStatusRoute
  checks = $Checks
  blockers = $Blockers
  tray = [ordered]@{
    enabled = $Enabled
    tray_host_enabled = $TrayHostEnabled
    tray_icon_enabled = $TrayIconEnabled
    startup_register = $StartupRegister
    notification_supported = $NotificationSupported
    host_preflight = $HostPreflight
    host_status_runner = $HostStatusRunner
    summon_preflight = $SummonPreflight
    summon_config = $SummonConfig
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
    service_control_authority = $false
    tray_registration_authority = $false
    tray_icon_authority = $false
    notification_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Lens tray preflight is read-only; tray registration and presence remain blocked.'
}

if ($Mode -eq 'Status') {
  $Payload | ConvertTo-Json -Depth 8
  exit 0
}

$Payload.ok = $false
$Payload.status = 'refused'
$Payload.error = 'lens_tray_action_not_authorized'
$Payload.message = 'Lens tray actions are not authorized by this preflight; use Status for read-only inspection.'
$Payload | ConvertTo-Json -Depth 8
exit 2
