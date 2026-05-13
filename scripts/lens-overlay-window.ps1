[CmdletBinding()]
param(
  [ValidateSet('Status', 'Start', 'Stop', 'Run')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [ValidateRange(1, 30)]
  [int]$StartupTimeoutSeconds = 5,

  [ValidateRange(0, 3600)]
  [int]$RunSeconds = 0
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

function Get-OverlayConfig {
  $ConfigPath = Join-Path $RepoRoot 'config\runtime\lens\overlay.json'
  $Config = Read-JsonFile -Path $ConfigPath
  return [ordered]@{
    path = $ConfigPath
    payload = $Config
    overlay_name = Get-StringProperty -Payload $Config -Name 'overlay_name' -Default 'Francis Lens Overlay'
    overlay_scope = Get-StringProperty -Payload $Config -Name 'overlay_scope' -Default 'user_session'
    status_route = Get-StringProperty -Payload $Config -Name 'status_route' -Default '/lens/status'
  }
}

function Write-OverlayState {
  param(
    [string]$Root,
    [string]$Status,
    [bool]$OverlayWindowVisible,
    [bool]$AlwaysOnTop,
    [string]$Message = ''
  )

  $Config = Get-OverlayConfig
  $RuntimeRoot = Join-Path $Root 'runtime\lens-overlay'
  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  $PidPath = Join-Path $RuntimeRoot 'lens-overlay.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  if ($Status -eq 'overlay_running') {
    Set-Content -LiteralPath $PidPath -Value ([string]$PID) -Encoding UTF8
  }
  $Payload = [ordered]@{
    kind = 'lens.overlay.runtime_state'
    status = $Status
    pid = $PID
    overlay_name = $Config.overlay_name
    overlay_scope = $Config.overlay_scope
    status_route = $Config.status_route
    overlay_window_visible = $OverlayWindowVisible
    always_on_top = $AlwaysOnTop
    updated_at = [DateTimeOffset]::UtcNow.ToString('o')
    message = $Message
    governance = [ordered]@{
      execution_authority = $false
      approval_decision_authority = $false
      memory_write = $false
      overlay_control_authority = $OverlayWindowVisible
      window_management_authority = $OverlayWindowVisible
      capture_authority = $false
      new_sensing_authority = $false
      summon_authority = $false
      tray_registration_authority = $false
      service_control_authority = $false
      local_process_launch_authority = $OverlayWindowVisible
      mutation_authority_granted = $OverlayWindowVisible
    }
  }
  $Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $StatusPath -Encoding UTF8
}

function Get-OverlayRuntimeReadback {
  param([string]$Root)

  $Config = Get-OverlayConfig
  $RuntimeRoot = Join-Path $Root 'runtime\lens-overlay'
  $PidPath = Join-Path $RuntimeRoot 'lens-overlay.pid'
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

  $StatusClaimsRunningOverlay = (
    $StatusKind -eq 'lens.overlay.runtime_state' -and
    $StatusValue -eq 'overlay_running' -and
    $StatusPid -gt 0 -and
    $StatusPid -eq $RuntimePid -and
    (Get-StringProperty -Payload $Status -Name 'overlay_name' -Default '') -eq $Config.overlay_name -and
    (Get-StringProperty -Payload $Status -Name 'overlay_scope' -Default '') -eq $Config.overlay_scope
  )
  $ProcessAlive = if ($StatusClaimsRunningOverlay) { Get-ProcessAlive -ProcessId $RuntimePid } else { $false }
  $OverlayVisible = $ProcessAlive -and (Get-BoolProperty -Payload $Status -Name 'overlay_window_visible' -Default $false)
  $AlwaysOnTop = $OverlayVisible -and (Get-BoolProperty -Payload $Status -Name 'always_on_top' -Default $false)
  $Ready = $OverlayVisible -and $AlwaysOnTop
  $RequirementState = if ($Ready) {
    'visible'
  } elseif ($ProcessAlive) {
    'process_running_no_visible_overlay_claim'
  } elseif ($RuntimeStateExists -or $PidPresent) {
    'stale_or_unverified'
  } else {
    'missing'
  }
  $Blocker = if ($Ready) {
    ''
  } elseif ($ProcessAlive) {
    'overlay_window_not_observed'
  } else {
    'overlay_window_runtime_missing'
  }

  return [ordered]@{
    ready = $Ready
    process_alive = $ProcessAlive
    overlay_window_visible = $OverlayVisible
    always_on_top = $AlwaysOnTop
    pid = $RuntimePid
    pid_present = $PidPresent
    status_path = $StatusPath
    pid_path = $PidPath
    runtime_state_exists = $RuntimeStateExists
    runtime_status = $StatusValue
    runtime_status_kind = $StatusKind
    runtime_status_pid = $StatusPid
    runtime_status_pid_matches_pid_file = ($StatusPid -gt 0 -and $StatusPid -eq $RuntimePid)
    overlay_name = Get-StringProperty -Payload $Status -Name 'overlay_name' -Default ''
    expected_overlay_name = $Config.overlay_name
    overlay_scope = Get-StringProperty -Payload $Status -Name 'overlay_scope' -Default ''
    expected_overlay_scope = $Config.overlay_scope
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

  $Readback = Get-OverlayRuntimeReadback -Root $Root
  $Ready = [bool]$Readback.ready
  return [ordered]@{
    ok = $true
    kind = 'lens.overlay.window.runtime'
    status = if ($StatusOverride) { $StatusOverride } elseif ($Ready) { 'visible' } else { 'missing' }
    mode = $ModeName
    ready = $Ready
    overlay_window = $Ready
    data_root = $Root
    runtime_state_path = 'data/runtime/lens-overlay/status.json'
    pid_path = 'data/runtime/lens-overlay/lens-overlay.pid'
    overlay_runtime = $Readback
    next_smallest_truthful_gap = if ($Ready) { 'overlay_authority_and_config' } else { 'overlay_window_runtime' }
    governance = [ordered]@{
      read_only_contract = ($ModeName -eq 'status')
      execution_authority = $false
      approval_decision_authority = $false
      memory_write = $false
      overlay_control_authority = ($ModeName -eq 'start')
      window_management_authority = ($ModeName -eq 'start')
      capture_authority = $false
      new_sensing_authority = $false
      summon_authority = $false
      local_process_launch_authority = ($ModeName -eq 'start')
      tray_registration_authority = $false
      service_control_authority = $false
      mutation_authority_granted = ($ModeName -eq 'start' -or $ModeName -eq 'stop')
    }
    message = if ($Ready) { 'Lens overlay window runtime is live.' } else { 'Lens overlay window runtime is not live.' }
  }
}

$DataRoot = Get-DataRoot -Override $DataDir
$ModeName = $Mode.ToLowerInvariant()
$RunningOnWindows = [System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT

if ($Mode -eq 'Run') {
  $RuntimeRoot = Join-Path $DataRoot 'runtime\lens-overlay'
  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  $Form = $null
  $Timer = $null
  $Failed = $false
  try {
    if (-not $RunningOnWindows) {
      Write-OverlayState -Root $DataRoot -Status 'unsupported' -OverlayWindowVisible $false -AlwaysOnTop $false -Message 'Windows overlay requires a Windows user session.'
      exit 3
    }
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    [System.Windows.Forms.Application]::EnableVisualStyles()
    $Config = Get-OverlayConfig
    $Screen = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
    $Form = New-Object System.Windows.Forms.Form
    $Form.Text = $Config.overlay_name
    $Form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedToolWindow
    $Form.StartPosition = [System.Windows.Forms.FormStartPosition]::Manual
    $Form.ShowInTaskbar = $false
    $Form.TopMost = $true
    $Form.Width = 360
    $Form.Height = 110
    $Form.Left = [Math]::Max(0, $Screen.Right - $Form.Width - 24)
    $Form.Top = [Math]::Max(0, $Screen.Top + 24)
    $Form.BackColor = [System.Drawing.Color]::FromArgb(28, 32, 36)
    $Form.ForeColor = [System.Drawing.Color]::White
    $Form.Opacity = 0.92
    $Label = New-Object System.Windows.Forms.Label
    $Label.AutoSize = $false
    $Label.Dock = [System.Windows.Forms.DockStyle]::Fill
    $Label.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
    $Label.Font = New-Object System.Drawing.Font('Segoe UI', 10, [System.Drawing.FontStyle]::Regular)
    $Label.Text = 'Francis Lens'
    $Form.Controls.Add($Label)
    $Form.Add_Shown({
        Write-OverlayState -Root $script:DataRoot -Status 'overlay_running' -OverlayWindowVisible $true -AlwaysOnTop $true -Message 'Francis Lens overlay window is running.'
      })
    if ($RunSeconds -gt 0) {
      $Timer = New-Object System.Windows.Forms.Timer
      $Timer.Interval = [Math]::Max(1000, $RunSeconds * 1000)
      $Timer.Add_Tick({
          $Timer.Stop()
          [System.Windows.Forms.Application]::ExitThread()
        })
      $Timer.Start()
    }
    [System.Windows.Forms.Application]::Run($Form)
  } catch {
    $Failed = $true
    Write-OverlayState -Root $DataRoot -Status 'failed' -OverlayWindowVisible $false -AlwaysOnTop $false -Message ([string]$_.Exception.Message)
    exit 1
  } finally {
    if ($null -ne $Timer) {
      $Timer.Dispose()
    }
    if ($null -ne $Form) {
      $Form.Dispose()
    }
    if (-not $Failed) {
      Write-OverlayState -Root $DataRoot -Status 'overlay_stopped' -OverlayWindowVisible $false -AlwaysOnTop $false -Message 'Francis Lens overlay window stopped.'
    }
    Remove-Item -LiteralPath (Join-Path $DataRoot 'runtime\lens-overlay\lens-overlay.pid') -Force -ErrorAction SilentlyContinue
  }
  exit 0
}

if ($Mode -eq 'Status') {
  New-StatusPayload -Root $DataRoot -ModeName $ModeName | ConvertTo-Json -Depth 8
  exit 0
}

if ($Mode -eq 'Stop') {
  $Readback = Get-OverlayRuntimeReadback -Root $DataRoot
  $RuntimePidToStop = [int]$Readback.pid
  if ([bool]$Readback.process_alive -and $RuntimePidToStop -gt 0) {
    Stop-Process -Id $RuntimePidToStop -Force -ErrorAction Stop
  }
  Write-OverlayState -Root $DataRoot -Status 'overlay_stopped' -OverlayWindowVisible $false -AlwaysOnTop $false -Message 'Francis Lens overlay window stopped by operator command.'
  Remove-Item -LiteralPath (Join-Path $DataRoot 'runtime\lens-overlay\lens-overlay.pid') -Force -ErrorAction SilentlyContinue
  New-StatusPayload -Root $DataRoot -ModeName $ModeName -StatusOverride 'stopped' | ConvertTo-Json -Depth 8
  exit 0
}

if (-not $RunningOnWindows) {
  $Payload = New-StatusPayload -Root $DataRoot -ModeName $ModeName -StatusOverride 'refused'
  $Payload.ok = $false
  $Payload.error = 'lens_overlay_window_unsupported_platform'
  $Payload.message = 'Lens overlay window Start is only supported on Windows user sessions.'
  $Payload | ConvertTo-Json -Depth 8
  exit 2
}

$Existing = Get-OverlayRuntimeReadback -Root $DataRoot
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
Start-Process -FilePath $PowerShell.Source -ArgumentList $ArgumentList -WindowStyle Hidden | Out-Null

$Deadline = [DateTimeOffset]::UtcNow.AddSeconds($StartupTimeoutSeconds)
do {
  Start-Sleep -Milliseconds 200
  $Readback = Get-OverlayRuntimeReadback -Root $DataRoot
  if ([bool]$Readback.ready) {
    New-StatusPayload -Root $DataRoot -ModeName $ModeName -StatusOverride 'started' | ConvertTo-Json -Depth 8
    exit 0
  }
} while ([DateTimeOffset]::UtcNow -lt $Deadline)

$Payload = New-StatusPayload -Root $DataRoot -ModeName $ModeName -StatusOverride 'start_timeout'
$Payload.ok = $false
$Payload.error = 'lens_overlay_window_start_timeout'
$Payload.message = 'Lens overlay window did not report a live always-on-top window before the startup timeout.'
$Payload | ConvertTo-Json -Depth 8
exit 1
