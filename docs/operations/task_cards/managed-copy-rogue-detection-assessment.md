# Task Card: Managed-Copy Rogue Detection Assessment

Task ID: `CR-FORGE-007`

Assigned seat: FORGE

Status: `READY`

## Objective

Implement a permission-gated, exact-schema assessment that records one immutable,
redacted rogue-signal evidence receipt for a structurally verified managed copy
without declaring the copy rogue or performing any containment or recovery action.

## Branch And Worktree

- Branch: `codex/forge-rogue-detection-assessment`
- Worktree: `D:\fg`
- Start from the exact local `main` containing this task card.
- Never work in `D:\Francis`.

## Runtime Isolation

- Lease: `LEASE-FORGE-007` in `control_room/RUNTIME_LEASES.md`.
- `FRANCIS_DATA_DIR`:
  `D:\Francis-runtime-leases\forge-rogue-detection-assessment\data`.
- Ports: `18008` / `18788` / `15178`; no service may bind them.
- Permitted processes: pytest, Ruff, mypy, and bounded validation only.
- Persistent services and operator-visible Orb access: denied.

## Files In Scope

- a narrowly named rogue-detection assessment module under `src/francis/`
- `src/francis/managed_copies.py`
- `src/francis/api/routes/managed_copies.py`
- `src/francis/api/mutation_authority_matrix.py`
- `tests/test_api_managed_copies.py`
- `tests/test_api_contract_chat_ui.py`
- `tests/test_api_mutating_route_authority_matrix.py`

## Do Not Touch

- live or production tenants, incidents, evidence, services, or runtimes
- halt, suspension, quarantine, replacement, restore, restart, or decommission
- tenant registry/state mutation, tools, shell, connectors, network, Lens, or Orb
- raw incident text, tenant identity, credentials, or unrestricted payloads
- completion ledger, Control Room aggregate files, and unrelated work

## Contracts

- source provision and structural-isolation receipts must validate and agree
- source signal IDs come only from the existing rogue-recovery contract
- assessment: `stage18_managed_copy_rogue_detection_assessment_v1`
- write scope: `managed_copies.rogue_recovery.write`
- ready status: `rogue_signal_assessed`, never `rogue_detected`
- readback: `GET /managed-copies/rogue-detection-assessments`

## Acceptance Criteria

- Permission denial occurs before provision, isolation, or evidence projection.
- Dry-run accepts only exact actor, copy/provision/isolation lineage, one canonical
  signal ID, its canonical severity, one bounded incident fingerprint, and a
  bounded nonempty list of evidence-reference hashes.
- Exact schema rejects unknown fields, raw incident/tenant material, credentials,
  arbitrary actions, malformed hashes, duplicate/unbounded evidence references,
  actor substitution, and nonexact Boolean/integer values.
- Planning revalidates current provision and structural-isolation receipts and
  fails closed on missing, malformed, foreign, or drifted lineage.
- Apply requires explicit confirmation and exact assessment-fingerprint replay,
  then writes one immutable, redacted, idempotent assessment receipt.
- Existing receipts are schema-validated and hash-bound; conflicts, malformed
  receipts, and cross-tenant/cross-copy substitutions fail closed.
- Readback validates receipts, reports drift/blockers without exposing invalid
  content, and remains empty against production state without real evidence.
- Every output and receipt keeps halt, quarantine, replacement, restore, tools,
  shell, network, tenant-state mutation, execution authority, and general
  mutation authority false.
- Fixture evidence proves software behavior only and never asserts a real copy is
  rogue or that the Stage 18 rogue-recovery deliverable is complete.

## Validation

Run focused rogue-assessment tests, the complete managed-copy card suite,
changed-path Ruff/format/mypy, and `git diff --check`. Repository-wide validation
is exact-head GitHub CI/CodeQL after integration; run local `scripts/check.ps1`
only for broad-impact or CI-divergence diagnosis.

## Required Reviews

- SENTINEL: privacy, authority, and no-containment boundary.
- VERA: exact-schema, lineage, receipt, and truthful-status acceptance mapping.
- HARBOR: route registration, portability, and integration.

## Non-Goals

- no production incident determination or evidence ingestion
- no halt, quarantine, replacement, restore, service, runtime, or Orb action
- no Stage 18 closure, FR-018 clearance, or physical-validation claim
