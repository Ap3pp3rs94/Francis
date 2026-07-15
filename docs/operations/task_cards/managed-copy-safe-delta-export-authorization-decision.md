# Task Card: Managed-Copy Safe-Delta Export Authorization Decision

Task ID: `CR-FORGE-005`

Assigned seat: FORGE

Status: `READY`

## Objective

Implement a separately scoped immutable approval/rejection decision receipt for
one exact, live-valid pending safe-delta export authorization request without
creating an artifact or performing export.

## Branch And Worktree

- Branch: `codex/forge-safe-delta-export-authorization-decision`
- Worktree: `D:\fg`
- Start from the exact local `main` containing this task card.
- Never work in `D:\Francis`.

## Runtime Isolation

- Lease: `LEASE-FORGE-005` in `control_room/RUNTIME_LEASES.md`.
- `FRANCIS_DATA_DIR`:
  `D:\Francis-runtime-leases\forge-safe-delta-export-authorization-decision\data`.
- Ports: `18006` / `18786` / `15176`; no service may bind them.
- Permitted processes: pytest, Ruff, mypy, and bounded validation only.
- Persistent services and operator-visible Orb access: denied.

## Files In Scope

- a narrowly named export-authorization decision module under `src/francis/`
- `src/francis/managed_copy_safe_delta_export_authorization.py`
- `src/francis/managed_copies.py`
- `src/francis/api/routes/managed_copies.py`
- `src/francis/api/mutation_authority_matrix.py`
- `tests/test_api_managed_copies.py`
- `tests/test_api_contract_chat_ui.py`
- `tests/test_api_mutating_route_authority_matrix.py`

## Do Not Touch

- live or production tenants, requests, approvals, data, services, or runtimes
- export artifacts, manifests, payloads, destinations, credentials, connectors,
  or network operations
- import, global learning, memory, registry, or tenant state
- Lens, Orb, input, renderer, overlay, or resident runtime
- completion ledger, Control Room aggregate files, and unrelated work

## Contracts

- source request:
  `stage18_managed_copy_safe_delta_export_authorization_request_v1`
- decision:
  `stage18_managed_copy_safe_delta_export_authorization_decision_v1`
- route: `POST /managed-copies/safe-delta-export-authorization-decision`
- readback: `GET /managed-copies/safe-delta-export-authorization-decisions`
- dedicated scope: `managed_copies.safe_delta.export.authorization.decide`
- exact outcomes: `approved` or `rejected`; no implicit/default approval

## Acceptance Criteria

- Unscoped actors are denied before request or lineage details are projected.
- Only one exact independently validated, live-aligned pending request is
  decidable; malformed, stale, foreign, conflicting, or drifted sources fail
  closed.
- The decision binds actor, request/receipt fingerprints, preflight/review/prior
  decision lineage, copy/provision/isolation lineage, action classifications,
  current tenant policy, exact outcome, and contract version.
- Exact schema rejects unknown fields, Boolean-like integers, actor
  substitution, unrestricted text, raw candidate/tenant material, credentials,
  and concrete destinations.
- Dry-run is deterministic and writes nothing. Recording requires explicit
  confirmation and exact fingerprint replay after a final live in-lock replan.
- Decision receipts are redacted, tenant-local, immutable, independently
  validated, idempotent for identical replay, and conflict-safe. A contradictory
  second decision cannot replace the first.
- Readback projects only validated live-aligned decisions and distinguishes
  `export_authorization_approved` from `export_authorization_rejected`.
- Even approved status creates no artifact, manifest, payload, destination,
  credential, network, export/import, learning, memory, registry, tenant-state,
  execution, or general mutation effect.
- Production source-loaded readback remains empty without a real pending request
  and explicit authorized operator decision. Fixture outcomes are test evidence,
  not production approval.

## Validation

Run focused decision plan/record/readback tests first, then the complete
managed-copies card suite, changed-path Ruff, format, mypy, and
`git diff --check`. Do not run `scripts/check.ps1` until ATLAS accepts a stable
review candidate.

## Required Reviews

- SENTINEL: decision authority, tenancy, privacy, and no-export boundary.
- VERA: acceptance mapping and discriminating drift/conflict regressions.
- HARBOR: route registration, portability, path length, and integration.
- MERIDIAN only if an established contract boundary changes or an ADR is needed.

## Non-Goals

- no real operator decision, production approval, export/import, artifact,
  manifest, payload, credential, concrete destination, connector, or network
- no global learning, runtime startup, Stage 18 closure, FR-018, or physical
  validation claim
