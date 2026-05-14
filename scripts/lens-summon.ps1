[CmdletBinding()]
param(
  [ValidateSet('Status', 'LocalOpen')]
  [string]$Mode = 'Status',

  [string]$ApiBaseUrl = 'http://127.0.0.1:8000',

  [string]$ChatUiBaseUrl = 'http://127.0.0.1:5173',

  [string]$ConfigOverridePath = '',

  [string]$StatusPath = '',

  [ValidateRange(1, 30)]
  [int]$TimeoutSeconds = 5,

  [switch]$NoLaunch
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

function Get-PropertyValue {
  param(
    [AllowNull()]
    [object]$Payload,
    [string]$Name,
    [AllowNull()]
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

function Get-StringProperty {
  param(
    [AllowNull()]
    [object]$Payload,
    [string]$Name,
    [string]$Default = ''
  )

  $Value = Get-PropertyValue -Payload $Payload -Name $Name -Default $Default
  if ($null -eq $Value) {
    return $Default
  }
  $Text = [string]$Value
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return $Default
  }
  return $Text
}

function Get-StringPropertyPreserveEmpty {
  param(
    [AllowNull()]
    [object]$Payload,
    [string]$Name,
    [string]$Default = ''
  )

  if ($null -eq $Payload) {
    return $Default
  }
  if ($Payload -is [System.Collections.IDictionary]) {
    if ($Payload.Contains($Name) -and $null -ne $Payload[$Name]) {
      return [string]$Payload[$Name]
    }
    return $Default
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) {
    return $Default
  }
  return [string]$Property.Value
}

function Get-BoolProperty {
  param(
    [AllowNull()]
    [object]$Payload,
    [string]$Name,
    [bool]$Default = $false
  )

  $Value = Get-PropertyValue -Payload $Payload -Name $Name -Default $Default
  if ($Value -is [bool]) {
    return [bool]$Value
  }
  if ($null -eq $Value) {
    return $Default
  }
  $Text = [string]$Value
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return $Default
  }
  return $Text.ToLowerInvariant() -eq 'true'
}

function New-Check {
  param(
    [string]$Id,
    [string]$Status,
    [bool]$Passed,
    [string]$Evidence,
    [string]$Reason
  )

  return [ordered]@{
    id = $Id
    status = $Status
    passed = $Passed
    evidence = $Evidence
    reason = $Reason
  }
}

function Invoke-CommandPaletteLocalOpen {
  param(
    [string]$PowerShellPath,
    [string]$ScriptPath,
    [bool]$DryRun
  )

  if ([string]::IsNullOrWhiteSpace($PowerShellPath) -or -not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
      error = 'command_palette_script_unavailable'
    }
  }

  $Arguments = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $ScriptPath,
    '-Mode',
    'LocalOpen',
    '-ApiBaseUrl',
    $ApiBaseUrl,
    '-ChatUiBaseUrl',
    $ChatUiBaseUrl,
    '-TimeoutSeconds',
    ([string]$TimeoutSeconds)
  )
  if (-not [string]::IsNullOrWhiteSpace($StatusPath)) {
    $Arguments += @('-StatusPath', $StatusPath)
  }
  if ($DryRun) {
    $Arguments += '-NoLaunch'
  }

  $Output = & $PowerShellPath @Arguments 2>&1
  $ExitCode = $LASTEXITCODE
  $Text = ($Output | ForEach-Object { [string]$_ }) -join "`n"
  $Payload = $null
  try {
    $Payload = $Text | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $Payload = $null
  }

  return [ordered]@{
    exit_code = $ExitCode
    payload = $Payload
    output = $Text
    error = if ($null -eq $Payload) { 'command_palette_json_unavailable' } else { '' }
  }
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$DefaultConfigPath = Join-Path $RepoRoot 'config\runtime\lens\summon.json'
$ConfigPath = if (-not [string]::IsNullOrWhiteSpace($ConfigOverridePath)) {
  [System.IO.Path]::GetFullPath($ConfigOverridePath)
} else {
  $DefaultConfigPath
}
$ConfigEvidencePath = if (-not [string]::IsNullOrWhiteSpace($ConfigOverridePath)) {
  $ConfigPath
} else {
  'config/runtime/lens/summon.json'
}
$Config = $null
$ConfigError = ''
try {
  $Config = Get-Content -LiteralPath $ConfigPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
} catch {
  $ConfigError = [string]$_.Exception.Message
}

$CommandPaletteScript = Join-Path $PSScriptRoot 'lens-command-palette.ps1'
$CommandPaletteScriptExists = Test-Path -LiteralPath $CommandPaletteScript -PathType Leaf
$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command powershell -ErrorAction SilentlyContinue
}
$PowerShellPath = if ($null -ne $PowerShell) { [string]$PowerShell.Source } else { '' }

$ModeName = $Mode.ToLowerInvariant()
$DryRun = $Mode -eq 'Status' -or [bool]$NoLaunch
$PaletteResult = Invoke-CommandPaletteLocalOpen -PowerShellPath $PowerShellPath -ScriptPath $CommandPaletteScript -DryRun $DryRun
$PalettePayload = Get-PropertyValue -Payload $PaletteResult -Name 'payload'
$PaletteExitCode = [int](Get-PropertyValue -Payload $PaletteResult -Name 'exit_code' -Default -1)
$PaletteLocalOpenAvailable = [bool](Get-PropertyValue -Payload $PalettePayload -Name 'local_open_available' -Default $false)
$PaletteReadbackReady = [bool](Get-PropertyValue -Payload $PalettePayload -Name 'readback_ready' -Default $false)
$PaletteTargetUrl = Get-StringProperty -Payload $PalettePayload -Name 'local_open_target_url' -Default ''
$PaletteOpened = [bool](Get-PropertyValue -Payload $PalettePayload -Name 'opened' -Default $false)
$LocalBindingReady = $CommandPaletteScriptExists -and $PaletteExitCode -eq 0 -and $PaletteLocalOpenAvailable -and $PaletteReadbackReady

$BlockedReason = Get-StringPropertyPreserveEmpty -Payload $Config -Name 'blocked_reason' -Default 'lens_summon_binding_disabled_pending_authority'
$GlobalHotkey = Get-StringProperty -Payload $Config -Name 'global_hotkey' -Default ''
$BindingScope = Get-StringProperty -Payload $Config -Name 'binding_scope' -Default 'global'
$SummonRunner = Get-StringProperty -Payload $Config -Name 'summon_runner' -Default 'scripts/lens-summon.ps1'
$BindingEnabled = Get-BoolProperty -Payload $Config -Name 'binding_enabled' -Default $false
$RegisterHotkey = Get-BoolProperty -Payload $Config -Name 'register_hotkey' -Default $false
$StartupRegister = Get-BoolProperty -Payload $Config -Name 'startup_register' -Default $false
$SummonAuthority = Get-BoolProperty -Payload $Config -Name 'summon_authority' -Default $false
$HotkeyRegistrationAuthority = Get-BoolProperty -Payload $Config -Name 'hotkey_registration_authority' -Default $false

$Blockers = [System.Collections.ArrayList]::new()
if (-not [string]::IsNullOrWhiteSpace($ConfigError)) { [void]$Blockers.Add('lens_summon_config_invalid') }
if (-not $CommandPaletteScriptExists) { [void]$Blockers.Add('command_palette_local_open_missing') }
if (-not $LocalBindingReady) { [void]$Blockers.Add('chat_ui_command_palette_local_open_missing') }
if ($BlockedReason) { [void]$Blockers.Add($BlockedReason) }
if (-not $GlobalHotkey) { [void]$Blockers.Add('global_hotkey_not_declared') }
if (-not $BindingEnabled) { [void]$Blockers.Add('global_hotkey_binding_disabled') }
if (-not $RegisterHotkey) { [void]$Blockers.Add('global_hotkey_registration_disabled') }
if (-not $HotkeyRegistrationAuthority) { [void]$Blockers.Add('hotkey_registration_authority_not_granted') }
if (-not $SummonAuthority) { [void]$Blockers.Add('summon_authority_not_granted') }

$Checks = @(
  (New-Check -Id 'summon_config' -Status $(if ($ConfigError) { 'invalid' } else { 'present_disabled' }) -Passed ([string]::IsNullOrWhiteSpace($ConfigError)) -Evidence 'config/runtime/lens/summon.json' -Reason 'Summon configuration must exist before a local binding can be reported.'),
  (New-Check -Id 'command_palette_local_open' -Status $(if ($LocalBindingReady) { 'local_open_ready' } else { 'blocked' }) -Passed $LocalBindingReady -Evidence 'scripts/lens-command-palette.ps1 -Mode LocalOpen' -Reason 'The local summon target delegates to the existing command-palette URL entrypoint.'),
  (New-Check -Id 'global_hotkey_binding' -Status $(if ($BindingEnabled -and $RegisterHotkey) { 'enabled' } else { 'disabled' }) -Passed ($BindingEnabled -and $RegisterHotkey) -Evidence $GlobalHotkey -Reason 'OS-wide summon remains blocked until a global hotkey binding is explicitly enabled.'),
  (New-Check -Id 'summon_authority' -Status $(if ($SummonAuthority) { 'allowed' } else { 'blocked' }) -Passed $SummonAuthority -Evidence 'summon_authority' -Reason 'The local launcher does not grant OS-level summon authority.')
)

$Opened = $Mode -eq 'LocalOpen' -and $PaletteOpened
$Payload = [ordered]@{
  ok = $LocalBindingReady
  kind = 'lens.summon.local_launcher'
  status = if ($Mode -eq 'LocalOpen' -and $PaletteOpened) { 'opened' } elseif ($Mode -eq 'LocalOpen' -and $LocalBindingReady) { 'local_open_ready' } elseif ($LocalBindingReady) { 'local_binding_ready' } else { 'blocked' }
  mode = $ModeName
  repo_root = $RepoRoot
  config_path = $ConfigEvidencePath
  summon_runner = $SummonRunner
  local_binding_ready = $LocalBindingReady
  summon_binding_target_ready = $LocalBindingReady
  local_summon_available = $LocalBindingReady
  os_level_summon = $false
  summon_anywhere = $false
  global_hotkey = $GlobalHotkey
  binding_scope = $BindingScope
  binding_enabled = $BindingEnabled
  register_hotkey = $RegisterHotkey
  startup_register = $StartupRegister
  local_open_target_url = $PaletteTargetUrl
  would_open_palette = $Mode -eq 'LocalOpen'
  opened = $Opened
  no_launch = [bool]$NoLaunch
  checks = @($Checks)
  blockers = [string[]]@($Blockers.ToArray())
  palette_launcher = [ordered]@{
    script = 'scripts/lens-command-palette.ps1'
    status = Get-StringProperty -Payload $PalettePayload -Name 'status' -Default ''
    local_open_available = $PaletteLocalOpenAvailable
    readback_ready = $PaletteReadbackReady
    exit_code = $PaletteExitCode
    error = Get-StringProperty -Payload $PalettePayload -Name 'error' -Default (
      Get-StringProperty -Payload $PaletteResult -Name 'error' -Default ''
    )
  }
  next_smallest_truthful_gap = 'global_hotkey_binding'
  governance = [ordered]@{
    read_only_contract = $Mode -eq 'Status'
    opens_palette = $Mode -eq 'LocalOpen'
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    summon_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    local_process_launch_authority = $Opened
    mutation_authority_granted = $false
  }
  message = if ($LocalBindingReady) {
    'Local Lens summon can target the existing command-palette URL entrypoint; OS-wide summon and global hotkey registration remain disabled.'
  } else {
    'Local Lens summon target is not ready; command-palette local-open readback is required.'
  }
}

$Payload | ConvertTo-Json -Depth 10
if ($LocalBindingReady) {
  exit 0
}
exit 1
