<# 
C:\Francis\scripts\ollama-pull-models.ps1

Pull one or more Ollama models and produce an operations log + CSV report.

Examples:
  # Pull a couple models
  .\ollama-pull-models.ps1 -Models "llama3.1:8b","qwen2.5:7b"

  # Pull from a text file (one model per line, # comments allowed)
  .\ollama-pull-models.ps1 -ModelsFile "C:\Francis\data\config\ollama-models.txt" -SkipExisting

  # Just verify API + list currently installed models
  .\ollama-pull-models.ps1 -ListOnly

Notes:
- If the API isn't reachable, the script will try to start `ollama serve` unless -NoServeStart is used.
- On Windows, Ollama is typically already running after install; starting serve again may fail if port is in use (that's OK).
#>

[CmdletBinding(SupportsShouldProcess=$true)]
param(
  [string]   $Root = "C:\Francis",

  # Model names like: llama3.1:8b, mistral, qwen2.5:7b, etc.
  [string[]] $Models = @(),

  # Text file with one model per line; blank lines and lines starting with # are ignored.
  [string]   $ModelsFile = "",

  # If set, models already present locally will be skipped.
  [switch]   $SkipExisting,

  # If set, do not pull anything; only show current installed models and API status.
  [switch]   $ListOnly,

  # If set, do not attempt to start `ollama serve` automatically when API is unreachable.
  [switch]   $NoServeStart,

  # If > 0, each pull is killed if it exceeds this many seconds.
  [int]      $TimeoutSec = 0,

  # If set, continue pulling other models even if one fails.
  [switch]   $ContinueOnError,

  # Optional: retry pulls that fail (ExitCode != 0)
  [ValidateRange(0,10)]
  [int]      $MaxRetries = 0,

  [ValidateRange(0,600)]
  [int]      $RetryDelaySec = 10
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-OpDir([string]$Path){
  New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

function Get-OllamaPath {
  $cmd = Get-Command ollama -ErrorAction SilentlyContinue
  if($cmd -and $cmd.Source){ return $cmd.Source }

  # Common Windows install locations (best-effort)
  $candidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"),
    (Join-Path $env:ProgramFiles "Ollama\ollama.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Ollama\ollama.exe")
  ) | Where-Object { $_ -and (Test-Path $_) }

  if($candidates.Count -gt 0){ return $candidates[0] }
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

function Start-OllamaServe {
  param([string]$OllamaExe)

  # Start ollama serve in background (best effort).
  # If it's already running, it may error/exit immediately due to port in use — that's fine.
  try{
    Start-Process -FilePath $OllamaExe -ArgumentList @("serve") -WindowStyle Hidden | Out-Null
    Start-Sleep -Milliseconds 800
  } catch {
    # don't throw; this is best-effort
  }
}

function Normalize-ModelName {
  param([string]$Model)

  $m = ($Model -as [string]).Trim()
  if([string]::IsNullOrWhiteSpace($m)){ return "" }

  # If user already provided a tag, respect it.
  if($m -match ":\S+$"){ return $m }

  # If no tag is provided, treat it as :latest for "is it installed?" checks.
  return "$m`:latest"
}

function Is-ModelInstalled {
  param(
    [System.Collections.Generic.HashSet[string]]$Installed,
    [string]$Model
  )

  if(-not $Installed){ return $false }

  $raw = ($Model -as [string]).Trim()
  if([string]::IsNullOrWhiteSpace($raw)){ return $false }

  $norm = Normalize-ModelName $raw

  # Check exact, then normalized (:latest)
  if($Installed.Contains($raw)){ return $true }
  if($norm -and $Installed.Contains($norm)){ return $true }

  return $false
}

function Get-InstalledModels {
  param([string]$OllamaExe)

  # Prefer API if available (more structured); fallback to `ollama list`.
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
    } catch {
      # fall through
    }
  }

  try{
    $out = & $OllamaExe list 2>$null
    # Typical output is a table; parse first "word" per non-header line
    foreach($line in ($out -split "`r?`n")){
      $t = $line.Trim()
      if(-not $t){ continue }
      if($t -match '^(NAME|MODEL)\s+'){ continue }
      $first = ($t -split '\s+')[0]
      if($first){ [void]$names.Add($first) }
    }
  } catch {
    # ignore; return what we have
  }

  return $names
}

function Read-ModelFile([string]$Path){
  if(-not (Test-Path -LiteralPath $Path)){ throw "ModelsFile not found: $Path" }

  $lines = Get-Content -LiteralPath $Path -ErrorAction Stop
  $out = @()

  foreach($l in $lines){
    $t = ($l -as [string]).Trim()
    if(-not $t){ continue }
    if($t.StartsWith("#")){ continue }
    $out += $t
  }

  return $out
}

function Invoke-OllamaPull {
  param(
    [string]$OllamaExe,
    [string]$Model,
    [int]$TimeoutSec
  )

  if($TimeoutSec -le 0){
    & $OllamaExe pull $Model
    return $LASTEXITCODE
  }

  # Timeout mode: use Start-Process + Wait-Process
  $tmpOut = [System.IO.Path]::GetTempFileName()
  $tmpErr = [System.IO.Path]::GetTempFileName()

  try{
    $p = Start-Process -FilePath $OllamaExe `
                       -ArgumentList @("pull", $Model) `
                       -NoNewWindow `
                       -PassThru `
                       -RedirectStandardOutput $tmpOut `
                       -RedirectStandardError  $tmpErr

    $done = $p.WaitForExit($TimeoutSec * 1000)
    if(-not $done){
      try { $p.Kill() } catch {}
      return 124  # timeout-like
    }

    return $p.ExitCode
  }
  finally{
    # Emit captured output back into the transcript/log for visibility
    if(Test-Path $tmpOut){
      $o = Get-Content -LiteralPath $tmpOut -ErrorAction SilentlyContinue
      if($o){ $o | ForEach-Object { $_ } }
      Remove-Item -LiteralPath $tmpOut -Force -ErrorAction SilentlyContinue
    }
    if(Test-Path $tmpErr){
      $e = Get-Content -LiteralPath $tmpErr -ErrorAction SilentlyContinue
      if($e){ $e | ForEach-Object { $_ } }
      Remove-Item -LiteralPath $tmpErr -Force -ErrorAction SilentlyContinue
    }
  }
}

# -----------------------------
# Logging setup (Francis layout)
# -----------------------------
$Now    = Get-Date -Format "yyyyMMdd_HHmmss"
$OutDir = Join-Path $Root "data\logs\operations"
New-OpDir $OutDir

$Csv = Join-Path $OutDir "ollama_pull_models_$Now.csv"
$Log = Join-Path $OutDir "ollama_pull_models_$Now.log"

$transcriptStarted = $false

try {
  try { Start-Transcript -LiteralPath $Log -Append | Out-Null; $transcriptStarted = $true } catch {}

  Write-Host "Root: $Root"
  Write-Host "Log : $Log"
  Write-Host "CSV : $Csv"
  Write-Host ""

  # -----------------------------
  # Locate Ollama
  # -----------------------------
  $Ollama = Get-OllamaPath
  if(-not $Ollama){
    throw "Ollama not found on PATH and not in common install locations. Install Ollama first."
  }

  Write-Host "Ollama: $Ollama"
  try { & $Ollama --version } catch {}
  Write-Host ""

  # -----------------------------
  # API check / start serve (best-effort)
  # -----------------------------
  $apiUp = Test-OllamaApi -Timeout 2
  if(-not $apiUp){
    Write-Warning "Ollama API not reachable at http://127.0.0.1:11434/api/tags"
    if(-not $NoServeStart){
      Write-Host "Attempting to start: ollama serve (background) ..."
      Start-OllamaServe -OllamaExe $Ollama
      $apiUp = Test-OllamaApi -Timeout 3
    }
  }

  if($apiUp){
    Write-Host "API: reachable (127.0.0.1:11434)"
  } else {
    Write-Warning "API still not reachable. Pulls may still work if Ollama auto-starts, but health checks/listing may fail."
  }
  Write-Host ""

  # -----------------------------
  # Determine model list
  # -----------------------------
  $modelsToPull = @()

  if($ModelsFile){
    $modelsToPull = Read-ModelFile $ModelsFile
  }
  elseif($Models.Count -gt 0){
    $modelsToPull = $Models
  }
  else{
    # Optional default file convention
    $defaultFile = Join-Path $Root "data\config\ollama-models.txt"
    if(Test-Path $defaultFile){
      Write-Host "No -Models/-ModelsFile provided; using default: $defaultFile"
      $modelsToPull = Read-ModelFile $defaultFile
    }
  }

  # Always show what is installed now
  $installed = Get-InstalledModels -OllamaExe $Ollama
  Write-Host "Installed models (current):"
  if($installed.Count -gt 0){
    $installed | Sort-Object | ForEach-Object { "  - $_" } | Write-Host
  } else {
    Write-Host "  (none found or unable to list)"
  }
  Write-Host ""

  if($ListOnly){
    Write-Host "ListOnly set; exiting without pulling."
    exit 0
  }

  if(-not $modelsToPull -or $modelsToPull.Count -eq 0){
    Write-Warning "No models provided. Use -Models or -ModelsFile (or create $Root\data\config\ollama-models.txt)."
    exit 2
  }

  # Normalize/unique while preserving order
  $seen = New-Object System.Collections.Generic.HashSet[string] ([StringComparer]::OrdinalIgnoreCase)
  $normalized = @()
  foreach($m in $modelsToPull){
    $t = ($m -as [string]).Trim()
    if(-not $t){ continue }
    if($seen.Add($t)){ $normalized += $t }
  }
  $modelsToPull = $normalized

  Write-Host "Models requested:"
  $modelsToPull | ForEach-Object { "  - $_" } | Write-Host
  Write-Host ""

  # Refresh installed list right before pulling (in case API came up)
  $installed = Get-InstalledModels -OllamaExe $Ollama

  # -----------------------------
  # Pull loop
  # -----------------------------
  $results = @()
  $anyFailed = $false

  foreach($model in $modelsToPull){

    $start = Get-Date
    $status = "PENDING"
    $why = ""
    $exitCode = $null
    $attempts = 0

    if($SkipExisting -and (Is-ModelInstalled -Installed $installed -Model $model)){
      $status = "SKIPPED"
      $why = "Already installed"
      $end = Get-Date
      $sec = [math]::Round(($end - $start).TotalSeconds, 2)

      $results += [pscustomobject]@{
        Model    = $model
        Status   = $status
        ExitCode = 0
        Attempts = 0
        Seconds  = $sec
        Started  = $start
        Ended    = $end
        Why      = $why
      }

      Write-Host "SKIP  $model  ($why)"
      continue
    }

    if(-not $PSCmdlet.ShouldProcess($model, "ollama pull")){
      $status = "WHATIF"
      $why = "ShouldProcess declined"
      $end = Get-Date
      $sec = [math]::Round(($end - $start).TotalSeconds, 2)

      $results += [pscustomobject]@{
        Model    = $model
        Status   = $status
        ExitCode = 0
        Attempts = 0
        Seconds  = $sec
        Started  = $start
        Ended    = $end
        Why      = $why
      }
      Write-Host "WHATIF $model"
      continue
    }

    Write-Host "PULL  $model"

    try{
      $maxAttempts = 1 + [Math]::Max(0, $MaxRetries)

      for($i=1; $i -le $maxAttempts; $i++){
        $attempts = $i
        $exitCode = Invoke-OllamaPull -OllamaExe $Ollama -Model $model -TimeoutSec $TimeoutSec

        if($exitCode -eq 0){
          break
        }

        if($exitCode -ne 0 -and $i -lt $maxAttempts){
          Write-Warning "FAIL  $model  (ExitCode=$exitCode) retrying in ${RetryDelaySec}s ..."
          if($RetryDelaySec -gt 0){ Start-Sleep -Seconds $RetryDelaySec }
        }
      }

      $end  = Get-Date
      $sec  = [math]::Round(($end - $start).TotalSeconds, 2)

      if($exitCode -eq 0){
        $status = "PULLED"
        $why    = ""
        # Update installed cache robustly
        [void]$installed.Add($model)
        $norm = Normalize-ModelName $model
        if($norm){ [void]$installed.Add($norm) }

        Write-Host "OK    $model  (${sec}s)"
      }
      elseif($exitCode -eq 124){
        $status = "TIMED_OUT"
        $why    = "Exceeded TimeoutSec=$TimeoutSec"
        $anyFailed = $true
        Write-Warning "TIMEOUT $model  (${sec}s) $why"
      }
      else{
        $status = "FAILED"
        $why    = "ExitCode=$exitCode"
        $anyFailed = $true
        Write-Warning "FAIL  $model  (${sec}s) $why"
      }

      $results += [pscustomobject]@{
        Model    = $model
        Status   = $status
        ExitCode = $exitCode
        Attempts = $attempts
        Seconds  = $sec
        Started  = $start
        Ended    = $end
        Why      = $why
      }

      if($status -in @("FAILED","TIMED_OUT")){
        if(-not $ContinueOnError){
          Write-Warning "Stopping on first error (use -ContinueOnError to keep going)."
          break
        }
      }
    }
    catch{
      $end  = Get-Date
      $sec  = [math]::Round(($end - $start).TotalSeconds, 2)
      $status = "FAILED"
      $why = $_.Exception.Message
      $anyFailed = $true

      $results += [pscustomobject]@{
        Model    = $model
        Status   = $status
        ExitCode = 1
        Attempts = $attempts
        Seconds  = $sec
        Started  = $start
        Ended    = $end
        Why      = $why
      }

      Write-Warning "FAIL  $model  (${sec}s) $why"
      if(-not $ContinueOnError){ break }
    }

    Write-Host ""
  }

  # -----------------------------
  # Report
  # -----------------------------
  $results | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $Csv

  Write-Host ""
  Write-Host "Summary:"
  $results | Group-Object Status | Sort-Object Count -Descending | Format-Table Count,Name -AutoSize

  Write-Host ""
  Write-Host "Saved report: $Csv"
  Write-Host "Saved log   : $Log"
  Write-Host ""

  if($anyFailed){ exit 1 } else { exit 0 }
}
finally {
  if($transcriptStarted){
    try { Stop-Transcript | Out-Null } catch {}
  }
}
