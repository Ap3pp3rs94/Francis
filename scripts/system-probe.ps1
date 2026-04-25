<#
D:\francis\scripts\system-probe.ps1

Purpose
  "System probe" / inventory + diagnostics snapshot for the Francis environment.
  Produces a JSON report + CSV tooling table + transcript log under:
    <Root>\data\logs\operations\

What it collects (best-effort, safe read-only)
  - OS + uptime
  - Computer system / BIOS
  - CPU + RAM
  - Disks/volumes
  - Network adapters + IPs
  - Key tools installed + versions (pwsh, python, node, npm, git, docker, wsl, ollama, etc.)
  - Optional: Ollama API health + installed models

Examples
  # Basic probe
  pwsh -File D:\francis\scripts\system-probe.ps1

  # Quick (less output)
  pwsh -File D:\francis\scripts\system-probe.ps1 -Quick

  # Include Ollama API/model inventory
  pwsh -File D:\francis\scripts\system-probe.ps1 -IncludeOllama

  # Include a public IP check (external call) - OFF by default
  pwsh -File D:\francis\scripts\system-probe.ps1 -IncludePublicIP

  # Save outputs somewhere else
  pwsh -File D:\francis\scripts\system-probe.ps1 -Root D:\Francis

Notes
  - No changes are made to the system.
  - Public IP lookup is disabled by default (needs internet).
  - Some fields require modules/cmdlets that may not exist on older Windows/PS builds; those are captured as errors in the report.
#>

[CmdletBinding()]
param(
  [string]$Root = 'D:\francis',

  # Reduce the amount of data collected (still writes JSON/CSV/log)
  [switch]$Quick,

  # Include Ollama API check + installed models (if ollama exists)
  [switch]$IncludeOllama,

  # External call to a public-IP endpoint (OFF by default)
  [switch]$IncludePublicIP,

  # If set, do not write transcript log
  [switch]$NoTranscript
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# -----------------------------
# Logging paths (Francis layout)
# -----------------------------
$Now    = Get-Date -Format "yyyyMMdd_HHmmss"
$OutDir = Join-Path $Root "data\logs\operations"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$LogPath  = Join-Path $OutDir "system_probe_$Now.log"
$JsonPath = Join-Path $OutDir "system_probe_$Now.json"
$CsvPath  = Join-Path $OutDir "system_probe_tools_$Now.csv"

if(-not $NoTranscript){
  try { Start-Transcript -Path $LogPath -Force | Out-Null } catch {}
}

function Write-Section([string]$Title){
  Write-Host ""
  Write-Host ("=" * 72)
  Write-Host $Title
  Write-Host ("=" * 72)
}

function Resolve-FullPath([string]$Path){
  try { return (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path }
  catch {
    try { return [System.IO.Path]::GetFullPath($Path) } catch { return $Path }
  }
}

$Errors = New-Object System.Collections.Generic.List[string]
function Add-Err([string]$Context, [string]$Message){
  $Errors.Add(("{0}: {1}" -f $Context, $Message)) | Out-Null
}

function Try-Get {
  param(
    [Parameter(Mandatory=$true)][string]$Context,
    [Parameter(Mandatory=$true)][scriptblock]$Script,
    $Default = $null
  )
  try { return & $Script }
  catch {
    Add-Err $Context $_.Exception.Message
    return $Default
  }
}

function Get-CommandInfo {
  param(
    [Parameter(Mandatory=$true)][string]$Name,
    [string[]]$VersionArgs = @('--version'),
    [int]$TimeoutSec = 4
  )

  $cmd = $null
  try { $cmd = Get-Command $Name -ErrorAction SilentlyContinue } catch {}

  if(-not $cmd -or -not $cmd.Source){
    return [pscustomobject]@{
      Name       = $Name
      Found      = $false
      Path       = $null
      Version    = $null
      FileVer    = $null
      Notes      = "Not found"
    }
  }

  $path = [string]$cmd.Source
  $fileVer = $null
  try {
    if(Test-Path -LiteralPath $path){
      $fileVer = (Get-Item -LiteralPath $path -ErrorAction SilentlyContinue).VersionInfo.FileVersion
    }
  } catch {}

  $verText = $null
  # Best-effort capture of "<cmd> --version" or similar
  try {
    $p = Start-Process -FilePath $path -ArgumentList $VersionArgs -PassThru -NoNewWindow `
      -RedirectStandardOutput ([System.IO.Path]::GetTempFileName()) `
      -RedirectStandardError  ([System.IO.Path]::GetTempFileName())

    $done = $p.WaitForExit($TimeoutSec * 1000)
    if(-not $done){
      try { $p.Kill() } catch {}
      $verText = "(timeout)"
    } else {
      $outFile = $p.StartInfo.RedirectStandardOutput
      $errFile = $p.StartInfo.RedirectStandardError
      # StartInfo paths not surfaced directly; fallback: just call synchronously if needed
      $verText = $null
    }
  } catch {
    # ignore; fallback to sync call below
  }

  if(-not $verText){
    try {
      $out = & $path @VersionArgs 2>&1
      if($out){
        $verText = (($out | Select-Object -First 2) -join " ").Trim()
      }
    } catch {
      # ignore
    }
  }

  return [pscustomobject]@{
    Name       = $Name
    Found      = $true
    Path       = $path
    Version    = $verText
    FileVer    = $fileVer
    Notes      = ""
  }
}

function Get-Uptime {
  # Returns a friendly object, best-effort
  $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
  $boot = $os.LastBootUpTime
  $uptime = (Get-Date) - $boot
  return [pscustomobject]@{
    LastBoot = $boot
    Uptime   = [string]$uptime
    UptimeDays = [math]::Round($uptime.TotalDays, 3)
  }
}

function Get-IPv4List {
  # Best-effort: use Get-NetIPAddress if available, else WMI
  $out = @()

  $netIp = Get-Command Get-NetIPAddress -ErrorAction SilentlyContinue
  if($netIp){
    try {
      $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
        Where-Object { $_.IPAddress -and $_.IPAddress -notlike '169.254*' } |
        Select-Object InterfaceAlias, IPAddress, PrefixLength
      return @($ips)
    } catch {
      Add-Err "Network:Get-NetIPAddress" $_.Exception.Message
    }
  }

  try {
    $cfgs = Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "IPEnabled=True" -ErrorAction Stop
    foreach($c in $cfgs){
      foreach($ip in @($c.IPAddress)){
        if($ip -and $ip -match '^\d{1,3}(\.\d{1,3}){3}$' -and $ip -notlike '169.254*'){
          $out += [pscustomobject]@{
            InterfaceAlias = $c.Description
            IPAddress      = $ip
            PrefixLength   = $null
          }
        }
      }
    }
  } catch {
    Add-Err "Network:WMI" $_.Exception.Message
  }

  return $out
}

function Test-TcpPort {
  param(
    [string]$Host = '127.0.0.1',
    [int]$Port = 11434,
    [int]$TimeoutMs = 600
  )
  try {
    $client = New-Object System.Net.Sockets.TcpClient
    $iar = $client.BeginConnect($Host, $Port, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
    if(-not $ok){
      try { $client.Close() } catch {}
      return $false
    }
    $client.EndConnect($iar) | Out-Null
    $client.Close()
    return $true
  } catch {
    return $false
  }
}

# -----------------------------
# Collect data
# -----------------------------
Write-Section "System Probe"
Write-Host ("Root   : {0}" -f (Resolve-FullPath $Root))
Write-Host ("OutDir : {0}" -f (Resolve-FullPath $OutDir))
Write-Host ("JSON   : {0}" -f $JsonPath)
Write-Host ("CSV    : {0}" -f $CsvPath)
if(-not $NoTranscript){
  Write-Host ("Log    : {0}" -f $LogPath)
}
Write-Host ("Quick  : {0}" -f $Quick)
Write-Host ("Ollama : {0}" -f $IncludeOllama)
Write-Host ("PublicIP: {0}" -f $IncludePublicIP)

$report = [ordered]@{
  timestamp = (Get-Date).ToString("o")
  root      = (Resolve-FullPath $Root)
  host      = [ordered]@{
    computerName = $env:COMPUTERNAME
    userName     = $env:USERNAME
    userDomain   = $env:USERDOMAIN
    isAdmin      = (Try-Get -Context "Host:IsAdmin" -Script {
      $id = [Security.Principal.WindowsIdentity]::GetCurrent()
      $p  = New-Object Security.Principal.WindowsPrincipal($id)
      $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } -Default $false)
    timeZone     = (Try-Get -Context "Host:TimeZone" -Script { (Get-TimeZone).Id } -Default $null)
    psVersion    = [ordered]@{
      PSEdition = $PSVersionTable.PSEdition
      PSVersion = $PSVersionTable.PSVersion.ToString()
      CLRVersion= ($PSVersionTable.CLRVersion?.ToString())
      OS        = ($PSVersionTable.OS)
      Platform  = ($PSVersionTable.Platform)
    }
  }
  os        = $null
  uptime    = $null
  system    = $null
  bios      = $null
  cpu       = $null
  memory    = $null
  storage   = $null
  network   = $null
  tools     = @()
  ollama    = $null
  publicIP  = $null
  errors    = @()
}

# OS
$report.os = Try-Get -Context "OS" -Default $null -Script {
  $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
  [pscustomobject]@{
    Caption        = $os.Caption
    Version        = $os.Version
    BuildNumber    = $os.BuildNumber
    OSArchitecture = $os.OSArchitecture
    InstallDate    = $os.InstallDate
    Locale         = $os.Locale
  }
}

# Uptime
$report.uptime = Try-Get -Context "Uptime" -Default $null -Script { Get-Uptime }

# System / BIOS (skip some if Quick)
$report.system = Try-Get -Context "System" -Default $null -Script {
  $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
  [pscustomobject]@{
    Manufacturer       = $cs.Manufacturer
    Model              = $cs.Model
    TotalPhysicalMemory= $cs.TotalPhysicalMemory
    Domain             = $cs.Domain
    PartOfDomain       = $cs.PartOfDomain
    HypervisorPresent  = ($cs.HypervisorPresent)
    NumberOfProcessors = $cs.NumberOfProcessors
    NumberOfLogicalProcessors = $cs.NumberOfLogicalProcessors
  }
}

if(-not $Quick){
  $report.bios = Try-Get -Context "BIOS" -Default $null -Script {
    $b = Get-CimInstance Win32_BIOS -ErrorAction Stop
    [pscustomobject]@{
      Manufacturer = $b.Manufacturer
      SMBIOSBIOSVersion = $b.SMBIOSBIOSVersion
      SerialNumber = $b.SerialNumber
      ReleaseDate  = $b.ReleaseDate
    }
  }
}

# CPU + RAM
$report.cpu = Try-Get -Context "CPU" -Default $null -Script {
  $cpus = Get-CimInstance Win32_Processor -ErrorAction Stop
  $first = $cpus | Select-Object -First 1
  [pscustomobject]@{
    Name          = $first.Name
    Manufacturer  = $first.Manufacturer
    Cores         = ($cpus | Measure-Object -Property NumberOfCores -Sum).Sum
    Logical       = ($cpus | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum
    MaxClockMHz   = $first.MaxClockSpeed
  }
}

$report.memory = Try-Get -Context "Memory" -Default $null -Script {
  $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
  $totalKB = [double]$os.TotalVisibleMemorySize
  $freeKB  = [double]$os.FreePhysicalMemory
  [pscustomobject]@{
    TotalGB = [math]::Round(($totalKB/1024/1024), 2)
    FreeGB  = [math]::Round(($freeKB/1024/1024), 2)
    UsedGB  = [math]::Round((($totalKB-$freeKB)/1024/1024), 2)
  }
}

# Storage (volumes + fixed disks)
$report.storage = Try-Get -Context "Storage" -Default $null -Script {
  $drives = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" -ErrorAction Stop |
    Select-Object DeviceID, VolumeName, FileSystem, Size, FreeSpace

  $driveObjs = @($drives | ForEach-Object {
    [pscustomobject]@{
      Drive      = $_.DeviceID
      Label      = $_.VolumeName
      FileSystem = $_.FileSystem
      SizeGB     = if($_.Size){ [math]::Round(($_.Size/1GB), 2) } else { $null }
      FreeGB     = if($_.FreeSpace){ [math]::Round(($_.FreeSpace/1GB), 2) } else { $null }
      FreePct    = if($_.Size -and $_.FreeSpace){ [math]::Round(($_.FreeSpace/$_.Size*100), 1) } else { $null }
    }
  })

  $phys = $null
  if(-not $Quick){
    # best-effort physical disk list
    $phys = Try-Get -Context "Storage:PhysicalDisks" -Default @() -Script {
      # Prefer Get-PhysicalDisk, fallback to Win32_DiskDrive
      $gp = Get-Command Get-PhysicalDisk -ErrorAction SilentlyContinue
      if($gp){
        return @(Get-PhysicalDisk | Select-Object FriendlyName, MediaType, BusType, Size, HealthStatus, OperationalStatus)
      } else {
        return @(Get-CimInstance Win32_DiskDrive | Select-Object Model, InterfaceType, MediaType, Size, SerialNumber)
      }
    }
  }

  return [pscustomobject]@{
    Volumes = $driveObjs
    PhysicalDisks = $phys
  }
}

# Network
$report.network = Try-Get -Context "Network" -Default $null -Script {
  $ipv4 = @(Get-IPv4List)

  $dns = $null
  $gw  = $null

  $netipcfg = Get-Command Get-NetIPConfiguration -ErrorAction SilentlyContinue
  if($netipcfg -and -not $Quick){
    try {
      $cfg = Get-NetIPConfiguration -ErrorAction Stop
      $dns = @($cfg.DnsServer.ServerAddresses | Where-Object { $_ } | Select-Object -Unique)
      $gw  = @($cfg.IPv4DefaultGateway.NextHop | Where-Object { $_ } | Select-Object -Unique)
    } catch {
      Add-Err "Network:Get-NetIPConfiguration" $_.Exception.Message
    }
  }

  [pscustomobject]@{
    IPv4 = $ipv4
    DnsServers = $dns
    DefaultGateways = $gw
  }
}

# Tools inventory
Write-Section "Tooling"
$tools = @()

# PowerShell itself
$tools += [pscustomobject]@{
  Name    = 'powershell'
  Found   = $true
  Path    = $PSHOME
  Version = $PSVersionTable.PSVersion.ToString()
  FileVer = $null
  Notes   = $PSVersionTable.PSEdition
}

# Common commands
$tools += Get-CommandInfo -Name 'python' -VersionArgs @('--version')
$tools += Get-CommandInfo -Name 'py'     -VersionArgs @('-V')
$tools += Get-CommandInfo -Name 'node'   -VersionArgs @('--version')
$tools += Get-CommandInfo -Name 'npm'    -VersionArgs @('--version')
$tools += Get-CommandInfo -Name 'pnpm'   -VersionArgs @('--version')
$tools += Get-CommandInfo -Name 'yarn'   -VersionArgs @('--version')
$tools += Get-CommandInfo -Name 'git'    -VersionArgs @('--version')
$tools += Get-CommandInfo -Name 'docker' -VersionArgs @('--version')
$tools += Get-CommandInfo -Name 'wsl'    -VersionArgs @('--version')
$tools += Get-CommandInfo -Name 'ollama' -VersionArgs @('--version')
$tools += Get-CommandInfo -Name 'nvidia-smi' -VersionArgs @('--help')

# Remove null duplicates if any
$report.tools = @($tools)

$tools | Format-Table -AutoSize Name,Found,Version,Path

# Ollama details (optional)
if($IncludeOllama){
  Write-Section "Ollama Probe"
  $ollamaExe = ($tools | Where-Object { $_.Name -eq 'ollama' -and $_.Found } | Select-Object -First 1).Path
  $apiUp = Test-TcpPort -Host '127.0.0.1' -Port 11434 -TimeoutMs 600

  $oll = [ordered]@{
    exe        = $ollamaExe
    apiPort11434Reachable = $apiUp
    apiTags    = $null
    models     = @()
    errors     = @()
  }

  if($apiUp){
    $oll.apiTags = Try-Get -Context "Ollama:API /api/tags" -Default $null -Script {
      Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3
    }
    if($oll.apiTags -and $oll.apiTags.models){
      $oll.models = @($oll.apiTags.models | Select-Object name, size, modified_at)
    }
    Write-Host "Ollama API: reachable"
    if($oll.models.Count -gt 0){
      Write-Host ("Models: {0}" -f $oll.models.Count)
      $oll.models | Select-Object -First 20 | Format-Table -AutoSize name,size,modified_at
      if($oll.models.Count -gt 20){
        Write-Host ("(showing first 20; see JSON for full list)")
      }
    } else {
      Write-Host "Models: (none or not returned)"
    }
  } else {
    Write-Warning "Ollama API port 11434 not reachable on 127.0.0.1 (service may be stopped)."
    if($ollamaExe){
      # still try ollama list (may work if it auto-starts)
      $list = Try-Get -Context "Ollama:ollama list" -Default $null -Script {
        & $ollamaExe list 2>&1
      }
      if($list){
        $oll.apiTags = $null
        $oll.models = @()
        $oll.errors += "API not reachable; captured 'ollama list' output in transcript."
        $list | ForEach-Object { Write-Host $_ }
      }
    }
  }

  $report.ollama = $oll
}

# Public IP (optional)
if($IncludePublicIP){
  Write-Section "Public IP"
  $report.publicIP = Try-Get -Context "PublicIP" -Default $null -Script {
    # External call; keep it simple + short timeout
    (Invoke-RestMethod -Method Get -Uri "https://api.ipify.org?format=json" -TimeoutSec 4)
  }
  if($report.publicIP){
    Write-Host ("Public IP: {0}" -f $report.publicIP.ip)
  } else {
    Write-Warning "Public IP lookup failed (see errors in report)."
  }
}

# Final errors
$report.errors = @($Errors)

# -----------------------------
# Write outputs
# -----------------------------
Write-Section "Write outputs"

# CSV tools
try {
  $report.tools | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $CsvPath
  Write-Host ("Saved CSV : {0}" -f $CsvPath)
} catch {
  Add-Err "ExportCSV" $_.Exception.Message
}

# JSON report (deep)
try {
  $report | ConvertTo-Json -Depth 10 | Out-File -LiteralPath $JsonPath -Encoding UTF8 -Force
  Write-Host ("Saved JSON: {0}" -f $JsonPath)
} catch {
  Add-Err "ExportJSON" $_.Exception.Message
}

# Summary
Write-Section "Summary"
try {
  $osCap = $report.os.Caption
  $cpu   = $report.cpu.Name
  $ramT  = $report.memory.TotalGB
  $ramF  = $report.memory.FreeGB
  $up    = $report.uptime.UptimeDays

  Write-Host ("OS   : {0}" -f $osCap)
  Write-Host ("CPU  : {0}" -f $cpu)
  Write-Host ("RAM  : {0} GB total / {1} GB free" -f $ramT,$ramF)
  Write-Host ("Up   : {0} days" -f $up)

  if($report.storage -and $report.storage.Volumes){
    Write-Host ""
    Write-Host "Volumes:"
    $report.storage.Volumes | Format-Table -AutoSize Drive,Label,FileSystem,SizeGB,FreeGB,FreePct
  }

  if($report.network -and $report.network.IPv4){
    Write-Host ""
    Write-Host "IPv4:"
    $report.network.IPv4 | Format-Table -AutoSize InterfaceAlias,IPAddress,PrefixLength
  }

  if($IncludeOllama -and $report.ollama){
    Write-Host ""
    Write-Host ("Ollama API port 11434 reachable: {0}" -f $report.ollama.apiPort11434Reachable)
  }

  if($report.errors -and $report.errors.Count -gt 0){
    Write-Host ""
    Write-Warning ("Non-fatal collection errors: {0}" -f $report.errors.Count)
    $report.errors | Select-Object -First 15 | ForEach-Object { Write-Warning $_ }
    if($report.errors.Count -gt 15){
      Write-Host "(showing first 15; see JSON for full list)"
    }
  }
} catch {
  Write-Warning ("Summary generation failed: {0}" -f $_.Exception.Message)
}

if(-not $NoTranscript){
  try { Stop-Transcript | Out-Null } catch {}
}
