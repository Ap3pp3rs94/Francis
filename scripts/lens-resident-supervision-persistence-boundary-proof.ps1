[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [ValidateRange(30, 240)]
  [int]$ChildProofTimeoutSeconds = 180
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

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

function Get-PowerShellPath {
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
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-resident-supervision-persistence-boundary-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}
$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$PythonPath = Get-PythonPath
$PowerShellPath = Get-PowerShellPath

if ([string]::IsNullOrWhiteSpace($PythonPath) -or [string]::IsNullOrWhiteSpace($PowerShellPath)) {
  [ordered]@{
    ok = $false
    kind = 'lens.resident_supervision.persistence_boundary.proof'
    status = 'proof_failed'
    mode = $Mode.ToLowerInvariant()
    repo_root = $RepoRoot
    data_root = $ProofDataRoot
    error = if ([string]::IsNullOrWhiteSpace($PythonPath)) { 'python_unavailable' } else { 'powershell_unavailable' }
  } | ConvertTo-Json -Depth 5
  exit 1
}

$ResidentBoundaryScript = Join-Path $PSScriptRoot 'lens-resident-host-runtime-boundary-proof.ps1'
if (-not (Test-Path -LiteralPath $ResidentBoundaryScript -PathType Leaf)) {
  throw "Lens resident-host runtime boundary proof script is missing: $ResidentBoundaryScript"
}

$BeforeResidentDataDir = [string]$env:FRANCIS_DATA_DIR
try {
  $env:FRANCIS_DATA_DIR = $ProofDataRoot
  $ResidentBoundaryResult = Invoke-JsonProcess -FileName $PowerShellPath -ProcessArgs @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $ResidentBoundaryScript,
    '-Mode',
    'Status',
    '-ForegroundRunSeconds',
    '10',
    '-HostLaunchRunSeconds',
    '10',
    '-ResidentCandidateRunSeconds',
    '10'
  ) -TimeoutSeconds $ChildProofTimeoutSeconds
} finally {
  if ([string]::IsNullOrWhiteSpace($BeforeResidentDataDir)) {
    Remove-Item Env:\FRANCIS_DATA_DIR -ErrorAction SilentlyContinue
  } else {
    $env:FRANCIS_DATA_DIR = $BeforeResidentDataDir
  }
}

$RouteSource = @'
import json
from fastapi.testclient import TestClient

from francis.api.app import create_app


def get(client, route):
    response = client.get(route)
    body = response.json()
    if response.status_code != 200:
        raise RuntimeError(f"{route} returned {response.status_code}: {body!r}")
    return body


client = TestClient(create_app())
payload = {
    "status": get(client, "/lens/status?limit=5"),
    "plan": get(client, "/lens/host/persistent-supervision"),
    "enablement": get(client, "/lens/host/persistent-supervision/enablement"),
}
print(json.dumps(payload))
'@

$PreviousRoot = [string]$env:FRANCIS_ROOT
$PreviousDataDir = [string]$env:FRANCIS_DATA_DIR
$PreviousProfile = [string]$env:FRANCIS_ENV_PROFILE
$PreviousRunMode = [string]$env:FRANCIS_RUN_MODE
$PreviousPythonPath = [string]$env:PYTHONPATH

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

$ResidentBoundary = Get-PropertyValue -Payload $ResidentBoundaryResult -Name 'payload'
$ResidentBoundaryGovernance = Get-PropertyValue -Payload $ResidentBoundary -Name 'governance'
$ResidentBoundaryBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ResidentBoundary -Name 'blockers' -Default @())
$RoutePayload = Get-PropertyValue -Payload $RouteResult -Name 'payload'
$Status = Get-PropertyValue -Payload $RoutePayload -Name 'status'
$ResidentHostStatus = Get-PropertyValue -Payload $Status -Name 'resident_host'
$Plan = Get-PropertyValue -Payload $RoutePayload -Name 'plan'
$Enablement = Get-PropertyValue -Payload $RoutePayload -Name 'enablement'
$PlanHandoff = Get-PropertyValue -Payload $Plan -Name 'first_missing_requirement_handoff'
$EnablementHandoff = Get-PropertyValue -Payload $Enablement -Name 'first_missing_requirement_handoff'
$PlanDependencies = @(Get-PropertyValue -Payload $Plan -Name 'enablement_dependency_readback' -Default @())
$EnablementDependencies = @(Get-PropertyValue -Payload $Enablement -Name 'enablement_dependency_readback' -Default @())
$PlanResidentDependency = Get-DependencyById -Items $PlanDependencies -Id 'resident_host_process'
$EnablementResidentDependency = Get-DependencyById -Items $EnablementDependencies -Id 'resident_host_process'

$ResidentCandidateProofObserved = (
  [int](Get-PropertyValue -Payload $ResidentBoundaryResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $ResidentBoundary -Name 'kind' -Default '') -eq 'lens.resident_host.runtime_blocker_boundary.proof' -and
  [string](Get-PropertyValue -Payload $ResidentBoundary -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $ResidentBoundary -Name 'resident_runtime_candidate_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentBoundary -Name 'resident_runtime_candidate_supervised' -Default $false) -and
  [string](Get-PropertyValue -Payload $ResidentBoundary -Name 'resident_runtime_candidate_next_smallest_truthful_gap' -Default '') -eq 'resident_supervision_not_persistent' -and
  [string](Get-PropertyValue -Payload $ResidentBoundary -Name 'resident_runtime_persistence_blocker' -Default '') -eq 'resident_supervision_not_persistent' -and
  -not [bool](Get-PropertyValue -Payload $ResidentBoundary -Name 'resident_runtime_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentBoundary -Name 'resident_runtime_persistent' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentBoundary -Name 'ready_for_resident_claim' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentBoundary -Name 'resident_claim_allowed' -Default $true) -and
  $ResidentBoundaryBlockers -contains 'resident_supervision_not_persistent'
)

$PlanCandidateReadbackObserved = (
  [int](Get-PropertyValue -Payload $RouteResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $Plan -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_plan' -and
  [string](Get-PropertyValue -Payload $Plan -Name 'route' -Default '') -eq '/lens/host/persistent-supervision' -and
  [string](Get-PropertyValue -Payload $Plan -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $PlanHandoff -Name 'id' -Default '') -eq 'resident_host_process' -and
  [string](Get-PropertyValue -Payload $PlanHandoff -Name 'blocker' -Default '') -eq 'resident_supervision_not_persistent' -and
  [string](Get-PropertyValue -Payload $PlanHandoff -Name 'requirement_state' -Default '') -eq 'resident_candidate_observed_not_persistent' -and
  [string](Get-PropertyValue -Payload $PlanHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_supervision_not_persistent' -and
  [string](Get-PropertyValue -Payload $PlanHandoff -Name 'authority_required' -Default '') -eq 'persistent_process_supervision_authority' -and
  [bool](Get-PropertyValue -Payload $PlanHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $PlanHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PlanHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PlanHandoff -Name 'would_mutate' -Default $true)
)
$EnablementCandidateReadbackObserved = (
  [int](Get-PropertyValue -Payload $RouteResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $Enablement -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_enablement.preflight' -and
  [string](Get-PropertyValue -Payload $Enablement -Name 'route' -Default '') -eq '/lens/host/persistent-supervision/enablement' -and
  [string](Get-PropertyValue -Payload $Enablement -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $EnablementHandoff -Name 'id' -Default '') -eq 'resident_host_process' -and
  [string](Get-PropertyValue -Payload $EnablementHandoff -Name 'blocker' -Default '') -eq 'resident_supervision_not_persistent' -and
  [string](Get-PropertyValue -Payload $EnablementHandoff -Name 'requirement_state' -Default '') -eq 'resident_candidate_observed_not_persistent' -and
  [string](Get-PropertyValue -Payload $EnablementHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_supervision_not_persistent' -and
  [string](Get-PropertyValue -Payload $EnablementHandoff -Name 'authority_required' -Default '') -eq 'persistent_process_supervision_authority' -and
  [bool](Get-PropertyValue -Payload $EnablementHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $EnablementHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $EnablementHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $EnablementHandoff -Name 'would_mutate' -Default $true)
)
$DependencyCandidateReadbackObserved = (
  $null -ne $PlanResidentDependency -and
  $null -ne $EnablementResidentDependency -and
  [string](Get-PropertyValue -Payload $PlanResidentDependency -Name 'requirement_state' -Default '') -eq 'resident_candidate_observed_not_persistent' -and
  [string](Get-PropertyValue -Payload $EnablementResidentDependency -Name 'requirement_state' -Default '') -eq 'resident_candidate_observed_not_persistent' -and
  [string](Get-PropertyValue -Payload $PlanResidentDependency -Name 'blocker' -Default '') -eq 'resident_supervision_not_persistent' -and
  [string](Get-PropertyValue -Payload $EnablementResidentDependency -Name 'blocker' -Default '') -eq 'resident_supervision_not_persistent' -and
  [bool](Get-PropertyValue -Payload $PlanResidentDependency -Name 'fresh_resident_runtime_candidate_supervised' -Default $false) -and
  [bool](Get-PropertyValue -Payload $EnablementResidentDependency -Name 'fresh_resident_runtime_candidate_supervised' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PlanResidentDependency -Name 'resident_supervised_runtime' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $EnablementResidentDependency -Name 'resident_supervised_runtime' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PlanResidentDependency -Name 'ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $EnablementResidentDependency -Name 'ready' -Default $true)
)
$RouteBlockingPreserved = (
  [string](Get-PropertyValue -Payload $Plan -Name 'next_smallest_truthful_gap' -Default '') -eq 'persistent_supervision_authority_not_granted' -and
  [string](Get-PropertyValue -Payload $Enablement -Name 'next_smallest_truthful_gap' -Default '') -eq 'persistent_supervision_authority_not_granted' -and
  -not [bool](Get-PropertyValue -Payload $Plan -Name 'persistent_supervision_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Enablement -Name 'persistent_supervision_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Enablement -Name 'enablement_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentHostStatus -Name 'resident_supervised_runtime' -Default $true) -and
  [bool](Get-PropertyValue -Payload $ResidentHostStatus -Name 'fresh_resident_runtime_candidate_supervised' -Default $false)
)
$SideEffectsBounded = (
  [bool](Get-PropertyValue -Payload $ResidentBoundaryGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentBoundaryGovernance -Name 'bounded_local_process_launch' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentBoundaryGovernance -Name 'temporary_runtime_state_write' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentBoundaryGovernance -Name 'api_local_process_launch_authority' -Default $true) -and
  (Test-GovernanceDenied -Governance $ResidentBoundaryGovernance -FalseKeys @(
      'product_execution_authority',
      'execution_authority',
      'approval_decision_authority',
      'process_supervision_authority',
      'process_restart_authority',
      'service_install_authority',
      'service_control_authority',
      'hotkey_registration_authority',
      'tray_registration_authority',
      'overlay_control_authority',
      'summon_authority',
      'capture_authority',
      'new_sensing_authority',
      'memory_write',
      'resident_claim_authority',
      'mutation_authority_granted'
    ))
)

$Checks = @(
  (New-Check -Id 'resident_candidate_boundary_proof' -Status $(if ($ResidentCandidateProofObserved) { 'resident_candidate_observed_not_persistent' } else { 'missing_or_unexpected' }) -Passed $ResidentCandidateProofObserved -Evidence 'scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status' -Reason 'A bounded resident candidate must be supervised once without becoming persistent or resident-claimable.'),
  (New-Check -Id 'persistent_supervision_plan_candidate_readback' -Status $(if ($PlanCandidateReadbackObserved) { 'candidate_handoff_promoted' } else { 'missing_or_unexpected' }) -Passed $PlanCandidateReadbackObserved -Evidence '/lens/host/persistent-supervision' -Reason 'The persistent-supervision plan must promote the fresh resident candidate to the resident_supervision_not_persistent handoff.'),
  (New-Check -Id 'persistent_supervision_enablement_candidate_readback' -Status $(if ($EnablementCandidateReadbackObserved) { 'candidate_handoff_promoted' } else { 'missing_or_unexpected' }) -Passed $EnablementCandidateReadbackObserved -Evidence '/lens/host/persistent-supervision/enablement' -Reason 'The enablement preflight must preserve the same resident-supervision persistence blocker.'),
  (New-Check -Id 'resident_dependency_candidate_readback' -Status $(if ($DependencyCandidateReadbackObserved) { 'dependency_readback_promoted' } else { 'missing_or_unexpected' }) -Passed $DependencyCandidateReadbackObserved -Evidence 'enablement dependency readback resident_host_process' -Reason 'The dependency readback must distinguish a fresh candidate from a persistent supervised resident runtime.'),
  (New-Check -Id 'route_blocking_preserved' -Status $(if ($RouteBlockingPreserved) { 'blocked_without_authority' } else { 'unexpected_ready' }) -Passed $RouteBlockingPreserved -Evidence 'plan + enablement route next_smallest_truthful_gap' -Reason 'Candidate proof must not make persistent supervision ready or grant persistent supervision authority.'),
  (New-Check -Id 'side_effects_bounded' -Status $(if ($SideEffectsBounded) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $SideEffectsBounded -Evidence 'resident boundary governance + route readback' -Reason 'The proof may launch one bounded diagnostic candidate but must not grant product/API launch, supervision, service, summon, memory, approval, or resident-claim authority.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })
$PlanHandoffNextGap = [string](Get-PropertyValue -Payload $PlanHandoff -Name 'next_smallest_truthful_gap' -Default '')
$RouteNextGap = [string](Get-PropertyValue -Payload $Enablement -Name 'next_smallest_truthful_gap' -Default '')
$BlockerBag = @()
$BlockerBag += @($ResidentBoundaryBlockers)
$BlockerBag += @(
  'resident_supervision_not_persistent',
  'persistent_supervision_authority_not_granted',
  'persistent_process_supervision_authority_required'
)
$AllBlockers = [string[]]@($BlockerBag | Sort-Object -Unique)

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.resident_supervision.persistence_boundary.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  data_root = $ProofDataRoot
  stage = 'Stage 6 / Lens MVP'
  stage_state = 'active'
  acceptance_criterion = 'system_resident_presence'
  previous_next_smallest_truthful_gap = 'resident_host_process_not_supervised'
  consumed_resident_candidate_next_smallest_truthful_gap = $PlanHandoffNextGap
  route_next_smallest_truthful_gap = $RouteNextGap
  next_smallest_truthful_gap = 'persistent_supervision_authority_not_granted'
  recommended_next_slice = 'consume_resident_supervision_persistence_boundary_in_stage6_audit'
  recommended_proof_script = 'scripts/lens-stage6-completion-audit.ps1 -Mode Status'
  resident_candidate_boundary_proof_observed = $ResidentCandidateProofObserved
  persistent_supervision_plan_candidate_readback_observed = $PlanCandidateReadbackObserved
  persistent_supervision_enablement_candidate_readback_observed = $EnablementCandidateReadbackObserved
  resident_dependency_candidate_readback_observed = $DependencyCandidateReadbackObserved
  route_blocking_preserved = $RouteBlockingPreserved
  side_effects_bounded = $SideEffectsBounded
  resident_runtime_candidate_supervised = [bool](Get-PropertyValue -Payload $ResidentHostStatus -Name 'fresh_resident_runtime_candidate_supervised' -Default $false)
  resident_supervised_runtime = [bool](Get-PropertyValue -Payload $ResidentHostStatus -Name 'resident_supervised_runtime' -Default $false)
  supervisor_freshness_status = [string](Get-PropertyValue -Payload $ResidentHostStatus -Name 'supervisor_freshness_status' -Default '')
  resident_host_process_requirement_state = [string](Get-PropertyValue -Payload $PlanResidentDependency -Name 'requirement_state' -Default '')
  resident_host_process_blocker = [string](Get-PropertyValue -Payload $PlanResidentDependency -Name 'blocker' -Default '')
  authority_required = [string](Get-PropertyValue -Payload $PlanHandoff -Name 'authority_required' -Default '')
  plan_route = '/lens/host/persistent-supervision'
  enablement_route = '/lens/host/persistent-supervision/enablement'
  checks = @($Checks)
  blockers = $AllBlockers
  proof = [ordered]@{
    resident_boundary_status = [string](Get-PropertyValue -Payload $ResidentBoundary -Name 'status' -Default '')
    resident_boundary_next_gap = [string](Get-PropertyValue -Payload $ResidentBoundary -Name 'next_smallest_truthful_gap' -Default '')
    resident_candidate_next_gap = [string](Get-PropertyValue -Payload $ResidentBoundary -Name 'resident_runtime_candidate_next_smallest_truthful_gap' -Default '')
    resident_candidate_persistence_blocker = [string](Get-PropertyValue -Payload $ResidentBoundary -Name 'resident_runtime_persistence_blocker' -Default '')
    resident_candidate_supervised = [bool](Get-PropertyValue -Payload $ResidentBoundary -Name 'resident_runtime_candidate_supervised' -Default $false)
    resident_candidate_persistent = [bool](Get-PropertyValue -Payload $ResidentBoundary -Name 'resident_runtime_persistent' -Default $false)
    plan_status = [string](Get-PropertyValue -Payload $Plan -Name 'status' -Default '')
    plan_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $Plan -Name 'next_smallest_truthful_gap' -Default '')
    plan_handoff_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $PlanHandoff -Name 'next_smallest_truthful_gap' -Default '')
    plan_handoff_requirement_state = [string](Get-PropertyValue -Payload $PlanHandoff -Name 'requirement_state' -Default '')
    enablement_status = [string](Get-PropertyValue -Payload $Enablement -Name 'status' -Default '')
    enablement_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $Enablement -Name 'next_smallest_truthful_gap' -Default '')
    enablement_handoff_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $EnablementHandoff -Name 'next_smallest_truthful_gap' -Default '')
    enablement_handoff_requirement_state = [string](Get-PropertyValue -Payload $EnablementHandoff -Name 'requirement_state' -Default '')
  }
  child_proof_runs = @(
    [ordered]@{
      name = 'resident_host_runtime_boundary'
      exit_code = [int](Get-PropertyValue -Payload $ResidentBoundaryResult -Name 'exit_code' -Default -1)
      timed_out = [bool](Get-PropertyValue -Payload $ResidentBoundaryResult -Name 'timed_out' -Default $false)
      timeout_seconds = [int](Get-PropertyValue -Payload $ResidentBoundaryResult -Name 'timeout_seconds' -Default $ChildProofTimeoutSeconds)
      duration_ms = [int](Get-PropertyValue -Payload $ResidentBoundaryResult -Name 'duration_ms' -Default 0)
    },
    [ordered]@{
      name = 'route_readback'
      exit_code = [int](Get-PropertyValue -Payload $RouteResult -Name 'exit_code' -Default -1)
      timed_out = [bool](Get-PropertyValue -Payload $RouteResult -Name 'timed_out' -Default $false)
      timeout_seconds = [int](Get-PropertyValue -Payload $RouteResult -Name 'timeout_seconds' -Default 60)
      duration_ms = [int](Get-PropertyValue -Payload $RouteResult -Name 'duration_ms' -Default 0)
    }
  )
  handoff = [ordered]@{
    previous_next_smallest_truthful_gap = 'resident_host_process_not_supervised'
    consumed_resident_candidate_next_smallest_truthful_gap = $PlanHandoffNextGap
    route_next_smallest_truthful_gap = $RouteNextGap
    next_smallest_truthful_gap = 'persistent_supervision_authority_not_granted'
    recommended_next_slice = 'consume_resident_supervision_persistence_boundary_in_stage6_audit'
    recommended_proof_script = 'scripts/lens-stage6-completion-audit.ps1 -Mode Status'
    authority_required = [string](Get-PropertyValue -Payload $PlanHandoff -Name 'authority_required' -Default '')
  }
  evidence = @(
    'scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status',
    '/lens/status?limit=5',
    '/lens/host/persistent-supervision',
    '/lens/host/persistent-supervision/enablement'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    route_readback_contract = $true
    wraps_resident_host_runtime_boundary_proof = $true
    wraps_persistent_supervision_plan_route = $true
    wraps_persistent_supervision_enablement_route = $true
    bounded_local_process_launch = $true
    bounded_process_launch = $true
    temporary_runtime_state_write = $true
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $true
    api_local_process_launch_authority = $false
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
    capture_authority = $false
    new_sensing_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'A bounded resident candidate can now be proven through persistent-supervision plan and enablement readback as resident_candidate_observed_not_persistent; persistent supervision remains blocked and authority-denied.'
}

$Payload | ConvertTo-Json -Depth 10
exit $(if ($ProofPassed) { 0 } else { 1 })
