# Task Card: Managed-Copy Safe-Delta Export Artifact Plan

Task ID: `CR-FORGE-006`

Assigned seat: FORGE

Status: `READY`

## Objective

Implement a deterministic, permission-gated, dry-run-only plan describing the
bounded artifact Francis could create after one exact live-valid approved
safe-delta export authorization decision, without persisting or exporting it.

## Branch And Worktree

- Branch: `codex/forge-safe-delta-export-artifact-plan`
- Worktree: `D:\fg`
- Start from the exact local `main` containing this task card.
- Never work in `D:\Francis`.

## Runtime Isolation

- Lease: `LEASE-FORGE-006` in `control_room/RUNTIME_LEASES.md`.
- `FRANCIS_DATA_DIR`:
  `D:\Francis-runtime-leases\forge-safe-delta-export-artifact-plan\data`.
- Ports: `18007` / `18787` / `15177`; no service may bind them.
- Permitted processes: pytest, Ruff, mypy, and bounded validation only.
- Persistent services and operator-visible Orb access: denied.

## Files In Scope

- a narrowly named export-artifact planning module under `src/francis/`
- existing safe-delta export authorization decision/readback modules as needed
- `src/francis/managed_copies.py`
- `src/francis/api/routes/managed_copies.py`
- `src/francis/api/mutation_authority_matrix.py`
- `tests/test_api_managed_copies.py`
- `tests/test_api_contract_chat_ui.py`
- `tests/test_api_mutating_route_authority_matrix.py`

## Do Not Touch

- live or production tenants, approvals, data, services, or runtimes
- persisted plans, receipts, artifacts, manifests, payloads, destinations,
  credentials, connectors, or network operations
- import, global learning, memory, registry, tenant state, Lens, or Orb
- completion ledger, Control Room aggregate files, and unrelated work

## Contracts

- source decision:
  `stage18_managed_copy_safe_delta_export_authorization_decision_v1`
- plan: `stage18_managed_copy_safe_delta_export_artifact_plan_v1`
- route: `POST /managed-copies/safe-delta-export-artifact-plan`
- scope: `managed_copies.safe_delta.export.artifact.preflight`
- exact mode: `dry_run: true`
- ready status: `export_artifact_plan_ready`, never exported/flow-active

## Acceptance Criteria

- Permission denial occurs before decision or lineage projection.
- Only one exact independently validated, live-aligned approved decision can
  produce a ready plan; rejected, pending, malformed, stale, foreign, or drifted
  sources fail closed.
- The deterministic plan binds actor, decision/request/preflight/review lineage,
  copy/provision/isolation lineage, current tenant policy, action
  classifications, bounded media/schema/retention enums, counts, and version.
- Exact schema rejects unknown fields, actor substitution, nonexact Boolean,
  raw candidate/tenant material, payload bytes, credentials, concrete
  destinations, connector data, and unrestricted text.
- Repeated exact requests return identical complete output and fingerprint.
- The response contains only bounded hashes, enums, counts, contract versions,
  and receipt references; it writes no file, receipt, plan, artifact, manifest,
  payload, tenant state, memory, registry, or learning, uses no network, and
  grants no approval, export, execution, or mutation authority.
- Production source-loaded invocation remains blocked without a real approved
  chain. Fixture approval is test evidence, not production authority.

## Validation

Run focused artifact-plan tests, the complete managed-copy card suite,
changed-path Ruff/format/mypy, and `git diff --check`. Repository-wide validation
is exact-head GitHub CI/CodeQL after integration; run local `scripts/check.ps1`
only for broad-impact or CI-divergence diagnosis.

## Required Reviews

- SENTINEL: approval consumption, privacy, and no-export boundary.
- VERA: acceptance mapping and drift/rejection discrimination.
- HARBOR: route registration, portability, and integration.

## Non-Goals

- no persisted plan, real approval, artifact/manifest/payload creation, export,
  import, destination/credential resolution, connector, network, or learning
- no runtime startup, Stage 18 closure, FR-018, or physical-validation claim
