# Export pinned requirements from uv.lock (optional helper).
#
# This does not replace the editable "install profile" files under requirements/.
# Instead, it writes pinned, non-editable dependency sets under requirements/locked/.

[CmdletBinding()]
param()

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

function Resolve-Uv {
  $cmd = Get-Command uv -ErrorAction SilentlyContinue
  if($cmd){ return $cmd.Source }

  $venvUv = Join-Path $repoRoot ".venv\\Scripts\\uv.exe"
  if(Test-Path -LiteralPath $venvUv){ return $venvUv }

  return $null
}

$uv = Resolve-Uv
if(-not $uv){
  throw "uv not found. Install it (recommended) or add it to .venv: `python -m pip install uv`."
}

$lock = Join-Path $repoRoot "uv.lock"
if(-not (Test-Path -LiteralPath $lock)){
  throw "uv.lock not found. Run: uv lock"
}
if((Get-Item -LiteralPath $lock).Length -le 0){
  throw "uv.lock is empty. Run: uv lock"
}

$outDir = Join-Path $repoRoot "requirements\\locked"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "Exporting pinned requirements from uv.lock -> $outDir"

& $uv export --format requirements.txt --extra core --no-emit-project --frozen --no-hashes --output-file (Join-Path $outDir "core.txt")
if($LASTEXITCODE -ne 0){ throw "uv export failed (core)" }

& $uv export --format requirements.txt --extra core --extra web --extra dev --no-emit-project --frozen --no-hashes --output-file (Join-Path $outDir "dev.txt")
if($LASTEXITCODE -ne 0){ throw "uv export failed (dev)" }

& $uv export --format requirements.txt --all-extras --no-emit-project --frozen --no-hashes --output-file (Join-Path $outDir "all-extras.txt")
if($LASTEXITCODE -ne 0){ throw "uv export failed (all-extras)" }

Write-Host "Done."
