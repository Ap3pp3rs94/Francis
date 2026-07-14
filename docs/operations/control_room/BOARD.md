# Francis Control Room Board

Updated: 2026-07-14

Canonical base observed: `4e1f4ce9d58243b310b16dd80c1446359900d9ae`

GitHub baseline:

- CodeQL run `29337593904`: success.
- CI run `29337593360`: in progress; all four matrix jobs were in pytest when
  last inspected.

## Fronts

### CR-FORGE-001 - Managed-copy safe-delta

- Agent: FORGE
- Roadmap: Phase 2, Stage 18 Managed Copies Platform
- Task card: `docs/operations/task_cards/managed-copy-safe-delta.md`
- Branch: `codex/forge-managed-copies-safe-delta`
- Worktree: `D:\Francis-worktrees\forge-managed-copies-safe-delta`
- State: `QUEUED`
- Latest reported commit: none; base only
- Validation: unverified; focused test was interrupted after a Windows path fix
- Dependencies: provision receipt, live structural-isolation receipt, tenant
  safe-delta policy, API actor-scope contract
- Blocker: exact shared-tree patch is not yet archived/applied to an isolated
  worktree
- Next action: ATLAS preserves and transfers the exact patch, then requests a
  FORGE `KICKOFF`

### CR-ARGUS-001 - Lens game observer

- Agent: ARGUS
- Roadmap: Phase 2 cross-stage Lens observation hardening
- Task card: `docs/operations/task_cards/lens-game-observer.md`
- Branch: `codex/argus-game-observer`
- Worktree: `D:\Francis-worktrees\argus-game-observer`
- State: `QUEUED`
- Latest reported commit: none; base only
- Validation: unverified
- Dependencies: game-observer runtime config, foreground-process readback,
  situation-model source contract, portable Windows typing
- Blocker: exact shared-tree patch is not yet archived/applied to an isolated
  worktree
- Next action: ATLAS preserves and transfers the exact patch, then requests an
  ARGUS `KICKOFF`

### CR-LUMEN-001 - Orb visual/choreography

- Agent: LUMEN
- Roadmap: Phase 2 cross-stage Orb interaction-fidelity hardening
- Task card: `docs/operations/task_cards/orb-visual-choreography.md`
- Branch: `codex/lumen-orb-choreography`
- Worktree: `D:\Francis-worktrees\lumen-orb-choreography`
- State: `QUEUED`
- Latest reported commit: none; base only
- Validation: unverified; no live visual proof claimed
- Dependencies: native renderer status, visual lock, overlay choreography,
  no-input/no-authority invariants
- Blocker: staged renderer/script/tests and unstaged visual-lock documentation
  are not yet archived/applied together in an isolated worktree
- Next action: ATLAS preserves both index and worktree components, transfers the
  combined patch, then requests a LUMEN `KICKOFF`

## Read-Only Review Seat

- VERA state: `READY`
- Current assignment: prepare independent acceptance mappings after worker
  commits exist
- Next action: inspect all three branch diffs after KICKOFF and challenge claims
  that lack exact test, receipt, readback, or commit evidence

## Unassigned Dirty Work

All untracked paths outside the three task-card scopes are `unverified` and
unassigned. They remain in `D:\Francis` and must not be cleaned, relocated, or
absorbed into a front without a new task card or operator decision.
