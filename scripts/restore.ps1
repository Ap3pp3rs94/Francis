<#
D:\francis\scripts\restore.ps1

Purpose
  Restore a "baseline working state" for the Francis workspace after cleanup/reset:
    - Recreate standard folders under Root
    - Optionally (re)build plugin project (delegates to plugin-build.ps1)
    - Optionally start Ollama + pull models (delegates to ollama-pull-models.ps1)
    - Optionally run file sanity scan (credential-delegate.ps1)

Safety
  - Non-destructive by default (creates folders / starts services).
  - Network-heavy actions (npm install, pulling models, installing Ollama) require -Force.
  - Uses -WhatIf/-Confirm via ShouldProcess.
  - Only operates under -Root by default (OverrideSafety available but still blocks system roots).

Logging
  - Transcript: <Root>\data\logs\operations\restore_<timestamp>.log
  - CSV      : <Root>\data\logs\operations\restore_<timestamp>.csv

Examples
  # Show what would happen (no changes)
  pwsh -File D:\francis\scripts\restore.ps1 -Mode Minimal -WhatIf

  # Restore folders + check tooling + build plugin + pull models (requires Force for network)
  pwsh -File D:\francis\scripts\restore.ps1 -Mode Standard -Force -RestorePlugin -PullModels

  # Full restore + sanity scan
  pwsh -File D:\francis\scripts\restore.ps1 -Mode Full -Force -RestorePlugin -PullModels -SanityCheck
#>

[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='Medium')]
param(
  [ValidateSet('Minimal','Standard','Full')]
  [string]$Mode = 'Minimal',

  [string]$Root = 'D:\francis',

  # Required for actions that pull/download/install (npm install, ollama pull, installers)
  [switch]$Force,

  # Create a default models file if missing: <Root>\data\config\ollama-models.txt
  [switch]$EnsureDefaultConfigs,

  # ---- Plugin restore (delegates to plugin-build.ps1) ----
  [switch]$RestorePlugin,
  [string]$ProjectPath = '',
  [ValidateSet('All','Clean','Install','Lint','Test','Build','Pack')]
  [string]$PluginMode = 'All',
  [switch]$SkipPluginValidate,

  # ---- Ollama restore (delegates to ollama-pull-models.ps1) ----
  [switch]$EnsureOllamaRunning,
  [switch]$PullModels,
  [string[]]$Models = @(),
  [string]$ModelsFile = '',
  [switch]$SkipExistingModels,
  [int]$OllamaTimeoutSec = 0,
  [switch]$ContinueOnModelError,

  # ---- Optional sanity scan (delegates to credential-delegate.ps1) ----
  [switch]$SanityCheck,

  # Safety override: allow ops outside Root (still blocks Windows/system roots)
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

$LogPath = Join-Path $OpsDir ("restore_{0}.log" -f $Now)
$CsvPath = Join-Path $OpsDir ("restore_{0}.csv" -f $Now)

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

  $pLower = $p.ToLowerInvariant()
  $rLower = $r.ToLowerInvariant()

  if($pLower -eq $rLower){ return $true } # equal is fine for creates
  if($pLower.StartsWith($rLower + "\")){ return $true }
  return $false
}

function New-DirSafe {
  param(
    [Parameter(Mandatory=$true)][string]$Path,
    [string]$Label = "Directory"
  )

  $full = Resolve-FullPath $Path

  if(Test-DangerousPath $full){
    $msg = "Refusing to create/operate on dangerous path: $full"
    Add-Action "New-Dir" $full "BLOCKED" $msg
    throw $msg
  }

  if(-not $OverrideSafety){
    if(-not (Test-IsUnderRoot -Path $full -RootPath $Root)){
      $msg = "Safety block: path is not under Root ($Root). Use -OverrideSafety if intentional. Path: $full"
      Add-Action "New-Dir" $full "BLOCKED" $msg
      throw $msg
    }
  }

  if(Test-Path -LiteralPath $full){
    Add-Action "New-Dir" $full "SKIPPED" "$Label already exists"
    return
  }

  if($PSCmdlet.ShouldProcess($full, "Create $Label")){
    New-Item -ItemType Directory -Force -Path $full | Out-Null
    Add-Action "New-Dir" $full "OK" "$Label created"
  } else {
    Add-Action "New-Dir" $full "WHATIF/SKIPPED" "Not approved"
  }
}

function Require-ForceForNetwork {
  param([string]$Thing)
  if(-not $Force){
    $msg = "$Thing can download/pull/install content. Re-run with -Force (and optionally -WhatIf first)."
    Add-Action "Guard" $Thing "BLOCKED" $msg
    throw $msg
  }
}

function Test-Command {
  param([string]$Name)
  try {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if($cmd -and $cmd.Source){ return $cmd.Source }
  } catch {}
  return $null
}

function Invoke-ChildScript {
  param(
    [Parameter(Mandatory=$true)][string]$ScriptPath,
    [string[]]$Args = @(),
    [string]$StepName = "Script"
  )

  $full = Resolve-FullPath $ScriptPath
  if(-not (Test-Path -LiteralPath $full)){
    Add-Action $StepName $full "SKIPPED" "Script not found"
    return
  }

  $cmdLine = "pwsh -File `"$full`" " + ($Args -join " ")
  Write-Host ""
  Write-Host ("> {0}" -f $cmdLine)

  if($PSCmdlet.ShouldProcess($full, $cmdLine)){
    try {
      & $full @Args
      $code = $LASTEXITCODE
      if($code -ne 0){
        Add-Action $StepName $full "FAILED" "ExitCode=$code"
        throw "$StepName failed (ExitCode=$code): $full"
      } else {
        Add-Action $StepName $full "OK" ($Args -join " ")
      }
    } catch {
      Add-Action $StepName $full "FAILED" $_.Exception.Message
      throw
    }
  } else {
    Add-Action $StepName $full "WHATIF/SKIPPED" "Not approved"
  }
}

function Write-DefaultOllamaModelsFile {
  $cfgDir = Join-Path $Root 'data\config'
  $file   = Join-Path $cfgDir 'ollama-models.txt'

  New-DirSafe -Path $cfgDir -Label "Config directory"

  if(Test-Path -LiteralPath $file){
    Add-Action "Config" $file "SKIPPED" "Already exists"
    return
  }

  $content = @(
    "# Ollama models to pull (one per line).",
    "# Blank lines allowed. Lines starting with # are ignored.",
    "# Examples:",
    "#   llama3.1:8b",
    "#   qwen2.5:7b",
    "",
    "llama3.1:8b"
  ) -join "`r`n"

  if($PSCmdlet.ShouldProcess($file, "Create default ollama-models.txt")){
    $content | Out-File -LiteralPath $file -Encoding UTF8 -Force
    Add-Action "Config" $file "OK" "Created default models file"
  } else {
    Add-Action "Config" $file "WHATIF/SKIPPED" "Not approved"
  }
}

# -----------------------------
# Decide defaults by Mode
# -----------------------------
# Minimal : folders + optional default configs + tooling check
# Standard: Minimal + optional plugin restore + optional ollama start/pull (requires -Force for pulls/build)
# Full    : Standard + sanity check (and runs plugin mode All by default)

if([string]::IsNullOrWhiteSpace($ProjectPath)){
  $ProjectPath = Join-Path $Root 'plugin'
}

if($Mode -eq 'Standard' -or $Mode -eq 'Full'){
  # Don’t silently enable the heavy actions; user still needs to set switches,
  # but we’ll do better “defaulting” if they already asked.
  # (No automatic flipping of switches here to avoid surprises.)
}

# -----------------------------
# Main
# -----------------------------
try {
  Start-Transcript -Path $LogPath -Force | Out-Null

  Write-Section "Restore"
  Write-Host ("Mode        : {0}" -f $Mode)
  Write-Host ("Root        : {0}" -f (Resolve-FullPath $Root))
  Write-Host ("Force       : {0}" -f $Force)
  Write-Host ("WhatIf      : {0}" -f $WhatIfPreference)
  Write-Host ("Log         : {0}" -f $LogPath)
  Write-Host ("CSV         : {0}" -f $CsvPath)

  if(-not (Test-Path -LiteralPath $Root)){
    # Creating root can be surprising; keep conservative.
    $msg = "Root not found: $Root (create it first, or point -Root at the correct folder)"
    Add-Action "Guard" $Root "FAILED" $msg
    throw $msg
  }

  # -----------------------------
  # Folder baseline
  # -----------------------------
  Write-Section "Ensure baseline folders"
  $dirs = @(
    (Join-Path $Root 'data'),
    (Join-Path $Root 'data\logs'),
    (Join-Path $Root 'data\logs\operations'),
    (Join-Path $Root 'data\artifacts'),
    (Join-Path $Root 'data\artifacts\plugins'),
    (Join-Path $Root 'data\config'),
    (Join-Path $Root 'data\tmp'),
    (Join-Path $Root 'data\cache'),
    (Join-Path $Root 'data\staging'),
    (Join-Path $Root 'data\scratch'),
    (Join-Path $Root 'scripts')
  )

  foreach($d in $dirs){
    New-DirSafe -Path $d -Label "Folder"
  }

  # -----------------------------
  # Optional default configs
  # -----------------------------
  if($EnsureDefaultConfigs){
    Write-Section "Ensure default configs"
    Write-DefaultOllamaModelsFile
  } else {
    Add-Action "Config" (Join-Path $Root 'data\config') "SKIPPED" "EnsureDefaultConfigs not set"
  }

  # -----------------------------
  # Tooling checks (informational)
  # -----------------------------
  Write-Section "Tooling checks"
  $node = Test-Command 'node'
  $npm  = Test-Command 'npm'
  $pnpm = Test-Command 'pnpm'
  $yarn = Test-Command 'yarn'
  $py   = Test-Command 'python'
  $oll  = Test-Command 'ollama'

  foreach($t in @(
    @{Name='node';   Path=$node},
    @{Name='npm';    Path=$npm},
    @{Name='pnpm';   Path=$pnpm},
    @{Name='yarn';   Path=$yarn},
    @{Name='python'; Path=$py},
    @{Name='ollama'; Path=$oll}
  )){
    if($t.Path){
      Add-Action "Tool" $t.Name "OK" $t.Path
      Write-Host ("{0,-8}: {1}" -f $t.Name,$t.Path)
      try {
        if($t.Name -in @('node','npm','pnpm','yarn','python','ollama')){
          & $t.Name --version 2>$null | ForEach-Object { if($_){ Write-Host ("          {0}" -f $_) } }
        }
      } catch {}
    } else {
      Add-Action "Tool" $t.Name "WARN" "Not found"
      Write-Host ("{0,-8}: (not found)" -f $t.Name)
    }
  }

  # -----------------------------
  # Ollama: ensure running + pull models
  # -----------------------------
  if($EnsureOllamaRunning -or $PullModels){
    Write-Section "Ollama restore"

    $pullScript = Join-Path $Root 'scripts\ollama-pull-models.ps1'
    if(-not (Test-Path -LiteralPath $pullScript)){
      $msg = "ollama-pull-models.ps1 not found at: $pullScript"
      Add-Action "Ollama" $pullScript "FAILED" $msg
      throw $msg
    }

    # If PullModels is requested, require Force (network)
    if($PullModels){
      Require-ForceForNetwork "Pulling Ollama models"
    }

    # If user just wants it running (no pull), we can call ListOnly which also triggers API check + optional serve start.
    if($EnsureOllamaRunning -and (-not $PullModels)){
      $args = @('-ListOnly')
      if($WhatIfPreference){ $args += '-WhatIf' }
      Invoke-ChildScript -ScriptPath $pullScript -Args $args -StepName "Ollama:ListOnly"
    }

    if($PullModels){
      $args = @()
      if($ModelsFile){
        $args += @('-ModelsFile', $ModelsFile)
      } elseif($Models -and $Models.Count -gt 0){
        $args += @('-Models', ($Models))
      } else {
        # Use default convention if present
        $default = Join-Path $Root 'data\config\ollama-models.txt'
        if(Test-Path -LiteralPath $default){
          $args += @('-ModelsFile', $default)
        } else {
          $msg = "No -Models/-ModelsFile provided and default file not found: $default (use -EnsureDefaultConfigs to create one)."
          Add-Action "Ollama" $default "FAILED" $msg
          throw $msg
        }
      }

      if($SkipExistingModels){ $args += '-SkipExisting' }
      if($OllamaTimeoutSec -gt 0){ $args += @('-TimeoutSec', $OllamaTimeoutSec) }
      if($ContinueOnModelError){ $args += '-ContinueOnError' }
      if($WhatIfPreference){ $args += '-WhatIf' }

      Invoke-ChildScript -ScriptPath $pullScript -Args $args -StepName "Ollama:PullModels"
    }
  } else {
    Add-Action "Ollama" "(none)" "SKIPPED" "EnsureOllamaRunning/PullModels not set"
  }

  # -----------------------------
  # Plugin: restore/build/package
  # -----------------------------
  if($RestorePlugin){
    Write-Section "Plugin restore"

    # Plugin builds/install typically download deps => require Force
    Require-ForceForNetwork "Plugin restore (npm/yarn/pnpm install/build)"

    $buildScript = Join-Path $Root 'scripts\plugin-build.ps1'
    if(-not (Test-Path -LiteralPath $buildScript)){
      $msg = "plugin-build.ps1 not found at: $buildScript"
      Add-Action "Plugin" $buildScript "FAILED" $msg
      throw $msg
    }

    if(-not (Test-Path -LiteralPath $ProjectPath)){
      $msg = "ProjectPath not found: $ProjectPath"
      Add-Action "Plugin" $ProjectPath "FAILED" $msg
      throw $msg
    }

    $args = @('-Mode', $PluginMode, '-ProjectPath', $ProjectPath, '-Root', $Root)
    if($SkipPluginValidate){ $args += '-SkipValidate' }
    if($WhatIfPreference){ $args += '-WhatIf' }

    Invoke-ChildScript -ScriptPath $buildScript -Args $args -StepName "Plugin:Build"
  } else {
    Add-Action "Plugin" "(none)" "SKIPPED" "RestorePlugin not set"
  }

  # -----------------------------
  # Sanity check (file scan)
  # -----------------------------
  if($SanityCheck){
    Write-Section "File sanity scan"
    $sanity = Join-Path $Root 'scripts\credential-delegate.ps1'
    if(-not (Test-Path -LiteralPath $sanity)){
      Add-Action "Sanity" $sanity "SKIPPED" "credential-delegate.ps1 not found"
    } else {
      # This script writes its own CSV and table output
      $args = @()
      if($WhatIfPreference){ $args += '-WhatIf' }
      Invoke-ChildScript -ScriptPath $sanity -Args $args -StepName "Sanity:FileScan"
    }
  } else {
    Add-Action "Sanity" "(none)" "SKIPPED" "SanityCheck not set"
  }

  # -----------------------------
  # Summary + CSV
  # -----------------------------
  Write-Section "Summary"
  $script:Actions | Format-Table -AutoSize Time,Action,Target,Result,Notes

  try{
    $script:Actions | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $CsvPath
    Write-Host ""
    Write-Host ("Saved CSV: {0}" -f $CsvPath)
  } catch {
    Write-Warning ("Failed to write CSV: {0}" -f $_.Exception.Message)
  }

  Write-Host ""
  Write-Host ("Saved log: {0}" -f $LogPath)

  # Non-zero exit if anything FAILED/BLOCKED
  $bad = $script:Actions | Where-Object { $_.Result -in @('FAILED','BLOCKED') }
  if($bad -and $bad.Count -gt 0){ exit 1 } else { exit 0 }

} catch {
  Write-Host ""
  Write-Host ("ERROR: {0}" -f $_.Exception.Message) -ForegroundColor Red
  throw
} finally {
  try { Stop-Transcript | Out-Null } catch {}
}
