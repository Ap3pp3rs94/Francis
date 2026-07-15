# Task Card: Managed-Copy Safe-Delta Export Preflight

Task ID: `CR-FORGE-003`

Assigned seat: FORGE

Status: `READY`

## Objective

Implement a permission-gated, dry-run-only preflight that proves whether one
approved safe-delta candidate remains eligible for a future separately governed
export without creating an artifact, exporting data, learning, or mutating state.

## Branch And Worktree

- Branch: `codex/forge-safe-delta-export-preflight`
- Worktree: `D:\fg`
- Start from the exact local `main` containing this task card.
- Never work in `D:\Francis`.

## Runtime Isolation

- Lease: `LEASE-FORGE-003` in `control_room/RUNTIME_LEASES.md`.
- `FRANCIS_DATA_DIR`:
  `D:\Francis-runtime-leases\forge-safe-delta-export-preflight\data`.
- Ports: `18004` / `18784` / `15174`; no service may bind them.
- Permitted processes: pytest, Ruff, mypy, and bounded validation only.
- Persistent services and operator-visible Orb access: denied.

## Files In Scope

- `src/francis/managed_copy_safe_delta_export.py` if a separate contract module
  is justified
- `src/francis/managed_copy_safe_delta.py`
- `src/francis/managed_copy_safe_delta_approval.py`
- `src/francis/managed_copies.py`
- `src/francis/api/routes/managed_copies.py`
- `tests/test_api_managed_copies.py`
- `tests/test_api_contract_chat_ui.py`
- `tests/test_api_mutating_route_authority_matrix.py`

## Do Not Touch

- live or production tenants, approvals, data, services, or runtimes
- export artifacts, manifests, destinations, connectors, or network operations
- import, global learning, memory, registry, or tenant state
- Lens, Orb, input, renderer, overlay, or resident runtime
- completion ledger, Control Room aggregate files, and unrelated work

## Contracts

- source review: `stage18_managed_copy_safe_delta_review_v1`
- source decision: `stage18_managed_copy_safe_delta_approval_v1`
- preflight: `stage18_managed_copy_safe_delta_export_preflight_v1`
- route: `POST /managed-copies/safe-delta-export-preflight`
- dedicated scope: `managed_copies.safe_delta.export.preflight`
- exact request schema: actor, copy/provision/isolation identifiers,
  `review_fingerprint`, `decision_receipt_id`, and exact `dry_run: true`
- deterministic fingerprint binds actor, approved decision, review, candidate,
  provision, isolation, current tenant policy, signal class, direction, and
  contract version

## Acceptance Criteria

- Unscoped actors are denied before lineage details are projected.
- Only a validated `approved` decision for the exact requested review may become
  `export_preflight_ready`; rejection is an explicit blocker.
- Missing, malformed, stale, conflicting, foreign, cross-copy, cross-tenant, or
  fingerprint-mismatched receipts fail closed.
- Provision, isolation, review, decision, or tenant-policy drift after approval
  fails closed.
- Unknown fields, Boolean-like integers, invalid enums, and any value other than
  exact `dry_run: true` fail closed.
- The request accepts no raw candidate material or raw tenant identity, and the
  response exposes neither.
- Repeated identical preflight is deterministic and side-effect free.
- Production source-loaded invocation remains blocked/empty without real
  receipts.
- Readback/status may report approval and preflight eligibility only from
  validated live-aligned receipts; `safe_delta_exported` and flow-active remain
  false.
- The route writes no file, receipt, manifest, artifact, tenant state, memory,
  registry, or learning state; uses no network; grants no export, execution, or
  mutation authority.

## Validation

Run focused preflight tests first, then the complete managed-copies card suite,
changed-path Ruff, format, mypy, and `git diff --check`. Do not run
`scripts/check.ps1` until ATLAS accepts a stable review candidate.

## Required Reviews

- SENTINEL: permission, tenancy, privacy, and no-export authority boundary.
- VERA: acceptance mapping and discriminating drift/rejection regressions.
- HARBOR: route registration, portability, and integration readiness.
- MERIDIAN only if an established contract boundary changes or an ADR is needed.

## Non-Goals

- no export/import, artifact/manifest creation, destination selection, or network
- no global-core learning or production customer/tenant facts
- no operator decision creation; consume only existing validated decision truth
- no runtime startup, Stage 18 closure, FR-018, or physical-validation claim
