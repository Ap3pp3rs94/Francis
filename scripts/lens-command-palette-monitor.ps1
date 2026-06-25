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

  [switch]$RequireChatGptMcpProof,

  [switch]$RequireManualAcousticOrbProof,

  [ValidateRange(1, 86400)]
  [int]$ChatGptMcpProofFreshnessSeconds = 300,

  [switch]$EnableChatGptConnectorChecks,

  [string]$ChatGptConnectorUrl = '',

  [ValidateRange(1, 65535)]
  [int]$ChatGptConnectorPort = 8787,

  [string]$CloudflaredTunnelName = '',

  [string]$CloudflaredHostname = '',

  [string]$CloudflaredTokenFile = '',

  [switch]$VerifyChatGptConnector,

  [ValidateRange(1, 60)]
  [int]$ChatGptConnectorProbeTimeoutSeconds = 5,

  [switch]$RequirePersistentChatGptIngress,

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

  if ($null -eq $Value) {
    return ''
  }
  $Text = ([string]$Value).Trim()
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return ''
  }
  if ($Text.Length -le $MaxLength) {
    return $Text
  }
  return $Text.Substring(0, $MaxLength)
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
  return [string[]]($Items.ToArray([string]))
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

function Test-OverlayMonitorProcessAlive {
  param([int]$ProcessId)

  if ($ProcessId -le 0) {
    return $false
  }
  return ($null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue))
}

function New-OverlayMonitorVoiceInputReadiness {
  param([object]$Voice)

  $WakeListening = [bool](Get-PropertyValue -Payload $Voice -Name 'wake_listening' -Default $false)
  $MicrophoneCapture = [bool](Get-PropertyValue -Payload $Voice -Name 'microphone_capture' -Default $false)
  $MicrophoneInputEffective = [bool](Get-PropertyValue -Payload $Voice -Name 'microphone_input_effective' -Default $false)
  $NeedsOperatorAudioInputCheck = [bool](Get-PropertyValue -Payload $Voice -Name 'needs_operator_audio_input_check' -Default $false)
  $Ok = [bool](Get-PropertyValue -Payload $Voice -Name 'ok' -Default $true)
  $VoiceStatus = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Voice -Name 'status' -Default '') -MaxLength 120
  $MicrophoneSignalStatus = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Voice -Name 'microphone_signal_status' -Default 'unknown') -MaxLength 120
  $AudioSignalProblem = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Voice -Name 'audio_signal_problem' -Default '') -MaxLength 160
  $AudioLevel = [int](Get-PropertyValue -Payload $Voice -Name 'audio_level' -Default 0)

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
    ready = [bool]$Ready
    status = $Status
    blocker = $Blocker
    next_operator_step = $NextOperatorStep
    message = $Message
    wake_listening = [bool]$WakeListening
    microphone_capture = [bool]$MicrophoneCapture
    microphone_signal_status = $MicrophoneSignalStatus
    microphone_input_effective = [bool]$MicrophoneInputEffective
    needs_operator_audio_input_check = [bool]$NeedsOperatorAudioInputCheck
    audio_signal_problem = $AudioSignalProblem
    audio_level = $AudioLevel
    transcript_redacted = $true
    grants_execution_authority = $false
    grants_mutation_authority = $false
  }
}

function Invoke-OverlayVoiceReadback {
  param(
    [string]$Root,
    [string]$Provider,
    [string]$RemoteVoiceId,
    [string]$RemoteVoiceName
  )

  $RuntimeRoot = Join-Path $Root 'runtime\lens-overlay'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  $PidPath = Join-Path $RuntimeRoot 'lens-overlay.pid'
  $VoiceStatusPath = Join-Path $RuntimeRoot 'voice-status.json'
  $VoiceTurnStatusPath = Join-Path $RuntimeRoot 'voice-turn-status.json'
  $StatusPayload = Read-JsonFile -Path $StatusPath
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

  $StatusKind = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $StatusPayload -Name 'kind' -Default '') -MaxLength 120
  $StatusValue = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $StatusPayload -Name 'status' -Default 'missing') -MaxLength 120
  $StatusPid = [int](Get-PropertyValue -Payload $StatusPayload -Name 'pid' -Default 0)
  $StatusClaimsRunningOverlay = (
    $StatusKind -eq 'lens.overlay.runtime_state' -and
    $StatusValue -eq 'overlay_running' -and
    $StatusPid -gt 0 -and
    $StatusPid -eq $RuntimePid
  )
  $ProcessAlive = if ($StatusClaimsRunningOverlay) { Test-OverlayMonitorProcessAlive -ProcessId $RuntimePid } else { $false }
  $OverlayVisible = ($ProcessAlive -and [bool](Get-PropertyValue -Payload $StatusPayload -Name 'overlay_window_visible' -Default $false))
  $AlwaysOnTop = ($OverlayVisible -and [bool](Get-PropertyValue -Payload $StatusPayload -Name 'always_on_top' -Default $false))
  $Ready = ($OverlayVisible -and $AlwaysOnTop)
  $VoiceReadbackFile = Read-JsonFile -Path $VoiceStatusPath
  $VoiceTurnReadbackFile = Read-JsonFile -Path $VoiceTurnStatusPath
  $Voice = if ($null -ne $VoiceReadbackFile) { $VoiceReadbackFile } else { Get-PropertyValue -Payload $StatusPayload -Name 'voice' -Default $null }
  $VoiceTurn = if ($null -ne $VoiceTurnReadbackFile) { $VoiceTurnReadbackFile } else { Get-PropertyValue -Payload $StatusPayload -Name 'voice_turn' -Default $null }
  $OverlayVoice = Get-PropertyValue -Payload $StatusPayload -Name 'overlay_voice' -Default $null
  $VoiceInputReadiness = Get-PropertyValue -Payload $StatusPayload -Name 'voice_input_readiness' -Default $null
  if ($null -eq $VoiceInputReadiness) {
    $VoiceInputReadiness = New-OverlayMonitorVoiceInputReadiness -Voice $OverlayVoice
  }
  $VoiceInputReady = [bool](Get-PropertyValue -Payload $StatusPayload -Name 'voice_input_ready' -Default (Get-PropertyValue -Payload $VoiceInputReadiness -Name 'ready' -Default $false))
  $ProviderReadiness = Get-PropertyValue -Payload $StatusPayload -Name 'voice_provider_readiness' -Default $null
  if ($null -eq $ProviderReadiness) {
    $VoiceLabel = if (-not [string]::IsNullOrWhiteSpace($RemoteVoiceName)) {
      $RemoteVoiceName
    } else {
      ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $OverlayVoice -Name 'selected_voice' -Default '') -MaxLength 120
    }
    $ProviderReadiness = [ordered]@{
      kind = 'lens.overlay.voice.provider_readiness'
      selected_provider = $Provider
      active_provider_configured = $false
      elevenlabs = [ordered]@{
        configured = $false
        api_key_present = $false
        voice_id_present = -not [string]::IsNullOrWhiteSpace($RemoteVoiceId)
        voice_label = $VoiceLabel
        credential_values_redacted = $true
        missing_configuration = @('api_key')
      }
      stores_secret = $false
      logs_text_payload = $false
    }
  }

  $Payload = [ordered]@{
    ok = $true
    kind = 'lens.overlay.window.runtime'
    status = if ($Ready) { 'visible' } else { $StatusValue }
    mode = 'status'
    ready = [bool]$Ready
    overlay_window = [bool]$Ready
    data_root = $Root
    runtime_state_path = 'data/runtime/lens-overlay/status.json'
    pid_path = 'data/runtime/lens-overlay/lens-overlay.pid'
    voice = $Voice
    voice_turn = $VoiceTurn
    overlay_voice = $OverlayVoice
    voice_input_readiness = $VoiceInputReadiness
    voice_input_ready = [bool]$VoiceInputReady
    voice_input_status = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $VoiceInputReadiness -Name 'status' -Default '') -MaxLength 120
    voice_input_blocker = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $VoiceInputReadiness -Name 'blocker' -Default '') -MaxLength 160
    next_voice_input_step = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $VoiceInputReadiness -Name 'next_operator_step' -Default '') -MaxLength 200
    voice_provider_readiness = $ProviderReadiness
    overlay_position = Get-PropertyValue -Payload $StatusPayload -Name 'overlay_position' -Default $null
    overlay_runtime = [ordered]@{
      ready = [bool]$Ready
      process_alive = [bool]$ProcessAlive
      overlay_window_visible = [bool]$OverlayVisible
      always_on_top = [bool]$AlwaysOnTop
      pid = [int]$RuntimePid
      pid_present = [bool]$PidPresent
      runtime_state_exists = [bool]$RuntimeStateExists
      runtime_status = $StatusValue
      runtime_status_kind = $StatusKind
      runtime_status_pid = [int]$StatusPid
      runtime_status_pid_matches_pid_file = ($StatusPid -gt 0 -and $StatusPid -eq $RuntimePid)
    }
    governance = [ordered]@{
      read_only_contract = $true
      execution_authority = $false
      approval_decision_authority = $false
      memory_write = $false
      overlay_control_authority = $false
      window_management_authority = $false
      capture_authority = $false
      new_sensing_authority = $false
      summon_authority = $false
      voice_output_authority = $false
      microphone_capture_active = [bool](Get-PropertyValue -Payload $OverlayVoice -Name 'microphone_capture' -Default $false)
      microphone_capture_authority = $false
      local_process_launch_authority = $false
      tray_registration_authority = $false
      service_control_authority = $false
      mutation_authority_granted = $false
    }
  }

  return [ordered]@{
    ok = $true
    exit_code = 0
    payload = $Payload
    error = ''
    raw_length = 0
  }
}

function Quote-ProcessArgument {
  param([string]$Value)

  if ($null -eq $Value) {
    return '""'
  }
  return '"' + ($Value -replace '"', '\"') + '"'
}

function Invoke-PowerShellJsonChild {
  param(
    [string[]]$Arguments,
    [int]$TimeoutSeconds,
    [string]$TimeoutStatus,
    [string]$TimeoutError
  )

  $PowerShell = Get-Command powershell -ErrorAction SilentlyContinue
  if ($null -eq $PowerShell) {
    $PowerShell = Get-Command pwsh -ErrorAction Stop
  }

  $BoundedTimeoutSeconds = [Math]::Max(1, $TimeoutSeconds)
  $Process = $null
  $Text = ''
  $ErrorText = ''

  try {
    $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $StartInfo.FileName = [string]$PowerShell.Source
    $StartInfo.Arguments = (@($Arguments) | ForEach-Object { Quote-ProcessArgument -Value $_ }) -join ' '
    $StartInfo.WorkingDirectory = $RepoRoot
    $StartInfo.UseShellExecute = $false
    $StartInfo.CreateNoWindow = $true
    $StartInfo.RedirectStandardOutput = $true
    $StartInfo.RedirectStandardError = $true

    $Process = [System.Diagnostics.Process]::new()
    $Process.StartInfo = $StartInfo
    $Started = $Process.Start()
    if (-not $Started) {
      return [ordered]@{
        ok = $false
        status = 'child_start_failed'
        exit_code = -1
        payload = $null
        error = 'process_not_started'
        raw_length = 0
        stderr_length = 0
        timed_out = $false
        timeout_seconds = $BoundedTimeoutSeconds
      }
    }

    $StdoutTask = $Process.StandardOutput.ReadToEndAsync()
    $StderrTask = $Process.StandardError.ReadToEndAsync()
    $Exited = $Process.WaitForExit($BoundedTimeoutSeconds * 1000)
    if (-not $Exited) {
      Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
      [void]$Process.WaitForExit(5000)
      return [ordered]@{
        ok = $false
        status = $TimeoutStatus
        exit_code = -1
        payload = $null
        error = $TimeoutError
        raw_length = 0
        stderr_length = 0
        timed_out = $true
        timeout_seconds = $BoundedTimeoutSeconds
      }
    }
    $ExitCode = [int]$Process.ExitCode
    $Text = ([string]$StdoutTask.GetAwaiter().GetResult()).Trim()
    $ErrorText = ([string]$StderrTask.GetAwaiter().GetResult()).Trim()
    try {
      return [ordered]@{
        ok = $ExitCode -eq 0
        status = if ($ExitCode -eq 0) { 'completed' } else { 'child_exit_nonzero' }
        exit_code = $ExitCode
        payload = ($Text | ConvertFrom-Json -ErrorAction Stop)
        error = ConvertTo-BoundedText -Value $ErrorText -MaxLength 512
        raw_length = $Text.Length
        stderr_length = $ErrorText.Length
        timed_out = $false
        timeout_seconds = $BoundedTimeoutSeconds
      }
    } catch {
      return [ordered]@{
        ok = $false
        status = 'child_json_parse_failed'
        exit_code = $ExitCode
        payload = $null
        error = ConvertTo-BoundedText -Value $_.Exception.Message -MaxLength 512
        raw_length = $Text.Length
        stderr_length = $ErrorText.Length
        timed_out = $false
        timeout_seconds = $BoundedTimeoutSeconds
      }
    }
  } catch {
    return [ordered]@{
      ok = $false
      status = 'child_start_failed'
      exit_code = -1
      payload = $null
      error = ConvertTo-BoundedText -Value $_.Exception.Message -MaxLength 512
      raw_length = 0
      stderr_length = 0
      timed_out = $false
      timeout_seconds = $BoundedTimeoutSeconds
    }
  } finally {
    if ($null -ne $Process) {
      $Process.Dispose()
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
      Set-PropertyValue -Payload $Payload -Name 'receipt_file_last_write_utc' -Value $File.LastWriteTimeUtc.ToString('o')
      [void]$Items.Add($Payload)
    }
  }
  return @($Items.ToArray())
}

function Get-LatestOverlayOrbPositionCommandReceipt {
  param([string]$Root)

  $ReceiptRoot = Join-Path $Root 'runtime\lens-overlay\orb-position-commands'
  if (-not (Test-Path -LiteralPath $ReceiptRoot -PathType Container)) {
    return $null
  }
  $File = Get-ChildItem -LiteralPath $ReceiptRoot -Filter '*.json' -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1
  if ($null -eq $File) {
    return $null
  }
  $Payload = Read-JsonFile -Path $File.FullName
  if ($null -eq $Payload) {
    return $null
  }
  Set-PropertyValue -Payload $Payload -Name 'receipt_path' -Value $File.FullName
  Set-PropertyValue -Payload $Payload -Name 'receipt_file_last_write_utc' -Value $File.LastWriteTimeUtc.ToString('o')
  return $Payload
}

function Test-ChatGptTranscriptUnavailableText {
  param([object]$Value)

  $Text = ([string]$Value).Trim().ToLowerInvariant()
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return $false
  }
  $Normalized = ($Text -replace '[^a-z0-9]+', ' ')
  $Normalized = ($Normalized -split '\s+' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join ' '
  foreach ($Marker in @('transcript unavailable', 'transcript not available', 'unavailable transcript')) {
    if ($Normalized -eq $Marker -or $Normalized.StartsWith("$Marker ", [System.StringComparison]::Ordinal)) {
      return $true
    }
  }
  return $false
}

function Get-ReceiptAgeSeconds {
  param([object]$Receipt)

  $CreatedTsText = [string](Get-PropertyValue -Payload $Receipt -Name 'created_ts' -Default '')
  $CreatedTs = 0.0
  if (-not [string]::IsNullOrWhiteSpace($CreatedTsText) -and [double]::TryParse($CreatedTsText, [ref]$CreatedTs)) {
    $NowTs = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    return [int][Math]::Max(0, [Math]::Floor([double]$NowTs - $CreatedTs))
  }

  $LastWriteText = [string](Get-PropertyValue -Payload $Receipt -Name 'receipt_file_last_write_utc' -Default '')
  if ([string]::IsNullOrWhiteSpace($LastWriteText)) {
    return 2147483647
  }
  try {
    $LastWrite = [DateTimeOffset]::Parse($LastWriteText)
    return [int][Math]::Max(0, [Math]::Floor(([DateTimeOffset]::UtcNow - $LastWrite).TotalSeconds))
  } catch {
    return 2147483647
  }
}

function Get-ReceiptId {
  param([object]$Receipt)

  if ($null -eq $Receipt) {
    return ''
  }
  $ReceiptId = [string](Get-PropertyValue -Payload $Receipt -Name 'receipt_id' -Default '')
  if (-not [string]::IsNullOrWhiteSpace($ReceiptId)) {
    return $ReceiptId
  }
  $Path = [string](Get-PropertyValue -Payload $Receipt -Name 'receipt_path' -Default '')
  if (-not [string]::IsNullOrWhiteSpace($Path)) {
    return [System.IO.Path]::GetFileNameWithoutExtension($Path)
  }
  return ''
}

function New-ChatGptMcpReceiptProof {
  param(
    [object[]]$Receipts,
    [int]$FreshnessSeconds
  )

  $AnyMcpServerReceipts = @(
    $Receipts | Where-Object {
      [string](Get-PropertyValue -Payload $_ -Name 'ingress_transport' -Default '') -eq 'mcp_gateway_tool' -and
      [string](Get-PropertyValue -Payload $_ -Name 'mcp_gateway_tool' -Default '') -eq 'francis.chatgpt_voice.ingress' -and
      [string](Get-PropertyValue -Payload $_ -Name 'mcp_server_tool' -Default '') -eq 'francis_chatgpt_voice_ingress'
    }
  )
  $AnyMcpProbeReceipts = @(
    $Receipts | Where-Object {
      [string](Get-PropertyValue -Payload $_ -Name 'ingress_transport' -Default '') -eq 'mcp_gateway_tool' -and
      [string](Get-PropertyValue -Payload $_ -Name 'mcp_gateway_tool' -Default '') -eq 'francis.chatgpt_voice.mcp_probe' -and
      [string](Get-PropertyValue -Payload $_ -Name 'mcp_server_tool' -Default '') -eq 'francis_chatgpt_voice_mcp_probe'
    }
  )
  $FreshAnyMcpServerReceipts = @($AnyMcpServerReceipts | Where-Object { (Get-ReceiptAgeSeconds -Receipt $_) -le $FreshnessSeconds })
  $FreshAnyMcpProbeReceipts = @($AnyMcpProbeReceipts | Where-Object { (Get-ReceiptAgeSeconds -Receipt $_) -le $FreshnessSeconds })
  $LatestAnyMcp = if (@($AnyMcpServerReceipts).Count -gt 0) { $AnyMcpServerReceipts[0] } else { $null }
  $LatestAnyMcpProbe = if (@($AnyMcpProbeReceipts).Count -gt 0) { $AnyMcpProbeReceipts[0] } else { $null }
  $ChatGptSourceReceipts = @(
    $Receipts | Where-Object {
      [string](Get-PropertyValue -Payload $_ -Name 'actor' -Default '') -eq 'chatgpt.voice' -and
      [string](Get-PropertyValue -Payload $_ -Name 'source' -Default '') -eq 'chatgpt.voice'
    }
  )
  $McpServerReceipts = @(
    $ChatGptSourceReceipts | Where-Object {
      [string](Get-PropertyValue -Payload $_ -Name 'ingress_transport' -Default '') -eq 'mcp_gateway_tool' -and
      [string](Get-PropertyValue -Payload $_ -Name 'mcp_gateway_tool' -Default '') -eq 'francis.chatgpt_voice.ingress' -and
      [string](Get-PropertyValue -Payload $_ -Name 'mcp_server_tool' -Default '') -eq 'francis_chatgpt_voice_ingress'
    }
  )
  $McpProbeReceipts = @(
    $ChatGptSourceReceipts | Where-Object {
      [string](Get-PropertyValue -Payload $_ -Name 'ingress_transport' -Default '') -eq 'mcp_gateway_tool' -and
      [string](Get-PropertyValue -Payload $_ -Name 'mcp_gateway_tool' -Default '') -eq 'francis.chatgpt_voice.mcp_probe' -and
      [string](Get-PropertyValue -Payload $_ -Name 'mcp_server_tool' -Default '') -eq 'francis_chatgpt_voice_mcp_probe'
    }
  )
  $UsableMcpServerReceipts = @(
    $McpServerReceipts | Where-Object {
      [string](Get-PropertyValue -Payload $_ -Name 'decision' -Default '') -eq 'recorded' -and
      [int](Get-PropertyValue -Payload $_ -Name 'transcript_char_count' -Default 0) -gt 0 -and
      [string](Get-PropertyValue -Payload $_ -Name 'reason' -Default '') -ne 'transcript_unavailable' -and
      -not (Test-ChatGptTranscriptUnavailableText -Value (Get-PropertyValue -Payload $_ -Name 'transcript' -Default ''))
    }
  )
  $FreshMcpServerReceipts = @($McpServerReceipts | Where-Object { (Get-ReceiptAgeSeconds -Receipt $_) -le $FreshnessSeconds })
  $FreshMcpProbeReceipts = @($McpProbeReceipts | Where-Object { (Get-ReceiptAgeSeconds -Receipt $_) -le $FreshnessSeconds })
  $McpConnectionProofReceipts = @($McpServerReceipts + $McpProbeReceipts)
  $FreshMcpConnectionProofReceipts = @($McpConnectionProofReceipts | Where-Object { (Get-ReceiptAgeSeconds -Receipt $_) -le $FreshnessSeconds })
  $FreshUsableMcpServerReceipts = @($UsableMcpServerReceipts | Where-Object { (Get-ReceiptAgeSeconds -Receipt $_) -le $FreshnessSeconds })
  $LatestChatGpt = if (@($ChatGptSourceReceipts).Count -gt 0) { $ChatGptSourceReceipts[0] } else { $null }
  $LatestMcp = if (@($McpServerReceipts).Count -gt 0) { $McpServerReceipts[0] } else { $null }
  $LatestMcpProbe = if (@($McpProbeReceipts).Count -gt 0) { $McpProbeReceipts[0] } else { $null }
  $LatestFreshMcpConnectionProof = if (@($FreshMcpConnectionProofReceipts).Count -gt 0) { $FreshMcpConnectionProofReceipts[0] } else { $null }
  $LatestFreshUsableMcp = if (@($FreshUsableMcpServerReceipts).Count -gt 0) { $FreshUsableMcpServerReceipts[0] } else { $null }
  $LatestMcpTranscriptUnavailable = (
    $null -ne $LatestMcp -and (
      [string](Get-PropertyValue -Payload $LatestMcp -Name 'reason' -Default '') -eq 'transcript_unavailable' -or
      (Test-ChatGptTranscriptUnavailableText -Value (Get-PropertyValue -Payload $LatestMcp -Name 'transcript' -Default ''))
    )
  )
  $Status = if ($null -ne $LatestFreshUsableMcp) {
    'fresh_usable_mcp_tool_receipt_observed'
  } elseif ($LatestMcpTranscriptUnavailable) {
    'latest_mcp_tool_receipt_transcript_unavailable'
  } elseif ($null -ne $LatestFreshMcpConnectionProof) {
    'fresh_mcp_connection_proof_observed'
  } elseif (@($UsableMcpServerReceipts).Count -gt 0) {
    'stale_mcp_tool_receipt_only'
  } elseif (@($McpConnectionProofReceipts).Count -gt 0) {
    'stale_mcp_connection_proof_only'
  } elseif (@($McpServerReceipts).Count -gt 0) {
    'mcp_tool_receipt_not_usable'
  } elseif (@($ChatGptSourceReceipts).Count -gt 0) {
    'chatgpt_source_without_mcp_tool_receipt'
  } else {
    'awaiting_chatgpt_mcp_tool_call'
  }
  $NextStep = if ($Status -eq 'fresh_usable_mcp_tool_receipt_observed') {
    'keep_monitoring_for_next_chatgpt_voice_turn'
  } elseif ($Status -eq 'stale_mcp_tool_receipt_only') {
    'trigger_fresh_chatgpt_app_mcp_tool_call'
  } elseif ($Status -eq 'latest_mcp_tool_receipt_transcript_unavailable') {
    'repeat_chatgpt_voice_turn_until_transcript_is_available'
  } elseif ($Status -eq 'fresh_mcp_connection_proof_observed') {
    'trigger_chatgpt_voice_app_turn_with_usable_transcript'
  } elseif ($Status -eq 'stale_mcp_connection_proof_only') {
    'trigger_fresh_chatgpt_mcp_connection_probe_or_voice_turn'
  } elseif ($Status -eq 'chatgpt_source_without_mcp_tool_receipt') {
    'select_francis_mcp_connector_in_chatgpt_and_trigger_voice_turn'
  } else {
    'call_francis_chatgpt_voice_mcp_probe_from_chatgpt_connector'
  }

  return [ordered]@{
    status = $Status
    proof_observed = ($null -ne $LatestFreshUsableMcp)
    mcp_connection_proof_observed = ($null -ne $LatestFreshMcpConnectionProof)
    mcp_connection_proof_status = if ($null -ne $LatestFreshMcpConnectionProof) { 'fresh_observed' } elseif (@($McpConnectionProofReceipts).Count -gt 0) { 'stale_only' } else { 'missing' }
    freshness_window_seconds = $FreshnessSeconds
    chatgpt_source_receipt_count = @($ChatGptSourceReceipts).Count
    any_mcp_server_receipt_count = @($AnyMcpServerReceipts).Count
    fresh_any_mcp_server_receipt_count = @($FreshAnyMcpServerReceipts).Count
    latest_any_mcp_server_receipt_id = Get-ReceiptId -Receipt $LatestAnyMcp
    latest_any_mcp_server_receipt_source = if ($null -ne $LatestAnyMcp) { [string](Get-PropertyValue -Payload $LatestAnyMcp -Name 'source' -Default '') } else { '' }
    latest_any_mcp_server_receipt_client_origin = if ($null -ne $LatestAnyMcp) { [string](Get-PropertyValue -Payload $LatestAnyMcp -Name 'client_origin' -Default '') } else { '' }
    any_mcp_probe_receipt_count = @($AnyMcpProbeReceipts).Count
    fresh_any_mcp_probe_receipt_count = @($FreshAnyMcpProbeReceipts).Count
    latest_any_mcp_probe_receipt_id = Get-ReceiptId -Receipt $LatestAnyMcpProbe
    latest_any_mcp_probe_receipt_source = if ($null -ne $LatestAnyMcpProbe) { [string](Get-PropertyValue -Payload $LatestAnyMcpProbe -Name 'source' -Default '') } else { '' }
    latest_any_mcp_probe_receipt_client_origin = if ($null -ne $LatestAnyMcpProbe) { [string](Get-PropertyValue -Payload $LatestAnyMcpProbe -Name 'client_origin' -Default '') } else { '' }
    mcp_server_receipt_count = @($McpServerReceipts).Count
    mcp_probe_receipt_count = @($McpProbeReceipts).Count
    fresh_mcp_probe_receipt_count = @($FreshMcpProbeReceipts).Count
    mcp_connection_proof_receipt_count = @($McpConnectionProofReceipts).Count
    fresh_mcp_connection_proof_receipt_count = @($FreshMcpConnectionProofReceipts).Count
    usable_mcp_server_receipt_count = @($UsableMcpServerReceipts).Count
    fresh_mcp_server_receipt_count = @($FreshMcpServerReceipts).Count
    fresh_usable_mcp_server_receipt_count = @($FreshUsableMcpServerReceipts).Count
    latest_chatgpt_source_receipt_id = Get-ReceiptId -Receipt $LatestChatGpt
    latest_mcp_server_receipt_id = Get-ReceiptId -Receipt $LatestMcp
    latest_mcp_probe_receipt_id = Get-ReceiptId -Receipt $LatestMcpProbe
    latest_mcp_connection_proof_receipt_id = Get-ReceiptId -Receipt $LatestFreshMcpConnectionProof
    latest_mcp_connection_proof_tool = if ($null -ne $LatestFreshMcpConnectionProof) { [string](Get-PropertyValue -Payload $LatestFreshMcpConnectionProof -Name 'mcp_server_tool' -Default '') } else { '' }
    latest_fresh_usable_mcp_server_receipt_id = Get-ReceiptId -Receipt $LatestFreshUsableMcp
    latest_mcp_server_receipt_age_seconds = if ($null -ne $LatestMcp) { Get-ReceiptAgeSeconds -Receipt $LatestMcp } else { $null }
    latest_mcp_transcript_unavailable = [bool]$LatestMcpTranscriptUnavailable
    transcript_redacted_from_summary = $true
    client_origin_verification = 'client_declared_not_cryptographically_verified'
    required_actor = 'chatgpt.voice'
    required_source = 'chatgpt.voice'
    required_ingress_transport = 'mcp_gateway_tool'
    required_mcp_gateway_tool = 'francis.chatgpt_voice.ingress'
    required_mcp_server_tool = 'francis_chatgpt_voice_ingress'
    required_mcp_probe_gateway_tool = 'francis.chatgpt_voice.mcp_probe'
    required_mcp_probe_server_tool = 'francis_chatgpt_voice_mcp_probe'
    next_operator_step = $NextStep
    grants_execution_authority = $false
    grants_mutation_authority = $false
  }
}

function New-ManualAcousticOrbPositionProof {
  param(
    [object]$Voice,
    [object]$OverlayVoice,
    [object]$LatestOrbPositionCommandReceipt,
    [bool]$VoiceInputReady,
    [bool]$WakeListening,
    [int]$FreshnessSeconds,
    [bool]$ManualAcousticProofRequired = $false
  )

  $VoiceStatus = [string](Get-PropertyValue -Payload $Voice -Name 'status' -Default '')
  $VoiceCommand = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Voice -Name 'orb_command' -Default '') -MaxLength 120
  $VoiceRequestId = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Voice -Name 'overlay_position_command_request_id' -Default '') -MaxLength 120
  $VoiceCommandSource = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Voice -Name 'overlay_position_command_source' -Default '') -MaxLength 120
  $VoiceTranscriptSource = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Voice -Name 'transcript_source' -Default '') -MaxLength 120
  $VoiceMicClaimed = [bool](Get-PropertyValue -Payload $Voice -Name 'microphone_recognition_claimed' -Default $false)
  $VoiceWakeDetected = [bool](Get-PropertyValue -Payload $Voice -Name 'wake_phrase_detected' -Default $false)
  $RequiredAcousticCommandSource = 'local_overlay_speech_recognition'
  $VoiceCommandSourceTrusted = ($VoiceCommandSource -eq $RequiredAcousticCommandSource)
  $VoiceLocalOrbCommand = (
    [bool](Get-PropertyValue -Payload $Voice -Name 'local_overlay_command' -Default $false) -and
    [bool](Get-PropertyValue -Payload $Voice -Name 'voice_orb_command' -Default $false) -and
    $VoiceStatus -eq 'orb_voice_command_applied'
  )
  $SignalObserved = (
    [bool](Get-PropertyValue -Payload $OverlayVoice -Name 'has_observed_microphone_signal' -Default $false) -or
    [bool](Get-PropertyValue -Payload $OverlayVoice -Name 'microphone_input_effective' -Default $false) -or
    [string](Get-PropertyValue -Payload $OverlayVoice -Name 'microphone_signal_status' -Default '') -eq 'signal_observed'
  )

  $ReceiptId = Get-ReceiptId -Receipt $LatestOrbPositionCommandReceipt
  $ReceiptRootPath = 'data/runtime/lens-overlay/orb-position-commands'
  $ReceiptFileName = if (-not [string]::IsNullOrWhiteSpace($ReceiptId)) {
    ([string]$ReceiptId) -replace '[^A-Za-z0-9_.-]', '_'
  } else {
    ''
  }
  $LatestReceiptPath = if (-not [string]::IsNullOrWhiteSpace($ReceiptFileName)) {
    '{0}/{1}.json' -f $ReceiptRootPath, $ReceiptFileName
  } else {
    ''
  }
  $ReceiptCommand = if ($null -ne $LatestOrbPositionCommandReceipt) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $LatestOrbPositionCommandReceipt -Name 'command' -Default '') -MaxLength 120 } else { '' }
  $ReceiptRequestId = if ($null -ne $LatestOrbPositionCommandReceipt) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $LatestOrbPositionCommandReceipt -Name 'request_id' -Default '') -MaxLength 120 } else { '' }
  $ReceiptCommandSource = if ($null -ne $LatestOrbPositionCommandReceipt) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $LatestOrbPositionCommandReceipt -Name 'command_source' -Default '') -MaxLength 120 } else { '' }
  $ReceiptTranscriptSource = if ($null -ne $LatestOrbPositionCommandReceipt) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $LatestOrbPositionCommandReceipt -Name 'transcript_source' -Default '') -MaxLength 120 } else { '' }
  $ReceiptMicClaimed = if ($null -ne $LatestOrbPositionCommandReceipt) { [bool](Get-PropertyValue -Payload $LatestOrbPositionCommandReceipt -Name 'microphone_recognition_claimed' -Default $false) } else { $false }
  $ReceiptWakeDetected = if ($null -ne $LatestOrbPositionCommandReceipt) { [bool](Get-PropertyValue -Payload $LatestOrbPositionCommandReceipt -Name 'wake_phrase_detected' -Default $false) } else { $false }
  $ReceiptCommandSourceTrusted = ($ReceiptCommandSource -eq $RequiredAcousticCommandSource)
  $ReceiptApplied = if ($null -ne $LatestOrbPositionCommandReceipt) {
    [bool](Get-PropertyValue -Payload $LatestOrbPositionCommandReceipt -Name 'applied' -Default $false) -and
    [string](Get-PropertyValue -Payload $LatestOrbPositionCommandReceipt -Name 'status' -Default '') -eq 'orb_voice_command_applied'
  } else {
    $false
  }
  $ReceiptAgeSeconds = if ($null -ne $LatestOrbPositionCommandReceipt) { Get-ReceiptAgeSeconds -Receipt $LatestOrbPositionCommandReceipt } else { $null }
  $ReceiptFresh = ($null -ne $ReceiptAgeSeconds -and [int]$ReceiptAgeSeconds -le $FreshnessSeconds)
  $ReceiptCommandMatchesVoice = (
    -not [string]::IsNullOrWhiteSpace($VoiceCommand) -and
    $ReceiptCommand -eq $VoiceCommand
  )
  $ReceiptRequestMatchesVoice = (
    -not [string]::IsNullOrWhiteSpace($ReceiptId) -and
    $VoiceLocalOrbCommand -and
    (
      [string]::IsNullOrWhiteSpace($VoiceRequestId) -or
      $ReceiptRequestId -eq $VoiceRequestId -or
      $ReceiptId -eq $VoiceRequestId
    )
  )
  $ReceiptMatchesVoice = (
    -not [string]::IsNullOrWhiteSpace($ReceiptId) -and
    $ReceiptApplied -and
    $ReceiptMicClaimed -and
    $ReceiptCommandSourceTrusted -and
    $ReceiptWakeDetected -and
    $ReceiptCommandMatchesVoice -and
    $ReceiptRequestMatchesVoice
  )
  $VoiceCommandCountsAsAcousticProof = ($VoiceLocalOrbCommand -and $VoiceMicClaimed -and $VoiceCommandSourceTrusted -and $VoiceWakeDetected)
  $ReceiptCountsAsAcousticProof = ($ReceiptMatchesVoice -and $ReceiptFresh)
  $ProofObserved = ($VoiceCommandCountsAsAcousticProof -and $ReceiptMatchesVoice -and $ReceiptFresh)
  $Status = if ($ProofObserved) {
    'fresh_acoustic_orb_position_command_observed'
  } elseif ($VoiceCommandCountsAsAcousticProof -and $ReceiptMatchesVoice) {
    'stale_acoustic_orb_position_command_observed'
  } elseif ($VoiceLocalOrbCommand -and -not $VoiceMicClaimed) {
    'latest_orb_position_command_not_microphone_origin'
  } elseif ($VoiceLocalOrbCommand -and -not $VoiceCommandSourceTrusted) {
    'latest_orb_position_command_not_local_overlay_speech_origin'
  } elseif ($VoiceInputReady -and $WakeListening -and $SignalObserved) {
    'ready_for_operator_acoustic_test'
  } elseif (-not $VoiceInputReady) {
    'voice_input_not_ready'
  } else {
    'missing_acoustic_orb_position_command'
  }
  $ProofBlocker = if ($ProofObserved) {
    'none'
  } elseif (-not $VoiceInputReady) {
    'voice_input_not_ready'
  } elseif (-not $WakeListening) {
    'wake_listener_not_ready'
  } elseif (-not $SignalObserved) {
    'microphone_signal_not_observed'
  } elseif (-not $VoiceLocalOrbCommand) {
    'awaiting_operator_spoken_orb_command'
  } elseif (-not $VoiceMicClaimed) {
    'latest_voice_command_not_microphone_origin'
  } elseif (-not $VoiceCommandSourceTrusted) {
    'latest_voice_command_not_local_overlay_speech_recognition'
  } elseif (-not $VoiceWakeDetected) {
    'latest_voice_command_missing_wake_phrase'
  } elseif ([string]::IsNullOrWhiteSpace($ReceiptId)) {
    'no_orb_position_receipt'
  } elseif (-not $ReceiptApplied) {
    'latest_orb_receipt_not_applied'
  } elseif (-not $ReceiptMicClaimed) {
    'latest_orb_receipt_not_microphone_origin'
  } elseif (-not $ReceiptCommandSourceTrusted) {
    'latest_orb_receipt_not_local_overlay_speech_recognition'
  } elseif (-not $ReceiptWakeDetected) {
    'latest_orb_receipt_missing_wake_phrase'
  } elseif (-not $ReceiptCommandMatchesVoice) {
    'orb_receipt_command_mismatch'
  } elseif (-not $ReceiptRequestMatchesVoice) {
    'orb_receipt_request_mismatch'
  } elseif (-not $ReceiptFresh) {
    'orb_receipt_stale'
  } else {
    'unknown_manual_acoustic_proof_gap'
  }
  $NextStep = if ($ProofObserved) {
    'keep_monitoring_or_repeat_for_next_acoustic_orb_move'
  } elseif ($Status -eq 'stale_acoustic_orb_position_command_observed') {
    'repeat_hey_francis_move_left_or_right'
  } elseif ($Status -eq 'latest_orb_position_command_not_microphone_origin') {
    'say_hey_francis_move_left_or_right_to_create_microphone_origin_receipt'
  } elseif ($Status -eq 'latest_orb_position_command_not_local_overlay_speech_origin') {
    'say_hey_francis_move_left_or_right_to_create_local_overlay_speech_receipt'
  } elseif ($Status -eq 'ready_for_operator_acoustic_test') {
    'say_hey_francis_move_left_or_right'
  } elseif ($Status -eq 'voice_input_not_ready') {
    'restore_overlay_voice_input_readiness'
  } else {
    'confirm_wake_listener_then_say_hey_francis_move_left_or_right'
  }
  $RequirementChecks = [ordered]@{
    voice_input_ready = [bool]$VoiceInputReady
    wake_listener_ready = [bool]$WakeListening
    microphone_signal_observed = [bool]$SignalObserved
    local_overlay_speech_command_observed = [bool]$VoiceLocalOrbCommand
    voice_command_microphone_origin = [bool]$VoiceMicClaimed
    voice_command_local_overlay_speech_source = [bool]$VoiceCommandSourceTrusted
    voice_command_wake_phrase_observed = [bool]$VoiceWakeDetected
    orb_receipt_observed = -not [string]::IsNullOrWhiteSpace($ReceiptId)
    orb_receipt_applied = [bool]$ReceiptApplied
    orb_receipt_microphone_origin = [bool]$ReceiptMicClaimed
    orb_receipt_local_overlay_speech_source = [bool]$ReceiptCommandSourceTrusted
    orb_receipt_wake_phrase_observed = [bool]$ReceiptWakeDetected
    orb_receipt_command_matches_voice = [bool]$ReceiptCommandMatchesVoice
    orb_receipt_request_matches_voice = [bool]$ReceiptRequestMatchesVoice
    orb_receipt_fresh = [bool]$ReceiptFresh
    api_injected_text_rejected = $true
    transcript_redacted = $true
    stores_transcript = $false
  }
  $FailedRequirementItems = [System.Collections.Generic.List[string]]::new()
  foreach ($Check in $RequirementChecks.GetEnumerator()) {
    if ([string]$Check.Key -eq 'stores_transcript') {
      if ([bool]$Check.Value) {
        $FailedRequirementItems.Add([string]$Check.Key)
      }
      continue
    }
    if (-not [bool]$Check.Value) {
      $FailedRequirementItems.Add([string]$Check.Key)
    }
  }
  $FailedRequirements = [string[]]$FailedRequirementItems.ToArray()
  $FirstFailedRequirement = if ($FailedRequirements.Count -gt 0) { $FailedRequirements[0] } else { 'none' }
  $VoiceCommandRejectionReason = if ($VoiceCommandCountsAsAcousticProof) {
    'none'
  } elseif (-not $VoiceLocalOrbCommand) {
    'no_local_overlay_speech_command'
  } elseif (-not $VoiceMicClaimed) {
    'latest_voice_command_not_microphone_origin'
  } elseif (-not $VoiceCommandSourceTrusted) {
    'latest_voice_command_not_local_overlay_speech_recognition'
  } elseif (-not $VoiceWakeDetected) {
    'latest_voice_command_missing_wake_phrase'
  } else {
    'unknown_voice_command_acoustic_rejection'
  }
  $OrbReceiptRejectionReason = if ($ReceiptCountsAsAcousticProof) {
    'none'
  } elseif ([string]::IsNullOrWhiteSpace($ReceiptId)) {
    'no_orb_position_receipt'
  } elseif (-not $ReceiptApplied) {
    'latest_orb_receipt_not_applied'
  } elseif (-not $ReceiptMicClaimed) {
    'latest_orb_receipt_not_microphone_origin'
  } elseif (-not $ReceiptCommandSourceTrusted) {
    'latest_orb_receipt_not_local_overlay_speech_recognition'
  } elseif (-not $ReceiptWakeDetected) {
    'latest_orb_receipt_missing_wake_phrase'
  } elseif (-not $ReceiptCommandMatchesVoice) {
    'orb_receipt_command_mismatch'
  } elseif (-not $ReceiptRequestMatchesVoice) {
    'orb_receipt_request_mismatch'
  } elseif (-not $ReceiptFresh) {
    'orb_receipt_stale'
  } else {
    'unknown_orb_receipt_acoustic_rejection'
  }
  $ProofSourceContract = [ordered]@{
    required_voice_command_source = $RequiredAcousticCommandSource
    required_orb_receipt_command_source = $RequiredAcousticCommandSource
    requires_microphone_recognition_claim = $true
    requires_wake_phrase = $true
    requires_matching_command = $true
    requires_matching_request_id_or_receipt_id = $true
    requires_applied_receipt = $true
    requires_fresh_receipt_seconds = $FreshnessSeconds
    api_injected_text_counts_as_proof = $false
    chatgpt_bridge_file_counts_as_proof = $false
    transcript_redacted = $true
    stores_transcript = $false
  }
  $ProofRejectionReasons = [ordered]@{
    latest_voice_command = $VoiceCommandRejectionReason
    latest_orb_receipt = $OrbReceiptRejectionReason
    first_failed_requirement = $FirstFailedRequirement
    proof_blocker = $ProofBlocker
  }
  $ProofEvidenceHint = [ordered]@{
    status = $(if ($ProofObserved) { 'satisfied' } else { 'blocked' })
    first_failed_requirement = $FirstFailedRequirement
    proof_blocker = $ProofBlocker
    next_operator_step = $NextStep
    voice_command_status_path = 'data/runtime/lens-overlay/status.json'
    microphone_status_path = 'data/runtime/lens-overlay/voice-status.json'
    orb_position_receipt_root = $ReceiptRootPath
    latest_orb_receipt_path = $LatestReceiptPath
    required_voice_status_fields = @(
      'voice.status',
      'voice.local_overlay_command',
      'voice.voice_orb_command',
      'voice.overlay_position_command_source',
      'voice.microphone_recognition_claimed',
      'voice.wake_phrase_detected',
      'voice.overlay_position_command_request_id'
    )
    required_orb_receipt_fields = @(
      'status',
      'applied',
      'request_id',
      'command',
      'command_source',
      'microphone_recognition_claimed',
      'wake_phrase_detected',
      'transcript_redacted',
      'stores_transcript'
    )
    accepted_command_source = $RequiredAcousticCommandSource
    rejected_command_sources = @(
      'chatgpt_voice_bridge_file_request',
      'http_api_text_injection',
      'mcp_gateway_tool_text_injection'
    )
    transcript_required = $false
    transcript_stored = $false
    transcript_redacted = $true
  }
  $ProofDiagnosticSummary = [ordered]@{
    first_failed_requirement = $FirstFailedRequirement
    proof_blocker = $ProofBlocker
    next_operator_step = $NextStep
    manual_acoustic_proof_required = [bool]$ManualAcousticProofRequired
    latest_voice_status = $VoiceStatus
    local_overlay_speech_command_observed = [bool]$VoiceLocalOrbCommand
    latest_voice_command_source = $VoiceCommandSource
    latest_voice_microphone_recognition_claimed = [bool]$VoiceMicClaimed
    latest_voice_local_overlay_speech_source = [bool]$VoiceCommandSourceTrusted
    latest_voice_wake_phrase_detected = [bool]$VoiceWakeDetected
    latest_voice_command_counts_as_acoustic_proof = [bool]$VoiceCommandCountsAsAcousticProof
    latest_orb_receipt_id = $ReceiptId
    latest_orb_receipt_command_source = $ReceiptCommandSource
    latest_orb_receipt_applied = [bool]$ReceiptApplied
    latest_orb_receipt_microphone_recognition_claimed = [bool]$ReceiptMicClaimed
    latest_orb_receipt_local_overlay_speech_source = [bool]$ReceiptCommandSourceTrusted
    latest_orb_receipt_wake_phrase_detected = [bool]$ReceiptWakeDetected
    latest_orb_receipt_command_matches_voice = [bool]$ReceiptCommandMatchesVoice
    latest_orb_receipt_request_matches_voice = [bool]$ReceiptRequestMatchesVoice
    latest_orb_receipt_age_seconds = $ReceiptAgeSeconds
    latest_orb_receipt_fresh = [bool]$ReceiptFresh
    latest_orb_receipt_counts_as_acoustic_proof = [bool]$ReceiptCountsAsAcousticProof
    latest_voice_command_rejection_reason = $VoiceCommandRejectionReason
    latest_orb_receipt_rejection_reason = $OrbReceiptRejectionReason
    required_receipt_source = $RequiredAcousticCommandSource
    api_injected_text_counts_as_proof = $false
    transcript_redacted = $true
    stores_transcript = $false
  }

  return [ordered]@{
    status = $Status
    proof_observed = [bool]$ProofObserved
    proof_blocker = $ProofBlocker
    first_failed_requirement = $FirstFailedRequirement
    failed_requirements = $FailedRequirements
    requirement_checks = $RequirementChecks
    proof_diagnostic_summary = $ProofDiagnosticSummary
    proof_source_contract = $ProofSourceContract
    proof_rejection_reasons = $ProofRejectionReasons
    proof_evidence_hint = $ProofEvidenceHint
    freshness_window_seconds = $FreshnessSeconds
    manual_acoustic_proof_required = [bool]$ManualAcousticProofRequired
    voice_input_ready = [bool]$VoiceInputReady
    wake_listening = [bool]$WakeListening
    microphone_signal_observed = [bool]$SignalObserved
    required_phrase = 'hey francis move left or hey francis move right'
    requires_local_overlay_speech_recognition = $true
    api_injected_text_counts_as_proof = $false
    transcript_redacted_from_summary = $true
    diagnostic_paths = [ordered]@{
      overlay_status = 'data/runtime/lens-overlay/status.json'
      overlay_voice_status = 'data/runtime/lens-overlay/voice-status.json'
      orb_position_receipt_root = $ReceiptRootPath
      latest_orb_receipt = $LatestReceiptPath
    }
    latest_voice_status = $VoiceStatus
    latest_voice_command = $VoiceCommand
    latest_voice_command_request_id = $VoiceRequestId
    latest_voice_command_source = $VoiceCommandSource
    latest_voice_transcript_source = $VoiceTranscriptSource
    latest_voice_microphone_recognition_claimed = [bool]$VoiceMicClaimed
    latest_voice_local_overlay_speech_source = [bool]$VoiceCommandSourceTrusted
    latest_voice_wake_phrase_detected = [bool]$VoiceWakeDetected
    latest_voice_command_counts_as_acoustic_proof = [bool]$VoiceCommandCountsAsAcousticProof
    latest_voice_command_rejection_reason = $VoiceCommandRejectionReason
    latest_orb_receipt_id = $ReceiptId
    latest_orb_receipt_command = $ReceiptCommand
    latest_orb_receipt_request_id = $ReceiptRequestId
    latest_orb_receipt_command_source = $ReceiptCommandSource
    latest_orb_receipt_transcript_source = $ReceiptTranscriptSource
    latest_orb_receipt_microphone_recognition_claimed = [bool]$ReceiptMicClaimed
    latest_orb_receipt_local_overlay_speech_source = [bool]$ReceiptCommandSourceTrusted
    latest_orb_receipt_wake_phrase_detected = [bool]$ReceiptWakeDetected
    latest_orb_receipt_applied = [bool]$ReceiptApplied
    latest_orb_receipt_age_seconds = $ReceiptAgeSeconds
    latest_orb_receipt_fresh = [bool]$ReceiptFresh
    latest_orb_receipt_matches_latest_voice_command = [bool]$ReceiptCommandMatchesVoice
    latest_orb_receipt_matches_latest_voice_request = [bool]$ReceiptRequestMatchesVoice
    latest_orb_receipt_counts_as_acoustic_proof = [bool]$ReceiptCountsAsAcousticProof
    latest_orb_receipt_rejection_reason = $OrbReceiptRejectionReason
    next_operator_step = $NextStep
    grants_execution_authority = $false
    grants_mutation_authority = $false
  }
}

function Invoke-ChatGptConnectorReadback {
  param(
    [string]$Root,
    [string]$ConnectorUrl,
    [int]$ConnectorPort,
    [bool]$VerifyConnector,
    [int]$ProbeTimeoutSeconds
  )

  $RuntimeRoot = Join-Path (Join-Path $Root 'runtime') 'chatgpt-voice-connector'
  $Arguments = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    (Join-Path $PSScriptRoot 'chatgpt-voice-connector.ps1'),
    '-Mode',
    'Status',
    '-RuntimeRoot',
    $RuntimeRoot,
    '-Port',
    ([string]$ConnectorPort),
    '-ConnectorProbeTimeoutSeconds',
    ([string]$ProbeTimeoutSeconds),
    '-Json'
  )
  if (-not [string]::IsNullOrWhiteSpace($ConnectorUrl)) {
    $Arguments += @('-ConnectorUrl', $ConnectorUrl)
  }
  if ($VerifyConnector) {
    $Arguments += '-VerifyConnector'
  }

  $ChildTimeoutSeconds = [Math]::Max(8, [Math]::Min(120, $ProbeTimeoutSeconds + 18))
  return Invoke-PowerShellJsonChild `
    -Arguments $Arguments `
    -TimeoutSeconds $ChildTimeoutSeconds `
    -TimeoutStatus 'connector_status_readback_timeout' `
    -TimeoutError 'chatgpt_connector_status_readback_timeout'
}

function Invoke-ChatGptPersistentIngressPlanReadback {
  param(
    [string]$Root,
    [string]$ConnectorUrl,
    [int]$ConnectorPort,
    [string]$CloudflaredTunnelName,
    [string]$CloudflaredHostname,
    [string]$CloudflaredTokenFile,
    [bool]$VerifyConnector,
    [int]$ProbeTimeoutSeconds
  )

  $RuntimeRoot = Join-Path (Join-Path $Root 'runtime') 'chatgpt-voice-connector'
  $Arguments = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    (Join-Path $PSScriptRoot 'chatgpt-voice-connector.ps1'),
    '-Mode',
    'PlanPersistentIngress',
    '-RuntimeRoot',
    $RuntimeRoot,
    '-Port',
    ([string]$ConnectorPort),
    '-ConnectorProbeTimeoutSeconds',
    ([string]$ProbeTimeoutSeconds),
    '-Json'
  )
  if (-not [string]::IsNullOrWhiteSpace($ConnectorUrl)) {
    $Arguments += @('-ConnectorUrl', $ConnectorUrl)
  }
  if (-not [string]::IsNullOrWhiteSpace($CloudflaredTunnelName)) {
    $Arguments += @('-CloudflaredTunnelName', $CloudflaredTunnelName)
  }
  if (-not [string]::IsNullOrWhiteSpace($CloudflaredHostname)) {
    $Arguments += @('-CloudflaredHostname', $CloudflaredHostname)
  }
  if (-not [string]::IsNullOrWhiteSpace($CloudflaredTokenFile)) {
    $Arguments += @('-CloudflaredTokenFile', $CloudflaredTokenFile)
  }
  if ($VerifyConnector) {
    $Arguments += '-VerifyConnector'
  }

  $ChildTimeoutSeconds = [Math]::Max(8, [Math]::Min(120, $ProbeTimeoutSeconds + 18))
  return Invoke-PowerShellJsonChild `
    -Arguments $Arguments `
    -TimeoutSeconds $ChildTimeoutSeconds `
    -TimeoutStatus 'persistent_ingress_plan_readback_timeout' `
    -TimeoutError 'chatgpt_persistent_ingress_plan_readback_timeout'
}

function New-ChatGptPersistentIngressPlanMonitorProjection {
  param(
    [string]$Root,
    [string]$ConnectorUrl,
    [int]$ConnectorPort,
    [string]$CloudflaredTunnelName,
    [string]$CloudflaredHostname,
    [string]$CloudflaredTokenFile,
    [bool]$VerifyConnector,
    [int]$ProbeTimeoutSeconds
  )

  $Readback = Invoke-ChatGptPersistentIngressPlanReadback -Root $Root -ConnectorUrl $ConnectorUrl -ConnectorPort $ConnectorPort -CloudflaredTunnelName $CloudflaredTunnelName -CloudflaredHostname $CloudflaredHostname -CloudflaredTokenFile $CloudflaredTokenFile -VerifyConnector $VerifyConnector -ProbeTimeoutSeconds $ProbeTimeoutSeconds
  $Payload = Get-PropertyValue -Payload $Readback -Name 'payload'
  $ReadbackStatus = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Readback -Name 'status' -Default '') -MaxLength 120
  $Governance = Get-PropertyValue -Payload $Payload -Name 'governance'
  $ProviderReadiness = Get-PropertyValue -Payload $Payload -Name 'provider_readiness'
  $InstallerReadiness = Get-PropertyValue -Payload $Payload -Name 'installer_readiness'
  $Cloudflared = Get-PropertyValue -Payload $ProviderReadiness -Name 'cloudflared_named_tunnel'
  $CloudflaredToken = Get-PropertyValue -Payload $ProviderReadiness -Name 'cloudflared_token_tunnel'
  $CloudflaredLogin = Get-PropertyValue -Payload $Payload -Name 'cloudflared_login'
  $CloudflaredPreflight = Get-PropertyValue -Payload $Cloudflared -Name 'named_tunnel_preflight'
  $Ngrok = Get-PropertyValue -Payload $ProviderReadiness -Name 'ngrok_reserved_domain'
  $Caddy = Get-PropertyValue -Payload $ProviderReadiness -Name 'caddy_reverse_proxy'
  $Ssh = Get-PropertyValue -Payload $ProviderReadiness -Name 'ssh_reverse_tunnel'
  $Winget = Get-PropertyValue -Payload $InstallerReadiness -Name 'winget'
  $ReadOnly = [bool](Get-PropertyValue -Payload $Governance -Name 'read_only' -Default $false)
  $StartsProcess = [bool](Get-PropertyValue -Payload $Governance -Name 'starts_process' -Default $true)
  $OpensPublicTunnel = [bool](Get-PropertyValue -Payload $Governance -Name 'opens_public_tunnel' -Default $true)
  $WritesData = [bool](Get-PropertyValue -Payload $Governance -Name 'writes_data' -Default $true)
  $CloudflaredSetupCommandItems = [System.Collections.Generic.List[string]]::new()
  foreach ($Command in @(Get-PropertyValue -Payload $Cloudflared -Name 'operator_provider_setup_commands' -Default @())) {
    $CommandText = ConvertTo-BoundedText -Value $Command -MaxLength 260
    if (-not [string]::IsNullOrWhiteSpace($CommandText)) {
      $CloudflaredSetupCommandItems.Add($CommandText)
    }
  }
  $CloudflaredSetupCommands = [string[]]$CloudflaredSetupCommandItems.ToArray()

  return [ordered]@{
    enabled = $true
    ok = [bool](Get-PropertyValue -Payload $Readback -Name 'ok' -Default $false)
    exit_code = [int](Get-PropertyValue -Payload $Readback -Name 'exit_code' -Default 0)
    status = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Payload -Name 'status' -Default $(if ([string]::IsNullOrWhiteSpace($ReadbackStatus)) { 'plan_unavailable' } else { $ReadbackStatus })) -MaxLength 96
    error = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Readback -Name 'error' -Default '') -MaxLength 512
    timed_out = [bool](Get-PropertyValue -Payload $Readback -Name 'timed_out' -Default $false)
    timeout_seconds = [int](Get-PropertyValue -Payload $Readback -Name 'timeout_seconds' -Default 0)
    local_endpoint = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Payload -Name 'local_endpoint' -Default '') -MaxLength 160
    blockers = @(Get-PropertyValue -Payload $Payload -Name 'blockers' -Default @())
    recommended_provider_order = @(Get-PropertyValue -Payload $Payload -Name 'recommended_provider_order' -Default @())
    next_operator_steps = @(Get-PropertyValue -Payload $Payload -Name 'next_operator_steps' -Default @())
    operator_handoff = Get-PropertyValue -Payload $Payload -Name 'operator_handoff' -Default $null
    providers = [ordered]@{
      cloudflared_named_tunnel_available = [bool](Get-PropertyValue -Payload $Cloudflared -Name 'available' -Default $false)
      cloudflared_named_tunnel_path = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Cloudflared -Name 'path' -Default '') -MaxLength 512
      cloudflared_named_tunnel_origin_cert_present = [bool](Get-PropertyValue -Payload $Cloudflared -Name 'origin_cert_present' -Default $false)
      cloudflared_named_tunnel_origin_cert_content_read = [bool](Get-PropertyValue -Payload $Cloudflared -Name 'origin_cert_content_read' -Default $false)
      cloudflared_named_tunnel_login_required = [bool](Get-PropertyValue -Payload $Cloudflared -Name 'login_required' -Default $true)
      cloudflared_named_tunnel_requested = [bool](Get-PropertyValue -Payload $Cloudflared -Name 'named_tunnel_requested' -Default $false)
      cloudflared_named_tunnel_requested_name = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Cloudflared -Name 'requested_tunnel_name' -Default '') -MaxLength 160
      cloudflared_named_tunnel_requested_hostname = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Cloudflared -Name 'requested_hostname' -Default '') -MaxLength 240
      cloudflared_named_tunnel_exists = [bool](Get-PropertyValue -Payload $Cloudflared -Name 'named_tunnel_exists' -Default $false)
      cloudflared_named_tunnel_preflight_checked = [bool](Get-PropertyValue -Payload $CloudflaredPreflight -Name 'checked' -Default $false)
      cloudflared_named_tunnel_preflight_exists = [bool](Get-PropertyValue -Payload $CloudflaredPreflight -Name 'exists' -Default $false)
      cloudflared_named_tunnel_preflight_output_discarded = [bool](Get-PropertyValue -Payload $CloudflaredPreflight -Name 'output_discarded' -Default $true)
      cloudflared_named_tunnel_operator_provider_setup_commands = $CloudflaredSetupCommands
      cloudflared_named_tunnel_next_operator_step = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Cloudflared -Name 'next_operator_step' -Default '') -MaxLength 160
      cloudflared_token_tunnel_available = [bool](Get-PropertyValue -Payload $CloudflaredToken -Name 'available' -Default $false)
      cloudflared_token_tunnel_path = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $CloudflaredToken -Name 'path' -Default '') -MaxLength 512
      cloudflared_token_tunnel_token_file_requested = [bool](Get-PropertyValue -Payload $CloudflaredToken -Name 'token_file_requested' -Default $false)
      cloudflared_token_tunnel_token_file_present = [bool](Get-PropertyValue -Payload $CloudflaredToken -Name 'token_file_present' -Default $false)
      cloudflared_token_tunnel_token_file_content_read = [bool](Get-PropertyValue -Payload $CloudflaredToken -Name 'token_file_content_read' -Default $false)
      cloudflared_token_tunnel_requested_hostname = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $CloudflaredToken -Name 'requested_hostname' -Default '') -MaxLength 240
      cloudflared_token_tunnel_hostname_requested = [bool](Get-PropertyValue -Payload $CloudflaredToken -Name 'hostname_requested' -Default $false)
      cloudflared_token_tunnel_next_operator_step = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $CloudflaredToken -Name 'next_operator_step' -Default '') -MaxLength 160
      cloudflared_login_status = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $CloudflaredLogin -Name 'status' -Default '') -MaxLength 96
      cloudflared_login_process_id = [int](Get-PropertyValue -Payload $CloudflaredLogin -Name 'process_id' -Default 0)
      cloudflared_login_process_alive = [bool](Get-PropertyValue -Payload $CloudflaredLogin -Name 'process_alive' -Default $false)
      cloudflared_login_provider_started = [bool](Get-PropertyValue -Payload $CloudflaredLogin -Name 'provider_login_started' -Default $false)
      cloudflared_login_browser_may_open = [bool](Get-PropertyValue -Payload $CloudflaredLogin -Name 'provider_login_browser_may_open' -Default $false)
      cloudflared_login_writes_origin_cert = [bool](Get-PropertyValue -Payload $CloudflaredLogin -Name 'provider_login_writes_origin_cert' -Default $false)
      cloudflared_login_origin_cert_present = [bool](Get-PropertyValue -Payload $CloudflaredLogin -Name 'origin_cert_present' -Default $false)
      cloudflared_login_origin_cert_content_read = [bool](Get-PropertyValue -Payload $CloudflaredLogin -Name 'origin_cert_content_read' -Default $false)
      cloudflared_login_public_tunnel_started = [bool](Get-PropertyValue -Payload $CloudflaredLogin -Name 'public_tunnel_started' -Default $false)
      cloudflared_login_connector_url_recorded = [bool](Get-PropertyValue -Payload $CloudflaredLogin -Name 'connector_url_recorded' -Default $false)
      ngrok_reserved_domain_available = [bool](Get-PropertyValue -Payload $Ngrok -Name 'available' -Default $false)
      caddy_reverse_proxy_available = [bool](Get-PropertyValue -Payload $Caddy -Name 'available' -Default $false)
      ssh_reverse_tunnel_available = [bool](Get-PropertyValue -Payload $Ssh -Name 'available' -Default $false)
      winget_available = [bool](Get-PropertyValue -Payload $Winget -Name 'available' -Default $false)
    }
    localtunnel_replacement = Get-PropertyValue -Payload $Payload -Name 'localtunnel_replacement' -Default $null
    governance = [ordered]@{
      read_only_contract = [bool]$ReadOnly
      starts_process = [bool]$StartsProcess
      opens_public_tunnel = [bool]$OpensPublicTunnel
      writes_repo = $false
      writes_data = [bool]$WritesData
      captures_audio = $false
      captures_screen = $false
      execution_authority = $false
      mutation_authority_granted = $false
    }
    governance_safe = [bool]($ReadOnly -and -not $StartsProcess -and -not $OpensPublicTunnel -and -not $WritesData)
  }
}

function New-ChatGptConnectorMonitorProjection {
  param(
    [string]$Root,
    [string]$ConnectorUrl,
    [int]$ConnectorPort,
    [bool]$VerifyConnector,
    [int]$ProbeTimeoutSeconds
  )

  $Readback = Invoke-ChatGptConnectorReadback -Root $Root -ConnectorUrl $ConnectorUrl -ConnectorPort $ConnectorPort -VerifyConnector $VerifyConnector -ProbeTimeoutSeconds $ProbeTimeoutSeconds
  $Payload = Get-PropertyValue -Payload $Readback -Name 'payload'
  $ReadbackStatus = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Readback -Name 'status' -Default '') -MaxLength 120
  $ConnectorUrlValue = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Payload -Name 'connector_url' -Default '') -MaxLength 512
  $ConnectorUrlSource = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Payload -Name 'connector_url_source' -Default '') -MaxLength 160
  $ConnectorShapeValid = [bool](Get-NestedPropertyValue -Payload $Payload -Path @('endpoint_status', 'chatgpt_connector', 'connector_url', 'shape_valid') -Default $false)
  $ConnectorReachabilityVerified = [bool](Get-NestedPropertyValue -Payload $Payload -Path @('endpoint_status', 'chatgpt_connector', 'connector_url', 'reachability_verified') -Default $false)
  $ConnectorUsable = [bool](Get-NestedPropertyValue -Payload $Payload -Path @('endpoint_status', 'chatgpt_connector', 'connector_url', 'usable_for_chatgpt') -Default $false)
  $ConnectorReason = ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $Payload -Path @('endpoint_status', 'chatgpt_connector', 'connector_url', 'reason') -Default '') -MaxLength 160
  $ExpectedToolPresent = [bool](Get-NestedPropertyValue -Payload $Payload -Path @('endpoint_status', 'chatgpt_connector', 'probe', 'expected_tool_present') -Default $false)
  $LocalListenerReady = [bool](Get-NestedPropertyValue -Payload $Payload -Path @('endpoint_status', 'local_listener', 'ready') -Default $false)
  $McpLauncherAlive = [bool](Get-NestedPropertyValue -Payload $Payload -Path @('processes', 'mcp_launcher', 'alive') -Default $false)
  $TunnelAlive = [bool](Get-NestedPropertyValue -Payload $Payload -Path @('processes', 'tunnel', 'alive') -Default $false)
  $LocalTunnelStable = [bool](Get-NestedPropertyValue -Payload $Payload -Path @('localtunnel', 'stable_for_existing_chatgpt_connector') -Default $true)
  $LocalTunnelReason = ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $Payload -Path @('localtunnel', 'reason') -Default '') -MaxLength 160
  $CloudflaredQuickStable = [bool](Get-NestedPropertyValue -Payload $Payload -Path @('cloudflared_quick_tunnel', 'stable_for_existing_chatgpt_connector') -Default $true)
  $CloudflaredQuickReason = ConvertTo-BoundedText -Value (Get-NestedPropertyValue -Payload $Payload -Path @('cloudflared_quick_tunnel', 'reason') -Default '') -MaxLength 160
  $ConnectorHost = ''
  if (-not [string]::IsNullOrWhiteSpace($ConnectorUrlValue)) {
    try {
      $ConnectorHost = ([System.Uri]$ConnectorUrlValue).Host
    } catch {
      $ConnectorHost = ''
    }
  }
  $KnownLocalTunnel = (
    $ConnectorUrlSource -eq 'localtunnel' -or
    (-not [string]::IsNullOrWhiteSpace($ConnectorHost) -and $ConnectorHost.EndsWith('.loca.lt', [System.StringComparison]::OrdinalIgnoreCase))
  )
  $KnownCloudflaredQuickTunnel = (
    $ConnectorUrlSource -eq 'cloudflared_quick' -or
    (-not [string]::IsNullOrWhiteSpace($ConnectorHost) -and $ConnectorHost.EndsWith('.trycloudflare.com', [System.StringComparison]::OrdinalIgnoreCase))
  )
  $PersistentCandidate = [bool]($ConnectorShapeValid -and -not $KnownLocalTunnel -and -not $KnownCloudflaredQuickTunnel)
  $IngressStatus = if (-not $ConnectorShapeValid) {
    if ([string]::IsNullOrWhiteSpace($ConnectorUrlValue)) { 'connector_url_missing' } else { 'connector_url_invalid' }
  } elseif ($KnownLocalTunnel) {
    'localtunnel_fallback_replace_needed'
  } elseif ($KnownCloudflaredQuickTunnel) {
    'cloudflared_quick_tunnel_replace_needed'
  } elseif ($ConnectorUsable -or (-not $VerifyConnector)) {
    'persistent_ingress_candidate'
  } else {
    'persistent_ingress_unverified'
  }
  $Blockers = @()
  if (-not $ConnectorShapeValid) {
    $Blockers += $(if ([string]::IsNullOrWhiteSpace($ConnectorReason)) { 'connector_url_not_ready' } else { $ConnectorReason })
  }
  if ($KnownLocalTunnel) {
    $Blockers += 'localtunnel_url_is_not_persistent_ingress'
  }
  if ($KnownCloudflaredQuickTunnel) {
    $Blockers += 'cloudflared_quick_url_is_not_persistent_ingress'
  }
  if (-not $LocalTunnelStable) {
    $Blockers += 'localtunnel_requested_subdomain_not_honored'
  }

  return [ordered]@{
    enabled = $true
    ok = [bool](Get-PropertyValue -Payload $Readback -Name 'ok' -Default $false)
    exit_code = [int](Get-PropertyValue -Payload $Readback -Name 'exit_code' -Default 0)
    status = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Payload -Name 'status' -Default $(if ([string]::IsNullOrWhiteSpace($ReadbackStatus)) { 'status_unavailable' } else { $ReadbackStatus })) -MaxLength 96
    error = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Readback -Name 'error' -Default '') -MaxLength 512
    timed_out = [bool](Get-PropertyValue -Payload $Readback -Name 'timed_out' -Default $false)
    timeout_seconds = [int](Get-PropertyValue -Payload $Readback -Name 'timeout_seconds' -Default 0)
    connector_url_present = -not [string]::IsNullOrWhiteSpace($ConnectorUrlValue)
    connector_url_host = $ConnectorHost
    connector_url_source = $ConnectorUrlSource
    connector_shape_valid = [bool]$ConnectorShapeValid
    connector_reason = $ConnectorReason
    connector_reachability_requested = [bool]$VerifyConnector
    connector_reachability_verified = [bool]$ConnectorReachabilityVerified
    connector_usable_for_chatgpt = [bool]$ConnectorUsable
    expected_tool_present = [bool]$ExpectedToolPresent
    local_listener_ready = [bool]$LocalListenerReady
    mcp_launcher_alive = [bool]$McpLauncherAlive
    public_tunnel_process_alive = [bool]$TunnelAlive
    known_localtunnel = [bool]$KnownLocalTunnel
    localtunnel_stable_for_existing_connector = [bool]$LocalTunnelStable
    localtunnel_reason = $LocalTunnelReason
    known_cloudflared_quick_tunnel = [bool]$KnownCloudflaredQuickTunnel
    cloudflared_quick_stable_for_existing_connector = [bool]$CloudflaredQuickStable
    cloudflared_quick_reason = $CloudflaredQuickReason
    persistent_candidate = [bool]$PersistentCandidate
    persistent_ingress_status = $IngressStatus
    blockers = @($Blockers)
    next_operator_step = if ($PersistentCandidate) {
      'verify_or_record_persistent_chatgpt_ingress'
    } elseif ($KnownLocalTunnel) {
      'replace_localtunnel_with_persistent_https_mcp_ingress'
    } elseif ($KnownCloudflaredQuickTunnel) {
      'replace_cloudflared_quick_tunnel_with_persistent_https_mcp_ingress'
    } else {
      'replace_ephemeral_tunnel_with_persistent_https_mcp_ingress'
    }
    governance = [ordered]@{
      read_only_contract = $true
      starts_process = $false
      opens_public_tunnel = $false
      writes_repo = $false
      writes_data = $false
      captures_audio = $false
      captures_screen = $false
      execution_authority = $false
      mutation_authority_granted = $false
    }
  }
}

function New-VoiceMonitorProjection {
  param(
    [string]$Root,
    [string]$Provider,
    [string]$RemoteVoiceId,
    [string]$RemoteVoiceName,
    [int]$McpProofFreshnessSeconds
  )

  $Readback = Invoke-OverlayVoiceReadback -Root $Root -Provider $Provider -RemoteVoiceId $RemoteVoiceId -RemoteVoiceName $RemoteVoiceName
  $Payload = Get-PropertyValue -Payload $Readback -Name 'payload'
  $OverlayVoice = Get-PropertyValue -Payload $Payload -Name 'overlay_voice'
  $Voice = Get-PropertyValue -Payload $Payload -Name 'voice'
  $VoiceTurn = Get-PropertyValue -Payload $Payload -Name 'voice_turn'
  $OverlayPosition = Get-PropertyValue -Payload $Payload -Name 'overlay_position'
  $ProviderReadiness = Get-PropertyValue -Payload $Payload -Name 'voice_provider_readiness'
  $ElevenLabs = Get-PropertyValue -Payload $ProviderReadiness -Name 'elevenlabs'
  $Receipts = @(Get-RecentChatGptVoiceReceipts -Root $Root -Limit 5)
  $McpProof = New-ChatGptMcpReceiptProof -Receipts $Receipts -FreshnessSeconds $McpProofFreshnessSeconds
  $LatestOrbPositionCommandReceipt = Get-LatestOverlayOrbPositionCommandReceipt -Root $Root

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
  $WakeListening = [bool](Get-PropertyValue -Payload $OverlayVoice -Name 'wake_listening' -Default $false)
  $WakePhrase = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $OverlayVoice -Name 'wake_phrase' -Default '') -MaxLength 80
  $ContinuousVoiceChat = [bool](Get-PropertyValue -Payload $OverlayVoice -Name 'continuous_voice_chat' -Default $false)
  $ContinuousVoiceChatMode = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $OverlayVoice -Name 'continuous_voice_chat_mode' -Default '') -MaxLength 120
  $SelfTriggerGuard = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $OverlayVoice -Name 'continuous_voice_chat_self_trigger_guard' -Default '') -MaxLength 160
  $MicrophoneGateWhileSpeaking = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $OverlayVoice -Name 'microphone_gate_while_speaking' -Default '') -MaxLength 120
  $ConversationForwardingWhileSpeaking = [bool](Get-PropertyValue -Payload $OverlayVoice -Name 'conversation_forwarding_while_speaking' -Default $true)
  $VoiceInputReady = [bool](Get-PropertyValue -Payload $Payload -Name 'voice_input_ready' -Default $false)
  $VoiceInputStatus = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Payload -Name 'voice_input_status' -Default '') -MaxLength 120
  $VoiceInputBlocker = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Payload -Name 'voice_input_blocker' -Default '') -MaxLength 160
  $NextVoiceInputStep = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Payload -Name 'next_voice_input_step' -Default '') -MaxLength 200
  $OverlayPositionAnchor = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $OverlayPosition -Name 'operator_position_anchor' -Default '') -MaxLength 120
  $VoicePositionCommandActive = [bool](Get-PropertyValue -Payload $OverlayPosition -Name 'voice_position_command_active' -Default $false)
  $VoiceOrbCommand = [bool](Get-PropertyValue -Payload $Voice -Name 'voice_orb_command' -Default $false)
  $LocalOverlayCommand = [bool](Get-PropertyValue -Payload $Voice -Name 'local_overlay_command' -Default $false)
  $LatestOrbCommandName = ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $Voice -Name 'orb_command' -Default '') -MaxLength 120
  $LatestOrbReceiptCommandName = if ($null -ne $LatestOrbPositionCommandReceipt) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $LatestOrbPositionCommandReceipt -Name 'command' -Default '') -MaxLength 120 } else { '' }
  $LatestOrbReceiptStatus = if ($null -ne $LatestOrbPositionCommandReceipt) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $LatestOrbPositionCommandReceipt -Name 'status' -Default '') -MaxLength 120 } else { '' }
  $LatestOrbReceiptApplied = if ($null -ne $LatestOrbPositionCommandReceipt) { [bool](Get-PropertyValue -Payload $LatestOrbPositionCommandReceipt -Name 'applied' -Default $false) } else { $false }
  $LatestOrbReceiptId = if ($null -ne $LatestOrbPositionCommandReceipt) { ConvertTo-BoundedText -Value (Get-PropertyValue -Payload $LatestOrbPositionCommandReceipt -Name 'request_id' -Default '') -MaxLength 120 } else { '' }
  if ([string]::IsNullOrWhiteSpace($LatestOrbCommandName) -and $OverlayPositionAnchor.StartsWith('voice_command_', [System.StringComparison]::OrdinalIgnoreCase)) {
    $LatestOrbCommandName = $OverlayPositionAnchor -replace '^voice_command_', 'move_orb_'
  }
  if ([string]::IsNullOrWhiteSpace($LatestOrbCommandName) -and -not [string]::IsNullOrWhiteSpace($LatestOrbReceiptCommandName)) {
    $LatestOrbCommandName = $LatestOrbReceiptCommandName
  }
  $LatestOrbCommandStatus = if ($VoiceOrbCommand -or $LocalOverlayCommand) { $VoiceStatus } elseif (-not [string]::IsNullOrWhiteSpace($LatestOrbReceiptStatus)) { $LatestOrbReceiptStatus } elseif ($VoicePositionCommandActive) { 'position_anchor_active' } else { '' }
  $LatestOrbCommandApplied = ($VoiceStatus -eq 'orb_voice_command_applied' -or $VoicePositionCommandActive -or $LatestOrbReceiptApplied)
  $OrbPositionCommandReady = ([bool]$VoiceInputReady -and [bool]$WakeListening)
  $ManualAcousticOrbProof = New-ManualAcousticOrbPositionProof -Voice $Voice -OverlayVoice $OverlayVoice -LatestOrbPositionCommandReceipt $LatestOrbPositionCommandReceipt -VoiceInputReady ([bool]$VoiceInputReady) -WakeListening ([bool]$WakeListening) -FreshnessSeconds $McpProofFreshnessSeconds -ManualAcousticProofRequired ([bool]$RequireManualAcousticOrbProof)
  $PassiveListenContract = 'passive_transcript_awareness_only_until_wake_phrase'
  $InterruptPhrase = 'francis stop'
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
  $LatestReceiptId = if ($null -ne $LatestReceipt) { Get-ReceiptId -Receipt $LatestReceipt } else { '' }
  $LatestReceiptActor = if ($null -ne $LatestReceipt) { [string](Get-PropertyValue -Payload $LatestReceipt -Name 'actor' -Default '') } else { '' }
  $LatestReceiptSource = if ($null -ne $LatestReceipt) { [string](Get-PropertyValue -Payload $LatestReceipt -Name 'source' -Default '') } else { '' }
  $LatestReceiptClientOrigin = if ($null -ne $LatestReceipt) { [string](Get-PropertyValue -Payload $LatestReceipt -Name 'client_origin' -Default '') } else { '' }
  $LatestReceiptIngressTransport = if ($null -ne $LatestReceipt) { [string](Get-PropertyValue -Payload $LatestReceipt -Name 'ingress_transport' -Default '') } else { '' }
  $LatestReceiptMcpGatewayTool = if ($null -ne $LatestReceipt) { [string](Get-PropertyValue -Payload $LatestReceipt -Name 'mcp_gateway_tool' -Default '') } else { '' }
  $LatestReceiptMcpServerTool = if ($null -ne $LatestReceipt) { [string](Get-PropertyValue -Payload $LatestReceipt -Name 'mcp_server_tool' -Default '') } else { '' }
  $LatestReceiptCountsAsMcpProof = (
    $LatestReceiptActor -eq 'chatgpt.voice' -and
    $LatestReceiptSource -eq 'chatgpt.voice' -and
    $LatestReceiptIngressTransport -eq 'mcp_gateway_tool' -and
    $LatestReceiptMcpGatewayTool -eq 'francis.chatgpt_voice.ingress' -and
    $LatestReceiptMcpServerTool -eq 'francis_chatgpt_voice_ingress'
  )
  $LatestReceiptProofRejectionReason = if ($null -eq $LatestReceipt) {
    'no_recent_receipt'
  } elseif ($LatestReceiptCountsAsMcpProof) {
    'counts_as_chatgpt_mcp_proof'
  } elseif ($LatestReceiptActor -ne 'chatgpt.voice' -or $LatestReceiptSource -ne 'chatgpt.voice') {
    'latest_receipt_not_chatgpt_voice_origin'
  } elseif ($LatestReceiptIngressTransport -ne 'mcp_gateway_tool') {
    'latest_receipt_not_mcp_gateway_tool_transport'
  } elseif ($LatestReceiptMcpGatewayTool -ne 'francis.chatgpt_voice.ingress') {
    'latest_receipt_wrong_mcp_gateway_tool'
  } else {
    'latest_receipt_wrong_mcp_server_tool'
  }

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
    wake_listening = [bool]$WakeListening
    wake_phrase = $WakePhrase
    passive_listen_contract = $PassiveListenContract
    continuous_voice_chat = [bool]$ContinuousVoiceChat
    continuous_voice_chat_mode = $ContinuousVoiceChatMode
    continuous_voice_chat_self_trigger_guard = $SelfTriggerGuard
    microphone_gate_while_speaking = $MicrophoneGateWhileSpeaking
    conversation_forwarding_while_speaking = [bool]$ConversationForwardingWhileSpeaking
    interrupt_phrase = $InterruptPhrase
    voice_input_ready = [bool]$VoiceInputReady
    voice_input_status = $VoiceInputStatus
    voice_input_blocker = $VoiceInputBlocker
    next_voice_input_step = $NextVoiceInputStep
    orb_position_command_ready = [bool]$OrbPositionCommandReady
    orb_position_command_targets = @('left', 'right')
    orb_position_command_requires_orb_reference = $true
    orb_position_command_accepts_francis_identity_reference = $true
    orb_position_command_accepts_wake_phrase_reference = $true
    orb_position_command_requires_direction = $true
    orb_position_command_conversation_forwarding_suppressed = $true
    orb_position_command_authority_scope = 'runtime_overlay_position_only'
    overlay_position_anchor = $OverlayPositionAnchor
    overlay_left = [double](Get-PropertyValue -Payload $OverlayPosition -Name 'left' -Default 0.0)
    overlay_top = [double](Get-PropertyValue -Payload $OverlayPosition -Name 'top' -Default 0.0)
    voice_position_command_active = [bool]$VoicePositionCommandActive
    latest_orb_position_command = $LatestOrbCommandName
    latest_orb_position_command_status = $LatestOrbCommandStatus
    latest_orb_position_command_applied = [bool]$LatestOrbCommandApplied
    latest_orb_position_command_receipt_id = $LatestOrbReceiptId
    latest_orb_position_command_receipt_observed = ($null -ne $LatestOrbPositionCommandReceipt)
    manual_acoustic_orb_position_proof = $ManualAcousticOrbProof
    api_permission_denied_observed = [bool]$PermissionDenied
    recent_receipt_count = @($Receipts).Count
    denied_recent_receipt_count = @($DeniedReceipts).Count
    latest_receipt_denied = [bool]$LatestReceiptDenied
    latest_receipt_status = if ($null -ne $LatestReceipt) { [string](Get-PropertyValue -Payload $LatestReceipt -Name 'status' -Default '') } else { '' }
    latest_receipt_chat_forward_status = if ($null -ne $LatestReceipt) { [string](Get-PropertyValue -Payload $LatestReceipt -Name 'chat_forward_status' -Default '') } else { '' }
    latest_receipt_chat_forward_error = if ($null -ne $LatestReceipt) { [string](Get-PropertyValue -Payload $LatestReceipt -Name 'chat_forward_error' -Default '') } else { '' }
    latest_receipt_id = $LatestReceiptId
    latest_receipt_actor = $LatestReceiptActor
    latest_receipt_source = $LatestReceiptSource
    latest_receipt_client_origin = $LatestReceiptClientOrigin
    latest_receipt_ingress_transport = $LatestReceiptIngressTransport
    latest_receipt_mcp_gateway_tool = $LatestReceiptMcpGatewayTool
    latest_receipt_mcp_server_tool = $LatestReceiptMcpServerTool
    latest_receipt_counts_as_chatgpt_mcp_proof = [bool]$LatestReceiptCountsAsMcpProof
    latest_receipt_proof_rejection_reason = $LatestReceiptProofRejectionReason
    chatgpt_mcp_proof = $McpProof
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
    [string]$VoiceChecksRemoteVoiceName,
    [bool]$RequireMcpProof,
    [bool]$RequireManualAcousticOrbProof,
    [int]$McpProofFreshnessSeconds,
    [bool]$ConnectorChecksEnabled,
    [string]$ConnectorChecksUrl,
    [int]$ConnectorChecksPort,
    [string]$ConnectorChecksCloudflaredTunnelName,
    [string]$ConnectorChecksCloudflaredHostname,
    [string]$ConnectorChecksCloudflaredTokenFile,
    [bool]$ConnectorChecksVerify,
    [int]$ConnectorChecksProbeTimeoutSeconds,
    [bool]$RequirePersistentIngress
  )

  $Bridge = Invoke-CommandPaletteBridge -ApiBaseUrl $ApiBaseUrl -ChatUiBaseUrl $ChatUiBaseUrl -LensStatusPath $LensStatusPath -TimeoutSeconds $TimeoutSeconds
  $BridgePayload = Get-PropertyValue -Payload $Bridge -Name 'payload'
  $Http = Invoke-CommandPaletteHttpProbe -Url $CommandPaletteUrl -TimeoutSeconds $TimeoutSeconds
  $VoiceMonitor = if ($VoiceChecksEnabled) {
    New-VoiceMonitorProjection -Root $Root -Provider $VoiceChecksProvider -RemoteVoiceId $VoiceChecksRemoteVoiceId -RemoteVoiceName $VoiceChecksRemoteVoiceName -McpProofFreshnessSeconds $McpProofFreshnessSeconds
  } else {
    [ordered]@{ enabled = $false }
  }
  $ConnectorMonitor = if ($ConnectorChecksEnabled) {
    New-ChatGptConnectorMonitorProjection -Root $Root -ConnectorUrl $ConnectorChecksUrl -ConnectorPort $ConnectorChecksPort -VerifyConnector $ConnectorChecksVerify -ProbeTimeoutSeconds $ConnectorChecksProbeTimeoutSeconds
  } else {
    [ordered]@{ enabled = $false }
  }
  $PersistentIngressPlanMonitor = if ($ConnectorChecksEnabled) {
    New-ChatGptPersistentIngressPlanMonitorProjection -Root $Root -ConnectorUrl $ConnectorChecksUrl -ConnectorPort $ConnectorChecksPort -CloudflaredTunnelName $ConnectorChecksCloudflaredTunnelName -CloudflaredHostname $ConnectorChecksCloudflaredHostname -CloudflaredTokenFile $ConnectorChecksCloudflaredTokenFile -VerifyConnector $ConnectorChecksVerify -ProbeTimeoutSeconds $ConnectorChecksProbeTimeoutSeconds
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
    $VoiceOverlayStatus = [string](Get-PropertyValue -Payload $VoiceMonitor -Name 'overlay_status' -Default '')
    $VoiceOverlayReady = [bool](Get-PropertyValue -Payload $VoiceMonitor -Name 'overlay_ready' -Default $false)
    $VoiceProviderReady = if ($VoiceChecksProvider -eq 'ElevenLabs') { [bool](Get-PropertyValue -Payload $VoiceMonitor -Name 'active_provider_configured' -Default $false) } else { $true }
    $VoiceIdentityOk = [bool](Get-PropertyValue -Payload $VoiceMonitor -Name 'voice_identity_ok' -Default $false)
    $GenericVoiceLabelObserved = [bool](Get-PropertyValue -Payload $VoiceMonitor -Name 'generic_voice_label_observed' -Default $false)
    $VoicePermissionDenied = [bool](Get-PropertyValue -Payload $VoiceMonitor -Name 'api_permission_denied_observed' -Default $false)
    $LatestReceiptDenied = [bool](Get-PropertyValue -Payload $VoiceMonitor -Name 'latest_receipt_denied' -Default $false)
    $DeniedRecentReceiptCount = [int](Get-PropertyValue -Payload $VoiceMonitor -Name 'denied_recent_receipt_count' -Default 0)
    $WakeListening = [bool](Get-PropertyValue -Payload $VoiceMonitor -Name 'wake_listening' -Default $false)
    $PassiveListenContract = [string](Get-PropertyValue -Payload $VoiceMonitor -Name 'passive_listen_contract' -Default '')
    $MicrophoneGateWhileSpeaking = [string](Get-PropertyValue -Payload $VoiceMonitor -Name 'microphone_gate_while_speaking' -Default '')
    $ConversationForwardingWhileSpeaking = [bool](Get-PropertyValue -Payload $VoiceMonitor -Name 'conversation_forwarding_while_speaking' -Default $true)
    $McpProof = Get-PropertyValue -Payload $VoiceMonitor -Name 'chatgpt_mcp_proof'
    $McpConnectionProofObserved = [bool](Get-PropertyValue -Payload $McpProof -Name 'mcp_connection_proof_observed' -Default $false)
    $McpConnectionProofStatus = [string](Get-PropertyValue -Payload $McpProof -Name 'mcp_connection_proof_status' -Default (Get-PropertyValue -Payload $McpProof -Name 'status' -Default 'not_checked'))
    $McpConnectionProofReceiptId = [string](Get-PropertyValue -Payload $McpProof -Name 'latest_mcp_connection_proof_receipt_id' -Default '')
    $ManualAcousticProof = Get-PropertyValue -Payload $VoiceMonitor -Name 'manual_acoustic_orb_position_proof'
    $ManualAcousticProofObserved = [bool](Get-PropertyValue -Payload $ManualAcousticProof -Name 'proof_observed' -Default $false)
    $ManualAcousticProofStatus = [string](Get-PropertyValue -Payload $ManualAcousticProof -Name 'status' -Default 'not_checked')
    $ManualAcousticProofReceiptId = [string](Get-PropertyValue -Payload $ManualAcousticProof -Name 'latest_orb_receipt_id' -Default '')
    $ManualAcousticProofBlocker = [string](Get-PropertyValue -Payload $ManualAcousticProof -Name 'proof_blocker' -Default 'no_fresh_acoustic_orb_position_receipt')
    $ManualAcousticProofFirstFailed = [string](Get-PropertyValue -Payload $ManualAcousticProof -Name 'first_failed_requirement' -Default 'none')
    $ManualAcousticProofNextStep = [string](Get-PropertyValue -Payload $ManualAcousticProof -Name 'next_operator_step' -Default '')
    $ManualAcousticProofDiagnostic = Get-PropertyValue -Payload $ManualAcousticProof -Name 'proof_diagnostic_summary'
    $ManualAcousticProofLatestVoiceStatus = [string](Get-PropertyValue -Payload $ManualAcousticProofDiagnostic -Name 'latest_voice_status' -Default '')
    $ManualAcousticProofLatestVoiceSource = [string](Get-PropertyValue -Payload $ManualAcousticProofDiagnostic -Name 'latest_voice_command_source' -Default '')
    $ManualAcousticProofLatestVoiceMicClaimed = [bool](Get-PropertyValue -Payload $ManualAcousticProofDiagnostic -Name 'latest_voice_microphone_recognition_claimed' -Default $false)
    $ManualAcousticProofLatestReceiptId = [string](Get-PropertyValue -Payload $ManualAcousticProofDiagnostic -Name 'latest_orb_receipt_id' -Default '')
    $ManualAcousticProofLatestReceiptSource = [string](Get-PropertyValue -Payload $ManualAcousticProofDiagnostic -Name 'latest_orb_receipt_command_source' -Default '')
    $ManualAcousticProofLatestReceiptApplied = [bool](Get-PropertyValue -Payload $ManualAcousticProofDiagnostic -Name 'latest_orb_receipt_applied' -Default $false)
    $ManualAcousticProofLatestReceiptMicClaimed = [bool](Get-PropertyValue -Payload $ManualAcousticProofDiagnostic -Name 'latest_orb_receipt_microphone_recognition_claimed' -Default $false)
    $ManualAcousticProofReceiptFresh = [bool](Get-PropertyValue -Payload $ManualAcousticProofDiagnostic -Name 'latest_orb_receipt_fresh' -Default $false)
    $ManualAcousticProofEvidence = if ($ManualAcousticProofObserved -and -not [string]::IsNullOrWhiteSpace($ManualAcousticProofReceiptId)) {
      $ManualAcousticProofReceiptId
    } elseif (-not [string]::IsNullOrWhiteSpace($ManualAcousticProofFirstFailed) -and $ManualAcousticProofFirstFailed -ne 'none') {
      'first_failed_requirement={0} proof_blocker={1} latest_voice_status={2} latest_voice_source={3} latest_voice_microphone={4} latest_orb_receipt_id={5} latest_orb_receipt_source={6} latest_orb_receipt_applied={7} latest_orb_receipt_microphone={8} receipt_fresh={9} next_operator_step={10}' -f $ManualAcousticProofFirstFailed, $ManualAcousticProofBlocker, $ManualAcousticProofLatestVoiceStatus, $ManualAcousticProofLatestVoiceSource, $ManualAcousticProofLatestVoiceMicClaimed, $ManualAcousticProofLatestReceiptId, $ManualAcousticProofLatestReceiptSource, $ManualAcousticProofLatestReceiptApplied, $ManualAcousticProofLatestReceiptMicClaimed, $ManualAcousticProofReceiptFresh, $ManualAcousticProofNextStep
    } elseif (-not [string]::IsNullOrWhiteSpace($ManualAcousticProofBlocker)) {
      $ManualAcousticProofBlocker
    } else {
      'no_fresh_acoustic_orb_position_receipt'
    }
    [void]$Checks.Add((New-MonitorCheck -Id 'voice_overlay_readback' -Passed $VoiceReadbackOk -Status $(if ($VoiceReadbackOk) { 'readback_ready' } else { 'readback_failed' }) -Evidence 'scripts/lens-overlay-window.ps1 -Mode Status'))
    [void]$Checks.Add((New-MonitorCheck -Id 'voice_overlay_runtime' -Passed ($VoiceReadbackOk -and $VoiceOverlayReady) -Status $(if ($VoiceReadbackOk -and $VoiceOverlayReady) { 'visible' } else { 'overlay_not_ready' }) -Evidence $(if ([string]::IsNullOrWhiteSpace($VoiceOverlayStatus)) { 'overlay_status_missing' } else { $VoiceOverlayStatus })))
    [void]$Checks.Add((New-MonitorCheck -Id 'voice_provider_readiness' -Passed $VoiceProviderReady -Status $(if ($VoiceProviderReady) { 'configured' } else { 'not_configured' }) -Evidence ([string](Get-PropertyValue -Payload $VoiceMonitor -Name 'selected_provider' -Default ''))))
    [void]$Checks.Add((New-MonitorCheck -Id 'voice_francis_identity' -Passed ($VoiceIdentityOk -and -not $GenericVoiceLabelObserved) -Status $(if ($VoiceIdentityOk -and -not $GenericVoiceLabelObserved) { 'francis_voice_identity_ready' } else { 'identity_drift' }) -Evidence ([string](Get-PropertyValue -Payload $VoiceMonitor -Name 'selected_voice' -Default ''))))
    [void]$Checks.Add((New-MonitorCheck -Id 'voice_passive_listen_contract' -Passed ($WakeListening -and $PassiveListenContract -eq 'passive_transcript_awareness_only_until_wake_phrase') -Status $(if ($WakeListening -and $PassiveListenContract -eq 'passive_transcript_awareness_only_until_wake_phrase') { 'passive_until_wake' } else { 'wake_gate_not_confirmed' }) -Evidence $PassiveListenContract))
    [void]$Checks.Add((New-MonitorCheck -Id 'voice_mic_gate_while_speaking' -Passed ($MicrophoneGateWhileSpeaking -eq 'francis_stop_only' -and -not $ConversationForwardingWhileSpeaking) -Status $(if ($MicrophoneGateWhileSpeaking -eq 'francis_stop_only' -and -not $ConversationForwardingWhileSpeaking) { 'francis_stop_only' } else { 'mic_gate_not_confirmed' }) -Evidence ("gate={0} forwarding_while_speaking={1}" -f $MicrophoneGateWhileSpeaking, $ConversationForwardingWhileSpeaking)))
    [void]$Checks.Add((New-MonitorCheck -Id 'voice_chat_bridge_denials' -Passed ((-not $VoicePermissionDenied) -and (-not $LatestReceiptDenied)) -Status $(if ((-not $VoicePermissionDenied) -and (-not $LatestReceiptDenied)) { 'latest_receipt_clean' } else { 'denial_observed' }) -Evidence ("latest_denied={0} recent_denied={1}" -f $LatestReceiptDenied, $DeniedRecentReceiptCount)))
    if ($RequireMcpProof) {
      [void]$Checks.Add((New-MonitorCheck -Id 'voice_chatgpt_mcp_tool_proof' -Passed $McpConnectionProofObserved -Status $McpConnectionProofStatus -Evidence $(if ([string]::IsNullOrWhiteSpace($McpConnectionProofReceiptId)) { 'no_fresh_mcp_connection_receipt' } else { $McpConnectionProofReceiptId })))
    }
    if ($RequireManualAcousticOrbProof) {
      [void]$Checks.Add((New-MonitorCheck -Id 'voice_manual_acoustic_orb_position_proof' -Passed $ManualAcousticProofObserved -Status $ManualAcousticProofStatus -Evidence $ManualAcousticProofEvidence))
    }
  }
  if ($ConnectorChecksEnabled) {
    $ConnectorReadbackOk = [bool](Get-PropertyValue -Payload $ConnectorMonitor -Name 'ok' -Default $false)
    $ConnectorStatus = [string](Get-PropertyValue -Payload $ConnectorMonitor -Name 'status' -Default 'status_unavailable')
    $ConnectorUsable = [bool](Get-PropertyValue -Payload $ConnectorMonitor -Name 'connector_usable_for_chatgpt' -Default $false)
    $PersistentCandidate = [bool](Get-PropertyValue -Payload $ConnectorMonitor -Name 'persistent_candidate' -Default $false)
    $PersistentStatus = [string](Get-PropertyValue -Payload $ConnectorMonitor -Name 'persistent_ingress_status' -Default 'unknown')
    $ConnectorHost = [string](Get-PropertyValue -Payload $ConnectorMonitor -Name 'connector_url_host' -Default '')
    $PlanGovernanceSafe = [bool](Get-PropertyValue -Payload $PersistentIngressPlanMonitor -Name 'governance_safe' -Default $false)
    $PlanStatus = [string](Get-PropertyValue -Payload $PersistentIngressPlanMonitor -Name 'status' -Default 'plan_unavailable')
    [void]$Checks.Add((New-MonitorCheck -Id 'chatgpt_voice_connector_readback' -Passed $ConnectorReadbackOk -Status $ConnectorStatus -Evidence $ConnectorHost))
    [void]$Checks.Add((New-MonitorCheck -Id 'chatgpt_voice_persistent_ingress_plan' -Passed $PlanGovernanceSafe -Status $PlanStatus -Evidence 'read_only_no_process_no_tunnel'))
    if ($ConnectorChecksVerify) {
      [void]$Checks.Add((New-MonitorCheck -Id 'chatgpt_voice_connector_reachability' -Passed $ConnectorUsable -Status $(if ($ConnectorUsable) { 'verified_usable' } else { 'not_usable' }) -Evidence $ConnectorHost))
    }
    if ($RequirePersistentIngress) {
      [void]$Checks.Add((New-MonitorCheck -Id 'chatgpt_voice_persistent_ingress' -Passed $PersistentCandidate -Status $PersistentStatus -Evidence $(if ([string]::IsNullOrWhiteSpace($ConnectorHost)) { 'no_connector_host' } else { $ConnectorHost })))
    }
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
    chatgpt_connector_monitor = $ConnectorMonitor
    chatgpt_persistent_ingress_plan_monitor = $PersistentIngressPlanMonitor
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
  $ProbeArgs = @{
    Root = $DataRoot
    CommandPaletteUrl = $CommandPaletteUrl
    ApiBaseUrl = $ApiBaseUrl
    ChatUiBaseUrl = $ChatUiBaseUrl
    LensStatusPath = $LensStatusPath
    TimeoutSeconds = $TimeoutSeconds
    VoiceChecksEnabled = [bool]$EnableVoiceChecks
    VoiceChecksProvider = $VoiceProvider
    VoiceChecksRemoteVoiceId = $ElevenLabsVoiceId
    VoiceChecksRemoteVoiceName = $ElevenLabsVoiceName
    RequireMcpProof = [bool]$RequireChatGptMcpProof
    RequireManualAcousticOrbProof = [bool]$RequireManualAcousticOrbProof
    McpProofFreshnessSeconds = $ChatGptMcpProofFreshnessSeconds
    ConnectorChecksEnabled = [bool]$EnableChatGptConnectorChecks
    ConnectorChecksUrl = $ChatGptConnectorUrl
    ConnectorChecksPort = $ChatGptConnectorPort
    ConnectorChecksCloudflaredTunnelName = $CloudflaredTunnelName
    ConnectorChecksCloudflaredHostname = $CloudflaredHostname
    ConnectorChecksCloudflaredTokenFile = $CloudflaredTokenFile
    ConnectorChecksVerify = [bool]$VerifyChatGptConnector
    ConnectorChecksProbeTimeoutSeconds = $ChatGptConnectorProbeTimeoutSeconds
    RequirePersistentIngress = [bool]$RequirePersistentChatGptIngress
  }
  $Payload = New-CommandPaletteMonitorProbe @ProbeArgs
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
    $Arguments += @('-ChatGptMcpProofFreshnessSeconds', ([string]$ChatGptMcpProofFreshnessSeconds))
    if ($RequireChatGptMcpProof) {
      $Arguments += '-RequireChatGptMcpProof'
    }
    if ($RequireManualAcousticOrbProof) {
      $Arguments += '-RequireManualAcousticOrbProof'
    }
  }
  if ($EnableChatGptConnectorChecks) {
    $Arguments += @('-EnableChatGptConnectorChecks', '-ChatGptConnectorProbeTimeoutSeconds', ([string]$ChatGptConnectorProbeTimeoutSeconds))
    if (-not [string]::IsNullOrWhiteSpace($ChatGptConnectorUrl)) {
      $Arguments += @('-ChatGptConnectorUrl', $ChatGptConnectorUrl)
    }
    $Arguments += @('-ChatGptConnectorPort', ([string]$ChatGptConnectorPort))
    if (-not [string]::IsNullOrWhiteSpace($CloudflaredTunnelName)) {
      $Arguments += @('-CloudflaredTunnelName', $CloudflaredTunnelName)
    }
    if (-not [string]::IsNullOrWhiteSpace($CloudflaredHostname)) {
      $Arguments += @('-CloudflaredHostname', $CloudflaredHostname)
    }
    if (-not [string]::IsNullOrWhiteSpace($CloudflaredTokenFile)) {
      $Arguments += @('-CloudflaredTokenFile', $CloudflaredTokenFile)
    }
    if ($VerifyChatGptConnector) {
      $Arguments += '-VerifyChatGptConnector'
    }
    if ($RequirePersistentChatGptIngress) {
      $Arguments += '-RequirePersistentChatGptIngress'
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
    $ProbeArgs = @{
      Root = $DataRoot
      CommandPaletteUrl = $CommandPaletteUrl
      ApiBaseUrl = $ApiBaseUrl
      ChatUiBaseUrl = $ChatUiBaseUrl
      LensStatusPath = $LensStatusPath
      TimeoutSeconds = $TimeoutSeconds
      VoiceChecksEnabled = [bool]$EnableVoiceChecks
      VoiceChecksProvider = $VoiceProvider
      VoiceChecksRemoteVoiceId = $ElevenLabsVoiceId
      VoiceChecksRemoteVoiceName = $ElevenLabsVoiceName
      RequireMcpProof = [bool]$RequireChatGptMcpProof
      RequireManualAcousticOrbProof = [bool]$RequireManualAcousticOrbProof
      McpProofFreshnessSeconds = $ChatGptMcpProofFreshnessSeconds
      ConnectorChecksEnabled = [bool]$EnableChatGptConnectorChecks
      ConnectorChecksUrl = $ChatGptConnectorUrl
      ConnectorChecksPort = $ChatGptConnectorPort
      ConnectorChecksCloudflaredTunnelName = $CloudflaredTunnelName
      ConnectorChecksCloudflaredHostname = $CloudflaredHostname
      ConnectorChecksCloudflaredTokenFile = $CloudflaredTokenFile
      ConnectorChecksVerify = [bool]$VerifyChatGptConnector
      ConnectorChecksProbeTimeoutSeconds = $ChatGptConnectorProbeTimeoutSeconds
      RequirePersistentIngress = [bool]$RequirePersistentChatGptIngress
    }
    $Payload = New-CommandPaletteMonitorProbe @ProbeArgs
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
