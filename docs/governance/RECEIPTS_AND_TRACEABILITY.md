# Receipts and Traceability

## Purpose
Define the mandatory evidence model for Francis so every meaningful action is explainable, replayable, and auditable.

## Identity Rules: `run_id` and `trace_id`
- Every user-visible operation MUST have a `run_id`.
- Every delegated or multi-step operation MUST carry a `trace_id` across components.
- Child actions may have distinct `run_id` values, but MUST reference the parent `trace_id`.
- Receipts are invalid if identity fields are missing or rewritten.

## Required Artifacts by Action Type
| Action Type | Minimum Receipts | Required Storage |
| --- | --- | --- |
| Read-only observation (state, diagnostics) | source context, timestamp, decision summary, confidence label | `workspace/logs/francis.log.jsonl`, `workspace/runs/run_ledger.jsonl` |
| File mutation | diff/changed paths, actor, scope, verification output, summary | `workspace/journals/fs.jsonl`, `workspace/runs/run_ledger.jsonl` |
| Command execution | command, allowlist status, exit code, stdout/stderr summary, verification notes | `workspace/logs/francis.log.jsonl`, `workspace/runs/run_ledger.jsonl` |
| Mission transition/tick | mission id, state transition, result status, artifacts produced | `workspace/missions/history.jsonl`, `workspace/runs/run_ledger.jsonl` |
| Forge stage/promote | proposal id, staged files, tests/docs evidence, risk tier, promotion approver | `workspace/forge/reports`, `workspace/forge/catalog.json`, `workspace/runs/run_ledger.jsonl` |
| Policy/approval decision | requested action, risk tier, decision, approver identity, rationale | `workspace/journals/decisions.jsonl` |
| Incident response | trigger event, severity, evidence pointers, remediation steps, final status | `workspace/incidents/incidents.jsonl`, `workspace/runs/run_ledger.jsonl` |

## Verification Gates Before Claims
- Francis MUST NOT claim "done" unless defined verification gates pass.
- Verification gates are action-specific (for example: tests/build/preview for code changes).
- Failed verification MUST downgrade language to "blocked" or "partial" with explicit next step.
- Confidence labels MUST match evidence state: Confirmed, Likely, or Uncertain.

## Append-Only Ledgers and Journals
- Journals and ledgers are append-only by default.
- Corrections are appended as superseding entries; previous records remain intact.
- Retention and export/import policy MUST preserve receipt lineage.
- Missing or malformed receipt entries are treated as integrity incidents.

## Acceptance Criteria Checklist
- [ ] Every meaningful action records `run_id` and applicable `trace_id`.
- [ ] Action claims include artifacts, verification state, and concise summaries.
- [ ] No completion claim is emitted before verification gates pass.
- [ ] Ledgers/journals are append-only and replayable.
- [ ] Receipt lineage is sufficient for end-to-end audit reconstruction.
