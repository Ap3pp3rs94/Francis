[CmdletBinding()]
param(
  [ValidateSet('Status', 'Bind', 'Launch')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [string]$ConfigOverridePath = ''
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

function Get-StringPropertyPreserveEmpty {
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
  return [string]$Property.Value
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

function Get-ProcessAlive {
  param([int]$ProcessId)

  if ($ProcessId -le 0) {
    return $false
  }
  try {
    return $null -ne (Get-Process -Id $ProcessId -ErrorAction Stop)
  } catch {
    return $false
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

function Get-TrayRuntimeReadback {
  param([string]$Root)

  $RuntimeRoot = Join-Path $Root 'runtime\lens-tray'
  $PidPath = Join-Path $RuntimeRoot 'lens-tray.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  $Status = Read-JsonFile -Path $StatusPath
  $StatusKind = Get-StringProperty -Payload $Status -Name 'kind' -Default ''
  $StatusValue = Get-StringProperty -Payload $Status -Name 'status' -Default ''
  $StatusPid = Get-IntegerProperty -Payload $Status -Name 'pid' -Default 0
  $RuntimeStateExists = Test-Path -LiteralPath $StatusPath -PathType Leaf
  $PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf
  $RuntimePid = 0
  if ($PidPresent) {
    try {
      $RuntimePid = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
    } catch {
      $RuntimePid = 0
    }
  }

  $StatusClaimsRunningTray = (
    $StatusKind -eq 'lens.tray.runtime_state' -and
    $StatusValue -eq 'tray_running' -and
    $StatusPid -gt 0 -and
    $StatusPid -eq $RuntimePid
  )
  $ProcessAlive = if ($StatusClaimsRunningTray) { Get-ProcessAlive -ProcessId $RuntimePid } else { $false }
  $TrayIconVisible = $ProcessAlive -and (Get-BoolProperty -Payload $Status -Name 'tray_icon_visible' -Default $false)
  $RequirementState = if ($TrayIconVisible) {
    'running'
  } elseif ($ProcessAlive) {
    'process_running_no_icon_claim'
  } elseif ($RuntimeStateExists -or $PidPresent) {
    'stale_or_unverified'
  } else {
    'missing'
  }
  $Blocker = if ($TrayIconVisible) {
    ''
  } elseif ($ProcessAlive) {
    'tray_icon_not_observed'
  } else {
    'tray_presence_runtime_missing'
  }

  return [ordered]@{
    ready = $TrayIconVisible
    process_alive = $ProcessAlive
    tray_icon_visible = $TrayIconVisible
    pid = $RuntimePid
    pid_present = $PidPresent
    status_path = $StatusPath
    pid_path = $PidPath
    runtime_state_exists = $RuntimeStateExists
    runtime_status = $StatusValue
    runtime_status_kind = $StatusKind
    runtime_status_pid = $StatusPid
    runtime_status_pid_matches_pid_file = ($StatusPid -gt 0 -and $StatusPid -eq $RuntimePid)
    requirement_state = $RequirementState
    blocker = $Blocker
  }
}

function Get-OverlayRuntimeReadback {
  param([string]$Root)

  $RuntimeRoot = Join-Path $Root 'runtime\lens-overlay'
  $PidPath = Join-Path $RuntimeRoot 'lens-overlay.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  $Status = Read-JsonFile -Path $StatusPath
  $StatusKind = Get-StringProperty -Payload $Status -Name 'kind' -Default ''
  $StatusValue = Get-StringProperty -Payload $Status -Name 'status' -Default ''
  $StatusPid = Get-IntegerProperty -Payload $Status -Name 'pid' -Default 0
  $RuntimeStateExists = Test-Path -LiteralPath $StatusPath -PathType Leaf
  $PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf
  $RuntimePid = 0
  if ($PidPresent) {
    try {
      $RuntimePid = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
    } catch {
      $RuntimePid = 0
    }
  }

  $StatusClaimsRunningOverlay = (
    $StatusKind -eq 'lens.overlay.runtime_state' -and
    $StatusValue -eq 'overlay_running' -and
    $StatusPid -gt 0 -and
    $StatusPid -eq $RuntimePid
  )
  $ProcessAlive = if ($StatusClaimsRunningOverlay) { Get-ProcessAlive -ProcessId $RuntimePid } else { $false }
  $OverlayWindowVisible = $ProcessAlive -and (Get-BoolProperty -Payload $Status -Name 'overlay_window_visible' -Default $false)
  $AlwaysOnTop = $OverlayWindowVisible -and (Get-BoolProperty -Payload $Status -Name 'always_on_top' -Default $false)
  $Ready = $OverlayWindowVisible -and $AlwaysOnTop
  $RequirementState = if ($Ready) {
    'visible_topmost'
  } elseif ($OverlayWindowVisible) {
    'visible_not_topmost'
  } elseif ($ProcessAlive) {
    'process_running_no_visible_overlay_claim'
  } elseif ($RuntimeStateExists -or $PidPresent) {
    'stale_or_unverified'
  } else {
    'missing'
  }
  $Blocker = if ($Ready) {
    ''
  } elseif ($OverlayWindowVisible) {
    'overlay_window_not_topmost'
  } elseif ($ProcessAlive) {
    'overlay_window_not_visible'
  } else {
    'overlay_window_runtime_missing'
  }

  return [ordered]@{
    ready = $Ready
    process_alive = $ProcessAlive
    overlay_window_visible = $OverlayWindowVisible
    always_on_top = $AlwaysOnTop
    pid = $RuntimePid
    pid_present = $PidPresent
    status_path = $StatusPath
    pid_path = $PidPath
    runtime_state_exists = $RuntimeStateExists
    runtime_status = $StatusValue
    runtime_status_kind = $StatusKind
    runtime_status_pid = $StatusPid
    runtime_status_pid_matches_pid_file = ($StatusPid -gt 0 -and $StatusPid -eq $RuntimePid)
    requirement_state = $RequirementState
    blocker = $Blocker
  }
}

function Get-HotkeyRuntimeReadback {
  param(
    [string]$Root,
    [string]$ExpectedHotkey,
    [string]$ExpectedBindingScope
  )

  $RuntimeRoot = Join-Path $Root 'runtime\lens-hotkey'
  $PidPath = Join-Path $RuntimeRoot 'lens-hotkey.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  $Status = Read-JsonFile -Path $StatusPath
  $StatusKind = Get-StringProperty -Payload $Status -Name 'kind' -Default ''
  $StatusValue = Get-StringProperty -Payload $Status -Name 'status' -Default ''
  $StatusPid = Get-IntegerProperty -Payload $Status -Name 'pid' -Default 0
  $RuntimeStateExists = Test-Path -LiteralPath $StatusPath -PathType Leaf
  $PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf
  $RuntimePid = 0
  if ($PidPresent) {
    try {
      $RuntimePid = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
    } catch {
      $RuntimePid = 0
    }
  }

  $StatusClaimsBoundHotkey = (
    $StatusKind -eq 'lens.hotkey.runtime_state' -and
    $StatusValue -eq 'hotkey_bound' -and
    $StatusPid -gt 0 -and
    $StatusPid -eq $RuntimePid -and
    (Get-BoolProperty -Payload $Status -Name 'hotkey_bound' -Default $false) -and
    (Get-StringProperty -Payload $Status -Name 'global_hotkey' -Default '') -eq $ExpectedHotkey -and
    (Get-StringProperty -Payload $Status -Name 'binding_scope' -Default '') -eq $ExpectedBindingScope
  )
  $ProcessAlive = $false
  if ($StatusClaimsBoundHotkey -and $RuntimePid -gt 0) {
    try {
      $ProcessAlive = $null -ne (Get-Process -Id $RuntimePid -ErrorAction Stop)
    } catch {
      $ProcessAlive = $false
    }
  }

  $Ready = $ProcessAlive -and $StatusClaimsBoundHotkey
  $RequirementState = if ($Ready) {
    'bound'
  } elseif ($ProcessAlive) {
    'process_running_no_bound_hotkey_claim'
  } elseif ($RuntimeStateExists -or $PidPresent) {
    'stale_or_unverified'
  } else {
    'missing'
  }
  $Blocker = if ($Ready) { '' } else { 'global_hotkey_binding_runtime_missing' }

  return [ordered]@{
    ready = $Ready
    process_alive = $ProcessAlive
    hotkey_bound = $Ready
    pid = $RuntimePid
    pid_present = $PidPresent
    status_path = $StatusPath
    pid_path = $PidPath
    runtime_state_exists = $RuntimeStateExists
    runtime_status = $StatusValue
    runtime_status_kind = $StatusKind
    runtime_status_pid = $StatusPid
    runtime_status_pid_matches_pid_file = ($StatusPid -gt 0 -and $StatusPid -eq $RuntimePid)
    global_hotkey = Get-StringProperty -Payload $Status -Name 'global_hotkey' -Default ''
    expected_global_hotkey = $ExpectedHotkey
    binding_scope = Get-StringProperty -Payload $Status -Name 'binding_scope' -Default ''
    expected_binding_scope = $ExpectedBindingScope
    launch_on_hotkey = Get-BoolProperty -Payload $Status -Name 'launch_on_hotkey' -Default $false
    summon_runner = Get-StringProperty -Payload $Status -Name 'summon_runner' -Default ''
    press_count = Get-IntegerProperty -Payload $Status -Name 'press_count' -Default 0
    requirement_state = $RequirementState
    blocker = $Blocker
  }
}

function Select-Blockers {
  param(
    [object[]]$Blockers,
    [string[]]$Candidates
  )

  $Selected = [System.Collections.ArrayList]::new()
  foreach ($Candidate in $Candidates) {
    if ($Blockers -contains $Candidate) {
      [void]$Selected.Add($Candidate)
    }
  }
  return @($Selected.ToArray())
}

function New-PrerequisiteReadback {
  param(
    [string]$Id,
    [string]$Family,
    [bool]$Ready,
    [string[]]$Blockers,
    [string]$Route,
    [string]$ReadinessRoute,
    [string]$ProofScript,
    [string]$NextStep,
    [string]$NextSmallestTruthfulGap,
    [string]$AuthorityRequired
  )

  $BlockerArray = [string[]]@($Blockers | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  $FirstBlocker = if (@($BlockerArray).Count -gt 0) { [string]$BlockerArray[0] } else { '' }
  return [ordered]@{
    id = $Id
    family = $Family
    status = if ($Ready) { 'ready' } else { 'blocked' }
    ready = $Ready
    route = $Route
    readiness_route = $ReadinessRoute
    proof_script = $ProofScript
    blocker = $FirstBlocker
    blockers = [string[]]@($BlockerArray)
    blocked_reason = $FirstBlocker
    next_step = $NextStep
    next_smallest_truthful_gap = $NextSmallestTruthfulGap
    authority_required = $AuthorityRequired
    authority_granted = $false
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
  }
}

function New-FirstMissingRequirementHandoff {
  param([object[]]$Dependencies)

  foreach ($Dependency in @($Dependencies)) {
    if (-not [bool]$Dependency.ready) {
      return [ordered]@{
        id = [string]$Dependency.id
        family = [string]$Dependency.family
        status = [string]$Dependency.status
        blocker = [string]$Dependency.blocker
        blockers = [string[]]@($Dependency.blockers)
        route = [string]$Dependency.route
        readiness_route = [string]$Dependency.readiness_route
        proof_script = [string]$Dependency.proof_script
        next_step = [string]$Dependency.next_step
        next_smallest_truthful_gap = [string]$Dependency.next_smallest_truthful_gap
        authority_required = [string]$Dependency.authority_required
        authority_granted = $false
        read_only_contract = $true
        diagnostic_only = $true
        would_execute = $false
        would_mutate = $false
      }
    }
  }
  return [ordered]@{}
}

function Select-AuthorityBlockers {
  param(
    [object[]]$Blockers
  )

  $Selected = [System.Collections.ArrayList]::new()
  foreach ($Blocker in $Blockers) {
    $Value = [string]$Blocker
    if ($Value.EndsWith('_authority_not_granted') -or $Value.EndsWith('_authority_false')) {
      [void]$Selected.Add($Value)
    }
  }
  return @($Selected.ToArray())
}

$ModeName = $Mode.ToLowerInvariant()
$DefaultConfigPath = Join-Path $RepoRoot 'config\runtime\lens\summon.json'
$ConfigPath = if (-not [string]::IsNullOrWhiteSpace($ConfigOverridePath)) {
  [System.IO.Path]::GetFullPath($ConfigOverridePath)
} else {
  $DefaultConfigPath
}
$ConfigEvidencePath = if (-not [string]::IsNullOrWhiteSpace($ConfigOverridePath)) {
  $ConfigPath
} else {
  'config/runtime/lens/summon.json'
}
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
$SummonRunner = Get-StringProperty -Payload $Config -Name 'summon_runner' -Default 'scripts/lens-summon.ps1'
$LocalPaletteLauncher = Get-StringProperty -Payload $Config -Name 'local_palette_launcher' -Default 'scripts/lens-command-palette.ps1 -Mode LocalOpen'
$BlockedReason = Get-StringPropertyPreserveEmpty -Payload $Config -Name 'blocked_reason' -Default 'lens_summon_binding_disabled_pending_authority'
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
$RequiredBeforeEnable = Get-StringListProperty -Payload $Config -Name 'required_before_enable'
$ConfigStatus = if ($ConfigExists -and -not $ConfigError) {
  if ($Enabled -or $BindingEnabled -or $RegisterHotkey -or $SummonAuthority) { 'present_enabled' } else { 'present_disabled' }
} elseif ($ConfigExists) {
  'invalid'
} else {
  'missing'
}
$ConfigReason = if ($ConfigError) {
  $ConfigError
} elseif ($ConfigExists -and $ConfigStatus -eq 'present_enabled') {
  'explicit summon config is present'
} elseif ($ConfigExists) {
  'disabled summon config is present'
} else {
  'summon config is missing'
}
$DataRoot = Get-DataRoot -Override $DataDir
$ResidentHostProcessReadback = Get-HostProcessReadback -Root $DataRoot
$TrayRuntimeReadback = Get-TrayRuntimeReadback -Root $DataRoot
$OverlayRuntimeReadback = Get-OverlayRuntimeReadback -Root $DataRoot
$HotkeyRuntimeReadback = Get-HotkeyRuntimeReadback -Root $DataRoot -ExpectedHotkey $GlobalHotkey -ExpectedBindingScope $BindingScope

$HostPreflightPath = Join-Path $RepoRoot $HostPreflight
$HostPreflightExists = Test-Path -LiteralPath $HostPreflightPath -PathType Leaf
$HostStatusRunnerPath = Join-Path $RepoRoot $HostStatusRunner
$HostStatusRunnerExists = Test-Path -LiteralPath $HostStatusRunnerPath -PathType Leaf
$SummonRunnerPath = Join-Path $RepoRoot $SummonRunner
$SummonRunnerExists = Test-Path -LiteralPath $SummonRunnerPath -PathType Leaf

$Checks = [System.Collections.ArrayList]::new()
Add-Check -Target $Checks -Id 'runtime_root' -Status 'ready' -Reason 'runtime root accepted' -Evidence $RepoRoot
Add-Check -Target $Checks -Id 'summon_config' -Status $ConfigStatus -Reason $ConfigReason -Evidence $ConfigEvidencePath
Add-Check -Target $Checks -Id 'summon_runner' -Status $(if ($SummonRunnerExists) { 'present' } else { 'missing' }) -Reason $(if ($SummonRunnerExists) { 'local summon launcher is present' } else { 'local summon launcher is missing' }) -Evidence $SummonRunner
Add-Check -Target $Checks -Id 'hotkey_declared' -Status $(if ($GlobalHotkey) { 'declared' } else { 'missing' }) -Reason $(if ($GlobalHotkey) { 'global hotkey intent is declared but not bound' } else { 'global hotkey intent is missing' }) -Evidence $GlobalHotkey
Add-Check -Target $Checks -Id 'binding_enabled' -Status $(if ($BindingEnabled) { 'enabled' } else { 'disabled' }) -Reason 'global binding remains disabled until resident Lens host exists' -Evidence $BindingScope
Add-Check -Target $Checks -Id 'register_hotkey' -Status $(if ($RegisterHotkey) { 'would_register' } else { 'disabled' }) -Reason 'hotkey registration remains disabled' -Evidence 'register_hotkey'
Add-Check -Target $Checks -Id 'startup_registration' -Status $(if ($StartupRegister) { 'would_register' } else { 'disabled' }) -Reason 'startup hotkey registration remains disabled' -Evidence 'startup_register'
Add-Check -Target $Checks -Id 'hotkey_runtime' -Status $(if ([bool]$HotkeyRuntimeReadback.ready) { 'bound' } elseif ([bool]$HotkeyRuntimeReadback.runtime_state_exists -or [bool]$HotkeyRuntimeReadback.pid_present) { 'stale_or_unverified' } else { 'missing' }) -Reason $(if ([bool]$HotkeyRuntimeReadback.ready) { 'global hotkey runtime reports a live bound hotkey' } else { 'global hotkey runtime is not live' }) -Evidence 'data/runtime/lens-hotkey/status.json'
Add-Check -Target $Checks -Id 'host_preflight' -Status $(if ($HostPreflightExists) { 'present' } else { 'missing' }) -Reason $(if ($HostPreflightExists) { 'host lifecycle preflight is present' } else { 'host lifecycle preflight is missing' }) -Evidence $HostPreflight
Add-Check -Target $Checks -Id 'host_status_runner' -Status $(if ($HostStatusRunnerExists) { 'present' } else { 'missing' }) -Reason $(if ($HostStatusRunnerExists) { 'host status runner is present' } else { 'host status runner is missing' }) -Evidence $HostStatusRunner
Add-Check -Target $Checks -Id 'palette_route' -Status 'declared' -Reason 'summon target route is declared for later UI/host binding' -Evidence $PaletteRoute
Add-Check -Target $Checks -Id 'overlay_window' -Status $(if ([bool]$OverlayRuntimeReadback.ready) { 'running' } elseif ($OverlayRequired) { 'missing' } else { 'not_required' }) -Reason $(if ([bool]$OverlayRuntimeReadback.ready) { 'overlay window runtime reports visible topmost overlay' } else { 'resident overlay window is not live' }) -Evidence 'data/runtime/lens-overlay/status.json'
Add-Check -Target $Checks -Id 'tray_presence' -Status $(if ([bool]$TrayRuntimeReadback.ready) { 'running' } elseif ($TrayRequired) { 'missing' } else { 'not_required' }) -Reason $(if ([bool]$TrayRuntimeReadback.ready) { 'tray runtime reports visible tray presence' } else { 'tray or equivalent presence is not live' }) -Evidence 'data/runtime/lens-tray/status.json'
Add-Check -Target $Checks -Id 'summon_authority' -Status $(if ($SummonAuthority) { 'allowed' } else { 'blocked' }) -Reason 'summon authority is not granted by this Stage 6 preflight' -Evidence 'summon_authority'
Add-Check -Target $Checks -Id 'hotkey_registration_authority' -Status $(if ($HotkeyRegistrationAuthority) { 'allowed' } else { 'blocked' }) -Reason 'hotkey registration authority is not granted' -Evidence 'hotkey_registration_authority'

$Blockers = [System.Collections.ArrayList]::new()
if ($BlockedReason) { [void]$Blockers.Add($BlockedReason) }
if (-not $ConfigExists) { [void]$Blockers.Add('lens_summon_config_missing') }
if ($ConfigError) { [void]$Blockers.Add('lens_summon_config_invalid') }
if (-not $GlobalHotkey) { [void]$Blockers.Add('global_hotkey_not_declared') }
if (-not $SummonRunnerExists) { [void]$Blockers.Add('lens_summon_runner_missing') }
if (-not $BindingEnabled) { [void]$Blockers.Add('global_hotkey_binding_disabled') }
if (-not $RegisterHotkey) { [void]$Blockers.Add('global_hotkey_registration_disabled') }
if (-not $HostPreflightExists) { [void]$Blockers.Add('lens_host_lifecycle_preflight_missing') }
if (-not $HostStatusRunnerExists) { [void]$Blockers.Add('lens_host_status_runner_missing') }
if ($OverlayRequired -and -not [bool]$OverlayRuntimeReadback.ready) { [void]$Blockers.Add('overlay_window_missing') }
if ($TrayRequired -and -not [bool]$TrayRuntimeReadback.ready) { [void]$Blockers.Add('tray_host_missing') }
if (-not $SummonAuthority) { [void]$Blockers.Add('summon_authority_not_granted') }
if (-not $HotkeyRegistrationAuthority) { [void]$Blockers.Add('hotkey_registration_authority_not_granted') }
if (-not $OverlayControlAuthority) { [void]$Blockers.Add('overlay_control_authority_not_granted') }
if (-not $LocalProcessLaunchAuthority) { [void]$Blockers.Add('local_process_launch_authority_not_granted') }

$BlockerArray = [string[]]@($Blockers.ToArray())
$BlockerGroups = [ordered]@{
  config = [string[]]@(Select-Blockers -Blockers $BlockerArray -Candidates @(
      'lens_summon_config_missing',
      'lens_summon_config_invalid'
    ))
  global_hotkey_binding = [string[]]@(Select-Blockers -Blockers $BlockerArray -Candidates @(
      'global_hotkey_not_declared',
      'global_hotkey_binding_disabled',
      'global_hotkey_registration_disabled',
      'hotkey_registration_authority_not_granted'
    ))
  summon_binding = [string[]]@(Select-Blockers -Blockers $BlockerArray -Candidates @(
      'lens_summon_binding_not_implemented',
      'lens_summon_binding_disabled_pending_authority',
      'lens_summon_runner_missing',
      'summon_authority_not_granted'
    ))
  host_dependency = [string[]]@(Select-Blockers -Blockers $BlockerArray -Candidates @(
      'lens_host_lifecycle_preflight_missing',
      'lens_host_status_runner_missing',
      'local_process_launch_authority_not_granted'
    ))
  surface_dependencies = [string[]]@(Select-Blockers -Blockers $BlockerArray -Candidates @(
      'tray_host_missing',
      'overlay_window_missing'
    ))
  authority = [string[]]@(Select-AuthorityBlockers -Blockers $BlockerArray)
}

$RequiredBeforeEnableDependencies = [System.Collections.ArrayList]::new()
foreach ($Requirement in @($RequiredBeforeEnable)) {
  switch ($Requirement) {
    'resident_host_process' {
      $RequirementBlockers = [System.Collections.ArrayList]::new()
      if (-not [bool]$ResidentHostProcessReadback.process_alive) {
        [void]$RequirementBlockers.Add([string]$ResidentHostProcessReadback.blocker)
      }
      [void]$RequiredBeforeEnableDependencies.Add((New-PrerequisiteReadback `
            -Id 'resident_host_process' `
            -Family 'resident_host' `
            -Ready ([bool]$ResidentHostProcessReadback.process_alive) `
            -Blockers ([string[]]@($RequirementBlockers.ToArray())) `
            -Route '/lens/host' `
            -ReadinessRoute '/lens/host/runtime-loop/readiness' `
            -ProofScript 'scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status' `
            -NextStep 'resolve_resident_host_process_before_summon_enablement' `
            -NextSmallestTruthfulGap 'resident_host_process_not_supervised' `
            -AuthorityRequired 'resident_runtime_execution_authority'))
    }
    'tray_presence' {
      $TrayReady = (-not $TrayRequired) -or [bool]$TrayRuntimeReadback.ready
      $RequirementBlockers = if (-not $TrayReady) { [string[]]@('tray_host_missing') } else { [string[]]@() }
      $TrayDependency = New-PrerequisiteReadback `
            -Id 'tray_presence' `
            -Family 'tray_presence' `
            -Ready $TrayReady `
            -Blockers $RequirementBlockers `
            -Route '/lens/tray' `
            -ReadinessRoute '/lens/tray/readiness' `
            -ProofScript 'scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status' `
            -NextStep 'resolve_tray_presence_before_summon_enablement' `
            -NextSmallestTruthfulGap 'summon_overlay_window_blocker_boundary' `
            -AuthorityRequired 'tray_registration_authority'
      $TrayDependency.tray_runtime_readback = $TrayRuntimeReadback
      $TrayDependency.runtime_ready = [bool]$TrayRuntimeReadback.ready
      $TrayDependency.runtime_requirement_state = [string]$TrayRuntimeReadback.requirement_state
      $TrayDependency.runtime_blocker = [string]$TrayRuntimeReadback.blocker
      $TrayDependency.tray_presence_source = if ([bool]$TrayRuntimeReadback.ready) { 'live_runtime_readback' } else { 'not_observed' }
      [void]$RequiredBeforeEnableDependencies.Add($TrayDependency)
    }
    'overlay_window' {
      $OverlayReady = (-not $OverlayRequired) -or [bool]$OverlayRuntimeReadback.ready
      $RequirementBlockers = if (-not $OverlayReady) { [string[]]@('overlay_window_missing') } else { [string[]]@() }
      $OverlayDependency = New-PrerequisiteReadback `
            -Id 'overlay_window' `
            -Family 'overlay_window' `
            -Ready $OverlayReady `
            -Blockers $RequirementBlockers `
            -Route '/lens/overlay' `
            -ReadinessRoute '/lens/overlay/readiness' `
            -ProofScript 'scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status' `
            -NextStep 'resolve_overlay_window_before_summon_enablement' `
            -NextSmallestTruthfulGap 'summon_global_hotkey_binding_blocker_boundary' `
            -AuthorityRequired 'overlay_control_authority'
      $OverlayDependency.overlay_runtime_readback = $OverlayRuntimeReadback
      $OverlayDependency.runtime_ready = [bool]$OverlayRuntimeReadback.ready
      $OverlayDependency.runtime_requirement_state = [string]$OverlayRuntimeReadback.requirement_state
      $OverlayDependency.runtime_blocker = [string]$OverlayRuntimeReadback.blocker
      $OverlayDependency.overlay_window_source = if ([bool]$OverlayRuntimeReadback.ready) { 'live_runtime_readback' } else { 'not_observed' }
      [void]$RequiredBeforeEnableDependencies.Add($OverlayDependency)
    }
    'global_hotkey_binding' {
      $RequirementBlockers = [System.Collections.ArrayList]::new()
      if (-not $GlobalHotkey) { [void]$RequirementBlockers.Add('global_hotkey_not_declared') }
      if (-not $BindingEnabled) { [void]$RequirementBlockers.Add('global_hotkey_binding_disabled') }
      if (-not $RegisterHotkey) { [void]$RequirementBlockers.Add('global_hotkey_registration_disabled') }
      if (-not $HotkeyRegistrationAuthority) { [void]$RequirementBlockers.Add('hotkey_registration_authority_not_granted') }
      $HotkeyDependency = New-PrerequisiteReadback `
            -Id 'global_hotkey_binding' `
            -Family 'global_hotkey_binding' `
            -Ready ($RequirementBlockers.Count -eq 0) `
            -Blockers ([string[]]@($RequirementBlockers.ToArray())) `
            -Route '/lens/summon' `
            -ReadinessRoute '/lens/summon/readiness' `
            -ProofScript 'scripts/lens-summon-global-hotkey-binding-blocker-proof.ps1 -Mode Status' `
            -NextStep 'resolve_global_hotkey_binding_before_summon_enablement' `
            -NextSmallestTruthfulGap 'summon_binding_blocker_boundary' `
            -AuthorityRequired 'hotkey_registration_authority'
      $HotkeyDependency.hotkey_runtime_readback = $HotkeyRuntimeReadback
      $HotkeyDependency.runtime_ready = [bool]$HotkeyRuntimeReadback.ready
      $HotkeyDependency.runtime_requirement_state = [string]$HotkeyRuntimeReadback.requirement_state
      $HotkeyDependency.runtime_blocker = [string]$HotkeyRuntimeReadback.blocker
      [void]$RequiredBeforeEnableDependencies.Add($HotkeyDependency)
    }
    'summon_binding' {
      $RequirementBlockers = [System.Collections.ArrayList]::new()
      if ($BlockedReason) { [void]$RequirementBlockers.Add($BlockedReason) }
      if (-not $SummonRunnerExists) { [void]$RequirementBlockers.Add('lens_summon_runner_missing') }
      if (-not $SummonAuthority) { [void]$RequirementBlockers.Add('summon_authority_not_granted') }
      [void]$RequiredBeforeEnableDependencies.Add((New-PrerequisiteReadback `
            -Id 'summon_binding' `
            -Family 'summon_binding' `
            -Ready ($RequirementBlockers.Count -eq 0) `
            -Blockers ([string[]]@($RequirementBlockers.ToArray())) `
            -Route '/lens/summon' `
            -ReadinessRoute '/lens/summon/readiness' `
            -ProofScript 'scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status' `
            -NextStep 'resolve_summon_binding_before_summon_enablement' `
            -NextSmallestTruthfulGap 'summon_authority_blocker_boundary' `
            -AuthorityRequired 'summon_authority'))
    }
  }
}
$RequiredBeforeEnableDependencyArray = @($RequiredBeforeEnableDependencies.ToArray())
$MissingRequiredBeforeEnable = [string[]]@(
  $RequiredBeforeEnableDependencyArray | Where-Object { -not [bool]$_.ready } | ForEach-Object { [string]$_.id }
)
$FirstMissingRequirementHandoff = New-FirstMissingRequirementHandoff -Dependencies $RequiredBeforeEnableDependencyArray
$FirstMissingRequiredBeforeEnable = if (@($MissingRequiredBeforeEnable).Count -gt 0) {
  [string]$MissingRequiredBeforeEnable[0]
} else {
  ''
}
$RecommendedHandoff = $FirstMissingRequirementHandoff
$RecommendedHandoffObserved = $false
$RecommendedHandoffSource = ''
$RecommendedNextSlice = ''
$RecommendedProofScript = ''
$RecommendedAuthorityRequired = ''
$RecommendedHandoffId = if ($RecommendedHandoff.Contains('id')) { [string]$RecommendedHandoff['id'] } else { '' }
if (-not [string]::IsNullOrWhiteSpace($RecommendedHandoffId)) {
  $RecommendedHandoffObserved = $true
  $RecommendedHandoffSource = 'summon_preflight_first_missing_requirement_handoff'
  $RecommendedNextSlice = [string]$RecommendedHandoff['next_step']
  $RecommendedProofScript = [string]$RecommendedHandoff['proof_script']
  $RecommendedAuthorityRequired = [string]$RecommendedHandoff['authority_required']
}

$Ready = $Blockers.Count -eq 0
$Payload = [ordered]@{
  ok = $true
  kind = 'lens.summon.preflight'
  status = if ($Ready) { 'ready' } else { 'blocked' }
  mode = $ModeName
  ready = $Ready
  repo_root = $RepoRoot
  data_root = $DataRoot
  summon_name = $SummonName
  config_path = $ConfigEvidencePath
  acceptance_criterion = 'summon_anywhere'
  next_smallest_truthful_gap = 'summon_anywhere_blockers'
  required_before_enable = @($RequiredBeforeEnable)
  missing_required_before_enable = @($MissingRequiredBeforeEnable)
  required_before_enable_ready = (@($MissingRequiredBeforeEnable).Count -eq 0)
  first_missing_required_before_enable = $FirstMissingRequiredBeforeEnable
  first_missing_requirement_handoff = $FirstMissingRequirementHandoff
  recommended_handoff_observed = $RecommendedHandoffObserved
  recommended_handoff_source = $RecommendedHandoffSource
  recommended_handoff = $RecommendedHandoff
  recommended_next_slice = $RecommendedNextSlice
  recommended_proof_script = $RecommendedProofScript
  authority_required = $RecommendedAuthorityRequired
  authority_granted = $false
  first_blocker_family = if ($RecommendedHandoffObserved) { [string]$RecommendedHandoff['family'] } else { '' }
  first_blocker_family_handoff = $RecommendedHandoff
  enablement_dependency_readback = @($RequiredBeforeEnableDependencyArray)
  resident_host_process_readback = $ResidentHostProcessReadback
  tray_runtime_readback = $TrayRuntimeReadback
  overlay_runtime_readback = $OverlayRuntimeReadback
  hotkey_runtime_readback = $HotkeyRuntimeReadback
  global_hotkey = $GlobalHotkey
  binding_scope = $BindingScope
  palette_route = $PaletteRoute
  checks = $Checks
  blockers = $Blockers
  blocker_groups = $BlockerGroups
  binding = [ordered]@{
    enabled = $Enabled
    binding_enabled = $BindingEnabled
    register_hotkey = $RegisterHotkey
    startup_register = $StartupRegister
    host_preflight = $HostPreflight
    host_status_runner = $HostStatusRunner
    summon_runner = $SummonRunner
    summon_runner_present = $SummonRunnerExists
    local_palette_launcher = $LocalPaletteLauncher
    local_binding_target_ready = $SummonRunnerExists
    global_hotkey_runtime_bound = [bool]$HotkeyRuntimeReadback.ready
    hotkey_runtime_requirement_state = [string]$HotkeyRuntimeReadback.requirement_state
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
    hotkey_runtime_readback = $true
    tray_runtime_readback = $true
    overlay_runtime_readback = $true
    summon_runner_readback = $true
    required_before_enable_readback = $true
    resident_host_process_readback = $true
    mutation_authority_granted = $false
  }
  message = 'Lens summon preflight is read-only; local launcher readback is present but global hotkey binding and summon authority remain blocked.'
}

if ($Mode -eq 'Status') {
  $Payload | ConvertTo-Json -Depth 8
  exit 0
}

$ActionMode = $Mode.ToLowerInvariant()
$RequiredAuthorities = [string[]]@(
  'summon_authority',
  'hotkey_registration_authority',
  'overlay_control_authority',
  'local_process_launch_authority'
)
$MissingAuthorities = [string[]]@(Select-AuthorityBlockers -Blockers $BlockerArray)
$ActionGate = [ordered]@{
  action = $ActionMode
  status = if ($Ready) { 'ready_for_execution' } else { 'blocked' }
  policy_gate = 'lens_summon_preflight'
  execution_handoff = "scripts/lens-summon-action.ps1 -Mode $Mode"
  bounded_runtime_handoff = if ($Mode -eq 'Bind') { 'scripts/lens-hotkey-binding.ps1 -Mode Start' } else { 'scripts/lens-summon.ps1 -Mode LocalOpen' }
  required_before_enable_ready = [bool]$Payload.required_before_enable_ready
  missing_required_before_enable = [string[]]@($MissingRequiredBeforeEnable)
  first_missing_required_before_enable = $FirstMissingRequiredBeforeEnable
  first_missing_requirement_handoff = $FirstMissingRequirementHandoff
  required_authorities = $RequiredAuthorities
  missing_authorities = $MissingAuthorities
  blocker_groups = $BlockerGroups
  blockers = $BlockerArray
  binding_execution_attempted = $false
  launch_execution_attempted = $false
  would_register_hotkey = $Ready -and $Mode -eq 'Bind'
  would_summon = $Ready -and $Mode -eq 'Launch'
  would_launch_process = $Ready -and $Mode -eq 'Launch'
  would_open_overlay = $Ready -and $Mode -eq 'Launch'
  would_write_memory = $false
  would_decide_approval = $false
  mutation_authority_granted = $false
}

$Payload.action_gate = $ActionGate
$Payload.binding_execution_attempted = $false
$Payload.launch_execution_attempted = $false
$Payload.governance.read_only_contract = $false
$Payload.governance.action_request_gated = $true
$Payload.governance.summon_action_authorized = $Ready
if ($Ready) {
  $Payload.status = 'ready_for_execution'
  $Payload.error = ''
  $Payload.message = 'Lens summon action passed preflight and is ready for the bounded hotkey-binding handoff; no binding or launch was executed by this preflight.'
  $Payload | ConvertTo-Json -Depth 10
  exit 0
}

$Payload.ok = $false
$Payload.status = 'blocked'
$Payload.error = "lens_summon_${ActionMode}_blocked_by_preflight"
$Payload.message = "Lens summon $ActionMode is blocked by preflight; no binding or launch was attempted."
$Payload | ConvertTo-Json -Depth 8
exit 2
