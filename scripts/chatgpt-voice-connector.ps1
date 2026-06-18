# Bounded operator control for the ChatGPT voice MCP connector.
#
# Status and PlanPersistentIngress modes are read-only. RecordUrl stores an
# operator-supplied persistent HTTPS MCP URL without opening a tunnel. Start mode
# opens a public localtunnel URL only when -ExposePublicTunnel is explicitly
# supplied by the operator.

[CmdletBinding(PositionalBinding = $false)]
param(
  [ValidateSet('Status', 'PlanPersistentIngress', 'RecordUrl', 'Start', 'Stop')]
  [string]$Mode = 'Status',
  [string]$HostAddress = '127.0.0.1',
  [int]$Port = 8787,
  [string]$Path = '/mcp',
  [string]$ConnectorUrl = '',
  [string]$TunnelSubdomain = 'francis-voice-178175',
  [string]$RuntimeRoot = '',
  [switch]$ExposePublicTunnel,
  [switch]$VerifyConnector,
  [ValidateRange(1, 60)]
  [int]$ConnectorProbeTimeoutSeconds = 5,
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

function Get-CommandReadiness {
  param(
    [string]$Name,
    [string]$Capability
  )

  $Command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
  return [ordered]@{
    name = $Name
    capability = $Capability
    available = $null -ne $Command
    path = if ($Command) { ConvertTo-BoundedText -Value $Command.Source -MaxLength 512 } else { '' }
  }
}

function New-ConnectorIngressProfile {
  param(
    [object]$EndpointStatus,
    [string]$ConnectorUrlSource = 'none'
  )

  $ConnectorUrl = ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $EndpointStatus -Path @('chatgpt_connector', 'connector_url', 'url') -Default '') -MaxLength 512
  $ConnectorProvided = [bool](Get-NestedPropertyValue -Payload $EndpointStatus -Path @('chatgpt_connector', 'connector_url', 'provided') -Default $false)
  $ConnectorShapeValid = [bool](Get-NestedPropertyValue -Payload $EndpointStatus -Path @('chatgpt_connector', 'connector_url', 'shape_valid') -Default $false)
  $ConnectorReason = ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $EndpointStatus -Path @('chatgpt_connector', 'connector_url', 'reason') -Default 'connector_url_not_provided') -MaxLength 160
  $Source = ConvertTo-BoundedText -Value $ConnectorUrlSource -MaxLength 160
  if ([string]::IsNullOrWhiteSpace($Source)) {
    $Source = 'none'
  }

  $ConnectorHostName = ''
  if (-not [string]::IsNullOrWhiteSpace($ConnectorUrl)) {
    try {
      $ConnectorHostName = ([System.Uri]$ConnectorUrl).Host
    } catch {
      $ConnectorHostName = ''
    }
  }

  $KnownLocalTunnel = (
    $Source -eq 'localtunnel' -or
    (-not [string]::IsNullOrWhiteSpace($ConnectorHostName) -and $ConnectorHostName.EndsWith('.loca.lt', [System.StringComparison]::OrdinalIgnoreCase))
  )
  $PersistentCandidate = [bool]($ConnectorShapeValid -and -not $KnownLocalTunnel)
  $Profile = if (-not $ConnectorProvided) {
    'missing'
  } elseif (-not $ConnectorShapeValid) {
    'invalid_https_mcp_url'
  } elseif ($KnownLocalTunnel) {
    'localtunnel_ephemeral'
  } else {
    'persistent_https_candidate'
  }

  $Blockers = @()
  if (-not $ConnectorProvided) {
    $Blockers += 'connector_url_required'
  } elseif (-not $ConnectorShapeValid) {
    $Blockers += $ConnectorReason
  } elseif ($KnownLocalTunnel) {
    $Blockers += 'localtunnel_url_is_not_persistent_ingress'
  }

  return [ordered]@{
    profile = $Profile
    source = $Source
    host = $ConnectorHostName
    known_localtunnel = [bool]$KnownLocalTunnel
    persistent_candidate = [bool]$PersistentCandidate
    blockers = $Blockers
  }
}

function New-PersistentIngressPlan {
  param(
    [object]$EndpointStatus,
    [string]$ConnectorUrlSource = 'none'
  )

  $ConnectorShapeValid = [bool](Get-NestedPropertyValue -Payload $EndpointStatus -Path @('chatgpt_connector', 'connector_url', 'shape_valid') -Default $false)
  $ConnectorProvided = [bool](Get-NestedPropertyValue -Payload $EndpointStatus -Path @('chatgpt_connector', 'connector_url', 'provided') -Default $false)
  $ConnectorReason = ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $EndpointStatus -Path @('chatgpt_connector', 'connector_url', 'reason') -Default 'connector_url_not_provided') -MaxLength 160
  $LocalReady = [bool](Get-NestedPropertyValue -Payload $EndpointStatus -Path @('local_listener', 'ready') -Default $false)
  $RecordCommand = ".\scripts\chatgpt-voice-connector.ps1 -Mode RecordUrl -ConnectorUrl `"https://YOUR-STABLE-HOST$Path`" -Json"
  $IngressProfile = New-ConnectorIngressProfile -EndpointStatus $EndpointStatus -ConnectorUrlSource $ConnectorUrlSource
  $PersistentCandidate = [bool](Get-PropertyValue -Payload $IngressProfile -Name 'persistent_candidate' -Default $false)
  $PlanStatus = if ($ConnectorShapeValid -and -not $PersistentCandidate) {
    'localtunnel_fallback_replace_needed'
  } elseif ($ConnectorShapeValid) {
    'connector_url_shape_valid_record_ready'
  } elseif ($ConnectorProvided) {
    'connector_url_shape_invalid'
  } else {
    'persistent_ingress_url_needed'
  }

  return [ordered]@{
    kind = 'francis.chatgpt_voice.persistent_ingress_plan'
    ok = $true
    status = $PlanStatus
    local_endpoint = "http://$HostAddress`:$Port$Path"
    mcp_path = $Path
    connector_url = [ordered]@{
      provided = $ConnectorProvided
      shape_valid = $ConnectorShapeValid
      source = (ConvertTo-BoundedText -Value $ConnectorUrlSource -MaxLength 160)
      reason = $ConnectorReason
      persistent_candidate = $PersistentCandidate
      host = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $IngressProfile -Name 'host' -Default '') -MaxLength 256
      ingress_profile = $IngressProfile
      record_command = $RecordCommand
    }
    blockers = @($IngressProfile.blockers)
    local_mcp_listener = [ordered]@{
      ready = $LocalReady
      status = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $EndpointStatus -Name 'status' -Default '') -MaxLength 96
    }
    provider_readiness = [ordered]@{
      cloudflared_named_tunnel = Get-CommandReadiness -Name 'cloudflared' -Capability 'persistent_named_https_tunnel'
      ngrok_reserved_domain = Get-CommandReadiness -Name 'ngrok' -Capability 'reserved_domain_https_tunnel'
      caddy_reverse_proxy = Get-CommandReadiness -Name 'caddy' -Capability 'persistent_https_reverse_proxy'
      ssh_reverse_tunnel = Get-CommandReadiness -Name 'ssh' -Capability 'stable_remote_reverse_tunnel_requires_external_host'
    }
    installer_readiness = [ordered]@{
      winget = Get-CommandReadiness -Name 'winget' -Capability 'windows_package_install_operator_run'
      choco = Get-CommandReadiness -Name 'choco' -Capability 'windows_package_install_operator_run'
      scoop = Get-CommandReadiness -Name 'scoop' -Capability 'windows_package_install_operator_run'
    }
    install_command_hints = [ordered]@{
      cloudflared_winget = 'winget install --id Cloudflare.cloudflared --exact'
      ngrok_winget = 'winget install --id Ngrok.Ngrok --exact'
      caddy_winget = 'winget install --id CaddyServer.Caddy --exact'
    }
    provider_config_hints = [ordered]@{
      cloudflared_named_tunnel = 'Create a named Cloudflare Tunnel for http://127.0.0.1:8787, route a stable hostname, then record https://<hostname>/mcp.'
      ngrok_reserved_domain = 'Run ngrok with a reserved domain pointing to http://127.0.0.1:8787, then record https://<reserved-domain>/mcp.'
      caddy_reverse_proxy = 'Configure a TLS hostname reverse proxy to http://127.0.0.1:8787, then record https://<hostname>/mcp.'
      ssh_reverse_tunnel = 'Use a stable external host to reverse-tunnel port 8787 behind HTTPS, then record that host URL ending in /mcp.'
    }
    recommended_provider_order = @(
      'cloudflared_named_tunnel',
      'ngrok_reserved_domain',
      'caddy_reverse_proxy',
      'ssh_reverse_tunnel'
    )
    next_operator_steps = @(
      'choose_or_install_a_persistent_https_ingress_provider',
      'point_provider_to_local_endpoint',
      'record_the_stable_https_mcp_url_with_recordurl',
      'rerun_orb_voice_overlay_lens_validation'
    )
    localtunnel_replacement = [ordered]@{
      localtunnel_supported_only_as_explicit_fallback = $true
      persistent_ingress_required_for_stable_chatgpt_connector = $true
    }
    governance = New-GovernancePayload -ReadOnly $true -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
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

function Resolve-ConnectorUrlCandidate {
  param(
    [string]$ExplicitConnectorUrl,
    [object]$State,
    [bool]$AllowState = $true
  )

  $Explicit = ConvertTo-BoundedText -Value $ExplicitConnectorUrl -MaxLength 512
  if (-not [string]::IsNullOrWhiteSpace($Explicit)) {
    return [ordered]@{
      url = $Explicit
      source = 'argument'
    }
  }

  $EnvironmentValue = ConvertTo-BoundedText -Value $env:FRANCIS_CHATGPT_VOICE_CONNECTOR_URL -MaxLength 512
  if (-not [string]::IsNullOrWhiteSpace($EnvironmentValue)) {
    return [ordered]@{
      url = $EnvironmentValue
      source = 'environment:FRANCIS_CHATGPT_VOICE_CONNECTOR_URL'
    }
  }

  if ($AllowState -and $State) {
    $StateConnectorUrl = ConvertTo-BoundedText -Value $State.connector_url -MaxLength 512
    if (-not [string]::IsNullOrWhiteSpace($StateConnectorUrl)) {
      return [ordered]@{
        url = $StateConnectorUrl
        source = 'runtime_state'
      }
    }
  }

  return [ordered]@{
    url = ''
    source = 'none'
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
    $Path,
    '-ConnectorProbeTimeoutSeconds',
    [string]$ConnectorProbeTimeoutSeconds
  )
  if (-not [string]::IsNullOrWhiteSpace($ConnectorUrl)) {
    $Args += @('-ConnectorUrl', $ConnectorUrl)
  }
  if ($VerifyConnector) {
    $Args += '-VerifyConnector'
  }

  $PowerShellHost = Resolve-PowerShellHost
  if ([string]::IsNullOrWhiteSpace($PowerShellHost)) {
    return [ordered]@{
      kind = 'francis.chatgpt_voice.mcp.status'
      ok = $false
      status = 'powershell_host_missing'
      error = 'powershell_host_missing'
    }
  }

  $Raw = & $PowerShellHost @Args 2>&1
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

function New-LocalTunnelStabilityPayload {
  param(
    [string]$ConnectorUrl,
    [string]$ConnectorUrlSource,
    [string]$RequestedSubdomain
  )

  $Source = ConvertTo-BoundedText -Value $ConnectorUrlSource -MaxLength 160
  $Requested = ConvertTo-BoundedText -Value $RequestedSubdomain -MaxLength 160
  $ActualHost = ''
  if (-not [string]::IsNullOrWhiteSpace($ConnectorUrl)) {
    try {
      $ActualHost = ([System.Uri]$ConnectorUrl).Host
    } catch {
      $ActualHost = ''
    }
  }

  $RequestedHost = ''
  if (-not [string]::IsNullOrWhiteSpace($Requested)) {
    $RequestedHost = if ($Requested.Contains('.')) { $Requested } else { "$Requested.loca.lt" }
  }

  $Applicable = (
    $Source -eq 'localtunnel' -and
    -not [string]::IsNullOrWhiteSpace($ActualHost) -and
    -not [string]::IsNullOrWhiteSpace($RequestedHost)
  )
  $Honored = $false
  $Reason = 'not_localtunnel'
  if ($Applicable) {
    $Honored = $ActualHost.Equals($RequestedHost, [System.StringComparison]::OrdinalIgnoreCase)
    $Reason = if ($Honored) { 'localtunnel_requested_subdomain_honored' } else { 'localtunnel_requested_subdomain_not_honored' }
  } elseif ($Source -eq 'localtunnel' -and [string]::IsNullOrWhiteSpace($RequestedHost)) {
    $Reason = 'localtunnel_subdomain_not_requested'
  } elseif ($Source -eq 'localtunnel') {
    $Reason = 'localtunnel_connector_url_missing'
  }

  return [ordered]@{
    connector_url_source = $Source
    requested_subdomain = $Requested
    requested_host = $RequestedHost
    actual_host = $ActualHost
    applicable = [bool]$Applicable
    requested_subdomain_honored = [bool]($Applicable -and $Honored)
    stable_for_existing_chatgpt_connector = [bool]((-not $Applicable) -or $Honored)
    reason = $Reason
  }
}

function New-StatusPayload {
  param(
    [object]$State,
    [object]$EndpointStatus,
    [string]$ConnectorUrlSource = 'none',
    [bool]$ReadOnly = $true,
    [bool]$StartsProcess = $false,
    [bool]$OpensPublicTunnel = $false,
    [bool]$WritesData = $false
  )

  $ConnectorUrl = ''
  $McpLauncherPid = 0
  $TunnelPid = 0
  $IngressMode = ''
  $StateConnectorUrlSource = ''
  $RequestedTunnelSubdomain = ''
  $ResolvedConnectorUrlSource = ConvertTo-BoundedText -Value $ConnectorUrlSource -MaxLength 160
  if ([string]::IsNullOrWhiteSpace($ResolvedConnectorUrlSource)) {
    $ResolvedConnectorUrlSource = 'none'
  }
  if ($State) {
    $ConnectorUrl = ConvertTo-BoundedText -Value $State.connector_url -MaxLength 512
    $McpLauncherPid = [int]($State.mcp_launcher_pid)
    $TunnelPid = [int]($State.tunnel_pid)
    $IngressMode = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'ingress_mode') -MaxLength 96
    $StateConnectorUrlSource = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'connector_url_source' -Default '') -MaxLength 160
    $RequestedTunnelSubdomain = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'requested_tunnel_subdomain' -Default '') -MaxLength 160
    if (-not [string]::IsNullOrWhiteSpace($ConnectorUrl) -and $ResolvedConnectorUrlSource -eq 'none') {
      $ResolvedConnectorUrlSource = if ([string]::IsNullOrWhiteSpace($StateConnectorUrlSource)) { 'runtime_state' } else { $StateConnectorUrlSource }
    }
  }
  if ([string]::IsNullOrWhiteSpace($ConnectorUrl) -and $EndpointStatus -and $EndpointStatus.chatgpt_connector) {
    $ConnectorUrl = ConvertTo-BoundedText -Value $EndpointStatus.chatgpt_connector.connector_url.url -MaxLength 512
    if (-not [string]::IsNullOrWhiteSpace($ConnectorUrl) -and $ResolvedConnectorUrlSource -eq 'none') {
      $ResolvedConnectorUrlSource = 'endpoint_status'
    }
  }
  if ([string]::IsNullOrWhiteSpace($IngressMode) -and -not [string]::IsNullOrWhiteSpace($ConnectorUrl)) {
    $IngressMode = 'manual_status_url'
  }

  $McpReadback = Get-ProcessReadback -ProcessId $McpLauncherPid -ExpectedCommandText 'chatgpt-voice-mcp.ps1'
  $TunnelReadback = Get-ProcessReadback -ProcessId $TunnelPid -ExpectedCommandText 'localtunnel\bin\lt.js'
  $LocalTunnel = New-LocalTunnelStabilityPayload -ConnectorUrl $ConnectorUrl -ConnectorUrlSource $StateConnectorUrlSource -RequestedSubdomain $RequestedTunnelSubdomain
  $Blockers = @()
  if ([bool]$LocalTunnel.applicable -and -not [bool]$LocalTunnel.requested_subdomain_honored) {
    $Blockers += 'localtunnel_requested_subdomain_not_honored'
  }
  $Ready = $false
  if ($EndpointStatus -and [string]$EndpointStatus.status -eq 'ready_for_chatgpt_connector') {
    $Ready = $true
  }
  $Status = if ($Ready) { 'ready_for_chatgpt_connector' } elseif ($State) { 'runtime_state_observed' } else { 'not_started' }
  if ($Status -eq 'runtime_state_observed' -and $Blockers.Count -gt 0) {
    $Status = 'runtime_state_observed_unstable_localtunnel_url'
  }

  return [ordered]@{
    kind = 'francis.chatgpt_voice.connector_control'
    ok = $Ready
    status = $Status
    connector_url = $ConnectorUrl
    connector_url_source = $ResolvedConnectorUrlSource
    ingress_mode = $IngressMode
    runtime_root = $RuntimeRoot
    state_path = $statePath
    processes = [ordered]@{
      mcp_launcher = $McpReadback
      tunnel = $TunnelReadback
    }
    localtunnel = $LocalTunnel
    blockers = $Blockers
    endpoint_status = $EndpointStatus
    governance = New-GovernancePayload -ReadOnly $ReadOnly -StartsProcess $StartsProcess -OpensPublicTunnel $OpensPublicTunnel -WritesData $WritesData
  }
}

if ($Mode -eq 'Status') {
  $State = Read-State
  $Candidate = Resolve-ConnectorUrlCandidate -ExplicitConnectorUrl $ConnectorUrl -State $State
  $EndpointStatus = Invoke-EndpointStatus -ConnectorUrl ([string]$Candidate.url)
  ConvertTo-JsonOutput -Payload (New-StatusPayload -State $State -EndpointStatus $EndpointStatus -ConnectorUrlSource ([string]$Candidate.source))
  exit 0
}

if ($Mode -eq 'PlanPersistentIngress') {
  $State = Read-State
  $Candidate = Resolve-ConnectorUrlCandidate -ExplicitConnectorUrl $ConnectorUrl -State $State
  $EndpointStatus = Invoke-EndpointStatus -ConnectorUrl ([string]$Candidate.url)
  ConvertTo-JsonOutput -Payload (New-PersistentIngressPlan -EndpointStatus $EndpointStatus -ConnectorUrlSource ([string]$Candidate.source))
  exit 0
}

if ($Mode -eq 'RecordUrl') {
  $Candidate = Resolve-ConnectorUrlCandidate -ExplicitConnectorUrl $ConnectorUrl -State $null -AllowState $false
  $RecordedConnectorUrl = ConvertTo-BoundedText -Value $Candidate.url -MaxLength 512
  if ([string]::IsNullOrWhiteSpace($RecordedConnectorUrl)) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'connector_url_required'
        connector_url = ''
        connector_url_source = [string]$Candidate.source
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
        connector_url_source = [string]$Candidate.source
        runtime_root = $RuntimeRoot
        state_path = $statePath
        endpoint_status = $EndpointStatus
        blockers = @($ShapeReason)
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  $IngressProfile = New-ConnectorIngressProfile -EndpointStatus $EndpointStatus -ConnectorUrlSource ([string]$Candidate.source)
  if (-not [bool](Get-PropertyValue -Payload $IngressProfile -Name 'persistent_candidate' -Default $false)) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'connector_url_not_persistent'
        connector_url = $RecordedConnectorUrl
        connector_url_source = [string]$Candidate.source
        runtime_root = $RuntimeRoot
        state_path = $statePath
        endpoint_status = $EndpointStatus
        connector_ingress_profile = $IngressProfile
        blockers = @($IngressProfile.blockers)
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
    connector_url_source = [string]$Candidate.source
    connector_host = $ConnectorHost
    local_endpoint = "http://$HostAddress`:$Port$Path"
    mcp_launcher_pid = 0
    tunnel_pid = 0
    updated_at = (Get-Date).ToUniversalTime().ToString('o')
    governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $true
  }
  Write-State -Payload $StatePayload

  $Payload = New-StatusPayload -State (Read-State) -EndpointStatus $EndpointStatus -ConnectorUrlSource ([string]$Candidate.source) -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $true
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
$LocalTunnelStability = New-LocalTunnelStabilityPayload -ConnectorUrl $ConnectorUrl -ConnectorUrlSource 'localtunnel' -RequestedSubdomain $TunnelSubdomain
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
  connector_url_source = 'localtunnel'
  connector_host = $ConnectorHost
  requested_tunnel_subdomain = $TunnelSubdomain
  requested_connector_host = [string]$LocalTunnelStability.requested_host
  localtunnel = $LocalTunnelStability
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
$Payload = New-StatusPayload -State (Read-State) -EndpointStatus $EndpointStatus -ConnectorUrlSource 'localtunnel' -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $true -WritesData $true
$Payload.status = if (-not [bool]$LocalTunnelStability.stable_for_existing_chatgpt_connector) { 'started_unstable_localtunnel_url' } elseif ([string]$EndpointStatus.status -eq 'ready_for_chatgpt_connector') { 'started_ready' } else { 'started_unverified' }
$Payload.ok = [bool]($Payload.status -eq 'started_ready')
ConvertTo-JsonOutput -Payload $Payload
