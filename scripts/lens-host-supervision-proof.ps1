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

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

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
    [string]$PowerShellPath,
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

function Get-CheckById {
  param(
    [object[]]$Checks,
    [string]$Id
  )

  foreach ($Check in @($Checks)) {
    if ([string](Get-PropertyValue -Payload $Check -Name 'id' -Default '') -eq $Id) {
      return $Check
    }
  }
  return $null
}

$PowerShellPath = Get-PowerShellPath
$HostPreflightPath = Join-Path $PSScriptRoot 'lens-host-preflight.ps1'
$ForegroundProofPath = Join-Path $PSScriptRoot 'lens-host-foreground-proof.ps1'
$HostLaunchProofPath = Join-Path $PSScriptRoot 'lens-host-launch-proof.ps1'
$ObservedForegroundRunSeconds = [Math]::Max($ForegroundRunSeconds, 5)
$HostPreflight = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $HostPreflightPath -ScriptArgs @('-Mode', 'Status')
$ForegroundProof = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $ForegroundProofPath -ScriptArgs @('-Mode', 'Status', '-RunSeconds', [string]$ObservedForegroundRunSeconds)
$HostLaunchProof = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $HostLaunchProofPath -ScriptArgs @('-Mode', 'Status', '-RunSeconds', [string]$HostLaunchRunSeconds)

$PreflightPayload = Get-PropertyValue -Payload $HostPreflight -Name 'payload'
$ForegroundPayload = Get-PropertyValue -Payload $ForegroundProof -Name 'payload'
$HostLaunchPayload = Get-PropertyValue -Payload $HostLaunchProof -Name 'payload'
$ServicePlan = Get-PropertyValue -Payload $PreflightPayload -Name 'service_plan'
$Service = Get-PropertyValue -Payload $PreflightPayload -Name 'service'
$PreflightGovernance = Get-PropertyValue -Payload $PreflightPayload -Name 'governance'
$ServicePlanGovernance = Get-PropertyValue -Payload $ServicePlan -Name 'governance'
$PreflightChecks = @(Get-PropertyValue -Payload $PreflightPayload -Name 'checks' -Default @())
$ProcessSupervisionCheck = Get-CheckById -Checks $PreflightChecks -Id 'process_supervision'
$ServiceControlCheck = Get-CheckById -Checks $PreflightChecks -Id 'service_control_authority'

$PreflightOk = (
  [int](Get-PropertyValue -Payload $HostPreflight -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $PreflightPayload -Name 'kind' -Default '') -eq 'lens.host.lifecycle_preflight' -and
  [string](Get-PropertyValue -Payload $PreflightPayload -Name 'status' -Default '') -eq 'blocked'
)
$ForegroundProofOk = (
  [int](Get-PropertyValue -Payload $ForegroundProof -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $ForegroundPayload -Name 'kind' -Default '') -eq 'lens.host.foreground_readiness_proof' -and
  [string](Get-PropertyValue -Payload $ForegroundPayload -Name 'status' -Default '') -eq 'proof_passed'
)
$HostLaunchProofOk = (
  [int](Get-PropertyValue -Payload $HostLaunchProof -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $HostLaunchPayload -Name 'kind' -Default '') -eq 'lens.host.launch_readiness_proof' -and
  [string](Get-PropertyValue -Payload $HostLaunchPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $HostLaunchPayload -Name 'bounded_host_launch_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostLaunchPayload -Name 'launch_authority_boundary' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostLaunchPayload -Name 'launch_completed' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $HostLaunchPayload -Name 'ready_for_resident_claim' -Default $true)
)
$ServicePlanBlocked = (
  [string](Get-PropertyValue -Payload $ServicePlan -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $ServicePlan -Name 'ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ServicePlan -Name 'would_install' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ServicePlan -Name 'would_start' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ServicePlan -Name 'wrapper_would_write' -Default $true)
)
$ServiceNotInstalled = -not [bool](Get-PropertyValue -Payload $Service -Name 'installed' -Default $true)
$SupervisionDisabled = [string](Get-PropertyValue -Payload $ProcessSupervisionCheck -Name 'status' -Default '') -eq 'blocked'
$ServiceControlDenied = (
  [string](Get-PropertyValue -Payload $ServiceControlCheck -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $PreflightGovernance -Name 'service_control_authority' -Default $true)
)
$NoInstallAuthority = (
  -not [bool](Get-PropertyValue -Payload $ServicePlanGovernance -Name 'service_install_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ServicePlanGovernance -Name 'local_process_launch_authority' -Default $true)
)

$Checks = @(
  (New-Check -Id 'host_lifecycle_preflight' -Status $(if ($PreflightOk) { 'blocked_readback_ready' } else { 'failed' }) -Passed $PreflightOk -Evidence 'scripts/lens-host-preflight.ps1 -Mode Status' -Reason 'Lifecycle preflight must be readable and blocked.')
  (New-Check -Id 'foreground_readiness_proof' -Status $(if ($ForegroundProofOk) { 'proof_passed' } else { 'failed' }) -Passed $ForegroundProofOk -Evidence 'scripts/lens-host-foreground-proof.ps1 -Mode Status' -Reason 'Bounded foreground process readback must be observable.')
  (New-Check -Id 'bounded_launch_proof' -Status $(if ($HostLaunchProofOk) { 'bounded_launch_observed' } else { 'failed' }) -Passed $HostLaunchProofOk -Evidence 'scripts/lens-host-launch-proof.ps1 -Mode Status' -Reason 'Bounded launch evidence must show one observed self-stopping host launch without claiming resident supervision.')
  (New-Check -Id 'service_plan_no_install' -Status $(if ($ServicePlanBlocked) { 'blocked_no_install' } else { 'failed' }) -Passed $ServicePlanBlocked -Evidence 'service_plan' -Reason 'Service plan must remain read-only and non-installing.')
  (New-Check -Id 'service_not_installed' -Status $(if ($ServiceNotInstalled) { 'not_installed' } else { 'installed' }) -Passed $ServiceNotInstalled -Evidence 'service.status' -Reason 'Resident host service is not installed by this proof.')
  (New-Check -Id 'process_supervision_disabled' -Status $(if ($SupervisionDisabled) { 'blocked' } else { 'unexpected' }) -Passed $SupervisionDisabled -Evidence 'process_supervision_enabled' -Reason 'Process supervision remains disabled until a later authority-changing slice.')
  (New-Check -Id 'service_control_denied' -Status $(if ($ServiceControlDenied) { 'blocked' } else { 'unexpected' }) -Passed $ServiceControlDenied -Evidence 'service_control_authority' -Reason 'Service start/stop/restart authority remains denied.')
  (New-Check -Id 'install_authority_denied' -Status $(if ($NoInstallAuthority) { 'blocked' } else { 'unexpected' }) -Passed $NoInstallAuthority -Evidence 'service_install_authority' -Reason 'Service install and service-plan launch authority remain denied.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })
$PreflightBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $PreflightPayload -Name 'blockers' -Default @())
$ForegroundBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ForegroundPayload -Name 'blockers' -Default @())
$HostLaunchBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostLaunchPayload -Name 'blockers' -Default @())
$AllBlockers = @($PreflightBlockers + $ForegroundBlockers + $HostLaunchBlockers + @(
  'resident_host_process_not_supervised',
  'resident_supervision_disabled',
  'resident_surface_runtime_missing'
  ) | Sort-Object -Unique)

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.host.supervision_readiness_proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  foreground_run_seconds = $ObservedForegroundRunSeconds
  requested_foreground_run_seconds = $ForegroundRunSeconds
  host_launch_run_seconds = $HostLaunchRunSeconds
  supervision_ready = $false
  ready_for_resident_claim = $false
  resident_claim_allowed = $false
  bounded_host_launch_observed = $HostLaunchProofOk
  resident_host_process = $false
  service_installed = $false
  supervised = $false
  service_managed = $false
  tray_presence = $false
  global_hotkey = $false
  overlay_window = $false
  summon_anywhere = $false
  checks = @($Checks)
  blockers = @($AllBlockers)
  proof = [ordered]@{
    lifecycle_preflight_status = [string](Get-PropertyValue -Payload $PreflightPayload -Name 'status' -Default '')
    foreground_proof_status = [string](Get-PropertyValue -Payload $ForegroundPayload -Name 'status' -Default '')
    foreground_process_observed = [bool](Get-PropertyValue -Payload $ForegroundPayload -Name 'foreground_process_observed' -Default $false)
    foreground_status_readback_matched = [bool](Get-PropertyValue -Payload $ForegroundPayload -Name 'foreground_status_readback_matched' -Default $false)
    foreground_completed = [bool](Get-PropertyValue -Payload $ForegroundPayload -Name 'foreground_completed' -Default $false)
    host_launch_proof_status = [string](Get-PropertyValue -Payload $HostLaunchPayload -Name 'status' -Default '')
    bounded_host_launch_observed = [bool](Get-PropertyValue -Payload $HostLaunchPayload -Name 'bounded_host_launch_observed' -Default $false)
    host_launch_completed = [bool](Get-PropertyValue -Payload $HostLaunchPayload -Name 'launch_completed' -Default $false)
    host_launch_authority_boundary = [bool](Get-PropertyValue -Payload $HostLaunchPayload -Name 'launch_authority_boundary' -Default $false)
    host_launch_ready_for_resident_claim = [bool](Get-PropertyValue -Payload $HostLaunchPayload -Name 'ready_for_resident_claim' -Default $true)
    service_plan_status = [string](Get-PropertyValue -Payload $ServicePlan -Name 'status' -Default '')
    service_plan_ready = [bool](Get-PropertyValue -Payload $ServicePlan -Name 'ready' -Default $false)
    service_plan_would_install = [bool](Get-PropertyValue -Payload $ServicePlan -Name 'would_install' -Default $false)
    service_plan_would_start = [bool](Get-PropertyValue -Payload $ServicePlan -Name 'would_start' -Default $false)
    service_plan_blocked_by = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ServicePlan -Name 'blocked_by' -Default @())
    service_status = [string](Get-PropertyValue -Payload $Service -Name 'status' -Default '')
    process_supervision_status = [string](Get-PropertyValue -Payload $ProcessSupervisionCheck -Name 'status' -Default '')
    service_control_status = [string](Get-PropertyValue -Payload $ServiceControlCheck -Name 'status' -Default '')
  }
  next_smallest_truthful_gap = 'resident_host_supervision_or_resident_overlay_runtime'
  governance = [ordered]@{
    read_only_contract = $true
    diagnostic_only = $true
    bounded_foreground_session = $true
    bounded_host_launch = $HostLaunchProofOk
    bounded_process_launch = $HostLaunchProofOk
    temporary_runtime_state_write = $true
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = $HostLaunchProofOk
    api_local_process_launch_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Lens host supervision readiness is observable and still blocked; this proof does not install, start, supervise, or expose a resident host.'
}

$Payload | ConvertTo-Json -Depth 10
if ($ProofPassed) {
  exit 0
}
exit 1
