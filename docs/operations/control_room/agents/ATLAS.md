# ATLAS Seat State

- Role: Build Manager and Francis Control Room chair
- Classification: internal manager/integrator
- Staffing: active local session
- Liveness: current sync cycle `CR-20260714-005`
- Current assignment: keep Stage 18 critical path moving through worker
  remediation, exact validation, specialist review, and local integration
- Current task card: none; ATLAS owns management/integration, not a feature front
- Branch: `main`
- Worktree: `D:\Francis`
- Contracts in play: repository workflow, Control Room protocol, ledger truth,
  three active task-card boundaries
- Known traps: unknown untracked work; operator-gated pushes; local-main Control
  Room commits move worker bases; no live Orb changes; no fake Stage 18 facts
- Latest verified evidence: CR-005 cycle base `6e883d1d` on local `main`;
  remote CodeQL `29340258957` and CI `29340258995` succeeded for `8c84dc4e`;
  full gate `VAL-20260714-028` passed with explicit exit `0` on exact integration
  head `cdfc4a23`
- Latest management evidence: external throughput response
  `reviews/ATLAS_EXTERNAL_THROUGHPUT_CHALLENGE_2026-07-14.txt`, ARCHIVIST
  precommit review, and `CR-DEC-0011` two-cycle/one-open-sync bounds
- Unresolved questions: goal controller rejected replacement of the already-
  blocked old goal; no product work is blocked by that tool-state mismatch
- Current blocker: post-CR-005 rebased proof; ARGUS and LUMEN remain separately
  parked on task-card ownership gaps
- Dependencies: revised cards before ARGUS/LUMEN edits; exact-head validation and
  affected review before promotion
- Next action: finalize and commit CR-005, freeze local `main`, then rebase and
  re-prove FORGE
- Replacement instruction: follow the compact startup order in `SESSION_BRIEF.md`;
  verify live state first and load deeper records only when the next decision
  requires them
