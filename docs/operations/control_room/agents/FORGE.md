# FORGE Seat State

- Role: governed backend systems and durable receipts
- Classification: internal mutating worker; slot 1
- Staffing: staffed through the current native FORGE worker session; reachability
  must be verified before depending on a delivered instruction
- Liveness: CR-FORGE-004 completed and promoted; CR-FORGE-005 assignment ready
- Current assignment: CR-FORGE-005 safe-delta export authorization decision
- Current task card:
  `docs/operations/task_cards/managed-copy-safe-delta-export-authorization-decision.md`
- Branch: `codex/forge-safe-delta-export-authorization-decision`
- Worktree: `D:\fg`
- Runtime lease: `LEASE-FORGE-005`; pytest/Ruff/mypy only, services and real Orb
  denied
- Contracts in play: safe-delta review and approval v1, export-preflight v1,
  provisioning, structural isolation, current tenant policy, actor scope, drift
  readback
- Known traps: Windows deep paths; no raw tenant/candidate data; no production
  fixtures; no approval/export/import/learning authority
- Latest verified evidence: CR-FORGE-004 exact candidate `44048d85` passed the
  full gate and all required reviews; `f3cc8c7c` passed focused post-promotion
  validation on the real main path
- Unresolved questions: none before bounded implementation
- Current blocker: none; production facts remain outside the card
- Dependencies: exact validated approval receipt and live lineage/policy fixtures
- Next action: implement the fixture-backed decision contract; do not create or
  imply a real approval, production decision, destination, or export action
- Replacement instruction: verify branch/worktree, read the card and CR messages,
  and resume only the recorded next action
