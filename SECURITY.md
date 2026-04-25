# Security Policy (Francis)



This document describes how to report security issues and the security expectations for the **Francis** workspace (scripts, configs, services, and supporting tooling under `D:\francis`).



## Supported Versions



Security fixes are provided for:



- The **current mainline** version of the Francis workspace (your active branch / latest deployment).

- The **most recent release artifact** (if you publish releases/zips).



Older copies, ad-hoc forks, and modified scripts may not receive fixes unless you can reproduce the issue on the current version.



## Reporting a Vulnerability



### Please do **not** report security vulnerabilities via public tickets/issues or chat logs.



Instead, report privately and include enough detail to reproduce.



**Preferred contact**

- Email: `security@YOUR-DOMAIN-HERE`  

  (Replace with your real mailbox, or a distribution list)



**Alternate contact**

- IT/Admin contact: `YOUR-ADMIN-EMAIL-HERE`



If you don’t have a dedicated mailbox, create one (or use a private shared inbox) so reports don’t get lost.



### What to include



Please include:



- A clear description of the issue and potential impact.

- The affected file(s)/script(s) (example: `D:\francis\scripts\plugin-build.ps1`).

- Exact steps to reproduce (commands run, inputs used).

- Any logs or screenshots that help—**redact secrets** (API keys, tokens, passwords).

- Your environment:

  - OS (Windows version / PowerShell version)

  - Whether you’re using WSL

  - Node/Python versions if relevant

  - Ollama version (if involved)



### Response expectations



We aim to:



- **Acknowledge** your report within **3 business days**

- **Triage** severity and confirm scope within **7 business days**

- **Fix or mitigate** as quickly as possible based on severity



If the issue is critical and actively exploitable, mitigation guidance may be shared before a full patch is released.



## Coordinated Disclosure



Please allow time for a fix before public disclosure. We support coordinated disclosure and will work with reporters on a reasonable publication timeline once a patch or mitigation is available.



## Scope



### In scope



- Scripts and automation under `D:\francis\scripts`

- Configuration files under `D:\francis\data\config` (and related config locations)

- Local services installed/managed by Francis scripts

- Logging/report outputs under `D:\francis\data\logs`



### Out of scope



- Issues requiring physical access to the machine (unless the script meaningfully increases risk)

- Attacks requiring a compromised OS/user account prior to using Francis

- Social engineering attempts or phishing

- Denial-of-service against infrastructure you do not own/operate

- Vulnerabilities in third-party software **unless** Francis enables an insecure configuration by default



## Security Guidelines (Operational)



These are the baseline expectations for a secure deployment.



### 1) Treat scripts as privileged code



Many scripts under `D:\francis\scripts` can:

- install services

- download tooling

- modify system state

- read/write logs and configuration



Only run scripts you trust and that you have reviewed.



**Recommended**

- Use `-WhatIf` / `ShouldProcess` where supported

- Run from a PowerShell session with least privileges whenever possible

- Keep `D:\francis` ACLs restricted (Admins + the service account only)



### 2) Secrets and credentials handling



**Do not store secrets in the repo or in plaintext files** under `D:\francis` unless they are properly protected and explicitly intended.



Preferred secret storage:

- Windows Credential Manager

- DPAPI-protected blobs

- Environment variables set at User/Machine scope (with care)

- A dedicated secrets manager (if available)



If you must use `.env` files:

- keep them **out of source control**

- restrict filesystem permissions



### 3) Downloads and installers



Some scripts may download installers or run remote install scripts.



**Minimum safety requirements**

- Prefer pinned versions where possible

- Prefer vendor HTTPS endpoints

- Record installer actions into logs under `D:\francis\data\logs\operations`

- Avoid `curl | sh` patterns unless you trust the source and understand the risk



If a script uses a remote install command, it should:

- log the URL and timestamp

- optionally support version pinning

- fail safely when network is unavailable



### 4) Logging



Logs are useful but can leak sensitive data.



Requirements:

- Do not log secrets (tokens, API keys, passwords, private URLs with embedded creds).

- If logs capture command output, ensure sensitive parameters are redacted.

- Keep logs under `D:\francis\data\logs\operations` and restrict access.



### 5) Local network exposure



If any service binds to a TCP port (example: local APIs):

- bind to `127.0.0.1` by default unless explicitly intended

- document any non-local binding

- avoid exposing management endpoints publicly



### 6) Integrity and tamper resistance (recommended)



- Consider code signing for PowerShell scripts.

- Monitor file integrity for `D:\francis\scripts` (hashes, change alerts).

- Ensure only authorized users can modify scripts executed by scheduled tasks/services.



## Security Guidelines (Development)



### Dependency hygiene



- Node: run `npm audit` / `pnpm audit` as part of CI (if applicable)

- Python: pin dependencies where possible; use virtual environments

- Keep PowerShell modules updated, especially those that parse structured formats (YAML/JSON)



### Input validation



Treat all external inputs as untrusted:

- URLs

- model names

- filesystem paths

- config values

- API responses



Validate and sanitize before use (especially when constructing commands).



### Safe process execution



Prefer calling executables with structured argument arrays rather than building command strings. Avoid injecting untrusted input into:

- `cmd.exe /c`

- `powershell -Command`

- `sh -c`

- `Invoke-Expression`



## Incident Response (if compromise is suspected)



If you suspect a security incident:



1. **Disconnect** affected machine(s) from the network (if appropriate).

2. **Preserve logs**:

   - `D:\francis\data\logs\operations`

   - Windows Event Logs relevant to script execution and services

3. **Stop services/processes** related to the incident (document what you stop).

4. Rotate credentials that may have been exposed.

5. Review script modifications under `D:\francis\scripts` (hash comparison).

6. Only after evidence is preserved, proceed with cleanup and restoration.



## Acknowledgements



If you want to acknowledge security reporters, add a section here (optional).  

Example:



- `@researcher-handle` — brief description, date



---



**Maintainers:**  

- Name/Team: `YOUR-NAME-OR-TEAM`  

- Contact: `security@YOUR-DOMAIN-HERE`



