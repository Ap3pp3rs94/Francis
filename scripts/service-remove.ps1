<#
D:\francis\scripts\service-remove.ps1

Purpose
  Remove Windows Services in a controlled, logged way (with optional cleanup of runtime + logs).

Modes
  - Status : show service details only
  - Remove : stop + delete service (requires admin + -Force)

Inputs
  - Single or multiple service names via -ServiceName
  - OR services config file via -ConfigPath (JSON/YAML)

Cleanup (optional)
  -CleanupRuntime : removes <Root>\data\runtime\services\<ServiceName>\
  -CleanupLogs    : removes stdout/stderr files declared in config entries (only if inside Root unless -OverrideSafety)

Safety
  - Blocks dangerous paths (drive roots, Windows folders)
  - By default, only deletes files/folders under -Root unless -OverrideSafety is used
  - Uses ShouldProcess (supports -WhatIf / -Confirm)

Logs
  - Transcript: <Root>\data\logs\operations\service_remove_<timestamp>.log
  - CSV      : <Root>\data\logs\operations\service_remove_<timestamp>.csv
  - JSON     : <Root>\data\logs\operations\service_remove_report_<timestamp>.json

Examples
  # Status check
  pwsh -File D:\francis\scripts\service-remove.ps1 -Mode Status -ServiceName Francis-Plugin

  # Remove a service
  pwsh -File D:\francis\scripts\service-remove.ps1 -Mode Remove -ServiceName Francis-Plugin -Force

  # Remove and cleanup runtime wrapper dir + logs (if configured)
  pwsh -File D:\francis\scripts\service-remove.ps1 -Mode Remove -ServiceName Francis-Plugin -Force -CleanupRuntime -CleanupLogs

  # Remove services from config
  pwsh -File D:\francis\scripts\service-remove.ps1 -Mode Remove -ConfigPath D:\francis\data\config\services.json -Force -CleanupRuntime -CleanupLogs

#>

[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
param(
  [ValidateSet('Status','Remove')]
  [string]$Mode = 'Remove',

  [string]$Root = 'D:\francis',

  # Optional: config file (JSON/YAML) that contains an array of services (or object with .services)
  [string]$ConfigPath = '',

  # One or more service names (ignored if -ConfigPath is provided)
  [string[]]$ServiceName = @(),

  # Best-effort: stop service before deleting
  [switch]$NoStopFirst,

  # Optional cleanup
  [switch]$CleanupRuntime,
  [switch]$CleanupLogs,

  # Required for removal
  [switch]$Force,

  # Allow cleanup paths outside Root (still blocks system folders/drive roots)
  [switch]$OverrideSafety
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# -----------------------------
# Logging setup
# -----------------------------
$Now     = Get-Date -Format "yyyyMMdd_HHmmss"
$OpsDir  = Join-Path $Root "data\logs\operations"
New-Item -ItemType Directory -Force -Path $OpsDir | Out-Null

$LogPath  = Join-Path $OpsDir "service_remove_$Now.log"
$CsvPath  = Join-Path $OpsDir "service_remove_$Now.csv"
$JsonPath = Join-Path $OpsDir "service_remove_report_$Now.json"

try { Start-Transcript -Path $LogPath -Force | Out-Null } catch {}

$script:Actions = New-Object System.Collections.Generic.List[object]

function Add-Action {
  param(
    [string]$Service,
    [string]$Action,
    [string]$Target,
    [string]$Result,
    [string]$Notes = ''
  )
  $script:Actions.Add([pscustomobject]@{
    Time    = (Get-Date).ToString('s')
    Service = $Service
    Action  = $Action
    Target  = $Target
    Result  = $Result
    Notes   = $Notes
  }) | Out-Null
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

function Test-DangerousPath([string]$Path){
  $p = (Resolve-FullPath $Path).TrimEnd('\')

  # Block drive roots (C:\, D:\)
  if($p -match '^[A-Za-z]:\\$'){ return $true }

  $blocked = @(
    $env:SystemRoot,
    (Join-Path $env:SystemDrive '\Windows'),
    (Join-Path $env:SystemDrive '\Program Files'),
    (Join-Path $env:SystemDrive '\Program Files (x86)'),
    (Join-Path $env:SystemDrive '\ProgramData')
  ) | ForEach-Object {
    try { (Resolve-FullPath $_).TrimEnd('\') } catch { $_ }
  }

  foreach($b in $blocked){
    if($p.ToLowerInvariant() -eq ($b.TrimEnd('\').ToLowerInvariant())){ return $true }
  }

  return $false
}

function Ensure-UnderRootOrOverride([string]$Path, [string]$Label){
  $full = Resolve-FullPath $Path

  if(Test-DangerousPath $full){
    throw "Refusing dangerous $Label path: $full"
  }

  if(-not $OverrideSafety){
    $rootFull = (Resolve-FullPath $Root).TrimEnd('\')
    $pLower = $full.TrimEnd('\').ToLowerInvariant()
    $rLower = $rootFull.ToLowerInvariant()
    if(-not ($pLower -eq $rLower -or $pLower.StartsWith($rLower + "\"))){
      throw "Safety block: $Label path is outside Root. Use -OverrideSafety to allow. Path: $full"
    }
  }

  return $full
}

function Test-IsAdmin {
  try {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
  } catch {
    return $false
  }
}

function Require-Admin([string]$ForAction){
  if(-not (Test-IsAdmin)){
    throw "Admin rights required for: $ForAction. Re-run PowerShell as Administrator."
  }
}

function Require-Force([string]$ForAction){
  if(-not $Force){
    throw "$ForAction requires -Force (try -WhatIf first)."
  }
}

function Get-ServiceSafe([string]$Name){
  try { return Get-Service -Name $Name -ErrorAction SilentlyContinue }
  catch { return $null }
}

function Invoke-Sc {
  param(
    [Parameter(Mandatory=$true)][string[]]$Args,
    [string]$Svc = ''
  )
  $exe = "$env:SystemRoot\System32\sc.exe"
  $cmdLine = "sc.exe " + ($Args -join ' ')
  Write-Host ("`n> {0}" -f $cmdLine)

  if($PSCmdlet.ShouldProcess(($Svc ?? ''), $cmdLine)){
    $out = & $exe @Args 2>&1
    $code = $LASTEXITCODE
    if($out){ $out | ForEach-Object { Write-Host $_ } }
    if($code -ne 0){
      throw "sc.exe failed (ExitCode=$code): $cmdLine"
    }
    return $out
  } else {
    Add-Action $Svc "sc.exe" $cmdLine "WHATIF/SKIPPED" "Not approved"
  }
}

function Stop-ServiceBestEffort([string]$Name){
  try {
    $svc = Get-ServiceSafe $Name
    if($svc -and $svc.Status -ne 'Stopped'){
      if($PSCmdlet.ShouldProcess($Name, "Stop-Service")){
        Stop-Service -Name $Name -Force -ErrorAction SilentlyContinue
        Add-Action $Name "Stop" $Name "OK" "Stop requested"
        Start-Sleep -Milliseconds 600
      } else {
        Add-Action $Name "Stop" $Name "WHATIF/SKIPPED" "Not approved"
      }
    } else {
      Add-Action $Name "Stop" $Name "SKIPPED" "Not running"
    }
  } catch {
    Add-Action $Name "Stop" $Name "FAILED" $_.Exception.Message
    # best-effort: don't throw
  }
}

function Remove-PathSafe {
  param(
    [Parameter(Mandatory=$true)][string]$Service,
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)][string]$Label,
    [switch]$IsFile
  )

  if([string]::IsNullOrWhiteSpace($Path)){ return }

  $full = Ensure-UnderRootOrOverride -Path $Path -Label $Label

  if(-not (Test-Path -LiteralPath $full)){
    Add-Action $Service "Cleanup" $full "SKIPPED" "$Label not found"
    return
  }

  if($PSCmdlet.ShouldProcess($full, "Delete $Label")){
    try {
      if($IsFile){
        Remove-Item -LiteralPath $full -Force -ErrorAction Stop
      } else {
        Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction Stop
      }
      Add-Action $Service "Cleanup" $full "OK" "$Label deleted"
    } catch {
      Add-Action $Service "Cleanup" $full "FAILED" $_.Exception.Message
      throw
    }
  } else {
    Add-Action $Service "Cleanup" $full "WHATIF/SKIPPED" "Not approved"
  }
}

# -----------------------------
# Optional config parsing (JSON/YAML)
# -----------------------------
$Py = $null
try { $Py = (Get-Command python -ErrorAction SilentlyContinue).Source } catch {}

$HasCfy = $false
try { if(Get-Command ConvertFrom-Yaml -ErrorAction SilentlyContinue){ $HasCfy = $true } } catch {}

$HasPyYaml = $false
if($Py){
  try { & $Py -c "import yaml" 2>$null; $HasPyYaml = ($LASTEXITCODE -eq 0) } catch {}
}

function Read-ConfigFile([string]$Path){
  $p = Resolve-FullPath $Path
  if(-not (Test-Path -LiteralPath $p)){ throw "ConfigPath not found: $p" }

  $ext = ([System.IO.Path]::GetExtension($p) ?? '').ToLowerInvariant()
  $raw = Get-Content -LiteralPath $p -Raw -ErrorAction Stop

  if($ext -eq '.json'){
    return ($raw | ConvertFrom-Json -ErrorAction Stop)
  }

  if($ext -in @('.yml','.yaml')){
    if($HasCfy){
      return ($raw | ConvertFrom-Yaml -ErrorAction Stop)
    }
    elseif($Py -and $HasPyYaml){
      $tmp = [System.IO.Path]::GetTempFileName()
      try{
        $raw | Out-File -LiteralPath $tmp -Encoding UTF8 -Force
        $out = & $Py -c @"
import sys, yaml, json
p=sys.argv[1]
s=open(p,'rb').read().decode('utf-8-sig')
obj=yaml.safe_load(s)
print(json.dumps(obj))
"@ $tmp 2>&1
        if($LASTEXITCODE -ne 0){
          throw (($out | Select-Object -First 1) -as [string])
        }
        return ($out | Out-String | ConvertFrom-Json -ErrorAction Stop)
      } finally {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
      }
    }
    else{
      throw "YAML config provided but no YAML parser available. Install PowerShell 7+ (ConvertFrom-Yaml) or Python+PyYAML."
    }
  }

  throw "Unsupported config extension: $ext (use .json/.yml/.yaml)"
}

function Normalize-ServiceDef {
  param($obj)

  $name = [string]($obj.name ?? $obj.ServiceName ?? $obj.serviceName ?? '')
  $stdout = [string]($obj.stdout ?? '')
  $stderr = [string]($obj.stderr ?? '')

  # some configs might nest logs
  if(-not $stdout -and $obj.logs -and $obj.logs.stdout){ $stdout = [string]$obj.logs.stdout }
  if(-not $stderr -and $obj.logs -and $obj.logs.stderr){ $stderr = [string]$obj.logs.stderr }

  return [pscustomobject]@{
    name   = $name
    stdout = $stdout
    stderr = $stderr
  }
}

function Get-ServiceDefs {

  if(-not [string]::IsNullOrWhiteSpace($ConfigPath)){
    $cfg = Read-ConfigFile -Path $ConfigPath

    $items = $null
    if($cfg -is [System.Collections.IEnumerable] -and -not ($cfg -is [string])){
      $items = @($cfg)
    } elseif($cfg.services){
      $items = @($cfg.services)
    } else {
      throw "Config file parsed but did not look like an array of services or object with .services"
    }

    return @($items | ForEach-Object { Normalize-ServiceDef $_ })
  }

  if($ServiceName -and $ServiceName.Count -gt 0){
    return @($ServiceName | ForEach-Object {
      [pscustomobject]@{ name = [string]$_; stdout=''; stderr='' }
    })
  }

  throw "No service names provided. Use -ServiceName or -ConfigPath."
}

# -----------------------------
# Main
# -----------------------------
try {
  Write-Section "Service Remove"
  Write-Host ("Mode          : {0}" -f $Mode)
  Write-Host ("Root          : {0}" -f (Resolve-FullPath $Root))
  Write-Host ("ConfigPath    : {0}" -f $ConfigPath)
  Write-Host ("CleanupRuntime: {0}" -f $CleanupRuntime)
  Write-Host ("CleanupLogs   : {0}" -f $CleanupLogs)
  Write-Host ("NoStopFirst   : {0}" -f $NoStopFirst)
  Write-Host ("WhatIf        : {0}" -f $WhatIfPreference)
  Write-Host ("Force         : {0}" -f $Force)
  Write-Host ("Log           : {0}" -f $LogPath)
  Write-Host ("CSV           : {0}" -f $CsvPath)
  Write-Host ("Report        : {0}" -f $JsonPath)

  if(Test-DangerousPath $Root){
    throw "Refusing to operate on dangerous Root: $Root"
  }

  $defs = Get-ServiceDefs
  if(-not $defs -or $defs.Count -eq 0){
    throw "No services specified."
  }

  foreach($d in $defs){
    if([string]::IsNullOrWhiteSpace($d.name)){
      throw "A service definition is missing 'name'."
    }
  }

  if($Mode -eq 'Remove'){
    Require-Admin "Remove services"
    Require-Force "Remove services"
  }

  foreach($d in $defs){
    $name = [string]$d.name

    Write-Section ("Service: {0}" -f $name)

    $svc = Get-ServiceSafe $name
    if(-not $svc){
      Write-Host "Not installed."
      Add-Action $name "Status" $name "SKIPPED" "Not installed"
      continue
    }

    # Show details
    $wmi = $null
    try { $wmi = Get-CimInstance Win32_Service -Filter "Name='$name'" -ErrorAction SilentlyContinue } catch {}
    Write-Host ("Name       : {0}" -f $svc.Name)
    Write-Host ("Status     : {0}" -f $svc.Status)
    if($wmi){
      Write-Host ("DisplayName: {0}" -f $wmi.DisplayName)
      Write-Host ("StartMode  : {0}" -f $wmi.StartMode)
      Write-Host ("PathName   : {0}" -f $wmi.PathName)
      Write-Host ("Account    : {0}" -f $wmi.StartName)
      Write-Host ("State      : {0}" -f $wmi.State)
    }

    Add-Action $name "Status" $name "OK" ("{0}" -f $svc.Status)

    if($Mode -eq 'Status'){
      continue
    }

    # Stop (best-effort)
    if(-not $NoStopFirst){
      Stop-ServiceBestEffort $name
    } else {
      Add-Action $name "Stop" $name "SKIPPED" "NoStopFirst set"
    }

    # Delete service
    if($PSCmdlet.ShouldProcess($name, "sc.exe delete")){
      try {
        Invoke-Sc -Svc $name -Args @('delete', $name) | Out-Null
        Add-Action $name "DeleteService" $name "OK" "Deleted service"
      } catch {
        Add-Action $name "DeleteService" $name "FAILED" $_.Exception.Message
        throw
      }
    } else {
      Add-Action $name "DeleteService" $name "WHATIF/SKIPPED" "Not approved"
    }

    # Cleanup runtime wrapper dir
    if($CleanupRuntime){
      $runtimeDir = Join-Path $Root ("data\runtime\services\{0}" -f $name)
      Remove-PathSafe -Service $name -Path $runtimeDir -Label "Runtime directory" | Out-Null
    } else {
      Add-Action $name "CleanupRuntime" "(n/a)" "SKIPPED" "CleanupRuntime not set"
    }

    # Cleanup log files if listed in config (or if they exist under runtime dir)
    if($CleanupLogs){

      # If config provided and had stdout/stderr, remove those files (only files)
      if(-not [string]::IsNullOrWhiteSpace([string]$d.stdout)){
        Remove-PathSafe -Service $name -Path ([string]$d.stdout) -Label "StdOut log file" -IsFile | Out-Null
      }
      if(-not [string]::IsNullOrWhiteSpace([string]$d.stderr)){
        Remove-PathSafe -Service $name -Path ([string]$d.stderr) -Label "StdErr log file" -IsFile | Out-Null
      }

      # Also remove default wrapper logs if present (without deleting whole runtime unless CleanupRuntime)
      $defaultRuntime = Join-Path $Root ("data\runtime\services\{0}" -f $name)
      $defaultStdout  = Join-Path $defaultRuntime "stdout.log"
      $defaultStderr  = Join-Path $defaultRuntime "stderr.log"

      if(-not $CleanupRuntime){
        if(Test-Path -LiteralPath $defaultStdout){
          Remove-PathSafe -Service $name -Path $defaultStdout -Label "Default stdout.log" -IsFile | Out-Null
        }
        if(Test-Path -LiteralPath $defaultStderr){
          Remove-PathSafe -Service $name -Path $defaultStderr -Label "Default stderr.log" -IsFile | Out-Null
        }
      }

    } else {
      Add-Action $name "CleanupLogs" "(n/a)" "SKIPPED" "CleanupLogs not set"
    }
  }

  # -----------------------------
  # Write outputs
  # -----------------------------
  Write-Section "Write reports"
  $script:Actions | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $CsvPath

  $report = [pscustomobject]@{
    timestamp     = $Now
    mode          = $Mode
    root          = (Resolve-FullPath $Root)
    config        = $ConfigPath
    cleanupRuntime= [bool]$CleanupRuntime
    cleanupLogs   = [bool]$CleanupLogs
    noStopFirst   = [bool]$NoStopFirst
    log           = $LogPath
    csv           = $CsvPath
    actions       = @($script:Actions)
  }
  $report | ConvertTo-Json -Depth 6 | Out-File -LiteralPath $JsonPath -Encoding UTF8 -Force

  Write-Section "Summary"
  $script:Actions | Group-Object Result | Sort-Object Count -Descending | Format-Table -AutoSize Count,Name

  Write-Host ""
  Write-Host ("Saved log   : {0}" -f $LogPath)
  Write-Host ("Saved CSV   : {0}" -f $CsvPath)
  Write-Host ("Saved report: {0}" -f $JsonPath)

  $bad = $script:Actions | Where-Object { $_.Result -in @('FAILED','BLOCKED') }
  if($bad -and $bad.Count -gt 0){ exit 1 } else { exit 0 }

} catch {
  Write-Host ""
  Write-Host ("ERROR: {0}" -f $_.Exception.Message) -ForegroundColor Red
  throw
} finally {
  try { Stop-Transcript | Out-Null } catch {}
}
