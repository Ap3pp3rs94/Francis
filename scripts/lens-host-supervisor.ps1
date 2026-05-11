[CmdletBinding()]
param(
  [ValidateSet('Status', 'Observe', 'SuperviseOnce', 'SuperviseResidentOnce', 'SuperviseResident')]
  [string]$Mode = 'Status',

  [ValidateRange(0, 30)]
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
    $StateStatus = [string](Get-PropertyValue -Payload $Latest -Name 'state_status' -Default '')
    $PidValue = [int](Get-PropertyValue -Payload $Latest -Name 'pid' -Default 0)
    $ProcessAlive = [bool](Get-PropertyValue -Payload $Latest -Name 'process_alive' -Default $false)
    $StatusReady = $StateStatus -eq $Status
    if ($Status -eq 'foreground_running') {
      $StatusReady = $StatusReady -and $PidValue -gt 0 -and $ProcessAlive
    }
    if ($StatusReady) {
      return $Latest
    }
    Start-Sleep -Milliseconds 100
  }
  return $Latest
}

function Wait-ForHostStoppedState {
  param(
    [string]$StatePath,
    [string]$PidPath,
    [int]$ExpectedPid,
    [string]$Status = 'foreground_stopped',
    [int]$TimeoutSeconds
  )

  $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $Latest = Get-HostState -StatePath $StatePath -PidPath $PidPath
  while ((Get-Date) -lt $Deadline) {
    $Latest = Get-HostState -StatePath $StatePath -PidPath $PidPath
    $StateStatus = [string](Get-PropertyValue -Payload $Latest -Name 'state_status' -Default '')
    $StoppedPid = [int](Get-PropertyValue -Payload $Latest -Name 'pid' -Default 0)
    $PidPresent = [bool](Get-PropertyValue -Payload $Latest -Name 'pid_present' -Default $true)
    $ProcessAlive = [bool](Get-PropertyValue -Payload $Latest -Name 'process_alive' -Default $true)
    $SameProcess = $ExpectedPid -le 0 -or $StoppedPid -eq $ExpectedPid
    if ($StateStatus -eq $Status -and $SameProcess -and -not $ProcessAlive -and -not $PidPresent) {
      return $Latest
    }
    Start-Sleep -Milliseconds 100
  }
  return $Latest
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

function Start-BoundedHostProcess {
  param(
    [string]$PowerShellPath,
    [string]$HostScriptPath,
    [string]$DataRoot,
    [int]$RunSeconds,
    [string]$SupervisorRuntimeDir,
    [string]$HostMode = 'Foreground'
  )

  if ([string]::IsNullOrWhiteSpace($PowerShellPath) -or -not (Test-Path -LiteralPath $HostScriptPath -PathType Leaf)) {
    return [ordered]@{
      started = $false
      process = $null
      stdout_path = ''
      stderr_path = ''
      error = 'host_script_unavailable'
    }
  }

  New-Item -ItemType Directory -Force -Path $SupervisorRuntimeDir | Out-Null
  $StdoutPath = Join-Path $SupervisorRuntimeDir 'supervised-host-stdout.json'
  $StderrPath = Join-Path $SupervisorRuntimeDir 'supervised-host-stderr.txt'
  Remove-Item -LiteralPath $StdoutPath -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $StderrPath -Force -ErrorAction SilentlyContinue

  $Command = (
    '$env:FRANCIS_DATA_DIR = ' +
    (Quote-PowerShellString -Value $DataRoot) +
    '; & ' +
    (Quote-PowerShellString -Value $HostScriptPath) +
    ' -Mode ' +
    (Quote-ProcessArgument -Value $HostMode) +
    ' -RunSeconds ' +
    [string]$RunSeconds +
    ' > ' +
    (Quote-PowerShellString -Value $StdoutPath) +
    ' 2> ' +
    (Quote-PowerShellString -Value $StderrPath)
  )

  $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
  $StartInfo.FileName = $PowerShellPath
  $StartInfo.Arguments = '-NoProfile -ExecutionPolicy Bypass -Command ' + (Quote-ProcessArgument -Value $Command)
  $StartInfo.WorkingDirectory = $RepoRoot
  $StartInfo.UseShellExecute = $false
  $StartInfo.CreateNoWindow = $true
  $StartInfo.RedirectStandardOutput = $false
  $StartInfo.RedirectStandardError = $false
  $StartInfo.EnvironmentVariables['FRANCIS_DATA_DIR'] = $DataRoot

  $Process = [System.Diagnostics.Process]::new()
  $Process.StartInfo = $StartInfo
  $Started = $Process.Start()
  return [ordered]@{
    started = $Started
    process = $Process
    stdout_path = $StdoutPath
    stderr_path = $StderrPath
    error = ''
  }
}

function Complete-BoundedHostProcess {
  param(
    [object]$StartedProcess,
    [int]$TimeoutSeconds
  )

  $Process = Get-PropertyValue -Payload $StartedProcess -Name 'process'
  if (-not [bool](Get-PropertyValue -Payload $StartedProcess -Name 'started' -Default $false) -or $null -eq $Process) {
    return [ordered]@{
      exit_code = 1
      exited = $false
      output = ''
      error = [string](Get-PropertyValue -Payload $StartedProcess -Name 'error' -Default 'not_started')
    }
  }

  $Exited = $Process.WaitForExit($TimeoutSeconds * 1000)
  if (-not $Exited) {
    try {
      $Process.Kill()
    } catch {
    }
    return [ordered]@{
      exit_code = 124
      exited = $false
      output = ''
      error = 'timeout'
    }
  }

  $StdoutPath = [string](Get-PropertyValue -Payload $StartedProcess -Name 'stdout_path' -Default '')
  $StderrPath = [string](Get-PropertyValue -Payload $StartedProcess -Name 'stderr_path' -Default '')
  $Stdout = ''
  $Stderr = ''
  if (-not [string]::IsNullOrWhiteSpace($StdoutPath) -and (Test-Path -LiteralPath $StdoutPath -PathType Leaf)) {
    $Stdout = Get-Content -LiteralPath $StdoutPath -Raw -ErrorAction SilentlyContinue
  }
  if (-not [string]::IsNullOrWhiteSpace($StderrPath) -and (Test-Path -LiteralPath $StderrPath -PathType Leaf)) {
    $Stderr = Get-Content -LiteralPath $StderrPath -Raw -ErrorAction SilentlyContinue
  }

  return [ordered]@{
    exit_code = [int]$Process.ExitCode
    exited = $true
    output = $Stdout
    error = $Stderr
  }
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
  supervisor_started_process = $false
  bounded_supervised_session = $false
  temporary_host_process_observed = $InitialProcessAlive
  ready_for_resident_claim = $false
  resident_claim_allowed = $false
  resident_host_process = $false
  resident_supervised_runtime = $false
  resident_runtime_candidate_supervised = $false
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
    resident_claim_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Lens host supervisor runner is diagnostic only; local process launch is bounded to proof modes and does not grant product supervision, restart, service, summon, overlay, tray, or resident-claim authority.'
}

if ($Mode -eq 'Status') {
  $Payload | ConvertTo-Json -Depth 8
  exit 0
}

if ($Mode -eq 'SuperviseResident') {
  $PowerShellPath = Get-PowerShellPath
  $HostScriptPath = Join-Path $PSScriptRoot 'lens-host.ps1'
  $Payload.governance.read_only_contract = $false
  $Payload.governance.bounded_supervisor_observation = $RunSeconds -gt 0
  $Payload.governance.temporary_runtime_state_write = $true
  $Payload.governance.local_process_launch_authority = $true
  $Payload.governance.process_supervision_authority = $true
  $Payload.next_smallest_truthful_gap = 'summon_tray_presence_blocker_boundary'

  $StartedProcess = Start-BoundedHostProcess `
    -PowerShellPath $PowerShellPath `
    -HostScriptPath $HostScriptPath `
    -DataRoot $DataRoot `
    -RunSeconds $RunSeconds `
    -SupervisorRuntimeDir $SupervisorRuntimeDir `
    -HostMode 'Resident'
  $HostStarted = [bool](Get-PropertyValue -Payload $StartedProcess -Name 'started' -Default $false)
  $Payload.supervisor_started_process = $HostStarted

  $RunningObservationTimeout = if ($RunSeconds -gt 0) { [Math]::Max(45, $RunSeconds + 45) } else { 45 }
  $RunningState = Wait-ForHostStatus -StatePath $HostStatePath -PidPath $HostPidPath -Status 'resident_running' -TimeoutSeconds $RunningObservationTimeout
  $RunningPid = [int](Get-PropertyValue -Payload $RunningState -Name 'pid' -Default 0)
  $RunningObserved = (
    $HostStarted -and
    [string](Get-PropertyValue -Payload $RunningState -Name 'state_status' -Default '') -eq 'resident_running' -and
    [bool](Get-PropertyValue -Payload $RunningState -Name 'process_alive' -Default $false) -and
    $RunningPid -gt 0
  )

  if ($RunningObserved) {
    $ObservedAt = (Get-Date).ToUniversalTime().ToString('o')
    Write-JsonFile -Path $SupervisorStatePath -Payload ([ordered]@{
        kind = 'lens.host.supervisor_state'
        status = 'resident_supervising'
        mode = 'supervise_resident'
        host_mode = 'resident'
        observed_pid = $RunningPid
        observed_state = 'resident_running'
        restarted_process = $false
        managed_service = $false
        resident_supervised_runtime = $true
        resident_claim_allowed = $false
        process_supervision_authority = $true
        process_restart_authority = $false
        service_control_authority = $false
        updated_at = $ObservedAt
        governance = $Payload.governance
      })
  }

  if ($RunSeconds -eq 0) {
    $Process = Get-PropertyValue -Payload $StartedProcess -Name 'process'
    if ($null -ne $Process) {
      while (-not $Process.HasExited) {
        Start-Sleep -Milliseconds 500
      }
    }
  }

  $Completion = Complete-BoundedHostProcess -StartedProcess $StartedProcess -TimeoutSeconds ([Math]::Max(45, $RunSeconds + 45))
  $StoppedState = Wait-ForHostStoppedState `
    -StatePath $HostStatePath `
    -PidPath $HostPidPath `
    -ExpectedPid $RunningPid `
    -Status 'resident_stopped' `
    -TimeoutSeconds ([Math]::Max(60, $RunSeconds + 60))
  $StoppedPid = [int](Get-PropertyValue -Payload $StoppedState -Name 'pid' -Default 0)
  $StoppedObserved = (
    $RunningObserved -and
    [string](Get-PropertyValue -Payload $StoppedState -Name 'state_status' -Default '') -eq 'resident_stopped' -and
    -not [bool](Get-PropertyValue -Payload $StoppedState -Name 'process_alive' -Default $true) -and
    $StoppedPid -eq $RunningPid -and
    -not (Test-LeafPathPresent -Path $HostPidPath)
  )
  $HostCompleted = [bool](Get-PropertyValue -Payload $Completion -Name 'exited' -Default $false) -and [int](Get-PropertyValue -Payload $Completion -Name 'exit_code' -Default -1) -eq 0
  $ProofPassed = $RunningObserved -and $StoppedObserved -and $HostCompleted
  $CompletedAt = (Get-Date).ToUniversalTime().ToString('o')

  Write-JsonFile -Path $SupervisorStatePath -Payload ([ordered]@{
      kind = 'lens.host.supervisor_state'
      status = if ($ProofPassed) { 'resident_supervision_probe_completed' } else { 'resident_supervision_probe_failed' }
      mode = 'supervise_resident'
      host_mode = 'resident'
      observed_pid = $RunningPid
      observed_state = [string](Get-PropertyValue -Payload $StoppedState -Name 'state_status' -Default '')
      restarted_process = $false
      managed_service = $false
      resident_supervised_runtime = $false
      resident_claim_allowed = $false
      process_supervision_authority = $true
      process_restart_authority = $false
      service_control_authority = $false
      updated_at = $CompletedAt
      governance = $Payload.governance
    })

  $Payload.ok = $ProofPassed
  $Payload.status = if ($ProofPassed) { 'resident_supervision_probe_completed' } else { 'resident_supervision_probe_failed' }
  $Payload.bounded_supervisor_observed = $ProofPassed
  $Payload.bounded_supervised_session = $ProofPassed
  $Payload.temporary_host_process_observed = $RunningObserved
  $Payload.supervisor_observed_running_state = $RunningObserved
  $Payload.supervisor_observed_stopped_state = $StoppedObserved
  $Payload.resident_runtime_candidate_supervised = $ProofPassed
  $Payload.resident_supervised_runtime = $RunningObserved
  $Payload.resident_host_process = $RunningObserved
  $Payload.supervised = $RunningObserved
  $Payload.host_readback = $StoppedState
  $Payload.blockers = @(
    'tray_host_missing',
    'global_hotkey_binding_missing',
    'overlay_window_missing',
    'summon_binding_missing',
    'service_control_authority_not_granted'
  ) | Sort-Object -Unique
  $Payload.proof.running_state_status = [string](Get-PropertyValue -Payload $RunningState -Name 'state_status' -Default '')
  $Payload.proof.running_pid = $RunningPid
  $Payload.proof.running_process_alive = [bool](Get-PropertyValue -Payload $RunningState -Name 'process_alive' -Default $false)
  $Payload.proof.stopped_state_status = [string](Get-PropertyValue -Payload $StoppedState -Name 'state_status' -Default '')
  $Payload.proof.stopped_pid = $StoppedPid
  $Payload.proof.stopped_process_alive = [bool](Get-PropertyValue -Payload $StoppedState -Name 'process_alive' -Default $true)
  $Payload.proof.same_process_observed = ($RunningPid -gt 0 -and $RunningPid -eq $StoppedPid)
  $Payload.proof.pid_file_present_after_stop = Test-LeafPathPresent -Path $HostPidPath
  $Payload.proof.supervisor_owned_launch = $HostStarted
  $Payload.proof.host_mode = 'resident'
  $Payload.proof.host_exit_code = [int](Get-PropertyValue -Payload $Completion -Name 'exit_code' -Default -1)

  $Payload | ConvertTo-Json -Depth 8
  if ($ProofPassed) {
    exit 0
  }
  exit 1
}

if ($Mode -eq 'SuperviseOnce' -or $Mode -eq 'SuperviseResidentOnce') {
  $ResidentCandidateMode = $Mode -eq 'SuperviseResidentOnce'
  $HostMode = if ($ResidentCandidateMode) { 'Resident' } else { 'Foreground' }
  $HostModeName = $HostMode.ToLowerInvariant()
  $RunningStatus = if ($ResidentCandidateMode) { 'resident_running' } else { 'foreground_running' }
  $StoppedStatus = if ($ResidentCandidateMode) { 'resident_stopped' } else { 'foreground_stopped' }
  $SupervisorMode = if ($ResidentCandidateMode) { 'supervise_resident_once' } else { 'supervise_once' }
  $ObservedRunningState = if ($ResidentCandidateMode) { 'resident_running' } else { 'foreground_running' }
  $NextGap = if ($ResidentCandidateMode) {
    'resident_supervision_not_persistent'
  } else {
    'resident_supervised_session_checkpoint_readback'
  }
  $PowerShellPath = Get-PowerShellPath
  $HostScriptPath = Join-Path $PSScriptRoot 'lens-host.ps1'
  $Payload.governance.read_only_contract = $false
  $Payload.governance.bounded_supervisor_observation = $true
  $Payload.governance.temporary_runtime_state_write = $true
  $Payload.governance.local_process_launch_authority = $true
  $Payload.next_smallest_truthful_gap = $NextGap

  $StartedProcess = Start-BoundedHostProcess `
    -PowerShellPath $PowerShellPath `
    -HostScriptPath $HostScriptPath `
    -DataRoot $DataRoot `
    -RunSeconds $RunSeconds `
    -SupervisorRuntimeDir $SupervisorRuntimeDir `
    -HostMode $HostMode
  $HostStarted = [bool](Get-PropertyValue -Payload $StartedProcess -Name 'started' -Default $false)
  $Payload.supervisor_started_process = $HostStarted

  $RunningObservationTimeout = [Math]::Max(45, $RunSeconds + 45)
  $RunningState = Wait-ForHostStatus -StatePath $HostStatePath -PidPath $HostPidPath -Status $RunningStatus -TimeoutSeconds $RunningObservationTimeout
  $RunningPid = [int](Get-PropertyValue -Payload $RunningState -Name 'pid' -Default 0)
  $RunningObserved = (
    $HostStarted -and
    [string](Get-PropertyValue -Payload $RunningState -Name 'state_status' -Default '') -eq $RunningStatus -and
    [bool](Get-PropertyValue -Payload $RunningState -Name 'process_alive' -Default $false) -and
    $RunningPid -gt 0
  )

  if ($RunningObserved) {
    $ObservedAt = (Get-Date).ToUniversalTime().ToString('o')
    Write-JsonFile -Path $SupervisorStatePath -Payload ([ordered]@{
      kind = 'lens.host.supervisor_state'
      status = 'supervising'
      mode = $SupervisorMode
      host_mode = $HostModeName
      observed_pid = $RunningPid
      observed_state = $ObservedRunningState
      restarted_process = $false
      managed_service = $false
      updated_at = $ObservedAt
      governance = $Payload.governance
    })
  }

  $Completion = Complete-BoundedHostProcess -StartedProcess $StartedProcess -TimeoutSeconds ([Math]::Max(45, $RunSeconds + 45))
  $StoppedObservationTimeout = [Math]::Max(60, $RunSeconds + 60)
  $StoppedState = Wait-ForHostStoppedState -StatePath $HostStatePath -PidPath $HostPidPath -ExpectedPid $RunningPid -Status $StoppedStatus -TimeoutSeconds $StoppedObservationTimeout
  $StoppedPid = [int](Get-PropertyValue -Payload $StoppedState -Name 'pid' -Default 0)
  $StoppedObserved = (
    $RunningObserved -and
    [string](Get-PropertyValue -Payload $StoppedState -Name 'state_status' -Default '') -eq $StoppedStatus -and
    -not [bool](Get-PropertyValue -Payload $StoppedState -Name 'process_alive' -Default $true) -and
    $StoppedPid -eq $RunningPid -and
    -not (Test-LeafPathPresent -Path $HostPidPath)
  )
  $HostCompleted = [bool](Get-PropertyValue -Payload $Completion -Name 'exited' -Default $false) -and [int](Get-PropertyValue -Payload $Completion -Name 'exit_code' -Default -1) -eq 0
  $ProofPassed = $RunningObserved -and $StoppedObserved -and $HostCompleted
  $CompletedAt = (Get-Date).ToUniversalTime().ToString('o')

  Write-JsonFile -Path $SupervisorStatePath -Payload ([ordered]@{
      kind = 'lens.host.supervisor_state'
      status = if ($ProofPassed) { 'supervised_session_completed' } else { 'supervised_session_failed' }
      mode = $SupervisorMode
      host_mode = $HostModeName
      observed_pid = $RunningPid
      observed_state = [string](Get-PropertyValue -Payload $StoppedState -Name 'state_status' -Default '')
      restarted_process = $false
      managed_service = $false
      updated_at = $CompletedAt
      governance = $Payload.governance
    })

  $Payload.ok = $ProofPassed
  $Payload.status = if ($ProofPassed) { 'supervised_session_completed' } else { 'supervised_session_failed' }
  $Payload.bounded_supervisor_observed = $ProofPassed
  $Payload.bounded_supervised_session = $ProofPassed
  $Payload.temporary_host_process_observed = $RunningObserved
  $Payload.supervisor_observed_running_state = $RunningObserved
  $Payload.supervisor_observed_stopped_state = $StoppedObserved
  $Payload.resident_runtime_candidate_supervised = $ResidentCandidateMode -and $ProofPassed
  $Payload.host_readback = $StoppedState
  $BoundedSupervisorBlockers = @(
    'resident_host_process_not_resident',
    'resident_supervision_not_persistent',
    'process_supervision_authority_not_granted',
    'process_restart_authority_not_granted',
    'service_control_authority_not_granted',
    'tray_host_missing',
    'global_hotkey_binding_missing',
    'overlay_window_missing',
    'summon_binding_missing'
  )
  if ($ResidentCandidateMode) {
    $BoundedSupervisorBlockers += 'resident_runtime_candidate_not_persistent'
  }
  $Payload.blockers = @($BoundedSupervisorBlockers | Sort-Object -Unique)
  $Payload.proof.running_state_status = [string](Get-PropertyValue -Payload $RunningState -Name 'state_status' -Default '')
  $Payload.proof.running_pid = $RunningPid
  $Payload.proof.running_process_alive = [bool](Get-PropertyValue -Payload $RunningState -Name 'process_alive' -Default $false)
  $Payload.proof.stopped_state_status = [string](Get-PropertyValue -Payload $StoppedState -Name 'state_status' -Default '')
  $Payload.proof.stopped_pid = $StoppedPid
  $Payload.proof.stopped_process_alive = [bool](Get-PropertyValue -Payload $StoppedState -Name 'process_alive' -Default $true)
  $Payload.proof.same_process_observed = ($RunningPid -gt 0 -and $RunningPid -eq $StoppedPid)
  $Payload.proof.pid_file_present_after_stop = Test-LeafPathPresent -Path $HostPidPath
  $Payload.proof.supervisor_owned_launch = $HostStarted
  $Payload.proof.host_mode = $HostModeName
  $Payload.proof.host_exit_code = [int](Get-PropertyValue -Payload $Completion -Name 'exit_code' -Default -1)

  $Payload | ConvertTo-Json -Depth 8
  if ($ProofPassed) {
    exit 0
  }
  exit 1
}

$RunningObservationTimeout = [Math]::Max(45, $RunSeconds + 45)
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

$StoppedObservationTimeout = [Math]::Max(60, $RunSeconds + 60)
$StoppedState = Wait-ForHostStoppedState -StatePath $HostStatePath -PidPath $HostPidPath -ExpectedPid $RunningPid -TimeoutSeconds $StoppedObservationTimeout
$StoppedPid = [int](Get-PropertyValue -Payload $StoppedState -Name 'pid' -Default 0)
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
