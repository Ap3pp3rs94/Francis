[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [ValidateRange(60, 86400)]
  [int]$MaxEvidenceAgeSeconds = 3600
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

function Get-ProofProperty {
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

function Read-ProofJson {
  param([string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return $null
  }
  for ($Attempt = 0; $Attempt -lt 5; $Attempt += 1) {
    try {
      return Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    } catch {
      if ($Attempt -lt 4) {
        Start-Sleep -Milliseconds 50
      }
    }
  }
  return $null
}

function Test-ProofProcessAlive {
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

function Resolve-ProofPath {
  param(
    [string]$Path,
    [string]$Root
  )

  if ([string]::IsNullOrWhiteSpace($Path)) {
    return ''
  }
  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $Root $Path))
}

function Get-ProofAgeSeconds {
  param([string]$UpdatedAt)

  if ([string]::IsNullOrWhiteSpace($UpdatedAt)) {
    return -1.0
  }
  try {
    $Timestamp = [DateTimeOffset]::Parse($UpdatedAt)
    return [Math]::Max(0, ([DateTimeOffset]::UtcNow - $Timestamp.ToUniversalTime()).TotalSeconds)
  } catch {
    return -1.0
  }
}

$DataRoot = if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  [System.IO.Path]::GetFullPath($DataDir)
} elseif (-not [string]::IsNullOrWhiteSpace([string]$env:FRANCIS_DATA_DIR)) {
  [System.IO.Path]::GetFullPath([string]$env:FRANCIS_DATA_DIR)
} else {
  Join-Path $RepoRoot 'data'
}

$SummonStatusPath = Join-Path $DataRoot 'runtime\lens-summon\status.json'
$OverlayStatusPath = Join-Path $DataRoot 'runtime\lens-overlay\status.json'
$HotkeyStatusPath = Join-Path $DataRoot 'runtime\lens-hotkey\status.json'
$TrayStatusPath = Join-Path $DataRoot 'runtime\lens-tray\status.json'
$SupervisorStatusPath = Join-Path $DataRoot 'runtime\lens-host-supervisor\status.json'
$RendererStatusPath = Join-Path $DataRoot 'runtime\native-orb-renderer\status.json'

$Summon = Read-ProofJson -Path $SummonStatusPath
$Overlay = Read-ProofJson -Path $OverlayStatusPath
$Hotkey = Read-ProofJson -Path $HotkeyStatusPath
$Tray = Read-ProofJson -Path $TrayStatusPath
$Supervisor = Read-ProofJson -Path $SupervisorStatusPath
$Renderer = Read-ProofJson -Path $RendererStatusPath
$OverlayControls = Get-ProofProperty -Payload $Overlay -Name 'orb_controls'
$OverlayRenderer = Get-ProofProperty -Payload $Overlay -Name 'native_renderer'
$NativeRequest = Get-ProofProperty -Payload $Summon -Name 'native_request'

$SummonReceiptPath = Resolve-ProofPath -Path ([string](Get-ProofProperty -Payload $Summon -Name 'receipt_path' -Default '')) -Root $RepoRoot
$SummonReceipt = Read-ProofJson -Path $SummonReceiptPath
$OrbReceiptPath = Resolve-ProofPath -Path ([string](Get-ProofProperty -Payload $SummonReceipt -Name 'orb_control_receipt_path' -Default '')) -Root $RepoRoot
$OrbReceipt = Read-ProofJson -Path $OrbReceiptPath

$SummonRequestId = [string](Get-ProofProperty -Payload $NativeRequest -Name 'request_id' -Default '')
$SummonReceiptRequestId = [string](Get-ProofProperty -Payload $SummonReceipt -Name 'request_id' -Default '')
$OrbReceiptRequestId = [string](Get-ProofProperty -Payload $OrbReceipt -Name 'request_id' -Default '')
$OverlayRequestId = [string](Get-ProofProperty -Payload $OverlayControls -Name 'latest_request_id' -Default '')
$SummonAgeSeconds = Get-ProofAgeSeconds -UpdatedAt ([string](Get-ProofProperty -Payload $Summon -Name 'updated_at' -Default ''))
$ReceiptAgeSeconds = Get-ProofAgeSeconds -UpdatedAt ([string](Get-ProofProperty -Payload $SummonReceipt -Name 'updated_at' -Default ''))

$OverlayPid = [int](Get-ProofProperty -Payload $Overlay -Name 'pid' -Default 0)
$HotkeyPid = [int](Get-ProofProperty -Payload $Hotkey -Name 'pid' -Default 0)
$TrayPid = [int](Get-ProofProperty -Payload $Tray -Name 'pid' -Default 0)
$SupervisorPid = [int](Get-ProofProperty -Payload $Supervisor -Name 'supervisor_pid' -Default 0)
$HostPid = [int](Get-ProofProperty -Payload $Supervisor -Name 'observed_pid' -Default 0)
$RendererPid = [int](Get-ProofProperty -Payload $Renderer -Name 'process_id' -Default 0)
$OverlayRendererPid = [int](Get-ProofProperty -Payload $OverlayRenderer -Name 'pid' -Default 0)
$RendererProcesses = @(Get-Process -Name 'native_orb_renderer' -ErrorAction SilentlyContinue)
$RendererProcessIds = [int[]]@($RendererProcesses | ForEach-Object { [int]$_.Id })

$Checks = [ordered]@{
  summon_status = (
    [string](Get-ProofProperty -Payload $Summon -Name 'kind' -Default '') -eq 'lens.summon.local_launcher' -and
    [string](Get-ProofProperty -Payload $Summon -Name 'status' -Default '') -eq 'native_surface_opened' -and
    [bool](Get-ProofProperty -Payload $Summon -Name 'ok' -Default $false) -and
    [bool](Get-ProofProperty -Payload $Summon -Name 'opened' -Default $false)
  )
  evidence_fresh = (
    $SummonAgeSeconds -ge 0 -and
    $ReceiptAgeSeconds -ge 0 -and
    $SummonAgeSeconds -le $MaxEvidenceAgeSeconds -and
    $ReceiptAgeSeconds -le $MaxEvidenceAgeSeconds
  )
  global_hotkey_trigger = [string](Get-ProofProperty -Payload $Summon -Name 'trigger' -Default '') -eq 'global_hotkey'
  request_consumed = [bool](Get-ProofProperty -Payload $Summon -Name 'native_request_consumed' -Default $false)
  request_correlation = (
    -not [string]::IsNullOrWhiteSpace($SummonRequestId) -and
    $SummonRequestId -eq $SummonReceiptRequestId -and
    $SummonRequestId -eq $OrbReceiptRequestId -and
    $SummonRequestId -eq $OverlayRequestId
  )
  summon_receipt = (
    [string](Get-ProofProperty -Payload $SummonReceipt -Name 'kind' -Default '') -eq 'lens.summon.execution_receipt' -and
    [string](Get-ProofProperty -Payload $SummonReceipt -Name 'status' -Default '') -eq 'native_surface_opened' -and
    [string](Get-ProofProperty -Payload $SummonReceipt -Name 'trigger' -Default '') -eq 'global_hotkey' -and
    [bool](Get-ProofProperty -Payload $SummonReceipt -Name 'opened' -Default $false)
  )
  orb_control_receipt = (
    [string](Get-ProofProperty -Payload $OrbReceipt -Name 'kind' -Default '') -eq 'lens.overlay.orb_control.receipt' -and
    [string](Get-ProofProperty -Payload $OrbReceipt -Name 'action' -Default '') -eq 'panel_open' -and
    [string](Get-ProofProperty -Payload $OrbReceipt -Name 'trigger' -Default '') -eq 'global_hotkey'
  )
  overlay_runtime = (
    [string](Get-ProofProperty -Payload $Overlay -Name 'status' -Default '') -eq 'overlay_running' -and
    [bool](Get-ProofProperty -Payload $Overlay -Name 'overlay_window_visible' -Default $false) -and
    [bool](Get-ProofProperty -Payload $Overlay -Name 'always_on_top' -Default $false) -and
    (Test-ProofProcessAlive -ProcessId $OverlayPid)
  )
  hotkey_runtime = (
    [string](Get-ProofProperty -Payload $Hotkey -Name 'status' -Default '') -eq 'hotkey_bound' -and
    [bool](Get-ProofProperty -Payload $Hotkey -Name 'hotkey_bound' -Default $false) -and
    [bool](Get-ProofProperty -Payload $Hotkey -Name 'launch_on_hotkey' -Default $false) -and
    [int](Get-ProofProperty -Payload $Hotkey -Name 'press_count' -Default 0) -gt 0 -and
    (Test-ProofProcessAlive -ProcessId $HotkeyPid)
  )
  tray_runtime = (
    [string](Get-ProofProperty -Payload $Tray -Name 'status' -Default '') -eq 'tray_running' -and
    (Test-ProofProcessAlive -ProcessId $TrayPid)
  )
  supervised_resident_host = (
    [string](Get-ProofProperty -Payload $Supervisor -Name 'status' -Default '') -eq 'resident_supervising' -and
    [bool](Get-ProofProperty -Payload $Supervisor -Name 'resident_supervised_runtime' -Default $false) -and
    (Test-ProofProcessAlive -ProcessId $SupervisorPid) -and
    (Test-ProofProcessAlive -ProcessId $HostPid)
  )
  single_canonical_renderer = (
    $RendererPid -gt 0 -and
    $RendererPid -eq $OverlayRendererPid -and
    [bool](Get-ProofProperty -Payload $Renderer -Name 'active_renderer' -Default $false) -and
    (Test-ProofProcessAlive -ProcessId $RendererPid) -and
    @($RendererProcessIds).Count -eq 1 -and
    $RendererProcessIds[0] -eq $RendererPid
  )
  authority_ready = [bool](Get-ProofProperty -Payload $Summon -Name 'execution_authority_ready' -Default $false)
  no_browser_fallback = -not [bool](Get-ProofProperty -Payload $Summon -Name 'browser_opened' -Default $true)
  no_physical_input = (
    -not [bool](Get-ProofProperty -Payload $Summon -Name 'controls_user_os_cursor' -Default $true) -and
    -not [bool](Get-ProofProperty -Payload $Summon -Name 'user_mouse_taken' -Default $true) -and
    -not [bool](Get-ProofProperty -Payload $Summon -Name 'physical_input_performed' -Default $true)
  )
}

$Blockers = [System.Collections.ArrayList]::new()
foreach ($Check in $Checks.GetEnumerator()) {
  if (-not [bool]$Check.Value) {
    [void]$Blockers.Add(('canonical_summon_{0}_not_proven' -f [string]$Check.Key))
  }
}
$ProofPassed = $Blockers.Count -eq 0
$GlobalHotkey = [string](Get-ProofProperty -Payload $Hotkey -Name 'global_hotkey' -Default '')

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.summon.canonical_runtime.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'blocked' }
  mode = $Mode.ToLowerInvariant()
  source = 'canonical_live_runtime_readback'
  data_root = $DataRoot
  allow_launch_on_hotkey = $true
  opened = [bool](Get-ProofProperty -Payload $Summon -Name 'opened' -Default $false)
  no_launch = $false
  summon_anywhere = $ProofPassed
  os_level_summon = $ProofPassed
  hotkey_launch_on_press_authority = [bool](Get-ProofProperty -Payload $Summon -Name 'execution_authority_ready' -Default $false)
  hotkey_launch_on_press = [bool]$Checks.global_hotkey_trigger -and [bool]$Checks.request_correlation
  global_hotkey = $GlobalHotkey
  request_id = $SummonRequestId
  summon_receipt_id = [string](Get-ProofProperty -Payload $Summon -Name 'receipt_id' -Default '')
  summon_receipt_path = $SummonReceiptPath
  orb_control_receipt_id = [string](Get-ProofProperty -Payload $OrbReceipt -Name 'receipt_id' -Default '')
  orb_control_receipt_path = $OrbReceiptPath
  overlay_pid = $OverlayPid
  hotkey_pid = $HotkeyPid
  tray_pid = $TrayPid
  supervisor_pid = $SupervisorPid
  resident_host_pid = $HostPid
  renderer_pid = $RendererPid
  renderer_process_count = @($RendererProcessIds).Count
  evidence_age_seconds = [ordered]@{
    summon_status = [Math]::Round($SummonAgeSeconds, 3)
    summon_receipt = [Math]::Round($ReceiptAgeSeconds, 3)
    maximum = $MaxEvidenceAgeSeconds
  }
  checks = $Checks
  blockers = [string[]]@($Blockers.ToArray())
  cleanup_errors = [string[]]@()
  summon_readiness_status_after_execute = if ($ProofPassed) { 'ready_for_operator_review' } else { 'blocked' }
  summon_readiness_blockers_after_execute = [string[]]@($Blockers.ToArray())
  previous_next_smallest_truthful_gap = 'summon_api_launch_on_hotkey_readback'
  next_smallest_truthful_gap = if ($ProofPassed) { 'stage6_lens_completion_audit' } else { 'canonical_summon_runtime_readback' }
  recommended_handoff_source = 'canonical_live_summon_runtime_readback_handoff'
  recommended_next_slice = if ($ProofPassed) { 'review_remaining_stage6_acceptance_after_canonical_summon' } else { 'repair_canonical_summon_runtime_readback' }
  recommended_proof_script = 'scripts/lens-canonical-summon-runtime-proof.ps1 -Mode Status'
  authority_required = 'none_readback_only'
  authority_granted = $false
  governance = [ordered]@{
    diagnostic_only = $true
    read_only_contract = $true
    canonical_runtime_only = $true
    launches_process = $false
    stops_process = $false
    restarts_process = $false
    writes_runtime_state = $false
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    tray_registration_authority = $false
    hotkey_registration_authority = $false
    overlay_control_authority = $false
    summon_authority = $false
    memory_write = $false
    mutation_authority_granted = $false
  }
}

$Payload | ConvertTo-Json -Depth 12
if ($ProofPassed) {
  exit 0
}
exit 1
