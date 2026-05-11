[CmdletBinding()]
param(
  [ValidateSet('Status', 'Start', 'Stop')]
  [string]$Mode = 'Status',

  [ValidateRange(5, 60)]
  [int]$LeaseSeconds = 30,

  [ValidateRange(1, 30)]
  [int]$StartupTimeoutSeconds = 10,

  [string]$DataDir = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

function Get-DataRoot {
  if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
    return [System.IO.Path]::GetFullPath($DataDir)
  }
  $Configured = [string]$env:FRANCIS_DATA_DIR
  if (-not [string]::IsNullOrWhiteSpace($Configured)) {
    return [System.IO.Path]::GetFullPath($Configured)
  }
  return (Join-Path $RepoRoot 'data')
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

function Get-PropertyValue {
  param(
    [AllowNull()]
    [object]$Payload,
    [string]$Name,
    [AllowNull()]
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

function Quote-PowerShellString {
  param([string]$Value)

  if ($null -eq $Value) {
    return "''"
  }
  return "'" + ($Value -replace "'", "''") + "'"
}

function Get-PidValue {
  param([string]$Path)

  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return 0
  }
  try {
    return [int]((Get-Content -LiteralPath $Path -Raw -ErrorAction Stop).Trim())
  } catch {
    return 0
  }
}

function Test-ProcessAlive {
  param([int]$ProcessId)

  if ($ProcessId -le 0) {
    return $false
  }
  try {
    Get-Process -Id $ProcessId -ErrorAction Stop | Out-Null
    return $true
  } catch {
    return $false
  }
}

function Get-ResidentState {
  param(
    [string]$StatePath,
    [string]$PidPath
  )

  $StatePayload = Read-JsonFile -Path $StatePath
  $PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf
  $PidValue = Get-PidValue -Path $PidPath
  $StateKind = [string](Get-PropertyValue -Payload $StatePayload -Name 'kind' -Default '')
  $StateStatus = [string](Get-PropertyValue -Payload $StatePayload -Name 'status' -Default '')
  $StateMode = [string](Get-PropertyValue -Payload $StatePayload -Name 'mode' -Default '')
  $StatePid = [int](Get-PropertyValue -Payload $StatePayload -Name 'pid' -Default 0)
  $StateClaimsResident = (
    $StateKind -eq 'lens.host.runtime_state' -and
    $StateStatus -eq 'resident_running' -and
    $StateMode -eq 'resident' -and
    $StatePid -gt 0 -and
    $StatePid -eq $PidValue
  )
  $ProcessAlive = $StateClaimsResident -and (Test-ProcessAlive -ProcessId $PidValue)
  return [ordered]@{
    state_exists = $null -ne $StatePayload
    state_kind = $StateKind
    state_status = $StateStatus
    state_mode = $StateMode
    state_pid = $StatePid
    state_pid_matches_pid_file = $StatePid -gt 0 -and $PidValue -gt 0 -and $StatePid -eq $PidValue
    state_updated_at = [string](Get-PropertyValue -Payload $StatePayload -Name 'updated_at' -Default '')
    state_started_at = [string](Get-PropertyValue -Payload $StatePayload -Name 'started_at' -Default '')
    heartbeat_count = [int](Get-PropertyValue -Payload $StatePayload -Name 'heartbeat_count' -Default 0)
    last_heartbeat_at = [string](Get-PropertyValue -Payload $StatePayload -Name 'last_heartbeat_at' -Default '')
    pid_present = $PidPresent
    pid = $PidValue
    process_alive = $ProcessAlive
    resident_session_active = $ProcessAlive
  }
}

function Wait-ForResidentRunning {
  param(
    [string]$StatePath,
    [string]$PidPath,
    [int]$TimeoutSeconds
  )

  $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $Latest = Get-ResidentState -StatePath $StatePath -PidPath $PidPath
  while ((Get-Date) -lt $Deadline) {
    $Latest = Get-ResidentState -StatePath $StatePath -PidPath $PidPath
    if ([bool](Get-PropertyValue -Payload $Latest -Name 'resident_session_active' -Default $false)) {
      return $Latest
    }
    Start-Sleep -Milliseconds 100
  }
  return $Latest
}

function New-Governance {
  param(
    [bool]$ReadOnlyContract,
    [bool]$LocalProcessLaunchAuthority,
    [bool]$ProcessStopAuthority,
    [bool]$RuntimeStateWrite,
    [bool]$MutationAuthority
  )

  return [ordered]@{
    read_only_contract = $ReadOnlyContract
    local_process_launch_authority = $LocalProcessLaunchAuthority
    process_stop_authority = $ProcessStopAuthority
    runtime_state_write = $RuntimeStateWrite
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    service_install_authority = $false
    service_control_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    tray_registration_authority = $false
    hotkey_registration_authority = $false
    overlay_control_authority = $false
    summon_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $MutationAuthority
  }
}

function New-BasePayload {
  param(
    [object]$ProcessReadback,
    [object]$Governance
  )

  $ResidentActive = [bool](Get-PropertyValue -Payload $ProcessReadback -Name 'resident_session_active' -Default $false)
  $Blockers = @(
    'resident_supervision_not_persistent',
    'tray_host_missing',
    'global_hotkey_binding_missing',
    'overlay_window_missing',
    'summon_binding_missing'
  )
  if (-not $ResidentActive) {
    $Blockers = @('resident_host_process_missing') + $Blockers
  }
  return [ordered]@{
    ok = $true
    kind = 'lens.host.resident_session'
    status = if ($ResidentActive) { 'resident_session_active' } elseif ([bool](Get-PropertyValue -Payload $ProcessReadback -Name 'state_exists' -Default $false)) { 'resident_session_stopped' } else { 'missing' }
    mode = $Mode.ToLowerInvariant()
    repo_root = $RepoRoot
    data_root = $DataRoot
    lease_seconds = $LeaseSeconds
    host_script = 'scripts/lens-host.ps1'
    host_mode = 'Resident'
    runtime_state_path = 'data/runtime/lens-host/status.json'
    pid_path = 'data/runtime/lens-host/lens-host.pid'
    session_state_path = 'data/runtime/lens-host-resident-session/status.json'
    stdout_path = 'data/runtime/lens-host-resident-session/stdout.json'
    stderr_path = 'data/runtime/lens-host-resident-session/stderr.txt'
    resident_session_active = $ResidentActive
    resident_runtime_candidate = $ResidentActive
    resident_supervised_runtime = $false
    resident_claim_allowed = $false
    process_readback = $ProcessReadback
    blockers = @($Blockers | Sort-Object -Unique)
    next_smallest_truthful_gap = if ($ResidentActive) { 'resident_supervision_not_persistent' } else { 'resident_host_process_missing' }
    governance = $Governance
    message = 'Lens resident session readback is bounded to a leased local host process; service install/control, tray, hotkey, overlay, summon, memory write, and resident claim remain blocked.'
  }
}

$ModeName = $Mode.ToLowerInvariant()
$DataRoot = Get-DataRoot
$HostScriptPath = Join-Path $PSScriptRoot 'lens-host.ps1'
$HostRuntimeDir = Join-Path $DataRoot 'runtime\lens-host'
$SessionRuntimeDir = Join-Path $DataRoot 'runtime\lens-host-resident-session'
$HostStatePath = Join-Path $HostRuntimeDir 'status.json'
$HostPidPath = Join-Path $HostRuntimeDir 'lens-host.pid'
$SessionStatePath = Join-Path $SessionRuntimeDir 'status.json'
$StdoutPath = Join-Path $SessionRuntimeDir 'stdout.json'
$StderrPath = Join-Path $SessionRuntimeDir 'stderr.txt'

$InitialState = Get-ResidentState -StatePath $HostStatePath -PidPath $HostPidPath

if ($Mode -eq 'Status') {
  $Payload = New-BasePayload -ProcessReadback $InitialState -Governance (
    New-Governance -ReadOnlyContract $true -LocalProcessLaunchAuthority $false -ProcessStopAuthority $false -RuntimeStateWrite $false -MutationAuthority $false
  )
  $Payload | ConvertTo-Json -Depth 8
  exit 0
}

if ($Mode -eq 'Start') {
  $Governance = New-Governance -ReadOnlyContract $false -LocalProcessLaunchAuthority $true -ProcessStopAuthority $false -RuntimeStateWrite $true -MutationAuthority $true
  if ([bool](Get-PropertyValue -Payload $InitialState -Name 'resident_session_active' -Default $false)) {
    $Payload = New-BasePayload -ProcessReadback $InitialState -Governance $Governance
    $Payload.status = 'resident_session_already_active'
    $Payload.applied = $false
    $Payload.started = $false
    $Payload | ConvertTo-Json -Depth 8
    exit 0
  }

  $PowerShellPath = Get-PowerShellPath
  if ([string]::IsNullOrWhiteSpace($PowerShellPath) -or -not (Test-Path -LiteralPath $HostScriptPath -PathType Leaf)) {
    $Payload = New-BasePayload -ProcessReadback $InitialState -Governance $Governance
    $Payload.ok = $false
    $Payload.status = 'host_script_unavailable'
    $Payload.applied = $false
    $Payload.started = $false
    $Payload.blockers = @('host_script_unavailable') + @($Payload.blockers)
    $Payload | ConvertTo-Json -Depth 8
    exit 1
  }

  New-Item -ItemType Directory -Force -Path $SessionRuntimeDir | Out-Null
  Remove-Item -LiteralPath $StdoutPath -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $StderrPath -Force -ErrorAction SilentlyContinue

  $StartedAt = (Get-Date).ToUniversalTime().ToString('o')
  $Command = (
    '$env:FRANCIS_DATA_DIR = ' +
    (Quote-PowerShellString -Value $DataRoot) +
    '; & ' +
    (Quote-PowerShellString -Value $HostScriptPath) +
    ' -Mode Resident -RunSeconds ' +
    [string]$LeaseSeconds +
    ' > ' +
    (Quote-PowerShellString -Value $StdoutPath) +
    ' 2> ' +
    (Quote-PowerShellString -Value $StderrPath)
  )
  try {
    $Process = Start-Process `
      -FilePath $PowerShellPath `
      -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $Command) `
      -WorkingDirectory $RepoRoot `
      -PassThru `
      -WindowStyle Hidden
  } catch {
    $Payload = New-BasePayload -ProcessReadback $InitialState -Governance $Governance
    $Payload.ok = $false
    $Payload.status = 'resident_session_start_failed'
    $Payload.applied = $false
    $Payload.started = $false
    $Payload.error = [string]$_.Exception.Message
    $Payload | ConvertTo-Json -Depth 8
    exit 1
  }

  $RunningState = Wait-ForResidentRunning -StatePath $HostStatePath -PidPath $HostPidPath -TimeoutSeconds $StartupTimeoutSeconds
  $Started = [bool](Get-PropertyValue -Payload $RunningState -Name 'resident_session_active' -Default $false)
  $ObservedAt = (Get-Date).ToUniversalTime().ToString('o')
  Write-JsonFile -Path $SessionStatePath -Payload ([ordered]@{
      kind = 'lens.host.resident_session_state'
      status = if ($Started) { 'resident_session_started' } else { 'resident_session_start_unverified' }
      mode = 'resident'
      lease_seconds = $LeaseSeconds
      launcher_pid = $PID
      child_pid = [int](Get-PropertyValue -Payload $RunningState -Name 'pid' -Default ([int]$Process.Id))
      process_id = [int]$Process.Id
      started_at = $StartedAt
      updated_at = $ObservedAt
      host_state_path = 'data/runtime/lens-host/status.json'
      host_pid_path = 'data/runtime/lens-host/lens-host.pid'
      stdout_path = 'data/runtime/lens-host-resident-session/stdout.json'
      stderr_path = 'data/runtime/lens-host-resident-session/stderr.txt'
      governance = $Governance
    })

  $Payload = New-BasePayload -ProcessReadback $RunningState -Governance $Governance
  $Payload.status = if ($Started) { 'resident_session_started' } else { 'resident_session_start_unverified' }
  $Payload.ok = $Started
  $Payload.applied = $Started
  $Payload.started = $Started
  $Payload.child_pid = [int](Get-PropertyValue -Payload $RunningState -Name 'pid' -Default ([int]$Process.Id))
  $Payload.session = Read-JsonFile -Path $SessionStatePath
  $Payload | ConvertTo-Json -Depth 8
  if ($Started) {
    exit 0
  }
  exit 1
}

$Governance = New-Governance -ReadOnlyContract $false -LocalProcessLaunchAuthority $false -ProcessStopAuthority $true -RuntimeStateWrite $true -MutationAuthority $true
if (-not [bool](Get-PropertyValue -Payload $InitialState -Name 'resident_session_active' -Default $false)) {
  $Payload = New-BasePayload -ProcessReadback $InitialState -Governance $Governance
  $Payload.status = 'resident_session_not_running'
  $Payload.applied = $false
  $Payload.stopped = $false
  $Payload | ConvertTo-Json -Depth 8
  exit 0
}

$ResidentPid = [int](Get-PropertyValue -Payload $InitialState -Name 'pid' -Default 0)
try {
  Stop-Process -Id $ResidentPid -Force -ErrorAction Stop
} catch {
}
Start-Sleep -Milliseconds 250
$StoppedAt = (Get-Date).ToUniversalTime().ToString('o')
$StoppedState = [ordered]@{
  kind = 'lens.host.runtime_state'
  status = 'resident_stopped'
  mode = 'resident'
  pid = $ResidentPid
  process_alive = $false
  resident = $false
  resident_claim_allowed = $false
  service_managed = $false
  tray_presence = $false
  global_hotkey = $false
  overlay_window = $false
  summon_anywhere = $false
  started_at = [string](Get-PropertyValue -Payload $InitialState -Name 'state_started_at' -Default '')
  updated_at = $StoppedAt
  heartbeat_interval_ms = 500
  heartbeat_count = [int](Get-PropertyValue -Payload $InitialState -Name 'heartbeat_count' -Default 0)
  last_heartbeat_at = [string](Get-PropertyValue -Payload $InitialState -Name 'last_heartbeat_at' -Default '')
  bounded_run_seconds = $LeaseSeconds
  stop_reason = 'resident_session_stop_requested'
  governance = $Governance
}
Write-JsonFile -Path $HostStatePath -Payload $StoppedState
Remove-Item -LiteralPath $HostPidPath -Force -ErrorAction SilentlyContinue
Write-JsonFile -Path $SessionStatePath -Payload ([ordered]@{
    kind = 'lens.host.resident_session_state'
    status = 'resident_session_stopped'
    mode = 'resident'
    lease_seconds = $LeaseSeconds
    child_pid = $ResidentPid
    updated_at = $StoppedAt
    stopped_at = $StoppedAt
    stop_reason = 'resident_session_stop_requested'
    governance = $Governance
  })

$FinalState = Get-ResidentState -StatePath $HostStatePath -PidPath $HostPidPath
$Payload = New-BasePayload -ProcessReadback $FinalState -Governance $Governance
$Payload.status = 'resident_session_stopped'
$Payload.applied = $true
$Payload.stopped = $true
$Payload.child_pid = $ResidentPid
$Payload.session = Read-JsonFile -Path $SessionStatePath
$Payload | ConvertTo-Json -Depth 8
exit 0
