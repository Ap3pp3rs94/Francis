[CmdletBinding()]
param(
  [ValidateSet('Status', 'Foreground', 'Launch', 'Resident')]
  [string]$Mode = 'Status',

  [ValidateRange(0, 60)]
  [int]$RunSeconds = 0
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$modeName = $Mode.ToLowerInvariant()
$ServiceConfigPath = Join-Path (Join-Path (Join-Path (Join-Path $RepoRoot 'config') 'runtime') 'services') 'lens-host.json'
$ServiceConfigExists = Test-Path -LiteralPath $ServiceConfigPath -PathType Leaf
$ServiceName = 'Francis-LensHost'
$RuntimeBlockedReason = 'lens_host_persistent_supervision_prerequisites_pending'
if ($ServiceConfigExists) {
  try {
    $ServiceConfigPayload = Get-Content -LiteralPath $ServiceConfigPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    $ServiceNameProperty = $ServiceConfigPayload.PSObject.Properties['service_name']
    if ($null -ne $ServiceNameProperty -and -not [string]::IsNullOrWhiteSpace([string]$ServiceNameProperty.Value)) {
      $ServiceName = [string]$ServiceNameProperty.Value
    }
    $BlockedReasonProperty = $ServiceConfigPayload.PSObject.Properties['blocked_reason']
    if ($null -ne $BlockedReasonProperty -and -not [string]::IsNullOrWhiteSpace([string]$BlockedReasonProperty.Value)) {
      $RuntimeBlockedReason = [string]$BlockedReasonProperty.Value
    }
  } catch {
    $ServiceName = 'Francis-LensHost'
  }
}

function Get-DataRoot {
  $Configured = [string]$env:FRANCIS_DATA_DIR
  if (-not [string]::IsNullOrWhiteSpace($Configured)) {
    return $Configured
  }
  return (Join-Path $RepoRoot 'data')
}

function Write-JsonFile {
  param(
    [string]$Path,
    [object]$Payload
  )

  $Parent = Split-Path -Parent $Path
  if (-not [string]::IsNullOrWhiteSpace($Parent)) {
    New-Item -ItemType Directory -Force -Path $Parent | Out-Null
  }
  $FileName = [System.IO.Path]::GetFileName($Path)
  $TempPath = Join-Path $Parent ('.' + $FileName + '.' + [guid]::NewGuid().ToString('N') + '.tmp')
  try {
    $Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $TempPath -Encoding UTF8
    $Moved = $false
    for ($Attempt = 0; $Attempt -lt 20 -and -not $Moved; $Attempt += 1) {
      try {
        Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
        Move-Item -LiteralPath $TempPath -Destination $Path -Force -ErrorAction Stop
        $Moved = $true
      } catch {
        if ($Attempt -ge 19) {
          throw
        }
        Start-Sleep -Milliseconds 50
      }
    }
  } finally {
    Remove-Item -LiteralPath $TempPath -Force -ErrorAction SilentlyContinue
  }
}

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
    $VenvConfigPath = Join-Path $RepoRoot '.venv\pyvenv.cfg'
    try {
      $HomeLine = Get-Content -LiteralPath $VenvConfigPath -ErrorAction Stop |
        Where-Object { $_ -match '^\s*home\s*=' } |
        Select-Object -First 1
      if (-not [string]::IsNullOrWhiteSpace([string]$HomeLine)) {
        $BaseHome = ([string]$HomeLine -split '=', 2)[1].Trim()
        $BasePython = Join-Path $BaseHome 'python.exe'
        if (Test-Path -LiteralPath $BasePython -PathType Leaf) {
          return $BasePython
        }
      }
    } catch {
    }
    return ''
  }
  $UnixVenv = Join-Path $RepoRoot '.venv/bin/python'
  if (Test-Path -LiteralPath $UnixVenv -PathType Leaf) {
    return $UnixVenv
  }
  foreach ($CommandName in @('python3', 'python')) {
    $Python = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($null -ne $Python) {
      return [string]$Python.Source
    }
  }
  return ''
}

function Get-PythonSitePackagesPath {
  $WindowsSitePackages = Join-Path $RepoRoot '.venv\Lib\site-packages'
  if (Test-Path -LiteralPath $WindowsSitePackages -PathType Container) {
    return $WindowsSitePackages
  }
  $UnixLib = Join-Path $RepoRoot '.venv/lib'
  if (Test-Path -LiteralPath $UnixLib -PathType Container) {
    $SitePackages = Get-ChildItem -LiteralPath $UnixLib -Directory -ErrorAction SilentlyContinue |
      ForEach-Object { Join-Path $_.FullName 'site-packages' } |
      Where-Object { Test-Path -LiteralPath $_ -PathType Container } |
      Select-Object -First 1
    if (-not [string]::IsNullOrWhiteSpace([string]$SitePackages)) {
      return [string]$SitePackages
    }
  }
  return ''
}

function Quote-ProcessArgument {
  param([string]$Value)

  if ($null -eq $Value) {
    return '""'
  }
  return '"' + ($Value -replace '"', '\"') + '"'
}

function Quote-PowerShellString {
  param([string]$Value)

  if ($null -eq $Value) {
    return "''"
  }
  return "'" + ($Value -replace "'", "''") + "'"
}

function Read-JsonFile {
  param([string]$Path)

  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return $null
  }
  try {
    return Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
  } catch {
    return $null
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

function Test-SafeIdentifier {
  param([object]$Value)

  $Raw = [string]$Value
  $Cleaned = $Raw.Trim()
  return (
    -not [string]::IsNullOrWhiteSpace($Cleaned) -and
    $Raw -eq $Cleaned -and
    -not $Cleaned.Contains('/') -and
    -not $Cleaned.Contains('\') -and
    -not $Cleaned.Contains('..') -and
    $Cleaned.Length -le 180
  )
}

function Get-PerceptionWorkerHandoff {
  $ExecutionDir = Join-Path (Join-Path (Join-Path $DataRoot 'runtime') 'lens-perception') 'execution'
  $EnablementPath = Join-Path $ExecutionDir 'enablement.json'
  $Result = [ordered]@{
    status = 'not_enabled'
    ready = $false
    enablement_path = 'data/runtime/lens-perception/execution/enablement.json'
    enablement_receipt_id = ''
    approval_id = ''
    authority_receipt_id = ''
    sample_rate_hz = 0.0
    retention_seconds = 0.0
    max_frames = 0
    expires_ts = 0
    blockers = @('lens_perception_execution_enablement_missing')
  }
  if (-not (Test-Path -LiteralPath $EnablementPath -PathType Leaf)) {
    return [pscustomobject]$Result
  }

  $Enablement = Read-JsonFile -Path $EnablementPath
  if ($null -eq $Enablement) {
    $Result['status'] = 'blocked'
    $Result['blockers'] = @('lens_perception_execution_enablement_unreadable')
    return [pscustomobject]$Result
  }

  $Blockers = @()
  $Kind = [string](Get-PropertyValue -Payload $Enablement -Name 'kind' -Default '')
  $Status = [string](Get-PropertyValue -Payload $Enablement -Name 'status' -Default '')
  $Enabled = Get-PropertyValue -Payload $Enablement -Name 'enabled' -Default $null
  $Source = [string](Get-PropertyValue -Payload $Enablement -Name 'source' -Default '')
  $ExecutionMode = [string](Get-PropertyValue -Payload $Enablement -Name 'mode' -Default '')
  $WorkerModule = [string](Get-PropertyValue -Payload $Enablement -Name 'worker_module' -Default '')
  if (
    $Kind -ne 'lens.perception.desktop_capture_execution.enablement' -or
    $Status -ne 'enabled_for_host_consumption' -or
    ($Enabled -isnot [bool]) -or
    -not [bool]$Enabled
  ) {
    $Blockers += 'lens_perception_execution_enablement_invalid'
  }
  if ($Source -ne 'desktop_ring_buffer' -or $ExecutionMode -ne 'resident' -or $WorkerModule -ne 'francis.lens.perception_worker') {
    $Blockers += 'lens_perception_execution_enablement_scope_invalid'
  }

  $EnablementReceiptId = [string](Get-PropertyValue -Payload $Enablement -Name 'enablement_receipt_id' -Default '')
  $ApprovalId = [string](Get-PropertyValue -Payload $Enablement -Name 'approval_id' -Default '')
  $AuthorityReceiptId = [string](Get-PropertyValue -Payload $Enablement -Name 'authority_receipt_id' -Default '')
  if (
    -not (Test-SafeIdentifier -Value $EnablementReceiptId) -or
    -not (Test-SafeIdentifier -Value $ApprovalId) -or
    -not (Test-SafeIdentifier -Value $AuthorityReceiptId)
  ) {
    $Blockers += 'lens_perception_execution_enablement_identifiers_invalid'
  }

  $ExpiresTs = 0L
  try {
    $ExpiresTs = [long](Get-PropertyValue -Payload $Enablement -Name 'expires_ts' -Default 0)
  } catch {
    $ExpiresTs = 0L
  }
  if ($ExpiresTs -le [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()) {
    $Blockers += 'lens_perception_execution_enablement_expired'
  }

  foreach ($Field in @(
    'camera_capture_authority',
    'microphone_capture_authority',
    'keyboard_capture_authority',
    'user_mouse_capture_authority',
    'input_execution_authority',
    'memory_write'
  )) {
    $FieldValue = Get-PropertyValue -Payload $Enablement -Name $Field -Default $null
    if (($FieldValue -isnot [bool]) -or [bool]$FieldValue) {
      $Blockers += 'lens_perception_execution_enablement_overbroad'
      break
    }
  }

  $SampleRateHz = 0.0
  $RetentionSeconds = 0.0
  $MaxFrames = 0
  try { $SampleRateHz = [double](Get-PropertyValue -Payload $Enablement -Name 'sample_rate_hz' -Default 0.0) } catch { $SampleRateHz = 0.0 }
  try { $RetentionSeconds = [double](Get-PropertyValue -Payload $Enablement -Name 'retention_seconds' -Default 0.0) } catch { $RetentionSeconds = 0.0 }
  try { $MaxFrames = [int](Get-PropertyValue -Payload $Enablement -Name 'max_frames' -Default 0) } catch { $MaxFrames = 0 }
  if (
    [double]::IsNaN($SampleRateHz) -or [double]::IsInfinity($SampleRateHz) -or
    $SampleRateHz -lt 0.5 -or $SampleRateHz -gt 4.0 -or
    [double]::IsNaN($RetentionSeconds) -or [double]::IsInfinity($RetentionSeconds) -or
    $RetentionSeconds -lt 60.0 -or $RetentionSeconds -gt 120.0 -or
    $MaxFrames -lt 1 -or $MaxFrames -gt 1200
  ) {
    $Blockers += 'lens_perception_execution_enablement_limits_invalid'
  }

  if (Test-SafeIdentifier -Value $EnablementReceiptId) {
    $ReceiptPath = Join-Path (Join-Path $ExecutionDir 'receipts') ($EnablementReceiptId + '.json')
    $Receipt = Read-JsonFile -Path $ReceiptPath
    if ($null -eq $Receipt) {
      $Blockers += 'lens_perception_execution_enablement_receipt_missing'
    } else {
      $ReceiptKind = [string](Get-PropertyValue -Payload $Receipt -Name 'kind' -Default '')
      $ReceiptStatus = [string](Get-PropertyValue -Payload $Receipt -Name 'status' -Default '')
      $ReceiptId = [string](Get-PropertyValue -Payload $Receipt -Name 'receipt_id' -Default '')
      $ReceiptApprovalId = [string](Get-PropertyValue -Payload $Receipt -Name 'approval_id' -Default '')
      $ReceiptAuthorityId = [string](Get-PropertyValue -Payload $Receipt -Name 'authority_receipt_id' -Default '')
      $ReceiptSource = [string](Get-PropertyValue -Payload $Receipt -Name 'source' -Default '')
      $ReceiptMode = [string](Get-PropertyValue -Payload $Receipt -Name 'mode' -Default '')
      $ReceiptExpiresTs = 0L
      try { $ReceiptExpiresTs = [long](Get-PropertyValue -Payload $Receipt -Name 'expires_ts' -Default 0) } catch { $ReceiptExpiresTs = 0L }
      if ($ReceiptKind -ne 'lens.perception.desktop_capture_execution.enablement_receipt' -or $ReceiptStatus -ne 'enabled_for_host_consumption') {
        $Blockers += 'lens_perception_execution_enablement_receipt_invalid'
      }
      if (
        $ReceiptId -ne $EnablementReceiptId -or
        $ReceiptApprovalId -ne $ApprovalId -or
        $ReceiptAuthorityId -ne $AuthorityReceiptId -or
        $ReceiptSource -ne 'desktop_ring_buffer' -or
        $ReceiptMode -ne 'resident' -or
        $ReceiptExpiresTs -ne $ExpiresTs
      ) {
        $Blockers += 'lens_perception_execution_enablement_receipt_mismatch'
      }
      $Authorities = Get-PropertyValue -Payload $Receipt -Name 'authorities' -Default $null
      foreach ($Field in @(
        'camera_capture_authority',
        'microphone_capture_authority',
        'keyboard_capture_authority',
        'user_mouse_capture_authority',
        'input_execution_authority',
        'memory_write'
      )) {
        $FieldValue = Get-PropertyValue -Payload $Authorities -Name $Field -Default $null
        if (($FieldValue -isnot [bool]) -or [bool]$FieldValue) {
          $Blockers += 'lens_perception_execution_enablement_receipt_overbroad'
          break
        }
      }
      foreach ($Field in @('desktop_capture_authority', 'execution_authority', 'host_handoff_write_authority')) {
        $FieldValue = Get-PropertyValue -Payload $Authorities -Name $Field -Default $null
        if (($FieldValue -isnot [bool]) -or -not [bool]$FieldValue) {
          $Blockers += 'lens_perception_execution_enablement_receipt_authority_missing'
          break
        }
      }
    }
  }

  $Result['enablement_receipt_id'] = $EnablementReceiptId
  $Result['approval_id'] = $ApprovalId
  $Result['authority_receipt_id'] = $AuthorityReceiptId
  $Result['sample_rate_hz'] = $SampleRateHz
  $Result['retention_seconds'] = $RetentionSeconds
  $Result['max_frames'] = $MaxFrames
  $Result['expires_ts'] = $ExpiresTs
  $Result['blockers'] = @($Blockers | Select-Object -Unique)
  if ($Result['blockers'].Count -eq 0) {
    $Result['status'] = 'ready_for_host_consumption'
    $Result['ready'] = $true
  } else {
    $Result['status'] = 'blocked'
  }
  return [pscustomobject]$Result
}

function Update-PerceptionWorkerState {
  param([System.Collections.Specialized.OrderedDictionary]$RunningState)

  if ($null -ne $script:PerceptionWorkerProcess) {
    try {
      if (-not $script:PerceptionWorkerProcess.HasExited) {
        $RunningState['perception_worker']['status'] = 'running'
        $RunningState['perception_worker']['process_alive'] = $true
        return
      }
      $script:PerceptionWorkerProcess.WaitForExit()
      $script:PerceptionWorkerProcess.Refresh()
      $RunningState['perception_worker']['status'] = 'exited'
      $RunningState['perception_worker']['process_alive'] = $false
      $RunningState['perception_worker']['process_exit_code'] = [int]$script:PerceptionWorkerProcess.ExitCode
      $WorkerResult = Read-JsonFile -Path $script:PerceptionWorkerStdoutPath
      if ($null -ne $WorkerResult) {
        $RunningState['perception_worker']['result_status'] = [string](Get-PropertyValue -Payload $WorkerResult -Name 'status' -Default '')
        try {
          $RunningState['perception_worker']['exit_code'] = [int](Get-PropertyValue -Payload $WorkerResult -Name 'exit_code' -Default $null)
        } catch {
          $RunningState['perception_worker']['exit_code'] = $null
        }
      }
      $RunningState['perception_worker']['blockers'] = @('lens_perception_worker_exited_for_enablement')
      $script:PerceptionWorkerProcess = $null
    } catch {
      $RunningState['perception_worker']['status'] = 'unreadable'
      $RunningState['perception_worker']['process_alive'] = $false
      $RunningState['perception_worker']['blockers'] = @('lens_perception_worker_process_readback_failed')
      $script:PerceptionWorkerProcess = $null
    }
  }

  $Handoff = Get-PerceptionWorkerHandoff
  $RunningState['perception_worker']['enablement_status'] = [string]$Handoff.status
  $RunningState['perception_worker']['enablement_receipt_id'] = [string]$Handoff.enablement_receipt_id
  $RunningState['perception_worker']['approval_id'] = [string]$Handoff.approval_id
  $RunningState['perception_worker']['authority_receipt_id'] = [string]$Handoff.authority_receipt_id
  $RunningState['perception_worker']['expires_ts'] = [long]$Handoff.expires_ts
  if (-not [bool]$Handoff.ready) {
    if ($RunningState['perception_worker']['status'] -ne 'exited') {
      $RunningState['perception_worker']['status'] = [string]$Handoff.status
      $RunningState['perception_worker']['blockers'] = @($Handoff.blockers)
    }
    return
  }

  $EnablementReceiptId = [string]$Handoff.enablement_receipt_id
  if ($EnablementReceiptId -eq $script:PerceptionWorkerAttemptedReceiptId) {
    return
  }
  $script:PerceptionWorkerAttemptedReceiptId = $EnablementReceiptId

  $PythonPath = Get-PythonPath
  if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $RunningState['perception_worker']['status'] = 'blocked'
    $RunningState['perception_worker']['blockers'] = @('lens_perception_worker_python_missing')
    return
  }

  $PerceptionRuntimeDir = Join-Path (Join-Path $DataRoot 'runtime') 'lens-perception'
  New-Item -ItemType Directory -Force -Path $PerceptionRuntimeDir | Out-Null
  $StdoutPath = Join-Path $PerceptionRuntimeDir ('worker-' + $EnablementReceiptId + '-stdout.json')
  $StderrPath = Join-Path $PerceptionRuntimeDir ('worker-' + $EnablementReceiptId + '-stderr.txt')
  $Arguments = @(
    '-m',
    'francis.lens.perception_worker',
    '--authority-receipt-id',
    [string]$Handoff.authority_receipt_id,
    '--execution-approval-id',
    [string]$Handoff.approval_id,
    '--sample-rate-hz',
    ([double]$Handoff.sample_rate_hz).ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--retention-seconds',
    ([double]$Handoff.retention_seconds).ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--max-frames',
    ([int]$Handoff.max_frames).ToString([System.Globalization.CultureInfo]::InvariantCulture)
  )

  $PreviousRootExists = Test-Path Env:\FRANCIS_ROOT
  $PreviousDataExists = Test-Path Env:\FRANCIS_DATA_DIR
  $PreviousPythonPathExists = Test-Path Env:\PYTHONPATH
  $PreviousRoot = [string]$env:FRANCIS_ROOT
  $PreviousData = [string]$env:FRANCIS_DATA_DIR
  $PreviousPythonPath = [string]$env:PYTHONPATH
  try {
    $env:FRANCIS_ROOT = $RepoRoot
    $env:FRANCIS_DATA_DIR = $DataRoot
    $SourceRoot = Join-Path $RepoRoot 'src'
    $PythonPathEntries = @($SourceRoot)
    $SitePackagesPath = Get-PythonSitePackagesPath
    if (-not [string]::IsNullOrWhiteSpace($SitePackagesPath)) {
      $PythonPathEntries += $SitePackagesPath
    }
    if (-not [string]::IsNullOrWhiteSpace($PreviousPythonPath)) {
      $PythonPathEntries += $PreviousPythonPath
    }
    $env:PYTHONPATH = $PythonPathEntries -join [System.IO.Path]::PathSeparator
    $StartParameters = @{
      FilePath = $PythonPath
      ArgumentList = $Arguments
      WorkingDirectory = $RepoRoot
      PassThru = $true
      RedirectStandardOutput = $StdoutPath
      RedirectStandardError = $StderrPath
    }
    if ([System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) {
      $StartParameters['WindowStyle'] = 'Hidden'
    }
    $script:PerceptionWorkerProcess = Start-Process @StartParameters
    $script:PerceptionWorkerStdoutPath = $StdoutPath
    $LaunchedAt = (Get-Date).ToUniversalTime().ToString('o')
    $RunningState['perception_worker']['status'] = 'launched'
    $RunningState['perception_worker']['pid'] = [int]$script:PerceptionWorkerProcess.Id
    $RunningState['perception_worker']['process_alive'] = $true
    $RunningState['perception_worker']['started_at'] = $LaunchedAt
    $RunningState['perception_worker']['stdout_path'] = 'data/runtime/lens-perception/' + [System.IO.Path]::GetFileName($StdoutPath)
    $RunningState['perception_worker']['stderr_path'] = 'data/runtime/lens-perception/' + [System.IO.Path]::GetFileName($StderrPath)
    $RunningState['perception_worker']['blockers'] = @()
    $RunningState['governance']['local_process_launch_authority'] = $true
    $RunningState['governance']['perception_worker_launch_authority'] = $true
    $RunningState['governance']['mutation_authority_granted'] = $true
  } catch {
    $RunningState['perception_worker']['status'] = 'launch_failed'
    $RunningState['perception_worker']['process_alive'] = $false
    $RunningState['perception_worker']['blockers'] = @('lens_perception_worker_process_launch_failed')
    $script:PerceptionWorkerProcess = $null
  } finally {
    if ($PreviousRootExists) { $env:FRANCIS_ROOT = $PreviousRoot } else { Remove-Item Env:\FRANCIS_ROOT -ErrorAction SilentlyContinue }
    if ($PreviousDataExists) { $env:FRANCIS_DATA_DIR = $PreviousData } else { Remove-Item Env:\FRANCIS_DATA_DIR -ErrorAction SilentlyContinue }
    if ($PreviousPythonPathExists) { $env:PYTHONPATH = $PreviousPythonPath } else { Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue }
  }
}

function Stop-OwnedPerceptionWorker {
  param([System.Collections.Specialized.OrderedDictionary]$RunningState)

  if ($null -eq $script:PerceptionWorkerProcess) {
    return
  }
  try {
    if (-not $script:PerceptionWorkerProcess.HasExited) {
      Stop-Process -Id $script:PerceptionWorkerProcess.Id -Force -ErrorAction Stop
      $script:PerceptionWorkerProcess.WaitForExit(3000)
      $RunningState['perception_worker']['status'] = 'stopped_with_resident_host'
    } else {
      $RunningState['perception_worker']['status'] = 'exited'
    }
    $RunningState['perception_worker']['process_exit_code'] = [int]$script:PerceptionWorkerProcess.ExitCode
  } catch {
    $RunningState['perception_worker']['status'] = 'stop_failed'
    $RunningState['perception_worker']['blockers'] = @('lens_perception_worker_owned_process_stop_failed')
  }
  $RunningState['perception_worker']['process_alive'] = $false
  $script:PerceptionWorkerProcess = $null
}

function Wait-ForRuntimeState {
  param(
    [string]$StatePath,
    [string]$Status,
    [int]$TimeoutSeconds = 10
  )

  $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $Deadline) {
    $Payload = Read-JsonFile -Path $StatePath
    if ($null -ne $Payload -and [string](Get-PropertyValue -Payload $Payload -Name 'status' -Default '') -eq $Status) {
      return $Payload
    }
    Start-Sleep -Milliseconds 100
  }
  return (Read-JsonFile -Path $StatePath)
}

$DataRoot = Get-DataRoot
$RuntimeDir = Join-Path (Join-Path $DataRoot 'runtime') 'lens-host'
$ProcessStatePath = Join-Path $RuntimeDir 'status.json'
$PidPath = Join-Path $RuntimeDir 'lens-host.pid'
$script:PerceptionWorkerProcess = $null
$script:PerceptionWorkerAttemptedReceiptId = ''
$script:PerceptionWorkerStdoutPath = ''
$ProcessStateExists = Test-Path -LiteralPath $ProcessStatePath -PathType Leaf
$ProcessStateStatus = ''
$ProcessStateUpdatedAt = ''
$ProcessStateHeartbeatCount = 0
$ProcessStateLastHeartbeatAt = ''
$ProcessStatePerceptionWorker = [ordered]@{
  status = 'not_observed'
  pid = 0
  process_alive = $false
  enablement_status = 'unknown'
  enablement_receipt_id = ''
  approval_id = ''
  authority_receipt_id = ''
  blockers = @('lens_perception_worker_runtime_not_observed')
}
if ($ProcessStateExists) {
  try {
    $ProcessStatePayload = Get-Content -LiteralPath $ProcessStatePath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    $StatusProperty = $ProcessStatePayload.PSObject.Properties['status']
    if ($null -ne $StatusProperty) {
      $ProcessStateStatus = [string]$StatusProperty.Value
    }
    $UpdatedProperty = $ProcessStatePayload.PSObject.Properties['updated_at']
    if ($null -ne $UpdatedProperty) {
      $ProcessStateUpdatedAt = [string]$UpdatedProperty.Value
    }
    $HeartbeatProperty = $ProcessStatePayload.PSObject.Properties['heartbeat_count']
    if ($null -ne $HeartbeatProperty) {
      try {
        $ProcessStateHeartbeatCount = [int]$HeartbeatProperty.Value
      } catch {
        $ProcessStateHeartbeatCount = 0
      }
    }
    $LastHeartbeatProperty = $ProcessStatePayload.PSObject.Properties['last_heartbeat_at']
    if ($null -ne $LastHeartbeatProperty) {
      $ProcessStateLastHeartbeatAt = [string]$LastHeartbeatProperty.Value
    }
    $PerceptionWorkerProperty = $ProcessStatePayload.PSObject.Properties['perception_worker']
    if ($null -ne $PerceptionWorkerProperty -and $null -ne $PerceptionWorkerProperty.Value) {
      $ProcessStatePerceptionWorker = $PerceptionWorkerProperty.Value
    }
  } catch {
    $ProcessStateStatus = 'unreadable'
  }
}
$PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf
$PidValue = 0
if ($PidPresent) {
  try {
    $PidValue = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
  } catch {
    $PidValue = 0
  }
}
$ProcessAlive = $false
if ($PidValue -gt 0) {
  if ($ProcessStateStatus -eq 'foreground_stopped' -and -not $PidPresent) {
    $ProcessAlive = $false
  } elseif ($ProcessStateStatus -eq 'resident_stopped' -and -not $PidPresent) {
    $ProcessAlive = $false
  } else {
    try {
      Get-Process -Id $PidValue -ErrorAction Stop | Out-Null
      $ProcessAlive = $true
    } catch {
      $ProcessAlive = $false
    }
  }
}
$ForegroundSessionActive = $ProcessAlive -and $ProcessStateStatus -eq 'foreground_running'
$ResidentSessionActive = $ProcessAlive -and $ProcessStateStatus -eq 'resident_running'
$ProcessReadbackStatus = if ($ProcessAlive) { 'process_observed' } elseif ($PidPresent -or $ProcessStateExists) { 'state_present_process_not_running' } else { 'missing' }
$ProcessBlockedReason = if ($ProcessAlive) { 'resident_host_not_supervised' } else { 'resident_host_process_missing' }
$Blockers = @(
  'tray_host_missing',
  'global_hotkey_binding_missing',
  'overlay_window_missing',
  'summon_binding_missing'
)
if (-not $ProcessAlive) {
  $Blockers = @('resident_host_process_missing') + $Blockers
} elseif ($ResidentSessionActive) {
  $Blockers = @('resident_host_process_not_supervised', 'resident_supervision_disabled') + $Blockers
}
$Blockers = @($RuntimeBlockedReason) + $Blockers
if (-not $ServiceConfigExists) {
  $Blockers = @('lens_host_service_config_missing') + $Blockers
}

$WindowsServiceSupported = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)
$ServiceInstalled = $false
$ServiceStatus = if ($WindowsServiceSupported) { 'not_installed' } else { 'unsupported_platform' }
$ServiceStartType = ''
$ServiceState = ''
$ServicePathName = ''
$ServiceAccount = ''
$ServiceReadbackError = ''
if ($WindowsServiceSupported) {
  try {
    $Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($null -ne $Service) {
      $ServiceInstalled = $true
      $ServiceStatus = ([string]$Service.Status).ToLowerInvariant()
      $FilterServiceName = $ServiceName.Replace("'", "''")
      $CimService = $null
      try {
        $CimService = Get-CimInstance Win32_Service -Filter "Name='$FilterServiceName'" -ErrorAction SilentlyContinue
      } catch {
        $CimService = $null
      }
      if ($null -ne $CimService) {
        $ServiceStartType = [string]$CimService.StartMode
        $ServiceState = [string]$CimService.State
        $ServicePathName = [string]$CimService.PathName
        $ServiceAccount = [string]$CimService.StartName
      }
    }
  } catch {
    $ServiceStatus = 'unavailable'
    $ServiceReadbackError = [string]$_.Exception.Message
  }
}
$ServiceBlockedReason = if ($ServiceInstalled) { $RuntimeBlockedReason } elseif ($WindowsServiceSupported) { 'lens_host_service_not_installed' } else { 'windows_service_readback_unavailable' }

$payload = [ordered]@{
  ok = $true
  kind = 'lens.host.status_runner'
  status = 'status_only'
  mode = $modeName
  repo_root = $RepoRoot
  service_config_path = 'config/runtime/services/lens-host.json'
  service_config_exists = $ServiceConfigExists
  service_readback = [ordered]@{
    status = $ServiceStatus
    readback_ready = $true
    service_name = $ServiceName
    installed = $ServiceInstalled
    windows_service = $WindowsServiceSupported
    start_type = $ServiceStartType
    state = $ServiceState
    path_name = $ServicePathName
    account = $ServiceAccount
    error = $ServiceReadbackError
    install_supported = $false
    start_supported = $false
    stop_supported = $false
    restart_supported = $false
    install_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    blocked_reason = $ServiceBlockedReason
  }
  process_readback = [ordered]@{
    status = $ProcessReadbackStatus
    readback_ready = $true
    runtime_state_path = 'data/runtime/lens-host/status.json'
    state_exists = $ProcessStateExists
    state_status = $ProcessStateStatus
    state_updated_at = $ProcessStateUpdatedAt
    heartbeat_count = $ProcessStateHeartbeatCount
    last_heartbeat_at = $ProcessStateLastHeartbeatAt
    pid_path = 'data/runtime/lens-host/lens-host.pid'
    pid_present = $PidPresent
    pid = $PidValue
    process_alive = $ProcessAlive
    supervision_enabled = $false
    start_supported = $false
    stop_supported = $false
    restart_supported = $false
    supervision_authority = $false
    blocked_reason = $ProcessBlockedReason
    perception_worker = $ProcessStatePerceptionWorker
  }
  route = '/lens/host'
  manifest_route = '/lens/host/manifest'
  launch_supported = $false
  foreground_supported = $true
  foreground_session = $ForegroundSessionActive
  resident_supported = $true
  resident_session = $ResidentSessionActive
  resident_runtime_candidate = $ResidentSessionActive
  foreground_run_seconds = $RunSeconds
  resident = $ResidentSessionActive
  resident_claim_allowed = $false
  process_supervision = $false
  tray_presence = $false
  global_hotkey = $false
  always_on_top_overlay = $false
  overlay_window = $false
  command_palette_binding = $false
  summon_anywhere = $false
  blockers = $Blockers
  governance = [ordered]@{
    read_only_contract = $true
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = $false
    perception_worker_launch_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    runtime_state_write = $Mode -eq 'Foreground' -or $Mode -eq 'Resident'
    foreground_session_authority = $Mode -eq 'Foreground'
    resident_runtime_candidate = $Mode -eq 'Resident'
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
}

if ($Mode -eq 'Status') {
  $payload | ConvertTo-Json -Depth 8
  exit 0
}

if ($Mode -eq 'Resident') {
  $StartedAt = (Get-Date).ToUniversalTime().ToString('o')
  $RunningGovernance = [ordered]@{
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = $false
    perception_worker_launch_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    runtime_state_write = $true
    foreground_session_authority = $false
    resident_runtime_candidate = $true
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  $RunningState = [ordered]@{
    kind = 'lens.host.runtime_state'
    status = 'resident_running'
    mode = 'resident'
    pid = $PID
    process_alive = $true
    resident = $true
    resident_claim_allowed = $false
    service_managed = $false
    tray_presence = $false
    global_hotkey = $false
    overlay_window = $false
    summon_anywhere = $false
    started_at = $StartedAt
    updated_at = $StartedAt
    heartbeat_interval_ms = 500
    heartbeat_count = 0
    last_heartbeat_at = $StartedAt
    bounded_run_seconds = $RunSeconds
    perception_worker = [ordered]@{
      status = 'not_enabled'
      pid = 0
      process_alive = $false
      enablement_status = 'not_enabled'
      enablement_receipt_id = ''
      approval_id = ''
      authority_receipt_id = ''
      expires_ts = 0
      started_at = ''
      result_status = ''
      exit_code = $null
      process_exit_code = $null
      stdout_path = ''
      stderr_path = ''
      blockers = @('lens_perception_execution_enablement_missing')
    }
    governance = $RunningGovernance
  }
  New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
  Set-Content -LiteralPath $PidPath -Value ([string]$PID) -Encoding ASCII
  Write-JsonFile -Path $ProcessStatePath -Payload $RunningState

  $HeartbeatCount = 0
  $LastHeartbeatAt = $StartedAt
  try {
    $HeartbeatDeadline = if ($RunSeconds -gt 0) { (Get-Date).AddSeconds($RunSeconds) } else { $null }
    while ($null -eq $HeartbeatDeadline -or (Get-Date) -lt $HeartbeatDeadline) {
      Start-Sleep -Milliseconds 500
      $HeartbeatCount += 1
      $LastHeartbeatAt = (Get-Date).ToUniversalTime().ToString('o')
      $RunningState['updated_at'] = $LastHeartbeatAt
      $RunningState['heartbeat_count'] = $HeartbeatCount
      $RunningState['last_heartbeat_at'] = $LastHeartbeatAt
      Update-PerceptionWorkerState -RunningState $RunningState
      Write-JsonFile -Path $ProcessStatePath -Payload $RunningState
    }
  } finally {
    Stop-OwnedPerceptionWorker -RunningState $RunningState
    $StoppedAt = (Get-Date).ToUniversalTime().ToString('o')
    $StoppedState = [ordered]@{
      kind = 'lens.host.runtime_state'
      status = 'resident_stopped'
      mode = 'resident'
      pid = $PID
      process_alive = $false
      resident = $false
      resident_claim_allowed = $false
      service_managed = $false
      tray_presence = $false
      global_hotkey = $false
      overlay_window = $false
      summon_anywhere = $false
      started_at = $StartedAt
      updated_at = $StoppedAt
      heartbeat_interval_ms = 500
      heartbeat_count = $HeartbeatCount
      last_heartbeat_at = $LastHeartbeatAt
      bounded_run_seconds = $RunSeconds
      stop_reason = 'resident_runtime_candidate_stopped'
      perception_worker = $RunningState['perception_worker']
      governance = $RunningGovernance
    }
    Write-JsonFile -Path $ProcessStatePath -Payload $StoppedState
    Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
  }

  $payload.status = 'resident_completed'
  $payload.ok = $true
  $payload.process_readback.status = 'state_present_process_not_running'
  $payload.process_readback.state_exists = $true
  $payload.process_readback.state_status = 'resident_stopped'
  $payload.process_readback.state_updated_at = $StoppedAt
  $payload.process_readback.heartbeat_count = $HeartbeatCount
  $payload.process_readback.last_heartbeat_at = $LastHeartbeatAt
  $payload.process_readback.pid_present = $false
  $payload.process_readback.pid = 0
  $payload.process_readback.process_alive = $false
  $payload.process_readback.perception_worker = $RunningState['perception_worker']
  $payload.foreground_supported = $true
  $payload.foreground_session = $false
  $payload.resident_supported = $true
  $payload.resident_session = $false
  $payload.resident_runtime_candidate = $true
  $payload.resident = $false
  $payload.resident_claim_allowed = $false
  $payload.foreground_run_seconds = $RunSeconds
  $payload.governance.local_process_launch_authority = $RunningGovernance['local_process_launch_authority']
  $payload.governance.perception_worker_launch_authority = $RunningGovernance['perception_worker_launch_authority']
  $payload.governance.mutation_authority_granted = $RunningGovernance['mutation_authority_granted']
  $payload.message = 'Lens host resident runtime candidate completed; persistent service supervision, tray, summon, overlay, and resident claim remain blocked.'
  $payload | ConvertTo-Json -Depth 8
  exit 0
}

if ($Mode -eq 'Foreground') {
  $StartedAt = (Get-Date).ToUniversalTime().ToString('o')
  $RunningGovernance = [ordered]@{
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    runtime_state_write = $true
    foreground_session_authority = $true
    mutation_authority_granted = $false
  }
  $RunningState = [ordered]@{
    kind = 'lens.host.runtime_state'
    status = 'foreground_running'
    mode = 'foreground'
    pid = $PID
    process_alive = $true
    resident = $false
    service_managed = $false
    tray_presence = $false
    global_hotkey = $false
    overlay_window = $false
    summon_anywhere = $false
    started_at = $StartedAt
    updated_at = $StartedAt
    heartbeat_interval_ms = 500
    heartbeat_count = 0
    last_heartbeat_at = $StartedAt
    bounded_run_seconds = $RunSeconds
    governance = $RunningGovernance
  }
  New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
  Set-Content -LiteralPath $PidPath -Value ([string]$PID) -Encoding ASCII
  Write-JsonFile -Path $ProcessStatePath -Payload $RunningState

  $HeartbeatCount = 0
  $LastHeartbeatAt = $StartedAt
  if ($RunSeconds -gt 0) {
    $HeartbeatDeadline = (Get-Date).AddSeconds($RunSeconds)
    while ((Get-Date) -lt $HeartbeatDeadline) {
      Start-Sleep -Milliseconds 500
      $HeartbeatCount += 1
      $LastHeartbeatAt = (Get-Date).ToUniversalTime().ToString('o')
      $RunningState['updated_at'] = $LastHeartbeatAt
      $RunningState['heartbeat_count'] = $HeartbeatCount
      $RunningState['last_heartbeat_at'] = $LastHeartbeatAt
      Write-JsonFile -Path $ProcessStatePath -Payload $RunningState
    }
  }

  $StoppedAt = (Get-Date).ToUniversalTime().ToString('o')
  $StoppedState = [ordered]@{
    kind = 'lens.host.runtime_state'
    status = 'foreground_stopped'
    mode = 'foreground'
    pid = $PID
    process_alive = $false
    resident = $false
    service_managed = $false
    tray_presence = $false
    global_hotkey = $false
    overlay_window = $false
    summon_anywhere = $false
    started_at = $StartedAt
    updated_at = $StoppedAt
    heartbeat_interval_ms = 500
    heartbeat_count = $HeartbeatCount
    last_heartbeat_at = $LastHeartbeatAt
    bounded_run_seconds = $RunSeconds
    stop_reason = 'bounded_foreground_session_completed'
    governance = $RunningGovernance
  }
  Write-JsonFile -Path $ProcessStatePath -Payload $StoppedState
  Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue

  $payload.status = 'foreground_completed'
  $payload.ok = $true
  $payload.process_readback.status = 'state_present_process_not_running'
  $payload.process_readback.state_exists = $true
  $payload.process_readback.state_status = 'foreground_stopped'
  $payload.process_readback.state_updated_at = $StoppedAt
  $payload.process_readback.heartbeat_count = $HeartbeatCount
  $payload.process_readback.last_heartbeat_at = $LastHeartbeatAt
  $payload.process_readback.pid_present = $false
  $payload.process_readback.pid = 0
  $payload.process_readback.process_alive = $false
  $payload.foreground_supported = $true
  $payload.foreground_session = $false
  $payload.foreground_run_seconds = $RunSeconds
  $payload.message = 'Lens host foreground status session completed; resident service, tray, summon, and overlay remain blocked.'
  $payload | ConvertTo-Json -Depth 8
  exit 0
}

$LaunchRunSeconds = if ($RunSeconds -gt 0) { $RunSeconds } else { 10 }
if ($Mode -eq 'Launch') {
  $PowerShellPath = Get-PowerShellPath
  $HostScriptPath = [string]$MyInvocation.MyCommand.Path
  $LaunchStdoutPath = Join-Path $RuntimeDir 'launch-stdout.json'
  $LaunchStderrPath = Join-Path $RuntimeDir 'launch-stderr.txt'
  New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
  Remove-Item -LiteralPath $LaunchStdoutPath -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $LaunchStderrPath -Force -ErrorAction SilentlyContinue

  $LaunchStarted = $false
  $LaunchPid = 0
  $RunningState = $null
  if (-not [string]::IsNullOrWhiteSpace($PowerShellPath)) {
    $ChildCommand = (
      '$env:FRANCIS_DATA_DIR = ' +
      (Quote-PowerShellString -Value $DataRoot) +
      '; & ' +
      (Quote-PowerShellString -Value $HostScriptPath) +
      ' -Mode Foreground -RunSeconds ' +
      [string]$LaunchRunSeconds +
      ' > ' +
      (Quote-PowerShellString -Value $LaunchStdoutPath) +
      ' 2> ' +
      (Quote-PowerShellString -Value $LaunchStderrPath)
    )
    $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $StartInfo.FileName = $PowerShellPath
    $StartInfo.Arguments = '-NoProfile -ExecutionPolicy Bypass -Command ' + (Quote-ProcessArgument -Value $ChildCommand)
    $StartInfo.WorkingDirectory = $RepoRoot
    $StartInfo.UseShellExecute = $false
    $StartInfo.CreateNoWindow = $true
    $StartInfo.RedirectStandardOutput = $false
    $StartInfo.RedirectStandardError = $false

    $LaunchProcess = [System.Diagnostics.Process]::new()
    $LaunchProcess.StartInfo = $StartInfo
    $LaunchStarted = $LaunchProcess.Start()
    if ($LaunchStarted) {
      $LaunchPid = [int]$LaunchProcess.Id
      $LaunchObservationTimeout = [Math]::Max(15, $LaunchRunSeconds + 15)
      $RunningState = Wait-ForRuntimeState -StatePath $ProcessStatePath -Status 'foreground_running' -TimeoutSeconds $LaunchObservationTimeout
    }
  }

  $ObservedPid = [int](Get-PropertyValue -Payload $RunningState -Name 'pid' -Default 0)
  $LaunchObserved = (
    $LaunchStarted -and
    [string](Get-PropertyValue -Payload $RunningState -Name 'status' -Default '') -eq 'foreground_running' -and
    [bool](Get-PropertyValue -Payload $RunningState -Name 'process_alive' -Default $false) -and
    $ObservedPid -gt 0
  )
  $ObservedAt = (Get-Date).ToUniversalTime().ToString('o')

  $payload.ok = $LaunchObserved
  $payload.status = if ($LaunchObserved) { 'launch_started' } else { 'launch_unverified' }
  $payload.mode = 'launch'
  $payload.launch_supported = $true
  $payload.launch_authority = $false
  $payload.diagnostic_launch_authority = $LaunchObserved
  $payload.foreground_supported = $true
  $payload.foreground_session = $LaunchObserved
  $payload.foreground_run_seconds = $LaunchRunSeconds
  $payload.process_readback.status = if ($LaunchObserved) { 'process_observed' } else { 'missing' }
  $payload.process_readback.state_exists = $null -ne $RunningState
  $payload.process_readback.state_status = [string](Get-PropertyValue -Payload $RunningState -Name 'status' -Default '')
  $payload.process_readback.state_updated_at = [string](Get-PropertyValue -Payload $RunningState -Name 'updated_at' -Default $ObservedAt)
  $payload.process_readback.heartbeat_count = [int](Get-PropertyValue -Payload $RunningState -Name 'heartbeat_count' -Default 0)
  $payload.process_readback.last_heartbeat_at = [string](Get-PropertyValue -Payload $RunningState -Name 'last_heartbeat_at' -Default '')
  $payload.process_readback.pid_present = Test-Path -LiteralPath $PidPath -PathType Leaf
  $payload.process_readback.pid = $ObservedPid
  $payload.process_readback.process_alive = $LaunchObserved
  $payload.process_readback.blocked_reason = if ($LaunchObserved) { 'resident_host_not_supervised' } else { 'resident_host_process_missing' }
  $payload.blockers = if ($LaunchObserved) {
    @(
      $RuntimeBlockedReason,
      'resident_host_process_not_supervised',
      'tray_host_missing',
      'global_hotkey_binding_missing',
      'overlay_window_missing',
      'summon_binding_missing'
    )
  } else {
    $Blockers
  }
  $payload.launch = [ordered]@{
    status = if ($LaunchObserved) { 'started_observed' } else { 'not_observed' }
    launcher_pid = $LaunchPid
    observed_pid = $ObservedPid
    run_seconds = $LaunchRunSeconds
    runtime_state_path = 'data/runtime/lens-host/status.json'
    pid_path = 'data/runtime/lens-host/lens-host.pid'
    stdout_path = 'data/runtime/lens-host/launch-stdout.json'
    stderr_path = 'data/runtime/lens-host/launch-stderr.txt'
    observed_at = $ObservedAt
    stop_mode = 'bounded_self_stop'
  }
  $payload.governance.diagnostic_only = $true
  $payload.governance.bounded_process_launch = $true
  $payload.governance.temporary_runtime_state_write = $true
  $payload.governance.product_execution_authority = $false
  $payload.governance.local_process_launch_authority = $LaunchObserved
  $payload.governance.api_local_process_launch_authority = $false
  $payload.governance.foreground_session_authority = $true
  $payload.governance.mutation_authority_granted = $false
  $payload.message = if ($LaunchObserved) {
    'Bounded Lens host foreground process was launched and observed; it self-stops after the requested run window and does not provide service, tray, summon, or overlay runtime.'
  } else {
    'Bounded Lens host launch could not be observed.'
  }
  $payload | ConvertTo-Json -Depth 8
  if ($LaunchObserved) {
    exit 0
  }
  exit 1
}

$payload.ok = $false
$payload.status = 'refused'
$payload.error = 'lens_host_runtime_not_implemented'
$payload.message = 'Lens host runtime mutation is not authorized by this runner; status, bounded foreground, and bounded resident candidate modes are separate governed paths.'
$payload | ConvertTo-Json -Depth 8
exit 2
