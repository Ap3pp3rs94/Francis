# Task Card: Managed-Copy Safe-Delta Candidate Review

Task ID: `CR-FORGE-001`

Assigned seat: FORGE

Status: `QUEUED` pending patch preservation and worktree creation

## Objective

Finish and prove the bounded Stage 18 hash-only safe-delta candidate-review path
without approving, exporting, importing, or learning from tenant data.

## Branch And Worktree

- Branch: `codex/forge-managed-copies-safe-delta`
- Worktree: `D:\Francis-worktrees\forge-managed-copies-safe-delta`
- Base: current `origin/main` at assignment time
- Never work in `D:\Francis`.

## Files In Scope

- `src/francis/managed_copy_safe_delta.py`
- `src/francis/managed_copies.py`
- `src/francis/api/routes/managed_copies.py`
- `tests/test_api_managed_copies.py`
- `tests/test_api_contract_chat_ui.py`
- `tests/test_api_mutating_route_authority_matrix.py` only if the route matrix
  needs a directly corresponding assertion

## Do Not Touch

- Lens, Orb, renderer, overlay, game-observer, and live-runtime files/processes
- `docs/operations/COMPLETION_LEDGER.md` unless the card closes a canonical gate
  with evidence and the manager/operator approves the ledger update
- production data or real approvals
- unrelated tracked, staged, or untracked files
- governance scope definitions beyond the existing
  `managed_copies.safe_delta.write` boundary

## Contracts To Compose With

- `stage18_managed_copy_safe_delta_review_v1`
- managed-copy provisioning receipt and live structural-isolation receipt
- tenant safe-delta policy: raw private pooling denied and operator review required
- exact dry-run fingerprint plus explicit confirmation
- API actor-scope enforcement and mutating-route authority matrix
- fail-closed readback when provision, isolation, or tenant policy drifts

## Acceptance Criteria

- The candidate schema stores only approved hashes, booleans, bounded counts, and
  enums; unknown or raw fields fail closed and are not echoed or persisted.
- A matching confirmed dry run records one tenant-local idempotent receipt.
- The receipt path works under the repository's long Windows pytest data root;
  filename-prefix collision or malformed existing content fails closed.
- The receipt explicitly leaves approval, export, import, learning, execution,
  mutation, registry, memory, and tenant-state writes disabled.
- GET readback validates receipts and reports live source-boundary drift.
- Existing Stage 17 prerequisite and unscoped-actor denial behavior remains true.
- Production source-loaded readback remains empty; no fixture is written outside
  test data roots.
- Tests change in step with code.

Required commands, all with exit code 0:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_api_managed_copies.py::test_managed_copy_creation_plan_records_redacted_lineage_bound_receipt -q
.venv\Scripts\python.exe -m pytest tests/test_api_managed_copies.py tests/test_api_contract_chat_ui.py tests/test_api_mutating_route_authority_matrix.py -q
.venv\Scripts\python.exe -m ruff check src/francis/managed_copy_safe_delta.py src/francis/managed_copies.py src/francis/api/routes/managed_copies.py tests/test_api_managed_copies.py tests/test_api_contract_chat_ui.py tests/test_api_mutating_route_authority_matrix.py
.venv\Scripts\python.exe -m ruff format --check src/francis/managed_copy_safe_delta.py src/francis/managed_copies.py src/francis/api/routes/managed_copies.py tests/test_api_managed_copies.py tests/test_api_contract_chat_ui.py tests/test_api_mutating_route_authority_matrix.py
.venv\Scripts\python.exe -m mypy src/francis/managed_copy_safe_delta.py src/francis/managed_copies.py src/francis/api/routes/managed_copies.py
git diff --check origin/main...HEAD
.\scripts\check.ps1
```

## Worker Receipt

Return the commit hash, changed files, exact command results, remaining risks, and
an explicit statement that no approval/export/learning/runtime action occurred.
