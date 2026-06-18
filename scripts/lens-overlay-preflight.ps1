[CmdletBinding()]
param(
  [ValidateSet('Status', 'Open', 'Focus')]
  [string]$Mode = 'Status',

  [string]$DataDir = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

function Add-Check {
  param(
    [System.Collections.ArrayList]$Target,
    [string]$Id,
    [string]$Status,
    [string]$Reason,
    [string]$Evidence = ''
  )

  [void]$Target.Add([ordered]@{
      id = $Id
      status = $Status
      reason = $Reason
      evidence = $Evidence
    })
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
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property) {
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

function Get-StringProperty {
  param(
    [object]$Payload,
    [string]$Name,
    [string]$Default = ''
  )

  if ($null -eq $Payload) {
    return $Default
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

function Get-StringListProperty {
  param(
    [object]$Payload,
    [string]$Name
  )

  $Items = [System.Collections.ArrayList]::new()
  if ($null -eq $Payload) {
    return @($Items.ToArray())
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) {
    return @($Items.ToArray())
  }

  if ($Property.Value -is [System.Array]) {
    foreach ($Item in $Property.Value) {
      $Value = [string]$Item
      if (-not [string]::IsNullOrWhiteSpace($Value)) {
        [void]$Items.Add($Value)
      }
    }
    return @($Items.ToArray())
  }

  $SingleValue = [string]$Property.Value
  if (-not [string]::IsNullOrWhiteSpace($SingleValue)) {
    [void]$Items.Add($SingleValue)
  }
  return @($Items.ToArray())
}

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

function Get-HostProcessReadback {
  param([string]$Root)

  $RuntimeRoot = Join-Path $Root 'runtime\lens-host'
  $PidPath = Join-Path $RuntimeRoot 'lens-host.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  $Status = Read-JsonFile -Path $StatusPath
  $StatusKind = Get-StringProperty -Payload $Status -Name 'kind' -Default ''
  $StatusValue = Get-StringProperty -Payload $Status -Name 'status' -Default ''
  $StatusPid = Get-IntegerProperty -Payload $Status -Name 'pid' -Default 0
  $RuntimeStateExists = Test-Path -LiteralPath $StatusPath -PathType Leaf
  $PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf
  $HostPid = 0
  if ($PidPresent) {
    try {
      $HostPid = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
    } catch {
      $HostPid = 0
    }
  }

  $StatusClaimsRunningHost = (
    $StatusKind -eq 'lens.host.runtime_state' -and
    @('foreground_running', 'resident_running') -contains $StatusValue -and
    $StatusPid -gt 0 -and
    $StatusPid -eq $HostPid
  )
  $ProcessAlive = $false
  if ($StatusClaimsRunningHost -and $HostPid -gt 0) {
    try {
      $ProcessAlive = $null -ne (Get-Process -Id $HostPid -ErrorAction Stop)
    } catch {
      $ProcessAlive = $false
    }
  }

  return [ordered]@{
    process_alive = $ProcessAlive
    pid = $HostPid
    pid_present = $PidPresent
    status_path = $StatusPath
    pid_path = $PidPath
    runtime_state_exists = $RuntimeStateExists
    runtime_status = $StatusValue
    runtime_status_kind = $StatusKind
    runtime_status_pid = $StatusPid
    runtime_status_pid_matches_pid_file = ($StatusPid -gt 0 -and $StatusPid -eq $HostPid)
    requirement_state = if ($ProcessAlive) { 'running' } elseif ($RuntimeStateExists -or $PidPresent) { 'stale_or_unverified' } else { 'missing' }
    blocker = if ($ProcessAlive) { '' } else { 'resident_host_process_missing' }
  }
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

function Get-OverlayRuntimeReadback {
  param(
    [string]$Root,
    [string]$ExpectedOverlayName,
    [string]$ExpectedOverlayScope
  )

  $RuntimeRoot = Join-Path $Root 'runtime\lens-overlay'
  $PidPath = Join-Path $RuntimeRoot 'lens-overlay.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  $Status = Read-JsonFile -Path $StatusPath
  $StatusKind = Get-StringProperty -Payload $Status -Name 'kind' -Default ''
  $StatusValue = Get-StringProperty -Payload $Status -Name 'status' -Default ''
  $StatusPid = Get-IntegerProperty -Payload $Status -Name 'pid' -Default 0
  $RuntimeStateExists = Test-Path -LiteralPath $StatusPath -PathType Leaf
  $PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf
  $OverlayPid = 0
  if ($PidPresent) {
    try {
      $OverlayPid = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
    } catch {
      $OverlayPid = 0
    }
  }

  $StatusClaimsRunningOverlay = (
    $StatusKind -eq 'lens.overlay.runtime_state' -and
    $StatusValue -eq 'overlay_running' -and
    $StatusPid -gt 0 -and
    $StatusPid -eq $OverlayPid -and
    (Get-StringProperty -Payload $Status -Name 'overlay_name' -Default '') -eq $ExpectedOverlayName -and
    (Get-StringProperty -Payload $Status -Name 'overlay_scope' -Default '') -eq $ExpectedOverlayScope
  )
  $ProcessAlive = $false
  if ($StatusClaimsRunningOverlay -and $OverlayPid -gt 0) {
    try {
      $ProcessAlive = $null -ne (Get-Process -Id $OverlayPid -ErrorAction Stop)
    } catch {
      $ProcessAlive = $false
    }
  }

  $OverlayWindowVisible = $ProcessAlive -and (Get-BoolProperty -Payload $Status -Name 'overlay_window_visible' -Default $false)
  $AlwaysOnTop = $OverlayWindowVisible -and (Get-BoolProperty -Payload $Status -Name 'always_on_top' -Default $false)
  $Ready = $OverlayWindowVisible -and $AlwaysOnTop
  $StatusOverlayVoice = if ($null -ne $Status -and $null -ne $Status.PSObject.Properties['overlay_voice']) { $Status.PSObject.Properties['overlay_voice'].Value } else { $null }
  $StatusVoiceInputReadiness = if ($null -ne $Status -and $null -ne $Status.PSObject.Properties['voice_input_readiness']) { $Status.PSObject.Properties['voice_input_readiness'].Value } else { $null }
  $VoiceInputReadiness = if ($null -ne $StatusVoiceInputReadiness) { $StatusVoiceInputReadiness } else { Get-OverlayVoiceInputReadiness -Voice $StatusOverlayVoice }

  return [ordered]@{
    ready = $Ready
    process_alive = $ProcessAlive
    overlay_window_visible = $OverlayWindowVisible
    always_on_top = $AlwaysOnTop
    pid = $OverlayPid
    pid_present = $PidPresent
    status_path = $StatusPath
    pid_path = $PidPath
    runtime_state_exists = $RuntimeStateExists
    runtime_status = $StatusValue
    runtime_status_kind = $StatusKind
    runtime_status_pid = $StatusPid
    runtime_status_pid_matches_pid_file = ($StatusPid -gt 0 -and $StatusPid -eq $OverlayPid)
    overlay_name = Get-StringProperty -Payload $Status -Name 'overlay_name' -Default ''
    expected_overlay_name = $ExpectedOverlayName
    overlay_scope = Get-StringProperty -Payload $Status -Name 'overlay_scope' -Default ''
    expected_overlay_scope = $ExpectedOverlayScope
    overlay_voice = $StatusOverlayVoice
    voice_input_readiness = $VoiceInputReadiness
    voice_input_ready = [bool]$VoiceInputReadiness.ready
    voice_input_status = $VoiceInputReadiness.status
    voice_input_blocker = $VoiceInputReadiness.blocker
    next_voice_input_step = $VoiceInputReadiness.next_operator_step
    requirement_state = if ($Ready) { 'visible' } elseif ($ProcessAlive) { 'process_running_no_visible_overlay_claim' } elseif ($RuntimeStateExists -or $PidPresent) { 'stale_or_unverified' } else { 'missing' }
    blocker = if ($Ready) { '' } elseif ($ProcessAlive) { 'overlay_window_not_observed' } else { 'overlay_window_runtime_missing' }
  }
}

$ModeName = $Mode.ToLowerInvariant()
$ConfigPath = Join-Path $RepoRoot 'config\runtime\lens\overlay.json'
$ConfigExists = Test-Path -LiteralPath $ConfigPath -PathType Leaf
$Config = $null
$ConfigError = ''
if ($ConfigExists) {
  try {
    $Config = Get-Content -LiteralPath $ConfigPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $ConfigError = [string]$_.Exception.Message
  }
}

$OverlayName = Get-StringProperty -Payload $Config -Name 'overlay_name' -Default 'Francis Lens Overlay'
$OverlayScope = Get-StringProperty -Payload $Config -Name 'overlay_scope' -Default 'user_session'
$StatusRoute = Get-StringProperty -Payload $Config -Name 'status_route' -Default '/lens/status'
$HostRoute = Get-StringProperty -Payload $Config -Name 'host_route' -Default '/lens/host'
$HostPreflight = Get-StringProperty -Payload $Config -Name 'host_preflight' -Default 'scripts/lens-host-preflight.ps1'
$HostStatusRunner = Get-StringProperty -Payload $Config -Name 'host_status_runner' -Default 'scripts/lens-host.ps1'
$OverlayRunner = Get-StringProperty -Payload $Config -Name 'overlay_runner' -Default 'scripts/lens-overlay-window.ps1'
$SummonPreflight = Get-StringProperty -Payload $Config -Name 'summon_preflight' -Default 'scripts/lens-summon-preflight.ps1'
$TrayPreflight = Get-StringProperty -Payload $Config -Name 'tray_preflight' -Default 'scripts/lens-tray-preflight.ps1'
$BlockedReason = Get-StringProperty -Payload $Config -Name 'blocked_reason' -Default 'lens_overlay_window_not_implemented'
$Enabled = Get-BoolProperty -Payload $Config -Name 'enabled' -Default $false
$WindowEnabled = Get-BoolProperty -Payload $Config -Name 'window_enabled' -Default $false
$AlwaysOnTop = Get-BoolProperty -Payload $Config -Name 'always_on_top' -Default $false
$DockSupported = Get-BoolProperty -Payload $Config -Name 'dock_supported' -Default $false
$FocusSupported = Get-BoolProperty -Payload $Config -Name 'focus_supported' -Default $false
$ClickThroughSupported = Get-BoolProperty -Payload $Config -Name 'click_through_supported' -Default $false
$CaptureSupported = Get-BoolProperty -Payload $Config -Name 'capture_supported' -Default $false
$OverlayControlAuthority = Get-BoolProperty -Payload $Config -Name 'overlay_control_authority' -Default $false
$WindowManagementAuthority = Get-BoolProperty -Payload $Config -Name 'window_management_authority' -Default $false
$LocalProcessLaunchAuthority = Get-BoolProperty -Payload $Config -Name 'local_process_launch_authority' -Default $false
$CaptureAuthority = Get-BoolProperty -Payload $Config -Name 'capture_authority' -Default $false
$SummonAuthority = Get-BoolProperty -Payload $Config -Name 'summon_authority' -Default $false
$TrayRegistrationAuthority = Get-BoolProperty -Payload $Config -Name 'tray_registration_authority' -Default $false
$RequiredBeforeEnable = Get-StringListProperty -Payload $Config -Name 'required_before_enable'

$HostPreflightExists = Test-Path -LiteralPath (Join-Path $RepoRoot $HostPreflight) -PathType Leaf
$HostStatusRunnerExists = Test-Path -LiteralPath (Join-Path $RepoRoot $HostStatusRunner) -PathType Leaf
$OverlayRunnerExists = Test-Path -LiteralPath (Join-Path $RepoRoot $OverlayRunner) -PathType Leaf
$SummonPreflightExists = Test-Path -LiteralPath (Join-Path $RepoRoot $SummonPreflight) -PathType Leaf
$TrayPreflightExists = Test-Path -LiteralPath (Join-Path $RepoRoot $TrayPreflight) -PathType Leaf
$DataRoot = Get-DataRoot -Override $DataDir
$HostProcessReadback = Get-HostProcessReadback -Root $DataRoot
$OverlayRuntimeReadback = Get-OverlayRuntimeReadback -Root $DataRoot -ExpectedOverlayName $OverlayName -ExpectedOverlayScope $OverlayScope
$OverlayRuntimeReady = [bool]$OverlayRuntimeReadback.ready
$RuntimeStateExists = [bool]$HostProcessReadback.runtime_state_exists
$PidPresent = [bool]$HostProcessReadback.pid_present
$ResidentHostProcessAlive = [bool]$HostProcessReadback.process_alive

$Checks = [System.Collections.ArrayList]::new()
Add-Check -Target $Checks -Id 'runtime_root' -Status 'ready' -Reason 'runtime root accepted' -Evidence $RepoRoot
Add-Check -Target $Checks -Id 'overlay_config' -Status $(if ($ConfigExists -and -not $ConfigError) { 'present_disabled' } elseif ($ConfigExists) { 'invalid' } else { 'missing' }) -Reason $(if ($ConfigError) { $ConfigError } elseif ($ConfigExists) { 'disabled overlay config is present' } else { 'overlay config is missing' }) -Evidence 'config/runtime/lens/overlay.json'
Add-Check -Target $Checks -Id 'window_enabled' -Status $(if ($WindowEnabled) { 'enabled' } else { 'disabled' }) -Reason 'overlay window remains disabled until resident host exists' -Evidence $OverlayScope
Add-Check -Target $Checks -Id 'always_on_top' -Status $(if ($AlwaysOnTop) { 'enabled' } else { 'disabled' }) -Reason 'always-on-top behavior remains disabled' -Evidence 'always_on_top'
Add-Check -Target $Checks -Id 'focus_support' -Status $(if ($FocusSupported) { 'declared' } else { 'disabled' }) -Reason 'overlay focus support is not implemented' -Evidence 'focus_supported'
Add-Check -Target $Checks -Id 'capture_support' -Status $(if ($CaptureSupported) { 'declared' } else { 'disabled' }) -Reason 'overlay capture support is not implemented' -Evidence 'capture_supported'
Add-Check -Target $Checks -Id 'host_preflight' -Status $(if ($HostPreflightExists) { 'present' } else { 'missing' }) -Reason $(if ($HostPreflightExists) { 'host lifecycle preflight is present' } else { 'host lifecycle preflight is missing' }) -Evidence $HostPreflight
Add-Check -Target $Checks -Id 'host_status_runner' -Status $(if ($HostStatusRunnerExists) { 'present' } else { 'missing' }) -Reason $(if ($HostStatusRunnerExists) { 'host status runner is present' } else { 'host status runner is missing' }) -Evidence $HostStatusRunner
Add-Check -Target $Checks -Id 'overlay_runner' -Status $(if ($OverlayRunnerExists) { 'present' } else { 'missing' }) -Reason $(if ($OverlayRunnerExists) { 'overlay window runtime runner is present' } else { 'overlay window runtime runner is missing' }) -Evidence $OverlayRunner
Add-Check -Target $Checks -Id 'summon_preflight' -Status $(if ($SummonPreflightExists) { 'present' } else { 'missing' }) -Reason $(if ($SummonPreflightExists) { 'summon preflight is present' } else { 'summon preflight is missing' }) -Evidence $SummonPreflight
Add-Check -Target $Checks -Id 'tray_preflight' -Status $(if ($TrayPreflightExists) { 'present' } else { 'missing' }) -Reason $(if ($TrayPreflightExists) { 'tray preflight is present' } else { 'tray preflight is missing' }) -Evidence $TrayPreflight
Add-Check -Target $Checks -Id 'runtime_state' -Status $(if ($ResidentHostProcessAlive) { 'process_observed' } elseif ($RuntimeStateExists -or $PidPresent) { 'stale_or_unverified' } else { 'missing' }) -Reason $(if ($ResidentHostProcessAlive) { 'resident host process is live and matches runtime state' } else { 'resident host runtime state is not live' }) -Evidence 'data/runtime/lens-host'
Add-Check -Target $Checks -Id 'overlay_runtime' -Status $OverlayRuntimeReadback.requirement_state -Reason $(if ($OverlayRuntimeReady) { 'overlay window runtime is live and topmost' } else { 'overlay window runtime is not live' }) -Evidence 'data/runtime/lens-overlay'
Add-Check -Target $Checks -Id 'voice_input' -Status $(if ([bool]$OverlayRuntimeReadback.voice_input_ready) { 'ready' } elseif (-not [string]::IsNullOrWhiteSpace([string]$OverlayRuntimeReadback.voice_input_blocker)) { 'blocked' } else { [string]$OverlayRuntimeReadback.voice_input_status }) -Reason $OverlayRuntimeReadback.voice_input_readiness.message -Evidence 'data/runtime/lens-overlay/status.json'
Add-Check -Target $Checks -Id 'overlay_control_authority' -Status $(if ($OverlayControlAuthority) { 'allowed' } else { 'blocked' }) -Reason 'overlay control authority is not granted' -Evidence 'overlay_control_authority'
Add-Check -Target $Checks -Id 'window_management_authority' -Status $(if ($WindowManagementAuthority) { 'allowed' } else { 'blocked' }) -Reason 'window management authority is not granted' -Evidence 'window_management_authority'

$Blockers = [System.Collections.ArrayList]::new()
if ($BlockedReason -and -not $OverlayRuntimeReady) { [void]$Blockers.Add($BlockedReason) }
if (-not $ConfigExists) { [void]$Blockers.Add('lens_overlay_config_missing') }
if ($ConfigError) { [void]$Blockers.Add('lens_overlay_config_invalid') }
if (-not $WindowEnabled) { [void]$Blockers.Add('overlay_window_disabled') }
if (-not $AlwaysOnTop) { [void]$Blockers.Add('always_on_top_disabled') }
if (-not $DockSupported) { [void]$Blockers.Add('overlay_dock_not_supported') }
if (-not $FocusSupported) { [void]$Blockers.Add('overlay_focus_not_supported') }
if (-not $ClickThroughSupported) { [void]$Blockers.Add('overlay_click_through_not_supported') }
if (-not $HostPreflightExists) { [void]$Blockers.Add('lens_host_lifecycle_preflight_missing') }
if (-not $HostStatusRunnerExists) { [void]$Blockers.Add('lens_host_status_runner_missing') }
if (-not $OverlayRunnerExists) { [void]$Blockers.Add('lens_overlay_runner_missing') }
if (-not $SummonPreflightExists) { [void]$Blockers.Add('lens_summon_preflight_missing') }
if (-not $TrayPreflightExists) { [void]$Blockers.Add('lens_tray_preflight_missing') }
if ($WindowEnabled -and -not $OverlayRuntimeReady) { [void]$Blockers.Add('overlay_window_runtime_missing') }
if ($OverlayRuntimeReady -and -not [string]::IsNullOrWhiteSpace([string]$OverlayRuntimeReadback.voice_input_blocker)) { [void]$Blockers.Add([string]$OverlayRuntimeReadback.voice_input_blocker) }
if (-not $ResidentHostProcessAlive) { [void]$Blockers.Add('resident_host_process_missing') }
if (-not $OverlayControlAuthority) { [void]$Blockers.Add('overlay_control_authority_not_granted') }
if (-not $WindowManagementAuthority) { [void]$Blockers.Add('window_management_authority_not_granted') }
if (-not $LocalProcessLaunchAuthority) { [void]$Blockers.Add('local_process_launch_authority_not_granted') }
if (-not $CaptureAuthority) { [void]$Blockers.Add('capture_authority_not_granted') }
if (-not $SummonAuthority) { [void]$Blockers.Add('summon_authority_not_granted') }
if (-not $TrayRegistrationAuthority) { [void]$Blockers.Add('tray_registration_authority_not_granted') }

$Ready = $Blockers.Count -eq 0
$Payload = [ordered]@{
  ok = $true
  kind = 'lens.overlay.preflight'
  status = if ($Ready) { 'ready' } else { 'blocked' }
  mode = $ModeName
  ready = $Ready
  repo_root = $RepoRoot
  data_root = $DataRoot
  overlay_name = $OverlayName
  config_path = 'config/runtime/lens/overlay.json'
  required_before_enable = @($RequiredBeforeEnable)
  overlay_scope = $OverlayScope
  status_route = $StatusRoute
  host_route = $HostRoute
  checks = $Checks
  blockers = $Blockers
  overlay = [ordered]@{
    enabled = $Enabled
    window_enabled = $WindowEnabled
    always_on_top = $AlwaysOnTop
    dock_supported = $DockSupported
    focus_supported = $FocusSupported
    click_through_supported = $ClickThroughSupported
    capture_supported = $CaptureSupported
    host_preflight = $HostPreflight
    host_status_runner = $HostStatusRunner
    overlay_runner = $OverlayRunner
    summon_preflight = $SummonPreflight
    tray_preflight = $TrayPreflight
  }
  overlay_runtime = $OverlayRuntimeReadback
  resident_host_process = $HostProcessReadback
  governance = [ordered]@{
    read_only_contract = $true
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    window_management_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = $false
    tray_registration_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Lens overlay preflight is read-only; overlay window and focus actions remain blocked.'
}

if ($Mode -eq 'Status') {
  $Payload | ConvertTo-Json -Depth 8
  exit 0
}

$Payload.ok = $false
$Payload.status = 'refused'
$Payload.error = 'lens_overlay_action_not_authorized'
$Payload.message = 'Lens overlay actions are not authorized by this preflight; use Status for read-only inspection.'
$Payload | ConvertTo-Json -Depth 8
exit 2
