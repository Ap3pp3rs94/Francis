# Francis Control Room Session Brief

Updated: 2026-07-14 (America/Chicago)

## Manager Role

ATLAS is the Francis Build Manager and Control Room chair. ATLAS plans,
decomposes, delegates, reviews, and promotes. Named workers own
feature implementation in isolated `codex/*` branches and worktrees. The manager
may make small integration fixes, but does not own a feature front. Before a
routine promotion, verify the task card, run `scripts/check.ps1` on the branch,
fast-forward `main`, push, and remove the merged branch/worktree. Escalate an
uncertain merge or any operator-only boundary.

Cold-start order:

1. Read `AGENTS.md`.
2. Read `docs/operations/COMPLETION_LEDGER.md`.
3. Read this brief and the active task cards under `docs/operations/task_cards/`.
4. Read `docs/operations/control_room/BOARD.md` and the assigned seat file.
5. Verify `git status --short --branch`, `git worktree list --porcelain`,
   `git branch -avv`, and current GitHub checks before acting.

## Canonical Posture

- Canonical branch: `main` at `4e1f4ce9` when this brief was written; verify it.
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

Current state: an uncommitted implementation exists in the shared worktree. Its
first confirmed write failed because the original Windows receipt path was too
deep. The path was shortened to `receipts/sd/<16-char-id>.json`; Ruff and targeted
mypy passed, but the focused end-to-end test was interrupted before this fix was
proven. Treat the slice as unverified.

Next smallest truthful gap: finish branch isolation, rerun the focused test,
audit receipt collision/fail-closed behavior, and prove the complete task card.
This is not an approval or export slice.

### Lens game observer

Task card: `docs/operations/task_cards/lens-game-observer.md`
Seat: ARGUS. Branch: `codex/argus-game-observer`.

Proof target: local, read-only, foreground-bound semantic game observations
compose with the Lens situation model through strict versioned contracts and do
not acquire input or execution authority.

Current state: an unstaged multi-file implementation exists in the shared
worktree. It extends runtime configuration, foreground-process identity,
semantic warming/classification, and situation-model validation. It has not been
reviewed or broad-validated as an isolated branch.

Next smallest truthful gap: isolate the exact diff, audit cross-platform Windows
API use, run focused contracts and the full branch gate, and return a committed
worker receipt. Do not activate a watcher or touch the live Lens runtime.

### Orb visual / choreography

Task card: `docs/operations/task_cards/orb-visual-choreography.md`
Seat: LUMEN. Branch: `codex/lumen-orb-choreography`.

Proof target: ring/color/choreography behavior remains deterministic and
truthfully driven by the canonical Orb state contract while preserving hit
testing, click-through behavior, authority fail-closed checks, and renderer
identity.

Current state: the C++ renderer, overlay script, and direct tests are staged in
the shared worktree; `ORB_VISUAL_LOCK.md` has a separate unstaged companion diff.
No live visual validation is claimed.

Next smallest truthful gap: preserve both index and working-tree parts in one
isolated branch, review the state-to-choreography mapping, run exact tests and the
full branch gate, and report what remains unproven without touching the live Orb.

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
  unstaged. Never use broad reset, restore, add, commit, or clean commands.
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

## Pending Operator Decisions

- Any real managed-copy customer request or safe-delta candidate/approval must be
  supplied or approved by the operator. No such production action is authorized.
- Stage closure decisions remain operator-only.
- Any uncertain promotion, destructive cleanup, public release, legal/license
  change, secret handling, GitHub setting, or new authority grant must stop at an
  evidence-backed request for operator decision.
- No current front is authorized to modify the live Orb process family.

## Control Room

- Shared coordination root: `docs/operations/control_room/`.
- ATLAS owns aggregate files. Workers submit structured reports; they do not edit
  aggregate Control Room state from implementation worktrees.
- VERA is independent and read-only by default.
- No more than FORGE, ARGUS, and LUMEN may hold mutating fronts concurrently.

## Promotion Readback

For each front, record before promotion:

- branch and exact commit hash;
- task-card acceptance results with command and exit code;
- `scripts/check.ps1` result;
- diff review and cross-platform review result;
- GitHub run URL after promotion;
- ledger entry or explicit statement that no ledger gate moved.
