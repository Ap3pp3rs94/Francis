# Starts the local Francis MCP endpoint for a ChatGPT developer-mode connector.
# This does not expose Francis to the public internet. Use an explicit HTTPS
# tunnel separately when you are ready to connect ChatGPT web/mobile.

[CmdletBinding(PositionalBinding = $false)]
param(
  [string]$HostAddress = '127.0.0.1',
  [int]$Port = 8787,
  [string]$Path = '/mcp',
  [string]$ConnectorUrl = '',
  [string[]]$AllowedHost = @(),
  [string[]]$AllowedOrigin = @(),
  [switch]$Json,
  [switch]$VerifyConnector,
  [ValidateRange(1, 60)]
  [int]$ConnectorProbeTimeoutSeconds = 5,
  [switch]$StatusOnly
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$srcPath = Join-Path $repoRoot 'src'
$venvPy = Join-Path $repoRoot '.venv\Scripts\python.exe'

function Test-VenvPython([string]$PathValue) {
  if (-not (Test-Path -LiteralPath $PathValue)) { return $false }
  & $PathValue --version *> $null
  return ($LASTEXITCODE -eq 0)
}

$python = if (Test-VenvPython $venvPy) { $venvPy } else { 'python' }
$endpoint = "http://$HostAddress`:$Port$Path"

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

function Add-ArgumentValues {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [string]$Name,
    [string[]]$Values
  )

  foreach ($Value in $Values) {
    $Text = ConvertTo-BoundedText -Value $Value -MaxLength 256
    if ([string]::IsNullOrWhiteSpace($Text)) { continue }
    $Target.Add($Name)
    $Target.Add($Text)
  }
}

function Test-ConnectorUrl {
  param(
    [string]$Value,
    [string]$ExpectedPath
  )

  $BoundedUrl = ConvertTo-BoundedText -Value $Value -MaxLength 512
  $Result = [ordered]@{
    provided = -not [string]::IsNullOrWhiteSpace($BoundedUrl)
    url = $BoundedUrl
    scheme = ''
    host_present = $false
    ends_with_mcp_path = $false
    https = $false
    shape_valid = $false
    reachability_verified = $false
    usable_for_chatgpt = $false
    reason = 'connector_url_not_provided'
  }
  if (-not [bool]$Result.provided) {
    return $Result
  }

  try {
    $Uri = [System.Uri]$BoundedUrl
  } catch {
    $Result.reason = 'connector_url_parse_failed'
    return $Result
  }

  $PathValue = $Uri.AbsolutePath.TrimEnd('/')
  $ExpectedPathValue = if ([string]::IsNullOrWhiteSpace($ExpectedPath)) { '/mcp' } else { $ExpectedPath.TrimEnd('/') }
  $Result.scheme = $Uri.Scheme
  $Result.host_present = -not [string]::IsNullOrWhiteSpace($Uri.Host)
  $Result.ends_with_mcp_path = $PathValue.EndsWith($ExpectedPathValue, [System.StringComparison]::OrdinalIgnoreCase)
  $Result.https = ($Uri.Scheme -eq 'https')
  $Result.shape_valid = [bool]$Result.https -and [bool]$Result.host_present -and [bool]$Result.ends_with_mcp_path
  $Result.usable_for_chatgpt = $false
  $Result.reason = if ([bool]$Result.shape_valid) { 'connector_url_shape_valid_reachability_not_verified' } elseif (-not [bool]$Result.https) { 'connector_url_must_be_https' } elseif (-not [bool]$Result.ends_with_mcp_path) { 'connector_url_must_end_with_mcp_path' } else { 'connector_url_missing_host' }
  return $Result
}

function Invoke-ConnectorProbe {
  param([string]$Url)

  $Result = [ordered]@{
    kind = 'francis.mcp_gateway.connector_probe'
    ok = $false
    status = 'not_run'
    connector_url = $Url
    expected_tool = 'francis_chatgpt_voice_ingress'
    reachability_verified = $false
    tool_list_observed = $false
    tool_count = 0
    expected_tool_present = $false
    error = ''
    governance = [ordered]@{
      read_only = $true
      writes_repo = $false
      writes_data = $false
      writes_receipts = $false
      calls_francis_tools = $false
      calls_model = $false
      grants_execution_authority = $false
      grants_mutation_authority = $false
    }
  }

  $PrevPythonPath = $env:PYTHONPATH
  try {
    if ($PrevPythonPath) {
      $env:PYTHONPATH = "$srcPath;$PrevPythonPath"
    } else {
      $env:PYTHONPATH = $srcPath
    }
    $Raw = & $python -m francis.mcp_gateway.connector_probe --connector-url $Url --expected-tool 'francis_chatgpt_voice_ingress' --timeout-seconds ([string]$ConnectorProbeTimeoutSeconds) 2>&1
    $ExitCode = $LASTEXITCODE
    try {
      $Parsed = $Raw | ConvertFrom-Json -ErrorAction Stop
    } catch {
      $Result.status = 'connector_probe_parse_failed'
      $Result.error = (ConvertTo-BoundedText -Value ($Raw -join "`n") -MaxLength 512)
      return $Result
    }
    $Parsed | Add-Member -NotePropertyName process_exit_code -NotePropertyValue $ExitCode -Force
    return $Parsed
  } finally {
    $env:PYTHONPATH = $PrevPythonPath
  }
}

function Test-LocalTcpListener {
  param(
    [string]$Address,
    [int]$PortValue
  )

  $TargetAddress = if ($Address -in @('0.0.0.0', '::', '')) { '127.0.0.1' } else { $Address }
  $Client = [System.Net.Sockets.TcpClient]::new()
  $AsyncResult = $null
  try {
    $AsyncResult = $Client.BeginConnect($TargetAddress, $PortValue, $null, $null)
    if (-not $AsyncResult.AsyncWaitHandle.WaitOne(250)) {
      return $false
    }
    $Client.EndConnect($AsyncResult)
    return [bool]$Client.Connected
  } catch {
    return $false
  } finally {
    if ($null -ne $AsyncResult) {
      $AsyncResult.AsyncWaitHandle.Dispose()
    }
    $Client.Dispose()
  }
}

function Get-LocalListenerReadback {
  param(
    [string]$Address,
    [int]$PortValue
  )

  $Readback = [ordered]@{
    ready = $false
    address = ''
    port = $PortValue
    owning_process = 0
    command_line = ''
  }

  if (-not (Test-LocalTcpListener -Address $Address -PortValue $PortValue)) {
    return $Readback
  }

  $NetTcpConnection = Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue
  if ($null -ne $NetTcpConnection) {
    $Listener = Get-NetTCPConnection -State Listen -LocalPort $PortValue -ErrorAction SilentlyContinue |
      Where-Object { $_.LocalAddress -eq $Address -or $_.LocalAddress -eq '0.0.0.0' -or $_.LocalAddress -eq '::' } |
      Select-Object -First 1 LocalAddress,LocalPort,OwningProcess
    if ($Listener) {
      $Readback.ready = $true
      $Readback.address = [string]$Listener.LocalAddress
      $Readback.port = [int]$Listener.LocalPort
      $Readback.owning_process = [int]$Listener.OwningProcess

      $CimCommand = Get-Command Get-CimInstance -ErrorAction SilentlyContinue
      if ($null -ne $CimCommand -and [int]$Listener.OwningProcess -gt 0) {
        $ProcessInfo = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f ([int]$Listener.OwningProcess)) -ErrorAction SilentlyContinue
        if ($ProcessInfo) {
          $Readback.command_line = ConvertTo-BoundedText -Value $ProcessInfo.CommandLine -MaxLength 512
        }
      }
    }
    return $Readback
  }

  $Readback.ready = $true
  $Readback.address = $Address
  return $Readback
}

function New-StatusPayload {
  param(
    [string]$Endpoint,
    [string]$ConnectorUrlValue
  )

  $Listener = Get-LocalListenerReadback -Address $HostAddress -PortValue $Port
  $Connector = Test-ConnectorUrl -Value $ConnectorUrlValue -ExpectedPath $Path
  $LocalReady = [bool]$Listener.ready
  $ReadyToAttemptLink = [bool]$LocalReady -and [bool]$Connector.shape_valid
  $Probe = $null
  if ([bool]$VerifyConnector -and [bool]$ReadyToAttemptLink) {
    $Probe = Invoke-ConnectorProbe -Url ([string]$Connector.url)
    $Connector.reachability_verified = [bool]$Probe.reachability_verified
    $Connector.usable_for_chatgpt = [bool]$Probe.ok
    $Connector.reason = if ([bool]$Probe.ok) { 'ready' } else { [string]$Probe.status }
  }
  $Blockers = New-Object System.Collections.Generic.List[string]
  if (-not [bool]$LocalReady) { [void]$Blockers.Add('local_mcp_listener_missing') }
  if (-not [bool]$Connector.shape_valid) { [void]$Blockers.Add([string]$Connector.reason) }
  if ([bool]$VerifyConnector -and [bool]$Connector.shape_valid -and -not [bool]$Connector.usable_for_chatgpt) {
    [void]$Blockers.Add([string]$Connector.reason)
  }
  $ConnectorReady = [bool]$LocalReady -and [bool]$Connector.usable_for_chatgpt

  return [ordered]@{
    kind = 'francis.chatgpt_voice.mcp.status'
    ok = [bool]$LocalReady
    status = if ($ConnectorReady) { 'ready_for_chatgpt_connector' } elseif ($ReadyToAttemptLink) { 'local_ready_connector_url_shape_valid' } elseif ($LocalReady) { 'local_ready_connector_url_needed' } else { 'local_listener_missing' }
    local_endpoint = $Endpoint
    mcp_path = $Path
    local_listener = [ordered]@{
      ready = [bool]$LocalReady
      address = ConvertTo-BoundedText -Value $Listener.address -MaxLength 160
      port = [int]$Listener.port
      owning_process = [int]$Listener.owning_process
      command_line = ConvertTo-BoundedText -Value $Listener.command_line -MaxLength 512
    }
    chatgpt_connector = [ordered]@{
      requires_https = $true
      requires_mcp_path = $Path
      connector_url = $Connector
      ready = [bool]$ConnectorReady
      ready_to_attempt_link = [bool]$ReadyToAttemptLink
      reachability_verified = [bool]$Connector.reachability_verified
      connector_probe_timeout_seconds = $ConnectorProbeTimeoutSeconds
      probe = $Probe
      native_localhost_access_claimed = $false
      opens_tunnel = $false
      next_operator_step = if ($ConnectorReady) { 'link_or_refresh_chatgpt_connector_then_select_it_in_chatgpt_chat' } elseif ($ReadyToAttemptLink) { 'link_or_refresh_chatgpt_connector_with_this_https_mcp_url_then_confirm_chatgpt_tool_list' } elseif ($LocalReady) { 'provide_https_mcp_connector_url_or_explicitly_authorize_tunnel' } else { 'start_local_chatgpt_voice_mcp_endpoint' }
    }
    blockers = [string[]]$Blockers.ToArray()
    governance = [ordered]@{
      read_only = $true
      status_only = $true
      writes_repo = $false
      writes_data = $false
      opens_public_tunnel = $false
      starts_process = $false
      grants_execution_authority = $false
      grants_mutation_authority = $false
      accepts_audio_stream = $false
      transcript_only_bridge = $true
    }
  }
}

if (-not $Json) {
  Write-Host "Francis ChatGPT voice MCP endpoint: $endpoint"
  Write-Host "ChatGPT requires an HTTPS URL ending in $Path. Expose this local endpoint with a tunnel only when intended."
}

if ($StatusOnly) {
  $Payload = New-StatusPayload -Endpoint $endpoint -ConnectorUrlValue $ConnectorUrl
  if ($Json) {
    $Payload | ConvertTo-Json -Depth 8
    exit 0
  }
  $listener = $Payload.local_listener
  if ([bool]$listener.ready) {
    $listener | Format-List
    exit 0
  }
  Write-Host "No listener is active on port $Port."
  exit 1
}

$prevPythonPath = $env:PYTHONPATH
$prevActorScopes = $env:FRANCIS_API_ACTOR_SCOPES
try {
  if ($prevPythonPath) {
    $env:PYTHONPATH = "$srcPath;$prevPythonPath"
  } else {
    $env:PYTHONPATH = $srcPath
  }
  $env:FRANCIS_API_ACTOR_SCOPES = '{"chatgpt.voice":["chatgpt.voice.bridge.read","chatgpt.voice.bridge.write","chat.write"]}'

  Push-Location $repoRoot
  try {
    $ServerArgs = [System.Collections.Generic.List[string]]::new()
    $ServerArgs.Add('-m')
    $ServerArgs.Add('francis.mcp_gateway.server')
    $ServerArgs.Add('--transport')
    $ServerArgs.Add('streamable-http')
    $ServerArgs.Add('--host')
    $ServerArgs.Add($HostAddress)
    $ServerArgs.Add('--port')
    $ServerArgs.Add([string]$Port)
    $ServerArgs.Add('--path')
    $ServerArgs.Add($Path)
    Add-ArgumentValues -Target $ServerArgs -Name '--allowed-host' -Values @('127.0.0.1', 'localhost', $AllowedHost)
    Add-ArgumentValues -Target $ServerArgs -Name '--allowed-origin' -Values $AllowedOrigin
    & $python @ServerArgs
    exit $LASTEXITCODE
  } finally {
    Pop-Location
  }
} finally {
  $env:PYTHONPATH = $prevPythonPath
  $env:FRANCIS_API_ACTOR_SCOPES = $prevActorScopes
}
