<#
D:\francis\scripts\trust-reset.ps1

Purpose
  Controlled reset of trust state while preserving history.

Safety
  - Default is dry run.
  - Writes only under -Root (default D:\francis).
  - Creates a backup of the prior state before reset.

Examples
  # Dry run
  pwsh -File D:\francis\scripts\trust-reset.ps1

  # Apply reset with a reason
  pwsh -File D:\francis\scripts\trust-reset.ps1 -Apply -Reason "post-incident reset"
#>

[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
param(
  [string]$Root = 'D:\francis',
  [switch]$Apply,
  [string]$Reason = 'manual_reset',
  [switch]$OverrideSafety
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Resolve-FullPath([string]$Path){
  try { return (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path }
  catch { try { return [System.IO.Path]::GetFullPath($Path) } catch { return $Path } }
}

function Test-DangerousPath([string]$Path){
  $p = (Resolve-FullPath $Path)
  $drive = [System.IO.Path]::GetPathRoot($p)
  if ($p -eq $drive) { return $true }
  $lower = $p.ToLowerInvariant()
  if ($lower -like "$($drive.ToLowerInvariant())windows*") { return $true }
  if ($lower -like "$($drive.ToLowerInvariant())program files*") { return $true }
  if ($lower -like "$($drive.ToLowerInvariant())programdata*") { return $true }
  return $false
}

if (-not (Test-Path -LiteralPath $Root)) {
  throw "Root not found: $Root"
}

if ((Test-DangerousPath $Root) -and -not $OverrideSafety) {
  throw "Refusing to operate on dangerous path: $Root (use -OverrideSafety to bypass)"
}

$Now = Get-Date -Format "yyyyMMdd_HHmmss"
$OpsDir = Join-Path $Root 'data\logs\operations'
$StatePath = Join-Path $Root 'data\trust\levels\current_state.json'
$BackupPath = Join-Path $OpsDir ("trust_reset_{0}.backup.json" -f $Now)
$LogPath = Join-Path $OpsDir ("trust_reset_{0}.log" -f $Now)
$AuditPath = Join-Path $OpsDir ("trust_reset_{0}.json" -f $Now)

New-Item -ItemType Directory -Force -Path $OpsDir | Out-Null

function Write-Log([string]$Message){
  $line = ("[{0}] {1}" -f (Get-Date).ToString('s'), $Message)
  Add-Content -Path $LogPath -Value $line
  Write-Host $line
}

$state = @{
  global_level = 0
  domain_levels = @{}
  last_updated = [double][DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
  reset_reason = $Reason
  reset_time_utc = (Get-Date).ToUniversalTime().ToString('s')
}

if (-not $Apply) {
  Write-Log "DRY RUN: would reset trust state at $StatePath"
  Write-Log "DRY RUN: would write backup to $BackupPath"
  Write-Log "DRY RUN: reason=$Reason"
  return
}

if ($PSCmdlet.ShouldProcess($StatePath, "Reset trust state")) {
  if (Test-Path -LiteralPath $StatePath) {
    Copy-Item -LiteralPath $StatePath -Destination $BackupPath -Force
    Write-Log "Backed up trust state to $BackupPath"
  } else {
    Write-Log "No existing trust state found; creating new state"
  }

  $stateDir = Split-Path -Parent $StatePath
  New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
  $state | ConvertTo-Json -Depth 5 | Set-Content -Path $StatePath -Encoding UTF8
  $state | ConvertTo-Json -Depth 5 | Set-Content -Path $AuditPath -Encoding UTF8
  Write-Log "Reset complete: $StatePath"
  Write-Log "Audit record: $AuditPath"
}
