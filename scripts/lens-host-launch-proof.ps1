[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(2, 30)]
  [int]$RunSeconds = 3,

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

function Quote-ProcessArgument {
  param([string]$Value)

  if ($null -eq $Value) {
    return '""'
  }
  return '"' + ($Value -replace '"', '\"') + '"'
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

$PowerShellPath = Get-PowerShellPath
$HostScriptPath = Join-Path $PSScriptRoot 'lens-host.ps1'
$HostScriptExists = Test-Path -LiteralPath $HostScriptPath -PathType Leaf

if ([string]::IsNullOrWhiteSpace($DataDir)) {
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-host-launch-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}
$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$RuntimeDir = Join-Path $ProofDataRoot 'runtime\lens-host'
$StatePath = Join-Path $RuntimeDir 'status.json'
$PidPath = Join-Path $RuntimeDir 'lens-host.pid'

$Checks = [System.Collections.ArrayList]::new()
[void]$Checks.Add((New-Check -Id 'powershell_runtime' -Status $(if ($PowerShellPath) { 'present' } else { 'missing' }) -Passed (-not [string]::IsNullOrWhiteSpace($PowerShellPath)) -Evidence $PowerShellPath -Reason 'PowerShell is required for the bounded launch proof.'))
[void]$Checks.Add((New-Check -Id 'host_status_runner' -Status $(if ($HostScriptExists) { 'present' } else { 'missing' }) -Passed $HostScriptExists -Evidence 'scripts/lens-host.ps1' -Reason 'The proof invokes the existing Lens host launch runner.'))

$LaunchResult = $null
$LaunchPayload = $null
$LaunchProcess = $null
$LaunchGovernance = $null
$LaunchObserved = $false
$LaunchAuthorityBounded = $false
$FinalState = $null
$FinalStatusResult = $null
$FinalStatusPayload = $null
$FinalProcessReadback = $null
$LaunchCompleted = $false

if ($PowerShellPath -and $HostScriptExists) {
  New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
  $LaunchResult = Invoke-HostScript -PowerShellPath $PowerShellPath -HostScriptPath $HostScriptPath -ProofDataRoot $ProofDataRoot -ScriptArgs @('-Mode', 'Launch', '-RunSeconds', [string]$RunSeconds) -TimeoutSeconds ([Math]::Max(45, ($RunSeconds * 2) + 30))
  $LaunchPayload = Get-PropertyValue -Payload $LaunchResult -Name 'payload'
  $LaunchProcess = Get-PropertyValue -Payload $LaunchPayload -Name 'process_readback'
  $LaunchGovernance = Get-PropertyValue -Payload $LaunchPayload -Name 'governance'
  $Launch = Get-PropertyValue -Payload $LaunchPayload -Name 'launch'

  $LaunchObserved = (
    [int](Get-PropertyValue -Payload $LaunchResult -Name 'exit_code' -Default -1) -eq 0 -and
    [string](Get-PropertyValue -Payload $LaunchPayload -Name 'kind' -Default '') -eq 'lens.host.status_runner' -and
    [string](Get-PropertyValue -Payload $LaunchPayload -Name 'status' -Default '') -eq 'launch_started' -and
    [bool](Get-PropertyValue -Payload $LaunchPayload -Name 'diagnostic_launch_authority' -Default $false) -and
    -not [bool](Get-PropertyValue -Payload $LaunchPayload -Name 'launch_authority' -Default $true) -and
    [string](Get-PropertyValue -Payload $Launch -Name 'status' -Default '') -eq 'started_observed' -and
    [string](Get-PropertyValue -Payload $LaunchProcess -Name 'status' -Default '') -eq 'process_observed' -and
    [string](Get-PropertyValue -Payload $LaunchProcess -Name 'state_status' -Default '') -eq 'foreground_running' -and
    [int](Get-PropertyValue -Payload $LaunchProcess -Name 'pid' -Default 0) -gt 0
  )
  $LaunchAuthorityBounded = (
    [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'diagnostic_only' -Default $false) -and
    [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'bounded_process_launch' -Default $false) -and
    [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'local_process_launch_authority' -Default $false) -and
    -not [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'product_execution_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'api_local_process_launch_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $LaunchGovernance -Name 'memory_write' -Default $true)
  )

  $FinalState = Wait-ForRuntimeState -StatePath $StatePath -Status 'foreground_stopped' -TimeoutSeconds ($RunSeconds + 10)
  $FinalStatusResult = Invoke-HostScript -PowerShellPath $PowerShellPath -HostScriptPath $HostScriptPath -ProofDataRoot $ProofDataRoot -ScriptArgs @('-Mode', 'Status')
  $FinalStatusPayload = Get-PropertyValue -Payload $FinalStatusResult -Name 'payload'
  $FinalProcessReadback = Get-PropertyValue -Payload $FinalStatusPayload -Name 'process_readback'
  $LaunchCompleted = (
    [string](Get-PropertyValue -Payload $FinalState -Name 'status' -Default '') -eq 'foreground_stopped' -and
    -not [bool](Get-PropertyValue -Payload $FinalState -Name 'process_alive' -Default $true) -and
    -not (Test-Path -LiteralPath $PidPath -PathType Leaf) -and
    [int](Get-PropertyValue -Payload $FinalStatusResult -Name 'exit_code' -Default -1) -eq 0 -and
    [string](Get-PropertyValue -Payload $FinalProcessReadback -Name 'status' -Default '') -eq 'state_present_process_not_running' -and
    [string](Get-PropertyValue -Payload $FinalProcessReadback -Name 'state_status' -Default '') -eq 'foreground_stopped'
  )
}

[void]$Checks.Add((New-Check -Id 'bounded_launch_started' -Status $(if ($LaunchObserved) { 'launch_started_observed' } else { 'not_observed' }) -Passed $LaunchObserved -Evidence 'scripts/lens-host.ps1 -Mode Launch' -Reason 'The existing launch runner must start and observe one bounded foreground host process.'))
[void]$Checks.Add((New-Check -Id 'launch_authority_boundary' -Status $(if ($LaunchAuthorityBounded) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $LaunchAuthorityBounded -Evidence 'launch.governance' -Reason 'The launch proof must remain diagnostic and must not grant product/API launch or execution authority.'))
[void]$Checks.Add((New-Check -Id 'bounded_launch_completion' -Status $(if ($LaunchCompleted) { 'self_stopped' } else { 'not_stopped' }) -Passed $LaunchCompleted -Evidence 'runtime/lens-host/status.json' -Reason 'The launched foreground host must self-stop and leave readback state only.'))

$ProofPassed = $LaunchObserved -and $LaunchAuthorityBounded -and $LaunchCompleted
$ObservedPid = [int](Get-PropertyValue -Payload $LaunchProcess -Name 'pid' -Default 0)
$FinalPid = [int](Get-PropertyValue -Payload $FinalState -Name 'pid' -Default 0)
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
  kind = 'lens.host.launch_readiness_proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  data_root = $ProofDataRoot
  run_seconds = $RunSeconds
  ready_for_resident_claim = $false
  bounded_host_launch_observed = $LaunchObserved
  launch_authority_boundary = $LaunchAuthorityBounded
  launch_completed = $LaunchCompleted
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
    launch_exit_code = [int](Get-PropertyValue -Payload $LaunchResult -Name 'exit_code' -Default -1)
    launch_status = [string](Get-PropertyValue -Payload $LaunchPayload -Name 'status' -Default '')
    launch_supported = [bool](Get-PropertyValue -Payload $LaunchPayload -Name 'launch_supported' -Default $false)
    launch_authority = [bool](Get-PropertyValue -Payload $LaunchPayload -Name 'launch_authority' -Default $true)
    diagnostic_launch_authority = [bool](Get-PropertyValue -Payload $LaunchPayload -Name 'diagnostic_launch_authority' -Default $false)
    observed_pid = $ObservedPid
    final_pid = $FinalPid
    final_state_status = [string](Get-PropertyValue -Payload $FinalState -Name 'status' -Default '')
    final_status_readback = [string](Get-PropertyValue -Payload $FinalProcessReadback -Name 'status' -Default '')
    final_status_state = [string](Get-PropertyValue -Payload $FinalProcessReadback -Name 'state_status' -Default '')
    pid_file_present_after_stop = Test-Path -LiteralPath $PidPath -PathType Leaf
  }
  governance = [ordered]@{
    diagnostic_only = $true
    bounded_host_launch = $true
    bounded_process_launch = $true
    temporary_runtime_state_write = $true
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = $true
    api_local_process_launch_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Bounded Lens host launch was observed and self-stopped; this proves diagnostic host launch readiness only, not resident supervision or product launch authority.'
}

$Payload | ConvertTo-Json -Depth 10
if ($ProofPassed) {
  exit 0
}
exit 1
