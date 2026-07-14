# ARGUS Seat State

- Role: observation, instrumentation, and readback truth
- Classification: internal mutating worker; slot 2
- Staffing: active agent `019f6100-97e3-7e23-a5c7-255ec738fd9b`
- Liveness: live/controllable in `CR-20260714-003`; interruption directive
  accepted and known pytest PIDs absent
- Current assignment: CR-ARGUS-001 Lens game observer
- Current task card: `docs/operations/task_cards/lens-game-observer.md`
- Branch: `codex/argus-game-observer`
- Worktree: `D:\Francis-worktrees\argus-game-observer`
- Runtime lease: `LEASE-ARGUS-001`; services, watcher, and real Orb denied
- Contracts in play: runtime config, game observation, situation-model readback,
  frame/receipt/process/model lineage, local-only/no-input governance
- Known traps: use the portable `getattr(ctypes, "WinDLL", None)` pattern from
  `adcb62a2`; Ubuntu CI enforces it; do not launch watchers or touch live Lens
- Latest verified evidence: clean commit `2e454ba5bc4a9e5f629da463be5696350703fcb2`;
  `VAL-20260714-007` diff-check pass; `VAL-20260714-003` is
  `INTERRUPTED_KNOWN_REMEDIATION`; no live action
- Unresolved questions: strict blocked-v2 projection plus bounded teaching
  status/IDs/timestamps/counts/text/blockers/review semantics
- Current blocker: `MSG-20260714-013`/`016` require malformed blocked/teaching
  projection remediation
- Dependencies: committed card sync; MERIDIAN/SENTINEL/HARBOR/VERA review
- Next action: execute remediation cycle one and return the first focused-green
  integration candidate; report only a new hash or contract/external blocker
- Replacement instruction: verify branch/worktree, read the card and CR messages,
  and resume only the recorded next action
