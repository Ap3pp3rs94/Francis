# Task Card: Lens Game Observer Contract

Task ID: `CR-ARGUS-001`

Assigned seat: ARGUS

Status: `ACTIVE` after rebase; current candidate `fa74bdfd`

## Objective

Finish and prove a local, read-only, foreground-bound semantic game-observer
contract that composes safely with the Lens situation model.

## Branch And Worktree

- Branch: `codex/argus-game-observer`
- Worktree: `D:\Francis-worktrees\argus-game-observer`
- Transfer source base: `8c84dc4e972b7921e9204e62f7cd655bd3ede037`
- First candidate parent: `d5516a54e9b939b2ae076f3be7b338b6cd2ed762`
- Final review base: exact committed local `main` head after Control Room sync
- Never work in `D:\Francis`.

## RUNTIME ISOLATION

- Lease: `LEASE-ARGUS-001` in `control_room/RUNTIME_LEASES.md`
- `FRANCIS_DATA_DIR`: `D:\Francis-runtime-leases\argus-game-observer\data`
- Pytest retention: worktree-local `data\test_runs\pytest`; unique to this
  worktree and governed by `tests/conftest.py`
- API / overlay / frontend ports: `18002` / `18782` / `15172`
- Permitted services: none; pytest/Ruff/mypy processes only
- Operator-visible Orb: denied
- Startup command: prohibited; no observer/watcher/bridge may be launched
- Shutdown: verify no front-owned persistent process or listener before review
- Cleanup: preserve test evidence; remove only proven front-owned temporary state

## Files In Scope

- `config/runtime/lens/game-observer.json`
- `src/francis/lens/game_observer.py`
- `src/francis/lens/situation_model.py`
- `src/francis/apprenticeship_game_teaching.py`
- `tests/unit/test_lens_game_observer.py`
- `tests/unit/test_lens_situation_model.py`
- `tests/unit/test_apprenticeship_game_teaching.py`
- `tests/unit/test_apprenticeship_game_episode_review.py`
- `tests/unit/test_lens_perception_worker.py`

## Do Not Touch

- native Orb renderer, overlay script, visual-lock documentation, or live
  Orb/Lens processes
- managed-copy or Stage 18 files
- input-actuator, SendInput, keyboard, mouse, or authority-grant surfaces
- unrelated tracked, staged, or untracked files
- completion ledger without a separately approved, evidence-backed gate closure

## Contracts To Compose With

- `lens.game_observer.runtime_config`
- `lens.game.observation`
- `lens.perception.situation_model_readback`
- `apprenticeship.game_teaching.observation`
- frame ID, receipt ID, target identity, process identity, model identity, and
  teaching-review lineage checks
- local-only inference, foreground-target requirement, and no-input-authority
  governance
- portable Windows API pattern from commit `adcb62a2`

## Acceptance Criteria

- Runtime configuration is strict, versioned, and rejects input authority or
  model paths outside the governed data boundary.
- Observations fail closed for missing/wrong foreground process, invalid model,
  stale lineage, low confidence, or malformed configuration.
- Situation-model readback accepts only a valid observer contract and surfaces a
  precise blocker for invalid data.
- Acceptance validates bounded target, process, model, scene, classification,
  frame, receipt, and teaching lineage rather than only checking field presence.
- New mandatory governance fields use a new producer contract version. Persisted
  v1 observation/heartbeat payloads receive explicit, conservative legacy
  handling and cannot be silently reinterpreted as the new contract.
- Windows process/window APIs use `getattr(ctypes, "WinDLL", None)` and return an
  explicit unsupported readback on non-Windows hosts.
- Model-path overrides remain under the governed data boundary; arbitrary
  absolute paths fail closed. Direct non-Windows tests cover the unsupported path.
- No watcher is launched, no process is manipulated, and no input authority is
  introduced by tests or implementation.
- Tests change in step with code.
- The v2 observer composes directly with the teaching recorder. Recognized v1
  observations remain blocked as legacy rather than silently normalized, and
  unknown or Boolean contract versions fail closed.
- An asynchronous classification result is discarded when its authority receipt
  rotates before commit; it returns `semantic_warming` and cannot write a
  teaching event under stale authority.

Required commands, all with exit code 0:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_lens_game_observer.py tests/unit/test_lens_situation_model.py tests/unit/test_apprenticeship_game_teaching.py tests/unit/test_apprenticeship_game_episode_review.py tests/unit/test_lens_perception_worker.py -q
.venv\Scripts\python.exe -m ruff check src/francis/lens/game_observer.py src/francis/lens/situation_model.py src/francis/apprenticeship_game_teaching.py tests/unit/test_lens_game_observer.py tests/unit/test_lens_situation_model.py tests/unit/test_apprenticeship_game_teaching.py tests/unit/test_apprenticeship_game_episode_review.py tests/unit/test_lens_perception_worker.py
.venv\Scripts\python.exe -m ruff format --check src/francis/lens/game_observer.py src/francis/lens/situation_model.py src/francis/apprenticeship_game_teaching.py tests/unit/test_lens_game_observer.py tests/unit/test_lens_situation_model.py tests/unit/test_apprenticeship_game_teaching.py tests/unit/test_apprenticeship_game_episode_review.py tests/unit/test_lens_perception_worker.py
.venv\Scripts\python.exe -m mypy src/francis/lens/game_observer.py src/francis/lens/situation_model.py src/francis/apprenticeship_game_teaching.py
git diff --check main...HEAD
.\scripts\check.ps1
```

## Mandatory Review Questions

- MERIDIAN: is the v2 producer plus conservative v1 reader an explicit compatible
  schema evolution, and does any part require an ADR?
- SENTINEL: do local-only, foreground-target, model-boundary, and no-input
  invariants remain fail closed?
- HARBOR: do Windows loaders preserve the `adcb62a2` portable pattern, does
  non-Windows collection pass, and is the exact rebased head tested?
- VERA: are every identity/lineage and legacy-version claim covered directly?
- ARCHIVIST is required only if the final diff adds or changes receipt evidence.

## Routed Remediation

Blocked v2 observations must not bypass foreground, scene, and classification
structure validation before situation-model projection. Add a crafted blocked-
state identity regression and either reject malformed blocked payloads or return
only a strict validated projection. Evidence: `MSG-20260714-013`.

Teaching-session and teaching-review payloads must validate bounded status,
identifiers, timestamps, counts, text fields, blockers, and review semantics
before any field is projected into the situation model. Add crafted lineage
regressions proving malformed teaching payloads fail closed. Evidence:
`MSG-20260714-016`.

Compose the current v2 observer producer with the teaching recorder without
weakening legacy handling. Persisting v1 is out of scope because the episode
receipt schema cannot represent that evolution truthfully. Add direct tests for
v2 recording, precise v1/unknown-version blockers, observer-to-recorder
composition, and authority-receipt rotation during classification.

## Worker Receipt

Return the commit hash, changed files, exact command results, cross-platform audit
result, and an explicit statement that no watcher/input/live-runtime action ran.
