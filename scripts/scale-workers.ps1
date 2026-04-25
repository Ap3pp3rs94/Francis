<#
D:\francis\scripts\scale-workers.ps1

Purpose
  Manage and scale a local pool of "worker" processes on Windows in a controlled way.

Key behaviors
  - Creates/uses a state file per worker group:
      <Root>\data\runtime\workers\<WorkerName>.json
    This file records the command/args/cwd and the PIDs started by this script.
  - By default, ONLY stops/kills workers that exist in the state file.
  - Writes logs:
      Transcript: <Root>\data\logs\operations\scale_workers_<timestamp>.log
      CSV      : <Root>\data\logs\operations\scale_workers_<timestamp>.csv
      Worker IO: <Root>\data\logs\workers\<WorkerName>\worker_<tag>_{out|err}.log

Safety
  - Scale down / Stop / Restart requires -Force.
  - Operates under -Root by default (OverrideSafety available but still blocks system roots).
  - Supports -WhatIf / -Confirm via ShouldProcess.

Examples
  # Show status (no changes)
  pwsh -File D:\francis\scripts\scale-workers.ps1 -WorkerName plugin -Mode Status

  # Scale to exactly 3 node workers
  pwsh -File D:\francis\scripts\scale-workers.ps1 -Mode Scale -WorkerName plugin -Count 3 `
    -Command node -Args @("dist\worker.js") -WorkingDirectory D:\francis\plugin

  # Scale down to 1 (requires Force because it stops workers)
  pwsh -File D:\francis\scripts\scale-workers.ps1 -Mode Scale -WorkerName plugin -Count 1 -Force

  # Stop all tracked workers (requires Force)
  pwsh -File D:\francis\scripts\scale-workers.ps1 -Mode Stop -WorkerName plugin -Force

  # Restart to 2 workers (requires Force)
  pwsh -File D:\francis\scripts\scale-workers.ps1 -Mode Restart -WorkerName plugin -Count 2 -Force
#>

[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
param(
  [ValidateSet('Status','Start','Scale','Stop','Restart','CleanState')]
  [string]$Mode = 'Status',

  [string]$Root = 'D:\francis',
  [string]$WorkerName = 'default',

  # Desired worker count (used by Start/Scale/Restart)
  [int]$Count = 1,

  # Executable to run (node/python/pwsh/your.exe). Optional if state file already exists.
  [string]$Command = '',

  # Arguments for the worker command. Optional if state exists.
  [string[]]$Args = @(),

  # Working directory for the worker. Optional if state exists.
  [string]$WorkingDirectory = '',

  # Required for any action that stops/kills workers (Stop/Restart/Scale-down).
  [switch]$Force,

  # If set, overwrite stored definition in the state file (Command/Args/Cwd).
  # If the state exists and differs, you must set -UpdateDefinition to change it.
  [switch]$UpdateDefinition,

  # Allow working directory outside Root (still blocks dangerous system roots).
  [switch]$OverrideSafety
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# -----------------------------
# Logging
# -----------------------------
$Now    = Get-Date -Format "yyyyMMdd_HHmmss"
$OpsDir = Join-Path $Root 'data\logs\operations'
New-Item -ItemType Directory -Force -Path $OpsDir | Out-Null

$LogPath = Join-Path $OpsDir ("scale_workers_{0}.log" -f $Now)
$CsvPath = Join-Path $OpsDir ("scale_workers_{0}.csv" -f $Now)

$script:Actions = New-Object System.Collections.Generic.List[object]

function Add-Action {
  param(
    [string]$Action,
    [string]$Target,
    [string]$Result,
    [string]$Notes = '',
    [int]$Pid = 0
  )
  $script:Actions.Add([pscustomobject]@{
    Time   = (Get-Date).ToString('s')
    Action = $Action
    Target = $Target
    Result = $Result
    Notes  = $Notes
    Pid    = $Pid
  }) | Out-Null
}

function Write-Section([string]$Title){
  Write-Host ""
  Write-Host ("=" * 72)
  Write-Host $Title
  Write-Host ("=" * 72)
}

function Resolve-FullPath([string]$Path){
  try {
    return (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
  } catch {
    try { return [System.IO.Path]::GetFullPath($Path) } catch { return $Path }
  }
}

function Test-DangerousPath([string]$Path){
  $p = (Resolve-FullPath $Path).TrimEnd('\')

  # Block drive roots like C:\ or D:\
  if($p -match '^[A-Za-z]:\\$'){ return $true }

  # Block common system folders
  $blocked = @(
    $env:SystemRoot,
    (Join-Path $env:SystemDrive '\Windows'),
    (Join-Path $env:SystemDrive '\Program Files'),
    (Join-Path $env:SystemDrive '\Program Files (x86)'),
    (Join-Path $env:SystemDrive '\ProgramData')
  ) | ForEach-Object {
    try { (Resolve-FullPath $_).TrimEnd('\') } catch { $_ }
  }

  foreach($b in $blocked){
    if($p.ToLowerInvariant() -eq ($b.TrimEnd('\').ToLowerInvariant())){ return $true }
  }

  return $false
}

function Test-IsUnderRoot {
  param([string]$Path,[string]$RootPath)

  $p = (Resolve-FullPath $Path).TrimEnd('\')
  $r = (Resolve-FullPath $RootPath).TrimEnd('\')

  $pLower = $p.ToLowerInvariant()
  $rLower = $r.ToLowerInvariant()

  if($pLower -eq $rLower){ return $true }
  if($pLower.StartsWith($rLower + "\")){ return $true }
  return $false
}

function Require-Force([string]$Why){
  if(-not $Force){
    $msg = "$Why requires -Force (try -WhatIf first)."
    Add-Action "Guard" $Why "BLOCKED" $msg
    throw $msg
  }
}

# -----------------------------
# State paths
# -----------------------------
$RuntimeDir = Join-Path $Root 'data\runtime\workers'
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

$StatePath = Join-Path $RuntimeDir ("{0}.json" -f $WorkerName)

$WorkerLogsDir = Join-Path $Root ("data\logs\workers\{0}" -f $WorkerName)
New-Item -ItemType Directory -Force -Path $WorkerLogsDir | Out-Null

function Load-State {
  if(Test-Path -LiteralPath $StatePath){
    try {
      $raw = Get-Content -LiteralPath $StatePath -Raw -ErrorAction Stop
      return ($raw | ConvertFrom-Json -ErrorAction Stop)
    } catch {
      Add-Action "State" $StatePath "FAILED" $_.Exception.Message
      throw "Failed to read/parse state file: $StatePath ($($_.Exception.Message))"
    }
  }

  # default state
  return [pscustomobject]@{
    workerName    = $WorkerName
    root          = $Root
    command       = ''
    args          = @()
    workingDir    = ''
    desiredCount  = 0
    instances     = @()  # each: { pid, tag, started, outLog, errLog }
    updated       = (Get-Date).ToString('s')
  }
}

function Save-State($state){
  $state.updated = (Get-Date).ToString('s')
  if($PSCmdlet.ShouldProcess($StatePath, "Write state file")){
    try {
      ($state | ConvertTo-Json -Depth 6) | Out-File -LiteralPath $StatePath -Encoding UTF8 -Force
      Add-Action "State" $StatePath "OK" "Saved"
    } catch {
      Add-Action "State" $StatePath "FAILED" $_.Exception.Message
      throw
    }
  } else {
    Add-Action "State" $StatePath "WHATIF/SKIPPED" "Not approved"
  }
}

function Get-RunningByPid([int]$Pid){
  if($Pid -le 0){ return $null }
  try { return Get-Process -Id $Pid -ErrorAction SilentlyContinue } catch { return $null }
}

function Prune-DeadInstances($state){
  $kept = @()
  $removed = 0

  foreach($i in @($state.instances)){
    $pid = 0
    try { $pid = [int]$i.pid } catch { $pid = 0 }

    if($pid -gt 0 -and (Get-RunningByPid $pid)){
      $kept += $i
    } else {
      $removed++
      Add-Action "Prune" ("PID {0}" -f $pid) "OK" "Not running -> removed from state" $pid
    }
  }

  $state.instances = @($kept)
  return $removed
}

function Normalize-Definition($state){
  # If caller provided a definition, validate it and optionally apply it.
  $defProvided = -not [string]::IsNullOrWhiteSpace($Command) -or ($Args.Count -gt 0) -or -not [string]::IsNullOrWhiteSpace($WorkingDirectory)

  # Prefer user-provided WorkingDirectory, else state's, else Root
  $wd = $WorkingDirectory
  if([string]::IsNullOrWhiteSpace($wd)){
    try { $wd = [string]$state.workingDir } catch { $wd = '' }
  }
  if([string]::IsNullOrWhiteSpace($wd)){
    $wd = $Root
  }
  $wdFull = Resolve-FullPath $wd

  if(Test-DangerousPath $wdFull){
    throw "Refusing to operate in dangerous working directory: $wdFull"
  }
  if(-not $OverrideSafety){
    if(-not (Test-IsUnderRoot -Path $wdFull -RootPath $Root)){
      throw "Safety block: WorkingDirectory is not under Root ($Root). Use -OverrideSafety if intentional. WorkingDirectory=$wdFull"
    }
  }
  if(-not (Test-Path -LiteralPath $wdFull)){
    throw "WorkingDirectory not found: $wdFull"
  }

  # Determine command/args to use
  $cmd = $Command
  if([string]::IsNullOrWhiteSpace($cmd)){
    try { $cmd = [string]$state.command } catch { $cmd = '' }
  }
  $useArgs = $Args
  if($useArgs.Count -eq 0){
    try { $useArgs = @($state.args) } catch { $useArgs = @() }
  }

  if([string]::IsNullOrWhiteSpace($cmd)){
    throw "No Command provided and state has no command. Provide -Command (and optional -Args/-WorkingDirectory)."
  }

  # If state exists with different definition, require UpdateDefinition to change it
  $stateExists = Test-Path -LiteralPath $StatePath
  if($stateExists){
    $sameCmd = ($cmd -eq [string]$state.command)
    $sameWd  = ($wdFull -eq (Resolve-FullPath ([string]$state.workingDir)))
    $sameArgs = $true
    try {
      $old = @($state.args)
      if($old.Count -ne $useArgs.Count){ $sameArgs = $false }
      else {
        for($k=0; $k -lt $old.Count; $k++){
          if([string]$old[$k] -ne [string]$useArgs[$k]){ $sameArgs = $false; break }
        }
      }
    } catch { $sameArgs = $false }

    if(-not ($sameCmd -and $sameWd -and $sameArgs)){
      if($defProvided -and $UpdateDefinition){
        Add-Action "Definition" $WorkerName "OK" "Updating stored definition"
        $state.command = $cmd
        $state.args = @($useArgs)
        $state.workingDir = $wdFull
      } elseif($defProvided -and (-not $UpdateDefinition)) {
        $msg = "State definition differs from provided definition. Re-run with -UpdateDefinition to overwrite stored Command/Args/WorkingDirectory."
        Add-Action "Definition" $WorkerName "BLOCKED" $msg
        throw $msg
      }
      # If def was NOT provided, we keep state definition.
    }
  } else {
    # New state file -> store definition
    $state.command = $cmd
    $state.args = @($useArgs)
    $state.workingDir = $wdFull
  }

  return $state
}

function Start-Instance {
  param(
    $state,
    [string]$Tag
  )

  $cmd = [string]$state.command
  $args = @($state.args)
  $cwd  = [string]$state.workingDir

  $outLog = Join-Path $WorkerLogsDir ("worker_{0}_out.log" -f $Tag)
  $errLog = Join-Path $WorkerLogsDir ("worker_{0}_err.log" -f $Tag)

  $display = "$cmd " + ($args -join " ")
  $target  = "{0} ({1})" -f $WorkerName,$Tag

  if($PSCmdlet.ShouldProcess($target, "Start worker: $display")){
    try {
      # Start the actual worker process; redirect IO for postmortem
      $p = Start-Process -FilePath $cmd `
                         -ArgumentList $args `
                         -WorkingDirectory $cwd `
                         -NoNewWindow `
                         -RedirectStandardOutput $outLog `
                         -RedirectStandardError  $errLog `
                         -PassThru

      $inst = [pscustomobject]@{
        pid      = [int]$p.Id
        tag      = $Tag
        started  = (Get-Date).ToString('s')
        outLog   = $outLog
        errLog   = $errLog
      }

      $state.instances = @($state.instances) + @($inst)

      Add-Action "Start" $target "OK" ("PID={0} Out={1} Err={2}" -f $p.Id,$outLog,$errLog) $p.Id
      return $true
    } catch {
      Add-Action "Start" $target "FAILED" $_.Exception.Message
      throw
    }
  } else {
    Add-Action "Start" $target "WHATIF/SKIPPED" "Not approved"
    return $false
  }
}

function Stop-Instance {
  param(
    $inst
  )

  $pid = 0
  try { $pid = [int]$inst.pid } catch { $pid = 0 }
  $tag = ''
  try { $tag = [string]$inst.tag } catch { $tag = '' }

  if($pid -le 0){
    Add-Action "Stop" ("{0} ({1})" -f $WorkerName,$tag) "SKIPPED" "No PID"
    return
  }

  $target = "{0} ({1}) PID {2}" -f $WorkerName,$tag,$pid

  if($PSCmdlet.ShouldProcess($target, "Stop worker process tree")){
    # Best effort: Stop-Process, then taskkill /T if still running
    try {
      $p = Get-RunningByPid $pid
      if(-not $p){
        Add-Action "Stop" $target "SKIPPED" "Not running" $pid
        return
      }

      try {
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
      } catch {}

      Start-Sleep -Milliseconds 250

      if(Get-RunningByPid $pid){
        try {
          & taskkill /PID $pid /T /F | Out-Null
        } catch {}
      }

      if(Get-RunningByPid $pid){
        Add-Action "Stop" $target "FAILED" "Process still running after attempts" $pid
      } else {
        Add-Action "Stop" $target "OK" "Stopped" $pid
      }
    } catch {
      Add-Action "Stop" $target "FAILED" $_.Exception.Message $pid
      throw
    }
  } else {
    Add-Action "Stop" $target "WHATIF/SKIPPED" "Not approved" $pid
  }
}

# -----------------------------
# Main
# -----------------------------
try {
  Start-Transcript -Path $LogPath -Force | Out-Null

  Write-Section "Scale Workers"
  Write-Host ("Mode       : {0}" -f $Mode)
  Write-Host ("Root       : {0}" -f (Resolve-FullPath $Root))
  Write-Host ("WorkerName : {0}" -f $WorkerName)
  Write-Host ("Count      : {0}" -f $Count)
  Write-Host ("Force      : {0}" -f $Force)
  Write-Host ("WhatIf     : {0}" -f $WhatIfPreference)
  Write-Host ("StatePath  : {0}" -f (Resolve-FullPath $StatePath))
  Write-Host ("Log        : {0}" -f $LogPath)
  Write-Host ("CSV        : {0}" -f $CsvPath)

  if(-not (Test-Path -LiteralPath $Root)){
    throw "Root not found: $Root"
  }

  $state = Load-State

  # Always prune dead instances first (keeps state honest)
  $removed = Prune-DeadInstances $state
  if($removed -gt 0){
    Add-Action "Prune" $WorkerName "OK" ("Removed {0} dead instance(s)" -f $removed)
  }

  if($Mode -eq 'CleanState'){
    # Just prune + save state
    Save-State $state
    Write-Section "CleanState complete"
  }
  elseif($Mode -eq 'Status'){
    Write-Section "Status"

    $storedCmd = ''
    $storedWd  = ''
    try { $storedCmd = [string]$state.command } catch {}
    try { $storedWd  = [string]$state.workingDir } catch {}

    Write-Host ("Definition : {0} {1}" -f $storedCmd, (($state.args -join ' ')))
    Write-Host ("WorkingDir : {0}" -f $storedWd)
    Write-Host ("Desired    : {0}" -f $state.desiredCount)

    $running = @()
    foreach($i in @($state.instances)){
      $pid = 0; try { $pid = [int]$i.pid } catch {}
      $isUp = $false
      if($pid -gt 0 -and (Get-RunningByPid $pid)){ $isUp = $true }

      $running += [pscustomobject]@{
        Tag     = [string]$i.tag
        Pid     = $pid
        Running = $isUp
        Started = [string]$i.started
        OutLog  = [string]$i.outLog
        ErrLog  = [string]$i.errLog
      }
    }

    if($running.Count -gt 0){
      $running | Sort-Object Running -Descending, Pid | Format-Table -AutoSize
    } else {
      Write-Host "(No tracked instances in state)"
    }

    # Save pruning changes (if any)
    Save-State $state
  }
  else {
    # Start/Scale/Stop/Restart
    if($Mode -in @('Stop','Restart')){
      Require-Force "Mode '$Mode'"
    }

    if($Mode -in @('Start','Scale','Restart')){
      if($Count -lt 0){ throw "Count must be >= 0" }
      $state.desiredCount = $Count
      $state = Normalize-Definition $state
    }

    $current = @($state.instances).Count

    if($Mode -eq 'Stop'){
      Write-Section "Stopping all tracked workers"
      foreach($i in @($state.instances)){
        Stop-Instance $i
      }
      # prune again after stop
      Prune-DeadInstances $state | Out-Null
      Save-State $state
    }
    elseif($Mode -eq 'Restart'){
      Write-Section "Restart"
      foreach($i in @($state.instances)){
        Stop-Instance $i
      }
      Prune-DeadInstances $state | Out-Null

      # start up to Count
      $need = $Count - @($state.instances).Count
      if($need -gt 0){
        for($n=1; $n -le $need; $n++){
          $tag = "{0}_{1}_{2}" -f $WorkerName,$Now,([Guid]::NewGuid().ToString('N').Substring(0,8))
          Start-Instance -state $state -Tag $tag | Out-Null
        }
      }

      Save-State $state
    }
    elseif($Mode -eq 'Start'){
      Write-Section "Start (ensure at least Count running)"
      # Start only if below Count; do not stop extras
      $current = @($state.instances).Count
      $need = $Count - $current
      if($need -le 0){
        Add-Action "Start" $WorkerName "SKIPPED" ("Already have {0} >= {1}" -f $current,$Count)
      } else {
        for($n=1; $n -le $need; $n++){
          $tag = "{0}_{1}_{2}" -f $WorkerName,$Now,([Guid]::NewGuid().ToString('N').Substring(0,8))
          Start-Instance -state $state -Tag $tag | Out-Null
        }
      }
      Save-State $state
    }
    elseif($Mode -eq 'Scale'){
      Write-Section "Scale (ensure exactly Count)"

      $current = @($state.instances).Count

      if($Count -lt $current){
        Require-Force "Scaling down from $current to $Count"
      }

      if($Count -eq $current){
        Add-Action "Scale" $WorkerName "OK" "Already at desired count: $Count"
      }
      elseif($Count -gt $current){
        $need = $Count - $current
        Add-Action "Scale" $WorkerName "OK" ("Scaling up: +{0}" -f $need)
        for($n=1; $n -le $need; $n++){
          $tag = "{0}_{1}_{2}" -f $WorkerName,$Now,([Guid]::NewGuid().ToString('N').Substring(0,8))
          Start-Instance -state $state -Tag $tag | Out-Null
        }
      }
      else {
        $kill = $current - $Count
        Add-Action "Scale" $WorkerName "OK" ("Scaling down: -{0}" -f $kill)

        # Stop newest first (reverse started order)
        $ordered = @($state.instances) | Sort-Object started -Descending
        $toStop = $ordered | Select-Object -First $kill
        foreach($i in $toStop){
          Stop-Instance $i
        }

        Prune-DeadInstances $state | Out-Null
      }

      Save-State $state
    }
  }

  Write-Section "Summary"
  $script:Actions | Format-Table -AutoSize Time,Action,Target,Result,Notes,Pid

  try {
    $script:Actions | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $CsvPath
    Write-Host ""
    Write-Host ("Saved CSV: {0}" -f $CsvPath)
  } catch {
    Write-Warning ("Failed to write CSV: {0}" -f $_.Exception.Message)
  }

  Write-Host ("Saved log: {0}" -f $LogPath)

  # Exit non-zero if failures/blocks happened
  $bad = $script:Actions | Where-Object { $_.Result -in @('FAILED','BLOCKED') }
  if($bad -and $bad.Count -gt 0){ exit 1 } else { exit 0 }

} catch {
  Write-Host ""
  Write-Host ("ERROR: {0}" -f $_.Exception.Message) -ForegroundColor Red
  throw
} finally {
  try { Stop-Transcript | Out-Null } catch {}
}
