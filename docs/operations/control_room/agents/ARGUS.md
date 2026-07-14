# ARGUS Seat State

- Role: observation, instrumentation, and readback truth
- Current assignment: CR-ARGUS-001 Lens game observer
- Current task card: `docs/operations/task_cards/lens-game-observer.md`
- Branch: `codex/argus-game-observer`
- Worktree: `D:\Francis-worktrees\argus-game-observer`
- Contracts in play: runtime config, game observation, situation-model readback,
  frame/receipt/process/model lineage, local-only/no-input governance
- Known traps: use the portable `getattr(ctypes, "WinDLL", None)` pattern from
  `adcb62a2`; Ubuntu CI enforces it; do not launch watchers or touch live Lens
- Latest verified evidence: no worker commit; shared-tree diff only, unverified
- Unresolved questions: confirm every new process/window readback is portable and
  every situation-model projection rejects malformed observer state
- Current blocker: worktree and patch transfer pending
- Dependencies: ATLAS preservation/assignment; later VERA review
- Next action: after KICKOFF, inspect transferred diff and map each added field to
  a strict producer/consumer test
- Replacement instruction: verify branch/worktree, read the card and CR messages,
  and resume only the recorded next action
