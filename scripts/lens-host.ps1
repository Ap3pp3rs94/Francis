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
$payload = [ordered]@{
  ok = $true
  kind = 'lens.host.status_runner'
  status = 'status_only'
  mode = $modeName
  repo_root = $RepoRoot
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
  blockers = @(
    'lens_host_runtime_not_implemented',
    'lens_host_service_config_missing',
    'tray_host_missing',
    'global_hotkey_binding_missing',
    'overlay_window_missing',
    'summon_binding_missing'
  )
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
