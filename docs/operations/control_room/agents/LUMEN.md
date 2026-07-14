# LUMEN Seat State

- Role: Orb interaction, visual behavior, and choreography
- Classification: internal mutating worker; slot 3
- Staffing: resumable agent `019f6100-9898-7353-9359-ed4727e2a4cb`
- Liveness: completed/released; front parked in `CR-20260714-004`
- Current assignment: CR-LUMEN-001 Orb right-click delivery / visual-lock alignment
- Current task card: `docs/operations/task_cards/orb-visual-choreography.md`
- Branch: `codex/lumen-orb-choreography`
- Worktree: `D:\FWT\lumen`
- Runtime lease: `LEASE-LUMEN-001`; compile-only, services/launch/real Orb denied
- Contracts in play: native renderer status/right-click request, overlay request
  queue/readback, visual-lock ring count, click-through/no-activate behavior,
  bounded messages, no-input authority
- Known traps: staged code/tests plus unstaged visual-lock documentation must stay
  together; visuals cannot imply action completion; never touch the live Orb
- Latest verified evidence: clean rebased commit
  `600704383d71c072b29a29e4061c86977f38a245`; `VAL-20260714-011` focused/build
  pass; all exact reviewers rejected; no live action
- Unresolved questions: durable restart-safe sequence allocator and producer
  failure/outcome readback ownership
- Current blocker: both guarantees require a schema/file owner outside the card
- Dependencies: task-card reassignment before any new edit or validation
- Next action: remain parked; preserve branch, moved worktree, and runtime lease
- Replacement instruction: verify branch/worktree, read the card and CR messages,
  and resume only the recorded next action
