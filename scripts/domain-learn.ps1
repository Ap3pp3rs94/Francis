<#
  domain-learn.ps1 (Full Drop)

  What it does (read-only):
    - Detects domain/forest info (if domain-joined)
    - Collects: domain, forest, FSMO roles, domain controllers, trusts
    - Collects: default domain password policy
    - Collects: AD Sites/Subnets (if available)
    - Optional (off by default): users, computers, groups, OUs, GPOs
    - Captures helpful local/network context: logon server, DNS client config, IP config, time sync status
    - Exports: log, JSON summary, and multiple CSV datasets

  Output folder (default):
    D:\francis\data\logs\operations\domain_learn\

  Examples:
    # Quick domain learn (safe defaults)
    powershell -ExecutionPolicy Bypass -File D:\francis\scripts\domain-learn.ps1

    # Specify domain explicitly
    powershell -ExecutionPolicy Bypass -File D:\francis\scripts\domain-learn.ps1 -Domain "corp.example.com"

    # Include computers + users (limited)
    powershell -ExecutionPolicy Bypass -File D:\francis\scripts\domain-learn.ps1 -IncludeComputers -IncludeUsers -MaxComputers 2000 -MaxUsers 2000

    # Include GPO list (requires GroupPolicy module)
    powershell -ExecutionPolicy Bypass -File D:\francis\scripts\domain-learn.ps1 -IncludeGPOs
#>

[CmdletBinding(SupportsShouldProcess=$true)]
param(
  [Parameter()][string]$Root = "D:\francis",
  [Parameter()][string]$Domain = "",
  [Parameter()][string]$Tag = "domain_learn",

  # Output override (optional)
  [Parameter()][string]$OutDir = "",

  # Optional AD enumeration (OFF by default)
  [Parameter()][switch]$IncludeUsers,
  [Parameter()][switch]$IncludeComputers,
  [Parameter()][switch]$IncludeGroups,
  [Parameter()][switch]$IncludeOUs,
  [Parameter()][switch]$IncludeGPOs,

  # Safety limits for optional enumeration
  [Parameter()][int]$MaxUsers = 1000,
  [Parameter()][int]$MaxComputers = 1000,
  [Parameter()][int]$MaxGroups = 1000,

  # If set, store raw command outputs to individual .txt files too
  [Parameter()][switch]$ExportRawCommandOutput
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

function Try-Run {
  param(
    [Parameter(Mandatory=$true)][string]$Name,
    [Parameter(Mandatory=$true)][scriptblock]$Block
  )
  try {
    $v = & $Block
    return [pscustomobject]@{ Name=$Name; Ok=$true; Value=$v; Error=$null }
  } catch {
    return [pscustomobject]@{ Name=$Name; Ok=$false; Value=$null; Error=$_.Exception.Message }
  }
}

function Invoke-CommandCapture {
  param(
    [Parameter(Mandatory=$true)][string]$Exe,
    [Parameter()][string[]]$Args = @()
  )

  $cmd = "$Exe " + ($Args -join " ")
  Write-Log ("Running: {0}" -f $cmd) "INFO"

  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $Exe
  $psi.Arguments = ($Args -join " ")
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

  [pscustomobject]@{
    Command  = $cmd
    ExitCode = $p.ExitCode
    StdOut   = $stdout
    StdErr   = $stderr
  }
}

function Export-DatasetCsv {
  param(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)]$Data
  )
  try {
    if ($null -eq $Data) { return }
    if ($Data -is [System.Collections.IEnumerable] -and -not ($Data -is [string])) {
      $Data | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $Path
    } else {
      # Single object -> wrap
      @($Data) | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $Path
    }
  } catch {
    Write-Log ("Failed exporting CSV {0}: {1}" -f $Path, $_.Exception.Message) "WARN"
  }
}

# -----------------------------
# Initialize paths/logging
# -----------------------------
$RootResolved = Resolve-FSPath $Root

if ([string]::IsNullOrWhiteSpace($OutDir)) {
  $OutDir = Join-Path $RootResolved "data\logs\operations\domain_learn"
}

New-Dir $OutDir

$Now = Get-Date -Format "yyyyMMdd_HHmmss"
$script:LogFile = Join-Path $OutDir ("{0}_{1}.log"  -f $Tag, $Now)
$JsonPath       = Join-Path $OutDir ("{0}_{1}.json" -f $Tag, $Now)

Write-Log ("Domain learn start. Root={0} OutDir={1}" -f $RootResolved, $OutDir) "STEP"

# -----------------------------
# Gather local system context
# -----------------------------
$cs = Get-CimInstance Win32_ComputerSystem
$os = Get-CimInstance Win32_OperatingSystem

$detectedDomain = ""
if (-not [string]::IsNullOrWhiteSpace($Domain)) {
  $detectedDomain = $Domain
} elseif ($cs.PartOfDomain -and -not [string]::IsNullOrWhiteSpace($cs.Domain)) {
  $detectedDomain = $cs.Domain
} elseif (-not [string]::IsNullOrWhiteSpace($env:USERDNSDOMAIN)) {
  $detectedDomain = $env:USERDNSDOMAIN
}

$localContext = [ordered]@{
  ComputerName    = $env:COMPUTERNAME
  UserName        = $env:USERNAME
  UserDomain      = $env:USERDOMAIN
  UserDnsDomain   = $env:USERDNSDOMAIN
  LogonServer     = $env:LOGONSERVER
  PartOfDomain    = [bool]$cs.PartOfDomain
  DetectedDomain  = $detectedDomain
  OS              = $os.Caption
  OSVersion       = $os.Version
  BuildNumber     = $os.BuildNumber
  Manufacturer    = $cs.Manufacturer
  Model           = $cs.Model
}

Write-Log ("Computer={0} PartOfDomain={1} Domain={2}" -f $localContext.ComputerName, $localContext.PartOfDomain, $localContext.DetectedDomain) "INFO"

# Network/DNS snapshot
$dnsServers = @()
$ipConfig   = @()
try {
  $dnsServers = Get-DnsClientServerAddress -AddressFamily IPv4 -ErrorAction Stop |
                Select-Object InterfaceAlias, ServerAddresses
} catch { }

try {
  $ipConfig = Get-NetIPConfiguration -ErrorAction Stop |
              Select-Object InterfaceAlias, IPv4Address, IPv4DefaultGateway, DnsSuffix, DNSServer
} catch { }

# Time sync snapshot
$w32tm = (Get-Command w32tm -ErrorAction SilentlyContinue).Source
$timeStatus = $null
if ($w32tm) {
  $r = Try-Run "w32tm_status" { & $w32tm /query /status 2>&1 | Out-String }
  if ($r.Ok) { $timeStatus = $r.Value }
}

# -----------------------------
# AD module detection
# -----------------------------
$hasAD = $false
try {
  Import-Module ActiveDirectory -ErrorAction Stop
  $hasAD = $true
  Write-Log "ActiveDirectory module loaded." "OK"
} catch {
  Write-Log "ActiveDirectory module not available (RSAT not installed?). Will use limited fallbacks where possible." "WARN"
}

$hasGP = $false
if ($IncludeGPOs) {
  try {
    Import-Module GroupPolicy -ErrorAction Stop
    $hasGP = $true
    Write-Log "GroupPolicy module loaded." "OK"
  } catch {
    Write-Log "GroupPolicy module not available; skipping GPO collection." "WARN"
    $hasGP = $false
  }
}

# -----------------------------
# Collect domain/forest/DC/trust info
# -----------------------------
$domainInfo  = $null
$forestInfo  = $null
$fsmoInfo    = $null
$dcList      = @()
$trustList   = @()
$pwdPolicy   = $null
$sites       = @()
$subnets     = @()

$rawCmd = [ordered]@{}

if (-not [string]::IsNullOrWhiteSpace($detectedDomain) -and $hasAD) {
  Write-Log "Collecting AD info via ActiveDirectory module..." "STEP"

  $rDomain = Try-Run "Get-ADDomain" { Get-ADDomain -Identity $detectedDomain }
  if ($rDomain.Ok) {
    $domainInfo = $rDomain.Value | Select-Object `
      DNSRoot, NetBIOSName, DomainSID, ParentDomain, DistinguishedName, `
      PDCEmulator, RIDMaster, InfrastructureMaster, ReplicaDirectoryServers, `
      AllowedDNSSuffixes
    Write-Log ("Domain: {0} (NetBIOS: {1})" -f $domainInfo.DNSRoot, $domainInfo.NetBIOSName) "OK"
  } else {
    Write-Log ("Get-ADDomain failed: {0}" -f $rDomain.Error) "WARN"
  }

  $rForest = Try-Run "Get-ADForest" { Get-ADForest -Identity $detectedDomain }
  if ($rForest.Ok) {
    $forestInfo = $rForest.Value | Select-Object `
      Name, RootDomain, Domains, GlobalCatalogs, Sites, `
      SchemaMaster, DomainNamingMaster, ForestMode
    Write-Log ("Forest: {0}" -f $forestInfo.Name) "OK"
  } else {
    Write-Log ("Get-ADForest failed: {0}" -f $rForest.Error) "WARN"
  }

  if ($domainInfo -or $forestInfo) {
    $fsmoInfo = [pscustomobject]@{
      DomainPDCEmulator         = $domainInfo.PDCEmulator
      DomainRIDMaster           = $domainInfo.RIDMaster
      DomainInfrastructureMaster= $domainInfo.InfrastructureMaster
      ForestSchemaMaster        = $forestInfo.SchemaMaster
      ForestDomainNamingMaster  = $forestInfo.DomainNamingMaster
    }
  }

  $rDCs = Try-Run "Get-ADDomainController" { Get-ADDomainController -Filter * -Server $detectedDomain }
  if ($rDCs.Ok -and $rDCs.Value) {
    $dcList = $rDCs.Value | Select-Object `
      HostName, Domain, Forest, Site, IPv4Address, IPv6Address, IsGlobalCatalog, IsReadOnly, Enabled, `
      OperatingSystem, OperatingSystemVersion
    Write-Log ("Domain Controllers found: {0}" -f (@($dcList).Count)) "OK"
  } else {
    Write-Log ("Get-ADDomainController failed: {0}" -f $rDCs.Error) "WARN"
  }

  $rTrusts = Try-Run "Get-ADTrust" { Get-ADTrust -Filter * -Server $detectedDomain }
  if ($rTrusts.Ok -and $rTrusts.Value) {
    $trustList = $rTrusts.Value | Select-Object `
      Name, Source, Target, Direction, TrustType, TrustAttributes, `
      ForestTransitive, IntraForest, SelectiveAuthentication, Created, Modified
    Write-Log ("Trusts found: {0}" -f (@($trustList).Count)) "OK"
  } else {
    # Trusts are common to fail without rights; don’t hard-fail.
    if ($rTrusts.Error) { Write-Log ("Get-ADTrust failed: {0}" -f $rTrusts.Error) "WARN" }
  }

  $rPwd = Try-Run "Get-ADDefaultDomainPasswordPolicy" { Get-ADDefaultDomainPasswordPolicy -Server $detectedDomain }
  if ($rPwd.Ok -and $rPwd.Value) {
    $pwdPolicy = $rPwd.Value | Select-Object `
      ComplexityEnabled, MinPasswordLength, PasswordHistoryCount, `
      MaxPasswordAge, MinPasswordAge, LockoutThreshold, LockoutDuration, LockoutObservationWindow, `
      ReversibleEncryptionEnabled
    Write-Log "Default domain password policy collected." "OK"
  } else {
    if ($rPwd.Error) { Write-Log ("Password policy fetch failed: {0}" -f $rPwd.Error) "WARN" }
  }

  $rSites = Try-Run "Get-ADReplicationSite" { Get-ADReplicationSite -Filter * -Server $detectedDomain }
  if ($rSites.Ok -and $rSites.Value) {
    $sites = $rSites.Value | Select-Object Name, DistinguishedName
    Write-Log ("AD Sites found: {0}" -f (@($sites).Count)) "OK"
  }

  $rSubnets = Try-Run "Get-ADReplicationSubnet" { Get-ADReplicationSubnet -Filter * -Server $detectedDomain }
  if ($rSubnets.Ok -and $rSubnets.Value) {
    $subnets = $rSubnets.Value | Select-Object Name, Site, Location, Description
    Write-Log ("AD Subnets found: {0}" -f (@($subnets).Count)) "OK"
  }

} else {
  Write-Log "Skipping AD module collection (no domain detected or ActiveDirectory module missing)." "WARN"
}

# -----------------------------
# Fallback command collection (works without AD module)
# -----------------------------
Write-Log "Collecting fallback command outputs (best effort)..." "STEP"

$nltest = (Get-Command nltest -ErrorAction SilentlyContinue).Source
if ($nltest -and -not [string]::IsNullOrWhiteSpace($detectedDomain)) {
  $r1 = Invoke-CommandCapture -Exe $nltest -Args @("/dclist:$detectedDomain")
  $rawCmd["nltest_dclist"] = $r1

  $r2 = Invoke-CommandCapture -Exe $nltest -Args @("/dsgetdc:$detectedDomain")
  $rawCmd["nltest_dsgetdc"] = $r2
}

if ($nltest) {
  $r3 = Invoke-CommandCapture -Exe $nltest -Args @("/domain_trusts")
  $rawCmd["nltest_domain_trusts"] = $r3
}

$ipconfig = (Get-Command ipconfig -ErrorAction SilentlyContinue).Source
if ($ipconfig) {
  $r4 = Invoke-CommandCapture -Exe $ipconfig -Args @("/all")
  $rawCmd["ipconfig_all"] = $r4
}

if ($w32tm) {
  $r5 = Invoke-CommandCapture -Exe $w32tm -Args @("/query","/status")
  $rawCmd["w32tm_status"] = $r5
}

# Optionally export raw outputs into text files
if ($ExportRawCommandOutput) {
  foreach ($k in $rawCmd.Keys) {
    $o = $rawCmd[$k]
    $txt = Join-Path $OutDir ("raw_{0}_{1}.txt" -f $k, $Now)
    $content = @()
    $content += "COMMAND: $($o.Command)"
    $content += "EXITCODE: $($o.ExitCode)"
    $content += ""
    $content += "STDOUT:"
    $content += ($o.StdOut -as [string])
    $content += ""
    $content += "STDERR:"
    $content += ($o.StdErr -as [string])
    if ($PSCmdlet.ShouldProcess($txt, "Write raw command output")) {
      $content | Set-Content -LiteralPath $txt -Encoding UTF8
    }
  }
}

# -----------------------------
# Optional enumeration (OFF by default)
# -----------------------------
$users     = @()
$computers = @()
$groups    = @()
$ous       = @()
$gpos      = @()

if ($hasAD -and -not [string]::IsNullOrWhiteSpace($detectedDomain)) {

  if ($IncludeUsers) {
    Write-Log ("Collecting AD Users (limit {0})..." -f $MaxUsers) "STEP"
    $rU = Try-Run "Get-ADUser" {
      Get-ADUser -Filter * -Server $detectedDomain -ResultSetSize $MaxUsers -Properties Enabled, LastLogonDate, PasswordLastSet, PasswordNeverExpires |
        Select-Object SamAccountName, Name, Enabled, LastLogonDate, PasswordLastSet, PasswordNeverExpires, DistinguishedName
    }
    if ($rU.Ok -and $rU.Value) {
      $users = $rU.Value
      Write-Log ("Users collected: {0}" -f (@($users).Count)) "OK"
    } else {
      Write-Log ("Users collection failed: {0}" -f $rU.Error) "WARN"
    }
  }

  if ($IncludeComputers) {
    Write-Log ("Collecting AD Computers (limit {0})..." -f $MaxComputers) "STEP"
    $rC = Try-Run "Get-ADComputer" {
      Get-ADComputer -Filter * -Server $detectedDomain -ResultSetSize $MaxComputers -Properties Enabled, LastLogonDate, OperatingSystem, OperatingSystemVersion |
        Select-Object Name, DNSHostName, Enabled, LastLogonDate, OperatingSystem, OperatingSystemVersion, DistinguishedName
    }
    if ($rC.Ok -and $rC.Value) {
      $computers = $rC.Value
      Write-Log ("Computers collected: {0}" -f (@($computers).Count)) "OK"
    } else {
      Write-Log ("Computers collection failed: {0}" -f $rC.Error) "WARN"
    }
  }

  if ($IncludeGroups) {
    Write-Log ("Collecting AD Groups (limit {0})..." -f $MaxGroups) "STEP"
    $rG = Try-Run "Get-ADGroup" {
      Get-ADGroup -Filter * -Server $detectedDomain -ResultSetSize $MaxGroups -Properties GroupScope, GroupCategory, ManagedBy |
        Select-Object SamAccountName, Name, GroupScope, GroupCategory, ManagedBy, DistinguishedName
    }
    if ($rG.Ok -and $rG.Value) {
      $groups = $rG.Value
      Write-Log ("Groups collected: {0}" -f (@($groups).Count)) "OK"
    } else {
      Write-Log ("Groups collection failed: {0}" -f $rG.Error) "WARN"
    }
  }

  if ($IncludeOUs) {
    Write-Log "Collecting AD Organizational Units..." "STEP"
    $rO = Try-Run "Get-ADOrganizationalUnit" {
      Get-ADOrganizationalUnit -Filter * -Server $detectedDomain -ResultSetSize 0 |
        Select-Object Name, DistinguishedName
    }
    if ($rO.Ok -and $rO.Value) {
      $ous = $rO.Value
      Write-Log ("OUs collected: {0}" -f (@($ous).Count)) "OK"
    } else {
      Write-Log ("OU collection failed: {0}" -f $rO.Error) "WARN"
    }
  }

  if ($IncludeGPOs -and $hasGP) {
    Write-Log "Collecting GPO list..." "STEP"
    $rP = Try-Run "Get-GPO" {
      Get-GPO -All | Select-Object DisplayName, Id, Owner, CreationTime, ModificationTime, GpoStatus
    }
    if ($rP.Ok -and $rP.Value) {
      $gpos = $rP.Value
      Write-Log ("GPOs collected: {0}" -f (@($gpos).Count)) "OK"
    } else {
      Write-Log ("GPO collection failed: {0}" -f $rP.Error) "WARN"
    }
  }
}

# -----------------------------
# Build report object
# -----------------------------
$report = [ordered]@{
  GeneratedAt = (Get-Date)
  Tag         = $Tag
  OutputDir   = $OutDir

  LocalContext = $localContext

  DNS = [ordered]@{
    DnsClientServerAddress = $dnsServers
    NetIPConfiguration     = $ipConfig
  }

  Time = [ordered]@{
    W32tmStatusText = $timeStatus
  }

  ActiveDirectory = [ordered]@{
    UsedADModule    = $hasAD
    DomainDetected  = $detectedDomain
    DomainInfo      = $domainInfo
    ForestInfo      = $forestInfo
    FSMORoles       = $fsmoInfo
    DomainControllers = $dcList
    Trusts          = $trustList
    DefaultPasswordPolicy = $pwdPolicy
    Sites           = $sites
    Subnets         = $subnets
  }

  Optional = [ordered]@{
    IncludedUsers     = [bool]$IncludeUsers
    IncludedComputers = [bool]$IncludeComputers
    IncludedGroups    = [bool]$IncludeGroups
    IncludedOUs       = [bool]$IncludeOUs
    IncludedGPOs      = [bool]$IncludeGPOs
    Users             = $users
    Computers         = $computers
    Groups            = $groups
    OUs               = $ous
    GPOs              = $gpos
  }

  FallbackCommands = $rawCmd
}

# -----------------------------
# Export JSON + CSV datasets
# -----------------------------
Write-Log "Exporting reports..." "STEP"

if ($PSCmdlet.ShouldProcess($JsonPath, "Write JSON report")) {
  $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $JsonPath -Encoding UTF8
}

# CSV datasets
Export-DatasetCsv -Path (Join-Path $OutDir ("domain_controllers_{0}.csv" -f $Now)) -Data $dcList
Export-DatasetCsv -Path (Join-Path $OutDir ("trusts_{0}.csv" -f $Now))            -Data $trustList
Export-DatasetCsv -Path (Join-Path $OutDir ("sites_{0}.csv" -f $Now))             -Data $sites
Export-DatasetCsv -Path (Join-Path $OutDir ("subnets_{0}.csv" -f $Now))           -Data $subnets
Export-DatasetCsv -Path (Join-Path $OutDir ("password_policy_{0}.csv" -f $Now))   -Data $pwdPolicy
Export-DatasetCsv -Path (Join-Path $OutDir ("fsmo_{0}.csv" -f $Now))              -Data $fsmoInfo

if ($IncludeUsers) {
  Export-DatasetCsv -Path (Join-Path $OutDir ("users_{0}.csv" -f $Now)) -Data $users
}
if ($IncludeComputers) {
  Export-DatasetCsv -Path (Join-Path $OutDir ("computers_{0}.csv" -f $Now)) -Data $computers
}
if ($IncludeGroups) {
  Export-DatasetCsv -Path (Join-Path $OutDir ("groups_{0}.csv" -f $Now)) -Data $groups
}
if ($IncludeOUs) {
  Export-DatasetCsv -Path (Join-Path $OutDir ("ous_{0}.csv" -f $Now)) -Data $ous
}
if ($IncludeGPOs) {
  Export-DatasetCsv -Path (Join-Path $OutDir ("gpos_{0}.csv" -f $Now)) -Data $gpos
}

# Summary to console
Write-Log ("Saved log:  {0}" -f $script:LogFile) "OK"
Write-Log ("Saved JSON: {0}" -f $JsonPath) "OK"

Write-Host ""
Write-Host "Summary:"
Write-Host ("  Domain detected:      {0}" -f $detectedDomain)
Write-Host ("  AD module available:  {0}" -f $hasAD)
Write-Host ("  DCs:                  {0}" -f (@($dcList).Count))
Write-Host ("  Trusts:               {0}" -f (@($trustList).Count))
Write-Host ("  Sites:                {0}" -f (@($sites).Count))
Write-Host ("  Subnets:              {0}" -f (@($subnets).Count))
Write-Host ("  Users collected:      {0}" -f (@($users).Count))
Write-Host ("  Computers collected:  {0}" -f (@($computers).Count))
Write-Host ("  Groups collected:     {0}" -f (@($groups).Count))
Write-Host ("  OUs collected:        {0}" -f (@($ous).Count))
Write-Host ("  GPOs collected:       {0}" -f (@($gpos).Count))
Write-Host ""
