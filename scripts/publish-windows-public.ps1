param(
    [string]$EnvFilePath = (Join-Path $PSScriptRoot "signing-public.local.ps1")
)

$ErrorActionPreference = "Stop"

function Test-ConfiguredValue {
    param(
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $false
    }

    return $Value -notmatch "<[^>]+>"
}

function Stop-WithMessage {
    param(
        [string]$Message
    )

    Write-Error $Message
    exit 1
}

$examplePath = Join-Path $PSScriptRoot "signing-public.example.ps1"

if (-not (Test-Path $EnvFilePath)) {
    Stop-WithMessage ("[francis-overlay] Missing local public signing env file at " + $EnvFilePath + ". Copy " + $examplePath + " to that path and fill the real publisher values before retrying.")
}

Write-Host ("[francis-overlay] Loading public signing env from " + $EnvFilePath)
. $EnvFilePath

if (-not (Test-ConfiguredValue $env:FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME)) {
    Stop-WithMessage ("[francis-overlay] FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME is still unset or placeholder in " + $EnvFilePath + ". Fill the real legal publisher name before retrying.")
}

if (-not (Test-ConfiguredValue $env:FRANCIS_WINDOWS_SIGNING_CHAIN_HINT)) {
    Stop-WithMessage ("[francis-overlay] FRANCIS_WINDOWS_SIGNING_CHAIN_HINT is still unset or placeholder in " + $EnvFilePath + ". Fill the expected public issuer or chain hint before retrying.")
}

$localPfxReady =
    ((Test-ConfiguredValue $env:WIN_CSC_LINK) -or (Test-ConfiguredValue $env:CSC_LINK)) -and
    ((Test-ConfiguredValue $env:WIN_CSC_KEY_PASSWORD) -or (Test-ConfiguredValue $env:CSC_KEY_PASSWORD))
$localStoreReady =
    (Test-ConfiguredValue $env:FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME) -or
    (Test-ConfiguredValue $env:FRANCIS_WINDOWS_SIGNING_SHA1)
$azureAuthReady =
    (Test-ConfiguredValue $env:AZURE_CLIENT_ID) -and
    (Test-ConfiguredValue $env:AZURE_TENANT_ID) -and
    (
        (Test-ConfiguredValue $env:AZURE_CLIENT_SECRET) -or
        (Test-ConfiguredValue $env:AZURE_CLIENT_CERTIFICATE_PATH) -or
        (
            (Test-ConfiguredValue $env:AZURE_USERNAME) -and
            (Test-ConfiguredValue $env:AZURE_PASSWORD)
        )
    )
$azureReady =
    (Test-ConfiguredValue $env:FRANCIS_AZURE_TRUSTED_SIGNING_ENDPOINT) -and
    (Test-ConfiguredValue $env:FRANCIS_AZURE_TRUSTED_SIGNING_ACCOUNT_NAME) -and
    (Test-ConfiguredValue $env:FRANCIS_AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE_NAME) -and
    $azureAuthReady

if (-not ($localPfxReady -or $localStoreReady -or $azureReady)) {
    Stop-WithMessage ("[francis-overlay] No complete public signing route is configured in " + $EnvFilePath + ". Fill either the cert-store, local PFX, or Azure Trusted Signing values before retrying.")
}

& npm run release:publish:windows:public
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
