param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status'
)

$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

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

function Get-PropertyValue {
  param(
    [object]$Payload,
    [string]$Name,
    [object]$Default = $null
  )

  if ($null -eq $Payload) {
    return $Default
  }
  if ($Payload -is [System.Collections.IDictionary] -and $Payload.Contains($Name)) {
    $Value = $Payload[$Name]
    if ($null -ne $Value) {
      return $Value
    }
    return $Default
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) {
    return $Default
  }
  return $Property.Value
}

function ConvertTo-StringArray {
  param([AllowNull()][object]$Value)

  if ($null -eq $Value) {
    return @()
  }
  if ($Value -is [System.Array]) {
    return @($Value | ForEach-Object { [string]$_ })
  }
  return @([string]$Value)
}

function New-Requirement {
  param(
    [string]$Id,
    [string]$Label,
    [bool]$Ready,
    [string]$Reason,
    [string]$AuthorityRequired = ''
  )

  return [ordered]@{
    id = $Id
    label = $Label
    ready = $Ready
    status = if ($Ready) { 'ready' } else { 'blocked' }
    reason = $Reason
    authority_required = $AuthorityRequired
    authority_granted = $false
  }
}

function Quote-CommandPart {
  param([string]$Value)

  if ([string]::IsNullOrWhiteSpace($Value)) {
    return '""'
  }
  if ($Value -match '\s' -or $Value.Contains('"')) {
    return '"' + ($Value -replace '"', '\"') + '"'
  }
  return $Value
}

$ConfigRelativePath = 'config/runtime/services/lens-host.json'
$ConfigPath = Join-Path $RepoRoot $ConfigRelativePath
$HostRelativePath = 'scripts/lens-host.ps1'
$HostPath = Join-Path $RepoRoot $HostRelativePath
$ManagerRelativePath = 'scripts/service-install.ps1'
$ManagerPath = Join-Path $RepoRoot $ManagerRelativePath
$Config = Read-JsonFile -Path $ConfigPath

$ConfigPresent = $null -ne $Config
$HostPresent = Test-Path -LiteralPath $HostPath -PathType Leaf
$ManagerPresent = Test-Path -LiteralPath $ManagerPath -PathType Leaf

$ServiceName = [string](Get-PropertyValue -Payload $Config -Name 'service_name' -Default 'Francis-LensHost')
$Executable = [string](Get-PropertyValue -Payload $Config -Name 'service_executable' -Default '')
$Arguments = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Config -Name 'service_arguments' -Default @())
$PlannedCommandParts = @()
if (-not [string]::IsNullOrWhiteSpace($Executable)) {
  $PlannedCommandParts += Quote-CommandPart -Value $Executable
}
$PlannedCommandParts += @($Arguments | ForEach-Object { Quote-CommandPart -Value $_ })

$ProcessSupervisionEnabled = [bool](Get-PropertyValue -Payload $Config -Name 'process_supervision_enabled' -Default $false)
$PersistentSupervisionEnabled = [bool](Get-PropertyValue -Payload $Config -Name 'persistent_supervision_enabled' -Default $false)
$ProcessRestartAuthority = [bool](Get-PropertyValue -Payload $Config -Name 'process_restart_authority' -Default $false)
$InstallAuthority = [bool](
  (Get-PropertyValue -Payload $Config -Name 'install_authority' -Default $false) -or
  (Get-PropertyValue -Payload $Config -Name 'service_install_authority' -Default $false)
)
$ServiceControlAuthority = [bool](Get-PropertyValue -Payload $Config -Name 'service_control_authority' -Default $false)
$ReceiptWriteAuthority = [bool](Get-PropertyValue -Payload $Config -Name 'receipt_write_authority' -Default $false)
$ResidentClaimAuthority = [bool](Get-PropertyValue -Payload $Config -Name 'resident_claim_authority' -Default $false)

$Requirements = @(
  (New-Requirement -Id 'service_config' -Label 'Lens host service config' -Ready $ConfigPresent -Reason $(if ($ConfigPresent) { '' } else { 'service_config_missing' })),
  (New-Requirement -Id 'host_entrypoint' -Label 'Lens host entrypoint' -Ready $HostPresent -Reason $(if ($HostPresent) { '' } else { 'host_entrypoint_missing' })),
  (New-Requirement -Id 'service_manager' -Label 'Service manager script' -Ready $ManagerPresent -Reason $(if ($ManagerPresent) { '' } else { 'service_manager_missing' })),
  (New-Requirement -Id 'process_supervision_enabled' -Label 'Process supervision enabled' -Ready $ProcessSupervisionEnabled -Reason $(if ($ProcessSupervisionEnabled) { '' } else { 'process_supervision_disabled' }) -AuthorityRequired 'process_supervision'),
  (New-Requirement -Id 'persistent_supervision_enabled' -Label 'Persistent supervision enabled' -Ready $PersistentSupervisionEnabled -Reason $(if ($PersistentSupervisionEnabled) { '' } else { 'persistent_supervision_disabled' }) -AuthorityRequired 'persistent_supervision'),
  (New-Requirement -Id 'process_restart_authority' -Label 'Process restart authority' -Ready $ProcessRestartAuthority -Reason $(if ($ProcessRestartAuthority) { '' } else { 'process_restart_authority_not_granted' }) -AuthorityRequired 'process_restart'),
  (New-Requirement -Id 'service_install_authority' -Label 'Service install authority' -Ready $InstallAuthority -Reason $(if ($InstallAuthority) { '' } else { 'service_install_authority_not_granted' }) -AuthorityRequired 'service_install'),
  (New-Requirement -Id 'service_control_authority' -Label 'Service control authority' -Ready $ServiceControlAuthority -Reason $(if ($ServiceControlAuthority) { '' } else { 'service_control_authority_not_granted' }) -AuthorityRequired 'service_control'),
  (New-Requirement -Id 'receipt_write_authority' -Label 'Persistent supervision receipt authority' -Ready $ReceiptWriteAuthority -Reason $(if ($ReceiptWriteAuthority) { '' } else { 'receipt_write_authority_not_granted' }) -AuthorityRequired 'receipt_write'),
  (New-Requirement -Id 'resident_claim_authority' -Label 'Resident claim authority' -Ready $ResidentClaimAuthority -Reason $(if ($ResidentClaimAuthority) { '' } else { 'resident_claim_authority_not_granted' }) -AuthorityRequired 'resident_claim')
)

$BlockedRequirements = @($Requirements | Where-Object { -not [bool]$_.ready })
$BlockedRequirementIds = @($BlockedRequirements | ForEach-Object { [string]$_.id })
$Blockers = @(
  $BlockedRequirements | ForEach-Object {
    $Reason = [string]$_.reason
    if (-not [string]::IsNullOrWhiteSpace($Reason)) {
      $Reason
    }
  }
) | Sort-Object -Unique

$Ready = $BlockedRequirements.Count -eq 0
$Payload = [ordered]@{
  ok = $true
  kind = 'lens.host.persistent_supervision_plan'
  status = if ($Ready) { 'ready' } else { 'blocked' }
  mode = $Mode.ToLowerInvariant()
  plan_available = $true
  persistent_supervision_ready = $Ready
  resident_claim_allowed = $false
  config_path = $ConfigRelativePath
  config_present = $ConfigPresent
  host_entrypoint = $HostRelativePath
  host_entrypoint_present = $HostPresent
  service_manager = $ManagerRelativePath
  service_manager_present = $ManagerPresent
  service_name = $ServiceName
  planned_command = ($PlannedCommandParts -join ' ')
  requirements_total = $Requirements.Count
  requirements_ready_total = ($Requirements.Count - $BlockedRequirements.Count)
  requirements_blocked_total = $BlockedRequirements.Count
  requirements = $Requirements
  blocked_requirements = [string[]]$BlockedRequirementIds
  blockers = [string[]]$Blockers
  plan = [ordered]@{
    mode = 'persistent_supervised_resident_host'
    service_name = $ServiceName
    command = ($PlannedCommandParts -join ' ')
    would_install_service = $false
    would_update_service = $false
    would_start_service = $false
    would_restart_process = $false
    would_supervise_process = $false
    would_write_receipt = $false
    would_write_memory = $false
    would_claim_resident = $false
  }
  next_smallest_truthful_gap = if ($Ready) { 'persistent_supervision_execution_boundary' } else { 'persistent_supervision_authority_not_granted' }
  governance = [ordered]@{
    diagnostic_only = $true
    read_only_contract = $true
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Persistent Lens host supervision is planned but blocked; this proof does not install, start, supervise, restart, write receipts, write memory, or claim a resident host.'
}

$Payload | ConvertTo-Json -Depth 8
exit 0
