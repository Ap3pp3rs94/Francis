param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status'
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

function Invoke-JsonScript {
  param(
    [Parameter(Mandatory = $true)]
    [string]$PowerShellPath,

    [Parameter(Mandatory = $true)]
    [string]$ScriptPath,

    [string[]]$ScriptArgs = @()
  )

  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
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

$SummonBlockersScript = Join-Path $PSScriptRoot 'lens-summon-anywhere-blockers-proof.ps1'
if (-not (Test-Path -LiteralPath $SummonBlockersScript -PathType Leaf)) {
  throw "Lens summon-anywhere blockers proof script is missing: $SummonBlockersScript"
}

$HostLifecycleProofScript = Join-Path $PSScriptRoot 'lens-resident-host-lifecycle-blockers-proof.ps1'
if (-not (Test-Path -LiteralPath $HostLifecycleProofScript -PathType Leaf)) {
  throw "Lens resident-host lifecycle blockers proof script is missing: $HostLifecycleProofScript"
}

$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command powershell -ErrorAction Stop
}

$SummonResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $SummonBlockersScript -ScriptArgs @('-Mode', 'Status')
$SummonPayload = $SummonResult.payload
$SummonBlockerGroups = Get-PropertyValue -Payload $SummonPayload -Name 'blocker_groups'
$SummonResidentHostBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonBlockerGroups -Name 'resident_host' -Default @()
)
$SummonBlockedFamilies = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPayload -Name 'blocked_families' -Default @()
)
$SummonGovernance = Get-PropertyValue -Payload $SummonPayload -Name 'governance'

$HostResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $HostLifecycleProofScript -ScriptArgs @('-Mode', 'Status')
$HostPayload = $HostResult.payload
$HostLifecycleGroups = Get-PropertyValue -Payload $HostPayload -Name 'lifecycle_blocker_groups'
$HostRuntimeGroup = Get-PropertyValue -Payload $HostLifecycleGroups -Name 'runtime'
$HostRuntimeBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $HostRuntimeGroup -Name 'blockers' -Default @()
)
$HostProcessReadbackGroup = Get-PropertyValue -Payload $HostLifecycleGroups -Name 'process_readback'
$HostProcessReadbackBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $HostProcessReadbackGroup -Name 'blockers' -Default @()
)
$HostSurfaceGroup = Get-PropertyValue -Payload $HostLifecycleGroups -Name 'surface_dependencies'
$HostSurfaceBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $HostSurfaceGroup -Name 'blockers' -Default @()
)
$HostGovernance = Get-PropertyValue -Payload $HostPayload -Name 'governance'

$SummonFirstFamilyObserved = (
  [int]$SummonResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'kind' -Default '') -eq 'lens.summon_anywhere_blockers.proof' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'first_blocker_family' -Default '') -eq 'resident_host' -and
  @($SummonBlockedFamilies).Count -gt 0 -and
  [string]$SummonBlockedFamilies[0] -eq 'resident_host' -and
  $SummonResidentHostBlockers -contains 'local_process_launch_authority_not_granted' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers'
)
$HostLifecycleObserved = (
  [int]$HostResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $HostPayload -Name 'kind' -Default '') -eq 'lens.resident_host.lifecycle_blockers_proof' -and
  [string](Get-PropertyValue -Payload $HostPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $HostPayload -Name 'first_blocker_group' -Default '') -eq 'runtime' -and
  [string](Get-PropertyValue -Payload $HostPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_host_runtime_blocker_boundary' -and
  $HostRuntimeBlockers -contains 'lens_host_runtime_not_implemented'
)
$HandoffAligned = (
  $SummonFirstFamilyObserved -and
  $HostLifecycleObserved -and
  $HostSurfaceBlockers -contains 'tray_host_missing' -and
  $HostSurfaceBlockers -contains 'global_hotkey_binding_missing' -and
  $HostSurfaceBlockers -contains 'overlay_window_missing' -and
  $HostSurfaceBlockers -contains 'summon_binding_missing'
)
$SideEffectsDenied = (
  [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostGovernance -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'process_supervision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'resident_claim_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'mutation_authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'mutation_authority_granted' -Default $true)
)

$Checks = @(
  (New-Check -Id 'summon_first_family' -Status $(if ($SummonFirstFamilyObserved) { 'resident_host_first' } else { 'missing_or_unexpected' }) -Passed $SummonFirstFamilyObserved -Evidence 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status' -Reason 'The summon-anywhere blocker proof must name resident_host as the first blocked acceptance family.'),
  (New-Check -Id 'resident_host_lifecycle_proof' -Status $(if ($HostLifecycleObserved) { 'runtime_blocked' } else { 'missing_or_unexpected' }) -Passed $HostLifecycleObserved -Evidence 'scripts/lens-resident-host-lifecycle-blockers-proof.ps1 -Mode Status' -Reason 'The resident-host lifecycle proof must consume the first family and point to the runtime blocker boundary.'),
  (New-Check -Id 'handoff_alignment' -Status $(if ($HandoffAligned) { 'handoff_aligned' } else { 'handoff_mismatch' }) -Passed $HandoffAligned -Evidence 'summon resident_host family + host lifecycle blocker groups' -Reason 'The first summon-anywhere family must map into host runtime/process/surface blockers without changing authority.'),
  (New-Check -Id 'side_effects_denied' -Status $(if ($SideEffectsDenied) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $SideEffectsDenied -Evidence 'summon and host governance payloads' -Reason 'The bridge proof must remain diagnostic/readback only and grant no launch, service, summon, memory, approval-decision, or resident-claim authority.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.summon_resident_host_blocker.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  stage = 'Stage 6 / Lens MVP'
  stage_state = 'active'
  acceptance_criterion = 'summon_anywhere'
  first_summon_blocker_family = 'resident_host'
  summon_next_smallest_truthful_gap = 'summon_anywhere_blockers'
  resident_host_next_smallest_truthful_gap = 'resident_host_runtime_blocker_boundary'
  next_smallest_truthful_gap = 'resident_host_runtime_blocker_boundary'
  summon_first_family_observed = $SummonFirstFamilyObserved
  resident_host_lifecycle_observed = $HostLifecycleObserved
  handoff_aligned = $HandoffAligned
  side_effects_denied = $SideEffectsDenied
  summon_resident_host_blockers = [string[]]@($SummonResidentHostBlockers)
  resident_host_runtime_blockers = [string[]]@($HostRuntimeBlockers)
  resident_host_process_readback_blockers = [string[]]@($HostProcessReadbackBlockers)
  resident_host_surface_blockers = [string[]]@($HostSurfaceBlockers)
  checks = @($Checks)
  evidence = @(
    'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status',
    'scripts/lens-resident-host-lifecycle-blockers-proof.ps1 -Mode Status',
    'scripts/lens-host-preflight.ps1 -Mode Status',
    'config/runtime/services/lens-host.json'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_summon_anywhere_blockers_proof = $true
    wraps_resident_host_lifecycle_blockers_proof = $true
    read_only_contract = $true
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'The Stage 6 summon-anywhere first blocker family is resident_host, and it hands off to the existing resident-host runtime blocker boundary without granting launch, service, summon, memory, approval-decision, or resident-claim authority.'
}

$Payload | ConvertTo-Json -Depth 8
exit $(if ($ProofPassed) { 0 } else { 1 })
