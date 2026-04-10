<#
  emergency-shutdown.ps1 (Full Drop)

  Purpose (read-only by default):
    Emergency “stop the bleeding” playbook for a Windows host.

  SAFE DEFAULTS:
    - DRY RUN unless -Execute is provided
    - Uses ShouldProcess (supports -WhatIf / -Confirm)
    - Logs everything under: C:\Francis\data\logs\operations\emergency_shutdown\

  Actions you can enable:
    - Stop specific services
    - Stop specific processes
    - Disable scheduled tasks (by full task path)
    - Disable network adapters (containment)
    - Optional local shutdown/reboot

  Examples:
    # Dry run (prints plan + writes report)
    powershell -ExecutionPolicy Bypass -File C:\Francis\scripts\emergency-shutdown.ps1

    # Stop services + processes (execute)
    powershell -ExecutionPolicy Bypass -File C:\Francis\scripts\emergency-shutdown.ps1 -Execute `
      -ServiceName "MyAppService","W3SVC" -ProcessName "node","python" -Force

    # Containment: disable NICs (execute) - WARNING: you may lose remote connectivity
    powershell -ExecutionPolicy Bypass -File C:\Francis\scripts\emergency-shutdown.ps1 -Execute -DisableNetwork

    # Full: stop stuff, disable NICs, then shutdown in 30 seconds
    powershell -ExecutionPolicy Bypass -File C:\Francis\scripts\emergency-shutdown.ps1 -Execute `
      -ServiceName "MyAppService" -ProcessName "node" -DisableNetwork -Shutdown -DelaySeconds 30 -Force

#>

[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
param(
  [Parameter()][string]$Root = "C:\Francis",
  [Parameter()][string]$Tag  = "emergency_shutdown",

  # Safety latch: nothing changes unless this is set
  [Parameter()][switch]$Execute,

  # Target actions
  [Parameter()][string[]]$ServiceName = @(),
  [Parameter()][string[]]$ProcessName = @(),
  [Parameter()][string[]]$ScheduledTaskPath = @(),   # e.g. "\Microsoft\Windows\UpdateOrchestrator\Schedule Scan"

  [Parameter()][switch]$DisableNetwork,              # disables all UP hardware NICs (best-effort)
  [Parameter()][string[]]$KeepAdapterName = @(),     # names to NOT disable, exact match

  [Parameter()][switch]$Shutdown,                    # local shutdown
  [Parameter()][switch]$Reboot,                      # local reboot
  [Parameter()][int]$DelaySeconds = 0,               # used for shutdown/reboot
  [Parameter()][switch]$Force,                       # more aggressive stops

  # If set, also exports snapshots to CSV/JSON
  [Parameter()][switch]$ExportSnapshots
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

function Try-Run {
  param([string]$Name, [scriptblock]$Block)
  try { return [pscustomobject]@{ Name=$Name; Ok=$true; Value=(& $Block); Error=$null } }
  catch { return [pscustomobject]@{ Name=$Name; Ok=$false; Value=$null; Error=$_.Exception.Message } }
}

function Export-Json {
  param([string]$Path, $Obj)
  try { $Obj | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $Path -Encoding UTF8 }
  catch { Write-Log ("JSON export failed: {0}" -f $_.Exception.Message) "WARN" }
}

function Export-CsvSafe {
  param([string]$Path, $Obj)
  try {
    if ($null -eq $Obj) { return }
    if ($Obj -is [System.Collections.IEnumerable] -and -not ($Obj -is [string])) {
      $Obj | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $Path
    } else {
      @($Obj) | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $Path
    }
  } catch {
    Write-Log ("CSV export failed for {0}: {1}" -f $Path, $_.Exception.Message) "WARN"
  }
}

function Stop-ServiceSafe {
  param([string]$Name, [switch]$ForceStop)

  $svc = Get-Service -Name $Name -ErrorAction Stop
  if ($svc.Status -eq 'Stopped') {
    Write-Log ("Service already stopped: {0}" -f $Name) "OK"
    return
  }

  $action = ("Stop service {0}" -f $Name)
  if ($PSCmdlet.ShouldProcess($Name, $action)) {
    if ($ForceStop) {
      Stop-Service -Name $Name -Force -ErrorAction Stop
    } else {
      Stop-Service -Name $Name -ErrorAction Stop
    }

    # wait a bit for clean stop
    $svc.WaitForStatus('Stopped','00:00:20')
    Write-Log ("Service stopped: {0}" -f $Name) "OK"
  }
}

function Stop-ProcessSafe {
  param([string]$Name, [switch]$ForceStop)

  $procs = @(Get-Process -Name $Name -ErrorAction SilentlyContinue)
  if (-not $procs -or $procs.Count -eq 0) {
    Write-Log ("No running process found: {0}" -f $Name) "INFO"
    return
  }

  foreach ($p in $procs) {
    $target = ("{0} (Id {1})" -f $p.ProcessName, $p.Id)
    $action = ("Stop process {0}" -f $target)

    if ($PSCmdlet.ShouldProcess($target, $action)) {
      if ($ForceStop) {
        Stop-Process -Id $p.Id -Force -ErrorAction Stop
      } else {
        Stop-Process -Id $p.Id -ErrorAction Stop
      }
      Write-Log ("Process stopped: {0}" -f $target) "OK"
    }
  }
}

function Disable-TaskSafe {
  param([string]$TaskPath)

  # schtasks wants /TN full path
  $schtasks = (Get-Command schtasks.exe -ErrorAction SilentlyContinue).Source
  if (-not $schtasks) {
    Write-Log "schtasks.exe not found; cannot disable tasks." "WARN"
    return
  }

  $action = ("Disable scheduled task {0}" -f $TaskPath)
  if ($PSCmdlet.ShouldProcess($TaskPath, $action)) {
    $out = & $schtasks /Change /TN $TaskPath /Disable 2>&1
    if ($LASTEXITCODE -eq 0) {
      Write-Log ("Task disabled: {0}" -f $TaskPath) "OK"
    } else {
      Write-Log ("Failed to disable task {0}: {1}" -f $TaskPath, (($out | Select-Object -First 1) -as [string])) "WARN"
    }
  }
}

function Disable-NetworkSafe {
  param([string[]]$KeepNames)

  $hasNetAdapter = $false
  try { Get-Command Get-NetAdapter -ErrorAction Stop | Out-Null; $hasNetAdapter = $true } catch { $hasNetAdapter = $false }

  if (-not $hasNetAdapter) {
    Write-Log "Get-NetAdapter not available; cannot disable NICs via NetAdapter module." "WARN"
    return @()
  }

  $keepers = @()
  if ($KeepNames) { $keepers = $KeepNames }

  # HardwareInterface excludes many virtual adapters; still best-effort
  $adapters = @(Get-NetAdapter -ErrorAction Stop | Where-Object {
    $_.Status -eq 'Up' -and $_.HardwareInterface -eq $true
  })

  if (-not $adapters -or $adapters.Count -eq 0) {
    Write-Log "No UP hardware adapters found to disable." "INFO"
    return @()
  }

  $disabled = @()

  foreach ($a in $adapters) {
    if ($keepers -contains $a.Name) {
      Write-Log ("Keeping adapter (skip disable): {0}" -f $a.Name) "INFO"
      continue
    }

    $action = ("Disable network adapter {0}" -f $a.Name)
    if ($PSCmdlet.ShouldProcess($a.Name, $action)) {
      # NOTE: This can cut off remote sessions immediately.
      Disable-NetAdapter -Name $a.Name -Confirm:$false -ErrorAction Stop | Out-Null
      Write-Log ("Adapter disabled: {0}" -f $a.Name) "OK"
      $disabled += $a.Name
    }
  }

  return $disabled
}

function Invoke-ShutdownSafe {
  param(
    [ValidateSet("Shutdown","Reboot")][string]$Mode,
    [int]$Delay = 0,
    [switch]$ForceIt
  )

  $shutdownExe = (Get-Command shutdown.exe -ErrorAction SilentlyContinue).Source
  if (-not $shutdownExe) {
    Write-Log "shutdown.exe not found; cannot shutdown/reboot." "WARN"
    return
  }

  $args = @()
  if ($Mode -eq "Shutdown") { $args += "/s" }
  if ($Mode -eq "Reboot")   { $args += "/r" }
  $args += "/t"; $args += [string]([Math]::Max(0,$Delay))

  if ($ForceIt) { $args += "/f" }

  $action = ("{0} computer in {1} seconds" -f $Mode, [Math]::Max(0,$Delay))
  if ($PSCmdlet.ShouldProcess($env:COMPUTERNAME, $action)) {
    Write-Log ("Executing: shutdown.exe {0}" -f ($args -join " ")) "WARN"
    & $shutdownExe @args | Out-Null
  }
}

# -----------------------------
# Initialize output/log
# -----------------------------
$RootResolved = Resolve-FSPath $Root
$OutDir = Join-Path $RootResolved "data\logs\operations\emergency_shutdown"
New-Dir $OutDir

$Now = Get-Date -Format "yyyyMMdd_HHmmss"
$script:LogFile = Join-Path $OutDir ("{0}_{1}.log" -f $Tag, $Now)
$JsonPath       = Join-Path $OutDir ("{0}_{1}.json" -f $Tag, $Now)

Write-Log ("Emergency shutdown start. Execute={0} Force={1}" -f [bool]$Execute, [bool]$Force) "STEP"

$admin = Test-IsAdmin
Write-Log ("IsAdmin={0}" -f $admin) "INFO"

# -----------------------------
# Snapshot (pre)
# -----------------------------
$cs = Get-CimInstance Win32_ComputerSystem
$os = Get-CimInstance Win32_OperatingSystem

$pre = [ordered]@{
  When        = (Get-Date)
  Computer    = $env:COMPUTERNAME
  User        = ("{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME)
  IsAdmin     = $admin
  PartOfDomain= [bool]$cs.PartOfDomain
  Domain      = $cs.Domain
  OS          = $os.Caption
  OSVersion   = $os.Version
  BootTime    = $os.LastBootUpTime

  Requested = [ordered]@{
    Execute           = [bool]$Execute
    Force             = [bool]$Force
    ServiceName       = $ServiceName
    ProcessName       = $ProcessName
    ScheduledTaskPath = $ScheduledTaskPath
    DisableNetwork    = [bool]$DisableNetwork
    KeepAdapterName   = $KeepAdapterName
    Shutdown          = [bool]$Shutdown
    Reboot            = [bool]$Reboot
    DelaySeconds      = $DelaySeconds
    ExportSnapshots   = [bool]$ExportSnapshots
  }
}

# Best-effort local state
$preState = [ordered]@{}
$preState["ServicesTargeted"] = @()
foreach ($s in $ServiceName) {
  $r = Try-Run "Get-Service $s" { Get-Service -Name $s | Select-Object Name, DisplayName, Status, StartType }
  if ($r.Ok -and $r.Value) { $preState["ServicesTargeted"] += $r.Value }
}

$preState["ProcessesTargeted"] = @()
foreach ($p in $ProcessName) {
  $r = Try-Run "Get-Process $p" { Get-Process -Name $p | Select-Object ProcessName, Id, CPU, StartTime -ErrorAction Stop }
  if ($r.Ok -and $r.Value) { $preState["ProcessesTargeted"] += $r.Value }
}

$preState["Adapters"] = @()
$rA = Try-Run "Get-NetAdapter" { Get-NetAdapter | Select-Object Name, InterfaceDescription, Status, HardwareInterface, LinkSpeed }
if ($rA.Ok -and $rA.Value) { $preState["Adapters"] = $rA.Value }

$preState["IPConfig"] = @()
$rIP = Try-Run "Get-NetIPConfiguration" { Get-NetIPConfiguration | Select-Object InterfaceAlias, IPv4Address, IPv4DefaultGateway, DnsSuffix }
if ($rIP.Ok -and $rIP.Value) { $preState["IPConfig"] = $rIP.Value }

# Export pre snapshot
$report = [ordered]@{
  Pre  = $pre
  PreState = $preState
  Actions = @()
  PostState = $null
}
Export-Json -Path $JsonPath -Obj $report
Write-Log ("Wrote initial JSON report: {0}" -f $JsonPath) "OK"

if ($ExportSnapshots) {
  Export-CsvSafe -Path (Join-Path $OutDir ("pre_services_{0}.csv" -f $Now))   -Obj $preState["ServicesTargeted"]
  Export-CsvSafe -Path (Join-Path $OutDir ("pre_processes_{0}.csv" -f $Now))  -Obj $preState["ProcessesTargeted"]
  Export-CsvSafe -Path (Join-Path $OutDir ("pre_adapters_{0}.csv" -f $Now))   -Obj $preState["Adapters"]
  Export-CsvSafe -Path (Join-Path $OutDir ("pre_ipconfig_{0}.csv" -f $Now))   -Obj $preState["IPConfig"]
}

# -----------------------------
# Dry run guard
# -----------------------------
if (-not $Execute) {
  Write-Log "DRY RUN: No changes will be made (use -Execute to actually perform actions)." "WARN"
  Write-Host ""
  Write-Host "Planned actions:"
  if ($ServiceName.Count -gt 0)   { Write-Host ("  - Stop services:  {0}" -f ($ServiceName -join ", ")) }
  if ($ProcessName.Count -gt 0)   { Write-Host ("  - Stop processes: {0}" -f ($ProcessName -join ", ")) }
  if ($ScheduledTaskPath.Count -gt 0) { Write-Host ("  - Disable tasks:  {0}" -f ($ScheduledTaskPath -join ", ")) }
  if ($DisableNetwork)            { Write-Host ("  - Disable network adapters (keep: {0})" -f (($KeepAdapterName -join ", "))) }
  if ($Shutdown)                  { Write-Host ("  - Shutdown in {0}s (force={1})" -f $DelaySeconds, [bool]$Force) }
  if ($Reboot)                    { Write-Host ("  - Reboot in {0}s (force={1})" -f $DelaySeconds, [bool]$Force) }
  Write-Host ""
  Write-Log ("Done (dry run). Log: {0}" -f $script:LogFile) "OK"
  exit 0
}

# Require admin for most actions
if (-not $admin) {
  Write-Log "Execute requested but process is not elevated (run PowerShell as Administrator)." "ERROR"
  throw "Not running as Administrator."
}

# Prevent conflicting shutdown flags
if ($Shutdown -and $Reboot) {
  throw "Choose only one: -Shutdown or -Reboot"
}

# -----------------------------
# Execute actions
# -----------------------------
Write-Log "EXECUTE MODE: Performing enabled actions..." "STEP"

$actionsTaken = New-Object System.Collections.Generic.List[object]

# 1) Stop services
foreach ($s in $ServiceName) {
  $actionsTaken.Add([pscustomobject]@{ Action="StopService"; Target=$s; When=(Get-Date) }) | Out-Null
  try { Stop-ServiceSafe -Name $s -ForceStop:$Force }
  catch { Write-Log ("Stop service failed ({0}): {1}" -f $s, $_.Exception.Message) "WARN" }
}

# 2) Stop processes
foreach ($p in $ProcessName) {
  $actionsTaken.Add([pscustomobject]@{ Action="StopProcess"; Target=$p; When=(Get-Date) }) | Out-Null
  try { Stop-ProcessSafe -Name $p -ForceStop:$Force }
  catch { Write-Log ("Stop process failed ({0}): {1}" -f $p, $_.Exception.Message) "WARN" }
}

# 3) Disable scheduled tasks
foreach ($t in $ScheduledTaskPath) {
  $actionsTaken.Add([pscustomobject]@{ Action="DisableScheduledTask"; Target=$t; When=(Get-Date) }) | Out-Null
  try { Disable-TaskSafe -TaskPath $t }
  catch { Write-Log ("Disable task failed ({0}): {1}" -f $t, $_.Exception.Message) "WARN" }
}

# 4) Disable network adapters (containment)
$disabledAdapters = @()
if ($DisableNetwork) {
  Write-Log "WARNING: Disabling NICs can drop your session immediately." "WARN"
  $actionsTaken.Add([pscustomobject]@{ Action="DisableNetworkAdapters"; Target="LocalMachine"; When=(Get-Date); Keep=($KeepAdapterName -join ",") }) | Out-Null
  try { $disabledAdapters = Disable-NetworkSafe -KeepNames $KeepAdapterName }
  catch { Write-Log ("Disable network failed: {0}" -f $_.Exception.Message) "WARN" }
}

# 5) Shutdown / reboot
if ($Shutdown) {
  $actionsTaken.Add([pscustomobject]@{ Action="Shutdown"; Target=$env:COMPUTERNAME; When=(Get-Date); DelaySeconds=$DelaySeconds; Force=[bool]$Force }) | Out-Null
  Invoke-ShutdownSafe -Mode "Shutdown" -Delay $DelaySeconds -ForceIt:$Force
}
elseif ($Reboot) {
  $actionsTaken.Add([pscustomobject]@{ Action="Reboot"; Target=$env:COMPUTERNAME; When=(Get-Date); DelaySeconds=$DelaySeconds; Force=[bool]$Force }) | Out-Null
  Invoke-ShutdownSafe -Mode "Reboot" -Delay $DelaySeconds -ForceIt:$Force
}

# -----------------------------
# Snapshot (post)
# -----------------------------
$postState = [ordered]@{}
$postState["ServicesTargeted"] = @()
foreach ($s in $ServiceName) {
  $r = Try-Run "Get-Service $s" { Get-Service -Name $s | Select-Object Name, DisplayName, Status, StartType }
  if ($r.Ok -and $r.Value) { $postState["ServicesTargeted"] += $r.Value }
}

$postState["ProcessesTargeted"] = @()
foreach ($p in $ProcessName) {
  $r = Try-Run "Get-Process $p" { Get-Process -Name $p | Select-Object ProcessName, Id, CPU, StartTime -ErrorAction Stop }
  if ($r.Ok -and $r.Value) { $postState["ProcessesTargeted"] += $r.Value }
}

$postState["Adapters"] = @()
$rA2 = Try-Run "Get-NetAdapter" { Get-NetAdapter | Select-Object Name, InterfaceDescription, Status, HardwareInterface, LinkSpeed }
if ($rA2.Ok -and $rA2.Value) { $postState["Adapters"] = $rA2.Value }

$postState["DisabledAdapters"] = $disabledAdapters

$report.Actions   = $actionsTaken
$report.PostState = $postState
Export-Json -Path $JsonPath -Obj $report

if ($ExportSnapshots) {
  Export-CsvSafe -Path (Join-Path $OutDir ("post_services_{0}.csv" -f $Now))   -Obj $postState["ServicesTargeted"]
  Export-CsvSafe -Path (Join-Path $OutDir ("post_processes_{0}.csv" -f $Now))  -Obj $postState["ProcessesTargeted"]
  Export-CsvSafe -Path (Join-Path $OutDir ("post_adapters_{0}.csv" -f $Now))   -Obj $postState["Adapters"]
  Export-CsvSafe -Path (Join-Path $OutDir ("actions_{0}.csv" -f $Now))         -Obj $actionsTaken
}

Write-Log ("Saved log:  {0}" -f $script:LogFile) "OK"
Write-Log ("Saved JSON: {0}" -f $JsonPath) "OK"
Write-Log "Emergency shutdown completed." "OK"
