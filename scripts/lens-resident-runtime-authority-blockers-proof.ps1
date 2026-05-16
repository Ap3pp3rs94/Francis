param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$DataDir = ''
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

function Select-Blockers {
  param(
    [string[]]$Blockers,
    [string[]]$Patterns
  )

  return [string[]]@(
    $Blockers | Where-Object {
      $Blocker = [string]$_
      foreach ($Pattern in $Patterns) {
        if ($Blocker -match $Pattern) {
          return $true
        }
      }
      return $false
    } | Sort-Object -Unique
  )
}

function New-AuthorityGroup {
  param(
    [string]$Id,
    [string]$Label,
    [string]$Route,
    [string[]]$Evidence,
    [string[]]$Blockers,
    [string[]]$RequiredBefore = @()
  )

  return [ordered]@{
    id = $Id
    label = $Label
    status = if ($Blockers.Count -gt 0) { 'blocked' } else { 'clear' }
    ready = $false
    authority_granted = $false
    would_execute = $false
    route = $Route
    evidence = [string[]]@($Evidence)
    required_before = [string[]]@($RequiredBefore)
    blockers = [string[]]@($Blockers)
  }
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$BoundaryProofScript = Join-Path $PSScriptRoot 'lens-resident-runtime-boundary-proof.ps1'
if (-not (Test-Path -LiteralPath $BoundaryProofScript -PathType Leaf)) {
  throw "Resident runtime boundary proof script is missing: $BoundaryProofScript"
}

$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command powershell -ErrorAction Stop
}

$BoundaryArgs = @('-Mode', $Mode)
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $BoundaryProofDataRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-resident-runtime-boundary-proof\" + [guid]::NewGuid().ToString('N') + "\data")
  $BoundaryArgs += @('-DataDir', $BoundaryProofDataRoot)
}

$BoundaryOutput = & $PowerShell.Source -NoProfile -ExecutionPolicy Bypass -File $BoundaryProofScript @BoundaryArgs 2>&1
$BoundaryExitCode = $LASTEXITCODE
$BoundaryText = ($BoundaryOutput | ForEach-Object { [string]$_ }) -join "`n"
$BoundaryPayload = $null
try {
  $BoundaryPayload = $BoundaryText | ConvertFrom-Json -ErrorAction Stop
} catch {
  $BoundaryPayload = $null
}

$Blockers = ConvertTo-StringArray -Value $BoundaryPayload.blockers
$ProcessBlockers = Select-Blockers -Blockers $Blockers -Patterns @(
  'local_process_launch',
  'process_supervision',
  'process_restart',
  'resident_host_process',
  'persistent_supervision'
)
$ServiceBlockers = Select-Blockers -Blockers $Blockers -Patterns @(
  'service_',
  'installable',
  'install_authority',
  'disabled_in_service_config'
)
$TrayBlockers = Select-Blockers -Blockers $Blockers -Patterns @(
  'tray',
  'notification'
)
$HotkeyBlockers = Select-Blockers -Blockers $Blockers -Patterns @(
  'hotkey',
  'summon',
  'global_hotkey'
)
$OverlayBlockers = Select-Blockers -Blockers $Blockers -Patterns @(
  'overlay',
  'window',
  'always_on_top',
  'capture'
)
$ResidentClaimBlockers = Select-Blockers -Blockers $Blockers -Patterns @(
  'resident_claim',
  'resident_surface_runtime',
  'lens_host_runtime'
)

$Groups = [ordered]@{
  process_supervision = New-AuthorityGroup `
    -Id 'process_supervision' `
    -Label 'Resident host process launch, supervision, and restart' `
    -Route '/lens/host/supervision/authority/readiness' `
    -Evidence @('/lens/host/supervision/authority', '/lens/host/supervision/authority/readiness') `
    -Blockers $ProcessBlockers `
    -RequiredBefore @('service_control', 'tray_presence', 'hotkey_summon', 'overlay_window', 'resident_claim')
  service_control = New-AuthorityGroup `
    -Id 'service_control' `
    -Label 'Service install, service config, and service control' `
    -Route '/lens/host/persistent-supervision/enablement' `
    -Evidence @('/lens/host/persistent-supervision/enablement', '/lens/host/persistent-supervision/enablement/execution/readiness') `
    -Blockers $ServiceBlockers `
    -RequiredBefore @('tray_presence', 'hotkey_summon', 'overlay_window', 'resident_claim')
  tray_presence = New-AuthorityGroup `
    -Id 'tray_presence' `
    -Label 'Tray presence and notification authority' `
    -Route '/lens/tray' `
    -Evidence @('/lens/tray') `
    -Blockers $TrayBlockers `
    -RequiredBefore @('resident_claim')
  hotkey_summon = New-AuthorityGroup `
    -Id 'hotkey_summon' `
    -Label 'Global hotkey and summon-anywhere authority' `
    -Route '/lens/summon' `
    -Evidence @('/lens/summon') `
    -Blockers $HotkeyBlockers `
    -RequiredBefore @('resident_claim')
  overlay_window = New-AuthorityGroup `
    -Id 'overlay_window' `
    -Label 'Overlay window, focus, dock, and capture authority' `
    -Route '/lens/overlay' `
    -Evidence @('/lens/overlay') `
    -Blockers $OverlayBlockers `
    -RequiredBefore @('resident_claim')
  resident_claim = New-AuthorityGroup `
    -Id 'resident_claim' `
    -Label 'Resident runtime claim authority' `
    -Route '/lens/resident-runtime/plan' `
    -Evidence @('/lens/resident-runtime/plan', '/lens/resident-runtime/execute') `
    -Blockers $ResidentClaimBlockers
}

$RemainingFamilies = [string[]]@(
  foreach ($Entry in $Groups.GetEnumerator()) {
    if ([string]$Entry.Value.status -eq 'blocked') {
      [string]$Entry.Key
    }
  }
)
$BoundaryObserved = (
  [int]$BoundaryExitCode -eq 0 -and
  [string]$BoundaryPayload.kind -eq 'lens.resident_runtime.granted_boundary_proof' -and
  [string]$BoundaryPayload.status -eq 'proof_passed' -and
  [bool]$BoundaryPayload.resident_runtime_execution_authority -and
  -not [bool]$BoundaryPayload.runtime_ready -and
  -not [bool]$BoundaryPayload.resident_claim_allowed -and
  -not [bool]$BoundaryPayload.executed
)
$ExpectedFamiliesBlocked = @(
  'process_supervision',
  'service_control',
  'tray_presence',
  'hotkey_summon',
  'overlay_window',
  'resident_claim'
) | Where-Object { $RemainingFamilies -contains $_ }
$ProofPassed = $BoundaryObserved -and $ExpectedFamiliesBlocked.Count -eq 6

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.resident_runtime.authority_blockers_proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  boundary_proof = [ordered]@{
    ok = $BoundaryObserved
    exit_code = [int]$BoundaryExitCode
    kind = [string]$BoundaryPayload.kind
    status = [string]$BoundaryPayload.status
    resident_runtime_execution_authority = [bool]$BoundaryPayload.resident_runtime_execution_authority
    runtime_ready = [bool]$BoundaryPayload.runtime_ready
    resident_claim_allowed = [bool]$BoundaryPayload.resident_claim_allowed
    applied = [bool]$BoundaryPayload.applied
    executed = [bool]$BoundaryPayload.executed
    would_launch_process = [bool]$BoundaryPayload.would_launch_process
    would_supervise_process = [bool]$BoundaryPayload.would_supervise_process
    would_start_service = [bool]$BoundaryPayload.would_start_service
    would_register_tray = [bool]$BoundaryPayload.would_register_tray
    would_register_hotkey = [bool]$BoundaryPayload.would_register_hotkey
    would_open_overlay = [bool]$BoundaryPayload.would_open_overlay
    would_write_memory = [bool]$BoundaryPayload.would_write_memory
    would_claim_resident = [bool]$BoundaryPayload.would_claim_resident
    combined_next_smallest_truthful_gap = [string]$BoundaryPayload.next_smallest_truthful_gap
  }
  authority_blocker_groups = $Groups
  remaining_authority_families = $RemainingFamilies
  authority_required = 'process_supervision_authority'
  authority_granted = $false
  summary = [ordered]@{
    blocker_total = [int]$Blockers.Count
    authority_family_total = 6
    blocked_authority_family_total = [int]$RemainingFamilies.Count
    combined_gap_split = $ProofPassed
  }
  next_smallest_truthful_gap = 'resident_runtime_process_supervision_authority_boundary'
  evidence = @(
    'scripts/lens-resident-runtime-boundary-proof.ps1 -Mode Status',
    '/lens/resident-runtime/execute',
    '/lens/host/supervision/authority/readiness',
    '/lens/host/persistent-supervision/enablement',
    '/lens/summon',
    '/lens/tray',
    '/lens/overlay'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_existing_boundary_proof = $true
    approval_request_write = [bool]$BoundaryPayload.governance.approval_request_write
    approval_decision_authority = $false
    resident_runtime_execution_authority = [bool]$BoundaryPayload.resident_runtime_execution_authority
    execution_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    tray_registration_authority = $false
    hotkey_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
}

$Payload | ConvertTo-Json -Depth 8
exit $(if ($ProofPassed) { 0 } else { 1 })
