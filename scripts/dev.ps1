$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$venvDir = Join-Path $repoRoot ".venv"
$venvPy = Join-Path $venvDir "Scripts\\python.exe"

function Test-VenvPython([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) { return $false }
  & $Path --version *> $null
  return ($LASTEXITCODE -eq 0)
}

if (-not (Test-VenvPython $venvPy)) {
  if (Test-Path -LiteralPath $venvDir) {
    Remove-Item -LiteralPath $venvDir -Recurse -Force -ErrorAction SilentlyContinue
  }

  python -m venv $venvDir
  $venvPy = Join-Path $venvDir "Scripts\\python.exe"
}

& $venvPy -m pip install --upgrade pip setuptools wheel
& $venvPy -m pip install -r (Join-Path $repoRoot "requirements\\dev.txt")

Start-Process powershell -ArgumentList '-NoExit','-Command','& .\scripts\francis.ps1 api'
Start-Process powershell -ArgumentList '-NoExit','-Command','& .\scripts\francis.ps1 daemon'
Start-Process powershell -ArgumentList '-NoExit','-Command','cd apps\chat_ui; npm install; npm run dev'
