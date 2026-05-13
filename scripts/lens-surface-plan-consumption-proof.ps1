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
  $Candidates = @('pwsh', 'powershell')
  foreach ($Candidate in $Candidates) {
    $Command = Get-Command $Candidate -ErrorAction SilentlyContinue
    if ($null -ne $Command) {
      return $Command.Source
    }
  }
  throw 'PowerShell executable not found.'
}

function Get-PropertyValue {
  param(
    [AllowNull()][object]$Payload,
    [string]$Name,
    [object]$Default = $null
  )

  if ($null -eq $Payload) {
    return $Default
  }
  if ($Payload -is [System.Collections.IDictionary] -and $Payload.Contains($Name)) {
    $Value = $Payload[$Name]
    if ($null -ne $Value) {
      return $Value
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
  param([AllowNull()][object]$Value)

  if ($null -eq $Value) {
    return @()
  }
  if ($Value -is [System.Array]) {
    return @($Value | ForEach-Object { [string]$_ })
  }
  return @([string]$Value)
}

function Invoke-JsonScript {
  param(
    [string]$PowerShellPath,
    [string]$ScriptPath,
    [string[]]$ArgumentList,
    [string]$DataRootEnv,
    [string]$RunRoot,
    [string]$Name
  )

  $StdOutPath = Join-Path $RunRoot ($Name + '.stdout.txt')
  $StdErrPath = Join-Path $RunRoot ($Name + '.stderr.txt')
  $PreviousDataRoot = $env:FRANCIS_DATA_DIR
  if (-not [string]::IsNullOrWhiteSpace($DataRootEnv)) {
    $env:FRANCIS_DATA_DIR = $DataRootEnv
  }
  try {
    $ProcessArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ScriptPath) + $ArgumentList
    & $PowerShellPath @ProcessArgs 1> $StdOutPath 2> $StdErrPath
    $ExitCode = if ($null -ne $LASTEXITCODE) { [int]$LASTEXITCODE } else { 0 }
  } finally {
    if ($null -eq $PreviousDataRoot) {
      Remove-Item Env:\FRANCIS_DATA_DIR -ErrorAction SilentlyContinue
    } else {
      $env:FRANCIS_DATA_DIR = $PreviousDataRoot
    }
  }

  $StdOut = ''
  $StdErr = ''
  if (Test-Path -LiteralPath $StdOutPath -PathType Leaf) {
    $RawStdOut = Get-Content -LiteralPath $StdOutPath -Raw -ErrorAction SilentlyContinue
    if ($null -ne $RawStdOut) {
      $StdOut = ([string]$RawStdOut).Trim()
    }
  }
  if (Test-Path -LiteralPath $StdErrPath -PathType Leaf) {
    $RawStdErr = Get-Content -LiteralPath $StdErrPath -Raw -ErrorAction SilentlyContinue
    if ($null -ne $RawStdErr) {
      $StdErr = ([string]$RawStdErr).Trim()
    }
  }

  $Payload = $null
  $ParseError = ''
  if (-not [string]::IsNullOrWhiteSpace($StdOut)) {
    try {
      $Payload = $StdOut | ConvertFrom-Json -ErrorAction Stop
    } catch {
      $ParseError = $_.Exception.Message
    }
  }

  return [ordered]@{
    exit_code = $ExitCode
    stdout = $StdOut
    stderr = $StdErr
    payload = $Payload
    parse_error = $ParseError
  }
}

function Test-SafeTempPath {
  param([string]$Path)

  $TempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
  $Resolved = [System.IO.Path]::GetFullPath($Path)
  return $Resolved.StartsWith($TempRoot, [System.StringComparison]::OrdinalIgnoreCase)
}

function Write-RuntimeJson {
  param(
    [string]$DataRoot,
    [string]$RuntimeName,
    [string]$PidFileName,
    [int]$ProcessId,
    [object]$Payload
  )

  $RuntimeRoot = Join-Path $DataRoot ('runtime/' + $RuntimeName)
  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  Set-Content -LiteralPath (Join-Path $RuntimeRoot $PidFileName) -Value ([string]$ProcessId) -Encoding utf8
  $Payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $RuntimeRoot 'status.json') -Encoding utf8
  return $Payload
}

function Write-ProofSurfaceRuntimeStates {
  param(
    [string]$DataRoot,
    [int]$ProcessId
  )

  $Now = [DateTimeOffset]::UtcNow.ToString('o')
  $Tray = Write-RuntimeJson -DataRoot $DataRoot -RuntimeName 'lens-tray' -PidFileName 'lens-tray.pid' -ProcessId $ProcessId -Payload ([ordered]@{
      kind = 'lens.tray.runtime_state'
      status = 'tray_running'
      pid = $ProcessId
      tray_icon_visible = $true
      presence_name = 'Francis Lens Tray Presence'
      proof_only = $true
      os_tray_registered = $false
      updated_at = $Now
      message = 'Synthetic tray runtime readback bound to the live proof process; no OS tray icon was registered.'
    })
  $Hotkey = Write-RuntimeJson -DataRoot $DataRoot -RuntimeName 'lens-hotkey' -PidFileName 'lens-hotkey.pid' -ProcessId $ProcessId -Payload ([ordered]@{
      kind = 'lens.hotkey.runtime_state'
      status = 'hotkey_bound'
      pid = $ProcessId
      global_hotkey = 'Ctrl+Alt+Space'
      binding_scope = 'global'
      hotkey_bound = $true
      launch_on_hotkey = $false
      summon_runner = 'scripts/lens-summon.ps1'
      press_count = 0
      proof_only = $true
      os_hotkey_registered = $false
      updated_at = $Now
      message = 'Synthetic hotkey runtime readback bound to the live proof process; no global hotkey was registered.'
    })
  $Overlay = Write-RuntimeJson -DataRoot $DataRoot -RuntimeName 'lens-overlay' -PidFileName 'lens-overlay.pid' -ProcessId $ProcessId -Payload ([ordered]@{
      kind = 'lens.overlay.runtime_state'
      status = 'overlay_running'
      pid = $ProcessId
      overlay_name = 'Francis Lens Overlay'
      overlay_scope = 'user_session'
      overlay_window_visible = $true
      always_on_top = $true
      proof_only = $true
      os_overlay_opened = $false
      updated_at = $Now
      message = 'Synthetic overlay runtime readback bound to the live proof process; no OS overlay window was opened.'
    })

  return [ordered]@{
    tray = $Tray
    hotkey = $Hotkey
    overlay = $Overlay
  }
}

function Get-DependencyById {
  param(
    [object[]]$Dependencies,
    [string]$Id
  )

  return @($Dependencies | Where-Object { [string](Get-PropertyValue -Payload $_ -Name 'id' -Default '') -eq $Id } | Select-Object -First 1)
}

$PowerShellPath = Get-PowerShellPath
$HostSupervisorPath = Join-Path $PSScriptRoot 'lens-host-supervisor.ps1'
$SurfaceRuntimePath = Join-Path $PSScriptRoot 'lens-stage6-surface-runtime.ps1'
$PlanPath = Join-Path $PSScriptRoot 'lens-persistent-supervision-plan.ps1'
$DataRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('francis-lens-surface-plan-consumption-proof-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null

$StartResult = $null
$SurfaceRuntimeStates = $null
$SurfaceRuntimeResult = $null
$PlanResult = $null
$StopResult = $null
$DataRootRemoved = $false

try {
  $StartResult = Invoke-JsonScript `
    -PowerShellPath $PowerShellPath `
    -ScriptPath $HostSupervisorPath `
    -ArgumentList @('-Mode', 'StartResident', '-DataDir', $DataRoot) `
    -DataRootEnv '' `
    -RunRoot $DataRoot `
    -Name 'start-resident'

  $SurfaceRuntimeStates = Write-ProofSurfaceRuntimeStates -DataRoot $DataRoot -ProcessId $PID

  $SurfaceRuntimeResult = Invoke-JsonScript `
    -PowerShellPath $PowerShellPath `
    -ScriptPath $SurfaceRuntimePath `
    -ArgumentList @('-Mode', 'Status', '-DataDir', $DataRoot) `
    -DataRootEnv '' `
    -RunRoot $DataRoot `
    -Name 'surface-runtime'

  $PlanResult = Invoke-JsonScript `
    -PowerShellPath $PowerShellPath `
    -ScriptPath $PlanPath `
    -ArgumentList @('-Mode', 'Status') `
    -DataRootEnv $DataRoot `
    -RunRoot $DataRoot `
    -Name 'persistent-supervision-plan'
} finally {
  try {
    $StopResult = Invoke-JsonScript `
      -PowerShellPath $PowerShellPath `
      -ScriptPath $HostSupervisorPath `
      -ArgumentList @('-Mode', 'StopResident', '-DataDir', $DataRoot) `
      -DataRootEnv '' `
      -RunRoot $DataRoot `
      -Name 'stop-resident'
  } catch {
    $StopResult = [ordered]@{
      exit_code = 1
      stdout = ''
      stderr = $_.Exception.Message
      payload = $null
      parse_error = ''
    }
  }

  if (Test-SafeTempPath -Path $DataRoot) {
    Remove-Item -LiteralPath $DataRoot -Recurse -Force -ErrorAction SilentlyContinue
    $DataRootRemoved = -not (Test-Path -LiteralPath $DataRoot)
  }
}

$StartPayload = Get-PropertyValue -Payload $StartResult -Name 'payload'
$SurfaceRuntimePayload = Get-PropertyValue -Payload $SurfaceRuntimeResult -Name 'payload'
$PlanPayload = Get-PropertyValue -Payload $PlanResult -Name 'payload'
$StopPayload = Get-PropertyValue -Payload $StopResult -Name 'payload'

$Dependencies = @(Get-PropertyValue -Payload $PlanPayload -Name 'enablement_dependency_readback' -Default @())
$ResidentDependency = @(Get-DependencyById -Dependencies $Dependencies -Id 'resident_host_process')
$TrayDependency = @(Get-DependencyById -Dependencies $Dependencies -Id 'tray_presence')
$HotkeyDependency = @(Get-DependencyById -Dependencies $Dependencies -Id 'global_hotkey_binding')
$OverlayDependency = @(Get-DependencyById -Dependencies $Dependencies -Id 'overlay_window')
$SummonDependency = @(Get-DependencyById -Dependencies $Dependencies -Id 'summon_binding')
$PlanHandoff = Get-PropertyValue -Payload $PlanPayload -Name 'first_missing_requirement_handoff'
$MissingRequired = @(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $PlanPayload -Name 'missing_required_before_enable' -Default @()))
$FirstMissing = [string](Get-PropertyValue -Payload $PlanPayload -Name 'first_missing_required_before_enable' -Default '')
$StartGovernance = Get-PropertyValue -Payload $StartPayload -Name 'governance'
$SurfaceGovernance = Get-PropertyValue -Payload $SurfaceRuntimePayload -Name 'governance'
$PlanGovernance = Get-PropertyValue -Payload $PlanPayload -Name 'governance'

$LiveResidentHostObserved = (
  [int](Get-PropertyValue -Payload $StartResult -Name 'exit_code' -Default 1) -eq 0 -and
  [string](Get-PropertyValue -Payload $StartPayload -Name 'status' -Default '') -in @('resident_supervision_started', 'resident_supervision_already_running') -and
  [bool](Get-PropertyValue -Payload $StartPayload -Name 'resident_host_process' -Default $false) -and
  [bool](Get-PropertyValue -Payload $StartPayload -Name 'resident_supervised_runtime' -Default $false)
)

$ResidentDependencyReady = (
  $ResidentDependency.Count -gt 0 -and
  [bool](Get-PropertyValue -Payload $ResidentDependency[0] -Name 'ready' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentDependency[0] -Name 'resident_supervised_runtime' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentDependency[0] -Name 'process_alive' -Default $false)
)
$TrayDependencyReady = (
  $TrayDependency.Count -gt 0 -and
  [bool](Get-PropertyValue -Payload $TrayDependency[0] -Name 'ready' -Default $false) -and
  [string](Get-PropertyValue -Payload $TrayDependency[0] -Name 'tray_presence_source' -Default '') -eq 'live_runtime_readback' -and
  [bool](Get-PropertyValue -Payload $TrayDependency[0] -Name 'tray_runtime_ready' -Default $false)
)
$HotkeyDependencyReady = (
  $HotkeyDependency.Count -gt 0 -and
  [bool](Get-PropertyValue -Payload $HotkeyDependency[0] -Name 'ready' -Default $false) -and
  [string](Get-PropertyValue -Payload $HotkeyDependency[0] -Name 'global_hotkey_source' -Default '') -eq 'live_runtime_readback' -and
  [bool](Get-PropertyValue -Payload $HotkeyDependency[0] -Name 'hotkey_runtime_ready' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HotkeyDependency[0] -Name 'hotkey_runtime_bound' -Default $false)
)
$OverlayDependencyReady = (
  $OverlayDependency.Count -gt 0 -and
  [bool](Get-PropertyValue -Payload $OverlayDependency[0] -Name 'ready' -Default $false) -and
  [string](Get-PropertyValue -Payload $OverlayDependency[0] -Name 'overlay_window_source' -Default '') -eq 'live_runtime_readback' -and
  [bool](Get-PropertyValue -Payload $OverlayDependency[0] -Name 'overlay_runtime_ready' -Default $false) -and
  [bool](Get-PropertyValue -Payload $OverlayDependency[0] -Name 'overlay_runtime_window_visible' -Default $false) -and
  [bool](Get-PropertyValue -Payload $OverlayDependency[0] -Name 'overlay_runtime_always_on_top' -Default $false)
)
$SummonBindingStillBlocked = (
  $SummonDependency.Count -gt 0 -and
  -not [bool](Get-PropertyValue -Payload $SummonDependency[0] -Name 'ready' -Default $true) -and
  [string](Get-PropertyValue -Payload $SummonDependency[0] -Name 'blocker' -Default '') -eq 'summon_binding_missing' -and
  [string](Get-PropertyValue -Payload $SummonDependency[0] -Name 'requirement_state' -Default '') -eq 'disabled_pending_authority'
)

$SurfaceRuntimeObserved = (
  [int](Get-PropertyValue -Payload $SurfaceRuntimeResult -Name 'exit_code' -Default 1) -eq 0 -and
  [string](Get-PropertyValue -Payload $SurfaceRuntimePayload -Name 'status' -Default '') -eq 'running' -and
  [bool](Get-PropertyValue -Payload $SurfaceRuntimePayload -Name 'ready' -Default $false) -and
  [int](Get-PropertyValue -Payload $SurfaceRuntimePayload -Name 'ready_total' -Default 0) -eq 3
)

$PlanConsumedSurfaceRuntime = (
  [int](Get-PropertyValue -Payload $PlanResult -Name 'exit_code' -Default 1) -eq 0 -and
  [string](Get-PropertyValue -Payload $PlanPayload -Name 'status' -Default '') -eq 'blocked' -and
  $ResidentDependencyReady -and
  $TrayDependencyReady -and
  $HotkeyDependencyReady -and
  $OverlayDependencyReady -and
  $SummonBindingStillBlocked -and
  $FirstMissing -eq 'summon_binding' -and
  @($MissingRequired).Count -eq 1 -and
  $MissingRequired -contains 'summon_binding'
)

$StopObserved = (
  [int](Get-PropertyValue -Payload $StopResult -Name 'exit_code' -Default 1) -eq 0 -and
  [string](Get-PropertyValue -Payload $StopPayload -Name 'status' -Default '') -eq 'resident_supervision_stopped' -and
  -not [bool](Get-PropertyValue -Payload $StopPayload -Name 'resident_host_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $StopPayload -Name 'resident_supervised_runtime' -Default $true)
)

$SideEffectsBounded = (
  [bool](Get-PropertyValue -Payload $StartGovernance -Name 'local_process_launch_authority' -Default $false) -and
  [bool](Get-PropertyValue -Payload $StartGovernance -Name 'process_supervision_authority' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $StartGovernance -Name 'service_install_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $StartGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $StartGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $StartGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $StartGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $StartGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $StartGovernance -Name 'resident_claim_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $StartGovernance -Name 'memory_write' -Default $true) -and
  [bool](Get-PropertyValue -Payload $SurfaceGovernance -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SurfaceGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SurfaceGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SurfaceGovernance -Name 'overlay_control_authority' -Default $true) -and
  [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'read_only_contract' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'mutation_authority_granted' -Default $true)
)

$ProofPassed = $LiveResidentHostObserved -and $SurfaceRuntimeObserved -and $PlanConsumedSurfaceRuntime -and $StopObserved -and $SideEffectsBounded -and $DataRootRemoved
$NextGap = if ($PlanConsumedSurfaceRuntime) { 'summon_binding' } elseif ($HotkeyDependencyReady) { 'overlay_window' } elseif ($TrayDependencyReady) { 'global_hotkey_binding' } else { 'resident_host_process' }
$RecommendedSlice = if ($PlanConsumedSurfaceRuntime) {
  'resolve_summon_binding_before_persistent_supervision_enablement'
} else {
  'debug_coordinated_surface_runtime_plan_consumption_readback'
}

$Payload = [ordered]@{
  kind = 'lens.surface_runtime.plan_consumption_proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  ok = $ProofPassed
  mode = $Mode.ToLowerInvariant()
  stage = 'Stage 6 / Lens MVP'
  stage_state = 'active'
  ready_to_close = $false
  data_root_removed = $DataRootRemoved
  live_resident_host_observed = $LiveResidentHostObserved
  coordinated_surface_runtime_readback_observed = $SurfaceRuntimeObserved
  persistent_supervision_plan_consumed_surface_runtime = $PlanConsumedSurfaceRuntime
  resident_dependency_ready = $ResidentDependencyReady
  tray_dependency_ready = $TrayDependencyReady
  global_hotkey_dependency_ready = $HotkeyDependencyReady
  overlay_dependency_ready = $OverlayDependencyReady
  summon_binding_still_blocked = $SummonBindingStillBlocked
  first_missing_required_before_enable = $FirstMissing
  missing_required_before_enable = $MissingRequired
  next_smallest_truthful_gap = $NextGap
  recommended_next_slice = $RecommendedSlice
  stop_observed = $StopObserved
  side_effects_bounded = $SideEffectsBounded
  proof_scope = [ordered]@{
    synthetic_tray_runtime_readback = $true
    synthetic_hotkey_runtime_readback = $true
    synthetic_overlay_runtime_readback = $true
    os_tray_registered = $false
    global_hotkey_registered = $false
    overlay_opened = $false
    persistent_supervision_enabled = $false
    summon_binding_enabled = $false
  }
  start_resident = [ordered]@{
    exit_code = [int](Get-PropertyValue -Payload $StartResult -Name 'exit_code' -Default 1)
    status = [string](Get-PropertyValue -Payload $StartPayload -Name 'status' -Default '')
    resident_host_process = [bool](Get-PropertyValue -Payload $StartPayload -Name 'resident_host_process' -Default $false)
    resident_supervised_runtime = [bool](Get-PropertyValue -Payload $StartPayload -Name 'resident_supervised_runtime' -Default $false)
    supervisor_pid = [int](Get-PropertyValue -Payload $StartPayload -Name 'supervisor_pid' -Default 0)
    host_pid = [int](Get-PropertyValue -Payload (Get-PropertyValue -Payload $StartPayload -Name 'host_readback') -Name 'pid' -Default 0)
    parse_error = [string](Get-PropertyValue -Payload $StartResult -Name 'parse_error' -Default '')
    stderr = [string](Get-PropertyValue -Payload $StartResult -Name 'stderr' -Default '')
  }
  surface_runtime = [ordered]@{
    exit_code = [int](Get-PropertyValue -Payload $SurfaceRuntimeResult -Name 'exit_code' -Default 1)
    status = [string](Get-PropertyValue -Payload $SurfaceRuntimePayload -Name 'status' -Default '')
    ready = [bool](Get-PropertyValue -Payload $SurfaceRuntimePayload -Name 'ready' -Default $false)
    ready_total = [int](Get-PropertyValue -Payload $SurfaceRuntimePayload -Name 'ready_total' -Default 0)
    component_total = [int](Get-PropertyValue -Payload $SurfaceRuntimePayload -Name 'component_total' -Default 0)
    parse_error = [string](Get-PropertyValue -Payload $SurfaceRuntimeResult -Name 'parse_error' -Default '')
    stderr = [string](Get-PropertyValue -Payload $SurfaceRuntimeResult -Name 'stderr' -Default '')
  }
  persistent_supervision_plan = [ordered]@{
    exit_code = [int](Get-PropertyValue -Payload $PlanResult -Name 'exit_code' -Default 1)
    status = [string](Get-PropertyValue -Payload $PlanPayload -Name 'status' -Default '')
    required_before_enable_ready = [bool](Get-PropertyValue -Payload $PlanPayload -Name 'required_before_enable_ready' -Default $false)
    first_missing_required_before_enable = $FirstMissing
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $PlanPayload -Name 'next_smallest_truthful_gap' -Default '')
    parse_error = [string](Get-PropertyValue -Payload $PlanResult -Name 'parse_error' -Default '')
    stderr = [string](Get-PropertyValue -Payload $PlanResult -Name 'stderr' -Default '')
  }
  resident_dependency = if ($ResidentDependency.Count -gt 0) { $ResidentDependency[0] } else { $null }
  tray_dependency = if ($TrayDependency.Count -gt 0) { $TrayDependency[0] } else { $null }
  global_hotkey_dependency = if ($HotkeyDependency.Count -gt 0) { $HotkeyDependency[0] } else { $null }
  overlay_dependency = if ($OverlayDependency.Count -gt 0) { $OverlayDependency[0] } else { $null }
  summon_dependency = if ($SummonDependency.Count -gt 0) { $SummonDependency[0] } else { $null }
  plan_first_missing_requirement_handoff = $PlanHandoff
  stop_resident = [ordered]@{
    exit_code = [int](Get-PropertyValue -Payload $StopResult -Name 'exit_code' -Default 1)
    status = [string](Get-PropertyValue -Payload $StopPayload -Name 'status' -Default '')
    resident_host_process = [bool](Get-PropertyValue -Payload $StopPayload -Name 'resident_host_process' -Default $true)
    resident_supervised_runtime = [bool](Get-PropertyValue -Payload $StopPayload -Name 'resident_supervised_runtime' -Default $true)
    parse_error = [string](Get-PropertyValue -Payload $StopResult -Name 'parse_error' -Default '')
    stderr = [string](Get-PropertyValue -Payload $StopResult -Name 'stderr' -Default '')
  }
  governance = [ordered]@{
    diagnostic_only = $false
    read_only_contract = $false
    temporary_runtime_state_write = $true
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    local_process_launch_authority = $true
    process_supervision_authority = $true
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    tray_registration_authority = $false
    tray_icon_authority = $false
    hotkey_registration_authority = $false
    overlay_control_authority = $false
    window_management_authority = $false
    summon_authority = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    mutation_authority_granted = $false
  }
}

$Payload | ConvertTo-Json -Depth 12
if ($ProofPassed) {
  exit 0
}
exit 1
