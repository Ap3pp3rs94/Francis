# ==============================================================================
#  FRANCIS — scripts/bootstrap.ps1
#  Project bootstrapper: preflight, venv, deps, directories, config scaffolding,
#  and baseline sanity checks (safe-by-default).
# ==============================================================================
#  Design stance:
#   - Default conservative: do not overwrite existing secrets/state unless -Force
#   - Create missing folders/files from examples/templates when available
#   - Log everything to data/logs/operations (human + machine readable)
#   - Work on Windows PowerShell 5.1 and PowerShell 7+ (best effort)
# ==============================================================================

[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param(
  # Root of the FRANCIS repo (defaults to parent of this scripts folder)
  [Parameter(Mandatory = $false)]
  [string]$Root = "",

  # Environment profile (maps to config/environments/<env>.yaml)
  [Parameter(Mandatory = $false)]
  [ValidateSet('dev','workstation','home','production','regulated','airgapped','federated','edge','high_availability','safety_critical')]
  [string]$Environment = 'dev',

  # Preferred model provider (does not change credentials; only validates + hints)
  [Parameter(Mandatory = $false)]
  [ValidateSet('auto','openai','ollama','ollama_openai_compat')]
  [string]$Provider = 'auto',

  # Dependency installer for Python
  [Parameter(Mandatory = $false)]
  [ValidateSet('auto','uv','pip')]
  [string]$PythonInstaller = 'auto',

  # Include Chat UI dependency bootstrap (Node/npm). Off by default (heavy).
  [Parameter(Mandatory = $false)]
  [switch]$IncludeChatUI,

  # Skip Python virtualenv creation
  [Parameter(Mandatory = $false)]
  [switch]$SkipVenv,

  # Skip Python dependency installation
  [Parameter(Mandatory = $false)]
  [switch]$SkipPythonDeps,

  # Skip sanity checks at the end
  [Parameter(Mandatory = $false)]
  [switch]$SkipSanity,

  # Do not overwrite existing files; use -Force to overwrite safe scaffolds (never secrets)
  [Parameter(Mandatory = $false)]
  [switch]$Force
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

if(-not $Root){
  $Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $Root

# -----------------------------
# Helpers
# -----------------------------
function New-RunId { ([guid]::NewGuid().ToString('n')) }

function Ensure-Dir([string]$Path){
  if(-not (Test-Path -LiteralPath $Path)){
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
  }
}

function Format-Bytes([long]$b){
  if($b -lt 1KB){ "$b B" }
  elseif($b -lt 1MB){ "{0:N2} KB" -f ($b/1KB) }
  elseif($b -lt 1GB){ "{0:N2} MB" -f ($b/1MB) }
  else { "{0:N2} GB" -f ($b/1GB) }
}

function Read-Text([string]$Path){
  $sr = New-Object System.IO.StreamReader($Path, [Text.Encoding]::UTF8, $true)
  try { return $sr.ReadToEnd() } finally { $sr.Close() }
}

function Write-OpEvent([string]$Stage,[string]$Outcome,[string]$Message,[hashtable]$Data){
  $evt = @{
    ts      = (Get-Date).ToString('o')
    run_id  = $RunId
    stage   = $Stage
    outcome = $Outcome
    message = $Message
    data    = $Data
  }
  ($evt | ConvertTo-Json -Depth 8 -Compress) | Add-Content -LiteralPath $JsonlLog -Encoding UTF8
}

function Write-Log([string]$Level,[string]$Message){
  $ts = (Get-Date).ToString("s")
  $line = "[$ts][$Level] $Message"
  $line | Add-Content -LiteralPath $TextLog -Encoding UTF8
  Write-Host $line
}

function Step([string]$Name,[scriptblock]$Block){
  $t0 = Get-Date
  try {
    Write-Log "INFO" "==> $Name"
    Write-OpEvent -Stage $Name -Outcome "START" -Message "Starting" -Data @{}
    & $Block
    $dt = (New-TimeSpan -Start $t0 -End (Get-Date)).TotalSeconds
    $Summary.Add([pscustomobject]@{ Step=$Name; Result="OK"; Seconds=[math]::Round($dt,2); Notes="" }) | Out-Null
    Write-OpEvent -Stage $Name -Outcome "OK" -Message "Completed" -Data @{ seconds=$dt }
    Write-Log "INFO" "<== $Name (OK, $([math]::Round($dt,2))s)"
  } catch {
    $dt = (New-TimeSpan -Start $t0 -End (Get-Date)).TotalSeconds
    $msg = $_.Exception.Message
    $Summary.Add([pscustomobject]@{ Step=$Name; Result="FAIL"; Seconds=[math]::Round($dt,2); Notes=$msg }) | Out-Null
    Write-OpEvent -Stage $Name -Outcome "FAIL" -Message $msg -Data @{ seconds=$dt }
    Write-Log "ERROR" "<== $Name (FAIL): $msg"
    throw
  }
}

function Get-Exe([string]$Name){
  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  if($cmd){ return $cmd.Source }
  return $null
}

function Copy-IfMissingOrForce([string]$Src,[string]$Dst,[switch]$IsSecret){
  if(Test-Path -LiteralPath $Dst){
    if($Force -and -not $IsSecret){
      Copy-Item -LiteralPath $Src -Destination $Dst -Force
      return "OVERWROTE"
    }
    return "EXISTS"
  } else {
    Copy-Item -LiteralPath $Src -Destination $Dst -Force
    return "CREATED"
  }
}

function Assert-ProjectLayout([string]$RootPath){
  $must = @(
    (Join-Path $RootPath "pyproject.toml"),
    (Join-Path $RootPath "src"),
    (Join-Path $RootPath "config"),
    (Join-Path $RootPath "scripts")
  )
  $missing = @()
  foreach($p in $must){
    if(-not (Test-Path -LiteralPath $p)){ $missing += $p }
  }
  if($missing.Count -gt 0){
    throw "Not a FRANCIS repo root (missing: $($missing -join ', ')). Root='$RootPath'"
  }
}

# -----------------------------
# Start run + logging
# -----------------------------
$RunId   = New-RunId
$Summary = New-Object 'System.Collections.Generic.List[object]'

$OpsDir  = Join-Path $Root "data\logs\operations"
Ensure-Dir $OpsDir
$TextLog = Join-Path $OpsDir ("bootstrap_{0}.log" -f $RunId)
$JsonlLog= Join-Path $OpsDir ("bootstrap_{0}.jsonl" -f $RunId)

"FRANCIS bootstrap run_id=$RunId ts=$((Get-Date).ToString('o')) root=$Root env=$Environment provider=$Provider psver=$($PSVersionTable.PSVersion)" |
  Set-Content -LiteralPath $TextLog -Encoding UTF8
"" | Set-Content -LiteralPath $JsonlLog -Encoding UTF8

Write-Log "INFO" "Bootstrap starting (run_id=$RunId)"
Write-Log "INFO" "Root: $Root"
Write-Log "INFO" "Environment: $Environment"
Write-Log "INFO" "Provider: $Provider"
Write-Log "INFO" "PowerShell: $($PSVersionTable.PSVersion)"

# -----------------------------
# Bootstrap stages
# -----------------------------
Step "Preflight: verify repo layout" {
  Assert-ProjectLayout $Root
}

Step "Scaffold: ensure critical directories" {
  $dirs = @(
    (Join-Path $Root "data"),
    (Join-Path $Root "data\logs"),
    (Join-Path $Root "data\logs\operations"),
    (Join-Path $Root "data\conversations"),
    (Join-Path $Root "data\conversations\ledger"),
    (Join-Path $Root "data\conversations\summaries"),
    (Join-Path $Root "data\approvals"),
    (Join-Path $Root "data\credentials"),
    (Join-Path $Root "data\credentials\delegations"),
    (Join-Path $Root "data\credentials\scopes"),
    (Join-Path $Root "data\trust"),
    (Join-Path $Root "data\trust\levels"),
    (Join-Path $Root "data\trust\metrics"),
    (Join-Path $Root "data\web_knowledge"),
    (Join-Path $Root "data\web_knowledge\blocked")
  )
  foreach($d in $dirs){
    if($PSCmdlet.ShouldProcess($d, "Create directory if missing")){
      Ensure-Dir $d
    }
  }
}

Step "Scaffold: copy safe example files (non-secret only)" {
  $pairs = @()

  $envExample = Join-Path $Root ".env.example"
  $envDst     = Join-Path $Root ".env"
  if(Test-Path -LiteralPath $envExample){
    $pairs += @{ src=$envExample; dst=$envDst; secret=$false }
  }

  $secretsExample = Join-Path $Root "config\secrets.example.yaml"
  $secretsDst     = Join-Path $Root "config\secrets.yaml"
  # Treat secrets.yaml as secret: DO NOT overwrite, even with -Force
  if(Test-Path -LiteralPath $secretsExample){
    $pairs += @{ src=$secretsExample; dst=$secretsDst; secret=$true }
  }

  $dataReadme = Join-Path $Root "data\README.md"
  $dataReadmeSrc = Join-Path $Root "data\README.md"
  if(Test-Path -LiteralPath $dataReadmeSrc){
    # already exists in repo; do nothing
  }

  foreach($p in $pairs){
    $src=$p.src; $dst=$p.dst; $isSecret=[bool]$p.secret
    if($PSCmdlet.ShouldProcess($dst, "Copy from $src (secret=$isSecret)")){
      $r = Copy-IfMissingOrForce -Src $src -Dst $dst -IsSecret:([bool]$isSecret)
      Write-Log "INFO" "Scaffold: $r -> $dst"
      Write-OpEvent -Stage "ScaffoldCopy" -Outcome "OK" -Message "copy $r" -Data @{ src=$src; dst=$dst; secret=$isSecret }
    }
  }
}

Step "Config: environment file presence + selection" {
  $envFile = Join-Path $Root ("config\environments\{0}.yaml" -f $Environment)
  if(-not (Test-Path -LiteralPath $envFile)){
    throw "Missing environment config: $envFile"
  }
  Write-Log "INFO" "Environment config found: $envFile"
  Write-OpEvent -Stage "EnvConfig" -Outcome "OK" -Message "env config present" -Data @{ env=$Environment; path=$envFile }
}

Step "Preflight: toolchain detection (python/node/uv)" {
  $py   = Get-Exe "python"
  $uv   = Get-Exe "uv"
  $node = Get-Exe "node"
  $npm  = Get-Exe "npm"

  $toolData = @{
    python = $py
    uv     = $uv
    node   = $node
    npm    = $npm
  }
  Write-Log "INFO" ("python: {0}" -f ($(if($py){$py}else{"(not found)"})))
  Write-Log "INFO" ("uv:     {0}" -f ($(if($uv){$uv}else{"(not found)"})))
  Write-Log "INFO" ("node:   {0}" -f ($(if($node){$node}else{"(not found)"})))
  Write-Log "INFO" ("npm:    {0}" -f ($(if($npm){$npm}else{"(not found)"})))

  Write-OpEvent -Stage "Toolchain" -Outcome "OK" -Message "detected" -Data $toolData

  if(-not $py -and -not $SkipVenv){
    throw "python not found. Install Python 3.11+ and ensure it's on PATH."
  }
}

Step "Python: verify version (>= 3.11 recommended)" {
  if($SkipVenv -and $SkipPythonDeps){
    Write-Log "WARN" "Skipping Python version check (SkipVenv + SkipPythonDeps)"
    return
  }
  $py = Get-Exe "python"
  if(-not $py){ throw "python not found." }

  $ver = & $py -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null
  if(-not $ver){ throw "Unable to query python version." }

  $parts = $ver.Split('.')
  $maj=[int]$parts[0]; $min=[int]$parts[1]

  Write-Log "INFO" "Python version: $ver"
  if($maj -lt 3 -or ($maj -eq 3 -and $min -lt 11)){
    Write-Log "WARN" "Python < 3.11 detected. Recommended: 3.11+ (tomllib, modern tooling). Continuing anyway."
  }
}

Step "Python: create venv (.venv)" {
  if($SkipVenv){
    Write-Log "WARN" "SkipVenv set; not creating venv."
    return
  }

  $py = Get-Exe "python"
  $venvDir = Join-Path $Root ".venv"
  $venvPy  = Join-Path $venvDir "Scripts\python.exe"

  if(Test-Path -LiteralPath $venvPy){
    Write-Log "INFO" "Venv already present: $venvPy"
    return
  }

  if($PSCmdlet.ShouldProcess($venvDir, "Create python venv")){
    & $py -m venv $venvDir
    if(-not (Test-Path -LiteralPath $venvPy)){
      throw "Venv creation did not produce expected python.exe at $venvPy"
    }
    Write-Log "INFO" "Created venv: $venvPy"
  }
}

Step "Python: install dependencies (uv sync or pip)" {
  if($SkipPythonDeps){
    Write-Log "WARN" "SkipPythonDeps set; not installing python dependencies."
    return
  }

  $uv = Get-Exe "uv"
  $py = Get-Exe "python"

  $venvPy = Join-Path (Join-Path $Root ".venv") "Scripts\python.exe"
  if(Test-Path -LiteralPath $venvPy){ $py = $venvPy }

  if(-not $py){
    throw "python not found (and venv python missing)."
  }

  $use = $PythonInstaller
  if($use -eq 'auto'){
    if($uv){ $use = 'uv' } else { $use = 'pip' }
  }

  if($use -eq 'uv'){
    if(-not $uv){ throw "uv selected but not found on PATH." }
    $lock = Join-Path $Root "uv.lock"
    $lockInfo = Get-Item -LiteralPath $lock -ErrorAction SilentlyContinue
    if($lockInfo -and $lockInfo.Length -gt 0){
      if($PSCmdlet.ShouldProcess($Root, "uv sync --frozen (extras: core,web,dev)")){
        Push-Location $Root
        try {
          & $uv sync --frozen --extra core --extra web --extra dev
          if($LASTEXITCODE -ne 0){ throw "uv sync failed (exit=$LASTEXITCODE)" }
        } finally { Pop-Location }
      }
      Write-Log "INFO" "uv sync completed (frozen)"
    } else {
      Write-Log "WARN" "uv.lock missing or empty; falling back to pip requirements."
      $use = 'pip'
    }
  }

  if($use -eq 'pip'){
    $req = Join-Path $Root "requirements\dev.txt"
    if(-not (Test-Path -LiteralPath $req)){
      $req = Join-Path $Root "requirements\base.txt"
    }
    if(-not (Test-Path -LiteralPath $req)){
      throw "No requirements file found (requirements/dev.txt or requirements/base.txt)."
    }

    if($PSCmdlet.ShouldProcess($req, "pip install -r")){
      Push-Location $Root
      try {
        & $py -m pip install --upgrade pip setuptools wheel | Out-Host
        if($LASTEXITCODE -ne 0){ throw "pip upgrade failed (exit=$LASTEXITCODE)" }

        & $py -m pip install -r $req | Out-Host
        if($LASTEXITCODE -ne 0){ throw "pip install failed (exit=$LASTEXITCODE): $req" }
      } finally { Pop-Location }
    }
    Write-Log "INFO" "pip install completed ($req)"
  }
}

Step "Chat UI: npm install (optional)" {
  if(-not $IncludeChatUI){
    Write-Log "INFO" "Chat UI bootstrap skipped (IncludeChatUI not set)."
    return
  }

  $node = Get-Exe "node"
  $npm  = Get-Exe "npm"
  if(-not $node -or -not $npm){
    throw "IncludeChatUI requested but node/npm not found on PATH."
  }

  $ui = Join-Path $Root "apps\chat_ui"
  if(-not (Test-Path -LiteralPath $ui)){
    throw "Chat UI folder not found: $ui"
  }

  $pkgLock = Join-Path $ui "package-lock.json"
  $pkgJson = Join-Path $ui "package.json"
  if(-not (Test-Path -LiteralPath $pkgJson)){ throw "Missing: $pkgJson" }

  Push-Location $ui
  try{
    if(Test-Path -LiteralPath $pkgLock){
      if($PSCmdlet.ShouldProcess($ui, "npm ci")){
        & $npm ci | Out-Host
      }
      Write-Log "INFO" "npm ci completed"
    } else {
      if($PSCmdlet.ShouldProcess($ui, "npm install")){
        & $npm install | Out-Host
      }
      Write-Log "INFO" "npm install completed"
    }
  } finally { Pop-Location }
}

Step "Sanity: lightweight checks (import/parse) + inventory" {
  if($SkipSanity){
    Write-Log "WARN" "SkipSanity set; skipping checks."
    return
  }

  # 1) Quick inventory summary (counts)
  $files = Get-ChildItem -LiteralPath $Root -Recurse -File -Force -ErrorAction SilentlyContinue
  $count = ($files | Measure-Object).Count
  $empty = ($files | Where-Object { $_.Length -eq 0 } | Measure-Object).Count
  Write-Log "INFO" "Inventory: $count files total; $empty empty"

  # 2) Python import sanity (if available)
  $venvPy = Join-Path (Join-Path $Root ".venv") "Scripts\python.exe"
  $py = $null
  if(Test-Path -LiteralPath $venvPy){ $py = $venvPy } else { $py = Get-Exe "python" }

  if($py){
    $src = Join-Path $Root "src"
    if(Test-Path -LiteralPath $src){
      Write-Log "INFO" "Python: compileall src/ (syntax check)"
      & $py -m compileall -q $src
      Write-Log "INFO" "Python: compileall OK"
    }

    $testImports = Join-Path $Root "tests\unit\test_imports.py"
    if(Test-Path -LiteralPath $testImports){
      & $py -c "import pytest" *> $null
      if($LASTEXITCODE -eq 0){
        Write-Log "INFO" "Python: running pytest ($testImports)"
        & $py -m pytest -q $testImports | Out-Host
        Write-Log "INFO" "Python: pytest completed"
      } else {
        Write-Log "WARN" "pytest not installed; skipping import smoke tests"
      }
    }
  } else {
    Write-Log "WARN" "Python not found; skipping python sanity checks."
  }

  # 3) Config presence checks (no deep parse here; safe + fast)
  $critical = @(
    "config\profile.yaml",
    "config\policies\action_readiness.yaml",
    "config\policies\api_permissions.yaml",
    "config\policies\approvals.yaml",
    "config\policies\data_governance.yaml",
    "config\runtime\scheduler.yaml"
  ) | ForEach-Object { Join-Path $Root $_ }

  foreach($p in $critical){
    if(Test-Path -LiteralPath $p){
      $len = (Get-Item -LiteralPath $p).Length
      if($len -eq 0){
        Write-Log "WARN" "CRITICAL config is EMPTY: $p"
      } else {
        Write-Log "INFO" "CRITICAL config present: $p ($([math]::Round($len/1KB,2)) KB)"
      }
    } else {
      Write-Log "WARN" "CRITICAL config missing: $p"
    }
  }
}

# -----------------------------
# Finish + summary
# -----------------------------
Write-Log "INFO" ""
Write-Log "INFO" "Bootstrap summary:"
$Summary | Format-Table -AutoSize | Out-String | ForEach-Object { $_.TrimEnd() } | ForEach-Object { Write-Host $_ }

Write-Log "INFO" ""
Write-Log "INFO" "Logs:"
Write-Log "INFO" "  Text : $TextLog"
Write-Log "INFO" "  JSONL: $JsonlLog"

Write-Log "INFO" ""
Write-Log "INFO" "Next steps (common):"
Write-Log "INFO" "  - Run doctor:   .\scripts\doctor.ps1"
Write-Log "INFO" "  - Start API:    .\scripts\francis.ps1 api"
Write-Log "INFO" "  - Start daemon: .\scripts\francis.ps1 daemon"
Write-Log "INFO" "  - Chat UI dev:  cd apps\chat_ui; npm run dev"

Write-Log "INFO" "Bootstrap complete."
