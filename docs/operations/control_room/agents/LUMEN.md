# LUMEN Seat State

- Role: Orb interaction, visual behavior, and choreography
- Classification: internal mutating worker; slot 3
- Staffing: active agent `019f6100-9898-7353-9359-ed4727e2a4cb`
- Liveness: live/controllable in `CR-20260714-003`; interruption directive
  accepted and known pytest PIDs absent
- Current assignment: CR-LUMEN-001 Orb right-click delivery / visual-lock alignment
- Current task card: `docs/operations/task_cards/orb-visual-choreography.md`
- Branch: `codex/lumen-orb-choreography`
- Worktree: `D:\Francis-worktrees\lumen-orb-choreography`
- Runtime lease: `LEASE-LUMEN-001`; compile-only, services/launch/real Orb denied
- Contracts in play: native renderer status/right-click request, overlay request
  queue/readback, visual-lock ring count, click-through/no-activate behavior,
  bounded messages, no-input authority
- Known traps: staged code/tests plus unstaged visual-lock documentation must stay
  together; visuals cannot imply action completion; never touch the live Orb
- Latest verified evidence: clean commit `a1b2c60bced10506cfd53bdfb97aa8b491656cea`;
  `VAL-20260714-008` diff-check pass; `VAL-20260714-004` is
  `INTERRUPTED_KNOWN_REMEDIATION`; HARBOR review; no live action
- Unresolved questions: non-replacing publication, one-publication-per-gesture,
  bounded discovery bytes/count, and strict per-cycle deferred backlog
- Current blocker: `MSG-20260714-014`/`017` and HARBOR review require queue
  remediation; native compile and full card acceptance remain pending
- Dependencies: committed card sync; SENTINEL/HARBOR/VERA/ARCHIVIST review; no
  ARGUS dependency for this bounded patch
- Next action: execute remediation cycle one, focused checks, and compile-only
  validation; report only a new hash or contract/external blocker
- Replacement instruction: verify branch/worktree, read the card and CR messages,
  and resume only the recorded next action
