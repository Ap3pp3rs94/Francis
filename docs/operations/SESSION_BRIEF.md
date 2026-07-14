# Francis Control Room Session Brief

Updated: 2026-07-14, sync cycle `CR-20260714-002` (America/Chicago)

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
2. Read `docs/operations/COMPLETION_LEDGER.md`.
3. Read this brief and the active task cards under `docs/operations/task_cards/`.
4. Read `docs/operations/control_room/BOARD.md`, `PROTOCOL.md`,
   `RUNTIME_LEASES.md`, `OPERATOR_QUEUE.md`, `EVIDENCE_INDEX.md`,
   `MESSAGE_LOG.md`, affected shards, and the seat file.
5. Verify `git status --short --branch`, `git worktree list --porcelain`,
   `git branch -avv`, and current GitHub checks before acting.

## Canonical Posture

- Canonical branch before this sync: local and remote `main` at `8c84dc4e`; verify
  the current head and do not assume this brief's commit was pushed.
- Canonical phase: Phase 2.
- Canonical active workstream: Stage 18 / Managed Copies Platform groundwork.
- Stage 17 is closed by governed receipt
  `stage17_capability_economy_closure_afd0fa32f7d1`.
- Stage 18 remains open. Production has no real customer request, tenant, or
  managed-copy runtime. Never invent customer identity, policy, or business facts.
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

Current state: the exact patch is preserved, hash-registered, and isolated in
FORGE's worktree. The shortened receipt path remains unverified. FORGE and VERA
found malformed overwrite, filename-prefix collision, unvalidated latest
readback, drift, and exclusive-create gaps. Treat the entire slice as unverified.

Next smallest truthful gap: synchronize the committed card, add failing tests for
malformed/collision/latest/drift/exclusive-create behavior, then apply the
smallest fail-closed correction. This is not an approval or export slice.

### Lens game observer

Task card: `docs/operations/task_cards/lens-game-observer.md`
Seat: ARGUS. Branch: `codex/argus-game-observer`.

Proof target: local, read-only, foreground-bound semantic game observations
compose with the Lens situation model through strict versioned contracts and do
not acquire input or execution authority.

Current state: the exact patch is preserved and isolated in ARGUS's worktree.
ARGUS confirmed portable `WinDLL` loading. ARGUS and VERA found unchanged v1
observation/heartbeat contracts, incomplete target/process/model/scene/
classification/teaching lineage validation, and an arbitrary absolute model-path
override. No watcher or live runtime was used.

Next smallest truthful gap: add explicit versioned producer/consumer migration
coverage, preserve conservative v1 compatibility, constrain the model boundary,
strengthen identity/lineage checks, and cover non-Windows behavior. Do not
activate a watcher or touch the live Lens runtime.

### Orb right-click delivery / visual-lock alignment

Task card: `docs/operations/task_cards/orb-visual-choreography.md`
Seat: LUMEN. Branch: `codex/lumen-orb-choreography`.

Proof target: native Orb right-click requests are queued and drained without
loss or optimistic completion claims, while the visual-lock ring count remains
aligned with renderer truth and shell/authority invariants remain unchanged.

Current state: the exact combined patch is preserved and assigned to LUMEN.
LUMEN verified that it is a right-click request durability slice plus an
8-streamer-ring documentation correction, not a canonical state-to-choreography
implementation. No live visual validation is claimed.

VERA additionally found no cap, TTL, backlog readback, deduplication, or durable
numeric ordering, plus a ring-count conflict in the host manifest.

Next smallest truthful gap: add direct tests for bounds/order/dedup/staleness,
align every ring-count truth surface, and obtain compile-only C++ evidence. Do
not launch the renderer or touch the live Orb. Canonical state-to-choreography
mapping remains a separate queued front.

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
- Runtime isolation: a worktree is not a data/process sandbox. Every active card
  uses its unique lease in `RUNTIME_LEASES.md`; all three leases currently deny
  persistent services and real Orb access.
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

## Control Room

- Shared coordination root: `docs/operations/control_room/`.
- A sync cycle opens on reconciliation and closes at its local-main docs commit;
  active-seat liveness is measured against that exact closing cycle.
- ATLAS owns aggregate files. Workers submit structured reports; they do not edit
  aggregate Control Room state from implementation worktrees.
- VERA is independent and read-only by default. Its current preflight is stored
  at `control_room/reviews/VERA/CR-20260714-preflight.md`.
- CLAUDE is external and `UNVERIFIED`; do not simulate it. MERIDIAN, SENTINEL,
  HARBOR, ARCHIVIST, and ECHO are durable but currently unstaffed.
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
