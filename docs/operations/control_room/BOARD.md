# Francis Control Room Board

Updated: 2026-07-14

Sync cycle: `CR-20260714-005`

Cycle-start local main:
`6e883d1d19a18d157ed99799d598a7f8285771fd`.

Remote `origin/main` observed during this sync:
`8c84dc4e972b7921e9204e62f7cd655bd3ede037`.

Push state: operator-gated; this sync is local only unless separately approved.

Operator-gated decisions are indexed in `OPERATOR_QUEUE.md`; exact evidence is
indexed in `EVIDENCE_INDEX.md`.

GitHub baseline:

- Remote CI run `29340258995` for `8c84dc4e`: success.
- Remote CodeQL run `29340258957` for `8c84dc4e`: success.
- Local `scripts/check.ps1` on historical head `d5516a54` did not produce a full
  pass: its initial run failed on a corrupt local Typer payload, and the later
  baseline pytest `VAL-20260714-001` was interrupted for integration priority.
- Full gate `VAL-20260714-028` passed with explicit exit `0` on exact integration
  head `cdfc4a23` in `D:\fg`. No full-gate claim exists for CR-005 parent
  `6e883d1d` or either parked worker head.

## Fronts

### CR-FORGE-001 - Managed-copy safe-delta

- Agent: FORGE
- Roadmap: Phase 2, Stage 18 Managed Copies Platform
- Task card: `docs/operations/task_cards/managed-copy-safe-delta.md`
- Branch: `codex/forge-managed-copies-safe-delta`
- Worktree: `D:\fg`
- State: `READY_FOR_PROMOTION`; pre-rebase exact integration gate passed
- Latest verified worker commit: `246580901b145a7f1f59d9c85d199ffdfdf536d8`
- Integration head: `cdfc4a23fe030b4e31dbf3b067c39d3e3daae1f8`
- Validation: correction focused suite/Ruff/format/mypy/diff-check passed;
  `VAL-20260714-028` full gate passed with explicit exit `0`
- Dependencies: provision receipt, live structural-isolation receipt, tenant
  safe-delta policy, API actor-scope contract
- Blocker: post-CR-005 rebase and exact rebased-head proof remain outstanding
- Next action: commit CR-005, freeze local main, rebase, and re-prove the exact
  promotion head
- Runtime lease: `LEASE-FORGE-001`; no service or live Orb access permitted

### CR-ARGUS-001 - Lens game observer

- Agent: ARGUS
- Roadmap: Phase 2 cross-stage Lens observation hardening
- Task card: `docs/operations/task_cards/lens-game-observer.md`
- Branch: `codex/argus-game-observer`
- Worktree: `D:\Francis-worktrees\argus-game-observer`
- State: `BLOCKED`; promotion rejected pending task-card scope reassignment
- Latest verified worker commit: `683134a7cccd6b4dd1b1cd1604d2641615f07307`
- Validation: `VAL-20260714-007` diff-check passed; full pytest
  `VAL-20260714-003` was `INTERRUPTED_KNOWN_REMEDIATION`; no pass/fail claim
- Dependencies: game-observer runtime config, foreground-process readback,
  situation-model source contract, portable Windows typing
- Blocker: the v2 producer is incompatible with the v1-only apprenticeship
  recorder; legacy heartbeat redaction and stale receipt-lineage readiness also
  fail review
- Next action: park until scope is reassigned to the teaching consumer and direct
  composition tests; no further validation on `683134a7`
- Runtime lease: `LEASE-ARGUS-001`; no watcher/service/live Orb access permitted

### CR-LUMEN-001 - Orb right-click delivery / visual-lock alignment

- Agent: LUMEN
- Roadmap: Phase 2 cross-stage Orb interaction-fidelity hardening
- Task card: `docs/operations/task_cards/orb-visual-choreography.md`
- Branch: `codex/lumen-orb-choreography`
- Worktree: `D:\FWT\lumen`
- State: `BLOCKED`; final cycle stopped before edits on ownership expansion
- Latest verified worker commit: `600704383d71c072b29a29e4061c86977f38a245`
- Validation: `VAL-20260714-008` diff-check passed; full pytest
  `VAL-20260714-004` was `INTERRUPTED_KNOWN_REMEDIATION`; no native compile or
  live visual proof claimed
- Dependencies: native renderer status, right-click request sequence/queue
  contract, visual lock, no-input/no-authority invariants
- Blocker: restart-safe global numeric sequencing and producer failure readback
  require a new durable allocator/outcome schema outside the card
- Next action: park pending durable sequence/outcome ownership reassignment; do
  not launch or modify the live Orb
- Runtime lease: `LEASE-LUMEN-001`; compile-only native build, no launch

## Review State

- VERA state: `RESPONDED`
- Evidence: `MSG-20260714-008` and
  `reviews/VERA/CR-20260714-preflight.md`
- Disposition: FORGE passed its pre-rebase full gate at integration head
  `cdfc4a23`; ARGUS and LUMEN remain parked on their recorded contract-ownership
  boundaries
- SENTINEL disposition: exact-type correction passed; see
  `reviews/SENTINEL/CR-20260714-forge-exact-types.md`
- VERA disposition: exact-type correction and discriminating regression passed;
  see `reviews/VERA/CR-20260714-forge-exact-types.md`
- MERIDIAN disposition: FORGE final architecture pass; no ADR; see
  `reviews/MERIDIAN/CR-20260714-forge-final.md`
- HARBOR disposition: FORGE final portability/integration static pass; see
  `reviews/HARBOR/CR-20260714-forge-final.md`
- ARCHIVIST disposition: LUMEN receipt/readback truth remains blocked; see
  `reviews/ARCHIVIST/CR-20260714-lumen-remediation.md`
- HARBOR passed only the affected `cdfc4a23` test-harness delta; no unchanged
  specialist finding was repeated
- Next action: commit CR-005, freeze local main, then rebase and re-prove the
  exact promotion head

Specialist sessions used in this cycle are completed/released. Their concrete
reports are stored above. CLAUDE is `UNVERIFIED`; no external audit is simulated.

## Runtime Leases

`control_room/RUNTIME_LEASES.md` records three unique isolated leases. All current
cards deny persistent services and the operator-visible Orb. All test-only leases
are released after `VAL-20260714-028`; required logs/state are preserved. No
assigned worker port is listening. Default ports remain reserved; an unknown
listener on `5173` is out of scope and must not be killed.

## Unassigned Dirty Work

Untracked Control Room paths named by `PROTOCOL.md` are ATLAS-owned pending this
open sync. Every other untracked path outside the three task-card scopes is
`unverified` and unassigned. None may be cleaned, relocated, or absorbed without
a task card or operator decision.

Concurrent tracked change: `src/francis/cli.py` has an uncommitted three-line
optional-import candidate written outside ATLAS/HARBOR. It is preserved,
unassigned, excluded from Control Room commits, and requires ownership plus a
bounded portability card before promotion.
