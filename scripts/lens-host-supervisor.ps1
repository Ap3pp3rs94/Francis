[CmdletBinding()]
param(
  [ValidateSet('Status', 'Observe')]
  [string]$Mode = 'Status',

  [ValidateRange(1, 30)]
  [int]$RunSeconds = 5,

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
    [object]$Payload,
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

function Test-LeafPathPresent {
  param([string]$Path)

  try {
    return [bool](Test-Path -LiteralPath $Path -PathType Leaf -ErrorAction Stop)
  } catch {
    return $true
  }
}

function Get-PidValue {
  param([string]$Path)

  if (-not (Test-LeafPathPresent -Path $Path)) {
    return 0
  }
  try {
    return [int]((Get-Content -LiteralPath $Path -Raw -ErrorAction Stop).Trim())
  } catch {
    return 0
  }
}

function Get-HostState {
  param(
    [string]$StatePath,
    [string]$PidPath
  )

  $StatePayload = Read-JsonFile -Path $StatePath
  $PidValue = Get-PidValue -Path $PidPath
  $PidPresent = Test-LeafPathPresent -Path $PidPath
  $StateStatus = [string](Get-PropertyValue -Payload $StatePayload -Name 'status' -Default '')
  if ($PidValue -le 0 -and $null -ne $StatePayload) {
    $PidValue = [int](Get-PropertyValue -Payload $StatePayload -Name 'pid' -Default 0)
  }
  $ProcessAlive = if ($StateStatus -eq 'foreground_stopped' -and -not $PidPresent) {
    $false
  } else {
    Test-ProcessAlive -ProcessId $PidValue
  }
  return [ordered]@{
    state_exists = $null -ne $StatePayload
    state_status = $StateStatus
    state_updated_at = [string](Get-PropertyValue -Payload $StatePayload -Name 'updated_at' -Default '')
    pid_present = $PidPresent
    pid = $PidValue
    process_alive = $ProcessAlive
  }
}

function Wait-ForHostStatus {
  param(
    [string]$StatePath,
    [string]$PidPath,
    [string]$Status,
    [int]$TimeoutSeconds
  )

  $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $Latest = Get-HostState -StatePath $StatePath -PidPath $PidPath
  while ((Get-Date) -lt $Deadline) {
    $Latest = Get-HostState -StatePath $StatePath -PidPath $PidPath
    if ([string](Get-PropertyValue -Payload $Latest -Name 'state_status' -Default '') -eq $Status) {
      return $Latest
    }
    Start-Sleep -Milliseconds 100
  }
  return $Latest
}

$ModeName = $Mode.ToLowerInvariant()
$DataRoot = Get-DataRoot
$HostRuntimeDir = Join-Path $DataRoot 'runtime\lens-host'
$SupervisorRuntimeDir = Join-Path $DataRoot 'runtime\lens-host-supervisor'
$HostStatePath = Join-Path $HostRuntimeDir 'status.json'
$HostPidPath = Join-Path $HostRuntimeDir 'lens-host.pid'
$SupervisorStatePath = Join-Path $SupervisorRuntimeDir 'status.json'
$InitialHostState = Get-HostState -StatePath $HostStatePath -PidPath $HostPidPath
$InitialProcessAlive = [bool](Get-PropertyValue -Payload $InitialHostState -Name 'process_alive' -Default $false)
$InitialPid = [int](Get-PropertyValue -Payload $InitialHostState -Name 'pid' -Default 0)

$BaseBlockers = @(
  'resident_host_process_not_supervised',
  'resident_supervision_disabled',
  'process_supervision_authority_not_granted',
  'process_restart_authority_not_granted',
  'service_control_authority_not_granted',
  'tray_host_missing',
  'global_hotkey_binding_missing',
  'overlay_window_missing',
  'summon_binding_missing'
)
if (-not $InitialProcessAlive) {
  $BaseBlockers = @('resident_host_process_missing') + $BaseBlockers
}
$BaseBlockers = @($BaseBlockers | Sort-Object -Unique)

$Payload = [ordered]@{
  ok = $true
  kind = 'lens.host.supervisor_runner'
  status = if ($InitialProcessAlive) { 'observe_ready' } else { 'blocked' }
  mode = $ModeName
  repo_root = $RepoRoot
  data_root = $DataRoot
  run_seconds = $RunSeconds
  host_state_path = 'data/runtime/lens-host/status.json'
  host_pid_path = 'data/runtime/lens-host/lens-host.pid'
  supervisor_state_path = 'data/runtime/lens-host-supervisor/status.json'
  observer_ready = $true
  bounded_supervisor_observed = $false
  supervisor_observed_running_state = $InitialProcessAlive
  supervisor_observed_stopped_state = $false
  supervisor_restarted_process = $false
  supervisor_managed_service = $false
  ready_for_resident_claim = $false
  resident_claim_allowed = $false
  resident_host_process = $false
  supervised = $false
  service_managed = $false
  tray_presence = $false
  global_hotkey = $false
  overlay_window = $false
  summon_anywhere = $false
  host_readback = $InitialHostState
  blockers = $BaseBlockers
  proof = [ordered]@{
    initial_state_status = [string](Get-PropertyValue -Payload $InitialHostState -Name 'state_status' -Default '')
    initial_pid = $InitialPid
    initial_process_alive = $InitialProcessAlive
    running_state_status = ''
    running_pid = 0
    running_process_alive = $false
    stopped_state_status = ''
    stopped_pid = 0
    stopped_process_alive = $false
    same_process_observed = $false
    pid_file_present_after_stop = Test-LeafPathPresent -Path $HostPidPath
  }
  next_smallest_truthful_gap = 'resident_host_process_supervision_authority_boundary'
  governance = [ordered]@{
    diagnostic_only = $true
    read_only_contract = $Mode -eq 'Status'
    bounded_supervisor_observation = $Mode -eq 'Observe'
    temporary_runtime_state_write = $Mode -eq 'Observe'
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    local_process_launch_authority = $false
    api_local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    overlay_control_authority = $false
    window_management_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Lens host supervisor runner is bounded observation only; it does not launch, restart, supervise, install, start, stop, or claim a resident host.'
}

if ($Mode -eq 'Status') {
  $Payload | ConvertTo-Json -Depth 8
  exit 0
}

$RunningObservationTimeout = [Math]::Max(15, $RunSeconds + 15)
$RunningState = Wait-ForHostStatus -StatePath $HostStatePath -PidPath $HostPidPath -Status 'foreground_running' -TimeoutSeconds $RunningObservationTimeout
$RunningPid = [int](Get-PropertyValue -Payload $RunningState -Name 'pid' -Default 0)
$RunningObserved = (
  [string](Get-PropertyValue -Payload $RunningState -Name 'state_status' -Default '') -eq 'foreground_running' -and
  [bool](Get-PropertyValue -Payload $RunningState -Name 'process_alive' -Default $false) -and
  $RunningPid -gt 0
)

if ($RunningObserved) {
  $ObservedAt = (Get-Date).ToUniversalTime().ToString('o')
  Write-JsonFile -Path $SupervisorStatePath -Payload ([ordered]@{
      kind = 'lens.host.supervisor_state'
      status = 'observing'
      mode = 'observe'
      observed_pid = $RunningPid
      observed_state = 'foreground_running'
      updated_at = $ObservedAt
      governance = $Payload.governance
    })
}

$StoppedObservationTimeout = [Math]::Max(15, $RunSeconds + 15)
$StoppedState = Wait-ForHostStatus -StatePath $HostStatePath -PidPath $HostPidPath -Status 'foreground_stopped' -TimeoutSeconds $StoppedObservationTimeout
$StoppedPid = [int](Get-PropertyValue -Payload $StoppedState -Name 'pid' -Default 0)
if ([string](Get-PropertyValue -Payload $StoppedState -Name 'state_status' -Default '') -eq 'foreground_stopped' -and $StoppedPid -gt 0) {
  # The foreground host writes its stopped state before the PowerShell process fully exits.
  $ExitDeadline = (Get-Date).AddSeconds([Math]::Max(20, $RunSeconds + 20))
  while (
    (Get-Date) -lt $ExitDeadline -and
    ((Test-ProcessAlive -ProcessId $StoppedPid) -or (Test-LeafPathPresent -Path $HostPidPath))
  ) {
    Start-Sleep -Milliseconds 100
    $StoppedState = Get-HostState -StatePath $HostStatePath -PidPath $HostPidPath
    $StoppedPid = [int](Get-PropertyValue -Payload $StoppedState -Name 'pid' -Default $StoppedPid)
  }
}
$StoppedObserved = (
  $RunningObserved -and
  [string](Get-PropertyValue -Payload $StoppedState -Name 'state_status' -Default '') -eq 'foreground_stopped' -and
  -not [bool](Get-PropertyValue -Payload $StoppedState -Name 'process_alive' -Default $true) -and
  $StoppedPid -eq $RunningPid -and
  -not (Test-LeafPathPresent -Path $HostPidPath)
)
$ProofPassed = $RunningObserved -and $StoppedObserved
$CompletedAt = (Get-Date).ToUniversalTime().ToString('o')

Write-JsonFile -Path $SupervisorStatePath -Payload ([ordered]@{
    kind = 'lens.host.supervisor_state'
    status = if ($ProofPassed) { 'observation_completed' } else { 'observation_failed' }
    mode = 'observe'
    observed_pid = $RunningPid
    observed_state = [string](Get-PropertyValue -Payload $StoppedState -Name 'state_status' -Default '')
    restarted_process = $false
    managed_service = $false
    updated_at = $CompletedAt
    governance = $Payload.governance
  })

$Payload.ok = $ProofPassed
$Payload.status = if ($ProofPassed) { 'observation_completed' } else { 'observation_failed' }
$Payload.bounded_supervisor_observed = $ProofPassed
$Payload.supervisor_observed_running_state = $RunningObserved
$Payload.supervisor_observed_stopped_state = $StoppedObserved
$Payload.host_readback = $StoppedState
$Payload.proof.running_state_status = [string](Get-PropertyValue -Payload $RunningState -Name 'state_status' -Default '')
$Payload.proof.running_pid = $RunningPid
$Payload.proof.running_process_alive = [bool](Get-PropertyValue -Payload $RunningState -Name 'process_alive' -Default $false)
$Payload.proof.stopped_state_status = [string](Get-PropertyValue -Payload $StoppedState -Name 'state_status' -Default '')
$Payload.proof.stopped_pid = $StoppedPid
$Payload.proof.stopped_process_alive = [bool](Get-PropertyValue -Payload $StoppedState -Name 'process_alive' -Default $true)
$Payload.proof.same_process_observed = ($RunningPid -gt 0 -and $RunningPid -eq $StoppedPid)
$Payload.proof.pid_file_present_after_stop = Test-LeafPathPresent -Path $HostPidPath

$Payload | ConvertTo-Json -Depth 8
if ($ProofPassed) {
  exit 0
}
exit 1
