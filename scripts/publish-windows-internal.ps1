param(
    [string]$SourceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")),
    [string]$InternalOutputRoot = (Join-Path (Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")) "dist") "internal-beta\\windows\\current")
)

$ErrorActionPreference = "Stop"

function Write-Section {
    param(
        [string]$Message
    )

    Write-Host ("[francis-overlay] " + $Message)
}

function Stop-WithMessage {
    param(
        [string]$Message
    )

    Write-Error $Message
    exit 1
}

function Test-ConfiguredValue {
    param(
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $false
    }

    return $Value -notmatch "<[^>]+>"
}

function Invoke-NpmCommand {
    param(
        [string[]]$Arguments
    )

    & npm @Arguments
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

function Resolve-CertificateExportPath {
    param(
        [pscustomobject]$BundleManifest
    )

    if (-not $BundleManifest.exportedSignerCertificate) {
        return $null
    }

    return [string]$BundleManifest.exportedSignerCertificate.targetPath
}

function Resolve-MachineLocalSigningRoute {
    $doctorJson = & node electron/signing-doctor.js
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $doctorReport = $doctorJson | ConvertFrom-Json
    if (-not $doctorReport.suggestedPowerShell.machineLocalSignedBuild.available) {
        Stop-WithMessage "[francis-overlay] No machine-local signing route is available for the internal beta lane."
    }

    return $doctorReport
}

function Get-CertificateByThumbprint {
    param(
        [string]$Thumbprint
    )

    if (-not (Test-ConfiguredValue $Thumbprint)) {
        return $null
    }

    $normalizedThumbprint = ($Thumbprint -replace '\s+', '').ToUpperInvariant()
    $storePaths = @(
        "Cert:\CurrentUser\My\$normalizedThumbprint",
        "Cert:\LocalMachine\My\$normalizedThumbprint",
        "Cert:\CurrentUser\Root\$normalizedThumbprint",
        "Cert:\LocalMachine\Root\$normalizedThumbprint"
    )
    $matched = @()
    foreach ($storePath in $storePaths) {
        if (-not (Test-Path $storePath)) {
            continue
        }
        $cert = Get-Item $storePath -ErrorAction SilentlyContinue
        if ($null -ne $cert) {
            $matched += $cert
        }
    }

    if ($matched.Count -gt 1) {
        Stop-WithMessage "[francis-overlay] Multiple local certificates matched the selected internal beta thumbprint."
    }

    if ($matched.Count -eq 1) {
        return $matched[0]
    }

    return $null
}

Write-Host ""
Write-Host "FRANCIS OVERLAY INTERNAL BETA / QA / TESTER ONLY"
Write-Host "This lane is for approved private distribution. It is not a public-trust release."
Write-Host ""

$localPfxReady =
    ((Test-ConfiguredValue $env:WIN_CSC_LINK) -or (Test-ConfiguredValue $env:CSC_LINK)) -and
    ((Test-ConfiguredValue $env:WIN_CSC_KEY_PASSWORD) -or (Test-ConfiguredValue $env:CSC_KEY_PASSWORD))
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

$selectedCert = $null

if ($azureReady) {
    Write-Section "Using configured Azure signing route for an internal beta build."
} elseif ($localPfxReady) {
    Write-Section "Using configured local PFX signing route for an internal beta build."
} else {
    $doctorReport = Resolve-MachineLocalSigningRoute
    $selectedSubject = [string]$doctorReport.suggestedPowerShell.machineLocalSignedBuild.env.FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME
    $selectedThumbprint = [string]$doctorReport.suggestedPowerShell.machineLocalSignedBuild.env.FRANCIS_WINDOWS_SIGNING_SHA1

    $env:FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME = $selectedSubject
    $env:FRANCIS_WINDOWS_SIGNING_SHA1 = $selectedThumbprint
    $selectedCert = Get-CertificateByThumbprint $selectedThumbprint
    $selectedIssuer = if ($selectedCert) { $selectedCert.Issuer.Trim() } else { "unknown issuer" }

    Write-Section ("Using machine-local signing certificate: " + $selectedSubject)
    Write-Section ("Issuer: " + $selectedIssuer)
    Write-Section ("Thumbprint: " + $selectedThumbprint)
}

Write-Section "Audience: approved QA / private beta testers only"
Write-Section "Trust expectation: machine-local signed build only. Not public-trust signed."

Push-Location $SourceRoot
try {
    Invoke-NpmCommand @("run", "release:hardening")
    Invoke-NpmCommand @("run", "overlay:dist:signed")

    $bundleJson = & node electron/internal-beta-bundle.cjs --include-signer-cert ("--output-root=" + $InternalOutputRoot)
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    $bundleManifest = $bundleJson | ConvertFrom-Json
    $certExportPath = Resolve-CertificateExportPath $bundleManifest
    if ($certExportPath) {
        Export-Certificate -Cert $selectedCert -FilePath $certExportPath -Type CERT | Out-Null
    }

    Write-Section "Internal beta bundle ready."
    Write-Section ("Bundle root: " + $bundleManifest.outputRoot)
    Write-Section ("Manifest: " + $bundleManifest.manifestPath)
    Write-Section ("Notice: " + $bundleManifest.noticePath)
    foreach ($artifact in $bundleManifest.artifacts) {
        Write-Section ("Artifact: " + $artifact.targetPath)
    }
    if ($certExportPath) {
        Write-Section ("Tester trust certificate: " + $certExportPath)
    }
    Write-Section "Internal beta builds remain TESTER ONLY and must not be presented as public-trust releases."
}
finally {
    Pop-Location
}
