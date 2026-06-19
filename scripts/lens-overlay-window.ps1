[CmdletBinding()]
param(
  [ValidateSet('Status', 'Start', 'Stop', 'Run', 'Speak', 'SyntheticVoiceTurn')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [ValidateSet('All', 'ProcessOnly')]
  [string]$VoiceEnvironmentScope = 'All',

  [string]$ChatUiBaseUrl = 'http://127.0.0.1:5173',

  [switch]$EnableAutonomousMotion,

  [switch]$DisableAutonomousMotion,

  [switch]$EnableManualOrbDrag,

  [switch]$EnableWakeListen,

  [switch]$EnableContinuousVoiceChat,

  [switch]$EnableVoiceLlm,

  [string]$VoiceText = '',

  [string]$VoiceTextPath = '',

  [ValidateSet('WindowsSapi', 'ElevenLabs')]
  [string]$VoiceProvider = 'WindowsSapi',

  [string]$VoiceName = 'Microsoft Zira Desktop',

  [string]$ElevenLabsVoiceId = '',

  [string]$ElevenLabsVoiceName = '',

  [string]$ElevenLabsModelId = 'eleven_multilingual_v2',

  [string]$ElevenLabsOutputFormat = 'mp3_44100_128',

  [ValidateRange(0.0, 1.0)]
  [double]$ElevenLabsStability = 0.58,

  [ValidateRange(0.0, 1.0)]
  [double]$ElevenLabsSimilarityBoost = 0.78,

  [ValidateRange(0.0, 1.0)]
  [double]$ElevenLabsStyle = 0.0,

  [ValidateRange(0.7, 1.2)]
  [double]$ElevenLabsSpeed = 0.89,

  [switch]$ElevenLabsUseSpeakerBoost,

  [switch]$PlaybackStateOnly,

  [string]$WakePhrase = 'hey francis',

  [string]$WakeResponse = "I'm here.",

  [ValidateRange(0.1, 1.0)]
  [double]$WakeConfidenceThreshold = 0.35,

  [ValidateRange(-10, 10)]
  [int]$VoiceRate = -1,

  [ValidateRange(0, 100)]
  [int]$VoiceVolume = 64,

  [ValidateRange(1, 30)]
  [int]$StartupTimeoutSeconds = 15,

  [ValidateRange(2, 30)]
  [int]$McpBodyStateTimeoutSeconds = 8,

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
  if ($Payload -is [System.Collections.IDictionary]) {
    if (-not $Payload.Contains($Name) -or $null -eq $Payload[$Name]) {
      return $Default
    }
    $Value = [string]$Payload[$Name]
    if ([string]::IsNullOrWhiteSpace($Value)) {
      return $Default
    }
    return $Value
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

function Get-UtcTimestampStringProperty {
  param(
    [object]$Payload,
    [string]$Name,
    [string]$Default = ''
  )

  if ($null -eq $Payload) {
    return $Default
  }
  $Value = $null
  if ($Payload -is [System.Collections.IDictionary]) {
    if (-not $Payload.Contains($Name) -or $null -eq $Payload[$Name]) {
      return $Default
    }
    $Value = $Payload[$Name]
  } else {
    $Property = $Payload.PSObject.Properties[$Name]
    if ($null -eq $Property -or $null -eq $Property.Value) {
      return $Default
    }
    $Value = $Property.Value
  }

  if ($Value -is [DateTimeOffset]) {
    return $Value.UtcDateTime.ToString('yyyy-MM-ddTHH:mm:ssZ', [System.Globalization.CultureInfo]::InvariantCulture)
  }
  if ($Value -is [DateTime]) {
    $DateTimeValue = [DateTime]$Value
    if ($DateTimeValue.Kind -eq [DateTimeKind]::Unspecified) {
      $DateTimeValue = [DateTime]::SpecifyKind($DateTimeValue, [DateTimeKind]::Utc)
    } else {
      $DateTimeValue = $DateTimeValue.ToUniversalTime()
    }
    return $DateTimeValue.ToString('yyyy-MM-ddTHH:mm:ssZ', [System.Globalization.CultureInfo]::InvariantCulture)
  }

  $Text = [string]$Value
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return $Default
  }
  return $Text
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
  if ($Payload -is [System.Collections.IDictionary]) {
    if (-not $Payload.Contains($Name) -or $null -eq $Payload[$Name]) {
      return $Default
    }
    if ($Payload[$Name] -is [bool]) {
      return [bool]$Payload[$Name]
    }
    $Value = [string]$Payload[$Name]
    if ([string]::IsNullOrWhiteSpace($Value)) {
      return $Default
    }
    return $Value.ToLowerInvariant() -eq 'true'
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
  if ($Payload -is [System.Collections.IDictionary]) {
    if (-not $Payload.Contains($Name) -or $null -eq $Payload[$Name]) {
      return $Default
    }
    if ($Payload[$Name] -is [array]) {
      return [int]$Payload[$Name].Count
    }
    try {
      return [int](@($Payload[$Name]).Count)
    } catch {
      return $Default
    }
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
    semantic_state = 'unknown'
    semantic_source = 'not_requested'
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

function Get-OverlayApiBaseUrl {
  $ApiBaseUrl = [string]$env:FRANCIS_API_BASE_URL
  if ([string]::IsNullOrWhiteSpace($ApiBaseUrl)) {
    $ApiBaseUrl = 'http://127.0.0.1:8000'
  }
  return $ApiBaseUrl.TrimEnd('/')
}

function Test-OverlayTruthy {
  param([string]$Value)

  $Clean = ([string]$Value).Trim().ToLowerInvariant()
  return $Clean -in @('1', 'true', 'yes', 'y', 'on')
}

function Get-OverlayVoiceUseLlm {
  if ($null -ne (Get-Variable -Name LensOverlayVoiceUseLlmRequested -Scope Script -ErrorAction SilentlyContinue)) {
    if ([bool]$script:LensOverlayVoiceUseLlmRequested) {
      return $true
    }
  }
  $Requested = [string]$env:FRANCIS_LENS_VOICE_USE_LLM
  if ([string]::IsNullOrWhiteSpace($Requested)) {
    return $false
  }
  return (Test-OverlayTruthy -Value $Requested)
}

function Read-McpBodyStateForOverlay {
  param(
    [string]$McpStatusRoute,
    [string]$OrbMcpStatusRoute,
    [int]$TimeoutSeconds = 8
  )

  $Projection = New-McpBodyStateProjection -McpStatusRoute $McpStatusRoute -OrbMcpStatusRoute $OrbMcpStatusRoute
  $ApiBaseUrl = Get-OverlayApiBaseUrl
  $Uri = '{0}{1}?actor=lens.overlay' -f $ApiBaseUrl, $McpStatusRoute
  Set-McpBodyStateValue -Projection $Projection -Name 'api_base_url' -Value $ApiBaseUrl
  Set-McpBodyStateValue -Projection $Projection -Name 'api_url' -Value $Uri
  Set-McpBodyStateValue -Projection $Projection -Name 'read_timeout_seconds' -Value $TimeoutSeconds

  try {
    $Body = Invoke-RestMethod -Uri $Uri -Method Get -TimeoutSec $TimeoutSeconds -ErrorAction Stop
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
    $OrbSemanticState = if ($null -ne $Body.PSObject.Properties['orb_semantic_state']) { $Body.PSObject.Properties['orb_semantic_state'].Value } else { $null }
    if ($null -ne $OrbSemanticState) {
      Set-McpBodyStateValue -Projection $Projection -Name 'orb_semantic_state' -Value $OrbSemanticState
      Set-McpBodyStateValue -Projection $Projection -Name 'semantic_state' -Value (Get-StringProperty -Payload $OrbSemanticState -Name 'semantic_state' -Default 'unknown')
      Set-McpBodyStateValue -Projection $Projection -Name 'semantic_source' -Value (Get-StringProperty -Payload $OrbSemanticState -Name 'source' -Default 'unknown')
    } else {
      Set-McpBodyStateValue -Projection $Projection -Name 'semantic_state' -Value 'unknown'
      Set-McpBodyStateValue -Projection $Projection -Name 'semantic_source' -Value 'unavailable'
    }
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
    Set-McpBodyStateValue -Projection $Projection -Name 'semantic_state' -Value 'unknown'
    Set-McpBodyStateValue -Projection $Projection -Name 'semantic_source' -Value 'unavailable'
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

function Set-OverlayLabelText {
  param(
    [object]$Label,
    [string]$Text
  )

  if ($null -eq $Label) {
    return
  }
  try {
    $Label.Text = $Text
    return
  } catch {
    try {
      $Label.Content = $Text
    } catch {
    }
  }
}

function Get-OrbEnergyReady {
  param([object]$BodyState)

  $LiveStatus = Get-StringProperty -Payload $BodyState -Name 'live_status' -Default 'not_requested'
  $BodyStatus = Get-StringProperty -Payload $BodyState -Name 'body_status' -Default 'unknown'
  $BlockersCount = Get-IntegerProperty -Payload $BodyState -Name 'blockers_count' -Default 0
  return ($LiveStatus -eq 'ready' -and $BodyStatus -eq 'ready' -and $BlockersCount -eq 0)
}

function New-OrbArgbColor {
  param(
    [int]$Alpha,
    [int]$Red,
    [int]$Green,
    [int]$Blue
  )

  return [System.Windows.Media.Color]::FromArgb([byte]$Alpha, [byte]$Red, [byte]$Green, [byte]$Blue)
}

function New-OrbRotateAnimation {
  param(
    [double]$From,
    [double]$To,
    [double]$Seconds
  )

  $Animation = New-Object System.Windows.Media.Animation.DoubleAnimation
  $Animation.From = $From
  $Animation.To = $To
  $Animation.Duration = New-Object System.Windows.Duration([TimeSpan]::FromSeconds($Seconds))
  $Animation.RepeatBehavior = [System.Windows.Media.Animation.RepeatBehavior]::Forever
  return $Animation
}

function New-OrbPulseAnimation {
  param(
    [double]$From,
    [double]$To,
    [double]$Seconds
  )

  $Animation = New-Object System.Windows.Media.Animation.DoubleAnimation
  $Animation.From = $From
  $Animation.To = $To
  $Animation.Duration = New-Object System.Windows.Duration([TimeSpan]::FromSeconds($Seconds))
  $Animation.AutoReverse = $true
  $Animation.RepeatBehavior = [System.Windows.Media.Animation.RepeatBehavior]::Forever
  return $Animation
}

function Clamp-OverlayDouble {
  param(
    [double]$Value,
    [double]$Minimum,
    [double]$Maximum
  )

  return [Math]::Min([Math]::Max($Value, $Minimum), $Maximum)
}

function Get-OverlayWpfRenderProfile {
  param([bool]$FrameSyncedMotion = $true)

  $Tier = -1
  $ProcessRenderMode = 'unknown'
  try {
    $RenderCapabilityType = 'System.Windows.Media.RenderCapability' -as [type]
    if ($null -ne $RenderCapabilityType) {
      $RawTier = [int]$RenderCapabilityType.GetProperty('Tier').GetValue($null, $null)
      $Tier = [int]($RawTier -shr 16)
    }
  } catch {
    $Tier = -1
  }
  try {
    $RenderOptionsType = 'System.Windows.Media.RenderOptions' -as [type]
    if ($null -ne $RenderOptionsType) {
      $ProcessRenderMode = [string]$RenderOptionsType.GetProperty('ProcessRenderMode').GetValue($null, $null)
    }
  } catch {
    $ProcessRenderMode = 'unknown'
  }

  return [ordered]@{
    source = 'wpf_render_capability'
    process_render_mode = $ProcessRenderMode
    render_tier = $Tier
    hardware_acceleration_expected = ($Tier -ge 1 -and $ProcessRenderMode -ne 'SoftwareOnly')
    frame_clock = if ($FrameSyncedMotion) { 'composition_target_rendering' } else { 'manual_drag_only' }
    frame_synced_motion = $FrameSyncedMotion
    motion_integrator = 'elapsed_time_delta_clamped'
  }
}

function Set-OverlayHardwareRenderMode {
  try {
    $RenderOptionsType = 'System.Windows.Media.RenderOptions' -as [type]
    $RenderModeType = 'System.Windows.Interop.RenderMode' -as [type]
    if ($null -ne $RenderOptionsType -and $null -ne $RenderModeType) {
      $DefaultRenderMode = [System.Enum]::Parse($RenderModeType, 'Default')
      $RenderOptionsType.GetProperty('ProcessRenderMode').SetValue($null, $DefaultRenderMode, $null)
    }
  } catch {
  }
}

function New-OrbVisualProjection {
  param(
    [bool]$AutonomousMotion = $false,
    [bool]$ManualDrag = $false
  )

  return [ordered]@{
    source = 'lens_orb_mcp_status_bridge'
    visual_contract = 'chat_ui.orbGlyph.energy_reference'
    renderer = 'wpf_3d_animated_energy_orb'
    animated = $true
    transparent_background = $true
    autonomous_motion = $AutonomousMotion
    right_corner_locked = (-not $AutonomousMotion -and -not $ManualDrag)
    default_anchor = if ($AutonomousMotion) { 'bounded_work_area' } elseif ($ManualDrag) { 'operator_manual' } else { 'bottom_right' }
    motion_profile = if ($AutonomousMotion) { 'bounded_desktop_roam' } elseif ($ManualDrag) { 'manual_drag_only' } else { 'right_corner_locked' }
    motion_clock = if ($AutonomousMotion) { 'composition_target_rendering' } elseif ($ManualDrag) { 'manual_drag_only' } else { 'anchored_static' }
    render_profile = Get-OverlayWpfRenderProfile -FrameSyncedMotion $AutonomousMotion
    manual_drag_supported = $ManualDrag
    desktop_roam_supported = $AutonomousMotion
    desktop_roam_bounds = 'work_area'
    route = '/?francis_lens=orb_overlay'
    grants_execution_authority = $false
    grants_mutation_authority = $false
  }
}

function New-OrbAutonomousMotionState {
  param(
    [object]$Window,
    [object]$WorkArea
  )

  $MinimumLeft = [double]$WorkArea.Left
  $MinimumTop = [double]$WorkArea.Top
  $MaximumLeft = [Math]::Max($MinimumLeft, [double]$WorkArea.Right - [double]$Window.Width)
  $MaximumTop = [Math]::Max($MinimumTop, [double]$WorkArea.Bottom - [double]$Window.Height)
  $RangeX = [Math]::Max(0.0, ($MaximumLeft - $MinimumLeft) / 2.0)
  $RangeY = [Math]::Max(0.0, ($MaximumTop - $MinimumTop) / 2.0)

  return [ordered]@{
    phase = 0.0
    anchor_left = $MinimumLeft + $RangeX
    anchor_top = $MinimumTop + $RangeY
    startup_left = [double]$Window.Left
    startup_top = [double]$Window.Top
    range_x = $RangeX
    range_y = $RangeY
    work_left = $MinimumLeft
    work_top = $MinimumTop
    work_right = [double]$WorkArea.Right
    work_bottom = [double]$WorkArea.Bottom
    roam_left = $MinimumLeft
    roam_top = $MinimumTop
    roam_right = $MaximumLeft
    roam_bottom = $MaximumTop
    desktop_roam_bounds = 'work_area'
    last_frame_seconds = -1.0
  }
}

function Set-OrbWindowDockPosition {
  param(
    [object]$Window,
    [object]$WorkArea,
    [double]$Margin = 48.0
  )

  if ($null -eq $Window -or $null -eq $WorkArea) {
    return
  }

  $Window.Left = [Math]::Max([double]$WorkArea.Left, [double]$WorkArea.Right - [double]$Window.Width - $Margin)
  $Window.Top = [Math]::Max([double]$WorkArea.Top, [double]$WorkArea.Bottom - [double]$Window.Height - $Margin)
}

function Reset-OrbAutonomousMotionAnchor {
  param(
    [object]$Window,
    [object]$MotionState
  )

  if ($null -eq $Window -or $null -eq $MotionState) {
    return
  }
  $MotionState['anchor_left'] = [double]$Window.Left
  $MotionState['anchor_top'] = [double]$Window.Top
  $MotionState['phase'] = 0.0
  $MotionState['last_frame_seconds'] = -1.0
}

function Update-OrbAutonomousMotion {
  param(
    [object]$Window,
    [object]$MotionState,
    [double]$FrameSeconds = -1.0
  )

  if ($null -eq $Window -or $null -eq $MotionState) {
    return
  }

  $DeltaSeconds = 0.08
  if ($FrameSeconds -ge 0.0) {
    $LastFrameSeconds = [double]$MotionState['last_frame_seconds']
    if ($LastFrameSeconds -ge 0.0) {
      $DeltaSeconds = [Math]::Max(0.0, $FrameSeconds - $LastFrameSeconds)
    } else {
      $DeltaSeconds = 0.0
    }
    $MotionState['last_frame_seconds'] = $FrameSeconds
  }
  $DeltaSeconds = [Math]::Min(0.05, $DeltaSeconds)
  $Phase = [double]$MotionState['phase'] + ($DeltaSeconds * 0.425)
  $MotionState['phase'] = $Phase
  $DriftX = ([Math]::Sin($Phase * 0.72) * [double]$MotionState['range_x']) + ([Math]::Sin($Phase * 0.23) * 24.0)
  $DriftY = ([Math]::Sin($Phase * 0.61) * [double]$MotionState['range_y']) + ([Math]::Sin($Phase * 0.31) * 18.0)
  $MinimumLeft = [double]$MotionState['work_left']
  $MinimumTop = [double]$MotionState['work_top']
  $MaximumLeft = [Math]::Max($MinimumLeft, [double]$MotionState['work_right'] - [double]$Window.Width)
  $MaximumTop = [Math]::Max($MinimumTop, [double]$MotionState['work_bottom'] - [double]$Window.Height)
  $TargetLeft = Clamp-OverlayDouble -Value ([double]$MotionState['anchor_left'] + $DriftX) -Minimum $MinimumLeft -Maximum $MaximumLeft
  $TargetTop = Clamp-OverlayDouble -Value ([double]$MotionState['anchor_top'] + $DriftY) -Minimum $MinimumTop -Maximum $MaximumTop
  $Ease = [Math]::Min(1.0, [Math]::Max(0.18, $DeltaSeconds * 12.0))
  $Window.Left = [double]$Window.Left + (($TargetLeft - [double]$Window.Left) * $Ease)
  $Window.Top = [double]$Window.Top + (($TargetTop - [double]$Window.Top) * $Ease)
}

function Set-OverlayStatusProperty {
  param(
    [object]$Payload,
    [string]$Name,
    [object]$Value
  )

  if ($null -eq $Payload) {
    return
  }
  if ($null -ne $Payload.PSObject.Properties[$Name]) {
    $Payload.PSObject.Properties[$Name].Value = $Value
    return
  }
  $Payload | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
}

function New-OverlayWindowPositionProjection {
  param(
    [object]$Window,
    [object]$MotionState,
    [bool]$OverlayWindowVisible,
    [AllowNull()]
    [object]$OrbVisual = $null
  )

  $HasWindow = $null -ne $Window
  $HasMotionState = $null -ne $MotionState
  if ($null -eq $OrbVisual) {
    $OrbVisualVariable = Get-Variable -Name LensOverlayOrbVisual -Scope Script -ErrorAction SilentlyContinue
    if ($null -ne $OrbVisualVariable) {
      $OrbVisual = $OrbVisualVariable.Value
    }
  }
  $AutonomousMotion = if ($null -ne $OrbVisual -and $null -ne $OrbVisual.PSObject.Properties['autonomous_motion']) { [bool]$OrbVisual.autonomous_motion } else { $false }
  $ManualDrag = if ($null -ne $OrbVisual -and $null -ne $OrbVisual.PSObject.Properties['manual_drag_supported']) { [bool]$OrbVisual.manual_drag_supported } else { $false }
  $OperatorPositionAnchor = ''
  $OperatorPositionAnchorVariable = Get-Variable -Name LensOverlayOperatorPositionAnchor -Scope Script -ErrorAction SilentlyContinue
  if ($null -ne $OperatorPositionAnchorVariable) {
    $OperatorPositionAnchor = ([string]$OperatorPositionAnchorVariable.Value).Trim()
  }
  $OperatorPositionAnchored = -not [string]::IsNullOrWhiteSpace($OperatorPositionAnchor)
  $RightCornerLocked = if ($OperatorPositionAnchored) { $false } elseif ($null -ne $OrbVisual -and $null -ne $OrbVisual.PSObject.Properties['right_corner_locked']) { [bool]$OrbVisual.right_corner_locked } else { (-not $AutonomousMotion -and -not $ManualDrag) }
  return [ordered]@{
    status = if ($OverlayWindowVisible -and $HasWindow) { 'visible_position_observed' } elseif ($HasWindow) { 'window_not_visible' } else { 'window_unavailable' }
    left = if ($HasWindow) { [double]$Window.Left } else { 0.0 }
    top = if ($HasWindow) { [double]$Window.Top } else { 0.0 }
    width = if ($HasWindow) { [double]$Window.Width } else { 0.0 }
    height = if ($HasWindow) { [double]$Window.Height } else { 0.0 }
    right_corner_locked = $RightCornerLocked
    default_anchor = if ($OperatorPositionAnchored) { $OperatorPositionAnchor } elseif ($AutonomousMotion) { 'bounded_work_area' } elseif ($ManualDrag) { 'operator_manual' } else { 'bottom_right' }
    operator_position_anchor = $OperatorPositionAnchor
    voice_position_command_active = $OperatorPositionAnchor.StartsWith('voice_command_', [System.StringComparison]::OrdinalIgnoreCase)
    desktop_roam_supported = $AutonomousMotion
    desktop_roam_bounds = 'work_area'
    manual_drag_supported = $ManualDrag
    anchor_left = if ($HasMotionState) { [double]$MotionState['anchor_left'] } else { 0.0 }
    anchor_top = if ($HasMotionState) { [double]$MotionState['anchor_top'] } else { 0.0 }
    range_x = if ($HasMotionState) { [double]$MotionState['range_x'] } else { 0.0 }
    range_y = if ($HasMotionState) { [double]$MotionState['range_y'] } else { 0.0 }
    roam_left = if ($HasMotionState) { [double]$MotionState['roam_left'] } else { 0.0 }
    roam_top = if ($HasMotionState) { [double]$MotionState['roam_top'] } else { 0.0 }
    roam_right = if ($HasMotionState) { [double]$MotionState['roam_right'] } else { 0.0 }
    roam_bottom = if ($HasMotionState) { [double]$MotionState['roam_bottom'] } else { 0.0 }
    startup_left = if ($HasMotionState) { [double]$MotionState['startup_left'] } else { 0.0 }
    startup_top = if ($HasMotionState) { [double]$MotionState['startup_top'] } else { 0.0 }
    grants_execution_authority = $false
    grants_mutation_authority = $false
  }
}

function Write-OverlayPositionState {
  param(
    [string]$Root,
    [object]$Window,
    [object]$MotionState,
    [bool]$OverlayWindowVisible
  )

  if ([string]::IsNullOrWhiteSpace($Root)) {
    return
  }

  $RuntimeRoot = Join-Path $Root 'runtime\lens-overlay'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  $Status = Read-JsonFile -Path $StatusPath
  if ($null -eq $Status) {
    return
  }

  $Position = New-OverlayWindowPositionProjection -Window $Window -MotionState $MotionState -OverlayWindowVisible $OverlayWindowVisible
  Set-OverlayStatusProperty -Payload $Status -Name 'overlay_position' -Value $Position
  Set-OverlayStatusProperty -Payload $Status -Name 'overlay_window_visible' -Value $OverlayWindowVisible
  Set-OverlayStatusProperty -Payload $Status -Name 'always_on_top' -Value (($null -ne $Window) -and [bool]$Window.TopMost)
  Set-OverlayStatusProperty -Payload $Status -Name 'updated_at' -Value ([DateTimeOffset]::UtcNow.ToString('o'))

  $TempPath = Join-Path $RuntimeRoot ("status.{0}.tmp" -f ([Guid]::NewGuid().ToString('N')))
  try {
    $Status | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $TempPath -Encoding UTF8
    Move-OverlayRuntimeStateFile -TempPath $TempPath -DestinationPath $StatusPath
  } finally {
    Remove-Item -LiteralPath $TempPath -Force -ErrorAction SilentlyContinue
  }
}

function Write-OrbAutonomousMotionPositionReceipt {
  param(
    [object]$Window,
    [object]$MotionState,
    [double]$FrameSeconds = -1.0
  )

  if ($null -eq $Window -or $null -eq $MotionState -or [string]::IsNullOrWhiteSpace($script:LensOverlayDataRoot)) {
    return
  }
  if ($FrameSeconds -lt 0.0) {
    return
  }

  $LastReceiptSeconds = [double]$script:LensOverlayLastPositionReceiptSeconds
  if ($LastReceiptSeconds -ge 0.0 -and (($FrameSeconds - $LastReceiptSeconds) -lt 1.0)) {
    return
  }

  $script:LensOverlayLastPositionReceiptSeconds = $FrameSeconds
  Write-OverlayPositionState -Root $script:LensOverlayDataRoot -Window $Window -MotionState $MotionState -OverlayWindowVisible $true
}

function Start-OrbFrameSyncedMotion {
  param(
    [object]$Window,
    [object]$MotionState
  )

  $Clock = [System.Diagnostics.Stopwatch]::StartNew()
  $script:LensOverlayRenderFrameClock = $Clock
  $Handler = [System.EventHandler]{
    param($Sender, $EventArgs)

    $FrameSeconds = if ($null -ne $script:LensOverlayRenderFrameClock) { $script:LensOverlayRenderFrameClock.Elapsed.TotalSeconds } else { -1.0 }
    Update-OrbAutonomousMotion -Window $script:LensOverlayWindow -MotionState $script:LensOverlayMotionState -FrameSeconds $FrameSeconds
    Write-OrbAutonomousMotionPositionReceipt -Window $script:LensOverlayWindow -MotionState $script:LensOverlayMotionState -FrameSeconds $FrameSeconds
  }
  [System.Windows.Media.CompositionTarget]::add_Rendering($Handler)
  return [ordered]@{
    clock = $Clock
    handler = $Handler
  }
}

function Stop-OrbFrameSyncedMotion {
  param([object]$Subscription)

  if ($null -eq $Subscription) {
    return
  }
  try {
    [System.Windows.Media.CompositionTarget]::remove_Rendering($Subscription['handler'])
  } catch {
  }
  try {
    $Subscription['clock'].Stop()
  } catch {
  }
}

function New-OrbTorusMesh {
  param(
    [double]$MajorRadius,
    [double]$TubeRadius,
    [int]$MajorSegments = 96,
    [int]$TubeSegments = 6
  )

  $Mesh = New-Object System.Windows.Media.Media3D.MeshGeometry3D
  for ($MajorIndex = 0; $MajorIndex -lt $MajorSegments; $MajorIndex += 1) {
    $Theta = 2.0 * [Math]::PI * $MajorIndex / $MajorSegments
    $CosTheta = [Math]::Cos($Theta)
    $SinTheta = [Math]::Sin($Theta)
    for ($TubeIndex = 0; $TubeIndex -lt $TubeSegments; $TubeIndex += 1) {
      $Phi = 2.0 * [Math]::PI * $TubeIndex / $TubeSegments
      $CosPhi = [Math]::Cos($Phi)
      $SinPhi = [Math]::Sin($Phi)
      $Radius = $MajorRadius + ($TubeRadius * $CosPhi)
      $X = $Radius * $CosTheta
      $Y = $Radius * $SinTheta
      $Z = $TubeRadius * $SinPhi
      [void]$Mesh.Positions.Add((New-Object System.Windows.Media.Media3D.Point3D -ArgumentList $X, $Y, $Z))
      [void]$Mesh.Normals.Add((New-Object System.Windows.Media.Media3D.Vector3D -ArgumentList ($CosPhi * $CosTheta), ($CosPhi * $SinTheta), $SinPhi))
      [void]$Mesh.TextureCoordinates.Add((New-Object System.Windows.Point -ArgumentList ($MajorIndex / $MajorSegments), ($TubeIndex / $TubeSegments)))
    }
  }

  for ($MajorIndex = 0; $MajorIndex -lt $MajorSegments; $MajorIndex += 1) {
    $NextMajor = ($MajorIndex + 1) % $MajorSegments
    for ($TubeIndex = 0; $TubeIndex -lt $TubeSegments; $TubeIndex += 1) {
      $NextTube = ($TubeIndex + 1) % $TubeSegments
      $A = ($MajorIndex * $TubeSegments) + $TubeIndex
      $B = ($NextMajor * $TubeSegments) + $TubeIndex
      $C = ($NextMajor * $TubeSegments) + $NextTube
      $D = ($MajorIndex * $TubeSegments) + $NextTube
      [void]$Mesh.TriangleIndices.Add([int]$A)
      [void]$Mesh.TriangleIndices.Add([int]$B)
      [void]$Mesh.TriangleIndices.Add([int]$C)
      [void]$Mesh.TriangleIndices.Add([int]$A)
      [void]$Mesh.TriangleIndices.Add([int]$C)
      [void]$Mesh.TriangleIndices.Add([int]$D)
    }
  }

  return $Mesh
}

function New-OrbSphereMesh {
  param(
    [double]$Radius,
    [int]$LatitudeSegments = 18,
    [int]$LongitudeSegments = 36
  )

  $Mesh = New-Object System.Windows.Media.Media3D.MeshGeometry3D
  for ($Lat = 0; $Lat -le $LatitudeSegments; $Lat += 1) {
    $Theta = [Math]::PI * $Lat / $LatitudeSegments
    $SinTheta = [Math]::Sin($Theta)
    $CosTheta = [Math]::Cos($Theta)
    for ($Lon = 0; $Lon -le $LongitudeSegments; $Lon += 1) {
      $Phi = 2.0 * [Math]::PI * $Lon / $LongitudeSegments
      $X = $Radius * $SinTheta * [Math]::Cos($Phi)
      $Y = $Radius * $CosTheta
      $Z = $Radius * $SinTheta * [Math]::Sin($Phi)
      [void]$Mesh.Positions.Add((New-Object System.Windows.Media.Media3D.Point3D -ArgumentList $X, $Y, $Z))
      [void]$Mesh.Normals.Add((New-Object System.Windows.Media.Media3D.Vector3D -ArgumentList ($X / $Radius), ($Y / $Radius), ($Z / $Radius)))
      [void]$Mesh.TextureCoordinates.Add((New-Object System.Windows.Point -ArgumentList ($Lon / $LongitudeSegments), ($Lat / $LatitudeSegments)))
    }
  }

  for ($Lat = 0; $Lat -lt $LatitudeSegments; $Lat += 1) {
    for ($Lon = 0; $Lon -lt $LongitudeSegments; $Lon += 1) {
      $A = ($Lat * ($LongitudeSegments + 1)) + $Lon
      $B = $A + $LongitudeSegments + 1
      $C = $B + 1
      $D = $A + 1
      [void]$Mesh.TriangleIndices.Add([int]$A)
      [void]$Mesh.TriangleIndices.Add([int]$B)
      [void]$Mesh.TriangleIndices.Add([int]$C)
      [void]$Mesh.TriangleIndices.Add([int]$A)
      [void]$Mesh.TriangleIndices.Add([int]$C)
      [void]$Mesh.TriangleIndices.Add([int]$D)
    }
  }

  return $Mesh
}

function New-OrbEnergyMaterial {
  param(
    [int]$Alpha,
    [int]$Red,
    [int]$Green,
    [int]$Blue
  )

  $Brush = New-Object System.Windows.Media.SolidColorBrush (New-OrbArgbColor -Alpha $Alpha -Red $Red -Green $Green -Blue $Blue)
  $Brush.Opacity = [Math]::Min(1.0, [Math]::Max(0.0, $Alpha / 255.0))
  $Material = New-Object System.Windows.Media.Media3D.EmissiveMaterial
  $Material.Brush = $Brush
  return $Material
}

function Add-Orb3DEnergyRing {
  param(
    [object]$ModelGroup,
    [int]$Index
  )

  $MajorRadius = 0.34 + ((($Index * 17) % 22) / 100.0)
  $TubeRadius = 0.0028 + ((($Index * 11) % 8) / 10000.0)
  $Mesh = New-OrbTorusMesh -MajorRadius $MajorRadius -TubeRadius $TubeRadius -MajorSegments 104 -TubeSegments 5
  $Alpha = 58 + (($Index * 23) % 132)
  $Material = New-OrbEnergyMaterial -Alpha $Alpha -Red 226 -Green 238 -Blue 252
  $Geometry = New-Object System.Windows.Media.Media3D.GeometryModel3D
  $Geometry.Geometry = $Mesh
  $Geometry.Material = $Material
  $Geometry.BackMaterial = $Material

  $Transforms = New-Object System.Windows.Media.Media3D.Transform3DGroup
  $Scale = New-Object System.Windows.Media.Media3D.ScaleTransform3D
  $Scale.ScaleX = 0.72 + ((($Index * 19) % 30) / 100.0)
  $Scale.ScaleY = 0.26 + ((($Index * 13) % 38) / 100.0)
  $Scale.ScaleZ = 0.58 + ((($Index * 29) % 30) / 100.0)
  [void]$Transforms.Children.Add($Scale)

  $PreTiltAxis = New-Object System.Windows.Media.Media3D.Vector3D -ArgumentList ((($Index * 3) % 7) - 3), ((($Index * 5) % 9) - 4), ((($Index * 7) % 11) - 5)
  if ($PreTiltAxis.Length -lt 0.1) {
    $PreTiltAxis = New-Object System.Windows.Media.Media3D.Vector3D -ArgumentList 1, 0, 0
  }
  $PreTiltAxis.Normalize()
  $PreTilt = New-Object System.Windows.Media.Media3D.AxisAngleRotation3D -ArgumentList $PreTiltAxis, (($Index * 37) % 360)
  [void]$Transforms.Children.Add((New-Object System.Windows.Media.Media3D.RotateTransform3D -ArgumentList $PreTilt))

  $SpinAxis = New-Object System.Windows.Media.Media3D.Vector3D -ArgumentList ((($Index * 7) % 5) - 2), ((($Index * 11) % 7) - 3), ((($Index * 13) % 9) - 4)
  if ($SpinAxis.Length -lt 0.1) {
    $SpinAxis = New-Object System.Windows.Media.Media3D.Vector3D -ArgumentList 0, 1, 0
  }
  $SpinAxis.Normalize()
  $Spin = New-Object System.Windows.Media.Media3D.AxisAngleRotation3D -ArgumentList $SpinAxis, (($Index * 53) % 360)
  [void]$Transforms.Children.Add((New-Object System.Windows.Media.Media3D.RotateTransform3D -ArgumentList $Spin))

  $Geometry.Transform = $Transforms
  [void]$ModelGroup.Children.Add($Geometry)

  $From = (($Index * 53) % 360)
  $To = if (($Index % 2) -eq 0) { $From + 360 } else { $From - 360 }
  $Spin.BeginAnimation([System.Windows.Media.Media3D.AxisAngleRotation3D]::AngleProperty, (New-OrbRotateAnimation -From $From -To $To -Seconds (12 + (($Index * 5) % 27))))
}

function Add-OrbEllipse {
  param(
    [object]$Canvas,
    [double]$Center,
    [double]$Width,
    [double]$Height,
    [double]$Angle,
    [double]$OffsetX,
    [double]$OffsetY,
    [double]$Opacity,
    [double]$StrokeThickness,
    [int]$Alpha,
    [double]$Seconds,
    [bool]$Reverse
  )

  $Ellipse = New-Object System.Windows.Shapes.Ellipse
  $Ellipse.Width = $Width
  $Ellipse.Height = $Height
  $Ellipse.Fill = $null
  $Ellipse.StrokeThickness = $StrokeThickness
  $Ellipse.Stroke = New-Object System.Windows.Media.SolidColorBrush (New-OrbArgbColor -Alpha $Alpha -Red 224 -Green 236 -Blue 250)
  $Ellipse.Opacity = $Opacity
  $Ellipse.RenderTransformOrigin = New-Object System.Windows.Point(0.5, 0.5)
  $Rotate = New-Object System.Windows.Media.RotateTransform
  $Rotate.Angle = $Angle
  $Ellipse.RenderTransform = $Rotate
  [System.Windows.Controls.Canvas]::SetLeft($Ellipse, $Center - ($Width / 2) + $OffsetX)
  [System.Windows.Controls.Canvas]::SetTop($Ellipse, $Center - ($Height / 2) + $OffsetY)
  if ($StrokeThickness -lt 0.8) {
    $Ellipse.Effect = New-Object System.Windows.Media.Effects.BlurEffect -Property @{ Radius = 0.45 }
  }
  [void]$Canvas.Children.Add($Ellipse)

  $To = if ($Reverse) { $Angle - 360 } else { $Angle + 360 }
  $Rotate.BeginAnimation([System.Windows.Media.RotateTransform]::AngleProperty, (New-OrbRotateAnimation -From $Angle -To $To -Seconds $Seconds))
  $Ellipse.BeginAnimation([System.Windows.UIElement]::OpacityProperty, (New-OrbPulseAnimation -From ([Math]::Max(0.05, $Opacity * 0.58)) -To ([Math]::Min(0.72, $Opacity * 1.35)) -Seconds ([Math]::Max(4, $Seconds / 3))))
}

function New-OrbEnergySurface {
  param([double]$Size = 220)

  $Root = New-Object System.Windows.Controls.Grid
  $Root.Width = $Size
  $Root.Height = $Size
  $Root.Background = [System.Windows.Media.Brushes]::Transparent
  $Root.ClipToBounds = $false

  $GlowCanvas = New-Object System.Windows.Controls.Canvas
  $GlowCanvas.Width = $Size
  $GlowCanvas.Height = $Size
  $GlowCanvas.Background = [System.Windows.Media.Brushes]::Transparent
  $Center = $Size / 2

  $OuterGlow = New-Object System.Windows.Shapes.Ellipse
  $OuterGlow.Width = 148
  $OuterGlow.Height = 148
  $OuterGlow.Opacity = 0.38
  $OuterGlow.Effect = New-Object System.Windows.Media.Effects.BlurEffect -Property @{ Radius = 16 }
  $GlowBrush = New-Object System.Windows.Media.RadialGradientBrush
  $GlowBrush.GradientStops.Add((New-Object System.Windows.Media.GradientStop((New-OrbArgbColor -Alpha 170 -Red 235 -Green 245 -Blue 255), 0.0)))
  $GlowBrush.GradientStops.Add((New-Object System.Windows.Media.GradientStop((New-OrbArgbColor -Alpha 40 -Red 182 -Green 205 -Blue 235), 0.42)))
  $GlowBrush.GradientStops.Add((New-Object System.Windows.Media.GradientStop((New-OrbArgbColor -Alpha 0 -Red 0 -Green 0 -Blue 0), 1.0)))
  $OuterGlow.Fill = $GlowBrush
  [System.Windows.Controls.Canvas]::SetLeft($OuterGlow, $Center - 74)
  [System.Windows.Controls.Canvas]::SetTop($OuterGlow, $Center - 74)
  [void]$GlowCanvas.Children.Add($OuterGlow)
  [void]$Root.Children.Add($GlowCanvas)

  $Viewport = New-Object System.Windows.Controls.Viewport3D
  $Viewport.Width = $Size
  $Viewport.Height = $Size
  $Viewport.ClipToBounds = $false
  $Viewport.IsHitTestVisible = $false
  $Camera = New-Object System.Windows.Media.Media3D.PerspectiveCamera
  $Camera.Position = New-Object System.Windows.Media.Media3D.Point3D -ArgumentList 0, 0, 3.2
  $Camera.LookDirection = New-Object System.Windows.Media.Media3D.Vector3D -ArgumentList 0, 0, -3.2
  $Camera.UpDirection = New-Object System.Windows.Media.Media3D.Vector3D -ArgumentList 0, 1, 0
  $Camera.FieldOfView = 56
  $Viewport.Camera = $Camera

  $ModelGroup = New-Object System.Windows.Media.Media3D.Model3DGroup
  [void]$ModelGroup.Children.Add((New-Object System.Windows.Media.Media3D.AmbientLight -ArgumentList (New-OrbArgbColor -Alpha 255 -Red 140 -Green 170 -Blue 205)))
  [void]$ModelGroup.Children.Add((New-Object System.Windows.Media.Media3D.DirectionalLight -ArgumentList (New-OrbArgbColor -Alpha 255 -Red 255 -Green 255 -Blue 255), (New-Object System.Windows.Media.Media3D.Vector3D -ArgumentList -0.2, -0.4, -1.0)))

  for ($Index = 0; $Index -lt 38; $Index += 1) {
    Add-Orb3DEnergyRing -ModelGroup $ModelGroup -Index $Index
  }

  $CoreMesh = New-OrbSphereMesh -Radius 0.24 -LatitudeSegments 22 -LongitudeSegments 44
  $CoreMaterial = New-OrbEnergyMaterial -Alpha 235 -Red 248 -Green 252 -Blue 255
  $CoreGeometry = New-Object System.Windows.Media.Media3D.GeometryModel3D
  $CoreGeometry.Geometry = $CoreMesh
  $CoreGeometry.Material = $CoreMaterial
  $CoreGeometry.BackMaterial = $CoreMaterial
  $CoreScale = New-Object System.Windows.Media.Media3D.ScaleTransform3D
  $CoreScale.ScaleX = 1.0
  $CoreScale.ScaleY = 0.9
  $CoreScale.ScaleZ = 1.0
  $CoreGeometry.Transform = $CoreScale
  [void]$ModelGroup.Children.Add($CoreGeometry)
  $CoreScale.BeginAnimation([System.Windows.Media.Media3D.ScaleTransform3D]::ScaleXProperty, (New-OrbPulseAnimation -From 0.84 -To 1.08 -Seconds 3.2))
  $CoreScale.BeginAnimation([System.Windows.Media.Media3D.ScaleTransform3D]::ScaleYProperty, (New-OrbPulseAnimation -From 0.78 -To 1.02 -Seconds 3.2))
  $CoreScale.BeginAnimation([System.Windows.Media.Media3D.ScaleTransform3D]::ScaleZProperty, (New-OrbPulseAnimation -From 0.9 -To 1.16 -Seconds 3.2))

  $ModelVisual = New-Object System.Windows.Media.Media3D.ModelVisual3D
  $ModelVisual.Content = $ModelGroup
  [void]$Viewport.Children.Add($ModelVisual)
  [void]$Root.Children.Add($Viewport)

  $Canvas = New-Object System.Windows.Controls.Canvas
  $Canvas.Width = $Size
  $Canvas.Height = $Size
  $Canvas.Background = [System.Windows.Media.Brushes]::Transparent
  $Canvas.IsHitTestVisible = $false

  for ($Index = 0; $Index -lt 56; $Index += 1) {
    $Width = 42 + (($Index * 29) % 76)
    $Height = 14 + (($Index * 17) % 50)
    $Angle = (($Index * 137.507) % 360) + ((($Index * 19) % 34) - 17)
    $OffsetX = (($Index * 23) % 24) - 12
    $OffsetY = (($Index * 31) % 24) - 12
    $Opacity = 0.08 + ((($Index * 13) % 22) / 100.0)
    $Alpha = 65 + (($Index * 11) % 95)
    $Seconds = 11 + (($Index * 7) % 29)
    Add-OrbEllipse -Canvas $Canvas -Center $Center -Width $Width -Height $Height -Angle $Angle -OffsetX $OffsetX -OffsetY $OffsetY -Opacity $Opacity -StrokeThickness 0.55 -Alpha $Alpha -Seconds $Seconds -Reverse (($Index % 2) -eq 0)
  }

  for ($Index = 0; $Index -lt 12; $Index += 1) {
    $Width = 58 + (($Index * 17) % 58)
    $Height = 18 + (($Index * 11) % 38)
    $Angle = (($Index * 41) % 360)
    $OffsetX = (($Index * 7) % 16) - 8
    $OffsetY = (($Index * 13) % 18) - 9
    Add-OrbEllipse -Canvas $Canvas -Center $Center -Width $Width -Height $Height -Angle $Angle -OffsetX $OffsetX -OffsetY $OffsetY -Opacity 0.22 -StrokeThickness 0.9 -Alpha 150 -Seconds (16 + $Index) -Reverse (($Index % 2) -eq 1)
  }

  $Core = New-Object System.Windows.Shapes.Ellipse
  $Core.Width = 64
  $Core.Height = 64
  $Core.Effect = New-Object System.Windows.Media.Effects.BlurEffect -Property @{ Radius = 1.6 }
  $CoreBrush = New-Object System.Windows.Media.RadialGradientBrush
  $CoreBrush.GradientStops.Add((New-Object System.Windows.Media.GradientStop((New-OrbArgbColor -Alpha 255 -Red 255 -Green 255 -Blue 255), 0.0)))
  $CoreBrush.GradientStops.Add((New-Object System.Windows.Media.GradientStop((New-OrbArgbColor -Alpha 235 -Red 230 -Green 240 -Blue 252), 0.24)))
  $CoreBrush.GradientStops.Add((New-Object System.Windows.Media.GradientStop((New-OrbArgbColor -Alpha 160 -Red 128 -Green 146 -Blue 168), 0.52)))
  $CoreBrush.GradientStops.Add((New-Object System.Windows.Media.GradientStop((New-OrbArgbColor -Alpha 35 -Red 9 -Green 14 -Blue 24), 1.0)))
  $Core.Fill = $CoreBrush
  $Core.RenderTransformOrigin = New-Object System.Windows.Point(0.5, 0.5)
  $CoreScale = New-Object System.Windows.Media.ScaleTransform
  $CoreScale.ScaleX = 1
  $CoreScale.ScaleY = 1
  $Core.RenderTransform = $CoreScale
  [System.Windows.Controls.Canvas]::SetLeft($Core, $Center - 32)
  [System.Windows.Controls.Canvas]::SetTop($Core, $Center - 32)
  [void]$Canvas.Children.Add($Core)
  $Core.BeginAnimation([System.Windows.UIElement]::OpacityProperty, (New-OrbPulseAnimation -From 0.74 -To 1.0 -Seconds 2.8))
  $CoreScale.BeginAnimation([System.Windows.Media.ScaleTransform]::ScaleXProperty, (New-OrbPulseAnimation -From 0.92 -To 1.08 -Seconds 3.2))
  $CoreScale.BeginAnimation([System.Windows.Media.ScaleTransform]::ScaleYProperty, (New-OrbPulseAnimation -From 0.94 -To 1.06 -Seconds 3.2))

  $HotCenter = New-Object System.Windows.Shapes.Ellipse
  $HotCenter.Width = 34
  $HotCenter.Height = 34
  $HotCenter.Effect = New-Object System.Windows.Media.Effects.BlurEffect -Property @{ Radius = 3.2 }
  $HotBrush = New-Object System.Windows.Media.RadialGradientBrush
  $HotBrush.GradientStops.Add((New-Object System.Windows.Media.GradientStop((New-OrbArgbColor -Alpha 255 -Red 255 -Green 255 -Blue 255), 0.0)))
  $HotBrush.GradientStops.Add((New-Object System.Windows.Media.GradientStop((New-OrbArgbColor -Alpha 160 -Red 255 -Green 255 -Blue 255), 0.48)))
  $HotBrush.GradientStops.Add((New-Object System.Windows.Media.GradientStop((New-OrbArgbColor -Alpha 0 -Red 255 -Green 255 -Blue 255), 1.0)))
  $HotCenter.Fill = $HotBrush
  [System.Windows.Controls.Canvas]::SetLeft($HotCenter, $Center - 17)
  [System.Windows.Controls.Canvas]::SetTop($HotCenter, $Center - 17)
  [void]$Canvas.Children.Add($HotCenter)
  $HotCenter.BeginAnimation([System.Windows.UIElement]::OpacityProperty, (New-OrbPulseAnimation -From 0.72 -To 1.0 -Seconds 1.9))

  [void]$Root.Children.Add($Canvas)
  return $Root
}

function Update-OverlayMcpBodyStateLabel {
  param(
    [object]$Label,
    [object]$Config,
    [string]$Root
  )

  $BodyState = Read-McpBodyStateForOverlay -McpStatusRoute $Config.mcp_status_route -OrbMcpStatusRoute $Config.orb_mcp_status_route -TimeoutSeconds $McpBodyStateTimeoutSeconds
  Set-OverlayLabelText -Label $Label -Text (Format-McpBodyStateLabel -BodyState $BodyState)
  if ($null -ne $script:LensOverlayEnergyRoot) {
    $script:LensOverlayEnergyRoot.Opacity = if (Get-OrbEnergyReady -BodyState $BodyState) { 1.0 } else { 0.72 }
  }
  Write-OverlayState -Root $Root -Status 'overlay_running' -OverlayWindowVisible $true -AlwaysOnTop $true -Message 'Francis Lens overlay window is running with MCP body-state readback.' -McpBodyState $BodyState -OrbVisual $script:LensOverlayOrbVisual -OverlayVoice $script:LensOverlayRuntimeVoice
}

function Update-OverlayMcpBodyStateLabelSafely {
  param(
    [object]$Label,
    [object]$Config,
    [string]$Root
  )

  try {
    Update-OverlayMcpBodyStateLabel -Label $Label -Config $Config -Root $Root
  } catch {
    $ErrorMessage = [string]$_.Exception.Message
    if ($ErrorMessage.Length -gt 300) {
      $ErrorMessage = $ErrorMessage.Substring(0, 300)
    }
    $BodyState = New-McpBodyStateProjection -McpStatusRoute $Config.mcp_status_route -OrbMcpStatusRoute $Config.orb_mcp_status_route
    Set-McpBodyStateValue -Projection $BodyState -Name 'live_status' -Value 'refresh_failed'
    Set-McpBodyStateValue -Projection $BodyState -Name 'error' -Value $ErrorMessage
    Set-McpBodyStateValue -Projection $BodyState -Name 'message' -Value 'Overlay runtime stayed visible after MCP body-state refresh failed.'
    try {
      Set-OverlayLabelText -Label $Label -Text (Format-McpBodyStateLabel -BodyState $BodyState)
    } catch {
    }
    try {
      Write-OverlayState -Root $Root -Status 'overlay_running' -OverlayWindowVisible $true -AlwaysOnTop $true -Message 'Francis Lens overlay window is running; MCP body-state readback refresh failed.' -McpBodyState $BodyState -OrbVisual $script:LensOverlayOrbVisual -OverlayVoice $script:LensOverlayRuntimeVoice
    } catch {
    }
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

function New-OverlayVoiceProjection {
  param(
    [string]$SelectedVoiceName = $VoiceName,
    [string]$Provider = $VoiceProvider,
    [bool]$WakeListening = $false,
    [string]$WakePhraseText = $WakePhrase
  )

  $UsingRemoteTts = $Provider -eq 'ElevenLabs'
  $ResolvedSelectedVoice = if ($UsingRemoteTts) {
    Get-ElevenLabsVoiceLabel -RequestedVoiceId $ElevenLabsVoiceId -FallbackLabel $SelectedVoiceName
  } else {
    $SelectedVoiceName
  }
  return [ordered]@{
    kind = 'lens.overlay.voice.runtime'
    status = 'available'
    source = if ($UsingRemoteTts) { 'elevenlabs_text_to_speech' } else { 'windows_sapi_speech_synthesis' }
    voice_provider = $Provider
    voice_persona = 'Francis'
    francis_surface = 'orb_voice'
    embodied_by = 'francis_orb'
    orb_role = 'embodiment'
    voice_lens_orb_identity = 'Francis'
    voice_lens_orb_are_francis_surfaces = $true
    voice_lens_orb_are_separate_identities = $false
    voice_lens_orb_separate_identities = $false
    speech_output = $true
    microphone_capture = $WakeListening
    voice_input = if ($WakeListening) { 'explicit_wake_phrase_or_wake_prefixed_utterance' } else { 'disabled_requires_explicit_microphone_authority' }
    wake_listening = $WakeListening
    wake_phrase = if ($WakeListening) { $WakePhraseText } else { '' }
    selected_voice = $ResolvedSelectedVoice
    remote_processing = $UsingRemoteTts
    remote_provider = if ($UsingRemoteTts) { 'elevenlabs' } else { '' }
    sends_text_to_remote_provider = $UsingRemoteTts
    stores_audio = $false
    audio_retention = if ($UsingRemoteTts) { 'transient_deleted_after_playback' } else { 'none' }
    stores_transcript = $false
    transcript_redacted = $true
    requires_explicit_speak_command = $true
    grants_execution_authority = $false
    grants_mutation_authority = $false
    updated_at = [DateTimeOffset]::UtcNow.ToString('o')
    message = if ($UsingRemoteTts) {
      if ($WakeListening) { 'Remote ElevenLabs speech output and explicit local wake-phrase listening are configured.' } else { 'Remote ElevenLabs speech output is configured; microphone capture is not enabled.' }
    } else {
      if ($WakeListening) { 'Local speech output and explicit wake-phrase listening are available.' } else { 'Local speech output is available; microphone capture is not enabled.' }
    }
  }
}

function New-OverlayRuntimeVoiceProjection {
  param(
    [string]$Provider = $VoiceProvider,
    [string]$Voice = $VoiceName,
    [bool]$WakeListening = $false,
    [string]$WakePhraseText = $WakePhrase,
    [string]$Status = '',
    [double]$ConfidenceThreshold = $WakeConfidenceThreshold,
    [int]$WakeAliasCount = 0
  )

  $SelectedVoice = Get-OverlaySelectedVoiceName -Provider $Provider -Voice $Voice -RequestedVoiceId $ElevenLabsVoiceId
  $Payload = New-OverlayVoiceProjection -SelectedVoiceName $SelectedVoice -Provider $Provider -WakeListening $WakeListening -WakePhraseText $WakePhraseText
  $Payload.status = if (-not [string]::IsNullOrWhiteSpace($Status)) {
    $Status
  } elseif ($WakeListening) {
    'listening'
  } else {
    'configured'
  }
  $Payload.ok = $Payload.status -ne 'listen_failed'
  $Payload.persistent_overlay_readback = $true
  $Payload.last_speech_receipt = $false
  $Payload.wake_confidence_threshold = $ConfidenceThreshold
  $Payload.wake_alias_count = $WakeAliasCount
  $Payload.transcript_redacted = $true
  $Payload.audio_observed = $false
  $Payload.audio_event_count = 0
  $Payload.has_observed_microphone_signal = $false
  $Payload.microphone_signal_status = if ($WakeListening) { 'unknown_until_audio_signal' } else { 'not_capturing' }
  $Payload.microphone_input_effective = $false
  $Payload.needs_operator_audio_input_check = $false
  $Payload.microphone_gate_while_speaking = 'francis_stop_only'
  $Payload.conversation_forwarding_while_speaking = $false
  $Payload.speech_detected = $false
  $Payload.speech_detected_count = 0
  $Payload.speech_hypothesis_count = 0
  $Payload.speech_rejected_count = 0
  $Payload.speech_recognition_diagnostics = 'redacted_counts_only'
  return $Payload
}

function Get-OverlayAudioCaptureEndpointReadback {
  $Payload = [ordered]@{
    kind = 'lens.overlay.audio_capture_endpoints'
    status = 'not_windows'
    source = 'windows_pnp_audio_endpoint'
    read_only = $true
    query_supported = $false
    capture_endpoint_count = 0
    active_capture_endpoint_count = 0
    unknown_capture_endpoint_count = 0
    capture_endpoint_names = @()
    active_capture_endpoint_names = @()
    endpoints = @()
    endpoint_instance_ids_redacted = $true
    default_capture_endpoint_resolved = $false
    default_capture_endpoint_reason = 'default_capture_endpoint_not_queried'
    explicit_endpoint_selection_supported = $false
    grants_execution_authority = $false
    grants_mutation_authority = $false
    message = 'Audio capture endpoint readback is only available on Windows.'
  }

  if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    return $Payload
  }

  $PnpCommand = Get-Command -Name Get-PnpDevice -ErrorAction SilentlyContinue
  if ($null -eq $PnpCommand) {
    $Payload.status = 'unavailable'
    $Payload.message = 'Get-PnpDevice is not available for read-only capture endpoint inspection.'
    return $Payload
  }

  try {
    $Endpoints = @(
      Get-PnpDevice -Class AudioEndpoint -ErrorAction Stop |
        Where-Object { [string]$_.InstanceId -like 'SWD\MMDEVAPI\{0.0.1.*' }
    )
  } catch {
    $Payload.status = 'query_failed'
    $Payload.error_type = [string]$_.Exception.GetType().Name
    $Payload.message = 'Windows audio capture endpoint inspection failed.'
    return $Payload
  }

  $EndpointItems = [System.Collections.ArrayList]::new()
  $EndpointNames = [System.Collections.ArrayList]::new()
  $ActiveEndpointNames = [System.Collections.ArrayList]::new()
  $UnknownCount = 0
  foreach ($Endpoint in $Endpoints) {
    $Name = Get-StringProperty -Payload $Endpoint -Name 'FriendlyName' -Default ''
    $Status = Get-StringProperty -Payload $Endpoint -Name 'Status' -Default ''
    if ([string]::IsNullOrWhiteSpace($Name)) {
      $Name = 'unnamed_capture_endpoint'
    }
    if ([string]::IsNullOrWhiteSpace($Status)) {
      $Status = 'Unknown'
    }
    if ($Status -eq 'Unknown') {
      $UnknownCount += 1
    }
    [void]$EndpointNames.Add($Name)
    if ($Status -eq 'OK') {
      [void]$ActiveEndpointNames.Add($Name)
    }
    [void]$EndpointItems.Add([ordered]@{
        name = $Name
        status = $Status
        instance_id_redacted = $true
      })
  }

  $Payload.status = 'available'
  $Payload.query_supported = $true
  $Payload.capture_endpoint_count = $Endpoints.Count
  $Payload.active_capture_endpoint_count = $ActiveEndpointNames.Count
  $Payload.unknown_capture_endpoint_count = $UnknownCount
  $Payload.capture_endpoint_names = @($EndpointNames.ToArray())
  $Payload.active_capture_endpoint_names = @($ActiveEndpointNames.ToArray())
  $Payload.endpoints = @($EndpointItems.ToArray())
  $Payload.default_capture_endpoint_reason = 'current_overlay_uses_system_speech_default_audio_device'
  $Payload.message = if ($ActiveEndpointNames.Count -gt 0) {
    'Windows reports at least one active audio capture endpoint; verify the default input device and mute/signal state.'
  } elseif ($Endpoints.Count -gt 0) {
    'Windows reports capture endpoints, but none are active.'
  } else {
    'Windows reports no audio capture endpoints.'
  }
  return $Payload
}

function Get-OverlaySpeechAudioInputTokenReadback {
  $Payload = [ordered]@{
    kind = 'lens.overlay.speech_audio_input_tokens'
    status = 'not_windows'
    source = 'windows_sapi_audio_input_registry'
    read_only = $true
    query_supported = $false
    token_count = 0
    token_names = @()
    tokens = @()
    token_device_ids_redacted = $true
    grants_execution_authority = $false
    grants_mutation_authority = $false
    message = 'Speech audio-input token readback is only available on Windows.'
  }

  if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    return $Payload
  }

  $TokenRoot = 'HKCU:\Software\Microsoft\Speech\AudioInput\TokenEnums\MMAudioIn'
  if (-not (Test-Path -LiteralPath $TokenRoot)) {
    $Payload.status = 'missing'
    $Payload.query_supported = $true
    $Payload.message = 'Windows Speech has no current-user MMAudioIn token registrations.'
    return $Payload
  }

  try {
    $TokenKeys = @(Get-ChildItem -LiteralPath $TokenRoot -ErrorAction Stop)
  } catch {
    $Payload.status = 'query_failed'
    $Payload.error_type = [string]$_.Exception.GetType().Name
    $Payload.message = 'Windows Speech audio-input token inspection failed.'
    return $Payload
  }

  $TokenItems = [System.Collections.ArrayList]::new()
  $TokenNames = [System.Collections.ArrayList]::new()
  foreach ($TokenKey in $TokenKeys) {
    $Properties = Get-ItemProperty -LiteralPath $TokenKey.PSPath -ErrorAction SilentlyContinue
    $TokenName = Get-StringProperty -Payload $Properties -Name '(default)' -Default ''
    if ([string]::IsNullOrWhiteSpace($TokenName)) {
      $TokenName = $TokenKey.PSChildName
    }
    [void]$TokenNames.Add($TokenName)
    [void]$TokenItems.Add([ordered]@{
        name = $TokenName
        device_id_redacted = $true
      })
  }

  $Payload.status = 'available'
  $Payload.query_supported = $true
  $Payload.token_count = $TokenItems.Count
  $Payload.token_names = @($TokenNames.ToArray())
  $Payload.tokens = @($TokenItems.ToArray())
  $Payload.message = if ($TokenItems.Count -gt 0) {
    'Windows Speech has registered audio-input token(s); verify mute, privacy access, and live signal.'
  } else {
    'Windows Speech has no registered audio-input tokens.'
  }
  return $Payload
}

function Get-OverlayDefaultCaptureEndpointReadback {
  $Payload = [ordered]@{
    kind = 'lens.overlay.default_capture_endpoint'
    status = 'not_windows'
    source = 'windows_coreaudio_default_capture_endpoint'
    read_only = $true
    query_supported = $false
    role = 'communications'
    resolved = $false
    endpoint_id_redacted = $true
    endpoint_state = -1
    muted = $null
    volume_scalar = $null
    channel_count = 0
    grants_execution_authority = $false
    grants_mutation_authority = $false
    message = 'Default capture endpoint readback is only available on Windows.'
  }

  if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    return $Payload
  }

  $TypeName = 'LensOverlayCoreAudioProbe'
  if ($null -eq ($TypeName -as [type])) {
    $Code = @'
using System;
using System.Globalization;
using System.Runtime.InteropServices;

public static class LensOverlayCoreAudioProbe {
  enum EDataFlow { eRender = 0, eCapture = 1, eAll = 2 }
  enum ERole { eConsole = 0, eMultimedia = 1, eCommunications = 2 }

  [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
  class MMDeviceEnumeratorComObject {}

  [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("A95664D2-9614-4F35-A746-DE8DB63617E6")]
  interface IMMDeviceEnumerator {
    int EnumAudioEndpoints(EDataFlow dataFlow, int dwStateMask, IntPtr ppDevices);
    int GetDefaultAudioEndpoint(EDataFlow dataFlow, ERole role, out IMMDevice ppEndpoint);
    int GetDevice([MarshalAs(UnmanagedType.LPWStr)] string pwstrId, out IMMDevice ppDevice);
    int RegisterEndpointNotificationCallback(IntPtr pClient);
    int UnregisterEndpointNotificationCallback(IntPtr pClient);
  }

  [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("D666063F-1587-4E43-81F1-B948E807363F")]
  interface IMMDevice {
    int Activate(ref Guid iid, int dwClsCtx, IntPtr pActivationParams, out IAudioEndpointVolume ppInterface);
    int OpenPropertyStore(int stgmAccess, IntPtr ppProperties);
    int GetId([MarshalAs(UnmanagedType.LPWStr)] out string ppstrId);
    int GetState(out int pdwState);
  }

  [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("5CDF2C82-841E-4546-9722-0CF74078229A")]
  interface IAudioEndpointVolume {
    int RegisterControlChangeNotify(IntPtr pNotify);
    int UnregisterControlChangeNotify(IntPtr pNotify);
    int GetChannelCount(out uint pnChannelCount);
    int SetMasterVolumeLevel(float fLevelDB, Guid pguidEventContext);
    int SetMasterVolumeLevelScalar(float fLevel, Guid pguidEventContext);
    int GetMasterVolumeLevel(out float pfLevelDB);
    int GetMasterVolumeLevelScalar(out float pfLevel);
    int SetChannelVolumeLevel(uint nChannel, float fLevelDB, Guid pguidEventContext);
    int SetChannelVolumeLevelScalar(uint nChannel, float fLevel, Guid pguidEventContext);
    int GetChannelVolumeLevel(uint nChannel, out float pfLevelDB);
    int GetChannelVolumeLevelScalar(uint nChannel, out float pfLevel);
    int SetMute([MarshalAs(UnmanagedType.Bool)] bool bMute, Guid pguidEventContext);
    int GetMute([MarshalAs(UnmanagedType.Bool)] out bool pbMute);
    int GetVolumeStepInfo(out uint pnStep, out uint pnStepCount);
    int VolumeStepUp(Guid pguidEventContext);
    int VolumeStepDown(Guid pguidEventContext);
    int QueryHardwareSupport(out uint pdwHardwareSupportMask);
    int GetVolumeRange(out float pflVolumeMindB, out float pflVolumeMaxdB, out float pflVolumeIncrementdB);
  }

  public static string GetDefaultCaptureEndpointJson() {
    var enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
    IMMDevice device;
    int hr = enumerator.GetDefaultAudioEndpoint(EDataFlow.eCapture, ERole.eCommunications, out device);
    if (hr != 0 || device == null) {
      return "{\"ok\":false,\"stage\":\"get_default_audio_endpoint\",\"hr\":" + hr.ToString(CultureInfo.InvariantCulture) + "}";
    }

    string id = "";
    int state = -1;
    device.GetId(out id);
    device.GetState(out state);

    Guid iid = new Guid("5CDF2C82-841E-4546-9722-0CF74078229A");
    IAudioEndpointVolume volume;
    hr = device.Activate(ref iid, 23, IntPtr.Zero, out volume);
    if (hr != 0 || volume == null) {
      return "{\"ok\":false,\"stage\":\"activate_endpoint_volume\",\"hr\":" + hr.ToString(CultureInfo.InvariantCulture) + ",\"state\":" + state.ToString(CultureInfo.InvariantCulture) + "}";
    }

    bool muted;
    float scalar;
    uint channels;
    volume.GetMute(out muted);
    volume.GetMasterVolumeLevelScalar(out scalar);
    volume.GetChannelCount(out channels);

    return "{\"ok\":true,\"state\":" + state.ToString(CultureInfo.InvariantCulture) +
      ",\"muted\":" + (muted ? "true" : "false") +
      ",\"volume_scalar\":" + scalar.ToString(CultureInfo.InvariantCulture) +
      ",\"channel_count\":" + channels.ToString(CultureInfo.InvariantCulture) +
      ",\"endpoint_id_present\":" + (!String.IsNullOrWhiteSpace(id) ? "true" : "false") + "}";
  }
}
'@
    try {
      Add-Type -TypeDefinition $Code -ErrorAction Stop
    } catch {
      $Payload.status = 'query_failed'
      $Payload.error_type = [string]$_.Exception.GetType().Name
      $Payload.message = 'CoreAudio probe type could not be loaded.'
      return $Payload
    }
  }

  try {
    $ProbeJson = [LensOverlayCoreAudioProbe]::GetDefaultCaptureEndpointJson()
    $Probe = $ProbeJson | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $Payload.status = 'query_failed'
    $Payload.error_type = [string]$_.Exception.GetType().Name
    $Payload.message = 'CoreAudio default capture endpoint inspection failed.'
    return $Payload
  }

  $Payload.query_supported = $true
  if (-not (Get-BoolProperty -Payload $Probe -Name 'ok' -Default $false)) {
    $Payload.status = 'query_failed'
    $Payload.error_stage = Get-StringProperty -Payload $Probe -Name 'stage' -Default ''
    $Payload.endpoint_state = Get-IntegerProperty -Payload $Probe -Name 'state' -Default -1
    $Payload.message = 'CoreAudio default capture endpoint inspection did not return usable endpoint volume state.'
    return $Payload
  }

  $Payload.status = 'available'
  $Payload.resolved = $true
  $Payload.endpoint_state = Get-IntegerProperty -Payload $Probe -Name 'state' -Default -1
  $Payload.muted = Get-BoolProperty -Payload $Probe -Name 'muted' -Default $false
  $Payload.volume_scalar = [double](Get-StringProperty -Payload $Probe -Name 'volume_scalar' -Default '0')
  $Payload.channel_count = Get-IntegerProperty -Payload $Probe -Name 'channel_count' -Default 0
  $Payload.endpoint_id_present = Get-BoolProperty -Payload $Probe -Name 'endpoint_id_present' -Default $false
  $Payload.message = if ([bool]$Payload.muted) {
    'CoreAudio default capture endpoint is muted.'
  } elseif ([double]$Payload.volume_scalar -le 0) {
    'CoreAudio default capture endpoint volume is zero.'
  } else {
    'CoreAudio default capture endpoint is resolved, unmuted, and has nonzero volume.'
  }
  return $Payload
}

function Get-OverlayVoiceInputReadiness {
  param([object]$Voice)

  $WakeListening = Get-BoolProperty -Payload $Voice -Name 'wake_listening' -Default $false
  $MicrophoneCapture = Get-BoolProperty -Payload $Voice -Name 'microphone_capture' -Default $false
  $MicrophoneInputEffective = Get-BoolProperty -Payload $Voice -Name 'microphone_input_effective' -Default $false
  $NeedsOperatorAudioInputCheck = Get-BoolProperty -Payload $Voice -Name 'needs_operator_audio_input_check' -Default $false
  $Ok = Get-BoolProperty -Payload $Voice -Name 'ok' -Default $true
  $VoiceStatus = Get-StringProperty -Payload $Voice -Name 'status' -Default ''
  $MicrophoneSignalStatus = Get-StringProperty -Payload $Voice -Name 'microphone_signal_status' -Default 'unknown'
  $AudioSignalProblem = Get-StringProperty -Payload $Voice -Name 'audio_signal_problem' -Default ''
  $AudioLevel = Get-IntegerProperty -Payload $Voice -Name 'audio_level' -Default 0
  $AudioCaptureEndpoints = Get-OverlayAudioCaptureEndpointReadback
  $SpeechAudioInputTokens = Get-OverlaySpeechAudioInputTokenReadback
  $DefaultCaptureEndpoint = Get-OverlayDefaultCaptureEndpointReadback

  $Ready = $false
  $Status = 'not_listening'
  $Blocker = 'wake_listener_not_active'
  $NextOperatorStep = 'start_overlay_with_wake_listener'
  $Message = 'Wake listener is not active.'

  if ($VoiceStatus -eq 'listen_failed' -or -not $Ok) {
    $Status = 'blocked'
    $Blocker = 'wake_listener_failed'
    $NextOperatorStep = 'inspect_lens_overlay_voice_status'
    $Message = 'Wake listener failed before usable microphone input was confirmed.'
  } elseif ($WakeListening -and $MicrophoneCapture) {
    if ($MicrophoneSignalStatus -eq 'no_signal') {
      $Status = 'blocked'
      $Blocker = 'microphone_no_signal'
      $NextOperatorStep = 'select_or_unmute_default_windows_microphone'
      $Message = 'Wake listener is attached, but the default Windows microphone is reporting no signal.'
    } elseif ($MicrophoneSignalStatus -eq 'audio_signal_problem') {
      $Status = 'blocked'
      $Blocker = 'microphone_signal_problem'
      $NextOperatorStep = 'check_windows_microphone_access_and_default_input'
      $Message = 'Wake listener is attached, but Windows reported an audio signal problem.'
    } elseif ($MicrophoneInputEffective -or $MicrophoneSignalStatus -eq 'signal_observed') {
      $Ready = $true
      $Status = 'ready'
      $Blocker = ''
      $NextOperatorStep = 'say_hey_francis_with_a_wake_prefixed_request'
      $Message = 'Wake listener has observed microphone signal.'
    } else {
      $Status = 'waiting_for_audio_signal'
      $Blocker = ''
      $NextOperatorStep = 'say_hey_francis_to_confirm_default_microphone_signal'
      $Message = 'Wake listener is attached and waiting to observe microphone signal.'
    }
  }

  return [ordered]@{
    kind = 'lens.overlay.voice_input_readiness'
    ready = $Ready
    status = $Status
    blocker = $Blocker
    next_operator_step = $NextOperatorStep
    message = $Message
    wake_listening = $WakeListening
    microphone_capture = $MicrophoneCapture
    microphone_signal_status = $MicrophoneSignalStatus
    microphone_input_effective = $MicrophoneInputEffective
    needs_operator_audio_input_check = $NeedsOperatorAudioInputCheck
    audio_signal_problem = $AudioSignalProblem
    audio_level = $AudioLevel
    audio_capture_endpoints = $AudioCaptureEndpoints
    capture_endpoint_count = [int]$AudioCaptureEndpoints.capture_endpoint_count
    active_capture_endpoint_count = [int]$AudioCaptureEndpoints.active_capture_endpoint_count
    default_capture_endpoint = $DefaultCaptureEndpoint
    default_capture_endpoint_resolved = [bool]$DefaultCaptureEndpoint.resolved
    default_capture_endpoint_muted = $DefaultCaptureEndpoint.muted
    default_capture_endpoint_volume_scalar = $DefaultCaptureEndpoint.volume_scalar
    explicit_endpoint_selection_supported = [bool]$AudioCaptureEndpoints.explicit_endpoint_selection_supported
    speech_audio_input_tokens = $SpeechAudioInputTokens
    speech_audio_input_token_count = [int]$SpeechAudioInputTokens.token_count
    transcript_redacted = $true
    grants_execution_authority = $false
    grants_mutation_authority = $false
  }
}

function Get-VoiceEnvironmentTargets {
  param([string]$Scope)

  if ($Scope -eq 'ProcessOnly') {
    return @([System.EnvironmentVariableTarget]::Process)
  }
  return @(
    [System.EnvironmentVariableTarget]::Process,
    [System.EnvironmentVariableTarget]::User,
    [System.EnvironmentVariableTarget]::Machine
  )
}

function Get-VoiceEnvironmentScopeNames {
  param([string]$Scope)

  if ($Scope -eq 'ProcessOnly') {
    return @('Process')
  }
  return @('Process', 'User', 'Machine')
}

function Get-ScopedEnvironmentValue {
  param(
    [string]$Name,
    [string]$Scope = $VoiceEnvironmentScope
  )

  foreach ($Target in (Get-VoiceEnvironmentTargets -Scope $Scope)) {
    try {
      $Value = [string][System.Environment]::GetEnvironmentVariable($Name, $Target)
      if (-not [string]::IsNullOrWhiteSpace($Value)) {
        return $Value
      }
    } catch {
    }
  }
  return ''
}

function Get-ScopedEnvironmentSource {
  param(
    [string]$Name,
    [string]$Scope = $VoiceEnvironmentScope
  )

  foreach ($ScopeName in (Get-VoiceEnvironmentScopeNames -Scope $Scope)) {
    try {
      $Target = [System.EnvironmentVariableTarget]::$ScopeName
      $Value = [string][System.Environment]::GetEnvironmentVariable($Name, $Target)
      if (-not [string]::IsNullOrWhiteSpace($Value)) {
        return ("{0}:{1}" -f $ScopeName, $Name)
      }
    } catch {
    }
  }
  return ''
}

function Get-ElevenLabsApiKey {
  $Scoped = Get-ScopedEnvironmentValue -Name 'FRANCIS_ELEVENLABS_API_KEY'
  if (-not [string]::IsNullOrWhiteSpace($Scoped)) {
    return $Scoped
  }
  return Get-ScopedEnvironmentValue -Name 'ELEVENLABS_API_KEY'
}

function Get-ElevenLabsVoiceId {
  param([string]$RequestedVoiceId)

  if (-not [string]::IsNullOrWhiteSpace($RequestedVoiceId)) {
    return $RequestedVoiceId.Trim()
  }
  $Scoped = Get-ScopedEnvironmentValue -Name 'FRANCIS_ELEVENLABS_VOICE_ID'
  if (-not [string]::IsNullOrWhiteSpace($Scoped)) {
    return $Scoped.Trim()
  }
  return (Get-ScopedEnvironmentValue -Name 'ELEVENLABS_VOICE_ID').Trim()
}

function Get-ElevenLabsApiKeySource {
  $Scoped = Get-ScopedEnvironmentSource -Name 'FRANCIS_ELEVENLABS_API_KEY'
  if (-not [string]::IsNullOrWhiteSpace($Scoped)) {
    return $Scoped
  }
  return Get-ScopedEnvironmentSource -Name 'ELEVENLABS_API_KEY'
}

function Get-ElevenLabsVoiceIdSource {
  param([string]$RequestedVoiceId)

  if (-not [string]::IsNullOrWhiteSpace($RequestedVoiceId)) {
    return 'script_parameter:ElevenLabsVoiceId'
  }
  $Scoped = Get-ScopedEnvironmentSource -Name 'FRANCIS_ELEVENLABS_VOICE_ID'
  if (-not [string]::IsNullOrWhiteSpace($Scoped)) {
    return $Scoped
  }
  return Get-ScopedEnvironmentSource -Name 'ELEVENLABS_VOICE_ID'
}

function Get-ElevenLabsVoiceLabel {
  param(
    [string]$RequestedVoiceId = $ElevenLabsVoiceId,
    [string]$FallbackLabel = ''
  )

  if (-not [string]::IsNullOrWhiteSpace($ElevenLabsVoiceName)) {
    return $ElevenLabsVoiceName.Trim()
  }
  $ScopedName = Get-ScopedEnvironmentValue -Name 'FRANCIS_ELEVENLABS_VOICE_NAME'
  if (-not [string]::IsNullOrWhiteSpace($ScopedName)) {
    return $ScopedName.Trim()
  }
  $ScopedLabel = Get-ScopedEnvironmentValue -Name 'FRANCIS_ELEVENLABS_VOICE_LABEL'
  if (-not [string]::IsNullOrWhiteSpace($ScopedLabel)) {
    return $ScopedLabel.Trim()
  }
  $GenericName = Get-ScopedEnvironmentValue -Name 'ELEVENLABS_VOICE_NAME'
  if (-not [string]::IsNullOrWhiteSpace($GenericName)) {
    return $GenericName.Trim()
  }

  $ResolvedVoiceId = Get-ElevenLabsVoiceId -RequestedVoiceId $RequestedVoiceId
  if ($ResolvedVoiceId -eq '56bWURjYFHyYyVf490Dp') {
    return 'Emma'
  }
  if (-not [string]::IsNullOrWhiteSpace($FallbackLabel) -and $FallbackLabel -ne 'elevenlabs') {
    return $FallbackLabel.Trim()
  }
  return 'ElevenLabs voice'
}

function Get-ElevenLabsVoiceLabelSource {
  param([string]$RequestedVoiceId = $ElevenLabsVoiceId)

  if (-not [string]::IsNullOrWhiteSpace($ElevenLabsVoiceName)) {
    return 'script_parameter:ElevenLabsVoiceName'
  }
  $ScopedName = Get-ScopedEnvironmentSource -Name 'FRANCIS_ELEVENLABS_VOICE_NAME'
  if (-not [string]::IsNullOrWhiteSpace($ScopedName)) {
    return $ScopedName
  }
  $ScopedLabel = Get-ScopedEnvironmentSource -Name 'FRANCIS_ELEVENLABS_VOICE_LABEL'
  if (-not [string]::IsNullOrWhiteSpace($ScopedLabel)) {
    return $ScopedLabel
  }
  $GenericName = Get-ScopedEnvironmentSource -Name 'ELEVENLABS_VOICE_NAME'
  if (-not [string]::IsNullOrWhiteSpace($GenericName)) {
    return $GenericName
  }
  $ResolvedVoiceId = Get-ElevenLabsVoiceId -RequestedVoiceId $RequestedVoiceId
  if ($ResolvedVoiceId -eq '56bWURjYFHyYyVf490Dp') {
    return 'known_voice_id:Emma'
  }
  return 'provider_default_label'
}

function Get-OverlaySelectedVoiceName {
  param(
    [string]$Provider = $VoiceProvider,
    [string]$Voice = $VoiceName,
    [string]$RequestedVoiceId = $ElevenLabsVoiceId
  )

  if ($Provider -eq 'ElevenLabs') {
    return Get-ElevenLabsVoiceLabel -RequestedVoiceId $RequestedVoiceId -FallbackLabel $Voice
  }
  return $Voice
}

function New-OverlayVoiceProviderReadiness {
  param(
    [string]$Provider = $VoiceProvider,
    [string]$RequestedVoiceId = $ElevenLabsVoiceId,
    [string]$ModelId = $ElevenLabsModelId,
    [string]$OutputFormat = $ElevenLabsOutputFormat,
    [double]$Speed = $ElevenLabsSpeed,
    [double]$Stability = $ElevenLabsStability,
    [double]$SimilarityBoost = $ElevenLabsSimilarityBoost,
    [double]$Style = $ElevenLabsStyle
  )

  $ApiKeySource = Get-ElevenLabsApiKeySource
  $VoiceIdSource = Get-ElevenLabsVoiceIdSource -RequestedVoiceId $RequestedVoiceId
  $VoiceLabel = Get-ElevenLabsVoiceLabel -RequestedVoiceId $RequestedVoiceId
  $VoiceLabelSource = Get-ElevenLabsVoiceLabelSource -RequestedVoiceId $RequestedVoiceId
  $ApiKeyPresent = -not [string]::IsNullOrWhiteSpace($ApiKeySource)
  $VoiceIdPresent = -not [string]::IsNullOrWhiteSpace($VoiceIdSource)
  $Missing = @()
  if (-not $ApiKeyPresent) {
    $Missing += 'api_key'
  }
  if (-not $VoiceIdPresent) {
    $Missing += 'voice_id'
  }

  return [ordered]@{
    kind = 'lens.overlay.voice.provider_readiness'
    selected_provider = $Provider
    environment_scope = $VoiceEnvironmentScope
    windows_sapi = [ordered]@{
      configured = ([System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT)
      credential_required = $false
      sends_text_to_remote_provider = $false
    }
    elevenlabs = [ordered]@{
      configured = ($ApiKeyPresent -and $VoiceIdPresent)
      api_key_present = $ApiKeyPresent
      api_key_source = $ApiKeySource
      voice_id_present = $VoiceIdPresent
      voice_id_source = $VoiceIdSource
      voice_label = $VoiceLabel
      voice_label_source = $VoiceLabelSource
      voice_label_redacted = $false
      missing_configuration = [string[]]$Missing
      model_id = $ModelId
      output_format = $OutputFormat
      speed = $Speed
      stability = $Stability
      similarity_boost = $SimilarityBoost
      style = $Style
      credential_values_redacted = $true
      sends_text_to_remote_provider = $true
      stores_audio = $false
      audio_retention = 'transient_deleted_after_playback'
    }
    active_provider_configured = if ($Provider -eq 'ElevenLabs') { ($ApiKeyPresent -and $VoiceIdPresent) } else { ([System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT) }
    francis_identity = 'Francis'
    orb_role = 'embodiment'
    voice_lens_orb_are_francis_surfaces = $true
    voice_lens_orb_are_separate_identities = $false
    remote_provider_requires_explicit_selection = $true
    stores_secret = $false
    logs_text_payload = $false
  }
}

function Get-OverlayAudioCacheRoot {
  param([string]$Root)

  return Join-Path $Root 'cache\audio\lens-overlay'
}

function Test-OverlayPathWithinRoot {
  param(
    [string]$Path,
    [string]$RootPath
  )

  if ([string]::IsNullOrWhiteSpace($Path) -or [string]::IsNullOrWhiteSpace($RootPath)) {
    return $false
  }
  try {
    $FullPath = [System.IO.Path]::GetFullPath($Path)
    $FullRoot = [System.IO.Path]::GetFullPath($RootPath)
    if (-not $FullRoot.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
      $FullRoot = '{0}{1}' -f $FullRoot, [System.IO.Path]::DirectorySeparatorChar
    }
    return $FullPath.StartsWith($FullRoot, [System.StringComparison]::OrdinalIgnoreCase)
  } catch {
    return $false
  }
}

function New-OverlayVoiceTextFile {
  param(
    [string]$Root,
    [string]$Text
  )

  $AudioRoot = Get-OverlayAudioCacheRoot -Root $Root
  New-Item -ItemType Directory -Force -Path $AudioRoot | Out-Null
  $TextPath = Join-Path $AudioRoot ("speech-script-{0}.txt" -f ([Guid]::NewGuid().ToString('N')))
  $Encoding = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($TextPath, $Text, $Encoding)
  return $TextPath
}

function Read-OverlayVoiceTextInput {
  param(
    [string]$Root,
    [string]$Text,
    [string]$TextPath
  )

  if (-not [string]::IsNullOrWhiteSpace($Text)) {
    return $Text
  }
  if ([string]::IsNullOrWhiteSpace($TextPath)) {
    return ''
  }
  $AudioRoot = Get-OverlayAudioCacheRoot -Root $Root
  if (-not (Test-OverlayPathWithinRoot -Path $TextPath -RootPath $AudioRoot)) {
    return ''
  }
  if (-not (Test-Path -LiteralPath $TextPath -PathType Leaf)) {
    return ''
  }
  return Get-Content -LiteralPath $TextPath -Raw -ErrorAction Stop
}

function Remove-OverlayVoiceTextFile {
  param(
    [string]$Root,
    [string]$TextPath
  )

  if ([string]::IsNullOrWhiteSpace($TextPath)) {
    return
  }
  $AudioRoot = Get-OverlayAudioCacheRoot -Root $Root
  if (Test-OverlayPathWithinRoot -Path $TextPath -RootPath $AudioRoot) {
    Remove-Item -LiteralPath $TextPath -Force -ErrorAction SilentlyContinue
  }
}

function Get-OverlayVoiceSpeechPidPath {
  param([string]$Root)

  return Join-Path (Join-Path $Root 'runtime\lens-overlay') 'lens-overlay-speech.pid'
}

function Get-OverlayVoicePlaybackStatusPath {
  param([string]$Root)

  return Join-Path (Join-Path $Root 'runtime\lens-overlay') 'voice-playback-status.json'
}

function Test-OverlayVoiceSpeechProcess {
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
  if ($null -eq (Get-Command -Name Get-CimInstance -ErrorAction SilentlyContinue)) {
    return $false
  }
  $Process = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
  if ($null -eq $Process) {
    return $false
  }
  $CommandLine = [string]$Process.CommandLine
  return (
    $CommandLine -like '*lens-overlay-window.ps1*' -and
    $CommandLine -like '*-Mode Speak*' -and
    $CommandLine -like '*-PlaybackStateOnly*'
  )
}

function Test-OverlayVoiceRecentSpeechPlayback {
  param(
    [string]$Root,
    [int]$CooldownSeconds = 4
  )

  $Playback = Read-JsonFile -Path (Get-OverlayVoicePlaybackStatusPath -Root $Root)
  if ($null -eq $Playback) {
    return $false
  }
  if ((Get-StringProperty -Payload $Playback -Name 'kind' -Default '') -ne 'lens.overlay.voice.runtime') {
    return $false
  }
  if (-not (Get-BoolProperty -Payload $Playback -Name 'playback_state_only' -Default $false)) {
    return $false
  }
  if ((Get-StringProperty -Payload $Playback -Name 'status' -Default '') -ne 'spoken') {
    return $false
  }
  $PlaybackProcessId = Get-IntegerProperty -Payload $Playback -Name 'speech_process_pid' -Default 0
  if (Test-OverlayVoiceSpeechProcess -ProcessId $PlaybackProcessId) {
    return $false
  }
  $UpdatedAt = Get-StringProperty -Payload $Playback -Name 'updated_at' -Default ''
  if ([string]::IsNullOrWhiteSpace($UpdatedAt)) {
    return $false
  }
  try {
    $CompletedAt = [DateTimeOffset]::Parse($UpdatedAt)
    $ElapsedSeconds = ([DateTimeOffset]::UtcNow - $CompletedAt).TotalSeconds
    return ($ElapsedSeconds -ge -1.0 -and $ElapsedSeconds -le [double]$CooldownSeconds)
  } catch {
    return $false
  }
}

function Get-OverlayOwnedSpeechGuardState {
  param(
    [string]$Root,
    [int]$CooldownSeconds = 4
  )

  $SpeechPidPath = Get-OverlayVoiceSpeechPidPath -Root $Root
  $SpeechProcessId = 0
  if (Test-Path -LiteralPath $SpeechPidPath -PathType Leaf) {
    try {
      $SpeechProcessId = [int]((Get-Content -LiteralPath $SpeechPidPath -Raw -ErrorAction Stop).Trim())
    } catch {
      $SpeechProcessId = 0
    }
  }

  $OwnedSpeechActive = Test-OverlayVoiceSpeechProcess -ProcessId $SpeechProcessId
  $OwnedSpeechRecentlyCompleted = Test-OverlayVoiceRecentSpeechPlayback -Root $Root -CooldownSeconds $CooldownSeconds
  return [ordered]@{
    owned_speech_active = [bool]$OwnedSpeechActive
    owned_speech_recently_completed = [bool]$OwnedSpeechRecentlyCompleted
    owned_speech_guard_active = ([bool]$OwnedSpeechActive -or [bool]$OwnedSpeechRecentlyCompleted)
    owned_speech_process_id = [int]$SpeechProcessId
    self_trigger_guard_window_seconds = [int]$CooldownSeconds
    microphone_gate_while_speaking = 'francis_stop_only'
    conversation_forwarding_while_speaking = $false
  }
}

function Stop-OverlayVoiceSpeechProcess {
  param(
    [string]$Root,
    [string]$Reason = 'owned_speech_process_cancelled'
  )

  $PidPath = Get-OverlayVoiceSpeechPidPath -Root $Root
  $ProcessId = 0
  if (Test-Path -LiteralPath $PidPath -PathType Leaf) {
    try {
      $ProcessId = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
    } catch {
      $ProcessId = 0
    }
  }

  $Stopped = $false
  if (Test-OverlayVoiceSpeechProcess -ProcessId $ProcessId) {
    try {
      Stop-Process -Id $ProcessId -Force -ErrorAction Stop
      $Stopped = $true
    } catch {
      $Stopped = $false
    }
  }
  if ($Stopped -or $ProcessId -le 0 -or -not (Test-OverlayVoiceSpeechProcess -ProcessId $ProcessId)) {
    Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
  }

  return [ordered]@{
    stopped = $Stopped
    process_id = $ProcessId
    reason = $Reason
    owned_process_checked = $true
    arbitrary_audio_control = $false
  }
}

function Invoke-OverlayAudioFilePlayback {
  param(
    [string]$Path,
    [int]$Volume,
    [int]$TimeoutSeconds = 30
  )

  Add-Type -AssemblyName PresentationCore
  Add-Type -AssemblyName WindowsBase
  $Player = New-Object System.Windows.Media.MediaPlayer
  $script:LensOverlayPlaybackOpened = $false
  $script:LensOverlayPlaybackEnded = $false
  $script:LensOverlayPlaybackFailed = ''
  $Player.add_MediaOpened({
      $script:LensOverlayPlaybackOpened = $true
    })
  $Player.add_MediaEnded({
      $script:LensOverlayPlaybackEnded = $true
    })
  $Player.add_MediaFailed({
      param($Sender, $EventArgs)

      if ($null -ne $EventArgs -and $null -ne $EventArgs.ErrorException) {
        $script:LensOverlayPlaybackFailed = [string]$EventArgs.ErrorException.Message
      } else {
        $script:LensOverlayPlaybackFailed = 'media_playback_failed'
      }
      $script:LensOverlayPlaybackEnded = $true
    })

  $Player.Volume = [Math]::Min(1.0, [Math]::Max(0.0, $Volume / 100.0))
  $Player.Open((New-Object System.Uri -ArgumentList ([System.IO.Path]::GetFullPath($Path))))
  $Player.Play()
  $Deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
  while (-not $script:LensOverlayPlaybackEnded -and [DateTimeOffset]::UtcNow -lt $Deadline) {
    try {
      [System.Windows.Threading.Dispatcher]::CurrentDispatcher.Invoke(
        [Action]{},
        [System.Windows.Threading.DispatcherPriority]::Background
      )
    } catch {
    }
    Start-Sleep -Milliseconds 50
  }
  $Player.Stop()
  $Player.Close()
  if (-not [string]::IsNullOrWhiteSpace($script:LensOverlayPlaybackFailed)) {
    throw $script:LensOverlayPlaybackFailed
  }
  if (-not $script:LensOverlayPlaybackEnded) {
    throw 'media_playback_timeout'
  }
}

function Invoke-OverlayElevenLabsVoiceSpeech {
  param(
    [string]$Root,
    [string]$Text,
    [int]$Volume,
    [bool]$WakeListening,
    [string]$WakePhraseText,
    [string]$RequestedVoiceId,
    [string]$ModelId,
    [string]$OutputFormat,
    [double]$Stability,
    [double]$SimilarityBoost,
    [double]$Style,
    [double]$Speed,
    [bool]$UseSpeakerBoost,
    [string]$SuccessStatus,
    [string]$SuccessMessage,
    [string]$StatusPath = ''
  )

  $ApiKey = Get-ElevenLabsApiKey
  $VoiceId = Get-ElevenLabsVoiceId -RequestedVoiceId $RequestedVoiceId
  $Missing = @()
  if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    $Missing += 'api_key'
  }
  if ([string]::IsNullOrWhiteSpace($VoiceId)) {
    $Missing += 'voice_id'
  }
  $VoiceLabel = Get-ElevenLabsVoiceLabel -RequestedVoiceId $RequestedVoiceId
  if ($Missing.Count -gt 0) {
    $Payload = New-OverlayVoiceProjection -SelectedVoiceName $VoiceLabel -Provider 'ElevenLabs' -WakeListening $WakeListening -WakePhraseText $WakePhraseText
    $Payload.status = 'refused'
    $Payload.ok = $false
    $Payload.error = 'elevenlabs_configuration_required'
    $Payload.missing_configuration = [string[]]$Missing
    $Payload.text_length = $Text.Length
    $Payload.text_redacted = $true
    $Payload.message = 'ElevenLabs voice output requires FRANCIS_ELEVENLABS_API_KEY and FRANCIS_ELEVENLABS_VOICE_ID, or explicit script parameters.'
    Write-OverlayVoiceState -Root $Root -Payload $Payload -StatusPath $StatusPath
    return $Payload
  }

  $AudioRoot = Get-OverlayAudioCacheRoot -Root $Root
  New-Item -ItemType Directory -Force -Path $AudioRoot | Out-Null
  $AudioPath = Join-Path $AudioRoot ("elevenlabs-{0}.mp3" -f ([Guid]::NewGuid().ToString('N')))
  $StartedAt = [DateTimeOffset]::UtcNow
  $DeletedAudio = $false
  try {
    $Uri = 'https://api.elevenlabs.io/v1/text-to-speech/{0}?output_format={1}' -f ([System.Uri]::EscapeDataString($VoiceId)), ([System.Uri]::EscapeDataString($OutputFormat))
    $Body = [ordered]@{
      text = $Text
      model_id = $ModelId
      voice_settings = [ordered]@{
        stability = $Stability
        similarity_boost = $SimilarityBoost
        style = $Style
        speed = $Speed
        use_speaker_boost = $UseSpeakerBoost
      }
    }
    $Headers = @{
      'xi-api-key' = $ApiKey
      'Accept' = 'audio/mpeg'
      'Content-Type' = 'application/json'
    }
    Invoke-WebRequest -Uri $Uri -Method Post -Headers $Headers -Body ($Body | ConvertTo-Json -Depth 8) -OutFile $AudioPath -TimeoutSec 45 | Out-Null
    Invoke-OverlayAudioFilePlayback -Path $AudioPath -Volume $Volume -TimeoutSeconds 45
    Remove-Item -LiteralPath $AudioPath -Force -ErrorAction SilentlyContinue
    $DeletedAudio = -not (Test-Path -LiteralPath $AudioPath -PathType Leaf)
    $ElapsedMs = [int]([DateTimeOffset]::UtcNow - $StartedAt).TotalMilliseconds

    $Payload = New-OverlayVoiceProjection -SelectedVoiceName $VoiceLabel -Provider 'ElevenLabs' -WakeListening $WakeListening -WakePhraseText $WakePhraseText
    $Payload.status = $SuccessStatus
    $Payload.ok = $true
    $Payload.voice_name = $VoiceLabel
    $Payload.voice_id_present = $true
    $Payload.model_id = $ModelId
    $Payload.output_format = $OutputFormat
    $Payload.speed = $Speed
    $Payload.text_length = $Text.Length
    $Payload.text_redacted = $true
    $Payload.rate = 'provider_default'
    $Payload.volume = $Volume
    $Payload.latency_ms = $ElapsedMs
    $Payload.remote_text_sent = $true
    $Payload.audio_written_to_disk = $false
    $Payload.temp_audio_deleted = $DeletedAudio
    $Payload.message = $SuccessMessage
    Write-OverlayVoiceState -Root $Root -Payload $Payload -StatusPath $StatusPath
    return $Payload
  } catch {
    $StatusCode = ''
    try {
      if ($null -ne $_.Exception.Response) {
        $StatusCode = [string]([int]$_.Exception.Response.StatusCode)
      }
    } catch {
      $StatusCode = ''
    }
    Remove-Item -LiteralPath $AudioPath -Force -ErrorAction SilentlyContinue
    $DeletedAudio = -not (Test-Path -LiteralPath $AudioPath -PathType Leaf)
    $Payload = New-OverlayVoiceProjection -SelectedVoiceName $VoiceLabel -Provider 'ElevenLabs' -WakeListening $WakeListening -WakePhraseText $WakePhraseText
    $Payload.status = 'failed'
    $Payload.ok = $false
    $Payload.error = if ($StatusCode) { "elevenlabs_http_$StatusCode" } else { [string]$_.Exception.Message }
    $Payload.text_length = $Text.Length
    $Payload.text_redacted = $true
    $Payload.remote_text_sent = $true
    $Payload.temp_audio_deleted = $DeletedAudio
    $Payload.message = 'ElevenLabs voice output failed before speech completed.'
    Write-OverlayVoiceState -Root $Root -Payload $Payload -StatusPath $StatusPath
    return $Payload
  }
}

function Get-OverlayVoiceStatusPath {
  param([string]$Root)

  return Join-Path (Join-Path $Root 'runtime\lens-overlay') 'voice-status.json'
}

function Move-OverlayRuntimeStateFile {
  param(
    [string]$TempPath,
    [string]$DestinationPath
  )

  if (Test-Path -LiteralPath $DestinationPath -PathType Leaf) {
    $BackupPath = '{0}.bak.{1}' -f $DestinationPath, ([Guid]::NewGuid().ToString('N'))
    [System.IO.File]::Replace($TempPath, $DestinationPath, $BackupPath)
    Remove-Item -LiteralPath $BackupPath -Force -ErrorAction SilentlyContinue
    return
  }
  Move-Item -LiteralPath $TempPath -Destination $DestinationPath -Force
}

function Join-OverlayProcessArguments {
  param([string[]]$Arguments)

  $Quoted = foreach ($Argument in $Arguments) {
    $Value = [string]$Argument
    if ($Value.Length -eq 0 -or $Value -match '\s') {
      '"{0}"' -f ($Value.Replace('"', '\"'))
    } else {
      $Value
    }
  }
  return ($Quoted -join ' ')
}

function Write-OverlayVoiceState {
  param(
    [string]$Root,
    [object]$Payload,
    [string]$StatusPath = ''
  )

  $RuntimeRoot = Join-Path $Root 'runtime\lens-overlay'
  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  if ([string]::IsNullOrWhiteSpace($StatusPath)) {
    $StatusPath = Get-OverlayVoiceStatusPath -Root $Root
  }
  $TempPath = Join-Path $RuntimeRoot ("voice-status.{0}.tmp" -f ([Guid]::NewGuid().ToString('N')))
  try {
    $Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $TempPath -Encoding UTF8
    Move-OverlayRuntimeStateFile -TempPath $TempPath -DestinationPath $StatusPath
  } finally {
    Remove-Item -LiteralPath $TempPath -Force -ErrorAction SilentlyContinue
  }
}

function Get-OverlayVoiceTurnStatusPath {
  param([string]$Root)

  return Join-Path (Join-Path $Root 'runtime\lens-overlay') 'voice-turn-status.json'
}

function Get-OverlayVoiceTurnReceiptRoot {
  param([string]$Root)

  return Join-Path (Join-Path $Root 'runtime\lens-overlay') 'voice-turns'
}

function Get-OverlayVoiceTurnReceiptPath {
  param(
    [string]$Root,
    [string]$TurnId
  )

  $CleanTurnId = ([string]$TurnId) -replace '[^A-Za-z0-9_.-]', '_'
  if ([string]::IsNullOrWhiteSpace($CleanTurnId)) {
    $CleanTurnId = 'unknown_turn'
  }
  return Join-Path (Get-OverlayVoiceTurnReceiptRoot -Root $Root) ('{0}.json' -f $CleanTurnId)
}

function New-OverlayVoiceTurnId {
  return 'voice_turn_{0}' -f ([Guid]::NewGuid().ToString('N'))
}

function Write-OverlayVoiceTurnFile {
  param(
    [string]$Path,
    [object]$Payload
  )

  $Root = Split-Path -Parent $Path
  New-Item -ItemType Directory -Force -Path $Root | Out-Null
  $TempPath = Join-Path $Root ("voice-turn.{0}.tmp" -f ([Guid]::NewGuid().ToString('N')))
  try {
    $Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $TempPath -Encoding UTF8
    Move-OverlayRuntimeStateFile -TempPath $TempPath -DestinationPath $Path
  } finally {
    Remove-Item -LiteralPath $TempPath -Force -ErrorAction SilentlyContinue
  }
}

function Read-OverlayVoiceTurnState {
  param([string]$Root)

  return Read-JsonFile -Path (Get-OverlayVoiceTurnStatusPath -Root $Root)
}

function Get-OverlayVoiceTurnReadback {
  param(
    [string]$Root,
    [object]$State = $null
  )

  $VoiceTurn = $State
  if ($null -eq $VoiceTurn) {
    $VoiceTurn = Read-OverlayVoiceTurnState -Root $Root
  }
  if ($null -eq $VoiceTurn) {
    return $null
  }

  $TurnStatus = Get-StringProperty -Payload $VoiceTurn -Name 'status' -Default ''
  if ($TurnStatus -ne 'speaking') {
    return $VoiceTurn
  }

  $SpeechProcessId = Get-IntegerProperty -Payload $VoiceTurn -Name 'speech_process_pid' -Default 0
  $SpeechProcessAlive = Test-OverlayVoiceSpeechProcess -ProcessId $SpeechProcessId
  $PlaybackStatusPath = Get-OverlayVoicePlaybackStatusPath -Root $Root
  $Playback = Read-JsonFile -Path $PlaybackStatusPath
  $PlaybackStatus = Get-StringProperty -Payload $Playback -Name 'status' -Default ''
  $PlaybackProcessId = Get-IntegerProperty -Payload $Playback -Name 'speech_process_pid' -Default 0
  $PlaybackMatchesTurn = (
    (Get-StringProperty -Payload $Playback -Name 'kind' -Default '') -eq 'lens.overlay.voice.runtime' -and
    (Get-BoolProperty -Payload $Playback -Name 'playback_state_only' -Default $false) -and
    $SpeechProcessId -gt 0 -and
    $PlaybackProcessId -eq $SpeechProcessId
  )
  $PlaybackCompleted = $PlaybackMatchesTurn -and $PlaybackStatus -in @('spoken', 'failed', 'refused', 'unsupported')
  if ($SpeechProcessAlive -or -not $PlaybackCompleted) {
    return $VoiceTurn
  }

  $Readback = [ordered]@{}
  if ($VoiceTurn -is [System.Collections.IDictionary]) {
    foreach ($Key in $VoiceTurn.Keys) {
      $Readback[$Key] = $VoiceTurn[$Key]
    }
  } else {
    foreach ($Property in $VoiceTurn.PSObject.Properties) {
      $Readback[$Property.Name] = $Property.Value
    }
  }

  $Readback.status = if ($PlaybackStatus -eq 'spoken') { 'spoken' } else { 'speech_playback_failed' }
  $Readback.voice_turn_completed = $true
  $Readback.handback_ready = $true
  $Readback.handback_state = if ($PlaybackStatus -eq 'spoken') { 'speech_playback_spoken' } else { 'speech_playback_not_spoken' }
  $Readback.playback_status = $PlaybackStatus
  $Readback.playback_receipt_observed = $true
  $Readback.speech_process_alive = $false
  $Readback.speech_process_checked = $true
  $Readback.completed_at = Get-UtcTimestampStringProperty -Payload $Playback -Name 'updated_at' -Default ''
  return $Readback
}

function Write-OverlayVoiceTurnReceipt {
  param(
    [string]$Root,
    [string]$TurnId,
    [object]$Payload
  )

  Write-OverlayVoiceTurnFile -Path (Get-OverlayVoiceTurnReceiptPath -Root $Root -TurnId $TurnId) -Payload $Payload
}

function Get-OverlayOrbPositionCommandRequestPath {
  param([string]$Root)

  return Join-Path (Join-Path $Root 'runtime\lens-overlay') 'orb-position-command-request.json'
}

function Get-OverlayOrbPositionCommandReceiptRoot {
  param([string]$Root)

  return Join-Path (Join-Path $Root 'runtime\lens-overlay') 'orb-position-commands'
}

function Get-OverlayOrbPositionCommandReceiptPath {
  param(
    [string]$Root,
    [string]$RequestId
  )

  $CleanRequestId = ([string]$RequestId) -replace '[^A-Za-z0-9_.-]', '_'
  if ([string]::IsNullOrWhiteSpace($CleanRequestId)) {
    $CleanRequestId = 'unknown_request'
  }
  return Join-Path (Get-OverlayOrbPositionCommandReceiptRoot -Root $Root) ('{0}.json' -f $CleanRequestId)
}

function Write-OverlayOrbPositionCommandReceipt {
  param(
    [string]$Root,
    [string]$RequestId,
    [object]$Request,
    [object]$Result
  )

  $CommandName = Get-StringProperty -Payload $Request -Name 'command' -Default ''
  $TargetSide = Get-StringProperty -Payload $Request -Name 'target_side' -Default ''
  $TargetAnchor = Get-StringProperty -Payload $Request -Name 'target_anchor' -Default ''
  $Receipt = [ordered]@{
    kind = 'lens.overlay.orb_position_command.receipt'
    status = Get-StringProperty -Payload $Result -Name 'status' -Default 'orb_position_command_result_unknown'
    ok = Get-BoolProperty -Payload $Result -Name 'ok' -Default $false
    request_id = $RequestId
    command = $CommandName
    target_side = $TargetSide
    target_anchor = $TargetAnchor
    applied = Get-BoolProperty -Payload $Result -Name 'runtime_overlay_position_changed' -Default $false
    overlay_left = Get-StringProperty -Payload $Result -Name 'overlay_left' -Default ''
    overlay_top = Get-StringProperty -Payload $Result -Name 'overlay_top' -Default ''
    source = Get-StringProperty -Payload $Request -Name 'source' -Default ''
    actor = Get-StringProperty -Payload $Request -Name 'actor' -Default ''
    client_origin = Get-StringProperty -Payload $Request -Name 'client_origin' -Default ''
    transcript_hash = Get-StringProperty -Payload $Request -Name 'transcript_hash' -Default ''
    transcript_redacted = $true
    stores_transcript = $false
    request_path = 'data/runtime/lens-overlay/orb-position-command-request.json'
    receipt_path = 'data/runtime/lens-overlay/orb-position-commands'
    overlay_runtime_owns_execution = $true
    bounded_overlay_position_mutation = $true
    mutation_authority_scope = 'runtime_overlay_position_only'
    chat_route_writes_conversation_ledger = $false
    conversation_forwarding_suppressed = $true
    grants_execution_authority = $false
    grants_mutation_authority = $false
    updated_at = [DateTimeOffset]::UtcNow.ToString('o')
  }
  Write-OverlayVoiceTurnFile -Path (Get-OverlayOrbPositionCommandReceiptPath -Root $Root -RequestId $RequestId) -Payload $Receipt
}

function Remove-OverlayOrbPositionCommandRequest {
  param(
    [string]$Root,
    [string]$Path
  )

  $RequestPath = if ([string]::IsNullOrWhiteSpace($Path)) {
    Get-OverlayOrbPositionCommandRequestPath -Root $Root
  } else {
    $Path
  }
  Remove-Item -LiteralPath $RequestPath -Force -ErrorAction SilentlyContinue
}

function Invoke-OverlayQueuedOrbPositionCommand {
  param([string]$Root)

  if ([string]::IsNullOrWhiteSpace($Root)) {
    return $null
  }

  $RequestPath = Get-OverlayOrbPositionCommandRequestPath -Root $Root
  $Request = Read-JsonFile -Path $RequestPath
  if ($null -eq $Request) {
    return $null
  }

  $RequestId = Get-StringProperty -Payload $Request -Name 'request_id' -Default ''
  if ([string]::IsNullOrWhiteSpace($RequestId)) {
    $RequestId = 'unknown_request'
  }
  $CommandName = Get-StringProperty -Payload $Request -Name 'command' -Default ''
  $TargetSide = Get-StringProperty -Payload $Request -Name 'target_side' -Default ''
  $TargetAnchor = Get-StringProperty -Payload $Request -Name 'target_anchor' -Default ''
  $Command = [ordered]@{
    recognized = $true
    intent = 'move_orb'
    command = $CommandName
    target_side = $TargetSide
    target_anchor = $TargetAnchor
  }
  $Result = Invoke-OverlayVoiceOrbCommand `
    -Root $Root `
    -Command $Command `
    -RecognizedText ('orb position command request {0}' -f $RequestId) `
    -Provider $script:LensOverlayRequestedVoiceProvider `
    -Voice $script:LensOverlayRequestedVoiceName `
    -RemoteVoiceId $script:LensOverlayRequestedElevenLabsVoiceId `
    -WakePhraseText $script:LensOverlayRequestedWakePhrase `
    -RecognitionConfidence 1.0 `
    -RecognitionThreshold $script:LensOverlayRequestedWakeConfidenceThreshold `
    -WakeAliasCount 0 `
    -WakeCount 0 `
    -WakePhraseDetected $true `
    -ContinuousVoiceChat $false `
    -CommandSource 'chatgpt_voice_bridge_file_request' `
    -CommandRequestId $RequestId `
    -TranscriptHashOverride (Get-StringProperty -Payload $Request -Name 'transcript_hash' -Default '') `
    -TranscriptLengthOverride (Get-IntegerProperty -Payload $Request -Name 'transcript_length' -Default 0)
  Write-OverlayOrbPositionCommandReceipt -Root $Root -RequestId $RequestId -Request $Request -Result $Result
  Remove-OverlayOrbPositionCommandRequest -Root $Root -Path $RequestPath
  return $Result
}

function Test-OverlayVoiceTurnCurrent {
  param(
    [string]$Root,
    [string]$TurnId
  )

  if ([string]::IsNullOrWhiteSpace($TurnId)) {
    return $false
  }
  $State = Read-OverlayVoiceTurnState -Root $Root
  if ($null -eq $State) {
    return $false
  }
  if ((Get-StringProperty -Payload $State -Name 'active_turn_id' -Default '') -ne $TurnId) {
    return $false
  }
  $Status = Get-StringProperty -Payload $State -Name 'status' -Default ''
  if ($Status -in @('active', 'chat_pending')) {
    return $true
  }
  if ($Status -ne 'speaking') {
    return $false
  }
  $Readback = Get-OverlayVoiceTurnReadback -Root $Root -State $State
  return (Get-StringProperty -Payload $Readback -Name 'status' -Default '') -eq 'speaking'
}

function Start-OverlayVoiceTurn {
  param(
    [string]$Root,
    [string]$UtteranceText,
    [double]$RecognitionConfidence,
    [double]$RecognitionThreshold,
    [int]$WakeAliasCount,
    [int]$WakeCount,
    [bool]$SyntheticTranscript = $false,
    [bool]$WakePhraseDetected = $true
  )

  $TurnId = New-OverlayVoiceTurnId
  $Previous = Read-OverlayVoiceTurnState -Root $Root
  $PreviousTurnId = if ($null -ne $Previous) { Get-StringProperty -Payload $Previous -Name 'active_turn_id' -Default '' } else { '' }
  $PreviousStatus = if ($null -ne $Previous) { Get-StringProperty -Payload $Previous -Name 'status' -Default '' } else { '' }
  $PriorSpeech = Stop-OverlayVoiceSpeechProcess -Root $Root -Reason 'voice_turn_superseded_before_chat_reply'
  if (-not [string]::IsNullOrWhiteSpace($PreviousTurnId) -and $PreviousStatus -in @('active', 'chat_pending', 'speaking')) {
    $PreviousPayload = [ordered]@{}
    foreach ($Property in $Previous.PSObject.Properties) {
      $PreviousPayload[$Property.Name] = $Property.Value
    }
    $PreviousPayload.status = 'superseded_by_new_voice_turn'
    $PreviousPayload.superseded_by_turn_id = $TurnId
    $PreviousPayload.superseded_at = [DateTimeOffset]::UtcNow.ToString('o')
    $PreviousPayload.speech_cancelled_at_supersession = [bool]$PriorSpeech.stopped
    $PreviousPayload.speech_cancelled_process_id = [int]$PriorSpeech.process_id
    $PreviousPayload.latest_voice_turn_wins = $true
    $PreviousPayload.stale_reply_suppression_supported = $true
    $PreviousPayload.thought_relevance_status = 'superseded_pending_result'
    $PreviousPayload.thought_retention_policy = 'drop_superseded_reply_unless_operator_reasks'
    $PreviousPayload.model_call_abort_requested = $false
    $PreviousPayload.model_call_abort_observed = $false
    $PreviousPayload.model_call_cancellation_supported = $false
    $PreviousPayload.thought_cancellation_supported = $false
    $PreviousPayload.next_smallest_truthful_gap = 'lens_voice_model_call_abort_and_thought_relevance'
    Write-OverlayVoiceTurnReceipt -Root $Root -TurnId $PreviousTurnId -Payload $PreviousPayload
  }
  $EffectiveWakePhraseDetected = (-not [bool]$SyntheticTranscript) -and [bool]$WakePhraseDetected
  $TranscriptSource = if ($SyntheticTranscript) {
    'operator_explicit_synthetic_voice_turn'
  } elseif ($EffectiveWakePhraseDetected) {
    'microphone_wake_listener'
  } else {
    'microphone_continuous_dictation'
  }
  $VoiceRecognition = if ($SyntheticTranscript) {
    'not_used_explicit_synthetic_transcript'
  } elseif ($EffectiveWakePhraseDetected) {
    'system_speech_wake_prefixed_dictation'
  } else {
    'system_speech_continuous_dictation'
  }
  $Payload = [ordered]@{
    kind = 'lens.overlay.voice.turn_state'
    status = 'chat_pending'
    active_turn_id = $TurnId
    previous_turn_id = $PreviousTurnId
    previous_status = $PreviousStatus
    started_at = [DateTimeOffset]::UtcNow.ToString('o')
    updated_at = [DateTimeOffset]::UtcNow.ToString('o')
    wake_count = $WakeCount
    recognition_confidence = [Math]::Round($RecognitionConfidence, 3)
    recognition_threshold = $RecognitionThreshold
    wake_alias_count = $WakeAliasCount
    wake_phrase_detected = [bool]$EffectiveWakePhraseDetected
    continuous_voice_chat = (-not [bool]$SyntheticTranscript -and -not [bool]$EffectiveWakePhraseDetected)
    synthetic_transcript = [bool]$SyntheticTranscript
    synthetic_voice_turn = [bool]$SyntheticTranscript
    synthetic_voice_turn_command = [bool]$SyntheticTranscript
    transcript_source = $TranscriptSource
    explicit_operator_text = [bool]$SyntheticTranscript
    microphone_speech = (-not [bool]$SyntheticTranscript)
    microphone_recognition_claimed = (-not [bool]$SyntheticTranscript)
    voice_recognition = $VoiceRecognition
    transcript_length = ([string]$UtteranceText).Length
    transcript_hash = Get-OverlayTextDigest -Text $UtteranceText
    transcript_redacted = $true
    overlay_stores_transcript = $false
    latest_voice_turn_wins = $true
    stale_reply_suppression_supported = $true
    thought_relevance_status = 'pending_current_turn'
    thought_retention_policy = 'pending_until_reply_or_superseded'
    cancels_prior_owned_speech = $true
    prior_speech_stopped = [bool]$PriorSpeech.stopped
    prior_speech_pid = [int]$PriorSpeech.process_id
    arbitrary_audio_control = $false
    model_call_abort_requested = $false
    model_call_abort_observed = $false
    model_call_cancellation_supported = $false
    thought_cancellation_supported = $false
    next_smallest_truthful_gap = 'lens_voice_model_call_abort_and_thought_relevance'
  }
  Write-OverlayVoiceTurnFile -Path (Get-OverlayVoiceTurnStatusPath -Root $Root) -Payload $Payload
  Write-OverlayVoiceTurnReceipt -Root $Root -TurnId $TurnId -Payload $Payload
  return $Payload
}

function Update-OverlayVoiceTurnReceipt {
  param(
    [string]$Root,
    [string]$TurnId,
    [string]$Status,
    [object]$Payload
  )

  $TurnPayload = [ordered]@{}
  if ($Payload -is [System.Collections.IDictionary]) {
    foreach ($Key in $Payload.Keys) {
      $TurnPayload[$Key] = $Payload[$Key]
    }
  } elseif ($null -ne $Payload) {
    foreach ($Property in $Payload.PSObject.Properties) {
      $TurnPayload[$Property.Name] = $Property.Value
    }
  }
  $TurnPayload.updated_at = [DateTimeOffset]::UtcNow.ToString('o')
  $TurnPayload.status = $Status
  Write-OverlayVoiceTurnReceipt -Root $Root -TurnId $TurnId -Payload $TurnPayload
  if (Test-OverlayVoiceTurnCurrent -Root $Root -TurnId $TurnId) {
    Write-OverlayVoiceTurnFile -Path (Get-OverlayVoiceTurnStatusPath -Root $Root) -Payload $TurnPayload
  }
}

function Get-OverlayVoiceReadback {
  param([string]$Root)

  $Status = Read-JsonFile -Path (Get-OverlayVoiceStatusPath -Root $Root)
  if ($null -ne $Status -and (Get-StringProperty -Payload $Status -Name 'kind' -Default '') -eq 'lens.overlay.voice.runtime') {
    if ((Get-StringProperty -Payload $Status -Name 'status' -Default '') -eq 'voice_input_suppressed_while_speaking') {
      $SpeechGuard = Get-OverlayOwnedSpeechGuardState -Root $Root
      if (-not (Get-BoolProperty -Payload $SpeechGuard -Name 'owned_speech_guard_active' -Default $false)) {
        $Provider = Get-StringProperty -Payload $Status -Name 'voice_provider' -Default $VoiceProvider
        $SelectedVoice = Get-StringProperty -Payload $Status -Name 'selected_voice' -Default ''
        $WakeListening = Get-BoolProperty -Payload $Status -Name 'wake_listening' -Default $false
        $WakePhraseText = Get-StringProperty -Payload $Status -Name 'wake_phrase' -Default $WakePhrase
        $Refreshed = New-OverlayVoiceProjection -SelectedVoiceName $SelectedVoice -Provider $Provider -WakeListening $WakeListening -WakePhraseText $WakePhraseText
        $Refreshed.status = if ($WakeListening) { 'listening' } else { 'available' }
        $Refreshed.ok = $true
        $Refreshed.previous_voice_status = 'voice_input_suppressed_while_speaking'
        $Refreshed.previous_voice_status_stale = $true
        $Refreshed.stale_suppression_cleared = $true
        $Refreshed.microphone_gate_while_speaking = 'francis_stop_only'
        $Refreshed.conversation_forwarding_while_speaking = $false
        $Refreshed.message = 'Francis owned speech guard is inactive; stale suppression status was cleared for readback.'
        return $Refreshed
      }
    }
    return $Status
  }
  return New-OverlayVoiceProjection
}

function Get-OverlayTextDigest {
  param([string]$Text)

  $Sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $Bytes = [System.Text.Encoding]::UTF8.GetBytes([string]$Text)
    $HashBytes = $Sha.ComputeHash($Bytes)
    return ([System.BitConverter]::ToString($HashBytes)).Replace('-', '').ToLowerInvariant()
  } finally {
    $Sha.Dispose()
  }
}

function New-OverlayWakeAliasList {
  param([string]$Phrase)

  $BoundedPhrase = ([string]$Phrase).Trim().ToLowerInvariant()
  if ([string]::IsNullOrWhiteSpace($BoundedPhrase)) {
    $BoundedPhrase = 'hey francis'
  }
  $Aliases = New-Object System.Collections.Generic.List[string]
  foreach ($Candidate in @($BoundedPhrase, 'hey francis', 'hey frances', 'hi francis', 'hi frances', 'okay francis', 'ok francis')) {
    $BoundedCandidate = ([string]$Candidate).Trim().ToLowerInvariant()
    if (-not [string]::IsNullOrWhiteSpace($BoundedCandidate) -and -not $Aliases.Contains($BoundedCandidate)) {
      [void]$Aliases.Add($BoundedCandidate)
    }
  }
  return [string[]]$Aliases.ToArray()
}

function Get-OverlayWakePrefixedUtterance {
  param(
    [string]$RecognizedText,
    [string[]]$WakeAliases
  )

  $Text = ([string]$RecognizedText).Trim()
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return ''
  }

  $OrderedAliases = @($WakeAliases | Sort-Object { $_.Length } -Descending)
  foreach ($Alias in $OrderedAliases) {
    $CleanAlias = ([string]$Alias).Trim()
    if ([string]::IsNullOrWhiteSpace($CleanAlias)) {
      continue
    }
    if ($Text.Equals($CleanAlias, [System.StringComparison]::OrdinalIgnoreCase)) {
      return ''
    }
    $Prefix = '{0} ' -f $CleanAlias
    if ($Text.StartsWith($Prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
      return $Text.Substring($CleanAlias.Length).Trim()
    }
  }
  return ''
}

function Test-OverlayWakePhraseRecognized {
  param(
    [string]$RecognizedText,
    [string[]]$WakeAliases
  )

  $Text = ([string]$RecognizedText).Trim()
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return $false
  }
  foreach ($Alias in $WakeAliases) {
    $CleanAlias = ([string]$Alias).Trim()
    if (-not [string]::IsNullOrWhiteSpace($CleanAlias) -and $Text.Equals($CleanAlias, [System.StringComparison]::OrdinalIgnoreCase)) {
      return $true
    }
  }
  return $false
}

function Test-OverlayStopPhraseRecognized {
  param(
    [string]$RecognizedText,
    [string[]]$WakeAliases
  )

  $Text = (([string]$RecognizedText).Trim().ToLowerInvariant() -replace '[^\p{L}\p{Nd}\s]', ' ')
  $Text = ($Text -replace '\s+', ' ').Trim()
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return $false
  }

  $StopPhrases = New-Object System.Collections.Generic.List[string]
  foreach ($Candidate in @('francis stop', 'frances stop')) {
    if (-not $StopPhrases.Contains($Candidate)) {
      [void]$StopPhrases.Add($Candidate)
    }
  }
  foreach ($Alias in $WakeAliases) {
    $CleanAlias = (([string]$Alias).Trim().ToLowerInvariant() -replace '[^\p{L}\p{Nd}\s]', ' ')
    $CleanAlias = ($CleanAlias -replace '\s+', ' ').Trim()
    if (-not [string]::IsNullOrWhiteSpace($CleanAlias)) {
      $Candidate = '{0} stop' -f $CleanAlias
      if (-not $StopPhrases.Contains($Candidate)) {
        [void]$StopPhrases.Add($Candidate)
      }
    }
  }

  return $StopPhrases.Contains($Text)
}

function Invoke-OverlayVoiceStopPhrase {
  param(
    [string]$Root,
    [string]$RecognizedText,
    [string]$Provider,
    [string]$Voice,
    [string]$WakePhraseText = $WakePhrase,
    [double]$RecognitionConfidence = 0.0,
    [double]$RecognitionThreshold = $WakeConfidenceThreshold,
    [int]$WakeAliasCount = 0,
    [int]$WakeCount = 0,
    [object]$SpeechGuard = $null
  )

  if ($null -eq $SpeechGuard) {
    $SpeechGuard = Get-OverlayOwnedSpeechGuardState -Root $Root -CooldownSeconds 4
  }
  $PriorSpeech = Stop-OverlayVoiceSpeechProcess -Root $Root -Reason 'francis_stop_phrase_interrupted_owned_speech'
  $Previous = Read-OverlayVoiceTurnState -Root $Root
  $PreviousTurnId = if ($null -ne $Previous) { Get-StringProperty -Payload $Previous -Name 'active_turn_id' -Default '' } else { '' }
  $PreviousStatus = if ($null -ne $Previous) { Get-StringProperty -Payload $Previous -Name 'status' -Default '' } else { '' }
  $InterruptedActiveTurn = (-not [string]::IsNullOrWhiteSpace($PreviousTurnId) -and $PreviousStatus -in @('active', 'chat_pending', 'speaking'))

  if ($InterruptedActiveTurn) {
    $PreviousPayload = [ordered]@{}
    foreach ($Property in $Previous.PSObject.Properties) {
      $PreviousPayload[$Property.Name] = $Property.Value
    }
    $PreviousPayload.status = 'interrupted_by_francis_stop_phrase'
    $PreviousPayload.interrupted_at = [DateTimeOffset]::UtcNow.ToString('o')
    $PreviousPayload.interrupt_phrase = 'francis_stop'
    $PreviousPayload.speech_cancelled_at_interruption = [bool]$PriorSpeech.stopped
    $PreviousPayload.speech_cancelled_process_id = [int]$PriorSpeech.process_id
    $PreviousPayload.context_scrubbed = $true
    $PreviousPayload.context_scrub_scope = 'interrupted_voice_turn_reply_context'
    $PreviousPayload.context_expansion_allowed_on_next_turn = $true
    $PreviousPayload.thought_relevance_status = 'interrupted_by_operator_stop_phrase'
    $PreviousPayload.thought_retention_policy = 'scrub_interrupted_reply_context_unless_operator_reopens'
    $PreviousPayload.chat_reply_suppressed = $true
    $PreviousPayload.speech_output_suppressed = $true
    $PreviousPayload.latest_voice_turn_wins = $true
    $PreviousPayload.stale_reply_suppression_supported = $true
    $PreviousPayload.model_call_abort_requested = $false
    $PreviousPayload.model_call_abort_observed = $false
    $PreviousPayload.model_call_cancellation_supported = $false
    $PreviousPayload.thought_cancellation_supported = $false
    $PreviousPayload.arbitrary_audio_control = $false
    $PreviousPayload.next_smallest_truthful_gap = 'lens_voice_model_call_abort_and_thought_relevance'
    Write-OverlayVoiceTurnFile -Path (Get-OverlayVoiceTurnStatusPath -Root $Root) -Payload $PreviousPayload
    Write-OverlayVoiceTurnReceipt -Root $Root -TurnId $PreviousTurnId -Payload $PreviousPayload
  }

  $SelectedSpeechVoice = Get-OverlaySelectedVoiceName -Provider $Provider -Voice $Voice
  $Payload = New-OverlayVoiceProjection -SelectedVoiceName $SelectedSpeechVoice -Provider $Provider -WakeListening $true -WakePhraseText $WakePhraseText
  $Payload.status = 'francis_stop_listening_restored'
  $Payload.ok = $true
  $Payload.message = 'Francis stop was recognized while speech was gated; owned speech was interrupted and listening returned without forwarding a new chat turn.'
  $Payload.stop_phrase_detected = $true
  $Payload.interrupt_phrase = 'francis_stop'
  $Payload.interrupted_active_voice_turn = [bool]$InterruptedActiveTurn
  $Payload.interrupted_turn_id = $PreviousTurnId
  $Payload.interrupted_previous_status = $PreviousStatus
  $Payload.owned_speech_active = Get-BoolProperty -Payload $SpeechGuard -Name 'owned_speech_active' -Default $false
  $Payload.owned_speech_recently_completed = Get-BoolProperty -Payload $SpeechGuard -Name 'owned_speech_recently_completed' -Default $false
  $Payload.speech_cancelled = [bool]$PriorSpeech.stopped
  $Payload.speech_cancelled_process_id = [int]$PriorSpeech.process_id
  $Payload.context_scrubbed = [bool]$InterruptedActiveTurn
  $Payload.context_scrub_scope = if ($InterruptedActiveTurn) { 'interrupted_voice_turn_reply_context' } else { 'none_active' }
  $Payload.context_expansion_allowed_on_next_turn = $true
  $Payload.chat_bridge_status = 'not_called'
  $Payload.chat_route_writes_conversation_ledger = $false
  $Payload.conversation_forwarding_suppressed = $true
  $Payload.speech_output_suppressed = $true
  $Payload.wake_phrase_detected = $true
  $Payload.wake_count = $WakeCount
  $Payload.recognition_confidence = [Math]::Round($RecognitionConfidence, 3)
  $Payload.recognition_threshold = $RecognitionThreshold
  $Payload.wake_alias_count = $WakeAliasCount
  $Payload.transcript_length = ([string]$RecognizedText).Length
  $Payload.transcript_hash = Get-OverlayTextDigest -Text $RecognizedText
  $Payload.transcript_redacted = $true
  $Payload.stores_transcript = $false
  $Payload.microphone_gate_while_speaking = 'francis_stop_only'
  $Payload.conversation_forwarding_while_speaking = $false
  $Payload.barge_in_scope = 'cancel_owned_speech_process_on_francis_stop_only'
  $Payload.model_call_abort_requested = $false
  $Payload.model_call_abort_observed = $false
  $Payload.model_call_cancellation_supported = $false
  $Payload.thought_cancellation_supported = $false
  $Payload.arbitrary_audio_control = $false
  Write-OverlayVoiceState -Root $Root -Payload $Payload
  return $Payload
}

function Resolve-OverlayVoiceOrbCommand {
  param([string]$Text)

  $Normalized = (([string]$Text).Trim().ToLowerInvariant() -replace '[^\p{L}\p{Nd}\s]', ' ')
  $Normalized = ($Normalized -replace '\s+', ' ').Trim()
  $Result = [ordered]@{
    recognized = $false
    intent = ''
    command = ''
    target_side = ''
    target_anchor = ''
    normalized_text_length = $Normalized.Length
    requires_explicit_orb_reference = $true
    requires_direction = $true
    conversation_forwarding_suppressed = $true
    grants_execution_authority = $false
    grants_mutation_authority = $false
  }
  if ([string]::IsNullOrWhiteSpace($Normalized)) {
    return $Result
  }

  $Words = @($Normalized.Split([char[]]@(' '), [System.StringSplitOptions]::RemoveEmptyEntries))
  $HasOrbReference = $Words -contains 'orb' -or $Words -contains 'orbs'
  $HasMoveVerb = $Words -contains 'move' -or $Words -contains 'put' -or $Words -contains 'place' -or $Words -contains 'dock' -or $Words -contains 'shift' -or $Words -contains 'send'
  $MoveLeft = $Words -contains 'left'
  $MoveRight = $Words -contains 'right'

  if (-not $HasOrbReference -or -not $HasMoveVerb -or ($MoveLeft -eq $MoveRight)) {
    return $Result
  }

  $TargetSide = if ($MoveLeft) { 'left' } else { 'right' }
  $Result.recognized = $true
  $Result.intent = 'move_orb'
  $Result.command = 'move_orb_{0}_side' -f $TargetSide
  $Result.target_side = $TargetSide
  $Result.target_anchor = 'voice_command_{0}_side' -f $TargetSide
  return $Result
}

function Set-OrbWindowSidePosition {
  param(
    [object]$Window,
    [object]$WorkArea,
    [ValidateSet('left', 'right')]
    [string]$Side,
    [double]$Margin = 48.0,
    [object]$MotionState = $null,
    [string]$TargetAnchor = '',
    [string]$Root = ''
  )

  if ($null -eq $Window -or $null -eq $WorkArea) {
    return [ordered]@{
      applied = $false
      error = 'overlay_window_or_work_area_unavailable'
    }
  }

  $ApplyPosition = [System.Func[object]]{
    $MinimumLeft = [double]$WorkArea.Left
    $MinimumTop = [double]$WorkArea.Top
    $MaximumLeft = [Math]::Max($MinimumLeft, [double]$WorkArea.Right - [double]$Window.Width)
    $MaximumTop = [Math]::Max($MinimumTop, [double]$WorkArea.Bottom - [double]$Window.Height)
    $TargetLeft = if ($Side -eq 'left') {
      Clamp-OverlayDouble -Value ($MinimumLeft + $Margin) -Minimum $MinimumLeft -Maximum $MaximumLeft
    } else {
      Clamp-OverlayDouble -Value ($MaximumLeft - $Margin) -Minimum $MinimumLeft -Maximum $MaximumLeft
    }
    $TargetTop = Clamp-OverlayDouble -Value ([double]$Window.Top) -Minimum $MinimumTop -Maximum $MaximumTop

    $Window.Left = $TargetLeft
    $Window.Top = $TargetTop
    if (-not [string]::IsNullOrWhiteSpace($TargetAnchor)) {
      $script:LensOverlayOperatorPositionAnchor = $TargetAnchor
    }
    Reset-OrbAutonomousMotionAnchor -Window $Window -MotionState $MotionState
    $PositionReceiptWritten = $false
    if (-not [string]::IsNullOrWhiteSpace($Root)) {
      Write-OverlayPositionState -Root $Root -Window $Window -MotionState $MotionState -OverlayWindowVisible $true
      $PositionReceiptWritten = $true
    }
    return [ordered]@{
      applied = $true
      left = [double]$Window.Left
      top = [double]$Window.Top
      target_side = $Side
      margin = $Margin
      position_receipt_written = $PositionReceiptWritten
    }
  }

  if ($null -ne $Window.Dispatcher -and -not [bool]$Window.Dispatcher.CheckAccess()) {
    return $Window.Dispatcher.Invoke($ApplyPosition)
  }
  return $ApplyPosition.Invoke()
}

function Invoke-OverlayVoiceOrbCommand {
  param(
    [string]$Root,
    [object]$Command,
    [string]$RecognizedText,
    [string]$Provider,
    [string]$Voice,
    [string]$RemoteVoiceId = '',
    [string]$WakePhraseText = $WakePhrase,
    [double]$RecognitionConfidence = 0.0,
    [double]$RecognitionThreshold = $WakeConfidenceThreshold,
    [int]$WakeAliasCount = 0,
    [int]$WakeCount = 0,
    [bool]$WakePhraseDetected = $true,
    [bool]$ContinuousVoiceChat = $false,
    [string]$CommandSource = 'local_overlay_speech_recognition',
    [string]$CommandRequestId = '',
    [string]$TranscriptHashOverride = '',
    [int]$TranscriptLengthOverride = -1
  )

  $TargetSide = Get-StringProperty -Payload $Command -Name 'target_side' -Default ''
  $TargetAnchor = Get-StringProperty -Payload $Command -Name 'target_anchor' -Default ''
  $CommandName = Get-StringProperty -Payload $Command -Name 'command' -Default ''
  $SelectedVoice = Get-OverlaySelectedVoiceName -Provider $Provider -Voice $Voice -RequestedVoiceId $RemoteVoiceId
  $Payload = New-OverlayVoiceProjection -SelectedVoiceName $SelectedVoice -Provider $Provider -WakeListening $true -WakePhraseText $WakePhraseText
  $Payload.local_overlay_command = $true
  $Payload.voice_orb_command = $true
  $Payload.voice_command_recognized = $true
  $Payload.orb_command = $CommandName
  $Payload.overlay_position_command = $CommandName
  $Payload.overlay_position_command_source = $CommandSource
  $Payload.overlay_position_command_request_id = $CommandRequestId
  $Payload.target_side = $TargetSide
  $Payload.target_anchor = $TargetAnchor
  $Payload.wake_phrase_detected = [bool]$WakePhraseDetected
  $Payload.wake_count = $WakeCount
  $Payload.recognition_confidence = [Math]::Round($RecognitionConfidence, 3)
  $Payload.recognition_threshold = $RecognitionThreshold
  $Payload.wake_alias_count = $WakeAliasCount
  $Payload.continuous_voice_chat = [bool]$ContinuousVoiceChat
  $Payload.transcript_source = if ($CommandSource -eq 'chatgpt_voice_bridge_file_request') { 'chatgpt_voice_bridge_command_request' } elseif ($WakePhraseDetected) { 'microphone_wake_listener' } else { 'microphone_continuous_dictation' }
  $Payload.voice_recognition = 'system_speech_local_orb_command'
  $Payload.transcript_length = if ($TranscriptLengthOverride -ge 0) { $TranscriptLengthOverride } else { ([string]$RecognizedText).Length }
  $Payload.transcript_hash = if (-not [string]::IsNullOrWhiteSpace($TranscriptHashOverride)) { $TranscriptHashOverride } else { Get-OverlayTextDigest -Text $RecognizedText }
  $Payload.transcript_redacted = $true
  $Payload.stores_transcript = $false
  $Payload.chat_bridge_status = 'not_called'
  $Payload.chat_route_writes_conversation_ledger = $false
  $Payload.conversation_forwarding_suppressed = $true
  $Payload.speech_output_suppressed = $true
  $Payload.bounded_overlay_position_mutation = $true
  $Payload.mutation_authority_scope = 'runtime_overlay_position_only'
  $Payload.grants_execution_authority = $false
  $Payload.grants_mutation_authority = $false

  if ($TargetSide -notin @('left', 'right')) {
    $Payload.status = 'orb_voice_command_refused'
    $Payload.ok = $false
    $Payload.error = 'unsupported_orb_position_target'
    $Payload.runtime_overlay_position_changed = $false
    $Payload.message = 'Orb voice command was recognized but refused because the requested side is unsupported.'
    Write-OverlayVoiceState -Root $Root -Payload $Payload
    return $Payload
  }

  $Window = $script:LensOverlayWindow
  $MotionState = $script:LensOverlayMotionState
  $WorkArea = $script:LensOverlayWorkArea
  if ($null -eq $WorkArea -and [System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT) {
    try {
      $WorkArea = [System.Windows.SystemParameters]::WorkArea
    } catch {
      $WorkArea = $null
    }
  }

  $Position = Set-OrbWindowSidePosition -Window $Window -WorkArea $WorkArea -Side $TargetSide -Margin 48 -MotionState $MotionState -TargetAnchor $TargetAnchor -Root $Root
  if (-not [bool]$Position['applied']) {
    $Payload.status = 'orb_voice_command_unavailable'
    $Payload.ok = $false
    $Payload.error = Get-StringProperty -Payload $Position -Name 'error' -Default 'overlay_window_position_unavailable'
    $Payload.runtime_overlay_position_changed = $false
    $Payload.position_receipt_written = $false
    $Payload.message = 'Orb voice command was recognized but the live overlay window was unavailable.'
    Write-OverlayVoiceState -Root $Root -Payload $Payload
    return $Payload
  }

  $Payload.status = 'orb_voice_command_applied'
  $Payload.ok = $true
  $Payload.runtime_overlay_position_changed = $true
  $Payload.position_receipt_written = Get-BoolProperty -Payload $Position -Name 'position_receipt_written' -Default $false
  $Payload.overlay_left = [double]$Position['left']
  $Payload.overlay_top = [double]$Position['top']
  $Payload.message = 'Orb position voice command applied locally and not forwarded to chat.'
  Write-OverlayVoiceState -Root $Root -Payload $Payload
  return $Payload
}

function Limit-OverlayVoiceReplyText {
  param(
    [string]$Text,
    [int]$MaxLength = 900
  )

  $Bounded = ([string]$Text).Trim()
  if ($Bounded.Length -le $MaxLength) {
    return $Bounded
  }
  if ($MaxLength -le 3) {
    return $Bounded.Substring(0, $MaxLength)
  }
  $Candidate = $Bounded.Substring(0, $MaxLength).TrimEnd()
  $MinimumUsefulBoundary = [Math]::Min(160, [Math]::Floor($MaxLength * 0.45))
  $SentenceBoundary = $Candidate.LastIndexOfAny([char[]]@('.', '!', '?'))
  if ($SentenceBoundary -ge $MinimumUsefulBoundary) {
    return $Candidate.Substring(0, $SentenceBoundary + 1).TrimEnd()
  }
  $WordBoundary = $Candidate.LastIndexOf(' ')
  if ($WordBoundary -ge $MinimumUsefulBoundary) {
    return ($Candidate.Substring(0, $WordBoundary).TrimEnd() + '...')
  }
  return ($Bounded.Substring(0, $MaxLength - 3).TrimEnd() + '...')
}

function Start-OverlayVoiceSpeechProcess {
  param(
    [string]$Root,
    [string]$Text,
    [string]$Provider,
    [string]$Voice,
    [int]$Rate,
    [int]$Volume,
    [string]$RemoteVoiceId = '',
    [string]$RemoteModelId = 'eleven_multilingual_v2',
    [string]$RemoteOutputFormat = 'mp3_44100_128',
    [double]$RemoteStability = 0.58,
    [double]$RemoteSimilarityBoost = 0.78,
    [double]$RemoteStyle = 0.0,
    [double]$RemoteSpeed = 0.89,
    [bool]$RemoteUseSpeakerBoost = $false,
    [string]$WakePhraseText = $WakePhrase
  )

  $PriorSpeech = Stop-OverlayVoiceSpeechProcess -Root $Root -Reason 'barge_in_replaced_owned_speech_process'
  $PidPath = Get-OverlayVoiceSpeechPidPath -Root $Root
  $PlaybackStatusPath = Get-OverlayVoicePlaybackStatusPath -Root $Root
  $SpeechScriptPath = ''
  $PowerShell = Get-Command powershell -ErrorAction SilentlyContinue
  if ($null -eq $PowerShell) {
    $PowerShell = Get-Command pwsh -ErrorAction Stop
  }

  try {
    $SpeechScriptPath = New-OverlayVoiceTextFile -Root $Root -Text $Text
  } catch {
    return [ordered]@{
      ok = $false
      process_id = 0
      pid_path = 'data/runtime/lens-overlay/lens-overlay-speech.pid'
      playback_status_path = 'data/runtime/lens-overlay/voice-playback-status.json'
      playback_status_full_path = $PlaybackStatusPath
      interrupted_prior_speech = [bool]$PriorSpeech.stopped
      interrupted_prior_speech_pid = [int]$PriorSpeech.process_id
      owns_process = $true
      arbitrary_audio_control = $false
      speech_script_transport = 'transient_local_file'
      speech_script_file_created = $false
      error = [string]$_.Exception.Message
    }
  }

  $ArgumentList = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $PSCommandPath,
    '-Mode',
    'Speak',
    '-DataDir',
    $Root,
    '-VoiceEnvironmentScope',
    $VoiceEnvironmentScope,
    '-VoiceProvider',
    $Provider,
    '-VoiceName',
    $Voice,
    '-ElevenLabsVoiceId',
    $RemoteVoiceId,
    '-ElevenLabsVoiceName',
    $ElevenLabsVoiceName,
    '-ElevenLabsModelId',
    $RemoteModelId,
    '-ElevenLabsOutputFormat',
    $RemoteOutputFormat,
    '-ElevenLabsStability',
    ([string]$RemoteStability),
    '-ElevenLabsSimilarityBoost',
    ([string]$RemoteSimilarityBoost),
    '-ElevenLabsStyle',
    ([string]$RemoteStyle),
    '-ElevenLabsSpeed',
    ([string]$RemoteSpeed),
    '-WakePhrase',
    $WakePhraseText,
    '-VoiceRate',
    ([string]$Rate),
    '-VoiceVolume',
    ([string]$Volume),
    '-VoiceTextPath',
    $SpeechScriptPath,
    '-PlaybackStateOnly'
  )
  if ($RemoteUseSpeakerBoost) {
    $ArgumentList += '-ElevenLabsUseSpeakerBoost'
  }

  try {
    $ArgumentText = Join-OverlayProcessArguments -Arguments $ArgumentList
    $Process = Start-Process -FilePath $PowerShell.Source -ArgumentList $ArgumentText -WindowStyle Hidden -PassThru
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $PidPath) | Out-Null
    Set-Content -LiteralPath $PidPath -Value ([string]$Process.Id) -Encoding UTF8
    return [ordered]@{
      ok = $true
      process_id = [int]$Process.Id
      pid_path = 'data/runtime/lens-overlay/lens-overlay-speech.pid'
      playback_status_path = 'data/runtime/lens-overlay/voice-playback-status.json'
      playback_status_full_path = $PlaybackStatusPath
      interrupted_prior_speech = [bool]$PriorSpeech.stopped
      interrupted_prior_speech_pid = [int]$PriorSpeech.process_id
      owns_process = $true
      arbitrary_audio_control = $false
      speech_script_transport = 'transient_local_file'
      speech_script_file_created = $true
      speech_script_command_line_redacted = $true
      speech_script_retention = 'transient_deleted_after_playback'
    }
  } catch {
    Remove-OverlayVoiceTextFile -Root $Root -TextPath $SpeechScriptPath
    return [ordered]@{
      ok = $false
      process_id = 0
      pid_path = 'data/runtime/lens-overlay/lens-overlay-speech.pid'
      playback_status_path = 'data/runtime/lens-overlay/voice-playback-status.json'
      playback_status_full_path = $PlaybackStatusPath
      interrupted_prior_speech = [bool]$PriorSpeech.stopped
      interrupted_prior_speech_pid = [int]$PriorSpeech.process_id
      owns_process = $true
      arbitrary_audio_control = $false
      speech_script_transport = 'transient_local_file'
      speech_script_file_created = $true
      speech_script_command_line_redacted = $true
      speech_script_retention = 'transient_deleted_after_playback'
      error = [string]$_.Exception.Message
    }
  }
}

function Invoke-OverlayVoiceChatTurn {
  param(
    [string]$Root,
    [string]$UtteranceText,
    [string]$Provider,
    [string]$Voice,
    [int]$Rate,
    [int]$Volume,
    [string]$RemoteVoiceId = '',
    [string]$RemoteModelId = 'eleven_multilingual_v2',
    [string]$RemoteOutputFormat = 'mp3_44100_128',
    [double]$RemoteStability = 0.58,
    [double]$RemoteSimilarityBoost = 0.78,
    [double]$RemoteStyle = 0.0,
    [double]$RemoteSpeed = 0.89,
    [bool]$RemoteUseSpeakerBoost = $false,
    [string]$WakePhraseText = $WakePhrase,
    [double]$RecognitionConfidence = 0.0,
    [double]$RecognitionThreshold = $WakeConfidenceThreshold,
    [int]$WakeAliasCount = 0,
    [int]$WakeCount = 0,
    [bool]$SyntheticTranscript = $false,
    [bool]$WakePhraseDetected = $true
  )

  $BoundedUtterance = ([string]$UtteranceText).Trim()
  $VoicePayloadWakeListening = (-not [bool]$SyntheticTranscript)
  $SelectedVoice = Get-OverlaySelectedVoiceName -Provider $Provider -Voice $Voice -RequestedVoiceId $RemoteVoiceId
  $EffectiveWakePhraseDetected = (-not [bool]$SyntheticTranscript) -and [bool]$WakePhraseDetected
  $ContinuousVoiceChat = (-not [bool]$SyntheticTranscript -and -not [bool]$EffectiveWakePhraseDetected)
  $TranscriptSource = if ($SyntheticTranscript) {
    'operator_explicit_synthetic_voice_turn'
  } elseif ($EffectiveWakePhraseDetected) {
    'microphone_wake_listener'
  } else {
    'microphone_continuous_dictation'
  }
  $VoiceRecognition = if ($SyntheticTranscript) {
    'not_used_explicit_synthetic_transcript'
  } elseif ($EffectiveWakePhraseDetected) {
    'system_speech_wake_prefixed_dictation'
  } else {
    'system_speech_continuous_dictation'
  }
  if ([string]::IsNullOrWhiteSpace($BoundedUtterance)) {
    if ($SyntheticTranscript) {
      $Payload = New-OverlayVoiceProjection -SelectedVoiceName $SelectedVoice -Provider $Provider -WakeListening $false -WakePhraseText $WakePhraseText
      $Payload.status = 'synthetic_voice_turn_refused'
      $Payload.ok = $false
      $Payload.error = 'synthetic_voice_turn_text_required'
      $Payload.message = 'Synthetic voice turn requires explicit bounded operator text.'
      $Payload.voice_turn = $true
      $Payload.synthetic_transcript = $true
      $Payload.synthetic_voice_turn = $true
      $Payload.synthetic_voice_turn_command = $true
      $Payload.transcript_source = $TranscriptSource
      $Payload.explicit_operator_text = $true
      $Payload.microphone_speech = $false
      $Payload.microphone_recognition_claimed = $false
      $Payload.voice_recognition = $VoiceRecognition
      $Payload.wake_phrase_detected = $false
      $Payload.transcript_redacted = $true
      $Payload.overlay_stores_transcript = $false
      $Payload.chat_bridge_route = '/chat/send'
      $Payload.chat_bridge_status = 'not_called'
      $Payload.speech_started = $false
      Write-OverlayVoiceState -Root $Root -Payload $Payload
      return $Payload
    }
    return Invoke-OverlayVoiceSpeech -Root $Root -Text $script:LensOverlayWakeResponse -Provider $Provider -Voice $Voice -Rate $Rate -Volume $Volume -RemoteVoiceId $RemoteVoiceId -RemoteModelId $RemoteModelId -RemoteOutputFormat $RemoteOutputFormat -RemoteStability $RemoteStability -RemoteSimilarityBoost $RemoteSimilarityBoost -RemoteStyle $RemoteStyle -RemoteSpeed $RemoteSpeed -RemoteUseSpeakerBoost $RemoteUseSpeakerBoost -WakeListening $true -WakePhraseText $WakePhraseText -SuccessStatus 'wake_acknowledged' -SuccessMessage 'Wake phrase detected and acknowledged through selected speech output.'
  }
  if ($BoundedUtterance.Length -gt 600) {
    $Payload = New-OverlayVoiceProjection -SelectedVoiceName $SelectedVoice -Provider $Provider -WakeListening $VoicePayloadWakeListening -WakePhraseText $WakePhraseText
    $Payload.status = 'voice_chat_refused'
    $Payload.ok = $false
    $Payload.error = 'voice_utterance_too_long'
    $Payload.max_utterance_length = 600
    $Payload.continuous_voice_chat = [bool]$ContinuousVoiceChat
    $Payload.synthetic_transcript = [bool]$SyntheticTranscript
    $Payload.synthetic_voice_turn = [bool]$SyntheticTranscript
    $Payload.synthetic_voice_turn_command = [bool]$SyntheticTranscript
    $Payload.transcript_source = $TranscriptSource
    $Payload.explicit_operator_text = [bool]$SyntheticTranscript
    $Payload.microphone_speech = (-not [bool]$SyntheticTranscript)
    $Payload.microphone_recognition_claimed = (-not [bool]$SyntheticTranscript)
    $Payload.voice_recognition = $VoiceRecognition
    $Payload.wake_phrase_detected = [bool]$EffectiveWakePhraseDetected
    $Payload.transcript_length = $BoundedUtterance.Length
    $Payload.transcript_redacted = $true
    $Payload.stores_transcript = $false
    $Payload.chat_bridge_route = '/chat/send'
    $Payload.chat_bridge_status = 'not_called'
    $Payload.message = 'Voice chat turn refused a wake-prefixed utterance longer than the bounded input limit.'
    Write-OverlayVoiceState -Root $Root -Payload $Payload
    return $Payload
  }

  $VoiceTurn = Start-OverlayVoiceTurn -Root $Root -UtteranceText $BoundedUtterance -RecognitionConfidence $RecognitionConfidence -RecognitionThreshold $RecognitionThreshold -WakeAliasCount $WakeAliasCount -WakeCount $WakeCount -SyntheticTranscript $SyntheticTranscript -WakePhraseDetected $WakePhraseDetected
  $VoiceTurnId = Get-StringProperty -Payload $VoiceTurn -Name 'active_turn_id' -Default ''
  $SupersedesVoiceTurnId = Get-StringProperty -Payload $VoiceTurn -Name 'previous_turn_id' -Default ''

  $ApiBaseUrl = Get-OverlayApiBaseUrl
  $ChatRoute = '/chat/send'
  $ChatUri = '{0}{1}' -f $ApiBaseUrl, $ChatRoute
  $ConversationActor = 'lens.overlay.voice'
  $ChatBridgeStatus = 'unavailable'
  $ChatReply = ''
  $ChatError = ''
  $ChatResponseStatus = ''
  $ChatExecutionTraceCaptured = $false
  $ChatModelRequested = $false
  $ChatModelResponseObserved = $false
  $ChatTraceVoiceTurnCorrelation = $false
  $ChatTraceStaleReplySuppressionSupported = $false
  $ChatTraceModelCallCancellationSupported = $false
  $ChatTraceBackendCurrentVoiceTurnLookupSupported = $false
  $ChatTraceBackendStaleReplyDropSupported = $false
  $ChatTraceThoughtRelevancePruningSupported = $false
  $ChatTraceVoiceTurnRelevancePolicy = ''
  $ChatTraceStaleReplySuppressionOwner = ''
  $ChatTraceStaleReplySuppressionBoundary = ''
  $ChatTraceModelCallAbortBoundary = ''
  $ChatTraceThoughtRelevancePruningBoundary = ''
  $UseLlm = Get-OverlayVoiceUseLlm

  try {
    $Body = [ordered]@{
      message = $BoundedUtterance
      use_llm = $UseLlm
      actor = $ConversationActor
      voice_turn_id = $VoiceTurnId
      supersedes_voice_turn_id = $SupersedesVoiceTurnId
    }
    $ChatBody = Invoke-RestMethod -Uri $ChatUri -Method Post -ContentType 'application/json' -Body ($Body | ConvertTo-Json -Depth 6) -TimeoutSec 20 -ErrorAction Stop
    $ChatReply = (Get-StringProperty -Payload $ChatBody -Name 'reply' -Default '').Trim()
    $ChatError = Get-StringProperty -Payload $ChatBody -Name 'error' -Default ''
    $ChatResponseStatus = Get-StringProperty -Payload $ChatBody -Name 'status' -Default ''
    $Trace = $null
    try {
      $Trace = $ChatBody.PSObject.Properties['execution_trace'].Value
    } catch {
      $Trace = $null
    }
    if ($null -ne $Trace) {
      $ChatExecutionTraceCaptured = Get-BoolProperty -Payload $Trace -Name 'model_or_tool_execution_span_captured' -Default $false
      $ChatModelRequested = Get-BoolProperty -Payload $Trace -Name 'model_call_requested' -Default $false
      $ChatModelResponseObserved = Get-BoolProperty -Payload $Trace -Name 'model_call_response_observed' -Default $false
      $ChatTraceVoiceTurnCorrelation = Get-BoolProperty -Payload $Trace -Name 'voice_turn_correlation' -Default $false
      $ChatTraceStaleReplySuppressionSupported = Get-BoolProperty -Payload $Trace -Name 'stale_reply_suppression_supported' -Default $false
      $ChatTraceModelCallCancellationSupported = Get-BoolProperty -Payload $Trace -Name 'model_call_cancellation_supported' -Default $false
      $ChatTraceBackendCurrentVoiceTurnLookupSupported = Get-BoolProperty -Payload $Trace -Name 'backend_current_voice_turn_lookup_supported' -Default $false
      $ChatTraceBackendStaleReplyDropSupported = Get-BoolProperty -Payload $Trace -Name 'backend_stale_reply_drop_supported' -Default $false
      $ChatTraceThoughtRelevancePruningSupported = Get-BoolProperty -Payload $Trace -Name 'thought_relevance_pruning_supported' -Default $false
      $ChatTraceVoiceTurnRelevancePolicy = Get-StringProperty -Payload $Trace -Name 'voice_turn_relevance_policy' -Default ''
      $ChatTraceStaleReplySuppressionOwner = Get-StringProperty -Payload $Trace -Name 'stale_reply_suppression_owner' -Default ''
      $ChatTraceStaleReplySuppressionBoundary = Get-StringProperty -Payload $Trace -Name 'stale_reply_suppression_boundary' -Default ''
      $ChatTraceModelCallAbortBoundary = Get-StringProperty -Payload $Trace -Name 'model_call_abort_boundary' -Default ''
      $ChatTraceThoughtRelevancePruningBoundary = Get-StringProperty -Payload $Trace -Name 'thought_relevance_pruning_boundary' -Default ''
    }
    if ([string]::IsNullOrWhiteSpace($ChatError) -and -not [string]::IsNullOrWhiteSpace($ChatReply)) {
      $ChatBridgeStatus = 'responded'
    } elseif ($ChatError -eq 'api_permission_denied') {
      $ChatBridgeStatus = 'denied'
    } else {
      $ChatBridgeStatus = 'failed'
    }
  } catch {
    $ChatError = [string]$_.Exception.Message
    $ChatBridgeStatus = 'unavailable'
  }

  $SpokenText = ''
  $SuccessStatus = 'voice_chat_spoken'
  $SuccessMessage = if ($SyntheticTranscript) {
    'Explicit synthetic voice turn routed through /chat/send and spoken through selected speech output.'
  } elseif ($ContinuousVoiceChat) {
    'Continuous voice turn routed through /chat/send and spoken through selected speech output.'
  } else {
    'Voice turn routed through /chat/send and spoken through selected speech output.'
  }
  if ($ChatBridgeStatus -eq 'responded') {
    $SpokenText = $ChatReply
  } elseif ($ChatBridgeStatus -eq 'denied') {
    $SpokenText = if ($SyntheticTranscript) { 'I received the test text, but the voice chat bridge is blocked by policy.' } else { 'I heard you, but the voice chat bridge is blocked by policy.' }
    $SuccessStatus = 'voice_chat_denied'
    $SuccessMessage = if ($SyntheticTranscript) { 'Explicit synthetic voice turn was received, but /chat/send denied the Lens voice actor.' } elseif ($ContinuousVoiceChat) { 'Continuous voice turn was recognized, but /chat/send denied the Lens voice actor.' } else { 'Wake-prefixed utterance was heard, but /chat/send denied the Lens voice actor.' }
  } else {
    $SpokenText = if ($SyntheticTranscript) { 'I received the test text, but the local chat bridge is not available right now.' } else { 'I heard you, but the local chat bridge is not available right now.' }
    $SuccessStatus = 'voice_chat_unavailable'
    $SuccessMessage = if ($SyntheticTranscript) { 'Explicit synthetic voice turn was received, but /chat/send did not return a usable reply.' } elseif ($ContinuousVoiceChat) { 'Continuous voice turn was recognized, but /chat/send did not return a usable reply.' } else { 'Wake-prefixed utterance was heard, but /chat/send did not return a usable reply.' }
  }
  $SpokenText = Limit-OverlayVoiceReplyText -Text $SpokenText -MaxLength 900

  if (-not (Test-OverlayVoiceTurnCurrent -Root $Root -TurnId $VoiceTurnId)) {
    $CurrentVoiceTurn = Read-OverlayVoiceTurnState -Root $Root
    $SupersededByTurnId = if ($null -ne $CurrentVoiceTurn) { Get-StringProperty -Payload $CurrentVoiceTurn -Name 'active_turn_id' -Default '' } else { '' }
    $SuppressedPayload = New-OverlayVoiceProjection -SelectedVoiceName $SelectedVoice -Provider $Provider -WakeListening $VoicePayloadWakeListening -WakePhraseText $WakePhraseText
    $SuppressedPayload.status = 'voice_chat_reply_superseded'
    $SuppressedPayload.ok = $true
    $SuppressedPayload.message = 'Voice chat reply was suppressed because a newer wake-prefixed utterance became the active turn.'
    $SuppressedPayload.voice_turn = $true
    $SuppressedPayload.turn_id = $VoiceTurnId
    $SuppressedPayload.superseded_by_turn_id = $SupersededByTurnId
    $SuppressedPayload.continuous_voice_chat = [bool]$ContinuousVoiceChat
    $SuppressedPayload.synthetic_transcript = [bool]$SyntheticTranscript
    $SuppressedPayload.synthetic_voice_turn = [bool]$SyntheticTranscript
    $SuppressedPayload.synthetic_voice_turn_command = [bool]$SyntheticTranscript
    $SuppressedPayload.transcript_source = $TranscriptSource
    $SuppressedPayload.explicit_operator_text = [bool]$SyntheticTranscript
    $SuppressedPayload.microphone_speech = (-not [bool]$SyntheticTranscript)
    $SuppressedPayload.microphone_recognition_claimed = (-not [bool]$SyntheticTranscript)
    $SuppressedPayload.voice_recognition = $VoiceRecognition
    $SuppressedPayload.wake_phrase_detected = [bool]$EffectiveWakePhraseDetected
    $SuppressedPayload.latest_voice_turn_wins = $true
    $SuppressedPayload.stale_reply_suppression_supported = $true
    $SuppressedPayload.chat_reply_suppressed = $true
    $SuppressedPayload.speech_started = $false
    $SuppressedPayload.speech_output_suppressed = $true
    $SuppressedPayload.speech_suppressed_reason = 'newer_voice_turn_active'
    $SuppressedPayload.chat_bridge_status = $ChatBridgeStatus
    $SuppressedPayload.chat_response_status = $ChatResponseStatus
    $SuppressedPayload.chat_reply_length = $ChatReply.Length
    $SuppressedPayload.chat_reply_redacted = $true
    $SuppressedPayload.model_or_tool_execution_span_captured = $ChatExecutionTraceCaptured
    $SuppressedPayload.model_call_requested = $ChatModelRequested
    $SuppressedPayload.model_call_response_observed = $ChatModelResponseObserved
    $SuppressedPayload.chat_trace_voice_turn_id = $VoiceTurnId
    $SuppressedPayload.chat_trace_supersedes_voice_turn_id = $SupersedesVoiceTurnId
    $SuppressedPayload.chat_trace_voice_turn_correlation = $ChatTraceVoiceTurnCorrelation
    $SuppressedPayload.chat_trace_stale_reply_suppression_supported = $ChatTraceStaleReplySuppressionSupported
    $SuppressedPayload.chat_trace_voice_turn_relevance_policy = $ChatTraceVoiceTurnRelevancePolicy
    $SuppressedPayload.chat_trace_stale_reply_suppression_owner = $ChatTraceStaleReplySuppressionOwner
    $SuppressedPayload.chat_trace_stale_reply_suppression_boundary = $ChatTraceStaleReplySuppressionBoundary
    $SuppressedPayload.chat_trace_model_call_abort_boundary = $ChatTraceModelCallAbortBoundary
    $SuppressedPayload.chat_trace_model_call_cancellation_supported = $ChatTraceModelCallCancellationSupported
    $SuppressedPayload.chat_trace_backend_current_voice_turn_lookup_supported = $ChatTraceBackendCurrentVoiceTurnLookupSupported
    $SuppressedPayload.chat_trace_backend_stale_reply_drop_supported = $ChatTraceBackendStaleReplyDropSupported
    $SuppressedPayload.chat_trace_thought_relevance_pruning_supported = $ChatTraceThoughtRelevancePruningSupported
    $SuppressedPayload.chat_trace_thought_relevance_pruning_boundary = $ChatTraceThoughtRelevancePruningBoundary
    $SuppressedPayload.model_call_completed_after_superseded = $ChatModelResponseObserved
    $SuppressedPayload.model_call_abort_requested = $false
    $SuppressedPayload.model_call_abort_observed = $false
    $SuppressedPayload.model_call_cancellation_supported = $false
    $SuppressedPayload.thought_relevance_status = 'stale_reply_dropped'
    $SuppressedPayload.thought_retention_policy = 'drop_superseded_reply_keep_trace_metadata'
    $SuppressedPayload.thought_cancellation_supported = $false
    $SuppressedPayload.thought_relevance_pruning_supported = $ChatTraceThoughtRelevancePruningSupported
    $SuppressedPayload.stale_reply_suppression_owner = 'lens.overlay'
    $SuppressedPayload.stale_reply_suppression_boundary = 'overlay_voice_turn_current_check'
    $SuppressedPayload.backend_stale_reply_drop_supported = $ChatTraceBackendStaleReplyDropSupported
    $SuppressedPayload.next_smallest_truthful_gap = 'lens_voice_model_call_abort_and_thought_relevance'
    Update-OverlayVoiceTurnReceipt -Root $Root -TurnId $VoiceTurnId -Status 'reply_superseded' -Payload $SuppressedPayload
    return $SuppressedPayload
  }

  $SpeechProcess = Start-OverlayVoiceSpeechProcess -Root $Root -Text $SpokenText -Provider $Provider -Voice $Voice -Rate $Rate -Volume $Volume -RemoteVoiceId $RemoteVoiceId -RemoteModelId $RemoteModelId -RemoteOutputFormat $RemoteOutputFormat -RemoteStability $RemoteStability -RemoteSimilarityBoost $RemoteSimilarityBoost -RemoteStyle $RemoteStyle -RemoteSpeed $RemoteSpeed -RemoteUseSpeakerBoost $RemoteUseSpeakerBoost -WakePhraseText $WakePhraseText
  $SelectedSpeechVoice = $SelectedVoice
  $SpeechPayload = New-OverlayVoiceProjection -SelectedVoiceName $SelectedSpeechVoice -Provider $Provider -WakeListening $VoicePayloadWakeListening -WakePhraseText $WakePhraseText
  $SpeechPayload.status = if ([bool]$SpeechProcess.ok) { 'voice_chat_speech_started' } else { 'voice_chat_speech_start_failed' }
  $SpeechPayload.ok = [bool]$SpeechProcess.ok
  if (-not [bool]$SpeechProcess.ok) {
    $SpeechPayload.error = Get-StringProperty -Payload $SpeechProcess -Name 'error' -Default 'speech_process_start_failed'
  }
  $SpeechPayload.message = if ([bool]$SpeechProcess.ok) { 'Voice turn routed through /chat/send and launched as an interruptible owned speech process.' } else { 'Voice turn routed through /chat/send but owned speech process launch failed.' }
  $SpeechPayload.voice_turn = $true
  $SpeechPayload.turn_id = $VoiceTurnId
  $SpeechPayload.wake_phrase_detected = [bool]$EffectiveWakePhraseDetected
  $SpeechPayload.wake_count = $WakeCount
  $SpeechPayload.recognition_confidence = [Math]::Round($RecognitionConfidence, 3)
  $SpeechPayload.recognition_threshold = $RecognitionThreshold
  $SpeechPayload.wake_alias_count = $WakeAliasCount
  $SpeechPayload.continuous_voice_chat = [bool]$ContinuousVoiceChat
  $SpeechPayload.synthetic_transcript = [bool]$SyntheticTranscript
  $SpeechPayload.synthetic_voice_turn = [bool]$SyntheticTranscript
  $SpeechPayload.synthetic_voice_turn_command = [bool]$SyntheticTranscript
  $SpeechPayload.transcript_source = $TranscriptSource
  $SpeechPayload.explicit_operator_text = [bool]$SyntheticTranscript
  $SpeechPayload.microphone_speech = (-not [bool]$SyntheticTranscript)
  $SpeechPayload.microphone_recognition_claimed = (-not [bool]$SyntheticTranscript)
  $SpeechPayload.voice_recognition = $VoiceRecognition
  $SpeechPayload.transcript_length = $BoundedUtterance.Length
  $SpeechPayload.transcript_hash = Get-OverlayTextDigest -Text $BoundedUtterance
  $SpeechPayload.transcript_redacted = $true
  $SpeechPayload.overlay_stores_transcript = $false
  $SpeechPayload.chat_route_writes_conversation_ledger = ($ChatBridgeStatus -eq 'responded')
  $SpeechPayload.chat_bridge_route = $ChatRoute
  $SpeechPayload.chat_bridge_api_base_url = $ApiBaseUrl
  $SpeechPayload.chat_bridge_actor = $ConversationActor
  $SpeechPayload.chat_bridge_status = $ChatBridgeStatus
  $SpeechPayload.chat_response_status = $ChatResponseStatus
  $SpeechPayload.chat_trace_voice_turn_id = $VoiceTurnId
  $SpeechPayload.chat_trace_supersedes_voice_turn_id = $SupersedesVoiceTurnId
  $SpeechPayload.chat_trace_voice_turn_correlation = $ChatTraceVoiceTurnCorrelation
  $SpeechPayload.chat_trace_stale_reply_suppression_supported = $ChatTraceStaleReplySuppressionSupported
  $SpeechPayload.chat_trace_voice_turn_relevance_policy = $ChatTraceVoiceTurnRelevancePolicy
  $SpeechPayload.chat_trace_stale_reply_suppression_owner = $ChatTraceStaleReplySuppressionOwner
  $SpeechPayload.chat_trace_stale_reply_suppression_boundary = $ChatTraceStaleReplySuppressionBoundary
  $SpeechPayload.chat_trace_model_call_abort_boundary = $ChatTraceModelCallAbortBoundary
  $SpeechPayload.chat_trace_model_call_cancellation_supported = $ChatTraceModelCallCancellationSupported
  $SpeechPayload.chat_trace_backend_current_voice_turn_lookup_supported = $ChatTraceBackendCurrentVoiceTurnLookupSupported
  $SpeechPayload.chat_trace_backend_stale_reply_drop_supported = $ChatTraceBackendStaleReplyDropSupported
  $SpeechPayload.chat_trace_thought_relevance_pruning_supported = $ChatTraceThoughtRelevancePruningSupported
  $SpeechPayload.chat_trace_thought_relevance_pruning_boundary = $ChatTraceThoughtRelevancePruningBoundary
  $SpeechPayload.chat_reply_length = $ChatReply.Length
  $SpeechPayload.chat_reply_redacted = $true
  $SpeechPayload.chat_error = $ChatError
  $SpeechPayload.llm_requested = $UseLlm
  $SpeechPayload.llm_request_source = 'FRANCIS_LENS_VOICE_USE_LLM'
  $SpeechPayload.model_or_tool_execution_span_captured = $ChatExecutionTraceCaptured
  $SpeechPayload.model_call_requested = $ChatModelRequested
  $SpeechPayload.model_call_response_observed = $ChatModelResponseObserved
  $SpeechPayload.speech_script_provider = if ($Provider -eq 'ElevenLabs') { 'elevenlabs_text_to_speech' } else { 'windows_sapi_speech_synthesis' }
  $SpeechPayload.speech_script_length = $SpokenText.Length
  $SpeechPayload.speech_script_max_length = 900
  $SpeechPayload.speech_script_sentence_aware_limit = $true
  $SpeechPayload.speech_script_truncated = ($ChatReply.Length -gt $SpokenText.Length)
  $SpeechPayload.speech_script_redacted = $true
  $SpeechPayload.speech_script_transport = Get-StringProperty -Payload $SpeechProcess -Name 'speech_script_transport' -Default 'transient_local_file'
  $SpeechPayload.speech_script_command_line_redacted = Get-BoolProperty -Payload $SpeechProcess -Name 'speech_script_command_line_redacted' -Default $true
  $SpeechPayload.speech_script_retention = Get-StringProperty -Payload $SpeechProcess -Name 'speech_script_retention' -Default 'transient_deleted_after_playback'
  $SpeechPayload.speech_success_status = $SuccessStatus
  $SpeechPayload.speech_success_message_redacted = $true
  $SpeechPayload.speech_playback_async = [bool]$SpeechProcess.ok
  $SpeechPayload.speech_playback_blocking = $false
  $SpeechPayload.speech_process_pid = [int]$SpeechProcess.process_id
  $SpeechPayload.speech_pid_path = Get-StringProperty -Payload $SpeechProcess -Name 'pid_path' -Default 'data/runtime/lens-overlay/lens-overlay-speech.pid'
  $SpeechPayload.speech_playback_status_path = Get-StringProperty -Payload $SpeechProcess -Name 'playback_status_path' -Default 'data/runtime/lens-overlay/voice-playback-status.json'
  $SpeechPayload.interrupted_prior_speech = [bool]$SpeechProcess.interrupted_prior_speech
  $SpeechPayload.interrupted_prior_speech_pid = [int]$SpeechProcess.interrupted_prior_speech_pid
  $SpeechPayload.prior_speech_cancelled_at_turn_start = Get-BoolProperty -Payload $VoiceTurn -Name 'prior_speech_stopped' -Default $false
  $SpeechPayload.prior_speech_pid_at_turn_start = Get-IntegerProperty -Payload $VoiceTurn -Name 'prior_speech_pid' -Default 0
  $SpeechPayload.wake_listener_released_before_speech_completion = $false
  $SpeechPayload.simultaneous_listen_while_speaking_supported = $false
  $SpeechPayload.stop_phrase_listen_while_speaking_supported = [bool]$SpeechProcess.ok
  $SpeechPayload.microphone_gate_while_speaking = 'francis_stop_only'
  $SpeechPayload.conversation_forwarding_while_speaking = $false
  $SpeechPayload.simultaneous_work_while_speaking_supported = $false
  $SpeechPayload.barge_in_supported = [bool]$SpeechProcess.ok
  $SpeechPayload.barge_in_scope = 'cancel_owned_speech_process_on_francis_stop_only'
  $SpeechPayload.latest_voice_turn_wins = $true
  $SpeechPayload.stale_reply_suppression_supported = $true
  $SpeechPayload.chat_reply_suppressed = $false
  $SpeechPayload.thought_relevance_status = 'current_reply_spoken'
  $SpeechPayload.thought_retention_policy = 'current_turn_active'
  $SpeechPayload.model_call_abort_requested = $false
  $SpeechPayload.model_call_abort_observed = $false
  $SpeechPayload.model_call_cancellation_supported = $false
  $SpeechPayload.arbitrary_audio_control = $false
  $SpeechPayload.thought_cancellation_supported = $false
  $SpeechPayload.thought_relevance_pruning_supported = $ChatTraceThoughtRelevancePruningSupported
  $SpeechPayload.stale_reply_suppression_owner = 'lens.overlay'
  $SpeechPayload.stale_reply_suppression_boundary = 'overlay_voice_turn_current_check'
  $SpeechPayload.backend_stale_reply_drop_supported = $ChatTraceBackendStaleReplyDropSupported
  $SpeechPayload.voice_turn_state_path = 'data/runtime/lens-overlay/voice-turn-status.json'
  $SpeechPayload.voice_turn_receipt_path = 'data/runtime/lens-overlay/voice-turns/{turn_id}.json'
  $SpeechPayload.next_smallest_truthful_gap = 'lens_voice_model_call_abort_and_thought_relevance'
  Update-OverlayVoiceTurnReceipt -Root $Root -TurnId $VoiceTurnId -Status 'speaking' -Payload $SpeechPayload
  Write-OverlayVoiceState -Root $Root -Payload $SpeechPayload
  return $SpeechPayload
}

function Invoke-OverlayVoiceSpeech {
  param(
    [string]$Root,
    [string]$Text,
    [string]$Provider,
    [string]$Voice,
    [int]$Rate,
    [int]$Volume,
    [string]$RemoteVoiceId = '',
    [string]$RemoteModelId = 'eleven_multilingual_v2',
    [string]$RemoteOutputFormat = 'mp3_44100_128',
    [double]$RemoteStability = 0.58,
    [double]$RemoteSimilarityBoost = 0.78,
    [double]$RemoteStyle = 0.0,
    [double]$RemoteSpeed = 0.89,
    [bool]$RemoteUseSpeakerBoost = $false,
    [bool]$WakeListening = $false,
    [string]$WakePhraseText = $WakePhrase,
    [string]$SuccessStatus = 'spoken',
    [string]$SuccessMessage = 'Voice output spoken through local Windows speech synthesis.',
    [string]$StatusPath = ''
  )

  $BoundedText = ([string]$Text).Trim()
  if ([string]::IsNullOrWhiteSpace($BoundedText)) {
    $Payload = New-OverlayVoiceProjection -SelectedVoiceName $Voice -Provider $Provider -WakeListening $WakeListening -WakePhraseText $WakePhraseText
    $Payload.status = 'refused'
    $Payload.ok = $false
    $Payload.error = 'voice_text_required'
    $Payload.message = 'Voice output requires explicit bounded text.'
    Write-OverlayVoiceState -Root $Root -Payload $Payload -StatusPath $StatusPath
    return $Payload
  }
  if ($BoundedText.Length -gt 900) {
    $Payload = New-OverlayVoiceProjection -SelectedVoiceName $Voice -Provider $Provider -WakeListening $WakeListening -WakePhraseText $WakePhraseText
    $Payload.status = 'refused'
    $Payload.ok = $false
    $Payload.error = 'voice_text_too_long'
    $Payload.text_length = $BoundedText.Length
    $Payload.max_text_length = 900
    $Payload.message = 'Voice output refused text longer than the bounded speech limit.'
    Write-OverlayVoiceState -Root $Root -Payload $Payload -StatusPath $StatusPath
    return $Payload
  }

  if ($Provider -eq 'ElevenLabs') {
    $RemoteSuccessMessage = if ($SuccessMessage -eq 'Voice output spoken through local Windows speech synthesis.') { 'Voice output spoken through ElevenLabs remote text-to-speech.' } else { $SuccessMessage }
    return Invoke-OverlayElevenLabsVoiceSpeech -Root $Root -Text $BoundedText -Volume $Volume -WakeListening $WakeListening -WakePhraseText $WakePhraseText -RequestedVoiceId $RemoteVoiceId -ModelId $RemoteModelId -OutputFormat $RemoteOutputFormat -Stability $RemoteStability -SimilarityBoost $RemoteSimilarityBoost -Style $RemoteStyle -Speed $RemoteSpeed -UseSpeakerBoost $RemoteUseSpeakerBoost -SuccessStatus $SuccessStatus -SuccessMessage $RemoteSuccessMessage -StatusPath $StatusPath
  }

  if (-not ([System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT)) {
    $Payload = New-OverlayVoiceProjection -SelectedVoiceName $Voice -Provider $Provider -WakeListening $WakeListening -WakePhraseText $WakePhraseText
    $Payload.status = 'unsupported'
    $Payload.ok = $false
    $Payload.error = 'voice_output_unsupported_platform'
    $Payload.message = 'Voice output is only supported in a Windows user session.'
    Write-OverlayVoiceState -Root $Root -Payload $Payload -StatusPath $StatusPath
    return $Payload
  }

  $Synthesizer = $null
  try {
    Add-Type -AssemblyName System.Speech
    $Synthesizer = New-Object System.Speech.Synthesis.SpeechSynthesizer
    if (-not [string]::IsNullOrWhiteSpace($Voice)) {
      $Synthesizer.SelectVoice($Voice)
    }
    $Synthesizer.Rate = $Rate
    $Synthesizer.Volume = $Volume
    $Synthesizer.SetOutputToDefaultAudioDevice()
    $VoiceName = [string]$Synthesizer.Voice.Name
    $Synthesizer.Speak($BoundedText)
    $Payload = New-OverlayVoiceProjection -SelectedVoiceName $VoiceName -Provider $Provider -WakeListening $WakeListening -WakePhraseText $WakePhraseText
    $Payload.status = $SuccessStatus
    $Payload.ok = $true
    $Payload.voice_name = $VoiceName
    $Payload.text_length = $BoundedText.Length
    $Payload.text_redacted = $true
    $Payload.rate = $Rate
    $Payload.volume = $Volume
    $Payload.message = $SuccessMessage
    Write-OverlayVoiceState -Root $Root -Payload $Payload -StatusPath $StatusPath
    return $Payload
  } catch {
    $Payload = New-OverlayVoiceProjection -SelectedVoiceName $Voice -Provider $Provider -WakeListening $WakeListening -WakePhraseText $WakePhraseText
    $Payload.status = 'failed'
    $Payload.ok = $false
    $Payload.error = [string]$_.Exception.Message
    $Payload.text_length = $BoundedText.Length
    $Payload.text_redacted = $true
    $Payload.message = 'Voice output failed before speech completed.'
    Write-OverlayVoiceState -Root $Root -Payload $Payload -StatusPath $StatusPath
    return $Payload
  } finally {
    if ($null -ne $Synthesizer) {
      $Synthesizer.Dispose()
    }
  }
}

function Start-OverlayWakeListener {
  param(
    [string]$Root,
    [string]$Phrase,
    [string]$Response,
    [string]$Provider,
    [string]$Voice,
    [int]$Rate,
    [int]$Volume,
    [string]$RemoteVoiceId,
    [string]$RemoteModelId,
    [string]$RemoteOutputFormat,
    [double]$RemoteStability,
    [double]$RemoteSimilarityBoost,
    [double]$RemoteStyle,
    [double]$RemoteSpeed,
    [bool]$RemoteUseSpeakerBoost,
    [double]$ConfidenceThreshold = $WakeConfidenceThreshold,
    [bool]$ContinuousVoiceChat = $false
  )

  $BoundedPhrase = ([string]$Phrase).Trim().ToLowerInvariant()
  if ([string]::IsNullOrWhiteSpace($BoundedPhrase)) {
    $BoundedPhrase = 'hey francis'
  }
  $BoundedResponse = ([string]$Response).Trim()
  if ([string]::IsNullOrWhiteSpace($BoundedResponse)) {
    $BoundedResponse = "I'm here."
  }
  if ($BoundedResponse.Length -gt 120) {
    $BoundedResponse = $BoundedResponse.Substring(0, 120)
  }
  $SelectedWakeVoice = Get-OverlaySelectedVoiceName -Provider $Provider -Voice $Voice -RequestedVoiceId $RemoteVoiceId

  try {
    Add-Type -AssemblyName System.Speech
    $Recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine
    $Choices = New-Object System.Speech.Recognition.Choices
    $WakeAliases = [string[]](New-OverlayWakeAliasList -Phrase $BoundedPhrase)
    foreach ($Alias in $WakeAliases) {
      [void]$Choices.Add($Alias)
    }
    $Builder = New-Object System.Speech.Recognition.GrammarBuilder
    $Builder.Culture = $Recognizer.RecognizerInfo.Culture
    $Builder.Append($Choices)
    $Grammar = New-Object System.Speech.Recognition.Grammar($Builder)
    $Grammar.Name = 'Francis Lens wake phrase'
    $Recognizer.LoadGrammar($Grammar)
    $UtteranceBuilder = New-Object System.Speech.Recognition.GrammarBuilder
    $UtteranceBuilder.Culture = $Recognizer.RecognizerInfo.Culture
    $UtteranceBuilder.Append($Choices)
    $UtteranceBuilder.AppendWildcard()
    $UtteranceGrammar = New-Object System.Speech.Recognition.Grammar($UtteranceBuilder)
    $UtteranceGrammar.Name = 'Francis Lens wake-prefixed utterance'
    $Recognizer.LoadGrammar($UtteranceGrammar)
    $DictationGrammar = New-Object System.Speech.Recognition.DictationGrammar
    $DictationGrammar.Name = 'Francis Lens wake-prefixed dictation fallback'
    $Recognizer.LoadGrammar($DictationGrammar)
    $Recognizer.SetInputToDefaultAudioDevice()
    $script:LensOverlayWakeRoot = $Root
    $script:LensOverlayWakePhrase = $BoundedPhrase
    $script:LensOverlayWakeResponse = $BoundedResponse
    $script:LensOverlayWakeAliases = [string[]]$WakeAliases
    $script:LensOverlayWakeVoiceProvider = $Provider
    $script:LensOverlayWakeVoice = $Voice
    $script:LensOverlayWakeRate = $Rate
    $script:LensOverlayWakeVolume = $Volume
    $script:LensOverlayWakeRemoteVoiceId = $RemoteVoiceId
    $script:LensOverlayWakeRemoteModelId = $RemoteModelId
    $script:LensOverlayWakeRemoteOutputFormat = $RemoteOutputFormat
    $script:LensOverlayWakeRemoteStability = $RemoteStability
    $script:LensOverlayWakeRemoteSimilarityBoost = $RemoteSimilarityBoost
    $script:LensOverlayWakeRemoteStyle = $RemoteStyle
    $script:LensOverlayWakeRemoteSpeed = $RemoteSpeed
    $script:LensOverlayWakeRemoteUseSpeakerBoost = $RemoteUseSpeakerBoost
    $script:LensOverlayWakeConfidenceThreshold = $ConfidenceThreshold
    $script:LensOverlayWakeAliasCount = $WakeAliases.Count
    $script:LensOverlayContinuousVoiceChat = [bool]$ContinuousVoiceChat
    $script:LensOverlayWakeAudioEventCount = 0
    $script:LensOverlayWakeSpeechDetectedCount = 0
    $script:LensOverlayWakeSpeechHypothesisCount = 0
    $script:LensOverlayWakeSpeechRejectedCount = 0
    $script:LensOverlayWakeCount = 0
    $Recognizer.Add_AudioLevelUpdated({
        param($Sender, $EventArgs)

        $script:LensOverlayWakeAudioEventCount += 1
        if ($null -ne $script:LensOverlayRuntimeVoice) {
          $script:LensOverlayRuntimeVoice.audio_observed = $true
          $script:LensOverlayRuntimeVoice.audio_event_count = $script:LensOverlayWakeAudioEventCount
          $script:LensOverlayRuntimeVoice.audio_level = [int]$EventArgs.AudioLevel
          if ([int]$EventArgs.AudioLevel -gt 0) {
            $script:LensOverlayRuntimeVoice.has_observed_microphone_signal = $true
            $script:LensOverlayRuntimeVoice.microphone_signal_status = 'signal_observed'
            $script:LensOverlayRuntimeVoice.microphone_input_effective = $true
            $script:LensOverlayRuntimeVoice.needs_operator_audio_input_check = $false
          }
          $script:LensOverlayRuntimeVoice.last_audio_observed_at = [DateTimeOffset]::UtcNow.ToString('o')
          $script:LensOverlayRuntimeVoice.transcript_redacted = $true
        }
      })
    $Recognizer.Add_AudioSignalProblemOccurred({
        param($Sender, $EventArgs)

        if ($null -ne $script:LensOverlayRuntimeVoice) {
          $script:LensOverlayRuntimeVoice.audio_signal_problem = [string]$EventArgs.AudioSignalProblem
          $script:LensOverlayRuntimeVoice.audio_signal_problem_at = [DateTimeOffset]::UtcNow.ToString('o')
          if ([string]$EventArgs.AudioSignalProblem -eq 'NoSignal') {
            if (Get-BoolProperty -Payload $script:LensOverlayRuntimeVoice -Name 'has_observed_microphone_signal' -Default $false) {
              $script:LensOverlayRuntimeVoice.microphone_signal_status = 'silence_after_signal'
              $script:LensOverlayRuntimeVoice.microphone_input_effective = $true
              $script:LensOverlayRuntimeVoice.needs_operator_audio_input_check = $false
              $script:LensOverlayRuntimeVoice.last_no_signal_after_signal_at = [DateTimeOffset]::UtcNow.ToString('o')
            } else {
              $script:LensOverlayRuntimeVoice.microphone_signal_status = 'unknown_until_audio_signal'
              $script:LensOverlayRuntimeVoice.microphone_input_effective = $false
              $script:LensOverlayRuntimeVoice.needs_operator_audio_input_check = $false
              $script:LensOverlayRuntimeVoice.last_no_signal_before_signal_at = [DateTimeOffset]::UtcNow.ToString('o')
            }
          } else {
            $script:LensOverlayRuntimeVoice.microphone_signal_status = 'audio_signal_problem'
            $script:LensOverlayRuntimeVoice.microphone_input_effective = $false
            $script:LensOverlayRuntimeVoice.needs_operator_audio_input_check = $true
          }
          $script:LensOverlayRuntimeVoice.transcript_redacted = $true
        }
      })
    $Recognizer.Add_SpeechDetected({
        param($Sender, $EventArgs)

        $script:LensOverlayWakeSpeechDetectedCount += 1
        if ($null -ne $script:LensOverlayRuntimeVoice) {
          $script:LensOverlayRuntimeVoice.speech_detected = $true
          $script:LensOverlayRuntimeVoice.speech_detected_count = $script:LensOverlayWakeSpeechDetectedCount
          $script:LensOverlayRuntimeVoice.last_speech_detected_at = [DateTimeOffset]::UtcNow.ToString('o')
          $script:LensOverlayRuntimeVoice.transcript_redacted = $true
          $script:LensOverlayRuntimeVoice.speech_recognition_diagnostics = 'redacted_counts_only'
        }
      })
    $Recognizer.Add_SpeechHypothesized({
        param($Sender, $EventArgs)

        $script:LensOverlayWakeSpeechHypothesisCount += 1
        if ($null -ne $script:LensOverlayRuntimeVoice) {
          $script:LensOverlayRuntimeVoice.speech_hypothesis_count = $script:LensOverlayWakeSpeechHypothesisCount
          $script:LensOverlayRuntimeVoice.last_speech_hypothesized_at = [DateTimeOffset]::UtcNow.ToString('o')
          $script:LensOverlayRuntimeVoice.transcript_redacted = $true
          $script:LensOverlayRuntimeVoice.speech_recognition_diagnostics = 'redacted_counts_only'
        }
      })
    $Recognizer.Add_SpeechRecognitionRejected({
        param($Sender, $EventArgs)

        $script:LensOverlayWakeSpeechRejectedCount += 1
        if ($null -ne $script:LensOverlayRuntimeVoice) {
          $script:LensOverlayRuntimeVoice.speech_rejected_count = $script:LensOverlayWakeSpeechRejectedCount
          $script:LensOverlayRuntimeVoice.last_speech_rejected_at = [DateTimeOffset]::UtcNow.ToString('o')
          if ($null -ne $EventArgs -and $null -ne $EventArgs.Result) {
            $script:LensOverlayRuntimeVoice.last_rejected_confidence = [Math]::Round([double]$EventArgs.Result.Confidence, 3)
          }
          $script:LensOverlayRuntimeVoice.transcript_redacted = $true
          $script:LensOverlayRuntimeVoice.stores_transcript = $false
          $script:LensOverlayRuntimeVoice.speech_recognition_diagnostics = 'redacted_counts_only'
        }
      })
    $Recognizer.Add_SpeechRecognized({
        param($Sender, $EventArgs)

        if ($null -eq $EventArgs -or $null -eq $EventArgs.Result) {
          return
        }
        if ([double]$EventArgs.Result.Confidence -lt $script:LensOverlayWakeConfidenceThreshold) {
          $Rejected = New-OverlayVoiceProjection -SelectedVoiceName (Get-OverlaySelectedVoiceName -Provider $script:LensOverlayWakeVoiceProvider -Voice $script:LensOverlayWakeVoice -RequestedVoiceId $script:LensOverlayWakeRemoteVoiceId) -Provider $script:LensOverlayWakeVoiceProvider -WakeListening $true -WakePhraseText $script:LensOverlayWakePhrase
          $Rejected.status = 'wake_rejected_low_confidence'
          $Rejected.ok = $false
          $Rejected.wake_phrase_detected = $false
          $Rejected.recognition_confidence = [Math]::Round([double]$EventArgs.Result.Confidence, 3)
          $Rejected.recognition_threshold = $script:LensOverlayWakeConfidenceThreshold
          $Rejected.wake_alias_count = $script:LensOverlayWakeAliasCount
          $Rejected.transcript_redacted = $true
          $Rejected.stores_transcript = $false
          $Rejected.message = 'Wake phrase candidate was heard below confidence threshold; no speech response was emitted.'
          Write-OverlayVoiceState -Root $script:LensOverlayWakeRoot -Payload $Rejected
          return
        }
        $RecognizedText = [string]$EventArgs.Result.Text
        $UtteranceText = Get-OverlayWakePrefixedUtterance -RecognizedText $RecognizedText -WakeAliases $script:LensOverlayWakeAliases
        $WakePhraseOnly = Test-OverlayWakePhraseRecognized -RecognizedText $RecognizedText -WakeAliases $script:LensOverlayWakeAliases
        $StopPhraseRecognized = Test-OverlayStopPhraseRecognized -RecognizedText $RecognizedText -WakeAliases $script:LensOverlayWakeAliases
        $SpeechGuard = Get-OverlayOwnedSpeechGuardState -Root $script:LensOverlayWakeRoot -CooldownSeconds 4
        $OwnedSpeechActive = Get-BoolProperty -Payload $SpeechGuard -Name 'owned_speech_active' -Default $false
        $OwnedSpeechRecentlyCompleted = Get-BoolProperty -Payload $SpeechGuard -Name 'owned_speech_recently_completed' -Default $false
        if ($StopPhraseRecognized) {
          $script:LensOverlayWakeCount += 1
          [void](Invoke-OverlayVoiceStopPhrase -Root $script:LensOverlayWakeRoot -RecognizedText $RecognizedText -Provider $script:LensOverlayWakeVoiceProvider -Voice $script:LensOverlayWakeVoice -WakePhraseText $script:LensOverlayWakePhrase -RecognitionConfidence ([double]$EventArgs.Result.Confidence) -RecognitionThreshold $script:LensOverlayWakeConfidenceThreshold -WakeAliasCount $script:LensOverlayWakeAliasCount -WakeCount $script:LensOverlayWakeCount -SpeechGuard $SpeechGuard)
          return
        }
        if ($OwnedSpeechActive -or $OwnedSpeechRecentlyCompleted) {
          $Suppressed = New-OverlayVoiceProjection -SelectedVoiceName (Get-OverlaySelectedVoiceName -Provider $script:LensOverlayWakeVoiceProvider -Voice $script:LensOverlayWakeVoice -RequestedVoiceId $script:LensOverlayWakeRemoteVoiceId) -Provider $script:LensOverlayWakeVoiceProvider -WakeListening $true -WakePhraseText $script:LensOverlayWakePhrase
          $Suppressed.status = 'voice_input_suppressed_while_speaking'
          $Suppressed.ok = $true
          $Suppressed.wake_phrase_detected = (-not [string]::IsNullOrWhiteSpace($UtteranceText) -or $WakePhraseOnly)
          $Suppressed.stop_phrase_detected = $false
          $Suppressed.continuous_voice_chat = [bool]$script:LensOverlayContinuousVoiceChat
          $Suppressed.continuous_voice_chat_blocker = if ($OwnedSpeechActive) { 'owned_speech_process_active' } else { 'owned_speech_recently_completed' }
          $Suppressed.owned_speech_recently_completed = [bool]$OwnedSpeechRecentlyCompleted
          $Suppressed.self_trigger_guard_window_seconds = 4
          $Suppressed.recognition_confidence = [Math]::Round([double]$EventArgs.Result.Confidence, 3)
          $Suppressed.recognition_threshold = $script:LensOverlayWakeConfidenceThreshold
          $Suppressed.transcript_length = $RecognizedText.Length
          $Suppressed.transcript_hash = Get-OverlayTextDigest -Text $RecognizedText
          $Suppressed.transcript_source = if ([string]::IsNullOrWhiteSpace($UtteranceText)) { 'microphone_continuous_dictation' } else { 'microphone_wake_listener' }
          $Suppressed.voice_recognition = 'system_speech_suppressed_during_owned_speech'
          $Suppressed.transcript_redacted = $true
          $Suppressed.stores_transcript = $false
          $Suppressed.speech_output_suppressed = $true
          $Suppressed.conversation_forwarding_suppressed = $true
          $Suppressed.microphone_gate_while_speaking = 'francis_stop_only'
          $Suppressed.conversation_forwarding_while_speaking = $false
          $Suppressed.required_interrupt_phrase = 'francis_stop'
          $Suppressed.barge_in_scope = 'cancel_owned_speech_process_on_francis_stop_only'
          $Suppressed.message = if ($OwnedSpeechActive) { 'Francis owned speech is active; microphone input is gated to the Francis stop phrase and this transcript was not forwarded.' } else { 'Francis owned speech just completed; microphone input remains briefly gated to avoid self-trigger loops and this transcript was not forwarded.' }
          Write-OverlayVoiceState -Root $script:LensOverlayWakeRoot -Payload $Suppressed
          return
        }
        $CommandWakePhraseDetected = (-not [string]::IsNullOrWhiteSpace($UtteranceText) -or $WakePhraseOnly)
        $CommandText = if (-not [string]::IsNullOrWhiteSpace($UtteranceText)) { $UtteranceText } else { $RecognizedText }
        $OrbCommand = Resolve-OverlayVoiceOrbCommand -Text $CommandText
        if ([bool]$OrbCommand['recognized'] -and ($CommandWakePhraseDetected -or [bool]$script:LensOverlayContinuousVoiceChat)) {
          $script:LensOverlayWakeCount += 1
          [void](Invoke-OverlayVoiceOrbCommand -Root $script:LensOverlayWakeRoot -Command $OrbCommand -RecognizedText $RecognizedText -Provider $script:LensOverlayWakeVoiceProvider -Voice $script:LensOverlayWakeVoice -RemoteVoiceId $script:LensOverlayWakeRemoteVoiceId -WakePhraseText $script:LensOverlayWakePhrase -RecognitionConfidence ([double]$EventArgs.Result.Confidence) -RecognitionThreshold $script:LensOverlayWakeConfidenceThreshold -WakeAliasCount $script:LensOverlayWakeAliasCount -WakeCount $script:LensOverlayWakeCount -WakePhraseDetected $CommandWakePhraseDetected -ContinuousVoiceChat ([bool]$script:LensOverlayContinuousVoiceChat))
          return
        }
        if ([string]::IsNullOrWhiteSpace($UtteranceText) -and -not $WakePhraseOnly) {
          if ([bool]$script:LensOverlayContinuousVoiceChat) {
            $script:LensOverlayWakeCount += 1
            [void](Invoke-OverlayVoiceChatTurn -Root $script:LensOverlayWakeRoot -UtteranceText $RecognizedText -Provider $script:LensOverlayWakeVoiceProvider -Voice $script:LensOverlayWakeVoice -Rate $script:LensOverlayWakeRate -Volume $script:LensOverlayWakeVolume -RemoteVoiceId $script:LensOverlayWakeRemoteVoiceId -RemoteModelId $script:LensOverlayWakeRemoteModelId -RemoteOutputFormat $script:LensOverlayWakeRemoteOutputFormat -RemoteStability $script:LensOverlayWakeRemoteStability -RemoteSimilarityBoost $script:LensOverlayWakeRemoteSimilarityBoost -RemoteStyle $script:LensOverlayWakeRemoteStyle -RemoteSpeed $script:LensOverlayWakeRemoteSpeed -RemoteUseSpeakerBoost $script:LensOverlayWakeRemoteUseSpeakerBoost -WakePhraseText $script:LensOverlayWakePhrase -RecognitionConfidence ([double]$EventArgs.Result.Confidence) -RecognitionThreshold $script:LensOverlayWakeConfidenceThreshold -WakeAliasCount $script:LensOverlayWakeAliasCount -WakeCount $script:LensOverlayWakeCount -WakePhraseDetected $false)
            return
          }
          $Rejected = New-OverlayVoiceProjection -SelectedVoiceName (Get-OverlaySelectedVoiceName -Provider $script:LensOverlayWakeVoiceProvider -Voice $script:LensOverlayWakeVoice -RequestedVoiceId $script:LensOverlayWakeRemoteVoiceId) -Provider $script:LensOverlayWakeVoiceProvider -WakeListening $true -WakePhraseText $script:LensOverlayWakePhrase
          $Rejected.status = 'wake_rejected_no_wake_phrase'
          $Rejected.ok = $false
          $Rejected.wake_phrase_detected = $false
          $Rejected.recognition_confidence = [Math]::Round([double]$EventArgs.Result.Confidence, 3)
          $Rejected.recognition_threshold = $script:LensOverlayWakeConfidenceThreshold
          $Rejected.wake_alias_count = $script:LensOverlayWakeAliasCount
          $Rejected.transcript_length = $RecognizedText.Length
          $Rejected.transcript_hash = Get-OverlayTextDigest -Text $RecognizedText
          $Rejected.transcript_redacted = $true
          $Rejected.stores_transcript = $false
          $Rejected.speech_output_suppressed = $true
          $Rejected.dictation_fallback_enabled = $true
          $Rejected.message = 'Speech was recognized without the Francis wake phrase; no response was emitted.'
          Write-OverlayVoiceState -Root $script:LensOverlayWakeRoot -Payload $Rejected
          return
        }
        $script:LensOverlayWakeCount += 1
        if (-not [string]::IsNullOrWhiteSpace($UtteranceText)) {
          [void](Invoke-OverlayVoiceChatTurn -Root $script:LensOverlayWakeRoot -UtteranceText $UtteranceText -Provider $script:LensOverlayWakeVoiceProvider -Voice $script:LensOverlayWakeVoice -Rate $script:LensOverlayWakeRate -Volume $script:LensOverlayWakeVolume -RemoteVoiceId $script:LensOverlayWakeRemoteVoiceId -RemoteModelId $script:LensOverlayWakeRemoteModelId -RemoteOutputFormat $script:LensOverlayWakeRemoteOutputFormat -RemoteStability $script:LensOverlayWakeRemoteStability -RemoteSimilarityBoost $script:LensOverlayWakeRemoteSimilarityBoost -RemoteStyle $script:LensOverlayWakeRemoteStyle -RemoteSpeed $script:LensOverlayWakeRemoteSpeed -RemoteUseSpeakerBoost $script:LensOverlayWakeRemoteUseSpeakerBoost -WakePhraseText $script:LensOverlayWakePhrase -RecognitionConfidence ([double]$EventArgs.Result.Confidence) -RecognitionThreshold $script:LensOverlayWakeConfidenceThreshold -WakeAliasCount $script:LensOverlayWakeAliasCount -WakeCount $script:LensOverlayWakeCount)
          return
        }
        $Payload = Invoke-OverlayVoiceSpeech -Root $script:LensOverlayWakeRoot -Text $script:LensOverlayWakeResponse -Provider $script:LensOverlayWakeVoiceProvider -Voice $script:LensOverlayWakeVoice -Rate $script:LensOverlayWakeRate -Volume $script:LensOverlayWakeVolume -RemoteVoiceId $script:LensOverlayWakeRemoteVoiceId -RemoteModelId $script:LensOverlayWakeRemoteModelId -RemoteOutputFormat $script:LensOverlayWakeRemoteOutputFormat -RemoteStability $script:LensOverlayWakeRemoteStability -RemoteSimilarityBoost $script:LensOverlayWakeRemoteSimilarityBoost -RemoteStyle $script:LensOverlayWakeRemoteStyle -RemoteSpeed $script:LensOverlayWakeRemoteSpeed -RemoteUseSpeakerBoost $script:LensOverlayWakeRemoteUseSpeakerBoost -WakeListening $true -WakePhraseText $script:LensOverlayWakePhrase -SuccessStatus 'wake_acknowledged' -SuccessMessage 'Wake phrase detected and acknowledged through selected speech output.'
        $Payload.wake_phrase_detected = $true
        $Payload.wake_count = $script:LensOverlayWakeCount
        $Payload.recognition_confidence = [Math]::Round([double]$EventArgs.Result.Confidence, 3)
        $Payload.recognition_threshold = $script:LensOverlayWakeConfidenceThreshold
        $Payload.wake_alias_count = $script:LensOverlayWakeAliasCount
        $Payload.transcript_redacted = $true
        Write-OverlayVoiceState -Root $script:LensOverlayWakeRoot -Payload $Payload
      })
    $Recognizer.RecognizeAsync([System.Speech.Recognition.RecognizeMode]::Multiple)
    $Payload = New-OverlayVoiceProjection -SelectedVoiceName $SelectedWakeVoice -Provider $Provider -WakeListening $true -WakePhraseText $BoundedPhrase
    $Payload.status = 'listening'
    $Payload.ok = $true
    $Payload.response_text_length = $BoundedResponse.Length
    $Payload.response_text_redacted = $true
    $Payload.recognition_threshold = $ConfidenceThreshold
    $Payload.wake_alias_count = $WakeAliases.Count
    $Payload.continuous_voice_chat = [bool]$ContinuousVoiceChat
    $Payload.continuous_voice_chat_mode = if ($ContinuousVoiceChat) { 'enabled_no_wake_phrase_required' } else { 'disabled_wake_phrase_required' }
    $Payload.continuous_voice_chat_self_trigger_guard = 'suppress_all_except_francis_stop_while_owned_speech_process_active'
    $Payload.microphone_gate_while_speaking = 'francis_stop_only'
    $Payload.conversation_forwarding_while_speaking = $false
    $Payload.transcript_redacted = $true
    $Payload.message = if ($ContinuousVoiceChat) { 'Explicit wake-phrase listening and continuous voice chat are active for Francis Lens.' } else { 'Explicit wake-phrase listening is active for Francis Lens.' }
    Write-OverlayVoiceState -Root $Root -Payload $Payload
    return $Recognizer
  } catch {
    $Payload = New-OverlayVoiceProjection -SelectedVoiceName $SelectedWakeVoice -Provider $Provider -WakeListening $false -WakePhraseText ''
    $Payload.status = 'listen_failed'
    $Payload.ok = $false
    $Payload.error = [string]$_.Exception.Message
    $Payload.message = 'Wake-phrase listening failed before microphone capture became active.'
    Write-OverlayVoiceState -Root $Root -Payload $Payload
    return $null
  }
}

function Write-OverlayState {
  param(
    [string]$Root,
    [string]$Status,
    [bool]$OverlayWindowVisible,
    [bool]$AlwaysOnTop,
    [string]$Message = '',
    [object]$McpBodyState = $null,
    [object]$OrbVisual = $null,
    [object]$OverlayVoice = $null
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
  if ($null -eq $OrbVisual) {
    $OrbVisual = New-OrbVisualProjection -AutonomousMotion $false
  }
  if ($null -eq $OverlayVoice) {
    $OverlayVoice = New-OverlayRuntimeVoiceProjection
  }
  $VoiceInputReadiness = Get-OverlayVoiceInputReadiness -Voice $OverlayVoice
  $OverlayWindowVariable = Get-Variable -Name LensOverlayWindow -Scope Script -ErrorAction SilentlyContinue
  $MotionStateVariable = Get-Variable -Name LensOverlayMotionState -Scope Script -ErrorAction SilentlyContinue
  $OverlayWindowForPosition = if ($null -ne $OverlayWindowVariable) { $OverlayWindowVariable.Value } else { $null }
  $MotionStateForPosition = if ($null -ne $MotionStateVariable) { $MotionStateVariable.Value } else { $null }
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
    orb_visual = $OrbVisual
    voice = Get-OverlayVoiceReadback -Root $Root
    voice_turn = Get-OverlayVoiceTurnReadback -Root $Root
    overlay_voice = $OverlayVoice
    voice_input_readiness = $VoiceInputReadiness
    voice_input_ready = [bool]$VoiceInputReadiness.ready
    voice_input_status = $VoiceInputReadiness.status
    voice_input_blocker = $VoiceInputReadiness.blocker
    next_voice_input_step = $VoiceInputReadiness.next_operator_step
    voice_provider_readiness = New-OverlayVoiceProviderReadiness
    overlay_window_visible = $OverlayWindowVisible
    always_on_top = $AlwaysOnTop
    overlay_position = New-OverlayWindowPositionProjection -Window $OverlayWindowForPosition -MotionState $MotionStateForPosition -OverlayWindowVisible $OverlayWindowVisible
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
    Move-OverlayRuntimeStateFile -TempPath $TempPath -DestinationPath $StatusPath
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
  $StatusOrbVisual = if ($null -ne $Status -and $null -ne $Status.PSObject.Properties['orb_visual']) { $Status.PSObject.Properties['orb_visual'].Value } else { $null }
  $OrbVisual = if ($null -ne $StatusOrbVisual) {
    $StatusOrbVisual
  } else {
    New-OrbVisualProjection -AutonomousMotion $false
  }
  $StatusVoice = if ($null -ne $Status -and $null -ne $Status.PSObject.Properties['voice']) { $Status.PSObject.Properties['voice'].Value } else { $null }
  $VoiceReadback = Get-OverlayVoiceReadback -Root $Root
  $Voice = if (Test-Path -LiteralPath (Get-OverlayVoiceStatusPath -Root $Root) -PathType Leaf) {
    $VoiceReadback
  } elseif ($null -ne $StatusVoice) {
    $StatusVoice
  } else {
    $VoiceReadback
  }
  $StatusVoiceTurn = if ($null -ne $Status -and $null -ne $Status.PSObject.Properties['voice_turn']) { $Status.PSObject.Properties['voice_turn'].Value } else { $null }
  $VoiceTurn = Get-OverlayVoiceTurnReadback -Root $Root
  if ($null -eq $VoiceTurn -and $null -ne $StatusVoiceTurn) {
    $VoiceTurn = Get-OverlayVoiceTurnReadback -Root $Root -State $StatusVoiceTurn
  }
  $StatusOverlayVoice = if ($null -ne $Status -and $null -ne $Status.PSObject.Properties['overlay_voice']) { $Status.PSObject.Properties['overlay_voice'].Value } else { $null }
  $OverlayVoice = if ($null -ne $StatusOverlayVoice) { $StatusOverlayVoice } else { New-OverlayRuntimeVoiceProjection }
  $StatusVoiceInputReadiness = if ($null -ne $Status -and $null -ne $Status.PSObject.Properties['voice_input_readiness']) { $Status.PSObject.Properties['voice_input_readiness'].Value } else { $null }
  $VoiceInputReadiness = if ($null -ne $StatusVoiceInputReadiness) { $StatusVoiceInputReadiness } else { Get-OverlayVoiceInputReadiness -Voice $OverlayVoice }
  $StatusVoiceProviderReadiness = if ($null -ne $Status -and $null -ne $Status.PSObject.Properties['voice_provider_readiness']) { $Status.PSObject.Properties['voice_provider_readiness'].Value } else { $null }
  $VoiceProviderReadiness = if ($null -ne $StatusVoiceProviderReadiness) { $StatusVoiceProviderReadiness } else { New-OverlayVoiceProviderReadiness }
  $StatusOverlayPosition = if ($null -ne $Status -and $null -ne $Status.PSObject.Properties['overlay_position']) { $Status.PSObject.Properties['overlay_position'].Value } else { $null }
  $OverlayPosition = if ($null -ne $StatusOverlayPosition) { $StatusOverlayPosition } else { New-OverlayWindowPositionProjection -Window $null -MotionState $null -OverlayWindowVisible $false }
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
    orb_visual = $OrbVisual
    voice = $Voice
    voice_turn = $VoiceTurn
    overlay_voice = $OverlayVoice
    voice_input_readiness = $VoiceInputReadiness
    voice_input_ready = [bool]$VoiceInputReadiness.ready
    voice_input_status = $VoiceInputReadiness.status
    voice_input_blocker = $VoiceInputReadiness.blocker
    next_voice_input_step = $VoiceInputReadiness.next_operator_step
    voice_provider_readiness = $VoiceProviderReadiness
    overlay_position = $OverlayPosition
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
  $VoiceInputReady = [bool]$Readback.voice_input_ready
  $VoiceInputBlocker = [string]$Readback.voice_input_blocker
  $NextSmallestTruthfulGap = if ($Ready -and -not $VoiceInputReady -and -not [string]::IsNullOrWhiteSpace($VoiceInputBlocker)) {
    'lens_voice_default_microphone_signal'
  } elseif ($Ready -and -not $VoiceInputReady) {
    'lens_voice_input_signal_confirmation'
  } elseif ($Ready) {
    'overlay_authority_and_config'
  } else {
    'overlay_window_runtime'
  }
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
    orb_visual = $Readback.orb_visual
    voice = $Readback.voice
    voice_turn = $Readback.voice_turn
    overlay_voice = $Readback.overlay_voice
    voice_input_readiness = $Readback.voice_input_readiness
    voice_input_ready = $VoiceInputReady
    voice_input_status = $Readback.voice_input_status
    voice_input_blocker = $VoiceInputBlocker
    next_voice_input_step = $Readback.next_voice_input_step
    voice_provider_readiness = $Readback.voice_provider_readiness
    overlay_position = $Readback.overlay_position
    overlay_runtime = $Readback
    next_smallest_truthful_gap = $NextSmallestTruthfulGap
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
      voice_output_authority = ($ModeName -eq 'speak')
      microphone_capture_active = (Get-BoolProperty -Payload $Readback.overlay_voice -Name 'microphone_capture' -Default $false)
      microphone_capture_authority = $false
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
$script:LensOverlayVoiceUseLlmRequested = [bool]$EnableVoiceLlm
$AutonomousMotionEnabled = [bool]$EnableAutonomousMotion -and -not [bool]$DisableAutonomousMotion
$ManualOrbDragEnabled = [bool]$EnableManualOrbDrag

if ($Mode -eq 'Speak') {
  $PlaybackStatusPath = if ($PlaybackStateOnly) { Get-OverlayVoicePlaybackStatusPath -Root $DataRoot } else { '' }
  try {
    $ResolvedVoiceText = Read-OverlayVoiceTextInput -Root $DataRoot -Text $VoiceText -TextPath $VoiceTextPath
    $VoicePayload = Invoke-OverlayVoiceSpeech -Root $DataRoot -Text $ResolvedVoiceText -Provider $VoiceProvider -Voice $VoiceName -Rate $VoiceRate -Volume $VoiceVolume -RemoteVoiceId $ElevenLabsVoiceId -RemoteModelId $ElevenLabsModelId -RemoteOutputFormat $ElevenLabsOutputFormat -RemoteStability $ElevenLabsStability -RemoteSimilarityBoost $ElevenLabsSimilarityBoost -RemoteStyle $ElevenLabsStyle -RemoteSpeed $ElevenLabsSpeed -RemoteUseSpeakerBoost ([bool]$ElevenLabsUseSpeakerBoost) -StatusPath $PlaybackStatusPath
    $VoicePayload.playback_state_only = [bool]$PlaybackStateOnly
    if ($PlaybackStateOnly) {
      $VoicePayload.speech_process_pid = $PID
      $VoicePayload.speech_pid_path = 'data/runtime/lens-overlay/lens-overlay-speech.pid'
      $VoicePayload.playback_status_path = 'data/runtime/lens-overlay/voice-playback-status.json'
      $VoicePayload.speech_script_transport = if ([string]::IsNullOrWhiteSpace($VoiceTextPath)) { 'command_parameter' } else { 'transient_local_file' }
      $VoicePayload.speech_script_command_line_redacted = -not [string]::IsNullOrWhiteSpace($VoiceTextPath)
      $VoicePayload.speech_script_retention = if ([string]::IsNullOrWhiteSpace($VoiceTextPath)) { 'not_applicable' } else { 'transient_deleted_after_playback' }
      Write-OverlayVoiceState -Root $DataRoot -Payload $VoicePayload -StatusPath $PlaybackStatusPath
    }
    $VoicePayload | ConvertTo-Json -Depth 8
    if ([bool]$VoicePayload.ok) {
      exit 0
    }
    exit 2
  } finally {
    if ($PlaybackStateOnly) {
      Remove-OverlayVoiceTextFile -Root $DataRoot -TextPath $VoiceTextPath
    }
    if ($PlaybackStateOnly) {
      $SpeechPidPath = Get-OverlayVoiceSpeechPidPath -Root $DataRoot
      $RecordedPid = 0
      try {
        $RecordedPid = [int]((Get-Content -LiteralPath $SpeechPidPath -Raw -ErrorAction Stop).Trim())
      } catch {
        $RecordedPid = 0
      }
      if ($RecordedPid -eq $PID) {
        Remove-Item -LiteralPath $SpeechPidPath -Force -ErrorAction SilentlyContinue
      }
    }
  }
}

if ($Mode -eq 'SyntheticVoiceTurn') {
  $ResolvedVoiceText = Read-OverlayVoiceTextInput -Root $DataRoot -Text $VoiceText -TextPath $VoiceTextPath
  $VoicePayload = Invoke-OverlayVoiceChatTurn -Root $DataRoot -UtteranceText $ResolvedVoiceText -Provider $VoiceProvider -Voice $VoiceName -Rate $VoiceRate -Volume $VoiceVolume -RemoteVoiceId $ElevenLabsVoiceId -RemoteModelId $ElevenLabsModelId -RemoteOutputFormat $ElevenLabsOutputFormat -RemoteStability $ElevenLabsStability -RemoteSimilarityBoost $ElevenLabsSimilarityBoost -RemoteStyle $ElevenLabsStyle -RemoteSpeed $ElevenLabsSpeed -RemoteUseSpeakerBoost ([bool]$ElevenLabsUseSpeakerBoost) -WakePhraseText $WakePhrase -RecognitionConfidence 1.0 -RecognitionThreshold $WakeConfidenceThreshold -WakeAliasCount 0 -WakeCount 0 -SyntheticTranscript $true
  $VoicePayload | ConvertTo-Json -Depth 8
  if ([bool]$VoicePayload.ok) {
    exit 0
  }
  exit 2
}

if ($Mode -eq 'Run') {
  $RuntimeRoot = Join-Path $DataRoot 'runtime\lens-overlay'
  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  $Form = $null
  $Timer = $null
  $RefreshTimer = $null
  $CommandTimer = $null
  $MotionSubscription = $null
  $WakeRecognizer = $null
  $Failed = $false
  $script:LensOverlayOrbVisual = New-OrbVisualProjection -AutonomousMotion $AutonomousMotionEnabled -ManualDrag $ManualOrbDragEnabled
  $script:LensOverlayEnergyRoot = $null
  $script:LensOverlayMotionState = $null
  $script:LensOverlayRenderFrameClock = $null
  $script:LensOverlayLastPositionReceiptSeconds = -1.0
  try {
    if (-not $RunningOnWindows) {
      Write-OverlayState -Root $DataRoot -Status 'unsupported' -OverlayWindowVisible $false -AlwaysOnTop $false -Message 'Windows overlay requires a Windows user session.'
      exit 3
    }
    Add-Type -AssemblyName PresentationFramework
    Add-Type -AssemblyName PresentationCore
    Add-Type -AssemblyName WindowsBase
    Set-OverlayHardwareRenderMode
    $script:LensOverlayOrbVisual = New-OrbVisualProjection -AutonomousMotion $AutonomousMotionEnabled -ManualDrag $ManualOrbDragEnabled
    $Config = Get-OverlayConfig
    $OrbSize = 220
    $Screen = [System.Windows.SystemParameters]::WorkArea
    $Form = New-Object System.Windows.Window
    $Form.Title = $Config.overlay_name
    $Form.WindowStyle = [System.Windows.WindowStyle]::None
    $Form.ResizeMode = [System.Windows.ResizeMode]::NoResize
    $Form.AllowsTransparency = $true
    $Form.Background = [System.Windows.Media.Brushes]::Transparent
    $Form.ShowInTaskbar = $true
    $Form.TopMost = $true
    $Form.Width = $OrbSize
    $Form.Height = $OrbSize
    Set-OrbWindowDockPosition -Window $Form -WorkArea $Screen -Margin 48

    $EnergyRoot = New-OrbEnergySurface -Size $OrbSize
    $EnergyRoot.Cursor = if ($ManualOrbDragEnabled) { [System.Windows.Input.Cursors]::SizeAll } else { [System.Windows.Input.Cursors]::Arrow }
    if ($ManualOrbDragEnabled) {
      $EnergyRoot.Add_MouseLeftButtonDown({
        param($Sender, $EventArgs)

        try {
          $EventArgs.Handled = $true
          $script:LensOverlayWindow.DragMove()
          $script:LensOverlayOperatorPositionAnchor = 'operator_manual'
          Reset-OrbAutonomousMotionAnchor -Window $script:LensOverlayWindow -MotionState $script:LensOverlayMotionState
        } catch {
        }
      })
    }
    $Form.Content = $EnergyRoot

    $Label = New-Object System.Windows.Controls.Label
    $Label.Content = "Francis Lens`nMCP body-state: $($Config.mcp_status_route)`nLive readback: starting"
    $Label.Visibility = [System.Windows.Visibility]::Collapsed
    $script:LensOverlayLabel = $Label
    $script:LensOverlayWindow = $Form
    $script:LensOverlayEnergyRoot = $EnergyRoot
    $script:LensOverlayMotionState = New-OrbAutonomousMotionState -Window $Form -WorkArea $Screen
    $script:LensOverlayWorkArea = $Screen
    $script:LensOverlayOperatorPositionAnchor = ''
    $script:LensOverlayConfig = $Config
    $script:LensOverlayDataRoot = $DataRoot
    $script:LensOverlayEnableWakeListen = [bool]$EnableWakeListen
    $script:LensOverlayVoiceUseLlmRequested = [bool]$EnableVoiceLlm
    $script:LensOverlayWakeRecognizer = $null
    $script:LensOverlayRequestedVoiceProvider = $VoiceProvider
    $script:LensOverlayRequestedVoiceName = $VoiceName
    $script:LensOverlayRequestedElevenLabsVoiceId = $ElevenLabsVoiceId
    $script:LensOverlayRequestedElevenLabsModelId = $ElevenLabsModelId
    $script:LensOverlayRequestedElevenLabsOutputFormat = $ElevenLabsOutputFormat
    $script:LensOverlayRequestedElevenLabsStability = $ElevenLabsStability
    $script:LensOverlayRequestedElevenLabsSimilarityBoost = $ElevenLabsSimilarityBoost
    $script:LensOverlayRequestedElevenLabsStyle = $ElevenLabsStyle
    $script:LensOverlayRequestedElevenLabsSpeed = $ElevenLabsSpeed
    $script:LensOverlayRequestedElevenLabsUseSpeakerBoost = [bool]$ElevenLabsUseSpeakerBoost
    $script:LensOverlayRequestedWakePhrase = $WakePhrase
    $script:LensOverlayRequestedWakeResponse = $WakeResponse
    $script:LensOverlayRequestedWakeConfidenceThreshold = $WakeConfidenceThreshold
    $script:LensOverlayRequestedContinuousVoiceChat = [bool]$EnableContinuousVoiceChat
    $script:LensOverlayRequestedVoiceRate = $VoiceRate
    $script:LensOverlayRequestedVoiceVolume = $VoiceVolume
    $script:LensOverlayRuntimeVoice = New-OverlayRuntimeVoiceProjection -Provider $VoiceProvider -Voice $VoiceName -WakeListening ([bool]$EnableWakeListen) -WakePhraseText $WakePhrase -ConfidenceThreshold $WakeConfidenceThreshold
    $script:LensOverlayRuntimeVoice.voice_llm_enabled = [bool]$EnableVoiceLlm
    $script:LensOverlayRuntimeVoice.voice_llm_request_source = if ($EnableVoiceLlm) { 'EnableVoiceLlm' } else { 'FRANCIS_LENS_VOICE_USE_LLM' }
    $script:LensOverlayRuntimeVoice.continuous_voice_chat = [bool]$EnableContinuousVoiceChat
    $script:LensOverlayRuntimeVoice.continuous_voice_chat_mode = if ($EnableContinuousVoiceChat) { 'enabled_no_wake_phrase_required' } else { 'disabled_wake_phrase_required' }
    $script:LensOverlayRuntimeVoice.continuous_voice_chat_self_trigger_guard = 'suppress_all_except_francis_stop_while_owned_speech_process_active'
    $script:LensOverlayRuntimeVoice.microphone_gate_while_speaking = 'francis_stop_only'
    $script:LensOverlayRuntimeVoice.conversation_forwarding_while_speaking = $false
    $Form.Add_Loaded({
        if ($script:LensOverlayEnableWakeListen -and $null -eq $script:LensOverlayWakeRecognizer) {
          try {
            $script:LensOverlayWakeRecognizer = Start-OverlayWakeListener -Root $script:LensOverlayDataRoot -Phrase $script:LensOverlayRequestedWakePhrase -Response $script:LensOverlayRequestedWakeResponse -Provider $script:LensOverlayRequestedVoiceProvider -Voice $script:LensOverlayRequestedVoiceName -Rate $script:LensOverlayRequestedVoiceRate -Volume $script:LensOverlayRequestedVoiceVolume -RemoteVoiceId $script:LensOverlayRequestedElevenLabsVoiceId -RemoteModelId $script:LensOverlayRequestedElevenLabsModelId -RemoteOutputFormat $script:LensOverlayRequestedElevenLabsOutputFormat -RemoteStability $script:LensOverlayRequestedElevenLabsStability -RemoteSimilarityBoost $script:LensOverlayRequestedElevenLabsSimilarityBoost -RemoteStyle $script:LensOverlayRequestedElevenLabsStyle -RemoteSpeed $script:LensOverlayRequestedElevenLabsSpeed -RemoteUseSpeakerBoost $script:LensOverlayRequestedElevenLabsUseSpeakerBoost -ConfidenceThreshold $script:LensOverlayRequestedWakeConfidenceThreshold -ContinuousVoiceChat $script:LensOverlayRequestedContinuousVoiceChat
            $script:LensOverlayRuntimeVoice = if ($null -ne $script:LensOverlayWakeRecognizer) {
              New-OverlayRuntimeVoiceProjection -Provider $script:LensOverlayRequestedVoiceProvider -Voice $script:LensOverlayRequestedVoiceName -WakeListening $true -WakePhraseText $script:LensOverlayRequestedWakePhrase -Status 'listening' -ConfidenceThreshold $script:LensOverlayRequestedWakeConfidenceThreshold -WakeAliasCount $script:LensOverlayWakeAliasCount
            } else {
              New-OverlayRuntimeVoiceProjection -Provider $script:LensOverlayRequestedVoiceProvider -Voice $script:LensOverlayRequestedVoiceName -WakeListening $false -WakePhraseText '' -Status 'listen_failed' -ConfidenceThreshold $script:LensOverlayRequestedWakeConfidenceThreshold
            }
          } catch {
            $ErrorMessage = [string]$_.Exception.Message
            if ($ErrorMessage.Length -gt 300) {
              $ErrorMessage = $ErrorMessage.Substring(0, 300)
            }
            $script:LensOverlayWakeRecognizer = $null
            $script:LensOverlayRuntimeVoice = New-OverlayRuntimeVoiceProjection -Provider $script:LensOverlayRequestedVoiceProvider -Voice $script:LensOverlayRequestedVoiceName -WakeListening $false -WakePhraseText '' -Status 'listen_failed' -ConfidenceThreshold $script:LensOverlayRequestedWakeConfidenceThreshold
            $script:LensOverlayRuntimeVoice.error = 'wake_listener_start_failed'
            $script:LensOverlayRuntimeVoice.error_detail = $ErrorMessage
            $script:LensOverlayRuntimeVoice.message = 'Wake listener failed during overlay startup; the Orb remains visible without claiming microphone capture.'
            Write-OverlayVoiceState -Root $script:LensOverlayDataRoot -Payload $script:LensOverlayRuntimeVoice
          }
          $script:LensOverlayRuntimeVoice.voice_llm_enabled = [bool]$script:LensOverlayVoiceUseLlmRequested
          $script:LensOverlayRuntimeVoice.voice_llm_request_source = if ($script:LensOverlayVoiceUseLlmRequested) { 'EnableVoiceLlm' } else { 'FRANCIS_LENS_VOICE_USE_LLM' }
          $script:LensOverlayRuntimeVoice.continuous_voice_chat = [bool]$script:LensOverlayRequestedContinuousVoiceChat
          $script:LensOverlayRuntimeVoice.continuous_voice_chat_mode = if ($script:LensOverlayRequestedContinuousVoiceChat) { 'enabled_no_wake_phrase_required' } else { 'disabled_wake_phrase_required' }
          $script:LensOverlayRuntimeVoice.continuous_voice_chat_self_trigger_guard = 'suppress_all_except_francis_stop_while_owned_speech_process_active'
          $script:LensOverlayRuntimeVoice.microphone_gate_while_speaking = 'francis_stop_only'
          $script:LensOverlayRuntimeVoice.conversation_forwarding_while_speaking = $false
        }
        Update-OverlayMcpBodyStateLabelSafely -Label $script:LensOverlayLabel -Config $script:LensOverlayConfig -Root $script:LensOverlayDataRoot
      })
    $RefreshTimer = New-Object System.Windows.Threading.DispatcherTimer
    $RefreshTimer.Interval = [TimeSpan]::FromSeconds(5)
    $RefreshTimer.Add_Tick({
        Update-OverlayMcpBodyStateLabelSafely -Label $script:LensOverlayLabel -Config $script:LensOverlayConfig -Root $script:LensOverlayDataRoot
      })
    $RefreshTimer.Start()
    $CommandTimer = New-Object System.Windows.Threading.DispatcherTimer
    $CommandTimer.Interval = [TimeSpan]::FromMilliseconds(500)
    $CommandTimer.Add_Tick({
        [void](Invoke-OverlayQueuedOrbPositionCommand -Root $script:LensOverlayDataRoot)
      })
    $CommandTimer.Start()
    if ($AutonomousMotionEnabled) {
      $MotionSubscription = Start-OrbFrameSyncedMotion -Window $script:LensOverlayWindow -MotionState $script:LensOverlayMotionState
      $script:LensOverlayRenderFrameClock = $MotionSubscription['clock']
    }
    if ($RunSeconds -gt 0) {
      $Timer = New-Object System.Windows.Threading.DispatcherTimer
      $Timer.Interval = [TimeSpan]::FromSeconds($RunSeconds)
      $Timer.Add_Tick({
          $Timer.Stop()
          $script:LensOverlayWindow.Close()
        })
      $Timer.Start()
    }
    $Application = New-Object System.Windows.Application
    [void]$Application.Run($Form)
  } catch {
    $Failed = $true
    Write-OverlayState -Root $DataRoot -Status 'failed' -OverlayWindowVisible $false -AlwaysOnTop $false -Message ([string]$_.Exception.Message)
    exit 1
  } finally {
    if ($null -ne $RefreshTimer) {
      $RefreshTimer.Stop()
    }
    if ($null -ne $Timer) {
      $Timer.Stop()
    }
    if ($null -ne $CommandTimer) {
      $CommandTimer.Stop()
    }
    if ($null -ne $MotionSubscription) {
      Stop-OrbFrameSyncedMotion -Subscription $MotionSubscription
    }
    $WakeRecognizer = $script:LensOverlayWakeRecognizer
    if ($null -ne $WakeRecognizer) {
      try {
        $WakeRecognizer.RecognizeAsyncCancel()
      } catch {
      }
      try {
        $WakeRecognizer.Dispose()
      } catch {
      }
    }
    if ($null -ne $Form) {
      try {
        if ($Form.IsVisible) {
          $Form.Close()
        }
      } catch {
      }
    }
    if (-not $Failed) {
      Write-OverlayState -Root $DataRoot -Status 'overlay_stopped' -OverlayWindowVisible $false -AlwaysOnTop $false -Message 'Francis Lens overlay window stopped.' -OrbVisual $script:LensOverlayOrbVisual
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
  '-VoiceEnvironmentScope',
  $VoiceEnvironmentScope,
  '-ChatUiBaseUrl',
  $ChatUiBaseUrl,
  '-VoiceProvider',
  $VoiceProvider,
  '-VoiceName',
  $VoiceName,
  '-ElevenLabsVoiceId',
  $ElevenLabsVoiceId,
  '-ElevenLabsVoiceName',
  $ElevenLabsVoiceName,
  '-ElevenLabsModelId',
  $ElevenLabsModelId,
  '-ElevenLabsOutputFormat',
  $ElevenLabsOutputFormat,
  '-ElevenLabsStability',
  ([string]$ElevenLabsStability),
  '-ElevenLabsSimilarityBoost',
  ([string]$ElevenLabsSimilarityBoost),
  '-ElevenLabsStyle',
  ([string]$ElevenLabsStyle),
  '-ElevenLabsSpeed',
  ([string]$ElevenLabsSpeed),
  '-WakePhrase',
  $WakePhrase,
  '-WakeResponse',
  $WakeResponse,
  '-WakeConfidenceThreshold',
  ([string]$WakeConfidenceThreshold),
  '-VoiceRate',
  ([string]$VoiceRate),
  '-VoiceVolume',
  ([string]$VoiceVolume),
  '-RunSeconds',
  ([string]$RunSeconds)
)
if ($DisableAutonomousMotion) {
  $ArgumentList += '-DisableAutonomousMotion'
}
if ($EnableAutonomousMotion) {
  $ArgumentList += '-EnableAutonomousMotion'
}
if ($EnableManualOrbDrag) {
  $ArgumentList += '-EnableManualOrbDrag'
}
if ($EnableWakeListen) {
  $ArgumentList += '-EnableWakeListen'
}
if ($EnableContinuousVoiceChat) {
  $ArgumentList += '-EnableContinuousVoiceChat'
}
if ($EnableVoiceLlm) {
  $ArgumentList += '-EnableVoiceLlm'
}
if ($ElevenLabsUseSpeakerBoost) {
  $ArgumentList += '-ElevenLabsUseSpeakerBoost'
}
$ArgumentText = Join-OverlayProcessArguments -Arguments $ArgumentList
Start-Process -FilePath $PowerShell.Source -ArgumentList $ArgumentText -WindowStyle Hidden | Out-Null

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
