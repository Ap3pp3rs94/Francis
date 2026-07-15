# FORGE Seat State

- Role: governed backend systems and durable receipts
- Classification: internal mutating worker; slot 1
- Staffing: staffed through the current native FORGE worker session; reachability
  must be verified before depending on a delivered instruction
- Liveness: CR-FORGE-003 completed and promoted; worker session available for
  reassignment after the next bounded card is committed
- Current assignment: none; next candidate is a pending safe-delta export
  authorization-request contract
- Current task card:
  `docs/operations/task_cards/managed-copy-safe-delta-export-preflight.md`
- Branch: `codex/forge-safe-delta-export-preflight`
- Worktree: `D:\fg`
- Runtime lease: `LEASE-FORGE-003`; pytest/Ruff/mypy only, services and real Orb
  denied
- Contracts in play: safe-delta review and approval v1, export-preflight v1,
  provisioning, structural isolation, current tenant policy, actor scope, drift
  readback
- Known traps: Windows deep paths; no raw tenant/candidate data; no production
  fixtures; no approval/export/import/learning authority
- Latest verified evidence: CR-FORGE-003 exact candidate `287a27c8` passed the
  full gate, all required affected reviews, and focused post-promotion checks
- Unresolved questions: none before bounded implementation
- Current blocker: none; production facts remain outside the card
- Dependencies: exact validated approval receipt and live lineage/policy fixtures
- Next action: await a bounded authorization-request task card; do not infer a
  production request, approval, destination, or retention fact
- Replacement instruction: verify branch/worktree, read the card and CR messages,
  and resume only the recorded next action
