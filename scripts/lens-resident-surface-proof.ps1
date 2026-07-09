[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(2, 60)]
  [int]$ForegroundRunSeconds = 15,

  [ValidateRange(5, 120)]
  [int]$LiveOperatorStartupTimeoutSeconds = 60,

  [ValidateRange(5, 120)]
  [int]$ResidentSurfaceReadbackTimeoutSeconds = 30,

  [string]$DataDir = ''
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

function Get-FreeTcpPort {
  $Address = [System.Net.IPAddress]::Parse('127.0.0.1')
  $Listener = [System.Net.Sockets.TcpListener]::new($Address, 0)
  try {
    $Listener.Start()
    return [int]$Listener.LocalEndpoint.Port
  } finally {
    $Listener.Stop()
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

function Wait-ForForegroundPid {
  param(
    [string]$PidPath,
    [int]$TimeoutSeconds = 10
  )

  $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $Latest = [ordered]@{
    pid_present = $false
    pid = 0
    process_alive = $false
  }
  while ((Get-Date) -lt $Deadline) {
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
      try {
        Get-Process -Id $PidValue -ErrorAction Stop | Out-Null
        $ProcessAlive = $true
      } catch {
        $ProcessAlive = $false
      }
    }
    $Latest = [ordered]@{
      pid_present = $PidPresent
      pid = $PidValue
      process_alive = $ProcessAlive
    }
    if ($PidPresent -and $PidValue -gt 0 -and $ProcessAlive) {
      return $Latest
    }
    Start-Sleep -Milliseconds 100
  }
  return $Latest
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

function Invoke-HttpJson {
  param(
    [string]$Uri,
    [int]$TimeoutSeconds = 10
  )

  try {
    $Response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -Method Get -TimeoutSec $TimeoutSeconds
    $Payload = $Response.Content | ConvertFrom-Json -ErrorAction Stop
    return [ordered]@{
      ok = $true
      status_code = [int]$Response.StatusCode
      payload = $Payload
      error = ''
    }
  } catch {
    return [ordered]@{
      ok = $false
      status_code = 0
      payload = $null
      error = [string]$_.Exception.Message
    }
  }
}

function Wait-ForResidentSurfaceReadback {
  param(
    [System.Diagnostics.Process]$Process,
    [string]$Uri,
    [int]$TimeoutSeconds
  )

  $HttpRequestTimeoutSeconds = [Math]::Min(15, [Math]::Max(5, $TimeoutSeconds))
  $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $LastResult = [ordered]@{
    ok = $false
    status_code = 0
    payload = $null
    error = 'resident_surface_readback_timeout'
  }
  while ((Get-Date) -lt $Deadline) {
    if ($null -ne $Process -and $Process.HasExited) {
      return [ordered]@{
        ok = $false
        status_code = 0
        payload = $null
        error = 'api_process_exited_before_resident_surface_readback'
      }
    }
    $LastResult = Invoke-HttpJson -Uri $Uri -TimeoutSeconds $HttpRequestTimeoutSeconds
    $Payload = Get-PropertyValue -Payload $LastResult -Name 'payload'
    if (
      [bool](Get-PropertyValue -Payload $LastResult -Name 'ok' -Default $false) -and
      [string](Get-PropertyValue -Payload $Payload -Name 'kind' -Default '') -eq 'lens.resident_surface.readback'
    ) {
      return $LastResult
    }
    Start-Sleep -Milliseconds 250
  }

  return [ordered]@{
    ok = $false
    status_code = 0
    payload = $null
    error = 'resident_surface_readback_timeout'
    last_error = [string](Get-PropertyValue -Payload $LastResult -Name 'error' -Default '')
  }
}

function Invoke-ResidentSurfaceRouteProcessReadback {
  param(
    [string]$PythonPath,
    [string]$DataDir = '',
    [string]$StdoutPath,
    [string]$StderrPath,
    [int]$TimeoutSeconds
  )

  $PythonCode = @'
import json
from francis.api.routes.lens import resident_surface

payload = resident_surface(limit=5)
print(json.dumps(payload, default=str))
'@
  $ReadbackScriptPath = Join-Path (Split-Path -Parent $StdoutPath) 'resident-surface-readback.py'
  Set-Content -LiteralPath $ReadbackScriptPath -Value $PythonCode -Encoding UTF8
  $Process = $null
  $StdoutTask = $null
  $StderrTask = $null
  $Stdout = ''
  $Stderr = ''
  $ExitCode = $null
  try {
    $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $StartInfo.FileName = $PythonPath
    $StartInfo.Arguments = "`"$ReadbackScriptPath`""
    $StartInfo.WorkingDirectory = $RepoRoot
    $StartInfo.UseShellExecute = $false
    $StartInfo.CreateNoWindow = $true
    $StartInfo.RedirectStandardOutput = $true
    $StartInfo.RedirectStandardError = $true
    $SrcPath = Join-Path $RepoRoot 'src'
    $PreviousPythonPath = [string]$env:PYTHONPATH
    if ([string]::IsNullOrWhiteSpace($PreviousPythonPath)) {
      $StartInfo.EnvironmentVariables['PYTHONPATH'] = $SrcPath
    } else {
      $StartInfo.EnvironmentVariables['PYTHONPATH'] = "$SrcPath$([System.IO.Path]::PathSeparator)$PreviousPythonPath"
    }
    if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
      $StartInfo.EnvironmentVariables['FRANCIS_DATA_DIR'] = $DataDir
    }
    $PreviousPythonWarnings = [string]$env:PYTHONWARNINGS
    if ([string]::IsNullOrWhiteSpace($PreviousPythonWarnings)) {
      $StartInfo.EnvironmentVariables['PYTHONWARNINGS'] = 'ignore::DeprecationWarning'
    } else {
      $StartInfo.EnvironmentVariables['PYTHONWARNINGS'] = "ignore::DeprecationWarning,$PreviousPythonWarnings"
    }

    $Process = [System.Diagnostics.Process]::new()
    $Process.StartInfo = $StartInfo
    if (-not $Process.Start()) {
      return [ordered]@{
        ok = $false
        status_code = 0
        payload = $null
        error = 'resident_surface_route_process_not_started'
      }
    }
    $StdoutTask = $Process.StandardOutput.ReadToEndAsync()
    $StderrTask = $Process.StandardError.ReadToEndAsync()
    $Completed = $Process.WaitForExit([Math]::Max(1, $TimeoutSeconds) * 1000)
    if (-not $Completed) {
      try {
        $Process.Kill()
      } catch {
      }
      $Process.WaitForExit(5000) | Out-Null
      return [ordered]@{
        ok = $false
        status_code = 0
        payload = $null
        error = 'resident_surface_route_process_timeout'
        readback_transport = 'direct_route_process'
      }
    }
    if ($null -ne $StdoutTask -and $StdoutTask.Wait(5000)) {
      $Stdout = $StdoutTask.Result
    }
    if ($null -ne $StderrTask -and $StderrTask.Wait(5000)) {
      $Stderr = $StderrTask.Result
    }
    $ExitCode = $Process.ExitCode
  } finally {
    Set-Content -LiteralPath $StdoutPath -Value $Stdout -Encoding UTF8 -ErrorAction SilentlyContinue
    Set-Content -LiteralPath $StderrPath -Value $Stderr -Encoding UTF8 -ErrorAction SilentlyContinue
  }

  $Payload = $null
  try {
    $Payload = $Stdout | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $Payload = $null
  }
  $PayloadKind = [string](Get-PropertyValue -Payload $Payload -Name 'kind' -Default '')
  $Succeeded = ($ExitCode -eq 0 -and $PayloadKind -eq 'lens.resident_surface.readback')
  return [ordered]@{
    ok = $Succeeded
    status_code = if ($Succeeded) { 200 } else { 0 }
    payload = $Payload
    error = if ($Succeeded) { '' } else { 'resident_surface_route_process_failed' }
    readback_transport = 'direct_route_process'
    process_exit_code = $ExitCode
  }
}

function Invoke-ResidentSurfaceReadback {
  param(
    [string]$DataDir = '',
    [int]$TimeoutSeconds = $ResidentSurfaceReadbackTimeoutSeconds
  )

  $PythonPath = Get-PythonPath
  if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    return [ordered]@{
      ok = $false
      status_code = 0
      payload = $null
      error = 'python_unavailable'
    }
  }

  $ReadbackRuntimeRoot = if ([string]::IsNullOrWhiteSpace($DataDir)) {
    Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-resident-surface-readback\" + [guid]::NewGuid().ToString('N'))
  } else {
    Join-Path $DataDir 'runtime\lens-resident-surface-readback'
  }
  New-Item -ItemType Directory -Force -Path $ReadbackRuntimeRoot | Out-Null

  $Port = Get-FreeTcpPort
  $BaseUrl = "http://127.0.0.1:$Port"
  $ReadbackUri = "$BaseUrl/lens/resident-surface?limit=5"
  $ApiStdoutPath = Join-Path $ReadbackRuntimeRoot 'api-stdout.log'
  $ApiStderrPath = Join-Path $ReadbackRuntimeRoot 'api-stderr.log'
  $DirectResult = Invoke-ResidentSurfaceRouteProcessReadback -PythonPath $PythonPath -DataDir $DataDir -StdoutPath $ApiStdoutPath -StderrPath $ApiStderrPath -TimeoutSeconds $TimeoutSeconds
  $DirectResult['base_url'] = ''
  $DirectResult['route'] = '/lens/resident-surface?limit=5'
  $DirectResult['timeout_seconds'] = $TimeoutSeconds
  $DirectResult['api_pid'] = 0
  $DirectResult['api_exit_code'] = Get-PropertyValue -Payload $DirectResult -Name 'process_exit_code'
  $DirectResult['api_stdout_path'] = $ApiStdoutPath
  $DirectResult['api_stderr_path'] = $ApiStderrPath
  return $DirectResult

  $ApiProcess = $null
  $StdoutTask = $null
  $StderrTask = $null
  $ApiStdout = ''
  $ApiStderr = ''
  $ApiExitCode = $null
  $Result = [ordered]@{
    ok = $false
    status_code = 0
    payload = $null
    error = 'resident_surface_readback_timeout'
  }
  try {
    $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $StartInfo.FileName = $PythonPath
    $StartInfo.Arguments = "-m francis api --host 127.0.0.1 --port $Port"
    $StartInfo.WorkingDirectory = $RepoRoot
    $StartInfo.UseShellExecute = $false
    $StartInfo.CreateNoWindow = $true
    $StartInfo.RedirectStandardOutput = $true
    $StartInfo.RedirectStandardError = $true
    $SrcPath = Join-Path $RepoRoot 'src'
    $PreviousPythonPath = [string]$env:PYTHONPATH
    if ([string]::IsNullOrWhiteSpace($PreviousPythonPath)) {
      $StartInfo.EnvironmentVariables['PYTHONPATH'] = $SrcPath
    } else {
      $StartInfo.EnvironmentVariables['PYTHONPATH'] = "$SrcPath$([System.IO.Path]::PathSeparator)$PreviousPythonPath"
    }
    if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
      $StartInfo.EnvironmentVariables['FRANCIS_DATA_DIR'] = $DataDir
    }
    $PreviousPythonWarnings = [string]$env:PYTHONWARNINGS
    if ([string]::IsNullOrWhiteSpace($PreviousPythonWarnings)) {
      $StartInfo.EnvironmentVariables['PYTHONWARNINGS'] = 'ignore::DeprecationWarning'
    } else {
      $StartInfo.EnvironmentVariables['PYTHONWARNINGS'] = "ignore::DeprecationWarning,$PreviousPythonWarnings"
    }

    $ApiProcess = [System.Diagnostics.Process]::new()
    $ApiProcess.StartInfo = $StartInfo
    $Started = $ApiProcess.Start()
    if (-not $Started) {
      return [ordered]@{
        ok = $false
        status_code = 0
        payload = $null
        error = 'resident_surface_readback_not_started'
        timeout_seconds = $TimeoutSeconds
      }
    }
    $StdoutTask = $ApiProcess.StandardOutput.ReadToEndAsync()
    $StderrTask = $ApiProcess.StandardError.ReadToEndAsync()
    $Result = Wait-ForResidentSurfaceReadback -Process $ApiProcess -Uri $ReadbackUri -TimeoutSeconds $TimeoutSeconds
  } finally {
    if ($null -ne $ApiProcess) {
      if (-not $ApiProcess.HasExited) {
        try {
          $ApiProcess.Kill()
        } catch {
        }
        $ApiProcess.WaitForExit(5000) | Out-Null
      }
      try {
        $ApiExitCode = $ApiProcess.ExitCode
      } catch {
        $ApiExitCode = $null
      }
      try {
        if ($null -ne $StdoutTask -and $StdoutTask.Wait(5000)) {
          $ApiStdout = $StdoutTask.Result
        }
      } catch {
        $ApiStdout = ''
      }
      try {
        if ($null -ne $StderrTask -and $StderrTask.Wait(5000)) {
          $ApiStderr = $StderrTask.Result
        }
      } catch {
        $ApiStderr = ''
      }
      Set-Content -LiteralPath $ApiStdoutPath -Value $ApiStdout -Encoding UTF8 -ErrorAction SilentlyContinue
      Set-Content -LiteralPath $ApiStderrPath -Value $ApiStderr -Encoding UTF8 -ErrorAction SilentlyContinue
    }
  }

  $Result['base_url'] = $BaseUrl
  $Result['route'] = '/lens/resident-surface?limit=5'
  $Result['timeout_seconds'] = $TimeoutSeconds
  $Result['api_pid'] = if ($null -ne $ApiProcess) { [int]$ApiProcess.Id } else { 0 }
  $Result['api_exit_code'] = $ApiExitCode
  $Result['api_stdout_path'] = $ApiStdoutPath
  $Result['api_stderr_path'] = $ApiStderrPath
  if (-not [bool](Get-PropertyValue -Payload $Result -Name 'ok' -Default $false) -and [string]::IsNullOrWhiteSpace([string](Get-PropertyValue -Payload $Result -Name 'error' -Default ''))) {
    $Result['error'] = 'resident_surface_readback_timeout'
  }
  return $Result
}

function Test-ForegroundSurfaceReadbackObserved {
  param([object]$SurfaceReadback)

  $SurfacePayload = Get-PropertyValue -Payload $SurfaceReadback -Name 'payload'
  $Runtime = Get-PropertyValue -Payload $SurfacePayload -Name 'resident_surface_runtime'
  $RuntimeBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Runtime -Name 'blockers' -Default @())

  return (
    [bool](Get-PropertyValue -Payload $SurfaceReadback -Name 'ok' -Default $false) -and
    [int](Get-PropertyValue -Payload $SurfaceReadback -Name 'status_code' -Default 0) -eq 200 -and
    [string](Get-PropertyValue -Payload $SurfacePayload -Name 'kind' -Default '') -eq 'lens.resident_surface.readback' -and
    [string](Get-PropertyValue -Payload $Runtime -Name 'status' -Default '') -eq 'foreground_runtime_observed' -and
    [bool](Get-PropertyValue -Payload $Runtime -Name 'foreground_runtime_observed' -Default $false) -and
    ($RuntimeBlockers -contains 'resident_surface_runtime_not_supervised') -and
    ($RuntimeBlockers -contains 'resident_surface_not_resident') -and
    -not ($RuntimeBlockers -contains 'resident_surface_runtime_missing') -and
    -not [bool](Get-PropertyValue -Payload $SurfacePayload -Name 'resident_surface_ready' -Default $true) -and
    -not [bool](Get-PropertyValue -Payload $SurfacePayload -Name 'resident_claim_allowed' -Default $true)
  )
}

function Test-ResidentSurfaceReadbackObserved {
  param([object]$SurfaceReadback)

  $SurfacePayload = Get-PropertyValue -Payload $SurfaceReadback -Name 'payload'
  $Runtime = Get-PropertyValue -Payload $SurfacePayload -Name 'resident_surface_runtime'
  $RuntimeBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Runtime -Name 'blockers' -Default @())

  return (
    [bool](Get-PropertyValue -Payload $SurfaceReadback -Name 'ok' -Default $false) -and
    [int](Get-PropertyValue -Payload $SurfaceReadback -Name 'status_code' -Default 0) -eq 200 -and
    [string](Get-PropertyValue -Payload $SurfacePayload -Name 'kind' -Default '') -eq 'lens.resident_surface.readback' -and
    [string](Get-PropertyValue -Payload $Runtime -Name 'status' -Default '') -eq 'resident_runtime_observed' -and
    [bool](Get-PropertyValue -Payload $Runtime -Name 'resident_runtime_observed' -Default $false) -and
    [bool](Get-PropertyValue -Payload $Runtime -Name 'resident_supervised_runtime' -Default $false) -and
    [bool](Get-PropertyValue -Payload $Runtime -Name 'runtime_ready' -Default $false) -and
    [bool](Get-PropertyValue -Payload $SurfacePayload -Name 'resident_surface_ready' -Default $false) -and
    -not ($RuntimeBlockers -contains 'resident_surface_runtime_missing') -and
    -not ($RuntimeBlockers -contains 'resident_surface_runtime_not_supervised') -and
    -not ($RuntimeBlockers -contains 'resident_surface_not_resident')
  )
}

function Invoke-ForegroundResidentSurfaceReadback {
  param(
    [string]$PowerShellPath,
    [int]$RunSeconds,
    [int]$ReadbackTimeoutSeconds = $ResidentSurfaceReadbackTimeoutSeconds
  )

  $HostScriptPath = Join-Path $PSScriptRoot 'lens-host.ps1'
  $HostScriptExists = Test-Path -LiteralPath $HostScriptPath -PathType Leaf
  if ([string]::IsNullOrWhiteSpace($PowerShellPath) -or -not $HostScriptExists) {
    return [ordered]@{
      ok = $false
      error = 'host_foreground_runner_unavailable'
      payload = $null
      runtime = $null
      runtime_blockers = @('resident_surface_runtime_missing')
    }
  }

  $ProofDataRoot = [System.IO.Path]::GetFullPath(
    (Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-resident-surface-runtime\" + [guid]::NewGuid().ToString('N') + "\data"))
  )
  $RuntimeDir = Join-Path $ProofDataRoot 'runtime\lens-host'
  $StatePath = Join-Path $RuntimeDir 'status.json'
  $PidPath = Join-Path $RuntimeDir 'lens-host.pid'
  $ForegroundOutputPath = Join-Path $RuntimeDir 'foreground-output.json'
  $ForegroundErrorPath = Join-Path $RuntimeDir 'foreground-error.txt'

  $ProofStarted = $false
  $RunningState = $null
  $RunningPid = $null
  $SurfaceReadback = $null
  $FinalPayload = $null
  $FinalState = $null
  $ForegroundExitCode = -1
  $ForegroundStdout = ''
  $ForegroundStderr = ''
  $ForegroundProcess = $null

  New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
  Remove-Item -LiteralPath $ForegroundOutputPath -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $ForegroundErrorPath -Force -ErrorAction SilentlyContinue

  try {
    $ChildCommand = (
      '$env:FRANCIS_DATA_DIR = ' +
      (Quote-PowerShellString -Value $ProofDataRoot) +
      '; & ' +
      (Quote-PowerShellString -Value $HostScriptPath) +
      ' -Mode Foreground -RunSeconds ' +
      [string]$RunSeconds +
      ' > ' +
      (Quote-PowerShellString -Value $ForegroundOutputPath) +
      ' 2> ' +
      (Quote-PowerShellString -Value $ForegroundErrorPath)
    )
    $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $StartInfo.FileName = $PowerShellPath
    $StartInfo.Arguments = '-NoProfile -ExecutionPolicy Bypass -Command ' + (Quote-ProcessArgument -Value $ChildCommand)
    $StartInfo.WorkingDirectory = $RepoRoot
    $StartInfo.UseShellExecute = $false
    $StartInfo.CreateNoWindow = $true
    $StartInfo.RedirectStandardOutput = $false
    $StartInfo.RedirectStandardError = $false

    $ForegroundProcess = [System.Diagnostics.Process]::new()
    $ForegroundProcess.StartInfo = $StartInfo
    $ProofStarted = $ForegroundProcess.Start()

    $RunningState = Wait-ForRuntimeState -StatePath $StatePath -Status 'foreground_running' -TimeoutSeconds 20
    $RunningPid = Wait-ForForegroundPid -PidPath $PidPath -TimeoutSeconds 20
    $ReadbackDeadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $ReadbackDeadline) {
      $SurfaceReadback = Invoke-ResidentSurfaceReadback -DataDir $ProofDataRoot -TimeoutSeconds $ReadbackTimeoutSeconds
      if (Test-ForegroundSurfaceReadbackObserved -SurfaceReadback $SurfaceReadback) {
        break
      }
      Start-Sleep -Milliseconds 250
    }

    $WaitTimeoutMs = [int](($RunSeconds + 30) * 1000)
    $Completed = $ForegroundProcess.WaitForExit($WaitTimeoutMs)
    if (-not $Completed) {
      try {
        $ForegroundProcess.Kill()
      } catch {
      }
      $ForegroundProcess.WaitForExit(5000) | Out-Null
    }
    $ForegroundExitCode = $ForegroundProcess.ExitCode
  } finally {
    if ($null -ne $ForegroundProcess -and -not $ForegroundProcess.HasExited) {
      try {
        $ForegroundProcess.Kill()
      } catch {
      }
      $ForegroundProcess.WaitForExit(5000) | Out-Null
    }
  }

  if (Test-Path -LiteralPath $ForegroundOutputPath -PathType Leaf) {
    $ForegroundStdout = Get-Content -LiteralPath $ForegroundOutputPath -Raw -ErrorAction SilentlyContinue
  }
  if (Test-Path -LiteralPath $ForegroundErrorPath -PathType Leaf) {
    $ForegroundStderr = Get-Content -LiteralPath $ForegroundErrorPath -Raw -ErrorAction SilentlyContinue
  }
  try {
    $FinalPayload = $ForegroundStdout | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $FinalPayload = $null
  }
  $FinalState = Read-JsonFile -Path $StatePath

  $SurfacePayload = Get-PropertyValue -Payload $SurfaceReadback -Name 'payload'
  $Runtime = Get-PropertyValue -Payload $SurfacePayload -Name 'resident_surface_runtime'
  $RuntimeBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Runtime -Name 'blockers' -Default @())
  $ForegroundObserved = (
    $ProofStarted -and
    [string](Get-PropertyValue -Payload $RunningState -Name 'status' -Default '') -eq 'foreground_running' -and
    [bool](Get-PropertyValue -Payload $RunningState -Name 'process_alive' -Default $false) -and
    [bool](Get-PropertyValue -Payload $RunningPid -Name 'pid_present' -Default $false) -and
    [int](Get-PropertyValue -Payload $RunningPid -Name 'pid' -Default 0) -gt 0 -and
    [bool](Get-PropertyValue -Payload $RunningPid -Name 'process_alive' -Default $false)
  )
  $ReadbackObserved = Test-ForegroundSurfaceReadbackObserved -SurfaceReadback $SurfaceReadback
  $ForegroundCompleted = (
    $ForegroundExitCode -eq 0 -and
    [string](Get-PropertyValue -Payload $FinalPayload -Name 'status' -Default '') -eq 'foreground_completed' -and
    [string](Get-PropertyValue -Payload $FinalState -Name 'status' -Default '') -eq 'foreground_stopped'
  )

  return [ordered]@{
    ok = ($ForegroundObserved -and $ReadbackObserved -and $ForegroundCompleted)
    error = [string](Get-PropertyValue -Payload $SurfaceReadback -Name 'error' -Default '')
    data_root = $ProofDataRoot
    runtime_state_path = 'runtime/lens-host/status.json'
    foreground_process_observed = $ForegroundObserved
    foreground_runtime_readback_observed = $ReadbackObserved
    foreground_completed = $ForegroundCompleted
    foreground_exit_code = $ForegroundExitCode
    payload = $SurfacePayload
    runtime = $Runtime
    runtime_blockers = $RuntimeBlockers
    running_state_status = [string](Get-PropertyValue -Payload $RunningState -Name 'status' -Default '')
    running_pid_present = [bool](Get-PropertyValue -Payload $RunningPid -Name 'pid_present' -Default $false)
    running_pid = [int](Get-PropertyValue -Payload $RunningPid -Name 'pid' -Default 0)
    running_pid_process_alive = [bool](Get-PropertyValue -Payload $RunningPid -Name 'process_alive' -Default $false)
    final_state_status = [string](Get-PropertyValue -Payload $FinalState -Name 'status' -Default '')
    foreground_stdout_length = if ($null -eq $ForegroundStdout) { 0 } else { $ForegroundStdout.Length }
    foreground_stderr_length = if ($null -eq $ForegroundStderr) { 0 } else { $ForegroundStderr.Length }
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

$PowerShellPath = Get-PowerShellPath
$HostPreflightPath = Join-Path $PSScriptRoot 'lens-host-preflight.ps1'
$SupervisionProofPath = Join-Path $PSScriptRoot 'lens-host-supervision-proof.ps1'
$LiveOperatorProofPath = Join-Path $PSScriptRoot 'lens-live-operator-proof.ps1'
$TrayPreflightPath = Join-Path $PSScriptRoot 'lens-tray-preflight.ps1'
$OverlayPreflightPath = Join-Path $PSScriptRoot 'lens-overlay-preflight.ps1'
$SummonPreflightPath = Join-Path $PSScriptRoot 'lens-summon-preflight.ps1'
$ReadbackDataRoot = ''
if ([string]::IsNullOrWhiteSpace($DataDir)) {
  $ReadbackDataRoot = [System.IO.Path]::GetFullPath(
    (Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-resident-surface-proof\" + [guid]::NewGuid().ToString('N') + "\data"))
  )
} else {
  $ReadbackDataRoot = [System.IO.Path]::GetFullPath($DataDir)
}
New-Item -ItemType Directory -Force -Path $ReadbackDataRoot | Out-Null

$LiveResidentSurfaceReadback = if ([string]::IsNullOrWhiteSpace($DataDir)) {
  Invoke-ResidentSurfaceReadback -TimeoutSeconds $ResidentSurfaceReadbackTimeoutSeconds
} else {
  Invoke-ResidentSurfaceReadback -DataDir $ReadbackDataRoot -TimeoutSeconds $ResidentSurfaceReadbackTimeoutSeconds
}
$LiveResidentSurfacePayload = Get-PropertyValue -Payload $LiveResidentSurfaceReadback -Name 'payload'
$LiveResidentSurfaceRuntime = Get-PropertyValue -Payload $LiveResidentSurfacePayload -Name 'resident_surface_runtime'
$LiveResidentSurfaceRuntimeBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $LiveResidentSurfaceRuntime -Name 'blockers' -Default @()
)
$ResidentSurfaceResidentRuntimeReadback = Test-ResidentSurfaceReadbackObserved -SurfaceReadback $LiveResidentSurfaceReadback
$ResidentSurfaceReadback = if ($ResidentSurfaceResidentRuntimeReadback) {
  $LiveResidentSurfaceReadback
} else {
  Invoke-ResidentSurfaceReadback -DataDir $ReadbackDataRoot -TimeoutSeconds $ResidentSurfaceReadbackTimeoutSeconds
}
$ForegroundSurfaceReadback = if ($ResidentSurfaceResidentRuntimeReadback) {
  [ordered]@{
    ok = $true
    error = ''
    skipped_due_to_live_resident_runtime = $true
    payload = $null
    runtime = $null
    runtime_blockers = [string[]]@()
    foreground_process_observed = $false
    foreground_runtime_readback_observed = $false
    foreground_completed = $false
    runtime_state_path = ''
    running_state_status = 'not_run_live_resident_runtime_observed'
    final_state_status = 'not_run_live_resident_runtime_observed'
  }
} else {
  Invoke-ForegroundResidentSurfaceReadback -PowerShellPath $PowerShellPath -RunSeconds $ForegroundRunSeconds -ReadbackTimeoutSeconds $ResidentSurfaceReadbackTimeoutSeconds
}
$HostPreflight = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $HostPreflightPath -ScriptArgs @('-Mode', 'Status')
$LiveOperatorProofSkipped = $ResidentSurfaceResidentRuntimeReadback
$LiveOperatorProof = if ($LiveOperatorProofSkipped) {
  [ordered]@{
    exit_code = 0
    payload = [ordered]@{
      kind = 'lens.live_operator_experience.proof'
      status = 'not_run_live_resident_runtime_observed'
      live_http_status_readback = $false
      operator_experience_proof = $false
      helpful_not_noisy_readback = $false
      live_operator_experience_ready = $false
      ready_for_stage6_closure = $false
      status_route = ''
      blockers = [string[]]@()
      proof = [ordered]@{
        status_error = ''
        api_pid = 0
        api_exit_code = $null
        api_stdout_path = ''
        api_stderr_path = ''
      }
    }
  }
} else {
  Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $LiveOperatorProofPath -ScriptArgs @(
    '-Mode', 'Status',
    '-DataDir', $ReadbackDataRoot,
    '-StartupTimeoutSeconds', [string]$LiveOperatorStartupTimeoutSeconds
  )
}
$TrayPreflight = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $TrayPreflightPath -ScriptArgs @('-Mode', 'Status', '-DataDir', $ReadbackDataRoot)
$OverlayPreflight = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $OverlayPreflightPath -ScriptArgs @('-Mode', 'Status', '-DataDir', $ReadbackDataRoot)
$SummonPreflight = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $SummonPreflightPath -ScriptArgs @('-Mode', 'Status', '-DataDir', $ReadbackDataRoot)

$HostPayload = Get-PropertyValue -Payload $HostPreflight -Name 'payload'
$LiveOperatorPayload = Get-PropertyValue -Payload $LiveOperatorProof -Name 'payload'
$LiveOperatorProofDetails = Get-PropertyValue -Payload $LiveOperatorPayload -Name 'proof'
$TrayPayload = Get-PropertyValue -Payload $TrayPreflight -Name 'payload'
$OverlayPayload = Get-PropertyValue -Payload $OverlayPreflight -Name 'payload'
$SummonPayload = Get-PropertyValue -Payload $SummonPreflight -Name 'payload'
$ResidentSurfacePayload = Get-PropertyValue -Payload $ResidentSurfaceReadback -Name 'payload'
$ForegroundSurfacePayload = Get-PropertyValue -Payload $ForegroundSurfaceReadback -Name 'payload'
$ForegroundSurfaceRuntime = Get-PropertyValue -Payload $ForegroundSurfaceReadback -Name 'runtime'

$Tray = Get-PropertyValue -Payload $TrayPayload -Name 'tray'
$Overlay = Get-PropertyValue -Payload $OverlayPayload -Name 'overlay'
$Binding = Get-PropertyValue -Payload $SummonPayload -Name 'binding'
$ResidentSurfaceGovernance = Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'governance'
$ResidentSurfaceReadbackBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'blockers' -Default @()
)
$ResidentSurfaceReadbackError = [string](Get-PropertyValue -Payload $ResidentSurfaceReadback -Name 'error' -Default '')
$LiveResidentSurfaceReadbackError = [string](Get-PropertyValue -Payload $LiveResidentSurfaceReadback -Name 'error' -Default '')
$ForegroundSurfaceReadbackError = [string](Get-PropertyValue -Payload $ForegroundSurfaceReadback -Name 'error' -Default '')
$ResidentSurfaceReadbackTimedOut = (
  $ResidentSurfaceReadbackError -eq 'resident_surface_readback_timeout' -or
  $ForegroundSurfaceReadbackError -eq 'resident_surface_readback_timeout'
)
$ForegroundSurfaceRuntimeBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $ForegroundSurfaceReadback -Name 'runtime_blockers' -Default @()
)
$HostGovernance = Get-PropertyValue -Payload $HostPayload -Name 'governance'
$TrayGovernance = Get-PropertyValue -Payload $TrayPayload -Name 'governance'
$OverlayGovernance = Get-PropertyValue -Payload $OverlayPayload -Name 'governance'
$SummonGovernance = Get-PropertyValue -Payload $SummonPayload -Name 'governance'

$HostLifecycleBlocked = (
  [int](Get-PropertyValue -Payload $HostPreflight -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $HostPayload -Name 'kind' -Default '') -eq 'lens.host.lifecycle_preflight' -and
  [string](Get-PropertyValue -Payload $HostPayload -Name 'status' -Default '') -eq 'blocked'
)
$SupervisionProofAvailable = Test-Path -LiteralPath $SupervisionProofPath -PathType Leaf
$TrayBlocked = (
  [int](Get-PropertyValue -Payload $TrayPreflight -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $TrayPayload -Name 'kind' -Default '') -eq 'lens.tray.preflight' -and
  [string](Get-PropertyValue -Payload $TrayPayload -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $TrayPayload -Name 'ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Tray -Name 'tray_host_enabled' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Tray -Name 'tray_icon_enabled' -Default $true)
)
$OverlayBlocked = (
  [int](Get-PropertyValue -Payload $OverlayPreflight -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $OverlayPayload -Name 'kind' -Default '') -eq 'lens.overlay.preflight' -and
  [string](Get-PropertyValue -Payload $OverlayPayload -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $OverlayPayload -Name 'ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Overlay -Name 'window_enabled' -Default $true)
)
$SummonBlocked = (
  [int](Get-PropertyValue -Payload $SummonPreflight -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'kind' -Default '') -eq 'lens.summon.preflight' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $SummonPayload -Name 'ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Binding -Name 'binding_enabled' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Binding -Name 'register_hotkey' -Default $true)
)
$LiveOperatorProofPassed = (
  [int](Get-PropertyValue -Payload $LiveOperatorProof -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'kind' -Default '') -eq 'lens.live_operator_experience.proof' -and
  [string](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'live_http_status_readback' -Default $false) -and
  [bool](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'operator_experience_proof' -Default $false) -and
  [bool](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'helpful_not_noisy_readback' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'resident_surface_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'resident_claim_allowed' -Default $true)
)
$LiveOperatorProofSatisfied = $LiveOperatorProofPassed -or $LiveOperatorProofSkipped
$ResidentSurfaceContentReadback = (
  [bool](Get-PropertyValue -Payload $ResidentSurfaceReadback -Name 'ok' -Default $false) -and
  [int](Get-PropertyValue -Payload $ResidentSurfaceReadback -Name 'status_code' -Default 0) -eq 200 -and
  [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'kind' -Default '') -eq 'lens.resident_surface.readback' -and
  [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'contract_status' -Default '') -eq 'readback_ready' -and
  [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'route' -Default '') -eq '/lens/resident-surface' -and
  [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'content_contract_ready' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'summon_authority' -Default $true)
)
$ResidentSurfaceForegroundRuntimeReadback = (
  [bool](Get-PropertyValue -Payload $ForegroundSurfaceReadback -Name 'ok' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ForegroundSurfaceReadback -Name 'foreground_process_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ForegroundSurfaceReadback -Name 'foreground_runtime_readback_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ForegroundSurfaceReadback -Name 'foreground_completed' -Default $false) -and
  [string](Get-PropertyValue -Payload $ForegroundSurfacePayload -Name 'kind' -Default '') -eq 'lens.resident_surface.readback' -and
  [string](Get-PropertyValue -Payload $ForegroundSurfaceRuntime -Name 'status' -Default '') -eq 'foreground_runtime_observed' -and
  [bool](Get-PropertyValue -Payload $ForegroundSurfaceRuntime -Name 'foreground_runtime_observed' -Default $false) -and
  ($ForegroundSurfaceRuntimeBlockers -contains 'resident_surface_runtime_not_supervised') -and
  ($ForegroundSurfaceRuntimeBlockers -contains 'resident_surface_not_resident') -and
  -not ($ForegroundSurfaceRuntimeBlockers -contains 'resident_surface_runtime_missing') -and
  -not [bool](Get-PropertyValue -Payload $ForegroundSurfacePayload -Name 'resident_surface_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ForegroundSurfacePayload -Name 'resident_claim_allowed' -Default $true)
)
$ResidentSurfaceRuntimeReadback = $ResidentSurfaceResidentRuntimeReadback -or $ResidentSurfaceForegroundRuntimeReadback
$ResidentSurfaceClaimAllowed = (
  $ResidentSurfaceResidentRuntimeReadback -and
  [bool](Get-PropertyValue -Payload $LiveResidentSurfacePayload -Name 'resident_claim_allowed' -Default $false)
)
$ResidentClaimAuthorityReady = (
  $ResidentSurfaceResidentRuntimeReadback -and
  [bool](Get-PropertyValue -Payload $LiveResidentSurfacePayload -Name 'resident_claim_authority_ready' -Default $false)
)
$ResidentClaimAuthorityReadinessRoute = [string](Get-PropertyValue -Payload $LiveResidentSurfacePayload -Name 'resident_claim_authority_readiness_route' -Default '/lens/host/persistent-supervision/resident-claim/authority/readiness')
$ResidentClaimAuthorityBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $LiveResidentSurfacePayload -Name 'resident_claim_authority_blockers' -Default @())
$AuthorityDenied = (
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'service_install_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'process_supervision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayGovernance -Name 'tray_icon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayGovernance -Name 'window_management_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'hotkey_registration_authority' -Default $true)
)
$ResidentClaimBoundaryReady = (
  ($ResidentSurfaceClaimAllowed -and $ResidentClaimAuthorityReady) -or
  ($HostLifecycleBlocked -and $TrayBlocked -and $OverlayBlocked -and $SummonBlocked -and $AuthorityDenied)
)

$Checks = @(
  (New-Check -Id 'resident_surface_content_readback' -Status $(if ($ResidentSurfaceContentReadback) { 'readback_ready' } else { 'failed' }) -Passed $ResidentSurfaceContentReadback -Evidence '/lens/resident-surface?limit=5' -Reason 'Resident surface content must be directly readable through the backend API route before runtime work can claim a surface.')
  (New-Check -Id 'resident_surface_runtime_readback' -Status $(if ($ResidentSurfaceResidentRuntimeReadback) { 'resident_runtime_observed' } elseif ($ResidentSurfaceForegroundRuntimeReadback) { 'foreground_runtime_observed' } else { 'missing_or_failed' }) -Passed $ResidentSurfaceRuntimeReadback -Evidence '/lens/resident-surface?limit=5' -Reason 'Resident surface proof must consume either live supervised resident runtime readback or the bounded foreground runtime handoff before replacing runtime-missing.')
  (New-Check -Id 'host_lifecycle_boundary' -Status $(if ($HostLifecycleBlocked) { 'blocked_readback_ready' } else { 'failed' }) -Passed $HostLifecycleBlocked -Evidence 'scripts/lens-host-preflight.ps1 -Mode Status' -Reason 'Host lifecycle must be readable and blocked before resident surface work.')
  (New-Check -Id 'supervision_proof_available' -Status $(if ($SupervisionProofAvailable) { 'available' } else { 'missing' }) -Passed $SupervisionProofAvailable -Evidence 'scripts/lens-host-supervision-proof.ps1' -Reason 'The separate foreground/supervision proof remains the bounded process-readiness evidence.')
  (New-Check -Id 'live_operator_experience_proof' -Status $(if ($LiveOperatorProofPassed) { 'proof_passed' } elseif ($LiveOperatorProofSkipped) { 'not_run_live_resident_runtime_observed' } else { 'missing_or_failed' }) -Passed $LiveOperatorProofSatisfied -Evidence 'scripts/lens-live-operator-proof.ps1 -Mode Status' -Reason 'The pre-resident live-operator proof is consumed only before a canonical supervised resident runtime is observed; after that, operator experience remains the next gate.')
  (New-Check -Id 'tray_presence_preflight' -Status $(if ($TrayBlocked) { 'blocked_disabled' } else { 'failed' }) -Passed $TrayBlocked -Evidence 'scripts/lens-tray-preflight.ps1 -Mode Status' -Reason 'Tray presence config must be readable, disabled, and blocked.')
  (New-Check -Id 'overlay_window_preflight' -Status $(if ($OverlayBlocked) { 'blocked_disabled' } else { 'failed' }) -Passed $OverlayBlocked -Evidence 'scripts/lens-overlay-preflight.ps1 -Mode Status' -Reason 'Overlay window config must be readable, disabled, and blocked.')
  (New-Check -Id 'summon_binding_preflight' -Status $(if ($SummonBlocked) { 'blocked_disabled' } else { 'failed' }) -Passed $SummonBlocked -Evidence 'scripts/lens-summon-preflight.ps1 -Mode Status' -Reason 'Summon binding config must be readable, declared, disabled, and blocked.')
  (New-Check -Id 'authority_boundary' -Status $(if ($AuthorityDenied) { 'blocked' } else { 'unexpected_authority' }) -Passed $AuthorityDenied -Evidence 'preflight.governance' -Reason 'Resident surface proof must not grant service, tray, overlay, hotkey, or summon authority.')
  (New-Check -Id 'resident_claim_boundary' -Status $(if ($ResidentSurfaceClaimAllowed) { 'claim_readback_ready' } elseif ($ResidentClaimBoundaryReady) { 'blocked' } else { 'unexpected_claim' }) -Passed $ResidentClaimBoundaryReady -Evidence 'resident surface flags' -Reason 'Resident claim must either remain blocked or be backed by live resident runtime and resident-claim authority readback.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })
if ($ResidentSurfaceResidentRuntimeReadback) {
  $ResidentSurfaceRuntimeBlockers = @(
    @($LiveResidentSurfaceRuntimeBlockers | Where-Object {
        $_ -ne 'resident_surface_missing' -and
        $_ -ne 'resident_surface_runtime_missing' -and
        $_ -ne 'resident_surface_runtime_not_supervised' -and
        $_ -ne 'resident_surface_not_resident'
      })
  ) | Sort-Object -Unique
} elseif ($ResidentSurfaceForegroundRuntimeReadback) {
  $ResidentSurfaceRuntimeBlockers = @(
    @($ForegroundSurfaceRuntimeBlockers | Where-Object {
        $_ -ne 'resident_surface_missing' -and $_ -ne 'resident_surface_runtime_missing'
      }) +
    @('resident_surface_runtime_not_supervised', 'resident_surface_not_resident')
  ) | Sort-Object -Unique
} else {
  $ResidentSurfaceRuntimeBlockers = @(
    @($ResidentSurfaceReadbackBlockers | Where-Object { $_ -ne 'resident_surface_missing' }) +
    @('resident_surface_runtime_missing')
  ) | Sort-Object -Unique
}
$BaseBlockers = @()
$BaseBlockers += @($ResidentSurfaceRuntimeBlockers)
$BaseBlockers += @(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostPayload -Name 'blockers' -Default @()))
$BaseBlockers += @(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $TrayPayload -Name 'blockers' -Default @()))
$BaseBlockers += @(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $OverlayPayload -Name 'blockers' -Default @()))
$BaseBlockers += @(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $SummonPayload -Name 'blockers' -Default @()))
$BaseBlockers += @(
  'tray_presence_missing',
  'overlay_window_missing',
  'summon_anywhere_missing'
)
if ($ResidentSurfaceResidentRuntimeReadback) {
  $BaseBlockers = @(
    $BaseBlockers | Where-Object {
      $_ -ne 'resident_surface_runtime_missing' -and
      $_ -ne 'resident_surface_runtime_not_supervised' -and
      $_ -ne 'resident_surface_not_resident' -and
      $_ -ne 'resident_host_process_missing' -and
      $_ -ne 'resident_host_process_not_supervised'
    }
  )
}
if ((-not $LiveOperatorProofPassed) -and (-not $LiveOperatorProofSkipped)) {
  $BaseBlockers += 'operator_experience_proof_missing'
}
if (-not $ResidentSurfaceContentReadback) {
  $BaseBlockers += 'resident_surface_readback_missing'
}
if ($ResidentSurfaceReadbackTimedOut) {
  $BaseBlockers += 'resident_surface_readback_timeout'
}
$AllBlockers = @($BaseBlockers | Sort-Object -Unique)
$ResidentSurfaceNextSmallestTruthfulGap = if ($ResidentSurfaceReadbackTimedOut) { 'resident_surface_readback_timeout' } elseif ($ResidentSurfaceResidentRuntimeReadback) { 'resident_surface_operator_experience_proof' } elseif ($ResidentSurfaceForegroundRuntimeReadback) { 'resident_surface_runtime_not_supervised' } else { 'resident_surface_runtime_missing' }
$RecommendedHandoffSource = 'resident_surface_runtime_supervision_handoff'
$RecommendedNextSlice = if ($ResidentSurfaceReadbackTimedOut) { 'fix_resident_surface_readback_timeout' } elseif ($ResidentSurfaceResidentRuntimeReadback) { 'prove_resident_surface_operator_experience_before_helpful_not_noisy_claim' } elseif ($ResidentSurfaceForegroundRuntimeReadback) { 'resolve_resident_surface_runtime_supervision_before_helpful_not_noisy_claim' } else { 'prove_resident_surface_foreground_runtime_before_helpful_not_noisy_claim' }
$RecommendedProofScript = 'scripts/lens-resident-surface-proof.ps1 -Mode Status'
$RecommendedAuthorityRequired = if ($ResidentSurfaceReadbackTimedOut) { 'none_readback_first' } elseif ($ResidentSurfaceResidentRuntimeReadback) { 'operator_experience_proof' } elseif ($ResidentSurfaceForegroundRuntimeReadback) { 'process_supervision_authority' } else { 'none_readback_first' }
$RuntimeSurfacePayload = if ($ResidentSurfaceResidentRuntimeReadback) { $LiveResidentSurfacePayload } else { $ForegroundSurfacePayload }
$ForegroundRecommendedHandoff = Get-PropertyValue -Payload $RuntimeSurfacePayload -Name 'recommended_handoff'
if ($null -eq $ForegroundRecommendedHandoff) {
  $ForegroundRecommendedHandoff = [ordered]@{}
}
$ForegroundRecommendedHandoffSource = [string](Get-PropertyValue -Payload $RuntimeSurfacePayload -Name 'recommended_handoff_source' -Default '')
if (-not [string]::IsNullOrWhiteSpace($ForegroundRecommendedHandoffSource)) {
  $RecommendedHandoffSource = $ForegroundRecommendedHandoffSource
}
$ForegroundRecommendedNextSlice = [string](Get-PropertyValue -Payload $RuntimeSurfacePayload -Name 'recommended_next_slice' -Default '')
if (-not [string]::IsNullOrWhiteSpace($ForegroundRecommendedNextSlice)) {
  $RecommendedNextSlice = $ForegroundRecommendedNextSlice
}
$ForegroundRecommendedProofScript = [string](Get-PropertyValue -Payload $RuntimeSurfacePayload -Name 'recommended_proof_script' -Default '')
if (-not [string]::IsNullOrWhiteSpace($ForegroundRecommendedProofScript)) {
  $RecommendedProofScript = $ForegroundRecommendedProofScript
}
$ForegroundRecommendedAuthorityRequired = [string](Get-PropertyValue -Payload $RuntimeSurfacePayload -Name 'authority_required' -Default '')
if (-not [string]::IsNullOrWhiteSpace($ForegroundRecommendedAuthorityRequired)) {
  $RecommendedAuthorityRequired = $ForegroundRecommendedAuthorityRequired
}
if ($ResidentSurfaceResidentRuntimeReadback) {
  $RecommendedHandoffSource = 'resident_surface_runtime_supervision_handoff'
  $RecommendedNextSlice = 'prove_resident_surface_operator_experience_before_helpful_not_noisy_claim'
  $RecommendedProofScript = 'scripts/lens-resident-surface-proof.ps1 -Mode Status'
  $RecommendedAuthorityRequired = 'operator_experience_proof'
  $ForegroundRecommendedHandoff = [ordered]@{
    id = 'resident_surface_runtime_supervision'
    status = 'blocked'
    next_smallest_truthful_gap = 'resident_surface_operator_experience_proof'
    next_step = $RecommendedNextSlice
    proof_script = $RecommendedProofScript
    route = '/lens/resident-surface'
    readiness_route = '/lens/resident-runtime/authority-grant/readiness'
    acceptance_criterion = 'helpful_not_noisy'
    blocker = 'resident_surface_operator_experience_proof'
    requirement_state = 'resident_runtime_observed'
    authority_required = $RecommendedAuthorityRequired
    authority_granted = $false
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
    would_supervise_process = $false
    would_restart_process = $false
    would_claim_resident = $false
  }
} elseif ($ResidentSurfaceForegroundRuntimeReadback) {
  $RecommendedHandoffSource = 'resident_surface_runtime_supervision_handoff'
  $RecommendedNextSlice = 'resolve_resident_surface_runtime_supervision_before_helpful_not_noisy_claim'
  $RecommendedProofScript = 'scripts/lens-resident-surface-proof.ps1 -Mode Status'
  $RecommendedAuthorityRequired = 'process_supervision_authority'
  $ForegroundRecommendedHandoff = [ordered]@{
    id = 'resident_surface_runtime_supervision'
    status = 'blocked'
    next_smallest_truthful_gap = 'resident_surface_runtime_not_supervised'
    next_step = $RecommendedNextSlice
    proof_script = $RecommendedProofScript
    route = '/lens/resident-surface'
    readiness_route = '/lens/resident-runtime/authority-grant/readiness'
    acceptance_criterion = 'helpful_not_noisy'
    blocker = 'resident_surface_runtime_not_supervised'
    requirement_state = 'foreground_observed_not_supervised'
    authority_required = $RecommendedAuthorityRequired
    authority_granted = $false
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
    would_supervise_process = $false
    would_restart_process = $false
    would_claim_resident = $false
  }
}

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.resident_surface.readiness_proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  resident_surface_ready = $ResidentSurfaceResidentRuntimeReadback
  resident_surface_content_readback = $ResidentSurfaceContentReadback
  resident_surface_resident_runtime_readback = $ResidentSurfaceResidentRuntimeReadback
  resident_surface_resident_runtime_observed = [bool](Get-PropertyValue -Payload $LiveResidentSurfaceRuntime -Name 'resident_runtime_observed' -Default $false)
  resident_surface_foreground_runtime_readback = $ResidentSurfaceForegroundRuntimeReadback
  resident_surface_foreground_runtime_observed = [bool](Get-PropertyValue -Payload $ForegroundSurfaceReadback -Name 'foreground_runtime_readback_observed' -Default $false)
  resident_surface_content_contract_ready = [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'content_contract_ready' -Default $false)
  resident_surface_contract_status = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'contract_status' -Default '')
  resident_surface_runtime_status = if ($ResidentSurfaceResidentRuntimeReadback) { [string](Get-PropertyValue -Payload $LiveResidentSurfaceRuntime -Name 'status' -Default '') } else { [string](Get-PropertyValue -Payload $ForegroundSurfaceRuntime -Name 'status' -Default '') }
  resident_surface_route = '/lens/resident-surface'
  ready_for_lens_resident_claim = $ResidentSurfaceClaimAllowed
  resident_claim_allowed = $ResidentSurfaceClaimAllowed
  resident_claim_authority_ready = $ResidentClaimAuthorityReady
  resident_claim_authority_readiness_route = $ResidentClaimAuthorityReadinessRoute
  resident_claim_authority_blockers = [string[]]@($ResidentClaimAuthorityBlockers)
  resident_host_process = $ResidentSurfaceResidentRuntimeReadback
  foreground_host_process_observed = [bool](Get-PropertyValue -Payload $ForegroundSurfaceReadback -Name 'foreground_process_observed' -Default $false)
  foreground_host_runtime_completed = [bool](Get-PropertyValue -Payload $ForegroundSurfaceReadback -Name 'foreground_completed' -Default $false)
  tray_presence = $false
  tray_icon = $false
  overlay_window = $false
  global_hotkey_bound = $false
  summon_anywhere = $false
  live_http_status_readback = ($ResidentSurfaceContentReadback -or [bool](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'live_http_status_readback' -Default $false))
  operator_experience_proof = $LiveOperatorProofPassed
  live_operator_experience_proof = $LiveOperatorProofPassed
  live_operator_experience_ready = $false
  checks = @($Checks)
  blockers = @($AllBlockers)
  recommended_handoff_source = $RecommendedHandoffSource
  recommended_next_slice = $RecommendedNextSlice
  recommended_proof_script = $RecommendedProofScript
  authority_required = $RecommendedAuthorityRequired
  authority_granted = $false
  execution_authority = $false
  approval_decision_authority = $false
  memory_write = $false
  process_supervision_authority = $false
  service_control_authority = $false
  resident_claim_authority = $ResidentClaimAuthorityReady
  recommended_handoff = $ForegroundRecommendedHandoff
  resident_runtime_authority_grant_readiness_route = [string](Get-PropertyValue -Payload $RuntimeSurfacePayload -Name 'resident_runtime_authority_grant_readiness_route' -Default '/lens/resident-runtime/authority-grant/readiness')
  resident_runtime_authority_grant_handoff_observed = [bool](Get-PropertyValue -Payload $RuntimeSurfacePayload -Name 'resident_runtime_authority_grant_handoff_observed' -Default $false)
  proof = [ordered]@{
    resident_surface_readback_status = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'status' -Default '')
    resident_surface_contract_status = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'contract_status' -Default '')
    resident_surface_route = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'route' -Default '')
    resident_surface_activation_route = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'activation_route' -Default '')
    resident_surface_content_contract_ready = [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'content_contract_ready' -Default $false)
    resident_surface_readback_blockers = $ResidentSurfaceReadbackBlockers
    resident_surface_resident_runtime_status = [string](Get-PropertyValue -Payload $LiveResidentSurfaceRuntime -Name 'status' -Default '')
    resident_surface_resident_runtime_observed = [bool](Get-PropertyValue -Payload $LiveResidentSurfaceRuntime -Name 'resident_runtime_observed' -Default $false)
    resident_surface_resident_runtime_blockers = $LiveResidentSurfaceRuntimeBlockers
    resident_surface_foreground_runtime_status = [string](Get-PropertyValue -Payload $ForegroundSurfaceRuntime -Name 'status' -Default '')
    resident_surface_foreground_runtime_observed = [bool](Get-PropertyValue -Payload $ForegroundSurfaceRuntime -Name 'foreground_runtime_observed' -Default $false)
    resident_surface_foreground_runtime_blockers = $ForegroundSurfaceRuntimeBlockers
    resident_claim_allowed = $ResidentSurfaceClaimAllowed
    resident_claim_authority_ready = $ResidentClaimAuthorityReady
    resident_claim_authority_readiness_route = $ResidentClaimAuthorityReadinessRoute
    resident_claim_authority_blockers = [string[]]@($ResidentClaimAuthorityBlockers)
    foreground_runtime_state_path = [string](Get-PropertyValue -Payload $ForegroundSurfaceReadback -Name 'runtime_state_path' -Default '')
    foreground_runtime_running_state = [string](Get-PropertyValue -Payload $ForegroundSurfaceReadback -Name 'running_state_status' -Default '')
    foreground_runtime_final_state = [string](Get-PropertyValue -Payload $ForegroundSurfaceReadback -Name 'final_state_status' -Default '')
    host_lifecycle_status = [string](Get-PropertyValue -Payload $HostPayload -Name 'status' -Default '')
    supervision_proof_available = $SupervisionProofAvailable
    live_operator_exit_code = [int](Get-PropertyValue -Payload $LiveOperatorProof -Name 'exit_code' -Default -1)
    live_operator_startup_timeout_seconds = $LiveOperatorStartupTimeoutSeconds
    resident_surface_readback_timeout_seconds = $ResidentSurfaceReadbackTimeoutSeconds
    live_operator_status = [string](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'status' -Default '')
    live_operator_helpful_not_noisy_readback = [bool](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'helpful_not_noisy_readback' -Default $false)
    live_operator_status_route = [string](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'status_route' -Default '')
    live_operator_status_error = [string](Get-PropertyValue -Payload $LiveOperatorProofDetails -Name 'status_error' -Default '')
    live_operator_api_pid = [int](Get-PropertyValue -Payload $LiveOperatorProofDetails -Name 'api_pid' -Default 0)
    live_operator_api_exit_code = Get-PropertyValue -Payload $LiveOperatorProofDetails -Name 'api_exit_code'
    live_operator_api_stdout_path = [string](Get-PropertyValue -Payload $LiveOperatorProofDetails -Name 'api_stdout_path' -Default '')
    live_operator_api_stderr_path = [string](Get-PropertyValue -Payload $LiveOperatorProofDetails -Name 'api_stderr_path' -Default '')
    live_operator_blockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $LiveOperatorPayload -Name 'blockers' -Default @())
    tray_status = [string](Get-PropertyValue -Payload $TrayPayload -Name 'status' -Default '')
    overlay_status = [string](Get-PropertyValue -Payload $OverlayPayload -Name 'status' -Default '')
    summon_status = [string](Get-PropertyValue -Payload $SummonPayload -Name 'status' -Default '')
    tray_host_enabled = [bool](Get-PropertyValue -Payload $Tray -Name 'tray_host_enabled' -Default $false)
    tray_icon_enabled = [bool](Get-PropertyValue -Payload $Tray -Name 'tray_icon_enabled' -Default $false)
    overlay_window_enabled = [bool](Get-PropertyValue -Payload $Overlay -Name 'window_enabled' -Default $false)
    overlay_focus_supported = [bool](Get-PropertyValue -Payload $Overlay -Name 'focus_supported' -Default $false)
    global_hotkey = [string](Get-PropertyValue -Payload $SummonPayload -Name 'global_hotkey' -Default '')
    summon_binding_enabled = [bool](Get-PropertyValue -Payload $Binding -Name 'binding_enabled' -Default $false)
    hotkey_registration_enabled = [bool](Get-PropertyValue -Payload $Binding -Name 'register_hotkey' -Default $false)
    tray_blockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $TrayPayload -Name 'blockers' -Default @())
    overlay_blockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $OverlayPayload -Name 'blockers' -Default @())
    summon_blockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $SummonPayload -Name 'blockers' -Default @())
  }
  next_smallest_truthful_gap = $ResidentSurfaceNextSmallestTruthfulGap
  governance = [ordered]@{
    read_only_contract = $true
    diagnostic_only = $true
    api_route_readback = $ResidentSurfaceContentReadback
    live_http_readback = ($ResidentSurfaceContentReadback -or $LiveOperatorProofPassed)
    temporary_api_process = ($ResidentSurfaceContentReadback -or $LiveOperatorProofPassed)
    bounded_foreground_session = $ResidentSurfaceForegroundRuntimeReadback
    foreground_session_skipped_due_to_live_resident_runtime = $ResidentSurfaceResidentRuntimeReadback
    pre_resident_live_operator_proof_skipped_due_to_live_resident_runtime = $LiveOperatorProofSkipped
    temporary_runtime_state_write = ($ResidentSurfaceContentReadback -or $LiveOperatorProofPassed -or $ResidentSurfaceForegroundRuntimeReadback)
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    window_management_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = $false
    api_local_process_launch_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    resident_claim_authority = $ResidentClaimAuthorityReady
    resident_claim_allowed = $ResidentSurfaceClaimAllowed
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    tray_icon_authority = $false
    notification_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Lens resident surface readiness now consumes the direct resident-surface API readback, the live HTTP operator proof, and a bounded foreground runtime readback, then remains blocked; this proof does not register tray presence, bind a hotkey, open an overlay, supervise a host, install a service, or claim summon-anywhere behavior.'
}

$Payload | ConvertTo-Json -Depth 10
if ($ProofPassed) {
  exit 0
}
exit 1
