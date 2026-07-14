# FORGE Seat State

- Role: governed backend systems and durable receipts
- Classification: internal mutating worker; slot 1
- Staffing: active agent `019f6100-96ab-7631-98b0-5b92909186e0`
- Liveness: current cycle `CR-20260714-002`
- Current assignment: CR-FORGE-001 managed-copy safe-delta candidate review
- Current task card: `docs/operations/task_cards/managed-copy-safe-delta.md`
- Branch: `codex/forge-managed-copies-safe-delta`
- Worktree: `D:\Francis-worktrees\forge-managed-copies-safe-delta`
- Runtime lease: `LEASE-FORGE-001`; services and real Orb denied
- Contracts in play: `stage18_managed_copy_safe_delta_review_v1`, provisioning,
  structural isolation, tenant safe-delta policy, actor scope, drift readback
- Known traps: Windows deep paths; no raw tenant/candidate data; no production
  fixtures; no approval/export/import/learning authority
- Latest verified evidence: KICKOFF at `8c84dc4e`; exact transferred diff; no
  staged changes; transfer `git diff --check` passed
- Unresolved questions: verify short receipt path collision behavior and malformed
  existing receipt fail-closed behavior
- Current blocker: malformed/colliding files, unvalidated latest readback,
  drift/exclusive-create behavior, and focused end-to-end path remain unproven
- Dependencies: committed card sync; MERIDIAN/SENTINEL/HARBOR/VERA/ARCHIVIST
  review after a worker commit
- Next action: add failing tests for every routed VERA finding before the
  smallest fail-closed correction; commit locally, do not push
- Replacement instruction: verify branch/worktree, read the card and CR messages,
  and resume only the recorded next action
