<# 
.SYNOPSIS
  Install / repair Ollama on Windows and optionally configure model storage + basic health check.

.DESCRIPTION
  - Downloads the official Ollama Windows installer (default: https://ollama.com/download/OllamaSetup.exe)
  - Runs a silent install by default (Inno Setup style flags)
  - Ensures `ollama.exe` is discoverable (adds install dir to USER PATH if needed)
  - Optionally sets `OLLAMA_MODELS` (User scope) to control where models are stored
  - Optionally starts `ollama serve` if API isn't reachable
  - Optionally pulls one or more models

.PARAMETER Root
  Base folder for Francis ops layout (logs, data).

.PARAMETER InstallerUrl
  Where to download the installer from.

.PARAMETER InstallDir
  Optional custom install directory passed to installer (/DIR="...").
  If omitted, installer default is used.

.PARAMETER ModelsDir
  Where Ollama models should be stored (via OLLAMA_MODELS).

.PARAMETER SkipSignatureCheck
  Skip Authenticode signature validation on the downloaded installer.

.PARAMETER ForceReinstall
  Always run the installer even if Ollama appears installed.

.PARAMETER NoSetModelsEnv
  Do not set OLLAMA_MODELS.

.PARAMETER StartServerIfNeeded
  If API isn't reachable, attempt to start `ollama serve` in the background.

.PARAMETER PullModels
  One or more models to pull after installation (can be large; optional).

.PARAMETER Interactive
  Run the installer interactively (no /SILENT flags).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File D:\francis\scripts\ollama-install.ps1

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File D:\francis\scripts\ollama-install.ps1 `
    -ModelsDir "D:\LLM\Ollama\models" -PullModels @("llama3.2","mistral") -StartServerIfNeeded

.NOTES
  Docs reference:
  - Install dir can be changed with /DIR="..." and models dir with OLLAMA_MODELS. :contentReference[oaicite:3]{index=3}
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [string]$Root = "D:\francis",

  [string]$InstallerUrl = "https://ollama.com/download/OllamaSetup.exe",

  [string]$InstallDir = "",

  [string]$ModelsDir = (Join-Path "D:\francis" "data\models\ollama"),

  [switch]$SkipSignatureCheck,

  [switch]$ForceReinstall,

  [switch]$NoSetModelsEnv,

  [switch]$StartServerIfNeeded,

  [string[]]$PullModels = @(),

  [switch]$Interactive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# --- Time + logging paths
$Now    = Get-Date -Format "yyyyMMdd_HHmmss"
$LogDir = Join-Path $Root "data\logs\operations"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$MainLog = Join-Path $LogDir "ollama_install_$Now.log"
$SetupLog = Join-Path $LogDir "ollama_setup_$Now.log"

function Write-Log {
  param(
    [Parameter(Mandatory=$true)][string]$Message,
    [ValidateSet("INFO","WARN","ERROR")][string]$Level = "INFO"
  )
  $line = "{0} [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Level, $Message
  $line | Tee-Object -FilePath $MainLog -Append
}

function Ensure-Dir([string]$Path){
  if([string]::IsNullOrWhiteSpace($Path)){ return }
  if(-not (Test-Path -LiteralPath $Path)){
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
  }
}

function Get-UserPath {
  return [Environment]::GetEnvironmentVariable("Path","User")
}

function Set-UserPath([string]$NewValue){
  [Environment]::SetEnvironmentVariable("Path", $NewValue, "User")
}

function Add-ToUserPath([string]$Dir){
  if([string]::IsNullOrWhiteSpace($Dir)){ return }
  $DirNorm = $Dir.TrimEnd('\')
  $p = Get-UserPath
  if([string]::IsNullOrWhiteSpace($p)){
    Set-UserPath $DirNorm
    return
  }

  $parts = $p.Split(';') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
  if($parts -contains $DirNorm){ return }

  $new = ($parts + $DirNorm) -join ';'
  Set-UserPath $new
}

function Resolve-OllamaExe {
  # 1) PATH
  $cmd = Get-Command ollama -ErrorAction SilentlyContinue
  if($cmd -and $cmd.Source -and (Test-Path -LiteralPath $cmd.Source)){
    return $cmd.Source
  }

  # 2) Common install locations (per docs + common sense)
  $candidates = @()

  # docs mention: %LOCALAPPDATA%\Programs\Ollama and %PROGRAMFILES%\Ollama :contentReference[oaicite:4]{index=4}
  $local = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
  $pf    = Join-Path ${env:ProgramFiles} "Ollama\ollama.exe"
  $candidates += @($local, $pf)

  if(-not [string]::IsNullOrWhiteSpace($InstallDir)){
    $candidates += (Join-Path $InstallDir "ollama.exe")
  }

  foreach($c in $candidates){
    if(Test-Path -LiteralPath $c){ return $c }
  }

  # 3) Light search (bounded)
  $roots = @()
  if(Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA "Programs\Ollama")){ $roots += (Join-Path $env:LOCALAPPDATA "Programs\Ollama") }
  if(Test-Path -LiteralPath (Join-Path ${env:ProgramFiles} "Ollama")){ $roots += (Join-Path ${env:ProgramFiles} "Ollama") }
  if(-not [string]::IsNullOrWhiteSpace($InstallDir) -and (Test-Path -LiteralPath $InstallDir)){ $roots += $InstallDir }

  foreach($r in $roots | Select-Object -Unique){
    try {
      $hit = Get-ChildItem -LiteralPath $r -Recurse -File -Filter "ollama.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
      if($hit){ return $hit.FullName }
    } catch {}
  }

  return $null
}

function Test-OllamaApi {
  param([int]$TimeoutSec = 2)

  # Docs: API local address is localhost:11434 :contentReference[oaicite:5]{index=5}
  $uri = "http://localhost:11434/api/tags"
  try {
    $resp = Invoke-WebRequest -Uri $uri -Method GET -TimeoutSec $TimeoutSec -ErrorAction Stop
    if($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300){ return $true }
    return $false
  } catch {
    return $false
  }
}

function Start-OllamaServe([string]$OllamaExe){
  if([string]::IsNullOrWhiteSpace($OllamaExe) -or -not (Test-Path -LiteralPath $OllamaExe)){
    throw "Cannot start server: ollama.exe not found"
  }

  Write-Log "Attempting to start: `"$OllamaExe`" serve"
  try {
    # Start hidden, don’t block
    Start-Process -FilePath $OllamaExe -ArgumentList @("serve") -WindowStyle Hidden | Out-Null
  } catch {
    throw "Failed to start `ollama serve`: $($_.Exception.Message)"
  }
}

function Download-File {
  param(
    [Parameter(Mandatory=$true)][string]$Url,
    [Parameter(Mandatory=$true)][string]$OutFile
  )

  # TLS hardening for Windows PowerShell 5.1
  try {
    [Net.ServicePointManager]::SecurityProtocol = `
      [Net.SecurityProtocolType]::Tls12 -bor `
      [Net.SecurityProtocolType]::Tls11 -bor `
      [Net.SecurityProtocolType]::Tls
  } catch {}

  Write-Log "Downloading installer: $Url"
  Ensure-Dir (Split-Path -Parent $OutFile)

  $bits = Get-Command Start-BitsTransfer -ErrorAction SilentlyContinue
  if($bits){
    try {
      Start-BitsTransfer -Source $Url -Destination $OutFile -ErrorAction Stop
      return
    } catch {
      Write-Log "BITS download failed, falling back to Invoke-WebRequest: $($_.Exception.Message)" "WARN"
    }
  }

  $iwParams = @{
    Uri         = $Url
    OutFile     = $OutFile
    ErrorAction = "Stop"
  }
  if($PSVersionTable.PSVersion.Major -lt 6){
    $iwParams.UseBasicParsing = $true
  }
  Invoke-WebRequest @iwParams
}

function Assert-InstallerSignature {
  param([Parameter(Mandatory=$true)][string]$Path)

  $sig = Get-AuthenticodeSignature -FilePath $Path
  if($sig.Status -ne "Valid"){
    $msg = "Installer signature is not valid. Status=$($sig.Status); Message=$($sig.StatusMessage)"
    throw $msg
  }
}

# --- Start
Write-Log "=== Ollama install start ($Now) ==="
Write-Log "Root=$Root"
Write-Log "InstallerUrl=$InstallerUrl"
if($InstallDir){ Write-Log "InstallDir=$InstallDir" }
Write-Log "ModelsDir=$ModelsDir"
Write-Log "Log=$MainLog"

# Preflight OS
if($env:OS -notlike "*Windows*"){
  throw "This script is intended for Windows."
}

# Check existing install
$existingExe = Resolve-OllamaExe
if($existingExe){
  Write-Log "Found existing ollama.exe at: $existingExe"
  try {
    $ver = & $existingExe --version 2>$null
    if($ver){ Write-Log "Existing version: $ver" }
  } catch {}
} else {
  Write-Log "No existing ollama.exe detected via PATH/common locations."
}

$shouldInstall = $ForceReinstall.IsPresent -or (-not $existingExe)

if($shouldInstall){
  $dl = Join-Path $env:TEMP ("OllamaSetup_{0}.exe" -f $Now)

  if($PSCmdlet.ShouldProcess($InstallerUrl, "Download Ollama installer")){
    Download-File -Url $InstallerUrl -OutFile $dl
    Write-Log "Downloaded to: $dl"
  }

  if(-not $SkipSignatureCheck){
    if($PSCmdlet.ShouldProcess($dl, "Validate Authenticode signature")){
      Write-Log "Validating installer signature..."
      Assert-InstallerSignature -Path $dl
      Write-Log "Installer signature: VALID"
    }
  } else {
    Write-Log "Skipping signature check (SkipSignatureCheck set)." "WARN"
  }

  # Build installer args (Inno Setup)
  $args = New-Object System.Collections.Generic.List[string]
  if(-not $Interactive){
    $args.Add("/SILENT")
    $args.Add("/NORESTART")
    $args.Add("/LOG=`"$SetupLog`"")
    if($InstallDir){
      $args.Add("/DIR=`"$InstallDir`"")
    }
  } else {
    Write-Log "Interactive install requested (no silent flags)."
    if($InstallDir){
      # Still pass /DIR in interactive mode if supplied
      $args.Add("/DIR=`"$InstallDir`"")
    }
  }

  Write-Log ("Running installer: {0} {1}" -f $dl, ($args -join " "))
  if($PSCmdlet.ShouldProcess($dl, "Run Ollama installer")){
    $p = Start-Process -FilePath $dl -ArgumentList $args -Wait -PassThru
    Write-Log "Installer exit code: $($p.ExitCode)"
    if($p.ExitCode -ne 0){
      throw "Installer exited with code $($p.ExitCode). Check setup log: $SetupLog"
    }
  }

  # Re-resolve after install
  $existingExe = Resolve-OllamaExe
  if(-not $existingExe){
    throw "Install completed but ollama.exe still not found. If you used a custom InstallDir, confirm it contains ollama.exe."
  }

  Write-Log "Post-install ollama.exe: $existingExe"
} else {
  Write-Log "Skipping install (already present). Use -ForceReinstall to re-run installer."
}

# Ensure models dir and env var
if(-not $NoSetModelsEnv){
  Ensure-Dir $ModelsDir

  # Set user env var
  Write-Log "Setting OLLAMA_MODELS (User) => $ModelsDir"
  [Environment]::SetEnvironmentVariable("OLLAMA_MODELS", $ModelsDir, "User")
  $env:OLLAMA_MODELS = $ModelsDir
} else {
  Write-Log "Not setting OLLAMA_MODELS (NoSetModelsEnv set)."
}

# Ensure ollama.exe directory is in PATH (User)
$ollamaExe = Resolve-OllamaExe
if(-not $ollamaExe){ throw "ollama.exe not found after install/resolve step." }

$ollamaDir = Split-Path -Parent $ollamaExe
Write-Log "Ensuring ollama directory is in USER PATH: $ollamaDir"
Add-ToUserPath $ollamaDir

# Refresh current session PATH so `ollama` works immediately
if($env:Path -notlike "*$ollamaDir*"){
  $env:Path = ($env:Path.TrimEnd(';') + ";" + $ollamaDir)
}

# Basic health check
$apiOk = Test-OllamaApi -TimeoutSec 2
if($apiOk){
  Write-Log "Ollama API reachable on localhost:11434"
} else {
  Write-Log "Ollama API NOT reachable on localhost:11434" "WARN"
  if($StartServerIfNeeded){
    Start-OllamaServe -OllamaExe $ollamaExe
    Start-Sleep -Seconds 2
    $apiOk2 = Test-OllamaApi -TimeoutSec 3
    if($apiOk2){
      Write-Log "Ollama API is reachable after starting 'ollama serve'."
      $apiOk = $true
    } else {
      Write-Log "Still cannot reach API after starting 'ollama serve'." "WARN"
    }
  }
}

# Optional model pulls
if($PullModels -and $PullModels.Count -gt 0){
  foreach($m in $PullModels){
    if([string]::IsNullOrWhiteSpace($m)){ continue }
    Write-Log "Pulling model: $m"
    try {
      & $ollamaExe pull $m | Tee-Object -FilePath $MainLog -Append
    } catch {
      Write-Log "Model pull failed for '$m': $($_.Exception.Message)" "ERROR"
      throw
    }
  }
}

# Final version report
try {
  $ver = & $ollamaExe --version 2>$null
  if($ver){ Write-Log "Installed version: $ver" }
} catch {}

Write-Log "=== Ollama install complete ==="
Write-Output ""
Write-Output ("Log: {0}" -f $MainLog)
Write-Output ("SetupLog: {0}" -f $SetupLog)
Write-Output ("ollama.exe: {0}" -f $ollamaExe)
if(-not $NoSetModelsEnv){
  Write-Output ("OLLAMA_MODELS (User): {0}" -f $ModelsDir)
}
Write-Output ("API reachable: {0}" -f $apiOk)
