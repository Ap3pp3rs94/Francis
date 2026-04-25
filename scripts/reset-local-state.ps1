<#
D:\francis\scripts\reset-local-state.ps1

Purpose
  Reset local "workspace state" under a Francis root in a controlled way:
    - Soft     : clear temp/cache + prune old logs
    - Standard : Soft + clear staging + plugin build outputs + prune old artifacts
    - Hard     : Standard + optionally delete more artifacts + optionally remove node_modules

Safety
  - By default, this script will only delete paths UNDER -Root (default D:\francis).
  - Blocks dangerous paths (drive roots, Windows folders, etc.)
  - Destructive modes require -Force.

Logging
  - Transcript: D:\francis\data\logs\operations\reset_local_state_<timestamp>.log
  - CSV      : D:\francis\data\logs\operations\reset_local_state_<timestamp>.csv

Examples
  # See what would happen
  pwsh -File D:\francis\scripts\reset-local-state.ps1 -Mode Soft -WhatIf

  # Standard cleanup (requires Force)
  pwsh -File D:\francis\scripts\reset-local-state.ps1 -Mode Standard -Force -ResetPlugin

  # Hard cleanup including node_modules and all artifacts under D:\francis\data\artifacts
  pwsh -File D:\francis\scripts\reset-local-state.ps1 -Mode Hard -Force -ResetPlugin -RemoveNodeModules -ClearArtifactsAll

  # Also do a soft Ollama stop/reset using your existing script (if present)
  pwsh -File D:\francis\scripts\reset-local-state.ps1 -Mode Standard -Force -ResetOllama

Notes
  - This is intentionally conservative. If you truly want to delete outside of -Root, use -OverrideSafety.
#>

[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
param(
  [ValidateSet('Soft','Standard','Hard')]
  [string]$Mode = 'Soft',

  [string]$Root = 'D:\francis',

  # Required for Standard/Hard (destructive modes)
  [switch]$Force,

  # If set, clean plugin build outputs (dist/build/out/.next/.output/coverage) under project paths.
  [switch]$ResetPlugin,

  # Optional project paths to clean; if empty and Root\plugin exists, it will be used automatically when -ResetPlugin is set.
  [string[]]$ProjectPaths = @(),

  # Remove node_modules (only in Standard/Hard; recommended only when needed)
  [switch]$RemoveNodeModules,

  # Remove .venv folders inside project paths (only in Standard/Hard)
  [switch]$RemoveVenv,

  # Artifact pruning
  [int]$PruneArtifactsDays = 14,   # Standard: remove artifacts older than this many days (0 disables pruning)
  [switch]$ClearArtifactsAll,      # Hard: delete Root\data\artifacts entirely (requires -Force)

  # Log pruning
  [int]$KeepOperationLogsDays = 30,  # Soft+: delete ops logs older than this many days (0 disables)

  # Optional: call existing Ollama reset script (default is Soft)
  [switch]$ResetOllama,
  [ValidateSet('Soft','PurgeModels','LogsOnly','Hard')]
  [string]$OllamaMode = 'Soft',

  # Safety override: allow deletes outside Root (still blocks system roots)
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

$LogPath = Join-Path $OpsDir ("reset_local_state_{0}.log" -f $Now)
$CsvPath = Join-Path $OpsDir ("reset_local_state_{0}.csv" -f $Now)

$script:Actions = New-Object System.Collections.Generic.List[object]

function Add-Action {
  param(
    [string]$Action,
    [string]$Target,
    [string]$Result,
    [string]$Notes = ''
  )
  $script:Actions.Add([pscustomobject]@{
    Time   = (Get-Date).ToString('s')
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

  # Block common Windows/system roots
  $blocked = @(
    $env:SystemRoot,
    (Join-Path $env:SystemDrive '\Windows'),
    (Join-Path $env:SystemDrive '\Program Files'),
    (Join-Path $env:SystemDrive '\Program Files (x86)'),
    (Join-Path $env:SystemDrive '\ProgramData')
  ) | ForEach-Object { Resolve-FullPath $_ } | ForEach-Object { $_.TrimEnd('\') }

  foreach($b in $blocked){
    if($p.ToLowerInvariant() -eq $b.ToLowerInvariant()){ return $true }
  }

  return $false
}

function Test-IsUnderRoot {
  param([string]$Path,[string]$RootPath)

  $p = (Resolve-FullPath $Path).TrimEnd('\')
  $r = (Resolve-FullPath $RootPath).TrimEnd('\')

  # Must be strictly under root (not equal to root)
  $pLower = $p.ToLowerInvariant()
  $rLower = $r.ToLowerInvariant()

  if($pLower -eq $rLower){ return $false }
  if($pLower.StartsWith($rLower + "\")){ return $true }
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
    if(-not (Test-IsUnderRoot -Path $full -RootPath $Root)){
      $msg = "Safety block: path is not under Root ($Root). Use -OverrideSafety if intentional. Path: $full"
      Add-Action "Remove" $full "BLOCKED" $msg
      throw $msg
    }
  }

  if($PSCmdlet.ShouldProcess($full, "Delete $Label")){
    $max = 3
    for($i=1; $i -le $max; $i++){
      try{
        Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction Stop
        Add-Action "Remove" $full "OK" "$Label deleted"
        return
      } catch {
        if($i -eq $max){
          Add-Action "Remove" $full "FAILED" $_.Exception.Message
          throw
        }
        Start-Sleep -Seconds 1
      }
    }
  } else {
    Add-Action "Remove" $full "WHATIF/SKIPPED" "$Label deletion not approved"
  }
}

function Prune-OldFiles {
  param(
    [Parameter(Mandatory=$true)][string]$Folder,
    [Parameter(Mandatory=$true)][int]$KeepDays,
    [string]$Label = "Files"
  )

  if($KeepDays -le 0){
    Add-Action "Prune" (Resolve-FullPath $Folder) "SKIPPED" "KeepDays=$KeepDays"
    return
  }

  if(-not (Test-Path -LiteralPath $Folder)){
    Add-Action "Prune" (Resolve-FullPath $Folder) "SKIPPED" "Folder not found"
    return
  }

  $cutoff = (Get-Date).AddDays(-1 * $KeepDays)
  $items = Get-ChildItem -LiteralPath $Folder -Recurse -File -Force -ErrorAction SilentlyContinue |
           Where-Object { $_.LastWriteTime -lt $cutoff }

  foreach($it in $items){
    if(Test-DangerousPath $it.FullName){ continue }

    if(-not $OverrideSafety){
      if(-not (Test-IsUnderRoot -Path $it.FullName -RootPath $Root)){
        continue
      }
    }

    if($PSCmdlet.ShouldProcess($it.FullName, "Delete old $Label (>$KeepDays days)")){
      try{
        Remove-Item -LiteralPath $it.FullName -Force -ErrorAction Stop
        Add-Action "Prune" $it.FullName "OK" "Older than $KeepDays days"
      } catch {
        Add-Action "Prune" $it.FullName "FAILED" $_.Exception.Message
      }
    } else {
      Add-Action "Prune" $it.FullName "WHATIF/SKIPPED" "Not approved"
    }
  }
}

function Require-ForceForDestructive {
  param([string]$ForMode)
  if($ForMode -in @('Standard','Hard')){
    if(-not $Force){
      $msg = "Mode '$ForMode' is destructive. Re-run with -Force (and optionally -WhatIf first)."
      Add-Action "Guard" $ForMode "BLOCKED" $msg
      throw $msg
    }
  }
}

function Get-DefaultProjects {
  $p = Join-Path $Root 'plugin'
  if(Test-Path -LiteralPath $p){ return @($p) }
  return @()
}

# -----------------------------
# Main
# -----------------------------
try {
  Start-Transcript -Path $LogPath -Force | Out-Null

  Write-Section "Reset Local State"
  Write-Host ("Mode                 : {0}" -f $Mode)
  Write-Host ("Root                 : {0}" -f (Resolve-FullPath $Root))
  Write-Host ("Force                : {0}" -f $Force)
  Write-Host ("ResetPlugin          : {0}" -f $ResetPlugin)
  Write-Host ("RemoveNodeModules    : {0}" -f $RemoveNodeModules)
  Write-Host ("RemoveVenv           : {0}" -f $RemoveVenv)
  Write-Host ("PruneArtifactsDays   : {0}" -f $PruneArtifactsDays)
  Write-Host ("ClearArtifactsAll    : {0}" -f $ClearArtifactsAll)
  Write-Host ("KeepOperationLogsDays: {0}" -f $KeepOperationLogsDays)
  Write-Host ("ResetOllama          : {0}" -f $ResetOllama)
  Write-Host ("OllamaMode           : {0}" -f $OllamaMode)
  Write-Host ("OverrideSafety       : {0}" -f $OverrideSafety)
  Write-Host ("WhatIf               : {0}" -f $WhatIfPreference)
  Write-Host ("Log                  : {0}" -f $LogPath)
  Write-Host ("CSV                  : {0}" -f $CsvPath)

  if(-not (Test-Path -LiteralPath $Root)){
    throw "Root not found: $Root"
  }

  Require-ForceForDestructive -ForMode $Mode

  # --- Always safe-ish targets (Soft+) ---
  Write-Section "Soft cleanup targets"
  $softTargets = @(
    @{ Path = (Join-Path $Root 'data\tmp');   Label = 'data\tmp'   },
    @{ Path = (Join-Path $Root 'data\cache'); Label = 'data\cache' }
  )

  foreach($t in $softTargets){
    Remove-PathSafe -Path $t.Path -Label $t.Label
  }

  # Prune old operation logs (files only)
  Write-Section "Prune old operation logs"
  Prune-OldFiles -Folder $OpsDir -KeepDays $KeepOperationLogsDays -Label "operations log file"

  # --- Standard mode extras ---
  if($Mode -in @('Standard','Hard')){
    Write-Section "Standard cleanup targets"

    # Staging / scratch areas (under Root)
    $stdTargets = @(
      @{ Path = (Join-Path $Root 'data\staging'); Label = 'data\staging' },
      @{ Path = (Join-Path $Root 'data\scratch'); Label = 'data\scratch' }
    )
    foreach($t in $stdTargets){
      Remove-PathSafe -Path $t.Path -Label $t.Label
    }

    # Plugin artifacts: delete stage_* folders always; prune old zips/reports by age
    $pluginsOut = Join-Path $Root 'data\artifacts\plugins'
    if(Test-Path -LiteralPath $pluginsOut){
      Write-Host ""
      Write-Host ("Plugin artifacts dir: {0}" -f (Resolve-FullPath $pluginsOut))

      # Delete all staging folders stage_*
      $stageDirs = Get-ChildItem -LiteralPath $pluginsOut -Directory -Force -ErrorAction SilentlyContinue |
                  Where-Object { $_.Name -like 'stage_*' }
      foreach($sd in $stageDirs){
        Remove-PathSafe -Path $sd.FullName -Label ("artifact staging " + $sd.Name)
      }

      # Prune old artifacts if enabled
      if($PruneArtifactsDays -gt 0){
        Prune-OldFiles -Folder $pluginsOut -KeepDays $PruneArtifactsDays -Label "plugin artifact"
      } else {
        Add-Action "Prune" (Resolve-FullPath $pluginsOut) "SKIPPED" "PruneArtifactsDays=$PruneArtifactsDays"
      }
    } else {
      Add-Action "Info" (Resolve-FullPath $pluginsOut) "SKIPPED" "plugins artifacts folder not found"
    }

    # Plugin project cleanup
    if($ResetPlugin){
      if(-not $ProjectPaths -or $ProjectPaths.Count -eq 0){
        $ProjectPaths = Get-DefaultProjects
      }

      if($ProjectPaths -and $ProjectPaths.Count -gt 0){
        Write-Section "Plugin project cleanup"

        foreach($proj in $ProjectPaths){
          if(-not (Test-Path -LiteralPath $proj)){
            Add-Action "Project" $proj "SKIPPED" "ProjectPath not found"
            continue
          }

          $projFull = Resolve-FullPath $proj
          Write-Host ("Project: {0}" -f $projFull)
          Add-Action "Project" $projFull "OK" "Selected"

          $buildDirs = @('dist','build','out','.next','.output','coverage')
          foreach($bd in $buildDirs){
            $p = Join-Path $projFull $bd
            Remove-PathSafe -Path $p -Label ("project output " + $bd)
          }

          if($RemoveVenv){
            $venvCandidates = @('.venv','venv')
            foreach($vd in $venvCandidates){
              $vp = Join-Path $projFull $vd
              Remove-PathSafe -Path $vp -Label ("python venv " + $vd)
            }
          }

          if($RemoveNodeModules){
            $nm = Join-Path $projFull 'node_modules'
            Remove-PathSafe -Path $nm -Label "node_modules"
          }

          Write-Host ""
        }
      } else {
        Add-Action "Plugin" "(none)" "SKIPPED" "ResetPlugin set but no ProjectPaths found/provided"
      }
    }

    # Optional: Ollama reset via your existing script
    if($ResetOllama){
      Write-Section "Ollama reset (delegated)"
      $ollamaReset = Join-Path $Root 'scripts\ollama-reset.ps1'

      if(Test-Path -LiteralPath $ollamaReset){
        # If a destructive OllamaMode is requested, require -Force here too
        $ollamaDestructive = @('PurgeModels','LogsOnly','Hard')
        if(($ollamaDestructive -contains $OllamaMode) -and (-not $Force)){
          $msg = "OllamaMode '$OllamaMode' is destructive. Re-run with -Force (and optionally -WhatIf first)."
          Add-Action "Ollama" $ollamaReset "BLOCKED" $msg
          throw $msg
        }

        $args = @('-Mode', $OllamaMode)
        if($Force){ $args += '-Force' }
        if($WhatIfPreference){ $args += '-WhatIf' }

        if($PSCmdlet.ShouldProcess($ollamaReset, ("Run ollama-reset.ps1 " + ($args -join ' ')))){
          try{
            & $ollamaReset @args
            Add-Action "Ollama" $ollamaReset "OK" ("Mode=" + $OllamaMode)
          } catch {
            Add-Action "Ollama" $ollamaReset "FAILED" $_.Exception.Message
            throw
          }
        } else {
          Add-Action "Ollama" $ollamaReset "WHATIF/SKIPPED" "Not approved"
        }
      } else {
        Add-Action "Ollama" $ollamaReset "SKIPPED" "ollama-reset.ps1 not found"
      }
    }
  }

  # --- Hard mode extras ---
  if($Mode -eq 'Hard'){
    Write-Section "Hard mode extras"

    if($ClearArtifactsAll){
      $allArtifacts = Join-Path $Root 'data\artifacts'
      Remove-PathSafe -Path $allArtifacts -Label 'data\artifacts (ALL)'
    } else {
      Add-Action "Artifacts" (Resolve-FullPath (Join-Path $Root 'data\artifacts')) "SKIPPED" "ClearArtifactsAll not set"
    }
  }

  # --- Summary ---
  Write-Section "Summary"
  $script:Actions | Format-Table -AutoSize Time,Action,Target,Result,Notes

  # CSV report
  try{
    $script:Actions | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $CsvPath
    Write-Host ""
    Write-Host ("Saved CSV: {0}" -f $CsvPath)
  } catch {
    Write-Warning ("Failed to write CSV: {0}" -f $_.Exception.Message)
  }

  Write-Host ""
  Write-Host ("Saved log: {0}" -f $LogPath)

} catch {
  Write-Host ""
  Write-Host ("ERROR: {0}" -f $_.Exception.Message) -ForegroundColor Red
  throw
} finally {
  try { Stop-Transcript | Out-Null } catch {}
}
