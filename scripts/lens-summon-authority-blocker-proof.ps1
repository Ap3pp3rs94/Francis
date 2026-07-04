param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [string]$StatusPath = ''
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
$SummonPreflightScript = Join-Path $PSScriptRoot 'lens-summon-preflight.ps1'
foreach ($ScriptPath in @($SummonBlockersScript, $SummonPreflightScript)) {
  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    throw "Required Lens proof script is missing: $ScriptPath"
  }
}

$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command powershell -ErrorAction Stop
}
$ChildDataRoot = ''
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $ChildDataRoot = [System.IO.Path]::GetFullPath($DataDir)
}

$SummonArgs = @('-Mode', 'Status')
if (-not [string]::IsNullOrWhiteSpace($StatusPath)) {
  $SummonArgs += @('-StatusPath', $StatusPath)
}
$SummonResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $SummonBlockersScript -ScriptArgs $SummonArgs -DataRoot $ChildDataRoot
$SummonPayload = $SummonResult.payload
$SummonBlockerGroups = Get-PropertyValue -Payload $SummonPayload -Name 'blocker_groups'
$SummonBlockedFamilies = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPayload -Name 'blocked_families' -Default @()
)
$SummonFamilyHandoffs = Get-PropertyValue -Payload $SummonPayload -Name 'blocked_family_handoffs' -Default @()
$SummonBindingFamilyHandoff = Get-HandoffById -Handoffs $SummonFamilyHandoffs -Id 'summon_binding'
$AuthorityFamilyHandoff = Get-HandoffById -Handoffs $SummonFamilyHandoffs -Id 'authority'
$SummonBindingFamilyBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'blockers' -Default @()
)
$AuthorityFamilyBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $AuthorityFamilyHandoff -Name 'blockers' -Default @()
)
$SummonAuthorityBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonBlockerGroups -Name 'authority' -Default @()
)
$SummonGovernance = Get-PropertyValue -Payload $SummonPayload -Name 'governance'
$SurfaceRuntimeReadbackObserved = Get-PropertyValue -Payload $SummonPayload -Name 'surface_runtime_readback_observed' -Default ([ordered]@{})
$SurfaceRuntimeSuppressedBlockers = Get-PropertyValue -Payload $SummonPayload -Name 'surface_runtime_suppressed_blockers' -Default ([ordered]@{})
$GlobalHotkeyRuntimeObserved = [bool](Get-PropertyValue -Payload $SurfaceRuntimeReadbackObserved -Name 'global_hotkey_binding' -Default $false)
$SummonBindingRuntimeObserved = [bool](Get-PropertyValue -Payload $SurfaceRuntimeReadbackObserved -Name 'summon_binding' -Default $false)
$SummonBindingSuppressedBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SurfaceRuntimeSuppressedBlockers -Name 'summon_binding' -Default @()
)
$ResidentHostSupervisedRuntimeObserved = [bool](
  Get-PropertyValue -Payload $SummonPayload -Name 'resident_host_supervised_runtime_observed' -Default $false
)

$SummonPreflightResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $SummonPreflightScript -ScriptArgs @('-Mode', 'Status') -DataRoot $ChildDataRoot
$SummonPreflightPayload = $SummonPreflightResult.payload
$SummonPreflightGovernance = Get-PropertyValue -Payload $SummonPreflightPayload -Name 'governance'
$SummonPreflightGroups = Get-PropertyValue -Payload $SummonPreflightPayload -Name 'blocker_groups'
$SummonPreflightBindingBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPreflightGroups -Name 'summon_binding' -Default @()
)
$SummonPreflightAuthorityBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPreflightGroups -Name 'authority' -Default @()
)
$SummonPreflightBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPreflightPayload -Name 'blockers' -Default @()
)
$SummonPreflightRequiredBefore = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPreflightPayload -Name 'required_before_enable' -Default @()
)
$SummonBinding = Get-PropertyValue -Payload $SummonPreflightPayload -Name 'binding'

$RequiredAuthorityBlockers = @(
  'summon_authority_not_granted',
  'hotkey_registration_authority_not_granted',
  'overlay_control_authority_not_granted'
)
$RequiredDirectAuthorityBlockers = @(
  'summon_authority_not_granted',
  'hotkey_registration_authority_not_granted',
  'overlay_control_authority_not_granted',
  'local_process_launch_authority_not_granted'
)
$SummonBindingFamilyIndex = [array]::IndexOf([string[]]@($SummonBlockedFamilies), 'summon_binding')
$GlobalHotkeyFamilyIndex = [array]::IndexOf([string[]]@($SummonBlockedFamilies), 'global_hotkey_binding')
$SummonAuthorityFamilyIndex = [array]::IndexOf([string[]]@($SummonBlockedFamilies), 'authority')
$AuthorityFamilyFollowsObservedChain = (
  $SummonAuthorityFamilyIndex -ge 0 -and
  $SummonAuthorityFamilyIndex -eq (@($SummonBlockedFamilies).Count - 1)
)
$AuthorityFamilyAlreadyDelegated = (
  $SummonAuthorityFamilyIndex -lt 0 -and
  @($SummonAuthorityBlockers).Count -eq 0 -and
  @($SummonPreflightAuthorityBlockers).Count -eq 0
)
$GlobalHotkeyFamilyAccountedFor = (
  $GlobalHotkeyFamilyIndex -ge 0 -or
  $GlobalHotkeyRuntimeObserved
)
$SummonBindingResolvedByRuntimeReadbackObserved = (
  $SummonBindingRuntimeObserved -and
  $SummonBindingFamilyIndex -lt 0 -and
  $GlobalHotkeyFamilyAccountedFor -and
  (
    (
      $AuthorityFamilyFollowsObservedChain -and
      [string](Get-PropertyValue -Payload $AuthorityFamilyHandoff -Name 'id' -Default '') -eq 'authority' -and
      ($RequiredAuthorityBlockers | Where-Object { $AuthorityFamilyBlockers -notcontains $_ }).Count -eq 0
    ) -or
    $AuthorityFamilyAlreadyDelegated
  )
)

$SummonAuthorityFamilyObservedLegacy = (
  [int]$SummonResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'kind' -Default '') -eq 'lens.summon_anywhere_blockers.proof' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'acceptance_criterion' -Default '') -eq 'summon_anywhere' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  $SummonBindingFamilyIndex -ge 0 -and
  $SummonAuthorityFamilyIndex -eq ($SummonBindingFamilyIndex + 1) -and
  ($RequiredAuthorityBlockers | Where-Object { $SummonAuthorityBlockers -notcontains $_ }).Count -eq 0
)
$SummonAuthorityFamilyObservedResolved = (
  [int]$SummonResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'kind' -Default '') -eq 'lens.summon_anywhere_blockers.proof' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'acceptance_criterion' -Default '') -eq 'summon_anywhere' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  $SummonBindingResolvedByRuntimeReadbackObserved -and
  (
    ($RequiredAuthorityBlockers | Where-Object { $SummonAuthorityBlockers -notcontains $_ }).Count -eq 0 -or
    $AuthorityFamilyAlreadyDelegated
  )
)
$SummonAuthorityFamilyObservedDelegated = (
  [int]$SummonResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'kind' -Default '') -eq 'lens.summon_anywhere_blockers.proof' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'acceptance_criterion' -Default '') -eq 'summon_anywhere' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  $AuthorityFamilyAlreadyDelegated -and
  $SummonBindingFamilyIndex -ge 0 -and
  $SummonBindingFamilyIndex -eq (@($SummonBlockedFamilies).Count - 1)
)
$SummonAuthorityFamilyObserved = (
  $SummonAuthorityFamilyObservedLegacy -or
  $SummonAuthorityFamilyObservedResolved -or
  $SummonAuthorityFamilyObservedDelegated
)
$SummonBindingContractReadbackObservedLegacy = (
  [string](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'id' -Default '') -eq 'summon_binding' -and
  [string](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'proof_script' -Default '') -eq 'scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'next_step' -Default '') -eq 'run_summon_binding_blocker_proof' -and
  [string](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_authority_blocker_boundary' -and
  [string](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'authority_required' -Default '') -eq 'summon_authority' -and
  -not [bool](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'would_mutate' -Default $true) -and
  $SummonBindingFamilyBlockers -contains 'lens_summon_binding_disabled_pending_authority' -and
  $SummonBindingFamilyBlockers -contains 'summon_authority_not_granted'
)
$SummonBindingContractReadbackObservedDelegated = (
  [string](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'id' -Default '') -eq 'summon_binding' -and
  [string](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'proof_script' -Default '') -eq 'scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'next_step' -Default '') -eq 'run_summon_binding_blocker_proof' -and
  [string](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_authority_blocker_boundary' -and
  [string](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'authority_required' -Default '') -eq 'summon_authority' -and
  -not [bool](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'would_mutate' -Default $true) -and
  $SummonBindingFamilyBlockers -contains 'lens_summon_binding_disabled_pending_authority' -and
  @($SummonAuthorityBlockers).Count -eq 0 -and
  @($SummonPreflightAuthorityBlockers).Count -eq 0
)
$SummonBindingContractReadbackObserved = (
  $SummonBindingContractReadbackObservedLegacy -or
  $SummonBindingContractReadbackObservedDelegated -or
  $SummonBindingResolvedByRuntimeReadbackObserved
)
$SummonPreflightLegacyAuthorityObserved = (
  ($RequiredDirectAuthorityBlockers | Where-Object { $SummonPreflightAuthorityBlockers -notcontains $_ }).Count -eq 0 -and
  ($RequiredDirectAuthorityBlockers | Where-Object { $SummonPreflightBlockers -notcontains $_ }).Count -eq 0
)
$SummonPreflightDelegatedAuthorityObserved = (
  @($SummonPreflightAuthorityBlockers).Count -eq 0 -and
  $SummonPreflightBindingBlockers -contains 'lens_summon_binding_disabled_pending_authority' -and
  $SummonPreflightBlockers -contains 'lens_summon_binding_disabled_pending_authority'
)
$SummonPreflightAuthorityObserved = (
  [int]$SummonPreflightResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'kind' -Default '') -eq 'lens.summon.preflight' -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'ready' -Default $true) -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'acceptance_criterion' -Default '') -eq 'summon_anywhere' -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'global_hotkey' -Default '') -eq 'Ctrl+Alt+F' -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'binding_scope' -Default '') -eq 'global' -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'palette_route' -Default '') -eq '/lens/status' -and
  -not [bool](Get-PropertyValue -Payload $SummonBinding -Name 'enabled' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonBinding -Name 'binding_enabled' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonBinding -Name 'register_hotkey' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonBinding -Name 'startup_register' -Default $true) -and
  (
    $SummonPreflightLegacyAuthorityObserved -or
    $SummonPreflightDelegatedAuthorityObserved
  )
)
$AuthorityReadbackAligned = (
  (
    ($RequiredAuthorityBlockers | Where-Object { $SummonAuthorityBlockers -notcontains $_ }).Count -eq 0 -and
    ($RequiredDirectAuthorityBlockers | Where-Object { $SummonPreflightAuthorityBlockers -notcontains $_ }).Count -eq 0 -and
    $SummonPreflightBindingBlockers -contains 'summon_authority_not_granted'
  ) -or (
    ($SummonAuthorityFamilyObservedDelegated -or ($SummonAuthorityFamilyObservedResolved -and $AuthorityFamilyAlreadyDelegated)) -and
    @($SummonAuthorityBlockers).Count -eq 0 -and
    @($SummonPreflightAuthorityBlockers).Count -eq 0
  )
)
$HandoffAligned = (
  $SummonAuthorityFamilyObserved -and
  $SummonBindingContractReadbackObserved -and
  $SummonPreflightAuthorityObserved -and
  $AuthorityReadbackAligned -and
  (
    $ResidentHostSupervisedRuntimeObserved -or
    $SummonAuthorityBlockers -contains 'local_process_launch_authority_not_granted' -or
    $SummonAuthorityFamilyObservedDelegated -or
    ($SummonAuthorityFamilyObservedResolved -and $AuthorityFamilyAlreadyDelegated)
  ) -and
  $SummonPreflightBindingBlockers -contains 'lens_summon_binding_disabled_pending_authority' -and
  $SummonPreflightRequiredBefore -contains 'summon_binding'
)
$SideEffectsDenied = (
  [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'diagnostic_only' -Default $false) -and
  $SummonBindingContractReadbackObserved -and
  [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'read_only_contract' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'approval_request_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'approval_request_write' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'capture_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'new_sensing_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'mutation_authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'mutation_authority_granted' -Default $true)
)

$PreviousSummonBlockerFamily = if ($SummonBindingResolvedByRuntimeReadbackObserved) {
  'global_hotkey_binding'
} else {
  'summon_binding'
}
$PreviousBindingNextGap = if ($SummonBindingResolvedByRuntimeReadbackObserved) {
  'stage6_lens_completion_audit'
} else {
  [string](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'next_smallest_truthful_gap' -Default '')
}
$PreviousBindingHandoff = if ($SummonBindingResolvedByRuntimeReadbackObserved) {
  [ordered]@{
    source = 'summon_anywhere_blockers.surface_runtime_readback_observed'
    status = 'runtime_readback_resolved'
    contract_status = 'resolved'
    proof_script = 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status'
    previous_summon_blocker_family = 'global_hotkey_binding'
    summon_binding_blocker_family = 'summon_binding'
    next_summon_blocker_family = 'authority'
    next_smallest_truthful_gap = 'stage6_lens_completion_audit'
    authority_required = [string](Get-PropertyValue -Payload $AuthorityFamilyHandoff -Name 'authority_required' -Default 'summon_hotkey_overlay_and_process_authority')
    authority_granted = $false
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
    handoff_aligned = $true
    side_effects_denied = $true
    blockers = [string[]]@()
    suppressed_blockers = [string[]]@($SummonBindingSuppressedBlockers)
  }
} else {
  [ordered]@{
    source = 'summon_anywhere_blockers.blocked_family_handoffs'
    status = 'contract_projected'
    contract_status = [string](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'status' -Default 'missing')
    proof_script = [string](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'proof_script' -Default '')
    previous_summon_blocker_family = 'global_hotkey_binding'
    summon_binding_blocker_family = [string](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'id' -Default '')
    next_summon_blocker_family = 'authority'
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'next_smallest_truthful_gap' -Default '')
    authority_required = [string](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'authority_required' -Default '')
    authority_granted = [bool](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'authority_granted' -Default $false)
    read_only_contract = [bool](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'read_only_contract' -Default $false)
    diagnostic_only = [bool](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'diagnostic_only' -Default $false)
    would_execute = [bool](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'would_execute' -Default $false)
    would_mutate = [bool](Get-PropertyValue -Payload $SummonBindingFamilyHandoff -Name 'would_mutate' -Default $false)
    handoff_aligned = $SummonBindingContractReadbackObserved
    side_effects_denied = $SummonBindingContractReadbackObserved
    blockers = [string[]]@($SummonBindingFamilyBlockers)
  }
}

$Checks = @(
  (New-Check -Id 'summon_authority_family' -Status $(if ($SummonAuthorityFamilyObservedDelegated) { 'authority_delegated_no_family_blocker' } elseif ($SummonAuthorityFamilyObservedResolved) { 'authority_family_after_resolved_summon_binding' } elseif ($SummonAuthorityFamilyObserved) { 'sixth_family_projected' } else { 'missing_or_unexpected' }) -Passed $SummonAuthorityFamilyObserved -Evidence 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status' -Reason 'The summon-anywhere blocker proof must keep authority after the summon-binding family when authority is still blocked, or show that delegated authority leaves only non-authority readiness blockers.'),
  (New-Check -Id 'previous_summon_binding_contract' -Status $(if ($SummonBindingResolvedByRuntimeReadbackObserved) { 'summon_binding_runtime_readback_resolved' } elseif ($SummonBindingContractReadbackObserved) { 'previous_family_contract_observed' } else { 'missing_or_unexpected' }) -Passed $SummonBindingContractReadbackObserved -Evidence 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status blocked_family_handoffs[summon_binding]' -Reason 'The summon-authority handoff should consume the summon-binding family contract or the explicit runtime readback before moving to the final blocker family.'),
  (New-Check -Id 'previous_summon_binding_contract_readback' -Status $(if ($SummonBindingResolvedByRuntimeReadbackObserved) { 'runtime_readback_resolved' } elseif ($SummonBindingContractReadbackObserved) { 'previous_contract_readback_observed' } else { 'missing_or_unexpected' }) -Passed $SummonBindingContractReadbackObserved -Evidence 'summon_anywhere_blockers.blocked_family_handoffs[summon_binding]' -Reason 'The summon-authority proof must preserve the bounded summon-binding contract or the explicit runtime readback without rerunning the slower summon-binding bridge proof.'),
  (New-Check -Id 'summon_preflight_authority' -Status $(if ($SummonPreflightAuthorityObserved) { 'blocked_readback_ready' } else { 'missing_or_unexpected' }) -Passed $SummonPreflightAuthorityObserved -Evidence 'scripts/lens-summon-preflight.ps1 -Mode Status' -Reason 'The direct summon preflight must remain blocked by explicit summon, hotkey-registration, overlay-control, and local-process-launch authority denials.'),
  (New-Check -Id 'handoff_alignment' -Status $(if ($HandoffAligned) { 'handoff_aligned' } else { 'handoff_mismatch' }) -Passed $HandoffAligned -Evidence 'summon authority blocker group + direct summon preflight authority blocker group' -Reason 'The authority blocker family must map to direct summon preflight without changing authority.'),
  (New-Check -Id 'side_effects_denied' -Status $(if ($SideEffectsDenied) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $SideEffectsDenied -Evidence 'summon, summon-binding family contract, and summon preflight governance payloads' -Reason 'The bridge proof must remain diagnostic/readback only and grant no summon, hotkey, overlay, process, memory, approval-decision, sensing, capture, or resident authority.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.summon_authority_blocker.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  stage = 'Stage 6 / Lens MVP'
  stage_state = 'active'
  acceptance_criterion = 'summon_anywhere'
  previous_summon_blocker_family = $PreviousSummonBlockerFamily
  summon_authority_blocker_family = 'authority'
  sixth_summon_blocker_family = 'authority'
  next_summon_blocker_family = 'stage6_lens_completion_audit'
  summon_next_smallest_truthful_gap = 'summon_anywhere_blockers'
  previous_binding_next_smallest_truthful_gap = $PreviousBindingNextGap
  direct_summon_preflight_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'next_smallest_truthful_gap' -Default '')
  next_smallest_truthful_gap = 'stage6_lens_completion_audit'
  authority_required = 'summon_hotkey_overlay_and_process_authority'
  authority_granted = $false
  recommended_handoff_source = 'summon_authority_handoff'
  recommended_next_slice = 'run_stage6_lens_completion_audit_after_summon_authority_handoff'
  recommended_proof_script = 'scripts/lens-stage6-completion-audit.ps1 -Mode Status'
  recommended_route = '/lens/status'
  recommended_readiness_route = '/lens/status'
  recommended_handoff = [ordered]@{
    id = 'stage6_lens_completion_audit'
    status = 'audit_needed'
    previous_summon_blocker_family = 'authority'
    next_summon_blocker_family = 'stage6_lens_completion_audit'
    next_smallest_truthful_gap = 'stage6_lens_completion_audit'
    next_step = 'run_stage6_lens_completion_audit_after_summon_authority_handoff'
    proof_script = 'scripts/lens-stage6-completion-audit.ps1 -Mode Status'
    route = '/lens/status'
    readiness_route = '/lens/status'
    acceptance_criterion = 'summon_anywhere'
    blocker_family = 'authority'
    authority_required = 'none_new_stage6_completion_audit'
    authority_granted = $false
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
  }
  summon_authority_family_observed = $SummonAuthorityFamilyObserved
  summon_authority_family_observed_after_resolved_summon_binding = $SummonAuthorityFamilyObservedResolved
  summon_authority_delegated_posture_observed = $AuthorityFamilyAlreadyDelegated
  previous_summon_binding_contract_observed = $SummonBindingContractReadbackObserved
  previous_summon_binding_contract_readback_observed = $SummonBindingContractReadbackObserved
  summon_binding_runtime_readback_observed = $SummonBindingRuntimeObserved
  summon_binding_resolved_by_runtime_readback = $SummonBindingResolvedByRuntimeReadbackObserved
  summon_preflight_authority_observed = $SummonPreflightAuthorityObserved
  resident_host_supervised_runtime_observed = $ResidentHostSupervisedRuntimeObserved
  all_summon_blocker_families_consumed = $HandoffAligned
  handoff_aligned = $HandoffAligned
  side_effects_denied = $SideEffectsDenied
  summon_authority_blockers = [string[]]@($SummonAuthorityBlockers)
  direct_summon_preflight_authority_blockers = [string[]]@($SummonPreflightAuthorityBlockers)
  direct_summon_preflight_binding_blockers = [string[]]@($SummonPreflightBindingBlockers)
  previous_binding_handoff = $PreviousBindingHandoff
  summon_authority_boundary = [ordered]@{
    status = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'status' -Default 'missing')
    ready = [bool](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'ready' -Default $false)
    summon_name = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'summon_name' -Default '')
    config_path = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'config_path' -Default '')
    global_hotkey = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'global_hotkey' -Default '')
    binding_scope = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'binding_scope' -Default '')
    palette_route = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'palette_route' -Default '')
    required_before_enable = [string[]]@($SummonPreflightRequiredBefore)
    binding_enabled = [bool](Get-PropertyValue -Payload $SummonBinding -Name 'binding_enabled' -Default $false)
    register_hotkey = [bool](Get-PropertyValue -Payload $SummonBinding -Name 'register_hotkey' -Default $false)
    startup_register = [bool](Get-PropertyValue -Payload $SummonBinding -Name 'startup_register' -Default $false)
    blockers = [string[]]@($SummonPreflightBlockers)
    summon_binding_blockers = [string[]]@($SummonPreflightBindingBlockers)
    authority_blockers = [string[]]@($SummonPreflightAuthorityBlockers)
  }
  checks = @($Checks)
  evidence = @(
    'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status',
    'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status blocked_family_handoffs[summon_binding]',
    'scripts/lens-summon-preflight.ps1 -Mode Status',
    'config/runtime/lens/summon.json',
    '/lens/summon'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_summon_anywhere_blockers_proof = $true
    wraps_summon_binding_blocker_proof = $false
    uses_summon_binding_family_contract_readback = $SummonBindingContractReadbackObserved
    summon_binding_contract_readback = $SummonBindingContractReadbackObserved
    summon_binding_runtime_readback_observed = $SummonBindingRuntimeObserved
    summon_binding_resolved_by_runtime_readback = $SummonBindingResolvedByRuntimeReadbackObserved
    wraps_summon_preflight = $true
    read_only_contract = $true
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
    window_management_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    summon_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'The Stage 6 summon-anywhere sixth blocker family is authority, and this handoff consumes the direct summon preflight without granting summon, hotkey, overlay, process, memory, approval-decision, sensing, capture, or resident authority.'
}

$Payload | ConvertTo-Json -Depth 8
exit $(if ($ProofPassed) { 0 } else { 1 })
