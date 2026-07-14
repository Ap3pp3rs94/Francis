# Francis Control Room Board

Updated: 2026-07-14

Sync cycle: `CR-20260714-004`

Cycle-start local main:
`8a5ca378a854b29eb0ca7adcad591e2a57f1a653`.

Remote `origin/main` observed during this sync:
`8c84dc4e972b7921e9204e62f7cd655bd3ede037`.

Push state: operator-gated; this sync is local only unless separately approved.

Operator-gated decisions are indexed in `OPERATOR_QUEUE.md`; exact evidence is
indexed in `EVIDENCE_INDEX.md`.

GitHub baseline:

- CodeQL run `29337593904`: success.
- CI run `29337593360`: cancelled by the Control Room baseline push.
- Control Room head CI `29340258995`: in progress; Ubuntu Python 3.12 and
  3.13 passed, both Windows jobs remain in pytest.
- Control Room head CodeQL `29340258957`: success.
- Local `scripts/check.ps1`: after exact CI-extra resync, exact head `d5516a54`
  passed branch state, Ruff, and format but failed mypy on the environment-
  sensitive optional `typer` import. HARBOR proved a corrupt Typer payload;
  locked reinstall repaired importability. A later static-pass observation lacks
  a reproducible validation receipt and is not a gate claim. Exact-head pytest is
  active as `VAL-20260714-001`.

## Fronts

### CR-FORGE-001 - Managed-copy safe-delta

- Agent: FORGE
- Roadmap: Phase 2, Stage 18 Managed Copies Platform
- Task card: `docs/operations/task_cards/managed-copy-safe-delta.md`
- Branch: `codex/forge-managed-copies-safe-delta`
- Worktree: `D:\Francis-worktrees\forge-managed-copies-safe-delta`
- State: `REMEDIATION_REQUIRED`; final cycle-two reassignment authorized
- Latest verified worker commit: `cd9cd50422115761a2340e3d322b449516f85b0d`
- Validation: `VAL-20260714-006` diff-check passed; full pytest
  `VAL-20260714-002` was `INTERRUPTED_KNOWN_REMEDIATION`; no pass/fail claim
- Dependencies: provision receipt, live structural-isolation receipt, tenant
  safe-delta policy, API actor-scope contract
- Blocker: cycle one duplicated structural-isolation path ownership and exact-
  fingerprint readback accepts a colliding shortened path; four direct evidence
  gaps remain
- Next action: FORGE executes the final `CR-DEC-0012` cycle using the isolation-
  owned guarded-subpath API; no third remediation cycle is authorized
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
- Disposition: ARGUS and LUMEN are parked on explicit contract-ownership scope;
  FORGE alone is assigned one final bounded remediation cycle
- SENTINEL disposition: exact ARGUS/LUMEN remediation reviews reject promotion;
  see `reviews/SENTINEL/CR-20260714-exact-remediation.md`
- MERIDIAN disposition: FORGE requires canonical path-owner reuse under
  `CR-DEC-0012`; no ADR; see
  `reviews/MERIDIAN/CR-20260714-exact-remediation.md`
- HARBOR disposition: LUMEN and FORGE exact remediation candidates remain
  blocked; see `reviews/HARBOR/CR-20260714-exact-remediation.md`
- ARCHIVIST disposition: LUMEN receipt/readback truth remains blocked; see
  `reviews/ARCHIVIST/CR-20260714-lumen-remediation.md`
- Next action: review only the next FORGE cycle-two hash; do not repeat unchanged
  findings or start a full gate before focused acceptance passes

Specialist sessions used in this cycle are completed/released. Their concrete
reports are stored above. CLAUDE is `UNVERIFIED`; no external audit is simulated.

## Runtime Leases

`control_room/RUNTIME_LEASES.md` records three unique isolated leases. All current
cards deny persistent services and the operator-visible Orb. Each lease is in
test-only use; no assigned ports are listening. Default ports remain reserved;
an unknown listener on `5173` is out of scope and must not be killed.

## Unassigned Dirty Work

Untracked Control Room paths named by `PROTOCOL.md` are ATLAS-owned pending this
open sync. Every other untracked path outside the three task-card scopes is
`unverified` and unassigned. None may be cleaned, relocated, or absorbed without
a task card or operator decision.

Concurrent tracked change: `src/francis/cli.py` has an uncommitted three-line
optional-import candidate written outside ATLAS/HARBOR. It is preserved,
unassigned, excluded from Control Room commits, and requires ownership plus a
bounded portability card before promotion.
