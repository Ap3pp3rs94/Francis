[CmdletBinding()]
param(
  [ValidateSet('Status', 'Open', 'Focus')]
  [string]$Mode = 'Status',

  [string]$DataDir = ''
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

function Get-DataRoot {
  param([string]$Override)

  if (-not [string]::IsNullOrWhiteSpace($Override)) {
    return [System.IO.Path]::GetFullPath($Override)
  }
  $EnvOverride = [string]$env:FRANCIS_DATA_DIR
  if (-not [string]::IsNullOrWhiteSpace($EnvOverride)) {
    return [System.IO.Path]::GetFullPath($EnvOverride)
  }
  return (Join-Path $RepoRoot 'data')
}

function Get-IntegerProperty {
  param(
    [object]$Payload,
    [string]$Name,
    [int]$Default = 0
  )

  $Value = Get-StringProperty -Payload $Payload -Name $Name -Default ''
  if ([string]::IsNullOrWhiteSpace($Value)) {
    return $Default
  }
  try {
    return [int]$Value
  } catch {
    return $Default
  }
}

function Read-JsonFile {
  param([string]$Path)

  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return $null
  }
  try {
    return Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
  } catch {
    return $null
  }
}

function Get-HostProcessReadback {
  param([string]$Root)

  $RuntimeRoot = Join-Path $Root 'runtime\lens-host'
  $PidPath = Join-Path $RuntimeRoot 'lens-host.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  $Status = Read-JsonFile -Path $StatusPath
  $StatusKind = Get-StringProperty -Payload $Status -Name 'kind' -Default ''
  $StatusValue = Get-StringProperty -Payload $Status -Name 'status' -Default ''
  $StatusPid = Get-IntegerProperty -Payload $Status -Name 'pid' -Default 0
  $RuntimeStateExists = Test-Path -LiteralPath $StatusPath -PathType Leaf
  $PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf
  $HostPid = 0
  if ($PidPresent) {
    try {
      $HostPid = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
    } catch {
      $HostPid = 0
    }
  }

  $StatusClaimsRunningHost = (
    $StatusKind -eq 'lens.host.runtime_state' -and
    @('foreground_running', 'resident_running') -contains $StatusValue -and
    $StatusPid -gt 0 -and
    $StatusPid -eq $HostPid
  )
  $ProcessAlive = $false
  if ($StatusClaimsRunningHost -and $HostPid -gt 0) {
    try {
      $ProcessAlive = $null -ne (Get-Process -Id $HostPid -ErrorAction Stop)
    } catch {
      $ProcessAlive = $false
    }
  }

  return [ordered]@{
    process_alive = $ProcessAlive
    pid = $HostPid
    pid_present = $PidPresent
    status_path = $StatusPath
    pid_path = $PidPath
    runtime_state_exists = $RuntimeStateExists
    runtime_status = $StatusValue
    runtime_status_kind = $StatusKind
    runtime_status_pid = $StatusPid
    runtime_status_pid_matches_pid_file = ($StatusPid -gt 0 -and $StatusPid -eq $HostPid)
    requirement_state = if ($ProcessAlive) { 'running' } elseif ($RuntimeStateExists -or $PidPresent) { 'stale_or_unverified' } else { 'missing' }
    blocker = if ($ProcessAlive) { '' } else { 'resident_host_process_missing' }
  }
}

function Get-OverlayRuntimeReadback {
  param(
    [string]$Root,
    [string]$ExpectedOverlayName,
    [string]$ExpectedOverlayScope
  )

  $RuntimeRoot = Join-Path $Root 'runtime\lens-overlay'
  $PidPath = Join-Path $RuntimeRoot 'lens-overlay.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  $Status = Read-JsonFile -Path $StatusPath
  $StatusKind = Get-StringProperty -Payload $Status -Name 'kind' -Default ''
  $StatusValue = Get-StringProperty -Payload $Status -Name 'status' -Default ''
  $StatusPid = Get-IntegerProperty -Payload $Status -Name 'pid' -Default 0
  $RuntimeStateExists = Test-Path -LiteralPath $StatusPath -PathType Leaf
  $PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf
  $OverlayPid = 0
  if ($PidPresent) {
    try {
      $OverlayPid = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
    } catch {
      $OverlayPid = 0
    }
  }

  $StatusClaimsRunningOverlay = (
    $StatusKind -eq 'lens.overlay.runtime_state' -and
    $StatusValue -eq 'overlay_running' -and
    $StatusPid -gt 0 -and
    $StatusPid -eq $OverlayPid -and
    (Get-StringProperty -Payload $Status -Name 'overlay_name' -Default '') -eq $ExpectedOverlayName -and
    (Get-StringProperty -Payload $Status -Name 'overlay_scope' -Default '') -eq $ExpectedOverlayScope
  )
  $ProcessAlive = $false
  if ($StatusClaimsRunningOverlay -and $OverlayPid -gt 0) {
    try {
      $ProcessAlive = $null -ne (Get-Process -Id $OverlayPid -ErrorAction Stop)
    } catch {
      $ProcessAlive = $false
    }
  }

  $OverlayWindowVisible = $ProcessAlive -and (Get-BoolProperty -Payload $Status -Name 'overlay_window_visible' -Default $false)
  $AlwaysOnTop = $OverlayWindowVisible -and (Get-BoolProperty -Payload $Status -Name 'always_on_top' -Default $false)
  $Ready = $OverlayWindowVisible -and $AlwaysOnTop

  return [ordered]@{
    ready = $Ready
    process_alive = $ProcessAlive
    overlay_window_visible = $OverlayWindowVisible
    always_on_top = $AlwaysOnTop
    pid = $OverlayPid
    pid_present = $PidPresent
    status_path = $StatusPath
    pid_path = $PidPath
    runtime_state_exists = $RuntimeStateExists
    runtime_status = $StatusValue
    runtime_status_kind = $StatusKind
    runtime_status_pid = $StatusPid
    runtime_status_pid_matches_pid_file = ($StatusPid -gt 0 -and $StatusPid -eq $OverlayPid)
    overlay_name = Get-StringProperty -Payload $Status -Name 'overlay_name' -Default ''
    expected_overlay_name = $ExpectedOverlayName
    overlay_scope = Get-StringProperty -Payload $Status -Name 'overlay_scope' -Default ''
    expected_overlay_scope = $ExpectedOverlayScope
    requirement_state = if ($Ready) { 'visible' } elseif ($ProcessAlive) { 'process_running_no_visible_overlay_claim' } elseif ($RuntimeStateExists -or $PidPresent) { 'stale_or_unverified' } else { 'missing' }
    blocker = if ($Ready) { '' } elseif ($ProcessAlive) { 'overlay_window_not_observed' } else { 'overlay_window_runtime_missing' }
  }
}

$ModeName = $Mode.ToLowerInvariant()
$ConfigPath = Join-Path $RepoRoot 'config\runtime\lens\overlay.json'
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

$OverlayName = Get-StringProperty -Payload $Config -Name 'overlay_name' -Default 'Francis Lens Overlay'
$OverlayScope = Get-StringProperty -Payload $Config -Name 'overlay_scope' -Default 'user_session'
$StatusRoute = Get-StringProperty -Payload $Config -Name 'status_route' -Default '/lens/status'
$HostRoute = Get-StringProperty -Payload $Config -Name 'host_route' -Default '/lens/host'
$HostPreflight = Get-StringProperty -Payload $Config -Name 'host_preflight' -Default 'scripts/lens-host-preflight.ps1'
$HostStatusRunner = Get-StringProperty -Payload $Config -Name 'host_status_runner' -Default 'scripts/lens-host.ps1'
$OverlayRunner = Get-StringProperty -Payload $Config -Name 'overlay_runner' -Default 'scripts/lens-overlay-window.ps1'
$SummonPreflight = Get-StringProperty -Payload $Config -Name 'summon_preflight' -Default 'scripts/lens-summon-preflight.ps1'
$TrayPreflight = Get-StringProperty -Payload $Config -Name 'tray_preflight' -Default 'scripts/lens-tray-preflight.ps1'
$BlockedReason = Get-StringProperty -Payload $Config -Name 'blocked_reason' -Default 'lens_overlay_window_not_implemented'
$Enabled = Get-BoolProperty -Payload $Config -Name 'enabled' -Default $false
$WindowEnabled = Get-BoolProperty -Payload $Config -Name 'window_enabled' -Default $false
$AlwaysOnTop = Get-BoolProperty -Payload $Config -Name 'always_on_top' -Default $false
$DockSupported = Get-BoolProperty -Payload $Config -Name 'dock_supported' -Default $false
$FocusSupported = Get-BoolProperty -Payload $Config -Name 'focus_supported' -Default $false
$ClickThroughSupported = Get-BoolProperty -Payload $Config -Name 'click_through_supported' -Default $false
$CaptureSupported = Get-BoolProperty -Payload $Config -Name 'capture_supported' -Default $false
$OverlayControlAuthority = Get-BoolProperty -Payload $Config -Name 'overlay_control_authority' -Default $false
$WindowManagementAuthority = Get-BoolProperty -Payload $Config -Name 'window_management_authority' -Default $false
$LocalProcessLaunchAuthority = Get-BoolProperty -Payload $Config -Name 'local_process_launch_authority' -Default $false
$CaptureAuthority = Get-BoolProperty -Payload $Config -Name 'capture_authority' -Default $false
$SummonAuthority = Get-BoolProperty -Payload $Config -Name 'summon_authority' -Default $false
$TrayRegistrationAuthority = Get-BoolProperty -Payload $Config -Name 'tray_registration_authority' -Default $false
$RequiredBeforeEnable = Get-StringListProperty -Payload $Config -Name 'required_before_enable'

$HostPreflightExists = Test-Path -LiteralPath (Join-Path $RepoRoot $HostPreflight) -PathType Leaf
$HostStatusRunnerExists = Test-Path -LiteralPath (Join-Path $RepoRoot $HostStatusRunner) -PathType Leaf
$OverlayRunnerExists = Test-Path -LiteralPath (Join-Path $RepoRoot $OverlayRunner) -PathType Leaf
$SummonPreflightExists = Test-Path -LiteralPath (Join-Path $RepoRoot $SummonPreflight) -PathType Leaf
$TrayPreflightExists = Test-Path -LiteralPath (Join-Path $RepoRoot $TrayPreflight) -PathType Leaf
$DataRoot = Get-DataRoot -Override $DataDir
$HostProcessReadback = Get-HostProcessReadback -Root $DataRoot
$OverlayRuntimeReadback = Get-OverlayRuntimeReadback -Root $DataRoot -ExpectedOverlayName $OverlayName -ExpectedOverlayScope $OverlayScope
$OverlayRuntimeReady = [bool]$OverlayRuntimeReadback.ready
$RuntimeStateExists = [bool]$HostProcessReadback.runtime_state_exists
$PidPresent = [bool]$HostProcessReadback.pid_present
$ResidentHostProcessAlive = [bool]$HostProcessReadback.process_alive

$Checks = [System.Collections.ArrayList]::new()
Add-Check -Target $Checks -Id 'runtime_root' -Status 'ready' -Reason 'runtime root accepted' -Evidence $RepoRoot
Add-Check -Target $Checks -Id 'overlay_config' -Status $(if ($ConfigExists -and -not $ConfigError) { 'present_disabled' } elseif ($ConfigExists) { 'invalid' } else { 'missing' }) -Reason $(if ($ConfigError) { $ConfigError } elseif ($ConfigExists) { 'disabled overlay config is present' } else { 'overlay config is missing' }) -Evidence 'config/runtime/lens/overlay.json'
Add-Check -Target $Checks -Id 'window_enabled' -Status $(if ($WindowEnabled) { 'enabled' } else { 'disabled' }) -Reason 'overlay window remains disabled until resident host exists' -Evidence $OverlayScope
Add-Check -Target $Checks -Id 'always_on_top' -Status $(if ($AlwaysOnTop) { 'enabled' } else { 'disabled' }) -Reason 'always-on-top behavior remains disabled' -Evidence 'always_on_top'
Add-Check -Target $Checks -Id 'focus_support' -Status $(if ($FocusSupported) { 'declared' } else { 'disabled' }) -Reason 'overlay focus support is not implemented' -Evidence 'focus_supported'
Add-Check -Target $Checks -Id 'capture_support' -Status $(if ($CaptureSupported) { 'declared' } else { 'disabled' }) -Reason 'overlay capture support is not implemented' -Evidence 'capture_supported'
Add-Check -Target $Checks -Id 'host_preflight' -Status $(if ($HostPreflightExists) { 'present' } else { 'missing' }) -Reason $(if ($HostPreflightExists) { 'host lifecycle preflight is present' } else { 'host lifecycle preflight is missing' }) -Evidence $HostPreflight
Add-Check -Target $Checks -Id 'host_status_runner' -Status $(if ($HostStatusRunnerExists) { 'present' } else { 'missing' }) -Reason $(if ($HostStatusRunnerExists) { 'host status runner is present' } else { 'host status runner is missing' }) -Evidence $HostStatusRunner
Add-Check -Target $Checks -Id 'overlay_runner' -Status $(if ($OverlayRunnerExists) { 'present' } else { 'missing' }) -Reason $(if ($OverlayRunnerExists) { 'overlay window runtime runner is present' } else { 'overlay window runtime runner is missing' }) -Evidence $OverlayRunner
Add-Check -Target $Checks -Id 'summon_preflight' -Status $(if ($SummonPreflightExists) { 'present' } else { 'missing' }) -Reason $(if ($SummonPreflightExists) { 'summon preflight is present' } else { 'summon preflight is missing' }) -Evidence $SummonPreflight
Add-Check -Target $Checks -Id 'tray_preflight' -Status $(if ($TrayPreflightExists) { 'present' } else { 'missing' }) -Reason $(if ($TrayPreflightExists) { 'tray preflight is present' } else { 'tray preflight is missing' }) -Evidence $TrayPreflight
Add-Check -Target $Checks -Id 'runtime_state' -Status $(if ($ResidentHostProcessAlive) { 'process_observed' } elseif ($RuntimeStateExists -or $PidPresent) { 'stale_or_unverified' } else { 'missing' }) -Reason $(if ($ResidentHostProcessAlive) { 'resident host process is live and matches runtime state' } else { 'resident host runtime state is not live' }) -Evidence 'data/runtime/lens-host'
Add-Check -Target $Checks -Id 'overlay_runtime' -Status $OverlayRuntimeReadback.requirement_state -Reason $(if ($OverlayRuntimeReady) { 'overlay window runtime is live and topmost' } else { 'overlay window runtime is not live' }) -Evidence 'data/runtime/lens-overlay'
Add-Check -Target $Checks -Id 'overlay_control_authority' -Status $(if ($OverlayControlAuthority) { 'allowed' } else { 'blocked' }) -Reason 'overlay control authority is not granted' -Evidence 'overlay_control_authority'
Add-Check -Target $Checks -Id 'window_management_authority' -Status $(if ($WindowManagementAuthority) { 'allowed' } else { 'blocked' }) -Reason 'window management authority is not granted' -Evidence 'window_management_authority'

$Blockers = [System.Collections.ArrayList]::new()
if ($BlockedReason -and -not $OverlayRuntimeReady) { [void]$Blockers.Add($BlockedReason) }
if (-not $ConfigExists) { [void]$Blockers.Add('lens_overlay_config_missing') }
if ($ConfigError) { [void]$Blockers.Add('lens_overlay_config_invalid') }
if (-not $WindowEnabled) { [void]$Blockers.Add('overlay_window_disabled') }
if (-not $AlwaysOnTop) { [void]$Blockers.Add('always_on_top_disabled') }
if (-not $DockSupported) { [void]$Blockers.Add('overlay_dock_not_supported') }
if (-not $FocusSupported) { [void]$Blockers.Add('overlay_focus_not_supported') }
if (-not $ClickThroughSupported) { [void]$Blockers.Add('overlay_click_through_not_supported') }
if (-not $HostPreflightExists) { [void]$Blockers.Add('lens_host_lifecycle_preflight_missing') }
if (-not $HostStatusRunnerExists) { [void]$Blockers.Add('lens_host_status_runner_missing') }
if (-not $OverlayRunnerExists) { [void]$Blockers.Add('lens_overlay_runner_missing') }
if (-not $SummonPreflightExists) { [void]$Blockers.Add('lens_summon_preflight_missing') }
if (-not $TrayPreflightExists) { [void]$Blockers.Add('lens_tray_preflight_missing') }
if ($WindowEnabled -and -not $OverlayRuntimeReady) { [void]$Blockers.Add('overlay_window_runtime_missing') }
if (-not $ResidentHostProcessAlive) { [void]$Blockers.Add('resident_host_process_missing') }
if (-not $OverlayControlAuthority) { [void]$Blockers.Add('overlay_control_authority_not_granted') }
if (-not $WindowManagementAuthority) { [void]$Blockers.Add('window_management_authority_not_granted') }
if (-not $LocalProcessLaunchAuthority) { [void]$Blockers.Add('local_process_launch_authority_not_granted') }
if (-not $CaptureAuthority) { [void]$Blockers.Add('capture_authority_not_granted') }
if (-not $SummonAuthority) { [void]$Blockers.Add('summon_authority_not_granted') }
if (-not $TrayRegistrationAuthority) { [void]$Blockers.Add('tray_registration_authority_not_granted') }

$Ready = $Blockers.Count -eq 0
$Payload = [ordered]@{
  ok = $true
  kind = 'lens.overlay.preflight'
  status = if ($Ready) { 'ready' } else { 'blocked' }
  mode = $ModeName
  ready = $Ready
  repo_root = $RepoRoot
  data_root = $DataRoot
  overlay_name = $OverlayName
  config_path = 'config/runtime/lens/overlay.json'
  required_before_enable = @($RequiredBeforeEnable)
  overlay_scope = $OverlayScope
  status_route = $StatusRoute
  host_route = $HostRoute
  checks = $Checks
  blockers = $Blockers
  overlay = [ordered]@{
    enabled = $Enabled
    window_enabled = $WindowEnabled
    always_on_top = $AlwaysOnTop
    dock_supported = $DockSupported
    focus_supported = $FocusSupported
    click_through_supported = $ClickThroughSupported
    capture_supported = $CaptureSupported
    host_preflight = $HostPreflight
    host_status_runner = $HostStatusRunner
    overlay_runner = $OverlayRunner
    summon_preflight = $SummonPreflight
    tray_preflight = $TrayPreflight
  }
  overlay_runtime = $OverlayRuntimeReadback
  resident_host_process = $HostProcessReadback
  governance = [ordered]@{
    read_only_contract = $true
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    window_management_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = $false
    tray_registration_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Lens overlay preflight is read-only; overlay window and focus actions remain blocked.'
}

if ($Mode -eq 'Status') {
  $Payload | ConvertTo-Json -Depth 8
  exit 0
}

$Payload.ok = $false
$Payload.status = 'refused'
$Payload.error = 'lens_overlay_action_not_authorized'
$Payload.message = 'Lens overlay actions are not authorized by this preflight; use Status for read-only inspection.'
$Payload | ConvertTo-Json -Depth 8
exit 2
