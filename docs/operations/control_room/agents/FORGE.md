# FORGE Seat State

- Role: governed backend systems and durable receipts
- Classification: internal mutating worker; slot 1
- Staffing: staffed through the current native FORGE worker session; reachability
  must be verified before depending on a delivered instruction
- Liveness: CR-FORGE-006 promoted; CR-FORGE-007 assignment ready
- Current assignment: CR-FORGE-007 rogue detection assessment
- Current task card:
  `docs/operations/task_cards/managed-copy-rogue-detection-assessment.md`
- Branch: `codex/forge-rogue-detection-assessment`
- Worktree: `D:\fg`
- Runtime lease: `LEASE-FORGE-007`; test-only, services and real Orb denied
- Contracts in play: safe-delta review and approval v1, export-preflight v1,
  provisioning, structural isolation, current tenant policy, actor scope, drift
  readback
- Known traps: Windows deep paths; no raw tenant/candidate data; no production
  fixtures; no approval/export/import/learning authority
- Latest verified evidence: CR-FORGE-006 exact candidate `2673cd5e` passed
  focused/card/static validation, post-promotion route/matrix checks, and all
  required affected reviews
- Unresolved questions: none before bounded implementation
- Current blocker: none; production facts remain outside the card
- Dependencies: exact validated approval receipt and live lineage/policy fixtures
- Next action: implement the bounded assessment receipt/readback without any
  containment, recovery, or production-incident claim
- Replacement instruction: verify branch/worktree, read the card and CR messages,
  and resume only the recorded next action
