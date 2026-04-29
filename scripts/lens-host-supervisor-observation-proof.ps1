[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(3, 30)]
  [int]$RunSeconds = 4,

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

function Invoke-HostScript {
  param(
    [string]$PowerShellPath,
    [string]$HostScriptPath,
    [string]$ProofDataRoot,
    [string[]]$ScriptArgs
  )

  if ([string]::IsNullOrWhiteSpace($PowerShellPath) -or -not (Test-Path -LiteralPath $HostScriptPath -PathType Leaf)) {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
    }
  }

  $PreviousDataDir = [string]$env:FRANCIS_DATA_DIR
  try {
    $env:FRANCIS_DATA_DIR = $ProofDataRoot
    $Output = & $PowerShellPath -NoProfile -ExecutionPolicy Bypass -File $HostScriptPath @ScriptArgs 2>&1
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
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-host-supervisor-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}
$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$RuntimeDir = Join-Path $ProofDataRoot 'runtime\lens-host'
$StatePath = Join-Path $RuntimeDir 'status.json'
$PidPath = Join-Path $RuntimeDir 'lens-host.pid'

$Checks = [System.Collections.ArrayList]::new()
[void]$Checks.Add((New-Check -Id 'powershell_runtime' -Status $(if ($PowerShellPath) { 'present' } else { 'missing' }) -Passed (-not [string]::IsNullOrWhiteSpace($PowerShellPath)) -Evidence $PowerShellPath -Reason 'PowerShell is required for bounded supervisor observation.'))
[void]$Checks.Add((New-Check -Id 'host_status_runner' -Status $(if ($HostScriptExists) { 'present' } else { 'missing' }) -Passed $HostScriptExists -Evidence 'scripts/lens-host.ps1' -Reason 'The proof observes the existing bounded Lens host runner.'))

$LaunchResult = $null
$LaunchPayload = $null
$LaunchProcess = $null
$LaunchGovernance = $null
$RunningState = $null
$StoppedState = $null
$FinalStatusResult = $null
$FinalStatusPayload = $null
$FinalProcessReadback = $null
$RunningPid = 0
$StoppedPid = 0
$LaunchObserved = $false
$RunningObserved = $false
$StoppedObserved = $false
$FinalStatusObserved = $false
$AuthorityBounded = $false

if ($PowerShellPath -and $HostScriptExists) {
  New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
  $LaunchResult = Invoke-HostScript -PowerShellPath $PowerShellPath -HostScriptPath $HostScriptPath -ProofDataRoot $ProofDataRoot -ScriptArgs @('-Mode', 'Launch', '-RunSeconds', [string]$RunSeconds)
  $LaunchPayload = Get-PropertyValue -Payload $LaunchResult -Name 'payload'
  $LaunchProcess = Get-PropertyValue -Payload $LaunchPayload -Name 'process_readback'
  $LaunchGovernance = Get-PropertyValue -Payload $LaunchPayload -Name 'governance'
  $Launch = Get-PropertyValue -Payload $LaunchPayload -Name 'launch'

  $RunningState = Wait-ForRuntimeState -StatePath $StatePath -Status 'foreground_running' -TimeoutSeconds 5
  $LaunchReadbackPid = [int](Get-PropertyValue -Payload $LaunchProcess -Name 'pid' -Default 0)
  $RunningPid = $LaunchReadbackPid
  if ($RunningPid -le 0) {
    $RunningPid = [int](Get-PropertyValue -Payload $RunningState -Name 'pid' -Default 0)
  }
  $LaunchObserved = (
    [int](Get-PropertyValue -Payload $LaunchResult -Name 'exit_code' -Default -1) -eq 0 -and
    [string](Get-PropertyValue -Payload $LaunchPayload -Name 'kind' -Default '') -eq 'lens.host.status_runner' -and
    [string](Get-PropertyValue -Payload $LaunchPayload -Name 'status' -Default '') -eq 'launch_started' -and
    [string](Get-PropertyValue -Payload $Launch -Name 'status' -Default '') -eq 'started_observed' -and
    [string](Get-PropertyValue -Payload $LaunchProcess -Name 'status' -Default '') -eq 'process_observed'
  )
  $RunningObserved = (
    $LaunchObserved -and
    [string](Get-PropertyValue -Payload $LaunchProcess -Name 'state_status' -Default '') -eq 'foreground_running' -and
    [bool](Get-PropertyValue -Payload $LaunchProcess -Name 'process_alive' -Default $false) -and
    $RunningPid -gt 0
  )
  $AuthorityBounded = (
    [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'diagnostic_only' -Default $false) -and
    [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'bounded_process_launch' -Default $false) -and
    [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'local_process_launch_authority' -Default $false) -and
    -not [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'product_execution_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'api_local_process_launch_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'service_control_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'memory_write' -Default $true)
  )

  $StoppedState = Wait-ForRuntimeState -StatePath $StatePath -Status 'foreground_stopped' -TimeoutSeconds ($RunSeconds + 10)
  $StoppedPid = [int](Get-PropertyValue -Payload $StoppedState -Name 'pid' -Default 0)
  $StoppedObserved = (
    [string](Get-PropertyValue -Payload $StoppedState -Name 'status' -Default '') -eq 'foreground_stopped' -and
    -not [bool](Get-PropertyValue -Payload $StoppedState -Name 'process_alive' -Default $true) -and
    $StoppedPid -eq $RunningPid -and
    -not (Test-ProcessAlive -ProcessId $StoppedPid) -and
    -not (Test-Path -LiteralPath $PidPath -PathType Leaf)
  )

  $FinalStatusResult = Invoke-HostScript -PowerShellPath $PowerShellPath -HostScriptPath $HostScriptPath -ProofDataRoot $ProofDataRoot -ScriptArgs @('-Mode', 'Status')
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
[void]$Checks.Add((New-Check -Id 'supervisor_observed_running_state' -Status $(if ($RunningObserved) { 'foreground_running_observed' } else { 'not_observed' }) -Passed $RunningObserved -Evidence 'runtime/lens-host/status.json' -Reason 'The observer must see the temporary foreground process while it is alive.'))
[void]$Checks.Add((New-Check -Id 'supervisor_observed_stopped_state' -Status $(if ($StoppedObserved) { 'foreground_stopped_observed' } else { 'not_observed' }) -Passed $StoppedObserved -Evidence 'runtime/lens-host/status.json' -Reason 'The observer must see the same process self-stop and leave no pid file.'))
[void]$Checks.Add((New-Check -Id 'status_readback_after_stop' -Status $(if ($FinalStatusObserved) { 'stopped_readback_ready' } else { 'not_observed' }) -Passed $FinalStatusObserved -Evidence 'scripts/lens-host.ps1 -Mode Status' -Reason 'Post-stop host status must report state present and process not running.'))
[void]$Checks.Add((New-Check -Id 'launch_authority_boundary' -Status $(if ($AuthorityBounded) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $AuthorityBounded -Evidence 'launch.governance' -Reason 'Supervisor observation must not grant product/API execution, service control, or memory-write authority.'))

$ProofPassed = $LaunchObserved -and $RunningObserved -and $StoppedObserved -and $FinalStatusObserved -and $AuthorityBounded
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
    runtime_state_path = 'runtime/lens-host/status.json'
    pid_path = 'runtime/lens-host/lens-host.pid'
    launch_exit_code = [int](Get-PropertyValue -Payload $LaunchResult -Name 'exit_code' -Default -1)
    launch_status = [string](Get-PropertyValue -Payload $LaunchPayload -Name 'status' -Default '')
    launch_supported = [bool](Get-PropertyValue -Payload $LaunchPayload -Name 'launch_supported' -Default $false)
    launch_authority = [bool](Get-PropertyValue -Payload $LaunchPayload -Name 'launch_authority' -Default $true)
    diagnostic_launch_authority = [bool](Get-PropertyValue -Payload $LaunchPayload -Name 'diagnostic_launch_authority' -Default $false)
    running_state_source = 'launch_process_readback'
    running_state_status = [string](Get-PropertyValue -Payload $LaunchProcess -Name 'state_status' -Default '')
    running_pid = $RunningPid
    running_process_alive = $RunningObserved
    stopped_state_status = [string](Get-PropertyValue -Payload $StoppedState -Name 'status' -Default '')
    stopped_pid = $StoppedPid
    same_process_observed = ($RunningPid -gt 0 -and $RunningPid -eq $StoppedPid)
    final_status_readback = [string](Get-PropertyValue -Payload $FinalProcessReadback -Name 'status' -Default '')
    final_status_state = [string](Get-PropertyValue -Payload $FinalProcessReadback -Name 'state_status' -Default '')
    pid_file_present_after_stop = Test-Path -LiteralPath $PidPath -PathType Leaf
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
