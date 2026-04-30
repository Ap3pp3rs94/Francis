[CmdletBinding()]
param(
  [ValidateSet('Status', 'Foreground', 'Launch')]
  [string]$Mode = 'Status',

  [ValidateRange(0, 30)]
  [int]$RunSeconds = 0
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$modeName = $Mode.ToLowerInvariant()
$ServiceConfigPath = Join-Path $RepoRoot 'config\runtime\services\lens-host.json'
$ServiceConfigExists = Test-Path -LiteralPath $ServiceConfigPath -PathType Leaf
$ServiceName = 'Francis-LensHost'
if ($ServiceConfigExists) {
  try {
    $ServiceConfigPayload = Get-Content -LiteralPath $ServiceConfigPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    $ServiceNameProperty = $ServiceConfigPayload.PSObject.Properties['service_name']
    if ($null -ne $ServiceNameProperty -and -not [string]::IsNullOrWhiteSpace([string]$ServiceNameProperty.Value)) {
      $ServiceName = [string]$ServiceNameProperty.Value
    }
  } catch {
    $ServiceName = 'Francis-LensHost'
  }
}

function Get-DataRoot {
  $Configured = [string]$env:FRANCIS_DATA_DIR
  if (-not [string]::IsNullOrWhiteSpace($Configured)) {
    return $Configured
  }
  return (Join-Path $RepoRoot 'data')
}

function Write-JsonFile {
  param(
    [string]$Path,
    [object]$Payload
  )

  $Parent = Split-Path -Parent $Path
  if (-not [string]::IsNullOrWhiteSpace($Parent)) {
    New-Item -ItemType Directory -Force -Path $Parent | Out-Null
  }
  $FileName = [System.IO.Path]::GetFileName($Path)
  $TempPath = Join-Path $Parent ('.' + $FileName + '.' + [guid]::NewGuid().ToString('N') + '.tmp')
  try {
    $Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $TempPath -Encoding UTF8
    Move-Item -LiteralPath $TempPath -Destination $Path -Force
  } finally {
    Remove-Item -LiteralPath $TempPath -Force -ErrorAction SilentlyContinue
  }
}

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

function Quote-ProcessArgument {
  param([string]$Value)

  if ($null -eq $Value) {
    return '""'
  }
  return '"' + ($Value -replace '"', '\"') + '"'
}

function Quote-PowerShellString {
  param([string]$Value)

  if ($null -eq $Value) {
    return "''"
  }
  return "'" + ($Value -replace "'", "''") + "'"
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

function Get-PropertyValue {
  param(
    [object]$Payload,
    [string]$Name,
    [object]$Default = $null
  )

  if ($null -eq $Payload) {
    return $Default
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) {
    return $Default
  }
  return $Property.Value
}

function Wait-ForRuntimeState {
  param(
    [string]$StatePath,
    [string]$Status,
    [int]$TimeoutSeconds = 10
  )

  $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $Deadline) {
    $Payload = Read-JsonFile -Path $StatePath
    if ($null -ne $Payload -and [string](Get-PropertyValue -Payload $Payload -Name 'status' -Default '') -eq $Status) {
      return $Payload
    }
    Start-Sleep -Milliseconds 100
  }
  return (Read-JsonFile -Path $StatePath)
}

$DataRoot = Get-DataRoot
$RuntimeDir = Join-Path $DataRoot 'runtime\lens-host'
$ProcessStatePath = Join-Path $RuntimeDir 'status.json'
$PidPath = Join-Path $RuntimeDir 'lens-host.pid'
$ProcessStateExists = Test-Path -LiteralPath $ProcessStatePath -PathType Leaf
$ProcessStateStatus = ''
$ProcessStateUpdatedAt = ''
if ($ProcessStateExists) {
  try {
    $ProcessStatePayload = Get-Content -LiteralPath $ProcessStatePath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    $StatusProperty = $ProcessStatePayload.PSObject.Properties['status']
    if ($null -ne $StatusProperty) {
      $ProcessStateStatus = [string]$StatusProperty.Value
    }
    $UpdatedProperty = $ProcessStatePayload.PSObject.Properties['updated_at']
    if ($null -ne $UpdatedProperty) {
      $ProcessStateUpdatedAt = [string]$UpdatedProperty.Value
    }
  } catch {
    $ProcessStateStatus = 'unreadable'
  }
}
$PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf
$PidValue = 0
if ($PidPresent) {
  try {
    $PidValue = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
  } catch {
    $PidValue = 0
  }
}
$ProcessAlive = $false
if ($PidValue -gt 0) {
  try {
    Get-Process -Id $PidValue -ErrorAction Stop | Out-Null
    $ProcessAlive = $true
  } catch {
    $ProcessAlive = $false
  }
}
$ProcessReadbackStatus = if ($ProcessAlive) { 'process_observed' } elseif ($PidPresent -or $ProcessStateExists) { 'state_present_process_not_running' } else { 'missing' }
$ProcessBlockedReason = if ($ProcessAlive) { 'resident_host_not_supervised' } else { 'resident_host_process_missing' }
$Blockers = @(
  'tray_host_missing',
  'global_hotkey_binding_missing',
  'overlay_window_missing',
  'summon_binding_missing'
)
if (-not $ProcessAlive) {
  $Blockers = @('resident_host_process_missing') + $Blockers
}
$Blockers = @('lens_host_runtime_not_implemented') + $Blockers
if (-not $ServiceConfigExists) {
  $Blockers = @('lens_host_service_config_missing') + $Blockers
}

$WindowsServiceSupported = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)
$ServiceInstalled = $false
$ServiceStatus = if ($WindowsServiceSupported) { 'not_installed' } else { 'unsupported_platform' }
$ServiceStartType = ''
$ServiceState = ''
$ServicePathName = ''
$ServiceAccount = ''
$ServiceReadbackError = ''
if ($WindowsServiceSupported) {
  try {
    $Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($null -ne $Service) {
      $ServiceInstalled = $true
      $ServiceStatus = ([string]$Service.Status).ToLowerInvariant()
      $FilterServiceName = $ServiceName.Replace("'", "''")
      $CimService = $null
      try {
        $CimService = Get-CimInstance Win32_Service -Filter "Name='$FilterServiceName'" -ErrorAction SilentlyContinue
      } catch {
        $CimService = $null
      }
      if ($null -ne $CimService) {
        $ServiceStartType = [string]$CimService.StartMode
        $ServiceState = [string]$CimService.State
        $ServicePathName = [string]$CimService.PathName
        $ServiceAccount = [string]$CimService.StartName
      }
    }
  } catch {
    $ServiceStatus = 'unavailable'
    $ServiceReadbackError = [string]$_.Exception.Message
  }
}
$ServiceBlockedReason = if ($ServiceInstalled) { 'lens_host_runtime_not_implemented' } elseif ($WindowsServiceSupported) { 'lens_host_service_not_installed' } else { 'windows_service_readback_unavailable' }

$payload = [ordered]@{
  ok = $true
  kind = 'lens.host.status_runner'
  status = 'status_only'
  mode = $modeName
  repo_root = $RepoRoot
  service_config_path = 'config/runtime/services/lens-host.json'
  service_config_exists = $ServiceConfigExists
  service_readback = [ordered]@{
    status = $ServiceStatus
    readback_ready = $true
    service_name = $ServiceName
    installed = $ServiceInstalled
    windows_service = $WindowsServiceSupported
    start_type = $ServiceStartType
    state = $ServiceState
    path_name = $ServicePathName
    account = $ServiceAccount
    error = $ServiceReadbackError
    install_supported = $false
    start_supported = $false
    stop_supported = $false
    restart_supported = $false
    install_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    blocked_reason = $ServiceBlockedReason
  }
  process_readback = [ordered]@{
    status = $ProcessReadbackStatus
    readback_ready = $true
    runtime_state_path = 'data/runtime/lens-host/status.json'
    state_exists = $ProcessStateExists
    state_status = $ProcessStateStatus
    state_updated_at = $ProcessStateUpdatedAt
    pid_path = 'data/runtime/lens-host/lens-host.pid'
    pid_present = $PidPresent
    pid = $PidValue
    process_alive = $ProcessAlive
    supervision_enabled = $false
    start_supported = $false
    stop_supported = $false
    restart_supported = $false
    supervision_authority = $false
    blocked_reason = $ProcessBlockedReason
  }
  route = '/lens/host'
  manifest_route = '/lens/host/manifest'
  launch_supported = $false
  foreground_supported = $true
  foreground_session = $ProcessAlive
  foreground_run_seconds = $RunSeconds
  resident = $false
  process_supervision = $false
  tray_presence = $false
  global_hotkey = $false
  always_on_top_overlay = $false
  overlay_window = $false
  command_palette_binding = $false
  summon_anywhere = $false
  blockers = $Blockers
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
    service_install_authority = $false
    service_control_authority = $false
    runtime_state_write = $Mode -eq 'Foreground'
    foreground_session_authority = $Mode -eq 'Foreground'
    mutation_authority_granted = $false
  }
}

if ($Mode -eq 'Status') {
  $payload | ConvertTo-Json -Depth 8
  exit 0
}

if ($Mode -eq 'Foreground') {
  $StartedAt = (Get-Date).ToUniversalTime().ToString('o')
  $RunningGovernance = [ordered]@{
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    runtime_state_write = $true
    foreground_session_authority = $true
    mutation_authority_granted = $false
  }
  $RunningState = [ordered]@{
    kind = 'lens.host.runtime_state'
    status = 'foreground_running'
    mode = 'foreground'
    pid = $PID
    process_alive = $true
    resident = $false
    service_managed = $false
    tray_presence = $false
    global_hotkey = $false
    overlay_window = $false
    summon_anywhere = $false
    started_at = $StartedAt
    updated_at = $StartedAt
    bounded_run_seconds = $RunSeconds
    governance = $RunningGovernance
  }
  Write-JsonFile -Path $ProcessStatePath -Payload $RunningState
  New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
  Set-Content -LiteralPath $PidPath -Value ([string]$PID) -Encoding ASCII

  if ($RunSeconds -gt 0) {
    Start-Sleep -Seconds $RunSeconds
  }

  $StoppedAt = (Get-Date).ToUniversalTime().ToString('o')
  $StoppedState = [ordered]@{
    kind = 'lens.host.runtime_state'
    status = 'foreground_stopped'
    mode = 'foreground'
    pid = $PID
    process_alive = $false
    resident = $false
    service_managed = $false
    tray_presence = $false
    global_hotkey = $false
    overlay_window = $false
    summon_anywhere = $false
    started_at = $StartedAt
    updated_at = $StoppedAt
    bounded_run_seconds = $RunSeconds
    stop_reason = 'bounded_foreground_session_completed'
    governance = $RunningGovernance
  }
  Write-JsonFile -Path $ProcessStatePath -Payload $StoppedState
  Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue

  $payload.status = 'foreground_completed'
  $payload.ok = $true
  $payload.process_readback.status = 'state_present_process_not_running'
  $payload.process_readback.state_exists = $true
  $payload.process_readback.state_status = 'foreground_stopped'
  $payload.process_readback.state_updated_at = $StoppedAt
  $payload.process_readback.pid_present = $false
  $payload.process_readback.pid = 0
  $payload.process_readback.process_alive = $false
  $payload.foreground_supported = $true
  $payload.foreground_session = $false
  $payload.foreground_run_seconds = $RunSeconds
  $payload.message = 'Lens host foreground status session completed; resident service, tray, summon, and overlay remain unimplemented.'
  $payload | ConvertTo-Json -Depth 8
  exit 0
}

$LaunchRunSeconds = if ($RunSeconds -gt 0) { $RunSeconds } else { 10 }
if ($Mode -eq 'Launch') {
  $PowerShellPath = Get-PowerShellPath
  $HostScriptPath = [string]$MyInvocation.MyCommand.Path
  $LaunchStdoutPath = Join-Path $RuntimeDir 'launch-stdout.json'
  $LaunchStderrPath = Join-Path $RuntimeDir 'launch-stderr.txt'
  New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
  Remove-Item -LiteralPath $LaunchStdoutPath -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $LaunchStderrPath -Force -ErrorAction SilentlyContinue

  $LaunchStarted = $false
  $LaunchPid = 0
  $RunningState = $null
  if (-not [string]::IsNullOrWhiteSpace($PowerShellPath)) {
    $ChildCommand = (
      '$env:FRANCIS_DATA_DIR = ' +
      (Quote-PowerShellString -Value $DataRoot) +
      '; & ' +
      (Quote-PowerShellString -Value $HostScriptPath) +
      ' -Mode Foreground -RunSeconds ' +
      [string]$LaunchRunSeconds +
      ' > ' +
      (Quote-PowerShellString -Value $LaunchStdoutPath) +
      ' 2> ' +
      (Quote-PowerShellString -Value $LaunchStderrPath)
    )
    $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $StartInfo.FileName = $PowerShellPath
    $StartInfo.Arguments = '-NoProfile -ExecutionPolicy Bypass -Command ' + (Quote-ProcessArgument -Value $ChildCommand)
    $StartInfo.WorkingDirectory = $RepoRoot
    $StartInfo.UseShellExecute = $false
    $StartInfo.CreateNoWindow = $true
    $StartInfo.RedirectStandardOutput = $false
    $StartInfo.RedirectStandardError = $false

    $LaunchProcess = [System.Diagnostics.Process]::new()
    $LaunchProcess.StartInfo = $StartInfo
    $LaunchStarted = $LaunchProcess.Start()
    if ($LaunchStarted) {
      $LaunchPid = [int]$LaunchProcess.Id
      $LaunchObservationTimeout = [Math]::Max(10, $LaunchRunSeconds + 10)
      $RunningState = Wait-ForRuntimeState -StatePath $ProcessStatePath -Status 'foreground_running' -TimeoutSeconds $LaunchObservationTimeout
    }
  }

  $ObservedPid = [int](Get-PropertyValue -Payload $RunningState -Name 'pid' -Default 0)
  $LaunchObserved = (
    $LaunchStarted -and
    [string](Get-PropertyValue -Payload $RunningState -Name 'status' -Default '') -eq 'foreground_running' -and
    [bool](Get-PropertyValue -Payload $RunningState -Name 'process_alive' -Default $false) -and
    $ObservedPid -gt 0
  )
  $ObservedAt = (Get-Date).ToUniversalTime().ToString('o')

  $payload.ok = $LaunchObserved
  $payload.status = if ($LaunchObserved) { 'launch_started' } else { 'launch_unverified' }
  $payload.mode = 'launch'
  $payload.launch_supported = $true
  $payload.launch_authority = $false
  $payload.diagnostic_launch_authority = $LaunchObserved
  $payload.foreground_supported = $true
  $payload.foreground_session = $LaunchObserved
  $payload.foreground_run_seconds = $LaunchRunSeconds
  $payload.process_readback.status = if ($LaunchObserved) { 'process_observed' } else { 'missing' }
  $payload.process_readback.state_exists = $null -ne $RunningState
  $payload.process_readback.state_status = [string](Get-PropertyValue -Payload $RunningState -Name 'status' -Default '')
  $payload.process_readback.state_updated_at = [string](Get-PropertyValue -Payload $RunningState -Name 'updated_at' -Default $ObservedAt)
  $payload.process_readback.pid_present = Test-Path -LiteralPath $PidPath -PathType Leaf
  $payload.process_readback.pid = $ObservedPid
  $payload.process_readback.process_alive = $LaunchObserved
  $payload.process_readback.blocked_reason = if ($LaunchObserved) { 'resident_host_not_supervised' } else { 'resident_host_process_missing' }
  $payload.blockers = if ($LaunchObserved) {
    @(
      'lens_host_runtime_not_implemented',
      'resident_host_process_not_supervised',
      'tray_host_missing',
      'global_hotkey_binding_missing',
      'overlay_window_missing',
      'summon_binding_missing'
    )
  } else {
    $Blockers
  }
  $payload.launch = [ordered]@{
    status = if ($LaunchObserved) { 'started_observed' } else { 'not_observed' }
    launcher_pid = $LaunchPid
    observed_pid = $ObservedPid
    run_seconds = $LaunchRunSeconds
    runtime_state_path = 'data/runtime/lens-host/status.json'
    pid_path = 'data/runtime/lens-host/lens-host.pid'
    stdout_path = 'data/runtime/lens-host/launch-stdout.json'
    stderr_path = 'data/runtime/lens-host/launch-stderr.txt'
    observed_at = $ObservedAt
    stop_mode = 'bounded_self_stop'
  }
  $payload.governance.diagnostic_only = $true
  $payload.governance.bounded_process_launch = $true
  $payload.governance.temporary_runtime_state_write = $true
  $payload.governance.product_execution_authority = $false
  $payload.governance.local_process_launch_authority = $LaunchObserved
  $payload.governance.api_local_process_launch_authority = $false
  $payload.governance.foreground_session_authority = $true
  $payload.governance.mutation_authority_granted = $false
  $payload.message = if ($LaunchObserved) {
    'Bounded Lens host foreground process was launched and observed; it self-stops after the requested run window and does not provide service, tray, summon, or overlay runtime.'
  } else {
    'Bounded Lens host launch could not be observed.'
  }
  $payload | ConvertTo-Json -Depth 8
  if ($LaunchObserved) {
    exit 0
  }
  exit 1
}

$payload.ok = $false
$payload.status = 'refused'
$payload.error = 'lens_host_runtime_not_implemented'
$payload.message = 'Lens host foreground/runtime launch is not implemented; this runner only reports status.'
$payload | ConvertTo-Json -Depth 8
exit 2
