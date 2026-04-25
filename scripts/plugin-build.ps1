<#
D:\francis\scripts\plugin-build.ps1

Generic “plugin build” runner for a Node-based plugin project (optionally validates ai-plugin.json + OpenAPI YAML/JSON).
Creates logs + a build report + a zipped artifact.

Defaults:
  Root        : D:\francis
  ProjectPath : D:\francis\plugin
  Output      : D:\francis\data\artifacts\plugins

Examples:
  pwsh -File .\plugin-build.ps1
  pwsh -File .\plugin-build.ps1 -ProjectPath D:\francis\plugins\my-plugin -All
  pwsh -File .\plugin-build.ps1 -Clean -Install -Build -Pack
  pwsh -File .\plugin-build.ps1 -Mode Build
  pwsh -File .\plugin-build.ps1 -Mode Pack -SkipValidate
  pwsh -File .\plugin-build.ps1 -WhatIf

Notes:
  - Uses pnpm if pnpm-lock.yaml exists and pnpm is installed; else yarn if yarn.lock exists and yarn is installed; else npm.
  - Will try common build output folders: dist, build, out, .next, .output
  - Validates:
      - ai-plugin.json (if found) as JSON
      - openapi.yaml/yml (if found) as YAML (PS ConvertFrom-Yaml or Python+PyYAML if available; else minimal TAB check)
      - openapi.json / swagger.json as JSON

Hardening in this version:
  - Fixes PackAllFiles wildcard parse bug
  - Adds secret-safe excludes for PackAllFiles (.env, keys, pem/pfx, etc.)
  - Writes a CSV step report in logs\operations
  - Writes SHA256 for the zip artifact
#>

[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='Medium')]
param(
  [ValidateSet('All','Clean','Install','Lint','Test','Build','Pack')]
  [string]$Mode = 'All',

  [string]$Root = 'D:\francis',
  [string]$ProjectPath = '',
  [string]$OutputDir = '',

  [switch]$Clean,
  [switch]$Install,
  [switch]$Lint,
  [switch]$Test,
  [switch]$Build,
  [switch]$Pack,

  [switch]$SkipValidate,
  [switch]$PackAllFiles,

  # If set, delete the staging directory after zipping (default is to keep it for inspection)
  [switch]$CleanupStage,

  # Optional: override which package manager to use
  [ValidateSet('auto','npm','yarn','pnpm')]
  [string]$PackageManager = 'auto'
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

# -----------------------------
# Helpers / logging
# -----------------------------
$Now = Get-Date -Format "yyyyMMdd_HHmmss"

if([string]::IsNullOrWhiteSpace($ProjectPath)){
  $ProjectPath = Join-Path $Root 'plugin'
}
if([string]::IsNullOrWhiteSpace($OutputDir)){
  $OutputDir = Join-Path $Root 'data\artifacts\plugins'
}

$LogDir = Join-Path $Root 'data\logs\operations'
New-Item -ItemType Directory -Force -Path $LogDir   | Out-Null
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$TranscriptPath = Join-Path $LogDir ("plugin_build_{0}.log" -f $Now)
$CsvStepsPath   = Join-Path $LogDir ("plugin_build_{0}.csv" -f $Now)
$ReportPath     = Join-Path $OutputDir ("plugin_build_report_{0}.json" -f $Now)

$script:Steps = New-Object System.Collections.Generic.List[object]

function Write-Section([string]$Title){
  Write-Host ""
  Write-Host ("=" * 72)
  Write-Host $Title
  Write-Host ("=" * 72)
}

function Add-Step {
  param(
    [string]$Step,
    [string]$Status,
    [string]$Details = ""
  )
  $script:Steps.Add([pscustomobject]@{
    Time    = (Get-Date).ToString("s")
    Step    = $Step
    Status  = $Status
    Details = $Details
  }) | Out-Null
}

function Resolve-FullPath([string]$Path){
  try {
    return (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
  } catch {
    try { return [System.IO.Path]::GetFullPath($Path) } catch { return $Path }
  }
}

function Invoke-Tool {
  param(
    [Parameter(Mandatory=$true)][string]$Exe,
    [Parameter(Mandatory=$true)][string[]]$Args,
    [Parameter(Mandatory=$true)][string]$Cwd,
    [string]$StepName = "Run"
  )

  $cmdLine = $Exe + " " + ($Args -join " ")
  Write-Host ("`n> {0}" -f $cmdLine)

  if(-not (Test-Path -LiteralPath $Cwd)){
    Add-Step $StepName "FAILED" "Working directory not found: $Cwd"
    throw "Working directory not found: $Cwd"
  }

  if($PSCmdlet.ShouldProcess($Cwd, $cmdLine)){
    $old = Get-Location
    try {
      Set-Location -LiteralPath $Cwd
      $out = & $Exe @Args 2>&1
      $code = $LASTEXITCODE
      if($out){ $out | ForEach-Object { Write-Host $_ } }
      if($code -ne 0){
        Add-Step $StepName "FAILED" "ExitCode=$code"
        throw "$StepName failed with ExitCode=$code"
      } else {
        Add-Step $StepName "OK" $cmdLine
      }
      return $out
    } finally {
      Set-Location $old
    }
  } else {
    Add-Step $StepName "WHATIF/SKIPPED" $cmdLine
  }
}

# YAML parser capability detection
$Py = $null
try { $Py = (Get-Command python -ErrorAction SilentlyContinue).Source } catch {}
$HasCfy = $false
try { if(Get-Command ConvertFrom-Yaml -ErrorAction SilentlyContinue){ $HasCfy = $true } } catch {}
$HasPyYaml = $false
if($Py){
  try {
    & $Py -c "import yaml" 2>$null
    $HasPyYaml = ($LASTEXITCODE -eq 0)
  } catch {}
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

function Find-FirstExistingFile {
  param(
    [Parameter(Mandatory=$true)][string]$Base,
    [Parameter(Mandatory=$true)][string[]]$Candidates
  )
  foreach($c in $Candidates){
    $p = Join-Path $Base $c
    if(Test-Path -LiteralPath $p){ return $p }
  }
  return $null
}

function Find-FirstExistingDir {
  param(
    [Parameter(Mandatory=$true)][string]$Base,
    [Parameter(Mandatory=$true)][string[]]$Candidates
  )
  foreach($c in $Candidates){
    $p = Join-Path $Base $c
    if(Test-Path -LiteralPath $p){ return $p }
  }
  return $null
}

function Get-PackageManager {
  param([string]$Project)

  if($PackageManager -ne 'auto'){
    return $PackageManager
  }

  $hasPnpmLock = Test-Path -LiteralPath (Join-Path $Project 'pnpm-lock.yaml')
  $hasYarnLock = Test-Path -LiteralPath (Join-Path $Project 'yarn.lock')

  $pnpm = $null; $yarn = $null; $npm = $null
  try { $pnpm = (Get-Command pnpm -ErrorAction SilentlyContinue).Source } catch {}
  try { $yarn = (Get-Command yarn -ErrorAction SilentlyContinue).Source } catch {}
  try { $npm  = (Get-Command npm  -ErrorAction SilentlyContinue).Source } catch {}

  if($hasPnpmLock -and $pnpm){ return 'pnpm' }
  if($hasYarnLock -and $yarn){ return 'yarn' }
  if($npm){ return 'npm' }

  throw "No package manager found (need npm, or yarn/pnpm)."
}

function Read-PackageJson {
  param([string]$Project)
  $pkgPath = Join-Path $Project 'package.json'
  if(-not (Test-Path -LiteralPath $pkgPath)){
    throw "package.json not found in: $Project"
  }
  $raw = Get-Content -LiteralPath $pkgPath -Raw -ErrorAction Stop
  return ($raw | ConvertFrom-Json -ErrorAction Stop)
}

function Has-NpmScript {
  param($PkgObj, [string]$Name)
  try {
    return ($null -ne $PkgObj.scripts) -and ($null -ne $PkgObj.scripts.$Name)
  } catch { return $false }
}

function Run-ScriptIfExists {
  param(
    [string]$Pm,
    [string]$Project,
    $PkgObj,
    [string]$ScriptName,
    [string]$StepName
  )

  if(-not (Has-NpmScript $PkgObj $ScriptName)){
    Add-Step $StepName "SKIPPED" "No script '$ScriptName' in package.json"
    return
  }

  switch($Pm){
    'pnpm' { Invoke-Tool -Exe 'pnpm' -Args @('run',$ScriptName) -Cwd $Project -StepName $StepName | Out-Null }
    'yarn' { Invoke-Tool -Exe 'yarn' -Args @($ScriptName)        -Cwd $Project -StepName $StepName | Out-Null }
    default{ Invoke-Tool -Exe 'npm'  -Args @('run',$ScriptName)   -Cwd $Project -StepName $StepName | Out-Null }
  }
}

function Remove-DirIfExists {
  param([string]$Path,[string]$Label)
  if(Test-Path -LiteralPath $Path){
    if($PSCmdlet.ShouldProcess($Path, "Remove $Label")){
      try{
        Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
        Add-Step "Clean:$Label" "OK" $Path
      } catch {
        Add-Step "Clean:$Label" "FAILED" $_.Exception.Message
        throw
      }
    } else {
      Add-Step "Clean:$Label" "WHATIF/SKIPPED" $Path
    }
  } else {
    Add-Step "Clean:$Label" "SKIPPED" "Not found: $Path"
  }
}

function Validate-PluginFiles {
  param([string]$Project)

  Write-Section "Validate plugin files (ai-plugin.json / OpenAPI)"

  $aiPlugin = Find-FirstExistingFile -Base $Project -Candidates @(
    '.well-known\ai-plugin.json',
    'ai-plugin.json'
  )

  if($aiPlugin){
    try{
      $raw = Get-Content -LiteralPath $aiPlugin -Raw -ErrorAction Stop
      $null = $raw | ConvertFrom-Json -ErrorAction Stop
      Add-Step "Validate:ai-plugin.json" "OK" (Resolve-FullPath $aiPlugin)
    } catch {
      Add-Step "Validate:ai-plugin.json" "FAILED" $_.Exception.Message
      throw "ai-plugin.json invalid: $($_.Exception.Message)"
    }
  } else {
    Add-Step "Validate:ai-plugin.json" "SKIPPED" "Not found"
  }

  $openapiYaml = Find-FirstExistingFile -Base $Project -Candidates @(
    'openapi.yaml','openapi.yml','swagger.yaml','swagger.yml'
  )
  $openapiJson = Find-FirstExistingFile -Base $Project -Candidates @(
    'openapi.json','swagger.json'
  )

  if($openapiYaml){
    $e = Test-YamlFile $openapiYaml
    if($e){
      Add-Step "Validate:OpenAPI(YAML)" "FAILED" $e
      throw "OpenAPI YAML invalid: $e"
    } else {
      Add-Step "Validate:OpenAPI(YAML)" "OK" (Resolve-FullPath $openapiYaml)
    }
  } else {
    Add-Step "Validate:OpenAPI(YAML)" "SKIPPED" "Not found"
  }

  if($openapiJson){
    try{
      $raw = Get-Content -LiteralPath $openapiJson -Raw -ErrorAction Stop
      $null = $raw | ConvertFrom-Json -ErrorAction Stop
      Add-Step "Validate:OpenAPI(JSON)" "OK" (Resolve-FullPath $openapiJson)
    } catch {
      Add-Step "Validate:OpenAPI(JSON)" "FAILED" $_.Exception.Message
      throw "OpenAPI JSON invalid: $($_.Exception.Message)"
    }
  } else {
    Add-Step "Validate:OpenAPI(JSON)" "SKIPPED" "Not found"
  }
}

function Test-ExcludeRel {
  param([string]$Rel, [string[]]$Patterns)
  $r = ($Rel -replace '/', '\')
  foreach($pat in $Patterns){
    $p = ($pat -replace '/', '\')
    if($r -like $p){ return $true }
  }
  return $false
}

function Stage-And-Pack {
  param(
    [string]$Project,
    [string]$OutDir,
    $PkgObj
  )

  Write-Section "Stage + Pack artifact"

  $name = $null
  try { $name = [string]$PkgObj.name } catch {}
  if([string]::IsNullOrWhiteSpace($name)){
    $name = Split-Path -Leaf $Project
  }

  $safeName = ($name -replace '[^A-Za-z0-9\.\-_]+','_')
  $stageDir = Join-Path $OutDir ("stage_{0}_{1}" -f $safeName,$Now)

  if(Test-Path -LiteralPath $stageDir){
    Remove-DirIfExists -Path $stageDir -Label "StagingDir"
  }
  New-Item -ItemType Directory -Force -Path $stageDir | Out-Null

  # Determine build output directory
  $buildOut = Find-FirstExistingDir -Base $Project -Candidates @('dist','build','out','.next','.output')
  if($buildOut){
    $dest = Join-Path $stageDir (Split-Path -Leaf $buildOut)
    if($PSCmdlet.ShouldProcess($buildOut, "Copy build output -> staging")){
      Copy-Item -LiteralPath $buildOut -Destination $dest -Recurse -Force -ErrorAction Stop
      Add-Step "Stage:BuildOutput" "OK" (Resolve-FullPath $buildOut)
    } else {
      Add-Step "Stage:BuildOutput" "WHATIF/SKIPPED" (Resolve-FullPath $buildOut)
    }
  } else {
    Add-Step "Stage:BuildOutput" "WARN" "No build output folder found (dist/build/out/.next/.output)"
  }

  # Copy common plugin metadata/spec files
  $metaFiles = @(
    '.well-known\ai-plugin.json',
    'ai-plugin.json',
    'openapi.yaml','openapi.yml','swagger.yaml','swagger.yml',
    'openapi.json','swagger.json',
    'logo.png','logo.jpg','logo.jpeg','logo.svg',
    'README.md'
  )

  foreach($mf in $metaFiles){
    $src = Join-Path $Project $mf
    if(Test-Path -LiteralPath $src){
      $relParent = Split-Path $mf -Parent
      $destDir = $stageDir
      if(-not [string]::IsNullOrWhiteSpace($relParent)){
        $destDir = Join-Path $stageDir $relParent
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
      }
      if($PSCmdlet.ShouldProcess($src, "Copy metadata -> staging")){
        Copy-Item -LiteralPath $src -Destination $destDir -Force -ErrorAction Stop
        Add-Step "Stage:Meta" "OK" $mf
      } else {
        Add-Step "Stage:Meta" "WHATIF/SKIPPED" $mf
      }
    }
  }

  # Optional: pack entire repo (with better exclusions)
  if($PackAllFiles){
    Write-Host "`nPackAllFiles enabled: staging repo files (exclusions applied)"

    $excludeRel = @(
      'node_modules\*',
      '.git\*',
      '.github\*',
      '.next\*',
      '.output\*',
      'coverage\*',
      'dist\cache\*',
      'build\cache\*',
      '*.log',
      '*.tmp',
      '*.bak',
      '.env',
      '.env.*',
      '*.pem',
      '*.key',
      '*.pfx',
      'id_rsa*',
      '*secret*',
      '*secrets*'
    )

    $projFull = (Resolve-FullPath $Project).TrimEnd('\')

    $all = Get-ChildItem -LiteralPath $Project -Recurse -File -Force -ErrorAction SilentlyContinue |
      Where-Object {
        $full = $_.FullName
        $rel = $full.Substring($projFull.Length).TrimStart('\')
        if(Test-ExcludeRel -Rel $rel -Patterns $excludeRel){ return $false }
        return $true
      }

    foreach($f in $all){
      $rel = $f.FullName.Substring($projFull.Length).TrimStart('\')
      $destFile = Join-Path $stageDir $rel
      $destFolder = Split-Path $destFile -Parent
      New-Item -ItemType Directory -Force -Path $destFolder | Out-Null
      if($PSCmdlet.ShouldProcess($f.FullName, "Copy repo file -> staging")){
        Copy-Item -LiteralPath $f.FullName -Destination $destFile -Force -ErrorAction SilentlyContinue
      }
    }

    Add-Step "Stage:RepoFiles" "OK" "Repo files staged (exclusions applied)"
  }

  # Create zip
  $zipPath = Join-Path $OutDir ("{0}_{1}.zip" -f $safeName,$Now)
  $shaPath = $zipPath + ".sha256"

  if($PSCmdlet.ShouldProcess($zipPath, "Compress-Archive from staging")){
    try{
      if(Test-Path -LiteralPath $zipPath){ Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue }
      Compress-Archive -Path (Join-Path $stageDir '*') -DestinationPath $zipPath -Force
      Add-Step "Pack:Zip" "OK" (Resolve-FullPath $zipPath)

      $h = Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath
      "{0} *{1}" -f $h.Hash.ToLowerInvariant(), (Split-Path -Leaf $zipPath) | Out-File -LiteralPath $shaPath -Encoding ASCII
      Add-Step "Pack:SHA256" "OK" (Resolve-FullPath $shaPath)

    } catch {
      Add-Step "Pack:Zip" "FAILED" $_.Exception.Message
      throw
    }
  } else {
    Add-Step "Pack:Zip" "WHATIF/SKIPPED" (Resolve-FullPath $zipPath)
  }

  Add-Step "Stage:Dir" "OK" (Resolve-FullPath $stageDir)

  if($CleanupStage){
    if($PSCmdlet.ShouldProcess($stageDir, "Remove staging directory")){
      try{
        Remove-Item -LiteralPath $stageDir -Recurse -Force -ErrorAction Stop
        Add-Step "Stage:Cleanup" "OK" "Staging directory removed"
      } catch {
        Add-Step "Stage:Cleanup" "FAILED" $_.Exception.Message
        throw
      }
    } else {
      Add-Step "Stage:Cleanup" "WHATIF/SKIPPED" "Not approved"
    }
  }
}

# -----------------------------
# Decide what to run
# -----------------------------
if($Mode -ne 'All'){
  $Clean   = $false; $Install = $false; $Lint = $false; $Test = $false; $Build = $false; $Pack = $false
  switch($Mode){
    'Clean'   { $Clean   = $true }
    'Install' { $Install = $true }
    'Lint'    { $Lint    = $true }
    'Test'    { $Test    = $true }
    'Build'   { $Build   = $true }
    'Pack'    { $Pack    = $true }
    default   { }
  }
} else {
  $any = $Clean -or $Install -or $Lint -or $Test -or $Build -or $Pack
  if(-not $any){
    $Clean = $true; $Install = $true; $Lint = $true; $Test = $true; $Build = $true; $Pack = $true
  }
}

# -----------------------------
# Main
# -----------------------------
try{
  Start-Transcript -Path $TranscriptPath -Force | Out-Null

  Write-Section "Plugin Build"
  Write-Host ("Root        : {0}" -f (Resolve-FullPath $Root))
  Write-Host ("ProjectPath : {0}" -f (Resolve-FullPath $ProjectPath))
  Write-Host ("OutputDir   : {0}" -f (Resolve-FullPath $OutputDir))
  Write-Host ("Mode        : {0}" -f $Mode)
  Write-Host ("WhatIf      : {0}" -f $WhatIfPreference)
  Write-Host ("Transcript  : {0}" -f $TranscriptPath)

  if(-not (Test-Path -LiteralPath $ProjectPath)){
    Add-Step "Guard:ProjectPath" "FAILED" "Not found: $ProjectPath"
    throw "ProjectPath not found: $ProjectPath"
  }

  $node = $null
  try { $node = (Get-Command node -ErrorAction SilentlyContinue).Source } catch {}
  if(-not $node){
    Add-Step "Guard:node" "FAILED" "node not found in PATH"
    throw "node not found in PATH"
  }
  Add-Step "Guard:node" "OK" $node

  $pm = Get-PackageManager -Project $ProjectPath
  Add-Step "Detect:PackageManager" "OK" $pm

  $pkg = Read-PackageJson -Project $ProjectPath
  $pkgName = $null
  try { $pkgName = [string]$pkg.name } catch {}
  Add-Step "Read:package.json" "OK" ("name={0}" -f $pkgName)

  if(-not $SkipValidate){
    Validate-PluginFiles -Project $ProjectPath
  } else {
    Add-Step "Validate" "SKIPPED" "SkipValidate set"
  }

  if($Clean){
    Write-Section "Clean"
    Remove-DirIfExists -Path (Join-Path $ProjectPath 'dist')      -Label "dist"
    Remove-DirIfExists -Path (Join-Path $ProjectPath 'build')     -Label "build"
    Remove-DirIfExists -Path (Join-Path $ProjectPath 'out')       -Label "out"
    Remove-DirIfExists -Path (Join-Path $ProjectPath '.next')     -Label ".next"
    Remove-DirIfExists -Path (Join-Path $ProjectPath '.output')   -Label ".output"
    Remove-DirIfExists -Path (Join-Path $ProjectPath 'coverage')  -Label "coverage"
  }

  if($Install){
    Write-Section "Install dependencies"
    switch($pm){
      'pnpm' {
        $pnpmLock = Join-Path $ProjectPath 'pnpm-lock.yaml'
        if(Test-Path -LiteralPath $pnpmLock){
          Invoke-Tool -Exe 'pnpm' -Args @('install','--frozen-lockfile') -Cwd $ProjectPath -StepName "Install:pnpm" | Out-Null
        } else {
          Invoke-Tool -Exe 'pnpm' -Args @('install') -Cwd $ProjectPath -StepName "Install:pnpm" | Out-Null
        }
      }
      'yarn' {
        $yarnLock = Join-Path $ProjectPath 'yarn.lock'
        $yarnVer = $null
        try { $yarnVer = (& yarn --version 2>$null | Select-Object -First 1) } catch {}
        if(Test-Path -LiteralPath $yarnLock){
          if($yarnVer -and $yarnVer.ToString().StartsWith("1.")){
            Invoke-Tool -Exe 'yarn' -Args @('install','--frozen-lockfile') -Cwd $ProjectPath -StepName "Install:yarn" | Out-Null
          } else {
            Invoke-Tool -Exe 'yarn' -Args @('install','--immutable') -Cwd $ProjectPath -StepName "Install:yarn" | Out-Null
          }
        } else {
          Invoke-Tool -Exe 'yarn' -Args @('install') -Cwd $ProjectPath -StepName "Install:yarn" | Out-Null
        }
      }
      default {
        $lock = Join-Path $ProjectPath 'package-lock.json'
        if(Test-Path -LiteralPath $lock){
          Invoke-Tool -Exe 'npm' -Args @('ci') -Cwd $ProjectPath -StepName "Install:npm ci" | Out-Null
        } else {
          Invoke-Tool -Exe 'npm' -Args @('install') -Cwd $ProjectPath -StepName "Install:npm install" | Out-Null
        }
      }
    }
  }

  if($Lint){
    Write-Section "Lint"
    Run-ScriptIfExists -Pm $pm -Project $ProjectPath -PkgObj $pkg -ScriptName 'lint' -StepName 'Lint'
  }

  if($Test){
    Write-Section "Test"
    Run-ScriptIfExists -Pm $pm -Project $ProjectPath -PkgObj $pkg -ScriptName 'test' -StepName 'Test'
  }

  if($Build){
    Write-Section "Build"
    if(Has-NpmScript $pkg 'build'){
      Run-ScriptIfExists -Pm $pm -Project $ProjectPath -PkgObj $pkg -ScriptName 'build' -StepName 'Build'
    } else {
      $tsc = $null
      try { $tsc = (Get-Command tsc -ErrorAction SilentlyContinue).Source } catch {}
      if($tsc){
        Invoke-Tool -Exe 'tsc' -Args @('-p','tsconfig.json') -Cwd $ProjectPath -StepName 'Build:tsc' | Out-Null
      } else {
        Add-Step "Build" "SKIPPED" "No build script and no tsc found"
      }
    }
  }

  if($Pack){
    Stage-And-Pack -Project $ProjectPath -OutDir $OutputDir -PkgObj $pkg
  }

  Write-Section "Write report"
  $report = [pscustomobject]@{
    Timestamp    = $Now
    Root         = (Resolve-FullPath $Root)
    ProjectPath  = (Resolve-FullPath $ProjectPath)
    OutputDir    = (Resolve-FullPath $OutputDir)
    Mode         = $Mode
    Actions      = @($script:Steps)
  }
  if($PSCmdlet.ShouldProcess($ReportPath, "Write JSON report")){
    $report | ConvertTo-Json -Depth 6 | Out-File -LiteralPath $ReportPath -Encoding UTF8
    Add-Step "Report:JSON" "OK" (Resolve-FullPath $ReportPath)
  } else {
    Add-Step "Report:JSON" "WHATIF/SKIPPED" (Resolve-FullPath $ReportPath)
  }

  # CSV steps report in operations log dir
  try{
    $script:Steps | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $CsvStepsPath
    Add-Step "Report:CSV" "OK" (Resolve-FullPath $CsvStepsPath)
  } catch {
    Add-Step "Report:CSV" "FAILED" $_.Exception.Message
  }

  Write-Section "Summary"
  $script:Steps | Format-Table -AutoSize Time,Step,Status,Details

  Write-Host ""
  Write-Host ("Transcript : {0}" -f $TranscriptPath)
  Write-Host ("Report JSON : {0}" -f $ReportPath)
  Write-Host ("Report CSV  : {0}" -f $CsvStepsPath)

} catch {
  Write-Host ""
  Write-Host ("ERROR: {0}" -f $_.Exception.Message) -ForegroundColor Red
  throw
} finally {
  try { Stop-Transcript | Out-Null } catch {}
}
