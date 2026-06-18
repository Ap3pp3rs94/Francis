[CmdletBinding()]
param(
  [ValidateSet('Probe', 'Run', 'Start', 'Status', 'Stop')]
  [string]$Mode = 'Probe',

  [string]$DataDir = '',

  [string]$CommandPaletteUrl = 'http://127.0.0.1:5173/?francis_lens=command_palette',

  [string]$ApiBaseUrl = 'http://127.0.0.1:8000',

  [string]$ChatUiBaseUrl = 'http://127.0.0.1:5173',

  [string]$LensStatusPath = '',

  [switch]$EnableVoiceChecks,

  [ValidateSet('WindowsSapi', 'ElevenLabs')]
  [string]$VoiceProvider = 'ElevenLabs',

  [string]$ElevenLabsVoiceId = '',

  [string]$ElevenLabsVoiceName = '',

  [ValidateRange(1, 600)]
  [int]$IntervalSeconds = 15,

  [ValidateRange(1, 30)]
  [int]$TimeoutSeconds = 5,

  [ValidateRange(0, 1000000)]
  [int]$MaxIterations = 0,

  [ValidateRange(1, 60)]
  [int]$StartupTimeoutSeconds = 30
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

function Get-MonitorRuntimeRoot {
  param([string]$Root)

  return Join-Path (Join-Path $Root 'runtime') 'lens-command-palette-monitor'
}

function Get-MonitorStatusPath {
  param([string]$Root)

  return Join-Path (Get-MonitorRuntimeRoot -Root $Root) 'status.json'
}

function Get-MonitorPidPath {
  param([string]$Root)

  return Join-Path (Get-MonitorRuntimeRoot -Root $Root) 'monitor.pid'
}

function Get-MonitorAnomalyPath {
  param([string]$Root)

  return Join-Path (Get-MonitorRuntimeRoot -Root $Root) 'anomalies.jsonl'
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

function Write-JsonFile {
  param(
    [string]$Path,
    [object]$Payload
  )

  $Root = Split-Path -Parent $Path
  New-Item -ItemType Directory -Force -Path $Root | Out-Null
  $TempPath = Join-Path $Root ("status.{0}.tmp" -f ([Guid]::NewGuid().ToString('N')))
  try {
    $Json = $Payload | ConvertTo-Json -Depth 12
    $Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($TempPath, $Json, $Utf8NoBom)
    Move-Item -LiteralPath $TempPath -Destination $Path -Force
  } finally {
    Remove-Item -LiteralPath $TempPath -Force -ErrorAction SilentlyContinue
  }
}

function Add-JsonLine {
  param(
    [string]$Path,
    [object]$Payload
  )

  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path) | Out-Null
  $JsonLine = ($Payload | ConvertTo-Json -Depth 12 -Compress) + [Environment]::NewLine
  $Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
  [System.IO.File]::AppendAllText($Path, $JsonLine, $Utf8NoBom)
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

function Set-PropertyValue {
  param(
    [object]$Payload,
    [string]$Name,
    [object]$Value
  )

  if ($Payload -is [System.Collections.IDictionary]) {
    $Payload[$Name] = $Value
    return
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property) {
    $Payload | Add-Member -NotePropertyName $Name -NotePropertyValue $Value -Force
    return
  }
  $Property.Value = $Value
}

function ConvertTo-StringArray {
  param([object]$Value)

  $Items = [System.Collections.ArrayList]::new()
  if ($null -eq $Value) {
    return @($Items.ToArray())
  }
  $RawItems = if ($Value -is [System.Array]) { @($Value) } else { @($Value) }
  foreach ($Item in $RawItems) {
    $Text = [string]$Item
    if (-not [string]::IsNullOrWhiteSpace($Text)) {
      [void]$Items.Add($Text)
    }
  }
  return @($Items.ToArray())
}

function New-MonitorCheck {
  param(
    [string]$Id,
    [bool]$Passed,
    [string]$Status,
    [string]$Evidence
  )

  return [ordered]@{
    id = $Id
    passed = $Passed
    status = $Status
    evidence = $Evidence
  }
}

function Test-MonitorProcess {
  param([int]$ProcessId)

  if ($ProcessId -le 0) {
    return $false
  }
  $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
  if ($null -eq $Process) {
    return $false
  }
  if (-not ([System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT)) {
    return $true
  }
  if ($null -eq (Get-Command -Name Get-CimInstance -ErrorAction SilentlyContinue)) {
    return $true
  }
  $Cim = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
  if ($null -eq $Cim) {
    return $false
  }
  $CommandLine = [string]$Cim.CommandLine
  return ($CommandLine -like '*lens-command-palette-monitor.ps1*' -and $CommandLine -like '*-Mode Run*')
}

function Invoke-CommandPaletteBridge {
  param(
    [string]$ApiBaseUrl,
    [string]$ChatUiBaseUrl,
    [string]$LensStatusPath,
    [int]$TimeoutSeconds
  )

  $Arguments = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    (Join-Path $PSScriptRoot 'lens-command-palette.ps1'),
    '-Mode',
    'Status',
    '-ApiBaseUrl',
    $ApiBaseUrl,
    '-ChatUiBaseUrl',
    $ChatUiBaseUrl,
    '-TimeoutSeconds',
    ([string]$TimeoutSeconds)
  )
  if (-not [string]::IsNullOrWhiteSpace($LensStatusPath)) {
    $Arguments += @('-StatusPath', $LensStatusPath)
  }

  $PowerShell = Get-Command powershell -ErrorAction SilentlyContinue
  if ($null -eq $PowerShell) {
    $PowerShell = Get-Command pwsh -ErrorAction Stop
  }

  $Output = & $PowerShell.Source @Arguments 2>&1
  $ExitCode = $LASTEXITCODE
  $Text = ($Output | ForEach-Object { [string]$_ }) -join "`n"
  try {
    $Payload = $Text | ConvertFrom-Json -ErrorAction Stop
    return [ordered]@{
      ok = ($ExitCode -eq 0)
      exit_code = $ExitCode
      payload = $Payload
      error = ''
      raw_length = $Text.Length
    }
  } catch {
    return [ordered]@{
      ok = $false
      exit_code = $ExitCode
      payload = $null
      error = [string]$_.Exception.Message
      raw_length = $Text.Length
    }
  }
}

function Invoke-CommandPaletteHttpProbe {
  param(
    [string]$Url,
    [int]$TimeoutSeconds
  )

  try {
    $Response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec $TimeoutSeconds -ErrorAction Stop
    $Body = [string]$Response.Content
    $RootPresent = ($Body -like '*id="root"*' -or $Body -like "*id='root'*")
    return [ordered]@{
      ok = ($Response.StatusCode -eq 200 -and $RootPresent)
      status_code = [int]$Response.StatusCode
      content_length = $Body.Length
      root_mount_present = $RootPresent
      error = ''
    }
  } catch {
    return [ordered]@{
      ok = $false
      status_code = 0
      content_length = 0
      root_mount_present = $false
      error = [string]$_.Exception.Message
    }
  }
}

function Invoke-OverlayVoiceReadback {
  param(
    [string]$Root,
    [string]$Provider,
    [string]$RemoteVoiceId,
    [string]$RemoteVoiceName
  )

  $Arguments = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    (Join-Path $PSScriptRoot 'lens-overlay-window.ps1'),
    '-Mode',
    'Status',
    '-DataDir',
    $Root,
    '-VoiceEnvironmentScope',
    'All',
    '-VoiceProvider',
    $Provider
  )
  if (-not [string]::IsNullOrWhiteSpace($RemoteVoiceId)) {
    $Arguments += @('-ElevenLabsVoiceId', $RemoteVoiceId)
  }
  if (-not [string]::IsNullOrWhiteSpace($RemoteVoiceName)) {
    $Arguments += @('-ElevenLabsVoiceName', $RemoteVoiceName)
  }

  $PowerShell = Get-Command powershell -ErrorAction SilentlyContinue
  if ($null -eq $PowerShell) {
    $PowerShell = Get-Command pwsh -ErrorAction Stop
  }

  $Output = & $PowerShell.Source @Arguments 2>&1
  $ExitCode = $LASTEXITCODE
  $Text = ($Output | ForEach-Object { [string]$_ }) -join "`n"
  try {
    $Payload = $Text | ConvertFrom-Json -ErrorAction Stop
    return [ordered]@{
      ok = ($ExitCode -eq 0)
      exit_code = $ExitCode
      payload = $Payload
      error = ''
      raw_length = $Text.Length
    }
  } catch {
    return [ordered]@{
      ok = $false
      exit_code = $ExitCode
      payload = $null
      error = [string]$_.Exception.Message
      raw_length = $Text.Length
    }
  }
}

function Get-RecentChatGptVoiceReceipts {
  param(
    [string]$Root,
    [int]$Limit = 5
  )

  $ReceiptRoot = Join-Path $Root 'integrations\chatgpt_voice\receipts'
  if (-not (Test-Path -LiteralPath $ReceiptRoot -PathType Container)) {
    return @()
  }
  $Items = [System.Collections.ArrayList]::new()
  $Files = @(Get-ChildItem -LiteralPath $ReceiptRoot -Filter '*.json' -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First $Limit)
  foreach ($File in $Files) {
    $Payload = Read-JsonFile -Path $File.FullName
    if ($null -ne $Payload) {
      Set-PropertyValue -Payload $Payload -Name 'receipt_path' -Value $File.FullName
      [void]$Items.Add($Payload)
    }
  }
  return @($Items.ToArray())
}

function New-VoiceMonitorProjection {
  param(
    [string]$Root,
    [string]$Provider,
    [string]$RemoteVoiceId,
    [string]$RemoteVoiceName
  )

  $Readback = Invoke-OverlayVoiceReadback -Root $Root -Provider $Provider -RemoteVoiceId $RemoteVoiceId -RemoteVoiceName $RemoteVoiceName
  $Payload = Get-PropertyValue -Payload $Readback -Name 'payload'
  $OverlayVoice = Get-PropertyValue -Payload $Payload -Name 'overlay_voice'
  $Voice = Get-PropertyValue -Payload $Payload -Name 'voice'
  $VoiceTurn = Get-PropertyValue -Payload $Payload -Name 'voice_turn'
  $ProviderReadiness = Get-PropertyValue -Payload $Payload -Name 'voice_provider_readiness'
  $ElevenLabs = Get-PropertyValue -Payload $ProviderReadiness -Name 'elevenlabs'
  $Receipts = @(Get-RecentChatGptVoiceReceipts -Root $Root -Limit 5)

  $SelectedProvider = [string](Get-PropertyValue -Payload $ProviderReadiness -Name 'selected_provider' -Default $Provider)
  $ActiveProviderConfigured = [bool](Get-PropertyValue -Payload $ProviderReadiness -Name 'active_provider_configured' -Default $false)
  $VoiceLabel = [string](Get-PropertyValue -Payload $ElevenLabs -Name 'voice_label' -Default '')
  $SelectedVoice = [string](Get-PropertyValue -Payload $OverlayVoice -Name 'selected_voice' -Default '')
  $VoiceStatus = [string](Get-PropertyValue -Payload $Voice -Name 'status' -Default '')
  $VoiceError = [string](Get-PropertyValue -Payload $Voice -Name 'error' -Default '')
  $VoiceChatError = [string](Get-PropertyValue -Payload $Voice -Name 'chat_error' -Default '')
  $TurnChatError = [string](Get-PropertyValue -Payload $VoiceTurn -Name 'chat_error' -Default '')
  $TurnBridgeStatus = [string](Get-PropertyValue -Payload $VoiceTurn -Name 'chat_bridge_status' -Default '')
  $OverlayBridgeStatus = [string](Get-PropertyValue -Payload $OverlayVoice -Name 'chat_bridge_status' -Default '')
  $LatestReceipt = if (@($Receipts).Count -gt 0) { $Receipts[0] } else { $null }
  $IdentityOk = (
    [string](Get-PropertyValue -Payload $OverlayVoice -Name 'voice_lens_orb_identity' -Default 'Francis') -eq 'Francis' -or
    [bool](Get-PropertyValue -Payload $OverlayVoice -Name 'voice_lens_orb_are_francis_surfaces' -Default $false)
  )
  $GenericVoiceLabel = ($SelectedProvider -eq 'ElevenLabs' -and ($SelectedVoice -in @('elevenlabs', 'wake-listener') -or $VoiceLabel -in @('', 'elevenlabs')))
  $PermissionDenied = (
    $VoiceError -eq 'api_permission_denied' -or
    $VoiceChatError -eq 'api_permission_denied' -or
    $TurnChatError -eq 'api_permission_denied'
  )
  $DeniedReceipts = @(
    $Receipts | Where-Object {
      [string](Get-PropertyValue -Payload $_ -Name 'chat_forward_status' -Default '') -eq 'denied' -or
      [string](Get-PropertyValue -Payload $_ -Name 'chat_forward_error' -Default '') -eq 'api_permission_denied' -or
      [string](Get-PropertyValue -Payload $_ -Name 'error' -Default '') -eq 'api_permission_denied'
    }
  )
  $LatestReceiptDenied = (
    $null -ne $LatestReceipt -and (
      [string](Get-PropertyValue -Payload $LatestReceipt -Name 'chat_forward_status' -Default '') -eq 'denied' -or
      [string](Get-PropertyValue -Payload $LatestReceipt -Name 'chat_forward_error' -Default '') -eq 'api_permission_denied' -or
      [string](Get-PropertyValue -Payload $LatestReceipt -Name 'error' -Default '') -eq 'api_permission_denied'
    )
  )

  return [ordered]@{
    enabled = $true
    ok = [bool](Get-PropertyValue -Payload $Readback -Name 'ok' -Default $false)
    exit_code = [int](Get-PropertyValue -Payload $Readback -Name 'exit_code' -Default 0)
    error = [string](Get-PropertyValue -Payload $Readback -Name 'error' -Default '')
    selected_provider = $SelectedProvider
    active_provider_configured = $ActiveProviderConfigured
    selected_voice = $SelectedVoice
    voice_label = $VoiceLabel
    voice_identity_ok = [bool]$IdentityOk
    generic_voice_label_observed = [bool]$GenericVoiceLabel
    overlay_status = [string](Get-PropertyValue -Payload $Payload -Name 'status' -Default '')
    overlay_ready = [bool](Get-PropertyValue -Payload $Payload -Name 'ready' -Default $false)
    overlay_voice_status = [string](Get-PropertyValue -Payload $OverlayVoice -Name 'status' -Default '')
    voice_status = $VoiceStatus
    voice_error = $VoiceError
    voice_chat_error = $VoiceChatError
    voice_turn_status = [string](Get-PropertyValue -Payload $VoiceTurn -Name 'status' -Default '')
    voice_turn_chat_error = $TurnChatError
    voice_turn_bridge_status = $TurnBridgeStatus
    overlay_bridge_status = $OverlayBridgeStatus
    api_permission_denied_observed = [bool]$PermissionDenied
    recent_receipt_count = @($Receipts).Count
    denied_recent_receipt_count = @($DeniedReceipts).Count
    latest_receipt_denied = [bool]$LatestReceiptDenied
    latest_receipt_status = if ($null -ne $LatestReceipt) { [string](Get-PropertyValue -Payload $LatestReceipt -Name 'status' -Default '') } else { '' }
    latest_receipt_chat_forward_status = if ($null -ne $LatestReceipt) { [string](Get-PropertyValue -Payload $LatestReceipt -Name 'chat_forward_status' -Default '') } else { '' }
    latest_receipt_chat_forward_error = if ($null -ne $LatestReceipt) { [string](Get-PropertyValue -Payload $LatestReceipt -Name 'chat_forward_error' -Default '') } else { '' }
    status_path = 'data/runtime/lens-overlay/status.json'
    voice_status_path = 'data/runtime/lens-overlay/voice-status.json'
    voice_turn_status_path = 'data/runtime/lens-overlay/voice-turn-status.json'
    receipt_root = 'data/integrations/chatgpt_voice/receipts'
    governance = [ordered]@{
      read_only_contract = $true
      controls_overlay = $false
      captures_audio = $false
      captures_screen = $false
      execution_authority = $false
      mutation_authority_granted = $false
    }
  }
}

function New-CommandPaletteMonitorProbe {
  param(
    [string]$Root,
    [string]$CommandPaletteUrl,
    [string]$ApiBaseUrl,
    [string]$ChatUiBaseUrl,
    [string]$LensStatusPath,
    [int]$TimeoutSeconds,
    [bool]$VoiceChecksEnabled,
    [string]$VoiceChecksProvider,
    [string]$VoiceChecksRemoteVoiceId,
    [string]$VoiceChecksRemoteVoiceName
  )

  $Bridge = Invoke-CommandPaletteBridge -ApiBaseUrl $ApiBaseUrl -ChatUiBaseUrl $ChatUiBaseUrl -LensStatusPath $LensStatusPath -TimeoutSeconds $TimeoutSeconds
  $BridgePayload = Get-PropertyValue -Payload $Bridge -Name 'payload'
  $Http = Invoke-CommandPaletteHttpProbe -Url $CommandPaletteUrl -TimeoutSeconds $TimeoutSeconds
  $VoiceMonitor = if ($VoiceChecksEnabled) {
    New-VoiceMonitorProjection -Root $Root -Provider $VoiceChecksProvider -RemoteVoiceId $VoiceChecksRemoteVoiceId -RemoteVoiceName $VoiceChecksRemoteVoiceName
  } else {
    [ordered]@{ enabled = $false }
  }
  $CommandTotal = [int](Get-PropertyValue -Payload $BridgePayload -Name 'command_total' -Default 0)
  $UrlEntrypoint = Get-PropertyValue -Payload $BridgePayload -Name 'url_entrypoint'
  $BridgeGovernance = Get-PropertyValue -Payload $BridgePayload -Name 'governance'

  $ExpectedRoute = '/?francis_lens=command_palette'
  $Route = [string](Get-PropertyValue -Payload $UrlEntrypoint -Name 'route' -Default '')
  $LocalSurface = [string](Get-PropertyValue -Payload $UrlEntrypoint -Name 'local_surface' -Default '')
  $OpensPalette = [bool](Get-PropertyValue -Payload $UrlEntrypoint -Name 'opens_palette_in_chat_ui' -Default $false)
  $ReadbackReady = [bool](Get-PropertyValue -Payload $BridgePayload -Name 'readback_ready' -Default $false)
  $LocalOpenAvailable = [bool](Get-PropertyValue -Payload $BridgePayload -Name 'local_open_available' -Default $false)
  $ExecutionAuthority = [bool](Get-PropertyValue -Payload $BridgeGovernance -Name 'execution_authority' -Default $true)
  $MutationAuthority = [bool](Get-PropertyValue -Payload $BridgeGovernance -Name 'mutation_authority_granted' -Default $true)
  $OpensPaletteFromBridge = [bool](Get-PropertyValue -Payload $BridgeGovernance -Name 'opens_palette' -Default $true)

  $Anomalies = [System.Collections.ArrayList]::new()
  $Checks = [System.Collections.ArrayList]::new()

  [void]$Checks.Add((New-MonitorCheck -Id 'chat_ui_command_palette_url' -Passed ([bool](Get-PropertyValue -Payload $Http -Name 'ok' -Default $false)) -Status $(if ([bool](Get-PropertyValue -Payload $Http -Name 'ok' -Default $false)) { 'reachable' } else { 'unreachable' }) -Evidence $CommandPaletteUrl))
  [void]$Checks.Add((New-MonitorCheck -Id 'command_palette_bridge' -Passed ([bool](Get-PropertyValue -Payload $Bridge -Name 'ok' -Default $false)) -Status $(if ([bool](Get-PropertyValue -Payload $Bridge -Name 'ok' -Default $false)) { 'available' } else { 'unavailable' }) -Evidence 'scripts/lens-command-palette.ps1 -Mode Status'))
  [void]$Checks.Add((New-MonitorCheck -Id 'command_palette_readback' -Passed $ReadbackReady -Status $(if ($ReadbackReady) { 'readback_ready' } else { 'not_ready' }) -Evidence ([string](Get-PropertyValue -Payload $BridgePayload -Name 'route' -Default ''))))
  [void]$Checks.Add((New-MonitorCheck -Id 'command_palette_url_entrypoint' -Passed ($LocalOpenAvailable -and $Route -eq $ExpectedRoute -and $LocalSurface -eq 'chat_ui.command_palette' -and $OpensPalette) -Status $(if ($LocalOpenAvailable) { 'ready' } else { 'not_ready' }) -Evidence $Route))
  [void]$Checks.Add((New-MonitorCheck -Id 'command_palette_commands' -Passed ($CommandTotal -gt 0) -Status $(if ($CommandTotal -gt 0) { 'commands_present' } else { 'commands_missing' }) -Evidence ([string]$CommandTotal)))
  [void]$Checks.Add((New-MonitorCheck -Id 'command_palette_governance' -Passed ((-not $ExecutionAuthority) -and (-not $MutationAuthority) -and (-not $OpensPaletteFromBridge)) -Status 'read_only' -Evidence 'execution=false mutation=false opens_palette=false'))
  if ($VoiceChecksEnabled) {
    $VoiceReadbackOk = [bool](Get-PropertyValue -Payload $VoiceMonitor -Name 'ok' -Default $false)
    $VoiceProviderReady = if ($VoiceChecksProvider -eq 'ElevenLabs') { [bool](Get-PropertyValue -Payload $VoiceMonitor -Name 'active_provider_configured' -Default $false) } else { $true }
    $VoiceIdentityOk = [bool](Get-PropertyValue -Payload $VoiceMonitor -Name 'voice_identity_ok' -Default $false)
    $GenericVoiceLabelObserved = [bool](Get-PropertyValue -Payload $VoiceMonitor -Name 'generic_voice_label_observed' -Default $false)
    $VoicePermissionDenied = [bool](Get-PropertyValue -Payload $VoiceMonitor -Name 'api_permission_denied_observed' -Default $false)
    $LatestReceiptDenied = [bool](Get-PropertyValue -Payload $VoiceMonitor -Name 'latest_receipt_denied' -Default $false)
    $DeniedRecentReceiptCount = [int](Get-PropertyValue -Payload $VoiceMonitor -Name 'denied_recent_receipt_count' -Default 0)
    [void]$Checks.Add((New-MonitorCheck -Id 'voice_overlay_readback' -Passed $VoiceReadbackOk -Status $(if ($VoiceReadbackOk) { 'readback_ready' } else { 'readback_failed' }) -Evidence 'scripts/lens-overlay-window.ps1 -Mode Status'))
    [void]$Checks.Add((New-MonitorCheck -Id 'voice_provider_readiness' -Passed $VoiceProviderReady -Status $(if ($VoiceProviderReady) { 'configured' } else { 'not_configured' }) -Evidence ([string](Get-PropertyValue -Payload $VoiceMonitor -Name 'selected_provider' -Default ''))))
    [void]$Checks.Add((New-MonitorCheck -Id 'voice_francis_identity' -Passed ($VoiceIdentityOk -and -not $GenericVoiceLabelObserved) -Status $(if ($VoiceIdentityOk -and -not $GenericVoiceLabelObserved) { 'francis_voice_identity_ready' } else { 'identity_drift' }) -Evidence ([string](Get-PropertyValue -Payload $VoiceMonitor -Name 'selected_voice' -Default ''))))
    [void]$Checks.Add((New-MonitorCheck -Id 'voice_chat_bridge_denials' -Passed ((-not $VoicePermissionDenied) -and (-not $LatestReceiptDenied)) -Status $(if ((-not $VoicePermissionDenied) -and (-not $LatestReceiptDenied)) { 'latest_receipt_clean' } else { 'denial_observed' }) -Evidence ("latest_denied={0} recent_denied={1}" -f $LatestReceiptDenied, $DeniedRecentReceiptCount)))
  }

  foreach ($Check in @($Checks.ToArray())) {
    if (-not [bool](Get-PropertyValue -Payload $Check -Name 'passed' -Default $false)) {
      [void]$Anomalies.Add([ordered]@{
          id = [string](Get-PropertyValue -Payload $Check -Name 'id' -Default 'unknown_check')
          status = [string](Get-PropertyValue -Payload $Check -Name 'status' -Default 'failed')
          evidence = [string](Get-PropertyValue -Payload $Check -Name 'evidence' -Default '')
        })
    }
  }

  $UrlShapeOk = ($CommandPaletteUrl -match '[?&]francis_lens=command_palette' -or $CommandPaletteUrl -match '[?&]lens_palette=(open|command_palette)')
  if (-not $UrlShapeOk) {
    [void]$Anomalies.Add([ordered]@{
        id = 'command_palette_url_shape'
        status = 'unexpected_url'
        evidence = $CommandPaletteUrl
      })
  }

  $KnownRoadmapBlockers = @('os_level_command_palette_missing', 'summon_anywhere_missing', 'global_hotkey_binding_missing')
  $BridgeBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $BridgePayload -Name 'blockers' -Default @())
  $UnexpectedBlockers = @($BridgeBlockers | Where-Object { $_ -notin $KnownRoadmapBlockers })
  if (@($UnexpectedBlockers).Count -gt 0) {
    [void]$Anomalies.Add([ordered]@{
        id = 'command_palette_unexpected_blockers'
        status = 'unexpected_blockers'
        evidence = (@($UnexpectedBlockers) -join ',')
      })
  }

  $Status = if (@($Anomalies.ToArray()).Count -gt 0) { 'anomaly' } else { 'healthy' }
  return [ordered]@{
    ok = ($Status -eq 'healthy')
    kind = 'lens.command_palette.monitor'
    status = $Status
    mode = $Mode.ToLowerInvariant()
    pid = $PID
    command_palette_url = $CommandPaletteUrl
    api_base_url = $ApiBaseUrl
    chat_ui_base_url = $ChatUiBaseUrl
    checked_at = [DateTimeOffset]::UtcNow.ToString('o')
    anomaly_count = @($Anomalies.ToArray()).Count
    anomalies = @($Anomalies.ToArray())
    checks = @($Checks.ToArray())
    http_probe = $Http
    bridge = [ordered]@{
      ok = [bool](Get-PropertyValue -Payload $Bridge -Name 'ok' -Default $false)
      exit_code = [int](Get-PropertyValue -Payload $Bridge -Name 'exit_code' -Default 0)
      error = [string](Get-PropertyValue -Payload $Bridge -Name 'error' -Default '')
      readback_ready = $ReadbackReady
      local_open_available = $LocalOpenAvailable
      route = $Route
      local_surface = $LocalSurface
      command_total = $CommandTotal
      availability = [string](Get-PropertyValue -Payload $BridgePayload -Name 'availability' -Default '')
      expected_roadmap_blockers = @($KnownRoadmapBlockers)
      observed_blockers = @($BridgeBlockers)
    }
    voice_monitor = $VoiceMonitor
    reporting = [ordered]@{
      status_path = 'data/runtime/lens-command-palette-monitor/status.json'
      anomaly_log_path = 'data/runtime/lens-command-palette-monitor/anomalies.jsonl'
      report_mode = 'poll_status_or_tail_anomaly_log'
    }
    governance = [ordered]@{
      read_only_contract = $true
      opens_browser = $false
      registers_hotkey = $false
      controls_overlay = $false
      execution_authority = $false
      mutation_authority_granted = $false
      memory_write = $false
      captures_screen = $false
      captures_audio = $false
      hidden_sensing = $false
    }
    message = if ($Status -eq 'healthy') { 'Command palette monitor observed the local URL and Lens readback contract without anomalies.' } else { 'Command palette monitor observed anomaly evidence; inspect anomalies and the anomaly log.' }
  }
}

$DataRoot = Get-DataRoot -Override $DataDir
$RuntimeRoot = Get-MonitorRuntimeRoot -Root $DataRoot
$StatusPath = Get-MonitorStatusPath -Root $DataRoot
$PidPath = Get-MonitorPidPath -Root $DataRoot
$AnomalyPath = Get-MonitorAnomalyPath -Root $DataRoot
New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null

if ($Mode -eq 'Status') {
  $State = Read-JsonFile -Path $StatusPath
  $RecordedPid = 0
  if (Test-Path -LiteralPath $PidPath -PathType Leaf) {
    try {
      $RecordedPid = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
    } catch {
      $RecordedPid = 0
    }
  }
  $ProcessAlive = Test-MonitorProcess -ProcessId $RecordedPid
  if ($null -eq $State) {
    $State = [ordered]@{
      ok = $false
      kind = 'lens.command_palette.monitor'
      status = 'missing'
      mode = 'status'
      anomaly_count = 0
      anomalies = @()
      checks = @()
    }
  }
  Set-PropertyValue -Payload $State -Name 'mode' -Value 'status'
  Set-PropertyValue -Payload $State -Name 'monitor_process_alive' -Value $ProcessAlive
  Set-PropertyValue -Payload $State -Name 'monitor_pid' -Value $RecordedPid
  Set-PropertyValue -Payload $State -Name 'status_path' -Value $StatusPath
  Set-PropertyValue -Payload $State -Name 'anomaly_log_path' -Value $AnomalyPath
  $State | ConvertTo-Json -Depth 12
  exit 0
}

if ($Mode -eq 'Stop') {
  $RecordedPid = 0
  if (Test-Path -LiteralPath $PidPath -PathType Leaf) {
    try {
      $RecordedPid = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
    } catch {
      $RecordedPid = 0
    }
  }
  $Stopped = $false
  if (Test-MonitorProcess -ProcessId $RecordedPid) {
    Stop-Process -Id $RecordedPid -Force -ErrorAction SilentlyContinue
    $Stopped = $true
  }
  Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
  $Payload = [ordered]@{
    ok = $true
    kind = 'lens.command_palette.monitor'
    status = 'stopped'
    mode = 'stop'
    monitor_pid = $RecordedPid
    stopped = $Stopped
    status_path = $StatusPath
    anomaly_log_path = $AnomalyPath
    governance = [ordered]@{
      stops_own_monitor_process_only = $true
      execution_authority = $false
      mutation_authority_granted = $false
      process_control_scope = 'own_monitor_process_only'
    }
  }
  Write-JsonFile -Path $StatusPath -Payload $Payload
  $Payload | ConvertTo-Json -Depth 8
  exit 0
}

if ($Mode -eq 'Probe') {
  $Payload = New-CommandPaletteMonitorProbe -Root $DataRoot -CommandPaletteUrl $CommandPaletteUrl -ApiBaseUrl $ApiBaseUrl -ChatUiBaseUrl $ChatUiBaseUrl -LensStatusPath $LensStatusPath -TimeoutSeconds $TimeoutSeconds -VoiceChecksEnabled ([bool]$EnableVoiceChecks) -VoiceChecksProvider $VoiceProvider -VoiceChecksRemoteVoiceId $ElevenLabsVoiceId -VoiceChecksRemoteVoiceName $ElevenLabsVoiceName
  Write-JsonFile -Path $StatusPath -Payload $Payload
  if ([int]$Payload.anomaly_count -gt 0) {
    Add-JsonLine -Path $AnomalyPath -Payload $Payload
  }
  $Payload | ConvertTo-Json -Depth 12
  if ([bool]$Payload.ok) {
    exit 0
  }
  exit 1
}

if ($Mode -eq 'Start') {
  $ExistingPid = 0
  if (Test-Path -LiteralPath $PidPath -PathType Leaf) {
    try {
      $ExistingPid = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
    } catch {
      $ExistingPid = 0
    }
  }
  if (Test-MonitorProcess -ProcessId $ExistingPid) {
    $Payload = Read-JsonFile -Path $StatusPath
    if ($null -eq $Payload) {
      $Payload = [ordered]@{
        ok = $true
        kind = 'lens.command_palette.monitor'
        status = 'already_running'
      }
    }
    Set-PropertyValue -Payload $Payload -Name 'mode' -Value 'start'
    Set-PropertyValue -Payload $Payload -Name 'status' -Value 'already_running'
    Set-PropertyValue -Payload $Payload -Name 'monitor_pid' -Value $ExistingPid
    $Payload | ConvertTo-Json -Depth 12
    exit 0
  }

  $PowerShell = Get-Command powershell -ErrorAction SilentlyContinue
  if ($null -eq $PowerShell) {
    $PowerShell = Get-Command pwsh -ErrorAction Stop
  }
  $Arguments = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $PSCommandPath,
    '-Mode',
    'Run',
    '-DataDir',
    $DataRoot,
    '-CommandPaletteUrl',
    $CommandPaletteUrl,
    '-ApiBaseUrl',
    $ApiBaseUrl,
    '-ChatUiBaseUrl',
    $ChatUiBaseUrl,
    '-IntervalSeconds',
    ([string]$IntervalSeconds),
    '-TimeoutSeconds',
    ([string]$TimeoutSeconds),
    '-MaxIterations',
    ([string]$MaxIterations)
  )
  if (-not [string]::IsNullOrWhiteSpace($LensStatusPath)) {
    $Arguments += @('-LensStatusPath', $LensStatusPath)
  }
  if ($EnableVoiceChecks) {
    $Arguments += @('-EnableVoiceChecks', '-VoiceProvider', $VoiceProvider)
    if (-not [string]::IsNullOrWhiteSpace($ElevenLabsVoiceId)) {
      $Arguments += @('-ElevenLabsVoiceId', $ElevenLabsVoiceId)
    }
    if (-not [string]::IsNullOrWhiteSpace($ElevenLabsVoiceName)) {
      $Arguments += @('-ElevenLabsVoiceName', $ElevenLabsVoiceName)
    }
  }
  $Process = Start-Process -FilePath $PowerShell.Source -ArgumentList $Arguments -WindowStyle Hidden -PassThru
  Set-Content -LiteralPath $PidPath -Value ([string]$Process.Id) -Encoding UTF8

  $Deadline = [DateTimeOffset]::UtcNow.AddSeconds($StartupTimeoutSeconds)
  do {
    Start-Sleep -Milliseconds 250
    $State = Read-JsonFile -Path $StatusPath
    if ($null -ne $State -and [int](Get-PropertyValue -Payload $State -Name 'pid' -Default 0) -eq [int]$Process.Id) {
      Set-PropertyValue -Payload $State -Name 'mode' -Value 'start'
      Set-PropertyValue -Payload $State -Name 'monitor_pid' -Value ([int]$Process.Id)
      Set-PropertyValue -Payload $State -Name 'monitor_process_alive' -Value (Test-MonitorProcess -ProcessId ([int]$Process.Id))
      $State | ConvertTo-Json -Depth 12
      exit 0
    }
  } while ([DateTimeOffset]::UtcNow -lt $Deadline)

  $ProcessAlive = Test-MonitorProcess -ProcessId ([int]$Process.Id)
  $Payload = [ordered]@{
    ok = [bool]$ProcessAlive
    kind = 'lens.command_palette.monitor'
    status = if ($ProcessAlive) { 'starting' } else { 'start_timeout' }
    mode = 'start'
    monitor_pid = [int]$Process.Id
    monitor_process_alive = [bool]$ProcessAlive
    first_probe_pending = [bool]$ProcessAlive
    error = if ($ProcessAlive) { '' } else { 'lens_command_palette_monitor_start_timeout' }
    status_path = $StatusPath
    anomaly_log_path = $AnomalyPath
    message = if ($ProcessAlive) { 'Command palette monitor process started; first probe has not written a status receipt yet.' } else { 'Command palette monitor did not report a live process before startup timeout.' }
  }
  Write-JsonFile -Path $StatusPath -Payload $Payload
  $Payload | ConvertTo-Json -Depth 8
  if ($ProcessAlive) {
    exit 0
  }
  exit 1
}

if ($Mode -eq 'Run') {
  Set-Content -LiteralPath $PidPath -Value ([string]$PID) -Encoding UTF8
  $Iteration = 0
  while ($true) {
    $Iteration += 1
    $Payload = New-CommandPaletteMonitorProbe -Root $DataRoot -CommandPaletteUrl $CommandPaletteUrl -ApiBaseUrl $ApiBaseUrl -ChatUiBaseUrl $ChatUiBaseUrl -LensStatusPath $LensStatusPath -TimeoutSeconds $TimeoutSeconds -VoiceChecksEnabled ([bool]$EnableVoiceChecks) -VoiceChecksProvider $VoiceProvider -VoiceChecksRemoteVoiceId $ElevenLabsVoiceId -VoiceChecksRemoteVoiceName $ElevenLabsVoiceName
    Set-PropertyValue -Payload $Payload -Name 'mode' -Value 'run'
    Set-PropertyValue -Payload $Payload -Name 'iteration' -Value $Iteration
    Write-JsonFile -Path $StatusPath -Payload $Payload
    if ([int]$Payload.anomaly_count -gt 0) {
      Add-JsonLine -Path $AnomalyPath -Payload $Payload
      Write-Output ("ANOMALY command_palette anomaly_count={0} status_path={1}" -f $Payload.anomaly_count, $StatusPath)
    }
    if ($MaxIterations -gt 0 -and $Iteration -ge $MaxIterations) {
      break
    }
    Start-Sleep -Seconds $IntervalSeconds
  }
  exit 0
}
