<#
D:\francis\scripts\service-install.ps1

Purpose
  Install / update / uninstall / manage Windows Services in a controlled, logged way.

Features
  - Supports a single service via parameters OR multiple services via -ConfigPath (JSON/YAML).
  - Modes: Status, Plan, Install, Update, Uninstall, Start, Stop, Restart
  - Optional wrapper run.cmd to:
      - enforce WorkingDirectory (services don't have a native "cwd")
      - optionally redirect stdout/stderr to files
  - Optional recovery actions (restart on failure)
  - Safety rails:
      - requires admin for mutating operations
      - requires -Force for Uninstall and some destructive changes
      - blocks dangerous filesystem paths for wrapper/log locations
  - Logs:
      - Transcript: <Root>\data\logs\operations\service_install_<timestamp>.log
      - CSV      : <Root>\data\logs\operations\service_install_<timestamp>.csv
      - JSON     : <Root>\data\logs\operations\service_install_report_<timestamp>.json

Config file format (JSON)
  [
    {
      "name": "Francis-Worker-1",
      "displayName": "Francis Worker 1",
      "description": "Background worker",
      "exe": "C:\\Program Files\\nodejs\\node.exe",
      "args": ["server.js", "--port", "4010"],
      "workingDir": "C:\\Francis\\workers\\worker1",
      "startType": "AutomaticDelayedStart",
      "useWrapper": true,
      "stdout": "C:\\Francis\\data\\logs\\services\\worker1_out.log",
      "stderr": "C:\\Francis\\data\\logs\\services\\worker1_err.log",
      "recovery": { "enabled": true, "restartDelaySec": 5, "maxRestarts": 3, "resetDays": 1 },
      "startAfter": true
    }
  ]

Config file format (YAML)
  - name: Francis-Worker-1
    displayName: Francis Worker 1
    description: Background worker
    exe: C:\Program Files\nodejs\node.exe
    args: [server.js, --port, "4010"]
    workingDir: D:\francis\workers\worker1
    startType: AutomaticDelayedStart
    useWrapper: true
    stdout: D:\francis\data\logs\services\worker1_out.log
    stderr: D:\francis\data\logs\services\worker1_err.log
    recovery:
      enabled: true
      restartDelaySec: 5
      maxRestarts: 3
      resetDays: 1
    startAfter: true

Examples
  # Status of a service
  pwsh -File D:\francis\scripts\service-install.ps1 -Mode Status -ServiceName Francis-Worker-1

  # Read-only install/update plan from config; performs no service mutation.
  pwsh -File D:\francis\scripts\service-install.ps1 -Mode Plan -ConfigPath D:\francis\config\runtime\services\lens-host.json

  # Install a service directly (no wrapper)
  pwsh -File D:\francis\scripts\service-install.ps1 -Mode Install `
    -ServiceName Francis-Plugin `
    -DisplayName "Francis Plugin" `
    -Description "Francis plugin HTTP service" `
    -Executable "C:\Program Files\nodejs\node.exe" `
    -Arguments @("server.js","--port","3000") `
    -WorkingDirectory "D:\francis\plugin" `
    -StartType AutomaticDelayedStart `
    -SetRecovery `
    -StartAfterInstall

  # Install/update all services from config
  pwsh -File D:\francis\scripts\service-install.ps1 -Mode Install -ConfigPath D:\francis\data\config\services.json

  # Update binPath/args for an existing service
  pwsh -File D:\francis\scripts\service-install.ps1 -Mode Update -ServiceName Francis-Plugin `
    -Executable "C:\Program Files\nodejs\node.exe" -Arguments @("server.js","--port","3001") `
    -WorkingDirectory "D:\francis\plugin" -UseWrapper -StartType AutomaticDelayedStart

  # Uninstall (requires -Force)
  pwsh -File D:\francis\scripts\service-install.ps1 -Mode Uninstall -ServiceName Francis-Plugin -Force

#>

[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
param(
  [ValidateSet('Status','Plan','Install','Update','Uninstall','Start','Stop','Restart')]
  [string]$Mode = 'Status',

  [string]$Root = 'D:\francis',

  # If provided, installs/updates/services from a config file (JSON or YAML).
  [string]$ConfigPath = '',

  # Single-service parameters (used when -ConfigPath not specified)
  [string]$ServiceName = '',
  [string]$DisplayName = '',
  [string]$Description = '',
  [string]$Executable = '',
  [string[]]$Arguments = @(),
  [string]$WorkingDirectory = '',
  [switch]$UseWrapper,

  # Wrapper redirection (only used when wrapper is enabled)
  [string]$StdOutPath = '',
  [string]$StdErrPath = '',

  [ValidateSet('Automatic','AutomaticDelayedStart','Manual','Disabled')]
  [string]$StartType = 'AutomaticDelayedStart',

  # Recovery options
  [switch]$SetRecovery,
  [int]$RecoveryRestartDelaySec = 5,
  [int]$RecoveryMaxRestarts = 3,
  [int]$RecoveryResetDays = 1,

  # Start after install/update
  [switch]$StartAfterInstall,

  # Required for destructive operations (Uninstall)
  [switch]$Force,

  # If you intentionally want wrapper/log paths outside Root (still blocks system folders)
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

$LogPath  = Join-Path $OpsDir "service_install_$Now.log"
$CsvPath  = Join-Path $OpsDir "service_install_$Now.csv"
$JsonPath = Join-Path $OpsDir "service_install_report_$Now.json"

try { Start-Transcript -Path $LogPath -Force | Out-Null } catch {}

$script:Actions = New-Object System.Collections.Generic.List[object]
$script:Plans = New-Object System.Collections.Generic.List[object]

function Add-Action {
  param(
    [string]$Service,
    [string]$Action,
    [string]$Result,
    [string]$Notes = ''
  )
  $script:Actions.Add([pscustomobject]@{
    Time    = (Get-Date).ToString('s')
    Service = $Service
    Action  = $Action
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
    $msg = "Admin rights required for: $ForAction. Re-run PowerShell as Administrator."
    throw $msg
  }
}

function Require-Force([string]$ForAction){
  if(-not $Force){
    throw "$ForAction requires -Force (try -WhatIf first)."
  }
}

function Quote-Arg([string]$s){
  if($null -eq $s){ return '' }
  if($s -match '[\s"]'){
    $escaped = $s -replace '"','\"'
    return '"' + $escaped + '"'
  }
  return $s
}

function Join-Args([string[]]$Items){
  if(-not $Items -or $Items.Count -eq 0){ return '' }
  return ($Items | ForEach-Object { Quote-Arg ([string]$_) }) -join ' '
}

function Resolve-ExecutableForPlan([string]$Exe){
  if([string]::IsNullOrWhiteSpace($Exe)){
    return [pscustomobject]@{
      value = ''
      resolved = ''
      exists = $false
      source = 'missing'
      reason = 'service executable is missing'
    }
  }

  $full = Resolve-FullPath $Exe
  if(Test-Path -LiteralPath $full -PathType Leaf){
    return [pscustomobject]@{
      value = $Exe
      resolved = $full
      exists = $true
      source = 'path'
      reason = ''
    }
  }

  try {
    $cmd = Get-Command $Exe -CommandType Application -ErrorAction Stop | Select-Object -First 1
    if($cmd -and -not [string]::IsNullOrWhiteSpace([string]$cmd.Source)){
      return [pscustomobject]@{
        value = $Exe
        resolved = [string]$cmd.Source
        exists = $true
        source = 'command'
        reason = ''
      }
    }
  } catch {}

  return [pscustomobject]@{
    value = $Exe
    resolved = $full
    exists = $false
    source = 'unresolved'
    reason = 'service executable could not be resolved'
  }
}

function Build-BinaryPathPlan {
  param(
    [Parameter(Mandatory=$true)][string]$SvcName,
    [Parameter(Mandatory=$true)][string]$Exe,
    [string[]]$CommandArgs,
    [string]$WorkDir,
    [switch]$WantWrapper,
    [string]$StdOut,
    [string]$StdErr
  )

  $argsS = Join-Args $CommandArgs
  $serviceCmd = Quote-Arg $Exe
  if(-not [string]::IsNullOrWhiteSpace($argsS)){ $serviceCmd += " $argsS" }

  $usesWrapper = [bool]($WantWrapper -or -not [string]::IsNullOrWhiteSpace($WorkDir) -or -not [string]::IsNullOrWhiteSpace($StdOut) -or -not [string]::IsNullOrWhiteSpace($StdErr))
  if($usesWrapper){
    $runtimeBase = Join-Path $Root "data\runtime\services"
    $runtimeBase = Ensure-OkPath -Path $runtimeBase -Label "Runtime base"
    $svcDir = Join-Path $runtimeBase $SvcName
    $svcDir = Ensure-OkPath -Path $svcDir -Label "Service runtime"
    $cmdPath = Join-Path $svcDir "run.cmd"
    $cmdExe = if([string]::IsNullOrWhiteSpace($env:SystemRoot)){ "cmd.exe" } else { Join-Path $env:SystemRoot "System32\cmd.exe" }
    return [pscustomobject]@{
      binary_path = ('"' + $cmdExe + '" /c "' + (Resolve-FullPath $cmdPath) + '"')
      service_command = $serviceCmd
      wrapper = [pscustomobject]@{
        enabled = $true
        path = (Resolve-FullPath $cmdPath)
        would_write = $false
      }
    }
  }

  return [pscustomobject]@{
    binary_path = $serviceCmd
    service_command = $serviceCmd
    wrapper = [pscustomobject]@{
      enabled = $false
      path = ''
      would_write = $false
    }
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
  }
  else {
    Add-Action $Svc "sc.exe" "WHATIF/SKIPPED" $cmdLine
  }
}

# -----------------------------
# YAML parsing (optional) for config
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

  if($ext -in @('.json')){
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

# -----------------------------
# Wrapper creation
# -----------------------------
function Ensure-OkPath([string]$Path, [string]$Label){
  $full = Resolve-FullPath $Path
  if(Test-DangerousPath $full){
    throw "Refusing dangerous $Label path: $full"
  }
  if(-not $OverrideSafety){
    $rootFull = Resolve-FullPath $Root
    # allow under Root only unless override
    $pLower = $full.ToLowerInvariant()
    $rLower = $rootFull.TrimEnd('\').ToLowerInvariant()
    if(-not ($pLower -eq $rLower -or $pLower.StartsWith($rLower + "\"))){
      throw "Safety block: $Label path is outside Root. Use -OverrideSafety to allow. Path: $full"
    }
  }
  return $full
}

function New-ServiceWrapper {
  param(
    [Parameter(Mandatory=$true)][string]$SvcName,
    [Parameter(Mandatory=$true)][string]$Exe,
    [string[]]$Args,
    [string]$WorkDir,
    [string]$StdOut,
    [string]$StdErr
  )

  $runtimeBase = Join-Path $Root "data\runtime\services"
  $runtimeBase = Ensure-OkPath -Path $runtimeBase -Label "Runtime base"
  New-Item -ItemType Directory -Force -Path $runtimeBase | Out-Null

  $svcDir = Join-Path $runtimeBase $SvcName
  $svcDir = Ensure-OkPath -Path $svcDir -Label "Service runtime"
  New-Item -ItemType Directory -Force -Path $svcDir | Out-Null

  $cmdPath = Join-Path $svcDir "run.cmd"

  $exeQ  = Quote-Arg $Exe
  $argsS = Join-Args $Args

  $lines = New-Object System.Collections.Generic.List[string]
  $lines.Add("@echo off") | Out-Null
  $lines.Add("setlocal") | Out-Null

  if(-not [string]::IsNullOrWhiteSpace($WorkDir)){
    $wd = Quote-Arg $WorkDir
    $lines.Add("cd /d $wd || exit /b 1") | Out-Null
  }

  $cmd = "$exeQ"
  if(-not [string]::IsNullOrWhiteSpace($argsS)){ $cmd += " $argsS" }

  # Optional redirection
  if(-not [string]::IsNullOrWhiteSpace($StdOut) -or -not [string]::IsNullOrWhiteSpace($StdErr)){
    $outP = $StdOut
    $errP = $StdErr

    if([string]::IsNullOrWhiteSpace($outP)){
      $outP = Join-Path $svcDir "stdout.log"
    }
    if([string]::IsNullOrWhiteSpace($errP)){
      $errP = Join-Path $svcDir "stderr.log"
    }

    $outP = Ensure-OkPath -Path $outP -Label "StdOut"
    $errP = Ensure-OkPath -Path $errP -Label "StdErr"

    # Ensure parents exist
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outP) | Out-Null
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $errP) | Out-Null

    $cmd = "$cmd 1>>" + (Quote-Arg $outP) + " 2>>" + (Quote-Arg $errP)
  }

  if($PSCmdlet.ShouldProcess($cmdPath, "Write wrapper run.cmd")){
    $lines.Add($cmd) | Out-Null
    $lines | Out-File -LiteralPath $cmdPath -Encoding ASCII -Force
    Add-Action $SvcName "Wrapper" "OK" (Resolve-FullPath $cmdPath)
  }
  else {
    Add-Action $SvcName "Wrapper" "WHATIF/SKIPPED" (Resolve-FullPath $cmdPath)
  }

  return (Resolve-FullPath $cmdPath)
}

function Build-BinaryPath {
  param(
    [Parameter(Mandatory=$true)][string]$SvcName,
    [Parameter(Mandatory=$true)][string]$Exe,
    [string[]]$Args,
    [string]$WorkDir,
    [switch]$WantWrapper,
    [string]$StdOut,
    [string]$StdErr
  )

  if($WantWrapper -or -not [string]::IsNullOrWhiteSpace($WorkDir) -or -not [string]::IsNullOrWhiteSpace($StdOut) -or -not [string]::IsNullOrWhiteSpace($StdErr)){
    $wrapper = New-ServiceWrapper -SvcName $SvcName -Exe $Exe -Args $Args -WorkDir $WorkDir -StdOut $StdOut -StdErr $StdErr
    # Service runs cmd.exe /c "<wrapper>"
    $cmdExe = "$env:SystemRoot\System32\cmd.exe"
    return ('"' + $cmdExe + '" /c "' + $wrapper + '"')
  }

  $exeQ  = Quote-Arg $Exe
  $argsS = Join-Args $Args
  if([string]::IsNullOrWhiteSpace($argsS)){
    return $exeQ
  }
  return "$exeQ $argsS"
}

# -----------------------------
# Service config helpers
# -----------------------------
function Set-StartTypeSc {
  param(
    [Parameter(Mandatory=$true)][string]$Name,
    [Parameter(Mandatory=$true)][string]$Type  # auto | demand | disabled | delayed-auto
  )

  Invoke-Sc -Svc $Name -Args @('config', $Name, 'start=', $Type) | Out-Null
  Add-Action $Name "StartType" "OK" $Type
}

function Set-DescriptionSc {
  param([string]$Name,[string]$Desc)
  if([string]::IsNullOrWhiteSpace($Desc)){ return }
  Invoke-Sc -Svc $Name -Args @('description', $Name, $Desc) | Out-Null
  Add-Action $Name "Description" "OK" ""
}

function Set-DisplayNameSc {
  param([string]$Name,[string]$Disp)
  if([string]::IsNullOrWhiteSpace($Disp)){ return }
  Invoke-Sc -Svc $Name -Args @('config', $Name, 'DisplayName=', $Disp) | Out-Null
  Add-Action $Name "DisplayName" "OK" $Disp
}

function Set-BinPathSc {
  param([string]$Name,[string]$BinPath)
  Invoke-Sc -Svc $Name -Args @('config', $Name, 'binPath=', $BinPath) | Out-Null
  Add-Action $Name "BinPath" "OK" $BinPath
}

function Set-RecoverySc {
  param(
    [Parameter(Mandatory=$true)][string]$Name,
    [int]$RestartDelaySec = 5,
    [int]$MaxRestarts = 3,
    [int]$ResetDays = 1
  )

  if($MaxRestarts -lt 1){ $MaxRestarts = 1 }
  if($RestartDelaySec -lt 1){ $RestartDelaySec = 1 }
  if($ResetDays -lt 0){ $ResetDays = 0 }

  $delayMs = $RestartDelaySec * 1000
  $actions = @()
  for($i=0; $i -lt $MaxRestarts; $i++){
    $actions += "restart/$delayMs"
  }
  $actionsStr = ($actions -join '/')

  # reset= is in seconds; commonly set to days*86400
  $resetSec = $ResetDays * 86400

  Invoke-Sc -Svc $Name -Args @('failure', $Name, 'reset=', "$resetSec", 'actions=', $actionsStr) | Out-Null
  Invoke-Sc -Svc $Name -Args @('failureflag', $Name, '1') | Out-Null

  Add-Action $Name "Recovery" "OK" ("resetSec=$resetSec actions=$actionsStr")
}

function Map-StartType([string]$t){
  switch($t){
    'Automatic' { return 'auto' }
    'Manual'    { return 'demand' }
    'Disabled'  { return 'disabled' }
    'AutomaticDelayedStart' { return 'delayed-auto' }
    default { return 'auto' }
  }
}

function Start-ServiceSafe([string]$Name){
  try {
    if($PSCmdlet.ShouldProcess($Name, "Start-Service")){
      Start-Service -Name $Name -ErrorAction Stop
      Add-Action $Name "Start" "OK" ""
    } else {
      Add-Action $Name "Start" "WHATIF/SKIPPED" "Not approved"
    }
  } catch {
    Add-Action $Name "Start" "FAILED" $_.Exception.Message
    throw
  }
}

function Stop-ServiceSafe([string]$Name){
  try {
    $svc = Get-ServiceSafe $Name
    if($svc -and $svc.Status -ne 'Stopped'){
      if($PSCmdlet.ShouldProcess($Name, "Stop-Service")){
        Stop-Service -Name $Name -Force -ErrorAction Stop
        Add-Action $Name "Stop" "OK" ""
      } else {
        Add-Action $Name "Stop" "WHATIF/SKIPPED" "Not approved"
      }
    } else {
      Add-Action $Name "Stop" "SKIPPED" "Not running"
    }
  } catch {
    Add-Action $Name "Stop" "FAILED" $_.Exception.Message
    throw
  }
}

# -----------------------------
# Normalize input -> service definitions
# -----------------------------
function Get-ObjectPropertyValue {
  param(
    [object]$Object,
    [string[]]$Names,
    $Default = $null
  )

  if($null -eq $Object){ return $Default }
  foreach($name in $Names){
    $prop = $Object.PSObject.Properties[$name]
    if($prop -and $null -ne $prop.Value){
      return $prop.Value
    }
  }
  return $Default
}

function Normalize-ServiceDef {
  param($obj)

  $rawArgs = Get-ObjectPropertyValue -Object $obj -Names @('args', 'Arguments', 'service_arguments') -Default $null

  $def = [pscustomobject]@{
    name        = [string](Get-ObjectPropertyValue -Object $obj -Names @('name', 'ServiceName', 'serviceName', 'service_name') -Default '')
    displayName = [string](Get-ObjectPropertyValue -Object $obj -Names @('displayName', 'DisplayName', 'display_name') -Default '')
    description = [string](Get-ObjectPropertyValue -Object $obj -Names @('description', 'Description') -Default '')
    exe         = [string](Get-ObjectPropertyValue -Object $obj -Names @('exe', 'Executable', 'binary', 'service_executable') -Default '')
    args        = @()
    workingDir  = [string](Get-ObjectPropertyValue -Object $obj -Names @('workingDir', 'WorkingDirectory', 'working_dir') -Default '')
    startType   = [string](Get-ObjectPropertyValue -Object $obj -Names @('startType', 'start_type') -Default $StartType)
    useWrapper  = [bool](Get-ObjectPropertyValue -Object $obj -Names @('useWrapper', 'use_wrapper') -Default $false)
    stdout      = [string](Get-ObjectPropertyValue -Object $obj -Names @('stdout', 'stdout_path') -Default '')
    stderr      = [string](Get-ObjectPropertyValue -Object $obj -Names @('stderr', 'stderr_path') -Default '')
    recovery    = Get-ObjectPropertyValue -Object $obj -Names @('recovery') -Default $null
    startAfter  = [bool](Get-ObjectPropertyValue -Object $obj -Names @('startAfter', 'start_after_install') -Default $false)
    installable = [bool](Get-ObjectPropertyValue -Object $obj -Names @('installable') -Default $true)
    installAuthority = [bool](Get-ObjectPropertyValue -Object $obj -Names @('install_authority') -Default $true)
    serviceInstallAuthority = [bool](Get-ObjectPropertyValue -Object $obj -Names @('service_install_authority') -Default $true)
    serviceControlAuthority = [bool](Get-ObjectPropertyValue -Object $obj -Names @('service_control_authority') -Default $true)
    blockedReason = [string](Get-ObjectPropertyValue -Object $obj -Names @('blocked_reason') -Default '')
  }

  # args can be string or array
  if($null -ne $rawArgs){
    if($rawArgs -is [string]){
      $def.args = @([string]$rawArgs)
    } else {
      $def.args = @($rawArgs | ForEach-Object { [string]$_ })
    }
  }

  return $def
}

function Get-ServiceDefs {

  if(-not [string]::IsNullOrWhiteSpace($ConfigPath)){
    $cfg = Read-ConfigFile -Path $ConfigPath

    # Accept an array, an object with "services", or one service definition object.
    $items = $null
    if($cfg -is [System.Collections.IEnumerable] -and -not ($cfg -is [string])){
      $items = @($cfg)
    } else {
      $services = $cfg.PSObject.Properties['services']
      if($services -and $null -ne $services.Value){
        $items = @($services.Value)
      } else {
        $items = @($cfg)
      }
    }

    return @($items | ForEach-Object { Normalize-ServiceDef $_ })
  }

  # Single service
  $def = [pscustomobject]@{
    name        = $ServiceName
    displayName = $DisplayName
    description = $Description
    exe         = $Executable
    args        = @($Arguments | ForEach-Object { [string]$_ })
    workingDir  = $WorkingDirectory
    startType   = $StartType
    useWrapper  = [bool]$UseWrapper
    stdout      = $StdOutPath
    stderr      = $StdErrPath
    recovery    = @{ enabled = [bool]$SetRecovery; restartDelaySec=$RecoveryRestartDelaySec; maxRestarts=$RecoveryMaxRestarts; resetDays=$RecoveryResetDays }
    startAfter  = [bool]$StartAfterInstall
    installable = $true
    installAuthority = $true
    serviceInstallAuthority = $true
    serviceControlAuthority = $true
    blockedReason = ''
  }

  return @($def)
}

function Get-ServiceAuthorityBlockers {
  param(
    [Parameter(Mandatory=$true)]$Definition,
    [Parameter(Mandatory=$true)][string]$Operation
  )

  $blockers = New-Object System.Collections.Generic.List[string]

  if($Operation -in @('Install','Update')){
    if(-not [bool]$Definition.installable){ $blockers.Add('installable_false') | Out-Null }
    if(-not [bool]$Definition.installAuthority){ $blockers.Add('install_authority_false') | Out-Null }
    if(-not [bool]$Definition.serviceInstallAuthority){ $blockers.Add('service_install_authority_false') | Out-Null }
    if(-not [bool]$Definition.serviceControlAuthority){ $blockers.Add('service_control_authority_false') | Out-Null }
  }
  elseif($Operation -in @('Start','Stop','Restart')){
    if(-not [bool]$Definition.serviceControlAuthority){ $blockers.Add('service_control_authority_false') | Out-Null }
  }
  elseif($Operation -eq 'Uninstall'){
    if(-not [bool]$Definition.serviceInstallAuthority){ $blockers.Add('service_install_authority_false') | Out-Null }
    if(-not [bool]$Definition.serviceControlAuthority){ $blockers.Add('service_control_authority_false') | Out-Null }
  }

  return @($blockers.ToArray())
}

# -----------------------------
# Main
# -----------------------------
try {
  Write-Section "Service Install / Manager"
  Write-Host ("Mode      : {0}" -f $Mode)
  Write-Host ("Root      : {0}" -f (Resolve-FullPath $Root))
  Write-Host ("ConfigPath : {0}" -f $ConfigPath)
  Write-Host ("Log       : {0}" -f $LogPath)
  Write-Host ("CSV       : {0}" -f $CsvPath)
  Write-Host ("Report    : {0}" -f $JsonPath)
  Write-Host ("WhatIf    : {0}" -f $WhatIfPreference)
  Write-Host ("Force     : {0}" -f $Force)

  if(Test-DangerousPath $Root){
    throw "Refusing to operate on dangerous Root: $Root"
  }

  $defs = Get-ServiceDefs
  if(-not $defs -or $defs.Count -eq 0){
    throw "No services specified."
  }

  # Guard: for direct operations, require a name
  foreach($d in $defs){
    if([string]::IsNullOrWhiteSpace($d.name)){
      throw "Service definition missing name."
    }
  }

  $authorityBlockedServices = @{}
  $authorityAllowedServiceCount = 0
  if($Mode -in @('Install','Update','Uninstall','Start','Stop','Restart')){
    foreach($d in $defs){
      $name = [string]$d.name
      $authorityBlockers = @(Get-ServiceAuthorityBlockers -Definition $d -Operation $Mode)
      if($authorityBlockers.Count -gt 0){
        $authorityBlockedServices[$name] = $true
        $notes = "authority_blocked: " + (($authorityBlockers | Sort-Object) -join ',')
        Add-Action $name $Mode "BLOCKED" $notes
        Write-Section ("Authority blocked: {0}" -f $name)
        Write-Host ("Mode       : {0}" -f $Mode)
        Write-Host ("Blocked by : {0}" -f (($authorityBlockers | Sort-Object) -join ', '))
      } else {
        $authorityAllowedServiceCount += 1
      }
    }
  }

  if($Mode -eq 'Plan'){
    foreach($d in $defs){
      $name = [string]$d.name
      Write-Section ("Plan: {0}" -f $name)

      $blockedBy = New-Object System.Collections.Generic.List[string]
      if(-not [bool]$d.installable){ $blockedBy.Add("installable_false") | Out-Null }
      if(-not [bool]$d.installAuthority){ $blockedBy.Add("install_authority_false") | Out-Null }
      if(-not [bool]$d.serviceInstallAuthority){ $blockedBy.Add("service_install_authority_false") | Out-Null }
      if(-not [bool]$d.serviceControlAuthority){ $blockedBy.Add("service_control_authority_false") | Out-Null }

      $exePlan = Resolve-ExecutableForPlan ([string]$d.exe)
      if(-not [bool]$exePlan.exists){ $blockedBy.Add("service_executable_unresolved") | Out-Null }

      $workDirStatus = "not_requested"
      $workDirResolved = ""
      if(-not [string]::IsNullOrWhiteSpace([string]$d.workingDir)){
        $workDirResolved = Resolve-FullPath ([string]$d.workingDir)
        if(Test-Path -LiteralPath $workDirResolved -PathType Container){
          if(Test-DangerousPath $workDirResolved){
            $workDirStatus = "dangerous"
            $blockedBy.Add("working_directory_dangerous") | Out-Null
          } elseif(-not $OverrideSafety){
            $rootFull = Resolve-FullPath $Root
            $wLower = $workDirResolved.TrimEnd('\').ToLowerInvariant()
            $rLower = $rootFull.TrimEnd('\').ToLowerInvariant()
            if(-not ($wLower -eq $rLower -or $wLower.StartsWith($rLower + "\"))){
              $workDirStatus = "outside_root"
              $blockedBy.Add("working_directory_outside_root") | Out-Null
            } else {
              $workDirStatus = "ready"
            }
          } else {
            $workDirStatus = "ready"
          }
        } else {
          $workDirStatus = "missing"
          $blockedBy.Add("working_directory_missing") | Out-Null
        }
      }

      $binaryPlan = [pscustomobject]@{
        binary_path = ''
        service_command = ''
        wrapper = [pscustomobject]@{
          enabled = $false
          path = ''
          would_write = $false
        }
      }
      if([bool]$exePlan.exists -and $workDirStatus -notin @("missing", "dangerous", "outside_root")){
        $binaryPlan = Build-BinaryPathPlan -SvcName $name -Exe ([string]$exePlan.resolved) -CommandArgs @($d.args) -WorkDir ([string]$d.workingDir) -WantWrapper:([bool]$d.useWrapper) -StdOut ([string]$d.stdout) -StdErr ([string]$d.stderr)
      }

      $ready = $blockedBy.Count -eq 0
      $plan = [pscustomobject]@{
        kind = 'service_install.plan'
        service = $name
        status = $(if($ready){ 'ready' } else { 'blocked' })
        ready = $ready
        would_install = $ready
        would_start = [bool]$d.startAfter
        mode = 'Plan'
        display_name = [string]$d.displayName
        description = [string]$d.description
        start_type = [string]$d.startType
        executable = [pscustomobject]@{
          value = [string]$d.exe
          resolved = [string]$exePlan.resolved
          exists = [bool]$exePlan.exists
          source = [string]$exePlan.source
          reason = [string]$exePlan.reason
        }
        arguments = @($d.args)
        working_directory = [pscustomobject]@{
          value = [string]$d.workingDir
          resolved = $workDirResolved
          status = $workDirStatus
        }
        binary_path = [string]$binaryPlan.binary_path
        service_command = [string]$binaryPlan.service_command
        wrapper = $binaryPlan.wrapper
        blocked_by = @($blockedBy)
        blocked_reason = [string]$d.blockedReason
        governance = [pscustomobject]@{
          read_only_contract = $true
          execution_authority = $false
          approval_decision_authority = $false
          memory_write = $false
          local_process_launch_authority = $false
          service_install_authority = $false
          service_control_authority = $false
          mutation_authority_granted = $false
        }
      }

      $script:Plans.Add($plan) | Out-Null
      Add-Action $name "Plan" "OK" ("status={0}; would_install={1}; blockers={2}" -f $plan.status, $plan.would_install, (($plan.blocked_by | Sort-Object) -join ','))
      Write-Host ("Plan status : {0}" -f $plan.status)
      Write-Host ("Would install: {0}" -f $plan.would_install)
      Write-Host ("Blocked by   : {0}" -f (($plan.blocked_by | Sort-Object) -join ', '))
    }
  }

  $mutating = $Mode -in @('Install','Update','Uninstall')
  if($mutating -and $authorityAllowedServiceCount -gt 0){
    Require-Admin $Mode
  }

  if($Mode -ne 'Plan'){
  foreach($d in $defs){
    $name = [string]$d.name
    if($authorityBlockedServices.ContainsKey($name)){
      continue
    }

    Write-Section ("Service: {0}" -f $name)

    $svc = Get-ServiceSafe $name

    if($Mode -eq 'Status'){
      if($svc){
        $wmi = $null
        try { $wmi = Get-CimInstance Win32_Service -Filter "Name='$name'" -ErrorAction SilentlyContinue } catch {}
        Write-Host ("Name       : {0}" -f $svc.Name)
        Write-Host ("Status     : {0}" -f $svc.Status)
        Write-Host ("StartType  : {0}" -f ($wmi.StartMode ?? "(unknown)"))
        if($wmi){
          Write-Host ("DisplayName: {0}" -f $wmi.DisplayName)
          Write-Host ("PathName   : {0}" -f $wmi.PathName)
          Write-Host ("Account    : {0}" -f $wmi.StartName)
          Write-Host ("State      : {0}" -f $wmi.State)
        }
        Add-Action $name "Status" "OK" ("{0}" -f $svc.Status)
      } else {
        Write-Host "Not installed."
        Add-Action $name "Status" "SKIPPED" "Not installed"
      }
      continue
    }

    if($Mode -eq 'Start'){
      if(-not $svc){
        Add-Action $name "Start" "FAILED" "Service not installed"
        throw "Service not installed: $name"
      }
      Start-ServiceSafe $name
      continue
    }

    if($Mode -eq 'Stop'){
      if(-not $svc){
        Add-Action $name "Stop" "SKIPPED" "Service not installed"
        continue
      }
      Stop-ServiceSafe $name
      continue
    }

    if($Mode -eq 'Restart'){
      if(-not $svc){
        Add-Action $name "Restart" "FAILED" "Service not installed"
        throw "Service not installed: $name"
      }
      Stop-ServiceSafe $name
      Start-Sleep -Milliseconds 600
      Start-ServiceSafe $name
      Add-Action $name "Restart" "OK" ""
      continue
    }

    if($Mode -eq 'Uninstall'){
      Require-Force "Uninstall"

      if(-not $svc){
        Add-Action $name "Uninstall" "SKIPPED" "Not installed"
        continue
      }

      Stop-ServiceSafe $name

      if($PSCmdlet.ShouldProcess($name, "sc.exe delete")){
        try {
          Invoke-Sc -Svc $name -Args @('delete', $name) | Out-Null
          Add-Action $name "Uninstall" "OK" "Deleted service"
        } catch {
          Add-Action $name "Uninstall" "FAILED" $_.Exception.Message
          throw
        }
      } else {
        Add-Action $name "Uninstall" "WHATIF/SKIPPED" "Not approved"
      }

      continue
    }

    # Install / Update need exe
    if([string]::IsNullOrWhiteSpace($d.exe)){
      throw "Service '$name' missing exe/Executable."
    }

    $exeFull = Resolve-FullPath $d.exe
    if(-not (Test-Path -LiteralPath $exeFull)){
      throw "Executable not found for '$name': $exeFull"
    }

    $workDir = [string]$d.workingDir
    if(-not [string]::IsNullOrWhiteSpace($workDir)){
      $workDir = Resolve-FullPath $workDir
      if(-not (Test-Path -LiteralPath $workDir)){
        throw "WorkingDirectory not found for '$name': $workDir"
      }
      if(Test-DangerousPath $workDir){
        throw "Refusing dangerous WorkingDirectory: $workDir"
      }
      if(-not $OverrideSafety){
        # allow only under Root
        $rootFull = Resolve-FullPath $Root
        $wLower = $workDir.TrimEnd('\').ToLowerInvariant()
        $rLower = $rootFull.TrimEnd('\').ToLowerInvariant()
        if(-not ($wLower -eq $rLower -or $wLower.StartsWith($rLower + "\"))){
          throw "Safety block: WorkingDirectory is outside Root. Use -OverrideSafety to allow. WorkDir: $workDir"
        }
      }
    }

    $wantWrapper = [bool]$d.useWrapper
    $binPath = Build-BinaryPath -SvcName $name -Exe $exeFull -Args $d.args -WorkDir $workDir -WantWrapper:($wantWrapper -or $UseWrapper) -StdOut $d.stdout -StdErr $d.stderr

    $disp = [string]$d.displayName
    if([string]::IsNullOrWhiteSpace($disp)){ $disp = $name }

    $desc = [string]$d.description

    $startTypeSc = Map-StartType ([string]$d.startType)

    $recoveryEnabled = $false
    $recDelay = $RecoveryRestartDelaySec
    $recMax   = $RecoveryMaxRestarts
    $recReset = $RecoveryResetDays

    if($d.recovery){
      try {
        if($null -ne $d.recovery.enabled){ $recoveryEnabled = [bool]$d.recovery.enabled }
        if($null -ne $d.recovery.restartDelaySec){ $recDelay = [int]$d.recovery.restartDelaySec }
        if($null -ne $d.recovery.maxRestarts){ $recMax = [int]$d.recovery.maxRestarts }
        if($null -ne $d.recovery.resetDays){ $recReset = [int]$d.recovery.resetDays }
      } catch {}
    } else {
      $recoveryEnabled = [bool]$SetRecovery
    }

    if($Mode -eq 'Install'){
      if($svc){
        Add-Action $name "Install" "FAILED" "Already installed (use -Mode Update or uninstall first)"
        throw "Service already exists: $name (use -Mode Update)"
      }

      Write-Host ("Installing: {0}" -f $name)
      Write-Host ("BinPath   : {0}" -f $binPath)
      Write-Host ("StartType : {0}" -f $startTypeSc)

      if($PSCmdlet.ShouldProcess($name, "New-Service")){
        try {
          # New-Service doesn't support delayed-auto directly; create as auto then adjust via sc.exe
          $startup = 'Automatic'
          if($startTypeSc -eq 'demand'){ $startup = 'Manual' }
          if($startTypeSc -eq 'disabled'){ $startup = 'Disabled' }

          New-Service -Name $name -BinaryPathName $binPath -DisplayName $disp -Description $desc -StartupType $startup | Out-Null
          Add-Action $name "Install" "OK" "Created service"

          # Apply DisplayName/Description/StartType via sc.exe for consistency and delayed-auto
          Set-DisplayNameSc -Name $name -Disp $disp
          Set-DescriptionSc -Name $name -Desc $desc
          Set-BinPathSc     -Name $name -BinPath $binPath
          Set-StartTypeSc   -Name $name -Type $startTypeSc

          if($recoveryEnabled){
            Set-RecoverySc -Name $name -RestartDelaySec $recDelay -MaxRestarts $recMax -ResetDays $recReset
          }

          if([bool]$d.startAfter -or $StartAfterInstall){
            Start-ServiceSafe $name
          }
        } catch {
          Add-Action $name "Install" "FAILED" $_.Exception.Message
          throw
        }
      } else {
        Add-Action $name "Install" "WHATIF/SKIPPED" "Not approved"
      }

      continue
    }

    if($Mode -eq 'Update'){
      if(-not $svc){
        Add-Action $name "Update" "FAILED" "Not installed"
        throw "Service not installed: $name"
      }

      Write-Host ("Updating: {0}" -f $name)
      Write-Host ("BinPath : {0}" -f $binPath)
      Write-Host ("StartType: {0}" -f $startTypeSc)

      if($PSCmdlet.ShouldProcess($name, "Update service config")){
        try {
          # Stop first (best effort)
          Stop-ServiceSafe $name

          Set-DisplayNameSc -Name $name -Disp $disp
          Set-DescriptionSc -Name $name -Desc $desc
          Set-BinPathSc     -Name $name -BinPath $binPath
          Set-StartTypeSc   -Name $name -Type $startTypeSc

          if($recoveryEnabled){
            Set-RecoverySc -Name $name -RestartDelaySec $recDelay -MaxRestarts $recMax -ResetDays $recReset
          }

          Add-Action $name "Update" "OK" "Updated configuration"

          if([bool]$d.startAfter -or $StartAfterInstall){
            Start-ServiceSafe $name
          }
        } catch {
          Add-Action $name "Update" "FAILED" $_.Exception.Message
          throw
        }
      } else {
        Add-Action $name "Update" "WHATIF/SKIPPED" "Not approved"
      }

      continue
    }
  }
  }

  # -----------------------------
  # Write outputs
  # -----------------------------
  Write-Section "Write reports"
  $script:Actions | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $CsvPath

  $report = [pscustomobject]@{
    timestamp = $Now
    mode      = $Mode
    root      = (Resolve-FullPath $Root)
    config    = $ConfigPath
    log       = $LogPath
    csv       = $CsvPath
    actions   = @($script:Actions.ToArray())
    plans     = @($script:Plans.ToArray())
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
