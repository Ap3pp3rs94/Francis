# Francis Control Room Session Brief

Updated: 2026-07-14, sync cycle `CR-20260714-005` (America/Chicago)

## Manager Role

ATLAS is the Francis Build Manager and Control Room chair. ATLAS plans,
decomposes, delegates, reviews, and promotes. Named workers own
feature implementation in isolated `codex/*` branches and worktrees. The manager
may make small integration fixes, but does not own a feature front. Control Room
state changes are committed as docs-only commits on local `main`; every push is
operator-gated. Promotion requires rebasing onto the exact committed local-main
head, rerunning the complete card and `scripts/check.ps1`, then fast-forwarding
local `main` only when certain. Escalate every listed operator boundary.

Cold-start order:

1. Read `AGENTS.md`.
2. Read only the current-phase/latest-evidence/remaining-gap sections of
   `docs/operations/COMPLETION_LEDGER.md` needed for orientation.
3. Read this brief, `BOARD.md`, `INTEGRATION_QUEUE.md`, `RUNTIME_LEASES.md`, and
   the active task card for each current front.
4. Verify Git/worktree state, native agent reachability, validation exits,
   runtime leases/ports, and protected runtime boundaries.
5. Load messages, reviews, evidence records, architecture, and history only when
   the next decision requires them.

## Canonical Posture

- CR-005 local-`main` parent:
  `6e883d1d19a18d157ed99799d598a7f8285771fd`; resolve the containing sync
  commit with `git rev-parse HEAD`. Remote `origin/main`:
  `8c84dc4e972b7921e9204e62f7cd655bd3ede037`. The local docs-only Control Room
  commits have not been pushed. Remote CI and CodeQL for `8c84dc4e` are green;
  that does not validate local-only commits.
- Canonical phase: Phase 2.
- Canonical active workstream: Stage 18 / Managed Copies Platform groundwork.
- Stage 17 is closed by governed receipt
  `stage17_capability_economy_closure_afd0fa32f7d1`.
- Stage 18 remains open. Production has no real customer request, tenant, or
  managed-copy runtime. Never invent customer identity, policy, or business facts.
- The ledger's first production gate is still that real operator-supplied
  request. FORGE is the highest-priority executable internal Stage 18 slice but
  cannot close or bypass the production gate with fixtures.
- Stage 6 is ledger-closed. Current Lens/Orb work is cross-stage hardening and
  must not be used to claim a new Stage 6 or Stage 18 closure.
- The live Orb process family is out of scope: do not stop, restart, replace,
  activate, or modify it while handling these branches.

## Active Fronts

### Managed copies / safe delta

Task card: `docs/operations/task_cards/managed-copy-safe-delta.md`
Seat: FORGE. Branch: `codex/forge-managed-copies-safe-delta`.

Proof target: a structurally verified tenant can record an exact-schema,
hash-only safe-delta candidate-review receipt while approval, export, import,
learning writes, and cross-tenant flow remain disabled. Readback must detect live
source-boundary drift and must not echo or persist raw customer data.

Current state: FORGE correction `24658090` enforces exact nested Boolean types
and passed focused tests, Ruff, format, mypy, and diff-check. SENTINEL and VERA
passed the affected correction. ATLAS integration head `cdfc4a23` adds a bounded
test-harness retry for transient supervisor status-file locks. Full gate
`VAL-20260714-028` passed with explicit exit `0` on that exact head in `D:\fg`.

Next smallest truthful gap: commit CR-005, rebase onto that exact local-main
head, and re-prove the rebased promotion candidate. This remains a hash-only
review slice, not approval or export.

### Lens game observer

Task card: `docs/operations/task_cards/lens-game-observer.md`
Seat: ARGUS. Branch: `codex/argus-game-observer`.

Proof target: local, read-only, foreground-bound semantic game observations
compose with the Lens situation model through strict versioned contracts and do
not acquire input or execution authority.

Current state: rebased commit `683134a7` passed its focused suite but VERA and
SENTINEL rejected promotion. The v2 producer is incompatible with the v1-only
apprenticeship recorder; strict legacy-heartbeat projection and receipt rotation
also remain open. No watcher or live runtime was used.

Next smallest truthful gap: parked pending a revised card that owns the teaching
consumer and direct observer-to-recorder composition tests. Do not validate or
expand the branch until that ownership is assigned.

### Orb right-click delivery / visual-lock alignment

Task card: `docs/operations/task_cards/orb-visual-choreography.md`
Seat: LUMEN. Branch: `codex/lumen-orb-choreography`.

Proof target: native Orb right-click requests are queued and drained without
loss or optimistic completion claims, while the visual-lock ring count remains
aligned with renderer truth and shell/authority invariants remain unchanged.

Current state: rebased commit `60070438` passed focused tests and compile-only
build, but all exact-diff reviewers rejected promotion. Cycle two stopped before
edits because restart-safe sequence allocation and producer-failure readback need
a durable schema owner outside the card. No live visual validation is claimed.

Next smallest truthful gap: parked pending ownership of a durable sequence high-
water mark and producer outcome surface. Do not launch or touch the live Orb.

## Contracts In Play

- Stage 18 safe-delta contract:
  `stage18_managed_copy_safe_delta_review_v1`.
- Safe-delta authority:
  `managed_copies.safe_delta.write`; candidate review does not confer approval,
  export, learning, execution, or mutation authority.
- Managed-copy routes:
  `POST /managed-copies/safe-delta-review` and
  `GET /managed-copies/safe-delta-reviews`, composed with provision and structural
  isolation receipts.
- Game observer configuration:
  `lens.game_observer.runtime_config`.
- Game observation payload:
  `lens.game.observation`, consumed only when the situation-model source contract
  and frame/receipt lineage validate.
- Lens situation readback:
  `lens.perception.situation_model_readback`; invalid observer contracts must be
  explicit blockers, not silently accepted.
- Orb renderer/runtime identity:
  `francis.native_orb_renderer.runtime_status`, the visual-lock contract, and the
  overlay window status/readback surfaces. Visual state must not imply authority.

## Known Traps

- Portable Windows typing: commit `adcb62a2` established the required pattern.
  Obtain `WinDLL` with `getattr(ctypes, "WinDLL", None)` and return an explicit
  unsupported readback when absent. Direct `ctypes.WinDLL` access breaks Ubuntu
  CI/type checking.
- Windows deep paths: Stage 18 tests use long isolated data roots. Tenant-local
  receipt paths and atomic temp names must remain below legacy path limits.
- Shared worktree index: Orb files are staged while the other fronts are
  unstaged in the historical source state. That state is archived and transferred;
  main now contains unrelated untracked work. Never use broad reset, restore,
  add, commit, or clean commands.
- Unrelated untracked files are operator/concurrent-session work. They are not
  assigned to these fronts and must remain untouched.
- Runtime truth outranks launcher output or optimistic receipts. No live-runtime
  claim is valid without matching route/readback evidence.
- No fake production facts: fixture tenants are test-only. Production Stage 18
  readback must remain empty until the operator supplies a real request.
- No authority shortcut: do not grant, decide, consume, export, activate, or
  physically validate anything as part of these cards.
- Completion ledger changes require a materially closed gate with exact evidence.
  Branch isolation, passing tests, and documentation alone do not close Stage 18.
- Local full-gate environments must include the `bridge` extra. CI installs
  `core`, `web`, `dev`, and `bridge`; the older bootstrap command omits `bridge`
  and leaves `jsonschema` unavailable for Grounded Presence test collection.
- HARBOR proved the local Typer metadata existed while all 17 module files were
  missing. ATLAS reinstalled only locked `typer==0.21.2`; importability is
  repaired. The later Ruff/format/mypy observation lacks a reproducible receipt
  and is not reusable gate evidence. Exact-head pytest remains pending.
- `src/francis/cli.py` also has a concurrent uncommitted optional-import candidate
  that ATLAS/HARBOR did not write. Preserve and exclude it; it needs ownership,
  tests for Typer-present/absent paths, and a bounded portability card.
- Runtime isolation: a worktree is not a data/process sandbox. Every active card
  uses its unique lease in `RUNTIME_LEASES.md`; all three leases currently deny
  persistent services and real Orb access. Full pytest writes only to each
  worktree's unique `data/test_runs/pytest` retention root.
- Message/readback bounds: `MESSAGE_LOG.md` is an index. Read the active front
  shard, `cross-front.md`, and `verification.md`; shards roll at 128 KiB or 250
  messages.
- Exact transfer provenance is in
  `control_room/handoffs/CR-20260714-mixed-tree-transfer.md`.

## Pending Operator Decisions

- Any real managed-copy customer request or safe-delta candidate/approval must be
  supplied or approved by the operator. No such production action is authorized.
- Stage closure decisions remain operator-only.
- Any uncertain promotion, destructive cleanup, public release, legal/license
  change, secret handling, GitHub setting, or new authority grant must stop at an
  evidence-backed request for operator decision.
- No current front is authorized to modify the live Orb process family.
- Pushing `main` or a worker branch is operator-only. Local Control Room commits
  do not imply publication.
- The old tool-managed roadmap goal remains `blocked`; the goal controller
  rejected the operator-requested replacement as "unfinished." This tool-state
  mismatch does not override the active repository-backed ATLAS mandate.
- A reread/reconciliation inside the current conversation is a context refresh,
  not context replacement. True replacement requires a fresh root manager
  session. This session performed only a refresh; no native control available to
  ATLAS creates a fresh root manager session, so replacement is unavailable here
  and is not simulated.

## Control Room

- Shared coordination root: `docs/operations/control_room/`.
- A sync cycle opens on reconciliation and closes at its local-main docs commit;
  active-seat liveness is measured against that exact closing cycle.
- ATLAS owns aggregate files. Workers submit structured reports; they do not edit
  aggregate Control Room state from implementation worktrees.
- VERA is independent and read-only by default. Its current preflight is stored
  at `control_room/reviews/VERA/CR-20260714-preflight.md`.
- CLAUDE is external and `UNVERIFIED`; do not simulate it. SENTINEL, HARBOR,
  MERIDIAN, and ARCHIVIST completed/released concrete review sessions in CR-003.
  ECHO remains unstaffed until a concrete question is routed.
- No more than FORGE, ARGUS, and LUMEN may hold mutating fronts concurrently.

## Promotion Readback

For each front, record before promotion and repeat after rebasing onto the exact
committed local-main head:

- branch and exact commit hash;
- task-card acceptance results with command and exit code;
- `scripts/check.ps1` result;
- diff review and cross-platform review result;
- GitHub run URL only after the operator authorizes a push;
- ledger entry or explicit statement that no ledger gate moved.
