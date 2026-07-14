# FORGE Seat State

- Role: governed backend systems and durable receipts
- Classification: internal mutating worker; slot 1
- Staffing: unstaffed; prior handle `019f6100-96ab-7631-98b0-5b92909186e0`
  returned `not_found`
- Liveness: correction session completed after commit `24658090`; front is in
  exact-head integration validation
- Current assignment: CR-FORGE-001 managed-copy safe-delta candidate review
- Current task card: `docs/operations/task_cards/managed-copy-safe-delta.md`
- Branch: `codex/forge-managed-copies-safe-delta`
- Worktree: `D:\fg`
- Runtime lease: `LEASE-FORGE-001` released after `VAL-20260714-028` exit `0`;
  services and real Orb denied
- Contracts in play: `stage18_managed_copy_safe_delta_review_v1`, provisioning,
  structural isolation, tenant safe-delta policy, actor scope, drift readback
- Known traps: Windows deep paths; no raw tenant/candidate data; no production
  fixtures; no approval/export/import/learning authority
- Latest verified evidence: correction `246580901b145a7f1f59d9c85d199ffdfdf536d8`
  passed focused suite/Ruff/format/mypy/diff-check and SENTINEL/VERA affected
  review; integration head `cdfc4a23fe030b4e31dbf3b067c39d3e3daae1f8`
- Unresolved questions: rebased exact-head proof
- Current blocker: CR-005 moves local main before promotion
- Dependencies: CR-005 rebase and exact rebased re-proof
- Next action: rebase and re-prove for promotion after CR-005 commits
- Replacement instruction: verify branch/worktree, read the card and CR messages,
  and resume only the recorded next action
