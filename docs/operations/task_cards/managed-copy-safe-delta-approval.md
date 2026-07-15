# Task Card: Managed-Copy Safe-Delta Approval Decision

Task ID: `CR-FORGE-002`

Assigned seat: FORGE

Status: `READY`

## Objective

Implement a receipt-backed approval or rejection decision for an existing,
live-aligned Stage 18 safe-delta candidate review without exporting, importing,
learning from, or mutating tenant data.

## Branch And Worktree

- Branch: `codex/forge-safe-delta-approval`
- Worktree: `D:\fg`
- Start from exact local `main` after this task-card commit.
- Never work in `D:\Francis`.

## Runtime Isolation

- Lease: `LEASE-FORGE-002` in `control_room/RUNTIME_LEASES.md`.
- `FRANCIS_DATA_DIR`: `D:\Francis-runtime-leases\forge-safe-delta-approval\data`.
- Ports: `18001` / `18781` / `15171`; no service may bind them.
- Permitted processes: pytest, Ruff, mypy, and bounded validation only.
- Persistent services and operator-visible Orb access: denied.

## Files In Scope

- `src/francis/managed_copy_safe_delta_approval.py` if a separate contract
  module is justified
- `src/francis/managed_copy_safe_delta.py`
- `src/francis/managed_copies.py`
- `src/francis/api/routes/managed_copies.py`
- `tests/test_api_managed_copies.py`
- `tests/test_api_contract_chat_ui.py`
- `tests/test_api_mutating_route_authority_matrix.py`

## Do Not Touch

- live or production data, approvals, tenants, or runtimes
- safe-delta export/import, global learning, memory, registry, or tenant state
- Lens, Orb, input, renderer, overlay, or resident runtime
- unrelated tracked or untracked files
- completion ledger or Control Room aggregate files

## Contracts

- source review: `stage18_managed_copy_safe_delta_review_v1`
- decision receipt: `stage18_managed_copy_safe_delta_approval_v1`
- dedicated scope: `managed_copies.safe_delta.approval.write`
- exact dry-run fingerprint plus explicit confirmation
- full copy, tenant, provision, isolation, candidate, policy, actor, and decision
  lineage

## Acceptance Criteria

- Unscoped actors cannot dry-run or record a decision.
- Only exact `approved` or `rejected` decisions are accepted; unknown fields,
  Boolean-like integers, and malformed values fail closed.
- Dry-run fingerprint binds the complete validated candidate review, actor,
  decision, live lineage, and current tenant safe-delta policy.
- Apply requires exact fingerprint replay and explicit confirmation.
- Approval and rejection create separate immutable redacted decision receipts;
  the candidate-review receipt is never mutated.
- Identical replay is idempotent; a conflicting second decision is rejected.
- Missing, foreign, stale, malformed, cross-tenant, policy-drifted, provision-
  drifted, or isolation-drifted review receipts fail closed.
- Readback validates every decision receipt before projecting the latest valid
  decision.
- Approval means eligible only for a future separately governed export
  preflight. Export, import, learning, execution, memory, registry, network, and
  tenant-state mutation remain false.
- Production source-loaded readback remains empty.

## Validation

Run focused decision tests first, then the complete managed-copies card suite,
changed-path Ruff, format, mypy, and `git diff --check`. Do not run
`scripts/check.ps1` until ATLAS accepts a stable review candidate.

## Required Reviews

- SENTINEL: authority, tenancy, conflict, and fail-closed decision semantics.
- VERA: acceptance mapping and discriminating regressions.
- HARBOR: exact-head portability and integration readiness.
- MERIDIAN only if the implementation changes an established contract boundary
  or requires an ADR.

## Non-Goals

- no export/import or global-core learning write
- no production tenant/candidate creation or customer facts
- no runtime startup, provisioning, rogue recovery, SLA, or decommission action
- no Stage 18 completion or FR-018 claim
