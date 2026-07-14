# Francis Control Room Board

Updated: 2026-07-14

Sync cycle: `CR-20260714-002`

Canonical local/remote base observed before this sync:
`8c84dc4e972b7921e9204e62f7cd655bd3ede037`.

Push state: operator-gated; this sync is local only unless separately approved.

Operator-gated decisions are indexed in `OPERATOR_QUEUE.md`; exact evidence is
indexed in `EVIDENCE_INDEX.md`.

GitHub baseline:

- CodeQL run `29337593904`: success.
- CI run `29337593360`: cancelled by the Control Room baseline push.
- Control Room head CI `29340258995`: in progress.
- Control Room head CodeQL `29340258957`: success.
- Local `scripts/check.ps1`: first run failed at pytest collection because the
  shared venv lacked the CI-required `bridge` extra and `jsonschema`; environment
  was resynced with the exact CI extras and an exact-head rerun is pending.

## Fronts

### CR-FORGE-001 - Managed-copy safe-delta

- Agent: FORGE
- Roadmap: Phase 2, Stage 18 Managed Copies Platform
- Task card: `docs/operations/task_cards/managed-copy-safe-delta.md`
- Branch: `codex/forge-managed-copies-safe-delta`
- Worktree: `D:\Francis-worktrees\forge-managed-copies-safe-delta`
- State: `ACTIVE`
- Latest reported commit: none; base only
- Validation: unverified; focused test was interrupted after a Windows path fix
- Dependencies: provision receipt, live structural-isolation receipt, tenant
  safe-delta policy, API actor-scope contract
- Blocker: malformed receipt content and filename-prefix collisions do not yet
  fail closed; focused end-to-end validation is missing
- Next action: FORGE runs the focused test, adds collision/malformed receipt
  plus invalid-latest/drift/exclusive-create coverage, then makes the smallest
  fail-closed correction
- Runtime lease: `LEASE-FORGE-001`; no service or live Orb access permitted

### CR-ARGUS-001 - Lens game observer

- Agent: ARGUS
- Roadmap: Phase 2 cross-stage Lens observation hardening
- Task card: `docs/operations/task_cards/lens-game-observer.md`
- Branch: `codex/argus-game-observer`
- Worktree: `D:\Francis-worktrees\argus-game-observer`
- State: `ACTIVE`
- Latest reported commit: none; base only
- Validation: transfer `git diff --check` passed; portable WinDLL scan passed;
  focused/full acceptance remains unverified
- Dependencies: game-observer runtime config, foreground-process readback,
  situation-model source contract, portable Windows typing
- Blocker: new mandatory governance fields currently reuse v1 observation and
  heartbeat versions without explicit legacy compatibility; identity/lineage
  validation and model override boundaries remain incomplete
- Next action: ARGUS adds v1 regression coverage, introduces a new producer
  version for the expanded contract, and preserves conservative legacy handling
- Runtime lease: `LEASE-ARGUS-001`; no watcher/service/live Orb access permitted

### CR-LUMEN-001 - Orb right-click delivery / visual-lock alignment

- Agent: LUMEN
- Roadmap: Phase 2 cross-stage Orb interaction-fidelity hardening
- Task card: `docs/operations/task_cards/orb-visual-choreography.md`
- Branch: `codex/lumen-orb-choreography`
- Worktree: `D:\Francis-worktrees\lumen-orb-choreography`
- State: `ACTIVE`
- Latest reported commit: none; base only
- Validation: transfer `git diff --check` passed; acceptance tests remain
  unverified; no live visual proof claimed
- Dependencies: native renderer status, right-click request sequence/queue
  contract, visual lock, no-input/no-authority invariants
- Blocker: transferred patch must prove ordered/loss-resistant queue delivery and
  fail-closed readback, bounds, TTL, deduplication, and all ring-count truth
  surfaces; broader choreography is outside this card
- Next action: LUMEN maps queue states to focused tests, then validates/remediates
  without live activation
- Runtime lease: `LEASE-LUMEN-001`; compile-only native build, no launch

## Review State

- VERA state: `RESPONDED`
- Evidence: `MSG-20260714-008` and
  `reviews/VERA/CR-20260714-preflight.md`
- Disposition: all three fronts remain `ACTIVE`; no worker commit is review-ready
- Next action: review exact worker commits only after remediation evidence exists

Specialists are durable but currently unstaffed. Their concrete questions are in
the task cards. CLAUDE is `UNVERIFIED`; no external audit is simulated.

## Runtime Leases

`control_room/RUNTIME_LEASES.md` records three unique idle leases. All current
cards deny persistent services and the operator-visible Orb. Default ports remain
reserved; an unknown listener on `5173` is out of scope and must not be killed.

## Unassigned Dirty Work

All untracked paths outside the three task-card scopes are `unverified` and
unassigned. They remain in `D:\Francis` and must not be cleaned, relocated, or
absorbed into a front without a new task card or operator decision.
