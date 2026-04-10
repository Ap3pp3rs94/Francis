# Francis 2.0 (Mega Tree + GapFix)

Local-first, policy-guarded, auditable autonomous colleague.

## Quick Start (Windows / PowerShell)
```powershell
cd C:\Francis
.\scripts\bootstrap.ps1
.\scripts\francis.ps1 api
```

## Quality checks
```powershell
.\scripts\check.ps1
```

### Daemon
```powershell
.\scripts\francis.ps1 daemon
```

### UI
```powershell
.\scripts\bootstrap.ps1 -IncludeChatUI
cd apps\chat_ui
npm run dev
```

API docs: http://127.0.0.1:8000/docs
UI: http://localhost:5173

### Supervised exec
```powershell
.\scripts\francis.ps1 supervised-exec --cmd "echo hello" --print-summary
```

`DECISION:` and `SUMMARY:` lines are written to `stderr`; `stdout` remains JSON.

If the run returns `needs_approval`, approve the `approval_id` (via the API under `/approvals`, or locally) and rerun:
```powershell
.\.venv\Scripts\python.exe -c "from francis.governance.approvals import decide; decide('<approval_id>','approve')"
.\scripts\francis.ps1 supervised-exec --cmd "echo hello" --approval-id <approval_id> --print-summary
```

## Editing docs safely on Windows

Replace canonical documentation sections by running the helper script from the repo root. From PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "Set-Location C:\Francis; python tools/replace_doc_block.py --file docs/POLICIES.md --start '### 4.4 Supervised-exec policy contract' --end '## 5. Environment profiles (policy bundles)' --template-file tools/templates/supervised_exec_contract.md"
```
