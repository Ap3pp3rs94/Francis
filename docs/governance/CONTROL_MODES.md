# Control Modes

## Mode Definitions

### Observe
- Allowed: read-only state collection, anomaly detection, mission/context summaries.
- Forbidden: writing code/files, executing mutating commands, promotions.
- Approvals: none for read-only within approved scope.

### Assist
- Allowed: prepare patches/plans/commands, draft PR notes, propose capability stages.
- Forbidden: unattended execution of mutating operations.
- Approvals: explicit user approval required before execution.

### Pilot
- Allowed: takeover-on-command execution within active scope, including code changes and mission ticks.
- Forbidden: out-of-scope actions, hidden background operations, irreversible actions without explicit consent.
- Approvals: mode entry confirmation + policy-required approvals.

### Away
- Allowed: scheduled mission advancement, observer scans, staged improvements, approval packet preparation.
- Forbidden: unsupervised high-risk operations, automatic promotion/deploy outside policy.
- Approvals: pre-authorized policy envelope; queue anything beyond envelope.

## Kill Switch / Panic Mode
- Must be always available and immediate.
- Must stop active execution and new action dispatch.
- Must preserve state and receipts for post-stop review.

## Scope Rules
- Repo-only, workspace-only, and app-specific scopes are explicit contracts.
- Out-of-scope actions are denied and logged.
- Scope changes require user acknowledgement.

## Acceptance Criteria
- Current mode is always visible and machine-readable.
- Pilot/Away can be revoked instantly.
- Francis never executes outside declared scope.
- Every mode transition emits receipts (`run_id`, decision record).
- Policy/approval checks are enforced before mutating actions.
