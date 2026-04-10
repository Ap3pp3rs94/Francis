<#
  industrial-calibrate.ps1 (Full Drop)

  Purpose:
    "Calibrate" a Windows workstation for industrial / kiosk / production usage by:
      - collecting a baseline snapshot (OS/HW/network/time/power/services/printers)
      - running sanity/health checks (DNS/DC discovery, ports, disk space, event log errors)
      - optionally applying a standard baseline config:
          * set power plan
          * disable sleep/hibernate
          * stage DNS servers on active NICs
          * ensure key services are running (Spooler, W32Time, etc.)
          * optionally set timezone + resync time

  SAFE DEFAULT:
    - DRY RUN unless -Execute is provided
    - Supports -WhatIf and -Confirm (ShouldProcess)

  Output:
    - Logs + JSON report + CSV checks under:
        C:\Francis\data\logs\operations\industrial_calibrate\

  Examples:
    # Dry run: gather info + checks only
    pwsh -File C:\Francis\scripts\industrial-calibrate.ps1 -DomainName corp.example.com

    # Apply baseline (power plan + sleep/hibernate + ensure services), then show results
    pwsh -File C:\Francis\scripts\industrial-calibrate.ps1 -Execute `
      -DomainName corp.example.com -PowerPlan HighPerformance -DisableSleep -DisableHibernate `
      -EnsureServices Spooler,W32Time -RestartIfNeeded

    # Stage DNS to DC/DNS IPs, then run connectivity checks
    pwsh -File C:\Francis\scripts\industrial-calibrate.ps1 -Execute `
      -DomainName corp.example.com -DnsServers 10.0.0.10,10.0.0.11 -EnsureServices W32Time `
      -TestTargets corp.example.com,fileserver01,printer01 -TestPorts "fileserver01:445","corp.example.com:389"

    # Set timezone + resync time (common for kiosks/pos)
    pwsh -File C:\Francis\scripts\industrial-calibrate.ps1 -Execute `
      -TimeZone "Eastern Standard Time" -NtpServer time.windows.com -ResyncTime
#>

[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='Medium')]
param(
  [Parameter()][string]$Root = "C:\Francis",
  [Parameter()][string]$Tag  = "industrial_calibrate",
  [Parameter()][switch]$Execute,

  # Optional environment hints (checks become smarter if provided)
  [Parameter()][string]$DomainName,

  # Optional network tests
  [Parameter()][string[]]$TestTargets = @(),
  # Format: "host:port"
  [Parameter()][string[]]$TestPorts   = @(),

  # Optional configuration actions
  [Parameter()][ValidateSet("Balanced","HighPerformance","UltimatePerformance")][string]$PowerPlan = "Balanced",
  [Parameter()][switch]$DisableSleep,
  [Parameter()][switch]$DisableHibernate,

  [Parameter()][string[]]$DnsServers = @(),
  [Parameter()][string[]]$KeepAdapterName = @(),

  [Parameter()][string[]]$EnsureServices = @("Spooler","W32Time"),
  [Parameter()][switch]$SetServicesAutomatic,

  [Parameter()][string]$TimeZone,
  [Parameter()][string]$NtpServer,
  [Parameter()][switch]$ResyncTime,

  [Parameter()][switch]$RestartIfNeeded,
  [Parameter()][switch]$Force
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
  try { $Obj | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $Path -Encoding UTF8 }
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
    $msg = $_.Exception.Message
    Write-Log $msg $OnError
    return $null
  }
}

# -----------------------------
# Networking helpers
# -----------------------------
function Get-ActiveAdapters {
  $cmd = Get-Command Get-NetAdapter -ErrorAction SilentlyContinue
  if (-not $cmd) { return @() }

  Get-NetAdapter | Where-Object {
    $_.Status -eq 'Up' -and $_.HardwareInterface -eq $true
  }
}

function Get-AdapterDnsServers {
  $cmd = Get-Command Get-DnsClientServerAddress -ErrorAction SilentlyContinue
  if (-not $cmd) { return @() }

  $out = @()
  foreach ($a in (Get-ActiveAdapters)) {
    $dns = Get-DnsClientServerAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue
    $servers = @()
    if ($dns -and $dns.ServerAddresses) { $servers = @($dns.ServerAddresses) }
    $out += [pscustomobject]@{ Adapter=$a.Name; Servers=($servers -join ",") }
  }
  return $out
}

function Set-DnsServersOnAdapters {
  param([string[]]$Servers, [string[]]$KeepNames)

  if (-not $Servers -or $Servers.Count -eq 0) {
    Add-Check "CONFIG" "DNS staging" "SKIPPED" "No DnsServers provided"
    return @()
  }

  $cmd = Get-Command Set-DnsClientServerAddress -ErrorAction SilentlyContinue
  if (-not $cmd) {
    Add-Check "CONFIG" "DNS staging" "FAILED" "Set-DnsClientServerAddress not available"
    return @()
  }

  $adapters = @(Get-ActiveAdapters)
  if (-not $adapters -or $adapters.Count -eq 0) {
    Add-Check "CONFIG" "DNS staging" "FAILED" "No UP hardware adapters found"
    return @()
  }

  $touched = @()
  foreach ($a in $adapters) {
    if ($KeepNames -and ($KeepNames -contains $a.Name)) {
      Write-Log ("Skip DNS staging for adapter: {0}" -f $a.Name) "INFO"
      continue
    }

    $action = ("Set DNS on adapter '{0}' to: {1}" -f $a.Name, ($Servers -join ", "))
    if ($PSCmdlet.ShouldProcess($a.Name, $action)) {
      Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ServerAddresses $Servers -ErrorAction Stop
      $touched += $a.Name
    }
  }

  if ($touched.Count -gt 0) {
    Add-Check "CONFIG" "DNS staging" "PASSED" ("Updated adapters: {0}" -f ($touched -join ", "))
  } else {
    Add-Check "CONFIG" "DNS staging" "WARN" "No adapters updated (all skipped?)"
  }

  return $touched
}

function Get-DomainControllersFromDNS {
  param([string]$Domain)

  if ([string]::IsNullOrWhiteSpace($Domain)) { return @() }

  $srv = "_ldap._tcp.dc._msdcs.$Domain"
  $dcs = New-Object System.Collections.Generic.HashSet[string]

  $cmd = Get-Command Resolve-DnsName -ErrorAction SilentlyContinue
  if (-not $cmd) { return @() }

  try {
    $records = Resolve-DnsName -Name $srv -Type SRV -ErrorAction Stop
    foreach ($r in $records) {
      if ($r.NameTarget) { [void]$dcs.Add(($r.NameTarget.TrimEnd('.')).ToLowerInvariant()) }
    }
  } catch {
    # Best effort only
  }

  return @($dcs)
}

function Test-Port {
  param([string]$Host, [int]$Port)
  try {
    return (Test-NetConnection -ComputerName $Host -Port $Port -InformationLevel Quiet)
  } catch { return $false }
}

function Test-Target {
  param([string]$Target)

  $dnsOk = $false
  $pingOk = $false
  $ip = ""

  $cmdDns = Get-Command Resolve-DnsName -ErrorAction SilentlyContinue
  if ($cmdDns) {
    try {
      $r = Resolve-DnsName -Name $Target -ErrorAction Stop | Select-Object -First 1
      if ($r -and $r.IPAddress) { $ip = $r.IPAddress; $dnsOk = $true }
      else { $dnsOk = $true } # resolved but no IP field returned
    } catch { $dnsOk = $false }
  } else {
    $dnsOk = $true # can't verify; don't fail solely for this
  }

  try {
    $pingOk = (Test-Connection -ComputerName $Target -Count 2 -Quiet -ErrorAction Stop)
  } catch { $pingOk = $false }

  return [pscustomobject]@{
    Target = $Target
    DnsOk  = $dnsOk
    IP     = $ip
    PingOk = $pingOk
  }
}

# -----------------------------
# Power / Time helpers
# -----------------------------
function Get-PowerPlans {
  $plans = @()
  try {
    $raw = powercfg /L 2>$null
    foreach ($line in $raw) {
      # Example: "Power Scheme GUID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx  (Balanced) *"
      if ($line -match "Power Scheme GUID:\s+([0-9a-fA-F-]{36})\s+\((.+?)\)\s*(\*)?") {
        $plans += [pscustomobject]@{
          Guid     = $Matches[1]
          Name     = $Matches[2]
          Active   = [bool]($Matches[3])
        }
      }
    }
  } catch { }
  return $plans
}

function Set-PowerPlanByName {
  param([ValidateSet("Balanced","HighPerformance","UltimatePerformance")][string]$Plan)

  $plans = Get-PowerPlans
  if (-not $plans -or $plans.Count -eq 0) {
    Add-Check "CONFIG" "Power plan" "FAILED" "powercfg plans not readable"
    return $false
  }

  # Match common names:
  $targetNames = switch ($Plan) {
    "Balanced"            { @("Balanced") }
    "HighPerformance"     { @("High performance","High Performance") }
    "UltimatePerformance" { @("Ultimate Performance") }
  }

  $match = $plans | Where-Object { $targetNames -contains $_.Name } | Select-Object -First 1
  if (-not $match) {
    Add-Check "CONFIG" "Power plan" "WARN" ("Requested '{0}' not found. Available: {1}" -f $Plan, (($plans.Name | Sort-Object -Unique) -join "; "))
    return $false
  }

  $action = ("Set power plan to '{0}' ({1})" -f $match.Name, $match.Guid)
  if ($PSCmdlet.ShouldProcess($env:COMPUTERNAME, $action)) {
    powercfg /S $match.Guid | Out-Null
    Add-Check "CONFIG" "Power plan" "PASSED" ("Set to: {0}" -f $match.Name)
    return $true
  }

  Add-Check "CONFIG" "Power plan" "SKIPPED" "ShouldProcess declined"
  return $false
}

function Disable-SleepAndDisplayTimeouts {
  # Sets AC/DC timeouts to "Never" for standby + monitor (common industrial/kiosk baseline)
  $action = "Disable sleep + display timeouts (AC/DC) via powercfg"
  if ($PSCmdlet.ShouldProcess($env:COMPUTERNAME, $action)) {
    powercfg /X standby-timeout-ac 0 | Out-Null
    powercfg /X standby-timeout-dc 0 | Out-Null
    powercfg /X monitor-timeout-ac 0 | Out-Null
    powercfg /X monitor-timeout-dc 0 | Out-Null
    Add-Check "CONFIG" "Disable sleep" "PASSED" "Standby + monitor timeouts set to 0 (Never)"
    return $true
  }
  Add-Check "CONFIG" "Disable sleep" "SKIPPED" "ShouldProcess declined"
  return $false
}

function Disable-Hibernate {
  $action = "Disable hibernate via powercfg /H off"
  if ($PSCmdlet.ShouldProcess($env:COMPUTERNAME, $action)) {
    powercfg /H off | Out-Null
    Add-Check "CONFIG" "Disable hibernate" "PASSED" "Hibernate disabled"
    return $true
  }
  Add-Check "CONFIG" "Disable hibernate" "SKIPPED" "ShouldProcess declined"
  return $false
}

function Set-TimeZoneSafe {
  param([string]$Tz)

  if ([string]::IsNullOrWhiteSpace($Tz)) {
    Add-Check "CONFIG" "Time zone" "SKIPPED" "No TimeZone provided"
    return $false
  }

  $cmd = Get-Command Set-TimeZone -ErrorAction SilentlyContinue
  if (-not $cmd) {
    Add-Check "CONFIG" "Time zone" "FAILED" "Set-TimeZone not available"
    return $false
  }

  $action = ("Set time zone to '{0}'" -f $Tz)
  if ($PSCmdlet.ShouldProcess($env:COMPUTERNAME, $action)) {
    Set-TimeZone -Id $Tz -ErrorAction Stop
    Add-Check "CONFIG" "Time zone" "PASSED" ("Set to: {0}" -f $Tz)
    return $true
  }

  Add-Check "CONFIG" "Time zone" "SKIPPED" "ShouldProcess declined"
  return $false
}

function Configure-NtpIfProvided {
  param([string]$Server)

  if ([string]::IsNullOrWhiteSpace($Server)) {
    Add-Check "CONFIG" "NTP server" "SKIPPED" "No NtpServer provided"
    return $false
  }

  # w32time config
  $action = ("Configure W32Time manual peer list: {0}" -f $Server)
  if ($PSCmdlet.ShouldProcess($env:COMPUTERNAME, $action)) {
    w32tm /config /manualpeerlist:$Server /syncfromflags:manual /update | Out-Null
    Add-Check "CONFIG" "NTP server" "PASSED" ("Configured: {0}" -f $Server)
    return $true
  }

  Add-Check "CONFIG" "NTP server" "SKIPPED" "ShouldProcess declined"
  return $false
}

function Resync-TimeIfRequested {
  if (-not $ResyncTime) {
    Add-Check "CONFIG" "Time resync" "SKIPPED" "ResyncTime not requested"
    return $false
  }

  $action = "Resync time (w32tm /resync)"
  if ($PSCmdlet.ShouldProcess($env:COMPUTERNAME, $action)) {
    w32tm /resync | Out-Null
    Add-Check "CONFIG" "Time resync" "PASSED" "Resync requested"
    return $true
  }

  Add-Check "CONFIG" "Time resync" "SKIPPED" "ShouldProcess declined"
  return $false
}

# -----------------------------
# Services / Printers
# -----------------------------
function Ensure-ServiceState {
  param(
    [string]$Name,
    [switch]$SetAuto
  )

  $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
  if (-not $svc) {
    Add-Check "SERVICES" $Name "WARN" "Service not found"
    return $false
  }

  if ($SetAuto) {
    try {
      if ($PSCmdlet.ShouldProcess($Name, "Set StartupType = Automatic")) {
        Set-Service -Name $Name -StartupType Automatic -ErrorAction Stop
      }
    } catch {
      Add-Check "SERVICES" $Name "WARN" ("Failed to set StartupType Automatic: {0}" -f $_.Exception.Message)
    }
  }

  if ($svc.Status -ne 'Running') {
    $action = "Start service"
    if ($PSCmdlet.ShouldProcess($Name, $action)) {
      try {
        Start-Service -Name $Name -ErrorAction Stop
        Add-Check "SERVICES" $Name "PASSED" "Started"
        return $true
      } catch {
        Add-Check "SERVICES" $Name "FAILED" ("Failed to start: {0}" -f $_.Exception.Message)
        return $false
      }
    } else {
      Add-Check "SERVICES" $Name "SKIPPED" "ShouldProcess declined"
      return $false
    }
  } else {
    Add-Check "SERVICES" $Name "PASSED" "Already running"
    return $true
  }
}

function Get-PrinterSnapshot {
  $cmd = Get-Command Get-Printer -ErrorAction SilentlyContinue
  if (-not $cmd) { return @() }

  Get-Printer | Select-Object Name,DriverName,PortName,PrinterStatus,Shared,Published
}

# -----------------------------
# Initialize output/log
# -----------------------------
$RootResolved = Resolve-FSPath $Root
$OutDir = Join-Path $RootResolved "data\logs\operations\industrial_calibrate"
New-Dir $OutDir

$Now = Get-Date -Format "yyyyMMdd_HHmmss"
$script:LogFile = Join-Path $OutDir ("{0}_{1}.log" -f $Tag, $Now)
$JsonPath       = Join-Path $OutDir ("{0}_{1}.json" -f $Tag, $Now)
$CsvPath        = Join-Path $OutDir ("{0}_{1}_checks.csv" -f $Tag, $Now)

$script:Checks = New-Object System.Collections.Generic.List[object]

Write-Log ("Industrial calibrate start. Execute={0} Force={1}" -f [bool]$Execute, [bool]$Force) "STEP"

$admin = Test-IsAdmin
Write-Log ("IsAdmin={0}" -f $admin) "INFO"
Add-Check "PRECHECK" "Admin" ($(if($admin){"PASSED"}else{"WARN"})) ($(if($admin){"Running elevated"}else{"Not elevated (changes may fail)"}))

if ($Execute -and -not $admin) {
  Write-Log "Execute requested but not elevated. Run PowerShell as Administrator." "ERROR"
  throw "Not running as Administrator."
}

# -----------------------------
# Baseline snapshot
# -----------------------------
Write-Log "Collecting baseline snapshot..." "STEP"

$os  = Get-CimInstance Win32_OperatingSystem
$cs  = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$bios= Get-CimInstance Win32_BIOS

$netAdapters = Try-Do { Get-ActiveAdapters } "WARN"
$dnsNow = Try-Do { Get-AdapterDnsServers } "WARN"

$printers = Try-Do { Get-PrinterSnapshot } "WARN"

$disks = @()
Try-Do {
  $disks = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" |
    Select-Object DeviceID, VolumeName,
      @{n="SizeGB";e={[math]::Round($_.Size/1GB,2)}},
      @{n="FreeGB";e={[math]::Round($_.FreeSpace/1GB,2)}},
      @{n="FreePct";e={ if($_.Size -gt 0){ [math]::Round(($_.FreeSpace/$_.Size)*100,1)} else {0}}}
} "WARN" | Out-Null

# Event log quick stats (last 24h)
$evStats = @()
Try-Do {
  $since = (Get-Date).AddHours(-24)
  $levels = @{
    1="Critical"; 2="Error"; 3="Warning"
  }
  foreach ($kv in $levels.GetEnumerator()) {
    $count = (Get-WinEvent -FilterHashtable @{LogName="System"; Level=$kv.Key; StartTime=$since} -ErrorAction SilentlyContinue).Count
    $evStats += [pscustomobject]@{ Log="System"; Level=$kv.Value; Count=$count }
  }
} "WARN" | Out-Null

# Domain/DC discovery (if DomainName provided)
$dcs = @()
if (-not [string]::IsNullOrWhiteSpace($DomainName)) {
  $dcs = @(Get-DomainControllersFromDNS -Domain $DomainName)
  if ($dcs.Count -gt 0) {
    Add-Check "NETWORK" "Domain DC discovery" "PASSED" ("Found: {0}" -f ($dcs -join ", "))
  } else {
    Add-Check "NETWORK" "Domain DC discovery" "WARN" "No DCs discovered via DNS SRV"
  }
} else {
  Add-Check "NETWORK" "Domain DC discovery" "SKIPPED" "No DomainName provided"
}

# Disk free space checks
foreach ($d in $disks) {
  if ($d.FreePct -lt 10) {
    Add-Check "STORAGE" ("Disk {0}" -f $d.DeviceID) "FAILED" ("Low free space: {0}% free ({1}GB/{2}GB)" -f $d.FreePct, $d.FreeGB, $d.SizeGB)
  } elseif ($d.FreePct -lt 20) {
    Add-Check "STORAGE" ("Disk {0}" -f $d.DeviceID) "WARN" ("Getting low: {0}% free ({1}GB/{2}GB)" -f $d.FreePct, $d.FreeGB, $d.SizeGB)
  } else {
    Add-Check "STORAGE" ("Disk {0}" -f $d.DeviceID) "PASSED" ("Free: {0}% ({1}GB/{2}GB)" -f $d.FreePct, $d.FreeGB, $d.SizeGB)
  }
}

# -----------------------------
# Planned / applied configuration
# -----------------------------
if (-not $Execute) {
  Write-Log "DRY RUN: No config changes will be made (use -Execute to apply)." "WARN"
} else {
  Write-Log "EXECUTE MODE: Applying requested calibration actions..." "STEP"

  # Power plan
  Try-Do { Set-PowerPlanByName -Plan $PowerPlan } "WARN" | Out-Null

  # Sleep / Hibernate
  if ($DisableSleep)     { Try-Do { Disable-SleepAndDisplayTimeouts } "WARN" | Out-Null }
  else { Add-Check "CONFIG" "Disable sleep" "SKIPPED" "DisableSleep not requested" }

  if ($DisableHibernate) { Try-Do { Disable-Hibernate } "WARN" | Out-Null }
  else { Add-Check "CONFIG" "Disable hibernate" "SKIPPED" "DisableHibernate not requested" }

  # DNS staging
  Try-Do { Set-DnsServersOnAdapters -Servers $DnsServers -KeepNames $KeepAdapterName } "WARN" | Out-Null

  # Timezone / NTP
  Try-Do { Set-TimeZoneSafe -Tz $TimeZone } "WARN" | Out-Null
  Try-Do { Configure-NtpIfProvided -Server $NtpServer } "WARN" | Out-Null
  Try-Do { Resync-TimeIfRequested } "WARN" | Out-Null

  # Services ensure running
  if ($EnsureServices -and $EnsureServices.Count -gt 0) {
    foreach ($s in $EnsureServices) {
      Try-Do { Ensure-ServiceState -Name $s -SetAuto:$SetServicesAutomatic } "WARN" | Out-Null
    }
  } else {
    Add-Check "SERVICES" "EnsureServices" "SKIPPED" "No services specified"
  }
}

# -----------------------------
# Connectivity tests
# -----------------------------
Write-Log "Running connectivity tests..." "STEP"

# Targets: use user-provided targets; also fold in DCs if found
$targets = New-Object System.Collections.Generic.HashSet[string]
foreach ($t in $TestTargets) { if (-not [string]::IsNullOrWhiteSpace($t)) { [void]$targets.Add($t) } }
foreach ($dc in $dcs) { if (-not [string]::IsNullOrWhiteSpace($dc)) { [void]$targets.Add($dc) } }

$targetResults = @()
foreach ($t in @($targets)) {
  $r = Test-Target -Target $t
  $targetResults += $r

  if (-not $r.DnsOk) {
    Add-Check "NETWORK" ("DNS {0}" -f $t) "FAILED" "DNS resolution failed"
  } else {
    Add-Check "NETWORK" ("DNS {0}" -f $t) "PASSED" ($(if($r.IP){"Resolved to $($r.IP)"}else{"Resolved"}))
  }

  if (-not $r.PingOk) {
    Add-Check "NETWORK" ("PING {0}" -f $t) "WARN" "Ping failed (may be blocked)"
  } else {
    Add-Check "NETWORK" ("PING {0}" -f $t) "PASSED" "Ping OK"
  }
}

# Port tests (host:port)
$portResults = @()
foreach ($hp in $TestPorts) {
  if ([string]::IsNullOrWhiteSpace($hp)) { continue }
  if ($hp -notmatch "^(.*):(\d+)$") {
    Add-Check "NETWORK" ("PORT {0}" -f $hp) "WARN" "Invalid format (expected host:port)"
    continue
  }
  $host = $Matches[1]
  $port = [int]$Matches[2]
  $ok = Test-Port -Host $host -Port $port
  $portResults += [pscustomobject]@{ Host=$host; Port=$port; Open=$ok }

  Add-Check "NETWORK" ("PORT {0}:{1}" -f $host, $port) ($(if($ok){"PASSED"}else{"FAILED"})) ($(if($ok){"Open"}else{"Closed/Blocked"}))
}

# Common DC ports (if DomainName provided and DCs found)
if ($dcs.Count -gt 0) {
  foreach ($dc in ($dcs | Select-Object -First 3)) {
    foreach ($p in 53,88,389,445,636) {
      $ok = Test-Port -Host $dc -Port $p
      Add-Check "NETWORK" ("DC {0}:{1}" -f $dc, $p) ($(if($ok){"PASSED"}else{"WARN"})) ($(if($ok){"Reachable"}else{"Not reachable"}))
    }
  }
}

# -----------------------------
# Build final report + export
# -----------------------------
$plans = Get-PowerPlans
$activePlan = ($plans | Where-Object { $_.Active } | Select-Object -First 1)

$report = [ordered]@{
  When = (Get-Date)
  Execute = [bool]$Execute

  Machine = [ordered]@{
    ComputerName = $env:COMPUTERNAME
    User         = ("{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME)
    IsAdmin      = $admin
  }

  Requested = [ordered]@{
    Root              = $RootResolved
    DomainName        = $DomainName
    TestTargets       = $TestTargets
    TestPorts         = $TestPorts

    PowerPlan         = $PowerPlan
    DisableSleep      = [bool]$DisableSleep
    DisableHibernate  = [bool]$DisableHibernate

    DnsServers        = $DnsServers
    KeepAdapterName   = $KeepAdapterName

    EnsureServices    = $EnsureServices
    SetServicesAuto   = [bool]$SetServicesAutomatic

    TimeZone          = $TimeZone
    NtpServer         = $NtpServer
    ResyncTime        = [bool]$ResyncTime

    RestartIfNeeded   = [bool]$RestartIfNeeded
    Force             = [bool]$Force
  }

  Snapshot = [ordered]@{
    OS = [ordered]@{
      Caption     = $os.Caption
      Version     = $os.Version
      BuildNumber = $os.BuildNumber
      InstallDate = $os.InstallDate
      LastBoot    = $os.LastBootUpTime
    }
    Hardware = [ordered]@{
      Manufacturer = $cs.Manufacturer
      Model        = $cs.Model
      TotalRAM_GB  = [math]::Round($cs.TotalPhysicalMemory/1GB,2)
      CPU          = $cpu.Name
      BIOS         = $bios.SMBIOSBIOSVersion
      Serial       = $bios.SerialNumber
    }
    Network = [ordered]@{
      ActiveAdapters = @($netAdapters | Select-Object Name,InterfaceDescription,ifIndex,LinkSpeed,MacAddress)
      DnsPerAdapter  = @($dnsNow)
    }
    Power = [ordered]@{
      ActivePlan = $(if($activePlan){ $activePlan.Name } else { "" })
      Plans      = @($plans)
    }
    Storage = @($disks)
    Printers = @($printers)
    EventLogLast24h = @($evStats)
  }

  Discovery = [ordered]@{
    DCs = $dcs
  }

  Tests = [ordered]@{
    Targets = @($targetResults)
    Ports   = @($portResults)
  }

  Checks = @($script:Checks)
}

Export-Json -Path $JsonPath -Obj $report
$script:Checks | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $CsvPath

# Summary output
Write-Log ("Saved log:   {0}" -f $script:LogFile) "OK"
Write-Log ("Saved JSON:  {0}" -f $JsonPath) "OK"
Write-Log ("Saved CSV:   {0}" -f $CsvPath) "OK"

Write-Host ""
Write-Host "=== CHECK SUMMARY ==="
$script:Checks | Group-Object Status | Sort-Object Count -Descending | Format-Table Count,Name -AutoSize
Write-Host ""
Write-Host "=== TOP FAIL/WARN ==="
$script:Checks | Where-Object { $_.Status -in @("FAILED","WARN") } |
  Select-Object Category,Item,Status,Details |
  Format-Table -AutoSize

# Optional restart guidance
if ($Execute -and $RestartIfNeeded) {
  # If we set power/time configs, a restart isn't strictly required, but can help ensure domain/time services stabilize.
  $action = "Restart computer (RestartIfNeeded requested)"
  if ($PSCmdlet.ShouldProcess($env:COMPUTERNAME, $action)) {
    Write-Log "Restarting now (RestartIfNeeded requested)..." "WARN"
    Restart-Computer -Force:$Force
  }
}

Write-Log "Industrial calibrate complete." "OK"
