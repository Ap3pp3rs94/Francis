# Bounded operator control for the ChatGPT voice MCP connector.
#
# Status mode is read-only. RecordUrl stores an operator-supplied persistent
# HTTPS MCP URL without opening a tunnel. Start mode opens a public localtunnel
# URL only when -ExposePublicTunnel is explicitly supplied by the operator.

[CmdletBinding(PositionalBinding = $false)]
param(
  [ValidateSet('Status', 'RecordUrl', 'Start', 'Stop')]
  [string]$Mode = 'Status',
  [string]$HostAddress = '127.0.0.1',
  [int]$Port = 8787,
  [string]$Path = '/mcp',
  [string]$ConnectorUrl = '',
  [string]$TunnelSubdomain = 'francis-voice-178175',
  [string]$RuntimeRoot = '',
  [switch]$ExposePublicTunnel,
  [switch]$VerifyConnector,
  [switch]$Json
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$mcpScript = Join-Path $PSScriptRoot 'chatgpt-voice-mcp.ps1'
if ([string]::IsNullOrWhiteSpace($RuntimeRoot)) {
  $RuntimeRoot = Join-Path $repoRoot 'data\runtime\chatgpt-voice-connector'
}
$statePath = Join-Path $RuntimeRoot 'status.json'

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

function ConvertTo-JsonOutput {
  param([object]$Payload)

  if ($Json) {
    $Payload | ConvertTo-Json -Depth 10
    return
  }
  $Payload | Format-List
}

function New-GovernancePayload {
  param(
    [bool]$ReadOnly,
    [bool]$StartsProcess,
    [bool]$OpensPublicTunnel,
    [bool]$WritesData
  )

  return [ordered]@{
    read_only = $ReadOnly
    starts_process = $StartsProcess
    opens_public_tunnel = $OpensPublicTunnel
    writes_repo = $false
    writes_data = $WritesData
    writes_receipts = $false
    accepts_audio_stream = $false
    transcript_only_bridge = $true
    grants_execution_authority = $false
    grants_mutation_authority = $false
    approves_proposals = $false
    promotes_capabilities = $false
  }
}

function Read-State {
  if (-not (Test-Path -LiteralPath $statePath)) { return $null }
  try {
    return Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json -ErrorAction Stop
  } catch {
    return $null
  }
}

function Write-State {
  param([object]$Payload)

  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  $tmp = Join-Path $RuntimeRoot ('.status-{0}.tmp' -f ([guid]::NewGuid().ToString('N')))
  $Payload | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $tmp -Encoding UTF8
  Move-Item -LiteralPath $tmp -Destination $statePath -Force
}

function Get-ProcessReadback {
  param(
    [int]$ProcessId,
    [string]$ExpectedCommandText = ''
  )

  $Payload = [ordered]@{
    pid = $ProcessId
    alive = $false
    command_line = ''
    command_matches_expected = $false
  }
  if ($ProcessId -le 0) { return $Payload }

  $ProcessInfo = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $ProcessId) -ErrorAction SilentlyContinue
  if ($ProcessInfo) {
    $CommandLine = ConvertTo-BoundedText -Value $ProcessInfo.CommandLine -MaxLength 768
    $Payload.alive = $true
    $Payload.command_line = $CommandLine
    $Payload.command_matches_expected = if ([string]::IsNullOrWhiteSpace($ExpectedCommandText)) {
      $true
    } else {
      $CommandLine.Contains($ExpectedCommandText)
    }
  }
  return $Payload
}

function Invoke-EndpointStatus {
  param([string]$ConnectorUrl)

  $Args = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $mcpScript,
    '-StatusOnly',
    '-Json',
    '-HostAddress',
    $HostAddress,
    '-Port',
    [string]$Port,
    '-Path',
    $Path
  )
  if (-not [string]::IsNullOrWhiteSpace($ConnectorUrl)) {
    $Args += @('-ConnectorUrl', $ConnectorUrl)
  }
  if ($VerifyConnector) {
    $Args += '-VerifyConnector'
  }

  $Raw = & powershell @Args 2>&1
  try {
    return $Raw | ConvertFrom-Json -ErrorAction Stop
  } catch {
    return [ordered]@{
      kind = 'francis.chatgpt_voice.mcp.status'
      ok = $false
      status = 'status_parse_failed'
      error = ConvertTo-BoundedText -Value ($Raw -join "`n") -MaxLength 512
    }
  }
}

function Resolve-LocalTunnelScript {
  $CacheRoot = Join-Path $env:LOCALAPPDATA 'npm-cache\_npx'
  if (Test-Path -LiteralPath $CacheRoot) {
    $Candidate = Get-ChildItem -LiteralPath $CacheRoot -Recurse -Filter 'lt.js' -ErrorAction SilentlyContinue |
      Where-Object { $_.FullName -like '*node_modules\localtunnel\bin\lt.js' } |
      Sort-Object LastWriteTime -Descending |
      Select-Object -First 1
    if ($Candidate) { return $Candidate.FullName }
  }

  $Npx = Get-Command npx.cmd -ErrorAction SilentlyContinue
  if ($Npx) {
    & $Npx.Source --yes localtunnel --version *> $null
    if (Test-Path -LiteralPath $CacheRoot) {
      $Candidate = Get-ChildItem -LiteralPath $CacheRoot -Recurse -Filter 'lt.js' -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -like '*node_modules\localtunnel\bin\lt.js' } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
      if ($Candidate) { return $Candidate.FullName }
    }
  }
  return ''
}

function Wait-ForTunnelUrl {
  param(
    [string]$StdoutPath,
    [int]$TimeoutSeconds = 15
  )

  $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $Deadline) {
    if (Test-Path -LiteralPath $StdoutPath) {
      $Text = Get-Content -LiteralPath $StdoutPath -Raw -ErrorAction SilentlyContinue
      if ($Text -match 'https://[^\s]+') {
        return $Matches[0].TrimEnd('/') + $Path
      }
    }
    Start-Sleep -Milliseconds 500
  }
  return ''
}

function Stop-KnownProcess {
  param(
    [int]$ProcessId,
    [string]$ExpectedCommandText
  )

  $Readback = Get-ProcessReadback -ProcessId $ProcessId -ExpectedCommandText $ExpectedCommandText
  if (-not [bool]$Readback.alive) { return $false }
  if (-not [bool]$Readback.command_matches_expected) { return $false }
  Stop-Process -Id $ProcessId -Force -ErrorAction Stop
  return $true
}

function New-StatusPayload {
  param(
    [object]$State,
    [object]$EndpointStatus,
    [bool]$ReadOnly = $true,
    [bool]$StartsProcess = $false,
    [bool]$OpensPublicTunnel = $false,
    [bool]$WritesData = $false
  )

  $ConnectorUrl = ''
  $McpLauncherPid = 0
  $TunnelPid = 0
  $IngressMode = ''
  if ($State) {
    $ConnectorUrl = ConvertTo-BoundedText -Value $State.connector_url -MaxLength 512
    $McpLauncherPid = [int]($State.mcp_launcher_pid)
    $TunnelPid = [int]($State.tunnel_pid)
    $IngressMode = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'ingress_mode') -MaxLength 96
  }
  if ([string]::IsNullOrWhiteSpace($ConnectorUrl) -and $EndpointStatus -and $EndpointStatus.chatgpt_connector) {
    $ConnectorUrl = ConvertTo-BoundedText -Value $EndpointStatus.chatgpt_connector.connector_url.url -MaxLength 512
  }
  if ([string]::IsNullOrWhiteSpace($IngressMode) -and -not [string]::IsNullOrWhiteSpace($ConnectorUrl)) {
    $IngressMode = 'manual_status_url'
  }

  $McpReadback = Get-ProcessReadback -ProcessId $McpLauncherPid -ExpectedCommandText 'chatgpt-voice-mcp.ps1'
  $TunnelReadback = Get-ProcessReadback -ProcessId $TunnelPid -ExpectedCommandText 'localtunnel\bin\lt.js'
  $Ready = $false
  if ($EndpointStatus -and [string]$EndpointStatus.status -eq 'ready_for_chatgpt_connector') {
    $Ready = $true
  }

  return [ordered]@{
    kind = 'francis.chatgpt_voice.connector_control'
    ok = $Ready
    status = if ($Ready) { 'ready_for_chatgpt_connector' } elseif ($State) { 'runtime_state_observed' } else { 'not_started' }
    connector_url = $ConnectorUrl
    ingress_mode = $IngressMode
    runtime_root = $RuntimeRoot
    state_path = $statePath
    processes = [ordered]@{
      mcp_launcher = $McpReadback
      tunnel = $TunnelReadback
    }
    endpoint_status = $EndpointStatus
    governance = New-GovernancePayload -ReadOnly $ReadOnly -StartsProcess $StartsProcess -OpensPublicTunnel $OpensPublicTunnel -WritesData $WritesData
  }
}

if ($Mode -eq 'Status') {
  $State = Read-State
  $StatusConnectorUrl = ConvertTo-BoundedText -Value $ConnectorUrl -MaxLength 512
  if ($State) {
    $StateConnectorUrl = ConvertTo-BoundedText -Value $State.connector_url -MaxLength 512
    if (-not [string]::IsNullOrWhiteSpace($StateConnectorUrl)) {
      $StatusConnectorUrl = $StateConnectorUrl
    }
  }
  $EndpointStatus = Invoke-EndpointStatus -ConnectorUrl $StatusConnectorUrl
  ConvertTo-JsonOutput -Payload (New-StatusPayload -State $State -EndpointStatus $EndpointStatus)
  exit 0
}

if ($Mode -eq 'RecordUrl') {
  $RecordedConnectorUrl = ConvertTo-BoundedText -Value $ConnectorUrl -MaxLength 512
  if ([string]::IsNullOrWhiteSpace($RecordedConnectorUrl)) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'connector_url_required'
        connector_url = ''
        runtime_root = $RuntimeRoot
        state_path = $statePath
        blockers = @('connector_url_required')
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  $EndpointStatus = Invoke-EndpointStatus -ConnectorUrl $RecordedConnectorUrl
  $ShapeValid = [bool](Get-NestedPropertyValue -Payload $EndpointStatus -Path @('chatgpt_connector', 'connector_url', 'shape_valid') -Default $false)
  $ShapeReason = ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $EndpointStatus -Path @('chatgpt_connector', 'connector_url', 'reason') -Default 'connector_url_shape_invalid') -MaxLength 160
  if (-not $ShapeValid) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'connector_url_shape_invalid'
        connector_url = $RecordedConnectorUrl
        runtime_root = $RuntimeRoot
        state_path = $statePath
        endpoint_status = $EndpointStatus
        blockers = @($ShapeReason)
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  $ConnectorHost = ([System.Uri]$RecordedConnectorUrl).Host
  $StatePayload = [ordered]@{
    kind = 'francis.chatgpt_voice.connector_control.state'
    status = 'persistent_connector_url_recorded'
    ingress_mode = 'persistent_https'
    connector_url = $RecordedConnectorUrl
    connector_host = $ConnectorHost
    local_endpoint = "http://$HostAddress`:$Port$Path"
    mcp_launcher_pid = 0
    tunnel_pid = 0
    updated_at = (Get-Date).ToUniversalTime().ToString('o')
    governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $true
  }
  Write-State -Payload $StatePayload

  $Payload = New-StatusPayload -State (Read-State) -EndpointStatus $EndpointStatus -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $true
  $Payload.status = 'persistent_connector_url_recorded'
  $Payload.ok = $true
  ConvertTo-JsonOutput -Payload $Payload
  exit 0
}

if ($Mode -eq 'Start' -and -not $ExposePublicTunnel) {
  ConvertTo-JsonOutput -Payload ([ordered]@{
      kind = 'francis.chatgpt_voice.connector_control'
      ok = $false
      status = 'operator_public_tunnel_authorization_required'
      connector_url = ''
      runtime_root = $RuntimeRoot
      state_path = $statePath
      blockers = @('expose_public_tunnel_flag_required')
      governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
    })
  exit 0
}

if ($Mode -eq 'Stop') {
  $State = Read-State
  $Stopped = @()
  if ($State) {
    if (Stop-KnownProcess -ProcessId ([int]$State.tunnel_pid) -ExpectedCommandText 'localtunnel\bin\lt.js') {
      $Stopped += 'tunnel'
    }
    if (Stop-KnownProcess -ProcessId ([int]$State.mcp_launcher_pid) -ExpectedCommandText 'chatgpt-voice-mcp.ps1') {
      $Stopped += 'mcp_launcher'
    }
  }
  $StopState = [ordered]@{
    kind = 'francis.chatgpt_voice.connector_control.state'
    status = 'stopped'
    connector_url = if ($State) { ConvertTo-BoundedText -Value $State.connector_url -MaxLength 512 } else { '' }
    mcp_launcher_pid = if ($State) { [int]$State.mcp_launcher_pid } else { 0 }
    tunnel_pid = if ($State) { [int]$State.tunnel_pid } else { 0 }
    stopped = $Stopped
    updated_at = (Get-Date).ToUniversalTime().ToString('o')
  }
  Write-State -Payload $StopState
  ConvertTo-JsonOutput -Payload ([ordered]@{
      kind = 'francis.chatgpt_voice.connector_control'
      ok = $true
      status = 'stopped'
      stopped = $Stopped
      runtime_root = $RuntimeRoot
      state_path = $statePath
      governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $true
    })
  exit 0
}

$LocalTunnelScript = Resolve-LocalTunnelScript
if ([string]::IsNullOrWhiteSpace($LocalTunnelScript) -or -not (Test-Path -LiteralPath $LocalTunnelScript)) {
  ConvertTo-JsonOutput -Payload ([ordered]@{
      kind = 'francis.chatgpt_voice.connector_control'
      ok = $false
      status = 'localtunnel_unavailable'
      error = 'localtunnel_script_not_found'
      governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
    })
  exit 0
}

New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
$TunnelStdout = Join-Path $RuntimeRoot 'localtunnel.stdout.log'
$TunnelStderr = Join-Path $RuntimeRoot 'localtunnel.stderr.log'
$McpStdout = Join-Path $RuntimeRoot 'mcp.stdout.log'
$McpStderr = Join-Path $RuntimeRoot 'mcp.stderr.log'

$TunnelArgs = @($LocalTunnelScript, '--port', [string]$Port, '--local-host', $HostAddress)
if (-not [string]::IsNullOrWhiteSpace($TunnelSubdomain)) {
  $TunnelArgs += @('--subdomain', $TunnelSubdomain)
}
$TunnelProcess = Start-Process -FilePath 'node' -ArgumentList $TunnelArgs -PassThru -WindowStyle Hidden -RedirectStandardOutput $TunnelStdout -RedirectStandardError $TunnelStderr
$ConnectorUrl = Wait-ForTunnelUrl -StdoutPath $TunnelStdout
if ([string]::IsNullOrWhiteSpace($ConnectorUrl)) {
  ConvertTo-JsonOutput -Payload ([ordered]@{
      kind = 'francis.chatgpt_voice.connector_control'
      ok = $false
      status = 'tunnel_url_unavailable'
      tunnel_pid = $TunnelProcess.Id
      tunnel_stdout = $TunnelStdout
      tunnel_stderr = $TunnelStderr
      governance = New-GovernancePayload -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $true -WritesData $true
    })
  exit 0
}

$ConnectorHost = ([System.Uri]$ConnectorUrl).Host
$McpArgs = @(
  '-NoProfile',
  '-ExecutionPolicy',
  'Bypass',
  '-File',
  $mcpScript,
  '-HostAddress',
  $HostAddress,
  '-Port',
  [string]$Port,
  '-Path',
  $Path,
  '-AllowedHost',
  $ConnectorHost
)
$McpProcess = Start-Process -FilePath 'powershell' -ArgumentList $McpArgs -PassThru -WindowStyle Hidden -RedirectStandardOutput $McpStdout -RedirectStandardError $McpStderr
Start-Sleep -Seconds 4

$StatePayload = [ordered]@{
  kind = 'francis.chatgpt_voice.connector_control.state'
  status = 'started'
  connector_url = $ConnectorUrl
  connector_host = $ConnectorHost
  local_endpoint = "http://$HostAddress`:$Port$Path"
  mcp_launcher_pid = $McpProcess.Id
  tunnel_pid = $TunnelProcess.Id
  mcp_stdout = $McpStdout
  mcp_stderr = $McpStderr
  tunnel_stdout = $TunnelStdout
  tunnel_stderr = $TunnelStderr
  updated_at = (Get-Date).ToUniversalTime().ToString('o')
  governance = New-GovernancePayload -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $true -WritesData $true
}
Write-State -Payload $StatePayload

$EndpointStatus = Invoke-EndpointStatus -ConnectorUrl $ConnectorUrl
$Payload = New-StatusPayload -State (Read-State) -EndpointStatus $EndpointStatus -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $true -WritesData $true
$Payload.status = if ([string]$EndpointStatus.status -eq 'ready_for_chatgpt_connector') { 'started_ready' } else { 'started_unverified' }
$Payload.ok = [bool]($Payload.status -eq 'started_ready')
ConvertTo-JsonOutput -Payload $Payload
