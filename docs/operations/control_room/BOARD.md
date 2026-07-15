# Francis Control Room Board

Updated: 2026-07-15

Sync cycle: `CR-20260715-013`

Cycle-start local main source head: `2673cd5e`.

Remote `origin/main` observed during this sync: `5f931fab`.

Push state: final validated integrated-main push is operator-authorized.

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

### CR-FORGE-007 - Rogue detection assessment

- Agent: FORGE
- Roadmap: Phase 2, Stage 18 Managed Copies Platform
- Task card: `docs/operations/task_cards/managed-copy-rogue-detection-assessment.md`
- Branch: `codex/forge-rogue-detection-assessment`
- Worktree: `D:\fg`
- State: `PROMOTED`
- Latest verified commit: `224c9859`
- Dependencies: exact provision and structural-isolation receipts plus bounded
  fixture signal/evidence references; production incidents are not inferred
- Validation: 7 focused tests, complete managed-copy card suite, changed-path
  Ruff/format/mypy/diff-check, and final SENTINEL/VERA passes
- Blocker: none for fixture-backed assessment software; real incident facts and
  containment/recovery authority remain external
- Next action: remove the temporary checkout, push exact integrated main, and
  observe remote CI
- Runtime lease: `LEASE-FORGE-007`; released, no service or live Orb access

### CR-FORGE-006 - Safe-delta export artifact plan

- Agent: FORGE
- Roadmap: Phase 2, Stage 18 Managed Copies Platform
- Task card: `docs/operations/task_cards/managed-copy-safe-delta-export-artifact-plan.md`
- Branch: `codex/forge-safe-delta-export-artifact-plan`
- Worktree: `D:\fg`
- State: `PROMOTED`
- Latest verified worker commit: `2673cd5e`
- Dependencies: one exact live-valid approved decision and current source
  lineage/policy; fixtures are test evidence only
- Validation: 3 focused tests, complete 94-test card suite, changed-path static
  checks, post-promotion route/matrix checks, and SENTINEL/VERA/HARBOR pass
- Blocker: none for this card; production approval and all export effects remain
  external/operator-controlled
- Next action: push after prior-head CI terminates, then select the next roadmap gap
- Runtime lease: `LEASE-FORGE-006`; released, no service or live Orb access

### CR-FORGE-005 - Safe-delta export authorization decision

- Agent: FORGE
- Roadmap: Phase 2, Stage 18 Managed Copies Platform
- Task card:
  `docs/operations/task_cards/managed-copy-safe-delta-export-authorization-decision.md`
- Branch: `codex/forge-safe-delta-export-authorization-decision`
- Worktree: `D:\fg`
- State: `PROMOTED`
- Latest verified base: local main containing CR-011
- Validation: predecessor request contract promoted at `44048d85`; focused
  Windows-path integration correction `f3cc8c7c` passed
- Dependencies: exact live-valid pending request, current source lineage/policy,
  dedicated decision scope; real decisions remain operator-only
- Blocker: none for fixture-backed software validation; no production approval
  or decision may be fabricated
- Next action: push integrated main and continue with CR-FORGE-006
- Runtime lease: `LEASE-FORGE-005`; released with no service or live Orb use

### CR-FORGE-004 - Safe-delta export authorization request

- Agent: FORGE
- Roadmap: Phase 2, Stage 18 Managed Copies Platform
- Task card:
  `docs/operations/task_cards/managed-copy-safe-delta-export-authorization-request.md`
- Branch: `codex/forge-safe-delta-export-authorization-request`
- Worktree: `D:\fg`
- State: `PROMOTED`
- Latest promoted source commit: `44048d85`; integration test correction
  `f3cc8c7c`
- Validation: 6 focused tests, complete 85-test card suite,
  SENTINEL/VERA/HARBOR pass, exact-head full gate, and focused post-promotion
  checks passed
- Dependencies: freshly recomputed eligible preflight, exact source lineage,
  current tenant policy, dedicated request scope
- Blocker: none for this card; production facts and approval remain external
- Next action: push integrated main and continue with CR-FORGE-005
- Runtime lease: `LEASE-FORGE-004`; released with no service or live Orb use

### CR-FORGE-003 - Managed-copy safe-delta export preflight

- Agent: FORGE
- Roadmap: Phase 2, Stage 18 Managed Copies Platform
- Task card:
  `docs/operations/task_cards/managed-copy-safe-delta-export-preflight.md`
- Branch: `codex/forge-safe-delta-export-preflight`
- Worktree: `D:\fg`
- State: `PROMOTED`
- Latest promoted source commit: `287a27c8`
- Validation: 6 focused tests, 2 matrix tests, complete 79-test card suite,
  SENTINEL/VERA/HARBOR affected review, exact-head full gate, and focused
  post-promotion checks passed
- Dependencies: validated approved decision receipt, exact review/candidate,
  live provision/isolation lineage, current tenant policy, dedicated scope
- Blocker: none for this card; production facts remain external
- Next action: push integrated main and assign the pending export-authorization
  request contract after its bounded card is committed
- Runtime lease: `LEASE-FORGE-003`; released, with no service or live Orb use

### CR-FORGE-002 - Managed-copy safe-delta approval

- Agent: FORGE
- Roadmap: Phase 2, Stage 18 Managed Copies Platform
- Task card: `docs/operations/task_cards/managed-copy-safe-delta-approval.md`
- Branch: `codex/forge-safe-delta-approval`
- Worktree: `D:\fg`
- State: `PROMOTED`
- Latest promoted source commit: `ff58d6d9`
- Validation: exact candidate `e799c857` passed the complete card suite and full
  `scripts/check.ps1` gate, exit `0`; post-promotion long-path remediation and
  complete 77-test card suite passed on `D:\Francis`
- Dependencies: exact safe-delta review receipt, live provision/isolation
  lineage, tenant policy, dedicated approval scope
- Blocker: none for this card; production facts remain external
- Next action: push integrated main, verify remote CI/CodeQL, then assign the
  dry-run-only export-preflight card
- Runtime lease: `LEASE-FORGE-002`; released after test processes exited; no
  service or live Orb access occurred

### CR-ARGUS-001 - Lens game observer

- Agent: ARGUS
- Roadmap: Phase 2 cross-stage Lens observation hardening
- Task card: `docs/operations/task_cards/lens-game-observer.md`
- Branch: `codex/argus-game-observer`
- Worktree: `D:\Francis-worktrees\argus-game-observer`
- State: `PROMOTED`
- Latest verified worker commit: `7af273af863f8a729f79f45429d8a72653f2036b`
- Validation: 103 card tests, affected integrations, post-promotion 115-test
  suite, Ruff, format, mypy, parser, VERA and HARBOR reviews passed
- Dependencies: game-observer runtime config, foreground-process readback,
  situation-model source contract, portable Windows typing
- Blocker: none; final integrated CI/CodeQL are pending
- Next action: no further ARGUS card work
- Runtime lease: `LEASE-ARGUS-001` released; no live runtime used

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
