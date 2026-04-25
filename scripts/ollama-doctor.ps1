<#
  D:\francis\scripts\ollama-doctor.ps1

  What it does (non-destructive by default):
    - Detects ollama.exe (PATH + common install locations)
    - Captures version + basic CLI output (ollama version/list/ps)
    - Checks server reachability (default http://127.0.0.1:11434)
      - GET /api/version
      - GET /api/tags
    - Checks whether port 11434 is listening
    - Checks for Ollama process + Windows service (if present)
    - Enumerates GPU(s) (Win32_VideoController) + optional nvidia-smi
    - Finds likely model directories and measures size (can be expensive on big stores)
    - Captures proxy environment + WinHTTP proxy
    - Pulls recent Windows Event Log entries that mention "Ollama" (best effort)
    - Writes:
        - log file
        - JSON report
        - CSV checks

  Safe default:
    - DRY RUN: no changes
    - Use -Execute plus an action switch to attempt fixes

  Examples:
    # Pure diagnostics (recommended first run)
    pwsh -File D:\francis\scripts\ollama-doctor.ps1

    # Diagnose a remote/alternate host
    pwsh -File D:\francis\scripts\ollama-doctor.ps1 -HostUrl "http://localhost:11434"

    # Attempt to start/restart service if present (only with -Execute)
    pwsh -File D:\francis\scripts\ollama-doctor.ps1 -Execute -StartServiceIfStopped

    # Try to start server in user session (only if service not found, only with -Execute)
    pwsh -File D:\francis\scripts\ollama-doctor.ps1 -Execute -StartServerIfNotRunning

    # Skip model directory size scan (faster)
    pwsh -File D:\francis\scripts\ollama-doctor.ps1 -SkipModelSize

#>

[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='Medium')]
param(
  [Parameter()][string]$Root = "D:\francis",
  [Parameter()][string]$Tag  = "ollama_doctor",

  # Default Ollama local server
  [Parameter()][string]$HostUrl = "http://127.0.0.1:11434",

  # Behavior
  [Parameter()][switch]$Execute,
  [Parameter()][int]$HttpTimeoutSec = 4,
  [Parameter()][int]$EventLogHours  = 24,

  # Potential fixes (only do anything when -Execute is set)
  [Parameter()][switch]$StartServiceIfStopped,
  [Parameter()][switch]$RestartService,
  [Parameter()][switch]$StartServerIfNotRunning,

  # Performance knobs
  [Parameter()][switch]$SkipModelSize,

  # Optional: add extra model paths you know about
  [Parameter()][string[]]$ExtraModelPaths = @()
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

function Export-Json {
  param([string]$Path, $Obj)
  try { $Obj | ConvertTo-Json -Depth 14 | Set-Content -LiteralPath $Path -Encoding UTF8 }
  catch { Write-Log ("JSON export failed: {0}" -f $_.Exception.Message) "WARN" }
}

function Add-Check {
  param(
    [string]$Category,
    [string]$Item,
    [ValidateSet("PASSED","WARN","FAILED","SKIPPED")][string]$Status,
    [string]$Details = ""
  )
  $script:Checks.Add([pscustomobject]@{
    Category = $Category
    Item     = $Item
    Status   = $Status
    Details  = $Details
  }) | Out-Null
}

function Try-Do {
  param(
    [scriptblock]$Block,
    [string]$OnError = "WARN"
  )
  try { & $Block }
  catch {
    Write-Log $_.Exception.Message $OnError
    return $null
  }
}

function Invoke-CommandSafe {
  param(
    [string]$Exe,
    [string[]]$Args = @(),
    [int]$MaxLines = 120
  )
  if ([string]::IsNullOrWhiteSpace($Exe) -or -not (Test-Path -LiteralPath $Exe)) {
    return [pscustomobject]@{ ExitCode = 127; Stdout = @(); Stderr = @("exe not found") }
  }

  $tmpOut = New-TemporaryFile
  $tmpErr = New-TemporaryFile

  try {
    $p = Start-Process -FilePath $Exe -ArgumentList $Args -NoNewWindow -PassThru `
      -RedirectStandardOutput $tmpOut.FullName -RedirectStandardError $tmpErr.FullName
    $p.WaitForExit()

    $o = @()
    $e = @()
    if (Test-Path $tmpOut.FullName) { $o = Get-Content -LiteralPath $tmpOut.FullName -ErrorAction SilentlyContinue }
    if (Test-Path $tmpErr.FullName) { $e = Get-Content -LiteralPath $tmpErr.FullName -ErrorAction SilentlyContinue }

    return [pscustomobject]@{
      ExitCode = $p.ExitCode
      Stdout   = @($o | Select-Object -First $MaxLines)
      Stderr   = @($e | Select-Object -First $MaxLines)
    }
  } finally {
    Remove-Item -LiteralPath $tmpOut.FullName -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tmpErr.FullName -Force -ErrorAction SilentlyContinue
  }
}

function Normalize-Url([string]$u) {
  if ([string]::IsNullOrWhiteSpace($u)) { return $u }
  return $u.TrimEnd("/")
}

function Test-HttpJson {
  param(
    [string]$Url,
    [int]$TimeoutSec = 4
  )
  try {
    $resp = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec $TimeoutSec -ErrorAction Stop
    return [pscustomobject]@{ Ok=$true; Data=$resp; Error="" }
  } catch {
    return [pscustomobject]@{ Ok=$false; Data=$null; Error=$_.Exception.Message }
  }
}

function Get-ListeningPortInfo {
  param([int]$Port)
  $cmd = Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue
  if ($cmd) {
    try {
      $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop
      return @($conns | Select-Object LocalAddress,LocalPort,OwningProcess)
    } catch { return @() }
  } else {
    # Fallback: netstat parse
    $out = @()
    Try-Do {
      $lines = netstat -ano | Select-String -Pattern "LISTENING" | Select-String -Pattern (":$Port\s")
      foreach ($l in $lines) { $out += $l.Line }
    } "WARN" | Out-Null
    return $out
  }
}

function Measure-DirSize {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) { return $null }
  try {
    $sum = 0L
    Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction Stop | ForEach-Object { $sum += $_.Length }
    return $sum
  } catch {
    return $null
  }
}

function Get-ProxyInfo {
  $envProxy = [ordered]@{
    HTTP_PROXY  = $env:HTTP_PROXY
    HTTPS_PROXY = $env:HTTPS_PROXY
    NO_PROXY    = $env:NO_PROXY
  }
  $winhttp = Try-Do { (netsh winhttp show proxy 2>$null) } "WARN"
  return [pscustomobject]@{
    Env    = $envProxy
    WinHTTP = @($winhttp)
  }
}

function Find-OllamaExe {
  # 1) PATH
  $cmd = Get-Command ollama -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source -and (Test-Path -LiteralPath $cmd.Source)) {
    return $cmd.Source
  }

  # 2) Common locations (best effort)
  $candidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"),
    (Join-Path $env:ProgramFiles "Ollama\ollama.exe"),
    (Join-Path $env:ProgramFiles "Ollama\bin\ollama.exe"),
    (Join-Path $env:ProgramFiles "Ollama\ollama.exe"),
    "C:\Ollama\ollama.exe"
  ) | Where-Object { $_ -and $_ -ne "" } | Select-Object -Unique

  foreach ($p in $candidates) {
    if (Test-Path -LiteralPath $p) { return $p }
  }

  return $null
}

function Find-OllamaService {
  # Service names can vary; search broadly.
  try {
    $svcs = Get-CimInstance Win32_Service -ErrorAction Stop |
      Where-Object { $_.Name -match "ollama" -or $_.DisplayName -match "ollama" }
    return @($svcs | Select-Object Name,DisplayName,State,StartMode,PathName)
  } catch {
    return @()
  }
}

function Get-GpuInfo {
  $gpus = @()
  Try-Do {
    $gpus = Get-CimInstance Win32_VideoController |
      Select-Object Name,AdapterCompatibility,DriverVersion,VideoProcessor,
        @{n="VRAM_GB";e={ if($_.AdapterRAM){ [math]::Round($_.AdapterRAM/1GB,2)} else { $null } }}
  } "WARN" | Out-Null

  $nvidia = $null
  $nvsmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
  if ($nvsmi) {
    $nvidia = Invoke-CommandSafe -Exe $nvsmi.Source -Args @("-L") -MaxLines 40
  }

  return [pscustomobject]@{
    VideoControllers = @($gpus)
    NvidiaSmi_L     = $nvidia
  }
}

function Get-ModelPaths {
  $paths = New-Object System.Collections.Generic.HashSet[string]

  if ($env:OLLAMA_MODELS) { [void]$paths.Add($env:OLLAMA_MODELS) }
  foreach ($p in $ExtraModelPaths) {
    if (-not [string]::IsNullOrWhiteSpace($p)) { [void]$paths.Add($p) }
  }

  # Common guesses
  $guesses = @(
    (Join-Path $env:USERPROFILE ".ollama\models"),
    (Join-Path $env:USERPROFILE ".ollama"),
    (Join-Path $env:LOCALAPPDATA "Ollama\models"),
    (Join-Path $env:LOCALAPPDATA "Ollama"),
    (Join-Path $env:APPDATA "Ollama"),
    (Join-Path $env:ProgramData "Ollama\models"),
    (Join-Path $env:ProgramData "Ollama")
  ) | Where-Object { $_ -and $_ -ne "" }

  foreach ($g in $guesses) { [void]$paths.Add($g) }

  $existing = @()
  foreach ($p in @($paths)) {
    try {
      if (Test-Path -LiteralPath $p) {
        $existing += (Resolve-FSPath $p)
      }
    } catch { }
  }

  return @($existing | Select-Object -Unique)
}

# -----------------------------
# Init output
# -----------------------------
$RootResolved = Resolve-FSPath $Root
$OutDir = Join-Path $RootResolved "data\logs\operations\ollama_doctor"
New-Dir $OutDir

$Now = Get-Date -Format "yyyyMMdd_HHmmss"
$script:LogFile = Join-Path $OutDir ("{0}_{1}.log" -f $Tag, $Now)
$JsonPath       = Join-Path $OutDir ("{0}_{1}.json" -f $Tag, $Now)
$CsvPath        = Join-Path $OutDir ("{0}_{1}_checks.csv" -f $Tag, $Now)

$script:Checks = New-Object System.Collections.Generic.List[object]

Write-Log ("Ollama doctor start. Execute={0}" -f [bool]$Execute) "STEP"

$admin = Test-IsAdmin
Add-Check "PRECHECK" "Admin" ($(if($admin){"PASSED"}else{"WARN"})) ($(if($admin){"Running elevated"}else{"Not elevated (fix actions may fail)"}))

if ($Execute -and (-not $admin) -and ($StartServiceIfStopped -or $RestartService)) {
  Write-Log "Service actions requested but not elevated. Run PowerShell as Administrator." "ERROR"
  throw "Not running as Administrator (required for service actions)."
}

$hostBase = Normalize-Url $HostUrl

# -----------------------------
# Detect Ollama binary
# -----------------------------
Write-Log "Detecting ollama.exe..." "STEP"
$ollamaExe = Find-OllamaExe

if ($ollamaExe) {
  Add-Check "OLLAMA" "Binary" "PASSED" $ollamaExe
  Write-Log ("ollama.exe: {0}" -f $ollamaExe) "OK"
} else {
  Add-Check "OLLAMA" "Binary" "FAILED" "ollama.exe not found in PATH or common locations"
  Write-Log "ollama.exe not found." "ERROR"
}

# Basic CLI
$cli = [ordered]@{}
if ($ollamaExe) {
  $ver = Invoke-CommandSafe -Exe $ollamaExe -Args @("version") -MaxLines 20
  $cli.Version = $ver
  if ($ver.ExitCode -eq 0) {
    Add-Check "OLLAMA" "CLI version" "PASSED" (($ver.Stdout -join " ") -replace "\s+"," ").Trim()
  } else {
    Add-Check "OLLAMA" "CLI version" "WARN" (($ver.Stderr -join " ") -replace "\s+"," ").Trim()
  }

  $list = Invoke-CommandSafe -Exe $ollamaExe -Args @("list") -MaxLines 200
  $cli.List = $list
  if ($list.ExitCode -eq 0) {
    Add-Check "OLLAMA" "CLI list" "PASSED" ("ExitCode 0; lines={0}" -f $list.Stdout.Count)
  } else {
    Add-Check "OLLAMA" "CLI list" "WARN" ("ExitCode {0}; {1}" -f $list.ExitCode, (($list.Stderr | Select-Object -First 1) -as [string]))
  }

  $ps = Invoke-CommandSafe -Exe $ollamaExe -Args @("ps") -MaxLines 200
  $cli.PS = $ps
  if ($ps.ExitCode -eq 0) {
    Add-Check "OLLAMA" "CLI ps" "PASSED" ("ExitCode 0; lines={0}" -f $ps.Stdout.Count)
  } else {
    Add-Check "OLLAMA" "CLI ps" "WARN" ("ExitCode {0}; {1}" -f $ps.ExitCode, (($ps.Stderr | Select-Object -First 1) -as [string]))
  }
}

# -----------------------------
# Process / service detection
# -----------------------------
Write-Log "Checking process/service..." "STEP"

$proc = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
if ($proc) {
  Add-Check "RUNTIME" "Process" "PASSED" ("ollama PID(s): {0}" -f (($proc.Id -join ", ")))
} else {
  Add-Check "RUNTIME" "Process" "WARN" "ollama process not detected"
}

$services = Find-OllamaService
if ($services.Count -gt 0) {
  $svcSummary = ($services | ForEach-Object { "{0}({1}/{2})" -f $_.Name, $_.State, $_.StartMode }) -join "; "
  Add-Check "RUNTIME" "Service" "PASSED" $svcSummary
} else {
  Add-Check "RUNTIME" "Service" "SKIPPED" "No Windows service matching 'Ollama' found"
}

# Optional service actions
if ($Execute -and $services.Count -gt 0) {
  $primary = $services | Select-Object -First 1
  $svcName = $primary.Name

  if ($RestartService) {
    $action = "Restart service '$svcName'"
    if ($PSCmdlet.ShouldProcess($env:COMPUTERNAME, $action)) {
      Try-Do { Restart-Service -Name $svcName -Force -ErrorAction Stop } "ERROR" | Out-Null
      Add-Check "FIX" "Restart service" "PASSED" $svcName
    } else {
      Add-Check "FIX" "Restart service" "SKIPPED" "ShouldProcess declined"
    }
  }
  elseif ($StartServiceIfStopped) {
    try {
      $svc = Get-Service -Name $svcName -ErrorAction Stop
      if ($svc.Status -ne "Running") {
        $action = "Start service '$svcName'"
        if ($PSCmdlet.ShouldProcess($env:COMPUTERNAME, $action)) {
          Start-Service -Name $svcName -ErrorAction Stop
          Add-Check "FIX" "Start service" "PASSED" $svcName
        } else {
          Add-Check "FIX" "Start service" "SKIPPED" "ShouldProcess declined"
        }
      } else {
        Add-Check "FIX" "Start service" "SKIPPED" "Service already running"
      }
    } catch {
      Add-Check "FIX" "Start service" "FAILED" $_.Exception.Message
    }
  }
}

# Optional: start server in user session (only if no service & no process detected)
if ($Execute -and $StartServerIfNotRunning -and -not $proc -and ($services.Count -eq 0) -and $ollamaExe) {
  $action = "Start 'ollama serve' (user session background process)"
  if ($PSCmdlet.ShouldProcess($env:COMPUTERNAME, $action)) {
    try {
      Start-Process -FilePath $ollamaExe -ArgumentList @("serve") -WindowStyle Hidden | Out-Null
      Add-Check "FIX" "Start server" "PASSED" "Started 'ollama serve' (user session)"
    } catch {
      Add-Check "FIX" "Start server" "FAILED" $_.Exception.Message
    }
  } else {
    Add-Check "FIX" "Start server" "SKIPPED" "ShouldProcess declined"
  }
}

# -----------------------------
# Port / API checks
# -----------------------------
Write-Log "Checking port 11434 and API..." "STEP"

$listen = Get-ListeningPortInfo -Port 11434
if ($listen -and $listen.Count -gt 0) {
  Add-Check "NETWORK" "Port 11434 listen" "PASSED" ("Listening entries: {0}" -f $listen.Count)
} else {
  Add-Check "NETWORK" "Port 11434 listen" "WARN" "No LISTEN detected on 11434"
}

$api = [ordered]@{}
$apiVersion = Test-HttpJson -Url ("{0}/api/version" -f $hostBase) -TimeoutSec $HttpTimeoutSec
$apiTags    = Test-HttpJson -Url ("{0}/api/tags"    -f $hostBase) -TimeoutSec $HttpTimeoutSec

$api.Version = $apiVersion
$api.Tags    = $apiTags

if ($apiVersion.Ok) {
  Add-Check "API" "GET /api/version" "PASSED" "OK"
} else {
  Add-Check "API" "GET /api/version" "FAILED" $apiVersion.Error
}

if ($apiTags.Ok) {
  # tags response often contains a "models" array; best-effort count
  $count = $null
  try { if ($apiTags.Data -and $apiTags.Data.models) { $count = @($apiTags.Data.models).Count } } catch { }
  Add-Check "API" "GET /api/tags" "PASSED" ($(if($null -ne $count){"models=$count"}else{"OK"}))
} else {
  Add-Check "API" "GET /api/tags" "FAILED" $apiTags.Error
}

# -----------------------------
# Model storage checks
# -----------------------------
Write-Log "Checking model storage paths..." "STEP"

$modelPaths = Get-ModelPaths
$modelInfo  = @()

if ($modelPaths.Count -eq 0) {
  Add-Check "STORAGE" "Model paths" "WARN" "No likely model directories found (or not accessible)"
} else {
  Add-Check "STORAGE" "Model paths" "PASSED" ($modelPaths -join "; ")
}

foreach ($p in $modelPaths) {
  $exists = Test-Path -LiteralPath $p
  $sizeBytes = $null

  if ($exists -and -not $SkipModelSize) {
    Write-Log ("Measuring size: {0} (can take a while)..." -f $p) "INFO"
    $sizeBytes = Measure-DirSize -Path $p
  }

  $modelInfo += [pscustomobject]@{
    Path       = $p
    Exists     = $exists
    SizeGB     = $(if($null -ne $sizeBytes){ [math]::Round($sizeBytes/1GB,2) } else { $null })
    SizeBytes  = $sizeBytes
    SizeScanned= [bool](-not $SkipModelSize)
  }
}

if ($SkipModelSize) {
  Add-Check "STORAGE" "Model size scan" "SKIPPED" "SkipModelSize specified"
} else {
  # Flag if any scanned sizes are null due to access errors
  $scanned = $modelInfo | Where-Object { $_.Exists -and $_.SizeScanned }
  if ($scanned.Count -gt 0 -and ($scanned | Where-Object { $null -eq $_.SizeBytes }).Count -gt 0) {
    Add-Check "STORAGE" "Model size scan" "WARN" "One or more paths could not be sized (permissions/long paths)"
  } elseif ($scanned.Count -gt 0) {
    Add-Check "STORAGE" "Model size scan" "PASSED" ("Scanned {0} path(s)" -f $scanned.Count)
  } else {
    Add-Check "STORAGE" "Model size scan" "SKIPPED" "No existing paths to scan"
  }
}

# -----------------------------
# GPU / system snapshot
# -----------------------------
Write-Log "Collecting GPU/system snapshot..." "STEP"

$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$gpu = Get-GpuInfo

if ($gpu.VideoControllers.Count -gt 0) {
  Add-Check "HARDWARE" "GPU detected" "PASSED" (($gpu.VideoControllers | ForEach-Object { $_.Name }) -join "; ")
} else {
  Add-Check "HARDWARE" "GPU detected" "WARN" "No Win32_VideoController entries found"
}

if ($gpu.NvidiaSmi_L -and $gpu.NvidiaSmi_L.ExitCode -eq 0) {
  Add-Check "HARDWARE" "nvidia-smi" "PASSED" (($gpu.NvidiaSmi_L.Stdout -join " | ") -replace "\s+"," ").Trim()
} elseif ($gpu.NvidiaSmi_L) {
  Add-Check "HARDWARE" "nvidia-smi" "WARN" (($gpu.NvidiaSmi_L.Stderr | Select-Object -First 1) -as [string])
} else {
  Add-Check "HARDWARE" "nvidia-smi" "SKIPPED" "nvidia-smi not found"
}

# -----------------------------
# Proxy / env snapshot
# -----------------------------
Write-Log "Collecting proxy + env snapshot..." "STEP"
$proxy = Get-ProxyInfo

# Ollama-related env vars
$ollamaEnv = [ordered]@{
  OLLAMA_HOST        = $env:OLLAMA_HOST
  OLLAMA_ORIGINS     = $env:OLLAMA_ORIGINS
  OLLAMA_MODELS      = $env:OLLAMA_MODELS
  OLLAMA_KEEP_ALIVE  = $env:OLLAMA_KEEP_ALIVE
  OLLAMA_DEBUG       = $env:OLLAMA_DEBUG
}

# -----------------------------
# Event logs (best effort)
# -----------------------------
Write-Log ("Collecting Event Log mentions of 'Ollama' (last {0}h)..." -f $EventLogHours) "STEP"
$events = @()
Try-Do {
  $since = (Get-Date).AddHours(-1 * [math]::Abs($EventLogHours))
  $events = Get-WinEvent -FilterHashtable @{ LogName="Application"; StartTime=$since } -ErrorAction SilentlyContinue |
    Where-Object { $_.Message -match "Ollama" -or $_.ProviderName -match "Ollama" } |
    Select-Object -First 80 TimeCreated,Id,LevelDisplayName,ProviderName,Message
} "WARN" | Out-Null

if ($events.Count -gt 0) {
  Add-Check "LOGS" "EventLog Application" "PASSED" ("Found {0} entries" -f $events.Count)
} else {
  Add-Check "LOGS" "EventLog Application" "SKIPPED" "No matching events found"
}

# -----------------------------
# Build report
# -----------------------------
$report = [ordered]@{
  When = (Get-Date)
  Execute = [bool]$Execute

  Machine = [ordered]@{
    ComputerName = $env:COMPUTERNAME
    User         = ("{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME)
    IsAdmin      = $admin
  }

  Requested = [ordered]@{
    Root                   = $RootResolved
    HostUrl                = $HostUrl
    HttpTimeoutSec         = $HttpTimeoutSec
    EventLogHours          = $EventLogHours

    StartServiceIfStopped  = [bool]$StartServiceIfStopped
    RestartService         = [bool]$RestartService
    StartServerIfNotRunning= [bool]$StartServerIfNotRunning

    SkipModelSize          = [bool]$SkipModelSize
    ExtraModelPaths        = $ExtraModelPaths
  }

  Snapshot = [ordered]@{
    OS = [ordered]@{
      Caption     = $os.Caption
      Version     = $os.Version
      BuildNumber = $os.BuildNumber
      LastBoot    = $os.LastBootUpTime
    }
    Hardware = [ordered]@{
      Manufacturer = $cs.Manufacturer
      Model        = $cs.Model
      TotalRAM_GB  = [math]::Round($cs.TotalPhysicalMemory/1GB,2)
      CPU          = $cpu.Name
    }
    Proxy = $proxy
    Env   = [ordered]@{
      Ollama = $ollamaEnv
    }
  }

  Ollama = [ordered]@{
    ExePath    = $ollamaExe
    CLI        = $cli
    Services   = $services
    Process    = @($proc | Select-Object Name,Id,Path,StartTime -ErrorAction SilentlyContinue)
    Port11434  = $listen
    API        = $api
    ModelPaths = $modelInfo
    GPU        = $gpu
    EventLog   = @($events)
  }

  Checks = @($script:Checks)
}

Export-Json -Path $JsonPath -Obj $report
$script:Checks | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $CsvPath

# -----------------------------
# Summary output
# -----------------------------
Write-Log ("Saved log:  {0}" -f $script:LogFile) "OK"
Write-Log ("Saved JSON: {0}" -f $JsonPath) "OK"
Write-Log ("Saved CSV:  {0}" -f $CsvPath) "OK"

Write-Host ""
Write-Host "=== CHECK SUMMARY ==="
$script:Checks | Group-Object Status | Sort-Object Count -Descending | Format-Table Count,Name -AutoSize

Write-Host ""
Write-Host "=== FAIL/WARN DETAILS ==="
$script:Checks | Where-Object { $_.Status -in @("FAILED","WARN") } |
  Select-Object Category,Item,Status,Details |
  Format-Table -AutoSize

Write-Log "Ollama doctor complete." "OK"
