# ARGUS Seat State

- Role: observation, instrumentation, and readback truth
- Classification: internal mutating worker; slot 2
- Staffing: active agent `019f6100-97e3-7e23-a5c7-255ec738fd9b`
- Liveness: current cycle `CR-20260714-002`
- Current assignment: CR-ARGUS-001 Lens game observer
- Current task card: `docs/operations/task_cards/lens-game-observer.md`
- Branch: `codex/argus-game-observer`
- Worktree: `D:\Francis-worktrees\argus-game-observer`
- Runtime lease: `LEASE-ARGUS-001`; services, watcher, and real Orb denied
- Contracts in play: runtime config, game observation, situation-model readback,
  frame/receipt/process/model lineage, local-only/no-input governance
- Known traps: use the portable `getattr(ctypes, "WinDLL", None)` pattern from
  `adcb62a2`; Ubuntu CI enforces it; do not launch watchers or touch live Lens
- Latest verified evidence: KICKOFF at `8c84dc4e`; exact five-file transfer;
  portable WinDLL scan passed; no live action
- Unresolved questions: exact legacy v1 conservative projection fields must be
  fixed in tests before implementation
- Current blocker: expanded fields reuse v1 contracts; identity/lineage checks,
  model override boundary, and non-Windows evidence remain incomplete
- Dependencies: committed card sync; MERIDIAN/SENTINEL/HARBOR/VERA review
- Next action: add legacy/identity/model-boundary/non-Windows tests, then make the
  smallest versioned fail-closed correction; commit locally, do not push
- Replacement instruction: verify branch/worktree, read the card and CR messages,
  and resume only the recorded next action
