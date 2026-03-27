# Public-trust Windows signing template for Francis.
# Copy the relevant block into scripts/signing-public.local.ps1 and fill the real values.

# Route A: Windows cert-store signing with a non-self-issued publisher certificate.
# $env:FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME = '<legal publisher name>'
# $env:FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME = '<certificate subject name>'
# $env:FRANCIS_WINDOWS_SIGNING_SHA1 = '<certificate thumbprint>'

# Route B: Azure Trusted Signing.
# $env:FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME = '<legal publisher name>'
# $env:FRANCIS_AZURE_TRUSTED_SIGNING_ENDPOINT = 'https://<region>.codesigning.azure.net/'
# $env:FRANCIS_AZURE_TRUSTED_SIGNING_ACCOUNT_NAME = '<trusted-signing-account>'
# $env:FRANCIS_AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE_NAME = '<certificate-profile>'
# $env:AZURE_CLIENT_ID = '<entra-client-id>'
# $env:AZURE_TENANT_ID = '<entra-tenant-id>'
# $env:AZURE_CLIENT_SECRET = '<entra-client-secret>'
