# Windows Public Signing

Francis public-trust Windows release no longer uses Electron Builder's built-in Azure Trusted Signing wrapper. The repo now owns the Windows sign step directly through [`build/sign/windows-sign.cjs`](../../build/sign/windows-sign.cjs), which invokes `signtool.exe` with `Azure.CodeSigning.Dlib.dll` and `metadata.json`.

## Required inputs

You need all of the following before `npm run release:publish:windows:public:local` can succeed:

- an Azure Artifact Signing account and `Public Trust` certificate profile
- an Entra app registration with `Artifact Signing Certificate Profile Signer`
- the real client secret value for that app
- the Azure Artifact Signing client tools on the machine
- `.NET 8 x64` runtime or SDK on the machine
- a populated `metadata.json`

The local public bootstrap lives at `scripts/signing-public.local.ps1`.

## Local env contract

The public lane expects these values in `scripts/signing-public.local.ps1`:

```powershell
$env:FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME='Austin Peppers'
$env:FRANCIS_WINDOWS_SIGNING_CHAIN_HINT='Microsoft ID Verified Code Signing PCA 2021'
$env:FRANCIS_AZURE_TRUSTED_SIGNING_ENDPOINT='https://cus.codesigning.azure.net/'
$env:FRANCIS_AZURE_TRUSTED_SIGNING_ACCOUNT_NAME='francis-signing-rg'
$env:FRANCIS_AZURE_TRUSTED_SIGNING_CERTIFICATE_PROFILE_NAME='francis-public-trust'
$env:DOTNET_ROOT='C:\Program Files\dotnet'
$env:PATH='C:\Program Files\dotnet;' + $env:PATH
$env:AZURE_SIGN_SIGNSDK_SIGNSTOOL='C:\path\to\signtool.exe'
$env:AZURE_SIGN_DLIB_PATH='C:\path\to\Azure.CodeSigning.Dlib.dll'
$env:AZURE_SIGN_METADATA_PATH='C:\path\to\metadata.json'
$env:AZURE_CLIENT_ID='<client-id>'
$env:AZURE_TENANT_ID='<tenant-id>'
$env:AZURE_CLIENT_SECRET='<client-secret-value>'
```

`AZURE_CLIENT_SECRET` must be the secret value, not the secret ID.

## metadata.json

`AZURE_SIGN_METADATA_PATH` must point to a JSON file with the Azure signing account details used by the dlib:

```json
{
  "Endpoint": "https://cus.codesigning.azure.net/",
  "CodeSigningAccountName": "francis-signing-rg",
  "CertificateProfileName": "francis-public-trust",
  "ExcludeCredentials": []
}
```

Keep `metadata.json` aligned with the corresponding `FRANCIS_AZURE_TRUSTED_SIGNING_*` env values. The verifier will fail closed if they diverge.

## Tooling prerequisites

- Install the Azure Artifact Signing client tools so the machine has:
  - `signtool.exe`
  - `Azure.CodeSigning.Dlib.dll`
  - a writable `metadata.json`
- Install `.NET 8 x64` or newer so `Azure.CodeSigning.Dlib.dll` can load.

Francis does not discover these tools heuristically anymore. The public lane is deterministic and env-driven:

- `AZURE_SIGN_SIGNSDK_SIGNSTOOL`
- `AZURE_SIGN_DLIB_PATH`
- `AZURE_SIGN_METADATA_PATH`

## Verification

Run these in order:

```powershell
npm run overlay:signing-doctor:public
npm run overlay:verify-windows-signing-env
npm run release:publish:windows:public:local
```

`overlay:signing-doctor:public` checks the public-trust identity posture.

`overlay:verify-windows-signing-env` checks:

- `signtool.exe` path
- `Azure.CodeSigning.Dlib.dll` path
- `metadata.json` path and JSON shape
- `metadata.json` alignment with the repo's public-signing env
- `.NET 8` runtime availability

`release:publish:windows:public:local` then runs:

1. public signing doctor
2. Windows signing env verifier
3. bounded `release:hardening`
4. `overlay:dist:public`

## Failure meanings

- `self_issued_only`
  - the machine still only has a private/self-issued signer posture; public release is blocked
- `publisher_mismatch`
  - the built artifacts do not match `FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME`
- `chain_hint_mismatch`
  - the built artifacts do not match `FRANCIS_WINDOWS_SIGNING_CHAIN_HINT`
- `invalid_client`
  - the Entra client secret is wrong; use the secret value, not the secret ID

## Current release split

- `npm run release:publish:windows`
  - internal beta / QA / tester-only
- `npm run release:publish:windows:public`
  - public-trust release with repo-owned sign hook
- `npm run release:publish:windows:public:local`
  - same public-trust path, but starts by loading `scripts/signing-public.local.ps1`
