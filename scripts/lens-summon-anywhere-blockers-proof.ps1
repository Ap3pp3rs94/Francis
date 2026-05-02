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

function Select-Blockers {
  param(
    [string[]]$Blockers,
    [string[]]$Candidates
  )

  return [string[]]@($Candidates | Where-Object { $Blockers -contains $_ })
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

$SummonPreflightScript = Join-Path $PSScriptRoot 'lens-summon-preflight.ps1'
if (-not (Test-Path -LiteralPath $SummonPreflightScript -PathType Leaf)) {
  throw "Lens summon preflight script is missing: $SummonPreflightScript"
}

$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command powershell -ErrorAction Stop
}

$SummonPreflightResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $SummonPreflightScript -ScriptArgs @('-Mode', 'Status')
$SummonPreflightPayload = $SummonPreflightResult.payload
$SummonPreflightBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPreflightPayload -Name 'blockers' -Default @()
)
$SummonPreflightRequiredBeforeEnable = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPreflightPayload -Name 'required_before_enable' -Default @()
)
$SummonPreflightGovernance = Get-PropertyValue -Payload $SummonPreflightPayload -Name 'governance'

$Stage6BlockerGroups = [ordered]@{
  resident_host = [string[]]@(Select-Blockers -Blockers $SummonPreflightBlockers -Candidates @(
      'lens_host_runtime_not_implemented',
      'resident_host_process_missing',
      'resident_host_process_not_supervised',
      'local_process_launch_authority_not_granted'
    ))
  tray_presence = [string[]]@(Select-Blockers -Blockers $SummonPreflightBlockers -Candidates @(
      'tray_host_missing'
    ))
  overlay_window = [string[]]@(Select-Blockers -Blockers $SummonPreflightBlockers -Candidates @(
      'overlay_window_missing'
    ))
  global_hotkey_binding = [string[]]@(Select-Blockers -Blockers $SummonPreflightBlockers -Candidates @(
      'global_hotkey_binding_disabled',
      'global_hotkey_registration_disabled',
      'hotkey_registration_authority_not_granted'
    ))
  summon_binding = [string[]]@(Select-Blockers -Blockers $SummonPreflightBlockers -Candidates @(
      'lens_summon_binding_not_implemented',
      'summon_authority_not_granted'
    ))
  authority = [string[]]@(Select-Blockers -Blockers $SummonPreflightBlockers -Candidates @(
      'summon_authority_not_granted',
      'hotkey_registration_authority_not_granted',
      'overlay_control_authority_not_granted',
      'local_process_launch_authority_not_granted'
    ))
}

$Stage6BlockerFamilyOrder = @(
  'resident_host',
  'tray_presence',
  'overlay_window',
  'global_hotkey_binding',
  'summon_binding',
  'authority'
)
$Stage6BlockedFamilies = [string[]]@(
  $Stage6BlockerFamilyOrder | Where-Object {
    (ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Stage6BlockerGroups -Name $_ -Default @())).Count -gt 0
  }
)

$SummonPreflightObserved = (
  [int]$SummonPreflightResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'kind' -Default '') -eq 'lens.summon.preflight' -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'ready' -Default $true) -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'acceptance_criterion' -Default '') -eq 'summon_anywhere' -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'global_hotkey' -Default '') -ne '' -and
  $SummonPreflightBlockers -contains 'global_hotkey_binding_disabled' -and
  $SummonPreflightBlockers -contains 'global_hotkey_registration_disabled' -and
  $SummonPreflightBlockers -contains 'summon_authority_not_granted' -and
  $SummonPreflightBlockers -contains 'hotkey_registration_authority_not_granted'
)
$Stage6FamilyProjectionObserved = (
  @($Stage6BlockedFamilies).Count -eq 6 -and
  $Stage6BlockedFamilies[0] -eq 'resident_host' -and
  $Stage6BlockedFamilies -contains 'tray_presence' -and
  $Stage6BlockedFamilies -contains 'overlay_window' -and
  $Stage6BlockedFamilies -contains 'global_hotkey_binding' -and
  $Stage6BlockedFamilies -contains 'summon_binding' -and
  $Stage6BlockedFamilies -contains 'authority'
)
$SideEffectsDenied = (
  [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'read_only_contract' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'capture_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'new_sensing_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'mutation_authority_granted' -Default $true)
)

$Checks = @(
  (New-Check -Id 'summon_preflight_readback' -Status $(if ($SummonPreflightObserved) { 'blocked_readback_ready' } else { 'missing_or_unexpected' }) -Passed $SummonPreflightObserved -Evidence 'scripts/lens-summon-preflight.ps1 -Mode Status' -Reason 'The direct summon preflight must name summon-anywhere as blocked and point to summon_anywhere_blockers.'),
  (New-Check -Id 'stage6_family_projection' -Status $(if ($Stage6FamilyProjectionObserved) { 'blocked_families_projected' } else { 'missing_or_unexpected' }) -Passed $Stage6FamilyProjectionObserved -Evidence 'summon preflight blockers projected into Stage 6 acceptance families' -Reason 'The handoff proof must expose the same blocker-family shape used by the Stage 6 completion audit.'),
  (New-Check -Id 'summon_side_effects_denied' -Status $(if ($SideEffectsDenied) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $SideEffectsDenied -Evidence 'lens.summon.preflight.governance' -Reason 'The proof must not grant summon, hotkey, overlay, process, memory, capture, sensing, approval-decision, or execution authority.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.summon_anywhere_blockers.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  stage = 'Stage 6 / Lens MVP'
  stage_state = 'active'
  acceptance_criterion = 'summon_anywhere'
  next_smallest_truthful_gap = 'summon_anywhere_blockers'
  summon_preflight_observed = $SummonPreflightObserved
  stage6_family_projection_observed = $Stage6FamilyProjectionObserved
  side_effects_denied = $SideEffectsDenied
  first_blocker_family = if (@($Stage6BlockedFamilies).Count -gt 0) { [string]$Stage6BlockedFamilies[0] } else { '' }
  blocked_families = [string[]]@($Stage6BlockedFamilies)
  blocker_groups = $Stage6BlockerGroups
  blockers = [string[]]@($SummonPreflightBlockers)
  summon_preflight = [ordered]@{
    status = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'status' -Default 'missing')
    ready = [bool](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'ready' -Default $false)
    summon_name = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'summon_name' -Default '')
    config_path = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'config_path' -Default '')
    global_hotkey = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'global_hotkey' -Default '')
    binding_scope = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'binding_scope' -Default '')
    palette_route = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'palette_route' -Default '')
    required_before_enable = [string[]]@($SummonPreflightRequiredBeforeEnable)
  }
  checks = @($Checks)
  evidence = @(
    'scripts/lens-summon-preflight.ps1 -Mode Status',
    'config/runtime/lens/summon.json',
    'docs/operations/COMPLETION_LEDGER.md',
    'docs/canonical/ROADMAP.md#4.12'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_summon_preflight = $true
    read_only_contract = [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'read_only_contract' -Default $false)
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = $false
    hotkey_registration_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Stage 6 summon-anywhere remains blocked by resident host, tray, overlay, global hotkey binding, summon binding, and authority gaps; this proof is read-only and grants no summon or runtime authority.'
}

$Payload | ConvertTo-Json -Depth 8
exit $(if ($ProofPassed) { 0 } else { 1 })
