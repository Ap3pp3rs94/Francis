[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status'
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

function Get-PropertyValue {
  param(
    [AllowNull()]
    [object]$Payload,
    [string]$Name
  )

  if ($null -eq $Payload) {
    return $null
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property) {
    return $null
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
  if ($Value -is [System.Array]) {
    return [string[]]@(
      $Value | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )
  }
  $Single = [string]$Value
  if ([string]::IsNullOrWhiteSpace($Single)) {
    return @()
  }
  return [string[]]@($Single)
}

function Get-ItemCount {
  param(
    [AllowNull()]
    [object]$Value
  )

  if ($null -eq $Value) {
    return 0
  }

  $ItemCount = 0
  foreach ($Item in @($Value)) {
    $ItemCount += 1
  }
  return $ItemCount
}

function New-GroupSummary {
  param(
    [string]$Id,
    [string]$Route,
    [string[]]$Blockers
  )

  $BlockerList = [System.Collections.ArrayList]::new()
  foreach ($Blocker in @($Blockers)) {
    $BlockerText = [string]$Blocker
    if (-not [string]::IsNullOrWhiteSpace($BlockerText)) {
      [void]$BlockerList.Add($BlockerText)
    }
  }

  return [ordered]@{
    id = $Id
    status = if ($BlockerList.Count -gt 0) { 'blocked' } else { 'clear' }
    ready = $false
    route = $Route
    blockers = $BlockerList
    readback_only = $true
    authority_granted = $false
    would_execute = $false
  }
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$PreflightScript = Join-Path $PSScriptRoot 'lens-host-preflight.ps1'
if (-not (Test-Path -LiteralPath $PreflightScript -PathType Leaf)) {
  throw "Lens host preflight script is missing: $PreflightScript"
}

$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command powershell -ErrorAction Stop
}

$PreflightOutput = & $PowerShell.Source -NoProfile -ExecutionPolicy Bypass -File $PreflightScript -Mode $Mode
$PreflightExitCode = $LASTEXITCODE
$PreflightText = ($PreflightOutput | ForEach-Object { [string]$_ }) -join "`n"
$PreflightPayload = $null
try {
  $PreflightPayload = $PreflightText | ConvertFrom-Json -ErrorAction Stop
} catch {
  $PreflightPayload = $null
}

$BlockerGroups = Get-PropertyValue -Payload $PreflightPayload -Name 'blocker_groups'
$RuntimeBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $BlockerGroups -Name 'runtime')
$ProcessReadbackBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $BlockerGroups -Name 'process_readback')
$ServicePlanBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $BlockerGroups -Name 'service_plan')
$SupervisionBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $BlockerGroups -Name 'supervision')
$SurfaceDependencyBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $BlockerGroups -Name 'surface_dependencies')
$AuthorityBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $BlockerGroups -Name 'authority')

$Groups = [ordered]@{
  runtime = New-GroupSummary -Id 'runtime' -Route '/lens/host/manifest' -Blockers $RuntimeBlockers
  process_readback = New-GroupSummary -Id 'process_readback' -Route '/lens/host/manifest' -Blockers $ProcessReadbackBlockers
  service_plan = New-GroupSummary -Id 'service_plan' -Route 'scripts/service-install.ps1 -Mode Plan' -Blockers $ServicePlanBlockers
  supervision = New-GroupSummary -Id 'supervision' -Route '/lens/host/supervision/authority/readiness' -Blockers $SupervisionBlockers
  surface_dependencies = New-GroupSummary -Id 'surface_dependencies' -Route '/lens/preflight' -Blockers $SurfaceDependencyBlockers
  authority = New-GroupSummary -Id 'authority' -Route '/lens/host/supervision/authority' -Blockers $AuthorityBlockers
}

$GroupOrder = [string[]]@(
  'runtime',
  'process_readback',
  'service_plan',
  'supervision',
  'surface_dependencies',
  'authority'
)
$BlockedGroups = [string[]]@(
  foreach ($GroupName in $GroupOrder) {
    if ((Get-ItemCount -Value $Groups[$GroupName].blockers) -gt 0) {
      [string]$GroupName
    }
  }
)
$FirstBlockerGroup = if ((Get-ItemCount -Value $BlockedGroups) -gt 0) { [string]$BlockedGroups[0] } else { '' }
$NextGapMap = @{
  runtime = 'resident_host_runtime_blocker_boundary'
  process_readback = 'resident_host_process_readback_boundary'
  service_plan = 'resident_host_service_plan_boundary'
  supervision = 'resident_host_supervision_boundary'
  surface_dependencies = 'resident_host_surface_dependency_boundary'
  authority = 'resident_host_authority_boundary'
}
$NextSmallestTruthfulGap = if ($NextGapMap.ContainsKey($FirstBlockerGroup)) {
  [string]$NextGapMap[$FirstBlockerGroup]
} else {
  'stage6_lens_completion_audit'
}

$Governance = Get-PropertyValue -Payload $PreflightPayload -Name 'governance'
$PreflightObserved = (
  [int]$PreflightExitCode -eq 0 -and
  [string](Get-PropertyValue -Payload $PreflightPayload -Name 'kind') -eq 'lens.host.lifecycle_preflight' -and
  [string](Get-PropertyValue -Payload $PreflightPayload -Name 'status') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $PreflightPayload -Name 'next_smallest_truthful_gap') -eq 'resident_host_lifecycle_blockers'
)
$ExpectedReadOnlyGovernance = (
  [bool](Get-PropertyValue -Payload $Governance -Name 'read_only_contract') -and
  -not [bool](Get-PropertyValue -Payload $Governance -Name 'execution_authority') -and
  -not [bool](Get-PropertyValue -Payload $Governance -Name 'approval_decision_authority') -and
  -not [bool](Get-PropertyValue -Payload $Governance -Name 'memory_write') -and
  -not [bool](Get-PropertyValue -Payload $Governance -Name 'local_process_launch_authority') -and
  -not [bool](Get-PropertyValue -Payload $Governance -Name 'service_install_authority') -and
  -not [bool](Get-PropertyValue -Payload $Governance -Name 'service_control_authority') -and
  -not [bool](Get-PropertyValue -Payload $Governance -Name 'overlay_control_authority') -and
  -not [bool](Get-PropertyValue -Payload $Governance -Name 'summon_authority') -and
  -not [bool](Get-PropertyValue -Payload $Governance -Name 'mutation_authority_granted')
)
$ExpectedGroupsPresent = (
  (Get-ItemCount -Value $RuntimeBlockers) -gt 0 -and
  (Get-ItemCount -Value $ServicePlanBlockers) -gt 0 -and
  (Get-ItemCount -Value $SupervisionBlockers) -gt 0 -and
  (Get-ItemCount -Value $SurfaceDependencyBlockers) -gt 0 -and
  (Get-ItemCount -Value $AuthorityBlockers) -gt 0
)
$ProofPassed = $PreflightObserved -and $ExpectedReadOnlyGovernance -and $ExpectedGroupsPresent

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.resident_host.lifecycle_blockers_proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  host_preflight = [ordered]@{
    ok = $PreflightObserved
    exit_code = [int]$PreflightExitCode
    kind = [string](Get-PropertyValue -Payload $PreflightPayload -Name 'kind')
    status = [string](Get-PropertyValue -Payload $PreflightPayload -Name 'status')
    ready = [bool](Get-PropertyValue -Payload $PreflightPayload -Name 'ready')
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $PreflightPayload -Name 'next_smallest_truthful_gap')
  }
  lifecycle_blocker_groups = $Groups
  blocked_groups = $BlockedGroups
  first_blocker_group = $FirstBlockerGroup
  next_smallest_truthful_gap = $NextSmallestTruthfulGap
  summary = [ordered]@{
    group_total = [int](Get-ItemCount -Value $GroupOrder)
    blocked_group_total = [int](Get-ItemCount -Value $BlockedGroups)
    required_groups_present = $ExpectedGroupsPresent
    lifecycle_handoff_consumed = $ProofPassed
  }
  evidence = @(
    'scripts/lens-host-preflight.ps1 -Mode Status',
    '/lens/host/manifest',
    '/lens/preflight',
    '/lens/host/supervision/authority/readiness'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_existing_preflight = $true
    read_only_contract = $true
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
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
}

$Payload | ConvertTo-Json -Depth 8
exit $(if ($ProofPassed) { 0 } else { 1 })
