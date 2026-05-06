[CmdletBinding()]
param(
  [ValidateSet('Status', 'Open')]
  [string]$Mode = 'Status',
  [string]$ApiBaseUrl = 'http://127.0.0.1:8000',
  [string]$StatusPath = '',
  [string]$ExecutionReadinessPath = '',
  [int]$TimeoutSeconds = 5
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

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

function Get-PropertyValue {
  param(
    [object]$Payload,
    [string]$Name,
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
  param([object]$Value)

  $Items = [System.Collections.ArrayList]::new()
  if ($null -eq $Value) {
    return @($Items.ToArray())
  }
  if ($Value -is [System.Array]) {
    foreach ($Item in $Value) {
      $Text = [string]$Item
      if (-not [string]::IsNullOrWhiteSpace($Text)) {
        [void]$Items.Add($Text)
      }
    }
    return @($Items.ToArray())
  }
  $SingleValue = [string]$Value
  if (-not [string]::IsNullOrWhiteSpace($SingleValue)) {
    [void]$Items.Add($SingleValue)
  }
  return @($Items.ToArray())
}

function ConvertTo-CommandItems {
  param([object]$Value)

  $Items = [System.Collections.ArrayList]::new()
  if ($null -eq $Value -or -not ($Value -is [System.Array])) {
    return @($Items.ToArray())
  }
  foreach ($Item in $Value) {
    $Id = [string](Get-PropertyValue -Payload $Item -Name 'id' -Default '')
    if ([string]::IsNullOrWhiteSpace($Id)) {
      continue
    }
    [void]$Items.Add([ordered]@{
        id = $Id
        label = [string](Get-PropertyValue -Payload $Item -Name 'label' -Default '')
        group = [string](Get-PropertyValue -Payload $Item -Name 'group' -Default 'Other')
        route = [string](Get-PropertyValue -Payload $Item -Name 'route' -Default '')
        action = [string](Get-PropertyValue -Payload $Item -Name 'action' -Default '')
        mutates = [bool](Get-PropertyValue -Payload $Item -Name 'mutates' -Default $false)
        write_guard = [string](Get-PropertyValue -Payload $Item -Name 'write_guard' -Default '')
        execution_authority = [bool](Get-PropertyValue -Payload $Item -Name 'execution_authority' -Default $false)
        approval_decision_authority = [bool](Get-PropertyValue -Payload $Item -Name 'approval_decision_authority' -Default $false)
        memory_write = [bool](Get-PropertyValue -Payload $Item -Name 'memory_write' -Default $false)
      })
  }
  return @($Items.ToArray())
}

function Read-LensStatus {
  param(
    [string]$StatusPath,
    [string]$ApiBaseUrl,
    [int]$TimeoutSeconds
  )

  if (-not [string]::IsNullOrWhiteSpace($StatusPath)) {
    $ResolvedStatusPath = (Resolve-Path -LiteralPath $StatusPath -ErrorAction Stop).Path
    return [ordered]@{
      ok = $true
      source = 'status_path'
      evidence = $ResolvedStatusPath
      payload = Get-Content -LiteralPath $ResolvedStatusPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
      error = ''
    }
  }

  $Base = $ApiBaseUrl.TrimEnd('/')
  $Url = "$Base/lens/status?limit=5"
  try {
    return [ordered]@{
      ok = $true
      source = 'api'
      evidence = $Url
      payload = Invoke-RestMethod -Method Get -Uri $Url -TimeoutSec ([Math]::Max(1, $TimeoutSeconds))
      error = ''
    }
  } catch {
    return [ordered]@{
      ok = $false
      source = 'api'
      evidence = $Url
      payload = $null
      error = [string]$_.Exception.Message
    }
  }
}

function Read-ExecutionReadiness {
  param(
    [string]$ExecutionReadinessPath,
    [string]$ApiBaseUrl,
    [int]$TimeoutSeconds
  )

  if (-not [string]::IsNullOrWhiteSpace($ExecutionReadinessPath)) {
    $ResolvedExecutionReadinessPath = (Resolve-Path -LiteralPath $ExecutionReadinessPath -ErrorAction Stop).Path
    return [ordered]@{
      ok = $true
      source = 'execution_readiness_path'
      evidence = $ResolvedExecutionReadinessPath
      payload = Get-Content -LiteralPath $ResolvedExecutionReadinessPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
      error = ''
    }
  }

  $Base = $ApiBaseUrl.TrimEnd('/')
  $Url = "$Base/lens/os-binding/execution/readiness?limit=5"
  try {
    return [ordered]@{
      ok = $true
      source = 'api'
      evidence = $Url
      payload = Invoke-RestMethod -Method Get -Uri $Url -TimeoutSec ([Math]::Max(1, $TimeoutSeconds))
      error = ''
    }
  } catch {
    return [ordered]@{
      ok = $false
      source = 'api'
      evidence = $Url
      payload = $null
      error = [string]$_.Exception.Message
    }
  }
}

$StatusRead = Read-LensStatus -StatusPath $StatusPath -ApiBaseUrl $ApiBaseUrl -TimeoutSeconds $TimeoutSeconds
$StatusPayload = Get-PropertyValue -Payload $StatusRead -Name 'payload'
$Palette = Get-PropertyValue -Payload $StatusPayload -Name 'command_palette'
$PaletteStatus = [string](Get-PropertyValue -Payload $Palette -Name 'status' -Default '')
$PaletteAvailability = [string](Get-PropertyValue -Payload $Palette -Name 'availability' -Default '')
$PaletteRoute = [string](Get-PropertyValue -Payload $Palette -Name 'route' -Default '/lens/status')
$LocalSurface = [string](Get-PropertyValue -Payload $Palette -Name 'local_surface' -Default '')
$Commands = ConvertTo-CommandItems -Value (Get-PropertyValue -Payload $Palette -Name 'commands' -Default @())
$CommandTotal = [int](Get-PropertyValue -Payload $Palette -Name 'command_total' -Default @($Commands).Count)
$SummonAnywhere = [bool](Get-PropertyValue -Payload $Palette -Name 'summon_anywhere' -Default $false)
$ReadbackReady = (
  [bool](Get-PropertyValue -Payload $StatusRead -Name 'ok' -Default $false) -and
  $PaletteStatus -eq 'readback_ready' -and
  @($Commands).Count -gt 0
)
$OsLevelReady = $ReadbackReady -and $PaletteAvailability -eq 'os_level' -and $SummonAnywhere

$Blockers = [System.Collections.ArrayList]::new()
if (-not [bool](Get-PropertyValue -Payload $StatusRead -Name 'ok' -Default $false)) {
  [void]$Blockers.Add('lens_status_api_unavailable')
}
if (-not $ReadbackReady) {
  [void]$Blockers.Add('command_palette_readback_missing')
}
if (-not $OsLevelReady) {
  [void]$Blockers.Add('os_level_command_palette_missing')
}
if (-not $SummonAnywhere) {
  [void]$Blockers.Add('summon_anywhere_missing')
  [void]$Blockers.Add('global_hotkey_binding_missing')
}

$Checks = @(
  (New-Check -Id 'lens_status_readback' -Status $(if ([bool](Get-PropertyValue -Payload $StatusRead -Name 'ok' -Default $false)) { 'available' } else { 'unavailable' }) -Passed ([bool](Get-PropertyValue -Payload $StatusRead -Name 'ok' -Default $false)) -Evidence ([string](Get-PropertyValue -Payload $StatusRead -Name 'evidence' -Default '')) -Reason 'Lens command-palette shell bridge must consume existing Lens status truth.')
  (New-Check -Id 'command_palette_readback' -Status $(if ($ReadbackReady) { 'readback_ready' } else { 'missing' }) -Passed $ReadbackReady -Evidence $PaletteRoute -Reason 'Palette commands must come from Lens status readback, not local shell invention.')
  (New-Check -Id 'os_level_palette_binding' -Status $(if ($OsLevelReady) { 'ready' } else { 'blocked' }) -Passed $OsLevelReady -Evidence $PaletteAvailability -Reason 'OS-level palette binding remains blocked until a real resident summon surface exists.')
)

$Payload = [ordered]@{
  ok = $ReadbackReady
  kind = 'lens.command_palette.shell_bridge'
  status = if ($OsLevelReady) { 'ready' } elseif ($ReadbackReady) { 'blocked' } else { 'unavailable' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  backend_source = [string](Get-PropertyValue -Payload $StatusRead -Name 'source' -Default '')
  backend_evidence = [string](Get-PropertyValue -Payload $StatusRead -Name 'evidence' -Default '')
  backend_error = [string](Get-PropertyValue -Payload $StatusRead -Name 'error' -Default '')
  readback_ready = $ReadbackReady
  os_level_command_palette = $OsLevelReady
  summon_anywhere = $SummonAnywhere
  availability = $PaletteAvailability
  route = $PaletteRoute
  local_surface = $LocalSurface
  command_total = $CommandTotal
  commands = @($Commands)
  checks = @($Checks)
  blockers = @($Blockers.ToArray())
  next_smallest_truthful_gap = 'os_level_command_palette_binding'
  governance = [ordered]@{
    read_only_contract = $true
    opens_palette = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    summon_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    local_process_launch_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Lens command-palette shell bridge is read-only; it reports backend palette truth but does not open an OS palette, register hotkeys, summon Francis, or control overlay/tray surfaces.'
}

if ($Mode -eq 'Status') {
  $Payload | ConvertTo-Json -Depth 10
  exit 0
}

$ExecutionReadinessRead = Read-ExecutionReadiness -ExecutionReadinessPath $ExecutionReadinessPath -ApiBaseUrl $ApiBaseUrl -TimeoutSeconds $TimeoutSeconds
$ExecutionReadinessPayload = Get-PropertyValue -Payload $ExecutionReadinessRead -Name 'payload'
$ExecutionReadinessBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ExecutionReadinessPayload -Name 'blockers' -Default @())
$ExecutionReadinessBlockedRequirements = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ExecutionReadinessPayload -Name 'blocked_requirements' -Default @())
$ExecutionReadinessRequiredBeforeBoundary = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ExecutionReadinessPayload -Name 'required_before_execution_boundary' -Default @())
$ExecutionReadinessBlockedPrerequisites = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ExecutionReadinessPayload -Name 'blocked_execution_prerequisites' -Default @())
$ExecutionBoundaryHandoff = Get-PropertyValue -Payload $ExecutionReadinessPayload -Name 'execution_boundary_handoff'
$ExecutionBoundaryHandoffBlockedRequirements = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ExecutionBoundaryHandoff -Name 'blocked_requirements' -Default @())
$ExecutionBoundaryHandoffBlockedSurfaces = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ExecutionBoundaryHandoff -Name 'blocked_surface_prerequisites' -Default @())
$ExecutionBoundaryHandoffRequiredBeforeBoundary = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ExecutionBoundaryHandoff -Name 'required_before_execution_boundary' -Default @())

$Payload.ok = $false
$Payload.status = 'refused'
$Payload.error = 'lens_command_palette_open_not_authorized'
$Payload.execution_readiness = [ordered]@{
  ok = [bool](Get-PropertyValue -Payload $ExecutionReadinessRead -Name 'ok' -Default $false)
  source = [string](Get-PropertyValue -Payload $ExecutionReadinessRead -Name 'source' -Default '')
  evidence = [string](Get-PropertyValue -Payload $ExecutionReadinessRead -Name 'evidence' -Default '')
  error = [string](Get-PropertyValue -Payload $ExecutionReadinessRead -Name 'error' -Default '')
  kind = [string](Get-PropertyValue -Payload $ExecutionReadinessPayload -Name 'kind' -Default '')
  status = [string](Get-PropertyValue -Payload $ExecutionReadinessPayload -Name 'status' -Default '')
  route = [string](Get-PropertyValue -Payload $ExecutionReadinessPayload -Name 'route' -Default '/lens/os-binding/execution/readiness')
  execute_route = [string](Get-PropertyValue -Payload $ExecutionReadinessPayload -Name 'execute_route' -Default '/lens/os-binding/execute')
  ready = [bool](Get-PropertyValue -Payload $ExecutionReadinessPayload -Name 'ready' -Default $false)
  execution_ready = [bool](Get-PropertyValue -Payload $ExecutionReadinessPayload -Name 'execution_ready' -Default $false)
  authority_granted = [bool](Get-PropertyValue -Payload $ExecutionReadinessPayload -Name 'authority_granted' -Default $false)
  os_level_command_palette_binding_authority = [bool](Get-PropertyValue -Payload $ExecutionReadinessPayload -Name 'os_level_command_palette_binding_authority' -Default $false)
  denial_boundary_observed = [bool](Get-PropertyValue -Payload $ExecutionReadinessPayload -Name 'denial_boundary_observed' -Default $false)
  denial_receipt_readback_ready = [bool](Get-PropertyValue -Payload $ExecutionReadinessPayload -Name 'denial_receipt_readback_ready' -Default $false)
  execution_prerequisites_ready = [bool](Get-PropertyValue -Payload $ExecutionReadinessPayload -Name 'execution_prerequisites_ready' -Default $false)
  required_before_execution_boundary = @($ExecutionReadinessRequiredBeforeBoundary)
  blocked_requirements = @($ExecutionReadinessBlockedRequirements)
  blocked_execution_prerequisites = @($ExecutionReadinessBlockedPrerequisites)
  blockers = @($ExecutionReadinessBlockers)
  next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $ExecutionReadinessPayload -Name 'next_smallest_truthful_gap' -Default '')
  execution_boundary_handoff = [ordered]@{
    status = [string](Get-PropertyValue -Payload $ExecutionBoundaryHandoff -Name 'status' -Default '')
    route = [string](Get-PropertyValue -Payload $ExecutionBoundaryHandoff -Name 'route' -Default '/lens/os-binding/execute')
    readiness_route = [string](Get-PropertyValue -Payload $ExecutionBoundaryHandoff -Name 'readiness_route' -Default '/lens/os-binding/execution/readiness')
    next_step = [string](Get-PropertyValue -Payload $ExecutionBoundaryHandoff -Name 'next_step' -Default '')
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $ExecutionBoundaryHandoff -Name 'next_smallest_truthful_gap' -Default '')
    required_before_execution_boundary = @($ExecutionBoundaryHandoffRequiredBeforeBoundary)
    blocked_requirements = @($ExecutionBoundaryHandoffBlockedRequirements)
    blocked_surface_prerequisites = @($ExecutionBoundaryHandoffBlockedSurfaces)
    read_only_contract = [bool](Get-PropertyValue -Payload $ExecutionBoundaryHandoff -Name 'read_only_contract' -Default $true)
    would_execute = [bool](Get-PropertyValue -Payload $ExecutionBoundaryHandoff -Name 'would_execute' -Default $false)
    would_open_palette = [bool](Get-PropertyValue -Payload $ExecutionBoundaryHandoff -Name 'would_open_palette' -Default $false)
    would_register_hotkey = [bool](Get-PropertyValue -Payload $ExecutionBoundaryHandoff -Name 'would_register_hotkey' -Default $false)
    would_summon = [bool](Get-PropertyValue -Payload $ExecutionBoundaryHandoff -Name 'would_summon' -Default $false)
    would_control_overlay = [bool](Get-PropertyValue -Payload $ExecutionBoundaryHandoff -Name 'would_control_overlay' -Default $false)
    would_launch_process = [bool](Get-PropertyValue -Payload $ExecutionBoundaryHandoff -Name 'would_launch_process' -Default $false)
    would_write_memory = [bool](Get-PropertyValue -Payload $ExecutionBoundaryHandoff -Name 'would_write_memory' -Default $false)
  }
}
$Payload.refusal_blockers = @($ExecutionReadinessBlockers)
$Payload.governance.execution_readiness_readback = [bool](Get-PropertyValue -Payload $ExecutionReadinessRead -Name 'ok' -Default $false)
$Payload.governance.execution_readiness_route = '/lens/os-binding/execution/readiness'
$Payload.message = 'Opening or binding an OS-level Lens command palette is not authorized by this shell bridge; use Status for read-only inspection.'
$Payload | ConvertTo-Json -Depth 10
exit 2
