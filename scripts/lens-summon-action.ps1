[CmdletBinding()]
param(
  [ValidateSet('Status', 'Bind', 'Launch')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [ValidateRange(1, 30)]
  [int]$StartupTimeoutSeconds = 5,

  [ValidateRange(1, 60)]
  [int]$RunSeconds = 5,

  [string]$ConfigOverridePath = '',

  [string]$StatusPath = '',

  [switch]$AllowLaunch
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

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

function Invoke-JsonScript {
  param(
    [string]$ScriptPath,
    [string[]]$ScriptArgs
  )

  $PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
  if ($null -eq $PowerShell) {
    $PowerShell = Get-Command powershell -ErrorAction Stop
  }
  $Output = & $PowerShell.Source @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $ScriptPath
  ) @ScriptArgs 2>&1
  $ExitCode = $LASTEXITCODE
  $Text = ($Output | ForEach-Object { [string]$_ }) -join "`n"
  $Payload = $null
  try {
    $Payload = $Text | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $Payload = $null
  }

  return [ordered]@{
    status = if ($null -ne $Payload -and $null -ne $Payload.PSObject.Properties['status']) { [string]$Payload.status } else { '' }
    exit_code = $ExitCode
    payload = $Payload
    output = $Text
    json_parsed = $null -ne $Payload
  }
}

$ModeName = $Mode.ToLowerInvariant()
$DataRoot = Get-DataRoot -Override $DataDir
$PreflightScript = Join-Path $PSScriptRoot 'lens-summon-preflight.ps1'
$HotkeyScript = Join-Path $PSScriptRoot 'lens-hotkey-binding.ps1'
$SummonScript = Join-Path $PSScriptRoot 'lens-summon.ps1'
$PreflightMode = if ($Mode -eq 'Status') { 'Status' } else { $Mode }
$PreflightArgs = @('-Mode', $PreflightMode, '-DataDir', $DataRoot)
if (-not [string]::IsNullOrWhiteSpace($ConfigOverridePath)) {
  $PreflightArgs += @('-ConfigOverridePath', $ConfigOverridePath)
}
$PreflightResult = Invoke-JsonScript -ScriptPath $PreflightScript -ScriptArgs $PreflightArgs
$PreflightPayload = $PreflightResult.payload
$PreflightReady = (
  [bool]$PreflightResult.json_parsed -and
  [bool]$PreflightPayload.ok -and
  [string]$PreflightPayload.status -eq 'ready_for_execution'
)
$ActionGate = if ($null -ne $PreflightPayload -and $null -ne $PreflightPayload.PSObject.Properties['action_gate']) {
  $PreflightPayload.action_gate
} else {
  $null
}

$ExecutionAttempted = $false
$HotkeyBindingAttempted = $false
$LaunchAttempted = $false
$HandoffResult = [ordered]@{
  status = 'not_requested'
  exit_code = $null
  json_parsed = $false
  payload = $null
}
$ExitCode = 0
$Status = if ($Mode -eq 'Status') { [string]$PreflightPayload.status } else { 'blocked_by_preflight' }
$Ok = $Mode -eq 'Status' -and [bool]$PreflightResult.json_parsed -and $PreflightResult.exit_code -eq 0
$ErrorText = ''

if (-not [bool]$PreflightResult.json_parsed) {
  $Ok = $false
  $Status = 'preflight_json_unavailable'
  $ErrorText = 'lens_summon_preflight_json_unavailable'
  $ExitCode = 1
} elseif ($Mode -ne 'Status' -and -not $PreflightReady) {
  $Ok = $false
  $Status = 'blocked_by_preflight'
  $ErrorText = 'lens_summon_action_blocked_by_preflight'
  $ExitCode = 2
} elseif ($Mode -ne 'Status') {
  $ExecutionAttempted = $true
  if ($Mode -eq 'Bind') {
    $HotkeyBindingAttempted = $true
    $Args = @(
      '-Mode',
      'Start',
      '-DataDir',
      $DataRoot,
      '-StartupTimeoutSeconds',
      ([string]$StartupTimeoutSeconds),
      '-RunSeconds',
      ([string]$RunSeconds),
      '-NoLaunch'
    )
    if (-not [string]::IsNullOrWhiteSpace($ConfigOverridePath)) {
      $Args += @('-ConfigOverridePath', $ConfigOverridePath)
    }
    $HandoffResult = Invoke-JsonScript -ScriptPath $HotkeyScript -ScriptArgs $Args
  } else {
    $LaunchAttempted = $true
    $Args = @('-Mode', 'LocalOpen')
    if (-not [string]::IsNullOrWhiteSpace($ConfigOverridePath)) {
      $Args += @('-ConfigOverridePath', $ConfigOverridePath)
    }
    if (-not [string]::IsNullOrWhiteSpace($StatusPath)) {
      $Args += @('-StatusPath', $StatusPath)
    }
    if (-not [bool]$AllowLaunch) {
      $Args += '-NoLaunch'
    }
    $HandoffResult = Invoke-JsonScript -ScriptPath $SummonScript -ScriptArgs $Args
  }

  $Ok = $HandoffResult.exit_code -eq 0 -and [bool]$HandoffResult.json_parsed
  $Status = if ($Ok) { 'handoff_completed' } else { 'handoff_failed' }
  $ErrorText = if ($Ok) { '' } else { 'lens_summon_action_handoff_failed' }
  $ExitCode = if ($Ok) { 0 } else { 1 }
}

$Payload = [ordered]@{
  ok = $Ok
  kind = 'lens.summon.action'
  status = $Status
  mode = $ModeName
  action = $ModeName
  repo_root = $RepoRoot
  data_root = $DataRoot
  config_override_path = if (-not [string]::IsNullOrWhiteSpace($ConfigOverridePath)) { [System.IO.Path]::GetFullPath($ConfigOverridePath) } else { '' }
  status_path = if (-not [string]::IsNullOrWhiteSpace($StatusPath)) { [System.IO.Path]::GetFullPath($StatusPath) } else { '' }
  preflight_exit_code = $PreflightResult.exit_code
  preflight_ready = $PreflightReady
  preflight = $PreflightPayload
  action_gate = $ActionGate
  execution_attempted = $ExecutionAttempted
  handoff_attempted = $ExecutionAttempted
  hotkey_binding_attempted = $HotkeyBindingAttempted
  launch_attempted = $LaunchAttempted
  allow_launch = [bool]$AllowLaunch
  run_seconds = $RunSeconds
  startup_timeout_seconds = $StartupTimeoutSeconds
  bounded_handoff = [ordered]@{
    status = [string]$HandoffResult.status
    exit_code = $HandoffResult.exit_code
    json_parsed = [bool]$HandoffResult.json_parsed
    payload = $HandoffResult.payload
  }
  error = $ErrorText
  message = if ($Mode -eq 'Status') {
    'Lens summon action status consumed the preflight contract without executing a handoff.'
  } elseif (-not $PreflightReady) {
    'Lens summon action was blocked by preflight; no hotkey binding or launch was attempted.'
  } else {
    'Lens summon action consumed the preflight gate and attempted the bounded handoff.'
  }
  next_smallest_truthful_gap = if ($Ok -and $Mode -ne 'Status') { 'summon_anywhere_runtime_readback' } else { 'summon_action_preflight_blockers' }
  governance = [ordered]@{
    read_only_contract = $Mode -eq 'Status'
    action_request_gated = $Mode -ne 'Status'
    execution_authority = $ExecutionAttempted
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    summon_authority = $ExecutionAttempted -and $Mode -eq 'Launch'
    hotkey_registration_authority = $ExecutionAttempted -and $Mode -eq 'Bind'
    local_process_launch_authority = $ExecutionAttempted -and ($Mode -eq 'Bind' -or ([bool]$AllowLaunch -and $Mode -eq 'Launch'))
    service_control_authority = $false
    tray_registration_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    mutation_authority_granted = $ExecutionAttempted -and $Ok -and ($Mode -eq 'Bind' -or ([bool]$AllowLaunch -and $Mode -eq 'Launch'))
  }
}

$Payload | ConvertTo-Json -Depth 12
exit $ExitCode
