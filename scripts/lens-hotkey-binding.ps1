[CmdletBinding()]
param(
  [ValidateSet('Status', 'Start', 'Stop', 'Run')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [ValidateRange(1, 30)]
  [int]$StartupTimeoutSeconds = 5,

  [ValidateRange(0, 3600)]
  [int]$RunSeconds = 0,

  [string]$ConfigOverridePath = '',

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

function Write-TextFileWithRetry {
  param(
    [string]$Path,
    [string]$Value,
    [ValidateRange(1, 100)]
    [int]$Attempts = 20,
    [ValidateRange(1, 5000)]
    [int]$DelayMilliseconds = 100
  )

  $Directory = Split-Path -Parent $Path
  if (-not [string]::IsNullOrWhiteSpace($Directory)) {
    New-Item -ItemType Directory -Force -Path $Directory | Out-Null
  }

  $LastError = $null
  for ($Attempt = 1; $Attempt -le $Attempts; $Attempt++) {
    $TempPath = "$Path.$PID.$([Guid]::NewGuid().ToString('N')).tmp"
    try {
      $Utf8NoBom = New-Object System.Text.UTF8Encoding $false
      [System.IO.File]::WriteAllText($TempPath, $Value, $Utf8NoBom)
      Move-Item -LiteralPath $TempPath -Destination $Path -Force -ErrorAction Stop
      return
    } catch {
      $LastError = $_
      Remove-Item -LiteralPath $TempPath -Force -ErrorAction SilentlyContinue
      if ($Attempt -lt $Attempts) {
        Start-Sleep -Milliseconds $DelayMilliseconds
      }
    }
  }

  throw $LastError
}

function Get-HotkeyConfig {
  $ConfigPath = if (-not [string]::IsNullOrWhiteSpace($ConfigOverridePath)) {
    [System.IO.Path]::GetFullPath($ConfigOverridePath)
  } else {
    Join-Path $RepoRoot 'config\runtime\lens\summon.json'
  }
  $Config = Read-JsonFile -Path $ConfigPath
  $BlockedReason = 'lens_summon_binding_disabled_pending_authority'
  if ($null -ne $Config) {
    $BlockedReasonProperty = $Config.PSObject.Properties['blocked_reason']
    if ($null -ne $BlockedReasonProperty -and $null -ne $BlockedReasonProperty.Value) {
      $BlockedReason = [string]$BlockedReasonProperty.Value
    }
  }
  return [ordered]@{
    path = $ConfigPath
    exists = Test-Path -LiteralPath $ConfigPath -PathType Leaf
    payload = $Config
    global_hotkey = Get-StringProperty -Payload $Config -Name 'global_hotkey' -Default 'Ctrl+Alt+Space'
    binding_scope = Get-StringProperty -Payload $Config -Name 'binding_scope' -Default 'global'
    summon_runner = Get-StringProperty -Payload $Config -Name 'summon_runner' -Default 'scripts/lens-summon.ps1'
    blocked_reason = $BlockedReason
    binding_enabled = Get-BoolProperty -Payload $Config -Name 'binding_enabled' -Default $false
    register_hotkey = Get-BoolProperty -Payload $Config -Name 'register_hotkey' -Default $false
    summon_authority = Get-BoolProperty -Payload $Config -Name 'summon_authority' -Default $false
    hotkey_registration_authority = Get-BoolProperty -Payload $Config -Name 'hotkey_registration_authority' -Default $false
    overlay_control_authority = Get-BoolProperty -Payload $Config -Name 'overlay_control_authority' -Default $false
    local_process_launch_authority = Get-BoolProperty -Payload $Config -Name 'local_process_launch_authority' -Default $false
  }
}

function Get-HotkeyStartBlockers {
  param(
    [object]$Config,
    [bool]$LaunchOnHotkey
  )

  $Blockers = [System.Collections.ArrayList]::new()
  if (-not [bool]$Config.exists) {
    [void]$Blockers.Add('lens_summon_config_missing')
  }
  if (-not [string]::IsNullOrWhiteSpace([string]$Config.blocked_reason)) {
    [void]$Blockers.Add([string]$Config.blocked_reason)
  }
  if (-not [bool]$Config.binding_enabled) {
    [void]$Blockers.Add('global_hotkey_binding_disabled')
  }
  if (-not [bool]$Config.register_hotkey) {
    [void]$Blockers.Add('global_hotkey_registration_disabled')
  }
  if (-not [bool]$Config.hotkey_registration_authority) {
    [void]$Blockers.Add('hotkey_registration_authority_not_granted')
  }
  if ($LaunchOnHotkey) {
    if (-not [bool]$Config.summon_authority) {
      [void]$Blockers.Add('summon_authority_not_granted')
    }
    if (-not [bool]$Config.overlay_control_authority) {
      [void]$Blockers.Add('overlay_control_authority_not_granted')
    }
    if (-not [bool]$Config.local_process_launch_authority) {
      [void]$Blockers.Add('local_process_launch_authority_not_granted')
    }
  }
  return [string[]]@($Blockers.ToArray())
}

function Resolve-HotkeyKeyCode {
  param([string]$KeyName)

  $Key = ([string]$KeyName).Trim().ToUpperInvariant()
  if ($Key.Length -eq 1) {
    $CodePoint = [int][char]$Key[0]
    if (($CodePoint -ge [int][char]'A' -and $CodePoint -le [int][char]'Z') -or ($CodePoint -ge [int][char]'0' -and $CodePoint -le [int][char]'9')) {
      return [ordered]@{ ok = $true; value = [uint32]$CodePoint }
    }
  }
  if ($Key -match '^F([1-9]|1[0-9]|2[0-4])$') {
    $Number = [int]$Matches[1]
    return [ordered]@{ ok = $true; value = [uint32](0x70 + $Number - 1) }
  }

  $NamedKeys = @{
    SPACE = 0x20
    ENTER = 0x0D
    RETURN = 0x0D
    ESC = 0x1B
    ESCAPE = 0x1B
    TAB = 0x09
    BACKSPACE = 0x08
    DELETE = 0x2E
    DEL = 0x2E
    INSERT = 0x2D
    INS = 0x2D
    HOME = 0x24
    END = 0x23
    PAGEUP = 0x21
    PGUP = 0x21
    PAGEDOWN = 0x22
    PGDN = 0x22
    LEFT = 0x25
    UP = 0x26
    RIGHT = 0x27
    DOWN = 0x28
  }
  if ($NamedKeys.ContainsKey($Key)) {
    return [ordered]@{ ok = $true; value = [uint32]$NamedKeys[$Key] }
  }

  return [ordered]@{ ok = $false; value = [uint32]0 }
}

function Resolve-HotkeyRegistration {
  param([string]$GlobalHotkey)

  $Text = ([string]$GlobalHotkey).Trim()
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return [ordered]@{ ok = $false; modifiers = [uint32]0; virtual_key = [uint32]0; error = 'global_hotkey_not_declared' }
  }

  $Modifiers = [uint32]0
  $KeyCode = [uint32]0
  $Parts = [string[]]@($Text -split '\+' | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_ })
  foreach ($Part in $Parts) {
    switch -Regex ($Part.ToUpperInvariant()) {
      '^(CTRL|CONTROL)$' {
        $Modifiers = $Modifiers -bor [uint32]0x0002
        continue
      }
      '^ALT$' {
        $Modifiers = $Modifiers -bor [uint32]0x0001
        continue
      }
      '^SHIFT$' {
        $Modifiers = $Modifiers -bor [uint32]0x0004
        continue
      }
      '^(WIN|WINDOWS|META)$' {
        $Modifiers = $Modifiers -bor [uint32]0x0008
        continue
      }
      default {
        if ($KeyCode -ne 0) {
          return [ordered]@{ ok = $false; modifiers = $Modifiers; virtual_key = $KeyCode; error = 'global_hotkey_multiple_keys' }
        }
        $ResolvedKey = Resolve-HotkeyKeyCode -KeyName $Part
        if (-not [bool]$ResolvedKey.ok) {
          return [ordered]@{ ok = $false; modifiers = $Modifiers; virtual_key = [uint32]0; error = 'global_hotkey_key_unsupported' }
        }
        $KeyCode = [uint32]$ResolvedKey.value
      }
    }
  }

  if ($Modifiers -eq 0) {
    return [ordered]@{ ok = $false; modifiers = $Modifiers; virtual_key = $KeyCode; error = 'global_hotkey_modifier_required' }
  }
  if ($KeyCode -eq 0) {
    return [ordered]@{ ok = $false; modifiers = $Modifiers; virtual_key = $KeyCode; error = 'global_hotkey_key_required' }
  }

  return [ordered]@{ ok = $true; modifiers = $Modifiers; virtual_key = $KeyCode; error = '' }
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
    Write-TextFileWithRetry -Path $PidPath -Value ([string]$PID)
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
  Write-TextFileWithRetry -Path $StatusPath -Value ($Payload | ConvertTo-Json -Depth 8)
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
  $StatusMessage = Get-StringProperty -Payload $Status -Name 'message' -Default ''
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
    runtime_status_message = $StatusMessage
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
  $LaunchOnHotkeyReady = $Ready -and [bool]$Readback.launch_on_hotkey
  return [ordered]@{
    ok = $true
    kind = 'lens.hotkey.binding.runtime'
    status = if ($StatusOverride) { $StatusOverride } elseif ($Ready) { 'bound' } else { 'missing' }
    mode = $ModeName
    ready = $Ready
    global_hotkey_binding = $Ready
    summon_anywhere = $LaunchOnHotkeyReady
    os_level_summon = $LaunchOnHotkeyReady
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
$LaunchOnHotkey = -not [bool]$NoLaunch
$ConfigForAction = Get-HotkeyConfig
$StartBlockers = if ($Mode -eq 'Start' -or $Mode -eq 'Run') {
  Get-HotkeyStartBlockers -Config $ConfigForAction -LaunchOnHotkey $LaunchOnHotkey
} else {
  [string[]]@()
}

if (@($StartBlockers).Count -gt 0) {
  $RequiredAuthorities = [string[]]@('hotkey_registration_authority')
  if ($LaunchOnHotkey) {
    $RequiredAuthorities = [string[]]@(
      'hotkey_registration_authority',
      'summon_authority',
      'overlay_control_authority',
      'local_process_launch_authority'
    )
  }
  $MissingAuthorities = [string[]]@(
    $StartBlockers | Where-Object { [string]$_ -like '*_authority_not_granted' }
  )
  $Payload = New-StatusPayload -Root $DataRoot -ModeName $ModeName -StatusOverride 'blocked_by_config'
  $Payload.ok = $false
  $Payload.error = "lens_hotkey_binding_${ModeName}_blocked_by_config"
  $Payload.config_path = [string]$ConfigForAction.path
  $Payload.blockers = [string[]]@($StartBlockers)
  $Payload.required_authorities = $RequiredAuthorities
  $Payload.missing_authorities = $MissingAuthorities
  $Payload.would_register_hotkey = $false
  $Payload.would_launch_process = $false
  $Payload.governance.hotkey_registration_authority = $false
  $Payload.governance.local_process_launch_authority = $false
  $Payload.governance.mutation_authority_granted = $false
  $Payload.message = 'Lens global hotkey binding start is blocked by summon config; no hotkey registration or launch runtime was attempted.'
  $Payload | ConvertTo-Json -Depth 8
  exit 2
}

if ($Mode -eq 'Run') {
  $RuntimeRoot = Join-Path $DataRoot 'runtime\lens-hotkey'
  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  $Window = $null
  $MainForm = $null
  $Timer = $null
  $Registered = $false
  $PressCount = 0
  $Failed = $false
  try {
    if (-not $RunningOnWindows) {
      $Failed = $true
      Write-HotkeyState -Root $DataRoot -Status 'unsupported' -HotkeyBound $false -Message 'Windows global hotkey binding requires Windows.'
      exit 3
    }
    Add-HotkeyTypes
    Add-Type -AssemblyName System.Drawing
    [System.Windows.Forms.Application]::EnableVisualStyles()
    $MainForm = New-Object System.Windows.Forms.Form
    $MainForm.Text = 'Francis Lens Hotkey Binding'
    $MainForm.ShowInTaskbar = $false
    $MainForm.WindowState = [System.Windows.Forms.FormWindowState]::Minimized
    $MainForm.Opacity = 0
    $MainForm.Size = New-Object System.Drawing.Size(0, 0)
    $MainForm.Add_Shown({
        $MainForm.Hide()
      })
    $Window = New-Object FrancisLensHotkeyWindow
    $CreateParams = New-Object System.Windows.Forms.CreateParams
    $Window.CreateHandle($CreateParams)
    $Window.add_HotkeyPressed([EventHandler]{
        $script:PressCount += 1
        Write-HotkeyState -Root $script:DataRoot -Status 'hotkey_bound' -HotkeyBound $true -Message 'Francis Lens global hotkey was pressed.' -LaunchOnHotkey $script:LaunchOnHotkey -PressCount $script:PressCount
        if ($script:LaunchOnHotkey) {
          $SummonScript = Join-Path $script:PSScriptRoot 'lens-summon.ps1'
          $SummonArguments = @(
            '-NoProfile',
            '-ExecutionPolicy',
            'Bypass',
            '-File',
            $SummonScript,
            '-Mode',
            'LocalOpen'
          )
          if (-not [string]::IsNullOrWhiteSpace($script:ConfigOverridePath)) {
            $SummonArguments += @('-ConfigOverridePath', $script:ConfigOverridePath)
          }
          Start-Process -FilePath 'powershell' -ArgumentList $SummonArguments -WindowStyle Hidden
        }
      })
    $HotkeyRegistration = Resolve-HotkeyRegistration -GlobalHotkey ([string]$ConfigForAction.global_hotkey)
    if (-not [bool]$HotkeyRegistration.ok) {
      $Failed = $true
      Write-HotkeyState -Root $DataRoot -Status 'failed' -HotkeyBound $false -Message "Invalid global hotkey '$($ConfigForAction.global_hotkey)': $($HotkeyRegistration.error)."
      exit 1
    }
    $Registered = [FrancisLensHotkeyNative]::RegisterHotKey($Window.Handle, 1, [uint32]$HotkeyRegistration.modifiers, [uint32]$HotkeyRegistration.virtual_key)
    if (-not $Registered) {
      $Failed = $true
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
          $MainForm.Close()
        })
      $Timer.Start()
    }
    [System.Windows.Forms.Application]::Run($MainForm)
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
    if ($null -ne $MainForm) {
      $MainForm.Dispose()
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
if (-not [bool]$Existing.ready -and -not [bool]$Existing.process_alive -and [string]$Existing.runtime_status) {
  $RuntimeStatus = [string]$Existing.runtime_status
  if ($RuntimeStatus -ne 'missing') {
    $RuntimeRoot = Join-Path $DataRoot 'runtime\lens-hotkey'
    Remove-Item -LiteralPath (Join-Path $RuntimeRoot 'status.json') -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $RuntimeRoot 'lens-hotkey.pid') -Force -ErrorAction SilentlyContinue
    $Existing = Get-HotkeyRuntimeReadback -Root $DataRoot
  }
}
if ([bool]$Existing.ready) {
  New-StatusPayload -Root $DataRoot -ModeName $ModeName -StatusOverride 'already_running' | ConvertTo-Json -Depth 8
  exit 0
}

$PowerShell = Get-Command powershell -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command pwsh -ErrorAction Stop
}
$StartedProcess = $null
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
if (-not [string]::IsNullOrWhiteSpace($ConfigOverridePath)) {
  $ArgumentList += @('-ConfigOverridePath', $ConfigOverridePath)
}
$StartedProcess = Start-Process -FilePath $PowerShell.Source -ArgumentList $ArgumentList -WindowStyle Hidden -PassThru

$Deadline = [DateTimeOffset]::UtcNow.AddSeconds($StartupTimeoutSeconds)
do {
  Start-Sleep -Milliseconds 200
  $Readback = Get-HotkeyRuntimeReadback -Root $DataRoot
  if ([bool]$Readback.ready) {
    New-StatusPayload -Root $DataRoot -ModeName $ModeName -StatusOverride 'started' | ConvertTo-Json -Depth 8
    exit 0
  }
  if ([string]$Readback.runtime_status -eq 'failed' -or [string]$Readback.runtime_status -eq 'unsupported') {
    $StartedProcessStopped = $false
    if ($null -ne $StartedProcess) {
      try {
        $StartedProcess.Refresh()
        if (-not $StartedProcess.HasExited) {
          Stop-Process -Id $StartedProcess.Id -Force -ErrorAction Stop
          $StartedProcessStopped = $true
        }
      } catch {
        $StartedProcessStopped = $false
      }
    }
    $Payload = New-StatusPayload -Root $DataRoot -ModeName $ModeName -StatusOverride 'start_failed'
    $Payload.ok = $false
    $Payload.error = if ([string]$Readback.runtime_status -eq 'unsupported') { 'lens_hotkey_binding_unsupported' } else { 'lens_hotkey_binding_start_failed' }
    $Payload.started_process_id = if ($null -ne $StartedProcess) { [int]$StartedProcess.Id } else { 0 }
    $Payload.started_process_stopped = $StartedProcessStopped
    $Payload.child_runtime_status = [string]$Readback.runtime_status
    $Payload.child_runtime_status_pid = [int]$Readback.runtime_status_pid
    $Payload.child_runtime_status_message = [string]$Readback.runtime_status_message
    $Payload.message = if ([string]$Readback.runtime_status_message) { [string]$Readback.runtime_status_message } else { 'Lens global hotkey binding child reported a terminal startup failure.' }
    $Payload | ConvertTo-Json -Depth 8
    exit 1
  }
} while ([DateTimeOffset]::UtcNow -lt $Deadline)

$StartedProcessStopped = $false
if ($null -ne $StartedProcess) {
  try {
    $StartedProcess.Refresh()
    if (-not $StartedProcess.HasExited) {
      Stop-Process -Id $StartedProcess.Id -Force -ErrorAction Stop
      $StartedProcessStopped = $true
    }
  } catch {
    $StartedProcessStopped = $false
  }
}

$Payload = New-StatusPayload -Root $DataRoot -ModeName $ModeName -StatusOverride 'start_timeout'
$Payload.ok = $false
$Payload.error = 'lens_hotkey_binding_start_timeout'
$Payload.started_process_id = if ($null -ne $StartedProcess) { [int]$StartedProcess.Id } else { 0 }
$Payload.started_process_stopped = $StartedProcessStopped
$Payload.message = 'Lens global hotkey binding did not report a live bound hotkey before the startup timeout.'
$Payload | ConvertTo-Json -Depth 8
exit 1
