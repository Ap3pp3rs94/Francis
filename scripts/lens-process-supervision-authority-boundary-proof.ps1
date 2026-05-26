[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(5, 60)]
  [int]$StartupTimeoutSeconds = 30,

  [ValidateRange(2, 30)]
  [int]$ForegroundRunSeconds = 2,

  [ValidateRange(2, 30)]
  [int]$HostLaunchRunSeconds = 3,

  [ValidateRange(3, 30)]
  [int]$SupervisorRunSeconds = 20,

  [ValidateRange(3, 60)]
  [int]$ResidentSurfaceForegroundRunSeconds = 40,

  [ValidateRange(30, 600)]
  [int]$ChildProofTimeoutSeconds = 360,

  [string]$CachedResidentSurfaceProofPath = '',

  [string]$CachedHostSupervisionProofPath = ''
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

function Get-PythonPath {
  $WindowsVenv = Join-Path $RepoRoot '.venv\Scripts\python.exe'
  if (Test-Path -LiteralPath $WindowsVenv -PathType Leaf) {
    & $WindowsVenv --version *> $null
    if ($LASTEXITCODE -eq 0) {
      return $WindowsVenv
    }
  }

  $UnixVenv = Join-Path $RepoRoot '.venv/bin/python'
  if (Test-Path -LiteralPath $UnixVenv -PathType Leaf) {
    & $UnixVenv --version *> $null
    if ($LASTEXITCODE -eq 0) {
      return $UnixVenv
    }
  }

  $Python = Get-Command python -ErrorAction SilentlyContinue
  if ($null -ne $Python) {
    return [string]$Python.Source
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

function Invoke-JsonScript {
  param(
    [string]$PowerShellPath,
    [string]$ScriptPath,
    [string[]]$ScriptArgs = @(),
    [int]$TimeoutSeconds = $ChildProofTimeoutSeconds
  )

  if ([string]::IsNullOrWhiteSpace($PowerShellPath) -or -not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
      error = 'script_unavailable'
      timed_out = $false
      timeout_seconds = $TimeoutSeconds
      duration_ms = 0
    }
  }

  $ArgumentParts = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    (Quote-ProcessArgument -Value $ScriptPath)
  )
  foreach ($Arg in $ScriptArgs) {
    $ArgumentParts += (Quote-ProcessArgument -Value $Arg)
  }

  $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
  $StartInfo.FileName = $PowerShellPath
  $StartInfo.Arguments = $ArgumentParts -join ' '
  $StartInfo.WorkingDirectory = $RepoRoot
  $StartInfo.UseShellExecute = $false
  $StartInfo.CreateNoWindow = $true
  $StartInfo.RedirectStandardOutput = $true
  $StartInfo.RedirectStandardError = $true

  $Process = [System.Diagnostics.Process]::new()
  $Process.StartInfo = $StartInfo
  $Started = $false
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

function Invoke-JsonScriptWithProofRetry {
  param(
    [string]$PowerShellPath,
    [string]$ScriptPath,
    [string[]]$ScriptArgs = @(),
    [string]$ExpectedKind,
    [int]$Attempts = 2,
    [int]$TimeoutSeconds = $ChildProofTimeoutSeconds
  )

  $LastProof = $null
  for ($Attempt = 1; $Attempt -le $Attempts; $Attempt++) {
    $Result = @(Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $ScriptPath -ScriptArgs $ScriptArgs -TimeoutSeconds $TimeoutSeconds)
    $Proof = if ($Result.Count -gt 0) { $Result[-1] } else { $null }
    $LastProof = $Proof

    $ExitCode = -1
    $Payload = $null
    if ($Proof -is [System.Collections.IDictionary]) {
      if ($Proof.Contains('exit_code') -and $null -ne $Proof['exit_code']) {
        $ExitCode = [int]$Proof['exit_code']
      }
      if ($Proof.Contains('payload') -and $null -ne $Proof['payload']) {
        $Payload = $Proof['payload']
      }
    }

    if (
      $ExitCode -eq 0 -and
      [string](Get-PropertyValue -Payload $Payload -Name 'kind' -Default '') -eq $ExpectedKind -and
      [string](Get-PropertyValue -Payload $Payload -Name 'status' -Default '') -eq 'proof_passed'
    ) {
      return $Proof
    }
    if ([bool](Get-PropertyValue -Payload $Proof -Name 'timed_out' -Default $false)) {
      return $Proof
    }
    if ($Attempt -lt $Attempts) {
      Start-Sleep -Milliseconds 750
    }
  }
  return $LastProof
}

function Read-CachedJsonScriptResult {
  param([string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path)) {
    return $null
  }
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
      error = 'cached_payload_missing'
      timed_out = $false
      timeout_seconds = $ChildProofTimeoutSeconds
      duration_ms = 0
      cached = $true
    }
  }

  $Text = Get-Content -LiteralPath $Path -Raw
  $Payload = $null
  try {
    $Payload = $Text | ConvertFrom-Json -ErrorAction Stop
  } catch {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = $Text
      error = 'cached_payload_json_invalid'
      timed_out = $false
      timeout_seconds = $ChildProofTimeoutSeconds
      duration_ms = 0
      cached = $true
    }
  }

  return [ordered]@{
    exit_code = 0
    payload = $Payload
    output = $Text
    error = ''
    timed_out = $false
    timeout_seconds = $ChildProofTimeoutSeconds
    duration_ms = 0
    cached = $true
  }
}

function Invoke-ActivationBoundary {
  param(
    [string]$PythonPath,
    [string]$ProofDataRoot
  )

  if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
      error = 'python_unavailable'
      timed_out = $false
      timeout_seconds = 60
      duration_ms = 0
    }
  }

  $Source = @'
import json

from francis.lens.activation import lens_resident_surface_activation_boundary

print(json.dumps(lens_resident_surface_activation_boundary(limit=5)))
'@

  $HadPreviousDataDir = Test-Path Env:\FRANCIS_DATA_DIR
  $PreviousDataDir = [string]$env:FRANCIS_DATA_DIR
  $TempSourcePath = ''
  $Timer = [System.Diagnostics.Stopwatch]::StartNew()
  try {
    if (-not [string]::IsNullOrWhiteSpace($ProofDataRoot)) {
      $env:FRANCIS_DATA_DIR = $ProofDataRoot
    }
    $TempSourcePath = [System.IO.Path]::GetTempFileName()
    Set-Content -LiteralPath $TempSourcePath -Value $Source -Encoding ASCII
    $Output = & $PythonPath $TempSourcePath 2>&1
    $ExitCode = $LASTEXITCODE
  } catch {
    $Timer.Stop()
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
      error = [string]$_.Exception.Message
      timed_out = $false
      timeout_seconds = 60
      duration_ms = [int]$Timer.ElapsedMilliseconds
    }
  } finally {
    if (-not [string]::IsNullOrWhiteSpace($TempSourcePath) -and (Test-Path -LiteralPath $TempSourcePath -PathType Leaf)) {
      Remove-Item -LiteralPath $TempSourcePath -ErrorAction SilentlyContinue
    }
    if ($HadPreviousDataDir) {
      $env:FRANCIS_DATA_DIR = $PreviousDataDir
    } else {
      Remove-Item Env:\FRANCIS_DATA_DIR -ErrorAction SilentlyContinue
    }
  }
  $Timer.Stop()

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
    error = ''
    timed_out = $false
    timeout_seconds = 60
    duration_ms = [int]$Timer.ElapsedMilliseconds
  }
}

function Invoke-ActivationPlan {
  param([string]$PythonPath)

  if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
      error = 'python_unavailable'
      timed_out = $false
      timeout_seconds = 60
      duration_ms = 0
    }
  }

  $Source = @'
import json

from francis.lens.activation import lens_resident_runtime_activation_plan

print(json.dumps(lens_resident_runtime_activation_plan()))
'@

  $TempSourcePath = ''
  $Timer = [System.Diagnostics.Stopwatch]::StartNew()
  try {
    $TempSourcePath = [System.IO.Path]::GetTempFileName()
    Set-Content -LiteralPath $TempSourcePath -Value $Source -Encoding ASCII
    $Output = & $PythonPath $TempSourcePath 2>&1
    $ExitCode = $LASTEXITCODE
  } catch {
    $Timer.Stop()
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
      error = [string]$_.Exception.Message
      timed_out = $false
      timeout_seconds = 60
      duration_ms = [int]$Timer.ElapsedMilliseconds
    }
  } finally {
    if (-not [string]::IsNullOrWhiteSpace($TempSourcePath) -and (Test-Path -LiteralPath $TempSourcePath -PathType Leaf)) {
      Remove-Item -LiteralPath $TempSourcePath -ErrorAction SilentlyContinue
    }
  }
  $Timer.Stop()

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
    error = ''
    timed_out = $false
    timeout_seconds = 60
    duration_ms = [int]$Timer.ElapsedMilliseconds
  }
}

function New-ChildProofRunSummary {
  param(
    [string]$Name,
    [object]$Result
  )

  return [ordered]@{
    name = $Name
    exit_code = [int](Get-PropertyValue -Payload $Result -Name 'exit_code' -Default -1)
    timed_out = [bool](Get-PropertyValue -Payload $Result -Name 'timed_out' -Default $false)
    timeout_seconds = [int](Get-PropertyValue -Payload $Result -Name 'timeout_seconds' -Default $ChildProofTimeoutSeconds)
    duration_ms = [int](Get-PropertyValue -Payload $Result -Name 'duration_ms' -Default 0)
    error = [string](Get-PropertyValue -Payload $Result -Name 'error' -Default '')
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

function Get-CriterionById {
  param(
    [object[]]$Criteria,
    [string]$Id
  )

  foreach ($Criterion in @($Criteria)) {
    if ([string](Get-PropertyValue -Payload $Criterion -Name 'id' -Default '') -eq $Id) {
      return $Criterion
    }
  }
  return $null
}

$PowerShellPath = Get-PowerShellPath
$PythonPath = Get-PythonPath
$ResidentSurfaceProofPath = Join-Path $PSScriptRoot 'lens-resident-surface-proof.ps1'
$HostSupervisionProofPath = Join-Path $PSScriptRoot 'lens-host-supervision-proof.ps1'
$ActivationBoundaryDataRoot = [System.IO.Path]::GetFullPath(
  (Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-process-supervision-activation-boundary\" + [guid]::NewGuid().ToString('N') + "\data"))
)
$EffectiveResidentSurfaceForegroundRunSeconds = 0

$ActivationBoundaryResult = Invoke-ActivationBoundary -PythonPath $PythonPath -ProofDataRoot $ActivationBoundaryDataRoot
$ActivationPlanResult = Invoke-ActivationPlan -PythonPath $PythonPath
$CachedResidentSurfaceResult = Read-CachedJsonScriptResult -Path $CachedResidentSurfaceProofPath
if ($null -ne $CachedResidentSurfaceResult) {
  $ResidentSurfaceResult = $CachedResidentSurfaceResult
} else {
  $ResidentSurfaceResult = Invoke-JsonScriptWithProofRetry -PowerShellPath $PowerShellPath -ScriptPath $ResidentSurfaceProofPath -ScriptArgs @(
    '-Mode', 'Status',
    '-ForegroundRunSeconds', [string]$ResidentSurfaceForegroundRunSeconds
  ) -ExpectedKind 'lens.resident_surface.readiness_proof'
  $EffectiveResidentSurfaceForegroundRunSeconds = $ResidentSurfaceForegroundRunSeconds
}
$CachedHostSupervisionResult = Read-CachedJsonScriptResult -Path $CachedHostSupervisionProofPath
if ($null -ne $CachedHostSupervisionResult) {
  $HostSupervisionResult = $CachedHostSupervisionResult
} else {
  $HostSupervisionResult = Invoke-JsonScriptWithProofRetry -PowerShellPath $PowerShellPath -ScriptPath $HostSupervisionProofPath -ScriptArgs @(
    '-Mode', 'Status',
    '-ForegroundRunSeconds', [string]$ForegroundRunSeconds,
    '-HostLaunchRunSeconds', [string]$HostLaunchRunSeconds
  ) -ExpectedKind 'lens.host.supervision_readiness_proof'
}
$ChildProofRuns = @(
  (New-ChildProofRunSummary -Name 'resident_surface_activation_boundary' -Result $ActivationBoundaryResult),
  (New-ChildProofRunSummary -Name 'resident_runtime_activation_plan' -Result $ActivationPlanResult),
  (New-ChildProofRunSummary -Name 'resident_surface_foreground_runtime' -Result $ResidentSurfaceResult),
  (New-ChildProofRunSummary -Name 'host_supervision' -Result $HostSupervisionResult)
)
$ChildProofTimeouts = @($ChildProofRuns | Where-Object { [bool]$_['timed_out'] } | ForEach-Object { [string]$_['name'] })

$ActivationBoundaryPayload = Get-PropertyValue -Payload $ActivationBoundaryResult -Name 'payload'
$ActivationPlanPayload = Get-PropertyValue -Payload $ActivationPlanResult -Name 'payload'
$ResidentSurfacePayload = Get-PropertyValue -Payload $ResidentSurfaceResult -Name 'payload'
$HostSupervisionPayload = Get-PropertyValue -Payload $HostSupervisionResult -Name 'payload'
$ActivationBoundaryGovernance = Get-PropertyValue -Payload $ActivationBoundaryPayload -Name 'governance'
$ActivationBoundaryExecution = Get-PropertyValue -Payload $ActivationBoundaryPayload -Name 'execution'
$ActivationPlanGovernance = Get-PropertyValue -Payload $ActivationPlanPayload -Name 'governance'
$ActivationPlanPlan = Get-PropertyValue -Payload $ActivationPlanPayload -Name 'plan'
$ActivationPlanSourceReadbacks = Get-PropertyValue -Payload $ActivationPlanPayload -Name 'source_readbacks'
$ActivationPlanHostSupervisionAuthority = Get-PropertyValue -Payload $ActivationPlanSourceReadbacks -Name 'host_supervision_authority'
$ResidentSurfaceRecommendedHandoff = Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'recommended_handoff'
$ResidentSurfaceProof = Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'proof'
$ResidentSurfaceBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'blockers' -Default @())
$ResidentSurfaceForegroundRuntimeBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ResidentSurfaceProof -Name 'resident_surface_foreground_runtime_blockers' -Default @())
$ResidentSurfaceRuntimeStatus = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_surface_runtime_status' -Default '')
$ResidentSurfaceNextSmallestTruthfulGap = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'next_smallest_truthful_gap' -Default '')
$ResidentSurfaceRecommendedNextSlice = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'recommended_next_slice' -Default '')
$ResidentSurfaceAuthorityRequired = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'authority_required' -Default '')
$HostSupervisionGovernance = Get-PropertyValue -Payload $HostSupervisionPayload -Name 'governance'
$HostSupervisionProof = Get-PropertyValue -Payload $HostSupervisionPayload -Name 'proof'
$ServicePlanBlockedBy = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_plan_blocked_by' -Default @())

$ActivationBoundaryObserved = (
  [int](Get-PropertyValue -Payload $ActivationBoundaryResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $ActivationBoundaryPayload -Name 'kind' -Default '') -eq 'lens.resident_surface.activation_boundary' -and
  [string](Get-PropertyValue -Payload $ActivationBoundaryPayload -Name 'status' -Default '') -eq 'blocked' -and
  [bool](Get-PropertyValue -Payload $ActivationBoundaryPayload -Name 'boundary_ready' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryPayload -Name 'resident_claim_allowed' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryPayload -Name 'execution_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryPayload -Name 'executed' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryPayload -Name 'applied' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryExecution -Name 'would_launch_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryExecution -Name 'would_install_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryExecution -Name 'would_start_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryExecution -Name 'would_register_hotkey' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryExecution -Name 'would_open_overlay' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryExecution -Name 'would_write_memory' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryExecution -Name 'would_decide_approval' -Default $true)
)
$ResidentSurfaceForegroundRuntimeProofObserved = (
  [int](Get-PropertyValue -Payload $ResidentSurfaceResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'kind' -Default '') -eq 'lens.resident_surface.readiness_proof' -and
  [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_surface_content_readback' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_surface_foreground_runtime_readback' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_surface_foreground_runtime_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_surface_runtime_status' -Default '') -eq 'foreground_runtime_observed' -and
  [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'foreground_host_process_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'foreground_host_runtime_completed' -Default $false) -and
  $ResidentSurfaceForegroundRuntimeBlockers -contains 'resident_surface_runtime_not_supervised' -and
  $ResidentSurfaceForegroundRuntimeBlockers -contains 'resident_surface_not_resident' -and
  -not ($ResidentSurfaceForegroundRuntimeBlockers -contains 'resident_surface_runtime_missing') -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_surface_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_claim_allowed' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_host_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'execution_authority' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'approval_decision_authority' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'memory_write' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'process_supervision_authority' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'service_control_authority' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_claim_authority' -Default $false)
)
$ResidentSurfaceResidentRuntimeProofObserved = (
  [int](Get-PropertyValue -Payload $ResidentSurfaceResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'kind' -Default '') -eq 'lens.resident_surface.readiness_proof' -and
  [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_surface_content_readback' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_surface_foreground_runtime_readback' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_surface_foreground_runtime_observed' -Default $false) -and
  $ResidentSurfaceRuntimeStatus -eq 'resident_runtime_observed' -and
  [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_surface_ready' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_host_process' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_claim_allowed' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'execution_authority' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'approval_decision_authority' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'memory_write' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'service_control_authority' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_claim_authority' -Default $false)
)
$ResidentSurfaceRuntimeProofObserved = $ResidentSurfaceForegroundRuntimeProofObserved -or $ResidentSurfaceResidentRuntimeProofObserved
$ResidentSurfaceProcessSupervisionHandoffObserved = (
  $ResidentSurfaceForegroundRuntimeProofObserved -and
  [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'recommended_handoff_source' -Default '') -eq 'resident_surface_runtime_supervision_handoff' -and
  $ResidentSurfaceRecommendedNextSlice -eq 'resolve_resident_surface_runtime_supervision_before_helpful_not_noisy_claim' -and
  [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'recommended_proof_script' -Default '') -eq 'scripts/lens-resident-surface-proof.ps1 -Mode Status' -and
  $ResidentSurfaceAuthorityRequired -eq 'process_supervision_authority' -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'authority_granted' -Default $true) -and
  [string](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'id' -Default '') -eq 'resident_surface_runtime_supervision' -and
  [string](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_surface_runtime_not_supervised' -and
  [string](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'readiness_route' -Default '') -eq '/lens/resident-runtime/authority-grant/readiness' -and
  [string](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'authority_required' -Default '') -eq 'process_supervision_authority' -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'would_mutate' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'would_supervise_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'would_restart_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'would_claim_resident' -Default $true)
)
$ResidentSurfaceOperatorExperienceHandoffObserved = (
  $ResidentSurfaceResidentRuntimeProofObserved -and
  [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'recommended_handoff_source' -Default '') -eq 'resident_surface_runtime_supervision_handoff' -and
  $ResidentSurfaceRecommendedNextSlice -eq 'prove_resident_surface_operator_experience_before_helpful_not_noisy_claim' -and
  [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'recommended_proof_script' -Default '') -eq 'scripts/lens-resident-surface-proof.ps1 -Mode Status' -and
  $ResidentSurfaceAuthorityRequired -eq 'operator_experience_proof' -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'authority_granted' -Default $true) -and
  [string](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'id' -Default '') -eq 'resident_surface_runtime_supervision' -and
  [string](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_surface_operator_experience_proof' -and
  [string](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'readiness_route' -Default '') -eq '/lens/resident-runtime/authority-grant/readiness' -and
  [string](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'authority_required' -Default '') -eq 'operator_experience_proof' -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'would_mutate' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'would_supervise_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'would_restart_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceRecommendedHandoff -Name 'would_claim_resident' -Default $true)
)
$ResidentSurfaceRuntimeSupervisionHandoffObserved = $ResidentSurfaceProcessSupervisionHandoffObserved -or $ResidentSurfaceOperatorExperienceHandoffObserved
$ActivationPlanReadbackObserved = (
  [int](Get-PropertyValue -Payload $ActivationPlanResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $ActivationPlanPayload -Name 'kind' -Default '') -eq 'lens.resident_runtime.activation_plan' -and
  [bool](Get-PropertyValue -Payload $ActivationPlanPayload -Name 'ok' -Default $false) -and
  [string](Get-PropertyValue -Payload $ActivationPlanPayload -Name 'status' -Default '') -eq 'blocked' -and
  [bool](Get-PropertyValue -Payload $ActivationPlanPayload -Name 'plan_available' -Default $false)
)
$ActivationPlanAuthorityObserved = (
  $ActivationPlanReadbackObserved -and
  [bool](Get-PropertyValue -Payload $ActivationPlanPayload -Name 'resident_runtime_execution_authority' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ActivationPlanPayload -Name 'host_supervision_authority' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ActivationPlanPayload -Name 'process_supervision_authority' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ActivationPlanPayload -Name 'process_restart_authority' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ActivationPlanPayload -Name 'bounded_resident_candidate_ready' -Default $false) -and
  -not [string]::IsNullOrWhiteSpace([string](Get-PropertyValue -Payload $ActivationPlanPayload -Name 'active_authority_grant_receipt_id' -Default '')) -and
  -not [string]::IsNullOrWhiteSpace([string](Get-PropertyValue -Payload $ActivationPlanHostSupervisionAuthority -Name 'active_grant_receipt_id' -Default '')) -and
  [bool](Get-PropertyValue -Payload $ActivationPlanGovernance -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ActivationPlanGovernance -Name 'plan_readback_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ActivationPlanGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationPlanGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationPlanGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationPlanGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationPlanGovernance -Name 'service_install_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationPlanGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationPlanGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationPlanGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationPlanGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationPlanGovernance -Name 'resident_claim_authority' -Default $true)
)
$ProcessSupervisionAuthorityGranted = $ActivationPlanAuthorityObserved -and [bool](Get-PropertyValue -Payload $ActivationPlanPayload -Name 'process_supervision_authority' -Default $false)
$ProcessRestartAuthorityGranted = $ActivationPlanAuthorityObserved -and [bool](Get-PropertyValue -Payload $ActivationPlanPayload -Name 'process_restart_authority' -Default $false)
$ActiveResidentRuntimeAuthorityGrantReceiptId = [string](Get-PropertyValue -Payload $ActivationPlanPayload -Name 'active_authority_grant_receipt_id' -Default '')
$ActiveHostSupervisionAuthorityGrantReceiptId = [string](Get-PropertyValue -Payload $ActivationPlanHostSupervisionAuthority -Name 'active_grant_receipt_id' -Default '')
$BoundedResidentCandidateReady = $ActivationPlanAuthorityObserved -and [bool](Get-PropertyValue -Payload $ActivationPlanPayload -Name 'bounded_resident_candidate_ready' -Default $false)
$ActivationPlanWouldLaunchProcess = $ActivationPlanAuthorityObserved -and [bool](Get-PropertyValue -Payload $ActivationPlanPlan -Name 'would_launch_process' -Default $false)
$ActivationPlanWouldSuperviseProcess = $ActivationPlanAuthorityObserved -and [bool](Get-PropertyValue -Payload $ActivationPlanPlan -Name 'would_supervise_process' -Default $false)
$HostSupervisionObserved = (
  [int](Get-PropertyValue -Payload $HostSupervisionResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'kind' -Default '') -eq 'lens.host.supervision_readiness_proof' -and
  [string](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'supervision_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'ready_for_resident_claim' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'resident_claim_allowed' -Default $true)
)
$ProcessSupervisionDenied = (
  $HostSupervisionObserved -and
  [string](Get-PropertyValue -Payload $HostSupervisionProof -Name 'process_supervision_status' -Default '') -in @('blocked', 'enabled') -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'supervised' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionGovernance -Name 'process_supervision_authority' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionGovernance -Name 'process_restart_authority' -Default $false)
)
$ProcessSupervisionAuthorityBoundaryObserved = $ActivationPlanAuthorityObserved -or $ProcessSupervisionDenied
$ServiceActivationPlanBlocked = (
  $HostSupervisionObserved -and
  [string](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_plan_status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_plan_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_plan_would_install' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_plan_would_start' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'service_installed' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'service_managed' -Default $true) -and
  $ServicePlanBlockedBy -contains 'service_install_authority_false' -and
  $ServicePlanBlockedBy -contains 'service_control_authority_false'
)
$AuthorityBoundary = (
  $ActivationBoundaryObserved -and
  $ResidentSurfaceRuntimeSupervisionHandoffObserved -and
  $HostSupervisionObserved -and
  [bool](Get-PropertyValue -Payload $ActivationBoundaryGovernance -Name 'boundary_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ActivationBoundaryGovernance -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostSupervisionGovernance -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryGovernance -Name 'activation_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryGovernance -Name 'service_install_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationBoundaryGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionGovernance -Name 'service_install_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisionGovernance -Name 'service_control_authority' -Default $true)
)

$Checks = @(
  (New-Check -Id 'resident_surface_activation_boundary' -Status $(if ($ActivationBoundaryObserved) { 'activation_boundary_observed' } else { 'failed' }) -Passed $ActivationBoundaryObserved -Evidence 'lens_resident_surface_activation_boundary' -Reason 'The resident surface activation denial boundary must be observed without rerunning the full overlay/live-operator proof package.')
  (New-Check -Id 'resident_runtime_activation_plan_readback' -Status $(if ($ActivationPlanAuthorityObserved) { 'authority_granted' } elseif ($ActivationPlanReadbackObserved) { 'readback_blocked' } else { 'failed' }) -Passed $ActivationPlanReadbackObserved -Evidence 'lens_resident_runtime_activation_plan' -Reason 'The process-supervision boundary proof must consume the current resident-runtime activation plan readback before deciding whether process supervision authority is still denied or has been granted.')
  (New-Check -Id 'resident_surface_foreground_runtime_proof' -Status $(if ($ResidentSurfaceResidentRuntimeProofObserved) { 'resident_runtime_observed' } elseif ($ResidentSurfaceForegroundRuntimeProofObserved) { 'foreground_runtime_observed' } else { 'failed' }) -Passed $ResidentSurfaceRuntimeProofObserved -Evidence 'scripts/lens-resident-surface-proof.ps1 -Mode Status' -Reason 'The process-supervision authority proof must consume the resident-surface runtime proof before claiming this boundary is the current blocker.')
  (New-Check -Id 'resident_surface_runtime_supervision_handoff' -Status $(if ($ResidentSurfaceRuntimeSupervisionHandoffObserved) { 'handoff_observed' } else { 'missing_or_failed' }) -Passed $ResidentSurfaceRuntimeSupervisionHandoffObserved -Evidence 'resident_surface_runtime_supervision_handoff' -Reason 'The resident-surface proof must hand off to the current governed next step without granting execution, mutation, or resident-claim authority.')
  (New-Check -Id 'host_supervision_boundary' -Status $(if ($HostSupervisionObserved) { 'supervision_blocked' } else { 'failed' }) -Passed $HostSupervisionObserved -Evidence 'scripts/lens-host-supervision-proof.ps1 -Mode Status' -Reason 'The host supervision proof must remain observable and blocked.')
  (New-Check -Id 'process_supervision_denied' -Status $(if ($ActivationPlanAuthorityObserved) { 'authority_granted' } elseif ($ProcessSupervisionDenied) { 'blocked' } else { 'unexpected_authority' }) -Passed $ProcessSupervisionAuthorityBoundaryObserved -Evidence 'process_supervision_authority + process_restart_authority' -Reason 'Resident process supervision and restart authority must be truthfully reported as denied or granted by active authority receipts without implying a supervised resident process exists.')
  (New-Check -Id 'service_activation_plan_blocked' -Status $(if ($ServiceActivationPlanBlocked) { 'blocked_no_service_activation' } else { 'unexpected_service_activation' }) -Passed $ServiceActivationPlanBlocked -Evidence 'service_plan' -Reason 'The service plan does not install, start, or manage a resident host service.')
  (New-Check -Id 'authority_boundary' -Status $(if ($AuthorityBoundary) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $AuthorityBoundary -Evidence 'activation_boundary.governance + host_supervision.governance' -Reason 'The proof chain must not execute, approve, write memory, activate services, register tray or hotkey bindings, control overlay windows, claim residency, or capture data.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })
$AllBlockerCandidates = @()
$AllBlockerCandidates += ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ActivationBoundaryPayload -Name 'blockers' -Default @())
$AllBlockerCandidates += ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ActivationPlanPayload -Name 'blockers' -Default @())
$AllBlockerCandidates += $ResidentSurfaceBlockers
$AllBlockerCandidates += ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostSupervisionPayload -Name 'blockers' -Default @())
if (-not $ActivationPlanAuthorityObserved) {
  $AllBlockerCandidates += 'process_supervision_authority_not_granted'
  $AllBlockerCandidates += 'process_restart_authority_not_granted'
}
$AllBlockerCandidates += @(
  'service_install_authority_not_granted',
  'service_control_authority_not_granted',
  'resident_host_process_not_supervised',
  'resident_supervision_disabled'
)
$AllBlockers = @($AllBlockerCandidates | Sort-Object -Unique)
$AllBlockers = @($AllBlockers | Where-Object {
    $_ -ne 'operator_experience_proof_missing' -and $_ -ne 'live_operator_experience_proof_missing'
  })
if ($ActivationPlanAuthorityObserved) {
  $AllBlockers = @($AllBlockers | Where-Object {
      $_ -ne 'process_supervision_authority_not_granted' -and $_ -ne 'process_restart_authority_not_granted'
    })
}

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.process_supervision_authority_boundary.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  startup_timeout_seconds = $StartupTimeoutSeconds
  foreground_run_seconds = $ForegroundRunSeconds
  host_launch_run_seconds = $HostLaunchRunSeconds
  supervisor_run_seconds = $SupervisorRunSeconds
  resident_surface_foreground_run_seconds = $ResidentSurfaceForegroundRunSeconds
  effective_resident_surface_foreground_run_seconds = $EffectiveResidentSurfaceForegroundRunSeconds
  activation_boundary_mode = 'direct_resident_surface_activation_boundary'
  child_proof_timeout_seconds = $ChildProofTimeoutSeconds
  child_proof_timeouts = [string[]]@($ChildProofTimeouts)
  child_proof_runs = @($ChildProofRuns)
  cached_resident_surface_proof = [bool](Get-PropertyValue -Payload $ResidentSurfaceResult -Name 'cached' -Default $false)
  cached_host_supervision_proof = [bool](Get-PropertyValue -Payload $HostSupervisionResult -Name 'cached' -Default $false)
  authority_required = if ($ActivationPlanAuthorityObserved) { 'resident_runtime_execution_and_host_supervision_authority' } else { 'process_supervision_and_service_control' }
  authority_granted = $ActivationPlanAuthorityObserved
  resident_runtime_activation_plan_readback_observed = $ActivationPlanReadbackObserved
  resident_runtime_activation_plan_authority_observed = $ActivationPlanAuthorityObserved
  active_resident_runtime_authority_grant_receipt_id = $ActiveResidentRuntimeAuthorityGrantReceiptId
  active_host_supervision_authority_grant_receipt_id = $ActiveHostSupervisionAuthorityGrantReceiptId
  bounded_resident_candidate_ready = $BoundedResidentCandidateReady
  activation_plan_would_launch_process = $ActivationPlanWouldLaunchProcess
  activation_plan_would_supervise_process = $ActivationPlanWouldSuperviseProcess
  resident_surface_runtime_proof_observed = $ResidentSurfaceRuntimeProofObserved
  resident_surface_foreground_runtime_proof_observed = $ResidentSurfaceForegroundRuntimeProofObserved
  resident_surface_resident_runtime_proof_observed = $ResidentSurfaceResidentRuntimeProofObserved
  resident_surface_runtime_supervision_handoff_observed = $ResidentSurfaceRuntimeSupervisionHandoffObserved
  resident_surface_operator_experience_handoff_observed = $ResidentSurfaceOperatorExperienceHandoffObserved
  resident_surface_runtime_supervision_handoff = $ResidentSurfaceRecommendedHandoff
  resident_surface_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'next_smallest_truthful_gap' -Default '')
  resident_surface_authority_required = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'authority_required' -Default '')
  resident_surface_authority_granted = [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'authority_granted' -Default $false)
  resident_surface_recommended_handoff_source = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'recommended_handoff_source' -Default '')
  resident_surface_recommended_next_slice = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'recommended_next_slice' -Default '')
  resident_surface_recommended_proof_script = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'recommended_proof_script' -Default '')
  recommended_handoff_source = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'recommended_handoff_source' -Default '')
  recommended_next_slice = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'recommended_next_slice' -Default '')
  recommended_proof_script = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'recommended_proof_script' -Default '')
  recommended_handoff = $ResidentSurfaceRecommendedHandoff
  process_supervision_authority_required = 'process_supervision_authority'
  process_supervision_authority_granted = $ProcessSupervisionAuthorityGranted
  process_restart_authority_required = 'process_restart_authority'
  process_restart_authority_granted = $ProcessRestartAuthorityGranted
  service_install_authority_required = 'service_install_authority'
  service_install_authority_granted = $false
  service_control_authority_required = 'service_control_authority'
  service_control_authority_granted = $false
  stage6_checkpoint_observed = $false
  resident_surface_activation_boundary_observed = $ActivationBoundaryObserved
  resident_overlay_activation_boundary_observed = $ActivationBoundaryObserved
  host_supervision_boundary_observed = $HostSupervisionObserved
  process_supervision_boundary_observed = $ProcessSupervisionAuthorityBoundaryObserved
  service_activation_plan_observed = $ServiceActivationPlanBlocked
  bounded_local_process_launch_observed = [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'bounded_host_launch_observed' -Default $false)
  supervision_ready = $false
  ready_for_resident_claim = $false
  resident_claim_allowed = $false
  resident_host_process = $false
  resident_host_supervised = $false
  service_installed = $false
  service_managed = $false
  process_supervision_ready = $ActivationPlanAuthorityObserved
  service_activation_ready = $false
  tray_presence = $false
  global_hotkey_bound = $false
  overlay_window = $false
  summon_anywhere = $false
  would_supervise_process = $false
  would_restart_process = $false
  would_install_service = $false
  would_start_service = $false
  would_write_wrapper = $false
  would_write_memory = $false
  would_decide_approval = $false
  checks = @($Checks)
  blockers = @($AllBlockers)
  proof = [ordered]@{
    checkpoint_status = 'not_run'
    checkpoint_stage_state = ''
    checkpoint_system_resident_status = ''
    checkpoint_next_smallest_truthful_gap = ''
    activation_boundary_source = 'direct_resident_surface_activation_boundary'
    activation_boundary_status = [string](Get-PropertyValue -Payload $ActivationBoundaryPayload -Name 'status' -Default '')
    activation_boundary_ok = [bool](Get-PropertyValue -Payload $ActivationBoundaryPayload -Name 'ok' -Default $false)
    activation_boundary_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $ActivationBoundaryPayload -Name 'next_smallest_truthful_gap' -Default '')
    resident_runtime_activation_plan_status = [string](Get-PropertyValue -Payload $ActivationPlanPayload -Name 'status' -Default '')
    resident_runtime_activation_plan_readback_observed = $ActivationPlanReadbackObserved
    resident_runtime_activation_plan_authority_observed = $ActivationPlanAuthorityObserved
    active_resident_runtime_authority_grant_receipt_id = $ActiveResidentRuntimeAuthorityGrantReceiptId
    active_host_supervision_authority_grant_receipt_id = $ActiveHostSupervisionAuthorityGrantReceiptId
    bounded_resident_candidate_ready = $BoundedResidentCandidateReady
    activation_plan_would_launch_process = $ActivationPlanWouldLaunchProcess
    activation_plan_would_supervise_process = $ActivationPlanWouldSuperviseProcess
    resident_surface_activation_boundary_observed = $ActivationBoundaryObserved
    resident_overlay_boundary_observed = $false
    resident_surface_foreground_runtime_proof_status = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'status' -Default '')
    resident_surface_runtime_proof_observed = $ResidentSurfaceRuntimeProofObserved
    resident_surface_foreground_runtime_proof_observed = $ResidentSurfaceForegroundRuntimeProofObserved
    resident_surface_resident_runtime_proof_observed = $ResidentSurfaceResidentRuntimeProofObserved
    resident_surface_runtime_supervision_handoff_observed = $ResidentSurfaceRuntimeSupervisionHandoffObserved
    resident_surface_operator_experience_handoff_observed = $ResidentSurfaceOperatorExperienceHandoffObserved
    resident_surface_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'next_smallest_truthful_gap' -Default '')
    resident_surface_authority_required = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'authority_required' -Default '')
    resident_surface_runtime_status = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_surface_runtime_status' -Default '')
    host_supervision_status = [string](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'status' -Default '')
    host_supervision_ready = [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'supervision_ready' -Default $false)
    host_ready_for_resident_claim = [bool](Get-PropertyValue -Payload $HostSupervisionPayload -Name 'ready_for_resident_claim' -Default $false)
    process_supervision_status = [string](Get-PropertyValue -Payload $HostSupervisionProof -Name 'process_supervision_status' -Default '')
    service_control_status = [string](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_control_status' -Default '')
    service_plan_status = [string](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_plan_status' -Default '')
    service_plan_ready = [bool](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_plan_ready' -Default $false)
    service_plan_would_install = [bool](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_plan_would_install' -Default $false)
    service_plan_would_start = [bool](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_plan_would_start' -Default $false)
    service_plan_blocked_by = $ServicePlanBlockedBy
    service_status = [string](Get-PropertyValue -Payload $HostSupervisionProof -Name 'service_status' -Default '')
  }
  next_smallest_truthful_gap = 'stage6_lens_completion_audit'
  governance = [ordered]@{
    diagnostic_only = $true
    checkpoint_readback = $false
    resident_surface_activation_boundary_readback = $ActivationBoundaryObserved
    resident_overlay_activation_boundary_readback = $ActivationBoundaryObserved
    resident_runtime_activation_plan_readback = $ActivationPlanReadbackObserved
    resident_runtime_activation_plan_authority_readback = $ActivationPlanAuthorityObserved
    cached_resident_surface_proof = [bool](Get-PropertyValue -Payload $ResidentSurfaceResult -Name 'cached' -Default $false)
    cached_host_supervision_proof = [bool](Get-PropertyValue -Payload $HostSupervisionResult -Name 'cached' -Default $false)
    live_http_readback = $false
    temporary_api_process = $false
    bounded_host_launch = [bool](Get-PropertyValue -Payload $HostSupervisionGovernance -Name 'bounded_host_launch' -Default $false)
    bounded_process_launch = [bool](Get-PropertyValue -Payload $HostSupervisionGovernance -Name 'bounded_process_launch' -Default $false)
    bounded_supervisor_observation = $HostSupervisionObserved
    resident_surface_activation_boundary_observed = $ActivationBoundaryObserved
    resident_overlay_activation_boundary_observed = $ActivationBoundaryObserved
    resident_surface_foreground_runtime_readback = $ResidentSurfaceForegroundRuntimeProofObserved
    resident_surface_resident_runtime_readback = $ResidentSurfaceResidentRuntimeProofObserved
    resident_surface_runtime_readback = $ResidentSurfaceRuntimeProofObserved
    resident_surface_runtime_supervision_handoff_readback = $ResidentSurfaceRuntimeSupervisionHandoffObserved
    resident_surface_operator_experience_handoff_readback = $ResidentSurfaceOperatorExperienceHandoffObserved
    resident_host_supervision_authority_denial_boundary_observed = $false
    resident_host_supervision_authority_denial_receipt_readback_observed = $false
    resident_host_supervision_authority_grant_receipt_readback_observed = $false
    resident_host_supervision_authority_readiness_audit_observed = $false
    temporary_runtime_state_write = $true
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    resident_overlay_activation_authority = $false
    resident_runtime_execution_authority = $ActivationPlanAuthorityObserved
    host_supervision_authority = $ActivationPlanAuthorityObserved
    process_restart_authority = $ProcessRestartAuthorityGranted
    process_supervision_authority = $ProcessSupervisionAuthorityGranted
    service_install_authority = $false
    service_control_authority = $false
    resident_claim_authority = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = [bool](Get-PropertyValue -Payload $HostSupervisionGovernance -Name 'local_process_launch_authority' -Default $false)
    api_local_process_launch_authority = $false
    activation_local_process_launch_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    tray_icon_authority = $false
    receipt_write_authority = $false
    denial_receipt_write_authority = $false
    mutation_authority_granted = $false
  }
  message = if ($ActivationPlanAuthorityObserved) { 'Stage 6 process supervision authority is granted by active resident-runtime and host-supervision readbacks, but Francis still has not supervised, restarted, installed, started, or managed a resident Lens host service.' } else { 'Stage 6 process supervision authority remains a boundary: resident surface activation denial and host supervision proof are observable, but Francis does not supervise, restart, install, start, or manage a resident Lens host service.' }
}

$Payload | ConvertTo-Json -Depth 10
if ($ProofPassed) {
  exit 0
}
exit 1
