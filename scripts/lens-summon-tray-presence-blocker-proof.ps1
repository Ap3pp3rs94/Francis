param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [string]$CachedSummonBlockersProofPath = ''
)

$ErrorActionPreference = 'Stop'

function ConvertTo-StringArray {
  param(
    [AllowNull()]
    [object]$Value
  )

  if ($null -eq $Value) {
    return @()
  }

  if ($Value -is [System.Array]) {
    return @($Value | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  }

  $Single = [string]$Value
  if ([string]::IsNullOrWhiteSpace($Single)) {
    return @()
  }
  return @($Single)
}

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

function Get-HandoffById {
  param(
    [AllowNull()]
    [object]$Handoffs,
    [string]$Id
  )

  foreach ($Handoff in @($Handoffs)) {
    if ([string](Get-PropertyValue -Payload $Handoff -Name 'id' -Default '') -eq $Id) {
      return $Handoff
    }
  }
  return $null
}

function Invoke-JsonScript {
  param(
    [Parameter(Mandatory = $true)]
    [string]$PowerShellPath,

    [Parameter(Mandatory = $true)]
    [string]$ScriptPath,

    [string[]]$ScriptArgs = @(),

    [string]$DataRoot = ''
  )

  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
    }
  }

  $HadPreviousDataRoot = Test-Path Env:\FRANCIS_DATA_DIR
  $PreviousDataRoot = [string]$env:FRANCIS_DATA_DIR
  try {
    if (-not [string]::IsNullOrWhiteSpace($DataRoot)) {
      $env:FRANCIS_DATA_DIR = [System.IO.Path]::GetFullPath($DataRoot)
    }
    $Output = & $PowerShellPath -NoProfile -ExecutionPolicy Bypass -File $ScriptPath @ScriptArgs 2>&1
    $ExitCode = $LASTEXITCODE
  } finally {
    if ($HadPreviousDataRoot) {
      $env:FRANCIS_DATA_DIR = $PreviousDataRoot
    } else {
      Remove-Item Env:\FRANCIS_DATA_DIR -ErrorAction SilentlyContinue
    }
  }
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
  }
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

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$SummonBlockersScript = Join-Path $PSScriptRoot 'lens-summon-anywhere-blockers-proof.ps1'
if (-not (Test-Path -LiteralPath $SummonBlockersScript -PathType Leaf)) {
  throw "Lens summon-anywhere blockers proof script is missing: $SummonBlockersScript"
}

$TrayBoundaryScript = Join-Path $PSScriptRoot 'lens-resident-runtime-tray-presence-boundary-proof.ps1'
if (-not (Test-Path -LiteralPath $TrayBoundaryScript -PathType Leaf)) {
  throw "Lens resident runtime tray-presence boundary proof script is missing: $TrayBoundaryScript"
}

$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command powershell -ErrorAction Stop
}
$ChildDataRoot = ''
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $ChildDataRoot = [System.IO.Path]::GetFullPath($DataDir)
}

$SummonResult = [ordered]@{
  exit_code = 0
  payload = $null
  output = ''
  cached = $false
}
if (-not [string]::IsNullOrWhiteSpace($CachedSummonBlockersProofPath)) {
  $ResolvedCachedSummonBlockersProofPath = (Resolve-Path -LiteralPath $CachedSummonBlockersProofPath -ErrorAction Stop).Path
  $SummonResult.payload = Get-Content -LiteralPath $ResolvedCachedSummonBlockersProofPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
  $SummonResult.output = $ResolvedCachedSummonBlockersProofPath
  $SummonResult.cached = $true
} else {
  $SummonResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $SummonBlockersScript -ScriptArgs @('-Mode', 'Status') -DataRoot $ChildDataRoot
}
$SummonPayload = $SummonResult.payload
$ResidentHostSupervisedRuntimeObserved = [bool](
  Get-PropertyValue -Payload $SummonPayload -Name 'resident_host_supervised_runtime_observed' -Default $false
)
$SummonFirstBlockerFamily = [string](Get-PropertyValue -Payload $SummonPayload -Name 'first_blocker_family' -Default '')
$SummonBlockerGroups = Get-PropertyValue -Payload $SummonPayload -Name 'blocker_groups'
$SummonBlockedFamilies = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPayload -Name 'blocked_families' -Default @()
)
$SummonFamilyHandoffs = Get-PropertyValue -Payload $SummonPayload -Name 'blocked_family_handoffs' -Default @()
$ResidentHostFamilyHandoff = Get-HandoffById -Handoffs $SummonFamilyHandoffs -Id 'resident_host'
$ResidentHostFamilyBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $ResidentHostFamilyHandoff -Name 'blockers' -Default @()
)
$SummonTrayPresenceBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonBlockerGroups -Name 'tray_presence' -Default @()
)
$SummonGovernance = Get-PropertyValue -Payload $SummonPayload -Name 'governance'

$TrayBoundaryArgs = @('-Mode', 'Status')
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $TrayBoundaryArgs += @('-DataDir', (Join-Path $DataDir 'proofs\resident-runtime-tray-presence-boundary\data'))
}
$TrayBoundaryResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $TrayBoundaryScript -ScriptArgs $TrayBoundaryArgs -DataRoot $ChildDataRoot
$TrayBoundaryPayload = $TrayBoundaryResult.payload
$TrayBoundaryGovernance = Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'governance'
$TrayPresence = Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'tray_presence'
$TrayPreflight = Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'tray_preflight'
$TrayBoundaryBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'blockers' -Default @()
)

$ResidentHostResolvedByCurrentSummonReadbackObserved = (
  -not ($SummonBlockedFamilies -contains 'resident_host') -and
  @($ResidentHostFamilyBlockers).Count -eq 0
)
$SummonTrayFamilyObserved = (
  [int]$SummonResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'kind' -Default '') -eq 'lens.summon_anywhere_blockers.proof' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'acceptance_criterion' -Default '') -eq 'summon_anywhere' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  (
    (
      -not $ResidentHostSupervisedRuntimeObserved -and
      @($SummonBlockedFamilies).Count -ge 2 -and
      [string]$SummonBlockedFamilies[0] -eq 'resident_host' -and
      [string]$SummonBlockedFamilies[1] -eq 'tray_presence' -and
      $SummonFirstBlockerFamily -eq 'resident_host'
    ) -or
    (
      $ResidentHostResolvedByCurrentSummonReadbackObserved -and
      @($SummonBlockedFamilies).Count -ge 1 -and
      [string]$SummonBlockedFamilies[0] -eq 'tray_presence' -and
      $SummonFirstBlockerFamily -eq 'tray_presence'
    )
  ) -and
  $SummonTrayPresenceBlockers -contains 'tray_host_missing'
)
$ResidentHostContractReadbackObservedLegacy = (
  [string](Get-PropertyValue -Payload $ResidentHostFamilyHandoff -Name 'id' -Default '') -eq 'resident_host' -and
  [string](Get-PropertyValue -Payload $ResidentHostFamilyHandoff -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $ResidentHostFamilyHandoff -Name 'proof_script' -Default '') -eq 'scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $ResidentHostFamilyHandoff -Name 'next_step' -Default '') -eq 'run_resident_host_blocker_proof' -and
  [string](Get-PropertyValue -Payload $ResidentHostFamilyHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_host_runtime_blocker_boundary' -and
  [string](Get-PropertyValue -Payload $ResidentHostFamilyHandoff -Name 'authority_required' -Default '') -eq 'resident_runtime_execution_authority' -and
  -not [bool](Get-PropertyValue -Payload $ResidentHostFamilyHandoff -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $ResidentHostFamilyHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentHostFamilyHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentHostFamilyHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentHostFamilyHandoff -Name 'would_mutate' -Default $true) -and
  $ResidentHostFamilyBlockers -contains 'local_process_launch_authority_not_granted'
)
$ResidentHostResolvedBySupervisionObserved = (
  $ResidentHostSupervisedRuntimeObserved -and
  $SummonFirstBlockerFamily -eq 'tray_presence' -and
  -not ($SummonBlockedFamilies -contains 'resident_host')
)
$ResidentHostContractReadbackObserved = (
  $ResidentHostContractReadbackObservedLegacy -or
  $ResidentHostResolvedByCurrentSummonReadbackObserved
)
$ResidentHostReadbackSource = if ($ResidentHostResolvedBySupervisionObserved) {
  'summon_anywhere_blockers.resident_host_supervised_runtime_observed'
} elseif ($ResidentHostResolvedByCurrentSummonReadbackObserved) {
  'summon_anywhere_blockers.resident_host_no_active_blockers'
} else {
  'summon_anywhere_blockers.blocked_family_handoffs'
}
$ResidentHostReadbackStatus = if ($ResidentHostResolvedBySupervisionObserved) {
  'resolved_by_supervision'
} elseif ($ResidentHostResolvedByCurrentSummonReadbackObserved) {
  'resolved_by_current_summon_readback'
} else {
  [string](Get-PropertyValue -Payload $ResidentHostFamilyHandoff -Name 'status' -Default 'missing')
}
$TrayBoundaryObserved = (
  [int]$TrayBoundaryResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'kind' -Default '') -eq 'lens.resident_runtime.tray_presence_boundary.proof' -and
  [string](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'authority_family' -Default '') -eq 'tray_presence' -and
  [string](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'next_authority_family' -Default '') -eq 'hotkey_summon' -and
  [bool](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'tray_presence_boundary_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'tray_preflight_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'side_effects_denied' -Default $false) -and
  [bool](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'third_authority_family_consumed' -Default $false) -and
  [string](Get-PropertyValue -Payload $TrayPresence -Name 'route' -Default '') -eq '/lens/tray' -and
  $TrayBoundaryBlockers -contains 'tray_registration_authority_not_granted' -and
  $TrayBoundaryBlockers -contains 'tray_icon_authority_not_granted' -and
  $TrayBoundaryBlockers -contains 'notification_authority_not_granted' -and
  $TrayBoundaryBlockers -contains 'tray_host_disabled'
)
$HandoffAligned = (
  $SummonTrayFamilyObserved -and
  $ResidentHostContractReadbackObserved -and
  $TrayBoundaryObserved -and
  $SummonTrayPresenceBlockers -contains 'tray_host_missing' -and
  $TrayBoundaryBlockers -contains 'tray_host_missing' -and
  [string](Get-PropertyValue -Payload $TrayPreflight -Name 'presence_name' -Default '') -eq 'Francis Lens Tray Presence' -and
  [string](Get-PropertyValue -Payload $TrayPreflight -Name 'config_path' -Default '') -eq 'config/runtime/lens/tray.json'
)
$SideEffectsDenied = (
  [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'diagnostic_only' -Default $false) -and
  $ResidentHostContractReadbackObserved -and
  [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'tray_icon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'notification_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'resident_claim_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'mutation_authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'mutation_authority_granted' -Default $true)
)

$Checks = @(
  (New-Check -Id 'summon_tray_presence_family' -Status $(if ($SummonTrayFamilyObserved) { 'current_family_projected' } else { 'missing_or_unexpected' }) -Passed $SummonTrayFamilyObserved -Evidence 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status' -Reason 'The summon-anywhere blocker proof must keep tray_presence as the current blocked acceptance family after resident_host has no active blockers.'),
  (New-Check -Id 'previous_resident_host_contract' -Status $(if ($ResidentHostContractReadbackObserved) { 'previous_family_contract_observed' } else { 'missing_or_unexpected' }) -Passed $ResidentHostContractReadbackObserved -Evidence 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status resident_host readback' -Reason 'The tray-presence handoff should consume either the resident-host family contract or the current no-active-resident-host-blocker readback before moving to tray_presence.'),
  (New-Check -Id 'previous_resident_host_contract_readback' -Status $(if ($ResidentHostContractReadbackObserved) { 'previous_contract_readback_observed' } else { 'missing_or_unexpected' }) -Passed $ResidentHostContractReadbackObserved -Evidence 'summon_anywhere_blockers resident_host readback' -Reason 'The tray-presence proof must preserve the bounded resident-host readback without rerunning the slower resident-host bridge proof.'),
  (New-Check -Id 'tray_presence_boundary' -Status $(if ($TrayBoundaryObserved) { 'blocked_readback_ready' } else { 'missing_or_unexpected' }) -Passed $TrayBoundaryObserved -Evidence 'scripts/lens-resident-runtime-tray-presence-boundary-proof.ps1 -Mode Status' -Reason 'The resident-runtime tray-presence boundary proof must remain blocked and read-only.'),
  (New-Check -Id 'handoff_alignment' -Status $(if ($HandoffAligned) { 'handoff_aligned' } else { 'handoff_mismatch' }) -Passed $HandoffAligned -Evidence 'summon tray_presence blocker group + resident runtime tray boundary proof' -Reason 'The summon tray_presence blocker must map to the direct tray preflight and resident-runtime tray boundary without changing authority.'),
  (New-Check -Id 'side_effects_denied' -Status $(if ($SideEffectsDenied) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $SideEffectsDenied -Evidence 'summon, resident-host family contract, and tray boundary governance payloads' -Reason 'The bridge proof must remain diagnostic/readback only and grant no tray, notification, summon, hotkey, overlay, process, service, memory, approval-decision, or resident-claim authority.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.summon_tray_presence_blocker.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  stage = 'Stage 6 / Lens MVP'
  stage_state = 'active'
  acceptance_criterion = 'summon_anywhere'
  previous_summon_blocker_family = 'resident_host'
  summon_tray_presence_blocker_family = 'tray_presence'
  second_summon_blocker_family = 'tray_presence'
  next_summon_blocker_family = 'overlay_window'
  summon_next_smallest_truthful_gap = 'summon_anywhere_blockers'
  resident_runtime_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'next_smallest_truthful_gap' -Default '')
  next_smallest_truthful_gap = 'summon_overlay_window_blocker_boundary'
  recommended_handoff_source = 'summon_tray_presence_handoff'
  recommended_next_slice = 'run_overlay_window_blocker_proof'
  recommended_proof_script = 'scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status'
  recommended_route = '/lens/overlay'
  recommended_readiness_route = '/lens/overlay/readiness'
  authority_required = 'overlay_control_authority'
  authority_granted = $false
  recommended_handoff = [ordered]@{
    id = 'overlay_window'
    status = 'blocked'
    previous_summon_blocker_family = 'tray_presence'
    next_summon_blocker_family = 'overlay_window'
    next_smallest_truthful_gap = 'summon_overlay_window_blocker_boundary'
    next_step = 'run_overlay_window_blocker_proof'
    proof_script = 'scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status'
    route = '/lens/overlay'
    readiness_route = '/lens/overlay/readiness'
    acceptance_criterion = 'summon_anywhere'
    blocker_family = 'overlay_window'
    authority_required = 'overlay_control_authority'
    authority_granted = $false
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
  }
  summon_tray_family_observed = $SummonTrayFamilyObserved
  previous_resident_host_contract_observed = $ResidentHostContractReadbackObserved
  previous_resident_host_contract_readback_observed = $ResidentHostContractReadbackObserved
  resident_host_resolved_by_supervision = $ResidentHostResolvedBySupervisionObserved
  resident_host_supervised_runtime_observed = $ResidentHostSupervisedRuntimeObserved
  resident_host_current_readback_resolved = $ResidentHostResolvedByCurrentSummonReadbackObserved
  previous_resident_host_contract = [ordered]@{
    source = $ResidentHostReadbackSource
    status = 'contract_projected'
    contract_status = $ResidentHostReadbackStatus
    proof_script = $(if ($ResidentHostResolvedByCurrentSummonReadbackObserved) { 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status' } else { [string](Get-PropertyValue -Payload $ResidentHostFamilyHandoff -Name 'proof_script' -Default '') })
    previous_summon_blocker_family = ''
    summon_resident_host_blocker_family = 'resident_host'
    next_summon_blocker_family = 'tray_presence'
    summon_next_smallest_truthful_gap = 'summon_anywhere_blockers'
    next_smallest_truthful_gap = $(if ($ResidentHostResolvedByCurrentSummonReadbackObserved) { 'summon_tray_presence_blocker_boundary' } else { [string](Get-PropertyValue -Payload $ResidentHostFamilyHandoff -Name 'next_smallest_truthful_gap' -Default '') })
    route = '/lens/host'
    readiness_route = '/lens/host/runtime-loop/readiness'
    authority_required = $(if ($ResidentHostResolvedByCurrentSummonReadbackObserved) { 'none_readback_only' } else { [string](Get-PropertyValue -Payload $ResidentHostFamilyHandoff -Name 'authority_required' -Default '') })
    authority_granted = $(if ($ResidentHostResolvedByCurrentSummonReadbackObserved) { $false } else { [bool](Get-PropertyValue -Payload $ResidentHostFamilyHandoff -Name 'authority_granted' -Default $false) })
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
    handoff_aligned = $ResidentHostContractReadbackObserved
    side_effects_denied = $ResidentHostContractReadbackObserved
    blockers = [string[]]@($(if ($ResidentHostResolvedByCurrentSummonReadbackObserved) { @() } else { $ResidentHostFamilyBlockers }))
  }
  tray_presence_boundary_observed = $TrayBoundaryObserved
  handoff_aligned = $HandoffAligned
  side_effects_denied = $SideEffectsDenied
  summon_tray_presence_blockers = [string[]]@($SummonTrayPresenceBlockers)
  resident_runtime_tray_presence_blockers = [string[]]@($TrayBoundaryBlockers)
  tray_presence_boundary = [ordered]@{
    status = [string](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'status' -Default 'missing')
    authority_family = [string](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'authority_family' -Default '')
    previous_authority_family = [string](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'previous_authority_family' -Default '')
    next_authority_family = [string](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'next_authority_family' -Default '')
    tray_presence_boundary_observed = [bool](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'tray_presence_boundary_observed' -Default $false)
    tray_preflight_observed = [bool](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'tray_preflight_observed' -Default $false)
    side_effects_denied = [bool](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'side_effects_denied' -Default $false)
    third_authority_family_consumed = [bool](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'third_authority_family_consumed' -Default $false)
    route = [string](Get-PropertyValue -Payload $TrayPresence -Name 'route' -Default '')
    tray_preflight_status = [string](Get-PropertyValue -Payload $TrayPreflight -Name 'status' -Default '')
    tray_preflight_presence_name = [string](Get-PropertyValue -Payload $TrayPreflight -Name 'presence_name' -Default '')
    tray_preflight_config_path = [string](Get-PropertyValue -Payload $TrayPreflight -Name 'config_path' -Default '')
    blockers = [string[]]@($TrayBoundaryBlockers)
  }
  checks = @($Checks)
  evidence = @(
    'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status',
    'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status blocked_family_handoffs[resident_host]',
    'scripts/lens-resident-runtime-tray-presence-boundary-proof.ps1 -Mode Status',
    'scripts/lens-tray-preflight.ps1 -Mode Status',
    '/lens/tray'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_summon_anywhere_blockers_proof = $true
    cached_summon_anywhere_blockers_proof = [bool]$SummonResult.cached
    wraps_summon_resident_host_blocker_proof = $false
    uses_resident_host_family_contract_readback = $ResidentHostContractReadbackObservedLegacy
    resident_host_contract_readback = $ResidentHostContractReadbackObservedLegacy
    resident_host_current_readback_resolved = $ResidentHostResolvedByCurrentSummonReadbackObserved
    resident_host_supervised_runtime_readback = $ResidentHostResolvedBySupervisionObserved
    wraps_resident_runtime_tray_presence_boundary_proof = $true
    tray_preflight_readback = [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'tray_preflight_readback' -Default $false)
    read_only_contract = $true
    wrapped_resident_runtime_approval_request_write = [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'approval_request_write' -Default $false)
    wrapped_resident_runtime_execution_authority = [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'resident_runtime_execution_authority' -Default $false)
    approval_request_write = $false
    resident_runtime_execution_authority = $false
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    tray_registration_authority = $false
    tray_icon_authority = $false
    notification_authority = $false
    hotkey_registration_authority = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'The Stage 6 summon-anywhere second blocker family is tray_presence, and this handoff consumes the existing resident-runtime tray-presence boundary proof without granting tray, notification, summon, hotkey, overlay, process, service, memory, approval-decision, or resident-claim authority.'
}

$Payload | ConvertTo-Json -Depth 8
exit $(if ($ProofPassed) { 0 } else { 1 })
