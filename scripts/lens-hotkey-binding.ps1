[CmdletBinding()]
param(
  [ValidateSet('Status', 'Start', 'Stop', 'Run')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [ValidateRange(1, 30)]
  [int]$StartupTimeoutSeconds = 5,

  [ValidateRange(0, 3600)]
  [int]$RunSeconds = 0,

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

function Get-StringProperty {
  param(
    [object]$Payload,
    [string]$Name,
    [string]$Default = ''
  )

  if ($null -eq $Payload) {
    return $Default
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) {
    return $Default
  }
  $Value = [string]$Property.Value
  if ([string]::IsNullOrWhiteSpace($Value)) {
    return $Default
  }
  return $Value
}

function Get-IntegerProperty {
  param(
    [object]$Payload,
    [string]$Name,
    [int]$Default = 0
  )

  $Value = Get-StringProperty -Payload $Payload -Name $Name -Default ''
  if ([string]::IsNullOrWhiteSpace($Value)) {
    return $Default
  }
  try {
    return [int]$Value
  } catch {
    return $Default
  }
}

function Get-BoolProperty {
  param(
    [object]$Payload,
    [string]$Name,
    [bool]$Default = $false
  )

  if ($null -eq $Payload) {
    return $Default
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) {
    return $Default
  }
  if ($Property.Value -is [bool]) {
    return [bool]$Property.Value
  }
  $Value = [string]$Property.Value
  if ([string]::IsNullOrWhiteSpace($Value)) {
    return $Default
  }
  return $Value.ToLowerInvariant() -eq 'true'
}

function Get-ProcessAlive {
  param([int]$ProcessId)

  if ($ProcessId -le 0) {
    return $false
  }
  try {
    return $null -ne (Get-Process -Id $ProcessId -ErrorAction Stop)
  } catch {
    return $false
  }
}

function Get-HotkeyConfig {
  $ConfigPath = Join-Path $RepoRoot 'config\runtime\lens\summon.json'
  $Config = Read-JsonFile -Path $ConfigPath
  return [ordered]@{
    path = $ConfigPath
    payload = $Config
    global_hotkey = Get-StringProperty -Payload $Config -Name 'global_hotkey' -Default 'Ctrl+Alt+Space'
    binding_scope = Get-StringProperty -Payload $Config -Name 'binding_scope' -Default 'global'
    summon_runner = Get-StringProperty -Payload $Config -Name 'summon_runner' -Default 'scripts/lens-summon.ps1'
  }
}

function Write-HotkeyState {
  param(
    [string]$Root,
    [string]$Status,
    [bool]$HotkeyBound,
    [string]$Message = '',
    [bool]$LaunchOnHotkey = $false,
    [int]$PressCount = 0
  )

  $Config = Get-HotkeyConfig
  $RuntimeRoot = Join-Path $Root 'runtime\lens-hotkey'
  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  $PidPath = Join-Path $RuntimeRoot 'lens-hotkey.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  if ($Status -eq 'hotkey_bound') {
    Set-Content -LiteralPath $PidPath -Value ([string]$PID) -Encoding UTF8
  }
  $Payload = [ordered]@{
    kind = 'lens.hotkey.runtime_state'
    status = $Status
    pid = $PID
    global_hotkey = $Config.global_hotkey
    binding_scope = $Config.binding_scope
    hotkey_bound = $HotkeyBound
    launch_on_hotkey = $LaunchOnHotkey
    summon_runner = $Config.summon_runner
    press_count = $PressCount
    updated_at = [DateTimeOffset]::UtcNow.ToString('o')
    message = $Message
    governance = [ordered]@{
      execution_authority = $false
      approval_decision_authority = $false
      memory_write = $false
      overlay_control_authority = $false
      summon_authority = $false
      hotkey_registration_authority = $HotkeyBound
      local_process_launch_authority = $LaunchOnHotkey
      tray_registration_authority = $false
      service_control_authority = $false
      capture_authority = $false
      new_sensing_authority = $false
      mutation_authority_granted = $HotkeyBound
    }
  }
  $Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $StatusPath -Encoding UTF8
}

function Get-HotkeyRuntimeReadback {
  param([string]$Root)

  $Config = Get-HotkeyConfig
  $RuntimeRoot = Join-Path $Root 'runtime\lens-hotkey'
  $PidPath = Join-Path $RuntimeRoot 'lens-hotkey.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  $Status = Read-JsonFile -Path $StatusPath
  $StatusKind = Get-StringProperty -Payload $Status -Name 'kind' -Default ''
  $StatusValue = Get-StringProperty -Payload $Status -Name 'status' -Default ''
  $StatusPid = Get-IntegerProperty -Payload $Status -Name 'pid' -Default 0
  $RuntimeStateExists = Test-Path -LiteralPath $StatusPath -PathType Leaf
  $PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf
  $RuntimePid = 0
  if ($PidPresent) {
    try {
      $RuntimePid = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
    } catch {
      $RuntimePid = 0
    }
  }

  $StatusClaimsBoundHotkey = (
    $StatusKind -eq 'lens.hotkey.runtime_state' -and
    $StatusValue -eq 'hotkey_bound' -and
    $StatusPid -gt 0 -and
    $StatusPid -eq $RuntimePid -and
    (Get-BoolProperty -Payload $Status -Name 'hotkey_bound' -Default $false) -and
    (Get-StringProperty -Payload $Status -Name 'global_hotkey' -Default '') -eq $Config.global_hotkey -and
    (Get-StringProperty -Payload $Status -Name 'binding_scope' -Default '') -eq $Config.binding_scope
  )
  $ProcessAlive = if ($StatusClaimsBoundHotkey) { Get-ProcessAlive -ProcessId $RuntimePid } else { $false }
  $Ready = $ProcessAlive -and $StatusClaimsBoundHotkey
  $RequirementState = if ($Ready) {
    'bound'
  } elseif ($ProcessAlive) {
    'process_running_no_bound_hotkey_claim'
  } elseif ($RuntimeStateExists -or $PidPresent) {
    'stale_or_unverified'
  } else {
    'missing'
  }
  $Blocker = if ($Ready) {
    ''
  } elseif ($ProcessAlive) {
    'global_hotkey_binding_not_observed'
  } else {
    'global_hotkey_binding_runtime_missing'
  }

  return [ordered]@{
    ready = $Ready
    process_alive = $ProcessAlive
    hotkey_bound = $Ready
    pid = $RuntimePid
    pid_present = $PidPresent
    status_path = $StatusPath
    pid_path = $PidPath
    runtime_state_exists = $RuntimeStateExists
    runtime_status = $StatusValue
    runtime_status_kind = $StatusKind
    runtime_status_pid = $StatusPid
    runtime_status_pid_matches_pid_file = ($StatusPid -gt 0 -and $StatusPid -eq $RuntimePid)
    global_hotkey = $Config.global_hotkey
    binding_scope = $Config.binding_scope
    launch_on_hotkey = Get-BoolProperty -Payload $Status -Name 'launch_on_hotkey' -Default $false
    summon_runner = $Config.summon_runner
    press_count = Get-IntegerProperty -Payload $Status -Name 'press_count' -Default 0
    requirement_state = $RequirementState
    blocker = $Blocker
  }
}

function New-StatusPayload {
  param(
    [string]$Root,
    [string]$ModeName,
    [string]$StatusOverride = ''
  )

  $Readback = Get-HotkeyRuntimeReadback -Root $Root
  $Ready = [bool]$Readback.ready
  return [ordered]@{
    ok = $true
    kind = 'lens.hotkey.binding.runtime'
    status = if ($StatusOverride) { $StatusOverride } elseif ($Ready) { 'bound' } else { 'missing' }
    mode = $ModeName
    ready = $Ready
    global_hotkey_binding = $Ready
    summon_anywhere = $false
    data_root = $Root
    runtime_state_path = 'data/runtime/lens-hotkey/status.json'
    pid_path = 'data/runtime/lens-hotkey/lens-hotkey.pid'
    hotkey_runtime = $Readback
    next_smallest_truthful_gap = if ($Ready) { 'summon_binding' } else { 'global_hotkey_binding' }
    governance = [ordered]@{
      read_only_contract = ($ModeName -eq 'status')
      execution_authority = $false
      approval_decision_authority = $false
      memory_write = $false
      overlay_control_authority = $false
      summon_authority = $false
      capture_authority = $false
      new_sensing_authority = $false
      local_process_launch_authority = ($ModeName -eq 'start' -and -not [bool]$NoLaunch)
      service_control_authority = $false
      hotkey_registration_authority = ($ModeName -eq 'start')
      tray_registration_authority = $false
      mutation_authority_granted = ($ModeName -eq 'start' -or $ModeName -eq 'stop')
    }
    message = if ($Ready) { 'Lens global hotkey binding runtime is live.' } else { 'Lens global hotkey binding runtime is not live.' }
  }
}

function Add-HotkeyTypes {
  Add-Type -AssemblyName System.Windows.Forms
  Add-Type -ReferencedAssemblies 'System.Windows.Forms' -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Windows.Forms;

public static class FrancisLensHotkeyNative {
  [DllImport("user32.dll", SetLastError = true)]
  public static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);

  [DllImport("user32.dll", SetLastError = true)]
  public static extern bool UnregisterHotKey(IntPtr hWnd, int id);
}

public sealed class FrancisLensHotkeyWindow : NativeWindow {
  public event EventHandler HotkeyPressed;
  private const int WM_HOTKEY = 0x0312;

  protected override void WndProc(ref Message m) {
    if (m.Msg == WM_HOTKEY && HotkeyPressed != null) {
      HotkeyPressed(this, EventArgs.Empty);
    }
    base.WndProc(ref m);
  }
}
'@
}

$DataRoot = Get-DataRoot -Override $DataDir
$ModeName = $Mode.ToLowerInvariant()
$RunningOnWindows = [System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT

if ($Mode -eq 'Run') {
  $RuntimeRoot = Join-Path $DataRoot 'runtime\lens-hotkey'
  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  $Window = $null
  $Timer = $null
  $Registered = $false
  $PressCount = 0
  $LaunchOnHotkey = -not [bool]$NoLaunch
  $Failed = $false
  try {
    if (-not $RunningOnWindows) {
      Write-HotkeyState -Root $DataRoot -Status 'unsupported' -HotkeyBound $false -Message 'Windows global hotkey binding requires Windows.'
      exit 3
    }
    Add-HotkeyTypes
    [System.Windows.Forms.Application]::EnableVisualStyles()
    $Window = New-Object FrancisLensHotkeyWindow
    $CreateParams = New-Object System.Windows.Forms.CreateParams
    $Window.CreateHandle($CreateParams)
    $Window.add_HotkeyPressed([EventHandler]{
        $script:PressCount += 1
        Write-HotkeyState -Root $script:DataRoot -Status 'hotkey_bound' -HotkeyBound $true -Message 'Francis Lens global hotkey was pressed.' -LaunchOnHotkey $script:LaunchOnHotkey -PressCount $script:PressCount
        if ($script:LaunchOnHotkey) {
          $SummonScript = Join-Path $script:PSScriptRoot 'lens-summon.ps1'
          Start-Process -FilePath 'powershell' -ArgumentList @(
            '-NoProfile',
            '-ExecutionPolicy',
            'Bypass',
            '-File',
            $SummonScript,
            '-Mode',
            'LocalOpen'
          ) -WindowStyle Hidden
        }
      })
    $Registered = [FrancisLensHotkeyNative]::RegisterHotKey($Window.Handle, 1, 0x0003, 0x20)
    if (-not $Registered) {
      $ErrorCode = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
      Write-HotkeyState -Root $DataRoot -Status 'failed' -HotkeyBound $false -Message "RegisterHotKey failed with Win32 error $ErrorCode."
      exit 1
    }
    Write-HotkeyState -Root $DataRoot -Status 'hotkey_bound' -HotkeyBound $true -Message 'Francis Lens global hotkey binding is running.' -LaunchOnHotkey $LaunchOnHotkey -PressCount $PressCount
    if ($RunSeconds -gt 0) {
      $Timer = New-Object System.Windows.Forms.Timer
      $Timer.Interval = [Math]::Max(1000, $RunSeconds * 1000)
      $Timer.Add_Tick({
          $Timer.Stop()
          [System.Windows.Forms.Application]::ExitThread()
        })
      $Timer.Start()
    }
    [System.Windows.Forms.Application]::Run()
  } catch {
    $Failed = $true
    Write-HotkeyState -Root $DataRoot -Status 'failed' -HotkeyBound $false -Message ([string]$_.Exception.Message)
    exit 1
  } finally {
    if ($Registered -and $null -ne $Window) {
      [void][FrancisLensHotkeyNative]::UnregisterHotKey($Window.Handle, 1)
    }
    if ($null -ne $Window) {
      $Window.DestroyHandle()
    }
    if ($null -ne $Timer) {
      $Timer.Dispose()
    }
    if (-not $Failed) {
      Write-HotkeyState -Root $DataRoot -Status 'hotkey_stopped' -HotkeyBound $false -Message 'Francis Lens global hotkey binding stopped.' -LaunchOnHotkey $false -PressCount $PressCount
    }
    Remove-Item -LiteralPath (Join-Path $DataRoot 'runtime\lens-hotkey\lens-hotkey.pid') -Force -ErrorAction SilentlyContinue
  }
  exit 0
}

if ($Mode -eq 'Status') {
  New-StatusPayload -Root $DataRoot -ModeName $ModeName | ConvertTo-Json -Depth 8
  exit 0
}

if ($Mode -eq 'Stop') {
  $Readback = Get-HotkeyRuntimeReadback -Root $DataRoot
  $RuntimePidToStop = [int]$Readback.pid
  if ([bool]$Readback.process_alive -and $RuntimePidToStop -gt 0) {
    Stop-Process -Id $RuntimePidToStop -Force -ErrorAction Stop
  }
  Write-HotkeyState -Root $DataRoot -Status 'hotkey_stopped' -HotkeyBound $false -Message 'Francis Lens global hotkey binding stopped by operator command.'
  Remove-Item -LiteralPath (Join-Path $DataRoot 'runtime\lens-hotkey\lens-hotkey.pid') -Force -ErrorAction SilentlyContinue
  New-StatusPayload -Root $DataRoot -ModeName $ModeName -StatusOverride 'stopped' | ConvertTo-Json -Depth 8
  exit 0
}

if (-not $RunningOnWindows) {
  $Payload = New-StatusPayload -Root $DataRoot -ModeName $ModeName -StatusOverride 'refused'
  $Payload.ok = $false
  $Payload.error = 'lens_hotkey_binding_unsupported_platform'
  $Payload.message = 'Lens global hotkey binding Start is only supported on Windows user sessions.'
  $Payload | ConvertTo-Json -Depth 8
  exit 2
}

$Existing = Get-HotkeyRuntimeReadback -Root $DataRoot
if ([bool]$Existing.ready) {
  New-StatusPayload -Root $DataRoot -ModeName $ModeName -StatusOverride 'already_running' | ConvertTo-Json -Depth 8
  exit 0
}

$PowerShell = Get-Command powershell -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command pwsh -ErrorAction Stop
}
$ArgumentList = @(
  '-NoProfile',
  '-ExecutionPolicy',
  'Bypass',
  '-STA',
  '-File',
  $PSCommandPath,
  '-Mode',
  'Run',
  '-DataDir',
  $DataRoot,
  '-RunSeconds',
  ([string]$RunSeconds)
)
if ($NoLaunch) {
  $ArgumentList += '-NoLaunch'
}
Start-Process -FilePath $PowerShell.Source -ArgumentList $ArgumentList -WindowStyle Hidden | Out-Null

$Deadline = [DateTimeOffset]::UtcNow.AddSeconds($StartupTimeoutSeconds)
do {
  Start-Sleep -Milliseconds 200
  $Readback = Get-HotkeyRuntimeReadback -Root $DataRoot
  if ([bool]$Readback.ready) {
    New-StatusPayload -Root $DataRoot -ModeName $ModeName -StatusOverride 'started' | ConvertTo-Json -Depth 8
    exit 0
  }
} while ([DateTimeOffset]::UtcNow -lt $Deadline)

$Payload = New-StatusPayload -Root $DataRoot -ModeName $ModeName -StatusOverride 'start_timeout'
$Payload.ok = $false
$Payload.error = 'lens_hotkey_binding_start_timeout'
$Payload.message = 'Lens global hotkey binding did not report a live bound hotkey before the startup timeout.'
$Payload | ConvertTo-Json -Depth 8
exit 1
