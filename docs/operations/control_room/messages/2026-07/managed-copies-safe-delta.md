# Managed Copies / Safe Delta Messages - 2026-07

## MSG-20260714-004

Legacy ID: `CR-MSG-0002`

FROM: FORGE
TO: ATLAS
FRONT: CR-FORGE-001 managed-copy safe-delta candidate review
MESSAGE TYPE: KICKOFF
TASK CARD: `docs/operations/task_cards/managed-copy-safe-delta.md`
BRANCH: `codex/forge-managed-copies-safe-delta`
WORKTREE: `D:\Francis-worktrees\forge-managed-copies-safe-delta`
CURRENT COMMIT: `8c84dc4e972b7921e9204e62f7cd655bd3ede037`
CLAIM: Assignment accepted; transferred diff inspected read-only; no approval,
production-route, or live-process mutation occurred.
EVIDENCE: four modified tracked files plus untracked
`src/francis/managed_copy_safe_delta.py`; no staged changes. Malformed JSON can
be overwritten, and a different full fingerprint sharing the 16-character path
prefix can be mistaken for `already_reviewed`.
CONTRACTS AFFECTED: `stage18_managed_copy_safe_delta_review_v1`, provision and
structural-isolation lineage, tenant policy, actor scope, POST and GET readback.
DEPENDENCIES: valid source receipts, tenant policy, independent review.
BLOCKER OR QUESTION: collision, malformed receipt, and focused end-to-end
behavior are unverified.
REQUESTED ACTION: retain FORGE ownership and route fail-closed remediation.
NEXT SMALLEST TRUTHFUL STEP: add malformed/collision tests before correction.
