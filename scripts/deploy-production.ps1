<#
  deploy-production.ps1 (Full Drop)

  Purpose:
    Deploy a new "release" into a stable "current" directory with rollback, logging, and optional restarts.

  Layout (defaults):
    C:\Francis\
      app\
        current\                (active)
        releases\               (timestamped staged releases)
        backups\                (previous currents)
      data\logs\operations\     (logs/reports)

  Source types:
    - Zip:    -SourceType Zip    -Source <path-to-zip>
    - Folder: -SourceType Folder -Source <path-to-folder>
    - Git:    -SourceType Git    -Source <repo-url-or-local-path> (requires git)

  Examples:
    # Deploy from zip:
    powershell -ExecutionPolicy Bypass -File C:\Francis\scripts\deploy-production.ps1 `
      -SourceType Zip -Source C:\Francis\staging\build.zip -ServiceName "FrancisSvc" `
      -HealthUrl "http://localhost:8080/health"

    # Deploy from folder (robocopy):
    powershell -ExecutionPolicy Bypass -File C:\Francis\scripts\deploy-production.ps1 `
      -SourceType Folder -Source C:\Francis\staging\build -IISSiteName "Francis" `
      -HealthUrl "http://localhost/health"

    # Dry run:
    powershell -ExecutionPolicy Bypass -File C:\Francis\scripts\deploy-production.ps1 `
      -SourceType Zip -Source C:\temp\build.zip -WhatIf

#>

[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
param(
  [Parameter()][string]$Root = "C:\Francis",

  [Parameter(Mandatory=$true)]
  [ValidateSet("Zip","Folder","Git")]
  [string]$SourceType,

  [Parameter(Mandatory=$true)]
  [string]$Source,

  # Deployment directories
  [Parameter()][string]$AppRoot = "",          # default: <Root>\app
  [Parameter()][string]$CurrentDirName = "current",
  [Parameter()][string]$ReleasesDirName = "releases",
  [Parameter()][string]$BackupsDirName  = "backups",

  # Logging / reports
  [Parameter()][string]$LogDir = "",           # default: <Root>\data\logs\operations
  [Parameter()][string]$Tag = "production",

  # Optional commands to run inside the staged release BEFORE swap (e.g., npm ci/build)
  [Parameter()][string[]]$PreSwapCommands = @(),

  # Optional commands to run in the NEW current AFTER swap (e.g., migrations)
  [Parameter()][string[]]$PostSwapCommands = @(),

  # Service / IIS restart controls (optional)
  [Parameter()][string]$ServiceName = "",
  [Parameter()][string]$IISSiteName = "",
  [Parameter()][string]$IISAppPoolName = "",

  # Health check (optional)
  [Parameter()][string]$HealthUrl = "",
  [Parameter()][int]$HealthTimeoutSec = 60,
  [Parameter()][int]$HealthIntervalSec = 3,

  # Retention
  [Parameter()][int]$KeepBackups  = 5,
  [Parameter()][int]$KeepReleases = 5,

  # Safety / behavior
  [Parameter()][switch]$SkipStopStart,
  [Parameter()][switch]$FailIfHealthCheckFails
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# -----------------------------
# Helpers
# -----------------------------
function Resolve-FSPath([string]$p) {
  try { return (Resolve-Path -LiteralPath $p -ErrorAction Stop).ProviderPath } catch { return $p }
}

function New-Dir([string]$p) {
  if (-not (Test-Path -LiteralPath $p)) {
    New-Item -ItemType Directory -Force -Path $p | Out-Null
  }
}

function Test-IsAdmin {
  try {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
  } catch { return $false }
}

function Write-Log {
  param(
    [Parameter(Mandatory=$true)][string]$Message,
    [ValidateSet("INFO","WARN","ERROR","STEP","OK")][string]$Level = "INFO"
  )
  $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
  $line = "[{0}] [{1}] {2}" -f $ts, $Level, $Message
  Write-Host $line
  if ($script:LogFile) { Add-Content -LiteralPath $script:LogFile -Value $line -Encoding UTF8 }
}

function Invoke-External {
  param(
    [Parameter(Mandatory=$true)][string]$FilePath,
    [Parameter()][string[]]$Arguments = @(),
    [Parameter()][string]$WorkingDirectory = ""
  )
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $FilePath
  $psi.Arguments = ($Arguments -join " ")
  if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) { $psi.WorkingDirectory = $WorkingDirectory }
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError  = $true
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true

  $p = New-Object System.Diagnostics.Process
  $p.StartInfo = $psi

  $null = $p.Start()
  $stdout = $p.StandardOutput.ReadToEnd()
  $stderr = $p.StandardError.ReadToEnd()
  $p.WaitForExit()

  return [pscustomobject]@{
    ExitCode = $p.ExitCode
    StdOut   = $stdout
    StdErr   = $stderr
  }
}

function Invoke-PSCommandLine {
  param(
    [Parameter(Mandatory=$true)][string]$CommandLine,
    [Parameter(Mandatory=$true)][string]$WorkingDirectory
  )
  # Runs via powershell.exe so command-lines like "npm ci" work without parsing headaches.
  $pwsh = (Get-Command powershell -ErrorAction SilentlyContinue).Source
  if (-not $pwsh) { throw "powershell.exe not found in PATH." }

  $args = @("-NoProfile","-ExecutionPolicy","Bypass","-Command", $CommandLine)
  $r = Invoke-External -FilePath $pwsh -Arguments $args -WorkingDirectory $WorkingDirectory

  if ($r.StdOut) { Write-Log $r.StdOut.TrimEnd() "INFO" }
  if ($r.StdErr) { Write-Log $r.StdErr.TrimEnd() "WARN" }

  if ($r.ExitCode -ne 0) {
    throw "Command failed (exit $($r.ExitCode)): $CommandLine"
  }
}

function Stop-Targets {
  if ($SkipStopStart) { Write-Log "SkipStopStart set; not stopping targets." "WARN"; return }

  if (-not [string]::IsNullOrWhiteSpace($ServiceName)) {
    Write-Log ("Stopping service: {0}" -f $ServiceName) "STEP"
    if ($PSCmdlet.ShouldProcess($ServiceName, "Stop-Service")) {
      try {
        Stop-Service -Name $ServiceName -Force -ErrorAction Stop
        Write-Log ("Service stopped: {0}" -f $ServiceName) "OK"
      } catch {
        throw "Failed to stop service '$ServiceName': $($_.Exception.Message)"
      }
    }
  }

  if (-not [string]::IsNullOrWhiteSpace($IISSiteName) -or -not [string]::IsNullOrWhiteSpace($IISAppPoolName)) {
    Write-Log "Stopping IIS targets (site/app pool)..." "STEP"
    if (-not (Test-IsAdmin)) {
      Write-Log "Not running as Administrator. IIS stop/start may fail." "WARN"
    }

    if ($PSCmdlet.ShouldProcess("IIS", "Stop website/app pool")) {
      try {
        Import-Module WebAdministration -ErrorAction Stop

        if (-not [string]::IsNullOrWhiteSpace($IISSiteName)) {
          try { Stop-Website -Name $IISSiteName -ErrorAction Stop; Write-Log ("Website stopped: {0}" -f $IISSiteName) "OK" } catch { throw }
        }
        if (-not [string]::IsNullOrWhiteSpace($IISAppPoolName)) {
          try { Stop-WebAppPool -Name $IISAppPoolName -ErrorAction Stop; Write-Log ("AppPool stopped: {0}" -f $IISAppPoolName) "OK" } catch { throw }
        }
      } catch {
        throw "Failed to stop IIS target(s): $($_.Exception.Message)"
      }
    }
  }
}

function Start-Targets {
  if ($SkipStopStart) { Write-Log "SkipStopStart set; not starting targets." "WARN"; return }

  if (-not [string]::IsNullOrWhiteSpace($IISAppPoolName) -or -not [string]::IsNullOrWhiteSpace($IISSiteName)) {
    Write-Log "Starting IIS targets (site/app pool)..." "STEP"
    if ($PSCmdlet.ShouldProcess("IIS", "Start website/app pool")) {
      try {
        Import-Module WebAdministration -ErrorAction Stop

        if (-not [string]::IsNullOrWhiteSpace($IISAppPoolName)) {
          Start-WebAppPool -Name $IISAppPoolName -ErrorAction Stop
          Write-Log ("AppPool started: {0}" -f $IISAppPoolName) "OK"
        }
        if (-not [string]::IsNullOrWhiteSpace($IISSiteName)) {
          Start-Website -Name $IISSiteName -ErrorAction Stop
          Write-Log ("Website started: {0}" -f $IISSiteName) "OK"
        }
      } catch {
        throw "Failed to start IIS target(s): $($_.Exception.Message)"
      }
    }
  }

  if (-not [string]::IsNullOrWhiteSpace($ServiceName)) {
    Write-Log ("Starting service: {0}" -f $ServiceName) "STEP"
    if ($PSCmdlet.ShouldProcess($ServiceName, "Start-Service")) {
      try {
        Start-Service -Name $ServiceName -ErrorAction Stop
        Write-Log ("Service started: {0}" -f $ServiceName) "OK"
      } catch {
        throw "Failed to start service '$ServiceName': $($_.Exception.Message)"
      }
    }
  }
}

function Test-Health {
  if ([string]::IsNullOrWhiteSpace($HealthUrl)) { return $true }

  Write-Log ("Health check: {0}" -f $HealthUrl) "STEP"
  $deadline = (Get-Date).AddSeconds($HealthTimeoutSec)

  while ((Get-Date) -lt $deadline) {
    try {
      # PS 5.1 needs -UseBasicParsing to avoid IE dependency issues
      $resp = $null
      try {
        $resp = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
      } catch {
        # Some environments still allow without -UseBasicParsing
        $resp = Invoke-WebRequest -Uri $HealthUrl -TimeoutSec 10 -ErrorAction Stop
      }

      if ($resp -and $resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300) {
        Write-Log ("Health OK (HTTP {0})" -f $resp.StatusCode) "OK"
        return $true
      }
      Write-Log ("Health not OK yet (HTTP {0})" -f $resp.StatusCode) "WARN"
    } catch {
      Write-Log ("Health check failed: {0}" -f $_.Exception.Message) "WARN"
    }

    Start-Sleep -Seconds $HealthIntervalSec
  }

  Write-Log ("Health check timed out after {0}s" -f $HealthTimeoutSec) "ERROR"
  return $false
}

function Copy-FolderRobust {
  param(
    [Parameter(Mandatory=$true)][string]$From,
    [Parameter(Mandatory=$true)][string]$To
  )

  # Prefer robocopy (handles long paths / retries better)
  $rc = (Get-Command robocopy -ErrorAction SilentlyContinue).Source
  if ($rc) {
    # /MIR is dangerous; we are copying into empty staged directory, so use /E.
    $args = @(
      "`"$From`"",
      "`"$To`"",
      "/E",
      "/R:2",
      "/W:2",
      "/NFL","/NDL","/NP"
    )
    $r = Invoke-External -FilePath $rc -Arguments $args

    # Robocopy exit codes: 0-7 are typically success-ish; >=8 indicates failures
    if ($r.ExitCode -ge 8) {
      if ($r.StdOut) { Write-Log $r.StdOut.TrimEnd() "INFO" }
      if ($r.StdErr) { Write-Log $r.StdErr.TrimEnd() "WARN" }
      throw "Robocopy failed with exit code $($r.ExitCode)."
    }
    return
  }

  # Fallback
  Copy-Item -LiteralPath $From\* -Destination $To -Recurse -Force -ErrorAction Stop
}

function Prune-OldDirs {
  param(
    [Parameter(Mandatory=$true)][string]$Dir,
    [Parameter(Mandatory=$true)][int]$Keep
  )
  if (-not (Test-Path -LiteralPath $Dir)) { return }
  if ($Keep -lt 0) { return }

  $items = Get-ChildItem -LiteralPath $Dir -Directory -Force -ErrorAction SilentlyContinue |
           Sort-Object LastWriteTime -Descending

  $toRemove = $items | Select-Object -Skip $Keep
  foreach ($d in $toRemove) {
    try {
      Write-Log ("Pruning old dir: {0}" -f $d.FullName) "INFO"
      if ($PSCmdlet.ShouldProcess($d.FullName, "Remove-Item -Recurse -Force")) {
        Remove-Item -LiteralPath $d.FullName -Recurse -Force -ErrorAction Stop
      }
    } catch {
      Write-Log ("Failed to prune {0}: {1}" -f $d.FullName, $_.Exception.Message) "WARN"
    }
  }
}

# -----------------------------
# Initialize paths/logging
# -----------------------------
$RootResolved = Resolve-FSPath $Root
if ([string]::IsNullOrWhiteSpace($AppRoot)) { $AppRoot = Join-Path $RootResolved "app" }
if ([string]::IsNullOrWhiteSpace($LogDir))  { $LogDir  = Join-Path $RootResolved "data\logs\operations" }

New-Dir $AppRoot
New-Dir $LogDir

$Now = Get-Date -Format "yyyyMMdd_HHmmss"
$ReleasesDir = Join-Path $AppRoot $ReleasesDirName
$BackupsDir  = Join-Path $AppRoot $BackupsDirName
$CurrentDir  = Join-Path $AppRoot $CurrentDirName
New-Dir $ReleasesDir
New-Dir $BackupsDir

$script:LogFile = Join-Path $LogDir ("deploy_{0}_{1}.log" -f $Tag, $Now)
$ReportJson     = Join-Path $LogDir ("deploy_{0}_{1}.json" -f $Tag, $Now)
$ReportCsv      = Join-Path $LogDir ("deploy_{0}_{1}.csv" -f $Tag, $Now)

$ops = New-Object System.Collections.Generic.List[object]
function Add-Op($step,$status,$detail) {
  $ops.Add([pscustomobject]@{
    Time   = (Get-Date)
    Step   = $step
    Status = $status
    Detail = $detail
  }) | Out-Null
}

Write-Log ("Deploy start. Root={0} AppRoot={1} SourceType={2} Source={3}" -f $RootResolved, $AppRoot, $SourceType, $Source) "STEP"
Add-Op "start" "OK" ("Root={0}; AppRoot={1}; SourceType={2}; Source={3}" -f $RootResolved, $AppRoot, $SourceType, $Source)

# -----------------------------
# Stage new release
# -----------------------------
$NewReleaseDir = Join-Path $ReleasesDir ("{0}_{1}" -f $Now, $Tag)
$BackupDir     = Join-Path $BackupsDir  ("{0}_{1}" -f $Now, $Tag)

if ($PSCmdlet.ShouldProcess($NewReleaseDir, "Create staged release directory")) {
  New-Dir $NewReleaseDir
}

try {
  Write-Log ("Staging release to: {0}" -f $NewReleaseDir) "STEP"
  Add-Op "stage_begin" "OK" $NewReleaseDir

  switch ($SourceType) {
    "Zip" {
      $zipPath = Resolve-FSPath $Source
      if (-not (Test-Path -LiteralPath $zipPath)) { throw "Zip source not found: $zipPath" }

      Write-Log ("Expanding zip: {0}" -f $zipPath) "INFO"
      if ($PSCmdlet.ShouldProcess($zipPath, "Expand-Archive to $NewReleaseDir")) {
        Expand-Archive -LiteralPath $zipPath -DestinationPath $NewReleaseDir -Force
      }
      Add-Op "stage_zip" "OK" $zipPath
    }

    "Folder" {
      $srcFolder = Resolve-FSPath $Source
      if (-not (Test-Path -LiteralPath $srcFolder)) { throw "Folder source not found: $srcFolder" }

      Write-Log ("Copying folder: {0}" -f $srcFolder) "INFO"
      if ($PSCmdlet.ShouldProcess($srcFolder, "Copy to $NewReleaseDir")) {
        Copy-FolderRobust -From $srcFolder -To $NewReleaseDir
      }
      Add-Op "stage_folder" "OK" $srcFolder
    }

    "Git" {
      $git = (Get-Command git -ErrorAction SilentlyContinue).Source
      if (-not $git) { throw "git not found in PATH. Install Git or use -SourceType Zip/Folder." }

      # If source is local path and exists, copy it; if it looks like URL, clone it.
      $looksLocal = $false
      try { $looksLocal = Test-Path -LiteralPath $Source } catch { $looksLocal = $false }

      if ($looksLocal) {
        $srcRepo = Resolve-FSPath $Source
        Write-Log ("Copying local repo folder: {0}" -f $srcRepo) "INFO"
        if ($PSCmdlet.ShouldProcess($srcRepo, "Copy repo to $NewReleaseDir")) {
          Copy-FolderRobust -From $srcRepo -To $NewReleaseDir
        }
        Add-Op "stage_git_localcopy" "OK" $srcRepo
      } else {
        Write-Log ("Cloning repo: {0}" -f $Source) "INFO"
        if ($PSCmdlet.ShouldProcess($Source, "git clone to $NewReleaseDir")) {
          $r = Invoke-External -FilePath $git -Arguments @("clone","--depth","1",$Source,"`"$NewReleaseDir`"")
          if ($r.StdOut) { Write-Log $r.StdOut.TrimEnd() "INFO" }
          if ($r.StdErr) { Write-Log $r.StdErr.TrimEnd() "WARN" }
          if ($r.ExitCode -ne 0) { throw "git clone failed (exit $($r.ExitCode))" }
        }
        Add-Op "stage_git_clone" "OK" $Source
      }
    }
  }

  # -----------------------------
  # Pre-swap commands
  # -----------------------------
  if ($PreSwapCommands -and $PreSwapCommands.Count -gt 0) {
    Write-Log "Running PreSwapCommands..." "STEP"
    foreach ($cmd in $PreSwapCommands) {
      if ([string]::IsNullOrWhiteSpace($cmd)) { continue }
      Write-Log ("PreSwap: {0}" -f $cmd) "INFO"
      Add-Op "preswap_cmd" "RUN" $cmd
      if ($PSCmdlet.ShouldProcess($NewReleaseDir, "Run PreSwap command: $cmd")) {
        Invoke-PSCommandLine -CommandLine $cmd -WorkingDirectory $NewReleaseDir
      }
      Add-Op "preswap_cmd" "OK" $cmd
    }
  }

  Add-Op "stage_complete" "OK" $NewReleaseDir
  Write-Log "Staging complete." "OK"

} catch {
  Add-Op "stage_failed" "FAILED" $_.Exception.Message
  Write-Log ("Staging failed: {0}" -f $_.Exception.Message) "ERROR"
  throw
}

# -----------------------------
# Swap + restart + health check + rollback
# -----------------------------
$didSwap = $false
$oldCurrentMoved = $false

try {
  # Stop targets before swapping
  Stop-Targets
  Add-Op "stop_targets" "OK" "stopped"

  # If current exists, move it to backups
  if (Test-Path -LiteralPath $CurrentDir) {
    Write-Log ("Backing up current to: {0}" -f $BackupDir) "STEP"
    if ($PSCmdlet.ShouldProcess($CurrentDir, "Move current to backup")) {
      Move-Item -LiteralPath $CurrentDir -Destination $BackupDir -Force
    }
    $oldCurrentMoved = $true
    Add-Op "backup_current" "OK" $BackupDir
  } else {
    Add-Op "backup_current" "OK" "no current dir"
  }

  # Move staged release into current (atomic if same volume)
  Write-Log ("Promoting release to current: {0} -> {1}" -f $NewReleaseDir, $CurrentDir) "STEP"
  if ($PSCmdlet.ShouldProcess($NewReleaseDir, "Move release to current")) {
    Move-Item -LiteralPath $NewReleaseDir -Destination $CurrentDir -Force
  }
  $didSwap = $true
  Add-Op "swap" "OK" ("current={0}" -f $CurrentDir)

  # Start targets
  Start-Targets
  Add-Op "start_targets" "OK" "started"

  # Post-swap commands
  if ($PostSwapCommands -and $PostSwapCommands.Count -gt 0) {
    Write-Log "Running PostSwapCommands..." "STEP"
    foreach ($cmd in $PostSwapCommands) {
      if ([string]::IsNullOrWhiteSpace($cmd)) { continue }
      Write-Log ("PostSwap: {0}" -f $cmd) "INFO"
      Add-Op "postswap_cmd" "RUN" $cmd
      if ($PSCmdlet.ShouldProcess($CurrentDir, "Run PostSwap command: $cmd")) {
        Invoke-PSCommandLine -CommandLine $cmd -WorkingDirectory $CurrentDir
      }
      Add-Op "postswap_cmd" "OK" $cmd
    }
  }

  # Health check
  $healthOk = Test-Health
  Add-Op "health" ($(if($healthOk){"OK"}else{"FAILED"})) $HealthUrl

  if (-not $healthOk -and $FailIfHealthCheckFails) {
    throw "Health check failed and -FailIfHealthCheckFails is set."
  }

  Write-Log "Deployment completed." "OK"
  Add-Op "deploy_complete" "OK" "done"

} catch {
  $err = $_.Exception.Message
  Write-Log ("Deployment error: {0}" -f $err) "ERROR"
  Add-Op "deploy_error" "FAILED" $err

  # Rollback if we swapped and had a backup
  if ($didSwap -and $oldCurrentMoved -and (Test-Path -LiteralPath $BackupDir)) {
    Write-Log "Attempting rollback..." "STEP"
    Add-Op "rollback_begin" "RUN" $BackupDir

    try {
      # Stop before rollback
      Stop-Targets

      # Move broken current aside
      $broken = Join-Path $BackupsDir ("broken_{0}_{1}" -f $Now, $Tag)
      if (Test-Path -LiteralPath $CurrentDir) {
        if ($PSCmdlet.ShouldProcess($CurrentDir, "Move broken current to $broken")) {
          Move-Item -LiteralPath $CurrentDir -Destination $broken -Force
        }
        Add-Op "rollback_move_broken" "OK" $broken
      }

      # Restore backup into current
      if ($PSCmdlet.ShouldProcess($BackupDir, "Restore backup to $CurrentDir")) {
        Move-Item -LiteralPath $BackupDir -Destination $CurrentDir -Force
      }
      Add-Op "rollback_restore" "OK" $CurrentDir

      # Start targets again
      Start-Targets
      Add-Op "rollback_restart" "OK" "started"

      # Health check after rollback (best effort)
      $rbOk = Test-Health
      Add-Op "rollback_health" ($(if($rbOk){"OK"}else{"FAILED"})) $HealthUrl

      Write-Log "Rollback completed." "OK"
      Add-Op "rollback_complete" "OK" "done"
    } catch {
      $rbErr = $_.Exception.Message
      Write-Log ("Rollback failed: {0}" -f $rbErr) "ERROR"
      Add-Op "rollback_failed" "FAILED" $rbErr
    }
  } else {
    Write-Log "Rollback not performed (no swap/backup available)." "WARN"
    Add-Op "rollback_skipped" "OK" "no swap/backup"
  }

  throw
} finally {
  # Retention / pruning
  Write-Log ("Pruning backups to last {0}..." -f $KeepBackups) "STEP"
  Prune-OldDirs -Dir $BackupsDir -Keep $KeepBackups

  Write-Log ("Pruning releases to last {0}..." -f $KeepReleases) "STEP"
  Prune-OldDirs -Dir $ReleasesDir -Keep $KeepReleases

  # Write reports
  try {
    $ops | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $ReportCsv
    $ops | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportJson -Encoding UTF8

    Write-Log ("Saved log: {0}" -f $script:LogFile) "INFO"
    Write-Log ("Saved report CSV: {0}" -f $ReportCsv) "INFO"
    Write-Log ("Saved report JSON: {0}" -f $ReportJson) "INFO"
  } catch {
    Write-Log ("Failed to write reports: {0}" -f $_.Exception.Message) "WARN"
  }
}
