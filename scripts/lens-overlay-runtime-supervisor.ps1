[CmdletBinding()]
param(
  [ValidateSet('Status', 'Run')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [string]$ManifestPath = '',

  [ValidateRange(0, 10)]
  [int]$MaxRestarts = 3,

  [ValidateRange(5, 3600)]
  [int]$RestartWindowSeconds = 60,

  [ValidateRange(1, 60)]
  [int]$BackoffSeconds = 2
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

function Get-DataRoot {
  param([string]$Override)

  if (-not [string]::IsNullOrWhiteSpace($Override)) {
    return [System.IO.Path]::GetFullPath($Override)
  }
  $Configured = [string]$env:FRANCIS_DATA_DIR
  if (-not [string]::IsNullOrWhiteSpace($Configured)) {
    return [System.IO.Path]::GetFullPath($Configured)
  }
  return (Join-Path $RepoRoot 'data')
}

function Read-JsonFile {
  param([string]$Path)

  try {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf -ErrorAction Stop)) {
      return $null
    }
    return Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
  } catch {
    return $null
  }
}

function Write-JsonFile {
  param(
    [string]$Path,
    [object]$Payload
  )

  $Parent = Split-Path -Parent $Path
  New-Item -ItemType Directory -Force -Path $Parent | Out-Null
  $TempPath = Join-Path $Parent ('.{0}.{1}.tmp' -f ([System.IO.Path]::GetFileName($Path)), ([guid]::NewGuid().ToString('N')))
  $BackupPath = $TempPath + '.bak'
  try {
    $Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $TempPath -Encoding UTF8
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
      [System.IO.File]::Replace($TempPath, $Path, $BackupPath, $true)
      Remove-Item -LiteralPath $BackupPath -Force -ErrorAction SilentlyContinue
    } else {
      Move-Item -LiteralPath $TempPath -Destination $Path -Force
    }
  } finally {
    Remove-Item -LiteralPath $TempPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $BackupPath -Force -ErrorAction SilentlyContinue
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
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) {
    return $Default
  }
  return $Property.Value
}

function Test-ProcessAlive {
  param([int]$ProcessId)

  if ($ProcessId -le 0) {
    return $false
  }
  try {
    Get-Process -Id $ProcessId -ErrorAction Stop | Out-Null
    return $true
  } catch {
    return $false
  }
}

function Get-PidValue {
  param([string]$Path)

  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return 0
  }
  try {
    return [int]((Get-Content -LiteralPath $Path -Raw -ErrorAction Stop).Trim())
  } catch {
    return 0
  }
}

function ConvertTo-ReceiptPath {
  param([string]$Path)

  $FullPath = [System.IO.Path]::GetFullPath($Path)
  $RootPrefix = $RepoRoot.TrimEnd('\') + '\'
  if ($FullPath.StartsWith($RootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    return $FullPath.Substring($RootPrefix.Length).Replace('\', '/')
  }
  return $FullPath
}

function Test-SupervisorProcess {
  param([int]$ProcessId)

  if (-not (Test-ProcessAlive -ProcessId $ProcessId)) {
    return $false
  }
  if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    return $true
  }
  try {
    $Process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
    $CommandLine = [string]$Process.CommandLine
    return (
      $CommandLine -like '*lens-overlay-runtime-supervisor.ps1*' -and
      $CommandLine -like '*-Mode Run*'
    )
  } catch {
    return $false
  }
}

function Stop-OwnedOrphanRenderer {
  param(
    [string]$Root,
    [int]$ExitedChildPid
  )

  if ($ExitedChildPid -le 0 -or [System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    return @()
  }
  $RendererRoot = [System.IO.Path]::GetFullPath((Join-Path $Root 'runtime\native-orb-renderer'))
  $Stopped = [System.Collections.ArrayList]::new()
  try {
    $Candidates = @(Get-CimInstance Win32_Process -Filter "Name = 'native_orb_renderer.exe'" -ErrorAction Stop)
  } catch {
    return @()
  }
  foreach ($Candidate in $Candidates) {
    $CommandLine = [string]$Candidate.CommandLine
    if ([int]$Candidate.ParentProcessId -ne $ExitedChildPid -or $CommandLine -notlike "*$RendererRoot*") {
      continue
    }
    try {
      Stop-Process -Id ([int]$Candidate.ProcessId) -Force -ErrorAction Stop
      [void]$Stopped.Add([int]$Candidate.ProcessId)
    } catch {
    }
  }
  return @($Stopped)
}

function Remove-StaleChildPid {
  param(
    [string]$Path,
    [int]$ExitedChildPid
  )

  if ((Get-PidValue -Path $Path) -eq $ExitedChildPid -and -not (Test-ProcessAlive -ProcessId $ExitedChildPid)) {
    Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
  }
}

function New-GovernanceProjection {
  param([object]$Manifest)

  return [ordered]@{
    authority_source = [string](Get-PropertyValue -Payload $Manifest -Name 'authority_source' -Default 'explicit_operator_start_switch')
    operator_authorized = [bool](Get-PropertyValue -Payload $Manifest -Name 'operator_authorized' -Default $false)
    process_supervision_authority = $true
    process_restart_authority = $true
    process_restart_authority_scope = 'overlay_runtime_child_only'
    bounded_restart_window = $true
    arbitrary_process_launch = $false
    service_install_authority = $false
    service_control_authority = $false
    input_control_authority = $false
    capture_authority = $false
    memory_write = $false
    learning_authority = $false
    generalization_authority = $false
  }
}

$DataRoot = Get-DataRoot -Override $DataDir
$RuntimeRoot = Join-Path $DataRoot 'runtime\lens-overlay'
$SupervisorPidPath = Join-Path $RuntimeRoot 'runtime-recovery-supervisor.pid'
$SupervisorStatusPath = Join-Path $RuntimeRoot 'runtime-recovery-status.json'
$StopRequestPath = Join-Path $RuntimeRoot 'runtime-recovery-stop-request.json'
$ChildPidPath = Join-Path $RuntimeRoot 'lens-overlay.pid'
$ReceiptRoot = Join-Path $RuntimeRoot 'runtime-recovery-receipts'
$LogRoot = Join-Path $RuntimeRoot 'runtime-recovery-logs'

function Get-SupervisorReadback {
  $State = Read-JsonFile -Path $SupervisorStatusPath
  $SupervisorPid = Get-PidValue -Path $SupervisorPidPath
  $Alive = Test-SupervisorProcess -ProcessId $SupervisorPid
  return [ordered]@{
    ok = $true
    kind = 'lens.overlay.runtime_recovery_readback'
    status = [string](Get-PropertyValue -Payload $State -Name 'status' -Default 'disabled_or_stopped')
    enabled = $Alive
    supervisor_pid = $SupervisorPid
    supervisor_process_alive = $Alive
    child_pid = [int](Get-PropertyValue -Payload $State -Name 'child_pid' -Default 0)
    child_process_alive = Test-ProcessAlive -ProcessId ([int](Get-PropertyValue -Payload $State -Name 'child_pid' -Default 0))
    restart_count = [int](Get-PropertyValue -Payload $State -Name 'restart_count' -Default 0)
    restart_count_in_window = [int](Get-PropertyValue -Payload $State -Name 'restart_count_in_window' -Default 0)
    max_restarts = [int](Get-PropertyValue -Payload $State -Name 'max_restarts' -Default 0)
    restart_window_seconds = [int](Get-PropertyValue -Payload $State -Name 'restart_window_seconds' -Default 0)
    latest_receipt_path = [string](Get-PropertyValue -Payload $State -Name 'latest_receipt_path' -Default '')
    status_path = ConvertTo-ReceiptPath -Path $SupervisorStatusPath
    pid_path = ConvertTo-ReceiptPath -Path $SupervisorPidPath
  }
}

if ($Mode -eq 'Status') {
  Get-SupervisorReadback | ConvertTo-Json -Depth 6
  exit 0
}

if ([string]::IsNullOrWhiteSpace($ManifestPath) -or -not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
  throw 'overlay_runtime_recovery_manifest_missing'
}

$Manifest = Read-JsonFile -Path $ManifestPath
$ManifestDataRoot = [System.IO.Path]::GetFullPath([string](Get-PropertyValue -Payload $Manifest -Name 'data_root' -Default ''))
$PowerShellPath = [string](Get-PropertyValue -Payload $Manifest -Name 'powershell_path' -Default '')
$OverlayScriptPath = [string](Get-PropertyValue -Payload $Manifest -Name 'overlay_script_path' -Default '')
$ArgumentText = [string](Get-PropertyValue -Payload $Manifest -Name 'argument_text' -Default '')
$OperatorAuthorized = [bool](Get-PropertyValue -Payload $Manifest -Name 'operator_authorized' -Default $false)
$AuthorityScope = [string](Get-PropertyValue -Payload $Manifest -Name 'process_restart_authority_scope' -Default '')
$ManifestMaxRestarts = [int](Get-PropertyValue -Payload $Manifest -Name 'max_restarts' -Default -1)
$ManifestRestartWindowSeconds = [int](Get-PropertyValue -Payload $Manifest -Name 'restart_window_seconds' -Default -1)
$ManifestBackoffSeconds = [int](Get-PropertyValue -Payload $Manifest -Name 'backoff_seconds' -Default -1)
$OverlayInvocationPattern = '(?i)^-NoProfile\s+-ExecutionPolicy\s+Bypass\s+-STA\s+-File\s+"?' + [regex]::Escape($OverlayScriptPath) + '"?\s+-Mode\s+Run(?:\s|$)'
$ManifestValid = (
  [string](Get-PropertyValue -Payload $Manifest -Name 'kind' -Default '') -eq 'lens.overlay.runtime_recovery_manifest' -and
  $ManifestDataRoot -eq [System.IO.Path]::GetFullPath($DataRoot) -and
  $OperatorAuthorized -and
  $AuthorityScope -eq 'overlay_runtime_child_only' -and
  $ManifestMaxRestarts -eq $MaxRestarts -and
  $ManifestRestartWindowSeconds -eq $RestartWindowSeconds -and
  $ManifestBackoffSeconds -eq $BackoffSeconds -and
  (Test-Path -LiteralPath $PowerShellPath -PathType Leaf) -and
  (Test-Path -LiteralPath $OverlayScriptPath -PathType Leaf) -and
  $ArgumentText -match $OverlayInvocationPattern -and
  $ArgumentText -notmatch '(?i)(^|\s)-Command(?:\s|$)'
)
if (-not $ManifestValid) {
  throw 'overlay_runtime_recovery_manifest_invalid_or_unauthorized'
}

$ExistingSupervisorPid = Get-PidValue -Path $SupervisorPidPath
if ($ExistingSupervisorPid -gt 0 -and $ExistingSupervisorPid -ne $PID -and (Test-SupervisorProcess -ProcessId $ExistingSupervisorPid)) {
  throw 'overlay_runtime_recovery_supervisor_already_running'
}

New-Item -ItemType Directory -Force -Path $RuntimeRoot, $ReceiptRoot, $LogRoot | Out-Null
Set-Content -LiteralPath $SupervisorPidPath -Value ([string]$PID) -Encoding UTF8
$Governance = New-GovernanceProjection -Manifest $Manifest
$StartedAt = [DateTimeOffset]::UtcNow
$RestartTimestamps = @()
$RestartCount = 0
$LatestReceiptPath = ''
$ExitCode = 0

function Write-SupervisorState {
  param(
    [string]$Status,
    [int]$ChildPid = 0,
    [bool]$ChildAlive = $false,
    [string]$Message = ''
  )

  $Cutoff = [DateTimeOffset]::UtcNow.AddSeconds(-$RestartWindowSeconds)
  $ActiveRestarts = @($script:RestartTimestamps | Where-Object { $_ -ge $Cutoff })
  Write-JsonFile -Path $SupervisorStatusPath -Payload ([ordered]@{
      kind = 'lens.overlay.runtime_recovery_state'
      status = $Status
      supervisor_pid = $PID
      supervisor_process_alive = $true
      child_pid = $ChildPid
      child_process_alive = $ChildAlive
      started_at = $StartedAt.ToString('o')
      updated_at = [DateTimeOffset]::UtcNow.ToString('o')
      restart_count = $script:RestartCount
      restart_count_in_window = $ActiveRestarts.Count
      max_restarts = $MaxRestarts
      restart_window_seconds = $RestartWindowSeconds
      backoff_seconds = $BackoffSeconds
      latest_receipt_path = $script:LatestReceiptPath
      message = $Message
      governance = $Governance
    })
}

function Write-RecoveryReceipt {
  param(
    [string]$Status,
    [int]$ChildPid,
    [Nullable[int]]$ChildExitCode,
    [string]$ChildStartedAt,
    [string]$ChildExitedAt,
    [double]$ChildUptimeSeconds,
    [bool]$RestartScheduled,
    [int[]]$StoppedRendererPids,
    [string]$StdoutPath,
    [string]$StderrPath,
    [string]$Error = ''
  )

  $ReceiptId = 'lens_overlay_recovery_{0}' -f ([guid]::NewGuid().ToString('N'))
  $ReceiptPath = Join-Path $ReceiptRoot ($ReceiptId + '.json')
  Write-JsonFile -Path $ReceiptPath -Payload ([ordered]@{
      kind = 'lens.overlay.runtime_recovery_receipt'
      receipt_id = $ReceiptId
      status = $Status
      supervisor_pid = $PID
      child_pid = $ChildPid
      child_exit_code = $ChildExitCode
      child_started_at = $ChildStartedAt
      child_exited_at = $ChildExitedAt
      child_uptime_seconds = [Math]::Round($ChildUptimeSeconds, 3)
      restart_scheduled = $RestartScheduled
      restart_count = $script:RestartCount
      max_restarts = $MaxRestarts
      restart_window_seconds = $RestartWindowSeconds
      orphan_renderer_pids_stopped = @($StoppedRendererPids)
      stdout_path = ConvertTo-ReceiptPath -Path $StdoutPath
      stderr_path = ConvertTo-ReceiptPath -Path $StderrPath
      error = $Error
      observed_at = [DateTimeOffset]::UtcNow.ToString('o')
      governance = $Governance
    })
  $script:LatestReceiptPath = ConvertTo-ReceiptPath -Path $ReceiptPath
  return $script:LatestReceiptPath
}

try {
  while (-not (Test-Path -LiteralPath $StopRequestPath -PathType Leaf)) {
    $AttemptId = [guid]::NewGuid().ToString('N')
    $StdoutPath = Join-Path $LogRoot ("child-$AttemptId-stdout.log")
    $StderrPath = Join-Path $LogRoot ("child-$AttemptId-stderr.log")
    $Child = $null
    $ChildStarted = [DateTimeOffset]::UtcNow
    try {
      $Child = Start-Process `
        -FilePath $PowerShellPath `
        -ArgumentList $ArgumentText `
        -WorkingDirectory $RepoRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $StdoutPath `
        -RedirectStandardError $StderrPath `
        -PassThru `
        -ErrorAction Stop
      [void](Write-RecoveryReceipt `
          -Status 'child_started' `
          -ChildPid ([int]$Child.Id) `
          -ChildExitCode $null `
          -ChildStartedAt $ChildStarted.ToString('o') `
          -ChildExitedAt '' `
          -ChildUptimeSeconds 0 `
          -RestartScheduled $false `
          -StoppedRendererPids @() `
          -StdoutPath $StdoutPath `
          -StderrPath $StderrPath)
      Write-SupervisorState -Status 'supervising' -ChildPid ([int]$Child.Id) -ChildAlive $true -Message 'Overlay runtime child is live under an explicit bounded recovery lease.'
      Wait-Process -Id ([int]$Child.Id) -ErrorAction SilentlyContinue
      $Child.Refresh()
      $ObservedExitCode = try { [int]$Child.ExitCode } catch { -1 }
      $ChildExited = [DateTimeOffset]::UtcNow
    } catch {
      $ObservedExitCode = -1
      $ChildExited = [DateTimeOffset]::UtcNow
      $LaunchError = [string]$_.Exception.Message
      [void](Write-RecoveryReceipt `
          -Status 'child_start_failed' `
          -ChildPid 0 `
          -ChildExitCode $ObservedExitCode `
          -ChildStartedAt $ChildStarted.ToString('o') `
          -ChildExitedAt $ChildExited.ToString('o') `
          -ChildUptimeSeconds 0 `
          -RestartScheduled $false `
          -StoppedRendererPids @() `
          -StdoutPath $StdoutPath `
          -StderrPath $StderrPath `
          -Error $LaunchError)
      $Child = $null
    }

    $ChildPid = if ($null -ne $Child) { [int]$Child.Id } else { 0 }
    $UptimeSeconds = [Math]::Max(0, ($ChildExited - $ChildStarted).TotalSeconds)
    if (Test-Path -LiteralPath $StopRequestPath -PathType Leaf) {
      [void](Write-RecoveryReceipt `
          -Status 'child_stopped_by_operator' `
          -ChildPid $ChildPid `
          -ChildExitCode $ObservedExitCode `
          -ChildStartedAt $ChildStarted.ToString('o') `
          -ChildExitedAt $ChildExited.ToString('o') `
          -ChildUptimeSeconds $UptimeSeconds `
          -RestartScheduled $false `
          -StoppedRendererPids @() `
          -StdoutPath $StdoutPath `
          -StderrPath $StderrPath)
      Write-SupervisorState -Status 'stopped_by_operator' -ChildPid $ChildPid -ChildAlive $false -Message 'Explicit operator stop ended the recovery lease; no restart was attempted.'
      break
    }

    $StoppedRendererPids = @(Stop-OwnedOrphanRenderer -Root $DataRoot -ExitedChildPid $ChildPid)
    Remove-StaleChildPid -Path $ChildPidPath -ExitedChildPid $ChildPid
    $Cutoff = [DateTimeOffset]::UtcNow.AddSeconds(-$RestartWindowSeconds)
    $RestartTimestamps = @($RestartTimestamps | Where-Object { $_ -ge $Cutoff })
    if ($RestartTimestamps.Count -ge $MaxRestarts) {
      [void](Write-RecoveryReceipt `
          -Status 'recovery_budget_exhausted' `
          -ChildPid $ChildPid `
          -ChildExitCode $ObservedExitCode `
          -ChildStartedAt $ChildStarted.ToString('o') `
          -ChildExitedAt $ChildExited.ToString('o') `
          -ChildUptimeSeconds $UptimeSeconds `
          -RestartScheduled $false `
          -StoppedRendererPids $StoppedRendererPids `
          -StdoutPath $StdoutPath `
          -StderrPath $StderrPath)
      Write-SupervisorState -Status 'recovery_budget_exhausted' -ChildPid $ChildPid -ChildAlive $false -Message 'Overlay recovery stopped after reaching the bounded restart budget.'
      $ExitCode = 1
      break
    }

    $RestartTimestamps += [DateTimeOffset]::UtcNow
    $RestartCount += 1
    [void](Write-RecoveryReceipt `
        -Status 'child_exited_restarting' `
        -ChildPid $ChildPid `
        -ChildExitCode $ObservedExitCode `
        -ChildStartedAt $ChildStarted.ToString('o') `
        -ChildExitedAt $ChildExited.ToString('o') `
        -ChildUptimeSeconds $UptimeSeconds `
        -RestartScheduled $true `
        -StoppedRendererPids $StoppedRendererPids `
        -StdoutPath $StdoutPath `
        -StderrPath $StderrPath)
    Write-SupervisorState -Status 'restart_scheduled' -ChildPid $ChildPid -ChildAlive $false -Message 'Overlay runtime child exited unexpectedly; bounded recovery is scheduled.'
    Start-Sleep -Seconds $BackoffSeconds
  }
} finally {
  if ((Get-PidValue -Path $SupervisorPidPath) -eq $PID) {
    Remove-Item -LiteralPath $SupervisorPidPath -Force -ErrorAction SilentlyContinue
  }
}

exit $ExitCode
