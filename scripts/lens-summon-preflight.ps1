[CmdletBinding()]
param(
  [ValidateSet('Status', 'Bind', 'Launch')]
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
$RequiredBeforeEnable = Get-StringListProperty -Payload $Config -Name 'required_before_enable'
$DataRoot = Get-DataRoot -Override $DataDir
$ResidentHostProcessReadback = Get-HostProcessReadback -Root $DataRoot

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
      $RequirementBlockers = if ($TrayRequired) { [string[]]@('tray_host_missing') } else { [string[]]@() }
      [void]$RequiredBeforeEnableDependencies.Add((New-PrerequisiteReadback `
            -Id 'tray_presence' `
            -Family 'tray_presence' `
            -Ready (-not $TrayRequired) `
            -Blockers $RequirementBlockers `
            -Route '/lens/tray' `
            -ReadinessRoute '/lens/tray/readiness' `
            -ProofScript 'scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status' `
            -NextStep 'resolve_tray_presence_before_summon_enablement' `
            -NextSmallestTruthfulGap 'summon_overlay_window_blocker_boundary' `
            -AuthorityRequired 'tray_registration_authority'))
    }
    'overlay_window' {
      $RequirementBlockers = if ($OverlayRequired) { [string[]]@('overlay_window_missing') } else { [string[]]@() }
      [void]$RequiredBeforeEnableDependencies.Add((New-PrerequisiteReadback `
            -Id 'overlay_window' `
            -Family 'overlay_window' `
            -Ready (-not $OverlayRequired) `
            -Blockers $RequirementBlockers `
            -Route '/lens/overlay' `
            -ReadinessRoute '/lens/overlay/readiness' `
            -ProofScript 'scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status' `
            -NextStep 'resolve_overlay_window_before_summon_enablement' `
            -NextSmallestTruthfulGap 'summon_global_hotkey_binding_blocker_boundary' `
            -AuthorityRequired 'overlay_control_authority'))
    }
    'global_hotkey_binding' {
      $RequirementBlockers = [System.Collections.ArrayList]::new()
      if (-not $GlobalHotkey) { [void]$RequirementBlockers.Add('global_hotkey_not_declared') }
      if (-not $BindingEnabled) { [void]$RequirementBlockers.Add('global_hotkey_binding_disabled') }
      if (-not $RegisterHotkey) { [void]$RequirementBlockers.Add('global_hotkey_registration_disabled') }
      if (-not $HotkeyRegistrationAuthority) { [void]$RequirementBlockers.Add('hotkey_registration_authority_not_granted') }
      [void]$RequiredBeforeEnableDependencies.Add((New-PrerequisiteReadback `
            -Id 'global_hotkey_binding' `
            -Family 'global_hotkey_binding' `
            -Ready ($RequirementBlockers.Count -eq 0) `
            -Blockers ([string[]]@($RequirementBlockers.ToArray())) `
            -Route '/lens/summon' `
            -ReadinessRoute '/lens/summon/readiness' `
            -ProofScript 'scripts/lens-summon-global-hotkey-binding-blocker-proof.ps1 -Mode Status' `
            -NextStep 'resolve_global_hotkey_binding_before_summon_enablement' `
            -NextSmallestTruthfulGap 'summon_binding_blocker_boundary' `
            -AuthorityRequired 'hotkey_registration_authority'))
    }
    'summon_binding' {
      $RequirementBlockers = [System.Collections.ArrayList]::new()
      if ($BlockedReason) { [void]$RequirementBlockers.Add($BlockedReason) }
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
  config_path = 'config/runtime/lens/summon.json'
  acceptance_criterion = 'summon_anywhere'
  next_smallest_truthful_gap = 'summon_anywhere_blockers'
  required_before_enable = @($RequiredBeforeEnable)
  missing_required_before_enable = @($MissingRequiredBeforeEnable)
  required_before_enable_ready = (@($MissingRequiredBeforeEnable).Count -eq 0)
  first_missing_required_before_enable = $FirstMissingRequiredBeforeEnable
  first_missing_requirement_handoff = $FirstMissingRequirementHandoff
  enablement_dependency_readback = @($RequiredBeforeEnableDependencyArray)
  resident_host_process_readback = $ResidentHostProcessReadback
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
    required_before_enable_readback = $true
    resident_host_process_readback = $true
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
