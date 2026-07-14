# ATLAS Seat State

- Role: Build Manager and Francis Control Room chair
- Classification: internal manager/integrator
- Staffing: active local session
- Liveness: current sync cycle `CR-20260714-004`
- Current assignment: keep Stage 18 critical path moving through worker
  remediation, exact validation, specialist review, and local integration
- Current task card: none; ATLAS owns management/integration, not a feature front
- Branch: `main`
- Worktree: `D:\Francis`
- Contracts in play: repository workflow, Control Room protocol, ledger truth,
  three active task-card boundaries
- Known traps: unknown untracked work; operator-gated pushes; local-main Control
  Room commits move worker bases; no live Orb changes; no fake Stage 18 facts
- Latest verified evidence: Control Room commit `d5516a54` on local `main`;
  CodeQL `29340258957` success for prior head; CI `29340258995` in progress;
  exact-head local gate failed mypy as `MSG-20260714-010`; Typer import repaired;
  exact-head pytest `VAL-20260714-001` running; later static-pass receipt invalid
- Latest management evidence: external throughput response
  `reviews/ATLAS_EXTERNAL_THROUGHPUT_CHALLENGE_2026-07-14.txt`, ARCHIVIST
  precommit review, and `CR-DEC-0011` two-cycle/one-open-sync bounds
- Unresolved questions: goal controller rejected replacement of the already-
  blocked old goal; no product work is blocked by that tool-state mismatch
- Current blocker: no project-level blocker; all three fronts have assigned
  remediation and distinct exact-head suites running
- Dependencies: worker results/remediation, exact reviewer evidence, GitHub CI
- Next action: collect suite exits and structured heartbeats, route remediation
  cycle one, and keep CR-003 open until the first candidate is review-ready;
  commit it once, then freeze local main for promotion
- Replacement instruction: read the session brief, board, decisions, message log,
  runtime leases, integration queue, message shards, and all seat files; verify
  every recorded fact before acting
