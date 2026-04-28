[CmdletBinding()]
param(
  [ValidateSet('Status', 'Foreground', 'Launch')]
  [string]$Mode = 'Status'
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$modeName = $Mode.ToLowerInvariant()
$ServiceConfigPath = Join-Path $RepoRoot 'config\runtime\services\lens-host.json'
$ServiceConfigExists = Test-Path -LiteralPath $ServiceConfigPath -PathType Leaf
$ServiceName = 'Francis-LensHost'
if ($ServiceConfigExists) {
  try {
    $ServiceConfigPayload = Get-Content -LiteralPath $ServiceConfigPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    $ServiceNameProperty = $ServiceConfigPayload.PSObject.Properties['service_name']
    if ($null -ne $ServiceNameProperty -and -not [string]::IsNullOrWhiteSpace([string]$ServiceNameProperty.Value)) {
      $ServiceName = [string]$ServiceNameProperty.Value
    }
  } catch {
    $ServiceName = 'Francis-LensHost'
  }
}
$ProcessStatePath = Join-Path $RepoRoot 'data\runtime\lens-host\status.json'
$PidPath = Join-Path $RepoRoot 'data\runtime\lens-host\lens-host.pid'
$ProcessStateExists = Test-Path -LiteralPath $ProcessStatePath -PathType Leaf
$PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf
$PidValue = 0
if ($PidPresent) {
  try {
    $PidValue = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
  } catch {
    $PidValue = 0
  }
}
$ProcessAlive = $false
if ($PidValue -gt 0) {
  try {
    Get-Process -Id $PidValue -ErrorAction Stop | Out-Null
    $ProcessAlive = $true
  } catch {
    $ProcessAlive = $false
  }
}
$Blockers = @(
  'lens_host_runtime_not_implemented',
  'tray_host_missing',
  'global_hotkey_binding_missing',
  'overlay_window_missing',
  'summon_binding_missing'
)
if (-not $ServiceConfigExists) {
  $Blockers = @('lens_host_service_config_missing') + $Blockers
}

$WindowsServiceSupported = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)
$ServiceInstalled = $false
$ServiceStatus = if ($WindowsServiceSupported) { 'not_installed' } else { 'unsupported_platform' }
$ServiceStartType = ''
$ServiceState = ''
$ServicePathName = ''
$ServiceAccount = ''
$ServiceReadbackError = ''
if ($WindowsServiceSupported) {
  try {
    $Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($null -ne $Service) {
      $ServiceInstalled = $true
      $ServiceStatus = ([string]$Service.Status).ToLowerInvariant()
      $FilterServiceName = $ServiceName.Replace("'", "''")
      $CimService = $null
      try {
        $CimService = Get-CimInstance Win32_Service -Filter "Name='$FilterServiceName'" -ErrorAction SilentlyContinue
      } catch {
        $CimService = $null
      }
      if ($null -ne $CimService) {
        $ServiceStartType = [string]$CimService.StartMode
        $ServiceState = [string]$CimService.State
        $ServicePathName = [string]$CimService.PathName
        $ServiceAccount = [string]$CimService.StartName
      }
    }
  } catch {
    $ServiceStatus = 'unavailable'
    $ServiceReadbackError = [string]$_.Exception.Message
  }
}
$ServiceBlockedReason = if ($ServiceInstalled) { 'lens_host_runtime_not_implemented' } elseif ($WindowsServiceSupported) { 'lens_host_service_not_installed' } else { 'windows_service_readback_unavailable' }

$payload = [ordered]@{
  ok = $true
  kind = 'lens.host.status_runner'
  status = 'status_only'
  mode = $modeName
  repo_root = $RepoRoot
  service_config_path = 'config/runtime/services/lens-host.json'
  service_config_exists = $ServiceConfigExists
  service_readback = [ordered]@{
    status = $ServiceStatus
    readback_ready = $true
    service_name = $ServiceName
    installed = $ServiceInstalled
    windows_service = $WindowsServiceSupported
    start_type = $ServiceStartType
    state = $ServiceState
    path_name = $ServicePathName
    account = $ServiceAccount
    error = $ServiceReadbackError
    install_supported = $false
    start_supported = $false
    stop_supported = $false
    restart_supported = $false
    install_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    blocked_reason = $ServiceBlockedReason
  }
  process_readback = [ordered]@{
    status = if ($ProcessAlive) { 'process_observed' } elseif ($PidPresent -or $ProcessStateExists) { 'state_present_process_not_running' } else { 'missing' }
    readback_ready = $true
    runtime_state_path = 'data/runtime/lens-host/status.json'
    state_exists = $ProcessStateExists
    pid_path = 'data/runtime/lens-host/lens-host.pid'
    pid_present = $PidPresent
    pid = $PidValue
    process_alive = $ProcessAlive
    supervision_enabled = $false
    start_supported = $false
    stop_supported = $false
    restart_supported = $false
    supervision_authority = $false
    blocked_reason = 'resident_host_process_missing'
  }
  route = '/lens/host'
  manifest_route = '/lens/host/manifest'
  launch_supported = $false
  foreground_supported = $false
  resident = $false
  process_supervision = $false
  tray_presence = $false
  global_hotkey = $false
  always_on_top_overlay = $false
  overlay_window = $false
  command_palette_binding = $false
  summon_anywhere = $false
  blockers = $Blockers
  governance = [ordered]@{
    read_only_contract = $true
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    mutation_authority_granted = $false
  }
}

if ($Mode -eq 'Status') {
  $payload | ConvertTo-Json -Depth 8
  exit 0
}

$payload.ok = $false
$payload.status = 'refused'
$payload.error = 'lens_host_runtime_not_implemented'
$payload.message = 'Lens host foreground/runtime launch is not implemented; this runner only reports status.'
$payload | ConvertTo-Json -Depth 8
exit 2
