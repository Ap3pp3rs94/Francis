# Task Card: Managed-Copy Safe-Delta Candidate Review

Task ID: `CR-FORGE-001`

Assigned seat: FORGE

Status: `REMEDIATION_REQUIRED` at `90c4dbe0` after ATLAS and SENTINEL pre-review

## Objective

Finish and prove the bounded Stage 18 hash-only safe-delta candidate-review path
without approving, exporting, importing, or learning from tenant data.

## Branch And Worktree

- Branch: `codex/forge-managed-copies-safe-delta`
- Worktree: `D:\Francis-worktrees\forge-managed-copies-safe-delta`
- Transfer source base: `8c84dc4e972b7921e9204e62f7cd655bd3ede037`
- First candidate parent: `d5516a54e9b939b2ae076f3be7b338b6cd2ed762`
- Final review base: exact committed local `main` head after Control Room sync
- Never work in `D:\Francis`.

## RUNTIME ISOLATION

- Lease: `LEASE-FORGE-001` in `control_room/RUNTIME_LEASES.md`
- `FRANCIS_DATA_DIR`: `D:\Francis-runtime-leases\forge-managed-copies-safe-delta\data`
- Pytest retention: worktree-local `data\test_runs\pytest`; unique to this
  worktree and governed by `tests/conftest.py`
- API / overlay / frontend ports: `18001` / `18781` / `15171`
- Permitted services: none; pytest/Ruff/mypy processes only
- Operator-visible Orb: denied
- Startup command: prohibited; tests create only isolated temporary state
- Shutdown: verify no front-owned persistent process or listener before review
- Cleanup: preserve test logs/receipts; remove only proven front-owned temporary
  state; never kill an unknown process

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
- Idempotence requires the complete stored fingerprint and validated contract,
  not only a shortened filename. Receipt creation cannot overwrite an existing
  unknown or colliding file.
- The receipt explicitly leaves approval, export, import, learning, execution,
  mutation, registry, memory, and tenant-state writes disabled.
- GET readback validates every candidate before selecting or exposing the latest
  receipt, redacts invalid content, and reports live source-boundary drift.
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
git diff --check main...HEAD
.\scripts\check.ps1
```

## Mandatory Review Questions

- MERIDIAN: does the receipt/readback compose with the existing Stage 18
  provision and structural-isolation contracts without a new ADR?
- SENTINEL: do collision, redaction, tenant isolation, and authority boundaries
  fail closed without creating approval/export/learning authority?
- HARBOR: does the shortened path remain safe on Windows and portable in CI, and
  is the exact rebased candidate the head tested?
- VERA: does every acceptance criterion map to a direct test and exact command?
- ARCHIVIST: can every readback claim be traced to a validated receipt and live
  source-boundary check without raw customer data?

## Routed Remediation

- Recompute candidate checks from persisted values; stored `ready` flags are not
  independent validation.
- Enforce an exact receipt/governance schema or return a strict safe projection.
- Bind receipt ID, timestamp/latest ordering, filename prefix, and containing
  tenant directory to the validated fingerprint and live provision lineage.
- Scope latest selection and invalidity to exact tenant/copy/provision/isolation
  lineage so one tenant cannot obscure another tenant's valid readback.
- Reuse structural isolation's canonical path guard rather than creating a
  competing tenant-path boundary. Request a card scope revision before touching
  `managed_copy_isolation.py` or adding a shared path module.
- Align the blocked readback's expected receipt path with the actual tenant-local
  `receipts/sd/*.json` contract.
- Redact unknown `signal_class` and `direction` values on blocked responses.
- Prove `receipts/sd` cannot be redirected by a symlink or Windows junction
  below the structurally verified parent.
- Add direct tests for every item above before requesting another review.

Evidence: `MSG-20260714-012`, `MSG-20260714-015`,
`docs/operations/control_room/reviews/SENTINEL/CR-20260714-forge-preflight.md`,
and `docs/operations/control_room/reviews/MERIDIAN/CR-20260714-forge-preflight.md`.

## Worker Receipt

Return the commit hash, changed files, exact command results, remaining risks, and
an explicit statement that no approval/export/learning/runtime action occurred.
