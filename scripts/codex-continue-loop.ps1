[CmdletBinding(PositionalBinding = $false)]
param(
  [string]$Prompt = "continue",
  [int]$PollSeconds = 20,
  [int]$IdleSeconds = 60,
  [string]$StopFile = ".tmp\codex-continue.stop",
  [string]$SessionId = "",
  [switch]$FollowLatestSession,
  [ValidateSet('ui', 'cli')]
  [string]$DeliveryMode = "ui",
  [string]$WindowTitlePattern = '^Codex(?:$| )',
  [int]$MaxIterations = 0,
  [switch]$DryRun
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$stopPath = if ([System.IO.Path]::IsPathRooted($StopFile)) {
  $StopFile
} else {
  Join-Path $repoRoot $StopFile
}
$stopDir = Split-Path -Parent $stopPath
if ($stopDir -and -not (Test-Path -LiteralPath $stopDir)) {
  New-Item -ItemType Directory -Path $stopDir -Force | Out-Null
}

function Write-LoopStatus([string]$Message) {
  $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
  Write-Host "[$timestamp] $Message"
}

function Resolve-CodexSessionFile([string]$TargetSessionId) {
  $sessionRoot = Join-Path $HOME '.codex\sessions'
  if (-not (Test-Path -LiteralPath $sessionRoot)) {
    return $null
  }

  if ([string]::IsNullOrWhiteSpace($TargetSessionId)) {
    return $null
  }

  Get-ChildItem -LiteralPath $sessionRoot -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "*$TargetSessionId*" } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1 -ExpandProperty FullName
}

function Resolve-LatestCodexSessionFile {
  $sessionRoot = Join-Path $HOME '.codex\sessions'
  if (-not (Test-Path -LiteralPath $sessionRoot)) {
    return $null
  }

  Get-ChildItem -LiteralPath $sessionRoot -Recurse -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1 -ExpandProperty FullName
}

function Get-SessionIdleSeconds([string]$SessionFilePath) {
  if ([string]::IsNullOrWhiteSpace($SessionFilePath)) {
    return $null
  }
  if (-not (Test-Path -LiteralPath $SessionFilePath)) {
    return $null
  }

  $file = Get-Item -LiteralPath $SessionFilePath
  $idle = ((Get-Date).ToUniversalTime() - $file.LastWriteTimeUtc).TotalSeconds
  return [Math]::Max(0, [int][Math]::Floor($idle))
}

function Get-SessionTurnState([string]$SessionFilePath, [int]$TailLines = 200) {
  if ([string]::IsNullOrWhiteSpace($SessionFilePath)) {
    return $null
  }
  if (-not (Test-Path -LiteralPath $SessionFilePath)) {
    return $null
  }

  try {
    $lines = @(Get-Content -LiteralPath $SessionFilePath -Tail $TailLines -ErrorAction Stop)
  } catch {
    return $null
  }

  $latestStartedIndex = -1
  $latestStartedAt = ""
  $latestTerminalIndex = -1
  $latestTerminalAt = ""
  $latestTerminalType = ""

  for ($index = 0; $index -lt $lines.Count; $index += 1) {
    $line = [string]$lines[$index]
    if ([string]::IsNullOrWhiteSpace($line)) {
      continue
    }

    try {
      $entry = $line | ConvertFrom-Json -Depth 20 -ErrorAction Stop
    } catch {
      continue
    }

    if ([string]$entry.type -ne 'event_msg') {
      continue
    }

    $eventType = [string]$entry.payload.type
    $timestamp = [string]$entry.timestamp
    if ($eventType -eq 'task_started') {
      $latestStartedIndex = $index
      $latestStartedAt = $timestamp
      continue
    }
    if ($eventType -in @('task_complete', 'turn_aborted')) {
      $latestTerminalIndex = $index
      $latestTerminalAt = $timestamp
      $latestTerminalType = $eventType
    }
  }

  $state = 'unknown'
  if ($latestStartedIndex -ge 0 -and $latestStartedIndex -gt $latestTerminalIndex) {
    $state = 'active'
  } elseif ($latestTerminalIndex -ge 0) {
    $state = 'idle'
  }

  [pscustomobject]@{
    State        = $state
    StartedAt    = $latestStartedAt
    TerminalAt   = $latestTerminalAt
    TerminalType = $latestTerminalType
  }
}

function Get-CodexProcesses {
  @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
      $cmd = [string]$_.CommandLine
      if ([string]::IsNullOrWhiteSpace($cmd)) { return $false }
      return (
        $cmd -match '@openai[\\/]+codex[\\/]+bin[\\/]+codex\.js' -or
        $cmd -match '(^|[\s\\/])codex(?:\.cmd|\.ps1|\.exe)?(?:\s|$)'
      )
    })
}

function Initialize-UiAutomationInterop {
  if (-not ("CodexWindowInterop" -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class CodexWindowInterop {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

  [DllImport("user32.dll")]
  public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

  [DllImport("user32.dll")]
  public static extern bool IsWindowVisible(IntPtr hWnd);

  [DllImport("user32.dll", CharSet = CharSet.Unicode)]
  public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int maxCount);

  [DllImport("user32.dll")]
  public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

  [DllImport("user32.dll")]
  public static extern bool SetForegroundWindow(IntPtr hWnd);

  [DllImport("user32.dll")]
  public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
}
'@
  }

  Add-Type -AssemblyName System.Windows.Forms
}

function Resolve-CodexWindow([string]$TitlePattern) {
  Initialize-UiAutomationInterop

  $script:codexWindowMatches = @()
  [CodexWindowInterop]::EnumWindows({
      param($hWnd, $lParam)
      if (-not [CodexWindowInterop]::IsWindowVisible($hWnd)) {
        return $true
      }

      $titleBuilder = New-Object System.Text.StringBuilder 512
      [void][CodexWindowInterop]::GetWindowText($hWnd, $titleBuilder, $titleBuilder.Capacity)
      $title = $titleBuilder.ToString()
      if ([string]::IsNullOrWhiteSpace($title) -or $title -notmatch $TitlePattern) {
        return $true
      }

      [uint32]$windowPid = 0
      [void][CodexWindowInterop]::GetWindowThreadProcessId($hWnd, [ref]$windowPid)
      $script:codexWindowMatches += [pscustomobject]@{
          Handle = $hWnd
          Title = $title
          ProcessId = [int]$windowPid
        }
      return $true
    }, [IntPtr]::Zero) | Out-Null

  $script:codexWindowMatches |
    Sort-Object ProcessId, Title |
    Select-Object -First 1
}

function Invoke-CodexContinueCli([string]$RepoRoot, [string]$ResumeSessionId, [string]$ResumePrompt, [switch]$Simulate) {
  $commandArgs = @('exec', 'resume')
  if ([string]::IsNullOrWhiteSpace($ResumeSessionId)) {
    $commandArgs += '--last'
  } else {
    $commandArgs += $ResumeSessionId
  }
  $commandArgs += $ResumePrompt

  Write-LoopStatus ("Launching codex {0}" -f ($commandArgs -join ' '))
  if ($Simulate) {
    return 0
  }

  Push-Location $RepoRoot
  try {
    & codex @commandArgs
    return $LASTEXITCODE
  } finally {
    Pop-Location
  }
}

function Invoke-CodexContinueUi([string]$ResumePrompt, [string]$TitlePattern, [switch]$Simulate) {
  $window = Resolve-CodexWindow $TitlePattern
  if (-not $window) {
    Write-LoopStatus ("No visible Codex window matched /{0}/." -f $TitlePattern)
    return 1
  }

  Write-LoopStatus ("Targeting Codex window pid={0} title='{1}'" -f $window.ProcessId, $window.Title)
  if ($Simulate) {
    return 0
  }

  [void][CodexWindowInterop]::ShowWindowAsync($window.Handle, 9)
  Start-Sleep -Milliseconds 250
  [void][CodexWindowInterop]::SetForegroundWindow($window.Handle)
  Start-Sleep -Milliseconds 350
  [System.Windows.Forms.SendKeys]::SendWait($ResumePrompt)
  Start-Sleep -Milliseconds 150
  [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
  return 0
}

if ($PollSeconds -lt 1) {
  throw "PollSeconds must be >= 1 (got $PollSeconds)."
}
if ($IdleSeconds -lt 1) {
  throw "IdleSeconds must be >= 1 (got $IdleSeconds)."
}
if ($MaxIterations -lt 0) {
  throw "MaxIterations must be >= 0 (got $MaxIterations)."
}

$resolvedSessionFile = if ([string]::IsNullOrWhiteSpace($SessionId)) {
  Resolve-LatestCodexSessionFile
} else {
  Resolve-CodexSessionFile $SessionId
}
if ($SessionId -and -not $resolvedSessionFile) {
  throw "Could not resolve a Codex session file for SessionId '$SessionId'."
}

Write-LoopStatus "Codex continue loop started."
Write-LoopStatus "Repo root: $repoRoot"
Write-LoopStatus "Stop file: $stopPath"
if ($SessionId) {
  Write-LoopStatus "Session id: $SessionId"
}
if ($resolvedSessionFile) {
  Write-LoopStatus "Session file: $resolvedSessionFile"
  Write-LoopStatus "Idle threshold: ${IdleSeconds}s"
  if (-not $SessionId) {
    if ($FollowLatestSession) {
      Write-LoopStatus "Session binding: follow_latest"
    } else {
      Write-LoopStatus "Session binding: pinned_at_start"
    }
  }
}
Write-LoopStatus "Delivery mode: $DeliveryMode"
if ($DeliveryMode -eq 'ui') {
  Write-LoopStatus "Window title pattern: $WindowTitlePattern"
}
if ($DryRun) {
  Write-LoopStatus "DryRun is enabled. No Codex command will be executed."
}

$iteration = 0
while ($true) {
  if (Test-Path -LiteralPath $stopPath) {
    Write-LoopStatus "Stop file detected. Exiting."
    break
  }
  if ($MaxIterations -gt 0 -and $iteration -ge $MaxIterations) {
    Write-LoopStatus "MaxIterations reached. Exiting."
    break
  }

  if (-not $SessionId -and ($FollowLatestSession -or -not $resolvedSessionFile)) {
    $latestSessionFile = Resolve-LatestCodexSessionFile
    if ($latestSessionFile -and $latestSessionFile -ne $resolvedSessionFile) {
      $resolvedSessionFile = $latestSessionFile
      Write-LoopStatus "Tracking latest session file: $resolvedSessionFile"
    }
  }

  if ($resolvedSessionFile) {
    $turnState = Get-SessionTurnState $resolvedSessionFile
    if ($turnState -and $turnState.State -eq 'active') {
      $startedAt = if ([string]::IsNullOrWhiteSpace($turnState.StartedAt)) { 'unknown' } else { $turnState.StartedAt }
      Write-LoopStatus ("Session still has an active turn (started {0}). Waiting {1}s." -f $startedAt, $PollSeconds)
      Start-Sleep -Seconds $PollSeconds
      continue
    }

    $idleFor = Get-SessionIdleSeconds $resolvedSessionFile
    if ($null -eq $idleFor) {
      Write-LoopStatus ("Session file is unavailable. Waiting {0}s." -f $PollSeconds)
      Start-Sleep -Seconds $PollSeconds
      continue
    }
    if ($idleFor -lt $IdleSeconds) {
      Write-LoopStatus ("Session idle for {0}s (< {1}s). Waiting {2}s." -f $idleFor, $IdleSeconds, $PollSeconds)
      Start-Sleep -Seconds $PollSeconds
      continue
    }
  } else {
    $runningCodex = Get-CodexProcesses
    if ($runningCodex.Count -gt 0) {
      Write-LoopStatus ("Codex already running ({0} process(es)). Waiting {1}s." -f $runningCodex.Count, $PollSeconds)
      Start-Sleep -Seconds $PollSeconds
      continue
    }
  }

  $iteration += 1
  if ($DeliveryMode -eq 'ui') {
    $exitCode = Invoke-CodexContinueUi -ResumePrompt $Prompt -TitlePattern $WindowTitlePattern -Simulate:$DryRun
  } else {
    $exitCode = Invoke-CodexContinueCli -RepoRoot $repoRoot -ResumeSessionId $SessionId -ResumePrompt $Prompt -Simulate:$DryRun
  }
  if ($exitCode -eq 0) {
    Write-LoopStatus "Codex turn completed."
  } else {
    Write-LoopStatus ("Codex exited with code {0}." -f $exitCode)
  }

  if ($MaxIterations -gt 0 -and $iteration -ge $MaxIterations) {
    Write-LoopStatus "MaxIterations reached after completion. Exiting."
    break
  }

  Start-Sleep -Seconds $PollSeconds
}
