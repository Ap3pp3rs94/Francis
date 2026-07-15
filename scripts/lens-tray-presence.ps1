[CmdletBinding()]
param(
  [ValidateSet('Status', 'Start', 'Stop', 'Run')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$')]
  [string]$RuntimeIdentity = '',

  [ValidateRange(1, 30)]
  [int]$StartupTimeoutSeconds = 5,

  [ValidateRange(0, 3600)]
  [int]$RunSeconds = 0
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RuntimeIdentity) -and -not [string]::IsNullOrWhiteSpace([string]$env:FRANCIS_RUNTIME_IDENTITY)) {
  if ([string]$env:FRANCIS_RUNTIME_IDENTITY -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$') {
    throw 'FRANCIS_RUNTIME_IDENTITY must contain only letters, numbers, dots, underscores, or hyphens and be at most 40 characters.'
  }
  $RuntimeIdentity = [string]$env:FRANCIS_RUNTIME_IDENTITY
}

$EffectivePresenceName = if ([string]::IsNullOrWhiteSpace($RuntimeIdentity)) { 'Francis Lens Tray Presence' } else { "Francis Lens Tray Presence [$RuntimeIdentity]" }
$EffectiveTrayText = if ([string]::IsNullOrWhiteSpace($RuntimeIdentity)) { 'Francis Lens' } else { "Francis Lens [$RuntimeIdentity]" }

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

function Write-TrayState {
  param(
    [string]$Root,
    [string]$Status,
    [bool]$TrayIconVisible,
    [string]$Message = ''
  )

  $RuntimeRoot = Join-Path $Root 'runtime\lens-tray'
  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  $PidPath = Join-Path $RuntimeRoot 'lens-tray.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  if ($Status -eq 'tray_running') {
    Set-Content -LiteralPath $PidPath -Value ([string]$PID) -Encoding UTF8
  }
  $Payload = [ordered]@{
    kind = 'lens.tray.runtime_state'
    status = $Status
    pid = $PID
    tray_icon_visible = $TrayIconVisible
    presence_name = $EffectivePresenceName
    tray_text = $EffectiveTrayText
    runtime_identity = $RuntimeIdentity
    updated_at = [DateTimeOffset]::UtcNow.ToString('o')
    message = $Message
  }
  $Payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $StatusPath -Encoding UTF8
}

function Get-TrayRuntimeReadback {
  param([string]$Root)

  $RuntimeRoot = Join-Path $Root 'runtime\lens-tray'
  $PidPath = Join-Path $RuntimeRoot 'lens-tray.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  $Status = Read-JsonFile -Path $StatusPath
  $StatusKind = Get-StringProperty -Payload $Status -Name 'kind' -Default ''
  $StatusValue = Get-StringProperty -Payload $Status -Name 'status' -Default ''
  $StatusPid = Get-IntegerProperty -Payload $Status -Name 'pid' -Default 0
  $StatusPresenceName = Get-StringProperty -Payload $Status -Name 'presence_name' -Default ''
  $StatusRuntimeIdentity = Get-StringProperty -Payload $Status -Name 'runtime_identity' -Default ''
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

  $StatusClaimsRunningTray = (
    $StatusKind -eq 'lens.tray.runtime_state' -and
    $StatusValue -eq 'tray_running' -and
    $StatusPid -gt 0 -and
    $StatusPid -eq $RuntimePid -and
    ([string]::IsNullOrWhiteSpace($RuntimeIdentity) -or (
      $StatusPresenceName -eq $EffectivePresenceName -and
      $StatusRuntimeIdentity -eq $RuntimeIdentity
    ))
  )
  $ProcessAlive = $false
  if ($StatusClaimsRunningTray) {
    $ProcessAlive = Get-ProcessAlive -ProcessId $RuntimePid
  }
  $TrayIconVisible = $ProcessAlive -and (Get-BoolProperty -Payload $Status -Name 'tray_icon_visible' -Default $false)
  $RequirementState = if ($TrayIconVisible) {
    'running'
  } elseif ($ProcessAlive) {
    'process_running_no_icon_claim'
  } elseif ($RuntimeStateExists -or $PidPresent) {
    'stale_or_unverified'
  } else {
    'missing'
  }
  $Blocker = if ($TrayIconVisible) {
    ''
  } elseif ($ProcessAlive) {
    'tray_icon_not_observed'
  } else {
    'tray_presence_runtime_missing'
  }

  return [ordered]@{
    ready = $TrayIconVisible
    process_alive = $ProcessAlive
    tray_icon_visible = $TrayIconVisible
    pid = $RuntimePid
    pid_present = $PidPresent
    status_path = $StatusPath
    pid_path = $PidPath
    runtime_state_exists = $RuntimeStateExists
    runtime_status = $StatusValue
    runtime_status_kind = $StatusKind
    runtime_status_pid = $StatusPid
    runtime_status_pid_matches_pid_file = ($StatusPid -gt 0 -and $StatusPid -eq $RuntimePid)
    presence_name = $StatusPresenceName
    expected_presence_name = $EffectivePresenceName
    runtime_identity = $StatusRuntimeIdentity
    expected_runtime_identity = $RuntimeIdentity
    runtime_identity_matches_expected = ([string]::IsNullOrWhiteSpace($RuntimeIdentity) -or $StatusRuntimeIdentity -eq $RuntimeIdentity)
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

  $Readback = Get-TrayRuntimeReadback -Root $Root
  $Ready = [bool]$Readback.ready
  return [ordered]@{
    ok = $true
    kind = 'lens.tray.presence.runtime'
    status = if ($StatusOverride) { $StatusOverride } elseif ($Ready) { 'running' } else { 'missing' }
    mode = $ModeName
    ready = $Ready
    tray_presence = $Ready
    runtime_identity = $RuntimeIdentity
    presence_name = $EffectivePresenceName
    tray_text = $EffectiveTrayText
    data_root = $Root
    runtime_state_path = 'data/runtime/lens-tray/status.json'
    pid_path = 'data/runtime/lens-tray/lens-tray.pid'
    tray_runtime = $Readback
    governance = [ordered]@{
      read_only_contract = ($ModeName -eq 'status')
      execution_authority = $false
      approval_decision_authority = $false
      memory_write = $false
      overlay_control_authority = $false
      summon_authority = $false
      capture_authority = $false
      new_sensing_authority = $false
      local_process_launch_authority = ($ModeName -eq 'start')
      service_control_authority = $false
      tray_registration_authority = ($ModeName -eq 'start')
      tray_icon_authority = ($ModeName -eq 'start')
      notification_authority = $false
      mutation_authority_granted = ($ModeName -eq 'start' -or $ModeName -eq 'stop')
    }
    message = if ($Ready) { 'Lens tray presence runtime is live.' } else { 'Lens tray presence runtime is not live.' }
  }
}

$DataRoot = Get-DataRoot -Override $DataDir
$ModeName = $Mode.ToLowerInvariant()
$RunningOnWindows = [System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT

if ($Mode -eq 'Run') {
  $RuntimeRoot = Join-Path $DataRoot 'runtime\lens-tray'
  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  $NotifyIcon = $null
  $Timer = $null
  $MainForm = $null
  try {
    if (-not $RunningOnWindows) {
      Write-TrayState -Root $DataRoot -Status 'unsupported' -TrayIconVisible $false -Message 'Windows tray presence requires Windows.'
      exit 3
    }
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    [System.Windows.Forms.Application]::EnableVisualStyles()
    $MainForm = New-Object System.Windows.Forms.Form
    $MainForm.Text = $EffectivePresenceName
    $MainForm.ShowInTaskbar = $false
    $MainForm.WindowState = [System.Windows.Forms.FormWindowState]::Minimized
    $MainForm.Opacity = 0
    $MainForm.Size = New-Object System.Drawing.Size(0, 0)
    $MainForm.Add_Shown({
        $MainForm.Hide()
      })
    $NotifyIcon = New-Object System.Windows.Forms.NotifyIcon
    $NotifyIcon.Text = $EffectiveTrayText
    $NotifyIcon.Icon = [System.Drawing.SystemIcons]::Application
    $NotifyIcon.Visible = $true
    Write-TrayState -Root $DataRoot -Status 'tray_running' -TrayIconVisible $true -Message 'Francis Lens tray presence is running.'
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
    Write-TrayState -Root $DataRoot -Status 'failed' -TrayIconVisible $false -Message ([string]$_.Exception.Message)
    exit 1
  } finally {
    if ($null -ne $NotifyIcon) {
      $NotifyIcon.Visible = $false
      $NotifyIcon.Dispose()
    }
    if ($null -ne $Timer) {
      $Timer.Dispose()
    }
    if ($null -ne $MainForm) {
      $MainForm.Dispose()
    }
    Write-TrayState -Root $DataRoot -Status 'tray_stopped' -TrayIconVisible $false -Message 'Francis Lens tray presence stopped.'
    $PidPath = Join-Path $DataRoot 'runtime\lens-tray\lens-tray.pid'
    Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
  }
  exit 0
}

if ($Mode -eq 'Status') {
  New-StatusPayload -Root $DataRoot -ModeName $ModeName | ConvertTo-Json -Depth 8
  exit 0
}

if ($Mode -eq 'Stop') {
  $Readback = Get-TrayRuntimeReadback -Root $DataRoot
  $RuntimePidToStop = [int]$Readback.pid
  if ([bool]$Readback.process_alive -and $RuntimePidToStop -gt 0) {
    Stop-Process -Id $RuntimePidToStop -Force -ErrorAction Stop
  }
  Write-TrayState -Root $DataRoot -Status 'tray_stopped' -TrayIconVisible $false -Message 'Francis Lens tray presence stopped by operator command.'
  Remove-Item -LiteralPath (Join-Path $DataRoot 'runtime\lens-tray\lens-tray.pid') -Force -ErrorAction SilentlyContinue
  New-StatusPayload -Root $DataRoot -ModeName $ModeName -StatusOverride 'stopped' | ConvertTo-Json -Depth 8
  exit 0
}

if (-not $RunningOnWindows) {
  $Payload = New-StatusPayload -Root $DataRoot -ModeName $ModeName -StatusOverride 'refused'
  $Payload.ok = $false
  $Payload.error = 'lens_tray_presence_unsupported_platform'
  $Payload.message = 'Lens tray presence Start is only supported on Windows user sessions.'
  $Payload | ConvertTo-Json -Depth 8
  exit 2
}

$Existing = Get-TrayRuntimeReadback -Root $DataRoot
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
  '-RuntimeIdentity',
  $RuntimeIdentity,
  '-RunSeconds',
  ([string]$RunSeconds)
)
Start-Process -FilePath $PowerShell.Source -ArgumentList $ArgumentList -WindowStyle Hidden | Out-Null

$Deadline = [DateTimeOffset]::UtcNow.AddSeconds($StartupTimeoutSeconds)
do {
  Start-Sleep -Milliseconds 200
  $Readback = Get-TrayRuntimeReadback -Root $DataRoot
  if ([bool]$Readback.ready) {
    New-StatusPayload -Root $DataRoot -ModeName $ModeName -StatusOverride 'started' | ConvertTo-Json -Depth 8
    exit 0
  }
} while ([DateTimeOffset]::UtcNow -lt $Deadline)

$Payload = New-StatusPayload -Root $DataRoot -ModeName $ModeName -StatusOverride 'start_timeout'
$Payload.ok = $false
$Payload.error = 'lens_tray_presence_start_timeout'
$Payload.message = 'Lens tray presence did not report a live tray icon before the startup timeout.'
$Payload | ConvertTo-Json -Depth 8
exit 1
