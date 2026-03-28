param()

$ErrorActionPreference = "Stop"

function Invoke-NpmScript {
    param(
        [Parameter(Mandatory)]
        [string]$ScriptName
    )

    & npm run $ScriptName
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Invoke-NpmScript -ScriptName "overlay:signing-doctor:public"
Invoke-NpmScript -ScriptName "overlay:verify-windows-signing-env"
Invoke-NpmScript -ScriptName "release:hardening"
Invoke-NpmScript -ScriptName "overlay:dist:public"
