<#
C:\Francis\scripts\ollama-reset.ps1

Purpose
  Reset Ollama on Windows in a controlled way:
    - Soft: stop Ollama processes/services (non-destructive)
    - PurgeModels: delete models directory (destructive)
    - LogsOnly: delete %LOCALAPPDATA%\Ollama (destructive-ish)
    - Hard: delete config (.ollama) + appdata (%LOCALAPPDATA%\Ollama) + models
    - Uninstall: Hard + remove binaries (%LOCALAPPDATA%\Programs\Ollama) + optional clear OLLAMA_MODELS env var

Enhancements in this drop
  - Exports a CSV report of actions to: <Root>\data\logs\operations\ollama_reset_<timestamp>.csv
  - Adds API health check (before/after): http://127.0.0.1:11434/api/tags
  - Lists installed models (before/after) via API or `ollama list`
  - Tightens safety heuristic: NO longer treats any generic "\models" folder as "safe" by default.
    If your OLLAMA_MODELS points to a non-ollama-looking folder, use -OverrideSafety to delete it.

Usage examples
  .\ollama-reset.ps1
  .\ollama-reset.ps1 -Restart
  .\ollama-reset.ps1 -Mode PurgeModels -Force
  .\ollama-reset.ps1 -Mode LogsOnly -Force
  .\ollama-reset.ps1 -Mode Hard -Force
  .\ollama-reset.ps1 -Mode Uninstall -Force -ClearEnvModelsPath

Notes
  - Supports -WhatIf and -Confirm (via ShouldProcess).
  - Includes safety rails to prevent deleting dangerous paths (e.g., C:\, C:\Windows).
  - Writes a transcript log to: <Root>\data\logs\operations\ollama_reset_<timestamp>.log
#>

[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
param(
  [ValidateSet('Soft','PurgeModels','LogsOnly','Hard','Uninstall')]
  [string]$Mode = 'Soft',

  # If set, tries to restart Ollama after completing the selected reset mode.
  [switch]$Restart,

  # Required for destructive modes (PurgeModels, LogsOnly, Hard, Uninstall).
  [switch]$Force,

  # If set (usually with Uninstall), clears OLLAMA_MODELS env var at the User scope.
  [switch]$ClearEnvModelsPath,

  # Only needed if you intentionally set OLLAMA_MODELS to a "non-ollama-looking" directory
  # and still want this script to delete it. (Still blocks drive roots/system folders.)
  [switch]$OverrideSafety,

  # Script logging root
  [string]$Root = 'C:\Francis',

  # If Ollama is installed as a Windows service under a custom name, add it here.
  [string[]]$ServiceNames = @('Ollama','ollama'),

  # Process names to stop
  [string[]]$ProcessNames = @('ollama','Ollama'),

  # API timeout seconds for health checks
  [ValidateRange(1,30)]
  [int]$ApiTimeoutSec = 3,

  # After restart, how long (seconds) to wait/poll for API to come up (0 = don't wait)
  [ValidateRange(0,120)]
  [int]$ApiWaitSec = 8
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

# ---------- Logging ----------
$Now   = Get-Date -Format "yyyyMMdd_HHmmss"
$OutDir = Join-Path $Root "data\logs\operations"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$LogPath = Join-Path $OutDir "ollama_reset_$Now.log"
$CsvPath = Join-Path $OutDir "ollama_reset_$Now.csv"

$script:Actions = New-Object System.Collections.Generic.List[object]

function Add-Action {
  param(
    [string]$Action,
    [string]$Target,
    [string]$Result,
    [string]$Notes = ""
  )
  $script:Actions.Add([pscustomobject]@{
    Time   = (Get-Date)
    Action = $Action
    Target = $Target
    Result = $Result
    Notes  = $Notes
  }) | Out-Null
}

function Write-Section([string]$Title){
  Write-Host ""
  Write-Host ("=" * 72)
  Write-Host $Title
  Write-Host ("=" * 72)
}

function Get-EnvVar([string]$Name){
  # Prefer User scope, fall back to Machine
  $u = [Environment]::GetEnvironmentVariable($Name,'User')
  if($u -and $u.Trim().Length -gt 0){ return $u }
  $m = [Environment]::GetEnvironmentVariable($Name,'Machine')
  if($m -and $m.Trim().Length -gt 0){ return $m }
  return $null
}

function Resolve-FullPath([string]$Path){
  try {
    $rp = Resolve-Path -LiteralPath $Path -ErrorAction Stop
    return $rp.Path
  } catch {
    # If it doesn't exist yet, normalize as best we can
    try { return [System.IO.Path]::GetFullPath($Path) } catch { return $Path }
  }
}

function Test-DangerousPath([string]$Path){
  $p = (Resolve-FullPath $Path)

  # Block drive roots like C:\ or D:\
  if($p -match '^[A-Za-z]:\\$'){ return $true }

  # Block some obvious system locations
  $blocked = @(
    ($env:SystemRoot),
    (Join-Path $env:SystemDrive '\Windows'),
    (Join-Path $env:SystemDrive '\Program Files'),
    (Join-Path $env:SystemDrive '\Program Files (x86)'),
    (Join-Path $env:SystemDrive '\ProgramData')
  ) | ForEach-Object { Resolve-FullPath $_ }

  foreach($b in $blocked){
    if($p.TrimEnd('\') -ieq $b.TrimEnd('\')){ return $true }
  }

  return $false
}

function Test-PathLooksLikeOllamaData([string]$Path){
  # Tightened heuristic:
  # Only allow if path includes a directory segment ".ollama" or "ollama".
  # (No longer whitelists arbitrary "\models" paths.)
  $p  = (Resolve-FullPath $Path)
  $pl = ($p -as [string]).ToLowerInvariant()

  if($pl -match '(\\|/)\.ollama(\\|/|$)'){ return $true }
  if($pl -match '(\\|/)ollama(\\|/|$)'){ return $true }

  return $false
}

function Remove-PathSafe {
  param(
    [Parameter(Mandatory=$true)][string]$Path,
    [string]$Label = "Path"
  )

  $full = Resolve-FullPath $Path

  if(-not (Test-Path -LiteralPath $full)){
    Add-Action "Remove" $full "SKIPPED" "$Label not found"
    return
  }

  if(Test-DangerousPath $full){
    $msg = "Refusing to delete dangerous path: $full"
    Add-Action "Remove" $full "BLOCKED" $msg
    throw $msg
  }

  if(-not $OverrideSafety){
    if(-not (Test-PathLooksLikeOllamaData $full)){
      $msg = "Safety block: path does not look like Ollama data. Use -OverrideSafety if intentional. Path: $full"
      Add-Action "Remove" $full "BLOCKED" $msg
      throw $msg
    }
  }

  if($PSCmdlet.ShouldProcess($full, "Delete $Label")){
    try {
      # Retry loop for transient locks
      $max = 3
      for($i=1; $i -le $max; $i++){
        try {
          Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction Stop
          Add-Action "Remove" $full "OK" "$Label deleted"
          return
        } catch {
          if($i -eq $max){ throw }
          Start-Sleep -Seconds 1
        }
      }
    } catch {
      Add-Action "Remove" $full "FAILED" $_.Exception.Message
      throw
    }
  } else {
    Add-Action "Remove" $full "WHATIF/SKIPPED" "$Label deletion not approved"
  }
}

function Get-OllamaExe {
  try {
    $cmd = Get-Command ollama -ErrorAction SilentlyContinue
    if($cmd -and $cmd.Source){ return $cmd.Source }
  } catch {}

  $c1 = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
  if(Test-Path -LiteralPath $c1){ return $c1 }

  $c2 = Join-Path $env:ProgramFiles "Ollama\ollama.exe"
  if(Test-Path -LiteralPath $c2){ return $c2 }

  $c3 = Join-Path ${env:ProgramFiles(x86)} "Ollama\ollama.exe"
  if($c3 -and (Test-Path -LiteralPath $c3)){ return $c3 }

  return $null
}

function Test-OllamaApi {
  param([int]$Timeout = 2)
  try{
    $null = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec $Timeout
    return $true
  } catch {
    return $false
  }
}

function Wait-OllamaApiUp {
  param([int]$WaitSec, [int]$TimeoutSec)

  if($WaitSec -le 0){ return (Test-OllamaApi -Timeout $TimeoutSec) }

  $deadline = (Get-Date).AddSeconds($WaitSec)
  do {
    if(Test-OllamaApi -Timeout $TimeoutSec){ return $true }
    Start-Sleep -Milliseconds 500
  } while((Get-Date) -lt $deadline)

  return $false
}

function Get-InstalledModels {
  param([string]$OllamaExe)

  $names = New-Object System.Collections.Generic.HashSet[string] ([StringComparer]::OrdinalIgnoreCase)

  if(Test-OllamaApi -Timeout 2){
    try{
      $tags = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3
      if($tags -and $tags.models){
        foreach($m in $tags.models){
          if($m.name){ [void]$names.Add([string]$m.name) }
        }
      }
      return $names
    } catch { }
  }

  if($OllamaExe){
    try{
      $out = & $OllamaExe list 2>$null
      foreach($line in ($out -split "`r?`n")){
        $t = $line.Trim()
        if(-not $t){ continue }
        if($t -match '^(NAME|MODEL)\s+'){ continue }
        $first = ($t -split '\s+')[0]
        if($first){ [void]$names.Add($first) }
      }
    } catch { }
  }

  return $names
}

function Stop-Ollama {
  Write-Section "Stopping Ollama (services + processes)"

  foreach($svcName in $ServiceNames){
    try {
      $svc = Get-Service -Name $svcName -ErrorAction SilentlyContinue
      if($null -ne $svc){
        if($svc.Status -ne 'Stopped'){
          if($PSCmdlet.ShouldProcess("Service $svcName", "Stop")){
            Stop-Service -Name $svcName -Force -ErrorAction SilentlyContinue
            Add-Action "Stop-Service" $svcName "OK" "Stop requested"
          } else {
            Add-Action "Stop-Service" $svcName "WHATIF/SKIPPED" "Not approved"
          }
        } else {
          Add-Action "Stop-Service" $svcName "SKIPPED" "Already stopped"
        }
      }
    } catch {
      Add-Action "Stop-Service" $svcName "FAILED" $_.Exception.Message
    }
  }

  foreach($pn in $ProcessNames){
    try {
      $procs = Get-Process -Name $pn -ErrorAction SilentlyContinue
      if($procs){
        foreach($p in $procs){
          if($PSCmdlet.ShouldProcess("Process $($p.Name) (PID $($p.Id))", "Stop")){
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            Add-Action "Stop-Process" "$($p.Name) (PID $($p.Id))" "OK" "Stop requested"
          } else {
            Add-Action "Stop-Process" "$($p.Name) (PID $($p.Id))" "WHATIF/SKIPPED" "Not approved"
          }
        }
      } else {
        Add-Action "Stop-Process" $pn "SKIPPED" "Not running"
      }
    } catch {
      Add-Action "Stop-Process" $pn "FAILED" $_.Exception.Message
    }
  }

  # Small pause to release locks
  Start-Sleep -Milliseconds 500
}

function Start-Ollama {
  Write-Section "Restarting Ollama"

  # Prefer service restart if a service exists
  foreach($svcName in $ServiceNames){
    try {
      $svc = Get-Service -Name $svcName -ErrorAction SilentlyContinue
      if($null -ne $svc){
        if($svc.Status -ne 'Running'){
          if($PSCmdlet.ShouldProcess("Service $svcName", "Start")){
            Start-Service -Name $svcName -ErrorAction SilentlyContinue
            Add-Action "Start-Service" $svcName "OK" "Start requested"
            return
          } else {
            Add-Action "Start-Service" $svcName "WHATIF/SKIPPED" "Not approved"
          }
        } else {
          Add-Action "Start-Service" $svcName "SKIPPED" "Already running"
          return
        }
      }
    } catch {
      Add-Action "Start-Service" $svcName "FAILED" $_.Exception.Message
    }
  }

  # Fallback: start `ollama serve` if CLI exists
  $ollamaCmd = Get-OllamaExe

  if($ollamaCmd){
    if($PSCmdlet.ShouldProcess($ollamaCmd, "Start 'ollama serve'")){
      try{
        Start-Process -FilePath $ollamaCmd -ArgumentList @('serve') -WindowStyle Hidden | Out-Null
        Add-Action "Start-Process" $ollamaCmd "OK" "Started: ollama serve"
      } catch {
        Add-Action "Start-Process" $ollamaCmd "FAILED" $_.Exception.Message
        throw
      }
    } else {
      Add-Action "Start-Process" $ollamaCmd "WHATIF/SKIPPED" "Not approved"
    }
  } else {
    Add-Action "Start-Ollama" "(none)" "SKIPPED" "Could not find ollama.exe. Start Ollama manually."
  }
}

function Require-ForceForDestructive {
  param([string]$ForMode)
  $destructive = @('PurgeModels','LogsOnly','Hard','Uninstall')
  if($destructive -contains $ForMode){
    if(-not $Force){
      $msg = "Mode '$ForMode' is destructive. Re-run with -Force (and optionally -WhatIf first)."
      Add-Action "Guard" $ForMode "BLOCKED" $msg
      throw $msg
    }
  }
}

# ---------- Main ----------
try {
  Start-Transcript -Path $LogPath -Force | Out-Null

  Write-Section "Ollama Reset Script"
  Write-Host "Mode      : $Mode"
  Write-Host "Restart   : $Restart"
  Write-Host "Force     : $Force"
  Write-Host "Override  : $OverrideSafety"
  Write-Host "WhatIf    : $($WhatIfPreference)"
  Write-Host "Log       : $LogPath"
  Write-Host "CSV       : $CsvPath"

  Require-ForceForDestructive -ForMode $Mode

  # Resolve paths
  $configDir  = Join-Path $env:USERPROFILE ".ollama"
  $appDataDir = Join-Path $env:LOCALAPPDATA "Ollama"
  $binDir     = Join-Path $env:LOCALAPPDATA "Programs\Ollama"

  $envModels = Get-EnvVar "OLLAMA_MODELS"
  $modelsDir = if($envModels){ $envModels } else { Join-Path $configDir "models" }

  $ollamaExe = Get-OllamaExe

  Write-Section "Resolved Paths"
  Write-Host ("OllamaExe : {0}" -f ($ollamaExe ? (Resolve-FullPath $ollamaExe) : "(not found)"))
  Write-Host ("ConfigDir : {0}" -f (Resolve-FullPath $configDir))
  Write-Host ("ModelsDir : {0}" -f (Resolve-FullPath $modelsDir))
  Write-Host ("AppData   : {0}" -f (Resolve-FullPath $appDataDir))
  Write-Host ("BinDir    : {0}" -f (Resolve-FullPath $binDir))
  if($envModels){
    Write-Host ("OLLAMA_MODELS is set to: {0}" -f $envModels)
  } else {
    Write-Host "OLLAMA_MODELS is not set (using default models location under .ollama)."
  }

  if($ollamaExe){
    try {
      $ver = & $ollamaExe --version 2>$null
      if($ver){ Add-Action "Version" $ollamaExe "OK" (($ver | Select-Object -First 1) -as [string]) }
    } catch {
      Add-Action "Version" $ollamaExe "WARN" "ollama --version failed"
    }
  } else {
    Add-Action "Locate" "ollama.exe" "WARN" "Not found in PATH/common locations"
  }

  # Pre: API + models
  Write-Section "Pre-Check (API + Installed Models)"
  $apiBefore = Test-OllamaApi -Timeout $ApiTimeoutSec
  Add-Action "API" "Before" ($(if($apiBefore){"UP"}else{"DOWN"})) "http://127.0.0.1:11434/api/tags"

  Write-Host ("API before : {0}" -f ($(if($apiBefore){"reachable"}else{"NOT reachable"})))

  $modelsBefore = Get-InstalledModels -OllamaExe $ollamaExe
  Write-Host "Installed models (before):"
  if($modelsBefore.Count -gt 0){
    $modelsBefore | Sort-Object | ForEach-Object { "  - $_" } | Write-Host
  } else {
    Write-Host "  (none found or unable to list)"
  }
  Add-Action "Models" "Before" "INFO" ("Count={0}" -f $modelsBefore.Count)

  # Stop first (always)
  Stop-Ollama

  Write-Section "Applying Reset Mode: $Mode"

  switch($Mode){
    'Soft' {
      Add-Action "Mode" $Mode "OK" "Stopped Ollama only"
    }

    'PurgeModels' {
      Remove-PathSafe -Path $modelsDir -Label "Models directory"
      Add-Action "Mode" $Mode "OK" "Models purged"
    }

    'LogsOnly' {
      Remove-PathSafe -Path $appDataDir -Label "AppData (logs/runtime) directory"
      Add-Action "Mode" $Mode "OK" "AppData purged"
    }

    'Hard' {
      Remove-PathSafe -Path $appDataDir -Label "AppData (logs/runtime) directory"

      $fullModels = Resolve-FullPath $modelsDir
      $fullConfig = Resolve-FullPath $configDir
      $modelsInsideConfig = $false
      try { $modelsInsideConfig = $fullModels.ToLowerInvariant().StartsWith($fullConfig.ToLowerInvariant() + "\") } catch {}

      if(-not $modelsInsideConfig){
        Remove-PathSafe -Path $modelsDir -Label "Models directory"
      } else {
        Add-Action "Remove" $fullModels "SKIPPED" "Models are inside ConfigDir; will be removed with ConfigDir"
      }

      Remove-PathSafe -Path $configDir -Label "Config (.ollama) directory"
      Add-Action "Mode" $Mode "OK" "Hard reset complete"
    }

    'Uninstall' {
      Remove-PathSafe -Path $appDataDir -Label "AppData (logs/runtime) directory"

      $fullModels = Resolve-FullPath $modelsDir
      $fullConfig = Resolve-FullPath $configDir
      $modelsInsideConfig = $false
      try { $modelsInsideConfig = $fullModels.ToLowerInvariant().StartsWith($fullConfig.ToLowerInvariant() + "\") } catch {}

      if(-not $modelsInsideConfig){
        Remove-PathSafe -Path $modelsDir -Label "Models directory"
      } else {
        Add-Action "Remove" $fullModels "SKIPPED" "Models are inside ConfigDir; will be removed with ConfigDir"
      }

      Remove-PathSafe -Path $configDir -Label "Config (.ollama) directory"
      Remove-PathSafe -Path $binDir -Label "Binaries directory (%LOCALAPPDATA%\Programs\Ollama)"

      if($ClearEnvModelsPath){
        if($PSCmdlet.ShouldProcess("EnvVar OLLAMA_MODELS (User)", "Clear")){
          try{
            [Environment]::SetEnvironmentVariable("OLLAMA_MODELS",$null,'User')
            Add-Action "Clear-EnvVar" "OLLAMA_MODELS (User)" "OK" "Cleared"
          } catch {
            Add-Action "Clear-EnvVar" "OLLAMA_MODELS (User)" "FAILED" $_.Exception.Message
            throw
          }
        } else {
          Add-Action "Clear-EnvVar" "OLLAMA_MODELS (User)" "WHATIF/SKIPPED" "Not approved"
        }
      }

      Add-Action "Mode" $Mode "OK" "Uninstall cleanup complete"
    }
  }

  if($Restart){
    Start-Ollama

    # Optional wait for API
    $apiUp = Wait-OllamaApiUp -WaitSec $ApiWaitSec -TimeoutSec $ApiTimeoutSec
    Add-Action "API" "AfterRestart" ($(if($apiUp){"UP"}else{"DOWN"})) ("Waited={0}s" -f $ApiWaitSec)
  }

  # Post: API + models
  Write-Section "Post-Check (API + Installed Models)"
  $apiAfter = Test-OllamaApi -Timeout $ApiTimeoutSec
  Add-Action "API" "After" ($(if($apiAfter){"UP"}else{"DOWN"})) "http://127.0.0.1:11434/api/tags"

  Write-Host ("API after  : {0}" -f ($(if($apiAfter){"reachable"}else{"NOT reachable"})))

  $modelsAfter = Get-InstalledModels -OllamaExe $ollamaExe
  Write-Host "Installed models (after):"
  if($modelsAfter.Count -gt 0){
    $modelsAfter | Sort-Object | ForEach-Object { "  - $_" } | Write-Host
  } else {
    Write-Host "  (none found or unable to list)"
  }
  Add-Action "Models" "After" "INFO" ("Count={0}" -f $modelsAfter.Count)

  Write-Section "Summary"
  $script:Actions | Sort-Object Time | Format-Table -AutoSize Time,Action,Target,Result,Notes

  # Export CSV report
  try {
    $script:Actions | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $CsvPath
    Write-Host ""
    Write-Host ("Saved CSV: {0}" -f $CsvPath)
  } catch {
    Write-Warning "Could not export CSV: $($_.Exception.Message)"
  }

  Write-Host ("Saved log: {0}" -f $LogPath)

} catch {
  Write-Host ""
  Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
  throw
} finally {
  try { Stop-Transcript | Out-Null } catch {}
}
