[CmdletBinding()]
param(
  [ValidateSet('Status', 'Configure', 'Clear', 'ListVoices')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [ValidateSet('All', 'ProcessOnly')]
  [string]$EnvironmentScope = 'All',

  [System.Security.SecureString]$ApiKeySecret,

  [string]$VoiceId = '',

  [ValidateRange(1, 100)]
  [int]$MaxVoices = 20,

  [string]$Search = '',

  [switch]$ConfirmConfigure,

  [switch]$ConfirmClear
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

function Get-EnvironmentTargets {
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

function Get-ScopedEnvironmentValue {
  param(
    [string]$Name,
    [string]$Scope
  )

  foreach ($Target in (Get-EnvironmentTargets -Scope $Scope)) {
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
    [string]$Scope
  )

  $ScopeNames = @('Process', 'User', 'Machine')
  if ($Scope -eq 'ProcessOnly') {
    $ScopeNames = @('Process')
  }
  foreach ($ScopeName in $ScopeNames) {
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

function Get-ElevenLabsApiKeySource {
  param([string]$Scope)

  $Scoped = Get-ScopedEnvironmentSource -Name 'FRANCIS_ELEVENLABS_API_KEY' -Scope $Scope
  if (-not [string]::IsNullOrWhiteSpace($Scoped)) {
    return $Scoped
  }
  return Get-ScopedEnvironmentSource -Name 'ELEVENLABS_API_KEY' -Scope $Scope
}

function Get-ElevenLabsApiKey {
  param([string]$Scope)

  $Scoped = Get-ScopedEnvironmentValue -Name 'FRANCIS_ELEVENLABS_API_KEY' -Scope $Scope
  if (-not [string]::IsNullOrWhiteSpace($Scoped)) {
    return $Scoped
  }
  return Get-ScopedEnvironmentValue -Name 'ELEVENLABS_API_KEY' -Scope $Scope
}

function Get-ElevenLabsVoiceIdSource {
  param(
    [string]$Scope,
    [string]$RequestedVoiceId = ''
  )

  if (-not [string]::IsNullOrWhiteSpace($RequestedVoiceId)) {
    return 'script_parameter:VoiceId'
  }
  $Scoped = Get-ScopedEnvironmentSource -Name 'FRANCIS_ELEVENLABS_VOICE_ID' -Scope $Scope
  if (-not [string]::IsNullOrWhiteSpace($Scoped)) {
    return $Scoped
  }
  return Get-ScopedEnvironmentSource -Name 'ELEVENLABS_VOICE_ID' -Scope $Scope
}

function Get-ObjectPropertyValue {
  param(
    [object]$Object,
    [string]$Name
  )

  if ($null -eq $Object) {
    return $null
  }
  $Property = $Object.PSObject.Properties[$Name]
  if ($null -eq $Property) {
    return $null
  }
  return $Property.Value
}

function ConvertTo-BoundedText {
  param(
    [object]$Value,
    [int]$MaxLength = 160
  )

  if ($null -eq $Value) {
    return ''
  }
  $Text = ([string]$Value).Trim()
  if ($Text.Length -le $MaxLength) {
    return $Text
  }
  return $Text.Substring(0, $MaxLength)
}

function ConvertTo-VoiceLabelSummary {
  param([object]$Labels)

  $Summary = [ordered]@{}
  if ($null -eq $Labels) {
    return $Summary
  }
  $Count = 0
  foreach ($Property in $Labels.PSObject.Properties) {
    if ($Count -ge 8) {
      break
    }
    $Summary[$Property.Name] = ConvertTo-BoundedText -Value $Property.Value -MaxLength 80
    $Count += 1
  }
  return $Summary
}

function ConvertTo-VoiceCatalogEntry {
  param([object]$Voice)

  $VoiceIdValue = Get-ObjectPropertyValue -Object $Voice -Name 'voice_id'
  $NameValue = Get-ObjectPropertyValue -Object $Voice -Name 'name'
  $CategoryValue = Get-ObjectPropertyValue -Object $Voice -Name 'category'
  $DescriptionValue = Get-ObjectPropertyValue -Object $Voice -Name 'description'
  $PreviewUrlValue = Get-ObjectPropertyValue -Object $Voice -Name 'preview_url'
  $LabelsValue = Get-ObjectPropertyValue -Object $Voice -Name 'labels'

  return [ordered]@{
    voice_id = ConvertTo-BoundedText -Value $VoiceIdValue -MaxLength 96
    name = ConvertTo-BoundedText -Value $NameValue -MaxLength 120
    category = ConvertTo-BoundedText -Value $CategoryValue -MaxLength 80
    description = ConvertTo-BoundedText -Value $DescriptionValue -MaxLength 220
    labels = ConvertTo-VoiceLabelSummary -Labels $LabelsValue
    preview_url_present = (-not [string]::IsNullOrWhiteSpace([string]$PreviewUrlValue))
  }
}

function New-ElevenLabsVoicesUri {
  param(
    [int]$PageSize,
    [string]$SearchText
  )

  $Parameters = [ordered]@{
    page_size = [string]$PageSize
    include_total_count = 'true'
    sort = 'name'
    sort_direction = 'asc'
  }
  if (-not [string]::IsNullOrWhiteSpace($SearchText)) {
    $Parameters['search'] = $SearchText.Trim()
  }

  $Pairs = @()
  foreach ($Key in $Parameters.Keys) {
    $Pairs += ('{0}={1}' -f ([System.Uri]::EscapeDataString([string]$Key)), ([System.Uri]::EscapeDataString([string]$Parameters[$Key])))
  }
  return 'https://api.elevenlabs.io/v2/voices?{0}' -f ($Pairs -join '&')
}

function Invoke-ElevenLabsVoiceCatalogList {
  param(
    [string]$Root,
    [int]$PageSize,
    [string]$SearchText,
    [System.Security.SecureString]$ApiKeyOverrideSecret
  )

  $ApiKeySource = Get-ElevenLabsApiKeySource -Scope $EnvironmentScope
  $ApiKey = ''
  if ($null -ne $ApiKeyOverrideSecret -and $ApiKeyOverrideSecret.Length -gt 0) {
    $ApiKey = Convert-SecretToPlainText -Secret $ApiKeyOverrideSecret
    if (-not [string]::IsNullOrWhiteSpace($ApiKey)) {
      $ApiKeySource = 'script_parameter:ApiKeySecret'
    }
  } else {
    $ApiKey = Get-ElevenLabsApiKey -Scope $EnvironmentScope
  }
  $SearchProvided = -not [string]::IsNullOrWhiteSpace($SearchText)
  if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    $Payload = New-SetupStatusPayload -Root $Root -ModeName 'listvoices' -Status 'refused' -Ok $false -Error 'elevenlabs_api_key_required' -Message 'ListVoices refused; pass -ApiKeySecret or set FRANCIS_ELEVENLABS_API_KEY/ELEVENLABS_API_KEY before querying the ElevenLabs voice catalog.'
    $Payload['voice_catalog'] = [ordered]@{
      endpoint = 'https://api.elevenlabs.io/v2/voices'
      remote_request_attempted = $false
      api_key_source = ''
      transient_api_key = $false
      stores_api_key = $false
      requested_page_size = $PageSize
      search_provided = $SearchProvided
      search_value_redacted = $true
      result_count = 0
      total_count = $null
      has_more = $false
      voices = @()
    }
    return $Payload
  }

  $Uri = New-ElevenLabsVoicesUri -PageSize $PageSize -SearchText $SearchText
  $StartedAt = [DateTimeOffset]::UtcNow
  try {
    $Headers = @{
      'xi-api-key' = $ApiKey
      'Accept' = 'application/json'
    }
    $Response = Invoke-RestMethod -Uri $Uri -Method Get -Headers $Headers -TimeoutSec 30
    $VoiceEntries = @()
    $VoiceObjects = Get-ObjectPropertyValue -Object $Response -Name 'voices'
    if ($null -ne $VoiceObjects) {
      foreach ($Voice in $VoiceObjects) {
        $VoiceEntries += ConvertTo-VoiceCatalogEntry -Voice $Voice
      }
    }
    $ElapsedMs = [int]([DateTimeOffset]::UtcNow - $StartedAt).TotalMilliseconds
    $Payload = New-SetupStatusPayload -Root $Root -ModeName 'listvoices' -Status 'voices_listed' -Ok $true -Message 'ElevenLabs voice catalog listed without logging credential values or speech text.'
    $Payload['voice_catalog'] = [ordered]@{
      endpoint = 'https://api.elevenlabs.io/v2/voices'
      remote_request_attempted = $true
      api_key_source = $ApiKeySource
      transient_api_key = ($ApiKeySource -eq 'script_parameter:ApiKeySecret')
      stores_api_key = $false
      requested_page_size = $PageSize
      search_provided = $SearchProvided
      search_value_redacted = $true
      result_count = $VoiceEntries.Count
      total_count = Get-ObjectPropertyValue -Object $Response -Name 'total_count'
      has_more = [bool](Get-ObjectPropertyValue -Object $Response -Name 'has_more')
      next_page_token_present = (-not [string]::IsNullOrWhiteSpace([string](Get-ObjectPropertyValue -Object $Response -Name 'next_page_token')))
      latency_ms = $ElapsedMs
      voices = [object[]]$VoiceEntries
    }
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
    $Payload = New-SetupStatusPayload -Root $Root -ModeName 'listvoices' -Status 'failed' -Ok $false -Error 'elevenlabs_voice_catalog_request_failed' -Message 'ElevenLabs voice catalog request failed; credential values and search text were not logged.'
    $Payload['voice_catalog'] = [ordered]@{
      endpoint = 'https://api.elevenlabs.io/v2/voices'
      remote_request_attempted = $true
      api_key_source = $ApiKeySource
      transient_api_key = ($ApiKeySource -eq 'script_parameter:ApiKeySecret')
      stores_api_key = $false
      requested_page_size = $PageSize
      search_provided = $SearchProvided
      search_value_redacted = $true
      status_code = $StatusCode
      result_count = 0
      total_count = $null
      has_more = $false
      voices = @()
    }
    return $Payload
  } finally {
    $ApiKey = ''
  }
}

function Convert-SecretToPlainText {
  param([System.Security.SecureString]$Secret)

  if ($null -eq $Secret -or $Secret.Length -le 0) {
    return ''
  }
  $Bstr = [IntPtr]::Zero
  try {
    $Bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secret)
    return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Bstr)
  } finally {
    if ($Bstr -ne [IntPtr]::Zero) {
      [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Bstr)
    }
  }
}

function New-SetupStatusPayload {
  param(
    [string]$Root,
    [string]$ModeName,
    [string]$Status,
    [bool]$Ok,
    [string]$Error = '',
    [string]$Message = '',
    [string]$RequestedVoiceId = ''
  )

  $ApiKeySource = Get-ElevenLabsApiKeySource -Scope $EnvironmentScope
  $VoiceIdSource = Get-ElevenLabsVoiceIdSource -Scope $EnvironmentScope -RequestedVoiceId $RequestedVoiceId
  $ApiKeyPresent = -not [string]::IsNullOrWhiteSpace($ApiKeySource)
  $VoiceIdPresent = -not [string]::IsNullOrWhiteSpace($VoiceIdSource)
  $Missing = @()
  if (-not $ApiKeyPresent) {
    $Missing += 'api_key'
  }
  if (-not $VoiceIdPresent) {
    $Missing += 'voice_id'
  }
  $ExplicitConfirmationRequired = $false
  $MutationTarget = ''
  if ($ModeName -eq 'configure' -or $ModeName -eq 'clear') {
    $ExplicitConfirmationRequired = $true
    $MutationTarget = 'user_environment_variables'
  }
  $ReadOnly = ($ModeName -eq 'status' -or $ModeName -eq 'listvoices')
  $RemoteRequest = ($ModeName -eq 'listvoices')

  return [ordered]@{
    ok = $Ok
    kind = 'lens.overlay.elevenlabs_voice_setup'
    status = $Status
    mode = $ModeName
    data_root = $Root
    ready = ($ApiKeyPresent -and $VoiceIdPresent)
    elevenlabs = [ordered]@{
      configured = ($ApiKeyPresent -and $VoiceIdPresent)
      api_key_present = $ApiKeyPresent
      api_key_source = $ApiKeySource
      voice_id_present = $VoiceIdPresent
      voice_id_source = $VoiceIdSource
      missing_configuration = [string[]]$Missing
      credential_values_redacted = $true
      stores_secret_in_repo = $false
      writes_user_environment = ($ModeName -eq 'configure')
      clears_user_environment = ($ModeName -eq 'clear')
    }
    commands = [ordered]@{
      status = '.\scripts\lens-elevenlabs-voice-setup.ps1 -Mode Status'
      list_voices = '$secret = Read-Host "ElevenLabs API key" -AsSecureString; .\scripts\lens-elevenlabs-voice-setup.ps1 -Mode ListVoices -ApiKeySecret $secret -Search "soft female calm" -MaxVoices 20'
      configure = '$secret = Read-Host "ElevenLabs API key" -AsSecureString; .\scripts\lens-elevenlabs-voice-setup.ps1 -Mode Configure -ApiKeySecret $secret -VoiceId <voice_id> -ConfirmConfigure'
      restart_overlay = '.\scripts\lens-overlay-window.ps1 -Mode Stop; .\scripts\lens-overlay-window.ps1 -Mode Start -EnableWakeListen -VoiceProvider ElevenLabs'
      smoke = '.\scripts\lens-overlay-window.ps1 -Mode Speak -VoiceProvider ElevenLabs -VoiceText "Francis voice check."'
    }
    governance = [ordered]@{
      explicit_confirmation_required = $ExplicitConfirmationRequired
      read_only = $ReadOnly
      remote_request = $RemoteRequest
      sends_speech_text_to_remote_provider = $false
      sends_search_to_remote_provider = ($RemoteRequest -and -not [string]::IsNullOrWhiteSpace($Search))
      search_value_redacted = $true
      writes_repo_secret = $false
      logs_secret_value = $false
      logs_text_payload = $false
      mutation_target = $MutationTarget
    }
    error = $Error
    message = $Message
    updated_at = [DateTimeOffset]::UtcNow.ToString('o')
  }
}

function Write-SetupReceipt {
  param(
    [string]$Root,
    [object]$Payload
  )

  $RuntimeRoot = Join-Path $Root 'runtime\lens-overlay'
  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
  $ReceiptPath = Join-Path $RuntimeRoot 'elevenlabs-voice-setup.json'
  $TempPath = Join-Path $RuntimeRoot ("elevenlabs-voice-setup.{0}.tmp" -f ([Guid]::NewGuid().ToString('N')))
  try {
    $Payload['receipt_path'] = 'data/runtime/lens-overlay/elevenlabs-voice-setup.json'
    $Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $TempPath -Encoding UTF8
    Move-Item -LiteralPath $TempPath -Destination $ReceiptPath -Force
  } finally {
    Remove-Item -LiteralPath $TempPath -Force -ErrorAction SilentlyContinue
  }
}

$DataRoot = Get-DataRoot -Override $DataDir
$ModeName = $Mode.ToLowerInvariant()

if ($Mode -eq 'Status') {
  $Payload = New-SetupStatusPayload -Root $DataRoot -ModeName $ModeName -Status 'ready' -Ok $true -Message 'ElevenLabs voice setup status read without exposing credential values.'
  $Payload | ConvertTo-Json -Depth 8
  exit 0
}

if ($Mode -eq 'ListVoices') {
  $Payload = Invoke-ElevenLabsVoiceCatalogList -Root $DataRoot -PageSize $MaxVoices -SearchText $Search -ApiKeyOverrideSecret $ApiKeySecret
  $Payload | ConvertTo-Json -Depth 10
  if ($Payload['ok']) {
    exit 0
  }
  if ($Payload['error'] -eq 'elevenlabs_api_key_required') {
    exit 2
  }
  exit 1
}

if ($Mode -eq 'Configure') {
  if (-not $ConfirmConfigure) {
    $Payload = New-SetupStatusPayload -Root $DataRoot -ModeName $ModeName -Status 'refused' -Ok $false -Error 'confirm_configure_required' -Message 'Configure refused; pass -ConfirmConfigure to write User-scope ElevenLabs environment variables.' -RequestedVoiceId $VoiceId
    Write-SetupReceipt -Root $DataRoot -Payload $Payload
    $Payload | ConvertTo-Json -Depth 8
    exit 2
  }

  if ($null -eq $ApiKeySecret -or $ApiKeySecret.Length -le 0) {
    $ApiKeySecret = Read-Host 'ElevenLabs API key' -AsSecureString
  }
  $ApiKeyPlainText = Convert-SecretToPlainText -Secret $ApiKeySecret
  try {
    $BoundedVoiceId = ([string]$VoiceId).Trim()
    $Missing = @()
    if ([string]::IsNullOrWhiteSpace($ApiKeyPlainText)) {
      $Missing += 'api_key'
    }
    if ([string]::IsNullOrWhiteSpace($BoundedVoiceId)) {
      $Missing += 'voice_id'
    }
    if ($Missing.Count -gt 0) {
      $Payload = New-SetupStatusPayload -Root $DataRoot -ModeName $ModeName -Status 'refused' -Ok $false -Error 'elevenlabs_configuration_required' -Message 'Configure refused; API key and voice ID are both required.' -RequestedVoiceId $VoiceId
      $Payload['elevenlabs']['missing_configuration'] = [string[]]$Missing
      Write-SetupReceipt -Root $DataRoot -Payload $Payload
      $Payload | ConvertTo-Json -Depth 8
      exit 2
    }

    [Environment]::SetEnvironmentVariable('FRANCIS_ELEVENLABS_API_KEY', $ApiKeyPlainText, 'User')
    [Environment]::SetEnvironmentVariable('FRANCIS_ELEVENLABS_VOICE_ID', $BoundedVoiceId, 'User')
    [Environment]::SetEnvironmentVariable('FRANCIS_ELEVENLABS_API_KEY', $ApiKeyPlainText, 'Process')
    [Environment]::SetEnvironmentVariable('FRANCIS_ELEVENLABS_VOICE_ID', $BoundedVoiceId, 'Process')
    $Payload = New-SetupStatusPayload -Root $DataRoot -ModeName $ModeName -Status 'configured' -Ok $true -Message 'ElevenLabs User-scope environment variables were configured; credential values were not logged.' -RequestedVoiceId $VoiceId
    Write-SetupReceipt -Root $DataRoot -Payload $Payload
    $Payload | ConvertTo-Json -Depth 8
    exit 0
  } finally {
    $ApiKeyPlainText = ''
  }
}

if ($Mode -eq 'Clear') {
  if (-not $ConfirmClear) {
    $Payload = New-SetupStatusPayload -Root $DataRoot -ModeName $ModeName -Status 'refused' -Ok $false -Error 'confirm_clear_required' -Message 'Clear refused; pass -ConfirmClear to remove User-scope ElevenLabs environment variables.'
    Write-SetupReceipt -Root $DataRoot -Payload $Payload
    $Payload | ConvertTo-Json -Depth 8
    exit 2
  }

  [Environment]::SetEnvironmentVariable('FRANCIS_ELEVENLABS_API_KEY', $null, 'User')
  [Environment]::SetEnvironmentVariable('FRANCIS_ELEVENLABS_VOICE_ID', $null, 'User')
  [Environment]::SetEnvironmentVariable('FRANCIS_ELEVENLABS_API_KEY', $null, 'Process')
  [Environment]::SetEnvironmentVariable('FRANCIS_ELEVENLABS_VOICE_ID', $null, 'Process')
  $Payload = New-SetupStatusPayload -Root $DataRoot -ModeName $ModeName -Status 'cleared' -Ok $true -Message 'ElevenLabs User-scope environment variables were cleared.'
  Write-SetupReceipt -Root $DataRoot -Payload $Payload
  $Payload | ConvertTo-Json -Depth 8
  exit 0
}
