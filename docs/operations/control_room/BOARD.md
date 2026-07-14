# Francis Control Room Board

Updated: 2026-07-14

Sync cycle: `CR-20260714-003`

Cycle-start local main:
`d5516a54e9b939b2ae076f3be7b338b6cd2ed762`.

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
- State: `REMEDIATION_REQUIRED`; worker remains active
- Latest verified worker commit: `90c4dbe0287c1f169cefad47debab85067dd4fd8`
- Validation: `VAL-20260714-006` diff-check passed; full pytest
  `VAL-20260714-002` was `INTERRUPTED_KNOWN_REMEDIATION`; no pass/fail claim
- Dependencies: provision receipt, live structural-isolation receipt, tenant
  safe-delta policy, API actor-scope contract
- Blocker: ATLAS/SENTINEL/MERIDIAN found unbound receipt/governance fields, persisted
  candidate checks not recomputed, unbound ID/time/file/tenant lineage, blocked
  enum echo, cross-tenant latest-state coupling, competing path ownership/path
  claims, and unproven nested junction confinement
- Next action: FORGE is executing remediation cycle one against the routed
  ATLAS/SENTINEL/MERIDIAN findings; report a scope blocker before path-owner edits
- Runtime lease: `LEASE-FORGE-001`; no service or live Orb access permitted

### CR-ARGUS-001 - Lens game observer

- Agent: ARGUS
- Roadmap: Phase 2 cross-stage Lens observation hardening
- Task card: `docs/operations/task_cards/lens-game-observer.md`
- Branch: `codex/argus-game-observer`
- Worktree: `D:\Francis-worktrees\argus-game-observer`
- State: `REMEDIATION_REQUIRED`; worker remains active
- Latest verified worker commit: `2e454ba5bc4a9e5f629da463be5696350703fcb2`
- Validation: `VAL-20260714-007` diff-check passed; full pytest
  `VAL-20260714-003` was `INTERRUPTED_KNOWN_REMEDIATION`; no pass/fail claim
- Dependencies: game-observer runtime config, foreground-process readback,
  situation-model source contract, portable Windows typing
- Blocker: v2 blocked observations can bypass foreground/scene/classification
  validation, and teaching payload status/IDs/timestamps/counts/text/blockers/
  review semantics are insufficiently validated before projection
- Next action: ARGUS is executing remediation cycle one for malformed blocked-
  state and teaching-lineage projection; it is first in the integration queue
- Runtime lease: `LEASE-ARGUS-001`; no watcher/service/live Orb access permitted

### CR-LUMEN-001 - Orb right-click delivery / visual-lock alignment

- Agent: LUMEN
- Roadmap: Phase 2 cross-stage Orb interaction-fidelity hardening
- Task card: `docs/operations/task_cards/orb-visual-choreography.md`
- Branch: `codex/lumen-orb-choreography`
- Worktree: `D:\Francis-worktrees\lumen-orb-choreography`
- State: `REMEDIATION_REQUIRED`; worker remains active
- Latest verified worker commit: `a1b2c60bced10506cfd53bdfb97aa8b491656cea`
- Validation: `VAL-20260714-008` diff-check passed; full pytest
  `VAL-20260714-004` was `INTERRUPTED_KNOWN_REMEDIATION`; no native compile or
  live visual proof claimed
- Dependencies: native renderer status, right-click request sequence/queue
  contract, visual lock, no-input/no-authority invariants
- Blocker: native publication uses replacing move semantics, one physical gesture
  can publish more than once, and overlay discovery/drain/marker projection work
  is unbounded despite the advertised 32-request queue limit
- Next action: LUMEN is executing remediation cycle one for occupied destination,
  gesture cardinality, bounded discovery/drain, and truthful readback
- Runtime lease: `LEASE-LUMEN-001`; compile-only native build, no launch

## Review State

- VERA state: `RESPONDED`
- Evidence: `MSG-20260714-008` and
  `reviews/VERA/CR-20260714-preflight.md`
- Disposition: all three fronts are actively progressing in
  `REMEDIATION_REQUIRED`; no worker commit is review-ready
- SENTINEL disposition for FORGE: `REMEDIATION_REQUIRED` at `90c4dbe0`, review
  `reviews/SENTINEL/CR-20260714-forge-preflight.md`
- MERIDIAN disposition for FORGE: `REMEDIATION_REQUIRED` at `90c4dbe0`, review
  `reviews/MERIDIAN/CR-20260714-forge-preflight.md`; no ADR for the narrow path
- HARBOR disposition for LUMEN: `REMEDIATION_REQUIRED` at `a1b2c60b`, review
  `reviews/HARBOR/CR-20260714-lumen-preflight.md`
- ARCHIVIST disposition for CR-003: `CHANGES_REQUIRED`, review
  `reviews/ARCHIVIST/CR-20260714-003-precommit.md`
- Next action: review exact post-remediation worker commits only

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
