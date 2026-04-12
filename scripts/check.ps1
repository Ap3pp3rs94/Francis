param(
    [string]$Root = ""
)

$ErrorActionPreference = "Stop"

if (-not $Root) {
    $Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

Push-Location $Root
try {
    $py = Join-Path $Root ".venv\\Scripts\\python.exe"
    if (-not (Test-Path $py)) {
        $py = "python"
    }

    function Invoke-Py {
        param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
        & $py @Args
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }

    Invoke-Py --version
    Invoke-Py -m ruff --version
    Invoke-Py -m mypy --version

    & (Join-Path $PSScriptRoot "check-branch-state.ps1") -Root $Root

    Invoke-Py -m ruff check .
    Invoke-Py -m ruff format --check .
    Invoke-Py -m mypy src
    Invoke-Py -m pytest -q
}
finally {
    Pop-Location
}
