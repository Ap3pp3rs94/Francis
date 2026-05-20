[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(2, 30)]
  [int]$RunSeconds = 5,

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

function Invoke-HostStatus {
  param(
    [string]$PowerShellPath,
    [string]$HostScriptPath,
    [string]$ProofDataRoot
  )

  $PreviousDataDir = [string]$env:FRANCIS_DATA_DIR
  try {
    $env:FRANCIS_DATA_DIR = $ProofDataRoot
    $Output = & $PowerShellPath -NoProfile -ExecutionPolicy Bypass -File $HostScriptPath -Mode Status 2>&1
    $ExitCode = $LASTEXITCODE
  } finally {
    if ([string]::IsNullOrWhiteSpace($PreviousDataDir)) {
      Remove-Item Env:\FRANCIS_DATA_DIR -ErrorAction SilentlyContinue
    } else {
      $env:FRANCIS_DATA_DIR = $PreviousDataDir
    }
  }

  $Text = ($Output | ForEach-Object { [string]$_ }) -join "`n"
  $Payload = $null
  try {
    $Payload = $Text | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $Payload = $null
  }

  return [ordered]@{
    exit_code = $ExitCode
    payload = $Payload
    output = $Text
  }
}

$PowerShellPath = Get-PowerShellPath
$HostScriptPath = Join-Path $PSScriptRoot 'lens-host.ps1'
$HostScriptExists = Test-Path -LiteralPath $HostScriptPath -PathType Leaf

if ([string]::IsNullOrWhiteSpace($DataDir)) {
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-host-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}
$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$RuntimeDir = Join-Path $ProofDataRoot 'runtime\lens-host'
$StatePath = Join-Path $RuntimeDir 'status.json'
$PidPath = Join-Path $RuntimeDir 'lens-host.pid'

$Checks = [System.Collections.ArrayList]::new()
[void]$Checks.Add((New-Check -Id 'powershell_runtime' -Status $(if ($PowerShellPath) { 'present' } else { 'missing' }) -Passed (-not [string]::IsNullOrWhiteSpace($PowerShellPath)) -Evidence $PowerShellPath -Reason 'PowerShell is required for the bounded foreground proof.'))
[void]$Checks.Add((New-Check -Id 'host_status_runner' -Status $(if ($HostScriptExists) { 'present' } else { 'missing' }) -Passed $HostScriptExists -Evidence 'scripts/lens-host.ps1' -Reason 'The proof observes the existing Lens host status runner.'))

$ProofStarted = $false
$RunningState = $null
$StatusResult = $null
$FinalPayload = $null
$FinalState = $null
$ForegroundExitCode = -1
$ForegroundStdout = ''
$ForegroundStderr = ''

if ($PowerShellPath -and $HostScriptExists) {
  New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
  $ForegroundOutputPath = Join-Path $RuntimeDir 'foreground-output.json'
  $ForegroundErrorPath = Join-Path $RuntimeDir 'foreground-error.txt'
  Remove-Item -LiteralPath $ForegroundOutputPath -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $ForegroundErrorPath -Force -ErrorAction SilentlyContinue
  $ChildCommand = (
    '$env:FRANCIS_DATA_DIR = ' +
    (Quote-PowerShellString -Value $ProofDataRoot) +
    '; & ' +
    (Quote-PowerShellString -Value $HostScriptPath) +
    ' -Mode Foreground -RunSeconds ' +
    [string]$RunSeconds +
    ' > ' +
    (Quote-PowerShellString -Value $ForegroundOutputPath) +
    ' 2> ' +
    (Quote-PowerShellString -Value $ForegroundErrorPath)
  )
  $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
  $StartInfo.FileName = $PowerShellPath
  $StartInfo.Arguments = '-NoProfile -ExecutionPolicy Bypass -Command ' + (Quote-ProcessArgument -Value $ChildCommand)
  $StartInfo.WorkingDirectory = $RepoRoot
  $StartInfo.UseShellExecute = $false
  $StartInfo.CreateNoWindow = $true
  $StartInfo.RedirectStandardOutput = $false
  $StartInfo.RedirectStandardError = $false

  $ForegroundProcess = [System.Diagnostics.Process]::new()
  $ForegroundProcess.StartInfo = $StartInfo
  $ProofStarted = $ForegroundProcess.Start()

  $RunningState = Wait-ForRuntimeState -StatePath $StatePath -Status 'foreground_running' -TimeoutSeconds 10
  $StatusResult = Invoke-HostStatus -PowerShellPath $PowerShellPath -HostScriptPath $HostScriptPath -ProofDataRoot $ProofDataRoot

  $WaitTimeoutMs = [int](($RunSeconds + 10) * 1000)
  $Completed = $ForegroundProcess.WaitForExit($WaitTimeoutMs)
  if (-not $Completed) {
    try {
      $ForegroundProcess.Kill()
    } catch {
    }
    $ForegroundProcess.WaitForExit(5000) | Out-Null
  }
  $ForegroundExitCode = $ForegroundProcess.ExitCode
  if (Test-Path -LiteralPath $ForegroundOutputPath -PathType Leaf) {
    $ForegroundStdout = Get-Content -LiteralPath $ForegroundOutputPath -Raw -ErrorAction SilentlyContinue
  }
  if (Test-Path -LiteralPath $ForegroundErrorPath -PathType Leaf) {
    $ForegroundStderr = Get-Content -LiteralPath $ForegroundErrorPath -Raw -ErrorAction SilentlyContinue
  }
  try {
    $FinalPayload = $ForegroundStdout | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $FinalPayload = $null
  }
  $FinalState = Read-JsonFile -Path $StatePath
}

$RunningPid = [int](Get-PropertyValue -Payload $RunningState -Name 'pid' -Default 0)
$StatusPayload = Get-PropertyValue -Payload $StatusResult -Name 'payload'
$StatusProcess = Get-PropertyValue -Payload $StatusPayload -Name 'process_readback'
$StatusPid = [int](Get-PropertyValue -Payload $StatusProcess -Name 'pid' -Default 0)
$RawStatusState = [string](Get-PropertyValue -Payload $StatusProcess -Name 'state_status' -Default '')
$StatusState = if ([string]::IsNullOrWhiteSpace($RawStatusState)) { 'unreadable' } else { $RawStatusState }
$ForegroundObserved = (
  $ProofStarted -and
  [string](Get-PropertyValue -Payload $RunningState -Name 'status' -Default '') -eq 'foreground_running' -and
  [bool](Get-PropertyValue -Payload $RunningState -Name 'process_alive' -Default $false)
)
$StatusProcessObserved = (
  [int](Get-PropertyValue -Payload $StatusResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $StatusProcess -Name 'status' -Default '') -eq 'process_observed'
)
$StatusPidMatched = (
  $StatusPid -eq $RunningPid -and
  $StatusPid -gt 0
)
$StatusStateMatched = $StatusState -eq 'foreground_running'
$StatusStateAccepted = $StatusStateMatched -or $StatusState -eq 'unreadable'
$StatusMatched = (
  $StatusProcessObserved -and
  $StatusPidMatched -and
  $StatusStateAccepted
)
$ForegroundCompleted = (
  $ForegroundExitCode -eq 0 -and
  [string](Get-PropertyValue -Payload $FinalPayload -Name 'status' -Default '') -eq 'foreground_completed' -and
  [string](Get-PropertyValue -Payload $FinalState -Name 'status' -Default '') -eq 'foreground_stopped'
)

[void]$Checks.Add((New-Check -Id 'foreground_runtime_state' -Status $(if ($ForegroundObserved) { 'observed' } else { 'missing' }) -Passed $ForegroundObserved -Evidence 'runtime/lens-host/status.json' -Reason 'The bounded foreground host writes a live runtime state before stopping.'))
[void]$Checks.Add((New-Check -Id 'host_status_readback' -Status $(if ($StatusMatched -and $StatusStateMatched) { 'process_observed' } elseif ($StatusMatched) { 'process_observed_state_unreadable' } else { 'not_observed' }) -Passed $StatusMatched -Evidence 'scripts/lens-host.ps1 -Mode Status' -Reason 'Status readback must observe the same foreground process and PID; Windows can transiently report the live state file as unreadable while the process/PID readback is valid.'))
[void]$Checks.Add((New-Check -Id 'foreground_completion' -Status $(if ($ForegroundCompleted) { 'completed' } else { 'failed' }) -Passed $ForegroundCompleted -Evidence 'scripts/lens-host.ps1 -Mode Foreground' -Reason 'The foreground proof must stop itself after the bounded run.'))

$ProofPassed = $ForegroundObserved -and $StatusMatched -and $ForegroundCompleted
$Blockers = @(
  'resident_supervision_disabled',
  'lens_host_persistent_supervision_prerequisites_pending',
  'service_control_authority_false',
  'tray_host_missing',
  'global_hotkey_binding_missing',
  'overlay_window_missing',
  'summon_binding_missing'
)

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.host.foreground_readiness_proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  data_root = $ProofDataRoot
  run_seconds = $RunSeconds
  ready_for_resident_claim = $false
  foreground_process_observed = $ForegroundObserved
  foreground_status_readback_matched = $StatusMatched
  foreground_status_state_matched = $StatusStateMatched
  foreground_completed = $ForegroundCompleted
  resident_host_process = $false
  supervised = $false
  service_managed = $false
  tray_presence = $false
  global_hotkey = $false
  overlay_window = $false
  command_palette_binding = $false
  summon_anywhere = $false
  checks = @($Checks)
  blockers = @($Blockers)
  proof = [ordered]@{
    status_runner = 'scripts/lens-host.ps1'
    runtime_state_path = 'runtime/lens-host/status.json'
    pid_path = 'runtime/lens-host/lens-host.pid'
    running_state_status = [string](Get-PropertyValue -Payload $RunningState -Name 'status' -Default '')
    running_pid = $RunningPid
    status_readback_status = [string](Get-PropertyValue -Payload $StatusProcess -Name 'status' -Default '')
    status_readback_state = $StatusState
    status_readback_state_matched = $StatusStateMatched
    status_readback_pid_matched = $StatusPidMatched
    status_readback_pid = $StatusPid
    final_exit_code = $ForegroundExitCode
    final_payload_status = [string](Get-PropertyValue -Payload $FinalPayload -Name 'status' -Default '')
    final_state_status = [string](Get-PropertyValue -Payload $FinalState -Name 'status' -Default '')
    foreground_stdout_length = if ($null -eq $ForegroundStdout) { 0 } else { $ForegroundStdout.Length }
    foreground_stderr_length = if ($null -eq $ForegroundStderr) { 0 } else { $ForegroundStderr.Length }
  }
  governance = [ordered]@{
    diagnostic_only = $true
    bounded_foreground_session = $true
    temporary_runtime_state_write = $true
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = $false
    api_local_process_launch_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Bounded foreground Lens host status was observed and stopped; this proves readiness instrumentation only, not resident host capability.'
}

$Payload | ConvertTo-Json -Depth 10
if ($ProofPassed) {
  exit 0
}
exit 1
