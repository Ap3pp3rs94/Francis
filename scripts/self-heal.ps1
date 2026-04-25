<#
D:\francis\scripts\self-evolve.ps1

Purpose
  "Self-evolve" = controlled update of the Francis workspace from a trusted source snapshot.

What it does
  - Creates a change plan by comparing a Source snapshot (folder or zip) to your Root (default D:\francis)
  - Applies changes with strong safety rails and full logging
  - Creates a rollback backup so you can restore prior state
  - Optionally verifies changed files (PowerShell parse / JSON parse / YAML parse if available)

Default scope
  - Only updates: <Root>\scripts\*
  - No deletes unless -AllowDeletes is specified (and -Force for destructive actions)

Logs / outputs
  - Transcript: <Root>\data\logs\operations\self_evolve_<timestamp>.log
  - CSV plan : <Root>\data\logs\operations\self_evolve_<timestamp>.csv
  - JSON rpt : <Root>\data\logs\operations\self_evolve_report_<timestamp>.json
  - Backups  : <Root>\data\backups\self_evolve\<timestamp>\  (includes rollback manifest)

Examples
  # Plan changes (no modifications)
  pwsh -File D:\francis\scripts\self-evolve.ps1 -Mode Plan -SourcePath C:\temp\francis_snapshot

  # Apply changes to scripts only (no deletes)
  pwsh -File D:\francis\scripts\self-evolve.ps1 -Mode Apply -SourcePath C:\temp\francis_snapshot -Verify

  # Apply from a zip
  pwsh -File D:\francis\scripts\self-evolve.ps1 -Mode Apply -SourcePath C:\temp\francis_snapshot.zip -Verify

  # Allow deletes (destructive -> requires -Force)
  pwsh -File D:\francis\scripts\self-evolve.ps1 -Mode Apply -SourcePath C:\temp\francis_snapshot -AllowDeletes -Force

  # Rollback using a backup folder
  pwsh -File D:\francis\scripts\self-evolve.ps1 -Mode Rollback -BackupDir D:\francis\data\backups\self_evolve\20260102_123456 -Force

  # Show current state / latest backup
  pwsh -File D:\francis\scripts\self-evolve.ps1 -Mode Status

Safety rails
  - Blocks dangerous targets (drive roots, Windows folders, Program Files, ProgramData)
  - Default restricts writes to within Root
  - Requires -Force for any destructive mode or for deletes / rollback
  - Supports -WhatIf / -Confirm via ShouldProcess
#>

[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
param(
  [ValidateSet('Status','Plan','Apply','Rollback','Verify','CleanTemp')]
  [string]$Mode = 'Status',

  [string]$Root = 'D:\francis',

  # Source snapshot path (directory or .zip). Required for Plan/Apply.
  [string]$SourcePath = '',

  # Default scope: scripts only. You can add more (e.g., 'data\config') if you want.
  [string[]]$Scopes = @('scripts'),

  # Exclusions applied under source scope (substring match on full path)
  [string[]]$ExcludeSubstrings = @('\node_modules\','\.git\','\data\logs\','\data\backups\','\data\runtime\'),

  # Allow deleting files in Root scope that do not exist in Source scope (destructive).
  [switch]$AllowDeletes,

  # Required for destructive actions: Apply with deletes, Rollback
  [switch]$Force,

  # Run sanity validation on changed files after Apply (or for Verify mode)
  [switch]$Verify,

  # Optional: run a full root sanity scan by calling credential-delegate.ps1 if present
  [switch]$RunFullSanityScript,

  # If you *intentionally* want to update outside Root, you can set this.
  # Still blocks system roots/folders.
  [switch]$OverrideSafety,

  # For Rollback mode: specify the backup directory to restore from.
  [string]$BackupDir = ''
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# -----------------------------
# Logging / paths
# -----------------------------
$Now   = Get-Date -Format 'yyyyMMdd_HHmmss'
$Ops   = Join-Path $Root 'data\logs\operations'
$BkpRoot = Join-Path $Root 'data\backups\self_evolve'
$Runtime = Join-Path $Root 'data\runtime\self_evolve'
$TempBase = Join-Path $Root 'data\runtime\self_evolve\temp'

New-Item -ItemType Directory -Force -Path $Ops     | Out-Null
New-Item -ItemType Directory -Force -Path $BkpRoot | Out-Null
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
New-Item -ItemType Directory -Force -Path $TempBase| Out-Null

$LogPath   = Join-Path $Ops ("self_evolve_{0}.log" -f $Now)
$CsvPath   = Join-Path $Ops ("self_evolve_{0}.csv" -f $Now)
$JsonPath  = Join-Path $Ops ("self_evolve_report_{0}.json" -f $Now)
$LatestPtr = Join-Path $Runtime 'latest_backup.txt'

$script:Actions = New-Object System.Collections.Generic.List[object]
$script:TempDir = $null

function Add-Action {
  param(
    [string]$Action,
    [string]$RelPath,
    [string]$Result,
    [string]$Notes = ''
  )
  $script:Actions.Add([pscustomobject]@{
    Time   = (Get-Date).ToString('s')
    Action = $Action
    Path   = $RelPath
    Result = $Result
    Notes  = $Notes
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

  # block drive roots like C:\
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

function Test-IsUnderRoot {
  param([string]$Path,[string]$RootPath)

  $p = (Resolve-FullPath $Path).TrimEnd('\')
  $r = (Resolve-FullPath $RootPath).TrimEnd('\')

  $pLower = $p.ToLowerInvariant()
  $rLower = $r.ToLowerInvariant()

  if($pLower -eq $rLower){ return $true }
  if($pLower.StartsWith($rLower + "\")){ return $true }
  return $false
}

function Get-RelativePath {
  param([string]$Base,[string]$Full)

  $b = (Resolve-FullPath $Base).TrimEnd('\') + '\'
  $f = (Resolve-FullPath $Full)

  $bUri = New-Object System.Uri($b)
  $fUri = New-Object System.Uri($f)

  $relUri = $bUri.MakeRelativeUri($fUri)
  $rel = [System.Uri]::UnescapeDataString($relUri.ToString()) -replace '/','\'
  return $rel
}

function Test-Excluded {
  param([string]$FullPath)

  $p = $FullPath.ToLowerInvariant()
  foreach($ex in $ExcludeSubstrings){
    if([string]::IsNullOrWhiteSpace($ex)){ continue }
    if($p.Contains(($ex.ToLowerInvariant()))){ return $true }
  }
  return $false
}

function Get-HashSafe {
  param([string]$Path)
  try {
    if(-not (Test-Path -LiteralPath $Path)){ return $null }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash
  } catch {
    return $null
  }
}

function Require-Force([string]$Why){
  if(-not $Force){
    $msg = "$Why requires -Force (try -WhatIf first)."
    Add-Action "Guard" $Why "BLOCKED" $msg
    throw $msg
  }
}

# -----------------------------
# Source resolve (folder or zip)
# -----------------------------
function New-TempDir {
  $d = Join-Path $TempBase ("evolve_{0}_{1}" -f $Now, ([Guid]::NewGuid().ToString('N').Substring(0,8)))
  New-Item -ItemType Directory -Force -Path $d | Out-Null
  return $d
}

function Resolve-SourceDir {
  param([string]$Src)

  if([string]::IsNullOrWhiteSpace($Src)){
    throw "SourcePath is required for Mode Plan/Apply."
  }

  $srcFull = Resolve-FullPath $Src
  if(-not (Test-Path -LiteralPath $srcFull)){
    throw "SourcePath not found: $srcFull"
  }

  $item = Get-Item -LiteralPath $srcFull -Force

  if($item.PSIsContainer){
    return $srcFull
  }

  # file - if zip, extract
  $ext = ([System.IO.Path]::GetExtension($srcFull) ?? '').ToLowerInvariant()
  if($ext -ne '.zip'){
    throw "SourcePath is a file but not .zip: $srcFull"
  }

  $tmp = New-TempDir
  $script:TempDir = $tmp

  Write-Host "Extracting zip -> $tmp"
  if($PSCmdlet.ShouldProcess($tmp, "Expand-Archive $srcFull")){
    Expand-Archive -LiteralPath $srcFull -DestinationPath $tmp -Force
    Add-Action "Extract" $srcFull "OK" $tmp
  } else {
    Add-Action "Extract" $srcFull "WHATIF/SKIPPED" $tmp
  }

  # Heuristic: if zip contains a single top folder, use that as source root
  $top = Get-ChildItem -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
  if($top -and $top.Count -eq 1 -and $top[0].PSIsContainer){
    return (Resolve-FullPath $top[0].FullName)
  }

  return $tmp
}

# -----------------------------
# Plan building
# -----------------------------
function Build-Plan {
  param([string]$SourceDir)

  $rootFull = Resolve-FullPath $Root
  $srcFull  = Resolve-FullPath $SourceDir

  if(Test-DangerousPath $rootFull){
    throw "Refusing to operate on dangerous Root: $rootFull"
  }

  if(-not $OverrideSafety){
    # Root is itself the allowed boundary; always true.
  }

  $plan = New-Object System.Collections.Generic.List[object]

  foreach($scopeRel in $Scopes){
    if([string]::IsNullOrWhiteSpace($scopeRel)){ continue }

    $scopeSrc = Join-Path $srcFull $scopeRel
    $scopeDst = Join-Path $rootFull $scopeRel

    if(-not (Test-Path -LiteralPath $scopeSrc)){
      Add-Action "Scope" $scopeRel "WARN" "Scope missing in source: $scopeSrc"
      continue
    }

    if(Test-DangerousPath $scopeDst){
      throw "Refusing to write into dangerous destination scope: $scopeDst"
    }
    if(-not $OverrideSafety){
      if(-not (Test-IsUnderRoot -Path $scopeDst -RootPath $rootFull)){
        throw "Safety block: destination scope is not under Root: $scopeDst"
      }
    }

    # Enumerate files in source scope
    $srcFiles = Get-ChildItem -LiteralPath $scopeSrc -Recurse -File -Force -ErrorAction SilentlyContinue |
      Where-Object { -not (Test-Excluded -FullPath $_.FullName) }

    foreach($sf in $srcFiles){
      $relFromSrcRoot = Get-RelativePath -Base $srcFull -Full $sf.FullName

      # Prevent path traversal
      if($relFromSrcRoot -match '^\.\.' -or $relFromSrcRoot -match '^[A-Za-z]:\\'){
        Add-Action "Plan" $relFromSrcRoot "BLOCKED" "Suspicious relative path"
        continue
      }

      $dstPath = Join-Path $rootFull $relFromSrcRoot

      if(-not $OverrideSafety){
        if(-not (Test-IsUnderRoot -Path $dstPath -RootPath $rootFull)){
          Add-Action "Plan" $relFromSrcRoot "BLOCKED" "Destination not under Root"
          continue
        }
      }

      $srcHash = Get-HashSafe $sf.FullName
      $dstHash = Get-HashSafe $dstPath

      $action = 'NOOP'
      if(-not (Test-Path -LiteralPath $dstPath)){
        $action = 'CREATE'
      } elseif($srcHash -and $dstHash -and ($srcHash -ne $dstHash)){
        $action = 'UPDATE'
      } elseif($srcHash -and -not $dstHash){
        # can't hash dst; treat as UPDATE to be safe
        $action = 'UPDATE'
      }

      $plan.Add([pscustomobject]@{
        Action    = $action
        RelPath   = $relFromSrcRoot
        Source    = $sf.FullName
        Dest      = $dstPath
        SrcHash   = $srcHash
        DstHash   = $dstHash
        SizeKB    = [math]::Round(($sf.Length/1KB),2)
      }) | Out-Null
    }

    if($AllowDeletes){
      # Enumerate destination files and delete those not found in source
      $dstFiles = @()
      if(Test-Path -LiteralPath $scopeDst){
        $dstFiles = Get-ChildItem -LiteralPath $scopeDst -Recurse -File -Force -ErrorAction SilentlyContinue |
          Where-Object { -not (Test-Excluded -FullPath $_.FullName) }
      }

      # Build a lookup of source rel paths under this scope
      $srcRelSet = New-Object System.Collections.Generic.HashSet[string] ([StringComparer]::OrdinalIgnoreCase)
      foreach($p in $plan){
        if(($p.RelPath -as [string]).StartsWith(($scopeRel.TrimEnd('\') + '\'), [System.StringComparison]::OrdinalIgnoreCase)){
          [void]$srcRelSet.Add([string]$p.RelPath)
        }
      }

      foreach($df in $dstFiles){
        $relFromRoot = Get-RelativePath -Base $rootFull -Full $df.FullName
        if(-not $srcRelSet.Contains($relFromRoot)){
          $plan.Add([pscustomobject]@{
            Action    = 'DELETE'
            RelPath   = $relFromRoot
            Source    = ''
            Dest      = $df.FullName
            SrcHash   = ''
            DstHash   = (Get-HashSafe $df.FullName)
            SizeKB    = [math]::Round(($df.Length/1KB),2)
          }) | Out-Null
        }
      }
    }
  }

  return @($plan)
}

# -----------------------------
# Backup / apply / rollback
# -----------------------------
function Ensure-ParentDir([string]$Path){
  $p = Split-Path -Parent $Path
  if([string]::IsNullOrWhiteSpace($p)){ return }
  if(-not (Test-Path -LiteralPath $p)){
    New-Item -ItemType Directory -Force -Path $p | Out-Null
  }
}

function Backup-File {
  param(
    [string]$BackupBase,
    [string]$RelPath,
    [string]$ExistingPath
  )

  $dst = Join-Path $BackupBase $RelPath
  Ensure-ParentDir $dst

  if(Test-Path -LiteralPath $ExistingPath){
    Copy-Item -LiteralPath $ExistingPath -Destination $dst -Force -ErrorAction Stop
    Add-Action "Backup" $RelPath "OK" $dst
  } else {
    Add-Action "Backup" $RelPath "SKIPPED" "No existing file to backup"
  }
}

function Apply-Plan {
  param(
    [object[]]$Plan,
    [string]$SourceDir
  )

  $backupDir = Join-Path $BkpRoot $Now
  New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

  $rollbackManifest = [pscustomobject]@{
    timestamp    = $Now
    root         = (Resolve-FullPath $Root)
    source       = (Resolve-FullPath $SourceDir)
    scopes       = @($Scopes)
    allowDeletes = [bool]$AllowDeletes
    createdFiles = @()
    deletedFiles = @()
    updatedFiles = @()
  }

  # Determine if destructive
  $hasDeletes = ($Plan | Where-Object { $_.Action -eq 'DELETE' }).Count -gt 0
  if($hasDeletes){
    Require-Force "Apply with deletes"
  }

  Write-Section "Applying changes"
  Write-Host ("BackupDir: {0}" -f (Resolve-FullPath $backupDir))

  foreach($item in $Plan){
    $act = [string]$item.Action
    $rel = [string]$item.RelPath
    $src = [string]$item.Source
    $dst = [string]$item.Dest

    if($act -eq 'NOOP'){
      Add-Action "Apply" $rel "SKIPPED" "No changes"
      continue
    }

    if(Test-DangerousPath $dst){
      Add-Action "Apply" $rel "BLOCKED" "Destination is dangerous"
      throw "Refusing to write/delete dangerous destination: $dst"
    }

    if(-not $OverrideSafety){
      if(-not (Test-IsUnderRoot -Path $dst -RootPath $Root)){
        Add-Action "Apply" $rel "BLOCKED" "Destination not under Root"
        throw "Safety block: destination not under Root: $dst"
      }
    }

    switch($act){
      'CREATE' {
        if($PSCmdlet.ShouldProcess($dst, "CREATE from $src")){
          try{
            Ensure-ParentDir $dst
            Copy-Item -LiteralPath $src -Destination $dst -Force -ErrorAction Stop
            Add-Action "CREATE" $rel "OK" ""
            $rollbackManifest.createdFiles += $rel
          } catch {
            Add-Action "CREATE" $rel "FAILED" $_.Exception.Message
            throw
          }
        } else {
          Add-Action "CREATE" $rel "WHATIF/SKIPPED" "Not approved"
        }
      }

      'UPDATE' {
        # backup existing
        Backup-File -BackupBase $backupDir -RelPath $rel -ExistingPath $dst

        if($PSCmdlet.ShouldProcess($dst, "UPDATE from $src")){
          try{
            Ensure-ParentDir $dst
            Copy-Item -LiteralPath $src -Destination $dst -Force -ErrorAction Stop
            Add-Action "UPDATE" $rel "OK" ""
            $rollbackManifest.updatedFiles += $rel
          } catch {
            Add-Action "UPDATE" $rel "FAILED" $_.Exception.Message
            throw
          }
        } else {
          Add-Action "UPDATE" $rel "WHATIF/SKIPPED" "Not approved"
        }
      }

      'DELETE' {
        Require-Force "Delete file(s)"

        # backup file before delete
        Backup-File -BackupBase $backupDir -RelPath $rel -ExistingPath $dst

        if($PSCmdlet.ShouldProcess($dst, "DELETE")){
          try{
            Remove-Item -LiteralPath $dst -Force -ErrorAction Stop
            Add-Action "DELETE" $rel "OK" ""
            $rollbackManifest.deletedFiles += $rel
          } catch {
            Add-Action "DELETE" $rel "FAILED" $_.Exception.Message
            throw
          }
        } else {
          Add-Action "DELETE" $rel "WHATIF/SKIPPED" "Not approved"
        }
      }

      default {
        Add-Action "Apply" $rel "SKIPPED" "Unknown action '$act'"
      }
    }
  }

  # Save rollback manifest in backup folder
  $rbPath = Join-Path $backupDir 'rollback_manifest.json'
  if($PSCmdlet.ShouldProcess($rbPath, "Write rollback manifest")){
    ($rollbackManifest | ConvertTo-Json -Depth 6) | Out-File -LiteralPath $rbPath -Encoding UTF8 -Force
    Add-Action "Backup" "rollback_manifest.json" "OK" $rbPath
  } else {
    Add-Action "Backup" "rollback_manifest.json" "WHATIF/SKIPPED" "Not approved"
  }

  # update latest pointer
  try {
    (Resolve-FullPath $backupDir) | Out-File -LiteralPath $LatestPtr -Encoding UTF8 -Force
  } catch {}

  return $backupDir
}

function Rollback-FromBackup {
  param([string]$Backup)

  Require-Force "Rollback"

  $backupFull = Resolve-FullPath $Backup
  if(-not (Test-Path -LiteralPath $backupFull)){
    throw "BackupDir not found: $backupFull"
  }

  $rbPath = Join-Path $backupFull 'rollback_manifest.json'
  if(-not (Test-Path -LiteralPath $rbPath)){
    throw "rollback_manifest.json not found in backup dir: $backupFull"
  }

  $rb = Get-Content -LiteralPath $rbPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop

  Write-Section "Rollback"
  Write-Host ("BackupDir : {0}" -f $backupFull)
  Write-Host ("Root      : {0}" -f (Resolve-FullPath $Root))

  # 1) Delete created files (those didn’t exist before)
  foreach($rel in @($rb.createdFiles)){
    $dst = Join-Path $Root $rel
    if(Test-Path -LiteralPath $dst){
      if($PSCmdlet.ShouldProcess($dst, "Rollback: delete created file")){
        try{
          Remove-Item -LiteralPath $dst -Force -ErrorAction Stop
          Add-Action "RB-DELETE" $rel "OK" "Removed created file"
        } catch {
          Add-Action "RB-DELETE" $rel "FAILED" $_.Exception.Message
          throw
        }
      } else {
        Add-Action "RB-DELETE" $rel "WHATIF/SKIPPED" "Not approved"
      }
    } else {
      Add-Action "RB-DELETE" $rel "SKIPPED" "Already not present"
    }
  }

  # 2) Restore backed-up files (updates + deletes)
  $backupFiles = Get-ChildItem -LiteralPath $backupFull -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notlike (Join-Path $backupFull 'rollback_manifest.json') }

  foreach($bf in $backupFiles){
    $rel = Get-RelativePath -Base $backupFull -Full $bf.FullName
    if($rel -ieq 'rollback_manifest.json'){ continue }

    $dst = Join-Path $Root $rel

    if(Test-DangerousPath $dst){
      Add-Action "RB-RESTORE" $rel "BLOCKED" "Destination dangerous"
      throw "Refusing to restore into dangerous destination: $dst"
    }

    if(-not $OverrideSafety){
      if(-not (Test-IsUnderRoot -Path $dst -RootPath $Root)){
        Add-Action "RB-RESTORE" $rel "BLOCKED" "Destination not under Root"
        throw "Safety block: restore destination not under Root: $dst"
      }
    }

    if($PSCmdlet.ShouldProcess($dst, "Rollback: restore from backup")){
      try{
        Ensure-ParentDir $dst
        Copy-Item -LiteralPath $bf.FullName -Destination $dst -Force -ErrorAction Stop
        Add-Action "RB-RESTORE" $rel "OK" ""
      } catch {
        Add-Action "RB-RESTORE" $rel "FAILED" $_.Exception.Message
        throw
      }
    } else {
      Add-Action "RB-RESTORE" $rel "WHATIF/SKIPPED" "Not approved"
    }
  }
}

# -----------------------------
# Verification (best-effort)
# -----------------------------
$Py = $null
try { $Py = (Get-Command python -ErrorAction SilentlyContinue).Source } catch {}
$HasCfy = $false
try { if(Get-Command ConvertFrom-Yaml -ErrorAction SilentlyContinue){ $HasCfy = $true } } catch {}
$HasPyYaml = $false
if($Py){
  try { & $Py -c "import yaml" 2>$null; $HasPyYaml = ($LASTEXITCODE -eq 0) } catch {}
}

function Test-TextReadable([string]$Path){
  try { Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | Out-Null; return $true } catch { return $false }
}

function Test-YamlFile([string]$Path){
  # returns $null on success, otherwise returns error string
  try{
    if($HasCfy){
      $raw = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
      $null = $raw | ConvertFrom-Yaml -ErrorAction Stop
      return $null
    }
    elseif($Py -and $HasPyYaml){
      $out = & $Py -c "import sys,yaml; p=sys.argv[1]; s=open(p,'rb').read().decode('utf-8-sig'); yaml.safe_load(s)" $Path 2>&1
      if($LASTEXITCODE -ne 0){ return (($out | Select-Object -First 1) -as [string]) }
      return $null
    }
    else{
      $raw = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
      if($raw -match "`t"){ return "YAML contains TAB characters (often invalid). Install PowerShell 7+ or PyYAML to fully parse." }
      return $null
    }
  } catch {
    return $_.Exception.Message
  }
}

function Verify-Files {
  param([string[]]$Paths)

  $rows = New-Object System.Collections.Generic.List[object]
  foreach($p in $Paths){
    if([string]::IsNullOrWhiteSpace($p)){ continue }
    if(-not (Test-Path -LiteralPath $p)){ continue }

    $f = Get-Item -LiteralPath $p -Force
    if($f.PSIsContainer){ continue }

    $ext = (($f.Extension ?? '')).ToLowerInvariant()
    $status = "PASSED"
    $why = ""

    try{
      switch($ext){
        ".json" {
          $raw = Get-Content -LiteralPath $p -Raw -ErrorAction Stop
          $null = $raw | ConvertFrom-Json -ErrorAction Stop
        }
        ".yaml" { $e = Test-YamlFile $p; if($e){ throw $e } }
        ".yml"  { $e = Test-YamlFile $p; if($e){ throw $e } }
        ".ps1" {
          $t=$null; $e=$null
          [void][System.Management.Automation.Language.Parser]::ParseFile($p,[ref]$t,[ref]$e)
          if($e -and $e.Count -gt 0){ throw $e[0].Message }
        }
        ".psm1" {
          $t=$null; $e=$null
          [void][System.Management.Automation.Language.Parser]::ParseFile($p,[ref]$t,[ref]$e)
          if($e -and $e.Count -gt 0){ throw $e[0].Message }
        }
        ".py" {
          if($Py){
            $out = & $Py -c "import sys,ast,tokenize; p=sys.argv[1]; ast.parse(tokenize.open(p).read(), filename=p)" $p 2>&1
            if($LASTEXITCODE -ne 0){ throw (($out | Select-Object -First 1) -as [string]) }
          } else {
            if(-not (Test-TextReadable $p)){ throw "Unreadable text file" }
          }
        }
        default {
          if(-not (Test-TextReadable $p)){ throw "Unreadable or binary (Get-Content failed)" }
        }
      }
    } catch {
      $status = "FAILED"
      $why = $_.Exception.Message
    }

    $rows.Add([pscustomobject]@{
      Path   = (Resolve-FullPath $p)
      Ext    = (if([string]::IsNullOrWhiteSpace($ext)){'(none)'}else{$ext})
      SizeKB = [math]::Round(($f.Length/1KB),2)
      Status = $status
      Why    = $why
    }) | Out-Null
  }

  return @($rows)
}

# -----------------------------
# Main
# -----------------------------
try {
  Start-Transcript -Path $LogPath -Force | Out-Null

  Write-Section "Self Evolve"
  Write-Host ("Mode   : {0}" -f $Mode)
  Write-Host ("Root   : {0}" -f (Resolve-FullPath $Root))
  Write-Host ("Log    : {0}" -f $LogPath)
  Write-Host ("CSV    : {0}" -f $CsvPath)
  Write-Host ("Report : {0}" -f $JsonPath)
  Write-Host ("Scopes : {0}" -f ($Scopes -join ', '))
  Write-Host ("Deletes: {0}" -f $AllowDeletes)
  Write-Host ("Force  : {0}" -f $Force)
  Write-Host ("WhatIf : {0}" -f $WhatIfPreference)

  if(-not (Test-Path -LiteralPath $Root)){
    throw "Root not found: $Root"
  }
  if(Test-DangerousPath $Root){
    throw "Refusing to operate on dangerous Root: $Root"
  }

  if($Mode -eq 'Status'){
    Write-Section "Status"
    if(Test-Path -LiteralPath $LatestPtr){
      $latest = (Get-Content -LiteralPath $LatestPtr -ErrorAction SilentlyContinue | Select-Object -First 1)
      if($latest){
        Write-Host ("Latest backup: {0}" -f $latest)
      } else {
        Write-Host "Latest backup: (none)"
      }
    } else {
      Write-Host "Latest backup: (none)"
    }

    $countBackups = 0
    if(Test-Path -LiteralPath $BkpRoot){
      $countBackups = (Get-ChildItem -LiteralPath $BkpRoot -Directory -Force -ErrorAction SilentlyContinue | Measure-Object).Count
    }
    Write-Host ("Backups available: {0}" -f $countBackups)

    Add-Action "Status" "." "OK" "Displayed status"
  }
  elseif($Mode -eq 'CleanTemp'){
    Write-Section "CleanTemp"
    if(Test-Path -LiteralPath $TempBase){
      if($PSCmdlet.ShouldProcess($TempBase, "Remove temp evolve folders")){
        Get-ChildItem -LiteralPath $TempBase -Directory -Force -ErrorAction SilentlyContinue |
          ForEach-Object {
            try {
              Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction Stop
              Add-Action "CleanTemp" (Split-Path -Leaf $_.FullName) "OK" ""
            } catch {
              Add-Action "CleanTemp" (Split-Path -Leaf $_.FullName) "FAILED" $_.Exception.Message
            }
          }
      } else {
        Add-Action "CleanTemp" $TempBase "WHATIF/SKIPPED" "Not approved"
      }
    } else {
      Add-Action "CleanTemp" $TempBase "SKIPPED" "Temp base not found"
    }
  }
  elseif($Mode -eq 'Rollback'){
    if([string]::IsNullOrWhiteSpace($BackupDir)){
      # try latest pointer
      if(Test-Path -LiteralPath $LatestPtr){
        $BackupDir = (Get-Content -LiteralPath $LatestPtr -ErrorAction SilentlyContinue | Select-Object -First 1)
      }
    }
    if([string]::IsNullOrWhiteSpace($BackupDir)){
      throw "BackupDir is required (or ensure latest_backup.txt exists)."
    }

    Rollback-FromBackup -Backup $BackupDir

    if($Verify){
      Write-Section "Verify after rollback (scopes)"
      $pathsToCheck = @()
      foreach($s in $Scopes){
        $p = Join-Path $Root $s
        if(Test-Path -LiteralPath $p){
          $pathsToCheck += (Get-ChildItem -LiteralPath $p -Recurse -File -Force -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
        }
      }
      $verifyRows = Verify-Files -Paths $pathsToCheck
      $verifyRows | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $CsvPath
      $failed = $verifyRows | Where-Object { $_.Status -eq 'FAILED' }
      if($failed -and $failed.Count -gt 0){
        Add-Action "Verify" "." "FAILED" ("{0} file(s) failed verification" -f $failed.Count)
      } else {
        Add-Action "Verify" "." "OK" "All checked files passed"
      }
    }
  }
  else {
    # Plan / Apply / Verify
    $srcDir = Resolve-SourceDir -Src $SourcePath
    Write-Host ("Source : {0}" -f (Resolve-FullPath $srcDir))

    $plan = Build-Plan -SourceDir $srcDir

    # output plan summary
    $counts = $plan | Group-Object Action | Sort-Object Count -Descending
    Write-Section "Plan summary"
    $counts | Format-Table -AutoSize Count,Name

    # write plan CSV
    $plan | Select-Object Action,RelPath,Dest,Source,SizeKB,SrcHash,DstHash |
      Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $CsvPath

    Add-Action "Plan" "." "OK" ("Wrote CSV plan: {0}" -f $CsvPath)

    if($Mode -eq 'Plan'){
      # no changes
    }
    elseif($Mode -eq 'Verify'){
      Write-Section "Verify (source scope files compared)"
      $paths = @()
      foreach($i in $plan){
        # verify destination if it exists, otherwise verify source (for creates)
        if($i.Action -eq 'DELETE'){ continue }
        $d = [string]$i.Dest
        if(Test-Path -LiteralPath $d){ $paths += $d }
        elseif(-not [string]::IsNullOrWhiteSpace([string]$i.Source)){ $paths += [string]$i.Source }
      }

      $verifyRows = Verify-Files -Paths ($paths | Select-Object -Unique)
      $verifyRows | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $CsvPath
      $failed = $verifyRows | Where-Object { $_.Status -eq 'FAILED' }
      if($failed -and $failed.Count -gt 0){
        Add-Action "Verify" "." "FAILED" ("{0} file(s) failed verification" -f $failed.Count)
      } else {
        Add-Action "Verify" "." "OK" "All checked files passed"
      }
    }
    elseif($Mode -eq 'Apply'){
      # Apply changes
      $backupDir = Apply-Plan -Plan $plan -SourceDir $srcDir
      Add-Action "Apply" "." "OK" ("BackupDir={0}" -f (Resolve-FullPath $backupDir))

      # Verify changed files only
      if($Verify){
        Write-Section "Verify changed files"
        $paths = @()
        foreach($i in $plan){
          if($i.Action -in @('CREATE','UPDATE')){
            $d = [string]$i.Dest
            if(Test-Path -LiteralPath $d){ $paths += $d }
          }
        }

        $verifyRows = Verify-Files -Paths ($paths | Select-Object -Unique)
        $verifyCsv = Join-Path $Ops ("self_evolve_verify_{0}.csv" -f $Now)
        $verifyRows | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $verifyCsv

        $failed = $verifyRows | Where-Object { $_.Status -eq 'FAILED' }
        if($failed -and $failed.Count -gt 0){
          Add-Action "Verify" "." "FAILED" ("{0} file(s) failed verification (see {1})" -f $failed.Count,$verifyCsv)
        } else {
          Add-Action "Verify" "." "OK" ("All checked files passed (see {0})" -f $verifyCsv)
        }
      }

      # Optional: run full sanity script if present
      if($RunFullSanityScript){
        $sanityScript = Join-Path $Root 'scripts\credential-delegate.ps1'
        if(Test-Path -LiteralPath $sanityScript){
          Write-Section "Run Full Sanity Script"
          if($PSCmdlet.ShouldProcess($sanityScript, "Execute credential-delegate.ps1")){
            try{
              & $sanityScript
              Add-Action "SanityScript" "scripts\credential-delegate.ps1" "OK" "Executed"
            } catch {
              Add-Action "SanityScript" "scripts\credential-delegate.ps1" "FAILED" $_.Exception.Message
            }
          } else {
            Add-Action "SanityScript" "scripts\credential-delegate.ps1" "WHATIF/SKIPPED" "Not approved"
          }
        } else {
          Add-Action "SanityScript" "scripts\credential-delegate.ps1" "SKIPPED" "Not found"
        }
      }
    }
    else {
      throw "Unknown mode: $Mode"
    }
  }

  # -----------------------------
  # Write JSON report
  # -----------------------------
  Write-Section "Write report"
  $report = [pscustomobject]@{
    timestamp = $Now
    mode      = $Mode
    root      = (Resolve-FullPath $Root)
    source    = (if([string]::IsNullOrWhiteSpace($SourcePath)) { '' } else { $SourcePath })
    scopes    = @($Scopes)
    allowDeletes = [bool]$AllowDeletes
    force     = [bool]$Force
    whatIf    = [bool]$WhatIfPreference
    log       = $LogPath
    csv       = $CsvPath
    actions   = @($script:Actions)
  }

  if($PSCmdlet.ShouldProcess($JsonPath, "Write JSON report")){
    $report | ConvertTo-Json -Depth 6 | Out-File -LiteralPath $JsonPath -Encoding UTF8 -Force
    Add-Action "Report" "." "OK" (Resolve-FullPath $JsonPath)
  } else {
    Add-Action "Report" "." "WHATIF/SKIPPED" (Resolve-FullPath $JsonPath)
  }

  Write-Section "Summary"
  $script:Actions | Format-Table -AutoSize Time,Action,Path,Result,Notes

  Write-Host ""
  Write-Host ("Saved log   : {0}" -f $LogPath)
  Write-Host ("Saved CSV   : {0}" -f $CsvPath)
  Write-Host ("Saved report: {0}" -f $JsonPath)

  # Exit non-zero if FAILED/BLOCKED
  $bad = $script:Actions | Where-Object { $_.Result -in @('FAILED','BLOCKED') }
  if($bad -and $bad.Count -gt 0){ exit 1 } else { exit 0 }

} catch {
  Write-Host ""
  Write-Host ("ERROR: {0}" -f $_.Exception.Message) -ForegroundColor Red
  throw
} finally {
  # Cleanup temp extraction (only if we created it)
  if($script:TempDir -and (Test-Path -LiteralPath $script:TempDir)){
    try{
      Remove-Item -LiteralPath $script:TempDir -Recurse -Force -ErrorAction SilentlyContinue
      Add-Action "Temp" $script:TempDir "OK" "Cleaned"
    } catch {}
  }
  try { Stop-Transcript | Out-Null } catch {}
}
