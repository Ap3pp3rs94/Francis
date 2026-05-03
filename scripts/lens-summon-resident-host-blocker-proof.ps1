param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(5, 60)]
  [int]$StartupTimeoutSeconds = 5,

  [ValidateRange(2, 30)]
  [int]$ForegroundRunSeconds = 2,

  [ValidateRange(2, 30)]
  [int]$HostLaunchRunSeconds = 2,

  [ValidateRange(3, 30)]
  [int]$SupervisorRunSeconds = 3,

  [switch]$ConsumeProcessSupervisionHandoff
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
$HostProcessSupervisionHandoffProofScript = Join-Path $PSScriptRoot 'lens-resident-host-process-supervision-blocker-proof.ps1'
if ($ConsumeProcessSupervisionHandoff -and -not (Test-Path -LiteralPath $HostProcessSupervisionHandoffProofScript -PathType Leaf)) {
  throw "Lens resident-host process supervision handoff proof script is missing: $HostProcessSupervisionHandoffProofScript"
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
$SummonAuthorityReadback = Get-PropertyValue -Payload $SummonPayload -Name 'os_binding_authority_request_readback'
$SummonAuthorityReadbackGovernance = Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'governance'

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
$HostProcessHandoffResult = [ordered]@{ exit_code = 0; payload = $null; output = '' }
$HostProcessHandoffPayload = $null
$HostProcessHandoffGovernance = $null
$HostProcessHandoffBlockers = @()
if ($ConsumeProcessSupervisionHandoff) {
  $HostProcessHandoffResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $HostProcessSupervisionHandoffProofScript -ScriptArgs @(
    '-Mode', 'Status',
    '-StartupTimeoutSeconds', [string]$StartupTimeoutSeconds,
    '-ForegroundRunSeconds', [string]$ForegroundRunSeconds,
    '-HostLaunchRunSeconds', [string]$HostLaunchRunSeconds,
    '-SupervisorRunSeconds', [string]$SupervisorRunSeconds
  )
  $HostProcessHandoffPayload = $HostProcessHandoffResult.payload
  $HostProcessHandoffGovernance = Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'governance'
  $HostProcessHandoffBlockers = ConvertTo-StringArray -Value (
    Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'blockers' -Default @()
  )
}

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
$SummonAuthorityReadbackObserved = (
  [bool](Get-PropertyValue -Payload $SummonPayload -Name 'os_binding_authority_request_readback_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'ok' -Default $false) -and
  [string](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'kind' -Default '') -eq 'lens.os_binding.command_palette_binding_authority.request_readback' -and
  [string](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'route' -Default '') -eq '/lens/os-binding/authority/requests' -and
  [string](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'request_route' -Default '') -eq '/lens/os-binding/authority/request' -and
  [string](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'readiness_route' -Default '') -eq '/lens/os-binding/readiness' -and
  [string](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'plan_route' -Default '') -eq '/lens/os-binding/plan' -and
  [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'stage6_criterion_readback_ready' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'os_level_command_palette_binding_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'os_level_command_palette' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'summon_anywhere' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'opens_palette' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'registers_hotkey' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'launches_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'controls_overlay' -Default $true) -and
  [bool](Get-PropertyValue -Payload $SummonAuthorityReadbackGovernance -Name 'read_only_contract' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SummonAuthorityReadbackGovernance -Name 'approval_request_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonAuthorityReadbackGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonAuthorityReadbackGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonAuthorityReadbackGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonAuthorityReadbackGovernance -Name 'resident_claim_authority' -Default $true)
)
$HostLifecycleObserved = (
  [int]$HostResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $HostPayload -Name 'kind' -Default '') -eq 'lens.resident_host.lifecycle_blockers_proof' -and
  [string](Get-PropertyValue -Payload $HostPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $HostPayload -Name 'first_blocker_group' -Default '') -eq 'runtime' -and
  [string](Get-PropertyValue -Payload $HostPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_host_runtime_blocker_boundary' -and
  $HostRuntimeBlockers -contains 'lens_host_runtime_not_implemented'
)
$HostProcessSupervisionHandoffObserved = (
  [bool]$ConsumeProcessSupervisionHandoff -and
  [int]$HostProcessHandoffResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'kind' -Default '') -eq 'lens.resident_host.process_supervision_blocker.proof' -and
  [string](Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'resident_host_process_handoff_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'process_supervision_boundary_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'handoff_consumed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'authority_denied' -Default $false) -and
  [string](Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'previous_next_smallest_truthful_gap' -Default '') -eq 'resident_host_process_not_supervised' -and
  [string](Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'stage6_lens_completion_audit' -and
  [string](Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'resident_host_process_blocker' -Default '') -eq 'resident_host_process_not_supervised' -and
  $HostProcessHandoffBlockers -contains 'resident_host_process_not_supervised' -and
  $HostProcessHandoffBlockers -contains 'process_supervision_authority_not_granted' -and
  $HostProcessHandoffBlockers -contains 'process_restart_authority_not_granted'
)
$HandoffAligned = (
  $SummonFirstFamilyObserved -and
  $HostLifecycleObserved -and
  ($HostProcessSupervisionHandoffObserved -or -not [bool]$ConsumeProcessSupervisionHandoff) -and
  $HostSurfaceBlockers -contains 'tray_host_missing' -and
  $HostSurfaceBlockers -contains 'global_hotkey_binding_missing' -and
  $HostSurfaceBlockers -contains 'overlay_window_missing' -and
  $HostSurfaceBlockers -contains 'summon_binding_missing'
)
$ProcessHandoffSideEffectsDenied = $true
if ($ConsumeProcessSupervisionHandoff) {
  $ProcessHandoffSideEffectsDenied = (
    [bool](Get-PropertyValue -Payload $HostProcessHandoffGovernance -Name 'diagnostic_only' -Default $false) -and
    [bool](Get-PropertyValue -Payload $HostProcessHandoffGovernance -Name 'bounded_local_process_launch' -Default $false) -and
    -not [bool](Get-PropertyValue -Payload $HostProcessHandoffGovernance -Name 'product_execution_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $HostProcessHandoffGovernance -Name 'api_local_process_launch_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $HostProcessHandoffGovernance -Name 'execution_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $HostProcessHandoffGovernance -Name 'approval_decision_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $HostProcessHandoffGovernance -Name 'memory_write' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $HostProcessHandoffGovernance -Name 'summon_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $HostProcessHandoffGovernance -Name 'process_supervision_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $HostProcessHandoffGovernance -Name 'process_restart_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $HostProcessHandoffGovernance -Name 'service_install_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $HostProcessHandoffGovernance -Name 'service_control_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $HostProcessHandoffGovernance -Name 'overlay_control_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $HostProcessHandoffGovernance -Name 'resident_claim_authority' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $HostProcessHandoffGovernance -Name 'mutation_authority_granted' -Default $true)
  )
}
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
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'mutation_authority_granted' -Default $true) -and
  $ProcessHandoffSideEffectsDenied
)

$Checks = @(
  (New-Check -Id 'summon_first_family' -Status $(if ($SummonFirstFamilyObserved) { 'resident_host_first' } else { 'missing_or_unexpected' }) -Passed $SummonFirstFamilyObserved -Evidence 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status' -Reason 'The summon-anywhere blocker proof must name resident_host as the first blocked acceptance family.'),
  (New-Check -Id 'summon_os_binding_authority_readback' -Status $(if ($SummonAuthorityReadbackObserved) { 'authority_readback_consumed' } else { 'missing_or_unexpected' }) -Passed $SummonAuthorityReadbackObserved -Evidence 'scripts/lens-summon-anywhere-blockers-proof.ps1:/lens/os-binding/authority/requests' -Reason 'The resident-host bridge must preserve the summon blocker proof authority-request readback before handing off the first blocker family.'),
  (New-Check -Id 'resident_host_lifecycle_proof' -Status $(if ($HostLifecycleObserved) { 'runtime_blocked' } else { 'missing_or_unexpected' }) -Passed $HostLifecycleObserved -Evidence 'scripts/lens-resident-host-lifecycle-blockers-proof.ps1 -Mode Status' -Reason 'The resident-host lifecycle proof must consume the first family and point to the runtime blocker boundary.')
)
if ($ConsumeProcessSupervisionHandoff) {
  $Checks += New-Check -Id 'resident_host_process_supervision_handoff' -Status $(if ($HostProcessSupervisionHandoffObserved) { 'process_handoff_consumed' } else { 'missing_or_unexpected' }) -Passed $HostProcessSupervisionHandoffObserved -Evidence 'scripts/lens-resident-host-process-supervision-blocker-proof.ps1 -Mode Status' -Reason 'The summon resident-host bridge should consume the newer process-supervision handoff before handing back to Stage 6 completion audit.'
}
$Checks += New-Check -Id 'handoff_alignment' -Status $(if ($HandoffAligned) { 'handoff_aligned' } else { 'handoff_mismatch' }) -Passed $HandoffAligned -Evidence $(if ($ConsumeProcessSupervisionHandoff) { 'summon resident_host family + host lifecycle/process handoff blocker groups' } else { 'summon resident_host family + host lifecycle blocker groups' }) -Reason 'The first summon-anywhere family must map into host runtime/process/surface blockers without changing authority.'
$Checks += New-Check -Id 'side_effects_denied' -Status $(if ($SideEffectsDenied) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $SideEffectsDenied -Evidence 'summon and host governance payloads' -Reason 'The bridge proof must remain diagnostic/readback only and grant no launch, service, summon, memory, approval-decision, or resident-claim authority.'

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

$ResidentHostNextSmallestTruthfulGap = if ($ConsumeProcessSupervisionHandoff) {
  'stage6_lens_completion_audit'
} else {
  'resident_host_runtime_blocker_boundary'
}
$ResidentHostProcessSupervisionNextSmallestTruthfulGap = if ($ConsumeProcessSupervisionHandoff) {
  'stage6_lens_completion_audit'
} else {
  ''
}
$Evidence = @(
  'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status',
  'scripts/lens-resident-host-lifecycle-blockers-proof.ps1 -Mode Status'
)
if ($ConsumeProcessSupervisionHandoff) {
  $Evidence += 'scripts/lens-resident-host-process-supervision-blocker-proof.ps1 -Mode Status'
}
$Evidence += @(
  'scripts/lens-host-preflight.ps1 -Mode Status',
  'config/runtime/services/lens-host.json'
)
$Message = if ($ConsumeProcessSupervisionHandoff) {
  'The Stage 6 summon-anywhere first blocker family is resident_host, and the bridge consumed the resident-host process-supervision handoff before returning to Stage 6 completion audit without granting product launch, service, summon, memory, approval-decision, or resident-claim authority.'
} else {
  'The Stage 6 summon-anywhere first blocker family is resident_host, and it hands off to the existing resident-host runtime blocker boundary without granting launch, service, summon, memory, approval-decision, or resident-claim authority.'
}

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
  summon_os_binding_authority_request_readback_observed = $SummonAuthorityReadbackObserved
  resident_host_lifecycle_next_smallest_truthful_gap = 'resident_host_runtime_blocker_boundary'
  resident_host_process_supervision_next_smallest_truthful_gap = $ResidentHostProcessSupervisionNextSmallestTruthfulGap
  resident_host_next_smallest_truthful_gap = $ResidentHostNextSmallestTruthfulGap
  next_smallest_truthful_gap = $ResidentHostNextSmallestTruthfulGap
  summon_first_family_observed = $SummonFirstFamilyObserved
  resident_host_lifecycle_observed = $HostLifecycleObserved
  consume_process_supervision_handoff = [bool]$ConsumeProcessSupervisionHandoff
  resident_host_process_supervision_handoff_observed = $HostProcessSupervisionHandoffObserved
  handoff_aligned = $HandoffAligned
  side_effects_denied = $SideEffectsDenied
  startup_timeout_seconds = $StartupTimeoutSeconds
  foreground_run_seconds = $ForegroundRunSeconds
  host_launch_run_seconds = $HostLaunchRunSeconds
  supervisor_run_seconds = $SupervisorRunSeconds
  summon_os_binding_authority_request_readback = [ordered]@{
    status = if ($SummonAuthorityReadbackObserved) { [string](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'status' -Default '') } else { 'missing_or_failed' }
    ok = $SummonAuthorityReadbackObserved
    kind = [string](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'kind' -Default '')
    route = [string](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'route' -Default '')
    request_route = [string](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'request_route' -Default '')
    readiness_route = [string](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'readiness_route' -Default '')
    plan_route = [string](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'plan_route' -Default '')
    stage6_criterion_readback_ready = [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'stage6_criterion_readback_ready' -Default $false)
    authority_granted = [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'authority_granted' -Default $false)
    os_level_command_palette_binding_authority = [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'os_level_command_palette_binding_authority' -Default $false)
    os_level_command_palette = [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'os_level_command_palette' -Default $false)
    summon_anywhere = [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'summon_anywhere' -Default $false)
    opens_palette = [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'opens_palette' -Default $false)
    registers_hotkey = [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'registers_hotkey' -Default $false)
    launches_process = [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'launches_process' -Default $false)
    controls_overlay = [bool](Get-PropertyValue -Payload $SummonAuthorityReadback -Name 'controls_overlay' -Default $false)
    governance = [ordered]@{
      read_only_contract = [bool](Get-PropertyValue -Payload $SummonAuthorityReadbackGovernance -Name 'read_only_contract' -Default $false)
      approval_request_write = $false
      execution_authority = $false
      approval_decision_authority = $false
      memory_write = $false
      resident_claim_authority = $false
    }
  }
  summon_resident_host_blockers = [string[]]@($SummonResidentHostBlockers)
  resident_host_runtime_blockers = [string[]]@($HostRuntimeBlockers)
  resident_host_process_readback_blockers = [string[]]@($HostProcessReadbackBlockers)
  resident_host_process_supervision_blockers = [string[]]@($HostProcessHandoffBlockers)
  resident_host_process_supervision_handoff = [ordered]@{
    status = [string](Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'status' -Default 'missing')
    previous_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'previous_next_smallest_truthful_gap' -Default '')
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'next_smallest_truthful_gap' -Default '')
    resident_host_process_handoff_observed = [bool](Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'resident_host_process_handoff_observed' -Default $false)
    process_supervision_boundary_observed = [bool](Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'process_supervision_boundary_observed' -Default $false)
    handoff_consumed = [bool](Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'handoff_consumed' -Default $false)
    authority_denied = [bool](Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'authority_denied' -Default $false)
    resident_host_process_state = [string](Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'resident_host_process_state' -Default '')
    resident_host_process_blocker = [string](Get-PropertyValue -Payload $HostProcessHandoffPayload -Name 'resident_host_process_blocker' -Default '')
  }
  resident_host_surface_blockers = [string[]]@($HostSurfaceBlockers)
  checks = @($Checks)
  evidence = @($Evidence)
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_summon_anywhere_blockers_proof = $true
    summon_os_binding_authority_request_readback = $SummonAuthorityReadbackObserved
    wraps_resident_host_lifecycle_blockers_proof = $true
    wraps_resident_host_process_supervision_blocker_proof = [bool]$ConsumeProcessSupervisionHandoff
    read_only_contract = $true
    bounded_local_process_launch = [bool]$ConsumeProcessSupervisionHandoff
    temporary_runtime_state_write = [bool]$ConsumeProcessSupervisionHandoff
    api_local_process_launch_authority = $false
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
  message = $Message
}

$Payload | ConvertTo-Json -Depth 8
exit $(if ($ProofPassed) { 0 } else { 1 })
