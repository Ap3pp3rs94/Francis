# Windows Internal Beta

This is the canonical private Windows distribution path for Francis Overlay while public-trust signing is still blocked on real signer procurement.

Use it for:

- internal QA
- approved private beta testers
- controlled operator demos on approved machines

Do not use it for:

- public download pages
- public customer rollout
- any claim that the artifacts are Microsoft-trusted, store-grade, or public-release signed

## Canonical Command

From the repo root:

```powershell
npm run release:publish:windows
```

That command is intentionally the internal-beta lane. It runs the bounded hardening checks, builds signed Windows artifacts with the machine-local signer route, and then writes a labeled tester bundle under:

```text
dist/internal-beta/windows/current/
```

## What The Internal Bundle Contains

The internal beta bundle is built to be hard to confuse with a future public release. It includes:

- `INTERNAL-BETA-NOTICE.txt`
- `internal-beta-manifest.json`
- relabeled artifacts such as:
  - `Francis-Overlay-<version>-x64-internal-beta-portable.exe`
  - `Francis-Overlay-<version>-x64-internal-beta-installer.exe`
- `build-signing.json`
- `build-provenance.json`
- `INSTALL-WINDOWS-INTERNAL-BETA.md`
- `Francis-Overlay-Internal-Beta-Signer.cer` when the internal lane used a Windows cert-store signer that can be exported locally

`dist/overlay/` remains the raw packaging/staging output. `dist/internal-beta/windows/current/` is the tester handoff output.

## Trust Model

The internal beta lane accepts a machine-local signer. On the current Francis build machine that means the self-issued dev certificate:

- Subject: `Francis Overlay Dev Signing`
- Issuer: `Francis Overlay Dev Signing`

That is acceptable for controlled tester distribution.

It is not acceptable for public release.

The public release path remains:

```powershell
npm run release:publish:windows:public
```

That path stays blocked until a non-self-issued publisher cert or Azure Artifact Signing route exists.

## Tester Install Workflow

### 1. Get the internal bundle

The build operator should hand testers the contents of:

```text
dist/internal-beta/windows/current/
```

At minimum the tester needs:

- the internal beta installer or portable artifact
- `INTERNAL-BETA-NOTICE.txt`
- `Francis-Overlay-Internal-Beta-Signer.cer` if it was exported with the bundle

### 2. Read the notice

Testers should confirm:

- the bundle says `INTERNAL / QA / TESTER ONLY`
- the signer is the expected Francis internal signer
- the artifact names include `internal-beta`

### 3. Trust the signer on the approved machine

If the bundle contains `Francis-Overlay-Internal-Beta-Signer.cer`, import it into `Trusted People`.

Current-user scope:

```powershell
Import-Certificate -FilePath .\Francis-Overlay-Internal-Beta-Signer.cer -CertStoreLocation Cert:\CurrentUser\TrustedPeople
```

Machine scope for managed/admin installs:

```powershell
Import-Certificate -FilePath .\Francis-Overlay-Internal-Beta-Signer.cer -CertStoreLocation Cert:\LocalMachine\TrustedPeople
```

If the bundle does not contain the cert file, the build operator must provide the matching public cert out of band before the tester proceeds.

### 4. Install or run the build

Installer path:

```powershell
.\Francis-Overlay-<version>-x64-internal-beta-installer.exe
```

Portable path:

```powershell
.\Francis-Overlay-<version>-x64-internal-beta-portable.exe
```

### 5. Expect SmartScreen friction

Importing the signer cert helps Windows trust the signature chain locally.

It does not give the build public reputation.

SmartScreen or local policy can still warn because this is not a public-trust release.

## What Not To Do

- Do not redistribute the internal beta bundle as a public download.
- Do not remove the `internal-beta` artifact labels.
- Do not claim the build is public-trust signed.
- Do not point testers at `dist/overlay/` and skip the labeled internal bundle.

## Troubleshooting

### `npm run release:publish:windows` fails before packaging

The internal lane could not find a usable local code-signing cert or could not disambiguate multiple certs. Set:

```powershell
$env:FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME = 'Your signer subject'
$env:FRANCIS_WINDOWS_SIGNING_SHA1 = 'Your thumbprint'
```

Then rerun the command.

### The installer still warns after importing the cert

That is expected. The internal beta lane does not provide public SmartScreen reputation.

### A maintainer tries to use the public command

That is still intentionally blocked until the machine has:

- `FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME`
- `FRANCIS_WINDOWS_SIGNING_CHAIN_HINT`
- a non-self-issued cert route or Azure Artifact Signing credentials

## Public Release Later

When signer procurement is done:

1. fill `scripts/signing-public.local.ps1`
2. run `npm run release:publish:windows:public:local`
3. publish only the public-trust artifacts
