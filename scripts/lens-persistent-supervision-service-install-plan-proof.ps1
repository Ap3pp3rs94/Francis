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
  $Text = [string]$Value
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return @()
  }
  return @($Text)
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

function Invoke-JsonReportProcess {
  param(
    [string]$PowerShellPath,
    [string]$ScriptPath,
    [string[]]$ScriptArgs
  )

  $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
  $StartInfo.FileName = $PowerShellPath
  $StartInfo.Arguments = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    (Quote-ProcessArgument -Value $ScriptPath)
  ) + @($ScriptArgs | ForEach-Object { Quote-ProcessArgument -Value $_ }) -join ' '
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
      output = ''
      error = [string]$_.Exception.Message
      report_path = ''
      report = $null
      duration_ms = [int]$Timer.ElapsedMilliseconds
    }
  }
  if (-not $Started) {
    $Timer.Stop()
    return [ordered]@{
      exit_code = 1
      output = ''
      error = 'process_not_started'
      report_path = ''
      report = $null
      duration_ms = [int]$Timer.ElapsedMilliseconds
    }
  }

  $Output = $Process.StandardOutput.ReadToEnd()
  $ErrorText = $Process.StandardError.ReadToEnd()
  $Process.WaitForExit()
  $Timer.Stop()

  $ReportPath = ''
  foreach ($Line in @($Output -split "`r?`n")) {
    if ($Line -match '^Saved report:\s*(.+)$') {
      $ReportPath = [string]$Matches[1]
    }
  }

  $Report = $null
  if (-not [string]::IsNullOrWhiteSpace($ReportPath) -and (Test-Path -LiteralPath $ReportPath -PathType Leaf)) {
    try {
      $Report = Get-Content -LiteralPath $ReportPath -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop
    } catch {
      $Report = $null
    }
  }

  return [ordered]@{
    exit_code = [int]$Process.ExitCode
    output = $Output
    error = $ErrorText
    report_path = $ReportPath
    report = $Report
    duration_ms = [int]$Timer.ElapsedMilliseconds
  }
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  [ordered]@{
    ok = $false
    kind = 'lens.host.persistent_supervision_service_install_plan.proof'
    status = 'proof_failed'
    mode = $Mode.ToLowerInvariant()
    repo_root = $RepoRoot
    error = 'pwsh_unavailable'
  } | ConvertTo-Json -Depth 8
  exit 1
}

$ServiceInstallScript = Join-Path $PSScriptRoot 'service-install.ps1'
$ServiceConfigPath = Join-Path $RepoRoot 'config\runtime\services\lens-host.json'
$WrapperPath = Join-Path $RepoRoot 'data\runtime\services\Francis-LensHost\run.cmd'
$WrapperExistedBefore = Test-Path -LiteralPath $WrapperPath -PathType Leaf

$Config = $null
try {
  $Config = Get-Content -LiteralPath $ServiceConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop
} catch {
  $Config = $null
}

$PlanResult = Invoke-JsonReportProcess -PowerShellPath $PowerShell.Source -ScriptPath $ServiceInstallScript -ScriptArgs @(
  '-Mode',
  'Plan',
  '-Root',
  $RepoRoot,
  '-ConfigPath',
  $ServiceConfigPath
)
$WrapperExistsAfter = Test-Path -LiteralPath $WrapperPath -PathType Leaf
$WrapperCreated = (-not $WrapperExistedBefore) -and $WrapperExistsAfter

$Report = Get-PropertyValue -Payload $PlanResult -Name 'report'
$Plans = @()
if ($null -ne $Report) {
  $Plans = @(Get-PropertyValue -Payload $Report -Name 'plans' -Default @())
}
$Plan = if ($Plans.Count -gt 0) { $Plans[0] } else { $null }
$PlanGovernance = Get-PropertyValue -Payload $Plan -Name 'governance'
$BlockedBy = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Plan -Name 'blocked_by' -Default @())
$RequiredBeforeEnable = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Config -Name 'required_before_enable' -Default @())

$ExpectedServiceBlockers = @(
  'installable_false',
  'install_authority_false',
  'service_install_authority_false',
  'service_control_authority_false'
)
$ExpectedRequiredBeforeEnable = @(
  'resident_host_process',
  'tray_presence',
  'global_hotkey_binding',
  'overlay_window',
  'summon_binding'
)

$ConfigObserved = (
  $null -ne $Config -and
  [string](Get-PropertyValue -Payload $Config -Name 'kind' -Default '') -eq 'lens.host.service_config' -and
  [string](Get-PropertyValue -Payload $Config -Name 'service_name' -Default '') -eq 'Francis-LensHost' -and
  -not [bool](Get-PropertyValue -Payload $Config -Name 'enabled' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Config -Name 'installable' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Config -Name 'install_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Config -Name 'service_install_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Config -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Config -Name 'process_supervision_enabled' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Config -Name 'persistent_supervision_enabled' -Default $true)
)
foreach ($Item in $ExpectedRequiredBeforeEnable) {
  if ($RequiredBeforeEnable -notcontains $Item) {
    $ConfigObserved = $false
  }
}

$PlanBlocked = (
  [int](Get-PropertyValue -Payload $PlanResult -Name 'exit_code' -Default -1) -eq 0 -and
  $null -ne $Report -and
  [string](Get-PropertyValue -Payload $Report -Name 'mode' -Default '') -eq 'Plan' -and
  $null -ne $Plan -and
  [string](Get-PropertyValue -Payload $Plan -Name 'kind' -Default '') -eq 'service_install.plan' -and
  [string](Get-PropertyValue -Payload $Plan -Name 'service' -Default '') -eq 'Francis-LensHost' -and
  [string](Get-PropertyValue -Payload $Plan -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $Plan -Name 'ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Plan -Name 'would_install' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Plan -Name 'would_start' -Default $true)
)
foreach ($Item in $ExpectedServiceBlockers) {
  if ($BlockedBy -notcontains $Item) {
    $PlanBlocked = $false
  }
}

$PlanGovernanceObserved = (
  [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'read_only_contract' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'service_install_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PlanGovernance -Name 'mutation_authority_granted' -Default $true)
)

$WrapperDenied = (
  $null -ne $Plan -and
  -not $WrapperCreated -and
  -not [bool](Get-PropertyValue -Payload (Get-PropertyValue -Payload $Plan -Name 'wrapper') -Name 'would_write' -Default $true)
)

$Checks = @(
  (New-Check -Id 'lens_host_service_config_disabled' -Status $(if ($ConfigObserved) { 'disabled' } else { 'missing_or_unexpected' }) -Passed $ConfigObserved -Evidence 'config/runtime/services/lens-host.json' -Reason 'Persistent supervision cannot be enabled until the service config explicitly allows the resident host and supervision path.')
  (New-Check -Id 'service_install_plan_blocked' -Status $(if ($PlanBlocked) { 'blocked' } else { 'missing_or_unexpected' }) -Passed $PlanBlocked -Evidence 'scripts/service-install.ps1 -Mode Plan -ConfigPath config/runtime/services/lens-host.json' -Reason 'The Windows service manager plan must remain blocked while install/control authority is false.')
  (New-Check -Id 'service_install_plan_governance' -Status $(if ($PlanGovernanceObserved) { 'read_only_bounded' } else { 'unexpected_authority' }) -Passed $PlanGovernanceObserved -Evidence 'service_install.plan.governance' -Reason 'The plan proof must not grant execution, service-install, service-control, memory, or approval-decision authority.')
  (New-Check -Id 'service_wrapper_not_created' -Status $(if ($WrapperDenied) { 'not_created' } else { 'unexpected_wrapper_write' }) -Passed $WrapperDenied -Evidence 'data/runtime/services/Francis-LensHost/run.cmd' -Reason 'Plan mode must not create the service wrapper or mutate runtime state.')
)
$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

[ordered]@{
  ok = $ProofPassed
  kind = 'lens.host.persistent_supervision_service_install_plan.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  service_config = 'config/runtime/services/lens-host.json'
  service_install_script = 'scripts/service-install.ps1'
  service_install_report = [string](Get-PropertyValue -Payload $PlanResult -Name 'report_path' -Default '')
  service_name = [string](Get-PropertyValue -Payload $Config -Name 'service_name' -Default '')
  service_plan_status = [string](Get-PropertyValue -Payload $Plan -Name 'status' -Default '')
  service_plan_ready = [bool](Get-PropertyValue -Payload $Plan -Name 'ready' -Default $false)
  service_plan_would_install = [bool](Get-PropertyValue -Payload $Plan -Name 'would_install' -Default $false)
  service_plan_would_start = [bool](Get-PropertyValue -Payload $Plan -Name 'would_start' -Default $false)
  process_supervision_enabled = [bool](Get-PropertyValue -Payload $Config -Name 'process_supervision_enabled' -Default $false)
  persistent_supervision_enabled = [bool](Get-PropertyValue -Payload $Config -Name 'persistent_supervision_enabled' -Default $false)
  persistent_supervision_enablement_disabled = $ConfigObserved -and $PlanBlocked
  installable = [bool](Get-PropertyValue -Payload $Config -Name 'installable' -Default $false)
  install_authority = [bool](Get-PropertyValue -Payload $Config -Name 'install_authority' -Default $false)
  service_install_authority = [bool](Get-PropertyValue -Payload $Config -Name 'service_install_authority' -Default $false)
  service_control_authority = [bool](Get-PropertyValue -Payload $Config -Name 'service_control_authority' -Default $false)
  wrapper_existed_before = $WrapperExistedBefore
  wrapper_exists_after = $WrapperExistsAfter
  wrapper_created_by_proof = $WrapperCreated
  checks = @($Checks)
  blocked_by = [string[]]@($BlockedBy)
  required_before_enable = [string[]]@($RequiredBeforeEnable)
  next_smallest_truthful_gap = 'persistent_supervision_enablement_disabled'
  evidence = [string[]]@(
    'scripts/lens-persistent-supervision-service-install-plan-proof.ps1 -Mode Status',
    'scripts/service-install.ps1 -Mode Plan -ConfigPath config/runtime/services/lens-host.json',
    'config/runtime/services/lens-host.json'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    read_only_contract = $true
    wraps_service_install_plan = $true
    service_config_readback = $ConfigObserved
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
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'The persistent Lens host service install plan is present but disabled and authority-blocked; plan mode does not install, start, write a wrapper, mutate service config, write memory, or claim residency.'
} | ConvertTo-Json -Depth 12

exit $(if ($ProofPassed) { 0 } else { 1 })
