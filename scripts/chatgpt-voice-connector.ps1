# Bounded operator control for the ChatGPT voice MCP connector.
#
# Status and PlanPersistentIngress modes are read-only. RecordUrl stores an
# operator-supplied persistent HTTPS MCP URL without opening a tunnel.
# StartCloudflaredLogin opens only the Cloudflare provider login flow when
# explicitly authorized. StartCloudflaredNamed starts a configured Cloudflare
# named tunnel only when the operator supplies a stable hostname, tunnel name,
# and -ExposePublicTunnel. RestartMcp refreshes only the local MCP launcher
# behind an existing connector URL. Start mode opens a public localtunnel URL
# only when -ExposePublicTunnel is explicitly supplied by the operator.

[CmdletBinding(PositionalBinding = $false)]
param(
  [ValidateSet('Status', 'PlanPersistentIngress', 'RecordUrl', 'StartPersistent', 'RestartMcp', 'StartCloudflaredLogin', 'StartCloudflaredNamed', 'StartCloudflaredQuick', 'Start', 'Stop')]
  [string]$Mode = 'Status',
  [string]$HostAddress = '127.0.0.1',
  [int]$Port = 8787,
  [string]$Path = '/mcp',
  [string]$ConnectorUrl = '',
  [string]$CloudflaredTunnelName = '',
  [string]$CloudflaredHostname = '',
  [string]$CloudflaredConfigPath = '',
  [string]$TunnelSubdomain = 'francis-voice-178175',
  [string]$RuntimeRoot = '',
  [switch]$ExposePublicTunnel,
  [switch]$AuthorizeCloudflaredLogin,
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
    [string]$Capability,
    [string]$ResolvedPath = ''
  )

  $Command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
  $Resolved = ConvertTo-BoundedText -Value $ResolvedPath -MaxLength 512
  $Path = if ($Command) { ConvertTo-BoundedText -Value $Command.Source -MaxLength 512 } else { $Resolved }
  $Available = [bool]($Command -or (-not [string]::IsNullOrWhiteSpace($Resolved) -and (Test-Path -LiteralPath $Resolved -PathType Leaf)))
  return [ordered]@{
    name = $Name
    capability = $Capability
    available = $Available
    path = if ($Available) { $Path } else { '' }
  }
}

function Get-CloudflaredOriginCertReadiness {
  $Candidates = [System.Collections.ArrayList]::new()
  $EnvCert = ConvertTo-BoundedText -Value $env:TUNNEL_ORIGIN_CERT -MaxLength 512
  if (-not [string]::IsNullOrWhiteSpace($EnvCert)) {
    [void]$Candidates.Add([ordered]@{
        source = 'environment:TUNNEL_ORIGIN_CERT'
        path = $EnvCert
        exists = [bool](Test-Path -LiteralPath $EnvCert -PathType Leaf)
      })
  }

  $UserProfile = ConvertTo-BoundedText -Value $env:USERPROFILE -MaxLength 512
  if (-not [string]::IsNullOrWhiteSpace($UserProfile)) {
    foreach ($Root in @('.cloudflared', '.cloudflare-warp', 'cloudflare-warp')) {
      $Path = Join-Path (Join-Path $UserProfile $Root) 'cert.pem'
      [void]$Candidates.Add([ordered]@{
          source = "default:$Root"
          path = $Path
          exists = [bool](Test-Path -LiteralPath $Path -PathType Leaf)
        })
    }
  }

  $Present = $Candidates | Where-Object { [bool](Get-PropertyValue -Payload $_ -Name 'exists' -Default $false) } | Select-Object -First 1
  return [ordered]@{
    present = [bool]$Present
    source = if ($Present) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Present -Name 'source' -Default '') -MaxLength 160 } else { '' }
    path = if ($Present) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Present -Name 'path' -Default '') -MaxLength 512 } else { '' }
    checked_path_count = @($Candidates).Count
    content_read = $false
  }
}

function Get-CloudflaredNamedTunnelReadiness {
  param(
    [string]$TunnelName = '',
    [string]$Hostname = ''
  )

  $CloudflaredPath = Resolve-CloudflaredPath
  $Readiness = Get-CommandReadiness -Name 'cloudflared' -Capability 'persistent_named_https_tunnel' -ResolvedPath $CloudflaredPath
  $OriginCert = Get-CloudflaredOriginCertReadiness
  $OriginCertPresent = [bool](Get-PropertyValue -Payload $OriginCert -Name 'present' -Default $false)
  $BoundedTunnelName = ConvertTo-BoundedText -Value $TunnelName -MaxLength 160
  $BoundedHostname = ConvertTo-CloudflaredHost -Value $Hostname
  $TunnelRequested = -not [string]::IsNullOrWhiteSpace($BoundedTunnelName)
  $TunnelPreflight = [ordered]@{
    checked = $false
    exists = $false
    output_discarded = $true
    content_read = $false
  }
  if ($OriginCertPresent -and $TunnelRequested -and [bool](Get-PropertyValue -Payload $Readiness -Name 'available' -Default $false)) {
    $TunnelPreflight = Test-CloudflaredNamedTunnelExists -CloudflaredPath $CloudflaredPath -TunnelName $BoundedTunnelName
  }
  $TunnelExists = [bool](Get-PropertyValue -Payload $TunnelPreflight -Name 'exists' -Default $false)
  $Readiness['origin_cert_present'] = $OriginCertPresent
  $Readiness['origin_cert_source'] = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $OriginCert -Name 'source' -Default '') -MaxLength 160
  $Readiness['origin_cert_path'] = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $OriginCert -Name 'path' -Default '') -MaxLength 512
  $Readiness['origin_cert_content_read'] = $false
  $Readiness['login_required'] = -not $OriginCertPresent
  $Readiness['requested_tunnel_name'] = $BoundedTunnelName
  $Readiness['requested_hostname'] = $BoundedHostname
  $Readiness['named_tunnel_requested'] = $TunnelRequested
  $Readiness['named_tunnel_exists'] = $TunnelExists
  $Readiness['named_tunnel_preflight'] = $TunnelPreflight
  $Readiness['operator_provider_setup_commands'] = if ($TunnelRequested -and -not $TunnelExists) {
    @(
      "cloudflared tunnel create $BoundedTunnelName",
      "cloudflared tunnel route dns $BoundedTunnelName $BoundedHostname"
    )
  } else {
    @()
  }
  $Readiness['next_operator_step'] = if (-not $OriginCertPresent) {
    'run_cloudflared_tunnel_login'
  } elseif ($TunnelRequested -and -not $TunnelExists) {
    'create_cloudflared_named_tunnel_and_route_hostname'
  } elseif ($TunnelRequested -and $TunnelExists) {
    'start_cloudflared_named_tunnel'
  } else {
    'create_or_start_cloudflared_named_tunnel'
  }
  return $Readiness
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
  $KnownCloudflaredQuickTunnel = (
    $Source -eq 'cloudflared_quick' -or
    (-not [string]::IsNullOrWhiteSpace($ConnectorHostName) -and $ConnectorHostName.EndsWith('.trycloudflare.com', [System.StringComparison]::OrdinalIgnoreCase))
  )
  $PersistentCandidate = [bool]($ConnectorShapeValid -and -not $KnownLocalTunnel -and -not $KnownCloudflaredQuickTunnel)
  $Profile = if (-not $ConnectorProvided) {
    'missing'
  } elseif (-not $ConnectorShapeValid) {
    'invalid_https_mcp_url'
  } elseif ($KnownLocalTunnel) {
    'localtunnel_ephemeral'
  } elseif ($KnownCloudflaredQuickTunnel) {
    'cloudflared_quick_ephemeral'
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
  } elseif ($KnownCloudflaredQuickTunnel) {
    $Blockers += 'cloudflared_quick_url_is_not_persistent_ingress'
  }

  return [ordered]@{
    profile = $Profile
    source = $Source
    host = $ConnectorHostName
    known_localtunnel = [bool]$KnownLocalTunnel
    known_cloudflared_quick_tunnel = [bool]$KnownCloudflaredQuickTunnel
    persistent_candidate = [bool]$PersistentCandidate
    blockers = $Blockers
  }
}

function New-PersistentIngressOperatorHandoff {
  param(
    [string]$HostAddress,
    [int]$Port,
    [string]$Path
  )

  $LocalEndpoint = "http://$HostAddress`:$Port$Path"
  $StableUrl = "https://YOUR-STABLE-HOST$Path"
  return [ordered]@{
    kind = 'francis.chatgpt_voice.persistent_ingress_operator_handoff'
    safe_to_display = $true
    read_only_plan = $true
    installs_provider = $false
    opens_tunnel = $false
    writes_state = $false
    requires_operator_provider_account_or_hostname = $true
    preferred_provider = 'cloudflared_named_tunnel'
    local_endpoint = $LocalEndpoint
    stable_url_placeholder = $StableUrl
    install_commands = [ordered]@{
      cloudflared_winget = 'winget install --id Cloudflare.cloudflared --exact --accept-source-agreements --accept-package-agreements'
      ngrok_winget = 'winget install --id Ngrok.Ngrok --exact --accept-source-agreements --accept-package-agreements'
      caddy_winget = 'winget install --id CaddyServer.Caddy --exact --accept-source-agreements --accept-package-agreements'
    }
    cloudflared_named_tunnel_steps = @(
      'Install cloudflared or confirm it is already available on PATH or in a standard install location.',
      'Run cloudflared tunnel login and complete the provider login in the browser.',
      'Create a named tunnel for Francis and route a stable hostname to the local MCP endpoint.',
      "Point the ingress service at $LocalEndpoint.",
      "Record the resulting stable connector URL as $StableUrl."
    )
    ngrok_reserved_domain_steps = @(
      'Install ngrok or confirm it is already available on PATH.',
      'Authenticate ngrok with an operator-owned account token outside Francis.',
      'Reserve a stable HTTPS domain in ngrok.',
      "Forward the reserved domain to $LocalEndpoint.",
      "Record the resulting stable connector URL as $StableUrl."
    )
    caddy_reverse_proxy_steps = @(
      'Install caddy or confirm it is already available on PATH.',
      'Configure a stable operator-owned HTTPS hostname.',
      "Reverse proxy that hostname to $LocalEndpoint.",
      "Record the resulting stable connector URL as $StableUrl."
    )
    governed_handoff_commands = [ordered]@{
      start_cloudflared_login = ".\scripts\chatgpt-voice-connector.ps1 -Mode StartCloudflaredLogin -AuthorizeCloudflaredLogin -Json"
      plan_cloudflared_named = ".\scripts\chatgpt-voice-connector.ps1 -Mode PlanPersistentIngress -CloudflaredTunnelName `"francis`" -CloudflaredHostname `"YOUR-STABLE-HOST`" -Json"
      record_url = ".\scripts\chatgpt-voice-connector.ps1 -Mode RecordUrl -ConnectorUrl `"$StableUrl`" -Json"
      start_persistent_mcp = ".\scripts\chatgpt-voice-connector.ps1 -Mode StartPersistent -ConnectorUrl `"$StableUrl`" -VerifyConnector -Json"
      start_cloudflared_named = ".\scripts\chatgpt-voice-connector.ps1 -Mode StartCloudflaredNamed -CloudflaredTunnelName `"francis`" -CloudflaredHostname `"YOUR-STABLE-HOST`" -ExposePublicTunnel -VerifyConnector -Json"
      validate_bridge = ".\scripts\orb-voice-overlay-lens-validation.ps1 -ConnectorUrl `"$StableUrl`" -VerifyConnector"
      monitor_command_palette = ".\scripts\lens-command-palette-monitor.ps1 -Mode Probe -EnableChatGptConnectorChecks -ChatGptConnectorUrl `"$StableUrl`" -VerifyChatGptConnector -RequirePersistentChatGptIngress"
    }
  }
}

function New-PersistentIngressPlan {
  param(
    [object]$EndpointStatus,
    [string]$ConnectorUrlSource = 'none',
    [string]$CloudflaredTunnelName = '',
    [string]$CloudflaredHostname = ''
  )

  $ConnectorShapeValid = [bool](Get-NestedPropertyValue -Payload $EndpointStatus -Path @('chatgpt_connector', 'connector_url', 'shape_valid') -Default $false)
  $ConnectorProvided = [bool](Get-NestedPropertyValue -Payload $EndpointStatus -Path @('chatgpt_connector', 'connector_url', 'provided') -Default $false)
  $ConnectorReason = ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $EndpointStatus -Path @('chatgpt_connector', 'connector_url', 'reason') -Default 'connector_url_not_provided') -MaxLength 160
  $LocalReady = [bool](Get-NestedPropertyValue -Payload $EndpointStatus -Path @('local_listener', 'ready') -Default $false)
  $RecordCommand = ".\scripts\chatgpt-voice-connector.ps1 -Mode RecordUrl -ConnectorUrl `"https://YOUR-STABLE-HOST$Path`" -Json"
  $IngressProfile = New-ConnectorIngressProfile -EndpointStatus $EndpointStatus -ConnectorUrlSource $ConnectorUrlSource
  $OperatorHandoff = New-PersistentIngressOperatorHandoff -HostAddress $HostAddress -Port $Port -Path $Path
  $PersistentCandidate = [bool](Get-PropertyValue -Payload $IngressProfile -Name 'persistent_candidate' -Default $false)
  $IngressProfileName = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $IngressProfile -Name 'profile' -Default '') -MaxLength 96
  $PlanStatus = if ($ConnectorShapeValid -and $IngressProfileName -eq 'localtunnel_ephemeral') {
    'localtunnel_fallback_replace_needed'
  } elseif ($ConnectorShapeValid -and $IngressProfileName -eq 'cloudflared_quick_ephemeral') {
    'cloudflared_quick_tunnel_replace_needed'
  } elseif ($ConnectorShapeValid -and -not $PersistentCandidate) {
    'ephemeral_tunnel_replace_needed'
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
      cloudflared_named_tunnel = Get-CloudflaredNamedTunnelReadiness -TunnelName $CloudflaredTunnelName -Hostname $CloudflaredHostname
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
    operator_handoff = $OperatorHandoff
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

  $StatusTimeoutSeconds = [Math]::Max(3, [Math]::Min(90, $ConnectorProbeTimeoutSeconds + 8))
  $TempBase = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-mcp-status-{0}" -f ([guid]::NewGuid().ToString('N')))
  $StdoutPath = "$TempBase.stdout.log"
  $StderrPath = "$TempBase.stderr.log"
  $Process = $null
  try {
    $StartProcessArgs = @{
      FilePath = $PowerShellHost
      ArgumentList = $Args
      PassThru = $true
      RedirectStandardOutput = $StdoutPath
      RedirectStandardError = $StderrPath
    }
    if ($PSVersionTable.PSEdition -eq 'Desktop' -or $IsWindows) {
      $StartProcessArgs.WindowStyle = 'Hidden'
    }
    $Process = Start-Process @StartProcessArgs
    Wait-Process -Id $Process.Id -Timeout $StatusTimeoutSeconds -ErrorAction SilentlyContinue
    $StillRunning = Get-Process -Id $Process.Id -ErrorAction SilentlyContinue
    if ($StillRunning) {
      Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
      return [ordered]@{
        kind = 'francis.chatgpt_voice.mcp.status'
        ok = $false
        status = 'status_timeout'
        error = 'mcp_status_readback_timeout'
        timeout_seconds = $StatusTimeoutSeconds
        connector_url = ConvertTo-BoundedText -Value $ConnectorUrl -MaxLength 512
      }
    }
  } catch {
    return [ordered]@{
      kind = 'francis.chatgpt_voice.mcp.status'
      ok = $false
      status = 'status_start_failed'
      error = ConvertTo-BoundedText -Value $_.Exception.Message -MaxLength 512
      connector_url = ConvertTo-BoundedText -Value $ConnectorUrl -MaxLength 512
    }
  }

  $Raw = @()
  if (Test-Path -LiteralPath $StdoutPath) {
    $Raw += Get-Content -LiteralPath $StdoutPath -ErrorAction SilentlyContinue
  }
  $Stderr = @()
  if (Test-Path -LiteralPath $StderrPath) {
    $Stderr += Get-Content -LiteralPath $StderrPath -ErrorAction SilentlyContinue
  }
  try {
    return ($Raw -join "`n") | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $Observed = @($Raw) + @($Stderr)
    return [ordered]@{
      kind = 'francis.chatgpt_voice.mcp.status'
      ok = $false
      status = 'status_parse_failed'
      error = ConvertTo-BoundedText -Value ($Observed -join "`n") -MaxLength 512
    }
  } finally {
    Remove-Item -LiteralPath $StdoutPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $StderrPath -Force -ErrorAction SilentlyContinue
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

function Resolve-CloudflaredPath {
  $Command = Get-Command cloudflared -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($Command) {
    return [string]$Command.Source
  }

  $KnownPaths = @(
    (Join-Path ${env:ProgramFiles(x86)} 'cloudflared\cloudflared.exe'),
    (Join-Path $env:ProgramFiles 'cloudflared\cloudflared.exe')
  )
  foreach ($KnownPath in $KnownPaths) {
    if (-not [string]::IsNullOrWhiteSpace($KnownPath) -and (Test-Path -LiteralPath $KnownPath -PathType Leaf)) {
      return $KnownPath
    }
  }
  return ''
}

function Test-CloudflaredNamedTunnelExists {
  param(
    [string]$CloudflaredPath,
    [string]$TunnelName
  )

  $Result = [ordered]@{
    checked = $false
    exists = $false
    exit_code = $null
    output_discarded = $true
    content_read = $false
    error = ''
  }

  if ([string]::IsNullOrWhiteSpace($CloudflaredPath) -or [string]::IsNullOrWhiteSpace($TunnelName)) {
    return $Result
  }

  try {
    $Result.checked = $true
    & $CloudflaredPath tunnel info $TunnelName *> $null
    $ExitCode = if ($null -ne $LASTEXITCODE) { [int]$LASTEXITCODE } else { 0 }
    $Result.exit_code = $ExitCode
    $Result.exists = [bool]($ExitCode -eq 0)
  } catch {
    $Result.exit_code = -1
    $Result.error = ConvertTo-BoundedText -Value $_.Exception.Message -MaxLength 512
  }

  return $Result
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

function Wait-ForCloudflaredQuickTunnelUrl {
  param(
    [string]$StdoutPath,
    [string]$StderrPath,
    [int]$TimeoutSeconds = 30
  )

  $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $Deadline) {
    $Text = ''
    if (Test-Path -LiteralPath $StdoutPath) {
      $Text += Get-Content -LiteralPath $StdoutPath -Raw -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $StderrPath) {
      $Text += "`n" + (Get-Content -LiteralPath $StderrPath -Raw -ErrorAction SilentlyContinue)
    }
    $Match = [regex]::Match($Text, 'https://[a-zA-Z0-9-]+\.trycloudflare\.com')
    if ($Match.Success) {
      return $Match.Value.TrimEnd('/')
    }
    Start-Sleep -Milliseconds 500
  }
  return ''
}

function Start-McpLauncher {
  param(
    [string]$ConnectorHost,
    [string]$StdoutPath = '',
    [string]$StderrPath = ''
  )

  $PowerShellHost = Resolve-PowerShellHost
  if ([string]::IsNullOrWhiteSpace($PowerShellHost)) {
    return $null
  }

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
    $Path
  )
  $BoundedConnectorHost = ConvertTo-BoundedText -Value $ConnectorHost -MaxLength 256
  if (-not [string]::IsNullOrWhiteSpace($BoundedConnectorHost)) {
    $McpArgs += @('-AllowedHost', $BoundedConnectorHost)
  }

  return Start-Process -FilePath $PowerShellHost -ArgumentList $McpArgs -PassThru -WindowStyle Hidden
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

function Wait-ForKnownProcessExit {
  param(
    [int]$ProcessId,
    [string]$ExpectedCommandText,
    [int]$TimeoutSeconds = 8
  )

  if ($ProcessId -le 0) { return $true }
  $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $Deadline) {
    $Readback = Get-ProcessReadback -ProcessId $ProcessId -ExpectedCommandText $ExpectedCommandText
    if (-not [bool]$Readback.alive) { return $true }
    if (-not [bool]$Readback.command_matches_expected) { return $true }
    Start-Sleep -Milliseconds 250
  }
  $FinalReadback = Get-ProcessReadback -ProcessId $ProcessId -ExpectedCommandText $ExpectedCommandText
  return (-not [bool]$FinalReadback.alive) -or (-not [bool]$FinalReadback.command_matches_expected)
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

function New-CloudflaredQuickTunnelPayload {
  param(
    [string]$ConnectorUrl,
    [string]$ConnectorUrlSource
  )

  $Source = ConvertTo-BoundedText -Value $ConnectorUrlSource -MaxLength 160
  $ActualHost = ''
  if (-not [string]::IsNullOrWhiteSpace($ConnectorUrl)) {
    try {
      $ActualHost = ([System.Uri]$ConnectorUrl).Host
    } catch {
      $ActualHost = ''
    }
  }
  $Applicable = (
    $Source -eq 'cloudflared_quick' -or
    (-not [string]::IsNullOrWhiteSpace($ActualHost) -and $ActualHost.EndsWith('.trycloudflare.com', [System.StringComparison]::OrdinalIgnoreCase))
  )

  return [ordered]@{
    connector_url_source = $Source
    actual_host = $ActualHost
    applicable = [bool]$Applicable
    quick_tunnel = [bool]$Applicable
    persistent_candidate = $false
    stable_for_existing_chatgpt_connector = [bool](-not $Applicable)
    reason = if ($Applicable) { 'cloudflared_quick_tunnel_ephemeral' } else { 'not_cloudflared_quick_tunnel' }
  }
}

function New-CloudflaredNamedTunnelPayload {
  param(
    [string]$ConnectorUrl,
    [string]$ConnectorUrlSource,
    [string]$TunnelName,
    [string]$Hostname,
    [string]$ConfigPath = ''
  )

  $Source = ConvertTo-BoundedText -Value $ConnectorUrlSource -MaxLength 160
  $BoundedTunnelName = ConvertTo-BoundedText -Value $TunnelName -MaxLength 160
  $BoundedHostname = ConvertTo-BoundedText -Value $Hostname -MaxLength 256
  $ActualHost = ''
  if (-not [string]::IsNullOrWhiteSpace($ConnectorUrl)) {
    try {
      $ActualHost = ([System.Uri]$ConnectorUrl).Host
    } catch {
      $ActualHost = ''
    }
  }

  $Applicable = (
    $Source -eq 'cloudflared_named' -or
    (-not [string]::IsNullOrWhiteSpace($BoundedTunnelName) -and -not [string]::IsNullOrWhiteSpace($BoundedHostname))
  )

  return [ordered]@{
    connector_url_source = $Source
    tunnel_name = $BoundedTunnelName
    hostname = $BoundedHostname
    actual_host = $ActualHost
    config_path = ConvertTo-BoundedText -Value $ConfigPath -MaxLength 512
    applicable = [bool]$Applicable
    quick_tunnel = $false
    persistent_candidate = [bool]$Applicable
    stable_for_existing_chatgpt_connector = [bool]$Applicable
    reason = if ($Applicable) { 'cloudflared_named_tunnel' } else { 'not_cloudflared_named_tunnel' }
  }
}

function Get-TunnelExpectedCommandText {
  param(
    [string]$ConnectorUrlSource,
    [string]$IngressMode
  )

  if (
    $ConnectorUrlSource -eq 'cloudflared_quick' -or
    $ConnectorUrlSource -eq 'cloudflared_named' -or
    $IngressMode -eq 'cloudflared_quick_ephemeral' -or
    $IngressMode -eq 'cloudflared_named_tunnel'
  ) {
    return 'cloudflared'
  }

  return 'localtunnel\bin\lt.js'
}

function Get-TunnelStopLabel {
  param(
    [string]$ConnectorUrlSource,
    [string]$IngressMode,
    [string]$Fallback = 'tunnel'
  )

  if ($ConnectorUrlSource -eq 'cloudflared_named' -or $IngressMode -eq 'cloudflared_named_tunnel') {
    return 'cloudflared_named_tunnel'
  }
  if ($ConnectorUrlSource -eq 'cloudflared_quick' -or $IngressMode -eq 'cloudflared_quick_ephemeral') {
    return 'cloudflared_quick_tunnel'
  }
  if ($Fallback -eq 'localtunnel_fallback') {
    return 'localtunnel_fallback'
  }
  return 'tunnel'
}

function ConvertTo-CloudflaredHost {
  param([string]$Value)

  $Bounded = ConvertTo-BoundedText -Value $Value -MaxLength 512
  if ([string]::IsNullOrWhiteSpace($Bounded)) {
    return ''
  }
  if ($Bounded -match '^https?://') {
    try {
      return ([System.Uri]$Bounded).Host
    } catch {
      return ''
    }
  }
  return $Bounded.Trim().TrimEnd('/').Split('/')[0]
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
  $CloudflaredNamedTunnel = $null
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
    $CloudflaredNamedTunnel = Get-PropertyValue -Payload $State -Name 'cloudflared_named_tunnel' -Default $null
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
  $TunnelExpectedCommandText = Get-TunnelExpectedCommandText -ConnectorUrlSource $StateConnectorUrlSource -IngressMode $IngressMode
  $TunnelReadback = Get-ProcessReadback -ProcessId $TunnelPid -ExpectedCommandText $TunnelExpectedCommandText
  $LocalTunnel = New-LocalTunnelStabilityPayload -ConnectorUrl $ConnectorUrl -ConnectorUrlSource $StateConnectorUrlSource -RequestedSubdomain $RequestedTunnelSubdomain
  $CloudflaredQuickTunnel = New-CloudflaredQuickTunnelPayload -ConnectorUrl $ConnectorUrl -ConnectorUrlSource $StateConnectorUrlSource
  if ($null -eq $CloudflaredNamedTunnel) {
    $CloudflaredNamedTunnel = New-CloudflaredNamedTunnelPayload -ConnectorUrl $ConnectorUrl -ConnectorUrlSource $StateConnectorUrlSource -TunnelName '' -Hostname '' -ConfigPath ''
  }
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
    cloudflared_quick_tunnel = $CloudflaredQuickTunnel
    cloudflared_named_tunnel = $CloudflaredNamedTunnel
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
  ConvertTo-JsonOutput -Payload (New-PersistentIngressPlan -EndpointStatus $EndpointStatus -ConnectorUrlSource ([string]$Candidate.source) -CloudflaredTunnelName $CloudflaredTunnelName -CloudflaredHostname $CloudflaredHostname)
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

if ($Mode -eq 'StartPersistent') {
  $State = Read-State
  $Candidate = Resolve-ConnectorUrlCandidate -ExplicitConnectorUrl $ConnectorUrl -State $State -AllowState $true
  $PersistentConnectorUrl = ConvertTo-BoundedText -Value ([string]$Candidate.url) -MaxLength 512
  if ([string]::IsNullOrWhiteSpace($PersistentConnectorUrl)) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'persistent_connector_url_required'
        connector_url = ''
        connector_url_source = [string]$Candidate.source
        runtime_root = $RuntimeRoot
        state_path = $statePath
        blockers = @('connector_url_required')
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  $EndpointStatus = Invoke-EndpointStatus -ConnectorUrl $PersistentConnectorUrl
  $ShapeValid = [bool](Get-NestedPropertyValue -Payload $EndpointStatus -Path @('chatgpt_connector', 'connector_url', 'shape_valid') -Default $false)
  $ShapeReason = ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $EndpointStatus -Path @('chatgpt_connector', 'connector_url', 'reason') -Default 'connector_url_shape_invalid') -MaxLength 160
  if (-not $ShapeValid) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'connector_url_shape_invalid'
        connector_url = $PersistentConnectorUrl
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
        connector_url = $PersistentConnectorUrl
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

  $ConnectorHost = ([System.Uri]$PersistentConnectorUrl).Host
  $PreviousListenerPid = [int](Get-NestedPropertyValue -Payload $EndpointStatus -Path @('local_listener', 'owning_process') -Default 0)
  $PreviousLauncherPid = if ($State) { [int](Get-PropertyValue -Payload $State -Name 'mcp_launcher_pid' -Default 0) } else { 0 }
  $PreviousTunnelPid = if ($State) { [int](Get-PropertyValue -Payload $State -Name 'tunnel_pid' -Default 0) } else { 0 }
  $PreviousConnectorUrlSource = if ($State) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'connector_url_source' -Default '') -MaxLength 160 } else { '' }
  $PreviousIngressMode = if ($State) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'ingress_mode' -Default '') -MaxLength 96 } else { '' }
  $PreviousTunnelExpectedCommandText = Get-TunnelExpectedCommandText -ConnectorUrlSource $PreviousConnectorUrlSource -IngressMode $PreviousIngressMode
  $Stopped = @()

  if ($PreviousListenerPid -gt 0) {
    $ListenerReadback = Get-ProcessReadback -ProcessId $PreviousListenerPid -ExpectedCommandText 'francis.mcp_gateway.server'
    if ([bool]$ListenerReadback.alive -and -not [bool]$ListenerReadback.command_matches_expected) {
      ConvertTo-JsonOutput -Payload ([ordered]@{
          kind = 'francis.chatgpt_voice.connector_control'
          ok = $false
          status = 'mcp_existing_listener_not_recognized'
          connector_url = $PersistentConnectorUrl
          runtime_root = $RuntimeRoot
          state_path = $statePath
          listener = $ListenerReadback
          blockers = @('existing_listener_not_francis_mcp_gateway')
          governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
        })
      exit 0
    }

    try {
      if (Stop-KnownProcess -ProcessId $PreviousListenerPid -ExpectedCommandText 'francis.mcp_gateway.server') {
        $Stopped += 'mcp_server_listener'
      }
    } catch {
      ConvertTo-JsonOutput -Payload ([ordered]@{
          kind = 'francis.chatgpt_voice.connector_control'
          ok = $false
          status = 'mcp_existing_listener_stop_failed'
          connector_url = $PersistentConnectorUrl
          runtime_root = $RuntimeRoot
          state_path = $statePath
          listener = $ListenerReadback
          error = ConvertTo-BoundedText -Value $_.Exception.Message -MaxLength 512
          blockers = @('existing_listener_stop_failed')
          governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
        })
      exit 0
    }

    if (-not (Wait-ForKnownProcessExit -ProcessId $PreviousListenerPid -ExpectedCommandText 'francis.mcp_gateway.server')) {
      ConvertTo-JsonOutput -Payload ([ordered]@{
          kind = 'francis.chatgpt_voice.connector_control'
          ok = $false
          status = 'mcp_existing_listener_still_active'
          connector_url = $PersistentConnectorUrl
          runtime_root = $RuntimeRoot
          state_path = $statePath
          listener = (Get-ProcessReadback -ProcessId $PreviousListenerPid -ExpectedCommandText 'francis.mcp_gateway.server')
          blockers = @('existing_listener_still_active')
          governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
        })
      exit 0
    }
  }

  if ($PreviousLauncherPid -gt 0) {
    try {
      if (Stop-KnownProcess -ProcessId $PreviousLauncherPid -ExpectedCommandText 'chatgpt-voice-mcp.ps1') {
        $Stopped += 'mcp_launcher'
      }
    } catch {
      ConvertTo-JsonOutput -Payload ([ordered]@{
          kind = 'francis.chatgpt_voice.connector_control'
          ok = $false
          status = 'mcp_launcher_stop_failed'
          connector_url = $PersistentConnectorUrl
          runtime_root = $RuntimeRoot
          state_path = $statePath
          error = ConvertTo-BoundedText -Value $_.Exception.Message -MaxLength 512
          blockers = @('mcp_launcher_stop_failed')
          governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
        })
      exit 0
    }
    [void](Wait-ForKnownProcessExit -ProcessId $PreviousLauncherPid -ExpectedCommandText 'chatgpt-voice-mcp.ps1')
  }

  if ($PreviousTunnelPid -gt 0) {
    try {
      if (Stop-KnownProcess -ProcessId $PreviousTunnelPid -ExpectedCommandText $PreviousTunnelExpectedCommandText) {
        $Stopped += Get-TunnelStopLabel -ConnectorUrlSource $PreviousConnectorUrlSource -IngressMode $PreviousIngressMode -Fallback 'localtunnel_fallback'
      }
    } catch {
      ConvertTo-JsonOutput -Payload ([ordered]@{
          kind = 'francis.chatgpt_voice.connector_control'
          ok = $false
          status = 'previous_tunnel_stop_failed'
          connector_url = $PersistentConnectorUrl
          runtime_root = $RuntimeRoot
          state_path = $statePath
          error = ConvertTo-BoundedText -Value $_.Exception.Message -MaxLength 512
          blockers = @('previous_tunnel_stop_failed')
          governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
        })
      exit 0
    }
    [void](Wait-ForKnownProcessExit -ProcessId $PreviousTunnelPid -ExpectedCommandText $PreviousTunnelExpectedCommandText)
  }

  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  $McpProcess = Start-McpLauncher -ConnectorHost $ConnectorHost
  if (-not $McpProcess) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'powershell_host_missing'
        connector_url = $PersistentConnectorUrl
        runtime_root = $RuntimeRoot
        state_path = $statePath
        stopped = $Stopped
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }
  Start-Sleep -Seconds 4

  $StartedAt = (Get-Date).ToUniversalTime().ToString('o')
  $StatePayload = [ordered]@{
    kind = 'francis.chatgpt_voice.connector_control.state'
    status = 'persistent_mcp_started'
    ingress_mode = 'persistent_https'
    connector_url = $PersistentConnectorUrl
    connector_url_source = [string]$Candidate.source
    connector_host = $ConnectorHost
    local_endpoint = "http://$HostAddress`:$Port$Path"
    mcp_launcher_pid = $McpProcess.Id
    previous_mcp_launcher_pid = $PreviousLauncherPid
    previous_mcp_listener_pid = $PreviousListenerPid
    previous_tunnel_pid = $PreviousTunnelPid
    tunnel_pid = 0
    mcp_stdout = ''
    mcp_stderr = ''
    mcp_log_capture = 'not_captured_detached_start'
    stopped = $Stopped
    started_at = $StartedAt
    updated_at = $StartedAt
    governance = New-GovernancePayload -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $false -WritesData $true
  }
  Write-State -Payload $StatePayload

  $EndpointAfter = Invoke-EndpointStatus -ConnectorUrl $PersistentConnectorUrl
  $Payload = New-StatusPayload -State (Read-State) -EndpointStatus $EndpointAfter -ConnectorUrlSource ([string]$Candidate.source) -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $false -WritesData $true
  $ConnectorReady = [string]$EndpointAfter.status -eq 'ready_for_chatgpt_connector'
  $LocalReady = [bool](Get-NestedPropertyValue -Payload $EndpointAfter -Path @('local_listener', 'ready') -Default $false)
  $Payload.status = if ($ConnectorReady) {
    'persistent_mcp_started_ready'
  } elseif ($LocalReady -and -not $VerifyConnector) {
    'persistent_mcp_started_local_ready'
  } elseif ($LocalReady) {
    'persistent_mcp_started_unverified'
  } else {
    'persistent_mcp_started_failed'
  }
  $Payload.ok = [bool]($ConnectorReady -or ($LocalReady -and -not $VerifyConnector))
  $Payload.persistent_start = [ordered]@{
    stopped = $Stopped
    previous_mcp_launcher_pid = $PreviousLauncherPid
    previous_mcp_listener_pid = $PreviousListenerPid
    previous_tunnel_pid = $PreviousTunnelPid
    mcp_launcher_pid = $McpProcess.Id
    connector_url = $PersistentConnectorUrl
    connector_host = $ConnectorHost
    mcp_log_capture = 'not_captured_detached_start'
    public_tunnel_started = $false
  }
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

if ($Mode -eq 'RestartMcp') {
  $State = Read-State
  if (-not $State) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'mcp_runtime_state_required'
        connector_url = ''
        runtime_root = $RuntimeRoot
        state_path = $statePath
        blockers = @('runtime_state_required')
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  $ExistingConnectorUrl = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'connector_url' -Default '') -MaxLength 512
  if ([string]::IsNullOrWhiteSpace($ExistingConnectorUrl)) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'mcp_connector_url_required'
        connector_url = ''
        runtime_root = $RuntimeRoot
        state_path = $statePath
        blockers = @('connector_url_required')
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  try {
    $ConnectorHost = ([System.Uri]$ExistingConnectorUrl).Host
  } catch {
    $ConnectorHost = ''
  }
  if ([string]::IsNullOrWhiteSpace($ConnectorHost)) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'mcp_connector_url_invalid'
        connector_url = $ExistingConnectorUrl
        runtime_root = $RuntimeRoot
        state_path = $statePath
        blockers = @('connector_url_missing_host')
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  $ConnectorUrlSource = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'connector_url_source' -Default 'runtime_state') -MaxLength 160
  if ([string]::IsNullOrWhiteSpace($ConnectorUrlSource)) {
    $ConnectorUrlSource = 'runtime_state'
  }

  $EndpointBefore = Invoke-EndpointStatus -ConnectorUrl $ExistingConnectorUrl
  $PreviousListenerPid = [int](Get-NestedPropertyValue -Payload $EndpointBefore -Path @('local_listener', 'owning_process') -Default 0)
  $PreviousLauncherPid = [int](Get-PropertyValue -Payload $State -Name 'mcp_launcher_pid' -Default 0)
  $Stopped = @()

  if ($PreviousListenerPid -gt 0) {
    $ListenerReadback = Get-ProcessReadback -ProcessId $PreviousListenerPid -ExpectedCommandText 'francis.mcp_gateway.server'
    if ([bool]$ListenerReadback.alive -and -not [bool]$ListenerReadback.command_matches_expected) {
      ConvertTo-JsonOutput -Payload ([ordered]@{
          kind = 'francis.chatgpt_voice.connector_control'
          ok = $false
          status = 'mcp_existing_listener_not_recognized'
          connector_url = $ExistingConnectorUrl
          runtime_root = $RuntimeRoot
          state_path = $statePath
          listener = $ListenerReadback
          blockers = @('existing_listener_not_francis_mcp_gateway')
          governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
        })
      exit 0
    }

    try {
      if (Stop-KnownProcess -ProcessId $PreviousListenerPid -ExpectedCommandText 'francis.mcp_gateway.server') {
        $Stopped += 'mcp_server_listener'
      }
    } catch {
      ConvertTo-JsonOutput -Payload ([ordered]@{
          kind = 'francis.chatgpt_voice.connector_control'
          ok = $false
          status = 'mcp_existing_listener_stop_failed'
          connector_url = $ExistingConnectorUrl
          runtime_root = $RuntimeRoot
          state_path = $statePath
          listener = $ListenerReadback
          error = ConvertTo-BoundedText -Value $_.Exception.Message -MaxLength 512
          blockers = @('existing_listener_stop_failed')
          governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
        })
      exit 0
    }

    if (-not (Wait-ForKnownProcessExit -ProcessId $PreviousListenerPid -ExpectedCommandText 'francis.mcp_gateway.server')) {
      ConvertTo-JsonOutput -Payload ([ordered]@{
          kind = 'francis.chatgpt_voice.connector_control'
          ok = $false
          status = 'mcp_existing_listener_still_active'
          connector_url = $ExistingConnectorUrl
          runtime_root = $RuntimeRoot
          state_path = $statePath
          listener = (Get-ProcessReadback -ProcessId $PreviousListenerPid -ExpectedCommandText 'francis.mcp_gateway.server')
          blockers = @('existing_listener_still_active')
          governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
        })
      exit 0
    }
  }

  if ($PreviousLauncherPid -gt 0) {
    try {
      if (Stop-KnownProcess -ProcessId $PreviousLauncherPid -ExpectedCommandText 'chatgpt-voice-mcp.ps1') {
        $Stopped += 'mcp_launcher'
      }
    } catch {
      ConvertTo-JsonOutput -Payload ([ordered]@{
          kind = 'francis.chatgpt_voice.connector_control'
          ok = $false
          status = 'mcp_launcher_stop_failed'
          connector_url = $ExistingConnectorUrl
          runtime_root = $RuntimeRoot
          state_path = $statePath
          error = ConvertTo-BoundedText -Value $_.Exception.Message -MaxLength 512
          blockers = @('mcp_launcher_stop_failed')
          governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
        })
      exit 0
    }
    [void](Wait-ForKnownProcessExit -ProcessId $PreviousLauncherPid -ExpectedCommandText 'chatgpt-voice-mcp.ps1')
  }

  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  $McpProcess = Start-McpLauncher -ConnectorHost $ConnectorHost
  if (-not $McpProcess) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'powershell_host_missing'
        connector_url = $ExistingConnectorUrl
        runtime_root = $RuntimeRoot
        state_path = $statePath
        stopped = $Stopped
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }
  Start-Sleep -Seconds 4

  $PreviousRestartCount = 0
  try {
    $PreviousRestartCount = [int](Get-PropertyValue -Payload $State -Name 'mcp_restart_count' -Default 0)
  } catch {
    $PreviousRestartCount = 0
  }
  $RestartedAt = (Get-Date).ToUniversalTime().ToString('o')
  $StatePayload = [ordered]@{
    kind = 'francis.chatgpt_voice.connector_control.state'
    status = 'mcp_restarted'
    connector_url = $ExistingConnectorUrl
    connector_url_source = $ConnectorUrlSource
    connector_host = $ConnectorHost
    ingress_mode = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'ingress_mode' -Default '') -MaxLength 96
    requested_tunnel_subdomain = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'requested_tunnel_subdomain' -Default '') -MaxLength 160
    requested_connector_host = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'requested_connector_host' -Default '') -MaxLength 160
    localtunnel = Get-PropertyValue -Payload $State -Name 'localtunnel' -Default $null
    local_endpoint = "http://$HostAddress`:$Port$Path"
    mcp_launcher_pid = $McpProcess.Id
    previous_mcp_launcher_pid = $PreviousLauncherPid
    previous_mcp_listener_pid = $PreviousListenerPid
    tunnel_pid = [int](Get-PropertyValue -Payload $State -Name 'tunnel_pid' -Default 0)
    mcp_stdout = ''
    mcp_stderr = ''
    mcp_log_capture = 'not_captured_detached_start'
    tunnel_stdout = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'tunnel_stdout' -Default '') -MaxLength 512
    tunnel_stderr = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'tunnel_stderr' -Default '') -MaxLength 512
    stopped = $Stopped
    mcp_restart_count = $PreviousRestartCount + 1
    last_mcp_restart_at = $RestartedAt
    updated_at = $RestartedAt
    governance = New-GovernancePayload -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $false -WritesData $true
  }
  Write-State -Payload $StatePayload

  $EndpointStatus = Invoke-EndpointStatus -ConnectorUrl $ExistingConnectorUrl
  $Payload = New-StatusPayload -State (Read-State) -EndpointStatus $EndpointStatus -ConnectorUrlSource $ConnectorUrlSource -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $false -WritesData $true
  $ConnectorReady = [string]$EndpointStatus.status -eq 'ready_for_chatgpt_connector'
  $LocalReady = [bool](Get-NestedPropertyValue -Payload $EndpointStatus -Path @('local_listener', 'ready') -Default $false)
  $Payload.status = if ($ConnectorReady) { 'mcp_restarted_ready' } elseif ($LocalReady) { 'mcp_restarted_local_ready' } else { 'mcp_restarted_unverified' }
  $Payload.ok = [bool]$ConnectorReady
  $Payload.restart = [ordered]@{
    stopped = $Stopped
    previous_mcp_launcher_pid = $PreviousLauncherPid
    previous_mcp_listener_pid = $PreviousListenerPid
    mcp_launcher_pid = $McpProcess.Id
    tunnel_pid_preserved = [int](Get-PropertyValue -Payload $State -Name 'tunnel_pid' -Default 0)
    connector_url_preserved = $ExistingConnectorUrl
    connector_host = $ConnectorHost
    mcp_log_capture = 'not_captured_detached_start'
    public_tunnel_restarted = $false
  }
  ConvertTo-JsonOutput -Payload $Payload
  exit 0
}

if ($Mode -eq 'StartCloudflaredLogin') {
  if (-not $AuthorizeCloudflaredLogin) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'operator_cloudflared_login_authorization_required'
        connector_url = ''
        runtime_root = $RuntimeRoot
        state_path = $statePath
        blockers = @('authorize_cloudflared_login_flag_required')
        next_operator_step = 'rerun_with_authorize_cloudflared_login'
        cloudflared_login = [ordered]@{
          public_tunnel_started = $false
          connector_url_recorded = $false
          provider_login_started = $false
          provider_login_browser_may_open = $false
        }
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  $CloudflaredPath = Resolve-CloudflaredPath
  if ([string]::IsNullOrWhiteSpace($CloudflaredPath) -or -not (Test-Path -LiteralPath $CloudflaredPath -PathType Leaf)) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'cloudflared_unavailable'
        error = 'cloudflared_executable_not_found'
        runtime_root = $RuntimeRoot
        state_path = $statePath
        blockers = @('cloudflared_unavailable')
        next_operator_step = 'install_cloudflared'
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  $OriginCertBefore = Get-CloudflaredOriginCertReadiness
  if ([bool](Get-PropertyValue -Payload $OriginCertBefore -Name 'present' -Default $false)) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $true
        status = 'cloudflared_login_already_ready'
        runtime_root = $RuntimeRoot
        state_path = $statePath
        cloudflared_path = $CloudflaredPath
        cloudflared_origin_cert = $OriginCertBefore
        blockers = @()
        next_operator_step = 'create_or_start_cloudflared_named_tunnel'
        cloudflared_login = [ordered]@{
          public_tunnel_started = $false
          connector_url_recorded = $false
          provider_login_started = $false
          provider_login_browser_may_open = $false
        }
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  try {
    $LoginProcess = Start-Process -FilePath $CloudflaredPath -ArgumentList @('tunnel', 'login') -WindowStyle Normal -PassThru
    Start-Sleep -Milliseconds 750
    $LoginReadback = Get-ProcessReadback -ProcessId $LoginProcess.Id -ExpectedCommandText 'cloudflared'
    $OriginCertAfter = Get-CloudflaredOriginCertReadiness
    $LoginProcessAlive = [bool](Get-PropertyValue -Payload $LoginReadback -Name 'alive' -Default $false)
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $true
        status = if ($LoginProcessAlive) { 'cloudflared_login_started' } else { 'cloudflared_login_started_process_not_alive' }
        runtime_root = $RuntimeRoot
        state_path = $statePath
        cloudflared_path = $CloudflaredPath
        cloudflared_origin_cert_before = $OriginCertBefore
        cloudflared_origin_cert_after = $OriginCertAfter
        blockers = @()
        next_operator_step = 'complete_cloudflared_browser_login_then_rerun_plan_persistent_ingress'
        cloudflared_login = [ordered]@{
          process_id = $LoginProcess.Id
          process_alive = $LoginProcessAlive
          process = $LoginReadback
          public_tunnel_started = $false
          connector_url_recorded = $false
          provider_login_started = $true
          provider_login_browser_may_open = $true
          provider_login_writes_origin_cert = $true
          origin_cert_content_read = $false
        }
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $false -WritesData $true
      })
    exit 0
  } catch {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'cloudflared_login_start_failed'
        error = ConvertTo-BoundedText -Value $_.Exception.Message -MaxLength 512
        runtime_root = $RuntimeRoot
        state_path = $statePath
        cloudflared_path = $CloudflaredPath
        cloudflared_origin_cert_before = $OriginCertBefore
        blockers = @('cloudflared_login_start_failed')
        next_operator_step = 'inspect_cloudflared_installation_or_run_cloudflared_tunnel_login_manually'
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }
}

if ($Mode -eq 'StartCloudflaredNamed') {
  if (-not $ExposePublicTunnel) {
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

  $BoundedTunnelName = ConvertTo-BoundedText -Value $CloudflaredTunnelName -MaxLength 160
  if ([string]::IsNullOrWhiteSpace($BoundedTunnelName)) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'cloudflared_named_tunnel_name_required'
        connector_url = ''
        runtime_root = $RuntimeRoot
        state_path = $statePath
        blockers = @('cloudflared_tunnel_name_required')
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  $Candidate = Resolve-ConnectorUrlCandidate -ExplicitConnectorUrl $ConnectorUrl -State $null -AllowState $false
  $NamedConnectorUrl = ConvertTo-BoundedText -Value ([string]$Candidate.url) -MaxLength 512
  $BoundedHostname = ConvertTo-CloudflaredHost -Value $CloudflaredHostname
  $ConnectorUrlSource = ConvertTo-BoundedText -Value ([string]$Candidate.source) -MaxLength 160
  if ([string]::IsNullOrWhiteSpace($NamedConnectorUrl) -and -not [string]::IsNullOrWhiteSpace($BoundedHostname)) {
    $NamedConnectorUrl = "https://$BoundedHostname$Path"
    $ConnectorUrlSource = 'cloudflared_named'
  }
  if ([string]::IsNullOrWhiteSpace($BoundedHostname) -and -not [string]::IsNullOrWhiteSpace($NamedConnectorUrl)) {
    $BoundedHostname = ConvertTo-CloudflaredHost -Value $NamedConnectorUrl
  }
  if ([string]::IsNullOrWhiteSpace($NamedConnectorUrl) -or [string]::IsNullOrWhiteSpace($BoundedHostname)) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'cloudflared_named_hostname_required'
        connector_url = $NamedConnectorUrl
        connector_url_source = $ConnectorUrlSource
        runtime_root = $RuntimeRoot
        state_path = $statePath
        blockers = @('cloudflared_hostname_or_connector_url_required')
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  try {
    $ConnectorHost = ([System.Uri]$NamedConnectorUrl).Host
  } catch {
    $ConnectorHost = ''
  }
  if ([string]::IsNullOrWhiteSpace($ConnectorHost)) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'connector_url_shape_invalid'
        connector_url = $NamedConnectorUrl
        connector_url_source = $ConnectorUrlSource
        runtime_root = $RuntimeRoot
        state_path = $statePath
        blockers = @('connector_url_missing_host')
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }
  if (-not $ConnectorHost.Equals($BoundedHostname, [System.StringComparison]::OrdinalIgnoreCase)) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'cloudflared_named_hostname_mismatch'
        connector_url = $NamedConnectorUrl
        connector_url_source = $ConnectorUrlSource
        cloudflared_hostname = $BoundedHostname
        connector_host = $ConnectorHost
        runtime_root = $RuntimeRoot
        state_path = $statePath
        blockers = @('cloudflared_hostname_mismatch')
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  $EndpointStatus = Invoke-EndpointStatus -ConnectorUrl $NamedConnectorUrl
  $ShapeValid = [bool](Get-NestedPropertyValue -Payload $EndpointStatus -Path @('chatgpt_connector', 'connector_url', 'shape_valid') -Default $false)
  $ShapeReason = ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $EndpointStatus -Path @('chatgpt_connector', 'connector_url', 'reason') -Default 'connector_url_shape_invalid') -MaxLength 160
  if (-not $ShapeValid) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'connector_url_shape_invalid'
        connector_url = $NamedConnectorUrl
        connector_url_source = $ConnectorUrlSource
        runtime_root = $RuntimeRoot
        state_path = $statePath
        endpoint_status = $EndpointStatus
        blockers = @($ShapeReason)
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  $IngressProfile = New-ConnectorIngressProfile -EndpointStatus $EndpointStatus -ConnectorUrlSource $ConnectorUrlSource
  if (-not [bool](Get-PropertyValue -Payload $IngressProfile -Name 'persistent_candidate' -Default $false)) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'connector_url_not_persistent'
        connector_url = $NamedConnectorUrl
        connector_url_source = $ConnectorUrlSource
        runtime_root = $RuntimeRoot
        state_path = $statePath
        endpoint_status = $EndpointStatus
        connector_ingress_profile = $IngressProfile
        blockers = @($IngressProfile.blockers)
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  $CloudflaredPath = Resolve-CloudflaredPath
  if ([string]::IsNullOrWhiteSpace($CloudflaredPath) -or -not (Test-Path -LiteralPath $CloudflaredPath -PathType Leaf)) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'cloudflared_unavailable'
        error = 'cloudflared_executable_not_found'
        connector_url = $NamedConnectorUrl
        runtime_root = $RuntimeRoot
        state_path = $statePath
        blockers = @('cloudflared_unavailable')
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  $OriginCert = Get-CloudflaredOriginCertReadiness
  if (-not [bool](Get-PropertyValue -Payload $OriginCert -Name 'present' -Default $false)) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'cloudflared_login_required'
        connector_url = $NamedConnectorUrl
        connector_url_source = $ConnectorUrlSource
        runtime_root = $RuntimeRoot
        state_path = $statePath
        cloudflared_path = $CloudflaredPath
        cloudflared_origin_cert = $OriginCert
        blockers = @('cloudflared_login_required')
        next_operator_step = 'run_start_cloudflared_login'
        governed_handoff_command = '.\scripts\chatgpt-voice-connector.ps1 -Mode StartCloudflaredLogin -AuthorizeCloudflaredLogin -Json'
        cloudflared_named_start = [ordered]@{
          public_tunnel_started = $false
          connector_url_recorded = $false
          existing_bridge_stopped = $false
          origin_cert_content_read = $false
        }
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  $NamedTunnelPreflight = Test-CloudflaredNamedTunnelExists -CloudflaredPath $CloudflaredPath -TunnelName $BoundedTunnelName
  if (-not [bool](Get-PropertyValue -Payload $NamedTunnelPreflight -Name 'exists' -Default $false)) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'cloudflared_named_tunnel_missing'
        connector_url = $NamedConnectorUrl
        connector_url_source = $ConnectorUrlSource
        runtime_root = $RuntimeRoot
        state_path = $statePath
        cloudflared_path = $CloudflaredPath
        cloudflared_tunnel_name = $BoundedTunnelName
        cloudflared_hostname = $BoundedHostname
        cloudflared_named_tunnel_preflight = $NamedTunnelPreflight
        blockers = @('cloudflared_named_tunnel_missing')
        next_operator_step = 'create_cloudflared_named_tunnel_and_route_hostname'
        operator_provider_setup_commands = @(
          "cloudflared tunnel create $BoundedTunnelName",
          "cloudflared tunnel route dns $BoundedTunnelName $BoundedHostname"
        )
        cloudflared_named_start = [ordered]@{
          public_tunnel_started = $false
          connector_url_recorded = $false
          existing_bridge_stopped = $false
          provider_tunnel_created = $false
          provider_route_created = $false
          preflight_output_discarded = [bool](Get-PropertyValue -Payload $NamedTunnelPreflight -Name 'output_discarded' -Default $true)
        }
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  $BoundedConfigPath = ConvertTo-BoundedText -Value $CloudflaredConfigPath -MaxLength 512
  if (-not [string]::IsNullOrWhiteSpace($BoundedConfigPath) -and -not (Test-Path -LiteralPath $BoundedConfigPath -PathType Leaf)) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'cloudflared_config_missing'
        connector_url = $NamedConnectorUrl
        runtime_root = $RuntimeRoot
        state_path = $statePath
        cloudflared_config_path = $BoundedConfigPath
        blockers = @('cloudflared_config_missing')
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  $State = Read-State
  $PreviousConnectorUrl = if ($State) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'connector_url' -Default '') -MaxLength 512 } else { '' }
  $PreviousListenerPid = 0
  if (-not [string]::IsNullOrWhiteSpace($PreviousConnectorUrl)) {
    $EndpointBefore = Invoke-EndpointStatus -ConnectorUrl $PreviousConnectorUrl
    $PreviousListenerPid = [int](Get-NestedPropertyValue -Payload $EndpointBefore -Path @('local_listener', 'owning_process') -Default 0)
  } else {
    $PreviousListenerPid = [int](Get-NestedPropertyValue -Payload $EndpointStatus -Path @('local_listener', 'owning_process') -Default 0)
  }
  $PreviousLauncherPid = if ($State) { [int](Get-PropertyValue -Payload $State -Name 'mcp_launcher_pid' -Default 0) } else { 0 }
  $PreviousTunnelPid = if ($State) { [int](Get-PropertyValue -Payload $State -Name 'tunnel_pid' -Default 0) } else { 0 }
  $PreviousConnectorUrlSource = if ($State) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'connector_url_source' -Default '') -MaxLength 160 } else { '' }
  $PreviousIngressMode = if ($State) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'ingress_mode' -Default '') -MaxLength 96 } else { '' }
  $PreviousTunnelExpectedCommandText = Get-TunnelExpectedCommandText -ConnectorUrlSource $PreviousConnectorUrlSource -IngressMode $PreviousIngressMode
  $Stopped = @()

  if ($PreviousListenerPid -gt 0) {
    $ListenerReadback = Get-ProcessReadback -ProcessId $PreviousListenerPid -ExpectedCommandText 'francis.mcp_gateway.server'
    if ([bool]$ListenerReadback.alive -and -not [bool]$ListenerReadback.command_matches_expected) {
      ConvertTo-JsonOutput -Payload ([ordered]@{
          kind = 'francis.chatgpt_voice.connector_control'
          ok = $false
          status = 'mcp_existing_listener_not_recognized'
          connector_url = $NamedConnectorUrl
          runtime_root = $RuntimeRoot
          state_path = $statePath
          listener = $ListenerReadback
          blockers = @('existing_listener_not_francis_mcp_gateway')
          governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
        })
      exit 0
    }
    if (Stop-KnownProcess -ProcessId $PreviousListenerPid -ExpectedCommandText 'francis.mcp_gateway.server') {
      $Stopped += 'mcp_server_listener'
      [void](Wait-ForKnownProcessExit -ProcessId $PreviousListenerPid -ExpectedCommandText 'francis.mcp_gateway.server')
    }
  }
  if ($PreviousLauncherPid -gt 0 -and (Stop-KnownProcess -ProcessId $PreviousLauncherPid -ExpectedCommandText 'chatgpt-voice-mcp.ps1')) {
    $Stopped += 'mcp_launcher'
    [void](Wait-ForKnownProcessExit -ProcessId $PreviousLauncherPid -ExpectedCommandText 'chatgpt-voice-mcp.ps1')
  }
  if ($PreviousTunnelPid -gt 0 -and (Stop-KnownProcess -ProcessId $PreviousTunnelPid -ExpectedCommandText $PreviousTunnelExpectedCommandText)) {
    $Stopped += Get-TunnelStopLabel -ConnectorUrlSource $PreviousConnectorUrlSource -IngressMode $PreviousIngressMode -Fallback 'localtunnel_fallback'
    [void](Wait-ForKnownProcessExit -ProcessId $PreviousTunnelPid -ExpectedCommandText $PreviousTunnelExpectedCommandText)
  }

  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  $McpProcess = Start-McpLauncher -ConnectorHost $ConnectorHost
  if (-not $McpProcess) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'powershell_host_missing'
        connector_url = $NamedConnectorUrl
        runtime_root = $RuntimeRoot
        state_path = $statePath
        stopped = $Stopped
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  $TunnelStdout = Join-Path $RuntimeRoot 'cloudflared-named-stdout.log'
  $TunnelStderr = Join-Path $RuntimeRoot 'cloudflared-named-stderr.log'
  Remove-Item -LiteralPath $TunnelStdout, $TunnelStderr -Force -ErrorAction SilentlyContinue
  $TunnelArgs = @('tunnel')
  if (-not [string]::IsNullOrWhiteSpace($BoundedConfigPath)) {
    $TunnelArgs += @('--config', $BoundedConfigPath)
  }
  $TunnelArgs += @('run', $BoundedTunnelName)
  try {
    $TunnelProcess = Start-Process -FilePath $CloudflaredPath -ArgumentList $TunnelArgs -RedirectStandardOutput $TunnelStdout -RedirectStandardError $TunnelStderr -PassThru -WindowStyle Hidden
  } catch {
    if (Stop-KnownProcess -ProcessId $McpProcess.Id -ExpectedCommandText 'chatgpt-voice-mcp.ps1') {
      [void](Wait-ForKnownProcessExit -ProcessId $McpProcess.Id -ExpectedCommandText 'chatgpt-voice-mcp.ps1')
    }
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'cloudflared_named_start_failed'
        connector_url = $NamedConnectorUrl
        runtime_root = $RuntimeRoot
        state_path = $statePath
        error = ConvertTo-BoundedText -Value $_.Exception.Message -MaxLength 512
        stopped = $Stopped
        blockers = @('cloudflared_named_start_failed')
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }
  Start-Sleep -Seconds 4

  $StartedAt = (Get-Date).ToUniversalTime().ToString('o')
  $CloudflaredNamed = New-CloudflaredNamedTunnelPayload -ConnectorUrl $NamedConnectorUrl -ConnectorUrlSource 'cloudflared_named' -TunnelName $BoundedTunnelName -Hostname $BoundedHostname -ConfigPath $BoundedConfigPath
  $StatePayload = [ordered]@{
    kind = 'francis.chatgpt_voice.connector_control.state'
    status = 'cloudflared_named_started'
    ingress_mode = 'cloudflared_named_tunnel'
    connector_url = $NamedConnectorUrl
    connector_url_source = 'cloudflared_named'
    connector_host = $ConnectorHost
    cloudflared_named_tunnel = $CloudflaredNamed
    cloudflared_named_tunnel_name = $BoundedTunnelName
    cloudflared_named_hostname = $BoundedHostname
    cloudflared_config_path = $BoundedConfigPath
    local_endpoint = "http://$HostAddress`:$Port$Path"
    mcp_launcher_pid = $McpProcess.Id
    previous_mcp_launcher_pid = $PreviousLauncherPid
    previous_mcp_listener_pid = $PreviousListenerPid
    previous_tunnel_pid = $PreviousTunnelPid
    tunnel_pid = $TunnelProcess.Id
    mcp_stdout = ''
    mcp_stderr = ''
    mcp_log_capture = 'not_captured_detached_start'
    tunnel_stdout = $TunnelStdout
    tunnel_stderr = $TunnelStderr
    tunnel_log_capture = 'captured_to_runtime_logs'
    stopped = $Stopped
    started_at = $StartedAt
    updated_at = $StartedAt
    governance = New-GovernancePayload -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $true -WritesData $true
  }
  Write-State -Payload $StatePayload

  $EndpointAfter = Invoke-EndpointStatus -ConnectorUrl $NamedConnectorUrl
  $Payload = New-StatusPayload -State (Read-State) -EndpointStatus $EndpointAfter -ConnectorUrlSource 'cloudflared_named' -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $true -WritesData $true
  $ConnectorReady = [string]$EndpointAfter.status -eq 'ready_for_chatgpt_connector'
  $LocalReady = [bool](Get-NestedPropertyValue -Payload $EndpointAfter -Path @('local_listener', 'ready') -Default $false)
  $TunnelReadback = Get-ProcessReadback -ProcessId $TunnelProcess.Id -ExpectedCommandText 'cloudflared'
  $TunnelAlive = [bool]$TunnelReadback.alive
  $NamedStartBlockers = @()
  $NamedStartNextStep = 'call_francis_chatgpt_voice_mcp_probe_from_chatgpt_connector'
  if (-not $TunnelAlive) {
    $NamedStartBlockers += 'cloudflared_named_tunnel_process_not_alive'
    $NamedStartNextStep = 'inspect_cloudflared_named_tunnel_logs'
  } elseif (-not $LocalReady) {
    $NamedStartBlockers += 'mcp_local_listener_not_ready'
    $NamedStartNextStep = 'inspect_chatgpt_voice_mcp_launcher'
  } elseif (-not $ConnectorReady) {
    $NamedStartBlockers += 'cloudflared_named_connector_unverified'
    $NamedStartNextStep = 'verify_cloudflared_hostname_route_and_chatgpt_connector_url'
  }
  $Payload.status = if ($ConnectorReady -and $TunnelAlive) {
    'cloudflared_named_started_ready'
  } elseif ($LocalReady -and $TunnelAlive -and -not $VerifyConnector) {
    'cloudflared_named_started_local_ready'
  } elseif ($TunnelAlive) {
    'cloudflared_named_started_unverified'
  } else {
    'cloudflared_named_started_failed'
  }
  $Payload.ok = [bool](($ConnectorReady -and $TunnelAlive) -or ($LocalReady -and $TunnelAlive -and -not $VerifyConnector))
  $Payload.blockers = $NamedStartBlockers
  $Payload.next_operator_step = $NamedStartNextStep
  $Payload.cloudflared_named_start = [ordered]@{
    stopped = $Stopped
    cloudflared_path = $CloudflaredPath
    cloudflared_config_path = $BoundedConfigPath
    cloudflared_tunnel_name = $BoundedTunnelName
    cloudflared_hostname = $BoundedHostname
    mcp_launcher_pid = $McpProcess.Id
    tunnel_pid = $TunnelProcess.Id
    tunnel_alive = $TunnelAlive
    connector_url = $NamedConnectorUrl
    connector_host = $ConnectorHost
    ingress_mode = 'cloudflared_named_tunnel'
    public_tunnel_started = $TunnelAlive
    connector_url_recorded = $true
    local_listener_ready = $LocalReady
    public_connector_verified = $ConnectorReady
    verify_connector_requested = [bool]$VerifyConnector
    next_operator_step = $NamedStartNextStep
    persistent_candidate = $true
  }
  ConvertTo-JsonOutput -Payload $Payload
  exit 0
}

if ($Mode -eq 'StartCloudflaredQuick') {
  if (-not $ExposePublicTunnel) {
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

  $CloudflaredPath = Resolve-CloudflaredPath
  if ([string]::IsNullOrWhiteSpace($CloudflaredPath) -or -not (Test-Path -LiteralPath $CloudflaredPath -PathType Leaf)) {
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'cloudflared_unavailable'
        error = 'cloudflared_executable_not_found'
        runtime_root = $RuntimeRoot
        state_path = $statePath
        blockers = @('cloudflared_unavailable')
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
      })
    exit 0
  }

  $State = Read-State
  $PreviousConnectorUrl = if ($State) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'connector_url' -Default '') -MaxLength 512 } else { '' }
  $PreviousListenerPid = 0
  if (-not [string]::IsNullOrWhiteSpace($PreviousConnectorUrl)) {
    $EndpointBefore = Invoke-EndpointStatus -ConnectorUrl $PreviousConnectorUrl
    $PreviousListenerPid = [int](Get-NestedPropertyValue -Payload $EndpointBefore -Path @('local_listener', 'owning_process') -Default 0)
  }
  $PreviousLauncherPid = if ($State) { [int](Get-PropertyValue -Payload $State -Name 'mcp_launcher_pid' -Default 0) } else { 0 }
  $PreviousTunnelPid = if ($State) { [int](Get-PropertyValue -Payload $State -Name 'tunnel_pid' -Default 0) } else { 0 }
  $PreviousConnectorUrlSource = if ($State) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'connector_url_source' -Default '') -MaxLength 160 } else { '' }
  $PreviousIngressMode = if ($State) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'ingress_mode' -Default '') -MaxLength 96 } else { '' }
  $PreviousTunnelExpectedCommandText = Get-TunnelExpectedCommandText -ConnectorUrlSource $PreviousConnectorUrlSource -IngressMode $PreviousIngressMode
  $Stopped = @()

  if ($PreviousListenerPid -gt 0 -and (Stop-KnownProcess -ProcessId $PreviousListenerPid -ExpectedCommandText 'francis.mcp_gateway.server')) {
    $Stopped += 'mcp_server_listener'
    [void](Wait-ForKnownProcessExit -ProcessId $PreviousListenerPid -ExpectedCommandText 'francis.mcp_gateway.server')
  }
  if ($PreviousLauncherPid -gt 0 -and (Stop-KnownProcess -ProcessId $PreviousLauncherPid -ExpectedCommandText 'chatgpt-voice-mcp.ps1')) {
    $Stopped += 'mcp_launcher'
    [void](Wait-ForKnownProcessExit -ProcessId $PreviousLauncherPid -ExpectedCommandText 'chatgpt-voice-mcp.ps1')
  }
  if ($PreviousTunnelPid -gt 0 -and (Stop-KnownProcess -ProcessId $PreviousTunnelPid -ExpectedCommandText $PreviousTunnelExpectedCommandText)) {
    $Stopped += Get-TunnelStopLabel -ConnectorUrlSource $PreviousConnectorUrlSource -IngressMode $PreviousIngressMode -Fallback 'localtunnel_fallback'
    [void](Wait-ForKnownProcessExit -ProcessId $PreviousTunnelPid -ExpectedCommandText $PreviousTunnelExpectedCommandText)
  }

  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  $TunnelStdout = Join-Path $RuntimeRoot 'cloudflared-quick-stdout.log'
  $TunnelStderr = Join-Path $RuntimeRoot 'cloudflared-quick-stderr.log'
  Remove-Item -LiteralPath $TunnelStdout, $TunnelStderr -Force -ErrorAction SilentlyContinue
  $TunnelArgs = @('tunnel', '--url', "http://$HostAddress`:$Port", '--no-autoupdate')
  $TunnelProcess = Start-Process -FilePath $CloudflaredPath -ArgumentList $TunnelArgs -RedirectStandardOutput $TunnelStdout -RedirectStandardError $TunnelStderr -PassThru -WindowStyle Hidden
  $TunnelBaseUrl = Wait-ForCloudflaredQuickTunnelUrl -StdoutPath $TunnelStdout -StderrPath $TunnelStderr -TimeoutSeconds $ConnectorProbeTimeoutSeconds
  if ([string]::IsNullOrWhiteSpace($TunnelBaseUrl)) {
    if (Stop-KnownProcess -ProcessId $TunnelProcess.Id -ExpectedCommandText 'cloudflared') {
      [void](Wait-ForKnownProcessExit -ProcessId $TunnelProcess.Id -ExpectedCommandText 'cloudflared')
    }
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'cloudflared_quick_tunnel_url_missing'
        runtime_root = $RuntimeRoot
        state_path = $statePath
        stopped = $Stopped
        cloudflared_path = $CloudflaredPath
        tunnel_pid = $TunnelProcess.Id
        tunnel_stdout = $TunnelStdout
        tunnel_stderr = $TunnelStderr
        blockers = @('cloudflared_quick_tunnel_url_missing')
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $true -WritesData $false
      })
    exit 0
  }

  $ConnectorUrl = "$TunnelBaseUrl$Path"
  $ConnectorHost = ([System.Uri]$ConnectorUrl).Host
  $McpProcess = Start-McpLauncher -ConnectorHost $ConnectorHost
  if (-not $McpProcess) {
    if (Stop-KnownProcess -ProcessId $TunnelProcess.Id -ExpectedCommandText 'cloudflared') {
      [void](Wait-ForKnownProcessExit -ProcessId $TunnelProcess.Id -ExpectedCommandText 'cloudflared')
    }
    ConvertTo-JsonOutput -Payload ([ordered]@{
        kind = 'francis.chatgpt_voice.connector_control'
        ok = $false
        status = 'powershell_host_missing'
        connector_url = $ConnectorUrl
        runtime_root = $RuntimeRoot
        state_path = $statePath
        stopped = $Stopped
        tunnel_pid = $TunnelProcess.Id
        governance = New-GovernancePayload -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $true -WritesData $false
      })
    exit 0
  }
  Start-Sleep -Seconds 4

  $StartedAt = (Get-Date).ToUniversalTime().ToString('o')
  $CloudflaredQuick = New-CloudflaredQuickTunnelPayload -ConnectorUrl $ConnectorUrl -ConnectorUrlSource 'cloudflared_quick'
  $StatePayload = [ordered]@{
    kind = 'francis.chatgpt_voice.connector_control.state'
    status = 'cloudflared_quick_started'
    ingress_mode = 'cloudflared_quick_ephemeral'
    connector_url = $ConnectorUrl
    connector_url_source = 'cloudflared_quick'
    connector_host = $ConnectorHost
    cloudflared_quick_tunnel = $CloudflaredQuick
    local_endpoint = "http://$HostAddress`:$Port$Path"
    mcp_launcher_pid = $McpProcess.Id
    previous_mcp_launcher_pid = $PreviousLauncherPid
    previous_mcp_listener_pid = $PreviousListenerPid
    previous_tunnel_pid = $PreviousTunnelPid
    tunnel_pid = $TunnelProcess.Id
    mcp_stdout = ''
    mcp_stderr = ''
    mcp_log_capture = 'not_captured_detached_start'
    tunnel_stdout = $TunnelStdout
    tunnel_stderr = $TunnelStderr
    tunnel_log_capture = 'captured_to_runtime_logs'
    stopped = $Stopped
    started_at = $StartedAt
    updated_at = $StartedAt
    governance = New-GovernancePayload -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $true -WritesData $true
  }
  Write-State -Payload $StatePayload

  $EndpointStatus = Invoke-EndpointStatus -ConnectorUrl $ConnectorUrl
  $Payload = New-StatusPayload -State (Read-State) -EndpointStatus $EndpointStatus -ConnectorUrlSource 'cloudflared_quick' -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $true -WritesData $true
  $ConnectorReady = [string]$EndpointStatus.status -eq 'ready_for_chatgpt_connector'
  $LocalReady = [bool](Get-NestedPropertyValue -Payload $EndpointStatus -Path @('local_listener', 'ready') -Default $false)
  $Payload.status = if ($ConnectorReady) {
    'cloudflared_quick_started_ready'
  } elseif ($LocalReady -and -not $VerifyConnector) {
    'cloudflared_quick_started_local_ready'
  } elseif ($LocalReady) {
    'cloudflared_quick_started_unverified'
  } else {
    'cloudflared_quick_started_failed'
  }
  $Payload.ok = [bool]($ConnectorReady -or ($LocalReady -and -not $VerifyConnector))
  $Payload.cloudflared_quick_start = [ordered]@{
    stopped = $Stopped
    cloudflared_path = $CloudflaredPath
    mcp_launcher_pid = $McpProcess.Id
    tunnel_pid = $TunnelProcess.Id
    connector_url = $ConnectorUrl
    connector_host = $ConnectorHost
    ingress_mode = 'cloudflared_quick_ephemeral'
    public_tunnel_started = $true
    persistent_candidate = $false
  }
  ConvertTo-JsonOutput -Payload $Payload
  exit 0
}

if ($Mode -eq 'Stop') {
  $State = Read-State
  $Stopped = @()
  if ($State) {
    $ExistingConnectorUrl = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'connector_url' -Default '') -MaxLength 512
    if (-not [string]::IsNullOrWhiteSpace($ExistingConnectorUrl)) {
      $EndpointBefore = Invoke-EndpointStatus -ConnectorUrl $ExistingConnectorUrl
      $PreviousListenerPid = [int](Get-NestedPropertyValue -Payload $EndpointBefore -Path @('local_listener', 'owning_process') -Default 0)
      if ($PreviousListenerPid -gt 0 -and (Stop-KnownProcess -ProcessId $PreviousListenerPid -ExpectedCommandText 'francis.mcp_gateway.server')) {
        $Stopped += 'mcp_server_listener'
        [void](Wait-ForKnownProcessExit -ProcessId $PreviousListenerPid -ExpectedCommandText 'francis.mcp_gateway.server')
      }
    }
    $StateConnectorUrlSource = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'connector_url_source' -Default '') -MaxLength 160
    $StateIngressMode = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'ingress_mode' -Default '') -MaxLength 96
    $TunnelExpectedCommandText = Get-TunnelExpectedCommandText -ConnectorUrlSource $StateConnectorUrlSource -IngressMode $StateIngressMode
    if (Stop-KnownProcess -ProcessId ([int]$State.tunnel_pid) -ExpectedCommandText $TunnelExpectedCommandText) {
      $Stopped += Get-TunnelStopLabel -ConnectorUrlSource $StateConnectorUrlSource -IngressMode $StateIngressMode
    }
    if (Stop-KnownProcess -ProcessId ([int]$State.mcp_launcher_pid) -ExpectedCommandText 'chatgpt-voice-mcp.ps1') {
      $Stopped += 'mcp_launcher'
    }
  }
  $StopState = [ordered]@{
    kind = 'francis.chatgpt_voice.connector_control.state'
    status = 'stopped'
    connector_url = if ($State) { ConvertTo-BoundedText -Value $State.connector_url -MaxLength 512 } else { '' }
    connector_url_source = if ($State) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'connector_url_source' -Default '') -MaxLength 160 } else { '' }
    ingress_mode = if ($State) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'ingress_mode' -Default '') -MaxLength 96 } else { '' }
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

if ($Mode -eq 'Start') {
  $State = Read-State
  if ($State) {
    $ExistingConnectorUrl = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $State -Name 'connector_url' -Default '') -MaxLength 512
    if (-not [string]::IsNullOrWhiteSpace($ExistingConnectorUrl)) {
      $EndpointBefore = Invoke-EndpointStatus -ConnectorUrl $ExistingConnectorUrl
      $PreviousListenerPid = [int](Get-NestedPropertyValue -Payload $EndpointBefore -Path @('local_listener', 'owning_process') -Default 0)
      if ($PreviousListenerPid -gt 0) {
        $ListenerReadback = Get-ProcessReadback -ProcessId $PreviousListenerPid -ExpectedCommandText 'francis.mcp_gateway.server'
        if ([bool]$ListenerReadback.alive -and -not [bool]$ListenerReadback.command_matches_expected) {
          ConvertTo-JsonOutput -Payload ([ordered]@{
              kind = 'francis.chatgpt_voice.connector_control'
              ok = $false
              status = 'mcp_existing_listener_not_recognized'
              connector_url = $ExistingConnectorUrl
              runtime_root = $RuntimeRoot
              state_path = $statePath
              listener = $ListenerReadback
              blockers = @('existing_listener_not_francis_mcp_gateway')
              governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
            })
          exit 0
        }
        if (Stop-KnownProcess -ProcessId $PreviousListenerPid -ExpectedCommandText 'francis.mcp_gateway.server') {
          [void](Wait-ForKnownProcessExit -ProcessId $PreviousListenerPid -ExpectedCommandText 'francis.mcp_gateway.server')
        }
      }
    }

    $PreviousLauncherPid = [int](Get-PropertyValue -Payload $State -Name 'mcp_launcher_pid' -Default 0)
    if ($PreviousLauncherPid -gt 0 -and (Stop-KnownProcess -ProcessId $PreviousLauncherPid -ExpectedCommandText 'chatgpt-voice-mcp.ps1')) {
      [void](Wait-ForKnownProcessExit -ProcessId $PreviousLauncherPid -ExpectedCommandText 'chatgpt-voice-mcp.ps1')
    }
  }
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
$TunnelStdout = ''
$TunnelStderr = ''
$TunnelLogCapture = 'not_captured_detached_start'
$RequestedTunnelHost = ConvertTo-BoundedText -Value $TunnelSubdomain -MaxLength 160
if ([string]::IsNullOrWhiteSpace($RequestedTunnelHost)) {
  ConvertTo-JsonOutput -Payload ([ordered]@{
      kind = 'francis.chatgpt_voice.connector_control'
      ok = $false
      status = 'localtunnel_subdomain_required'
      error = 'localtunnel_subdomain_required_for_detached_start'
      governance = New-GovernancePayload -ReadOnly $false -StartsProcess $false -OpensPublicTunnel $false -WritesData $false
    })
  exit 0
}
if (-not $RequestedTunnelHost.Contains('.')) {
  $RequestedTunnelHost = "$RequestedTunnelHost.loca.lt"
}

$TunnelArgs = @($LocalTunnelScript, '--port', [string]$Port, '--local-host', $HostAddress)
if (-not [string]::IsNullOrWhiteSpace($TunnelSubdomain)) {
  $TunnelArgs += @('--subdomain', $TunnelSubdomain)
}
$TunnelProcess = Start-Process -FilePath 'node' -ArgumentList $TunnelArgs -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 4
$ConnectorUrl = "https://$RequestedTunnelHost$Path"

$ConnectorHost = ([System.Uri]$ConnectorUrl).Host
$LocalTunnelStability = New-LocalTunnelStabilityPayload -ConnectorUrl $ConnectorUrl -ConnectorUrlSource 'localtunnel' -RequestedSubdomain $TunnelSubdomain
$McpProcess = Start-McpLauncher -ConnectorHost $ConnectorHost
if (-not $McpProcess) {
  ConvertTo-JsonOutput -Payload ([ordered]@{
      kind = 'francis.chatgpt_voice.connector_control'
      ok = $false
      status = 'powershell_host_missing'
      connector_url = $ConnectorUrl
      tunnel_pid = $TunnelProcess.Id
      tunnel_stdout = $TunnelStdout
      tunnel_stderr = $TunnelStderr
      governance = New-GovernancePayload -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $true -WritesData $true
    })
  exit 0
}
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
  mcp_stdout = ''
  mcp_stderr = ''
  mcp_log_capture = 'not_captured_detached_start'
  tunnel_stdout = $TunnelStdout
  tunnel_stderr = $TunnelStderr
  tunnel_log_capture = $TunnelLogCapture
  updated_at = (Get-Date).ToUniversalTime().ToString('o')
  governance = New-GovernancePayload -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $true -WritesData $true
}
Write-State -Payload $StatePayload

$EndpointStatus = Invoke-EndpointStatus -ConnectorUrl $ConnectorUrl
$Payload = New-StatusPayload -State (Read-State) -EndpointStatus $EndpointStatus -ConnectorUrlSource 'localtunnel' -ReadOnly $false -StartsProcess $true -OpensPublicTunnel $true -WritesData $true
$Payload.status = if (-not [bool]$LocalTunnelStability.stable_for_existing_chatgpt_connector) { 'started_unstable_localtunnel_url' } elseif ([string]$EndpointStatus.status -eq 'ready_for_chatgpt_connector') { 'started_ready' } else { 'started_unverified' }
$Payload.ok = [bool]($Payload.status -eq 'started_ready')
ConvertTo-JsonOutput -Payload $Payload
