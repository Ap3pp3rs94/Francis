# Bounded API launcher for the local Orb/voice runtime.
#
# This does not relax Francis API policy. It starts the API with the actor
# scopes already required by the governed chat and ChatGPT voice bridge routes.

[CmdletBinding(PositionalBinding = $false)]
param(
  [ValidateSet('Status', 'PrintScopePolicy', 'Start', 'Restart', 'Stop')]
  [string]$Mode = 'Status',

  [string]$HostAddress = '127.0.0.1',

  [ValidateRange(1, 65535)]
  [int]$Port = 8000,

  [ValidateRange(1, 120)]
  [int]$StartupTimeoutSeconds = 30,

  [switch]$Json
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$FrancisScript = Join-Path $PSScriptRoot 'francis.ps1'
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

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

function ConvertTo-JsonOutput {
  param([object]$Payload)

  if ($Json) {
    $Payload | ConvertTo-Json -Depth 12
    return
  }
  $Payload | Format-List
}

function Resolve-PowerShellHost {
  $WindowsPowerShell = Get-Command powershell -ErrorAction SilentlyContinue
  if ($null -ne $WindowsPowerShell) {
    return [string]$WindowsPowerShell.Source
  }

  $PowerShellCore = Get-Command pwsh -ErrorAction SilentlyContinue
  if ($null -ne $PowerShellCore) {
    return [string]$PowerShellCore.Source
  }

  return ''
}

function New-StringList {
  param([object]$Value)

  $Items = New-Object 'System.Collections.Generic.List[string]'
  if ($null -eq $Value -or $Value -is [string]) {
    return ,$Items
  }

  foreach ($Item in @($Value)) {
    $Text = ConvertTo-BoundedText -Value $Item -MaxLength 160
    if (-not [string]::IsNullOrWhiteSpace($Text) -and -not $Items.Contains($Text)) {
      [void]$Items.Add($Text)
    }
  }
  return ,$Items
}

function Read-ExistingActorScopePolicy {
  $Policy = [ordered]@{}
  $Raw = ConvertTo-BoundedText -Value $env:FRANCIS_API_ACTOR_SCOPES -MaxLength 20000
  if ([string]::IsNullOrWhiteSpace($Raw)) {
    return [ordered]@{
      policy = $Policy
      source_status = 'empty'
      parse_error = ''
    }
  }

  try {
    $Parsed = $Raw | ConvertFrom-Json -ErrorAction Stop
  } catch {
    return [ordered]@{
      policy = $Policy
      source_status = 'invalid_json_ignored'
      parse_error = ConvertTo-BoundedText -Value $_.Exception.Message -MaxLength 240
    }
  }

  foreach ($Property in @($Parsed.PSObject.Properties)) {
    $Actor = ConvertTo-BoundedText -Value $Property.Name -MaxLength 160
    if ([string]::IsNullOrWhiteSpace($Actor)) { continue }
    $Scopes = New-StringList -Value $Property.Value
    $Policy[$Actor] = $Scopes
  }

  return [ordered]@{
    policy = $Policy
    source_status = 'parsed'
    parse_error = ''
  }
}

function Add-ActorScopes {
  param(
    [System.Collections.IDictionary]$Policy,
    [string]$Actor,
    [string[]]$Scopes
  )

  if (-not $Policy.Contains($Actor)) {
    $Policy[$Actor] = New-Object 'System.Collections.Generic.List[string]'
  }

  $List = $Policy[$Actor]
  foreach ($Scope in $Scopes) {
    $Text = ConvertTo-BoundedText -Value $Scope -MaxLength 160
    if (-not [string]::IsNullOrWhiteSpace($Text) -and -not $List.Contains($Text)) {
      [void]$List.Add($Text)
    }
  }
}

function Convert-PolicyToSerializable {
  param([System.Collections.IDictionary]$Policy)

  $Serializable = [ordered]@{}
  foreach ($Key in $Policy.Keys) {
    $Serializable[[string]$Key] = @($Policy[$Key])
  }
  return $Serializable
}

function New-OrbVoiceActorScopePolicy {
  $Existing = Read-ExistingActorScopePolicy
  $Policy = [ordered]@{}
  foreach ($Key in $Existing.policy.Keys) {
    $Policy[[string]$Key] = New-StringList -Value $Existing.policy[$Key]
  }

  Add-ActorScopes -Policy $Policy -Actor 'lens.overlay.voice' -Scopes @('chat.write')
  Add-ActorScopes -Policy $Policy -Actor 'chatgpt.voice' -Scopes @(
    'chatgpt.voice.bridge.read',
    'chatgpt.voice.bridge.write',
    'chat.write'
  )
  Add-ActorScopes -Policy $Policy -Actor 'chat_ui.voice' -Scopes @(
    'chatgpt.voice.bridge.write',
    'chat.write'
  )

  $Serializable = Convert-PolicyToSerializable -Policy $Policy
  return [ordered]@{
    policy = $Serializable
    policy_json = ($Serializable | ConvertTo-Json -Compress -Depth 8)
    existing_policy_status = $Existing.source_status
    existing_policy_parse_error = $Existing.parse_error
    required_actor_scopes = [ordered]@{
      'lens.overlay.voice' = @('chat.write')
      'chatgpt.voice' = @('chatgpt.voice.bridge.read', 'chatgpt.voice.bridge.write', 'chat.write')
      'chat_ui.voice' = @('chatgpt.voice.bridge.write', 'chat.write')
    }
  }
}

function Get-ListeningProcessIds {
  $Connections = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
  $Ids = New-Object 'System.Collections.Generic.List[int]'
  foreach ($Connection in $Connections) {
    $ListenerPid = [int]$Connection.OwningProcess
    if ($ListenerPid -gt 0 -and -not $Ids.Contains($ListenerPid)) {
      [void]$Ids.Add($ListenerPid)
    }
  }
  return @($Ids)
}

function Get-ProcessReadback {
  param([int]$ProcessId)

  $Payload = [ordered]@{
    pid = $ProcessId
    alive = $false
    command_line = ''
    command_mentions_francis_api = $false
  }
  if ($ProcessId -le 0) { return $Payload }

  $ProcessInfo = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $ProcessId) -ErrorAction SilentlyContinue
  if ($ProcessInfo) {
    $CommandLine = ConvertTo-BoundedText -Value $ProcessInfo.CommandLine -MaxLength 1200
    $Payload.alive = $true
    $Payload.command_line = $CommandLine
    $Payload.command_mentions_francis_api = (
      $CommandLine -like '*francis*' -and
      $CommandLine -like '* api *'
    )
  }
  return $Payload
}

function Invoke-ApiHealth {
  $Uri = 'http://{0}:{1}/chat/health' -f $HostAddress, $Port
  try {
    $Body = Invoke-RestMethod -Uri $Uri -Method Get -TimeoutSec 3 -ErrorAction Stop
    return [ordered]@{
      ok = [bool]$Body.ok
      status = if ([bool]$Body.ok) { 'healthy' } else { 'unhealthy_response' }
      route = '/chat/health'
    }
  } catch {
    return [ordered]@{
      ok = $false
      status = 'unreachable'
      route = '/chat/health'
      error = ConvertTo-BoundedText -Value $_.Exception.Message -MaxLength 240
    }
  }
}

function New-GovernancePayload {
  param(
    [bool]$ReadOnly,
    [bool]$StartsProcess,
    [bool]$StopsProcess
  )

  return [ordered]@{
    read_only = $ReadOnly
    starts_process = $StartsProcess
    stops_process = $StopsProcess
    writes_repo = $false
    writes_data = $false
    opens_public_tunnel = $false
    captures_audio = $false
    captures_screen = $false
    records_transcript = $false
    grants_execution_authority = $false
    grants_mutation_authority = $false
    actor_scope_source = 'process_environment_for_spawned_api_only'
  }
}

function New-StatusPayload {
  param(
    [string]$Status,
    [object]$PolicyBundle,
    [object[]]$StoppedProcesses = @(),
    [object]$StartedProcess = $null,
    [string]$ErrorText = ''
  )

  $Listeners = @(Get-ListeningProcessIds)
  $Readbacks = @()
  foreach ($Listener in $Listeners) {
    $Readbacks += Get-ProcessReadback -ProcessId $Listener
  }
  $Health = if ($Listeners.Count -gt 0) { Invoke-ApiHealth } else {
    [ordered]@{
      ok = $false
      status = 'not_listening'
      route = '/chat/health'
    }
  }

  return [ordered]@{
    kind = 'francis.orb_voice.api_runtime'
    ok = ($Status -in @('ready', 'started', 'restarted', 'stopped', 'policy_ready'))
    status = $Status
    mode = $Mode
    api_base_url = ('http://{0}:{1}' -f $HostAddress, $Port)
    listener_process_ids = @($Listeners)
    listener_count = $Listeners.Count
    process_readback = @($Readbacks)
    health = $Health
    required_actor_scopes = $PolicyBundle.required_actor_scopes
    actor_scope_policy = $PolicyBundle.policy
    actor_scope_policy_json = $PolicyBundle.policy_json
    existing_policy_status = $PolicyBundle.existing_policy_status
    existing_policy_parse_error = $PolicyBundle.existing_policy_parse_error
    started_process = $StartedProcess
    stopped_processes = @($StoppedProcesses)
    error = $ErrorText
    governance = New-GovernancePayload -ReadOnly ($Mode -in @('Status', 'PrintScopePolicy')) -StartsProcess ($Mode -in @('Start', 'Restart')) -StopsProcess ($Mode -in @('Stop', 'Restart'))
    doctrine = [ordered]@{
      voice_lens_orb_are_francis_surfaces = $true
      orb_role = 'embodiment'
      no_proposal_approval_claimed = $true
      no_promotion_claimed = $true
      no_execution_authority_claimed = $true
      no_mutation_authority_claimed = $true
    }
  }
}

function Stop-ListeningApiProcesses {
  $Stopped = @()
  foreach ($ListenerProcessId in @(Get-ListeningProcessIds)) {
    $Readback = Get-ProcessReadback -ProcessId $ListenerProcessId
    if (-not [bool]$Readback.command_mentions_francis_api) {
      $Stopped += [ordered]@{
        pid = $ListenerProcessId
        stopped = $false
        reason = 'listener_not_identified_as_francis_api'
        command_line = $Readback.command_line
      }
      continue
    }
    Stop-Process -Id $ListenerProcessId -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
    $StillAlive = $null -ne (Get-Process -Id $ListenerProcessId -ErrorAction SilentlyContinue)
    $Stopped += [ordered]@{
      pid = $ListenerProcessId
      stopped = (-not $StillAlive)
      reason = if ($StillAlive) { 'stop_process_did_not_exit' } else { 'stopped_francis_api_listener' }
      command_line = $Readback.command_line
    }
  }
  return @($Stopped)
}

function Start-OrbVoiceApi {
  param([string]$PolicyJson)

  $PowerShellHost = Resolve-PowerShellHost
  if ([string]::IsNullOrWhiteSpace($PowerShellHost)) {
    throw 'powershell_host_missing'
  }
  if (-not (Test-Path -LiteralPath $FrancisScript -PathType Leaf)) {
    throw 'francis_script_missing'
  }

  $Command = @(
    ('$env:FRANCIS_API_ACTOR_SCOPES = {0}' -f ("'" + ($PolicyJson -replace "'", "''") + "'")),
    '$env:PYTHONUTF8 = "1"',
    ('Set-Location -LiteralPath {0}' -f ("'" + ($RepoRoot -replace "'", "''") + "'")),
    ('& {0} api --host {1} --port {2}' -f ("'" + ($FrancisScript -replace "'", "''") + "'"), ("'" + ($HostAddress -replace "'", "''") + "'"), $Port)
  ) -join '; '
  $Encoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($Command))

  $Info = New-Object System.Diagnostics.ProcessStartInfo
  $Info.FileName = $PowerShellHost
  $Info.Arguments = "-NoProfile -ExecutionPolicy Bypass -EncodedCommand $Encoded"
  $Info.WorkingDirectory = $RepoRoot
  $Info.UseShellExecute = $false
  $Info.CreateNoWindow = $true
  $Info.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
  [void]$Info.EnvironmentVariables.Set_Item('FRANCIS_API_ACTOR_SCOPES', $PolicyJson)
  [void]$Info.EnvironmentVariables.Set_Item('PYTHONUTF8', '1')

  $Process = [System.Diagnostics.Process]::Start($Info)
  $Deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
  do {
    Start-Sleep -Milliseconds 500
    $Health = Invoke-ApiHealth
    if ([bool]$Health.ok) {
      return [ordered]@{
        pid = [int]$Process.Id
        started = $true
        health = $Health
      }
    }
  } while ([DateTime]::UtcNow -lt $Deadline)

  return [ordered]@{
    pid = [int]$Process.Id
    started = $false
    health = Invoke-ApiHealth
  }
}

$PolicyBundle = New-OrbVoiceActorScopePolicy

if ($Mode -eq 'PrintScopePolicy') {
  ConvertTo-JsonOutput -Payload (New-StatusPayload -Status 'policy_ready' -PolicyBundle $PolicyBundle)
  exit 0
}

if ($Mode -eq 'Status') {
  $Status = if (@(Get-ListeningProcessIds).Count -gt 0) { 'ready' } else { 'not_started' }
  ConvertTo-JsonOutput -Payload (New-StatusPayload -Status $Status -PolicyBundle $PolicyBundle)
  exit 0
}

if ($Mode -eq 'Stop') {
  $Stopped = Stop-ListeningApiProcesses
  ConvertTo-JsonOutput -Payload (New-StatusPayload -Status 'stopped' -PolicyBundle $PolicyBundle -StoppedProcesses $Stopped)
  exit 0
}

if ($Mode -eq 'Start') {
  if (@(Get-ListeningProcessIds).Count -gt 0) {
    ConvertTo-JsonOutput -Payload (New-StatusPayload -Status 'already_running' -PolicyBundle $PolicyBundle)
    exit 0
  }
  $Started = Start-OrbVoiceApi -PolicyJson $PolicyBundle.policy_json
  $Status = if ([bool]$Started.started) { 'started' } else { 'start_timeout' }
  ConvertTo-JsonOutput -Payload (New-StatusPayload -Status $Status -PolicyBundle $PolicyBundle -StartedProcess $Started)
  exit 0
}

if ($Mode -eq 'Restart') {
  $Stopped = Stop-ListeningApiProcesses
  $Started = Start-OrbVoiceApi -PolicyJson $PolicyBundle.policy_json
  $Status = if ([bool]$Started.started) { 'restarted' } else { 'start_timeout' }
  ConvertTo-JsonOutput -Payload (New-StatusPayload -Status $Status -PolicyBundle $PolicyBundle -StoppedProcesses $Stopped -StartedProcess $Started)
  exit 0
}
