param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [ValidateRange(30, 240)]
  [int]$ChildProofTimeoutSeconds = 180
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

function Quote-ProcessArgument {
  param([string]$Value)

  if ($null -eq $Value) {
    return '""'
  }
  return '"' + ($Value -replace '"', '\"') + '"'
}

function Stop-ProcessTree {
  param([System.Diagnostics.Process]$Process)

  if ($null -eq $Process -or $Process.HasExited) {
    return
  }

  try {
    $Process.Kill($true)
  } catch {
    try {
      $Process.Kill()
    } catch {
    }
  }
}

function Invoke-JsonProcess {
  param(
    [Parameter(Mandatory = $true)]
    [string]$FileName,

    [string[]]$ProcessArgs = @(),

    [int]$TimeoutSeconds = $ChildProofTimeoutSeconds
  )

  $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
  $StartInfo.FileName = $FileName
  $StartInfo.Arguments = (@($ProcessArgs) | ForEach-Object { Quote-ProcessArgument -Value $_ }) -join ' '
  $StartInfo.WorkingDirectory = $RepoRoot
  $StartInfo.UseShellExecute = $false
  $StartInfo.CreateNoWindow = $true
  $StartInfo.RedirectStandardOutput = $true
  $StartInfo.RedirectStandardError = $true

  $Process = [System.Diagnostics.Process]::new()
  $Process.StartInfo = $StartInfo
  $Timer = [System.Diagnostics.Stopwatch]::StartNew()
  try {
    $Started = $Process.Start()
  } catch {
    $Timer.Stop()
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
      error = [string]$_.Exception.Message
      timed_out = $false
      timeout_seconds = $TimeoutSeconds
      duration_ms = [int]$Timer.ElapsedMilliseconds
    }
  }

  if (-not $Started) {
    $Timer.Stop()
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
      error = 'process_not_started'
      timed_out = $false
      timeout_seconds = $TimeoutSeconds
      duration_ms = [int]$Timer.ElapsedMilliseconds
    }
  }

  $StdoutTask = $Process.StandardOutput.ReadToEndAsync()
  $StderrTask = $Process.StandardError.ReadToEndAsync()
  $Exited = $Process.WaitForExit($TimeoutSeconds * 1000)
  if (-not $Exited) {
    Stop-ProcessTree -Process $Process
    [void]$Process.WaitForExit(5000)
    $Timer.Stop()
    return [ordered]@{
      exit_code = 124
      payload = $null
      output = ''
      error = 'timeout'
      timed_out = $true
      timeout_seconds = $TimeoutSeconds
      duration_ms = [int]$Timer.ElapsedMilliseconds
    }
  }

  $Text = $StdoutTask.GetAwaiter().GetResult()
  $ErrorText = $StderrTask.GetAwaiter().GetResult()
  $Timer.Stop()
  $Payload = $null
  try {
    $Payload = $Text | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $Payload = $null
  }

  return [ordered]@{
    exit_code = [int]$Process.ExitCode
    payload = $Payload
    output = $Text
    error = $ErrorText
    timed_out = $false
    timeout_seconds = $TimeoutSeconds
    duration_ms = [int]$Timer.ElapsedMilliseconds
  }
}

function Get-PythonPath {
  $Python = Get-Command python -ErrorAction SilentlyContinue
  if ($null -ne $Python) {
    return [string]$Python.Source
  }
  $Py = Get-Command py -ErrorAction SilentlyContinue
  if ($null -ne $Py) {
    return [string]$Py.Source
  }
  return ''
}

function Test-StringArrayExact {
  param(
    [string[]]$Actual,
    [string[]]$Expected
  )

  if (@($Actual).Count -ne @($Expected).Count) {
    return $false
  }
  for ($Index = 0; $Index -lt @($Expected).Count; $Index += 1) {
    if ([string]$Actual[$Index] -ne [string]$Expected[$Index]) {
      return $false
    }
  }
  return $true
}

function Get-DependencyById {
  param(
    [AllowNull()]
    [object[]]$Items,
    [string]$Id
  )

  foreach ($Item in @($Items)) {
    if ([string](Get-PropertyValue -Payload $Item -Name 'id' -Default '') -eq $Id) {
      return $Item
    }
  }
  return $null
}

function Test-GovernanceDenied {
  param(
    [AllowNull()]
    [object]$Governance,
    [string[]]$FalseKeys
  )

  foreach ($Key in @($FalseKeys)) {
    if ([bool](Get-PropertyValue -Payload $Governance -Name $Key -Default $false)) {
      return $false
    }
  }
  return $true
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

if ([string]::IsNullOrWhiteSpace($DataDir)) {
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-persistent-supervision-prerequisites-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}
$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$PythonPath = Get-PythonPath
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
  [ordered]@{
    ok = $false
    kind = 'lens.persistent_supervision.prerequisites.proof'
    status = 'proof_failed'
    error = 'python_unavailable'
  } | ConvertTo-Json -Depth 5
  exit 1
}

$PreviousRoot = [string]$env:FRANCIS_ROOT
$PreviousDataDir = [string]$env:FRANCIS_DATA_DIR
$PreviousProfile = [string]$env:FRANCIS_ENV_PROFILE
$PreviousRunMode = [string]$env:FRANCIS_RUN_MODE
$PreviousPythonPath = [string]$env:PYTHONPATH

$RouteSource = @'
import json
from copy import deepcopy
from fastapi.testclient import TestClient

from francis.api.app import create_app
from francis.lens.host_manifest import (
    lens_host_launch_manifest,
    lens_host_persistent_supervision_enablement_preflight,
    lens_host_persistent_supervision_plan,
)


def get(client, route):
    response = client.get(route)
    body = response.json()
    if response.status_code != 200:
        raise RuntimeError(f"{route} returned {response.status_code}: {body!r}")
    return body


client = TestClient(create_app())
status = get(client, "/lens/status?limit=5")
resident_host = status.get("resident_host") if isinstance(status.get("resident_host"), dict) else {}
manifest = lens_host_launch_manifest()
guard_manifest = deepcopy(manifest)
guard_supervision = guard_manifest.get("supervision_readiness")
if not isinstance(guard_supervision, dict):
    guard_supervision = {}
guard_supervision.update(
    {
        "authority_grant_active": True,
        "authority_grant": {
            "receipt_id": "synthetic-required-prerequisite-guard",
            "status": "authority_granted",
        },
        "process_supervision_enabled": True,
        "persistent_supervision_enabled": True,
        "process_restart_authority": True,
        "service_install_authority": True,
        "service_control_authority": True,
        "receipt_write_authority": True,
        "resident_claim_authority": True,
    }
)
guard_manifest["supervision_readiness"] = guard_supervision
payload = {
    "plan": get(client, "/lens/host/persistent-supervision"),
    "enablement": get(client, "/lens/host/persistent-supervision/enablement"),
    "required_prerequisite_guard": {
        "projection": "synthetic_manifest_readiness_guard",
        "plan": lens_host_persistent_supervision_plan(manifest=guard_manifest),
        "enablement": lens_host_persistent_supervision_enablement_preflight(manifest=guard_manifest),
    },
    "status_readback": {
        "kind": status.get("kind"),
        "resident_host_route": resident_host.get("route"),
        "persistent_supervision_plan_route": resident_host.get("persistent_supervision_plan_route"),
        "persistent_supervision_enablement_route": resident_host.get("persistent_supervision_enablement_route"),
        "persistent_supervision_plan": resident_host.get("persistent_supervision_plan"),
        "persistent_supervision_enablement": resident_host.get("persistent_supervision_enablement"),
    },
}
print(json.dumps(payload))
'@

try {
  $env:FRANCIS_ROOT = $RepoRoot
  $env:FRANCIS_DATA_DIR = $ProofDataRoot
  $env:FRANCIS_ENV_PROFILE = 'dev'
  $env:FRANCIS_RUN_MODE = 'api'
  $SourceRoot = Join-Path $RepoRoot 'src'
  if ([string]::IsNullOrWhiteSpace($PreviousPythonPath)) {
    $env:PYTHONPATH = $SourceRoot
  } else {
    $env:PYTHONPATH = $SourceRoot + [System.IO.Path]::PathSeparator + $PreviousPythonPath
  }
  $RouteResult = Invoke-JsonProcess -FileName $PythonPath -ProcessArgs @('-c', $RouteSource) -TimeoutSeconds 60
} finally {
  if ([string]::IsNullOrWhiteSpace($PreviousRoot)) {
    Remove-Item Env:\FRANCIS_ROOT -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_ROOT = $PreviousRoot
  }
  if ([string]::IsNullOrWhiteSpace($PreviousDataDir)) {
    Remove-Item Env:\FRANCIS_DATA_DIR -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_DATA_DIR = $PreviousDataDir
  }
  if ([string]::IsNullOrWhiteSpace($PreviousProfile)) {
    Remove-Item Env:\FRANCIS_ENV_PROFILE -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_ENV_PROFILE = $PreviousProfile
  }
  if ([string]::IsNullOrWhiteSpace($PreviousRunMode)) {
    Remove-Item Env:\FRANCIS_RUN_MODE -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_RUN_MODE = $PreviousRunMode
  }
  if ([string]::IsNullOrWhiteSpace($PreviousPythonPath)) {
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
  } else {
    $env:PYTHONPATH = $PreviousPythonPath
  }
}

$FamilyChainScript = Join-Path $PSScriptRoot 'lens-summon-anywhere-family-chain-proof.ps1'
if (-not (Test-Path -LiteralPath $FamilyChainScript -PathType Leaf)) {
  throw "Lens summon-anywhere family chain proof script is missing: $FamilyChainScript"
}

$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command powershell -ErrorAction Stop
}
$FamilyChainResult = Invoke-JsonProcess -FileName $PowerShell.Source -ProcessArgs @(
  '-NoProfile',
  '-ExecutionPolicy',
  'Bypass',
  '-File',
  $FamilyChainScript,
  '-Mode',
  'Status',
  '-DataDir',
  $ProofDataRoot
) -TimeoutSeconds $ChildProofTimeoutSeconds

$RoutePayload = $RouteResult.payload
$Plan = Get-PropertyValue -Payload $RoutePayload -Name 'plan'
$Enablement = Get-PropertyValue -Payload $RoutePayload -Name 'enablement'
$RequiredPrerequisiteGuard = Get-PropertyValue -Payload $RoutePayload -Name 'required_prerequisite_guard'
$GuardPlan = Get-PropertyValue -Payload $RequiredPrerequisiteGuard -Name 'plan'
$GuardEnablement = Get-PropertyValue -Payload $RequiredPrerequisiteGuard -Name 'enablement'
$StatusReadback = Get-PropertyValue -Payload $RoutePayload -Name 'status_readback'
$StatusPlan = Get-PropertyValue -Payload $StatusReadback -Name 'persistent_supervision_plan'
$StatusEnablement = Get-PropertyValue -Payload $StatusReadback -Name 'persistent_supervision_enablement'
$FamilyChain = $FamilyChainResult.payload

$ExpectedPrerequisites = @(
  'resident_host_process',
  'tray_presence',
  'global_hotkey_binding',
  'overlay_window',
  'summon_binding'
)
$ExpectedFamilyMap = [ordered]@{
  resident_host_process = 'resident_host'
  tray_presence = 'tray_presence'
  global_hotkey_binding = 'global_hotkey_binding'
  overlay_window = 'overlay_window'
  summon_binding = 'summon_binding'
}
$ExpectedDependencyRoutes = [ordered]@{
  resident_host_process = '/lens/host'
  tray_presence = '/lens/tray'
  global_hotkey_binding = '/lens/summon'
  overlay_window = '/lens/overlay'
  summon_binding = '/lens/summon'
}
$ExpectedDependencyBlockers = [ordered]@{
  resident_host_process = 'resident_host_process_missing'
  tray_presence = 'tray_host_missing'
  global_hotkey_binding = 'global_hotkey_binding_missing'
  overlay_window = 'overlay_window_missing'
  summon_binding = 'summon_binding_missing'
}

$PlanRequired = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Plan -Name 'required_before_enable' -Default @())
$PlanMissing = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Plan -Name 'missing_required_before_enable' -Default @())
$EnablementRequired = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Enablement -Name 'required_before_enable' -Default @())
$EnablementMissing = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Enablement -Name 'missing_required_before_enable' -Default @())
$GuardPlanRequired = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $GuardPlan -Name 'required_before_enable' -Default @())
$GuardPlanMissing = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $GuardPlan -Name 'missing_required_before_enable' -Default @())
$GuardPlanBlockedRequirements = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $GuardPlan -Name 'blocked_requirements' -Default @())
$GuardPlanBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $GuardPlan -Name 'blockers' -Default @())
$GuardEnablementRequired = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $GuardEnablement -Name 'required_before_enable' -Default @())
$GuardEnablementMissing = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $GuardEnablement -Name 'missing_required_before_enable' -Default @())
$GuardEnablementBlockedRequirements = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $GuardEnablement -Name 'blocked_requirements' -Default @())
$GuardEnablementBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $GuardEnablement -Name 'blockers' -Default @())
$PlanDependencies = @(Get-PropertyValue -Payload $Plan -Name 'enablement_dependency_readback' -Default @())
$EnablementDependencies = @(Get-PropertyValue -Payload $Enablement -Name 'enablement_dependency_readback' -Default @())
$PlanFirstMissingRequiredBeforeEnable = [string](Get-PropertyValue -Payload $Plan -Name 'first_missing_required_before_enable' -Default '')
$EnablementFirstMissingRequiredBeforeEnable = [string](Get-PropertyValue -Payload $Enablement -Name 'first_missing_required_before_enable' -Default '')
$PlanFirstMissingRequirementHandoff = Get-PropertyValue -Payload $Plan -Name 'first_missing_requirement_handoff' -Default ([ordered]@{})
$EnablementFirstMissingRequirementHandoff = Get-PropertyValue -Payload $Enablement -Name 'first_missing_requirement_handoff' -Default ([ordered]@{})
$FamilyChainFamilies = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $FamilyChain -Name 'blocked_families' -Default @())
$FamilyChainHandoffs = @(Get-PropertyValue -Payload $FamilyChain -Name 'blocked_family_handoffs' -Default @())

$PlanRouteReadbackObserved = (
  [int]$RouteResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $Plan -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_plan' -and
  [string](Get-PropertyValue -Payload $Plan -Name 'route' -Default '') -eq '/lens/host/persistent-supervision' -and
  [string](Get-PropertyValue -Payload $Plan -Name 'status' -Default '') -eq 'blocked' -and
  [bool](Get-PropertyValue -Payload $Plan -Name 'plan_available' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Plan -Name 'persistent_supervision_ready' -Default $true)
)
$EnablementRouteReadbackObserved = (
  [int]$RouteResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $Enablement -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_enablement.preflight' -and
  [string](Get-PropertyValue -Payload $Enablement -Name 'route' -Default '') -eq '/lens/host/persistent-supervision/enablement' -and
  [string](Get-PropertyValue -Payload $Enablement -Name 'plan_route' -Default '') -eq '/lens/host/persistent-supervision' -and
  [string](Get-PropertyValue -Payload $Enablement -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $Enablement -Name 'persistent_supervision_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Enablement -Name 'enablement_ready' -Default $true)
)
$RequiredBeforeEnableObserved = (
  (Test-StringArrayExact -Actual $PlanRequired -Expected $ExpectedPrerequisites) -and
  (Test-StringArrayExact -Actual $EnablementRequired -Expected $ExpectedPrerequisites)
)
$MissingRequiredBeforeEnableObserved = (
  (Test-StringArrayExact -Actual $PlanMissing -Expected $ExpectedPrerequisites) -and
  (Test-StringArrayExact -Actual $EnablementMissing -Expected $ExpectedPrerequisites)
)
$FirstMissingRequirementObserved = (
  $PlanFirstMissingRequiredBeforeEnable -eq 'resident_host_process' -and
  $EnablementFirstMissingRequiredBeforeEnable -eq 'resident_host_process' -and
  [string](Get-PropertyValue -Payload $PlanFirstMissingRequirementHandoff -Name 'id' -Default '') -eq 'resident_host_process' -and
  [string](Get-PropertyValue -Payload $EnablementFirstMissingRequirementHandoff -Name 'id' -Default '') -eq 'resident_host_process' -and
  [string](Get-PropertyValue -Payload $PlanFirstMissingRequirementHandoff -Name 'route' -Default '') -eq '/lens/host' -and
  [string](Get-PropertyValue -Payload $EnablementFirstMissingRequirementHandoff -Name 'route' -Default '') -eq '/lens/host' -and
  [string](Get-PropertyValue -Payload $PlanFirstMissingRequirementHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_host_runtime_blocker_boundary' -and
  [string](Get-PropertyValue -Payload $EnablementFirstMissingRequirementHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_host_runtime_blocker_boundary' -and
  [bool](Get-PropertyValue -Payload $PlanFirstMissingRequirementHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $EnablementFirstMissingRequirementHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $PlanFirstMissingRequirementHandoff -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $EnablementFirstMissingRequirementHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PlanFirstMissingRequirementHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $EnablementFirstMissingRequirementHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PlanFirstMissingRequirementHandoff -Name 'would_mutate' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $EnablementFirstMissingRequirementHandoff -Name 'would_mutate' -Default $true)
)
$RequiredPrerequisiteGuardObserved = (
  [int]$RouteResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $RequiredPrerequisiteGuard -Name 'projection' -Default '') -eq 'synthetic_manifest_readiness_guard' -and
  [string](Get-PropertyValue -Payload $GuardPlan -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_plan' -and
  [string](Get-PropertyValue -Payload $GuardEnablement -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_enablement.preflight' -and
  [string](Get-PropertyValue -Payload $GuardPlan -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $GuardEnablement -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $GuardPlan -Name 'persistent_supervision_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $GuardEnablement -Name 'enablement_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $GuardPlan -Name 'required_before_enable_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $GuardEnablement -Name 'required_before_enable_ready' -Default $true) -and
  [string](Get-PropertyValue -Payload $GuardPlan -Name 'next_smallest_truthful_gap' -Default '') -eq 'persistent_supervision_required_prerequisites_missing' -and
  [string](Get-PropertyValue -Payload $GuardEnablement -Name 'next_smallest_truthful_gap' -Default '') -eq 'persistent_supervision_required_prerequisites_missing' -and
  (Test-StringArrayExact -Actual $GuardPlanRequired -Expected $ExpectedPrerequisites) -and
  (Test-StringArrayExact -Actual $GuardEnablementRequired -Expected $ExpectedPrerequisites) -and
  (Test-StringArrayExact -Actual $GuardPlanMissing -Expected $ExpectedPrerequisites) -and
  (Test-StringArrayExact -Actual $GuardEnablementMissing -Expected $ExpectedPrerequisites) -and
  (Test-StringArrayExact -Actual $GuardPlanBlockedRequirements -Expected @('required_before_enable')) -and
  (Test-StringArrayExact -Actual $GuardEnablementBlockedRequirements -Expected @('required_before_enable')) -and
  (Test-StringArrayExact -Actual $GuardPlanBlockers -Expected @('persistent_supervision_required_prerequisites_missing')) -and
  (Test-StringArrayExact -Actual $GuardEnablementBlockers -Expected @('persistent_supervision_required_prerequisites_missing'))
)

$DependenciesObserved = $true
$DependencyReadback = @()
foreach ($Prerequisite in @($ExpectedPrerequisites)) {
  $PlanDependency = Get-DependencyById -Items $PlanDependencies -Id $Prerequisite
  $EnablementDependency = Get-DependencyById -Items $EnablementDependencies -Id $Prerequisite
  $Route = [string]$ExpectedDependencyRoutes[$Prerequisite]
  $Blocker = [string]$ExpectedDependencyBlockers[$Prerequisite]
  $Observed = (
    $null -ne $PlanDependency -and
    $null -ne $EnablementDependency -and
    [string](Get-PropertyValue -Payload $PlanDependency -Name 'route' -Default '') -eq $Route -and
    [string](Get-PropertyValue -Payload $EnablementDependency -Name 'route' -Default '') -eq $Route -and
    [string](Get-PropertyValue -Payload $PlanDependency -Name 'status' -Default '') -eq 'blocked' -and
    [string](Get-PropertyValue -Payload $EnablementDependency -Name 'status' -Default '') -eq 'blocked' -and
    -not [bool](Get-PropertyValue -Payload $PlanDependency -Name 'ready' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $EnablementDependency -Name 'ready' -Default $true) -and
    [string](Get-PropertyValue -Payload $PlanDependency -Name 'blocker' -Default '') -eq $Blocker -and
    [string](Get-PropertyValue -Payload $EnablementDependency -Name 'blocker' -Default '') -eq $Blocker
  )
  if (-not $Observed) {
    $DependenciesObserved = $false
  }
  $DependencyReadback += [ordered]@{
    id = $Prerequisite
    family = [string]$ExpectedFamilyMap[$Prerequisite]
    route = $Route
    blocker = $Blocker
    observed = $Observed
  }
}

$PrerequisitesMappedToFamilyChain = $true
foreach ($Prerequisite in @($ExpectedPrerequisites)) {
  $Family = [string]$ExpectedFamilyMap[$Prerequisite]
  if ($FamilyChainFamilies -notcontains $Family) {
    $PrerequisitesMappedToFamilyChain = $false
  }
}
$FamilyChainObserved = (
  [int]$FamilyChainResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $FamilyChain -Name 'kind' -Default '') -eq 'lens.summon_anywhere_family_chain.proof' -and
  [string](Get-PropertyValue -Payload $FamilyChain -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $FamilyChain -Name 'family_chain_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $FamilyChain -Name 'handoff_aligned' -Default $false) -and
  [bool](Get-PropertyValue -Payload $FamilyChain -Name 'side_effects_denied' -Default $false) -and
  $PrerequisitesMappedToFamilyChain
)
$StatusReadbackObserved = (
  [string](Get-PropertyValue -Payload $StatusReadback -Name 'kind' -Default '') -eq 'lens.status' -and
  [string](Get-PropertyValue -Payload $StatusReadback -Name 'persistent_supervision_plan_route' -Default '') -eq '/lens/host/persistent-supervision' -and
  [string](Get-PropertyValue -Payload $StatusReadback -Name 'persistent_supervision_enablement_route' -Default '') -eq '/lens/host/persistent-supervision/enablement' -and
  [string](Get-PropertyValue -Payload $StatusPlan -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_plan' -and
  [string](Get-PropertyValue -Payload $StatusEnablement -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_enablement.preflight'
)

$DeniedKeys = @(
  'execution_authority',
  'approval_decision_authority',
  'memory_write',
  'local_process_launch_authority',
  'process_supervision_authority',
  'process_restart_authority',
  'service_install_authority',
  'service_control_authority',
  'receipt_write_authority',
  'resident_claim_authority',
  'service_config_write_authority',
  'mutation_authority_granted'
)
$PlanGovernance = Get-PropertyValue -Payload $Plan -Name 'governance'
$EnablementGovernance = Get-PropertyValue -Payload $Enablement -Name 'governance'
$SideEffectsDenied = (
  (Test-GovernanceDenied -Governance $PlanGovernance -FalseKeys $DeniedKeys) -and
  (Test-GovernanceDenied -Governance $EnablementGovernance -FalseKeys $DeniedKeys) -and
  [bool](Get-PropertyValue -Payload $FamilyChain -Name 'side_effects_denied' -Default $false) -and
  -not (Test-Path -LiteralPath (Join-Path $ProofDataRoot 'runtime\lens-host\status.json') -PathType Leaf) -and
  -not (Test-Path -LiteralPath (Join-Path $ProofDataRoot 'runtime\lens-host\lens-host.pid') -PathType Leaf) -and
  -not (Test-Path -LiteralPath (Join-Path $ProofDataRoot 'runtime\lens-host-supervisor\status.json') -PathType Leaf)
)

$Checks = @(
  (New-Check -Id 'persistent_supervision_plan_route_readback' -Status $(if ($PlanRouteReadbackObserved) { 'blocked_readback_ready' } else { 'missing_or_unexpected' }) -Passed $PlanRouteReadbackObserved -Evidence '/lens/host/persistent-supervision' -Reason 'The persistent-supervision plan route must remain blocked and readable before any enablement claim.'),
  (New-Check -Id 'persistent_supervision_enablement_route_readback' -Status $(if ($EnablementRouteReadbackObserved) { 'blocked_readback_ready' } else { 'missing_or_unexpected' }) -Passed $EnablementRouteReadbackObserved -Evidence '/lens/host/persistent-supervision/enablement' -Reason 'The enablement preflight must remain blocked and non-mutating.'),
  (New-Check -Id 'required_before_enable_readback' -Status $(if ($RequiredBeforeEnableObserved) { 'prerequisites_projected' } else { 'missing_or_unexpected' }) -Passed $RequiredBeforeEnableObserved -Evidence 'required_before_enable on plan and enablement routes' -Reason 'The operator-visible contract must expose every prerequisite required before persistent supervision can be enabled.'),
  (New-Check -Id 'missing_required_before_enable_readback' -Status $(if ($MissingRequiredBeforeEnableObserved) { 'missing_prerequisites_projected' } else { 'missing_or_unexpected' }) -Passed $MissingRequiredBeforeEnableObserved -Evidence 'missing_required_before_enable on plan and enablement routes' -Reason 'The route must show that every prerequisite is still missing in the current disabled posture.'),
  (New-Check -Id 'first_missing_requirement_handoff' -Status $(if ($FirstMissingRequirementObserved) { 'first_missing_requirement_bound' } else { 'missing_or_unexpected' }) -Passed $FirstMissingRequirementObserved -Evidence 'first_missing_requirement_handoff on plan and enablement routes' -Reason 'The route must name the first concrete prerequisite to resolve before persistent supervision enablement.'),
  (New-Check -Id 'required_before_enable_readiness_guard' -Status $(if ($RequiredPrerequisiteGuardObserved) { 'prerequisite_guard_blocks_enablement' } else { 'missing_or_unexpected' }) -Passed $RequiredPrerequisiteGuardObserved -Evidence 'synthetic manifest projection of otherwise-ready persistent supervision routes' -Reason 'If authority and enablement toggles are otherwise ready, missing resident-host, tray, hotkey, overlay, and summon surfaces must still block persistent supervision.'),
  (New-Check -Id 'enablement_dependency_readback' -Status $(if ($DependenciesObserved) { 'dependency_routes_bound' } else { 'missing_or_unexpected' }) -Passed $DependenciesObserved -Evidence 'enablement_dependency_readback on plan and enablement routes' -Reason 'Each prerequisite must name a concrete readback route and blocker.'),
  (New-Check -Id 'summon_family_chain_alignment' -Status $(if ($FamilyChainObserved) { 'family_chain_aligned' } else { 'missing_or_unexpected' }) -Passed $FamilyChainObserved -Evidence 'scripts/lens-summon-anywhere-family-chain-proof.ps1 -Mode Status' -Reason 'Persistent-supervision prerequisites must align with the already-proven Stage 6 summon-anywhere blocker family chain.'),
  (New-Check -Id 'lens_status_operator_readback' -Status $(if ($StatusReadbackObserved) { 'operator_readback_ready' } else { 'missing_or_unexpected' }) -Passed $StatusReadbackObserved -Evidence '/lens/status resident_host persistent-supervision readback' -Reason 'The operator status payload must carry the same persistent-supervision plan and enablement readback.'),
  (New-Check -Id 'side_effects_denied' -Status $(if ($SideEffectsDenied) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $SideEffectsDenied -Evidence 'route governance + family-chain governance + proof data root' -Reason 'This proof must not start a runtime, mutate service config, write memory, claim residence, or grant process/service/summon authority.')
)
$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

[ordered]@{
  ok = $ProofPassed
  kind = 'lens.persistent_supervision.prerequisites.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  data_root = $ProofDataRoot
  stage = 'Stage 6 / Lens MVP'
  stage_state = 'active'
  acceptance_criterion = 'system_resident_presence'
  plan_route = '/lens/host/persistent-supervision'
  enablement_route = '/lens/host/persistent-supervision/enablement'
  route_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $Enablement -Name 'next_smallest_truthful_gap' -Default '')
  guard_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $GuardEnablement -Name 'next_smallest_truthful_gap' -Default '')
  family_chain_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $FamilyChain -Name 'next_smallest_truthful_gap' -Default '')
  next_smallest_truthful_gap = 'persistent_supervision_required_prerequisites_missing'
  persistent_supervision_plan_readback_observed = $PlanRouteReadbackObserved
  persistent_supervision_enablement_readback_observed = $EnablementRouteReadbackObserved
  required_before_enable_observed = $RequiredBeforeEnableObserved
  missing_required_before_enable_observed = $MissingRequiredBeforeEnableObserved
  first_missing_requirement_observed = $FirstMissingRequirementObserved
  required_before_enable_guard_observed = $RequiredPrerequisiteGuardObserved
  dependency_readback_observed = $DependenciesObserved
  family_chain_observed = $FamilyChainObserved
  prerequisites_mapped_to_family_chain = $PrerequisitesMappedToFamilyChain
  lens_status_operator_readback_observed = $StatusReadbackObserved
  side_effects_denied = $SideEffectsDenied
  required_before_enable = [string[]]@($EnablementRequired)
  missing_required_before_enable = [string[]]@($EnablementMissing)
  first_missing_required_before_enable = $EnablementFirstMissingRequiredBeforeEnable
  first_missing_requirement_handoff = $EnablementFirstMissingRequirementHandoff
  dependency_readback = @($DependencyReadback)
  family_chain = [ordered]@{
    status = if ($FamilyChainObserved) { [string](Get-PropertyValue -Payload $FamilyChain -Name 'status' -Default '') } else { 'missing_or_failed' }
    exit_code = [int]$FamilyChainResult.exit_code
    timed_out = [bool]$FamilyChainResult.timed_out
    duration_ms = [int]$FamilyChainResult.duration_ms
    blocked_families = [string[]]@($FamilyChainFamilies)
    handoff_count = @($FamilyChainHandoffs).Count
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $FamilyChain -Name 'next_smallest_truthful_gap' -Default '')
    side_effects_denied = [bool](Get-PropertyValue -Payload $FamilyChain -Name 'side_effects_denied' -Default $false)
  }
  route_readback = [ordered]@{
    status = if ($PlanRouteReadbackObserved -and $EnablementRouteReadbackObserved) { 'readback_ready' } else { 'missing_or_failed' }
    exit_code = [int]$RouteResult.exit_code
    timed_out = [bool]$RouteResult.timed_out
    duration_ms = [int]$RouteResult.duration_ms
    plan_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $Plan -Name 'next_smallest_truthful_gap' -Default '')
    enablement_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $Enablement -Name 'next_smallest_truthful_gap' -Default '')
    guard_plan_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $GuardPlan -Name 'next_smallest_truthful_gap' -Default '')
    guard_enablement_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $GuardEnablement -Name 'next_smallest_truthful_gap' -Default '')
    plan_status = [string](Get-PropertyValue -Payload $Plan -Name 'status' -Default '')
    enablement_status = [string](Get-PropertyValue -Payload $Enablement -Name 'status' -Default '')
    guard_plan_status = [string](Get-PropertyValue -Payload $GuardPlan -Name 'status' -Default '')
    guard_enablement_status = [string](Get-PropertyValue -Payload $GuardEnablement -Name 'status' -Default '')
  }
  guard_readback = [ordered]@{
    projection = [string](Get-PropertyValue -Payload $RequiredPrerequisiteGuard -Name 'projection' -Default '')
    observed = $RequiredPrerequisiteGuardObserved
    plan_status = [string](Get-PropertyValue -Payload $GuardPlan -Name 'status' -Default '')
    enablement_status = [string](Get-PropertyValue -Payload $GuardEnablement -Name 'status' -Default '')
    plan_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $GuardPlan -Name 'next_smallest_truthful_gap' -Default '')
    enablement_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $GuardEnablement -Name 'next_smallest_truthful_gap' -Default '')
    required_before_enable = [string[]]@($GuardEnablementRequired)
    missing_required_before_enable = [string[]]@($GuardEnablementMissing)
    blocked_requirements = [string[]]@($GuardEnablementBlockedRequirements)
    blockers = [string[]]@($GuardEnablementBlockers)
  }
  checks = @($Checks)
  evidence = @(
    '/lens/host/persistent-supervision',
    '/lens/host/persistent-supervision/enablement',
    '/lens/status',
    'synthetic manifest required-before-enable readiness guard projection',
    'scripts/lens-summon-anywhere-family-chain-proof.ps1 -Mode Status',
    'docs/canonical/ROADMAP.md#4.12'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    read_only_contract = $true
    wraps_persistent_supervision_plan_route = $true
    wraps_persistent_supervision_enablement_route = $true
    wraps_lens_status = $true
    wraps_summon_anywhere_family_chain_proof = $true
    readiness_guard_projection = $true
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    persistent_supervision_enablement_authority = $false
    persistent_supervision_execution_authority = $false
    service_config_write_authority = $false
    tray_registration_authority = $false
    hotkey_registration_authority = $false
    overlay_control_authority = $false
    summon_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Persistent-supervision enablement prerequisites are readable from the plan, enablement, and operator status routes; the required-before-enable guard still blocks an otherwise-ready projection on missing resident-host, tray, hotkey, overlay, and summon surfaces without granting runtime, service, summon, memory, or resident authority.'
} | ConvertTo-Json -Depth 8

exit $(if ($ProofPassed) { 0 } else { 1 })
