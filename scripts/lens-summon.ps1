[CmdletBinding()]
param(
  [ValidateSet('Status', 'LocalOpen')]
  [string]$Mode = 'Status',

  [string]$ApiBaseUrl = 'http://127.0.0.1:8000',

  [string]$ChatUiBaseUrl = 'http://127.0.0.1:5173',

  [string]$ConfigOverridePath = '',

  [string]$DataDir = '',

  [ValidateSet('local_open', 'global_hotkey')]
  [string]$Trigger = 'local_open',

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

function Read-SummonJsonFile {
  param([string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return $null
  }
  try {
    return Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
  } catch {
    return $null
  }
}

function Write-SummonJsonFile {
  param(
    [string]$Path,
    [object]$Payload
  )

  $Parent = Split-Path -Parent $Path
  New-Item -ItemType Directory -Force -Path $Parent | Out-Null
  $TempPath = '{0}.tmp-{1}' -f $Path, ([Guid]::NewGuid().ToString('N'))
  try {
    Set-Content -LiteralPath $TempPath -Value ($Payload | ConvertTo-Json -Depth 12) -Encoding UTF8
    Move-Item -LiteralPath $TempPath -Destination $Path -Force
  } finally {
    Remove-Item -LiteralPath $TempPath -Force -ErrorAction SilentlyContinue
  }
}

function Test-SummonProcessAlive {
  param([int]$ProcessId)

  if ($ProcessId -le 0) {
    return $false
  }
  try {
    $Process = Get-Process -Id $ProcessId -ErrorAction Stop
    return -not [bool]$Process.HasExited
  } catch {
    return $false
  }
}

function Get-NativeOrbSummonReadback {
  param(
    [string]$Root,
    [string]$ExpectedGlobalHotkey
  )

  $OverlayRoot = Join-Path $Root 'runtime\lens-overlay'
  $OverlayStatusPath = Join-Path $OverlayRoot 'status.json'
  $OverlayPidPath = Join-Path $OverlayRoot 'lens-overlay.pid'
  $OverlayStatus = Read-SummonJsonFile -Path $OverlayStatusPath
  $OverlayPid = 0
  if (Test-Path -LiteralPath $OverlayPidPath -PathType Leaf) {
    try { $OverlayPid = [int]((Get-Content -LiteralPath $OverlayPidPath -Raw).Trim()) } catch { $OverlayPid = 0 }
  }
  $OverlayControls = Get-PropertyValue -Payload $OverlayStatus -Name 'orb_controls'
  $OverlayReady = (
    $OverlayPid -gt 0 -and
    (Test-SummonProcessAlive -ProcessId $OverlayPid) -and
    (Get-StringProperty -Payload $OverlayStatus -Name 'kind' -Default '') -eq 'lens.overlay.runtime_state' -and
    (Get-StringProperty -Payload $OverlayStatus -Name 'status' -Default '') -eq 'overlay_running' -and
    [int](Get-PropertyValue -Payload $OverlayStatus -Name 'pid' -Default 0) -eq $OverlayPid -and
    (Get-BoolProperty -Payload $OverlayStatus -Name 'overlay_window_visible' -Default $false) -and
    (Get-BoolProperty -Payload $OverlayStatus -Name 'always_on_top' -Default $false) -and
    (Get-BoolProperty -Payload $OverlayControls -Name 'right_click_panel_supported' -Default $false)
  )

  $HotkeyRoot = Join-Path $Root 'runtime\lens-hotkey'
  $HotkeyStatusPath = Join-Path $HotkeyRoot 'status.json'
  $HotkeyPidPath = Join-Path $HotkeyRoot 'lens-hotkey.pid'
  $HotkeyStatus = Read-SummonJsonFile -Path $HotkeyStatusPath
  $HotkeyPid = 0
  if (Test-Path -LiteralPath $HotkeyPidPath -PathType Leaf) {
    try { $HotkeyPid = [int]((Get-Content -LiteralPath $HotkeyPidPath -Raw).Trim()) } catch { $HotkeyPid = 0 }
  }
  $HotkeyReady = (
    $HotkeyPid -gt 0 -and
    (Test-SummonProcessAlive -ProcessId $HotkeyPid) -and
    (Get-StringProperty -Payload $HotkeyStatus -Name 'kind' -Default '') -eq 'lens.hotkey.runtime_state' -and
    (Get-StringProperty -Payload $HotkeyStatus -Name 'status' -Default '') -eq 'hotkey_bound' -and
    [int](Get-PropertyValue -Payload $HotkeyStatus -Name 'pid' -Default 0) -eq $HotkeyPid -and
    (Get-BoolProperty -Payload $HotkeyStatus -Name 'hotkey_bound' -Default $false) -and
    (Get-BoolProperty -Payload $HotkeyStatus -Name 'launch_on_hotkey' -Default $false) -and
    (Get-StringProperty -Payload $HotkeyStatus -Name 'global_hotkey' -Default '') -eq $ExpectedGlobalHotkey
  )

  return [ordered]@{
    ready = $OverlayReady
    native_surface_ready = $OverlayReady
    overlay_pid = $OverlayPid
    overlay_process_alive = Test-SummonProcessAlive -ProcessId $OverlayPid
    overlay_window_visible = Get-BoolProperty -Payload $OverlayStatus -Name 'overlay_window_visible' -Default $false
    always_on_top = Get-BoolProperty -Payload $OverlayStatus -Name 'always_on_top' -Default $false
    right_click_panel_supported = Get-BoolProperty -Payload $OverlayControls -Name 'right_click_panel_supported' -Default $false
    panel_visible = Get-BoolProperty -Payload $OverlayControls -Name 'panel_visible' -Default $false
    latest_request_id = Get-StringProperty -Payload $OverlayControls -Name 'latest_request_id' -Default ''
    latest_status = Get-StringProperty -Payload $OverlayControls -Name 'latest_status' -Default ''
    last_receipt_path = Get-StringProperty -Payload $OverlayControls -Name 'last_receipt_path' -Default ''
    hotkey_runtime_ready = $HotkeyReady
    hotkey_pid = $HotkeyPid
    launch_on_hotkey = Get-BoolProperty -Payload $HotkeyStatus -Name 'launch_on_hotkey' -Default $false
    press_count = [int](Get-PropertyValue -Payload $HotkeyStatus -Name 'press_count' -Default 0)
    summon_anywhere_ready = $OverlayReady -and $HotkeyReady
    overlay_status_path = 'data/runtime/lens-overlay/status.json'
    hotkey_status_path = 'data/runtime/lens-hotkey/status.json'
  }
}

function Invoke-NativeOrbPanelOpen {
  param(
    [string]$Root,
    [object]$Readback,
    [string]$GlobalHotkey,
    [string]$Trigger,
    [int]$WaitSeconds
  )

  if (-not (Get-BoolProperty -Payload $Readback -Name 'ready' -Default $false)) {
    return [ordered]@{ ok = $false; status = 'native_surface_unavailable'; opened = $false; request_consumed = $false; request_id = ''; request_path = ''; receipt_path = ''; error = 'canonical_overlay_runtime_not_ready' }
  }
  $RequestPath = Join-Path (Join-Path $Root 'runtime\lens-overlay') 'summon-request.json'
  if (Test-Path -LiteralPath $RequestPath -PathType Leaf) {
    return [ordered]@{ ok = $false; status = 'summon_request_already_pending'; opened = $false; request_consumed = $false; request_id = ''; request_path = $RequestPath; receipt_path = ''; error = 'summon_request_already_pending' }
  }

  $RequestId = 'summon-{0}-{1}' -f $Trigger, ([Guid]::NewGuid().ToString('N'))
  $Request = [ordered]@{
    kind = 'lens.overlay.summon_request'
    schema_version = 'lens.overlay.summon_request.v1'
    request_id = $RequestId
    action = 'open_orb_panel'
    authority_scope = 'runtime_overlay_panel_only'
    source = if ($Trigger -eq 'global_hotkey') { 'lens.hotkey.global' } else { 'lens.summon.local_open' }
    trigger = $Trigger
    global_hotkey = $GlobalHotkey
    created_at = [DateTimeOffset]::UtcNow.ToString('o')
    governance = [ordered]@{
      overlay_control_authority = $true
      local_process_launch_authority = $false
      controls_user_os_cursor = $false
      user_mouse_taken = $false
      physical_input_performed = $false
      memory_write = $false
      resident_claim_authority = $false
    }
  }
  Write-SummonJsonFile -Path $RequestPath -Payload $Request

  $Deadline = [DateTimeOffset]::UtcNow.AddSeconds([Math]::Max(1, $WaitSeconds))
  do {
    Start-Sleep -Milliseconds 100
    $Current = Get-NativeOrbSummonReadback -Root $Root -ExpectedGlobalHotkey $GlobalHotkey
    $Consumed = -not (Test-Path -LiteralPath $RequestPath -PathType Leaf)
    $Correlated = (Get-StringProperty -Payload $Current -Name 'latest_request_id' -Default '') -eq $RequestId
    $PanelVisible = Get-BoolProperty -Payload $Current -Name 'panel_visible' -Default $false
    if ($Consumed -and $Correlated -and $PanelVisible) {
      return [ordered]@{
        ok = $true
        status = 'native_surface_opened'
        opened = $true
        request_consumed = $true
        request_id = $RequestId
        request_path = $RequestPath
        receipt_path = Get-StringProperty -Payload $Current -Name 'last_receipt_path' -Default ''
        error = ''
      }
    }
  } while ([DateTimeOffset]::UtcNow -lt $Deadline)

  Remove-Item -LiteralPath $RequestPath -Force -ErrorAction SilentlyContinue
  return [ordered]@{
    ok = $false
    status = 'native_surface_open_failed'
    opened = $false
    request_consumed = $false
    request_id = $RequestId
    request_path = $RequestPath
    receipt_path = ''
    error = 'canonical_overlay_summon_request_not_acknowledged'
  }
}

function Write-SummonReceipt {
  param(
    [string]$Root,
    [object]$Payload
  )

  $ReceiptId = 'lsum_{0}_{1}' -f ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()), ([Guid]::NewGuid().ToString('N').Substring(0, 12))
  $ReceiptPath = Join-Path (Join-Path $Root 'lens\summon\receipts') ('{0}.json' -f $ReceiptId)
  $NativeRequest = Get-PropertyValue -Payload $Payload -Name 'native_request'
  $Receipt = [ordered]@{
    kind = 'lens.summon.execution_receipt'
    receipt_id = $ReceiptId
    status = Get-StringProperty -Payload $Payload -Name 'status' -Default 'unknown'
    trigger = Get-StringProperty -Payload $Payload -Name 'trigger' -Default 'local_open'
    global_hotkey = Get-StringProperty -Payload $Payload -Name 'global_hotkey' -Default ''
    request_id = Get-StringProperty -Payload $NativeRequest -Name 'request_id' -Default ''
    request_consumed = Get-BoolProperty -Payload $Payload -Name 'native_request_consumed' -Default $false
    native_surface = Get-StringProperty -Payload $Payload -Name 'native_surface' -Default ''
    opened = Get-BoolProperty -Payload $Payload -Name 'opened' -Default $false
    orb_control_receipt_path = Get-StringProperty -Payload $NativeRequest -Name 'receipt_path' -Default ''
    controls_user_os_cursor = $false
    user_mouse_taken = $false
    physical_input_performed = $false
    browser_opened = Get-BoolProperty -Payload $Payload -Name 'browser_opened' -Default $false
    updated_at = [DateTimeOffset]::UtcNow.ToString('o')
  }
  Write-SummonJsonFile -Path $ReceiptPath -Payload $Receipt
  return [ordered]@{ receipt_id = $ReceiptId; receipt_path = $ReceiptPath }
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot
$DataRoot = if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  [System.IO.Path]::GetFullPath($DataDir)
} elseif (-not [string]::IsNullOrWhiteSpace([string]$env:FRANCIS_DATA_DIR)) {
  [System.IO.Path]::GetFullPath([string]$env:FRANCIS_DATA_DIR)
} else {
  Join-Path $RepoRoot 'data'
}

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
$BlockedReason = Get-StringPropertyPreserveEmpty -Payload $Config -Name 'blocked_reason' -Default 'lens_summon_binding_disabled_pending_authority'
$GlobalHotkey = Get-StringProperty -Payload $Config -Name 'global_hotkey' -Default ''
$BindingScope = Get-StringProperty -Payload $Config -Name 'binding_scope' -Default 'global'
$SummonRunner = Get-StringProperty -Payload $Config -Name 'summon_runner' -Default 'scripts/lens-summon.ps1'
$BindingEnabled = Get-BoolProperty -Payload $Config -Name 'binding_enabled' -Default $false
$RegisterHotkey = Get-BoolProperty -Payload $Config -Name 'register_hotkey' -Default $false
$StartupRegister = Get-BoolProperty -Payload $Config -Name 'startup_register' -Default $false
$SummonAuthority = Get-BoolProperty -Payload $Config -Name 'summon_authority' -Default $false
$HotkeyRegistrationAuthority = Get-BoolProperty -Payload $Config -Name 'hotkey_registration_authority' -Default $false
$OverlayControlAuthority = Get-BoolProperty -Payload $Config -Name 'overlay_control_authority' -Default $false
$LocalProcessLaunchAuthority = Get-BoolProperty -Payload $Config -Name 'local_process_launch_authority' -Default $false
$SummonExecutionAuthorized = $SummonAuthority -and [string]::IsNullOrWhiteSpace($BlockedReason)
if ($Trigger -eq 'global_hotkey') {
  $SummonExecutionAuthorized = (
    $SummonExecutionAuthorized -and
    $BindingEnabled -and
    $RegisterHotkey -and
    $HotkeyRegistrationAuthority
  )
}
$NativeExecutionAuthorized = $SummonExecutionAuthorized -and $OverlayControlAuthority
$FallbackExecutionAuthorized = $SummonExecutionAuthorized -and $LocalProcessLaunchAuthority
$NativeReadback = Get-NativeOrbSummonReadback -Root $DataRoot -ExpectedGlobalHotkey $GlobalHotkey
$NativeSurfaceReady = Get-BoolProperty -Payload $NativeReadback -Name 'ready' -Default $false

$PaletteResult = if ($NativeSurfaceReady) {
  [ordered]@{
    exit_code = 0
    payload = [ordered]@{
      status = 'not_invoked_native_primary'
      local_open_available = $CommandPaletteScriptExists
      readback_ready = $CommandPaletteScriptExists
      local_open_target_url = "$ChatUiBaseUrl/?francis_lens=command_palette"
      opened = $false
      error = ''
    }
    output = ''
    error = ''
  }
} else {
  Invoke-CommandPaletteLocalOpen -PowerShellPath $PowerShellPath -ScriptPath $CommandPaletteScript -DryRun ($DryRun -or -not $FallbackExecutionAuthorized)
}
$PalettePayload = Get-PropertyValue -Payload $PaletteResult -Name 'payload'
$PaletteExitCode = [int](Get-PropertyValue -Payload $PaletteResult -Name 'exit_code' -Default -1)
$PaletteLocalOpenAvailable = [bool](Get-PropertyValue -Payload $PalettePayload -Name 'local_open_available' -Default $false)
$PaletteReadbackReady = [bool](Get-PropertyValue -Payload $PalettePayload -Name 'readback_ready' -Default $false)
$PaletteTargetUrl = Get-StringProperty -Payload $PalettePayload -Name 'local_open_target_url' -Default ''
$PaletteOpened = [bool](Get-PropertyValue -Payload $PalettePayload -Name 'opened' -Default $false) -and -not $NativeSurfaceReady
$FallbackBindingReady = $CommandPaletteScriptExists -and $PaletteExitCode -eq 0 -and $PaletteLocalOpenAvailable -and $PaletteReadbackReady
$LocalBindingReady = $NativeSurfaceReady -or $FallbackBindingReady

$NativeOpenResult = [ordered]@{
  ok = $false
  status = if ($NativeSurfaceReady -and -not $NativeExecutionAuthorized) { 'native_execution_not_authorized' } elseif ($NativeSurfaceReady) { 'native_surface_ready' } else { 'native_surface_unavailable' }
  opened = $false
  request_consumed = $false
  request_id = ''
  request_path = ''
  receipt_path = ''
  error = if ($NativeSurfaceReady -and -not $NativeExecutionAuthorized) { 'summon_execution_authority_not_ready' } else { '' }
}
if ($Mode -eq 'LocalOpen' -and -not [bool]$NoLaunch -and $NativeSurfaceReady -and $NativeExecutionAuthorized) {
  $NativeOpenResult = Invoke-NativeOrbPanelOpen -Root $DataRoot -Readback $NativeReadback -GlobalHotkey $GlobalHotkey -Trigger $Trigger -WaitSeconds $TimeoutSeconds
}
$NativeOpened = Get-BoolProperty -Payload $NativeOpenResult -Name 'opened' -Default $false
$Opened = $NativeOpened -or $PaletteOpened
$SummonAnywhereReady = (
  (Get-BoolProperty -Payload $NativeReadback -Name 'summon_anywhere_ready' -Default $false) -and
  $SummonAuthority -and
  $OverlayControlAuthority -and
  [string]::IsNullOrWhiteSpace($BlockedReason) -and
  $BindingEnabled -and
  $RegisterHotkey -and
  $HotkeyRegistrationAuthority
)

$Blockers = [System.Collections.ArrayList]::new()
if (-not [string]::IsNullOrWhiteSpace($ConfigError)) { [void]$Blockers.Add('lens_summon_config_invalid') }
if (-not $NativeSurfaceReady -and -not $CommandPaletteScriptExists) { [void]$Blockers.Add('command_palette_local_open_missing') }
if (-not $LocalBindingReady) { [void]$Blockers.Add('canonical_or_fallback_summon_target_missing') }
if ($BlockedReason) { [void]$Blockers.Add($BlockedReason) }
if (-not $GlobalHotkey) { [void]$Blockers.Add('global_hotkey_not_declared') }
if (-not $BindingEnabled) { [void]$Blockers.Add('global_hotkey_binding_disabled') }
if (-not $RegisterHotkey) { [void]$Blockers.Add('global_hotkey_registration_disabled') }
if (-not $HotkeyRegistrationAuthority) { [void]$Blockers.Add('hotkey_registration_authority_not_granted') }
if (-not $SummonAuthority) { [void]$Blockers.Add('summon_authority_not_granted') }
if ($NativeSurfaceReady -and -not $OverlayControlAuthority) { [void]$Blockers.Add('overlay_control_authority_not_granted') }
if (-not $NativeSurfaceReady -and -not $LocalProcessLaunchAuthority) { [void]$Blockers.Add('local_process_launch_authority_not_granted') }
if ($Mode -eq 'LocalOpen' -and -not [bool]$NoLaunch -and $NativeSurfaceReady -and $NativeExecutionAuthorized -and -not $NativeOpened) {
  [void]$Blockers.Add((Get-StringProperty -Payload $NativeOpenResult -Name 'error' -Default 'canonical_overlay_summon_request_failed'))
}

$Checks = @(
  (New-Check -Id 'summon_config' -Status $(if ($ConfigError) { 'invalid' } else { 'present' }) -Passed ([string]::IsNullOrWhiteSpace($ConfigError)) -Evidence $ConfigEvidencePath -Reason 'Summon configuration must exist before a local binding can be reported.'),
  (New-Check -Id 'native_orb_surface_target' -Status $(if ($NativeSurfaceReady) { 'native_surface_ready' } else { 'unavailable' }) -Passed ($NativeSurfaceReady -or $FallbackBindingReady) -Evidence 'data/runtime/lens-overlay/status.json' -Reason 'The canonical live Orb panel is the primary summon target; the web surface is fallback-only.'),
  (New-Check -Id 'web_surface_fallback' -Status $(if ($FallbackBindingReady) { 'available' } else { 'unavailable' }) -Passed ($NativeSurfaceReady -or $FallbackBindingReady) -Evidence 'scripts/lens-command-palette.ps1 -Mode LocalOpen -NoLaunch' -Reason 'The web command palette remains available only when the canonical overlay cannot accept the request.'),
  (New-Check -Id 'global_hotkey_binding' -Status $(if ($BindingEnabled -and $RegisterHotkey) { 'enabled' } else { 'disabled' }) -Passed ($BindingEnabled -and $RegisterHotkey) -Evidence $GlobalHotkey -Reason 'OS-wide summon requires the configured global hotkey binding.'),
  (New-Check -Id 'summon_authority' -Status $(if ($SummonAuthority) { 'allowed' } else { 'blocked' }) -Passed $SummonAuthority -Evidence 'summon_authority' -Reason 'The launcher consumes configured summon authority but does not grant new authority.')
)

$Status = if ($Mode -eq 'LocalOpen' -and $NativeOpened) {
  'native_surface_opened'
} elseif ($Mode -eq 'LocalOpen' -and -not [bool]$NoLaunch -and $NativeSurfaceReady -and -not $NativeExecutionAuthorized) {
  'blocked_by_authority'
} elseif ($Mode -eq 'LocalOpen' -and -not [bool]$NoLaunch -and -not $NativeSurfaceReady -and -not $FallbackExecutionAuthorized) {
  'blocked_by_authority'
} elseif ($Mode -eq 'LocalOpen' -and $NativeSurfaceReady -and -not [bool]$NoLaunch) {
  'native_surface_open_failed'
} elseif ($Mode -eq 'LocalOpen' -and $PaletteOpened) {
  'opened'
} elseif ($Mode -eq 'LocalOpen' -and $LocalBindingReady) {
  'local_open_ready'
} elseif ($LocalBindingReady) {
  'local_binding_ready'
} else {
  'blocked'
}
$NextGap = if ($SummonAnywhereReady -and $NativeOpened) {
  'stage6_lens_completion_audit'
} elseif ($SummonAnywhereReady) {
  'summon_binding_runtime_readback'
} else {
  'global_hotkey_binding'
}
$OperationOk = if ($Mode -eq 'LocalOpen' -and -not [bool]$NoLaunch) { $Opened } else { $LocalBindingReady }
$Payload = [ordered]@{
  ok = $OperationOk
  kind = 'lens.summon.local_launcher'
  status = $Status
  mode = $ModeName
  trigger = $Trigger
  repo_root = $RepoRoot
  data_root = $DataRoot
  config_path = $ConfigEvidencePath
  summon_runner = $SummonRunner
  launch_target = if ($NativeSurfaceReady) { 'lens.overlay.orb_panel' } else { 'chat_ui.command_palette' }
  native_launch_target = 'lens.overlay.orb_panel'
  native_surface = 'lens.overlay.orb.right_click_panel'
  native_surface_ready = $NativeSurfaceReady
  native_handoff_ready = $NativeSurfaceReady
  execution_authority_ready = if ($NativeSurfaceReady) { $NativeExecutionAuthorized } else { $FallbackExecutionAuthorized }
  local_binding_ready = $LocalBindingReady
  summon_binding_target_ready = $LocalBindingReady
  local_summon_available = $LocalBindingReady
  os_level_summon = $SummonAnywhereReady
  summon_anywhere = $SummonAnywhereReady
  global_hotkey = $GlobalHotkey
  binding_scope = $BindingScope
  binding_enabled = $BindingEnabled
  register_hotkey = $RegisterHotkey
  startup_register = $StartupRegister
  local_open_target_url = $PaletteTargetUrl
  would_open_palette = $Mode -eq 'LocalOpen' -and -not $NativeSurfaceReady
  opened = $Opened
  browser_opened = $PaletteOpened
  native_request = [ordered]@{
    request_id = Get-StringProperty -Payload $NativeOpenResult -Name 'request_id' -Default ''
    request_path = Get-StringProperty -Payload $NativeOpenResult -Name 'request_path' -Default ''
    receipt_path = Get-StringProperty -Payload $NativeOpenResult -Name 'receipt_path' -Default ''
  }
  native_request_consumed = Get-BoolProperty -Payload $NativeOpenResult -Name 'request_consumed' -Default $false
  no_launch = [bool]$NoLaunch
  checks = @($Checks)
  blockers = [string[]]@($Blockers.ToArray())
  native_surface_readbacks = $NativeReadback
  palette_launcher = [ordered]@{
    script = 'scripts/lens-command-palette.ps1'
    role = 'fallback_web_surface_only'
    status = Get-StringProperty -Payload $PalettePayload -Name 'status' -Default ''
    local_open_available = $PaletteLocalOpenAvailable
    readback_ready = $PaletteReadbackReady
    exit_code = $PaletteExitCode
    error = Get-StringProperty -Payload $PalettePayload -Name 'error' -Default (
      Get-StringProperty -Payload $PaletteResult -Name 'error' -Default ''
    )
  }
  next_smallest_truthful_gap = $NextGap
  governance = [ordered]@{
    read_only_contract = $Mode -eq 'Status'
    opens_palette = $PaletteOpened
    execution_authority = $Opened
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $NativeOpened
    summon_authority = $NativeOpened
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    local_process_launch_authority = $PaletteOpened
    mutation_authority_granted = $NativeOpened
  }
  controls_user_os_cursor = $false
  user_mouse_taken = $false
  physical_input_performed = $false
  updated_at = [DateTimeOffset]::UtcNow.ToString('o')
  message = if ($NativeOpened) {
    'Francis Lens summon opened the command surface on the canonical live Orb.'
  } elseif ($Mode -eq 'LocalOpen' -and -not [bool]$NoLaunch -and $NativeSurfaceReady -and -not $NativeExecutionAuthorized) {
    'Francis Lens summon refused the native Orb request because configured execution authority is not ready.'
  } elseif ($NativeSurfaceReady) {
    'The canonical live Orb is the summon target; the request was not acknowledged.'
  } elseif ($LocalBindingReady) {
    'The canonical Orb is unavailable; the existing web command-palette entrypoint remains fallback-only.'
  } else {
    'No canonical Orb or fallback command-palette summon target is ready.'
  }
}

if ($Mode -eq 'LocalOpen' -and -not [bool]$NoLaunch -and $Opened) {
  $Receipt = Write-SummonReceipt -Root $DataRoot -Payload $Payload
  $Payload['receipt_id'] = [string]$Receipt.receipt_id
  $Payload['receipt_path'] = [string]$Receipt.receipt_path
  Write-SummonJsonFile -Path (Join-Path (Join-Path $DataRoot 'runtime\lens-summon') 'status.json') -Payload $Payload
}

$Payload | ConvertTo-Json -Depth 10
if ($OperationOk) {
  exit 0
}
exit 1
