[CmdletBinding()]
param(
  [ValidateSet('Status', 'Install', 'Start', 'Launch')]
  [string]$Mode = 'Status'
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

function Get-ArrayProperty {
  param(
    [object]$Payload,
    [string]$Name
  )

  if ($null -eq $Payload) {
    return @()
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) {
    return @()
  }
  if ($Property.Value -is [string]) {
    return @([string]$Property.Value)
  }
  return @($Property.Value | ForEach-Object { [string]$_ })
}

function Quote-CommandArg {
  param([string]$Value)

  if ($null -eq $Value) {
    return ''
  }
  if ($Value -match '[\s"]') {
    return '"' + ($Value -replace '"', '\"') + '"'
  }
  return $Value
}

function Join-CommandLine {
  param(
    [string]$Executable,
    [string[]]$Items
  )

  $Parts = [System.Collections.ArrayList]::new()
  if (-not [string]::IsNullOrWhiteSpace($Executable)) {
    [void]$Parts.Add((Quote-CommandArg -Value $Executable))
  }
  foreach ($Item in $Items) {
    [void]$Parts.Add((Quote-CommandArg -Value $Item))
  }
  return ($Parts -join ' ')
}

function Get-WindowsServiceSupported {
  try {
    return [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
      [System.Runtime.InteropServices.OSPlatform]::Windows
    )
  } catch {
    return $false
  }
}

$ModeName = $Mode.ToLowerInvariant()
$ServiceConfigPath = Join-Path $RepoRoot 'config\runtime\services\lens-host.json'
$ServiceConfigExists = Test-Path -LiteralPath $ServiceConfigPath -PathType Leaf
$ServiceConfig = $null
$ConfigError = ''
if ($ServiceConfigExists) {
  try {
    $ServiceConfig = Get-Content -LiteralPath $ServiceConfigPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $ConfigError = [string]$_.Exception.Message
  }
}

$Entrypoint = Get-StringProperty -Payload $ServiceConfig -Name 'entrypoint' -Default 'scripts/lens-host.ps1'
$EntrypointPath = Join-Path $RepoRoot $Entrypoint
$EntrypointExists = Test-Path -LiteralPath $EntrypointPath -PathType Leaf
$Manager = Get-StringProperty -Payload $ServiceConfig -Name 'manager' -Default 'scripts/service-install.ps1'
$ManagerPath = Join-Path $RepoRoot $Manager
$ManagerExists = Test-Path -LiteralPath $ManagerPath -PathType Leaf
$ServiceName = Get-StringProperty -Payload $ServiceConfig -Name 'service_name' -Default 'Francis-LensHost'
$BlockedReason = Get-StringProperty -Payload $ServiceConfig -Name 'blocked_reason' -Default 'lens_host_runtime_not_implemented'
$ServiceExecutable = Get-StringProperty -Payload $ServiceConfig -Name 'service_executable' -Default ''
$ServiceArguments = Get-ArrayProperty -Payload $ServiceConfig -Name 'service_arguments'
$WorkingDirectory = Get-StringProperty -Payload $ServiceConfig -Name 'working_dir' -Default ''
$UseWrapper = Get-BoolProperty -Payload $ServiceConfig -Name 'use_wrapper' -Default $false
$StartType = Get-StringProperty -Payload $ServiceConfig -Name 'start_type' -Default 'Manual'
$Installable = Get-BoolProperty -Payload $ServiceConfig -Name 'installable' -Default $false
$InstallAuthority = Get-BoolProperty -Payload $ServiceConfig -Name 'install_authority' -Default $false
$ServiceInstallAuthority = Get-BoolProperty -Payload $ServiceConfig -Name 'service_install_authority' -Default $false
$ServiceControlAuthority = Get-BoolProperty -Payload $ServiceConfig -Name 'service_control_authority' -Default $false
$AutoStart = Get-BoolProperty -Payload $ServiceConfig -Name 'auto_start' -Default $false
$StartAfterInstall = Get-BoolProperty -Payload $ServiceConfig -Name 'start_after_install' -Default $false
$ProcessSupervisionEnabled = Get-BoolProperty -Payload $ServiceConfig -Name 'process_supervision_enabled' -Default $false
$ServiceStatusReadback = Get-BoolProperty -Payload $ServiceConfig -Name 'service_status_readback' -Default $false

$WindowsServiceSupported = Get-WindowsServiceSupported
$ServiceInstalled = $false
$ServiceStatus = if ($WindowsServiceSupported) { 'not_installed' } else { 'unsupported_platform' }
if ($WindowsServiceSupported) {
  try {
    $Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($null -ne $Service) {
      $ServiceInstalled = $true
      $ServiceStatus = ([string]$Service.Status).ToLowerInvariant()
    }
  } catch {
    $ServiceStatus = 'unavailable'
  }
}

$RuntimeStatePath = Join-Path $RepoRoot 'data\runtime\lens-host\status.json'
$PidPath = Join-Path $RepoRoot 'data\runtime\lens-host\lens-host.pid'
$RuntimeStateExists = Test-Path -LiteralPath $RuntimeStatePath -PathType Leaf
$PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf

$PlanBlockers = [System.Collections.ArrayList]::new()
if (-not $ServiceConfigExists) { [void]$PlanBlockers.Add('service_config_missing') }
if ($ConfigError) { [void]$PlanBlockers.Add('service_config_invalid') }
if (-not $ManagerExists) { [void]$PlanBlockers.Add('service_manager_missing') }
if (-not $EntrypointExists) { [void]$PlanBlockers.Add('host_entrypoint_missing') }
if ([string]::IsNullOrWhiteSpace($ServiceExecutable)) { [void]$PlanBlockers.Add('service_executable_missing') }
if (-not $Installable) { [void]$PlanBlockers.Add('installable_false') }
if (-not $InstallAuthority) { [void]$PlanBlockers.Add('install_authority_false') }
if (-not $ServiceInstallAuthority) { [void]$PlanBlockers.Add('service_install_authority_false') }
if (-not $ServiceControlAuthority) { [void]$PlanBlockers.Add('service_control_authority_false') }
$ServicePlanReady = $PlanBlockers.Count -eq 0
$PlannedCommand = Join-CommandLine -Executable $ServiceExecutable -Items $ServiceArguments

$Checks = [System.Collections.ArrayList]::new()
Add-Check -Target $Checks -Id 'runtime_root' -Status 'ready' -Reason 'runtime root accepted' -Evidence $RepoRoot
Add-Check -Target $Checks -Id 'service_config' -Status $(if ($ServiceConfigExists -and -not $ConfigError) { 'present_disabled' } elseif ($ServiceConfigExists) { 'invalid' } else { 'missing' }) -Reason $(if ($ConfigError) { $ConfigError } elseif ($ServiceConfigExists) { 'disabled readiness config is present' } else { 'lens host service config is missing' }) -Evidence 'config/runtime/services/lens-host.json'
Add-Check -Target $Checks -Id 'host_entrypoint' -Status $(if ($EntrypointExists) { 'present' } else { 'missing' }) -Reason $(if ($EntrypointExists) { 'status runner is present' } else { 'status runner is missing' }) -Evidence $Entrypoint
Add-Check -Target $Checks -Id 'service_manager' -Status $(if ($ManagerExists) { 'present' } else { 'missing' }) -Reason $(if ($ManagerExists) { 'service manager script is present' } else { 'service manager script is missing' }) -Evidence $Manager
Add-Check -Target $Checks -Id 'service_status_readback' -Status $(if ($ServiceStatusReadback) { 'ready' } else { 'missing' }) -Reason $(if ($ServiceStatusReadback) { 'service status readback is declared' } else { 'service status readback is not declared' }) -Evidence $ServiceName
Add-Check -Target $Checks -Id 'service_plan' -Status $(if ($ServicePlanReady) { 'ready' } else { 'blocked' }) -Reason $(if ($ServicePlanReady) { 'service manager dry-run plan has no blockers' } else { 'service manager dry-run plan remains blocked' }) -Evidence 'scripts/service-install.ps1 -Mode Plan'
Add-Check -Target $Checks -Id 'windows_service' -Status $ServiceStatus -Reason $(if ($ServiceInstalled) { 'declared service is installed' } else { 'declared service is not installed or cannot be queried here' }) -Evidence $ServiceName
Add-Check -Target $Checks -Id 'install_authority' -Status $(if ($Installable -and $InstallAuthority -and $ServiceInstallAuthority) { 'allowed' } else { 'blocked' }) -Reason 'service install authority is not granted by this Stage 6 preflight' -Evidence 'installable/install_authority/service_install_authority'
Add-Check -Target $Checks -Id 'service_control_authority' -Status $(if ($ServiceControlAuthority) { 'allowed' } else { 'blocked' }) -Reason 'service start/stop/restart authority is not granted by this Stage 6 preflight' -Evidence 'service_control_authority'
Add-Check -Target $Checks -Id 'startup_policy' -Status $(if ($AutoStart -or $StartAfterInstall) { 'would_start' } else { 'disabled' }) -Reason 'startup remains disabled until resident host runtime exists' -Evidence 'auto_start/start_after_install'
Add-Check -Target $Checks -Id 'process_supervision' -Status $(if ($ProcessSupervisionEnabled) { 'enabled' } else { 'blocked' }) -Reason 'process supervision remains disabled' -Evidence 'process_supervision_enabled'
Add-Check -Target $Checks -Id 'runtime_state' -Status $(if ($RuntimeStateExists -or $PidPresent) { 'state_present' } else { 'missing' }) -Reason 'resident host runtime state is not present' -Evidence 'data/runtime/lens-host'
Add-Check -Target $Checks -Id 'tray_presence' -Status 'missing' -Reason 'tray or equivalent presence host is not implemented' -Evidence 'required_before_enable'
Add-Check -Target $Checks -Id 'global_hotkey_binding' -Status 'missing' -Reason 'global summon hotkey is not implemented' -Evidence 'required_before_enable'
Add-Check -Target $Checks -Id 'overlay_window' -Status 'missing' -Reason 'always-on-top Lens overlay is not implemented' -Evidence 'required_before_enable'
Add-Check -Target $Checks -Id 'summon_binding' -Status 'missing' -Reason 'OS-wide summon binding is not implemented' -Evidence 'required_before_enable'

$Blockers = [System.Collections.ArrayList]::new()
if (-not $ServiceConfigExists) { [void]$Blockers.Add('lens_host_service_config_missing') }
if ($ConfigError) { [void]$Blockers.Add('lens_host_service_config_invalid') }
if (-not $EntrypointExists) { [void]$Blockers.Add('lens_host_entrypoint_missing') }
if (-not $ManagerExists) { [void]$Blockers.Add('lens_host_service_manager_missing') }
if (-not $Installable -or -not $InstallAuthority -or -not $ServiceInstallAuthority) { [void]$Blockers.Add('lens_host_install_not_authorized') }
if (-not $ServiceControlAuthority) { [void]$Blockers.Add('lens_host_service_control_not_authorized') }
if (-not $ServiceInstalled) { [void]$Blockers.Add('lens_host_service_not_installed') }
if (-not $ProcessSupervisionEnabled) { [void]$Blockers.Add('resident_host_process_supervision_disabled') }
if (-not $RuntimeStateExists -and -not $PidPresent) { [void]$Blockers.Add('resident_host_process_missing') }
[void]$Blockers.Add('tray_host_missing')
[void]$Blockers.Add('global_hotkey_binding_missing')
[void]$Blockers.Add('overlay_window_missing')
[void]$Blockers.Add('summon_binding_missing')
if ($BlockedReason) { [void]$Blockers.Insert(0, $BlockedReason) }

$ProcessReadbackBlockers = [System.Collections.ArrayList]::new()
if (-not $RuntimeStateExists -and -not $PidPresent) {
  [void]$ProcessReadbackBlockers.Add('resident_host_process_missing')
}

$AuthorityBlockers = [System.Collections.ArrayList]::new()
foreach ($Candidate in @(
    'install_authority_false',
    'service_install_authority_false',
    'service_control_authority_false'
  )) {
  if ($PlanBlockers -contains $Candidate) {
    [void]$AuthorityBlockers.Add($Candidate)
  }
}

$RuntimeBlockers = [System.Collections.ArrayList]::new()
if ($BlockedReason) { [void]$RuntimeBlockers.Add($BlockedReason) }
if (-not $ServiceConfigExists) { [void]$RuntimeBlockers.Add('lens_host_service_config_missing') }
if (-not $EntrypointExists) { [void]$RuntimeBlockers.Add('lens_host_entrypoint_missing') }

$BlockerGroups = [ordered]@{
  runtime = [string[]]@($RuntimeBlockers)
  process_readback = [string[]]@($ProcessReadbackBlockers)
  service_plan = [string[]]@($PlanBlockers)
  surface_dependencies = [string[]]@(
    'tray_host_missing',
    'global_hotkey_binding_missing',
    'overlay_window_missing',
    'summon_binding_missing'
  )
  authority = [string[]]@($AuthorityBlockers)
}

$Ready = $Blockers.Count -eq 0
$Payload = [ordered]@{
  ok = $true
  kind = 'lens.host.lifecycle_preflight'
  status = if ($Ready) { 'ready' } else { 'blocked' }
  mode = $ModeName
  ready = $Ready
  next_smallest_truthful_gap = 'resident_host_lifecycle_blockers'
  repo_root = $RepoRoot
  service_name = $ServiceName
  service_config_path = 'config/runtime/services/lens-host.json'
  entrypoint = $Entrypoint
  checks = $Checks
  blockers = $Blockers
  blocker_groups = $BlockerGroups
  service = [ordered]@{
    status = $ServiceStatus
    installed = $ServiceInstalled
    windows_service = $WindowsServiceSupported
    installable = $Installable
    auto_start = $AutoStart
    start_after_install = $StartAfterInstall
  }
  service_plan = [ordered]@{
    kind = 'service_install.plan_projection'
    status = if ($ServicePlanReady) { 'ready' } else { 'blocked' }
    ready = $ServicePlanReady
    source = 'config/runtime/services/lens-host.json'
    manager = $Manager
    manager_exists = $ManagerExists
    plan_mode = 'Plan'
    service_name = $ServiceName
    service_executable = $ServiceExecutable
    service_arguments = $ServiceArguments
    planned_command = $PlannedCommand
    working_directory = $WorkingDirectory
    start_type = $StartType
    use_wrapper = $UseWrapper
    would_install = ($Installable -and $InstallAuthority -and $ServiceInstallAuthority)
    would_start = $StartAfterInstall
    wrapper_would_write = $false
    blocked_by = $PlanBlockers
    blocked_reason = $BlockedReason
    governance = [ordered]@{
      read_only_contract = $true
      execution_authority = $false
      approval_decision_authority = $false
      memory_write = $false
      local_process_launch_authority = $false
      service_install_authority = $false
      service_control_authority = $false
      wrapper_write_authority = $false
      mutation_authority_granted = $false
    }
  }
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
  message = 'Lens host lifecycle preflight is read-only; install/start/launch remain blocked until resident host runtime prerequisites exist.'
}

if ($Mode -eq 'Status') {
  $Payload | ConvertTo-Json -Depth 8
  exit 0
}

$Payload.ok = $false
$Payload.status = 'refused'
$Payload.error = 'lens_host_lifecycle_action_not_authorized'
$Payload.message = 'Lens host lifecycle actions are not authorized by this preflight; use Status for read-only inspection.'
$Payload | ConvertTo-Json -Depth 8
exit 2
