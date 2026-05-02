[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(2, 30)]
  [int]$ForegroundRunSeconds = 2,

  [ValidateRange(2, 30)]
  [int]$HostLaunchRunSeconds = 3
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

function Get-PowerShellPath {
  try {
    $Current = Get-Process -Id $PID -ErrorAction Stop
    if (-not [string]::IsNullOrWhiteSpace([string]$Current.Path)) {
      return [string]$Current.Path
    }
  } catch {
  }

  $Pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
  if ($null -ne $Pwsh) {
    return [string]$Pwsh.Source
  }
  $WindowsPowerShell = Get-Command powershell -ErrorAction SilentlyContinue
  if ($null -ne $WindowsPowerShell) {
    return [string]$WindowsPowerShell.Source
  }
  return ''
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

function ConvertTo-StringArray {
  param(
    [AllowNull()]
    [object]$Value
  )

  if ($null -eq $Value) {
    return @()
  }
  if ($Value -is [string]) {
    if ([string]::IsNullOrWhiteSpace($Value)) {
      return @()
    }
    return @($Value)
  }
  if ($Value -is [System.Array]) {
    return @($Value | ForEach-Object {
        $Item = [string]$_
        if (-not [string]::IsNullOrWhiteSpace($Item)) {
          $Item
        }
      })
  }
  $SingleValue = [string]$Value
  if ([string]::IsNullOrWhiteSpace($SingleValue)) {
    return @()
  }
  return @($SingleValue)
}

function Invoke-JsonScript {
  param(
    [Parameter(Mandatory = $true)]
    [string]$PowerShellPath,

    [Parameter(Mandatory = $true)]
    [string]$ScriptPath,

    [string[]]$ScriptArgs = @()
  )

  if ([string]::IsNullOrWhiteSpace($PowerShellPath) -or -not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
    }
  }

  $Output = & $PowerShellPath -NoProfile -ExecutionPolicy Bypass -File $ScriptPath @ScriptArgs 2>&1
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

$SummonResidentHostProofPath = Join-Path $PSScriptRoot 'lens-summon-resident-host-blocker-proof.ps1'
$HostSupervisionProofPath = Join-Path $PSScriptRoot 'lens-host-supervision-proof.ps1'
$PowerShellPath = Get-PowerShellPath

$SummonResidentHostResult = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $SummonResidentHostProofPath -ScriptArgs @('-Mode', 'Status')
$HostSupervisionResult = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $HostSupervisionProofPath -ScriptArgs @(
  '-Mode', 'Status',
  '-ForegroundRunSeconds', [string]$ForegroundRunSeconds,
  '-HostLaunchRunSeconds', [string]$HostLaunchRunSeconds
)

$SummonResidentHostPayload = Get-PropertyValue -Payload $SummonResidentHostResult -Name 'payload'
$HostSupervisionPayload = Get-PropertyValue -Payload $HostSupervisionResult -Name 'payload'
$SummonGovernance = Get-PropertyValue -Payload $SummonResidentHostPayload -Name 'governance'
$HostGovernance = Get-PropertyValue -Payload $HostSupervisionPayload -Name 'governance'
$HostProof = Get-PropertyValue -Payload $HostSupervisionPayload -Name 'proof'
$HostBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostSupervisionPayload -Name 'blockers' -Default @())
$SummonRuntimeBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $SummonResidentHostPayload -Name 'resident_host_runtime_blockers' -Default @())
$SummonSurfaceBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $SummonResidentHostPayload -Name 'resident_host_surface_blockers' -Default @())

$RuntimeHandoffObserved = (
  [int](Get-PropertyValue -Payload $SummonResidentHostResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $SummonResidentHostPayload -Name 'kind' -Default '') -eq 'lens.summon_resident_host_blocker.proof' -and
  [string](Get-PropertyValue -Payload $SummonResidentHostPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $SummonResidentHostPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_host_runtime_blocker_boundary' -and
  [string](Get-PropertyValue -Payload $SummonResidentHostPayload -Name 'first_summon_blocker_family' -Default '') -eq 'resident_host'
)
$BoundedRuntimeObserved = (
  [int](Get-PropertyValue -Payload $HostSupervisionResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'kind' -Default '') -eq 'lens.host.supervision_readiness_proof' -and
  [string](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'bounded_host_launch_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'foreground_process_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'resident_host_process_state' -Default '') -eq 'foreground_observed_not_supervised'
)
$RuntimeBoundaryBlocked = (
  $RuntimeHandoffObserved -and
  $BoundedRuntimeObserved -and
  $SummonRuntimeBlockers -contains 'lens_host_runtime_not_implemented' -and
  $HostBlockers -contains 'lens_host_runtime_not_implemented' -and
  $HostBlockers -contains 'resident_host_process_not_supervised' -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'supervision_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'ready_for_resident_claim' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'resident_claim_allowed' -Default $true)
)
$ProcessSupervisionHandoffObserved = (
  [string](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_host_process_not_supervised' -and
  [string](Get-PropertyValue -Payload $HostProof -Name 'process_supervision_status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $HostProof -Name 'service_control_status' -Default '') -eq 'blocked'
)
$SideEffectsBounded = (
  [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostGovernance -Name 'bounded_host_launch' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostGovernance -Name 'bounded_process_launch' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostGovernance -Name 'temporary_runtime_state_write' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostGovernance -Name 'local_process_launch_authority' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'api_local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'product_execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'process_supervision_authority' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'process_restart_authority' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'service_install_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'capture_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'new_sensing_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'resident_claim_authority' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'mutation_authority_granted' -Default $true)
)

$Checks = @(
  (New-Check -Id 'resident_host_runtime_handoff' -Status $(if ($RuntimeHandoffObserved) { 'handoff_consumed' } else { 'missing_or_unexpected' }) -Passed $RuntimeHandoffObserved -Evidence 'scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status' -Reason 'The previous resident-host handoff must point at the runtime blocker boundary.'),
  (New-Check -Id 'bounded_runtime_observation' -Status $(if ($BoundedRuntimeObserved) { 'foreground_observed_not_supervised' } else { 'not_observed' }) -Passed $BoundedRuntimeObserved -Evidence 'scripts/lens-host-supervision-proof.ps1 -Mode Status' -Reason 'The runtime boundary must distinguish a bounded foreground observation from a resident supervised host.'),
  (New-Check -Id 'runtime_boundary_blocked' -Status $(if ($RuntimeBoundaryBlocked) { 'blocked' } else { 'unexpected_ready' }) -Passed $RuntimeBoundaryBlocked -Evidence 'runtime blockers + host supervision proof blockers' -Reason 'The resident host runtime remains blocked by missing runtime implementation and unsupervised process state.'),
  (New-Check -Id 'process_supervision_handoff' -Status $(if ($ProcessSupervisionHandoffObserved) { 'next_blocker_identified' } else { 'missing_or_unexpected' }) -Passed $ProcessSupervisionHandoffObserved -Evidence 'host supervision proof next_smallest_truthful_gap' -Reason 'After consuming the runtime boundary, the next concrete blocker is process supervision.'),
  (New-Check -Id 'side_effects_bounded' -Status $(if ($SideEffectsBounded) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $SideEffectsBounded -Evidence 'summon resident-host governance + host supervision governance' -Reason 'The proof may observe one bounded diagnostic host run but must not grant product/API launch, execution, supervision, service, summon, memory, approval, or resident-claim authority.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })
$BlockerBag = @()
$BlockerBag += @($SummonRuntimeBlockers)
$BlockerBag += @($SummonSurfaceBlockers)
$BlockerBag += @($HostBlockers)
$BlockerBag += @(
  'resident_host_runtime_blocker_boundary_consumed',
  'resident_host_process_not_supervised',
  'process_supervision_authority_not_granted',
  'process_restart_authority_not_granted'
)
$AllBlockers = [string[]]@($BlockerBag | Sort-Object -Unique)

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.resident_host.runtime_blocker_boundary.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  stage = 'Stage 6 / Lens MVP'
  stage_state = 'active'
  acceptance_criterion = 'summon_anywhere'
  previous_next_smallest_truthful_gap = 'resident_host_runtime_blocker_boundary'
  next_smallest_truthful_gap = 'resident_host_process_not_supervised'
  runtime_handoff_observed = $RuntimeHandoffObserved
  bounded_runtime_observed = $BoundedRuntimeObserved
  runtime_boundary_blocked = $RuntimeBoundaryBlocked
  process_supervision_handoff_observed = $ProcessSupervisionHandoffObserved
  side_effects_bounded = $SideEffectsBounded
  foreground_run_seconds = [Math]::Max($ForegroundRunSeconds, 5)
  requested_foreground_run_seconds = $ForegroundRunSeconds
  host_launch_run_seconds = $HostLaunchRunSeconds
  resident_host_process_state = [string](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'resident_host_process_state' -Default '')
  resident_host_process_blocker = [string](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'resident_host_process_blocker' -Default '')
  resident_runtime_ready = $false
  supervision_ready = $false
  ready_for_resident_claim = $false
  resident_claim_allowed = $false
  resident_host_process = $false
  resident_host_supervised = $false
  service_managed = $false
  tray_presence = $false
  global_hotkey = $false
  overlay_window = $false
  summon_anywhere = $false
  checks = @($Checks)
  blockers = $AllBlockers
  proof = [ordered]@{
    summon_resident_host_status = [string](Get-PropertyValue -Payload $SummonResidentHostPayload -Name 'status' -Default '')
    summon_resident_host_next_gap = [string](Get-PropertyValue -Payload $SummonResidentHostPayload -Name 'next_smallest_truthful_gap' -Default '')
    host_supervision_status = [string](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'status' -Default '')
    bounded_host_launch_observed = [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'bounded_host_launch_observed' -Default $false)
    foreground_process_observed = [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'foreground_process_observed' -Default $false)
    host_supervision_next_gap = [string](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'next_smallest_truthful_gap' -Default '')
    process_supervision_status = [string](Get-PropertyValue -Payload $HostProof -Name 'process_supervision_status' -Default '')
    service_control_status = [string](Get-PropertyValue -Payload $HostProof -Name 'service_control_status' -Default '')
    host_ready_for_resident_claim = [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'ready_for_resident_claim' -Default $false)
  }
  evidence = @(
    'scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status',
    'scripts/lens-host-supervision-proof.ps1 -Mode Status',
    'scripts/lens-host-launch-proof.ps1 -Mode Status',
    'scripts/lens-host-foreground-proof.ps1 -Mode Status'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_summon_resident_host_blocker_proof = $true
    wraps_host_supervision_proof = $true
    bounded_local_process_launch = $true
    bounded_process_launch = $true
    temporary_runtime_state_write = $true
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    local_process_launch_authority = $true
    api_local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'The resident-host runtime blocker boundary is consumed as a diagnostic proof: Francis can observe one bounded foreground host run, but the resident runtime remains blocked by missing implementation and unsupervised process state.'
}

$Payload | ConvertTo-Json -Depth 10
exit $(if ($ProofPassed) { 0 } else { 1 })
