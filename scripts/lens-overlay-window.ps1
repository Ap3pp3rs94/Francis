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

  [ValidateRange(1, 30)]
  [int]$McpBodyStateTimeoutSeconds = 1,

  [ValidateRange(0, 3600)]
  [int]$McpRefreshIntervalSeconds = 0,

  [ValidateRange(0, 3600)]
  [int]$RunSeconds = 0,

  [ValidateRange(1, 60)]
  [int]$OrbMovePlaceTimeoutSeconds = 12
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

function Initialize-OverlayKeyboardInterop {
  if ('FrancisLensOverlayKeyboardNative' -as [type]) {
    return
  }

  Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class FrancisLensOverlayKeyboardNative
{
    [DllImport("user32.dll")]
    public static extern short GetAsyncKeyState(int vKey);
}
'@
}

function Test-OverlayVirtualKeyDown {
  param([int]$VirtualKey)

  try {
    Initialize-OverlayKeyboardInterop
    return ((([int][FrancisLensOverlayKeyboardNative]::GetAsyncKeyState($VirtualKey)) -band 0x8000) -ne 0)
  } catch {
    return $false
  }
}

function Test-OverlayContinuousVoiceChatPushToTalkActive {
  $ControlDown = (Test-OverlayVirtualKeyDown -VirtualKey 0x11) -or (Test-OverlayVirtualKeyDown -VirtualKey 0xA2) -or (Test-OverlayVirtualKeyDown -VirtualKey 0xA3)
  $VDown = Test-OverlayVirtualKeyDown -VirtualKey 0x56
  return ($ControlDown -and $VDown)
}

function Get-OverlayContinuousVoiceChatMode {
  param([bool]$ContinuousVoiceChat)

  if ($ContinuousVoiceChat) {
    return 'push_to_talk_ctrl_v_required'
  }
  return 'disabled_wake_phrase_required'
}

function Set-OverlayContinuousVoiceChatGateReadback {
  param(
    [object]$Payload,
    [bool]$ContinuousVoiceChat,
    [bool]$PushToTalkActive = $false
  )

  if ($null -eq $Payload) {
    return
  }
  $Payload.continuous_voice_chat = [bool]$ContinuousVoiceChat
  $Payload.continuous_voice_chat_mode = Get-OverlayContinuousVoiceChatMode -ContinuousVoiceChat $ContinuousVoiceChat
  $Payload.continuous_voice_chat_free_run = $false
  $Payload.continuous_voice_chat_push_to_talk_required = [bool]$ContinuousVoiceChat
  $Payload.continuous_voice_chat_push_to_talk_chord = 'Ctrl+V'
  $Payload.continuous_voice_chat_push_to_talk_active = [bool]$PushToTalkActive
  $Payload.continuous_voice_chat_blocks_unheld_dictation = [bool]$ContinuousVoiceChat
  $Payload.continuous_voice_chat_self_trigger_guard = 'suppress_all_except_francis_stop_while_owned_speech_process_active'
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

function Get-OrbHitBoxSize {
  $Variable = Get-Variable -Name LensOverlayOrbHitBoxSize -Scope Script -ErrorAction SilentlyContinue
  if ($null -ne $Variable) {
    return [double]$Variable.Value
  }
  return 72.0
}

function Test-OrbFullScreenOverlayPlane {
  param(
    [object]$Window,
    [object]$WorkArea
  )

  if ($null -eq $Window -or $null -eq $WorkArea) {
    return $false
  }
  return (
    [double]$Window.Width -ge ([double]$WorkArea.Width - 1.0) -and
    [double]$Window.Height -ge ([double]$WorkArea.Height - 1.0)
  )
}

function Get-OrbInWindowOffsetX {
  $Variable = Get-Variable -Name LensOverlayOrbInWindowOffsetX -Scope Script -ErrorAction SilentlyContinue
  if ($null -ne $Variable) {
    return [double]$Variable.Value
  }
  return 0.0
}

function Get-OrbInWindowOffsetY {
  $Variable = Get-Variable -Name LensOverlayOrbInWindowOffsetY -Scope Script -ErrorAction SilentlyContinue
  if ($null -ne $Variable) {
    return [double]$Variable.Value
  }
  return 0.0
}

function Set-OrbInWindowOffset {
  param(
    [double]$OffsetX,
    [double]$OffsetY
  )

  $script:LensOverlayOrbInWindowOffsetX = $OffsetX
  $script:LensOverlayOrbInWindowOffsetY = $OffsetY
  $Transform = $null
  $TransformVariable = Get-Variable -Name LensOverlayOrbWindowOffsetTransform -Scope Script -ErrorAction SilentlyContinue
  if ($null -ne $TransformVariable) {
    $Transform = $TransformVariable.Value
  }
  if ($null -eq $Transform -and $null -ne $script:LensOverlayEnergyRoot) {
    $Transform = New-Object System.Windows.Media.TranslateTransform
    $script:LensOverlayEnergyRoot.RenderTransform = $Transform
    $script:LensOverlayOrbWindowOffsetTransform = $Transform
  }
  if ($null -ne $Transform) {
    $Transform.X = $OffsetX
    $Transform.Y = $OffsetY
  }
}

function Get-OrbWindowPlacementForTarget {
  param(
    [object]$Window,
    [object]$WorkArea,
    [double]$X,
    [double]$Y
  )

  $MinimumLeft = [double]$WorkArea.Left
  $MinimumTop = [double]$WorkArea.Top
  $FullScreenOverlayPlane = Test-OrbFullScreenOverlayPlane -Window $Window -WorkArea $WorkArea
  $MaximumLeft = [Math]::Max($MinimumLeft, [double]$WorkArea.Right - [double]$Window.Width)
  $MaximumTop = [Math]::Max($MinimumTop, [double]$WorkArea.Bottom - [double]$Window.Height)
  $IdealLeft = if ($FullScreenOverlayPlane) { $MinimumLeft } else { $X - ([double]$Window.Width / 2.0) }
  $IdealTop = if ($FullScreenOverlayPlane) { $MinimumTop } else { $Y - ([double]$Window.Height / 2.0) }
  $TargetLeft = if ($FullScreenOverlayPlane) { $MinimumLeft } else { Clamp-OverlayDouble -Value $IdealLeft -Minimum $MinimumLeft -Maximum $MaximumLeft }
  $TargetTop = if ($FullScreenOverlayPlane) { $MinimumTop } else { Clamp-OverlayDouble -Value $IdealTop -Minimum $MinimumTop -Maximum $MaximumTop }
  $MaximumOffsetX = [double]$Window.Width / 2.0
  $MaximumOffsetY = [double]$Window.Height / 2.0
  $OffsetX = Clamp-OverlayDouble -Value ($X - ($TargetLeft + ([double]$Window.Width / 2.0))) -Minimum (-1.0 * $MaximumOffsetX) -Maximum $MaximumOffsetX
  $OffsetY = Clamp-OverlayDouble -Value ($Y - ($TargetTop + ([double]$Window.Height / 2.0))) -Minimum (-1.0 * $MaximumOffsetY) -Maximum $MaximumOffsetY
  $OrbCenterX = $TargetLeft + ([double]$Window.Width / 2.0) + $OffsetX
  $OrbCenterY = $TargetTop + ([double]$Window.Height / 2.0) + $OffsetY

  return [ordered]@{
    left = $TargetLeft
    top = $TargetTop
    offset_x = $OffsetX
    offset_y = $OffsetY
    orb_center_x = $OrbCenterX
    orb_center_y = $OrbCenterY
    target_x = $X
    target_y = $Y
    window_clamped = ([Math]::Abs($IdealLeft - $TargetLeft) -gt 0.001 -or [Math]::Abs($IdealTop - $TargetTop) -gt 0.001)
    in_window_offset_applied = ([Math]::Abs($OffsetX) -gt 0.001 -or [Math]::Abs($OffsetY) -gt 0.001)
    target_reachable_by_orb_center = ([Math]::Abs($OrbCenterX - $X) -le 0.75 -and [Math]::Abs($OrbCenterY - $Y) -le 0.75)
    overlay_window_stationary = $FullScreenOverlayPlane
    full_screen_overlay_plane = $FullScreenOverlayPlane
    click_hit_box_size = Get-OrbHitBoxSize
    click_hit_box_scope = 'orb_core_only'
    reach_mode = if ($FullScreenOverlayPlane) { 'full_screen_overlay_orb_offset' } else { 'window_plus_in_window_offset' }
  }
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

function Get-OverlayVirtualScreenBounds {
  return [pscustomobject]@{
    Left = [double][System.Windows.SystemParameters]::VirtualScreenLeft
    Top = [double][System.Windows.SystemParameters]::VirtualScreenTop
    Width = [double][System.Windows.SystemParameters]::VirtualScreenWidth
    Height = [double][System.Windows.SystemParameters]::VirtualScreenHeight
    Right = [double][System.Windows.SystemParameters]::VirtualScreenLeft + [double][System.Windows.SystemParameters]::VirtualScreenWidth
    Bottom = [double][System.Windows.SystemParameters]::VirtualScreenTop + [double][System.Windows.SystemParameters]::VirtualScreenHeight
    source = 'virtual_screen_including_taskbar'
  }
}

function Initialize-OverlayNativeWindowInterop {
  if ('FrancisLensOverlayNativeWindow' -as [type]) {
    return
  }

  Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class FrancisLensOverlayNativeWindow
{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, UInt32 uFlags);
}
'@
}

function Set-OverlayWindowTopMostPinned {
  param([object]$Window)

  if ($null -eq $Window) {
    return $false
  }
  try {
    $Window.TopMost = $false
    $Window.TopMost = $true
    Initialize-OverlayNativeWindowInterop
    $Helper = New-Object System.Windows.Interop.WindowInteropHelper -ArgumentList $Window
    if ($Helper.Handle -eq [IntPtr]::Zero) {
      return $false
    }
    $HwndTopMost = [IntPtr](-1)
    $Flags = [UInt32](0x0001 -bor 0x0002 -bor 0x0010 -bor 0x0040)
    $Pinned = [FrancisLensOverlayNativeWindow]::SetWindowPos($Helper.Handle, $HwndTopMost, 0, 0, 0, 0, $Flags)
    $script:LensOverlayTopMostPinApplied = [bool]$Pinned
    return [bool]$Pinned
  } catch {
    $script:LensOverlayTopMostPinApplied = $false
    return $false
  }
}

function New-OrbRingColorContract {
  return [ordered]@{
    kind = 'lens.overlay.orb_ring_color_contract'
    status = 'ready'
    source = 'docs/operations/ORB_VISUAL_LOCK.md'
    render_source = 'scripts/lens-overlay-window.ps1'
    visual_contract = 'chat_ui.orbGlyph.energy_reference'
    renderer = 'wpf_3d_animated_energy_orb'
    visual_lock_status = 'locked'
    state_driven_render_object = $true
    ring_motion_contract = 'parametric_orbital_motion'
    grants_execution_authority = $false
    grants_mutation_authority = $false
    ring_family = [ordered]@{
      material = 'silver_white_energy_ring'
      three_d_ring_color = '#E2EEFC'
      two_d_orbit_color = '#E0ECFA'
      three_d_ring_count = 38
      fine_orbit_count = 56
      bright_orbit_count = 12
    }
    glow_family = [ordered]@{
      outer_glow_primary = '#EBF5FF'
      outer_glow_secondary = '#B6CDEB'
      core_primary = '#FFFFFF'
      core_secondary = '#E6F0FC'
      core_shadow = '#8092A8'
      hot_center = '#FFFFFF'
    }
  }
}

function Add-OrbVisualRingColorContract {
  param([object]$OrbVisual)

  if ($null -eq $OrbVisual) {
    return New-OrbVisualProjection -AutonomousMotion $false
  }

  if ($OrbVisual -is [System.Collections.IDictionary]) {
    if (-not $OrbVisual.Contains('ring_color_contract') -or $null -eq $OrbVisual['ring_color_contract']) {
      $OrbVisual['ring_color_contract'] = New-OrbRingColorContract
    }
    return $OrbVisual
  }

  $RingContractProperty = $OrbVisual.PSObject.Properties['ring_color_contract']
  if ($null -eq $RingContractProperty -or $null -eq $RingContractProperty.Value) {
    $OrbVisual | Add-Member -NotePropertyName 'ring_color_contract' -NotePropertyValue (New-OrbRingColorContract) -Force
  }
  return $OrbVisual
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
    ring_color_contract = New-OrbRingColorContract
    autonomous_motion = $AutonomousMotion
    right_corner_locked = (-not $AutonomousMotion -and -not $ManualDrag)
    default_anchor = if ($AutonomousMotion) { 'bounded_work_area' } elseif ($ManualDrag) { 'operator_manual' } else { 'bottom_right' }
    motion_profile = if ($AutonomousMotion) { 'bounded_desktop_roam' } elseif ($ManualDrag) { 'manual_drag_only' } else { 'right_corner_locked' }
    motion_clock = if ($AutonomousMotion) { 'composition_target_rendering' } elseif ($ManualDrag) { 'manual_drag_only' } else { 'anchored_static' }
    render_profile = Get-OverlayWpfRenderProfile -FrameSyncedMotion $AutonomousMotion
    manual_drag_supported = $ManualDrag
    desktop_roam_supported = $AutonomousMotion
    desktop_roam_bounds = 'virtual_screen'
    in_window_orb_offset_supported = $true
    edge_reach_supported = $true
    overlay_coordinate_plane = 'virtual_screen_full_screen'
    overlay_includes_taskbar = $true
    overlay_window_is_coordinate_plane = $true
    click_hit_box_size = Get-OrbHitBoxSize
    click_hit_box_scope = 'orb_core_only'
    orb_visual_can_extend_beyond_click_box = $true
    reach_mode = 'full_screen_overlay_orb_offset'
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
  $FullScreenOverlayPlane = Test-OrbFullScreenOverlayPlane -Window $Window -WorkArea $WorkArea
  $RangeX = if ($FullScreenOverlayPlane) { [Math]::Max(0.0, [double]$WorkArea.Width / 2.0) } else { [Math]::Max(0.0, ($MaximumLeft - $MinimumLeft) / 2.0) }
  $RangeY = if ($FullScreenOverlayPlane) { [Math]::Max(0.0, [double]$WorkArea.Height / 2.0) } else { [Math]::Max(0.0, ($MaximumTop - $MinimumTop) / 2.0) }

  return [ordered]@{
    phase = 0.0
    anchor_left = if ($FullScreenOverlayPlane) { [double]$WorkArea.Left + ([double]$WorkArea.Width / 2.0) } else { $MinimumLeft + $RangeX }
    anchor_top = if ($FullScreenOverlayPlane) { [double]$WorkArea.Top + ([double]$WorkArea.Height / 2.0) } else { $MinimumTop + $RangeY }
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
    roam_right = if ($FullScreenOverlayPlane) { [double]$WorkArea.Right } else { $MaximumLeft }
    roam_bottom = if ($FullScreenOverlayPlane) { [double]$WorkArea.Bottom } else { $MaximumTop }
    desktop_roam_bounds = if ($WorkArea.PSObject.Properties['source'] -and [string]$WorkArea.source -eq 'virtual_screen_including_taskbar') { 'virtual_screen' } else { 'work_area' }
    full_screen_overlay_plane = $FullScreenOverlayPlane
    overlay_includes_taskbar = ($WorkArea.PSObject.Properties['source'] -and [string]$WorkArea.source -eq 'virtual_screen_including_taskbar')
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
  $FullScreenOverlayPlane = if ($MotionState.Contains('full_screen_overlay_plane')) { [bool]$MotionState['full_screen_overlay_plane'] } else { $false }
  $MotionState['anchor_left'] = if ($FullScreenOverlayPlane) { [double]$Window.Left + ([double]$Window.Width / 2.0) + (Get-OrbInWindowOffsetX) } else { [double]$Window.Left }
  $MotionState['anchor_top'] = if ($FullScreenOverlayPlane) { [double]$Window.Top + ([double]$Window.Height / 2.0) + (Get-OrbInWindowOffsetY) } else { [double]$Window.Top }
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

  $OperatorAnchorVariable = Get-Variable -Name LensOverlayOperatorPositionAnchor -Scope Script -ErrorAction SilentlyContinue
  $OperatorAnchor = if ($null -ne $OperatorAnchorVariable) { [string]$OperatorAnchorVariable.Value } else { '' }
  if (-not [string]::IsNullOrWhiteSpace($OperatorAnchor)) {
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
  $FullScreenOverlayPlane = if ($MotionState.Contains('full_screen_overlay_plane')) { [bool]$MotionState['full_screen_overlay_plane'] } else { $false }
  if ($FullScreenOverlayPlane) {
    $TargetCenterX = Clamp-OverlayDouble -Value ([double]$MotionState['anchor_left'] + $DriftX) -Minimum $MinimumLeft -Maximum ([double]$MotionState['work_right'])
    $TargetCenterY = Clamp-OverlayDouble -Value ([double]$MotionState['anchor_top'] + $DriftY) -Minimum $MinimumTop -Maximum ([double]$MotionState['work_bottom'])
    $TargetOffsetX = $TargetCenterX - ([double]$Window.Left + ([double]$Window.Width / 2.0))
    $TargetOffsetY = $TargetCenterY - ([double]$Window.Top + ([double]$Window.Height / 2.0))
    $Ease = [Math]::Min(1.0, [Math]::Max(0.18, $DeltaSeconds * 12.0))
    $OffsetX = Get-OrbInWindowOffsetX
    $OffsetY = Get-OrbInWindowOffsetY
    Set-OrbInWindowOffset -OffsetX ($OffsetX + (($TargetOffsetX - $OffsetX) * $Ease)) -OffsetY ($OffsetY + (($TargetOffsetY - $OffsetY) * $Ease))
    return
  }
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
  $OrbOffsetX = Get-OrbInWindowOffsetX
  $OrbOffsetY = Get-OrbInWindowOffsetY
  $OrbCenterX = if ($HasWindow) { [double]$Window.Left + ([double]$Window.Width / 2.0) + $OrbOffsetX } else { 0.0 }
  $OrbCenterY = if ($HasWindow) { [double]$Window.Top + ([double]$Window.Height / 2.0) + $OrbOffsetY } else { 0.0 }
  $FullScreenOverlayPlane = if ($HasWindow -and $HasMotionState -and $MotionState.Contains('full_screen_overlay_plane')) { [bool]$MotionState['full_screen_overlay_plane'] } else { $false }
  $OverlayIncludesTaskbar = if ($HasMotionState -and $MotionState.Contains('overlay_includes_taskbar')) { [bool]$MotionState['overlay_includes_taskbar'] } else { $false }
  $HitBoxSize = Get-OrbHitBoxSize
  $HitTestPassthroughVariable = Get-Variable -Name LensOverlayHitTestPassthroughEnabled -Scope Script -ErrorAction SilentlyContinue
  $HitTestPassthroughEnabled = if ($null -ne $HitTestPassthroughVariable) { [bool]$HitTestPassthroughVariable.Value } else { $false }
  $TopMostPinVariable = Get-Variable -Name LensOverlayTopMostPinApplied -Scope Script -ErrorAction SilentlyContinue
  $TopMostPinApplied = if ($null -ne $TopMostPinVariable) { [bool]$TopMostPinVariable.Value } else { $false }
  return [ordered]@{
    status = if ($OverlayWindowVisible -and $HasWindow) { 'visible_position_observed' } elseif ($HasWindow) { 'window_not_visible' } else { 'window_unavailable' }
    left = if ($HasWindow) { [double]$Window.Left } else { 0.0 }
    top = if ($HasWindow) { [double]$Window.Top } else { 0.0 }
    width = if ($HasWindow) { [double]$Window.Width } else { 0.0 }
    height = if ($HasWindow) { [double]$Window.Height } else { 0.0 }
    orb_center_x = $OrbCenterX
    orb_center_y = $OrbCenterY
    orb_in_window_offset_x = $OrbOffsetX
    orb_in_window_offset_y = $OrbOffsetY
    in_window_orb_offset_supported = $true
    in_window_orb_offset_active = ([Math]::Abs($OrbOffsetX) -gt 0.001 -or [Math]::Abs($OrbOffsetY) -gt 0.001)
    edge_reach_supported = $true
    full_screen_overlay_plane = $FullScreenOverlayPlane
    overlay_coordinate_plane = if ($OverlayIncludesTaskbar) { 'virtual_screen_full_screen' } elseif ($FullScreenOverlayPlane) { 'work_area_full_screen' } else { 'window_bounds' }
    overlay_includes_taskbar = $OverlayIncludesTaskbar
    overlay_window_is_coordinate_plane = $FullScreenOverlayPlane
    overlay_window_stationary_for_orb_motion = $FullScreenOverlayPlane
    topmost_pin_supported = $true
    topmost_pin_applied = $TopMostPinApplied
    click_hit_box_size = $HitBoxSize
    click_hit_box_left = $OrbCenterX - ($HitBoxSize / 2.0)
    click_hit_box_top = $OrbCenterY - ($HitBoxSize / 2.0)
    click_hit_box_scope = 'orb_core_only'
    hit_test_passthrough_outside_click_box_supported = $true
    hit_test_passthrough_outside_click_box_enabled = $HitTestPassthroughEnabled
    orb_visual_can_extend_beyond_click_box = $true
    reach_mode = if ($FullScreenOverlayPlane) { 'full_screen_overlay_orb_offset' } else { 'window_plus_in_window_offset' }
    right_corner_locked = $RightCornerLocked
    default_anchor = if ($OperatorPositionAnchored) { $OperatorPositionAnchor } elseif ($AutonomousMotion) { 'bounded_work_area' } elseif ($ManualDrag) { 'operator_manual' } else { 'bottom_right' }
    operator_position_anchor = $OperatorPositionAnchor
    voice_position_command_active = $OperatorPositionAnchor.StartsWith('voice_command_', [System.StringComparison]::OrdinalIgnoreCase)
    desktop_roam_supported = $AutonomousMotion
    desktop_roam_bounds = if ($OverlayIncludesTaskbar) { 'virtual_screen' } else { 'work_area' }
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
  param(
    [double]$Size = 220,
    [double]$HitBoxSize = 72
  )

  $Root = New-Object System.Windows.Controls.Grid
  $Root.Width = $Size
  $Root.Height = $Size
  $Root.Background = $null
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
  $HitBox = New-Object System.Windows.Controls.Border
  $HitBox.Width = $HitBoxSize
  $HitBox.Height = $HitBoxSize
  $HitBox.Background = [System.Windows.Media.Brushes]::Transparent
  $HitBox.HorizontalAlignment = [System.Windows.HorizontalAlignment]::Center
  $HitBox.VerticalAlignment = [System.Windows.VerticalAlignment]::Center
  $HitBox.Focusable = $true
  $HitBox.ClipToBounds = $false
  [System.Windows.Controls.Panel]::SetZIndex($HitBox, 50)
  [void]$Root.Children.Add($HitBox)
  $script:LensOverlayOrbHitBox = $HitBox
  return $Root
}

function Register-OverlayOrbHitTestHook {
  param(
    [object]$Window,
    [object]$HitBox
  )

  if ($null -eq $Window -or $null -eq $HitBox) {
    return
  }

  $AttachHook = {
  try {
    $Helper = New-Object System.Windows.Interop.WindowInteropHelper -ArgumentList $script:LensOverlayWindow
    $Source = [System.Windows.Interop.HwndSource]::FromHwnd($Helper.Handle)
      if ($null -eq $Source) {
        return
      }
      $Hook = [System.Windows.Interop.HwndSourceHook]{
        param(
          [IntPtr]$Hwnd,
          [int]$Message,
          [IntPtr]$WParam,
          [IntPtr]$LParam,
          [ref]$Handled
        )

        if ($Message -ne 0x0084) {
          return [IntPtr]::Zero
        }

        $ActiveHitBox = $script:LensOverlayOrbHitBox
        if ($null -eq $ActiveHitBox -or -not [bool]$ActiveHitBox.IsVisible) {
          $Handled.Value = $true
          return [IntPtr](-1)
        }

        try {
          $Raw = $LParam.ToInt64()
          $ScreenX = [int16]($Raw -band 0xffff)
          $ScreenY = [int16](($Raw -shr 16) -band 0xffff)
          $TopLeft = $ActiveHitBox.PointToScreen((New-Object System.Windows.Point(0, 0)))
          $Width = if ([double]$ActiveHitBox.ActualWidth -gt 0.0) { [double]$ActiveHitBox.ActualWidth } else { Get-OrbHitBoxSize }
          $Height = if ([double]$ActiveHitBox.ActualHeight -gt 0.0) { [double]$ActiveHitBox.ActualHeight } else { Get-OrbHitBoxSize }
          if ($ScreenX -ge [double]$TopLeft.X -and $ScreenX -le ([double]$TopLeft.X + $Width) -and $ScreenY -ge [double]$TopLeft.Y -and $ScreenY -le ([double]$TopLeft.Y + $Height)) {
            return [IntPtr]::Zero
          }
        } catch {
        }

        $Handled.Value = $true
        return [IntPtr](-1)
      }
      $Source.AddHook($Hook)
      $script:LensOverlayHwndSource = $Source
      $script:LensOverlayHitTestHook = $Hook
      $script:LensOverlayHitTestPassthroughEnabled = $true
      [void](Set-OverlayWindowTopMostPinned -Window $script:LensOverlayWindow)
    } catch {
      $script:LensOverlayHitTestPassthroughEnabled = $false
    }
  }

  $script:LensOverlayAttachHitTestHook = $AttachHook
  $Window.Add_SourceInitialized({
      if ($null -ne $script:LensOverlayAttachHitTestHook) {
        [void]$script:LensOverlayAttachHitTestHook.Invoke()
      }
    })
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

function New-DeferredMcpBodyStateForOverlay {
  param([object]$Config)

  $BodyState = New-McpBodyStateProjection -McpStatusRoute $Config.mcp_status_route -OrbMcpStatusRoute $Config.orb_mcp_status_route
  Set-McpBodyStateValue -Projection $BodyState -Name 'live_status' -Value 'refresh_deferred_for_animation'
  Set-McpBodyStateValue -Projection $BodyState -Name 'body_status' -Value 'deferred'
  Set-McpBodyStateValue -Projection $BodyState -Name 'embodied_posture' -Value 'unknown'
  Set-McpBodyStateValue -Projection $BodyState -Name 'semantic_state' -Value 'unknown'
  Set-McpBodyStateValue -Projection $BodyState -Name 'semantic_source' -Value 'refresh_deferred'
  Set-McpBodyStateValue -Projection $BodyState -Name 'tool_count' -Value 0
  Set-McpBodyStateValue -Projection $BodyState -Name 'expected_tool_count' -Value 0
  Set-McpBodyStateValue -Projection $BodyState -Name 'missing_tools_count' -Value 0
  Set-McpBodyStateValue -Projection $BodyState -Name 'blockers_count' -Value 0
  Set-McpBodyStateValue -Projection $BodyState -Name 'resident' -Value $false
  Set-McpBodyStateValue -Projection $BodyState -Name 'input_status' -Value 'unknown'
  Set-McpBodyStateValue -Projection $BodyState -Name 'takeover_status' -Value 'unknown'
  Set-McpBodyStateValue -Projection $BodyState -Name 'message' -Value 'Overlay runtime is visible; live MCP body-state refresh is deferred so Orb animation stays smooth.'
  return $BodyState
}

function Publish-DeferredOverlayMcpBodyState {
  param(
    [object]$Label,
    [object]$Config,
    [string]$Root
  )

  $BodyState = New-DeferredMcpBodyStateForOverlay -Config $Config
  Set-OverlayLabelText -Label $Label -Text (Format-McpBodyStateLabel -BodyState $BodyState)
  if ($null -ne $script:LensOverlayEnergyRoot) {
    $script:LensOverlayEnergyRoot.Opacity = 0.72
  }
  Write-OverlayState -Root $Root -Status 'overlay_running' -OverlayWindowVisible $true -AlwaysOnTop $true -Message 'Francis Lens overlay window is running; live MCP body-state refresh is deferred for Orb animation smoothness.' -McpBodyState $BodyState -OrbVisual $script:LensOverlayOrbVisual -OverlayVoice $script:LensOverlayRuntimeVoice
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

function Get-OverlayRuntimePidFromFile {
  param([string]$Root)

  $PidPath = Join-Path (Join-Path $Root 'runtime\lens-overlay') 'lens-overlay.pid'
  if (-not (Test-Path -LiteralPath $PidPath -PathType Leaf)) {
    return 0
  }
  try {
    return [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
  } catch {
    return 0
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
    voice_input = if ($WakeListening) { 'explicit_wake_phrase_or_direct_francis_address' } else { 'disabled_requires_explicit_microphone_authority' }
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
  Set-OverlayContinuousVoiceChatGateReadback -Payload $Payload -ContinuousVoiceChat $false -PushToTalkActive $false
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
      $NextOperatorStep = 'say_francis_or_hey_francis_with_a_bounded_request'
      $Message = 'Wake listener has observed microphone signal; direct Francis address and the configured wake phrase are both accepted for bounded voice turns.'
    } else {
      $Status = 'waiting_for_audio_signal'
      $Blocker = ''
      $NextOperatorStep = 'say_francis_or_hey_francis_to_confirm_default_microphone_signal'
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
  $VoiceTurn = Read-OverlayVoiceTurnState -Root $Root
  $ExternalVoiceSpeechActive = $false
  $ExternalVoiceSpeechAgeSeconds = -1
  $ExternalVoiceTurnId = ''
  if ($null -ne $VoiceTurn) {
    $SpeechOutputOwner = Get-StringProperty -Payload $VoiceTurn -Name 'speech_output_owner' -Default ''
    $ClientSpeaksTopLevelReply = Get-BoolProperty -Payload $VoiceTurn -Name 'client_speaks_top_level_reply' -Default $false
    $ExternalVoiceTurnId = Get-StringProperty -Payload $VoiceTurn -Name 'turn_id' -Default ''
    $UpdatedAt = Get-StringProperty -Payload $VoiceTurn -Name 'updated_at' -Default ''
    if ($SpeechOutputOwner -eq 'chatgpt_voice_client' -and $ClientSpeaksTopLevelReply -and -not [string]::IsNullOrWhiteSpace($UpdatedAt)) {
      try {
        $UpdatedAtOffset = [DateTimeOffset]::Parse($UpdatedAt)
        $ExternalVoiceSpeechAgeSeconds = [int][Math]::Floor(([DateTimeOffset]::UtcNow - $UpdatedAtOffset).TotalSeconds)
        $ExternalVoiceSpeechActive = ($ExternalVoiceSpeechAgeSeconds -ge -1 -and $ExternalVoiceSpeechAgeSeconds -le [int]$CooldownSeconds)
      } catch {
        $ExternalVoiceSpeechActive = $false
        $ExternalVoiceSpeechAgeSeconds = -1
      }
    }
  }
  $GuardActive = ([bool]$OwnedSpeechActive -or [bool]$OwnedSpeechRecentlyCompleted -or [bool]$ExternalVoiceSpeechActive)
  return [ordered]@{
    owned_speech_active = [bool]$OwnedSpeechActive
    owned_speech_recently_completed = [bool]$OwnedSpeechRecentlyCompleted
    external_voice_speech_active = [bool]$ExternalVoiceSpeechActive
    external_voice_speech_age_seconds = [int]$ExternalVoiceSpeechAgeSeconds
    external_voice_turn_id = $ExternalVoiceTurnId
    external_voice_speech_owner = 'chatgpt_voice_client'
    owned_speech_guard_active = [bool]$GuardActive
    owned_speech_process_id = [int]$SpeechProcessId
    self_trigger_guard_window_seconds = [int]$CooldownSeconds
    microphone_gate_while_speaking = 'francis_stop_only'
    conversation_forwarding_while_speaking = $false
    single_voice_owner_guard = 'owned_or_external_client_voice'
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

function Get-OverlayOrbVirtualPointerStatePath {
  return Join-Path (Join-Path $RepoRoot '.francis\orb_operator') 'virtual_pointer_state.json'
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
  $TargetVertical = Get-StringProperty -Payload $Request -Name 'target_vertical' -Default ''
  $TargetCorner = Get-StringProperty -Payload $Request -Name 'target_corner' -Default ''
  $TargetAnchor = Get-StringProperty -Payload $Request -Name 'target_anchor' -Default ''
  $ReferenceType = Get-StringProperty -Payload $Request -Name 'reference_type' -Default ''
  $CommandSource = Get-StringProperty -Payload $Request -Name 'command_source' -Default (Get-StringProperty -Payload $Result -Name 'overlay_position_command_source' -Default '')
  $CommandId = Get-StringProperty -Payload $Request -Name 'command_id' -Default $CommandName
  $AuthorityScope = Get-StringProperty -Payload $Request -Name 'authority_scope' -Default (Get-StringProperty -Payload $Result -Name 'mutation_authority_scope' -Default 'runtime_overlay_position_only')
  $CaptureMode = Get-StringProperty -Payload $Request -Name 'capture_mode' -Default ''
  $Handler = Get-StringProperty -Payload $Request -Name 'handler' -Default ''
  $TriggerId = Get-StringProperty -Payload $Request -Name 'trigger_id' -Default ''
  $GlobalHotkey = Get-StringProperty -Payload $Request -Name 'global_hotkey' -Default ''
  $OverlayPositionAnchor = Get-StringProperty -Payload $Result -Name 'overlay_position_anchor' -Default $TargetAnchor
  $Receipt = [ordered]@{
    kind = 'lens.overlay.orb_position_command.receipt'
    receipt_kind = Get-StringProperty -Payload $Request -Name 'receipt_kind' -Default 'overlay_position'
    status = Get-StringProperty -Payload $Result -Name 'status' -Default 'orb_position_command_result_unknown'
    ok = Get-BoolProperty -Payload $Result -Name 'ok' -Default $false
    request_id = $RequestId
    command = $CommandName
    command_id = $CommandId
    reference_type = $ReferenceType
    command_source = $CommandSource
    target_side = $TargetSide
    target_vertical = $TargetVertical
    target_corner = $TargetCorner
    target_anchor = $TargetAnchor
    overlay_position_anchor = $OverlayPositionAnchor
    applied = Get-BoolProperty -Payload $Result -Name 'runtime_overlay_position_changed' -Default $false
    overlay_left = Get-StringProperty -Payload $Result -Name 'overlay_left' -Default ''
    overlay_top = Get-StringProperty -Payload $Result -Name 'overlay_top' -Default ''
    target_x = Get-StringProperty -Payload $Result -Name 'target_x' -Default ''
    target_y = Get-StringProperty -Payload $Result -Name 'target_y' -Default ''
    source = Get-StringProperty -Payload $Request -Name 'source' -Default ''
    actor = Get-StringProperty -Payload $Request -Name 'actor' -Default ''
    client_origin = Get-StringProperty -Payload $Request -Name 'client_origin' -Default ''
    trigger_id = $TriggerId
    trigger_kind = Get-StringProperty -Payload $Request -Name 'trigger_kind' -Default ''
    global_hotkey = $GlobalHotkey
    trigger_carries_authority = Get-BoolProperty -Payload $Request -Name 'trigger_carries_authority' -Default $false
    capture_mode = $CaptureMode
    handler = $Handler
    microphone_recognition_claimed = Get-BoolProperty -Payload $Result -Name 'microphone_recognition_claimed' -Default (Get-BoolProperty -Payload $Request -Name 'microphone_recognition_claimed' -Default $false)
    microphone_speech = Get-BoolProperty -Payload $Result -Name 'microphone_speech' -Default (Get-BoolProperty -Payload $Request -Name 'microphone_speech' -Default $false)
    wake_phrase_detected = Get-BoolProperty -Payload $Result -Name 'wake_phrase_detected' -Default (Get-BoolProperty -Payload $Request -Name 'wake_phrase_detected' -Default $false)
    transcript_source = Get-StringProperty -Payload $Result -Name 'transcript_source' -Default (Get-StringProperty -Payload $Request -Name 'transcript_source' -Default '')
    transcript_hash = Get-StringProperty -Payload $Request -Name 'transcript_hash' -Default ''
    transcript_redacted = $true
    stores_transcript = $false
    request_path = 'data/runtime/lens-overlay/orb-position-command-request.json'
    receipt_path = 'data/runtime/lens-overlay/orb-position-commands'
    overlay_runtime_owns_execution = $true
    bounded_overlay_position_mutation = $true
    authority_scope = $AuthorityScope
    mutation_authority_scope = 'runtime_overlay_position_only'
    chat_route_writes_conversation_ledger = $false
    conversation_forwarding_suppressed = $true
    controls_user_os_cursor = $false
    user_mouse_taken = $false
    physical_input_performed = $false
    desktop_effect_performed = $false
    grants_execution_authority = $false
    grants_mutation_authority = $false
    updated_at = [DateTimeOffset]::UtcNow.ToString('o')
  }
  Write-OverlayVoiceTurnFile -Path (Get-OverlayOrbPositionCommandReceiptPath -Root $Root -RequestId $RequestId) -Payload $Receipt
}

function Write-OverlayOrbVirtualPointerReceipt {
  param(
    [string]$Root,
    [string]$RequestId,
    [object]$Pointer,
    [object]$Result
  )

  $LastAction = if ($null -ne $Pointer -and $null -ne $Pointer.PSObject.Properties['last_action']) { $Pointer.last_action } else { $null }
  $PublicAction = if ($null -ne $LastAction -and $null -ne $LastAction.PSObject.Properties['public_action']) { $LastAction.public_action } else { $null }
  $Gesture = if ($null -ne $LastAction -and $null -ne $LastAction.PSObject.Properties['gesture']) { $LastAction.gesture } else { $null }
  $DragStart = if ($null -ne $Gesture -and $null -ne $Gesture.PSObject.Properties['start']) { $Gesture.start } else { $null }
  $DragEnd = if ($null -ne $Gesture -and $null -ne $Gesture.PSObject.Properties['end']) { $Gesture.end } else { $null }
  $Receipt = [ordered]@{
    kind = 'lens.overlay.orb_virtual_pointer.receipt'
    status = Get-StringProperty -Payload $Result -Name 'status' -Default 'orb_virtual_pointer_result_unknown'
    ok = Get-BoolProperty -Payload $Result -Name 'ok' -Default $false
    request_id = $RequestId
    pointer_id = Get-StringProperty -Payload $Pointer -Name 'pointer_id' -Default 'francis.orb.primary_virtual_pointer'
    pointer_mode = Get-StringProperty -Payload $Pointer -Name 'mode' -Default 'orb_pointer'
    pointer_updated_at = Get-StringProperty -Payload $Pointer -Name 'updated_at' -Default ''
    virtual_pointer_x = Get-StringProperty -Payload $Pointer -Name 'x' -Default ''
    virtual_pointer_y = Get-StringProperty -Payload $Pointer -Name 'y' -Default ''
    last_input_kind = Get-StringProperty -Payload $LastAction -Name 'input_kind' -Default ''
    last_action_status = Get-StringProperty -Payload $LastAction -Name 'status' -Default ''
    last_public_action_kind = Get-StringProperty -Payload $PublicAction -Name 'kind' -Default ''
    last_action_button = Get-StringProperty -Payload $PublicAction -Name 'button' -Default ''
    last_action_clicks = Get-StringProperty -Payload $PublicAction -Name 'clicks' -Default ''
    gesture_kind = Get-StringProperty -Payload $Gesture -Name 'kind' -Default ''
    drag_start_x = Get-StringProperty -Payload $DragStart -Name 'x' -Default ''
    drag_start_y = Get-StringProperty -Payload $DragStart -Name 'y' -Default ''
    drag_target_x = Get-StringProperty -Payload $DragEnd -Name 'x' -Default ''
    drag_target_y = Get-StringProperty -Payload $DragEnd -Name 'y' -Default ''
    applied = Get-BoolProperty -Payload $Result -Name 'runtime_overlay_position_changed' -Default $false
    overlay_left = Get-StringProperty -Payload $Result -Name 'overlay_left' -Default ''
    overlay_top = Get-StringProperty -Payload $Result -Name 'overlay_top' -Default ''
    source = 'francis.orb_operator.virtual_pointer_state'
    actor = Get-StringProperty -Payload $LastAction -Name 'actor' -Default 'francis.orb_operator'
    client_origin = 'francis_orb_virtual_pointer'
    request_path = '.francis/orb_operator/virtual_pointer_state.json'
    receipt_path = 'data/runtime/lens-overlay/orb-position-commands'
    overlay_runtime_owns_execution = $true
    bounded_overlay_position_mutation = $true
    mutation_authority_scope = 'runtime_overlay_position_only'
    controls_user_os_cursor = $false
    user_mouse_taken = $false
    physical_input_performed = $false
    desktop_effect_performed = $false
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
  $CommandId = Get-StringProperty -Payload $Request -Name 'command_id' -Default $CommandName
  $CaptureMode = Get-StringProperty -Payload $Request -Name 'capture_mode' -Default ''
  if ($CommandId -eq 'orb.move' -and $CaptureMode -eq 'one_shot_click') {
    Remove-OverlayOrbPositionCommandRequest -Root $Root -Path $RequestPath
    $TimeoutSeconds = 12
    $TimeoutVariable = Get-Variable -Name LensOverlayOrbMovePlaceTimeoutSeconds -Scope Script -ErrorAction SilentlyContinue
    if ($null -ne $TimeoutVariable) {
      $TimeoutSeconds = [int]$TimeoutVariable.Value
    }
    return Invoke-OverlayOrbMovePlaceMode -Root $Root -Request $Request -TimeoutSeconds $TimeoutSeconds
  }
  $TargetSide = Get-StringProperty -Payload $Request -Name 'target_side' -Default ''
  $TargetVertical = Get-StringProperty -Payload $Request -Name 'target_vertical' -Default ''
  $TargetCorner = Get-StringProperty -Payload $Request -Name 'target_corner' -Default ''
  $TargetAnchor = Get-StringProperty -Payload $Request -Name 'target_anchor' -Default ''
  $ReferenceType = Get-StringProperty -Payload $Request -Name 'reference_type' -Default ''
  $Command = [ordered]@{
    recognized = $true
    intent = 'move_orb'
    command = $CommandName
    command_id = $CommandId
    target_side = $TargetSide
    target_vertical = $TargetVertical
    target_corner = $TargetCorner
    target_anchor = $TargetAnchor
    reference_type = $ReferenceType
    receipt_kind = Get-StringProperty -Payload $Request -Name 'receipt_kind' -Default 'overlay_position'
    authority_scope = Get-StringProperty -Payload $Request -Name 'authority_scope' -Default 'runtime_overlay_position_only'
    source = Get-StringProperty -Payload $Request -Name 'source' -Default ''
    actor = Get-StringProperty -Payload $Request -Name 'actor' -Default ''
    client_origin = Get-StringProperty -Payload $Request -Name 'client_origin' -Default ''
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

function Get-OverlayContinuousVoiceTurnGuard {
  param(
    [string]$Root,
    [ValidateRange(1, 600)]
    [int]$MaxPendingSeconds = 90
  )

  $State = Read-OverlayVoiceTurnState -Root $Root
  if ($null -eq $State) {
    return [ordered]@{
      allowed = $true
      blocker = ''
      active_turn_id = ''
      active_turn_status = ''
      active_turn_age_seconds = 0
      max_pending_seconds = $MaxPendingSeconds
    }
  }

  $Status = Get-StringProperty -Payload $State -Name 'status' -Default ''
  $TurnId = Get-StringProperty -Payload $State -Name 'active_turn_id' -Default ''
  $UpdatedAt = Get-StringProperty -Payload $State -Name 'updated_at' -Default ''
  $AgeSeconds = 0
  if (-not [string]::IsNullOrWhiteSpace($UpdatedAt)) {
    try {
      $UpdatedAtOffset = [DateTimeOffset]::Parse($UpdatedAt)
      $AgeSeconds = [int][Math]::Max(0, [Math]::Floor(([DateTimeOffset]::UtcNow - $UpdatedAtOffset).TotalSeconds))
    } catch {
      $AgeSeconds = 0
    }
  }

  $PendingBlocksContinuous = (-not [string]::IsNullOrWhiteSpace($TurnId) -and $Status -in @('chat_pending', 'speaking') -and $AgeSeconds -le $MaxPendingSeconds)
  return [ordered]@{
    allowed = (-not $PendingBlocksContinuous)
    blocker = if ($PendingBlocksContinuous) { 'voice_chat_turn_pending' } else { '' }
    active_turn_id = $TurnId
    active_turn_status = $Status
    active_turn_age_seconds = $AgeSeconds
    max_pending_seconds = $MaxPendingSeconds
  }
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
  $ContinuousVoiceChatPushToTalkActive = if ($ContinuousVoiceChat) { Test-OverlayContinuousVoiceChatPushToTalkActive } else { $false }
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

function Get-OverlayScriptBool {
  param(
    [string]$Name,
    [bool]$Default = $false
  )

  $Variable = Get-Variable -Name $Name -Scope Script -ErrorAction SilentlyContinue
  if ($null -eq $Variable) {
    return $Default
  }
  return [bool]$Variable.Value
}

function Get-OverlayScriptValue {
  param(
    [string]$Name,
    [object]$Default = $null
  )

  $Variable = Get-Variable -Name $Name -Scope Script -ErrorAction SilentlyContinue
  if ($null -eq $Variable) {
    return $Default
  }
  return $Variable.Value
}

function Get-OverlayOrbControlState {
  $Variable = Get-Variable -Name LensOverlayOrbControlState -Scope Script -ErrorAction SilentlyContinue
  if ($null -eq $Variable -or $null -eq $Variable.Value) {
    $script:LensOverlayOrbControlState = [ordered]@{
      right_click_panel_supported = $true
      panel_visible = $false
      panel_width = 292
      panel_max_height = 268
      chat_input_max_length = 600
      conversation_surface = 'lens.overlay.orb.right_click_chat'
      chat_bridge_route = '/chat/send'
      chat_bridge_actor = 'lens.overlay.voice'
      voice_reply_requested = $true
      latest_status = 'not_opened'
      latest_action = ''
      latest_feature = ''
      last_receipt_path = ''
      grants_execution_authority = $false
      grants_mutation_authority = $false
    }
  }
  return $script:LensOverlayOrbControlState
}

function Get-OverlayOrbControlFeatures {
  $WakeRecognizer = Get-OverlayScriptValue -Name LensOverlayWakeRecognizer
  $MotionSubscription = Get-OverlayScriptValue -Name LensOverlayMotionSubscription
  $ContinuousVoiceChat = Get-OverlayScriptBool -Name LensOverlayRequestedContinuousVoiceChat
  return [ordered]@{
    wake_listen = ($null -ne $WakeRecognizer)
    continuous_voice_chat = $ContinuousVoiceChat
    continuous_voice_chat_mode = Get-OverlayContinuousVoiceChatMode -ContinuousVoiceChat $ContinuousVoiceChat
    continuous_voice_chat_push_to_talk_chord = 'Ctrl+V'
    continuous_voice_chat_free_run = $false
    voice_llm = Get-OverlayVoiceUseLlm
    ambient_motion = ($null -ne $MotionSubscription)
  }
}

function Get-OverlayOrbControlReadback {
  $State = Get-OverlayOrbControlState
  $State['features'] = Get-OverlayOrbControlFeatures
  $State['voice_reply_requested'] = $true
  $State['chat_bridge_route'] = '/chat/send'
  $State['chat_bridge_actor'] = 'lens.overlay.voice'
  $State['conversation_surface'] = 'lens.overlay.orb.right_click_chat'
  $State['grants_execution_authority'] = $false
  $State['grants_mutation_authority'] = $false
  return $State
}

function Get-OverlayOrbControlReceiptRoot {
  param([string]$Root)

  return Join-Path (Join-Path $Root 'runtime\lens-overlay') 'orb-controls'
}

function Write-OverlayOrbControlReceipt {
  param(
    [string]$Root,
    [string]$Action,
    [object]$Details = $null
  )

  if ([string]::IsNullOrWhiteSpace($Root)) {
    return [ordered]@{}
  }

  $ReceiptRoot = Get-OverlayOrbControlReceiptRoot -Root $Root
  New-Item -ItemType Directory -Force -Path $ReceiptRoot | Out-Null
  $ReceiptId = 'orb-control-{0}' -f ([Guid]::NewGuid().ToString('N'))
  $ReceiptPath = Join-Path $ReceiptRoot ('{0}.json' -f $ReceiptId)
  $Receipt = [ordered]@{
    kind = 'lens.overlay.orb_control.receipt'
    receipt_id = $ReceiptId
    action = $Action
    control_surface = 'lens.overlay.orb.right_click_panel'
    conversation_surface = 'lens.overlay.orb.right_click_chat'
    chat_bridge_route = '/chat/send'
    chat_bridge_actor = 'lens.overlay.voice'
    voice_reply_requested = $true
    bounded_overlay_control = $true
    overlay_runtime_owns_execution = $true
    overlay_stores_transcript = $false
    transcript_redacted = $true
    grants_execution_authority = $false
    grants_mutation_authority = $false
    controls_user_os_cursor = $false
    user_mouse_taken = $false
    physical_input_performed = $false
    desktop_effect_performed = $false
    updated_at = [DateTimeOffset]::UtcNow.ToString('o')
  }

  if ($null -ne $Details) {
    if ($Details -is [System.Collections.IDictionary]) {
      foreach ($Key in $Details.Keys) {
        $Name = [string]$Key
        if (-not $Receipt.Contains($Name)) {
          $Receipt[$Name] = $Details[$Key]
        }
      }
    } else {
      foreach ($Property in $Details.PSObject.Properties) {
        $Name = [string]$Property.Name
        if (-not $Receipt.Contains($Name)) {
          $Receipt[$Name] = $Property.Value
        }
      }
    }
  }

  $TempPath = Join-Path $ReceiptRoot ("{0}.tmp" -f ([Guid]::NewGuid().ToString('N')))
  try {
    $Receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $TempPath -Encoding UTF8
    Move-OverlayRuntimeStateFile -TempPath $TempPath -DestinationPath $ReceiptPath
  } finally {
    Remove-Item -LiteralPath $TempPath -Force -ErrorAction SilentlyContinue
  }

  $State = Get-OverlayOrbControlState
  $State['latest_action'] = $Action
  $State['last_receipt_path'] = 'data/runtime/lens-overlay/orb-controls/{0}.json' -f $ReceiptId
  $State['latest_status'] = Get-StringProperty -Payload $Receipt -Name 'status' -Default $Action
  return $Receipt
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

function Test-OverlayDirectFrancisAddressRecognized {
  param([string]$RecognizedText)

  $Text = (([string]$RecognizedText).Trim().ToLowerInvariant() -replace '[^\p{L}\p{Nd}\s]', ' ')
  $Text = ($Text -replace '\s+', ' ').Trim()
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return $false
  }
  return ($Text -eq 'francis' -or $Text -eq 'frances' -or $Text.StartsWith('francis ') -or $Text.StartsWith('frances '))
}

function Get-OverlayDirectFrancisAddressedUtterance {
  param([string]$RecognizedText)

  $Text = ([string]$RecognizedText).Trim()
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return ''
  }

  $Match = [regex]::Match($Text, '^\s*(francis|frances)\b[\s,;:\-]*(?<utterance>.*)$', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
  if (-not $Match.Success) {
    return ''
  }
  return ([string]$Match.Groups['utterance'].Value).Trim()
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
  param(
    [string]$Text,
    [bool]$WakePhraseDetected = $false
  )

  $Normalized = (([string]$Text).Trim().ToLowerInvariant() -replace '[^\p{L}\p{Nd}\s]', ' ')
  $Normalized = ($Normalized -replace '\s+', ' ').Trim()
  $Result = [ordered]@{
    recognized = $false
    intent = ''
    command = ''
    target_side = ''
    target_vertical = ''
    target_corner = ''
    target_anchor = ''
    normalized_text_length = $Normalized.Length
    requires_explicit_orb_reference = $true
    wake_phrase_satisfies_orb_reference = $true
    reference_type = ''
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
  $HasFrancisReference = $Words -contains 'francis' -or $Words -contains 'frances'
  $HasEmbodimentReference = $HasOrbReference -or $HasFrancisReference -or [bool]$WakePhraseDetected
  $HasMoveVerb = $Words -contains 'move' -or $Words -contains 'put' -or $Words -contains 'place' -or $Words -contains 'dock' -or $Words -contains 'shift' -or $Words -contains 'send' -or $Words -contains 'go' -or $Words -contains 'come' -or $Words -contains 'slide' -or $Words -contains 'park' -or $Words -contains 'anchor' -or $Words -contains 'snap' -or $Words -contains 'bring' -or $Words -contains 'set'
  $MoveLeft = $Words -contains 'left'
  $MoveRight = $Words -contains 'right'
  $MoveTop = $Words -contains 'top' -or $Words -contains 'upper'
  $MoveBottom = $Words -contains 'bottom' -or $Words -contains 'lower'
  $HasHorizontalDirection = ($MoveLeft -or $MoveRight) -and ($MoveLeft -ne $MoveRight)
  $HasVerticalDirection = ($MoveTop -or $MoveBottom) -and ($MoveTop -ne $MoveBottom)

  if (-not $HasEmbodimentReference -or -not $HasMoveVerb -or (-not $HasHorizontalDirection -and -not $HasVerticalDirection)) {
    return $Result
  }
  if (($MoveLeft -and $MoveRight) -or ($MoveTop -and $MoveBottom)) {
    return $Result
  }

  $TargetSide = if ($HasHorizontalDirection) { if ($MoveLeft) { 'left' } else { 'right' } } else { '' }
  $TargetVertical = if ($HasVerticalDirection) { if ($MoveTop) { 'top' } else { 'bottom' } } else { '' }
  $TargetCorner = if (-not [string]::IsNullOrWhiteSpace($TargetSide) -and -not [string]::IsNullOrWhiteSpace($TargetVertical)) { '{0}_{1}' -f $TargetVertical, $TargetSide } else { '' }
  $ReferenceType = if ($HasOrbReference) { 'orb' } elseif ($HasFrancisReference) { 'francis_identity' } else { 'wake_phrase' }
  $TargetKind = if (-not [string]::IsNullOrWhiteSpace($TargetCorner)) { 'corner' } elseif (-not [string]::IsNullOrWhiteSpace($TargetVertical)) { 'edge' } else { 'side' }
  $TargetToken = if (-not [string]::IsNullOrWhiteSpace($TargetCorner)) { $TargetCorner } elseif (-not [string]::IsNullOrWhiteSpace($TargetVertical)) { $TargetVertical } else { $TargetSide }
  $Result.recognized = $true
  $Result.intent = 'move_orb'
  $Result.command = 'move_orb_{0}_{1}' -f $TargetToken, $TargetKind
  $Result.target_side = $TargetSide
  $Result.target_vertical = $TargetVertical
  $Result.target_corner = $TargetCorner
  $Result.target_anchor = 'voice_command_{0}_{1}' -f $TargetToken, $TargetKind
  $Result.reference_type = $ReferenceType
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
    $FullScreenOverlayPlane = Test-OrbFullScreenOverlayPlane -Window $Window -WorkArea $WorkArea
    if ($FullScreenOverlayPlane) {
      $TargetX = if ($Side -eq 'left') {
        Clamp-OverlayDouble -Value ([double]$WorkArea.Left + $Margin) -Minimum ([double]$WorkArea.Left) -Maximum ([double]$WorkArea.Right)
      } else {
        Clamp-OverlayDouble -Value ([double]$WorkArea.Right - $Margin) -Minimum ([double]$WorkArea.Left) -Maximum ([double]$WorkArea.Right)
      }
      $CurrentCenterY = [double]$Window.Top + ([double]$Window.Height / 2.0) + (Get-OrbInWindowOffsetY)
      $TargetY = Clamp-OverlayDouble -Value $CurrentCenterY -Minimum ([double]$WorkArea.Top) -Maximum ([double]$WorkArea.Bottom)
      $Placement = Get-OrbWindowPlacementForTarget -Window $Window -WorkArea $WorkArea -X $TargetX -Y $TargetY
      $Window.Left = [double]$Placement['left']
      $Window.Top = [double]$Placement['top']
      Set-OrbInWindowOffset -OffsetX ([double]$Placement['offset_x']) -OffsetY ([double]$Placement['offset_y'])
    } else {
      $TargetLeft = if ($Side -eq 'left') {
        Clamp-OverlayDouble -Value ($MinimumLeft + $Margin) -Minimum $MinimumLeft -Maximum $MaximumLeft
      } else {
        Clamp-OverlayDouble -Value ($MaximumLeft - $Margin) -Minimum $MinimumLeft -Maximum $MaximumLeft
      }
      $TargetTop = Clamp-OverlayDouble -Value ([double]$Window.Top) -Minimum $MinimumTop -Maximum $MaximumTop
      $Window.Left = $TargetLeft
      $Window.Top = $TargetTop
      Set-OrbInWindowOffset -OffsetX 0.0 -OffsetY 0.0
      $Placement = Get-OrbWindowPlacementForTarget -Window $Window -WorkArea $WorkArea -X ([double]$Window.Left + ([double]$Window.Width / 2.0)) -Y ([double]$Window.Top + ([double]$Window.Height / 2.0))
    }
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
      orb_center_x = [double]$Placement['orb_center_x']
      orb_center_y = [double]$Placement['orb_center_y']
      orb_in_window_offset_x = [double]$Placement['offset_x']
      orb_in_window_offset_y = [double]$Placement['offset_y']
      full_screen_overlay_plane = [bool]$Placement['full_screen_overlay_plane']
      overlay_window_stationary = [bool]$Placement['overlay_window_stationary']
      click_hit_box_size = [double]$Placement['click_hit_box_size']
      click_hit_box_scope = [string]$Placement['click_hit_box_scope']
      reach_mode = [string]$Placement['reach_mode']
      position_receipt_written = $PositionReceiptWritten
    }
  }

  if ($null -ne $Window.Dispatcher -and -not [bool]$Window.Dispatcher.CheckAccess()) {
    return $Window.Dispatcher.Invoke($ApplyPosition)
  }
  return $ApplyPosition.Invoke()
}

function Get-OrbCommandTargetCoordinate {
  param(
    [object]$Window,
    [object]$WorkArea,
    [string]$TargetSide = '',
    [string]$TargetVertical = '',
    [double]$Margin = 48.0
  )

  if ($null -eq $Window -or $null -eq $WorkArea) {
    return [ordered]@{
      applied = $false
      error = 'overlay_window_or_work_area_unavailable'
    }
  }

  $HasHorizontalTarget = $TargetSide -in @('left', 'right')
  $HasVerticalTarget = $TargetVertical -in @('top', 'bottom')
  if ((-not [string]::IsNullOrWhiteSpace($TargetSide) -and -not $HasHorizontalTarget) -or (-not [string]::IsNullOrWhiteSpace($TargetVertical) -and -not $HasVerticalTarget)) {
    return [ordered]@{
      applied = $false
      error = 'unsupported_orb_position_target'
    }
  }
  if (-not $HasHorizontalTarget -and -not $HasVerticalTarget) {
    return [ordered]@{
      applied = $false
      error = 'missing_orb_position_target'
    }
  }

  $CurrentCenterX = [double]$Window.Left + ([double]$Window.Width / 2.0) + (Get-OrbInWindowOffsetX)
  $CurrentCenterY = [double]$Window.Top + ([double]$Window.Height / 2.0) + (Get-OrbInWindowOffsetY)
  $MinimumX = [double]$WorkArea.Left
  $MaximumX = [double]$WorkArea.Right
  $MinimumY = [double]$WorkArea.Top
  $MaximumY = [double]$WorkArea.Bottom

  $TargetX = if ($TargetSide -eq 'left') {
    [double]$WorkArea.Left + $Margin
  } elseif ($TargetSide -eq 'right') {
    [double]$WorkArea.Right - $Margin
  } else {
    $CurrentCenterX
  }
  $TargetY = if ($TargetVertical -eq 'top') {
    [double]$WorkArea.Top + $Margin
  } elseif ($TargetVertical -eq 'bottom') {
    [double]$WorkArea.Bottom - $Margin
  } else {
    $CurrentCenterY
  }
  $TargetX = Clamp-OverlayDouble -Value $TargetX -Minimum $MinimumX -Maximum $MaximumX
  $TargetY = Clamp-OverlayDouble -Value $TargetY -Minimum $MinimumY -Maximum $MaximumY
  $TargetCorner = if ($HasHorizontalTarget -and $HasVerticalTarget) { '{0}_{1}' -f $TargetVertical, $TargetSide } else { '' }

  return [ordered]@{
    applied = $true
    target_x = [double]$TargetX
    target_y = [double]$TargetY
    target_side = $TargetSide
    target_vertical = $TargetVertical
    target_corner = $TargetCorner
    margin = $Margin
  }
}

function Set-OrbWindowCoordinatePosition {
  param(
    [object]$Window,
    [object]$WorkArea,
    [double]$X,
    [double]$Y,
    [object]$MotionState = $null,
    [string]$TargetAnchor = 'orb_pointer',
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
    $Placement = Get-OrbWindowPlacementForTarget -Window $Window -WorkArea $WorkArea -X $X -Y $Y
    $TargetLeft = [double]$Placement['left']
    $TargetTop = [double]$Placement['top']

    $Window.Left = $TargetLeft
    $Window.Top = $TargetTop
    Set-OrbInWindowOffset -OffsetX ([double]$Placement['offset_x']) -OffsetY ([double]$Placement['offset_y'])
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
      x = $X
      y = $Y
      orb_center_x = [double]$Placement['orb_center_x']
      orb_center_y = [double]$Placement['orb_center_y']
      orb_in_window_offset_x = [double]$Placement['offset_x']
      orb_in_window_offset_y = [double]$Placement['offset_y']
      in_window_offset_applied = [bool]$Placement['in_window_offset_applied']
      target_reachable_by_orb_center = [bool]$Placement['target_reachable_by_orb_center']
      window_clamped = [bool]$Placement['window_clamped']
      full_screen_overlay_plane = [bool]$Placement['full_screen_overlay_plane']
      overlay_window_stationary = [bool]$Placement['overlay_window_stationary']
      click_hit_box_size = [double]$Placement['click_hit_box_size']
      click_hit_box_scope = [string]$Placement['click_hit_box_scope']
      reach_mode = [string]$Placement['reach_mode']
      target_anchor = $TargetAnchor
      position_receipt_written = $PositionReceiptWritten
    }
  }

  if ($null -ne $Window.Dispatcher -and -not [bool]$Window.Dispatcher.CheckAccess()) {
    return $Window.Dispatcher.Invoke($ApplyPosition)
  }
  return $ApplyPosition.Invoke()
}

function Start-OrbWindowCoordinateTravel {
  param(
    [object]$Window,
    [object]$WorkArea,
    [double]$X,
    [double]$Y,
    [object]$MotionState = $null,
    [string]$TargetAnchor = 'orb_pointer',
    [string]$Root = '',
    [string]$RequestId = '',
    [object]$Request = $null,
    [ValidateRange(0, 5000)]
    [int]$DurationMilliseconds = 0
  )

  if ($null -eq $Window -or $null -eq $WorkArea) {
    return [ordered]@{
      status = 'orb_move_place_unavailable'
      ok = $false
      request_id = $RequestId
      error = 'overlay_window_or_work_area_unavailable'
      runtime_overlay_position_changed = $false
      grants_execution_authority = $false
      grants_mutation_authority = $false
    }
  }
  if ($null -ne $script:LensOverlayOrbMoveTravelRenderingHandler) {
    return [ordered]@{
      status = 'orb_move_place_travel_already_active'
      ok = $false
      request_id = $RequestId
      runtime_overlay_position_changed = $false
      grants_execution_authority = $false
      grants_mutation_authority = $false
    }
  }

  $StartTravel = [System.Func[object]]{
    $Placement = Get-OrbWindowPlacementForTarget -Window $Window -WorkArea $WorkArea -X $X -Y $Y
    $TargetLeft = [double]$Placement['left']
    $TargetTop = [double]$Placement['top']
    $TargetOffsetX = [double]$Placement['offset_x']
    $TargetOffsetY = [double]$Placement['offset_y']
    $StartLeft = [double]$Window.Left
    $StartTop = [double]$Window.Top
    $StartOffsetX = Get-OrbInWindowOffsetX
    $StartOffsetY = Get-OrbInWindowOffsetY
    $StartCenterX = $StartLeft + ([double]$Window.Width / 2.0) + $StartOffsetX
    $StartCenterY = $StartTop + ([double]$Window.Height / 2.0) + $StartOffsetY
    $Distance = [Math]::Sqrt([Math]::Pow(([double]$Placement['orb_center_x']) - $StartCenterX, 2.0) + [Math]::Pow(([double]$Placement['orb_center_y']) - $StartCenterY, 2.0))
    $Duration = [Math]::Max(420, [Math]::Min(1600, [int](320 + ($Distance * 0.95))))
    if ($DurationMilliseconds -gt 0) {
      $Duration = [Math]::Max(240, [Math]::Min(2200, $DurationMilliseconds))
    }

    $Clock = [System.Diagnostics.Stopwatch]::StartNew()
    $script:LensOverlayOrbMoveTravelContext = [ordered]@{
      request_id = $RequestId
      request = $Request
      root = $Root
      window = $Window
      work_area = $WorkArea
      motion_state = $MotionState
      target_anchor = $TargetAnchor
      target_x = $X
      target_y = $Y
      start_left = $StartLeft
      start_top = $StartTop
      start_offset_x = $StartOffsetX
      start_offset_y = $StartOffsetY
      target_left = $TargetLeft
      target_top = $TargetTop
      target_offset_x = $TargetOffsetX
      target_offset_y = $TargetOffsetY
      orb_center_x = [double]$Placement['orb_center_x']
      orb_center_y = [double]$Placement['orb_center_y']
      window_clamped = [bool]$Placement['window_clamped']
      in_window_offset_applied = [bool]$Placement['in_window_offset_applied']
      target_reachable_by_orb_center = [bool]$Placement['target_reachable_by_orb_center']
      full_screen_overlay_plane = [bool]$Placement['full_screen_overlay_plane']
      overlay_window_stationary = [bool]$Placement['overlay_window_stationary']
      click_hit_box_size = [double]$Placement['click_hit_box_size']
      click_hit_box_scope = [string]$Placement['click_hit_box_scope']
      reach_mode = [string]$Placement['reach_mode']
      duration_ms = $Duration
      distance = $Distance
      clock = $Clock
      first_frame_elapsed_ms = -1.0
    }
    $Handler = [System.EventHandler]{
      param($Sender, $EventArgs)

        $Context = $script:LensOverlayOrbMoveTravelContext
        $RenderingHandler = $script:LensOverlayOrbMoveTravelRenderingHandler
        if ($null -eq $Context -or $null -eq $RenderingHandler) {
          return
        }
        $TravelWindow = $Context['window']
        if ($null -eq $TravelWindow) {
          [System.Windows.Media.CompositionTarget]::remove_Rendering($RenderingHandler)
          $script:LensOverlayOrbMoveTravelRenderingHandler = $null
          $script:LensOverlayOrbMoveTravelContext = $null
          return
        }
        $RawElapsedMilliseconds = [double]$Context['clock'].Elapsed.TotalMilliseconds
        if ([double]$Context['first_frame_elapsed_ms'] -lt 0.0) {
          $Context['first_frame_elapsed_ms'] = $RawElapsedMilliseconds
        }
        $ElapsedMilliseconds = [Math]::Max(0.0, $RawElapsedMilliseconds - [double]$Context['first_frame_elapsed_ms'])
        $DurationMs = [Math]::Max(1.0, [double]$Context['duration_ms'])
        $Progress = [Math]::Min(1.0, [Math]::Max(0.0, $ElapsedMilliseconds / $DurationMs))
        $Ease = ($Progress * $Progress * $Progress) * (($Progress * (($Progress * 6.0) - 15.0)) + 10.0)
        $TravelWindow.Left = [double]$Context['start_left'] + (([double]$Context['target_left'] - [double]$Context['start_left']) * $Ease)
        $TravelWindow.Top = [double]$Context['start_top'] + (([double]$Context['target_top'] - [double]$Context['start_top']) * $Ease)
        $OffsetX = [double]$Context['start_offset_x'] + (([double]$Context['target_offset_x'] - [double]$Context['start_offset_x']) * $Ease)
        $OffsetY = [double]$Context['start_offset_y'] + (([double]$Context['target_offset_y'] - [double]$Context['start_offset_y']) * $Ease)
        Set-OrbInWindowOffset -OffsetX $OffsetX -OffsetY $OffsetY

        if ($Progress -lt 1.0) {
          return
        }

        $TravelWindow.Left = [double]$Context['target_left']
        $TravelWindow.Top = [double]$Context['target_top']
        Set-OrbInWindowOffset -OffsetX ([double]$Context['target_offset_x']) -OffsetY ([double]$Context['target_offset_y'])
        if (-not [string]::IsNullOrWhiteSpace([string]$Context['target_anchor'])) {
          $script:LensOverlayOperatorPositionAnchor = [string]$Context['target_anchor']
        }
        Reset-OrbAutonomousMotionAnchor -Window $TravelWindow -MotionState $Context['motion_state']
        $PositionReceiptWritten = $false
        if (-not [string]::IsNullOrWhiteSpace([string]$Context['root'])) {
          Write-OverlayPositionState -Root ([string]$Context['root']) -Window $TravelWindow -MotionState $Context['motion_state'] -OverlayWindowVisible $true
          $PositionReceiptWritten = $true
        }
        $Result = [ordered]@{
          status = 'orb_move_place_applied'
          ok = $true
          request_id = [string]$Context['request_id']
          command = 'orb.move'
          command_id = 'orb.move'
          runtime_overlay_position_changed = $true
          overlay_left = [double]$TravelWindow.Left
          overlay_top = [double]$TravelWindow.Top
          target_x = [double]$Context['target_x']
          target_y = [double]$Context['target_y']
          orb_center_x = [double]$Context['orb_center_x']
          orb_center_y = [double]$Context['orb_center_y']
          orb_in_window_offset_x = [double]$Context['target_offset_x']
          orb_in_window_offset_y = [double]$Context['target_offset_y']
          in_window_offset_applied = [bool]$Context['in_window_offset_applied']
          target_reachable_by_orb_center = [bool]$Context['target_reachable_by_orb_center']
          window_clamped = [bool]$Context['window_clamped']
          full_screen_overlay_plane = [bool]$Context['full_screen_overlay_plane']
          overlay_window_stationary = [bool]$Context['overlay_window_stationary']
          click_hit_box_size = [double]$Context['click_hit_box_size']
          click_hit_box_scope = [string]$Context['click_hit_box_scope']
          reach_mode = [string]$Context['reach_mode']
          overlay_position_anchor = [string]$Context['target_anchor']
          position_receipt_written = $PositionReceiptWritten
          travelled_to_target = $true
          travel_duration_ms = [int][Math]::Round($ElapsedMilliseconds)
          travel_distance = [double]$Context['distance']
          travel_timing_source = 'composition_rendering'
          travel_easing = 'smootherstep'
          bounded_overlay_position_mutation = $true
          mutation_authority_scope = 'runtime_overlay_position_only'
          controls_user_os_cursor = $false
          user_mouse_taken = $false
          physical_input_performed = $false
          desktop_effect_performed = $false
          grants_execution_authority = $false
          grants_mutation_authority = $false
          error = ''
        }
        if ($null -ne $Context['request'] -and -not [string]::IsNullOrWhiteSpace([string]$Context['root'])) {
          Write-OverlayOrbPositionCommandReceipt -Root ([string]$Context['root']) -RequestId ([string]$Context['request_id']) -Request $Context['request'] -Result $Result
          $Result.position_command_receipt_path = 'data/runtime/lens-overlay/orb-position-commands/{0}.json' -f ([string]$Context['request_id'])
        }
        $script:LensOverlayOrbMovePlaceModeResult = $Result
        $Context['clock'].Stop()
        [System.Windows.Media.CompositionTarget]::remove_Rendering($RenderingHandler)
        $script:LensOverlayOrbMoveTravelRenderingHandler = $null
        $script:LensOverlayOrbMoveTravelContext = $null
      }
    $script:LensOverlayOrbMoveTravelRenderingHandler = $Handler
    [System.Windows.Media.CompositionTarget]::add_Rendering($Handler)
    return [ordered]@{
      status = 'orb_move_place_travel_started'
      ok = $true
      request_id = $RequestId
      target_x = $X
      target_y = $Y
      target_left = $TargetLeft
      target_top = $TargetTop
      orb_center_x = [double]$Placement['orb_center_x']
      orb_center_y = [double]$Placement['orb_center_y']
      orb_in_window_offset_x = $TargetOffsetX
      orb_in_window_offset_y = $TargetOffsetY
      in_window_offset_applied = [bool]$Placement['in_window_offset_applied']
      target_reachable_by_orb_center = [bool]$Placement['target_reachable_by_orb_center']
      window_clamped = [bool]$Placement['window_clamped']
      reach_mode = [string]$Placement['reach_mode']
      travel_duration_ms = $Duration
      travel_distance = $Distance
      travel_timing_source = 'composition_rendering'
      travel_easing = 'smootherstep'
      runtime_overlay_position_changed = $false
      travelled_to_target = $false
      grants_execution_authority = $false
      grants_mutation_authority = $false
    }
  }

  if ($null -ne $Window.Dispatcher -and -not [bool]$Window.Dispatcher.CheckAccess()) {
    return $Window.Dispatcher.Invoke($StartTravel)
  }
  return $StartTravel.Invoke()
}

function Dismiss-OverlayOrbMoveCaptureWindow {
  if ($null -ne $script:LensOverlayOrbMoveCaptureTimeoutTimer) {
    try {
      $script:LensOverlayOrbMoveCaptureTimeoutTimer.Stop()
    } catch {
    }
  }
  if ($null -ne $script:LensOverlayOrbMoveCaptureWindow) {
    try {
      if ([bool]$script:LensOverlayOrbMoveCaptureWindow.IsVisible) {
        $script:LensOverlayOrbMoveCaptureWindow.Hide()
      }
    } catch {
    }
  }
  $script:LensOverlayOrbMoveCaptureWindow = $null
  $script:LensOverlayOrbMoveCaptureContext = $null
  $script:LensOverlayOrbMoveCaptureTimeoutTimer = $null
}

function Invoke-OverlayOrbMovePlaceMode {
  param(
    [string]$Root,
    [object]$Request,
    [ValidateRange(1, 60)]
    [int]$TimeoutSeconds = 12
  )

  $RequestId = Get-StringProperty -Payload $Request -Name 'request_id' -Default ''
  if ([string]::IsNullOrWhiteSpace($RequestId)) {
    $RequestId = 'orb-move-place-{0}' -f ([Guid]::NewGuid().ToString('N'))
  }
  $AuthorityScope = Get-StringProperty -Payload $Request -Name 'authority_scope' -Default ''
  if ($AuthorityScope -ne 'runtime_overlay_position_only') {
    return [ordered]@{
      status = 'orb_move_place_refused'
      ok = $false
      request_id = $RequestId
      error = 'unsupported_orb_move_authority_scope'
      runtime_overlay_position_changed = $false
      grants_execution_authority = $false
      grants_mutation_authority = $false
    }
  }

  $Window = $script:LensOverlayWindow
  $MotionState = $script:LensOverlayMotionState
  $WorkArea = $script:LensOverlayWorkArea
  if ($null -eq $WorkArea -and [System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT) {
    try {
      $WorkArea = Get-OverlayVirtualScreenBounds
    } catch {
      $WorkArea = $null
    }
  }
  if ($null -eq $Window -or $null -eq $WorkArea) {
    return [ordered]@{
      status = 'orb_move_place_unavailable'
      ok = $false
      request_id = $RequestId
      error = 'overlay_window_or_work_area_unavailable'
      runtime_overlay_position_changed = $false
      grants_execution_authority = $false
      grants_mutation_authority = $false
    }
  }
  $ExistingCaptureVariable = Get-Variable -Name LensOverlayOrbMoveCaptureWindow -Scope Script -ErrorAction SilentlyContinue
  if ($null -ne $ExistingCaptureVariable -and $null -ne $ExistingCaptureVariable.Value) {
    try {
      if ([bool]$ExistingCaptureVariable.Value.IsVisible) {
        return [ordered]@{
          status = 'orb_move_place_already_armed'
          ok = $false
          request_id = $RequestId
          capture_window_visible = $true
          runtime_overlay_position_changed = $false
          grants_execution_authority = $false
          grants_mutation_authority = $false
        }
      }
      $script:LensOverlayOrbMoveCaptureWindow = $null
      $script:LensOverlayOrbMoveCaptureContext = $null
      $script:LensOverlayOrbMoveCaptureTimeoutTimer = $null
    } catch {
      $script:LensOverlayOrbMoveCaptureWindow = $null
      $script:LensOverlayOrbMoveCaptureContext = $null
      $script:LensOverlayOrbMoveCaptureTimeoutTimer = $null
    }
  }

  $TargetAnchor = Get-StringProperty -Payload $Request -Name 'target_anchor' -Default 'orb_move_one_shot_click'
  $script:LensOverlayOrbMovePlaceModeHandled = $false
  $script:LensOverlayOrbMovePlaceModeResult = [ordered]@{
    status = 'orb_move_place_cancelled'
    ok = $false
    request_id = $RequestId
    cancel_reason = 'not_completed'
    runtime_overlay_position_changed = $false
    grants_execution_authority = $false
    grants_mutation_authority = $false
  }

  $CaptureWindow = New-Object System.Windows.Window
  $CaptureWindow.Title = 'Francis Orb Move Capture'
  $CaptureWindow.WindowStyle = [System.Windows.WindowStyle]::None
  $CaptureWindow.ResizeMode = [System.Windows.ResizeMode]::NoResize
  $CaptureWindow.AllowsTransparency = $true
  $TransparentBrush = New-Object System.Windows.Media.SolidColorBrush
  $TransparentBrush.Color = [System.Windows.Media.Color]::FromArgb(1, 0, 0, 0)
  $CaptureWindow.Background = $TransparentBrush
  $CaptureWindow.ShowInTaskbar = $false
  $CaptureWindow.TopMost = $true
  try {
    $CaptureWindow.Owner = $Window
  } catch {
  }
  $CaptureWindow.WindowStartupLocation = [System.Windows.WindowStartupLocation]::Manual
  $CaptureWindow.Left = [double]$WorkArea.Left
  $CaptureWindow.Top = [double]$WorkArea.Top
  $CaptureWindow.Width = [double]$WorkArea.Width
  $CaptureWindow.Height = [double]$WorkArea.Height
  $CaptureWindow.Cursor = [System.Windows.Input.Cursors]::Cross

  $CaptureRoot = New-Object System.Windows.Controls.Grid
  $CaptureRoot.Focusable = $true
  $CaptureRoot.Background = $TransparentBrush
  $CueBorder = New-Object System.Windows.Controls.Border
  $CueBrush = New-Object System.Windows.Media.SolidColorBrush
  $CueBrush.Color = [System.Windows.Media.Color]::FromArgb(96, 234, 242, 255)
  $CueBorder.BorderBrush = $CueBrush
  $CueBorder.BorderThickness = New-Object System.Windows.Thickness(2)
  [void]$CaptureRoot.Children.Add($CueBorder)
  $CaptureWindow.Content = $CaptureRoot

  $TimeoutTimer = New-Object System.Windows.Threading.DispatcherTimer
  $TimeoutTimer.Interval = [TimeSpan]::FromSeconds([Math]::Max(1, $TimeoutSeconds))
  $TimeoutTimer.Add_Tick({
      if (-not [bool]$script:LensOverlayOrbMovePlaceModeHandled) {
        $Context = $script:LensOverlayOrbMoveCaptureContext
        $ContextRequestId = if ($null -ne $Context) { [string]$Context['request_id'] } else { 'unknown_request' }
        $script:LensOverlayOrbMovePlaceModeHandled = $true
        $script:LensOverlayOrbMovePlaceModeResult = [ordered]@{
          status = 'orb_move_place_cancelled'
          ok = $false
          request_id = $ContextRequestId
          cancel_reason = 'timeout'
          runtime_overlay_position_changed = $false
          grants_execution_authority = $false
          grants_mutation_authority = $false
        }
        Dismiss-OverlayOrbMoveCaptureWindow
      }
    })
  $CaptureWindow.Add_KeyDown({
      param($Sender, $EventArgs)

      if ($EventArgs.Key -eq [System.Windows.Input.Key]::Escape -and -not [bool]$script:LensOverlayOrbMovePlaceModeHandled) {
        $Context = $script:LensOverlayOrbMoveCaptureContext
        $ContextRequestId = if ($null -ne $Context) { [string]$Context['request_id'] } else { 'unknown_request' }
        $EventArgs.Handled = $true
        $script:LensOverlayOrbMovePlaceModeHandled = $true
        $script:LensOverlayOrbMovePlaceModeResult = [ordered]@{
          status = 'orb_move_place_cancelled'
          ok = $false
          request_id = $ContextRequestId
          cancel_reason = 'escape'
          runtime_overlay_position_changed = $false
          grants_execution_authority = $false
          grants_mutation_authority = $false
        }
        Dismiss-OverlayOrbMoveCaptureWindow
      }
    })
  $CaptureRoot.Add_MouseRightButtonDown({
      param($Sender, $EventArgs)

      if (-not [bool]$script:LensOverlayOrbMovePlaceModeHandled) {
        $Context = $script:LensOverlayOrbMoveCaptureContext
        $ContextRequestId = if ($null -ne $Context) { [string]$Context['request_id'] } else { 'unknown_request' }
        $EventArgs.Handled = $true
        $script:LensOverlayOrbMovePlaceModeHandled = $true
        $script:LensOverlayOrbMovePlaceModeResult = [ordered]@{
          status = 'orb_move_place_cancelled'
          ok = $false
          request_id = $ContextRequestId
          cancel_reason = 'right_click'
          runtime_overlay_position_changed = $false
          grants_execution_authority = $false
          grants_mutation_authority = $false
        }
        Dismiss-OverlayOrbMoveCaptureWindow
      }
    })
  $CaptureRoot.Add_MouseLeftButtonDown({
      param($Sender, $EventArgs)

      if ([bool]$script:LensOverlayOrbMovePlaceModeHandled) {
        return
      }
      $EventArgs.Handled = $true
      $script:LensOverlayOrbMovePlaceModeHandled = $true
      $Context = $script:LensOverlayOrbMoveCaptureContext
      $Capture = $script:LensOverlayOrbMoveCaptureWindow
      if ($null -eq $Context -or $null -eq $Capture) {
        $script:LensOverlayOrbMovePlaceModeResult = [ordered]@{
          status = 'orb_move_place_unavailable'
          ok = $false
          request_id = 'unknown_request'
          error = 'orb_move_capture_context_unavailable'
          runtime_overlay_position_changed = $false
          grants_execution_authority = $false
          grants_mutation_authority = $false
        }
        return
      }
      $Point = $EventArgs.GetPosition($Sender)
      $TargetX = [double]$Capture.Left + [double]$Point.X
      $TargetY = [double]$Capture.Top + [double]$Point.Y
      $ContextRequestId = [string]$Context['request_id']
      $ContextRoot = [string]$Context['root']
      $ContextRequest = $Context['request']
      $ContextTargetAnchor = [string]$Context['target_anchor']
      $Travel = Start-OrbWindowCoordinateTravel -Window $Context['window'] -WorkArea $Context['work_area'] -X $TargetX -Y $TargetY -MotionState $Context['motion_state'] -TargetAnchor $ContextTargetAnchor -Root $ContextRoot -RequestId $ContextRequestId -Request $ContextRequest
      $Payload = [ordered]@{
        status = Get-StringProperty -Payload $Travel -Name 'status' -Default 'orb_move_place_travel_unknown'
        ok = Get-BoolProperty -Payload $Travel -Name 'ok' -Default $false
        request_id = $ContextRequestId
        command = 'orb.move'
        command_id = 'orb.move'
        runtime_overlay_position_changed = $false
        overlay_left = 0.0
        overlay_top = 0.0
        target_x = $TargetX
        target_y = $TargetY
        orb_center_x = Get-StringProperty -Payload $Travel -Name 'orb_center_x' -Default ''
        orb_center_y = Get-StringProperty -Payload $Travel -Name 'orb_center_y' -Default ''
        orb_in_window_offset_x = Get-StringProperty -Payload $Travel -Name 'orb_in_window_offset_x' -Default ''
        orb_in_window_offset_y = Get-StringProperty -Payload $Travel -Name 'orb_in_window_offset_y' -Default ''
        in_window_offset_applied = Get-BoolProperty -Payload $Travel -Name 'in_window_offset_applied' -Default $false
        target_reachable_by_orb_center = Get-BoolProperty -Payload $Travel -Name 'target_reachable_by_orb_center' -Default $false
        window_clamped = Get-BoolProperty -Payload $Travel -Name 'window_clamped' -Default $false
        reach_mode = Get-StringProperty -Payload $Travel -Name 'reach_mode' -Default 'window_plus_in_window_offset'
        overlay_position_anchor = $ContextTargetAnchor
        travel_started = Get-BoolProperty -Payload $Travel -Name 'ok' -Default $false
        travelled_to_target = $false
        travel_duration_ms = Get-IntegerProperty -Payload $Travel -Name 'travel_duration_ms' -Default 0
        travel_timing_source = Get-StringProperty -Payload $Travel -Name 'travel_timing_source' -Default 'composition_rendering'
        travel_easing = Get-StringProperty -Payload $Travel -Name 'travel_easing' -Default 'smootherstep'
        position_receipt_written = $false
        bounded_overlay_position_mutation = $true
        mutation_authority_scope = 'runtime_overlay_position_only'
        controls_user_os_cursor = $false
        user_mouse_taken = $false
        physical_input_performed = $false
        desktop_effect_performed = $false
        grants_execution_authority = $false
        grants_mutation_authority = $false
        error = Get-StringProperty -Payload $Travel -Name 'error' -Default ''
      }
      $script:LensOverlayOrbMovePlaceModeResult = $Payload
      Dismiss-OverlayOrbMoveCaptureWindow
    })
  $CaptureWindow.Add_Loaded({
      if ($null -ne $script:LensOverlayOrbMoveCaptureWindow) {
        [void]$script:LensOverlayOrbMoveCaptureWindow.Activate()
        if ($null -ne $script:LensOverlayOrbMoveCaptureWindow.Content) {
          [void]$script:LensOverlayOrbMoveCaptureWindow.Content.Focus()
        }
      }
      if ($null -ne $script:LensOverlayOrbMoveCaptureTimeoutTimer) {
        $script:LensOverlayOrbMoveCaptureTimeoutTimer.Start()
      }
    })
  $CaptureWindow.Add_Closed({
      param($Sender, $EventArgs)

      if ($null -ne $script:LensOverlayOrbMoveCaptureTimeoutTimer) {
        $script:LensOverlayOrbMoveCaptureTimeoutTimer.Stop()
      }
      if ($script:LensOverlayOrbMoveCaptureWindow -eq $Sender) {
        $script:LensOverlayOrbMoveCaptureWindow = $null
        $script:LensOverlayOrbMoveCaptureContext = $null
        $script:LensOverlayOrbMoveCaptureTimeoutTimer = $null
      }
    })

  $script:LensOverlayOrbMoveCaptureContext = [ordered]@{
    request_id = $RequestId
    root = $Root
    request = $Request
    target_anchor = $TargetAnchor
    window = $Window
    work_area = $WorkArea
    motion_state = $MotionState
  }
  $script:LensOverlayOrbMoveCaptureTimeoutTimer = $TimeoutTimer
  $script:LensOverlayOrbMoveCaptureWindow = $CaptureWindow
  [void]$CaptureWindow.Show()
  return [ordered]@{
    status = 'orb_move_place_armed'
    ok = $true
    request_id = $RequestId
    capture_window_visible = $true
    timeout_seconds = $TimeoutSeconds
    runtime_overlay_position_changed = $false
    grants_execution_authority = $false
    grants_mutation_authority = $false
  }
}

function Invoke-OverlayOrbVirtualPointerState {
  param([string]$Root)

  if ([string]::IsNullOrWhiteSpace($Root)) {
    return $null
  }

  $PointerPath = Get-OverlayOrbVirtualPointerStatePath
  if (-not (Test-Path -LiteralPath $PointerPath -PathType Leaf)) {
    return $null
  }
  try {
    $PointerItem = Get-Item -LiteralPath $PointerPath -ErrorAction Stop
    $PointerWriteTicks = [Int64]$PointerItem.LastWriteTimeUtc.Ticks
    $LastPointerWriteTicksVariable = Get-Variable -Name LensOverlayLastOrbVirtualPointerWriteTicks -Scope Script -ErrorAction SilentlyContinue
    $LastPointerWriteTicks = if ($null -ne $LastPointerWriteTicksVariable) { [Int64]$LastPointerWriteTicksVariable.Value } else { [Int64]0 }
    if ($PointerWriteTicks -eq $LastPointerWriteTicks) {
      return $null
    }
  } catch {
    return $null
  }
  $Pointer = Read-JsonFile -Path $PointerPath
  if ($null -eq $Pointer) {
    $script:LensOverlayLastOrbVirtualPointerWriteTicks = $PointerWriteTicks
    return $null
  }

  $PointerMode = Get-StringProperty -Payload $Pointer -Name 'mode' -Default ''
  $PointerUpdatedAt = Get-StringProperty -Payload $Pointer -Name 'updated_at' -Default ''
  if ($PointerMode -ne 'orb_pointer' -or [string]::IsNullOrWhiteSpace($PointerUpdatedAt)) {
    $script:LensOverlayLastOrbVirtualPointerWriteTicks = $PointerWriteTicks
    return $null
  }
  $LastPointerVariable = Get-Variable -Name LensOverlayLastOrbVirtualPointerUpdatedAt -Scope Script -ErrorAction SilentlyContinue
  $LastPointerUpdatedAt = if ($null -ne $LastPointerVariable) { [string]$LastPointerVariable.Value } else { '' }
  if ($PointerUpdatedAt -eq $LastPointerUpdatedAt) {
    $script:LensOverlayLastOrbVirtualPointerWriteTicks = $PointerWriteTicks
    return $null
  }

  $X = [double](Get-IntegerProperty -Payload $Pointer -Name 'x' -Default 0)
  $Y = [double](Get-IntegerProperty -Payload $Pointer -Name 'y' -Default 0)
  $Window = $script:LensOverlayWindow
  $MotionState = $script:LensOverlayMotionState
  $WorkArea = $script:LensOverlayWorkArea
  if ($null -eq $WorkArea -and [System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT) {
    try {
      $WorkArea = Get-OverlayVirtualScreenBounds
    } catch {
      $WorkArea = $null
    }
  }

  $Position = Set-OrbWindowCoordinatePosition -Window $Window -WorkArea $WorkArea -X $X -Y $Y -MotionState $MotionState -TargetAnchor 'orb_pointer' -Root $Root
  $Payload = [ordered]@{
    status = if ([bool]$Position['applied']) { 'orb_virtual_pointer_applied' } else { 'orb_virtual_pointer_unavailable' }
    ok = [bool]$Position['applied']
    runtime_overlay_position_changed = [bool]$Position['applied']
    virtual_pointer_x = $X
    virtual_pointer_y = $Y
    overlay_left = if ([bool]$Position['applied']) { [double]$Position['left'] } else { 0.0 }
    overlay_top = if ([bool]$Position['applied']) { [double]$Position['top'] } else { 0.0 }
    orb_center_x = if ([bool]$Position['applied']) { [double]$Position['orb_center_x'] } else { 0.0 }
    orb_center_y = if ([bool]$Position['applied']) { [double]$Position['orb_center_y'] } else { 0.0 }
    orb_in_window_offset_x = if ([bool]$Position['applied']) { [double]$Position['orb_in_window_offset_x'] } else { 0.0 }
    orb_in_window_offset_y = if ([bool]$Position['applied']) { [double]$Position['orb_in_window_offset_y'] } else { 0.0 }
    full_screen_overlay_plane = Get-BoolProperty -Payload $Position -Name 'full_screen_overlay_plane' -Default $false
    overlay_window_stationary = Get-BoolProperty -Payload $Position -Name 'overlay_window_stationary' -Default $false
    click_hit_box_size = Get-StringProperty -Payload $Position -Name 'click_hit_box_size' -Default ''
    click_hit_box_scope = Get-StringProperty -Payload $Position -Name 'click_hit_box_scope' -Default ''
    reach_mode = Get-StringProperty -Payload $Position -Name 'reach_mode' -Default ''
    position_receipt_written = Get-BoolProperty -Payload $Position -Name 'position_receipt_written' -Default $false
    controls_user_os_cursor = $false
    user_mouse_taken = $false
    physical_input_performed = $false
    desktop_effect_performed = $false
    grants_execution_authority = $false
    grants_mutation_authority = $false
    error = Get-StringProperty -Payload $Position -Name 'error' -Default ''
  }
  $RequestId = 'orb-virtual-pointer-{0}' -f (Get-OverlayTextDigest -Text $PointerUpdatedAt).Substring(0, 12)
  Write-OverlayOrbVirtualPointerReceipt -Root $Root -RequestId $RequestId -Pointer $Pointer -Result $Payload
  $script:LensOverlayLastOrbVirtualPointerUpdatedAt = $PointerUpdatedAt
  $script:LensOverlayLastOrbVirtualPointerWriteTicks = $PointerWriteTicks
  return $Payload
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
  $TargetVertical = Get-StringProperty -Payload $Command -Name 'target_vertical' -Default ''
  $TargetCorner = Get-StringProperty -Payload $Command -Name 'target_corner' -Default ''
  $TargetAnchor = Get-StringProperty -Payload $Command -Name 'target_anchor' -Default ''
  $CommandName = Get-StringProperty -Payload $Command -Name 'command' -Default ''
  $IsBridgeFileCommand = ($CommandSource -eq 'chatgpt_voice_bridge_file_request')
  $IsDirectFrancisAddressCommand = ($CommandSource -eq 'local_overlay_direct_francis_address')
  $EffectiveCommandRequestId = $CommandRequestId
  if ([string]::IsNullOrWhiteSpace($EffectiveCommandRequestId) -and -not $IsBridgeFileCommand) {
    $TargetRequestSegment = if (-not [string]::IsNullOrWhiteSpace($TargetCorner)) { $TargetCorner } elseif (-not [string]::IsNullOrWhiteSpace($TargetSide)) { $TargetSide } elseif (-not [string]::IsNullOrWhiteSpace($TargetVertical)) { $TargetVertical } else { 'target' }
    $EffectiveCommandRequestId = 'local-orb-{0}-{1}' -f $TargetRequestSegment, ([Guid]::NewGuid().ToString('N'))
  }
  $SelectedVoice = Get-OverlaySelectedVoiceName -Provider $Provider -Voice $Voice -RequestedVoiceId $RemoteVoiceId
  $Payload = New-OverlayVoiceProjection -SelectedVoiceName $SelectedVoice -Provider $Provider -WakeListening $true -WakePhraseText $WakePhraseText
  $Payload.local_overlay_command = $true
  $Payload.voice_orb_command = $true
  $Payload.voice_command_recognized = $true
  $Payload.orb_command = $CommandName
  $Payload.overlay_position_command = $CommandName
  $Payload.orb_command_reference_type = Get-StringProperty -Payload $Command -Name 'reference_type' -Default ''
  $Payload.overlay_position_command_source = $CommandSource
  $Payload.overlay_position_command_request_id = $EffectiveCommandRequestId
  $Payload.target_side = $TargetSide
  $Payload.target_vertical = $TargetVertical
  $Payload.target_corner = $TargetCorner
  $Payload.target_anchor = $TargetAnchor
  $Payload.wake_phrase_detected = [bool]$WakePhraseDetected
  $Payload.wake_count = $WakeCount
  $Payload.recognition_confidence = [Math]::Round($RecognitionConfidence, 3)
  $Payload.recognition_threshold = $RecognitionThreshold
  $Payload.wake_alias_count = $WakeAliasCount
  Set-OverlayContinuousVoiceChatGateReadback -Payload $Payload -ContinuousVoiceChat $ContinuousVoiceChat -PushToTalkActive $ContinuousVoiceChat
  $Payload.direct_francis_address_detected = [bool]$IsDirectFrancisAddressCommand
  $Payload.transcript_source = if ($CommandSource -eq 'chatgpt_voice_bridge_file_request') { 'chatgpt_voice_bridge_command_request' } elseif ($IsDirectFrancisAddressCommand) { 'microphone_direct_francis_address' } elseif ($WakePhraseDetected) { 'microphone_wake_listener' } else { 'microphone_continuous_dictation' }
  $Payload.voice_recognition = 'system_speech_local_orb_command'
  $Payload.microphone_speech = (-not [bool]$IsBridgeFileCommand)
  $Payload.microphone_recognition_claimed = (-not [bool]$IsBridgeFileCommand)
  $Payload.synthetic_transcript = [bool]$IsBridgeFileCommand
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

  $HasHorizontalTarget = $TargetSide -in @('left', 'right')
  $HasVerticalTarget = $TargetVertical -in @('top', 'bottom')
  $UnsupportedHorizontalTarget = (-not [string]::IsNullOrWhiteSpace($TargetSide) -and -not $HasHorizontalTarget)
  $UnsupportedVerticalTarget = (-not [string]::IsNullOrWhiteSpace($TargetVertical) -and -not $HasVerticalTarget)
  if ($UnsupportedHorizontalTarget -or $UnsupportedVerticalTarget -or (-not $HasHorizontalTarget -and -not $HasVerticalTarget)) {
    $Payload.status = 'orb_voice_command_refused'
    $Payload.ok = $false
    $Payload.error = 'unsupported_orb_position_target'
    $Payload.runtime_overlay_position_changed = $false
    $Payload.message = 'Orb voice command was recognized but refused because the requested target is unsupported.'
    Write-OverlayVoiceState -Root $Root -Payload $Payload
    return $Payload
  }

  $ReceiptSource = Get-StringProperty -Payload $Command -Name 'source' -Default ''
  if ([string]::IsNullOrWhiteSpace($ReceiptSource)) {
    $ReceiptSource = if ($IsBridgeFileCommand) { 'chatgpt.voice_bridge' } else { 'lens.overlay.voice' }
  }
  $ReceiptActor = Get-StringProperty -Payload $Command -Name 'actor' -Default ''
  if ([string]::IsNullOrWhiteSpace($ReceiptActor)) {
    $ReceiptActor = if ($IsBridgeFileCommand) { 'chatgpt_voice_bridge' } else { 'lens.overlay.voice' }
  }
  $ReceiptClientOrigin = Get-StringProperty -Payload $Command -Name 'client_origin' -Default ''
  if ([string]::IsNullOrWhiteSpace($ReceiptClientOrigin)) {
    $ReceiptClientOrigin = if ($IsBridgeFileCommand) { 'chatgpt_voice_bridge_file_request' } else { 'local_overlay_speech_recognition' }
  }
  $CommandReceiptRequest = [ordered]@{
    command = $CommandName
    command_id = Get-StringProperty -Payload $Command -Name 'command_id' -Default $CommandName
    target_side = $TargetSide
    target_vertical = $TargetVertical
    target_corner = $TargetCorner
    target_anchor = $TargetAnchor
    reference_type = Get-StringProperty -Payload $Command -Name 'reference_type' -Default ''
    command_source = $CommandSource
    source = $ReceiptSource
    actor = $ReceiptActor
    client_origin = $ReceiptClientOrigin
    authority_scope = Get-StringProperty -Payload $Command -Name 'authority_scope' -Default 'runtime_overlay_position_only'
    receipt_kind = Get-StringProperty -Payload $Command -Name 'receipt_kind' -Default 'overlay_position'
    microphone_recognition_claimed = (-not [bool]$IsBridgeFileCommand)
    microphone_speech = (-not [bool]$IsBridgeFileCommand)
    wake_phrase_detected = [bool]$WakePhraseDetected
    transcript_source = $Payload.transcript_source
    transcript_hash = $Payload.transcript_hash
    transcript_length = $Payload.transcript_length
  }

  $Window = $script:LensOverlayWindow
  $MotionState = $script:LensOverlayMotionState
  $WorkArea = $script:LensOverlayWorkArea
  if ($null -eq $WorkArea -and [System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT) {
    try {
      $WorkArea = Get-OverlayVirtualScreenBounds
    } catch {
      $WorkArea = $null
    }
  }

  if ($HasVerticalTarget) {
    $Target = Get-OrbCommandTargetCoordinate -Window $Window -WorkArea $WorkArea -TargetSide $TargetSide -TargetVertical $TargetVertical -Margin 48
    if (-not [bool]$Target['applied']) {
      $Payload.status = 'orb_voice_command_unavailable'
      $Payload.ok = $false
      $Payload.error = Get-StringProperty -Payload $Target -Name 'error' -Default 'overlay_window_position_unavailable'
      $Payload.runtime_overlay_position_changed = $false
      $Payload.position_receipt_written = $false
      $Payload.message = 'Orb voice command was recognized but the live overlay target coordinate was unavailable.'
      Write-OverlayVoiceState -Root $Root -Payload $Payload
      return $Payload
    }

    $Travel = Start-OrbWindowCoordinateTravel `
      -Window $Window `
      -WorkArea $WorkArea `
      -X ([double]$Target['target_x']) `
      -Y ([double]$Target['target_y']) `
      -MotionState $MotionState `
      -TargetAnchor $TargetAnchor `
      -Root $Root `
      -RequestId $EffectiveCommandRequestId `
      -Request $CommandReceiptRequest
    if (-not [bool]$Travel['ok']) {
      $Payload.status = 'orb_voice_command_unavailable'
      $Payload.ok = $false
      $Payload.error = Get-StringProperty -Payload $Travel -Name 'error' -Default (Get-StringProperty -Payload $Travel -Name 'status' -Default 'orb_coordinate_travel_unavailable')
      $Payload.runtime_overlay_position_changed = $false
      $Payload.position_receipt_written = $false
      $Payload.message = 'Orb voice command was recognized but coordinate travel could not start.'
      Write-OverlayVoiceState -Root $Root -Payload $Payload
      return $Payload
    }

    $Payload.status = 'orb_voice_command_travel_started'
    $Payload.ok = $true
    $Payload.runtime_overlay_position_changed = $false
    $Payload.position_receipt_written = $false
    $Payload.travel_started = Get-BoolProperty -Payload $Travel -Name 'ok' -Default $false
    $Payload.travelled_to_target = $false
    $Payload.target_x = [double]$Travel['target_x']
    $Payload.target_y = [double]$Travel['target_y']
    $Payload.orb_center_x = [double]$Travel['orb_center_x']
    $Payload.orb_center_y = [double]$Travel['orb_center_y']
    $Payload.orb_in_window_offset_x = [double]$Travel['orb_in_window_offset_x']
    $Payload.orb_in_window_offset_y = [double]$Travel['orb_in_window_offset_y']
    $Payload.target_reachable_by_orb_center = Get-BoolProperty -Payload $Travel -Name 'target_reachable_by_orb_center' -Default $false
    $Payload.window_clamped = Get-BoolProperty -Payload $Travel -Name 'window_clamped' -Default $false
    $Payload.reach_mode = Get-StringProperty -Payload $Travel -Name 'reach_mode' -Default ''
    $Payload.travel_duration_ms = Get-IntegerProperty -Payload $Travel -Name 'travel_duration_ms' -Default 0
    $Payload.travel_distance = Get-StringProperty -Payload $Travel -Name 'travel_distance' -Default ''
    $Payload.travel_timing_source = Get-StringProperty -Payload $Travel -Name 'travel_timing_source' -Default ''
    $Payload.travel_easing = Get-StringProperty -Payload $Travel -Name 'travel_easing' -Default ''
    $Payload.message = 'Orb position voice command started local travel and was not forwarded to chat.'
    if (-not [bool]$IsBridgeFileCommand) {
      Write-OverlayOrbPositionCommandReceipt -Root $Root -RequestId $EffectiveCommandRequestId -Request $CommandReceiptRequest -Result $Payload
      $Payload.position_command_receipt_path = 'data/runtime/lens-overlay/orb-position-commands/{0}.json' -f $EffectiveCommandRequestId
    }
    Write-OverlayVoiceState -Root $Root -Payload $Payload
    return $Payload
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
  if (-not [bool]$IsBridgeFileCommand) {
    Write-OverlayOrbPositionCommandReceipt -Root $Root -RequestId $EffectiveCommandRequestId -Request $CommandReceiptRequest -Result $Payload
    $Payload.position_command_receipt_path = 'data/runtime/lens-overlay/orb-position-commands/{0}.json' -f $EffectiveCommandRequestId
  }
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

function Invoke-OverlayVoiceChatBridgeRequest {
  param(
    [string]$ChatUri,
    [string]$Message,
    [bool]$UseLlm,
    [string]$ConversationActor,
    [string]$VoiceTurnId,
    [string]$SupersedesVoiceTurnId,
    [ValidateRange(1, 120)]
    [int]$TimeoutSeconds = 20
  )

  $Result = [ordered]@{
    ok = $false
    status = 'unavailable'
    reply = ''
    error = ''
    response_status = ''
    use_llm = [bool]$UseLlm
    timeout_seconds = $TimeoutSeconds
    execution_trace_captured = $false
    model_or_tool_execution_span_captured = $false
    model_call_requested = $false
    model_call_response_observed = $false
    trace_voice_turn_correlation = $false
    trace_stale_reply_suppression_supported = $false
    trace_model_call_cancellation_supported = $false
    trace_backend_current_voice_turn_lookup_supported = $false
    trace_backend_stale_reply_drop_supported = $false
    trace_thought_relevance_pruning_supported = $false
    trace_voice_turn_relevance_policy = ''
    trace_stale_reply_suppression_owner = ''
    trace_stale_reply_suppression_boundary = ''
    trace_model_call_abort_boundary = ''
    trace_thought_relevance_pruning_boundary = ''
  }

  try {
    $Body = [ordered]@{
      message = $Message
      use_llm = [bool]$UseLlm
      actor = $ConversationActor
      voice_turn_id = $VoiceTurnId
      supersedes_voice_turn_id = $SupersedesVoiceTurnId
    }
    $ChatBody = Invoke-RestMethod -Uri $ChatUri -Method Post -ContentType 'application/json' -Body ($Body | ConvertTo-Json -Depth 6) -TimeoutSec $TimeoutSeconds -ErrorAction Stop
    $Reply = (Get-StringProperty -Payload $ChatBody -Name 'reply' -Default '').Trim()
    $ErrorText = Get-StringProperty -Payload $ChatBody -Name 'error' -Default ''
    $ResponseStatus = Get-StringProperty -Payload $ChatBody -Name 'status' -Default ''
    $Result.reply = $Reply
    $Result.error = $ErrorText
    $Result.response_status = $ResponseStatus

    $Trace = $null
    try {
      $Trace = $ChatBody.PSObject.Properties['execution_trace'].Value
    } catch {
      $Trace = $null
    }
    if ($null -ne $Trace) {
      $Result.execution_trace_captured = $true
      $Result.model_or_tool_execution_span_captured = Get-BoolProperty -Payload $Trace -Name 'model_or_tool_execution_span_captured' -Default $false
      $Result.model_call_requested = Get-BoolProperty -Payload $Trace -Name 'model_call_requested' -Default $false
      $Result.model_call_response_observed = Get-BoolProperty -Payload $Trace -Name 'model_call_response_observed' -Default $false
      $Result.trace_voice_turn_correlation = Get-BoolProperty -Payload $Trace -Name 'voice_turn_correlation' -Default $false
      $Result.trace_stale_reply_suppression_supported = Get-BoolProperty -Payload $Trace -Name 'stale_reply_suppression_supported' -Default $false
      $Result.trace_model_call_cancellation_supported = Get-BoolProperty -Payload $Trace -Name 'model_call_cancellation_supported' -Default $false
      $Result.trace_backend_current_voice_turn_lookup_supported = Get-BoolProperty -Payload $Trace -Name 'backend_current_voice_turn_lookup_supported' -Default $false
      $Result.trace_backend_stale_reply_drop_supported = Get-BoolProperty -Payload $Trace -Name 'backend_stale_reply_drop_supported' -Default $false
      $Result.trace_thought_relevance_pruning_supported = Get-BoolProperty -Payload $Trace -Name 'thought_relevance_pruning_supported' -Default $false
      $Result.trace_voice_turn_relevance_policy = Get-StringProperty -Payload $Trace -Name 'voice_turn_relevance_policy' -Default ''
      $Result.trace_stale_reply_suppression_owner = Get-StringProperty -Payload $Trace -Name 'stale_reply_suppression_owner' -Default ''
      $Result.trace_stale_reply_suppression_boundary = Get-StringProperty -Payload $Trace -Name 'stale_reply_suppression_boundary' -Default ''
      $Result.trace_model_call_abort_boundary = Get-StringProperty -Payload $Trace -Name 'model_call_abort_boundary' -Default ''
      $Result.trace_thought_relevance_pruning_boundary = Get-StringProperty -Payload $Trace -Name 'thought_relevance_pruning_boundary' -Default ''
    }

    if ([string]::IsNullOrWhiteSpace($ErrorText) -and -not [string]::IsNullOrWhiteSpace($Reply)) {
      $Result.ok = $true
      $Result.status = 'responded'
    } elseif ($ErrorText -eq 'api_permission_denied') {
      $Result.status = 'denied'
    } else {
      $Result.status = 'failed'
    }
  } catch {
    $Result.error = [string]$_.Exception.Message
    $Result.status = 'unavailable'
  }
  return $Result
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
      Set-OverlayContinuousVoiceChatGateReadback -Payload $Payload -ContinuousVoiceChat $false -PushToTalkActive $false
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
    Set-OverlayContinuousVoiceChatGateReadback -Payload $Payload -ContinuousVoiceChat $ContinuousVoiceChat -PushToTalkActive $ContinuousVoiceChatPushToTalkActive
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
  $PrimaryTimeoutSeconds = if ($UseLlm) { 0 } else { 20 }
  $FallbackTimeoutSeconds = 45
  $ChatBridgePrimaryStatus = ''
  $ChatBridgePrimaryError = ''
  $ChatBridgeFallbackUsed = $false
  $ChatBridgeEffectiveUseLlm = [bool]$UseLlm

  if ($UseLlm) {
    $ChatBridgePrimaryStatus = 'llm_deferred_for_voice_bridge_availability'
    $ChatBridgePrimaryError = 'local_llm_voice_turn_not_called_without_abort_or_quality_guard'
    $ChatBridgeFallbackUsed = $true
    $ChatBridgeEffectiveUseLlm = $false
    $Attempt = Invoke-OverlayVoiceChatBridgeRequest -ChatUri $ChatUri -Message $BoundedUtterance -UseLlm $false -ConversationActor $ConversationActor -VoiceTurnId $VoiceTurnId -SupersedesVoiceTurnId $SupersedesVoiceTurnId -TimeoutSeconds $FallbackTimeoutSeconds
  } else {
    $Attempt = Invoke-OverlayVoiceChatBridgeRequest -ChatUri $ChatUri -Message $BoundedUtterance -UseLlm $false -ConversationActor $ConversationActor -VoiceTurnId $VoiceTurnId -SupersedesVoiceTurnId $SupersedesVoiceTurnId -TimeoutSeconds $PrimaryTimeoutSeconds
    $ChatBridgePrimaryStatus = [string]$Attempt['status']
    $ChatBridgePrimaryError = [string]$Attempt['error']
  }

  $ChatBridgeStatus = [string]$Attempt['status']
  $ChatReply = [string]$Attempt['reply']
  $ChatError = [string]$Attempt['error']
  $ChatResponseStatus = [string]$Attempt['response_status']
  $ChatExecutionTraceCaptured = [bool]$Attempt['model_or_tool_execution_span_captured']
  $ChatModelRequested = [bool]$Attempt['model_call_requested']
  $ChatModelResponseObserved = [bool]$Attempt['model_call_response_observed']
  $ChatTraceVoiceTurnCorrelation = [bool]$Attempt['trace_voice_turn_correlation']
  $ChatTraceStaleReplySuppressionSupported = [bool]$Attempt['trace_stale_reply_suppression_supported']
  $ChatTraceModelCallCancellationSupported = [bool]$Attempt['trace_model_call_cancellation_supported']
  $ChatTraceBackendCurrentVoiceTurnLookupSupported = [bool]$Attempt['trace_backend_current_voice_turn_lookup_supported']
  $ChatTraceBackendStaleReplyDropSupported = [bool]$Attempt['trace_backend_stale_reply_drop_supported']
  $ChatTraceThoughtRelevancePruningSupported = [bool]$Attempt['trace_thought_relevance_pruning_supported']
  $ChatTraceVoiceTurnRelevancePolicy = [string]$Attempt['trace_voice_turn_relevance_policy']
  $ChatTraceStaleReplySuppressionOwner = [string]$Attempt['trace_stale_reply_suppression_owner']
  $ChatTraceStaleReplySuppressionBoundary = [string]$Attempt['trace_stale_reply_suppression_boundary']
  $ChatTraceModelCallAbortBoundary = [string]$Attempt['trace_model_call_abort_boundary']
  $ChatTraceThoughtRelevancePruningBoundary = [string]$Attempt['trace_thought_relevance_pruning_boundary']

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
    Set-OverlayContinuousVoiceChatGateReadback -Payload $SuppressedPayload -ContinuousVoiceChat $ContinuousVoiceChat -PushToTalkActive $ContinuousVoiceChatPushToTalkActive
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
    $SuppressedPayload.chat_bridge_primary_status = $ChatBridgePrimaryStatus
    $SuppressedPayload.chat_bridge_primary_error = $ChatBridgePrimaryError
    $SuppressedPayload.chat_bridge_fallback_used = $ChatBridgeFallbackUsed
    $SuppressedPayload.chat_bridge_effective_use_llm = $ChatBridgeEffectiveUseLlm
    $SuppressedPayload.chat_bridge_primary_timeout_seconds = $PrimaryTimeoutSeconds
    $SuppressedPayload.chat_bridge_fallback_timeout_seconds = if ($ChatBridgeFallbackUsed) { $FallbackTimeoutSeconds } else { 0 }
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
  Set-OverlayContinuousVoiceChatGateReadback -Payload $SpeechPayload -ContinuousVoiceChat $ContinuousVoiceChat -PushToTalkActive $ContinuousVoiceChatPushToTalkActive
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
  $SpeechPayload.chat_bridge_primary_status = $ChatBridgePrimaryStatus
  $SpeechPayload.chat_bridge_primary_error = $ChatBridgePrimaryError
  $SpeechPayload.chat_bridge_fallback_used = $ChatBridgeFallbackUsed
  $SpeechPayload.chat_bridge_effective_use_llm = $ChatBridgeEffectiveUseLlm
  $SpeechPayload.chat_bridge_primary_timeout_seconds = $PrimaryTimeoutSeconds
  $SpeechPayload.chat_bridge_fallback_timeout_seconds = if ($ChatBridgeFallbackUsed) { $FallbackTimeoutSeconds } else { 0 }
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
  $SpeechPayload.llm_fallback_used = $ChatBridgeFallbackUsed
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

function Update-OverlayRuntimeVoiceFeatureFlags {
  if ($null -eq (Get-OverlayScriptValue -Name LensOverlayRuntimeVoice)) {
    $script:LensOverlayRuntimeVoice = New-OverlayRuntimeVoiceProjection -Provider $script:LensOverlayRequestedVoiceProvider -Voice $script:LensOverlayRequestedVoiceName -WakeListening ($null -ne (Get-OverlayScriptValue -Name LensOverlayWakeRecognizer)) -WakePhraseText $script:LensOverlayRequestedWakePhrase -ConfidenceThreshold $script:LensOverlayRequestedWakeConfidenceThreshold
  }
  $script:LensOverlayRuntimeVoice.voice_llm_enabled = Get-OverlayVoiceUseLlm
  $script:LensOverlayRuntimeVoice.voice_llm_request_source = if (Get-OverlayVoiceUseLlm) { 'orb_right_click_panel_or_EnableVoiceLlm' } else { 'disabled' }
  $ContinuousVoiceChat = Get-OverlayScriptBool -Name LensOverlayRequestedContinuousVoiceChat
  Set-OverlayContinuousVoiceChatGateReadback -Payload $script:LensOverlayRuntimeVoice -ContinuousVoiceChat $ContinuousVoiceChat -PushToTalkActive (Test-OverlayContinuousVoiceChatPushToTalkActive)
  $script:LensOverlayRuntimeVoice.microphone_gate_while_speaking = 'francis_stop_only'
  $script:LensOverlayRuntimeVoice.conversation_forwarding_while_speaking = $false
}

function Publish-OverlayOrbControlRuntimeState {
  if ([string]::IsNullOrWhiteSpace((Get-OverlayScriptValue -Name LensOverlayDataRoot -Default ''))) {
    return
  }
  if ($null -eq (Get-OverlayScriptValue -Name LensOverlayWindow)) {
    return
  }
  $Config = Get-OverlayScriptValue -Name LensOverlayConfig -Default (Get-OverlayConfig)
  $BodyState = New-DeferredMcpBodyStateForOverlay -Config $Config
  Write-OverlayState -Root $script:LensOverlayDataRoot -Status 'overlay_running' -OverlayWindowVisible $true -AlwaysOnTop ([bool]$script:LensOverlayWindow.TopMost) -Message 'Francis Lens overlay window is running with Orb right-click controls available.' -McpBodyState $BodyState -OrbVisual $script:LensOverlayOrbVisual -OverlayVoice $script:LensOverlayRuntimeVoice
}

function Set-OverlayOrbControlStatusText {
  param([string]$Text)

  $StatusText = Get-OverlayScriptValue -Name LensOverlayOrbPanelStatusText
  if ($null -eq $StatusText) {
    return
  }
  try {
    $StatusText.Text = $Text
  } catch {
  }
}

function Update-OverlayOrbPanelFeatureChecks {
  $script:LensOverlayOrbPanelSyncing = $true
  try {
    $WakeCheck = Get-OverlayScriptValue -Name LensOverlayOrbPanelWakeCheck
    $ContinuousCheck = Get-OverlayScriptValue -Name LensOverlayOrbPanelContinuousCheck
    $LlmCheck = Get-OverlayScriptValue -Name LensOverlayOrbPanelLlmCheck
    $MotionCheck = Get-OverlayScriptValue -Name LensOverlayOrbPanelMotionCheck
    if ($null -ne $WakeCheck) {
      $WakeCheck.IsChecked = ($null -ne (Get-OverlayScriptValue -Name LensOverlayWakeRecognizer))
    }
    if ($null -ne $ContinuousCheck) {
      $ContinuousCheck.IsChecked = Get-OverlayScriptBool -Name LensOverlayRequestedContinuousVoiceChat
    }
    if ($null -ne $LlmCheck) {
      $LlmCheck.IsChecked = Get-OverlayVoiceUseLlm
    }
    if ($null -ne $MotionCheck) {
      $MotionCheck.IsChecked = ($null -ne (Get-OverlayScriptValue -Name LensOverlayMotionSubscription))
    }
  } finally {
    $script:LensOverlayOrbPanelSyncing = $false
  }
}

function Set-OverlayOrbFeatureToggle {
  param(
    [ValidateSet('wake_listen', 'continuous_voice_chat', 'voice_llm', 'ambient_motion')]
    [string]$Feature,
    [bool]$Enabled
  )

  $Status = 'updated'
  $ActualEnabled = $Enabled
  $ErrorMessage = ''
  switch ($Feature) {
    'wake_listen' {
      $script:LensOverlayEnableWakeListen = $Enabled
      if ($Enabled) {
        if ($null -eq (Get-OverlayScriptValue -Name LensOverlayWakeRecognizer)) {
          try {
            $script:LensOverlayWakeRecognizer = Start-OverlayWakeListener -Root $script:LensOverlayDataRoot -Phrase $script:LensOverlayRequestedWakePhrase -Response $script:LensOverlayRequestedWakeResponse -Provider $script:LensOverlayRequestedVoiceProvider -Voice $script:LensOverlayRequestedVoiceName -Rate $script:LensOverlayRequestedVoiceRate -Volume $script:LensOverlayRequestedVoiceVolume -RemoteVoiceId $script:LensOverlayRequestedElevenLabsVoiceId -RemoteModelId $script:LensOverlayRequestedElevenLabsModelId -RemoteOutputFormat $script:LensOverlayRequestedElevenLabsOutputFormat -RemoteStability $script:LensOverlayRequestedElevenLabsStability -RemoteSimilarityBoost $script:LensOverlayRequestedElevenLabsSimilarityBoost -RemoteStyle $script:LensOverlayRequestedElevenLabsStyle -RemoteSpeed $script:LensOverlayRequestedElevenLabsSpeed -RemoteUseSpeakerBoost $script:LensOverlayRequestedElevenLabsUseSpeakerBoost -ConfidenceThreshold $script:LensOverlayRequestedWakeConfidenceThreshold -ContinuousVoiceChat $script:LensOverlayRequestedContinuousVoiceChat
          } catch {
            $script:LensOverlayWakeRecognizer = $null
            $ErrorMessage = [string]$_.Exception.Message
          }
        }
        $ActualEnabled = $null -ne (Get-OverlayScriptValue -Name LensOverlayWakeRecognizer)
        if ($ActualEnabled) {
          $script:LensOverlayRuntimeVoice = New-OverlayRuntimeVoiceProjection -Provider $script:LensOverlayRequestedVoiceProvider -Voice $script:LensOverlayRequestedVoiceName -WakeListening $true -WakePhraseText $script:LensOverlayRequestedWakePhrase -Status 'listening' -ConfidenceThreshold $script:LensOverlayRequestedWakeConfidenceThreshold -WakeAliasCount $script:LensOverlayWakeAliasCount
        } else {
          $Status = 'failed'
          $script:LensOverlayRuntimeVoice = New-OverlayRuntimeVoiceProjection -Provider $script:LensOverlayRequestedVoiceProvider -Voice $script:LensOverlayRequestedVoiceName -WakeListening $false -WakePhraseText '' -Status 'listen_failed' -ConfidenceThreshold $script:LensOverlayRequestedWakeConfidenceThreshold
          $script:LensOverlayRuntimeVoice.error = 'wake_listener_start_failed'
        }
      } else {
        $WakeRecognizer = Get-OverlayScriptValue -Name LensOverlayWakeRecognizer
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
        $script:LensOverlayWakeRecognizer = $null
        $ActualEnabled = $false
        $script:LensOverlayRuntimeVoice = New-OverlayRuntimeVoiceProjection -Provider $script:LensOverlayRequestedVoiceProvider -Voice $script:LensOverlayRequestedVoiceName -WakeListening $false -WakePhraseText '' -Status 'configured' -ConfidenceThreshold $script:LensOverlayRequestedWakeConfidenceThreshold
      }
      Update-OverlayRuntimeVoiceFeatureFlags
      Write-OverlayVoiceState -Root $script:LensOverlayDataRoot -Payload $script:LensOverlayRuntimeVoice
    }
    'continuous_voice_chat' {
      $script:LensOverlayRequestedContinuousVoiceChat = $Enabled
      $script:LensOverlayContinuousVoiceChat = $Enabled
      Update-OverlayRuntimeVoiceFeatureFlags
      Write-OverlayVoiceState -Root $script:LensOverlayDataRoot -Payload $script:LensOverlayRuntimeVoice
      if ($Enabled) {
        Set-OverlayOrbControlStatusText -Text 'Push-to-talk armed. Hold Ctrl+V while speaking.'
      } else {
        Set-OverlayOrbControlStatusText -Text 'Push-to-talk off. Use the wake phrase or direct Francis address.'
      }
    }
    'voice_llm' {
      $script:LensOverlayVoiceUseLlmRequested = $Enabled
      Update-OverlayRuntimeVoiceFeatureFlags
      Write-OverlayVoiceState -Root $script:LensOverlayDataRoot -Payload $script:LensOverlayRuntimeVoice
    }
    'ambient_motion' {
      if ($Enabled) {
        if ($null -eq (Get-OverlayScriptValue -Name LensOverlayMotionSubscription)) {
          Reset-OrbAutonomousMotionAnchor -Window $script:LensOverlayWindow -MotionState $script:LensOverlayMotionState
          $script:LensOverlayMotionSubscription = Start-OrbFrameSyncedMotion -Window $script:LensOverlayWindow -MotionState $script:LensOverlayMotionState
        }
        $ActualEnabled = $null -ne (Get-OverlayScriptValue -Name LensOverlayMotionSubscription)
      } else {
        $MotionSubscription = Get-OverlayScriptValue -Name LensOverlayMotionSubscription
        if ($null -ne $MotionSubscription) {
          Stop-OrbFrameSyncedMotion -Subscription $MotionSubscription
        }
        $script:LensOverlayMotionSubscription = $null
        $script:LensOverlayRenderFrameClock = $null
        Reset-OrbAutonomousMotionAnchor -Window $script:LensOverlayWindow -MotionState $script:LensOverlayMotionState
        $ActualEnabled = $false
      }
      $script:LensOverlayOrbVisual = New-OrbVisualProjection -AutonomousMotion $ActualEnabled -ManualDrag (Get-OverlayScriptBool -Name LensOverlayManualOrbDragEnabled)
      Write-OverlayPositionState -Root $script:LensOverlayDataRoot -Window $script:LensOverlayWindow -MotionState $script:LensOverlayMotionState -OverlayWindowVisible $true
    }
  }

  $State = Get-OverlayOrbControlState
  $State['latest_feature'] = $Feature
  $State['latest_status'] = if ($Status -eq 'failed') { 'toggle_failed' } else { 'toggle_applied' }
  $Receipt = Write-OverlayOrbControlReceipt -Root $script:LensOverlayDataRoot -Action 'feature_toggle' -Details ([ordered]@{
      status = $State['latest_status']
      feature = $Feature
      requested_enabled = $Enabled
      actual_enabled = $ActualEnabled
      error = $ErrorMessage
      features = Get-OverlayOrbControlFeatures
    })
  Publish-OverlayOrbControlRuntimeState
  Set-OverlayOrbControlStatusText -Text ("{0}: {1}" -f ($Feature -replace '_', ' '), $(if ($ActualEnabled) { 'on' } else { 'off' }))
  Update-OverlayOrbPanelFeatureChecks
  return $Receipt
}

function Invoke-OverlayOrbPanelChatSubmit {
  param([string]$Text)

  $BoundedText = ([string]$Text).Trim()
  if ([string]::IsNullOrWhiteSpace($BoundedText)) {
    Set-OverlayOrbControlStatusText -Text 'Type a short message first.'
    return Write-OverlayOrbControlReceipt -Root $script:LensOverlayDataRoot -Action 'chat_refused' -Details ([ordered]@{
        status = 'chat_refused'
        error = 'empty_chat_text'
        chat_text_redacted = $true
      })
  }
  if ($BoundedText.Length -gt 600) {
    Set-OverlayOrbControlStatusText -Text 'Message is over 600 characters.'
    return Write-OverlayOrbControlReceipt -Root $script:LensOverlayDataRoot -Action 'chat_refused' -Details ([ordered]@{
        status = 'chat_refused'
        error = 'chat_text_too_long'
        chat_input_length = $BoundedText.Length
        chat_text_redacted = $true
      })
  }

  $TextPath = New-OverlayVoiceTextFile -Root $script:LensOverlayDataRoot -Text $BoundedText
  try {
    try {
      $PowerShell = Get-Command pwsh -ErrorAction Stop
    } catch {
      $PowerShell = Get-Command powershell -ErrorAction Stop
    }
    $ArgumentList = @(
      '-NoProfile',
      '-ExecutionPolicy',
      'Bypass',
      '-File',
      $PSCommandPath,
      '-Mode',
      'SyntheticVoiceTurn',
      '-DataDir',
      $script:LensOverlayDataRoot,
      '-VoiceEnvironmentScope',
      $script:LensOverlayVoiceEnvironmentScope,
      '-VoiceProvider',
      $script:LensOverlayRequestedVoiceProvider,
      '-VoiceName',
      $script:LensOverlayRequestedVoiceName,
      '-ElevenLabsVoiceId',
      $script:LensOverlayRequestedElevenLabsVoiceId,
      '-ElevenLabsModelId',
      $script:LensOverlayRequestedElevenLabsModelId,
      '-ElevenLabsOutputFormat',
      $script:LensOverlayRequestedElevenLabsOutputFormat,
      '-ElevenLabsStability',
      ([string]$script:LensOverlayRequestedElevenLabsStability),
      '-ElevenLabsSimilarityBoost',
      ([string]$script:LensOverlayRequestedElevenLabsSimilarityBoost),
      '-ElevenLabsStyle',
      ([string]$script:LensOverlayRequestedElevenLabsStyle),
      '-ElevenLabsSpeed',
      ([string]$script:LensOverlayRequestedElevenLabsSpeed),
      '-WakePhrase',
      $script:LensOverlayRequestedWakePhrase,
      '-WakeConfidenceThreshold',
      ([string]$script:LensOverlayRequestedWakeConfidenceThreshold),
      '-VoiceRate',
      ([string]$script:LensOverlayRequestedVoiceRate),
      '-VoiceVolume',
      ([string]$script:LensOverlayRequestedVoiceVolume),
      '-VoiceTextPath',
      $TextPath
    )
    if (Get-OverlayVoiceUseLlm) {
      $ArgumentList += '-EnableVoiceLlm'
    }
    if (Get-OverlayScriptBool -Name LensOverlayRequestedElevenLabsUseSpeakerBoost) {
      $ArgumentList += '-ElevenLabsUseSpeakerBoost'
    }
    $ArgumentText = Join-OverlayProcessArguments -Arguments $ArgumentList
    $Process = Start-Process -FilePath $PowerShell.Source -ArgumentList $ArgumentText -WindowStyle Hidden -PassThru
    Set-OverlayOrbControlStatusText -Text 'Sent. Reply will speak if the chat route responds.'
    $Input = Get-OverlayScriptValue -Name LensOverlayOrbPanelInput
    if ($null -ne $Input) {
      $Input.Text = ''
    }
    return Write-OverlayOrbControlReceipt -Root $script:LensOverlayDataRoot -Action 'chat_queued' -Details ([ordered]@{
        status = 'chat_queued'
        chat_input_length = $BoundedText.Length
        chat_input_hash = Get-OverlayTextDigest -Text $BoundedText
        chat_text_redacted = $true
        synthetic_voice_turn = $true
        explicit_operator_text = $true
        voice_reply_requested = $true
        speech_output_owner = 'lens.overlay'
        chat_process_started = $true
        chat_process_id = [int]$Process.Id
        text_transport = 'transient_local_file'
        text_file_command_line_redacted = $true
        text_file_retention = 'transient_deleted_by_synthetic_voice_turn'
      })
  } catch {
    Remove-OverlayVoiceTextFile -Root $script:LensOverlayDataRoot -TextPath $TextPath
    $ErrorMessage = [string]$_.Exception.Message
    Set-OverlayOrbControlStatusText -Text 'Chat could not start.'
    return Write-OverlayOrbControlReceipt -Root $script:LensOverlayDataRoot -Action 'chat_failed' -Details ([ordered]@{
        status = 'chat_failed'
        error = $ErrorMessage
        chat_input_length = $BoundedText.Length
        chat_input_hash = Get-OverlayTextDigest -Text $BoundedText
        chat_text_redacted = $true
        text_file_deleted_after_failure = $true
      })
  }
}

function New-OverlayOrbPanelCheckBox {
  param(
    [string]$Text,
    [string]$Feature
  )

  $CheckBox = New-Object System.Windows.Controls.CheckBox
  $CheckBox.Content = $Text
  $CheckBox.Tag = $Feature
  $CheckBox.Margin = New-Object System.Windows.Thickness(0, 2, 12, 2)
  $CheckBox.Foreground = New-Object System.Windows.Media.SolidColorBrush([System.Windows.Media.Color]::FromArgb(238, 226, 232, 240))
  $CheckBox.FontSize = 11
  $CheckBox.Add_Click({
      param($Sender, $EventArgs)

      if ([bool](Get-OverlayScriptBool -Name LensOverlayOrbPanelSyncing)) {
        return
      }
      $EventArgs.Handled = $true
      [void](Set-OverlayOrbFeatureToggle -Feature ([string]$Sender.Tag) -Enabled ([bool]$Sender.IsChecked))
    })
  return $CheckBox
}

function New-OverlayOrbRightClickPanel {
  param([object]$PlacementTarget)

  $Popup = New-Object System.Windows.Controls.Primitives.Popup
  $Popup.PlacementTarget = $PlacementTarget
  $Popup.Placement = [System.Windows.Controls.Primitives.PlacementMode]::MousePoint
  $Popup.StaysOpen = $false
  $Popup.AllowsTransparency = $true

  $Border = New-Object System.Windows.Controls.Border
  $Border.Width = 292
  $Border.MaxHeight = 268
  $Border.CornerRadius = New-Object System.Windows.CornerRadius(8)
  $Border.Padding = New-Object System.Windows.Thickness(10)
  $Border.Background = New-Object System.Windows.Media.SolidColorBrush([System.Windows.Media.Color]::FromArgb(238, 11, 18, 32))
  $Border.BorderBrush = New-Object System.Windows.Media.SolidColorBrush([System.Windows.Media.Color]::FromArgb(180, 203, 213, 225))
  $Border.BorderThickness = New-Object System.Windows.Thickness(1)

  $Stack = New-Object System.Windows.Controls.StackPanel
  $Stack.Orientation = [System.Windows.Controls.Orientation]::Vertical

  $Header = New-Object System.Windows.Controls.TextBlock
  $Header.Text = 'Francis Orb'
  $Header.FontSize = 13
  $Header.FontWeight = [System.Windows.FontWeights]::SemiBold
  $Header.Foreground = New-Object System.Windows.Media.SolidColorBrush([System.Windows.Media.Color]::FromArgb(255, 248, 250, 252))
  $Header.Margin = New-Object System.Windows.Thickness(0, 0, 0, 6)
  [void]$Stack.Children.Add($Header)

  $FeatureWrap = New-Object System.Windows.Controls.WrapPanel
  $FeatureWrap.Margin = New-Object System.Windows.Thickness(0, 0, 0, 8)
  $WakeCheck = New-OverlayOrbPanelCheckBox -Text 'Listen' -Feature 'wake_listen'
  $ContinuousCheck = New-OverlayOrbPanelCheckBox -Text 'PTT' -Feature 'continuous_voice_chat'
  $LlmCheck = New-OverlayOrbPanelCheckBox -Text 'LLM' -Feature 'voice_llm'
  $MotionCheck = New-OverlayOrbPanelCheckBox -Text 'Drift' -Feature 'ambient_motion'
  [void]$FeatureWrap.Children.Add($WakeCheck)
  [void]$FeatureWrap.Children.Add($ContinuousCheck)
  [void]$FeatureWrap.Children.Add($LlmCheck)
  [void]$FeatureWrap.Children.Add($MotionCheck)
  [void]$Stack.Children.Add($FeatureWrap)

  $ChatRow = New-Object System.Windows.Controls.DockPanel
  $ChatRow.LastChildFill = $true
  $ChatRow.Margin = New-Object System.Windows.Thickness(0, 0, 0, 6)
  $SendButton = New-Object System.Windows.Controls.Button
  $SendButton.Content = 'Send'
  $SendButton.MinWidth = 54
  $SendButton.Height = 26
  $SendButton.Margin = New-Object System.Windows.Thickness(8, 0, 0, 0)
  [System.Windows.Controls.DockPanel]::SetDock($SendButton, [System.Windows.Controls.Dock]::Right)
  $Input = New-Object System.Windows.Controls.TextBox
  $Input.Height = 26
  $Input.MaxLength = 600
  $Input.ToolTip = 'Message Francis through the Orb'
  $Input.FontSize = 12
  $Input.Add_KeyDown({
      param($Sender, $EventArgs)

      if ($EventArgs.Key -eq [System.Windows.Input.Key]::Enter) {
        $EventArgs.Handled = $true
        [void](Invoke-OverlayOrbPanelChatSubmit -Text ([string]$Sender.Text))
      }
    })
  $SendButton.Add_Click({
      param($Sender, $EventArgs)

      $EventArgs.Handled = $true
      [void](Invoke-OverlayOrbPanelChatSubmit -Text ([string]$script:LensOverlayOrbPanelInput.Text))
    })
  [void]$ChatRow.Children.Add($SendButton)
  [void]$ChatRow.Children.Add($Input)
  [void]$Stack.Children.Add($ChatRow)

  $StatusText = New-Object System.Windows.Controls.TextBlock
  $StatusText.Text = 'Receipted Orb chat. Hold Ctrl+V for push-to-talk.'
  $StatusText.FontSize = 11
  $StatusText.TextWrapping = [System.Windows.TextWrapping]::Wrap
  $StatusText.Foreground = New-Object System.Windows.Media.SolidColorBrush([System.Windows.Media.Color]::FromArgb(220, 203, 213, 225))
  [void]$Stack.Children.Add($StatusText)

  $Border.Child = $Stack
  $Popup.Child = $Border
  $Popup.Add_Closed({
      $State = Get-OverlayOrbControlState
      $State['panel_visible'] = $false
      $State['latest_status'] = 'panel_closed'
    })

  $script:LensOverlayOrbPanelWakeCheck = $WakeCheck
  $script:LensOverlayOrbPanelContinuousCheck = $ContinuousCheck
  $script:LensOverlayOrbPanelLlmCheck = $LlmCheck
  $script:LensOverlayOrbPanelMotionCheck = $MotionCheck
  $script:LensOverlayOrbPanelInput = $Input
  $script:LensOverlayOrbPanelStatusText = $StatusText
  return $Popup
}

function Show-OverlayOrbRightClickPanel {
  param([object]$PlacementTarget)

  if ($null -eq (Get-OverlayScriptValue -Name LensOverlayOrbPanelPopup)) {
    $script:LensOverlayOrbPanelPopup = New-OverlayOrbRightClickPanel -PlacementTarget $PlacementTarget
  }
  Update-OverlayOrbPanelFeatureChecks
  $State = Get-OverlayOrbControlState
  $State['panel_visible'] = $true
  $State['latest_status'] = 'panel_open'
  [void](Write-OverlayOrbControlReceipt -Root $script:LensOverlayDataRoot -Action 'panel_open' -Details ([ordered]@{
        status = 'panel_open'
        trigger = 'right_click'
        panel_width = 292
        panel_max_height = 268
        features = Get-OverlayOrbControlFeatures
      }))
  $script:LensOverlayOrbPanelPopup.IsOpen = $true
  Set-OverlayOrbControlStatusText -Text 'Receipted Orb chat. Replies speak through voice.'
  try {
    [void]$script:LensOverlayOrbPanelInput.Focus()
  } catch {
  }
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
    $script:LensOverlayContinuousVoicePushToTalkObserved = $false
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
        if (Test-OverlayContinuousVoiceChatPushToTalkActive) {
          $script:LensOverlayContinuousVoicePushToTalkObserved = $true
        }
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
        if (Test-OverlayContinuousVoiceChatPushToTalkActive) {
          $script:LensOverlayContinuousVoicePushToTalkObserved = $true
        }
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
        $ContinuousVoicePushToTalkActive = Test-OverlayContinuousVoiceChatPushToTalkActive
        $ContinuousVoicePushToTalkObserved = [bool](Get-OverlayScriptValue -Name LensOverlayContinuousVoicePushToTalkObserved -Default $false)
        $ContinuousVoicePushToTalkAllowed = ($ContinuousVoicePushToTalkActive -or $ContinuousVoicePushToTalkObserved)
        $script:LensOverlayContinuousVoicePushToTalkObserved = $false
        if ([double]$EventArgs.Result.Confidence -lt $script:LensOverlayWakeConfidenceThreshold) {
          $Rejected = New-OverlayVoiceProjection -SelectedVoiceName (Get-OverlaySelectedVoiceName -Provider $script:LensOverlayWakeVoiceProvider -Voice $script:LensOverlayWakeVoice -RequestedVoiceId $script:LensOverlayWakeRemoteVoiceId) -Provider $script:LensOverlayWakeVoiceProvider -WakeListening $true -WakePhraseText $script:LensOverlayWakePhrase
          $Rejected.status = 'wake_rejected_low_confidence'
          $Rejected.ok = $false
          $Rejected.wake_phrase_detected = $false
          $Rejected.recognition_confidence = [Math]::Round([double]$EventArgs.Result.Confidence, 3)
          $Rejected.recognition_threshold = $script:LensOverlayWakeConfidenceThreshold
          $Rejected.wake_alias_count = $script:LensOverlayWakeAliasCount
          Set-OverlayContinuousVoiceChatGateReadback -Payload $Rejected -ContinuousVoiceChat ([bool]$script:LensOverlayContinuousVoiceChat) -PushToTalkActive $ContinuousVoicePushToTalkAllowed
          $Rejected.transcript_redacted = $true
          $Rejected.stores_transcript = $false
          $Rejected.message = 'Wake phrase candidate was heard below confidence threshold; no speech response was emitted.'
          Write-OverlayVoiceState -Root $script:LensOverlayWakeRoot -Payload $Rejected
          return
        }
        $RecognizedText = [string]$EventArgs.Result.Text
        $UtteranceText = Get-OverlayWakePrefixedUtterance -RecognizedText $RecognizedText -WakeAliases $script:LensOverlayWakeAliases
        $DirectFrancisAddressDetected = Test-OverlayDirectFrancisAddressRecognized -RecognizedText $RecognizedText
        $DirectFrancisUtteranceText = if ($DirectFrancisAddressDetected) { Get-OverlayDirectFrancisAddressedUtterance -RecognizedText $RecognizedText } else { '' }
        $WakePhraseOnly = Test-OverlayWakePhraseRecognized -RecognizedText $RecognizedText -WakeAliases $script:LensOverlayWakeAliases
        $StopPhraseRecognized = Test-OverlayStopPhraseRecognized -RecognizedText $RecognizedText -WakeAliases $script:LensOverlayWakeAliases
        $SpeechGuard = Get-OverlayOwnedSpeechGuardState -Root $script:LensOverlayWakeRoot -CooldownSeconds 12
        $OwnedSpeechActive = Get-BoolProperty -Payload $SpeechGuard -Name 'owned_speech_active' -Default $false
        $OwnedSpeechRecentlyCompleted = Get-BoolProperty -Payload $SpeechGuard -Name 'owned_speech_recently_completed' -Default $false
        $ExternalVoiceSpeechActive = Get-BoolProperty -Payload $SpeechGuard -Name 'external_voice_speech_active' -Default $false
        if ($StopPhraseRecognized) {
          $script:LensOverlayWakeCount += 1
          [void](Invoke-OverlayVoiceStopPhrase -Root $script:LensOverlayWakeRoot -RecognizedText $RecognizedText -Provider $script:LensOverlayWakeVoiceProvider -Voice $script:LensOverlayWakeVoice -WakePhraseText $script:LensOverlayWakePhrase -RecognitionConfidence ([double]$EventArgs.Result.Confidence) -RecognitionThreshold $script:LensOverlayWakeConfidenceThreshold -WakeAliasCount $script:LensOverlayWakeAliasCount -WakeCount $script:LensOverlayWakeCount -SpeechGuard $SpeechGuard)
          return
        }
        if ($OwnedSpeechActive -or $OwnedSpeechRecentlyCompleted -or $ExternalVoiceSpeechActive) {
          $Suppressed = New-OverlayVoiceProjection -SelectedVoiceName (Get-OverlaySelectedVoiceName -Provider $script:LensOverlayWakeVoiceProvider -Voice $script:LensOverlayWakeVoice -RequestedVoiceId $script:LensOverlayWakeRemoteVoiceId) -Provider $script:LensOverlayWakeVoiceProvider -WakeListening $true -WakePhraseText $script:LensOverlayWakePhrase
          $Suppressed.status = 'voice_input_suppressed_while_speaking'
          $Suppressed.ok = $true
          $Suppressed.wake_phrase_detected = (-not [string]::IsNullOrWhiteSpace($UtteranceText) -or $WakePhraseOnly -or $DirectFrancisAddressDetected)
          $Suppressed.direct_francis_address_detected = [bool]$DirectFrancisAddressDetected
          $Suppressed.stop_phrase_detected = $false
          Set-OverlayContinuousVoiceChatGateReadback -Payload $Suppressed -ContinuousVoiceChat ([bool]$script:LensOverlayContinuousVoiceChat) -PushToTalkActive $ContinuousVoicePushToTalkAllowed
          $Suppressed.continuous_voice_chat_blocker = if ($OwnedSpeechActive) { 'owned_speech_process_active' } elseif ($OwnedSpeechRecentlyCompleted) { 'owned_speech_recently_completed' } else { 'external_voice_transport_speaking' }
          $Suppressed.owned_speech_recently_completed = [bool]$OwnedSpeechRecentlyCompleted
          $Suppressed.external_voice_speech_active = [bool]$ExternalVoiceSpeechActive
          $Suppressed.external_voice_turn_id = Get-StringProperty -Payload $SpeechGuard -Name 'external_voice_turn_id' -Default ''
          $Suppressed.single_voice_owner_guard = Get-StringProperty -Payload $SpeechGuard -Name 'single_voice_owner_guard' -Default ''
          $Suppressed.self_trigger_guard_window_seconds = Get-IntegerProperty -Payload $SpeechGuard -Name 'self_trigger_guard_window_seconds' -Default 12
          $Suppressed.recognition_confidence = [Math]::Round([double]$EventArgs.Result.Confidence, 3)
          $Suppressed.recognition_threshold = $script:LensOverlayWakeConfidenceThreshold
          $Suppressed.transcript_length = $RecognizedText.Length
          $Suppressed.transcript_hash = Get-OverlayTextDigest -Text $RecognizedText
          $Suppressed.transcript_source = if (-not [string]::IsNullOrWhiteSpace($UtteranceText)) { 'microphone_wake_listener' } elseif ($DirectFrancisAddressDetected) { 'microphone_direct_francis_address' } else { 'microphone_continuous_dictation' }
          $Suppressed.voice_recognition = 'system_speech_suppressed_during_owned_speech'
          $Suppressed.transcript_redacted = $true
          $Suppressed.stores_transcript = $false
          $Suppressed.speech_output_suppressed = $true
          $Suppressed.conversation_forwarding_suppressed = $true
          $Suppressed.microphone_gate_while_speaking = 'francis_stop_only'
          $Suppressed.conversation_forwarding_while_speaking = $false
          $Suppressed.required_interrupt_phrase = 'francis_stop'
          $Suppressed.barge_in_scope = if ($ExternalVoiceSpeechActive) { 'suppress_external_voice_transport_echo_on_francis_stop_only' } else { 'cancel_owned_speech_process_on_francis_stop_only' }
          $Suppressed.message = if ($OwnedSpeechActive) { 'Francis owned speech is active; microphone input is gated to the Francis stop phrase and this transcript was not forwarded.' } elseif ($OwnedSpeechRecentlyCompleted) { 'Francis owned speech just completed; microphone input remains briefly gated to avoid self-trigger loops and this transcript was not forwarded.' } else { 'Francis is speaking through the browser or ChatGPT voice transport; overlay microphone input is gated to the Francis stop phrase and this transcript was not forwarded.' }
          Write-OverlayVoiceState -Root $script:LensOverlayWakeRoot -Payload $Suppressed
          return
        }
        $CommandWakePhraseDetected = (-not [string]::IsNullOrWhiteSpace($UtteranceText) -or $WakePhraseOnly -or $DirectFrancisAddressDetected)
        $CommandText = if (-not [string]::IsNullOrWhiteSpace($UtteranceText)) { $UtteranceText } elseif ($DirectFrancisAddressDetected) { $RecognizedText } else { $RecognizedText }
        $OrbCommand = Resolve-OverlayVoiceOrbCommand -Text $CommandText -WakePhraseDetected:$CommandWakePhraseDetected
        $ContinuousVoiceCommandAllowed = ([bool]$script:LensOverlayContinuousVoiceChat -and [bool]$ContinuousVoicePushToTalkAllowed)
        if ([bool]$OrbCommand['recognized'] -and ($CommandWakePhraseDetected -or $ContinuousVoiceCommandAllowed)) {
          $script:LensOverlayWakeCount += 1
          $LocalOrbCommandSource = if ($DirectFrancisAddressDetected -and [string]::IsNullOrWhiteSpace($UtteranceText)) { 'local_overlay_direct_francis_address' } else { 'local_overlay_speech_recognition' }
          [void](Invoke-OverlayVoiceOrbCommand -Root $script:LensOverlayWakeRoot -Command $OrbCommand -RecognizedText $RecognizedText -Provider $script:LensOverlayWakeVoiceProvider -Voice $script:LensOverlayWakeVoice -RemoteVoiceId $script:LensOverlayWakeRemoteVoiceId -WakePhraseText $script:LensOverlayWakePhrase -RecognitionConfidence ([double]$EventArgs.Result.Confidence) -RecognitionThreshold $script:LensOverlayWakeConfidenceThreshold -WakeAliasCount $script:LensOverlayWakeAliasCount -WakeCount $script:LensOverlayWakeCount -WakePhraseDetected $CommandWakePhraseDetected -ContinuousVoiceChat $ContinuousVoiceCommandAllowed -CommandSource $LocalOrbCommandSource)
          return
        }
        if ([string]::IsNullOrWhiteSpace($UtteranceText) -and -not $WakePhraseOnly -and -not $DirectFrancisAddressDetected) {
          if ([bool]$script:LensOverlayContinuousVoiceChat) {
            if (-not [bool]$ContinuousVoicePushToTalkAllowed) {
              $Suppressed = New-OverlayVoiceProjection -SelectedVoiceName (Get-OverlaySelectedVoiceName -Provider $script:LensOverlayWakeVoiceProvider -Voice $script:LensOverlayWakeVoice -RequestedVoiceId $script:LensOverlayWakeRemoteVoiceId) -Provider $script:LensOverlayWakeVoiceProvider -WakeListening $true -WakePhraseText $script:LensOverlayWakePhrase
              $Suppressed.status = 'voice_input_suppressed_push_to_talk_inactive'
              $Suppressed.ok = $true
              $Suppressed.wake_phrase_detected = $false
              $Suppressed.direct_francis_address_detected = $false
              Set-OverlayContinuousVoiceChatGateReadback -Payload $Suppressed -ContinuousVoiceChat $true -PushToTalkActive $false
              $Suppressed.continuous_voice_chat_blocker = 'push_to_talk_chord_not_held'
              $Suppressed.required_push_to_talk_chord = 'Ctrl+V'
              $Suppressed.recognition_confidence = [Math]::Round([double]$EventArgs.Result.Confidence, 3)
              $Suppressed.recognition_threshold = $script:LensOverlayWakeConfidenceThreshold
              $Suppressed.transcript_length = $RecognizedText.Length
              $Suppressed.transcript_hash = Get-OverlayTextDigest -Text $RecognizedText
              $Suppressed.transcript_source = 'microphone_continuous_dictation'
              $Suppressed.voice_recognition = 'system_speech_suppressed_push_to_talk_inactive'
              $Suppressed.transcript_redacted = $true
              $Suppressed.stores_transcript = $false
              $Suppressed.speech_output_suppressed = $true
              $Suppressed.conversation_forwarding_suppressed = $true
              $Suppressed.message = 'No-wake continuous voice chat is push-to-talk gated; hold Ctrl+V while speaking or use the Francis wake phrase.'
              Write-OverlayVoiceState -Root $script:LensOverlayWakeRoot -Payload $Suppressed
              return
            }
            $PendingTurnGuard = Get-OverlayContinuousVoiceTurnGuard -Root $script:LensOverlayWakeRoot -MaxPendingSeconds 90
            if (-not [bool]$PendingTurnGuard['allowed']) {
              $Suppressed = New-OverlayVoiceProjection -SelectedVoiceName (Get-OverlaySelectedVoiceName -Provider $script:LensOverlayWakeVoiceProvider -Voice $script:LensOverlayWakeVoice -RequestedVoiceId $script:LensOverlayWakeRemoteVoiceId) -Provider $script:LensOverlayWakeVoiceProvider -WakeListening $true -WakePhraseText $script:LensOverlayWakePhrase
              $Suppressed.status = 'voice_input_suppressed_pending_turn'
              $Suppressed.ok = $true
              $Suppressed.wake_phrase_detected = $false
              $Suppressed.direct_francis_address_detected = $false
              Set-OverlayContinuousVoiceChatGateReadback -Payload $Suppressed -ContinuousVoiceChat $true -PushToTalkActive $true
              $Suppressed.continuous_voice_chat_blocker = [string]$PendingTurnGuard['blocker']
              $Suppressed.pending_voice_turn_guard = $true
              $Suppressed.pending_voice_turn_id = [string]$PendingTurnGuard['active_turn_id']
              $Suppressed.pending_voice_turn_status = [string]$PendingTurnGuard['active_turn_status']
              $Suppressed.pending_voice_turn_age_seconds = [int]$PendingTurnGuard['active_turn_age_seconds']
              $Suppressed.pending_voice_turn_max_seconds = [int]$PendingTurnGuard['max_pending_seconds']
              $Suppressed.recognition_confidence = [Math]::Round([double]$EventArgs.Result.Confidence, 3)
              $Suppressed.recognition_threshold = $script:LensOverlayWakeConfidenceThreshold
              $Suppressed.transcript_length = $RecognizedText.Length
              $Suppressed.transcript_hash = Get-OverlayTextDigest -Text $RecognizedText
              $Suppressed.transcript_source = 'microphone_continuous_dictation'
              $Suppressed.voice_recognition = 'system_speech_suppressed_pending_voice_turn'
              $Suppressed.transcript_redacted = $true
              $Suppressed.stores_transcript = $false
              $Suppressed.speech_output_suppressed = $true
              $Suppressed.conversation_forwarding_suppressed = $true
              $Suppressed.message = 'Continuous microphone dictation is waiting for the active Francis voice turn to finish before forwarding another chat request.'
              Write-OverlayVoiceState -Root $script:LensOverlayWakeRoot -Payload $Suppressed
              return
            }
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
        $AddressedUtteranceText = if (-not [string]::IsNullOrWhiteSpace($UtteranceText)) { $UtteranceText } elseif ($DirectFrancisAddressDetected) { $DirectFrancisUtteranceText } else { '' }
        if (-not [string]::IsNullOrWhiteSpace($AddressedUtteranceText)) {
          [void](Invoke-OverlayVoiceChatTurn -Root $script:LensOverlayWakeRoot -UtteranceText $AddressedUtteranceText -Provider $script:LensOverlayWakeVoiceProvider -Voice $script:LensOverlayWakeVoice -Rate $script:LensOverlayWakeRate -Volume $script:LensOverlayWakeVolume -RemoteVoiceId $script:LensOverlayWakeRemoteVoiceId -RemoteModelId $script:LensOverlayWakeRemoteModelId -RemoteOutputFormat $script:LensOverlayWakeRemoteOutputFormat -RemoteStability $script:LensOverlayWakeRemoteStability -RemoteSimilarityBoost $script:LensOverlayWakeRemoteSimilarityBoost -RemoteStyle $script:LensOverlayWakeRemoteStyle -RemoteSpeed $script:LensOverlayWakeRemoteSpeed -RemoteUseSpeakerBoost $script:LensOverlayWakeRemoteUseSpeakerBoost -WakePhraseText $script:LensOverlayWakePhrase -RecognitionConfidence ([double]$EventArgs.Result.Confidence) -RecognitionThreshold $script:LensOverlayWakeConfidenceThreshold -WakeAliasCount $script:LensOverlayWakeAliasCount -WakeCount $script:LensOverlayWakeCount -WakePhraseDetected $CommandWakePhraseDetected)
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
    Set-OverlayContinuousVoiceChatGateReadback -Payload $Payload -ContinuousVoiceChat $ContinuousVoiceChat -PushToTalkActive (Test-OverlayContinuousVoiceChatPushToTalkActive)
    $Payload.microphone_gate_while_speaking = 'francis_stop_only'
    $Payload.conversation_forwarding_while_speaking = $false
    $Payload.transcript_redacted = $true
    $Payload.message = if ($ContinuousVoiceChat) { 'Explicit wake-phrase listening is active; no-wake voice chat is push-to-talk gated by Ctrl+V.' } else { 'Explicit wake-phrase listening is active for Francis Lens.' }
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
    orb_controls = Get-OverlayOrbControlReadback
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
  $OrbVisual = Add-OrbVisualRingColorContract -OrbVisual $OrbVisual
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
  $StatusOrbControls = if ($null -ne $Status -and $null -ne $Status.PSObject.Properties['orb_controls']) { $Status.PSObject.Properties['orb_controls'].Value } else { $null }
  $OrbControls = if ($null -ne $StatusOrbControls) { $StatusOrbControls } else { Get-OverlayOrbControlReadback }
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
    orb_controls = $OrbControls
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
    orb_controls = $Readback.orb_controls
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

function New-OverlayStoppedVoiceInputReadiness {
  return [ordered]@{
    kind = 'lens.overlay.voice_input_readiness'
    ready = $false
    status = 'not_listening'
    blocker = 'wake_listener_not_active'
    next_operator_step = 'start_overlay_with_wake_listener'
    message = 'Wake listener is not active.'
    wake_listening = $false
    microphone_capture = $false
    microphone_signal_status = 'not_capturing'
    microphone_input_effective = $false
    needs_operator_audio_input_check = $false
    transcript_redacted = $true
    grants_execution_authority = $false
    grants_mutation_authority = $false
  }
}

function New-OverlayStoppedVoiceProviderReadiness {
  return [ordered]@{
    kind = 'lens.overlay.voice_provider_readiness'
    status = 'not_queried'
    message = 'Voice provider readiness was not queried during overlay stop cleanup.'
  }
}

function Write-OverlayStoppedState {
  param(
    [string]$Root,
    [string]$Message = 'Francis Lens overlay window stopped by operator command.'
  )

  $Config = Get-OverlayConfig
  $RuntimeRoot = Join-Path $Root 'runtime\lens-overlay'
  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  $McpBodyState = New-McpBodyStateProjection -McpStatusRoute $Config.mcp_status_route -OrbMcpStatusRoute $Config.orb_mcp_status_route
  $OrbVisual = New-OrbVisualProjection -AutonomousMotion $false
  $OverlayVoice = New-OverlayRuntimeVoiceProjection
  $VoiceInputReadiness = New-OverlayStoppedVoiceInputReadiness
  $Payload = [ordered]@{
    kind = 'lens.overlay.runtime_state'
    status = 'overlay_stopped'
    pid = $PID
    overlay_name = $Config.overlay_name
    overlay_scope = $Config.overlay_scope
    status_route = $Config.status_route
    mcp_status_route = $Config.mcp_status_route
    orb_mcp_status_route = $Config.orb_mcp_status_route
    mcp_body_state = $McpBodyState
    orb_visual = $OrbVisual
    voice = $OverlayVoice
    voice_turn = $null
    overlay_voice = $OverlayVoice
    voice_input_readiness = $VoiceInputReadiness
    voice_input_ready = $false
    voice_input_status = 'not_listening'
    voice_input_blocker = 'wake_listener_not_active'
    next_voice_input_step = 'start_overlay_with_wake_listener'
    voice_provider_readiness = New-OverlayStoppedVoiceProviderReadiness
    overlay_window_visible = $false
    always_on_top = $false
    overlay_position = New-OverlayWindowPositionProjection -Window $null -MotionState $null -OverlayWindowVisible $false
    updated_at = [DateTimeOffset]::UtcNow.ToString('o')
    message = $Message
    governance = [ordered]@{
      execution_authority = $false
      approval_decision_authority = $false
      memory_write = $false
      overlay_control_authority = $false
      window_management_authority = $false
      capture_authority = $false
      new_sensing_authority = $false
      summon_authority = $false
      tray_registration_authority = $false
      service_control_authority = $false
      local_process_launch_authority = $false
      mutation_authority_granted = $false
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

function New-StoppedStatusPayload {
  param(
    [string]$Root,
    [string]$ModeName
  )

  $Config = Get-OverlayConfig
  $RuntimeRoot = Join-Path $Root 'runtime\lens-overlay'
  $PidPath = Join-Path $RuntimeRoot 'lens-overlay.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  $Status = Read-JsonFile -Path $StatusPath
  $RuntimeStateExists = Test-Path -LiteralPath $StatusPath -PathType Leaf
  $PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf
  $RuntimePid = Get-OverlayRuntimePidFromFile -Root $Root
  $RuntimeProcessAlive = if ($RuntimePid -gt 0) { Test-OverlayRuntimeProcess -ProcessId $RuntimePid } else { $false }
  $RuntimeStatus = Get-StringProperty -Payload $Status -Name 'status' -Default 'overlay_stopped'
  $RuntimeStatusKind = Get-StringProperty -Payload $Status -Name 'kind' -Default 'lens.overlay.runtime_state'
  $RuntimeStatusPid = Get-IntegerProperty -Payload $Status -Name 'pid' -Default 0
  $McpStatusRoute = Get-StringProperty -Payload $Status -Name 'mcp_status_route' -Default $Config.mcp_status_route
  $OrbMcpStatusRoute = Get-StringProperty -Payload $Status -Name 'orb_mcp_status_route' -Default $Config.orb_mcp_status_route
  $McpBodyState = New-McpBodyStateProjection -McpStatusRoute $McpStatusRoute -OrbMcpStatusRoute $OrbMcpStatusRoute
  $OrbVisual = New-OrbVisualProjection -AutonomousMotion $false
  $OverlayVoice = New-OverlayRuntimeVoiceProjection
  $VoiceInputReadiness = New-OverlayStoppedVoiceInputReadiness
  $VoiceProviderReadiness = New-OverlayStoppedVoiceProviderReadiness
  $OverlayPosition = New-OverlayWindowPositionProjection -Window $null -MotionState $null -OverlayWindowVisible $false
  $RuntimeReadback = [ordered]@{
    ready = $false
    process_alive = $false
    runtime_process_alive = $RuntimeProcessAlive
    overlay_window_visible = $false
    always_on_top = $false
    pid = $RuntimePid
    pid_present = $PidPresent
    status_path = $StatusPath
    pid_path = $PidPath
    runtime_state_exists = $RuntimeStateExists
    runtime_status = $RuntimeStatus
    runtime_status_kind = $RuntimeStatusKind
    runtime_status_pid = $RuntimeStatusPid
    runtime_status_pid_matches_pid_file = ($RuntimeStatusPid -gt 0 -and $RuntimeStatusPid -eq $RuntimePid)
    overlay_name = Get-StringProperty -Payload $Status -Name 'overlay_name' -Default $Config.overlay_name
    expected_overlay_name = $Config.overlay_name
    overlay_scope = Get-StringProperty -Payload $Status -Name 'overlay_scope' -Default $Config.overlay_scope
    expected_overlay_scope = $Config.overlay_scope
    mcp_status_route = $McpStatusRoute
    orb_mcp_status_route = $OrbMcpStatusRoute
    mcp_body_state_route = $McpStatusRoute
    mcp_body_state = $McpBodyState
    orb_visual = $OrbVisual
    voice = $OverlayVoice
    voice_turn = $null
    overlay_voice = $OverlayVoice
    voice_input_readiness = $VoiceInputReadiness
    voice_input_ready = $false
    voice_input_status = 'not_listening'
    voice_input_blocker = 'wake_listener_not_active'
    next_voice_input_step = 'start_overlay_with_wake_listener'
    voice_provider_readiness = $VoiceProviderReadiness
    overlay_position = $OverlayPosition
    requirement_state = if ($RuntimeStateExists -or $PidPresent) { 'stale_or_unverified' } else { 'missing' }
    blocker = 'overlay_window_runtime_missing'
  }

  return [ordered]@{
    ok = $true
    kind = 'lens.overlay.window.runtime'
    status = 'stopped'
    mode = $ModeName
    ready = $false
    overlay_window = $false
    data_root = $Root
    runtime_state_path = 'data/runtime/lens-overlay/status.json'
    pid_path = 'data/runtime/lens-overlay/lens-overlay.pid'
    mcp_status_route = $McpStatusRoute
    orb_mcp_status_route = $OrbMcpStatusRoute
    mcp_body_state_route = $McpStatusRoute
    mcp_body_state = $McpBodyState
    orb_visual = $OrbVisual
    voice = $OverlayVoice
    voice_turn = $null
    overlay_voice = $OverlayVoice
    voice_input_readiness = $VoiceInputReadiness
    voice_input_ready = $false
    voice_input_status = 'not_listening'
    voice_input_blocker = 'wake_listener_not_active'
    next_voice_input_step = 'start_overlay_with_wake_listener'
    voice_provider_readiness = $VoiceProviderReadiness
    overlay_position = $OverlayPosition
    overlay_runtime = $RuntimeReadback
    next_smallest_truthful_gap = 'overlay_window_runtime'
    governance = [ordered]@{
      read_only_contract = $false
      execution_authority = $false
      approval_decision_authority = $false
      memory_write = $false
      overlay_control_authority = $false
      window_management_authority = $false
      capture_authority = $false
      new_sensing_authority = $false
      summon_authority = $false
      voice_output_authority = $false
      microphone_capture_active = $false
      microphone_capture_authority = $false
      local_process_launch_authority = $false
      tray_registration_authority = $false
      service_control_authority = $false
      mutation_authority_granted = $true
    }
    message = 'Lens overlay window runtime is not live.'
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
  try {
    $ResolvedVoiceText = Read-OverlayVoiceTextInput -Root $DataRoot -Text $VoiceText -TextPath $VoiceTextPath
    $VoicePayload = Invoke-OverlayVoiceChatTurn -Root $DataRoot -UtteranceText $ResolvedVoiceText -Provider $VoiceProvider -Voice $VoiceName -Rate $VoiceRate -Volume $VoiceVolume -RemoteVoiceId $ElevenLabsVoiceId -RemoteModelId $ElevenLabsModelId -RemoteOutputFormat $ElevenLabsOutputFormat -RemoteStability $ElevenLabsStability -RemoteSimilarityBoost $ElevenLabsSimilarityBoost -RemoteStyle $ElevenLabsStyle -RemoteSpeed $ElevenLabsSpeed -RemoteUseSpeakerBoost ([bool]$ElevenLabsUseSpeakerBoost) -WakePhraseText $WakePhrase -RecognitionConfidence 1.0 -RecognitionThreshold $WakeConfidenceThreshold -WakeAliasCount 0 -WakeCount 0 -SyntheticTranscript $true
    $VoicePayload | ConvertTo-Json -Depth 8
    if ([bool]$VoicePayload.ok) {
      exit 0
    }
    exit 2
  } finally {
    Remove-OverlayVoiceTextFile -Root $DataRoot -TextPath $VoiceTextPath
  }
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
  $script:LensOverlayMotionSubscription = $null
  $script:LensOverlayRenderFrameClock = $null
  $script:LensOverlayLastPositionReceiptSeconds = -1.0
  $script:LensOverlayLastOrbVirtualPointerUpdatedAt = ''
  $script:LensOverlayLastOrbVirtualPointerWriteTicks = [Int64]0
  $script:LensOverlayApplication = $null
  $script:LensOverlayOrbPanelPopup = $null
  $script:LensOverlayOrbPanelInput = $null
  $script:LensOverlayOrbPanelStatusText = $null
  $script:LensOverlayOrbPanelWakeCheck = $null
  $script:LensOverlayOrbPanelContinuousCheck = $null
  $script:LensOverlayOrbPanelLlmCheck = $null
  $script:LensOverlayOrbPanelMotionCheck = $null
  $script:LensOverlayOrbPanelSyncing = $false
  $script:LensOverlayOrbControlState = $null
  $script:LensOverlayOrbWindowOffsetTransform = $null
  $script:LensOverlayOrbInWindowOffsetX = 0.0
  $script:LensOverlayOrbInWindowOffsetY = 0.0
  $script:LensOverlayOrbHitBox = $null
  $script:LensOverlayOrbHitBoxSize = 72.0
  $script:LensOverlayOverlayRoot = $null
  $script:LensOverlayOrbDragActive = $false
  $script:LensOverlayHwndSource = $null
  $script:LensOverlayHitTestHook = $null
  $script:LensOverlayAttachHitTestHook = $null
  $script:LensOverlayHitTestPassthroughEnabled = $false
  $script:LensOverlayTopMostPinApplied = $false
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
    $OrbHitBoxSize = Get-OrbHitBoxSize
    $Screen = Get-OverlayVirtualScreenBounds
    $Form = New-Object System.Windows.Window
    $Form.Title = $Config.overlay_name
    $Form.WindowStyle = [System.Windows.WindowStyle]::None
    $Form.ResizeMode = [System.Windows.ResizeMode]::NoResize
    $Form.AllowsTransparency = $true
    $Form.Background = [System.Windows.Media.Brushes]::Transparent
    $Form.ShowInTaskbar = $true
    $Form.TopMost = $true
    $Form.Left = [double]$Screen.Left
    $Form.Top = [double]$Screen.Top
    $Form.Width = [double]$Screen.Width
    $Form.Height = [double]$Screen.Height

    $OverlayRoot = New-Object System.Windows.Controls.Canvas
    $OverlayRoot.Width = [double]$Screen.Width
    $OverlayRoot.Height = [double]$Screen.Height
    $OverlayRoot.Background = [System.Windows.Media.Brushes]::Transparent
    $OverlayRoot.ClipToBounds = $false
    $EnergyRoot = New-OrbEnergySurface -Size $OrbSize -HitBoxSize $OrbHitBoxSize
    $OrbOffsetTransform = New-Object System.Windows.Media.TranslateTransform
    $EnergyRoot.RenderTransform = $OrbOffsetTransform
    $script:LensOverlayOrbWindowOffsetTransform = $OrbOffsetTransform
    [System.Windows.Controls.Canvas]::SetLeft($EnergyRoot, ([double]$Screen.Width / 2.0) - ($OrbSize / 2.0))
    [System.Windows.Controls.Canvas]::SetTop($EnergyRoot, ([double]$Screen.Height / 2.0) - ($OrbSize / 2.0))
    [void]$OverlayRoot.Children.Add($EnergyRoot)
    $OrbClickTarget = $script:LensOverlayOrbHitBox
    if ($null -eq $OrbClickTarget) {
      $OrbClickTarget = $EnergyRoot
    }
    $OrbClickTarget.Cursor = if ($ManualOrbDragEnabled) { [System.Windows.Input.Cursors]::SizeAll } else { [System.Windows.Input.Cursors]::Arrow }
    $OrbClickTarget.Add_MouseRightButtonDown({
        param($Sender, $EventArgs)

        $EventArgs.Handled = $true
        Show-OverlayOrbRightClickPanel -PlacementTarget $Sender
      })
    if ($ManualOrbDragEnabled) {
      $OrbClickTarget.Add_MouseLeftButtonDown({
        param($Sender, $EventArgs)

        try {
          $EventArgs.Handled = $true
          $script:LensOverlayOrbDragActive = $true
          [void]$Sender.CaptureMouse()
          $script:LensOverlayOperatorPositionAnchor = 'operator_manual'
        } catch {
        }
      })
      $OrbClickTarget.Add_MouseMove({
        param($Sender, $EventArgs)

        if (-not [bool]$script:LensOverlayOrbDragActive) {
          return
        }
        try {
          $EventArgs.Handled = $true
          $Point = $EventArgs.GetPosition($script:LensOverlayWindow)
          $TargetX = [double]$script:LensOverlayWindow.Left + [double]$Point.X
          $TargetY = [double]$script:LensOverlayWindow.Top + [double]$Point.Y
          [void](Set-OrbWindowCoordinatePosition -Window $script:LensOverlayWindow -WorkArea $script:LensOverlayWorkArea -X $TargetX -Y $TargetY -MotionState $script:LensOverlayMotionState -TargetAnchor 'operator_manual' -Root $script:LensOverlayDataRoot)
        } catch {
        }
      })
      $OrbClickTarget.Add_MouseLeftButtonUp({
        param($Sender, $EventArgs)

        try {
          $EventArgs.Handled = $true
          $script:LensOverlayOrbDragActive = $false
          $Sender.ReleaseMouseCapture()
        } catch {
        }
      })
      $OrbClickTarget.Add_LostMouseCapture({
        $script:LensOverlayOrbDragActive = $false
      })
    }
    $Form.Content = $OverlayRoot

    $Label = New-Object System.Windows.Controls.Label
    $Label.Content = "Francis Lens`nMCP body-state: $($Config.mcp_status_route)`nLive readback: starting"
    $Label.Visibility = [System.Windows.Visibility]::Collapsed
    $script:LensOverlayLabel = $Label
    $script:LensOverlayWindow = $Form
    $script:LensOverlayEnergyRoot = $EnergyRoot
    $script:LensOverlayOverlayRoot = $OverlayRoot
    $script:LensOverlayMotionState = New-OrbAutonomousMotionState -Window $Form -WorkArea $Screen
    $script:LensOverlayWorkArea = $Screen
    $script:LensOverlayOperatorPositionAnchor = ''
    $script:LensOverlayConfig = $Config
    $script:LensOverlayDataRoot = $DataRoot
    $script:LensOverlayVoiceEnvironmentScope = $VoiceEnvironmentScope
    $script:LensOverlayManualOrbDragEnabled = $ManualOrbDragEnabled
    Register-OverlayOrbHitTestHook -Window $Form -HitBox $OrbClickTarget
    $InitialOrbX = [double]$Screen.Right - ($OrbSize / 2.0) - 48.0
    $InitialOrbY = [double]$Screen.Bottom - ($OrbSize / 2.0) - 48.0
    Set-OrbInWindowOffset -OffsetX ($InitialOrbX - ([double]$Form.Left + ([double]$Form.Width / 2.0))) -OffsetY ($InitialOrbY - ([double]$Form.Top + ([double]$Form.Height / 2.0)))
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
    $script:LensOverlayOrbMovePlaceTimeoutSeconds = $OrbMovePlaceTimeoutSeconds
    $script:LensOverlayOrbMovePlaceModeHandled = $false
    $script:LensOverlayOrbMovePlaceModeResult = $null
    $script:LensOverlayOrbMoveCaptureWindow = $null
    $script:LensOverlayOrbMoveCaptureContext = $null
    $script:LensOverlayOrbMoveCaptureTimeoutTimer = $null
    $script:LensOverlayOrbMoveTravelRenderingHandler = $null
    $script:LensOverlayOrbMoveTravelContext = $null
    $script:LensOverlayRuntimeVoice = New-OverlayRuntimeVoiceProjection -Provider $VoiceProvider -Voice $VoiceName -WakeListening ([bool]$EnableWakeListen) -WakePhraseText $WakePhrase -ConfidenceThreshold $WakeConfidenceThreshold
    $script:LensOverlayRuntimeVoice.voice_llm_enabled = [bool]$EnableVoiceLlm
    $script:LensOverlayRuntimeVoice.voice_llm_request_source = if ($EnableVoiceLlm) { 'EnableVoiceLlm' } else { 'FRANCIS_LENS_VOICE_USE_LLM' }
    Set-OverlayContinuousVoiceChatGateReadback -Payload $script:LensOverlayRuntimeVoice -ContinuousVoiceChat ([bool]$EnableContinuousVoiceChat) -PushToTalkActive (Test-OverlayContinuousVoiceChatPushToTalkActive)
    $script:LensOverlayRuntimeVoice.microphone_gate_while_speaking = 'francis_stop_only'
    $script:LensOverlayRuntimeVoice.conversation_forwarding_while_speaking = $false
    $Form.Add_Loaded({
        [void](Set-OverlayWindowTopMostPinned -Window $script:LensOverlayWindow)
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
          Set-OverlayContinuousVoiceChatGateReadback -Payload $script:LensOverlayRuntimeVoice -ContinuousVoiceChat ([bool]$script:LensOverlayRequestedContinuousVoiceChat) -PushToTalkActive (Test-OverlayContinuousVoiceChatPushToTalkActive)
          $script:LensOverlayRuntimeVoice.microphone_gate_while_speaking = 'francis_stop_only'
          $script:LensOverlayRuntimeVoice.conversation_forwarding_while_speaking = $false
        }
        Publish-DeferredOverlayMcpBodyState -Label $script:LensOverlayLabel -Config $script:LensOverlayConfig -Root $script:LensOverlayDataRoot
      })
    if ($McpRefreshIntervalSeconds -gt 0) {
      $RefreshTimer = New-Object System.Windows.Threading.DispatcherTimer
      $RefreshTimer.Interval = [TimeSpan]::FromSeconds($McpRefreshIntervalSeconds)
      $RefreshTimer.Add_Tick({
          Update-OverlayMcpBodyStateLabelSafely -Label $script:LensOverlayLabel -Config $script:LensOverlayConfig -Root $script:LensOverlayDataRoot
        })
      $RefreshTimer.Start()
    }
    $CommandTimer = New-Object System.Windows.Threading.DispatcherTimer
    $CommandTimer.Interval = [TimeSpan]::FromMilliseconds(500)
    $CommandTimer.Add_Tick({
        [void](Invoke-OverlayOrbVirtualPointerState -Root $script:LensOverlayDataRoot)
        [void](Invoke-OverlayQueuedOrbPositionCommand -Root $script:LensOverlayDataRoot)
      })
    $CommandTimer.Start()
    if ($AutonomousMotionEnabled) {
      $MotionSubscription = Start-OrbFrameSyncedMotion -Window $script:LensOverlayWindow -MotionState $script:LensOverlayMotionState
      $script:LensOverlayMotionSubscription = $MotionSubscription
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
    $script:LensOverlayApplication = $Application
    $Application.ShutdownMode = [System.Windows.ShutdownMode]::OnExplicitShutdown
    $Application.MainWindow = $Form
    $Form.Add_Closed({
        if ($null -ne $script:LensOverlayApplication) {
          $script:LensOverlayApplication.Shutdown()
        }
      })
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
    if ($null -ne $script:LensOverlayMotionSubscription) {
      Stop-OrbFrameSyncedMotion -Subscription $script:LensOverlayMotionSubscription
      $script:LensOverlayMotionSubscription = $null
    } elseif ($null -ne $MotionSubscription) {
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
    if ($null -ne $script:LensOverlayApplication) {
      try {
        $script:LensOverlayApplication.Shutdown()
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
  $RuntimePidToStop = Get-OverlayRuntimePidFromFile -Root $DataRoot
  if ($RuntimePidToStop -gt 0) {
    Stop-OverlayRuntimeProcess -ProcessId $RuntimePidToStop | Out-Null
  }
  Write-OverlayStoppedState -Root $DataRoot -Message 'Francis Lens overlay window stopped by operator command.'
  Remove-Item -LiteralPath (Join-Path $DataRoot 'runtime\lens-overlay\lens-overlay.pid') -Force -ErrorAction SilentlyContinue
  New-StoppedStatusPayload -Root $DataRoot -ModeName $ModeName | ConvertTo-Json -Depth 8
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
  '-McpBodyStateTimeoutSeconds',
  ([string]$McpBodyStateTimeoutSeconds),
  '-McpRefreshIntervalSeconds',
  ([string]$McpRefreshIntervalSeconds),
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
Start-Process -FilePath $PowerShell.Source -ArgumentList $ArgumentText -WindowStyle Normal | Out-Null

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
