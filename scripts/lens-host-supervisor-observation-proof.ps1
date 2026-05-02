[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(3, 30)]
  [int]$RunSeconds = 20,

  [string]$DataDir = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

function New-Check {
  param(
    [string]$Id,
    [string]$Status,
    [bool]$Passed,
    [string]$Evidence = '',
    [string]$Reason = ''
  )

  return [ordered]@{
    id = $Id
    status = $Status
    passed = $Passed
    evidence = $Evidence
    reason = $Reason
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

function ConvertTo-StringArray {
  param([object]$Value)

  if ($null -eq $Value) {
    return @()
  }
  if ($Value -is [string]) {
    if ([string]::IsNullOrWhiteSpace($Value)) {
      return @()
    }
    return @($Value)
  }
  if ($Value -is [System.Array]) {
    return @($Value | ForEach-Object {
        $Item = [string]$_
        if (-not [string]::IsNullOrWhiteSpace($Item)) {
          $Item
        }
      })
  }
  $SingleValue = [string]$Value
  if ([string]::IsNullOrWhiteSpace($SingleValue)) {
    return @()
  }
  return @($SingleValue)
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

function Stop-ProcessTree {
  param([System.Diagnostics.Process]$Process)

  if ($null -eq $Process -or $Process.HasExited) {
    return
  }
  try {
    $Process.Kill($true)
  } catch {
    try {
      $Process.Kill()
    } catch {
    }
  }
}

function Invoke-HostScript {
  param(
    [string]$PowerShellPath,
    [string]$HostScriptPath,
    [string]$ProofDataRoot,
    [string[]]$ScriptArgs,
    [int]$TimeoutSeconds = 60
  )

  if ([string]::IsNullOrWhiteSpace($PowerShellPath) -or -not (Test-Path -LiteralPath $HostScriptPath -PathType Leaf)) {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
      error = 'script_unavailable'
      timed_out = $false
    }
  }

  $ArgumentParts = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    (Quote-ProcessArgument -Value $HostScriptPath)
  )
  foreach ($Arg in $ScriptArgs) {
    $ArgumentParts += (Quote-ProcessArgument -Value $Arg)
  }

  $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
  $StartInfo.FileName = $PowerShellPath
  $StartInfo.Arguments = $ArgumentParts -join ' '
  $StartInfo.WorkingDirectory = $RepoRoot
  $StartInfo.UseShellExecute = $false
  $StartInfo.CreateNoWindow = $true
  $StartInfo.RedirectStandardOutput = $true
  $StartInfo.RedirectStandardError = $true
  $StartInfo.EnvironmentVariables['FRANCIS_DATA_DIR'] = $ProofDataRoot

  $Process = [System.Diagnostics.Process]::new()
  $Process.StartInfo = $StartInfo
  $Started = $false
  try {
    $Started = $Process.Start()
  } catch {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
      error = [string]$_.Exception.Message
      timed_out = $false
    }
  }
  if (-not $Started) {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
      error = 'process_not_started'
      timed_out = $false
    }
  }

  $StdoutTask = $Process.StandardOutput.ReadToEndAsync()
  $StderrTask = $Process.StandardError.ReadToEndAsync()
  $Exited = $Process.WaitForExit($TimeoutSeconds * 1000)
  if (-not $Exited) {
    Stop-ProcessTree -Process $Process
    [void]$Process.WaitForExit(5000)
    return [ordered]@{
      exit_code = 124
      payload = $null
      output = ''
      error = 'timeout'
      timed_out = $true
    }
  }

  $Text = $StdoutTask.GetAwaiter().GetResult()
  $ErrorText = $StderrTask.GetAwaiter().GetResult()
  $Payload = $null
  try {
    $Payload = $Text | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $Payload = $null
  }

  return [ordered]@{
    exit_code = [int]$Process.ExitCode
    payload = $Payload
    output = $Text
    error = $ErrorText
    timed_out = $false
  }
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

function Start-JsonScript {
  param(
    [string]$PowerShellPath,
    [string]$ScriptPath,
    [string]$ProofDataRoot,
    [string[]]$ScriptArgs
  )

  if ([string]::IsNullOrWhiteSpace($PowerShellPath) -or -not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    return [ordered]@{
      started = $false
      process = $null
      error = 'script_unavailable'
    }
  }

  $AsyncDir = Join-Path $ProofDataRoot 'runtime\lens-host-supervisor-proof'
  New-Item -ItemType Directory -Force -Path $AsyncDir | Out-Null
  $StdoutPath = Join-Path $AsyncDir 'launch-stdout.json'
  $StderrPath = Join-Path $AsyncDir 'launch-stderr.txt'
  Remove-Item -LiteralPath $StdoutPath -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $StderrPath -Force -ErrorAction SilentlyContinue

  $ScriptArgumentText = @()
  foreach ($Arg in $ScriptArgs) {
    if ($Arg.StartsWith('-')) {
      $ScriptArgumentText += $Arg
    } else {
      $ScriptArgumentText += (Quote-PowerShellString -Value $Arg)
    }
  }
  $Command = (
    '$env:FRANCIS_DATA_DIR = ' +
    (Quote-PowerShellString -Value $ProofDataRoot) +
    '; & ' +
    (Quote-PowerShellString -Value $ScriptPath) +
    ' ' +
    ($ScriptArgumentText -join ' ') +
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
  $StartInfo.EnvironmentVariables['FRANCIS_DATA_DIR'] = $ProofDataRoot

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

function Complete-JsonScript {
  param(
    [object]$StartedProcess,
    [int]$TimeoutSeconds = 20
  )

  $Process = Get-PropertyValue -Payload $StartedProcess -Name 'process'
  if (-not [bool](Get-PropertyValue -Payload $StartedProcess -Name 'started' -Default $false) -or $null -eq $Process) {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
      error = [string](Get-PropertyValue -Payload $StartedProcess -Name 'error' -Default 'not_started')
    }
  }

  $Exited = $Process.WaitForExit($TimeoutSeconds * 1000)
  if (-not $Exited) {
    Stop-ProcessTree -Process $Process
    [void]$Process.WaitForExit(5000)
    return [ordered]@{
      exit_code = 124
      payload = $null
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
  $Payload = $null
  try {
    $Payload = $Stdout | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $Payload = $null
  }

  return [ordered]@{
    exit_code = [int]$Process.ExitCode
    payload = $Payload
    output = $Stdout
    error = $Stderr
  }
}

$PowerShellPath = Get-PowerShellPath
$HostScriptPath = Join-Path $PSScriptRoot 'lens-host.ps1'
$SupervisorScriptPath = Join-Path $PSScriptRoot 'lens-host-supervisor.ps1'
$HostScriptExists = Test-Path -LiteralPath $HostScriptPath -PathType Leaf
$SupervisorScriptExists = Test-Path -LiteralPath $SupervisorScriptPath -PathType Leaf

if ([string]::IsNullOrWhiteSpace($DataDir)) {
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-host-supervisor-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}
$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$RuntimeDir = Join-Path $ProofDataRoot 'runtime\lens-host'
$StatePath = Join-Path $RuntimeDir 'status.json'
$PidPath = Join-Path $RuntimeDir 'lens-host.pid'

$Checks = [System.Collections.ArrayList]::new()
[void]$Checks.Add((New-Check -Id 'powershell_runtime' -Status $(if ($PowerShellPath) { 'present' } else { 'missing' }) -Passed (-not [string]::IsNullOrWhiteSpace($PowerShellPath)) -Evidence $PowerShellPath -Reason 'PowerShell is required for bounded supervisor observation.'))
[void]$Checks.Add((New-Check -Id 'host_status_runner' -Status $(if ($HostScriptExists) { 'present' } else { 'missing' }) -Passed $HostScriptExists -Evidence 'scripts/lens-host.ps1' -Reason 'The proof observes the existing bounded Lens host runner.'))
[void]$Checks.Add((New-Check -Id 'host_supervisor_runner' -Status $(if ($SupervisorScriptExists) { 'present' } else { 'missing' }) -Passed $SupervisorScriptExists -Evidence 'scripts/lens-host-supervisor.ps1' -Reason 'The proof consumes the reusable bounded host supervisor runner.'))

$LaunchResult = $null
$LaunchPayload = $null
$LaunchProcess = $null
$LaunchGovernance = $null
$SupervisorResult = $null
$SupervisorPayload = $null
$SupervisorProof = $null
$SupervisorGovernance = $null
$FinalStatusResult = $null
$FinalStatusPayload = $null
$FinalProcessReadback = $null
$RunningPid = 0
$StoppedPid = 0
$LaunchObserved = $false
$SupervisorObserved = $false
$RunningObserved = $false
$StoppedObserved = $false
$FinalStatusObserved = $false
$AuthorityBounded = $false

if ($PowerShellPath -and $HostScriptExists -and $SupervisorScriptExists) {
  New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
  $LaunchStartedProcess = Start-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $HostScriptPath -ProofDataRoot $ProofDataRoot -ScriptArgs @('-Mode', 'Launch', '-RunSeconds', [string]$RunSeconds)
  $SupervisorResult = Invoke-HostScript -PowerShellPath $PowerShellPath -HostScriptPath $SupervisorScriptPath -ProofDataRoot $ProofDataRoot -ScriptArgs @('-Mode', 'Observe', '-RunSeconds', [string]$RunSeconds, '-DataDir', $ProofDataRoot) -TimeoutSeconds ([Math]::Max(90, ($RunSeconds * 2) + 60))
  $LaunchResult = Complete-JsonScript -StartedProcess $LaunchStartedProcess -TimeoutSeconds ([Math]::Max(30, $RunSeconds + 30))
  $LaunchPayload = Get-PropertyValue -Payload $LaunchResult -Name 'payload'
  $LaunchProcess = Get-PropertyValue -Payload $LaunchPayload -Name 'process_readback'
  $LaunchGovernance = Get-PropertyValue -Payload $LaunchPayload -Name 'governance'
  $Launch = Get-PropertyValue -Payload $LaunchPayload -Name 'launch'

  $LaunchReadbackPid = [int](Get-PropertyValue -Payload $LaunchProcess -Name 'pid' -Default 0)
  $RunningPid = $LaunchReadbackPid
  $LaunchObserved = (
    [int](Get-PropertyValue -Payload $LaunchResult -Name 'exit_code' -Default -1) -eq 0 -and
    [string](Get-PropertyValue -Payload $LaunchPayload -Name 'kind' -Default '') -eq 'lens.host.status_runner' -and
    [string](Get-PropertyValue -Payload $LaunchPayload -Name 'status' -Default '') -eq 'launch_started' -and
    [string](Get-PropertyValue -Payload $Launch -Name 'status' -Default '') -eq 'started_observed' -and
    [string](Get-PropertyValue -Payload $LaunchProcess -Name 'status' -Default '') -eq 'process_observed'
  )

  $SupervisorPayload = Get-PropertyValue -Payload $SupervisorResult -Name 'payload'
  $SupervisorProof = Get-PropertyValue -Payload $SupervisorPayload -Name 'proof'
  $SupervisorGovernance = Get-PropertyValue -Payload $SupervisorPayload -Name 'governance'
  $RunningPid = [int](Get-PropertyValue -Payload $SupervisorProof -Name 'running_pid' -Default $RunningPid)
  $StoppedPid = [int](Get-PropertyValue -Payload $SupervisorProof -Name 'stopped_pid' -Default 0)
  $SupervisorObserved = (
    $LaunchObserved -and
    [int](Get-PropertyValue -Payload $SupervisorResult -Name 'exit_code' -Default -1) -eq 0 -and
    [string](Get-PropertyValue -Payload $SupervisorPayload -Name 'kind' -Default '') -eq 'lens.host.supervisor_runner' -and
    [string](Get-PropertyValue -Payload $SupervisorPayload -Name 'status' -Default '') -eq 'observation_completed' -and
    [bool](Get-PropertyValue -Payload $SupervisorPayload -Name 'bounded_supervisor_observed' -Default $false)
  )
  $RunningObserved = (
    $SupervisorObserved -and
    [bool](Get-PropertyValue -Payload $SupervisorPayload -Name 'supervisor_observed_running_state' -Default $false) -and
    [string](Get-PropertyValue -Payload $SupervisorProof -Name 'running_state_status' -Default '') -eq 'foreground_running' -and
    [bool](Get-PropertyValue -Payload $SupervisorProof -Name 'running_process_alive' -Default $false) -and
    $RunningPid -gt 0
  )
  $StoppedObserved = (
    $SupervisorObserved -and
    [bool](Get-PropertyValue -Payload $SupervisorPayload -Name 'supervisor_observed_stopped_state' -Default $false) -and
    [string](Get-PropertyValue -Payload $SupervisorProof -Name 'stopped_state_status' -Default '') -eq 'foreground_stopped' -and
    -not [bool](Get-PropertyValue -Payload $SupervisorProof -Name 'stopped_process_alive' -Default $true) -and
    [bool](Get-PropertyValue -Payload $SupervisorProof -Name 'same_process_observed' -Default $false) -and
    -not [bool](Get-PropertyValue -Payload $SupervisorProof -Name 'pid_file_present_after_stop' -Default $true) -and
    $StoppedPid -eq $RunningPid
  )
  $AuthorityBounded = (
    [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'diagnostic_only' -Default $false) -and
    [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'bounded_process_launch' -Default $false) -and
    [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'local_process_launch_authority' -Default $false) -and
    -not [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'product_execution_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'api_local_process_launch_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'service_control_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'memory_write' -Default $true) -and
    [bool](Get-PropertyValue -Payload $SupervisorGovernance -Name 'diagnostic_only' -Default $false) -and
    [bool](Get-PropertyValue -Payload $SupervisorGovernance -Name 'bounded_supervisor_observation' -Default $false) -and
    -not [bool](Get-PropertyValue -Payload $SupervisorGovernance -Name 'local_process_launch_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $SupervisorGovernance -Name 'product_execution_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $SupervisorGovernance -Name 'process_supervision_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $SupervisorGovernance -Name 'process_restart_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $SupervisorGovernance -Name 'service_control_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $SupervisorGovernance -Name 'memory_write' -Default $true)
  )

  $FinalStatusResult = Invoke-HostScript -PowerShellPath $PowerShellPath -HostScriptPath $HostScriptPath -ProofDataRoot $ProofDataRoot -ScriptArgs @('-Mode', 'Status') -TimeoutSeconds 30
  $FinalStatusPayload = Get-PropertyValue -Payload $FinalStatusResult -Name 'payload'
  $FinalProcessReadback = Get-PropertyValue -Payload $FinalStatusPayload -Name 'process_readback'
  $FinalStatusObserved = (
    [int](Get-PropertyValue -Payload $FinalStatusResult -Name 'exit_code' -Default -1) -eq 0 -and
    [string](Get-PropertyValue -Payload $FinalProcessReadback -Name 'status' -Default '') -eq 'state_present_process_not_running' -and
    [string](Get-PropertyValue -Payload $FinalProcessReadback -Name 'state_status' -Default '') -eq 'foreground_stopped' -and
    -not [bool](Get-PropertyValue -Payload $FinalProcessReadback -Name 'pid_present' -Default $true)
  )
}

[void]$Checks.Add((New-Check -Id 'bounded_launch_started' -Status $(if ($LaunchObserved) { 'launch_started_observed' } else { 'not_observed' }) -Passed $LaunchObserved -Evidence 'scripts/lens-host.ps1 -Mode Launch' -Reason 'Supervisor observation starts from one bounded host launch.'))
[void]$Checks.Add((New-Check -Id 'supervisor_runner_consumed' -Status $(if ($SupervisorObserved) { 'observation_completed' } else { 'not_observed' }) -Passed $SupervisorObserved -Evidence 'scripts/lens-host-supervisor.ps1 -Mode Observe' -Reason 'The proof must consume the reusable bounded supervisor runner.'))
[void]$Checks.Add((New-Check -Id 'supervisor_observed_running_state' -Status $(if ($RunningObserved) { 'foreground_running_observed' } else { 'not_observed' }) -Passed $RunningObserved -Evidence 'scripts/lens-host-supervisor.ps1 -Mode Observe' -Reason 'The observer must see the temporary foreground process while it is alive.'))
[void]$Checks.Add((New-Check -Id 'supervisor_observed_stopped_state' -Status $(if ($StoppedObserved) { 'foreground_stopped_observed' } else { 'not_observed' }) -Passed $StoppedObserved -Evidence 'scripts/lens-host-supervisor.ps1 -Mode Observe' -Reason 'The observer must see the same process self-stop and leave no pid file.'))
[void]$Checks.Add((New-Check -Id 'status_readback_after_stop' -Status $(if ($FinalStatusObserved) { 'stopped_readback_ready' } else { 'not_observed' }) -Passed $FinalStatusObserved -Evidence 'scripts/lens-host.ps1 -Mode Status' -Reason 'Post-stop host status must report state present and process not running.'))
[void]$Checks.Add((New-Check -Id 'launch_authority_boundary' -Status $(if ($AuthorityBounded) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $AuthorityBounded -Evidence 'launch.governance' -Reason 'Supervisor observation must not grant product/API execution, service control, or memory-write authority.'))

$ProofPassed = $LaunchObserved -and $SupervisorObserved -and $RunningObserved -and $StoppedObserved -and $FinalStatusObserved -and $AuthorityBounded
$Blockers = @(
  'resident_host_process_not_supervised',
  'resident_supervision_disabled',
  'lens_host_runtime_not_implemented',
  'service_control_authority_false',
  'tray_host_missing',
  'global_hotkey_binding_missing',
  'overlay_window_missing',
  'summon_binding_missing'
)

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.host.supervisor_observation_proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  data_root = $ProofDataRoot
  run_seconds = $RunSeconds
  bounded_supervisor_observed = $ProofPassed
  supervision_observation_ready = $ProofPassed
  supervisor_observed_running_state = $RunningObserved
  supervisor_observed_stopped_state = $StoppedObserved
  supervisor_restarted_process = $false
  supervisor_managed_service = $false
  ready_for_resident_claim = $false
  temporary_host_process_observed = $RunningObserved
  resident_host_process = $false
  supervised = $false
  service_managed = $false
  tray_presence = $false
  global_hotkey = $false
  overlay_window = $false
  summon_anywhere = $false
  checks = @($Checks)
  blockers = @($Blockers)
  proof = [ordered]@{
    status_runner = 'scripts/lens-host.ps1'
    supervisor_runner = 'scripts/lens-host-supervisor.ps1'
    runtime_state_path = 'runtime/lens-host/status.json'
    pid_path = 'runtime/lens-host/lens-host.pid'
    launch_exit_code = [int](Get-PropertyValue -Payload $LaunchResult -Name 'exit_code' -Default -1)
    launch_status = [string](Get-PropertyValue -Payload $LaunchPayload -Name 'status' -Default '')
    launch_supported = [bool](Get-PropertyValue -Payload $LaunchPayload -Name 'launch_supported' -Default $false)
    launch_authority = [bool](Get-PropertyValue -Payload $LaunchPayload -Name 'launch_authority' -Default $true)
    diagnostic_launch_authority = [bool](Get-PropertyValue -Payload $LaunchPayload -Name 'diagnostic_launch_authority' -Default $false)
    supervisor_runner_exit_code = [int](Get-PropertyValue -Payload $SupervisorResult -Name 'exit_code' -Default -1)
    supervisor_runner_status = [string](Get-PropertyValue -Payload $SupervisorPayload -Name 'status' -Default '')
    supervisor_state_path = 'runtime/lens-host-supervisor/status.json'
    running_state_source = 'supervisor_runner_observe'
    running_state_status = [string](Get-PropertyValue -Payload $SupervisorProof -Name 'running_state_status' -Default '')
    running_pid = $RunningPid
    running_process_alive = $RunningObserved
    stopped_state_status = [string](Get-PropertyValue -Payload $SupervisorProof -Name 'stopped_state_status' -Default '')
    stopped_pid = $StoppedPid
    stopped_process_alive = [bool](Get-PropertyValue -Payload $SupervisorProof -Name 'stopped_process_alive' -Default $true)
    same_process_observed = [bool](Get-PropertyValue -Payload $SupervisorProof -Name 'same_process_observed' -Default $false)
    final_status_readback = [string](Get-PropertyValue -Payload $FinalProcessReadback -Name 'status' -Default '')
    final_status_state = [string](Get-PropertyValue -Payload $FinalProcessReadback -Name 'state_status' -Default '')
    pid_file_present_after_stop = [bool](Get-PropertyValue -Payload $SupervisorProof -Name 'pid_file_present_after_stop' -Default (Test-Path -LiteralPath $PidPath -PathType Leaf))
  }
  next_smallest_truthful_gap = 'resident_host_process_supervision_or_resident_overlay_runtime'
  governance = [ordered]@{
    diagnostic_only = $true
    bounded_host_launch = $ProofPassed
    bounded_process_launch = $ProofPassed
    bounded_supervisor_observation = $ProofPassed
    temporary_runtime_state_write = $true
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = $ProofPassed
    api_local_process_launch_authority = $false
    process_restart_authority = $false
    process_supervision_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Bounded Lens host supervisor observation watched one diagnostic host process through running and stopped states; this proves observation only, not resident supervision or service management.'
}

$Payload | ConvertTo-Json -Depth 10
if ($ProofPassed) {
  exit 0
}
exit 1
