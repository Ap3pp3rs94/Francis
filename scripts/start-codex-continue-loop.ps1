[CmdletBinding(PositionalBinding = $false)]
param(
  [string]$Prompt = "continue",
  [int]$PollSeconds = 5,
  [int]$IdleSeconds = 60,
  [string]$SessionId = "",
  [switch]$FollowLatestSession,
  [ValidateSet('ui', 'cli')]
  [string]$DeliveryMode = "ui",
  [string]$WindowTitlePattern = '^Codex(?:$| )|Francis$',
  [string]$StopFile = ".tmp\codex-continue.stop",
  [string]$PidFile = ".tmp\codex-continue.pid",
  [string]$LogFile = ".tmp\codex-continue.log",
  [switch]$Restart
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Resolve-LoopPath([string]$Candidate) {
  if ([string]::IsNullOrWhiteSpace($Candidate)) {
    return $null
  }
  if ([System.IO.Path]::IsPathRooted($Candidate)) {
    return $Candidate
  }
  return Join-Path $repoRoot $Candidate
}

function Get-LoopPid([string]$PidPath) {
  if ([string]::IsNullOrWhiteSpace($PidPath) -or -not (Test-Path -LiteralPath $PidPath)) {
    return $null
  }
  try {
    $text = (Get-Content -LiteralPath $PidPath -ErrorAction Stop | Select-Object -First 1).Trim()
    if (-not $text) {
      return $null
    }
    return [int]$text
  } catch {
    return $null
  }
}

function Get-LoopProcess([string]$PidPath) {
  $existingPid = Get-LoopPid $PidPath
  if ($null -eq $existingPid) {
    return $null
  }
  try {
    $process = Get-Process -Id $existingPid -ErrorAction Stop
    return $process
  } catch {
    return $null
  }
}

function Quote-Argument([string]$Value) {
  if ($null -eq $Value) {
    return '""'
  }
  '"' + ($Value -replace '"', '\"') + '"'
}

$stopPath = Resolve-LoopPath $StopFile
$pidPath = Resolve-LoopPath $PidFile
$logPath = Resolve-LoopPath $LogFile
$loopScript = Join-Path $repoRoot 'scripts\codex-continue-loop.ps1'

$existingProcess = Get-LoopProcess $pidPath
if ($existingProcess) {
  if (-not $Restart) {
    Write-Host ("Codex continue loop is already running (pid {0}). Use -Restart to replace it." -f $existingProcess.Id)
    exit 0
  }

  if ($stopPath) {
    $stopDir = Split-Path -Parent $stopPath
    if ($stopDir -and -not (Test-Path -LiteralPath $stopDir)) {
      New-Item -ItemType Directory -Path $stopDir -Force | Out-Null
    }
    Set-Content -LiteralPath $stopPath -Value "stop $(Get-Date -Format o)" -Encoding utf8
  }
  Start-Sleep -Seconds 1
  try {
    Stop-Process -Id $existingProcess.Id -Force -ErrorAction Stop
  } catch {
  }
}

if ($stopPath -and (Test-Path -LiteralPath $stopPath)) {
  Remove-Item -LiteralPath $stopPath -Force -ErrorAction SilentlyContinue
}

$startArgs = @(
  '-NoProfile',
  '-WindowStyle', 'Hidden',
  '-ExecutionPolicy', 'Bypass',
  '-File', $loopScript,
  '-Prompt', $Prompt,
  '-PollSeconds', ([string]$PollSeconds),
  '-IdleSeconds', ([string]$IdleSeconds),
  '-StopFile', $stopPath,
  '-PidFile', $pidPath,
  '-LogFile', $logPath,
  '-DeliveryMode', $DeliveryMode,
  '-WindowTitlePattern', $WindowTitlePattern
)
if ($SessionId) {
  $startArgs += @('-SessionId', $SessionId)
}
if ($FollowLatestSession) {
  $startArgs += '-FollowLatestSession'
}

$commandLine = 'powershell.exe ' + (($startArgs | ForEach-Object { Quote-Argument ([string]$_) }) -join ' ')
$created = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $commandLine }
if ([int]$created.ReturnValue -ne 0) {
  throw ("Failed to launch codex continue loop via Win32_Process.Create (return={0})." -f $created.ReturnValue)
}
$processId = [int]$created.ProcessId

Write-Host "Codex continue loop started."
Write-Host ("PID: {0}" -f $processId)
Write-Host ("IdleSeconds: {0}" -f $IdleSeconds)
Write-Host ("PollSeconds: {0}" -f $PollSeconds)
Write-Host ("Stop file: {0}" -f $stopPath)
Write-Host ("PID file: {0}" -f $pidPath)
Write-Host ("Log file: {0}" -f $logPath)
if ($SessionId) {
  Write-Host ("SessionId: {0}" -f $SessionId)
} elseif ($FollowLatestSession) {
  Write-Host "Session binding: follow_latest"
} else {
  Write-Host "Session binding: latest_at_start"
}
