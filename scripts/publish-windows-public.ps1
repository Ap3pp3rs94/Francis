param(
    [string]$EnvFilePath = (Join-Path $PSScriptRoot "signing-public.local.ps1")
)

$ErrorActionPreference = "Stop"

if (Test-Path $EnvFilePath) {
    Write-Host ("[francis-overlay] Loading public signing env from " + $EnvFilePath)
    . $EnvFilePath
} else {
    Write-Host ("[francis-overlay] No local public signing env file found at " + $EnvFilePath)
}

& npm run release:publish:windows:public
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
