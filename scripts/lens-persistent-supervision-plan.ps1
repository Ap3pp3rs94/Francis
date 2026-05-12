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

function ConvertTo-Number {
  param([AllowNull()][object]$Value)

  if ($null -eq $Value -or $Value -is [bool]) {
    return 0
  }
  try {
    return [double]$Value
  } catch {
    return 0
  }
}

function Get-DataRoot {
  $Override = [string]$env:FRANCIS_DATA_DIR
  if (-not [string]::IsNullOrWhiteSpace($Override)) {
    return $Override
  }
  return (Join-Path $RepoRoot 'data')
}

function Get-LatestActiveHostSupervisionAuthorityGrant {
  param([string]$DataRoot)

  $GrantRoot = Join-Path $DataRoot 'lens/host_supervision_authority_grants'
  if (-not (Test-Path -LiteralPath $GrantRoot -PathType Container)) {
    return $null
  }

  $Now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
  $Candidates = @()
  foreach ($Path in @(Get-ChildItem -LiteralPath $GrantRoot -Filter '*.json' -File -ErrorAction SilentlyContinue)) {
    $Item = Read-JsonFile -Path $Path.FullName
    if ($null -eq $Item) {
      continue
    }
    $Lease = Get-PropertyValue -Payload $Item -Name 'lease' -Default $null
    $Boundary = Get-PropertyValue -Payload $Item -Name 'authority_boundary' -Default $null
    $ExpiresTs = ConvertTo-Number -Value (Get-PropertyValue -Payload $Lease -Name 'expires_ts' -Default (Get-PropertyValue -Payload $Item -Name 'expires_ts' -Default 0))
    if (
      [string](Get-PropertyValue -Payload $Item -Name 'kind' -Default '') -ne 'lens.host.supervision_authority.grant.receipt' -or
      [string](Get-PropertyValue -Payload $Item -Name 'status' -Default '') -ne 'authority_granted' -or
      -not [bool](Get-PropertyValue -Payload $Lease -Name 'active' -Default $false) -or
      -not [bool](Get-PropertyValue -Payload $Boundary -Name 'authority_granted' -Default $false) -or
      $ExpiresTs -le $Now
    ) {
      continue
    }
    $Candidates += $Item
  }

  if ($Candidates.Count -eq 0) {
    return $null
  }
  return @($Candidates | Sort-Object `
    @{Expression = { ConvertTo-Number -Value (Get-PropertyValue -Payload $_ -Name 'created_ts' -Default 0) }; Descending = $true}, `
    @{Expression = { [string](Get-PropertyValue -Payload $_ -Name 'receipt_id' -Default '') }; Descending = $true} `
  )[0]
}

function New-Requirement {
  param(
    [string]$Id,
    [string]$Label,
    [bool]$Ready,
    [string]$Reason,
    [string]$AuthorityRequired = '',
    [bool]$AuthorityGranted = $false
  )

  return [ordered]@{
    id = $Id
    label = $Label
    ready = $Ready
    status = if ($Ready) { 'ready' } else { 'blocked' }
    reason = $Reason
    authority_required = $AuthorityRequired
    authority_granted = $AuthorityGranted
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

function Test-TruthyProperty {
  param(
    [AllowNull()]
    [object]$Payload,
    [string]$Name
  )

  return [bool](Get-PropertyValue -Payload $Payload -Name $Name -Default $false)
}

function ConvertTo-EpochSeconds {
  param([AllowNull()][object]$Value)

  if ($null -eq $Value) {
    return 0.0
  }
  try {
    return [double]$Value
  } catch {
  }
  try {
    return [double]([System.DateTimeOffset]::Parse([string]$Value)).ToUnixTimeSeconds()
  } catch {
    return 0.0
  }
}

function Get-LatestHostSupervisionExecutionReceipt {
  param([string]$DataRoot)

  $ReceiptRoot = Join-Path $DataRoot 'lens/host_supervision_executions'
  if (-not (Test-Path -LiteralPath $ReceiptRoot -PathType Container)) {
    return $null
  }

  $Latest = $null
  $LatestTs = 0.0
  foreach ($File in Get-ChildItem -LiteralPath $ReceiptRoot -Filter '*.json' -File -ErrorAction SilentlyContinue) {
    $Receipt = Read-JsonFile -Path $File.FullName
    if ($null -eq $Receipt) {
      continue
    }
    if ([string](Get-PropertyValue -Payload $Receipt -Name 'kind' -Default '') -ne 'lens.host.supervision.execution.receipt') {
      continue
    }
    $Ts = ConvertTo-EpochSeconds -Value (Get-PropertyValue -Payload $Receipt -Name 'created_ts' -Default 0)
    if ($null -eq $Latest -or $Ts -ge $LatestTs) {
      $Latest = $Receipt
      $LatestTs = $Ts
    }
  }
  return $Latest
}

function Get-ResidentCandidateReadback {
  param([string]$DataRoot)

  $SupervisorStatusPath = Join-Path $DataRoot 'runtime/lens-host-supervisor/status.json'
  $SupervisorStatus = Read-JsonFile -Path $SupervisorStatusPath
  $SupervisorKind = [string](Get-PropertyValue -Payload $SupervisorStatus -Name 'kind' -Default '')
  $SupervisorState = [string](Get-PropertyValue -Payload $SupervisorStatus -Name 'status' -Default '')
  $SupervisorMode = [string](Get-PropertyValue -Payload $SupervisorStatus -Name 'mode' -Default '')
  $SupervisorHostMode = [string](Get-PropertyValue -Payload $SupervisorStatus -Name 'host_mode' -Default '')
  $SupervisorUpdatedAt = [string](Get-PropertyValue -Payload $SupervisorStatus -Name 'updated_at' -Default '')
  $UpdatedTs = ConvertTo-EpochSeconds -Value $SupervisorUpdatedAt
  $FreshWindowSeconds = 900
  $NowTs = [double]([System.DateTimeOffset]::UtcNow.ToUnixTimeSeconds())
  $FreshSupervisorCandidate = (
    $SupervisorKind -eq 'lens.host.supervisor_state' -and
    $SupervisorState -eq 'supervised_session_completed' -and
    $SupervisorMode -eq 'supervise_resident_once' -and
    $SupervisorHostMode -eq 'resident' -and
    $UpdatedTs -gt 0 -and
    (($NowTs - $UpdatedTs) -le $FreshWindowSeconds)
  )

  $Receipt = Get-LatestHostSupervisionExecutionReceipt -DataRoot $DataRoot
  $ReceiptExecution = Get-PropertyValue -Payload $Receipt -Name 'execution' -Default $null
  $ReceiptStatus = [string](Get-PropertyValue -Payload $Receipt -Name 'status' -Default '')
  $ReceiptCandidate = (
    $null -ne $Receipt -and
    $ReceiptStatus -eq 'resident_candidate_supervised_not_persistent' -and
    (Test-TruthyProperty -Payload $ReceiptExecution -Name 'bounded_supervised_session') -and
    (Test-TruthyProperty -Payload $ReceiptExecution -Name 'temporary_host_process_observed') -and
    (Test-TruthyProperty -Payload $ReceiptExecution -Name 'resident_runtime_candidate_supervised') -and
    -not (Test-TruthyProperty -Payload $ReceiptExecution -Name 'resident_supervised_runtime')
  )

  return [ordered]@{
    resident_runtime_candidate_supervised = [bool]($FreshSupervisorCandidate -or $ReceiptCandidate)
    fresh_resident_runtime_candidate_supervised = [bool]$FreshSupervisorCandidate
    supervision_execution_receipt_observed = [bool]$ReceiptCandidate
    supervision_execution_receipt_id = [string](Get-PropertyValue -Payload $Receipt -Name 'receipt_id' -Default '')
    supervision_execution_readback_status = if ($ReceiptCandidate) { 'receipt_observed' } else { 'empty' }
    supervision_execution_next_smallest_truthful_gap = if ($ReceiptCandidate) {
      [string](Get-PropertyValue -Payload $ReceiptExecution -Name 'next_smallest_truthful_gap' -Default 'resident_supervision_not_persistent')
    } else {
      ''
    }
    supervisor_freshness_status = if ($FreshSupervisorCandidate) { 'fresh' } elseif ($null -ne $SupervisorStatus) { 'stale_or_not_candidate' } else { 'missing' }
    supervisor_state_age_seconds = if ($UpdatedTs -gt 0) { [int]([Math]::Max(0, $NowTs - $UpdatedTs)) } else { $null }
  }
}

function Get-HostProcessReadback {
  param([string]$DataRoot)

  $RuntimeRoot = Join-Path $DataRoot 'runtime/lens-host'
  $PidPath = Join-Path $RuntimeRoot 'lens-host.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  $Status = Read-JsonFile -Path $StatusPath
  $StatusKind = [string](Get-PropertyValue -Payload $Status -Name 'kind' -Default '')
  $StatusValue = [string](Get-PropertyValue -Payload $Status -Name 'status' -Default '')
  $StatusPid = [int](Get-PropertyValue -Payload $Status -Name 'pid' -Default 0)
  $HostPid = 0
  if (Test-Path -LiteralPath $PidPath -PathType Leaf) {
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

  $CandidateReadback = Get-ResidentCandidateReadback -DataRoot $DataRoot
  $CandidateObserved = [bool](Get-PropertyValue -Payload $CandidateReadback -Name 'resident_runtime_candidate_supervised' -Default $false)
  $BlockedReason = if ($ProcessAlive) {
    'resident_host_not_supervised'
  } elseif ($CandidateObserved) {
    'resident_supervision_not_persistent'
  } else {
    'resident_host_process_missing'
  }
  $Blocker = if ($ProcessAlive) {
    'resident_host_process_not_supervised'
  } elseif ($CandidateObserved) {
    'resident_supervision_not_persistent'
  } else {
    'resident_host_process_missing'
  }
  $RequirementState = if ($ProcessAlive) {
    'foreground_observed_not_supervised'
  } elseif ($CandidateObserved) {
    'resident_candidate_observed_not_persistent'
  } else {
    'missing'
  }
  $NextGap = if ($CandidateObserved) { 'resident_supervision_not_persistent' } else { 'resident_host_process_not_supervised' }

  return [ordered]@{
    process_alive = $ProcessAlive
    pid = $HostPid
    status_path = $StatusPath
    pid_path = $PidPath
    runtime_status = $StatusValue
    runtime_status_kind = $StatusKind
    runtime_status_pid = $StatusPid
    blocked_reason = $BlockedReason
    blocker = $Blocker
    requirement_state = $RequirementState
    next_smallest_truthful_gap = $NextGap
    resident_runtime_candidate_supervised = [bool](Get-PropertyValue -Payload $CandidateReadback -Name 'resident_runtime_candidate_supervised' -Default $false)
    fresh_resident_runtime_candidate_supervised = [bool](Get-PropertyValue -Payload $CandidateReadback -Name 'fresh_resident_runtime_candidate_supervised' -Default $false)
    supervision_execution_receipt_observed = [bool](Get-PropertyValue -Payload $CandidateReadback -Name 'supervision_execution_receipt_observed' -Default $false)
    supervision_execution_receipt_id = [string](Get-PropertyValue -Payload $CandidateReadback -Name 'supervision_execution_receipt_id' -Default '')
    supervision_execution_readback_status = [string](Get-PropertyValue -Payload $CandidateReadback -Name 'supervision_execution_readback_status' -Default '')
    supervision_execution_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $CandidateReadback -Name 'supervision_execution_next_smallest_truthful_gap' -Default '')
    supervisor_freshness_status = [string](Get-PropertyValue -Payload $CandidateReadback -Name 'supervisor_freshness_status' -Default '')
    supervisor_state_age_seconds = Get-PropertyValue -Payload $CandidateReadback -Name 'supervisor_state_age_seconds' -Default $null
  }
}

function New-EnablementDependency {
  param(
    [string]$Id,
    [string]$Family,
    [string]$Route,
    [string]$ReadinessRoute,
    [bool]$Ready,
    [string]$Blocker,
    [string]$RequirementState,
    [string]$BlockedReason,
    [string]$ProofScript = '',
    [string]$PreflightScript = '',
    [AllowNull()]
    [object]$Extra = $null
  )

  $Dependency = [ordered]@{
    id = $Id
    family = $Family
    route = $Route
    readiness_route = $ReadinessRoute
    proof_script = $ProofScript
    preflight_script = $PreflightScript
    ready = $Ready
    status = if ($Ready) { 'ready' } else { 'blocked' }
    blocker = if ($Ready) { '' } else { $Blocker }
    requirement_state = if ($Ready) { 'ready' } else { $RequirementState }
    blocked_reason = if ($Ready) { '' } else { $BlockedReason }
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
  }

  if ($null -ne $Extra) {
    foreach ($Property in $Extra.PSObject.Properties) {
      $Dependency[$Property.Name] = $Property.Value
    }
  }
  return $Dependency
}

$ConfigRelativePath = 'config/runtime/services/lens-host.json'
$ConfigPath = Join-Path $RepoRoot $ConfigRelativePath
$HostRelativePath = 'scripts/lens-host.ps1'
$HostPath = Join-Path $RepoRoot $HostRelativePath
$ManagerRelativePath = 'scripts/service-install.ps1'
$ManagerPath = Join-Path $RepoRoot $ManagerRelativePath
$TrayConfigRelativePath = 'config/runtime/lens/tray.json'
$SummonConfigRelativePath = 'config/runtime/lens/summon.json'
$OverlayConfigRelativePath = 'config/runtime/lens/overlay.json'
$Config = Read-JsonFile -Path $ConfigPath
$TrayConfig = Read-JsonFile -Path (Join-Path $RepoRoot $TrayConfigRelativePath)
$SummonConfig = Read-JsonFile -Path (Join-Path $RepoRoot $SummonConfigRelativePath)
$OverlayConfig = Read-JsonFile -Path (Join-Path $RepoRoot $OverlayConfigRelativePath)
$DataRoot = Get-DataRoot
$ActiveAuthorityGrant = Get-LatestActiveHostSupervisionAuthorityGrant -DataRoot $DataRoot
$GrantAuthorities = Get-PropertyValue -Payload $ActiveAuthorityGrant -Name 'authorities' -Default $null
$AuthorityGrantActive = $null -ne $ActiveAuthorityGrant

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
$ProcessRestartAuthority = [bool](
  (Get-PropertyValue -Payload $Config -Name 'process_restart_authority' -Default $false) -or
  (Get-PropertyValue -Payload $GrantAuthorities -Name 'process_restart_authority' -Default $false)
)
$InstallAuthority = [bool](
  (Get-PropertyValue -Payload $Config -Name 'install_authority' -Default $false) -or
  (Get-PropertyValue -Payload $Config -Name 'service_install_authority' -Default $false) -or
  (Get-PropertyValue -Payload $GrantAuthorities -Name 'service_install_authority' -Default $false)
)
$ServiceControlAuthority = [bool](
  (Get-PropertyValue -Payload $Config -Name 'service_control_authority' -Default $false) -or
  (Get-PropertyValue -Payload $GrantAuthorities -Name 'service_control_authority' -Default $false)
)
$ReceiptWriteAuthority = [bool](
  (Get-PropertyValue -Payload $Config -Name 'receipt_write_authority' -Default $false) -or
  (Get-PropertyValue -Payload $GrantAuthorities -Name 'receipt_write_authority' -Default $false)
)
$ResidentClaimAuthority = [bool](
  (Get-PropertyValue -Payload $Config -Name 'resident_claim_authority' -Default $false) -or
  (Get-PropertyValue -Payload $GrantAuthorities -Name 'resident_claim_authority' -Default $false)
)

$Requirements = @(
  (New-Requirement -Id 'service_config' -Label 'Lens host service config' -Ready $ConfigPresent -Reason $(if ($ConfigPresent) { '' } else { 'service_config_missing' })),
  (New-Requirement -Id 'host_entrypoint' -Label 'Lens host entrypoint' -Ready $HostPresent -Reason $(if ($HostPresent) { '' } else { 'host_entrypoint_missing' })),
  (New-Requirement -Id 'service_manager' -Label 'Service manager script' -Ready $ManagerPresent -Reason $(if ($ManagerPresent) { '' } else { 'service_manager_missing' })),
  (New-Requirement -Id 'process_supervision_enabled' -Label 'Process supervision enabled' -Ready $ProcessSupervisionEnabled -Reason $(if ($ProcessSupervisionEnabled) { '' } else { 'process_supervision_disabled' }) -AuthorityRequired 'process_supervision'),
  (New-Requirement -Id 'persistent_supervision_enabled' -Label 'Persistent supervision enabled' -Ready $PersistentSupervisionEnabled -Reason $(if ($PersistentSupervisionEnabled) { '' } else { 'persistent_supervision_disabled' }) -AuthorityRequired 'persistent_supervision'),
  (New-Requirement -Id 'process_restart_authority' -Label 'Process restart authority' -Ready $ProcessRestartAuthority -Reason $(if ($ProcessRestartAuthority) { '' } else { 'process_restart_authority_not_granted' }) -AuthorityRequired 'process_restart' -AuthorityGranted $ProcessRestartAuthority),
  (New-Requirement -Id 'service_install_authority' -Label 'Service install authority' -Ready $InstallAuthority -Reason $(if ($InstallAuthority) { '' } else { 'service_install_authority_not_granted' }) -AuthorityRequired 'service_install' -AuthorityGranted $InstallAuthority),
  (New-Requirement -Id 'service_control_authority' -Label 'Service control authority' -Ready $ServiceControlAuthority -Reason $(if ($ServiceControlAuthority) { '' } else { 'service_control_authority_not_granted' }) -AuthorityRequired 'service_control' -AuthorityGranted $ServiceControlAuthority),
  (New-Requirement -Id 'receipt_write_authority' -Label 'Persistent supervision receipt authority' -Ready $ReceiptWriteAuthority -Reason $(if ($ReceiptWriteAuthority) { '' } else { 'receipt_write_authority_not_granted' }) -AuthorityRequired 'receipt_write' -AuthorityGranted $ReceiptWriteAuthority),
  (New-Requirement -Id 'resident_claim_authority' -Label 'Resident claim authority' -Ready $ResidentClaimAuthority -Reason $(if ($ResidentClaimAuthority) { '' } else { 'resident_claim_authority_not_granted' }) -AuthorityRequired 'resident_claim' -AuthorityGranted $ResidentClaimAuthority)
)

$HostProcessReadback = Get-HostProcessReadback -DataRoot $DataRoot
$HostProcessProofScript = if ([string]$HostProcessReadback.blocker -eq 'resident_supervision_not_persistent') {
  'scripts/lens-resident-supervision-persistence-boundary-proof.ps1 -Mode Status'
} else {
  'scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status'
}
$TrayReady = (
  (Test-TruthyProperty -Payload $TrayConfig -Name 'enabled') -and
  (Test-TruthyProperty -Payload $TrayConfig -Name 'tray_host_enabled') -and
  (Test-TruthyProperty -Payload $TrayConfig -Name 'tray_icon_enabled') -and
  (Test-TruthyProperty -Payload $TrayConfig -Name 'startup_register') -and
  (Test-TruthyProperty -Payload $TrayConfig -Name 'tray_registration_authority') -and
  (Test-TruthyProperty -Payload $TrayConfig -Name 'tray_icon_authority')
)
$GlobalHotkeyReady = (
  (Test-TruthyProperty -Payload $SummonConfig -Name 'enabled') -and
  (Test-TruthyProperty -Payload $SummonConfig -Name 'binding_enabled') -and
  (Test-TruthyProperty -Payload $SummonConfig -Name 'register_hotkey') -and
  (Test-TruthyProperty -Payload $SummonConfig -Name 'startup_register') -and
  (Test-TruthyProperty -Payload $SummonConfig -Name 'hotkey_registration_authority')
)
$OverlayReady = (
  (Test-TruthyProperty -Payload $OverlayConfig -Name 'enabled') -and
  (Test-TruthyProperty -Payload $OverlayConfig -Name 'window_enabled') -and
  (Test-TruthyProperty -Payload $OverlayConfig -Name 'overlay_control_authority') -and
  (Test-TruthyProperty -Payload $OverlayConfig -Name 'window_management_authority')
)
$SummonReady = (
  (Test-TruthyProperty -Payload $SummonConfig -Name 'enabled') -and
  (Test-TruthyProperty -Payload $SummonConfig -Name 'binding_enabled') -and
  (Test-TruthyProperty -Payload $SummonConfig -Name 'summon_authority') -and
  (Test-TruthyProperty -Payload $SummonConfig -Name 'local_process_launch_authority') -and
  $TrayReady -and
  $OverlayReady
)
$RequiredBeforeEnable = @(
  'resident_host_process',
  'tray_presence',
  'global_hotkey_binding',
  'overlay_window',
  'summon_binding'
)
$EnablementDependencyReadback = @(
  (New-EnablementDependency -Id 'resident_host_process' -Family 'resident_host' -Route '/lens/host' -ReadinessRoute '/lens/host/runtime-loop/readiness' -Ready $false -Blocker ([string]$HostProcessReadback.blocker) -RequirementState ([string]$HostProcessReadback.requirement_state) -BlockedReason ([string]$HostProcessReadback.blocked_reason) -ProofScript $HostProcessProofScript -Extra ([pscustomobject]@{
        process_alive = [bool]$HostProcessReadback.process_alive
        pid = [int]$HostProcessReadback.pid
        runtime_status = [string]$HostProcessReadback.runtime_status
        next_smallest_truthful_gap = [string]$HostProcessReadback.next_smallest_truthful_gap
        resident_runtime_candidate_supervised = [bool]$HostProcessReadback.resident_runtime_candidate_supervised
        fresh_resident_runtime_candidate_supervised = [bool]$HostProcessReadback.fresh_resident_runtime_candidate_supervised
        supervision_execution_receipt_observed = [bool]$HostProcessReadback.supervision_execution_receipt_observed
        supervision_execution_receipt_id = [string]$HostProcessReadback.supervision_execution_receipt_id
        supervision_execution_readback_status = [string]$HostProcessReadback.supervision_execution_readback_status
        supervision_execution_next_smallest_truthful_gap = [string]$HostProcessReadback.supervision_execution_next_smallest_truthful_gap
        supervisor_freshness_status = [string]$HostProcessReadback.supervisor_freshness_status
        supervisor_state_age_seconds = $HostProcessReadback.supervisor_state_age_seconds
      })),
  (New-EnablementDependency -Id 'tray_presence' -Family 'tray_presence' -Route '/lens/tray' -ReadinessRoute '/lens/tray/readiness' -Ready $TrayReady -Blocker 'tray_host_missing' -RequirementState 'tray_host_disabled' -BlockedReason ([string](Get-PropertyValue -Payload $TrayConfig -Name 'blocked_reason' -Default 'lens_tray_presence_disabled_pending_authority')) -PreflightScript 'scripts/lens-tray-preflight.ps1 -Mode Status' -Extra ([pscustomobject]@{
        config_path = $TrayConfigRelativePath
        config_exists = $null -ne $TrayConfig
        tray_host_enabled = (Test-TruthyProperty -Payload $TrayConfig -Name 'tray_host_enabled')
        tray_icon_enabled = (Test-TruthyProperty -Payload $TrayConfig -Name 'tray_icon_enabled')
        tray_registration_authority = (Test-TruthyProperty -Payload $TrayConfig -Name 'tray_registration_authority')
        tray_icon_authority = (Test-TruthyProperty -Payload $TrayConfig -Name 'tray_icon_authority')
      })),
  (New-EnablementDependency -Id 'global_hotkey_binding' -Family 'global_hotkey_binding' -Route '/lens/summon' -ReadinessRoute '/lens/summon/readiness' -Ready $GlobalHotkeyReady -Blocker 'global_hotkey_binding_missing' -RequirementState 'binding_disabled' -BlockedReason 'global_hotkey_binding_disabled' -PreflightScript 'scripts/lens-summon-preflight.ps1 -Mode Status' -Extra ([pscustomobject]@{
        config_path = $SummonConfigRelativePath
        config_exists = $null -ne $SummonConfig
        global_hotkey = [string](Get-PropertyValue -Payload $SummonConfig -Name 'global_hotkey' -Default '')
        binding_enabled = (Test-TruthyProperty -Payload $SummonConfig -Name 'binding_enabled')
        register_hotkey = (Test-TruthyProperty -Payload $SummonConfig -Name 'register_hotkey')
        hotkey_registration_authority = (Test-TruthyProperty -Payload $SummonConfig -Name 'hotkey_registration_authority')
      })),
  (New-EnablementDependency -Id 'overlay_window' -Family 'overlay_window' -Route '/lens/overlay' -ReadinessRoute '/lens/overlay/readiness' -Ready $OverlayReady -Blocker 'overlay_window_missing' -RequirementState 'window_disabled' -BlockedReason ([string](Get-PropertyValue -Payload $OverlayConfig -Name 'blocked_reason' -Default 'lens_overlay_window_not_implemented')) -PreflightScript 'scripts/lens-overlay-preflight.ps1 -Mode Status' -Extra ([pscustomobject]@{
        config_path = $OverlayConfigRelativePath
        config_exists = $null -ne $OverlayConfig
        window_enabled = (Test-TruthyProperty -Payload $OverlayConfig -Name 'window_enabled')
        overlay_control_authority = (Test-TruthyProperty -Payload $OverlayConfig -Name 'overlay_control_authority')
        window_management_authority = (Test-TruthyProperty -Payload $OverlayConfig -Name 'window_management_authority')
      })),
  (New-EnablementDependency -Id 'summon_binding' -Family 'summon_binding' -Route '/lens/summon' -ReadinessRoute '/lens/summon/readiness' -Ready $SummonReady -Blocker 'summon_binding_missing' -RequirementState 'disabled_pending_authority' -BlockedReason ([string](Get-PropertyValue -Payload $SummonConfig -Name 'blocked_reason' -Default 'lens_summon_binding_disabled_pending_authority')) -PreflightScript 'scripts/lens-summon-preflight.ps1 -Mode Status' -Extra ([pscustomobject]@{
        config_path = $SummonConfigRelativePath
        config_exists = $null -ne $SummonConfig
        summon_runner = [string](Get-PropertyValue -Payload $SummonConfig -Name 'summon_runner' -Default 'scripts/lens-summon.ps1')
        local_palette_launcher = [string](Get-PropertyValue -Payload $SummonConfig -Name 'local_palette_launcher' -Default 'scripts/lens-command-palette.ps1 -Mode LocalOpen')
        summon_enabled = (Test-TruthyProperty -Payload $SummonConfig -Name 'enabled')
        binding_enabled = (Test-TruthyProperty -Payload $SummonConfig -Name 'binding_enabled')
        summon_authority = (Test-TruthyProperty -Payload $SummonConfig -Name 'summon_authority')
        local_process_launch_authority = (Test-TruthyProperty -Payload $SummonConfig -Name 'local_process_launch_authority')
      }))
)
$MissingRequiredBeforeEnable = [string[]]@($EnablementDependencyReadback | Where-Object { -not [bool]$_.ready } | ForEach-Object { [string]$_.id })
$FirstMissingRequirementHandoff = $EnablementDependencyReadback | Where-Object { -not [bool]$_.ready } | Select-Object -First 1
$RequiredBeforeEnableReady = $MissingRequiredBeforeEnable.Count -eq 0
$RequiredBeforeEnableGuardNextGap = if ($RequiredBeforeEnableReady) {
  'persistent_supervision_enablement_readiness'
} else {
  'persistent_supervision_required_prerequisites_missing'
}

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
if (-not $RequiredBeforeEnableReady) {
  $Blockers = @($Blockers + @('persistent_supervision_required_prerequisites_missing') | Sort-Object -Unique)
}

$Ready = $BlockedRequirements.Count -eq 0 -and $RequiredBeforeEnableReady
$AuthorityRequirementIds = @(
  'process_restart_authority',
  'service_install_authority',
  'service_control_authority',
  'receipt_write_authority',
  'resident_claim_authority'
)
$AuthorityBlocked = @($BlockedRequirementIds | Where-Object { $AuthorityRequirementIds -contains $_ }).Count -gt 0
$NextSmallestTruthfulGap = if ($Ready) {
  'persistent_supervision_execution_boundary'
} elseif (-not $RequiredBeforeEnableReady) {
  'persistent_supervision_required_prerequisites_missing'
} elseif (-not $AuthorityBlocked) {
  'persistent_supervision_execution_boundary'
} else {
  'persistent_supervision_authority_not_granted'
}
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
  data_root = $DataRoot
  authority_grant_active = $AuthorityGrantActive
  authority_grant_route = '/lens/host/supervision/authority'
  authority_grants_route = '/lens/host/supervision/authority/grants'
  authority_grant_receipt_id = [string](Get-PropertyValue -Payload $ActiveAuthorityGrant -Name 'receipt_id' -Default '')
  requirements_total = $Requirements.Count
  requirements_ready_total = ($Requirements.Count - $BlockedRequirements.Count)
  requirements_blocked_total = $BlockedRequirements.Count
  requirements = $Requirements
  blocked_requirements = [string[]]$BlockedRequirementIds
  required_before_enable_ready = $RequiredBeforeEnableReady
  required_before_enable = [string[]]$RequiredBeforeEnable
  missing_required_before_enable = [string[]]$MissingRequiredBeforeEnable
  first_missing_required_before_enable = [string](Get-PropertyValue -Payload $FirstMissingRequirementHandoff -Name 'id' -Default '')
  first_missing_requirement_handoff = $FirstMissingRequirementHandoff
  enablement_dependency_readback = @($EnablementDependencyReadback)
  required_before_enable_guard_next_smallest_truthful_gap = $RequiredBeforeEnableGuardNextGap
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
  next_smallest_truthful_gap = $NextSmallestTruthfulGap
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
