# FORGE Seat State

- Role: governed backend systems and durable receipts
- Classification: internal mutating worker; slot 1
- Staffing: staffed through the current native FORGE worker session; reachability
  must be verified before depending on a delivered instruction
- Liveness: CR-FORGE-006 completed and promoted locally
- Current assignment: CR-FORGE-006 safe-delta export artifact plan
- Current task card:
  `docs/operations/task_cards/managed-copy-safe-delta-export-artifact-plan.md`
- Branch: `codex/forge-safe-delta-export-artifact-plan`
- Worktree: `D:\fg`
- Runtime lease: `LEASE-FORGE-006`; released, services and real Orb denied
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
- Next action: hold for the next bounded Stage 18 assignment after integrated
  push; do not persist an artifact or imply real approval/export authority
- Replacement instruction: verify branch/worktree, read the card and CR messages,
  and resume only the recorded next action
