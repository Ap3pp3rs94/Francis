# FORGE Seat State

- Role: governed backend systems and durable receipts
- Current assignment: CR-FORGE-001 managed-copy safe-delta candidate review
- Current task card: `docs/operations/task_cards/managed-copy-safe-delta.md`
- Branch: `codex/forge-managed-copies-safe-delta`
- Worktree: `D:\Francis-worktrees\forge-managed-copies-safe-delta`
- Contracts in play: `stage18_managed_copy_safe_delta_review_v1`, provisioning,
  structural isolation, tenant safe-delta policy, actor scope, drift readback
- Known traps: Windows deep paths; no raw tenant/candidate data; no production
  fixtures; no approval/export/import/learning authority
- Latest verified evidence: no worker commit; shared-tree diff only, unverified
- Unresolved questions: verify short receipt path collision behavior and malformed
  existing receipt fail-closed behavior
- Current blocker: worktree and patch transfer pending
- Dependencies: ATLAS preservation/assignment; later VERA review
- Next action: after KICKOFF, inspect transferred diff and run the single focused
  end-to-end test before making further changes
- Replacement instruction: verify branch/worktree, read the card and CR messages,
  and resume only the recorded next action
