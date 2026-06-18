[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [string]$ConnectorRuntimeRoot = '',

  [string]$ConnectorHostAddress = '127.0.0.1',

  [int]$ConnectorPort = 8787,

  [string]$ConnectorUrl = '',

  [switch]$VerifyConnector,

  [ValidateRange(1, 60)]
  [int]$ConnectorProbeTimeoutSeconds = 5,

  [ValidateRange(1, 86400)]
  [int]$ChatGptReceiptFreshnessSeconds = 900,

  [ValidateRange(1, 100)]
  [int]$ReceiptLimit = 10
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

if ([string]::IsNullOrWhiteSpace($DataDir)) {
  $DataDir = Join-Path $RepoRoot 'data'
}
$DataRoot = [System.IO.Path]::GetFullPath($DataDir)
if ([string]::IsNullOrWhiteSpace($ConnectorRuntimeRoot)) {
  $ConnectorRuntimeRoot = Join-Path $DataRoot 'runtime\chatgpt-voice-connector'
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

function Get-NestedPropertyValue {
  param(
    [object]$Payload,
    [string[]]$Path,
    [object]$Default = $null
  )

  $Current = $Payload
  foreach ($Name in $Path) {
    $Current = Get-PropertyValue -Payload $Current -Name $Name -Default $null
    if ($null -eq $Current) {
      return $Default
    }
  }
  return $Current
}

function ConvertTo-BoundedText {
  param(
    [object]$Value,
    [int]$MaxLength = 512
  )

  if ($null -eq $Value) { return '' }
  $Text = [string]$Value
  if ([string]::IsNullOrWhiteSpace($Text)) { return '' }
  $Trimmed = $Text.Trim()
  if ($Trimmed.Length -le $MaxLength) { return $Trimmed }
  return $Trimmed.Substring(0, $MaxLength)
}

function ConvertTo-NullableDouble {
  param([object]$Value)

  if ($null -eq $Value) { return $null }
  $Text = ConvertTo-BoundedText -Value $Value -MaxLength 64
  if ([string]::IsNullOrWhiteSpace($Text)) { return $null }
  $Parsed = 0.0
  $Styles = [System.Globalization.NumberStyles]::Float
  $Culture = [System.Globalization.CultureInfo]::InvariantCulture
  if ([double]::TryParse($Text, $Styles, $Culture, [ref]$Parsed)) {
    return $Parsed
  }
  return $null
}

function Get-UnixTimestampSeconds {
  param([System.DateTime]$Value)

  return [double]([System.DateTimeOffset]::new($Value.ToUniversalTime()).ToUnixTimeSeconds())
}

function ConvertTo-RelativeRepoPath {
  param([string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
  try {
    $FullPath = [System.IO.Path]::GetFullPath($Path)
    $Root = $RepoRoot.TrimEnd('\') + '\'
    if ($FullPath.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
      return ($FullPath.Substring($Root.Length) -replace '\\', '/')
    }
    return $FullPath
  } catch {
    return $Path
  }
}

function New-Check {
  param(
    [string]$Id,
    [string]$Status,
    [bool]$Passed,
    [string]$Evidence = '',
    [string]$Reason = ''
  )

  return [ordered]@{
    id = $Id
    status = $Status
    passed = [bool]$Passed
    evidence = $Evidence
    reason = $Reason
  }
}

function Get-PythonPath {
  $WindowsVenv = Join-Path $RepoRoot '.venv\Scripts\python.exe'
  if (Test-Path -LiteralPath $WindowsVenv -PathType Leaf) {
    & $WindowsVenv --version *> $null
    if ($LASTEXITCODE -eq 0) {
      return $WindowsVenv
    }
  }

  $Python = Get-Command python -ErrorAction SilentlyContinue
  if ($null -ne $Python) {
    return [string]$Python.Source
  }
  return ''
}

function Invoke-JsonScript {
  param(
    [string]$ScriptPath,
    [string[]]$ScriptArgs = @()
  )

  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    return [ordered]@{
      ok = $false
      exit_code = 1
      payload = $null
      output = ''
      error = 'script_missing'
    }
  }

  $Output = & powershell -NoProfile -ExecutionPolicy Bypass -File $ScriptPath @ScriptArgs 2>&1
  $ExitCode = $LASTEXITCODE
  $Text = ($Output | ForEach-Object { [string]$_ }) -join "`n"
  $Payload = $null
  try {
    $Payload = $Text | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $Payload = $null
  }

  return [ordered]@{
    ok = ($ExitCode -eq 0 -and $null -ne $Payload)
    exit_code = [int]$ExitCode
    payload = $Payload
    output = $Text
    error = if ($null -ne $Payload) { '' } else { 'json_parse_failed' }
  }
}

function Read-JsonFile {
  param([string]$Path)

  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return $null
  }
  try {
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -ErrorAction Stop
  } catch {
    return $null
  }
}

function Get-ChatGptVoiceReceiptSummary {
  param(
    [int]$Limit,
    [int]$FreshnessSeconds
  )

  function Test-UnavailableTranscriptText {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    $Normalized = ($Value.ToLowerInvariant() -replace '[^a-z0-9]+', ' ').Trim()
    $Normalized = ($Normalized -split '\s+' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join ' '
    $Markers = @(
      'transcript unavailable',
      'transcript not available',
      'unavailable transcript'
    )
    foreach ($Marker in $Markers) {
      if ($Normalized -eq $Marker -or $Normalized.StartsWith("$Marker ", [System.StringComparison]::Ordinal)) {
        return $true
      }
    }
    return $false
  }

  $ReceiptRoot = Join-Path $DataRoot 'integrations\chatgpt_voice\receipts'
  $Files = @()
  if (Test-Path -LiteralPath $ReceiptRoot -PathType Container) {
    $Files = @(Get-ChildItem -LiteralPath $ReceiptRoot -File -Filter '*.json' |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First $Limit)
  }

  $Items = @()
  $NowTs = Get-UnixTimestampSeconds -Value ([System.DateTime]::UtcNow)
  $ChatGptSourceCount = 0
  $UsableChatGptSourceCount = 0
  $FreshChatGptSourceCount = 0
  $FreshUsableChatGptSourceCount = 0
  $StaleChatGptSourceCount = 0
  $TranscriptUnavailableCount = 0
  $ProbeSourceCount = 0
  foreach ($File in $Files) {
    $Receipt = Read-JsonFile -Path $File.FullName
    if ($null -eq $Receipt) { continue }

    $Actor = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Receipt -Name 'actor') -MaxLength 96
    $Source = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Receipt -Name 'source') -MaxLength 160
    $Decision = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Receipt -Name 'decision') -MaxLength 64
    $ForwardStatus = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Receipt -Name 'chat_forward_status') -MaxLength 64
    $Reply = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Receipt -Name 'reply') -MaxLength 512
    $Reason = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Receipt -Name 'reason') -MaxLength 96
    $TranscriptCount = [int](Get-PropertyValue -Payload $Receipt -Name 'transcript_char_count' -Default 0)
    $TranscriptUnavailable = ($Reason -eq 'transcript_unavailable' -or (Test-UnavailableTranscriptText -Value (Get-PropertyValue -Payload $Receipt -Name 'transcript' -Default '')))
    $ReceiptId = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Receipt -Name 'receipt_id') -MaxLength 160
    if ([string]::IsNullOrWhiteSpace($ReceiptId)) {
      $ReceiptId = [System.IO.Path]::GetFileNameWithoutExtension($File.Name)
    }
    $ReceiptCreatedTs = ConvertTo-NullableDouble -Value (Get-PropertyValue -Payload $Receipt -Name 'created_ts' -Default $null)
    $ObservedTsSource = 'created_ts'
    if ($null -eq $ReceiptCreatedTs) {
      $ReceiptCreatedTs = Get-UnixTimestampSeconds -Value $File.LastWriteTimeUtc
      $ObservedTsSource = 'file_mtime'
    }
    $ReceiptAgeSeconds = [int][Math]::Max(0, [Math]::Floor($NowTs - [double]$ReceiptCreatedTs))
    $FreshForLiveProof = $ReceiptAgeSeconds -le $FreshnessSeconds
    $CleanChatGptSource = ($Actor -eq 'chatgpt.voice' -and $Source -eq 'chatgpt.voice')
    $UsableChatGptSource = ($CleanChatGptSource -and $Decision -eq 'recorded' -and $TranscriptCount -gt 0 -and -not $TranscriptUnavailable)
    $ProbeSource = ($Source -like 'codex.*' -or $Source -like '*.smoke' -or $Source -like '*probe*')
    if ($CleanChatGptSource) { $ChatGptSourceCount++ }
    if ($UsableChatGptSource) { $UsableChatGptSourceCount++ }
    if ($CleanChatGptSource -and $FreshForLiveProof) { $FreshChatGptSourceCount++ }
    if ($UsableChatGptSource -and $FreshForLiveProof) { $FreshUsableChatGptSourceCount++ }
    if ($CleanChatGptSource -and -not $FreshForLiveProof) { $StaleChatGptSourceCount++ }
    if ($CleanChatGptSource -and $TranscriptUnavailable) { $TranscriptUnavailableCount++ }
    if ($ProbeSource) { $ProbeSourceCount++ }

    $Items += [ordered]@{
        receipt_id = $ReceiptId
        receipt_path = ConvertTo-RelativeRepoPath -Path $File.FullName
        actor = $Actor
        source = $Source
        source_claims_chatgpt_voice = [bool]$CleanChatGptSource
        usable_chatgpt_transcript = [bool]$UsableChatGptSource
        fresh_for_live_proof = [bool]$FreshForLiveProof
        receipt_age_seconds = $ReceiptAgeSeconds
        observed_ts_source = $ObservedTsSource
        created_ts_present = $ObservedTsSource -eq 'created_ts'
        transcript_unavailable_detected = [bool]$TranscriptUnavailable
        source_claims_probe = [bool]$ProbeSource
        decision = $Decision
        reason = $Reason
        chat_forward_status = $ForwardStatus
        chat_forwarded = [bool](Get-PropertyValue -Payload $Receipt -Name 'chat_forwarded' -Default $false)
        transcript_char_count = $TranscriptCount
        transcript_redacted_from_summary = $true
        reply_present = -not [string]::IsNullOrWhiteSpace($Reply)
        reply_source = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Receipt -Name 'reply_source') -MaxLength 96
        grants_execution_authority = [bool](Get-NestedPropertyValue -Payload $Receipt -Path @('governance', 'grants_execution_authority') -Default $false)
        grants_mutation_authority = [bool](Get-NestedPropertyValue -Payload $Receipt -Path @('governance', 'grants_mutation_authority') -Default $false)
      }
  }

  $Latest = $null
  if ($Items.Count -gt 0) {
    $Latest = $Items[0]
  }
  $LatestChatGpt = $null
  $LatestUsableChatGpt = $null
  $LatestFreshChatGpt = $null
  $LatestFreshUsableChatGpt = $null
  foreach ($Item in $Items) {
    if ([bool](Get-PropertyValue -Payload $Item -Name 'source_claims_chatgpt_voice' -Default $false)) {
      $LatestChatGpt = $Item
      break
    }
  }
  foreach ($Item in $Items) {
    if ([bool](Get-PropertyValue -Payload $Item -Name 'usable_chatgpt_transcript' -Default $false)) {
      $LatestUsableChatGpt = $Item
      break
    }
  }
  foreach ($Item in $Items) {
    if ([bool](Get-PropertyValue -Payload $Item -Name 'source_claims_chatgpt_voice' -Default $false) -and [bool](Get-PropertyValue -Payload $Item -Name 'fresh_for_live_proof' -Default $false)) {
      $LatestFreshChatGpt = $Item
      break
    }
  }
  foreach ($Item in $Items) {
    if ([bool](Get-PropertyValue -Payload $Item -Name 'usable_chatgpt_transcript' -Default $false) -and [bool](Get-PropertyValue -Payload $Item -Name 'fresh_for_live_proof' -Default $false)) {
      $LatestFreshUsableChatGpt = $Item
      break
    }
  }
  return [ordered]@{
    receipt_root = ConvertTo-RelativeRepoPath -Path $ReceiptRoot
    count = [int]$Items.Count
    freshness_window_seconds = [int]$FreshnessSeconds
    clean_chatgpt_source_count = [int]$ChatGptSourceCount
    usable_chatgpt_source_count = [int]$UsableChatGptSourceCount
    fresh_chatgpt_source_count = [int]$FreshChatGptSourceCount
    fresh_usable_chatgpt_source_count = [int]$FreshUsableChatGptSourceCount
    stale_chatgpt_source_count = [int]$StaleChatGptSourceCount
    transcript_unavailable_count = [int]$TranscriptUnavailableCount
    probe_source_count = [int]$ProbeSourceCount
    latest = $Latest
    latest_chatgpt_source = $LatestChatGpt
    latest_usable_chatgpt_source = $LatestUsableChatGpt
    latest_fresh_chatgpt_source = $LatestFreshChatGpt
    latest_fresh_usable_chatgpt_source = $LatestFreshUsableChatGpt
    receipts = $Items
    transcript_text_redacted_from_summary = $true
  }
}

function Get-OrbAndSandboxReadback {
  $PythonPath = Get-PythonPath
  if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    return [ordered]@{
      ok = $false
      error = 'python_unavailable'
      orb = $null
      mona_lisa_evaluation = $null
    }
  }

  $Source = @'
from __future__ import annotations

import json
import os

from francis.agent.sandbox_canvas import evaluate_mona_lisa_sandbox_artifact
from francis.world_state.orb import snapshot

print(json.dumps(dict(
    ok=True,
    orb=snapshot(),
    mona_lisa_evaluation=evaluate_mona_lisa_sandbox_artifact(),
), ensure_ascii=True, default=str))
'@

  $PrevDataDir = $env:FRANCIS_DATA_DIR
  $PrevPythonPath = $env:PYTHONPATH
  $PreviousErrorActionPreference = $null
  try {
    $env:FRANCIS_DATA_DIR = $DataRoot
    $SrcPath = Join-Path $RepoRoot 'src'
    if ([string]::IsNullOrWhiteSpace($PrevPythonPath)) {
      $env:PYTHONPATH = $SrcPath
    } else {
      $env:PYTHONPATH = "$SrcPath;$PrevPythonPath"
    }
    Push-Location $RepoRoot
    try {
      $PreviousErrorActionPreference = $ErrorActionPreference
      $ErrorActionPreference = 'Continue'
      $Output = & $PythonPath -c $Source 2>&1
      $ExitCode = $LASTEXITCODE
      $ErrorActionPreference = $PreviousErrorActionPreference
    } finally {
      if ($null -ne $PreviousErrorActionPreference) {
        $ErrorActionPreference = $PreviousErrorActionPreference
      }
      Pop-Location
    }
  } finally {
    $env:FRANCIS_DATA_DIR = $PrevDataDir
    $env:PYTHONPATH = $PrevPythonPath
  }

  $Text = ($Output | ForEach-Object { [string]$_ }) -join "`n"
  if ($ExitCode -ne 0) {
    return [ordered]@{
      ok = $false
      error = 'python_readback_failed'
      exit_code = [int]$ExitCode
      output = ConvertTo-BoundedText -Value $Text -MaxLength 2048
      orb = $null
      mona_lisa_evaluation = $null
    }
  }

  try {
    return $Text | ConvertFrom-Json -ErrorAction Stop
  } catch {
    return [ordered]@{
      ok = $false
      error = 'python_readback_json_parse_failed'
      output = ConvertTo-BoundedText -Value $Text -MaxLength 2048
      orb = $null
      mona_lisa_evaluation = $null
    }
  }
}

$OverlayResult = Invoke-JsonScript -ScriptPath (Join-Path $PSScriptRoot 'lens-overlay-window.ps1') -ScriptArgs @(
  '-Mode',
  'Status',
  '-DataDir',
  $DataRoot
)
$Overlay = Get-PropertyValue -Payload $OverlayResult -Name 'payload'

$ConnectorArgs = @(
  '-Mode',
  'Status',
  '-Json',
  '-RuntimeRoot',
  $ConnectorRuntimeRoot,
  '-HostAddress',
  $ConnectorHostAddress,
  '-Port',
  [string]$ConnectorPort,
  '-ConnectorProbeTimeoutSeconds',
  [string]$ConnectorProbeTimeoutSeconds
)
if (-not [string]::IsNullOrWhiteSpace($ConnectorUrl)) {
  $ConnectorArgs += @('-ConnectorUrl', $ConnectorUrl)
}
if ($VerifyConnector) {
  $ConnectorArgs += '-VerifyConnector'
}
$ConnectorResult = Invoke-JsonScript -ScriptPath (Join-Path $PSScriptRoot 'chatgpt-voice-connector.ps1') -ScriptArgs $ConnectorArgs
$Connector = Get-PropertyValue -Payload $ConnectorResult -Name 'payload'

$PlanArgs = @(
  '-Mode',
  'PlanPersistentIngress',
  '-Json',
  '-RuntimeRoot',
  $ConnectorRuntimeRoot,
  '-HostAddress',
  $ConnectorHostAddress,
  '-Port',
  [string]$ConnectorPort,
  '-ConnectorProbeTimeoutSeconds',
  [string]$ConnectorProbeTimeoutSeconds
)
if (-not [string]::IsNullOrWhiteSpace($ConnectorUrl)) {
  $PlanArgs += @('-ConnectorUrl', $ConnectorUrl)
}
if ($VerifyConnector) {
  $PlanArgs += '-VerifyConnector'
}
$PersistentIngressPlanResult = Invoke-JsonScript -ScriptPath (Join-Path $PSScriptRoot 'chatgpt-voice-connector.ps1') -ScriptArgs $PlanArgs
$PersistentIngressPlan = Get-PropertyValue -Payload $PersistentIngressPlanResult -Name 'payload'

$Receipts = Get-ChatGptVoiceReceiptSummary -Limit $ReceiptLimit -FreshnessSeconds $ChatGptReceiptFreshnessSeconds
$Readbacks = Get-OrbAndSandboxReadback
$Orb = Get-PropertyValue -Payload $Readbacks -Name 'orb'
$Evaluation = Get-PropertyValue -Payload $Readbacks -Name 'mona_lisa_evaluation'

$Checks = @()

$OverlayParsed = [bool](Get-PropertyValue -Payload $OverlayResult -Name 'ok' -Default $false)
$OverlayReady = [bool](Get-PropertyValue -Payload $Overlay -Name 'ready' -Default $false)
$OverlayStatus = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Overlay -Name 'status') -MaxLength 96
$Checks += (New-Check -Id 'overlay_status_readback' -Status $OverlayStatus -Passed ($OverlayParsed -and $OverlayReady) -Evidence (ConvertTo-RelativeRepoPath -Path (Join-Path $DataRoot 'runtime\lens-overlay\status.json')) -Reason $(if ($OverlayParsed) { '' } else { [string](Get-PropertyValue -Payload $OverlayResult -Name 'error' -Default 'overlay_status_unavailable') }))

$McpLiveStatus = ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $Overlay -Path @('mcp_body_state', 'live_status') -Default '') -MaxLength 96
$McpReady = $McpLiveStatus -eq 'ready'
$Checks += (New-Check -Id 'lens_mcp_body_state_readback' -Status $McpLiveStatus -Passed $McpReady -Evidence '/lens/mcp/status' -Reason $(if ($McpReady) { '' } else { 'mcp_body_state_not_ready' }))

$VoiceInputStatus = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Overlay -Name 'voice_input_status' -Default (Get-NestedPropertyValue -Payload $Overlay -Path @('voice_input_readiness', 'status') -Default 'unknown')) -MaxLength 96
$VoiceWaitingOrReady = $VoiceInputStatus -in @('ready', 'waiting_for_audio_signal')
$Checks += (New-Check -Id 'overlay_voice_input_readiness' -Status $VoiceInputStatus -Passed $VoiceWaitingOrReady -Evidence (ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Overlay -Name 'next_voice_input_step') -MaxLength 160) -Reason $(if ($VoiceWaitingOrReady) { '' } else { 'voice_input_status_not_ready_or_waiting' }))

$ConnectorEndpointStatus = ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $Connector -Path @('endpoint_status', 'status') -Default '') -MaxLength 96
$LocalListenerReady = [bool](Get-NestedPropertyValue -Payload $Connector -Path @('endpoint_status', 'local_listener', 'ready') -Default $false)
$Checks += (New-Check -Id 'chatgpt_voice_local_mcp_listener' -Status $ConnectorEndpointStatus -Passed $LocalListenerReady -Evidence (ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $Connector -Path @('endpoint_status', 'local_endpoint') -Default '') -MaxLength 160) -Reason $(if ($LocalListenerReady) { '' } else { 'local_mcp_listener_missing' }))

$ConnectorUrlShapeValid = [bool](Get-NestedPropertyValue -Payload $Connector -Path @('endpoint_status', 'chatgpt_connector', 'connector_url', 'shape_valid') -Default $false)
$ConnectorUrlProvided = [bool](Get-NestedPropertyValue -Payload $Connector -Path @('endpoint_status', 'chatgpt_connector', 'connector_url', 'provided') -Default $false)
$ConnectorUrlReason = ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $Connector -Path @('endpoint_status', 'chatgpt_connector', 'connector_url', 'reason') -Default 'connector_url_not_provided') -MaxLength 160
$ConnectorUrlSource = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Connector -Name 'connector_url_source' -Default 'none') -MaxLength 160
$Checks += (New-Check -Id 'chatgpt_voice_public_connector_url' -Status $(if ($ConnectorUrlShapeValid) { 'shape_valid' } elseif ($ConnectorUrlProvided) { 'shape_invalid' } else { 'missing' }) -Passed $ConnectorUrlShapeValid -Evidence (ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $Connector -Path @('endpoint_status', 'chatgpt_connector', 'connector_url', 'url') -Default '') -MaxLength 240) -Reason $(if ($ConnectorUrlShapeValid) { '' } else { $ConnectorUrlReason }))

$ConnectorReachabilityVerified = [bool](Get-NestedPropertyValue -Payload $Connector -Path @('endpoint_status', 'chatgpt_connector', 'reachability_verified') -Default $false)
$ConnectorUsableForChatGpt = [bool](Get-NestedPropertyValue -Payload $Connector -Path @('endpoint_status', 'chatgpt_connector', 'ready') -Default $false)
$ObservedConnectorProbeTimeoutSeconds = [int](Get-NestedPropertyValue -Payload $Connector -Path @('endpoint_status', 'chatgpt_connector', 'connector_probe_timeout_seconds') -Default $ConnectorProbeTimeoutSeconds)
$ConnectorReachabilityStatus = if ($ConnectorUsableForChatGpt) {
  'verified'
} elseif ($ConnectorUrlShapeValid -and -not $VerifyConnector) {
  'verification_not_requested'
} elseif ($ConnectorUrlShapeValid) {
  'not_verified'
} else {
  'not_ready'
}
$Checks += (New-Check -Id 'chatgpt_voice_connector_reachability' -Status $ConnectorReachabilityStatus -Passed $ConnectorUsableForChatGpt -Evidence (ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $Connector -Path @('endpoint_status', 'chatgpt_connector', 'connector_url', 'url') -Default '') -MaxLength 240) -Reason $(if ($ConnectorUsableForChatGpt) { '' } elseif ($ConnectorUrlShapeValid -and -not $VerifyConnector) { 'connector_reachability_probe_not_requested' } elseif ($ConnectorUrlShapeValid) { $ConnectorUrlReason } else { 'connector_url_not_ready' }))

$PersistentIngressPlanStatus = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $PersistentIngressPlan -Name 'status' -Default '') -MaxLength 96
$PersistentIngressPlanSafe = (
  [bool](Get-NestedPropertyValue -Payload $PersistentIngressPlan -Path @('governance', 'read_only') -Default $false) -and
  -not [bool](Get-NestedPropertyValue -Payload $PersistentIngressPlan -Path @('governance', 'starts_process') -Default $true) -and
  -not [bool](Get-NestedPropertyValue -Payload $PersistentIngressPlan -Path @('governance', 'opens_public_tunnel') -Default $true) -and
  -not [bool](Get-NestedPropertyValue -Payload $PersistentIngressPlan -Path @('governance', 'writes_data') -Default $true)
)
$Checks += (New-Check -Id 'persistent_ingress_plan_readback' -Status $(if ([string]::IsNullOrWhiteSpace($PersistentIngressPlanStatus)) { 'missing' } else { $PersistentIngressPlanStatus }) -Passed $PersistentIngressPlanSafe -Evidence (ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $PersistentIngressPlan -Name 'local_endpoint' -Default '') -MaxLength 160) -Reason $(if ($PersistentIngressPlanSafe) { '' } else { 'persistent_ingress_plan_unavailable_or_not_read_only' }))

$ReceiptObserved = [int](Get-PropertyValue -Payload $Receipts -Name 'count' -Default 0) -gt 0
$Checks += (New-Check -Id 'chatgpt_voice_bridge_receipt_observed' -Status $(if ($ReceiptObserved) { 'observed' } else { 'missing' }) -Passed $ReceiptObserved -Evidence (ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $Receipts -Path @('latest', 'receipt_path') -Default '') -MaxLength 240) -Reason $(if ($ReceiptObserved) { '' } else { 'no_chatgpt_voice_bridge_receipts_found' }))

$ChatGptSourceObserved = [int](Get-PropertyValue -Payload $Receipts -Name 'fresh_chatgpt_source_count' -Default 0) -gt 0
$AnyHistoricalChatGptSourceObserved = [int](Get-PropertyValue -Payload $Receipts -Name 'clean_chatgpt_source_count' -Default 0) -gt 0
$Checks += (New-Check -Id 'chatgpt_app_source_receipt_observed' -Status $(if ($ChatGptSourceObserved) { 'fresh_observed' } elseif ($AnyHistoricalChatGptSourceObserved) { 'stale_only' } else { 'missing' }) -Passed $ChatGptSourceObserved -Evidence (ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $Receipts -Path @('latest_fresh_chatgpt_source', 'receipt_path') -Default '') -MaxLength 240) -Reason $(if ($ChatGptSourceObserved) { '' } elseif ($AnyHistoricalChatGptSourceObserved) { 'chatgpt_source_receipts_are_outside_freshness_window' } else { 'no_recent_source_equals_chatgpt_voice_receipt_found' }))

$UsableChatGptSourceObserved = [int](Get-PropertyValue -Payload $Receipts -Name 'fresh_usable_chatgpt_source_count' -Default 0) -gt 0
$AnyHistoricalUsableChatGptSourceObserved = [int](Get-PropertyValue -Payload $Receipts -Name 'usable_chatgpt_source_count' -Default 0) -gt 0
$LatestChatGptUnavailable = [bool](Get-NestedPropertyValue -Payload $Receipts -Path @('latest_chatgpt_source', 'transcript_unavailable_detected') -Default $false)
$Checks += (New-Check -Id 'chatgpt_app_usable_transcript_observed' -Status $(if ($UsableChatGptSourceObserved) { 'fresh_observed' } elseif ($LatestChatGptUnavailable) { 'transcript_unavailable' } elseif ($AnyHistoricalUsableChatGptSourceObserved) { 'stale_only' } else { 'missing' }) -Passed $UsableChatGptSourceObserved -Evidence (ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $Receipts -Path @('latest_fresh_usable_chatgpt_source', 'receipt_path') -Default '') -MaxLength 240) -Reason $(if ($UsableChatGptSourceObserved) { '' } elseif ($LatestChatGptUnavailable) { 'latest_chatgpt_source_receipt_has_unavailable_transcript' } elseif ($AnyHistoricalUsableChatGptSourceObserved) { 'usable_chatgpt_voice_transcript_receipts_are_outside_freshness_window' } else { 'no_recent_usable_chatgpt_voice_transcript_receipt_found' }))

$OrbOk = [bool](Get-PropertyValue -Payload $Orb -Name 'ok' -Default $false)
$OrbStatus = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Orb -Name 'status' -Default (Get-PropertyValue -Payload $Orb -Name 'subsystem' -Default 'unknown')) -MaxLength 96
$Checks += (New-Check -Id 'orb_substrate_readback' -Status $OrbStatus -Passed $OrbOk -Evidence '/system/orb direct snapshot' -Reason $(if ($OrbOk) { '' } else { 'orb_snapshot_not_ok' }))

$EvaluationOk = [bool](Get-PropertyValue -Payload $Evaluation -Name 'ok' -Default $false)
$EvaluationPassed = [bool](Get-PropertyValue -Payload $Evaluation -Name 'passed' -Default $false)
$EvaluationStatus = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Evaluation -Name 'status' -Default 'missing') -MaxLength 96
$Checks += (New-Check -Id 'mona_lisa_sandbox_replay_evaluation' -Status $EvaluationStatus -Passed ($EvaluationOk -and $EvaluationPassed) -Evidence (ConvertTo-RelativeRepoPath -Path (ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Evaluation -Name 'artifact_dir') -MaxLength 512)) -Reason $(if ($EvaluationOk -and $EvaluationPassed) { '' } else { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Evaluation -Name 'error' -Default 'sandbox_evaluation_not_passed') -MaxLength 160 }))

$GovernanceSafe = (
  [bool](Get-NestedPropertyValue -Payload $Overlay -Path @('governance', 'read_only_contract') -Default $false) -and
  -not [bool](Get-NestedPropertyValue -Payload $Overlay -Path @('governance', 'execution_authority') -Default $true) -and
  -not [bool](Get-NestedPropertyValue -Payload $Connector -Path @('governance', 'opens_public_tunnel') -Default $true) -and
  -not [bool](Get-NestedPropertyValue -Payload $Connector -Path @('governance', 'starts_process') -Default $true)
)
$Checks += (New-Check -Id 'doctrine_authority_bounds' -Status $(if ($GovernanceSafe) { 'preserved' } else { 'violated' }) -Passed $GovernanceSafe -Evidence 'status_only_no_tunnel_no_provider_no_desktop_action' -Reason $(if ($GovernanceSafe) { '' } else { 'unexpected_authority_flag' }))

$CheckArray = $Checks
$CriticalIds = @(
  'overlay_status_readback',
  'lens_mcp_body_state_readback',
  'chatgpt_voice_bridge_receipt_observed',
  'chatgpt_app_source_receipt_observed',
  'chatgpt_app_usable_transcript_observed',
  'orb_substrate_readback',
  'mona_lisa_sandbox_replay_evaluation',
  'doctrine_authority_bounds'
)
$CriticalPassed = $true
foreach ($CheckId in $CriticalIds) {
  $Check = $CheckArray | Where-Object { [string](Get-PropertyValue -Payload $_ -Name 'id') -eq $CheckId } | Select-Object -First 1
  if (-not [bool](Get-PropertyValue -Payload $Check -Name 'passed' -Default $false)) {
    $CriticalPassed = $false
    break
  }
}

$Status = 'proof_blocked'
if (-not $ChatGptSourceObserved -and $AnyHistoricalChatGptSourceObserved) {
  $Status = 'proof_blocked_stale_chatgpt_app_source_receipt'
} elseif (-not $ChatGptSourceObserved) {
  $Status = 'proof_blocked_no_chatgpt_app_source_receipt'
} elseif (-not $UsableChatGptSourceObserved -and -not $LatestChatGptUnavailable -and $AnyHistoricalUsableChatGptSourceObserved) {
  $Status = 'proof_blocked_stale_usable_chatgpt_app_transcript'
} elseif (-not $UsableChatGptSourceObserved) {
  $Status = 'proof_blocked_no_usable_chatgpt_app_transcript'
} elseif (-not $ConnectorUrlShapeValid) {
  $Status = 'proof_partial_current_connector_url_missing'
} elseif (-not $ConnectorUsableForChatGpt) {
  $Status = 'proof_partial_connector_reachability_unverified'
} elseif ($CriticalPassed) {
  $Status = 'proof_passed'
} elseif (-not ($EvaluationOk -and $EvaluationPassed)) {
  $Status = 'proof_blocked_sandbox_replay_not_confirmed'
}

$NextGap = if (-not $ChatGptSourceObserved) {
  'trigger_fresh_chatgpt_app_voice_tool_call_and_confirm_source_receipt'
} elseif (-not $UsableChatGptSourceObserved) {
  'trigger_fresh_chatgpt_app_voice_tool_call_with_usable_transcript'
} elseif (-not $ConnectorUrlShapeValid) {
  'record_current_https_mcp_connector_url_or_replace_tunnel_with_persistent_ingress'
} elseif (-not $ConnectorUsableForChatGpt) {
  'verify_current_https_mcp_connector_reachability_or_trigger_fresh_chatgpt_tool_call'
} elseif ($VoiceInputStatus -eq 'waiting_for_audio_signal') {
  'confirm_live_microphone_signal_for_overlay_voice_input'
} elseif (-not ($EvaluationOk -and $EvaluationPassed)) {
  'restore_or_create_read_only_mona_lisa_sandbox_replay_artifact'
} else {
  'run_fresh_live_chatgpt_voice_to_francis_turn_and_confirm_receipt'
}

[ordered]@{
  ok = ($Status -eq 'proof_passed')
  kind = 'francis.orb_voice_overlay_lens.validation'
  status = $Status
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  data_root = $DataRoot
  checks = $CheckArray
  overlay = [ordered]@{
    status = $OverlayStatus
    ready = $OverlayReady
    runtime_state_path = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Overlay -Name 'runtime_state_path') -MaxLength 240
    mcp_body_live_status = $McpLiveStatus
    mcp_body_route = ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $Overlay -Path @('mcp_body_state', 'route') -Default '') -MaxLength 160
    voice_input_status = $VoiceInputStatus
    next_voice_input_step = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Overlay -Name 'next_voice_input_step') -MaxLength 160
    voice_turn_status = ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $Overlay -Path @('voice_turn', 'status') -Default '') -MaxLength 96
    handback_ready = [bool](Get-NestedPropertyValue -Payload $Overlay -Path @('voice_turn', 'handback_ready') -Default $false)
    grants_execution_authority = [bool](Get-NestedPropertyValue -Payload $Overlay -Path @('governance', 'execution_authority') -Default $false)
    grants_mutation_authority = [bool](Get-NestedPropertyValue -Payload $Overlay -Path @('governance', 'mutation_authority_granted') -Default $false)
  }
  chatgpt_voice_connector = [ordered]@{
    status = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Connector -Name 'status') -MaxLength 96
    local_endpoint_status = $ConnectorEndpointStatus
    local_listener_ready = $LocalListenerReady
    connector_url_provided = $ConnectorUrlProvided
    connector_url_shape_valid = $ConnectorUrlShapeValid
    connector_url_source = $ConnectorUrlSource
    connector_url_reason = $ConnectorUrlReason
    connector_reachability_verified = $ConnectorReachabilityVerified
    connector_usable_for_chatgpt = $ConnectorUsableForChatGpt
    connector_reachability_status = $ConnectorReachabilityStatus
    connector_reachability_probe_requested = [bool]$VerifyConnector
    connector_probe_timeout_seconds = $ObservedConnectorProbeTimeoutSeconds
    opens_public_tunnel = [bool](Get-NestedPropertyValue -Payload $Connector -Path @('governance', 'opens_public_tunnel') -Default $false)
    starts_process = [bool](Get-NestedPropertyValue -Payload $Connector -Path @('governance', 'starts_process') -Default $false)
  }
  persistent_ingress_plan = $PersistentIngressPlan
  chatgpt_voice_receipts = $Receipts
  substrate_readback = [ordered]@{
    ok = [bool](Get-PropertyValue -Payload $Readbacks -Name 'ok' -Default $false)
    error = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Readbacks -Name 'error') -MaxLength 240
    exit_code = Get-PropertyValue -Payload $Readbacks -Name 'exit_code' -Default $null
    output = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Readbacks -Name 'output') -MaxLength 1000
  }
  orb = [ordered]@{
    ok = $OrbOk
    status = $OrbStatus
    read_only_snapshot = $true
  }
  mona_lisa_sandbox = [ordered]@{
    ok = $EvaluationOk
    passed = $EvaluationPassed
    status = $EvaluationStatus
    evaluation_mode = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Evaluation -Name 'evaluation_mode') -MaxLength 96
    artifact_dir = ConvertTo-RelativeRepoPath -Path (ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Evaluation -Name 'artifact_dir') -MaxLength 512)
    recognizability_score = Get-NestedPropertyValue -Payload $Evaluation -Path @('recognizability', 'score') -Default $null
    visual_similarity_claim = [bool](Get-NestedPropertyValue -Payload $Evaluation -Path @('governance', 'visual_similarity_claim') -Default $false)
    live_desktop_perception_claim = [bool](Get-NestedPropertyValue -Payload $Evaluation -Path @('governance', 'live_desktop_perception_claim') -Default $false)
  }
  governance = [ordered]@{
    read_only = $true
    status_only = $true
    writes_repo = $false
    starts_process = $false
    opens_public_tunnel = $false
    calls_remote_voice_provider = $false
    calls_model = $false
    live_desktop_action = $false
    screenshots = $false
    pixels = $false
    ocr = $false
    grants_execution_authority = $false
    grants_mutation_authority = $false
    closes_stage6 = $false
  }
  next_smallest_truthful_gap = $NextGap
  doctrine = [ordered]@{
    no_orb_visual_change = $true
    no_second_overlay_application = $true
    no_second_lens_application = $true
    no_voice_direct_to_orb_animation = $true
    no_proposal_approval_claimed = $true
    no_promotion_claimed = $true
    no_stage_closure_claimed = $true
  }
} | ConvertTo-Json -Depth 12
