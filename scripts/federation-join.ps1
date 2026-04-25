<#
  federation-join.ps1 (Full Drop)

  What it does:
    - Preflight checks (Admin, current domain/workgroup, DNS, DC discovery)
    - Optional: stage DNS servers on active NICs before join
    - Joins this machine to an AD domain (Add-Computer)
    - Optional: restart after join
    - Writes logs + JSON report under:
        D:\francis\data\logs\operations\federation_join\

  SAFE DEFAULTS:
    - DRY RUN unless -Execute is provided
    - Uses ShouldProcess (supports -WhatIf / -Confirm)

  Examples:
    # Dry run (no changes)
    powershell -ExecutionPolicy Bypass -File D:\francis\scripts\federation-join.ps1 -DomainName corp.example.com

    # Join using interactive credential prompt + restart
    powershell -ExecutionPolicy Bypass -File D:\francis\scripts\federation-join.ps1 -Execute `
      -DomainName corp.example.com -Credential (Get-Credential) -Restart

    # Join and place in a specific OU
    powershell -ExecutionPolicy Bypass -File D:\francis\scripts\federation-join.ps1 -Execute `
      -DomainName corp.example.com -OUPath "OU=Workstations,OU=NYC,DC=corp,DC=example,DC=com" -Credential (Get-Credential) -Restart

    # Stage DNS (use your DC/DNS IPs), then join
    powershell -ExecutionPolicy Bypass -File D:\francis\scripts\federation-join.ps1 -Execute `
      -DomainName corp.example.com -DnsServers 10.0.0.10,10.0.0.11 -Credential (Get-Credential) -Restart

    # Rename computer first (then join)
    powershell -ExecutionPolicy Bypass -File D:\francis\scripts\federation-join.ps1 -Execute `
      -DomainName corp.example.com -NewComputerName POS-TERM-014 -Credential (Get-Credential) -Restart
#>

[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
param(
  [Parameter()][string]$Root = "D:\francis",
  [Parameter()][string]$Tag  = "federation_join",

  # Safety latch: nothing changes unless this is set
  [Parameter()][switch]$Execute,

  # Required for the join
  [Parameter(Mandatory=$true)][string]$DomainName,

  # Optional OU DN
  [Parameter()][string]$OUPath,

  # Optional rename before join
  [Parameter()][string]$NewComputerName,

  # Credential used for join (if omitted, Add-Computer uses current context)
  [Parameter()][pscredential]$Credential,

  # Optional DNS staging (use DC/DNS IPs for your domain)
  [Parameter()][string[]]$DnsServers = @(),
  [Parameter()][string[]]$KeepAdapterName = @(),  # adapters to NOT touch when staging DNS

  # Behaviors
  [Parameter()][switch]$Restart,
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

function Get-ActiveAdapters {
  try {
    Get-NetAdapter -ErrorAction Stop | Where-Object {
      $_.Status -eq 'Up' -and $_.HardwareInterface -eq $true
    }
  } catch { @() }
}

function Set-DnsServersOnAdapters {
  param(
    [string[]]$Servers,
    [string[]]$KeepNames
  )

  if (-not $Servers -or $Servers.Count -eq 0) { return @() }

  $adapters = @(Get-ActiveAdapters)
  if (-not $adapters -or $adapters.Count -eq 0) {
    Write-Log "No UP hardware adapters found for DNS staging." "WARN"
    return @()
  }

  $touched = @()
  foreach ($a in $adapters) {
    if ($KeepNames -and ($KeepNames -contains $a.Name)) {
      Write-Log ("Keeping adapter (skip DNS staging): {0}" -f $a.Name) "INFO"
      continue
    }

    $action = ("Set DNS on adapter '{0}' to: {1}" -f $a.Name, ($Servers -join ", "))
    if ($PSCmdlet.ShouldProcess($a.Name, $action)) {
      Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ServerAddresses $Servers -ErrorAction Stop
      Write-Log ("DNS staged on adapter: {0}" -f $a.Name) "OK"
      $touched += $a.Name
    }
  }

  return $touched
}

function Get-DomainControllersFromDNS {
  param([string]$Domain)

  $srv = "_ldap._tcp.dc._msdcs.$Domain"
  $dcs = New-Object System.Collections.Generic.HashSet[string]

  try {
    $records = Resolve-DnsName -Name $srv -Type SRV -ErrorAction Stop
    foreach ($r in $records) {
      if ($r.NameTarget) { [void]$dcs.Add(($r.NameTarget.TrimEnd('.')).ToLowerInvariant()) }
    }
  } catch {
    # Best-effort fallback: try A record for domain itself
    try {
      $a = Resolve-DnsName -Name $Domain -Type A -ErrorAction Stop
      foreach ($r in $a) { if ($r.Name) { [void]$dcs.Add(($Domain.ToLowerInvariant())) } }
    } catch { }
  }

  return @($dcs)
}

function Test-Port {
  param([string]$Host, [int]$Port)
  try {
    return (Test-NetConnection -ComputerName $Host -Port $Port -InformationLevel Quiet)
  } catch { return $false }
}

function Get-JoinState {
  $cs = Get-CimInstance Win32_ComputerSystem
  [pscustomobject]@{
    ComputerName = $env:COMPUTERNAME
    PartOfDomain = [bool]$cs.PartOfDomain
    Domain       = $cs.Domain
    Workgroup    = $cs.Workgroup
  }
}

function Invoke-RenameIfNeeded {
  param([string]$NewName)

  if ([string]::IsNullOrWhiteSpace($NewName)) { return $false }

  $current = $env:COMPUTERNAME
  if ($current -ieq $NewName) {
    Write-Log ("Computer name already '{0}' (no rename needed)." -f $NewName) "OK"
    return $false
  }

  $action = ("Rename computer from '{0}' to '{1}'" -f $current, $NewName)
  if ($PSCmdlet.ShouldProcess($current, $action)) {
    Rename-Computer -NewName $NewName -Force:$Force -ErrorAction Stop
    Write-Log ("Rename scheduled: {0} -> {1} (restart may be required)." -f $current, $NewName) "OK"
    return $true
  }

  return $false
}

function Invoke-DomainJoin {
  param(
    [string]$Domain,
    [string]$OU,
    [pscredential]$Cred
  )

  $args = @{
    DomainName = $Domain
    ErrorAction = "Stop"
  }

  if (-not [string]::IsNullOrWhiteSpace($OU)) {
    $args["OUPath"] = $OU
  }
  if ($Cred) {
    $args["Credential"] = $Cred
  }
  if ($Force) {
    $args["Force"] = $true
  }

  $action = "Join computer to domain '$Domain'"
  if ($PSCmdlet.ShouldProcess($env:COMPUTERNAME, $action)) {
    Add-Computer @args
    Write-Log ("Domain join initiated for: {0}" -f $Domain) "OK"
  }
}

# -----------------------------
# Initialize output/log
# -----------------------------
$RootResolved = Resolve-FSPath $Root
$OutDir = Join-Path $RootResolved "data\logs\operations\federation_join"
New-Dir $OutDir

$Now = Get-Date -Format "yyyyMMdd_HHmmss"
$script:LogFile = Join-Path $OutDir ("{0}_{1}.log" -f $Tag, $Now)
$JsonPath       = Join-Path $OutDir ("{0}_{1}.json" -f $Tag, $Now)

Write-Log ("Federation join start. Domain={0} Execute={1} Force={2}" -f $DomainName, [bool]$Execute, [bool]$Force) "STEP"

$admin = Test-IsAdmin
Write-Log ("IsAdmin={0}" -f $admin) "INFO"

$stateBefore = Get-JoinState
Write-Log ("Current state: PartOfDomain={0} Domain={1} Workgroup={2}" -f $stateBefore.PartOfDomain, $stateBefore.Domain, $stateBefore.Workgroup) "INFO"

# -----------------------------
# Preflight discovery
# -----------------------------
$dcs = @(Get-DomainControllersFromDNS -Domain $DomainName)
if ($dcs.Count -gt 0) {
  Write-Log ("Discovered DC candidates via DNS: {0}" -f ($dcs -join ", ")) "INFO"
} else {
  Write-Log "Could not discover DCs via DNS SRV (check DNS settings / connectivity)." "WARN"
}

$portResults = @()
foreach ($dc in $dcs | Select-Object -First 6) {
  $portResults += [pscustomobject]@{
    DC   = $dc
    LDAP = (Test-Port $dc 389)
    LDAPS= (Test-Port $dc 636)
    KRB  = (Test-Port $dc 88)
    SMB  = (Test-Port $dc 445)
    DNS  = (Test-Port $dc 53)
  }
}

# Report skeleton
$report = [ordered]@{
  When = (Get-Date)
  Computer = $env:COMPUTERNAME
  User = ("{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME)
  IsAdmin = $admin

  Requested = [ordered]@{
    Execute         = [bool]$Execute
    DomainName      = $DomainName
    OUPath          = $OUPath
    NewComputerName = $NewComputerName
    HasCredential   = [bool]($Credential)
    DnsServers      = $DnsServers
    KeepAdapterName = $KeepAdapterName
    Restart         = [bool]$Restart
    Force           = [bool]$Force
  }

  Before = $stateBefore
  DCs = $dcs
  DCConnectivity = $portResults
  Actions = @()
  After = $null
}

Export-Json -Path $JsonPath -Obj $report
Write-Log ("Saved initial report: {0}" -f $JsonPath) "OK"

# -----------------------------
# Dry run guard
# -----------------------------
if (-not $Execute) {
  Write-Log "DRY RUN: No changes will be made (use -Execute to perform join)." "WARN"
  Write-Host ""
  Write-Host "Planned actions:"
  if (-not [string]::IsNullOrWhiteSpace($NewComputerName)) { Write-Host ("  - Rename computer to: {0}" -f $NewComputerName) }
  if ($DnsServers.Count -gt 0) { Write-Host ("  - Stage DNS servers: {0}" -f ($DnsServers -join ", ")) }
  Write-Host ("  - Join domain: {0}" -f $DomainName)
  if (-not [string]::IsNullOrWhiteSpace($OUPath)) { Write-Host ("    OUPath: {0}" -f $OUPath) }
  if ($Restart) { Write-Host "  - Restart after join" }
  Write-Host ""
  Write-Log ("Done (dry run). Log: {0}" -f $script:LogFile) "OK"
  exit 0
}

# -----------------------------
# Execute mode checks
# -----------------------------
if (-not $admin) {
  Write-Log "Execute requested but not elevated. Run PowerShell as Administrator." "ERROR"
  throw "Not running as Administrator."
}

# If already joined to the target domain, do nothing
if ($stateBefore.PartOfDomain -and ($stateBefore.Domain -ieq $DomainName)) {
  Write-Log ("Already joined to target domain '{0}'. No action needed." -f $DomainName) "OK"
  $report.After = (Get-JoinState)
  Export-Json -Path $JsonPath -Obj $report
  exit 0
}

# If already on some other domain, warn (can still proceed if user has rights)
if ($stateBefore.PartOfDomain -and ($stateBefore.Domain -and ($stateBefore.Domain -ine $DomainName))) {
  Write-Log ("WARNING: Machine is already domain-joined to '{0}'. Attempting join to '{1}' may fail or require unjoin first." -f $stateBefore.Domain, $DomainName) "WARN"
}

# -----------------------------
# Execute actions
# -----------------------------
Write-Log "EXECUTE MODE: Performing requested join steps..." "STEP"
$actions = New-Object System.Collections.Generic.List[object]

# 1) Optional DNS staging
if ($DnsServers.Count -gt 0) {
  $actions.Add([pscustomobject]@{ Action="StageDNS"; When=(Get-Date); Servers=($DnsServers -join ","); Keep=($KeepAdapterName -join ",") }) | Out-Null
  try {
    $touched = Set-DnsServersOnAdapters -Servers $DnsServers -KeepNames $KeepAdapterName
    Write-Log ("DNS staged on adapters: {0}" -f ($touched -join ", ")) "OK"
  } catch {
    Write-Log ("DNS staging failed: {0}" -f $_.Exception.Message) "WARN"
  }
}

# 2) Optional rename
$didRename = $false
if (-not [string]::IsNullOrWhiteSpace($NewComputerName)) {
  $actions.Add([pscustomobject]@{ Action="RenameComputer"; When=(Get-Date); NewName=$NewComputerName }) | Out-Null
  try { $didRename = Invoke-RenameIfNeeded -NewName $NewComputerName }
  catch { Write-Log ("Rename failed: {0}" -f $_.Exception.Message) "WARN" }
}

# 3) Domain join
$actions.Add([pscustomobject]@{ Action="DomainJoin"; When=(Get-Date); Domain=$DomainName; OUPath=$OUPath; UsedCredential=[bool]($Credential) }) | Out-Null
try {
  Invoke-DomainJoin -Domain $DomainName -OU $OUPath -Cred $Credential
} catch {
  Write-Log ("Domain join failed: {0}" -f $_.Exception.Message) "ERROR"
  $report.Actions = $actions
  $report.After = (Get-JoinState)
  Export-Json -Path $JsonPath -Obj $report
  throw
}

# 4) Restart if requested OR if rename occurred (rename typically needs restart)
if ($Restart -or $didRename) {
  $why = @()
  if ($Restart)  { $why += "Restart requested" }
  if ($didRename){ $why += "Rename performed" }

  $actions.Add([pscustomobject]@{ Action="RestartComputer"; When=(Get-Date); Reason=($why -join "; ") }) | Out-Null

  $action = ("Restart computer now ({0})" -f ($why -join "; "))
  if ($PSCmdlet.ShouldProcess($env:COMPUTERNAME, $action)) {
    Write-Log ("Restarting now. Reason: {0}" -f ($why -join "; ")) "WARN"
    Restart-Computer -Force:$Force
  }
} else {
  Write-Log "Join initiated. A restart may still be required for the domain join to fully apply." "WARN"
}

# Post-state (may not run if Restart occurs immediately)
$report.Actions = $actions
$report.After = (Get-JoinState)
Export-Json -Path $JsonPath -Obj $report

Write-Log ("Saved log:  {0}" -f $script:LogFile) "OK"
Write-Log ("Saved JSON: {0}" -f $JsonPath) "OK"
Write-Log "Federation join completed." "OK"
