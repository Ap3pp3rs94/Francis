[CmdletBinding()]
param(
  [ValidateSet('Status', 'Start', 'Stop', 'Run')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [ValidateRange(1, 30)]
  [int]$StartupTimeoutSeconds = 10,

  [ValidateRange(0, 3600)]
  [int]$RunSeconds = 30,

  [switch]$NoLaunch
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

function ConvertTo-StringArray {
  param([AllowNull()][object]$Value)

  if ($null -eq $Value) {
    return @()
  }
  if ($Value -is [System.Array]) {
    return @($Value | ForEach-Object {
        $Item = [string]$_
        if (-not [string]::IsNullOrWhiteSpace($Item)) {
          $Item
        }
      })
  }
  $Single = [string]$Value
  if ([string]::IsNullOrWhiteSpace($Single)) {
    return @()
  }
  return @($Single)
}

function Get-PowerShellPath {
  $PowerShell = Get-Command powershell -ErrorAction SilentlyContinue
  if ($null -ne $PowerShell) {
    return [string]$PowerShell.Source
  }
  $Pwsh = Get-Command pwsh -ErrorAction Stop
  return [string]$Pwsh.Source
}

function Invoke-JsonRuntime {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ScriptName,

    [Parameter(Mandatory = $true)]
    [string[]]$ScriptArgs
  )

  $ScriptPath = Join-Path $PSScriptRoot $ScriptName
  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
      error = "script_unavailable:$ScriptName"
    }
  }

  $Output = & $PowerShellPath -NoProfile -ExecutionPolicy Bypass -File $ScriptPath @ScriptArgs 2>&1
  $ExitCode = $LASTEXITCODE
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
    error = ''
  }
}

function New-ComponentReadback {
  param(
    [string]$Id,
    [object]$Result
  )

  $Payload = Get-PropertyValue -Payload $Result -Name 'payload'
  $Blockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Payload -Name 'blockers')
  $Blocker = [string](Get-PropertyValue -Payload $Payload -Name 'blocker' -Default '')
  if (-not [string]::IsNullOrWhiteSpace($Blocker)) {
    $Blockers = @($Blockers + $Blocker | Select-Object -Unique)
  }

  return [ordered]@{
    id = $Id
    exit_code = [int](Get-PropertyValue -Payload $Result -Name 'exit_code' -Default 1)
    kind = [string](Get-PropertyValue -Payload $Payload -Name 'kind' -Default '')
    status = [string](Get-PropertyValue -Payload $Payload -Name 'status' -Default 'missing')
    ready = [bool](Get-PropertyValue -Payload $Payload -Name 'ready' -Default $false)
    process_alive = [bool](Get-PropertyValue -Payload $Payload -Name 'process_alive' -Default $false)
    pid = [int](Get-PropertyValue -Payload $Payload -Name 'pid' -Default 0)
    blockers = [string[]]@($Blockers)
    payload = $Payload
  }
}

function Get-StatusReadback {
  $Tray = Invoke-JsonRuntime -ScriptName 'lens-tray-presence.ps1' -ScriptArgs @(
    '-Mode', 'Status',
    '-DataDir', $DataRoot
  )
  $HotkeyArgs = @(
    '-Mode', 'Status',
    '-DataDir', $DataRoot
  )
  $Hotkey = Invoke-JsonRuntime -ScriptName 'lens-hotkey-binding.ps1' -ScriptArgs $HotkeyArgs
  $Overlay = Invoke-JsonRuntime -ScriptName 'lens-overlay-window.ps1' -ScriptArgs @(
    '-Mode', 'Status',
    '-DataDir', $DataRoot
  )

  $Components = @(
    (New-ComponentReadback -Id 'tray_presence' -Result $Tray),
    (New-ComponentReadback -Id 'global_hotkey_binding' -Result $Hotkey),
    (New-ComponentReadback -Id 'overlay_window' -Result $Overlay)
  )
  $ReadyComponents = @($Components | Where-Object { [bool]$_['ready'] })
  $FailedComponents = @($Components | Where-Object { [int]$_['exit_code'] -ne 0 })
  $Blockers = @(
    $Components | ForEach-Object {
      if (-not [bool]$_['ready']) {
        [string]$_['id'] + '_runtime_missing'
      }
      ConvertTo-StringArray -Value $_['blockers']
    }
  ) | Select-Object -Unique
  $Ready = @($ReadyComponents).Count -eq @($Components).Count

  return [ordered]@{
    ok = @($FailedComponents).Count -eq 0
    kind = 'lens.stage6.surface_runtime'
    status = if ($Ready) { 'running' } elseif (@($FailedComponents).Count -gt 0) { 'degraded' } else { 'missing' }
    mode = $Mode.ToLowerInvariant()
    repo_root = $RepoRoot
    data_root = $DataRoot
    stage = 'Stage 6 / Lens MVP'
    acceptance_criteria = @('summon_anywhere', 'helpful_not_noisy', 'system_resident_presence')
    ready = $Ready
    ready_total = @($ReadyComponents).Count
    component_total = @($Components).Count
    blocked_components = [string[]]@($Components | Where-Object { -not [bool]$_['ready'] } | ForEach-Object { [string]$_['id'] })
    components = @($Components)
    blockers = [string[]]@($Blockers)
    next_smallest_truthful_gap = if ($Ready) {
      'stage6_lens_completion_audit'
    } else {
      'stage6_surface_runtime_activation'
    }
    governance = [ordered]@{
      diagnostic_only = $true
      local_runtime_coordinator = $true
      bounded_runtime_window = $RunSeconds -gt 0
      execution_authority = $false
      approval_decision_authority = $false
      memory_write = $false
      process_supervision_authority = $false
      process_restart_authority = $false
      service_install_authority = $false
      service_control_authority = $false
      tray_registration_authority = $false
      hotkey_registration_authority = $false
      overlay_control_authority = $false
      summon_authority = $false
      resident_claim_authority = $false
      mutation_authority_granted = $false
    }
  }
}

$DataRoot = Get-DataRoot -Override $DataDir
$PowerShellPath = Get-PowerShellPath

if ($Mode -eq 'Status') {
  Get-StatusReadback | ConvertTo-Json -Depth 10
  exit 0
}

if ($Mode -eq 'Stop') {
  $OverlayStop = Invoke-JsonRuntime -ScriptName 'lens-overlay-window.ps1' -ScriptArgs @(
    '-Mode', 'Stop',
    '-DataDir', $DataRoot
  )
  $HotkeyStop = Invoke-JsonRuntime -ScriptName 'lens-hotkey-binding.ps1' -ScriptArgs @(
    '-Mode', 'Stop',
    '-DataDir', $DataRoot
  )
  $TrayStop = Invoke-JsonRuntime -ScriptName 'lens-tray-presence.ps1' -ScriptArgs @(
    '-Mode', 'Stop',
    '-DataDir', $DataRoot
  )
  $Status = Get-StatusReadback
  $Status['mode'] = 'stop'
  $Status['status'] = 'stopped'
  $Status['stop_results'] = @(
    (New-ComponentReadback -Id 'overlay_window' -Result $OverlayStop),
    (New-ComponentReadback -Id 'global_hotkey_binding' -Result $HotkeyStop),
    (New-ComponentReadback -Id 'tray_presence' -Result $TrayStop)
  )
  $Status | ConvertTo-Json -Depth 10
  exit 0
}

if ($Mode -eq 'Start' -or $Mode -eq 'Run') {
  $TrayStart = Invoke-JsonRuntime -ScriptName 'lens-tray-presence.ps1' -ScriptArgs @(
    '-Mode', 'Start',
    '-DataDir', $DataRoot,
    '-StartupTimeoutSeconds', ([string]$StartupTimeoutSeconds),
    '-RunSeconds', ([string]$RunSeconds)
  )
  $HotkeyArgs = @(
    '-Mode', 'Start',
    '-DataDir', $DataRoot,
    '-StartupTimeoutSeconds', ([string]$StartupTimeoutSeconds),
    '-RunSeconds', ([string]$RunSeconds)
  )
  if ($NoLaunch) {
    $HotkeyArgs += '-NoLaunch'
  }
  $HotkeyStart = Invoke-JsonRuntime -ScriptName 'lens-hotkey-binding.ps1' -ScriptArgs $HotkeyArgs
  $OverlayStart = Invoke-JsonRuntime -ScriptName 'lens-overlay-window.ps1' -ScriptArgs @(
    '-Mode', 'Start',
    '-DataDir', $DataRoot,
    '-StartupTimeoutSeconds', ([string]$StartupTimeoutSeconds),
    '-RunSeconds', ([string]$RunSeconds)
  )

  $Status = Get-StatusReadback
  $Status['mode'] = $Mode.ToLowerInvariant()
  $Status['status'] = if ([bool]$Status['ready']) { 'started' } else { 'start_incomplete' }
  $Status['start_results'] = @(
    (New-ComponentReadback -Id 'tray_presence' -Result $TrayStart),
    (New-ComponentReadback -Id 'global_hotkey_binding' -Result $HotkeyStart),
    (New-ComponentReadback -Id 'overlay_window' -Result $OverlayStart)
  )

  if ($Mode -eq 'Run') {
    $SleepSeconds = [Math]::Max(1, $RunSeconds)
    Start-Sleep -Seconds $SleepSeconds
    $BeforeStop = Get-StatusReadback
    $Stop = & $PowerShellPath -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath -Mode Stop -DataDir $DataRoot | ConvertFrom-Json
    $Status['mode'] = 'run'
    $Status['status_before_stop'] = $BeforeStop.status
    $Status['ready_before_stop'] = [bool]$BeforeStop.ready
    $Status['stop'] = $Stop
  }

  $Status | ConvertTo-Json -Depth 10
  exit $(if ([bool]$Status['ready'] -or $Mode -eq 'Run') { 0 } else { 1 })
}
