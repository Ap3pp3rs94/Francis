# LUMEN Seat State

- Role: Orb interaction, visual behavior, and choreography
- Current assignment: CR-LUMEN-001 Orb visual/choreography
- Current task card: `docs/operations/task_cards/orb-visual-choreography.md`
- Branch: `codex/lumen-orb-choreography`
- Worktree: `D:\Francis-worktrees\lumen-orb-choreography`
- Contracts in play: native renderer status, visual lock, overlay choreography,
  click-through/no-activate behavior, bounded messages, no-input authority
- Known traps: staged code/tests plus unstaged visual-lock documentation must stay
  together; visuals cannot imply action completion; never touch the live Orb
- Latest verified evidence: no worker commit; shared-tree diff only, unverified
- Unresolved questions: map each visual transition to validated state and identify
  any effect wording that could overclaim governed action completion
- Current blocker: worktree and combined patch transfer pending
- Dependencies: ATLAS preservation/assignment; later VERA review; consult ARGUS
  only through recorded Control Room messages if observer fields are needed
- Next action: after KICKOFF, inspect the transferred state-to-choreography mapping
  and run focused static contract tests
- Replacement instruction: verify branch/worktree, read the card and CR messages,
  and resume only the recorded next action
