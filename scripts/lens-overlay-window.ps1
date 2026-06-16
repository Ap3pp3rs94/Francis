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

function Get-CountProperty {
  param(
    [object]$Payload,
    [string]$Name,
    [int]$Default = 0
  )

  if ($null -eq $Payload) {
    return $Default
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) {
    return $Default
  }
  if ($Property.Value -is [array]) {
    return [int]$Property.Value.Count
  }
  try {
    return [int](@($Property.Value).Count)
  } catch {
    return $Default
  }
}

function New-McpBodyStateProjection {
  param(
    [string]$McpStatusRoute,
    [string]$OrbMcpStatusRoute
  )

  return [ordered]@{
    status = 'linked'
    source = 'lens_orb_mcp_status_bridge'
    route = $McpStatusRoute
    mcp_status_route = $McpStatusRoute
    orb_mcp_status_route = $OrbMcpStatusRoute
    read_only = $true
    grants_execution_authority = $false
    grants_mutation_authority = $false
    live_status = 'not_requested'
    message = 'Overlay runtime is linked to the read-only Lens-Orb MCP body-state route.'
  }
}

function Set-McpBodyStateValue {
  param(
    [System.Collections.Specialized.OrderedDictionary]$Projection,
    [string]$Name,
    [object]$Value
  )

  $Projection[$Name] = $Value
}

function Read-McpBodyStateForOverlay {
  param(
    [string]$McpStatusRoute,
    [string]$OrbMcpStatusRoute
  )

  $Projection = New-McpBodyStateProjection -McpStatusRoute $McpStatusRoute -OrbMcpStatusRoute $OrbMcpStatusRoute
  $ApiBaseUrl = [string]$env:FRANCIS_API_BASE_URL
  if ([string]::IsNullOrWhiteSpace($ApiBaseUrl)) {
    $ApiBaseUrl = 'http://127.0.0.1:8000'
  }
  $ApiBaseUrl = $ApiBaseUrl.TrimEnd('/')
  $Uri = '{0}{1}?actor=lens.overlay' -f $ApiBaseUrl, $McpStatusRoute
  Set-McpBodyStateValue -Projection $Projection -Name 'api_base_url' -Value $ApiBaseUrl
  Set-McpBodyStateValue -Projection $Projection -Name 'api_url' -Value $Uri

  try {
    $Body = Invoke-RestMethod -Uri $Uri -Method Get -TimeoutSec 2 -ErrorAction Stop
    $Mcp = $Body.PSObject.Properties['mcp'].Value
    $InputComponent = $Body.PSObject.Properties['components'].Value.PSObject.Properties['francis.input.status'].Value
    $TakeoverComponent = $Body.PSObject.Properties['components'].Value.PSObject.Properties['francis.takeover.status'].Value
    $ExpectedToolCount = Get-IntegerProperty -Payload $Mcp -Name 'expected_tool_count' -Default 0
    if ($ExpectedToolCount -le 0) {
      $ExpectedToolCount = Get-IntegerProperty -Payload $Mcp -Name 'expected_min_tool_count' -Default 0
    }

    Set-McpBodyStateValue -Projection $Projection -Name 'live_status' -Value 'ready'
    Set-McpBodyStateValue -Projection $Projection -Name 'body_status' -Value (Get-StringProperty -Payload $Body -Name 'status' -Default 'unknown')
    Set-McpBodyStateValue -Projection $Projection -Name 'embodied_posture' -Value (Get-StringProperty -Payload $Body -Name 'embodied_posture' -Default 'unknown')
    Set-McpBodyStateValue -Projection $Projection -Name 'tool_count' -Value (Get-IntegerProperty -Payload $Mcp -Name 'tool_count' -Default 0)
    Set-McpBodyStateValue -Projection $Projection -Name 'expected_tool_count' -Value $ExpectedToolCount
    Set-McpBodyStateValue -Projection $Projection -Name 'missing_tools_count' -Value (Get-CountProperty -Payload $Mcp -Name 'missing_tools' -Default 0)
    Set-McpBodyStateValue -Projection $Projection -Name 'blockers_count' -Value (Get-CountProperty -Payload $Body -Name 'blockers' -Default 0)
    Set-McpBodyStateValue -Projection $Projection -Name 'resident' -Value (Get-BoolProperty -Payload $Body -Name 'resident' -Default $false)
    Set-McpBodyStateValue -Projection $Projection -Name 'input_status' -Value (Get-StringProperty -Payload $InputComponent -Name 'status' -Default 'unknown')
    Set-McpBodyStateValue -Projection $Projection -Name 'takeover_status' -Value (Get-StringProperty -Payload $TakeoverComponent -Name 'status' -Default 'unknown')
    Set-McpBodyStateValue -Projection $Projection -Name 'message' -Value 'Overlay runtime is displaying live read-only Lens-Orb MCP body-state.'
  } catch {
    Set-McpBodyStateValue -Projection $Projection -Name 'live_status' -Value 'unavailable'
    Set-McpBodyStateValue -Projection $Projection -Name 'error' -Value ([string]$_.Exception.Message)
    Set-McpBodyStateValue -Projection $Projection -Name 'body_status' -Value 'unavailable'
    Set-McpBodyStateValue -Projection $Projection -Name 'embodied_posture' -Value 'unknown'
    Set-McpBodyStateValue -Projection $Projection -Name 'tool_count' -Value 0
    Set-McpBodyStateValue -Projection $Projection -Name 'expected_tool_count' -Value 0
    Set-McpBodyStateValue -Projection $Projection -Name 'missing_tools_count' -Value 0
    Set-McpBodyStateValue -Projection $Projection -Name 'blockers_count' -Value 0
    Set-McpBodyStateValue -Projection $Projection -Name 'resident' -Value $false
    Set-McpBodyStateValue -Projection $Projection -Name 'input_status' -Value 'unknown'
    Set-McpBodyStateValue -Projection $Projection -Name 'takeover_status' -Value 'unknown'
    Set-McpBodyStateValue -Projection $Projection -Name 'message' -Value 'Overlay runtime could not read the live Lens-Orb MCP body-state API; route link remains available.'
  }

  return $Projection
}

function Format-McpBodyStateLabel {
  param([object]$BodyState)

  if ($null -eq $BodyState) {
    return "Francis Lens`nMCP body-state: unavailable"
  }

  $LiveStatus = Get-StringProperty -Payload $BodyState -Name 'live_status' -Default 'not_requested'
  $Route = Get-StringProperty -Payload $BodyState -Name 'route' -Default '/lens/mcp/status'
  if ($LiveStatus -ne 'ready') {
    return "Francis Lens`nMCP body-state: $Route`nLive readback: $LiveStatus"
  }

  $Status = Get-StringProperty -Payload $BodyState -Name 'body_status' -Default 'unknown'
  $Posture = Get-StringProperty -Payload $BodyState -Name 'embodied_posture' -Default 'unknown'
  $ToolCount = Get-IntegerProperty -Payload $BodyState -Name 'tool_count' -Default 0
  $ExpectedToolCount = Get-IntegerProperty -Payload $BodyState -Name 'expected_tool_count' -Default 0
  $Resident = Get-BoolProperty -Payload $BodyState -Name 'resident' -Default $false
  $TakeoverStatus = Get-StringProperty -Payload $BodyState -Name 'takeover_status' -Default 'unknown'
  $InputStatus = Get-StringProperty -Payload $BodyState -Name 'input_status' -Default 'unknown'
  $BlockersCount = Get-IntegerProperty -Payload $BodyState -Name 'blockers_count' -Default 0

  return @(
    'Francis Lens'
    ('Status: {0} | Posture: {1}' -f $Status, $Posture)
    ('Tools: {0}/{1} | Resident: {2}' -f $ToolCount, $ExpectedToolCount, $Resident.ToString().ToLowerInvariant())
    ('Takeover: {0} | Input: {1} | Blockers: {2}' -f $TakeoverStatus, $InputStatus, $BlockersCount)
  ) -join "`n"
}

function Update-OverlayMcpBodyStateLabel {
  param(
    [object]$Label,
    [object]$Config,
    [string]$Root
  )

  $BodyState = Read-McpBodyStateForOverlay -McpStatusRoute $Config.mcp_status_route -OrbMcpStatusRoute $Config.orb_mcp_status_route
  $Label.Text = Format-McpBodyStateLabel -BodyState $BodyState
  Write-OverlayState -Root $Root -Status 'overlay_running' -OverlayWindowVisible $true -AlwaysOnTop $true -Message 'Francis Lens overlay window is running with MCP body-state readback.' -McpBodyState $BodyState
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

function Test-OverlayRuntimeProcess {
  param([int]$ProcessId)

  if ($ProcessId -le 0) {
    return $false
  }
  if (-not (Get-ProcessAlive -ProcessId $ProcessId)) {
    return $false
  }
  if (-not ([System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT)) {
    return $false
  }
  try {
    $Process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
  } catch {
    return $false
  }
  if ($null -eq $Process) {
    return $false
  }
  $CommandLine = [string]$Process.CommandLine
  return (
    $CommandLine -like '*lens-overlay-window.ps1*' -and
    $CommandLine -like '*-Mode Run*'
  )
}

function Stop-OverlayRuntimeProcess {
  param([int]$ProcessId)

  if (Test-OverlayRuntimeProcess -ProcessId $ProcessId) {
    Stop-Process -Id $ProcessId -Force -ErrorAction Stop
    return $true
  }
  return $false
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
    mcp_status_route = Get-StringProperty -Payload $Config -Name 'mcp_status_route' -Default '/lens/mcp/status'
    orb_mcp_status_route = Get-StringProperty -Payload $Config -Name 'orb_mcp_status_route' -Default '/lens/orb/mcp-status'
  }
}

function Write-OverlayState {
  param(
    [string]$Root,
    [string]$Status,
    [bool]$OverlayWindowVisible,
    [bool]$AlwaysOnTop,
    [string]$Message = '',
    [object]$McpBodyState = $null
  )

  $Config = Get-OverlayConfig
  $RuntimeRoot = Join-Path $Root 'runtime\lens-overlay'
  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  $PidPath = Join-Path $RuntimeRoot 'lens-overlay.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  if ($Status -eq 'overlay_running') {
    Set-Content -LiteralPath $PidPath -Value ([string]$PID) -Encoding UTF8
  }
  if ($null -eq $McpBodyState) {
    $McpBodyState = New-McpBodyStateProjection -McpStatusRoute $Config.mcp_status_route -OrbMcpStatusRoute $Config.orb_mcp_status_route
  }
  $Payload = [ordered]@{
    kind = 'lens.overlay.runtime_state'
    status = $Status
    pid = $PID
    overlay_name = $Config.overlay_name
    overlay_scope = $Config.overlay_scope
    status_route = $Config.status_route
    mcp_status_route = $Config.mcp_status_route
    orb_mcp_status_route = $Config.orb_mcp_status_route
    mcp_body_state = $McpBodyState
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
  $TempPath = Join-Path $RuntimeRoot ("status.{0}.tmp" -f ([Guid]::NewGuid().ToString('N')))
  try {
    $Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $TempPath -Encoding UTF8
    Move-Item -LiteralPath $TempPath -Destination $StatusPath -Force
  } finally {
    Remove-Item -LiteralPath $TempPath -Force -ErrorAction SilentlyContinue
  }
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

  $McpStatusRoute = Get-StringProperty -Payload $Status -Name 'mcp_status_route' -Default $Config.mcp_status_route
  $OrbMcpStatusRoute = Get-StringProperty -Payload $Status -Name 'orb_mcp_status_route' -Default $Config.orb_mcp_status_route
  $StatusMcpBodyState = if ($null -ne $Status -and $null -ne $Status.PSObject.Properties['mcp_body_state']) { $Status.PSObject.Properties['mcp_body_state'].Value } else { $null }
  $McpBodyState = if ($null -ne $StatusMcpBodyState) { $StatusMcpBodyState } else { New-McpBodyStateProjection -McpStatusRoute $McpStatusRoute -OrbMcpStatusRoute $OrbMcpStatusRoute }
  $StatusClaimsRunningOverlay = (
    $StatusKind -eq 'lens.overlay.runtime_state' -and
    $StatusValue -eq 'overlay_running' -and
    $StatusPid -gt 0 -and
    $StatusPid -eq $RuntimePid -and
    (Get-StringProperty -Payload $Status -Name 'overlay_name' -Default '') -eq $Config.overlay_name -and
    (Get-StringProperty -Payload $Status -Name 'overlay_scope' -Default '') -eq $Config.overlay_scope
  )
  $RuntimeProcessAlive = Test-OverlayRuntimeProcess -ProcessId $RuntimePid
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
    runtime_process_alive = $RuntimeProcessAlive
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
    mcp_status_route = $McpStatusRoute
    orb_mcp_status_route = $OrbMcpStatusRoute
    mcp_body_state_route = $McpStatusRoute
    mcp_body_state = $McpBodyState
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

  $Config = Get-OverlayConfig
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
    mcp_status_route = $Config.mcp_status_route
    orb_mcp_status_route = $Config.orb_mcp_status_route
    mcp_body_state_route = $Config.mcp_status_route
    mcp_body_state = $Readback.mcp_body_state
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
  $RefreshTimer = $null
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
    $Form.Width = 440
    $Form.Height = 150
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
    $Label.Text = "Francis Lens`nMCP body-state: $($Config.mcp_status_route)`nLive readback: starting"
    $Form.Controls.Add($Label)
    $script:LensOverlayLabel = $Label
    $script:LensOverlayConfig = $Config
    $script:LensOverlayDataRoot = $DataRoot
    $Form.Add_Shown({
        Update-OverlayMcpBodyStateLabel -Label $script:LensOverlayLabel -Config $script:LensOverlayConfig -Root $script:LensOverlayDataRoot
      })
    $RefreshTimer = New-Object System.Windows.Forms.Timer
    $RefreshTimer.Interval = 5000
    $RefreshTimer.Add_Tick({
        Update-OverlayMcpBodyStateLabel -Label $script:LensOverlayLabel -Config $script:LensOverlayConfig -Root $script:LensOverlayDataRoot
      })
    $RefreshTimer.Start()
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
    if ($null -ne $RefreshTimer) {
      $RefreshTimer.Dispose()
    }
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
  if ($RuntimePidToStop -gt 0) {
    Stop-OverlayRuntimeProcess -ProcessId $RuntimePidToStop | Out-Null
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
if ([bool]$Existing.runtime_process_alive -and [int]$Existing.pid -gt 0) {
  Stop-OverlayRuntimeProcess -ProcessId ([int]$Existing.pid) | Out-Null
  Remove-Item -LiteralPath (Join-Path $DataRoot 'runtime\lens-overlay\lens-overlay.pid') -Force -ErrorAction SilentlyContinue
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
$TimedOut = Get-OverlayRuntimeReadback -Root $DataRoot
if ([bool]$TimedOut.runtime_process_alive -and [int]$TimedOut.pid -gt 0) {
  Stop-OverlayRuntimeProcess -ProcessId ([int]$TimedOut.pid) | Out-Null
  Remove-Item -LiteralPath (Join-Path $DataRoot 'runtime\lens-overlay\lens-overlay.pid') -Force -ErrorAction SilentlyContinue
}
$Payload.ok = $false
$Payload.error = 'lens_overlay_window_start_timeout'
$Payload.message = 'Lens overlay window did not report a live always-on-top window before the startup timeout.'
$Payload | ConvertTo-Json -Depth 8
exit 1
