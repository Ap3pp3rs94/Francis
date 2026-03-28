param(
    [string]$EnvFilePath = ""
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

function Resolve-DotnetCommand {
    $command = Get-Command dotnet -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    foreach ($candidate in @(
        "C:\Program Files\dotnet\dotnet.exe",
        "C:\Program Files (x86)\dotnet\dotnet.exe"
    )) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return ""
}

if ($EnvFilePath -and (Test-Path $EnvFilePath)) {
    Write-Host ("[francis-overlay] Loading signing env from " + $EnvFilePath)
    . $EnvFilePath
}

$requiredEnv = @(
    "AZURE_SIGN_SIGNSDK_SIGNSTOOL",
    "AZURE_SIGN_DLIB_PATH",
    "AZURE_SIGN_METADATA_PATH"
)

foreach ($name in $requiredEnv) {
    if (-not (Test-ConfiguredValue (Get-Item -Path ("Env:" + $name) -ErrorAction SilentlyContinue).Value)) {
        Stop-WithMessage ("[francis-overlay] " + $name + " is required for the repo-owned Windows sign hook. Point it at the exact local tool or metadata path before retrying.")
    }
}

$signtoolPath = $env:AZURE_SIGN_SIGNSDK_SIGNSTOOL
$dlibPath = $env:AZURE_SIGN_DLIB_PATH
$metadataPath = $env:AZURE_SIGN_METADATA_PATH
$timestampUrl = if (Test-ConfiguredValue $env:AZURE_SIGN_TIMESTAMP_URL) { $env:AZURE_SIGN_TIMESTAMP_URL } else { "http://timestamp.acs.microsoft.com" }
$dotnet = Resolve-DotnetCommand

if (-not $dotnet) {
    Stop-WithMessage "[francis-overlay] dotnet.exe is required for Azure.CodeSigning.Dlib.dll. Install the .NET 8 x64 runtime or SDK and retry."
}

$runtimeFolders = @()
foreach ($runtimeRoot in @(
    "C:\Program Files\dotnet\shared\Microsoft.NETCore.App",
    "C:\Program Files (x86)\dotnet\shared\Microsoft.NETCore.App"
)) {
    if (Test-Path $runtimeRoot) {
        $runtimeFolders += Get-ChildItem -Path $runtimeRoot -Directory -ErrorAction SilentlyContinue
    }
}

if ($runtimeFolders.Count -eq 0) {
    Stop-WithMessage "[francis-overlay] Microsoft.NETCore.App runtime is not installed. Azure.CodeSigning.Dlib.runtimeconfig.json requires .NET 8 or newer."
}

$supportedRuntime = $false
foreach ($runtimeFolder in $runtimeFolders) {
    $version = $null
    if ([version]::TryParse($runtimeFolder.Name, [ref]$version) -and $version.Major -ge 8) {
        $supportedRuntime = $true
        break
    }
}

if (-not $supportedRuntime) {
    Stop-WithMessage "[francis-overlay] The installed Microsoft.NETCore.App runtime is older than 8. Install .NET 8 x64 or newer before retrying."
}

foreach ($entry in @(
    @{ Name = "signtool.exe"; Path = $signtoolPath },
    @{ Name = "Azure.CodeSigning.Dlib.dll"; Path = $dlibPath },
    @{ Name = "metadata.json"; Path = $metadataPath }
)) {
    if (-not (Test-Path $entry.Path)) {
        Stop-WithMessage ("[francis-overlay] " + $entry.Name + " was not found at " + $entry.Path + ". Install the Azure Artifact Signing client tools or fix the env path before retrying.")
    }
}

try {
    $metadata = Get-Content -Path $metadataPath -Raw | ConvertFrom-Json
} catch {
    Stop-WithMessage ("[francis-overlay] metadata.json at " + $metadataPath + " could not be parsed as JSON: " + $_.Exception.Message)
}

foreach ($field in @("Endpoint", "CodeSigningAccountName", "CertificateProfileName")) {
    $value = [string]$metadata.$field
    if ([string]::IsNullOrWhiteSpace($value)) {
        Stop-WithMessage ("[francis-overlay] metadata.json is missing " + $field + ". Populate the file with the Azure Artifact Signing account endpoint, account name, and certificate profile before retrying.")
    }
}

if ((Test-ConfiguredValue $env:FRANCIS_AZURE_TRUSTED_SIGNING_ENDPOINT) -and ($metadata.Endpoint -ne $env:FRANCIS_AZURE_TRUSTED_SIGNING_ENDPOINT)) {
    Stop-WithMessage ("[francis-overlay] metadata.json Endpoint does not match FRANCIS_AZURE_TRUSTED_SIGNING_ENDPOINT. Keep the repo preflight env and the direct signtool metadata aligned.")
}

if ((Test-ConfiguredValue $env:FRANCIS_AZURE_TRUSTED_SIGNING_ACCOUNT_NAME) -and ($metadata.CodeSigningAccountName -ne $env:FRANCIS_AZURE_TRUSTED_SIGNING_ACCOUNT_NAME)) {
    Stop-WithMessage ("[francis-overlay] metadata.json CodeSigningAccountName does not match FRANCIS_AZURE_TRUSTED_SIGNING_ACCOUNT_NAME.")
}

if ((Test-ConfiguredValue $env:FRANCIS_AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE_NAME) -and ($metadata.CertificateProfileName -ne $env:FRANCIS_AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE_NAME)) {
    Stop-WithMessage ("[francis-overlay] metadata.json CertificateProfileName does not match FRANCIS_AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE_NAME.")
}

$signtoolVersion = (Get-Item $signtoolPath).VersionInfo.FileVersion
$dlibVersion = (Get-Item $dlibPath).VersionInfo.FileVersion

Write-Host "[francis-overlay] Windows signing env verified"
Write-Host ("  signtool: " + $signtoolPath)
Write-Host ("  signtoolVersion: " + $signtoolVersion)
Write-Host ("  dlib: " + $dlibPath)
Write-Host ("  dlibVersion: " + $dlibVersion)
Write-Host ("  metadata: " + $metadataPath)
Write-Host ("  metadata.Endpoint: " + $metadata.Endpoint)
Write-Host ("  metadata.CodeSigningAccountName: " + $metadata.CodeSigningAccountName)
Write-Host ("  metadata.CertificateProfileName: " + $metadata.CertificateProfileName)
Write-Host ("  dotnet: " + $dotnet)
Write-Host ("  dotnetRuntimeRoot: " + (($runtimeFolders | Select-Object -First 1).Parent.FullName))
Write-Host ("  timestamp: " + $timestampUrl)
