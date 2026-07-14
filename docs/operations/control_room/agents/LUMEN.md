# LUMEN Seat State

- Role: Orb interaction, visual behavior, and choreography
- Classification: internal mutating worker; slot 3
- Staffing: active agent `019f6100-9898-7353-9359-ed4727e2a4cb`
- Liveness: current cycle `CR-20260714-002`
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
- Latest verified evidence: KICKOFF at `8c84dc4e`; five in-scope files;
  `git diff --check` exit 0; no live action
- Unresolved questions: prove bounded numeric ordering, TTL, deduplication,
  backlog/readback outcomes, and ring parity including host manifest
- Current blocker: focused acceptance tests and full branch gate are unverified
- Dependencies: committed card sync; SENTINEL/HARBOR/VERA/ARCHIVIST review; no
  ARGUS dependency for this bounded patch
- Next action: add fail-closed queue/ring tests, remediate, compile without
  `-Run`/`-Launch`, commit locally, and do not push
- Replacement instruction: verify branch/worktree, read the card and CR messages,
  and resume only the recorded next action
