# ARGUS Seat State

- Role: observation, instrumentation, and readback truth
- Classification: internal mutating worker; slot 2
- Staffing: resumable agent `019f6100-97e3-7e23-a5c7-255ec738fd9b`
- Liveness: completed/released; front parked in `CR-20260714-004`
- Current assignment: CR-ARGUS-001 Lens game observer
- Current task card: `docs/operations/task_cards/lens-game-observer.md`
- Branch: `codex/argus-game-observer`
- Worktree: `D:\Francis-worktrees\argus-game-observer`
- Runtime lease: `LEASE-ARGUS-001`; services, watcher, and real Orb denied
- Contracts in play: runtime config, game observation, situation-model readback,
  frame/receipt/process/model lineage, local-only/no-input governance
- Known traps: use the portable `getattr(ctypes, "WinDLL", None)` pattern from
  `adcb62a2`; Ubuntu CI enforces it; do not launch watchers or touch live Lens
- Latest verified evidence: clean rebased commit
  `683134a7cccd6b4dd1b1cd1604d2641615f07307`; `VAL-20260714-009` focused pass;
  VERA/SENTINEL rejected promotion; no live action
- Unresolved questions: apprenticeship v2 consumption, strict legacy heartbeat
  projection, and producer receipt-rotation readiness
- Current blocker: required teaching-consumer files are outside the current card
- Dependencies: task-card scope reassignment before any new edit or validation
- Next action: remain parked; preserve branch and runtime lease
- Replacement instruction: verify branch/worktree, read the card and CR messages,
  and resume only the recorded next action
