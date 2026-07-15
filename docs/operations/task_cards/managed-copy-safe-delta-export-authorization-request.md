# Task Card: Managed-Copy Safe-Delta Export Authorization Request

Task ID: `CR-FORGE-004`

Assigned seat: FORGE

Status: `READY`

## Objective

Implement a separately scoped, immutable pending authorization-request receipt
for one exact safe-delta export action, bound to a freshly recomputed eligible
preflight without approving or performing export.

## Branch And Worktree

- Branch: `codex/forge-safe-delta-export-authorization-request`
- Worktree: `D:\fg`
- Start from the exact local `main` containing this task card.
- Never work in `D:\Francis`.

## Runtime Isolation

- Lease: `LEASE-FORGE-004` in `control_room/RUNTIME_LEASES.md`.
- `FRANCIS_DATA_DIR`:
  `D:\Francis-runtime-leases\forge-safe-delta-export-authorization-request\data`.
- Ports: `18005` / `18785` / `15175`; no service may bind them.
- Permitted processes: pytest, Ruff, mypy, and bounded validation only.
- Persistent services and operator-visible Orb access: denied.

## Files In Scope

- a narrowly named safe-delta export authorization-request module under
  `src/francis/`
- `src/francis/managed_copy_safe_delta_export.py`
- `src/francis/managed_copies.py`
- `src/francis/api/routes/managed_copies.py`
- `src/francis/api/mutation_authority_matrix.py`
- `tests/test_api_managed_copies.py`
- `tests/test_api_contract_chat_ui.py`
- `tests/test_api_mutating_route_authority_matrix.py`

## Do Not Touch

- live or production tenants, approvals, data, services, or runtimes
- export artifacts, manifests, payloads, destinations, credentials, connectors,
  or network operations
- import, global learning, memory, registry, or tenant state
- Lens, Orb, input, renderer, overlay, or resident runtime
- completion ledger, Control Room aggregate files, and unrelated work

## Contracts

- preflight: `stage18_managed_copy_safe_delta_export_preflight_v1`
- request: `stage18_managed_copy_safe_delta_export_authorization_request_v1`
- route: `POST /managed-copies/safe-delta-export-authorization-request`
- readback: `GET /managed-copies/safe-delta-export-authorization-requests`
- dedicated scope: `managed_copies.safe_delta.export.authorization.request`
- request state: `export_authorization_pending`; never approved or executed
- exact action binding includes actor, preflight fingerprint, review and decision
  lineage, copy/provision/isolation lineage, current tenant policy, signal class,
  `direction=export`, bounded export class, retention classification, destination
  class, purpose fingerprint, and contract version

## Acceptance Criteria

- Unscoped actors are denied before lineage or action details are projected.
- Only a freshly recomputed `export_preflight_ready` result for the exact actor
  and lineage can produce a request plan.
- Missing, malformed, stale, conflicting, foreign, cross-copy, cross-tenant, or
  fingerprint-mismatched source receipts fail closed.
- Drift in provision, isolation, review, decision, preflight, or tenant policy
  fails closed both during planning and immediately before recording.
- Exact schema rejects unknown fields, Boolean-like integers, unsupported action
  classifications, raw candidate material, raw tenant identity, credentials,
  concrete destinations, and unrestricted free-form action data.
- Dry-run writes nothing and returns a deterministic request fingerprint.
- Recording requires explicit confirmation and exact fingerprint replay against
  a freshly recomputed plan.
- The tenant-local receipt is redacted, immutable, independently validated,
  idempotent for exact replay, and collision/conflict safe.
- Readback/status projects only validated receipts and reports
  `export_authorization_pending` while export and flow-active remain false.
- The route may write only the pending request receipt. It writes no export
  artifact, manifest, payload, tenant state, memory, registry, or learning;
  uses no network; grants no approval, export, execution, or mutation authority.
- Production source-loaded readback remains empty without real receipts and
  operator-supplied action classifications.

## Validation

Run focused request plan/record/readback tests first, then the complete
managed-copies card suite, changed-path Ruff, format, mypy, and
`git diff --check`. Do not run `scripts/check.ps1` until ATLAS accepts a stable
review candidate.

## Required Reviews

- SENTINEL: permission, tenancy, privacy, and request-versus-approval boundary.
- VERA: acceptance mapping and discriminating drift/replay regressions.
- HARBOR: route registration, portability, path length, and integration.
- MERIDIAN only if an established contract boundary changes or an ADR is needed.

## Non-Goals

- no approval decision, export/import, artifact/manifest/payload creation,
  credential or concrete destination selection, connector, or network operation
- no global-core learning or production customer/tenant facts
- no runtime startup, Stage 18 closure, FR-018, or physical-validation claim
