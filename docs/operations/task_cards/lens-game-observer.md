# Task Card: Lens Game Observer Contract

Task ID: `CR-ARGUS-001`

Assigned seat: ARGUS

Status: `QUEUED` pending patch preservation and worktree creation

## Objective

Finish and prove a local, read-only, foreground-bound semantic game-observer
contract that composes safely with the Lens situation model.

## Branch And Worktree

- Branch: `codex/argus-game-observer`
- Worktree: `D:\Francis-worktrees\argus-game-observer`
- Base: current `origin/main` at assignment time
- Never work in `D:\Francis`.

## Files In Scope

- `config/runtime/lens/game-observer.json`
- `src/francis/lens/game_observer.py`
- `src/francis/lens/situation_model.py`
- `tests/unit/test_lens_game_observer.py`
- `tests/unit/test_lens_situation_model.py`

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
- Windows process/window APIs use `getattr(ctypes, "WinDLL", None)` and return an
  explicit unsupported readback on non-Windows hosts.
- No watcher is launched, no process is manipulated, and no input authority is
  introduced by tests or implementation.
- Tests change in step with code.

Required commands, all with exit code 0:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_lens_game_observer.py tests/unit/test_lens_situation_model.py -q
.venv\Scripts\python.exe -m ruff check src/francis/lens/game_observer.py src/francis/lens/situation_model.py tests/unit/test_lens_game_observer.py tests/unit/test_lens_situation_model.py
.venv\Scripts\python.exe -m ruff format --check src/francis/lens/game_observer.py src/francis/lens/situation_model.py tests/unit/test_lens_game_observer.py tests/unit/test_lens_situation_model.py
.venv\Scripts\python.exe -m mypy src/francis/lens/game_observer.py src/francis/lens/situation_model.py
git diff --check origin/main...HEAD
.\scripts\check.ps1
```

## Worker Receipt

Return the commit hash, changed files, exact command results, cross-platform audit
result, and an explicit statement that no watcher/input/live-runtime action ran.
