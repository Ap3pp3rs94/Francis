# Task Card: Orb Visual And Choreography Contract

Task ID: `CR-LUMEN-001`

Assigned seat: LUMEN

Status: `QUEUED` pending patch preservation and worktree creation

## Objective

Finish and prove deterministic ring/color/choreography mapping for the canonical
Orb renderer without changing its authority, shell behavior, or live process.

## Branch And Worktree

- Branch: `codex/lumen-orb-choreography`
- Worktree: `D:\Francis-worktrees\lumen-orb-choreography`
- Base: current `origin/main` at assignment time
- Never work in `D:\Francis`.

## Files In Scope

- `native/orb/native_orb_renderer.cpp`
- `scripts/lens-overlay-window.ps1`
- `docs/operations/ORB_VISUAL_LOCK.md`
- `tests/test_lens_overlay_window_script.py`
- `tests/unit/test_native_orb_cpp_renderer.py`

## Do Not Touch

- the running Orb/Lens process family, runtime data, config, receipts, binaries,
  supervisor, tray, hotkey, or voice provider
- game-observer and managed-copy files
- input-actuator authority, hit-testing policy, focus/z-order policy, or physical
  cursor/keyboard behavior except where the existing contract is asserted
- unrelated tracked, staged, or untracked files
- completion ledger without a separately approved, evidence-backed gate closure

## Contracts To Compose With

- native renderer status kind `francis.native_orb_renderer.runtime_status`
- canonical visual-lock renderer identity and ring/color state contract
- overlay window status/readback and choreography projection
- click-through/no-activate shell behavior, bounded move/contact messages, and
  fail-closed authority flags
- visual state must never imply execution or input authority

## Acceptance Criteria

- Ring/color/choreography output is deterministically derived from validated
  canonical state and preserves the documented visual identity.
- Unknown, malformed, stale, or authority-bearing state fails closed rather than
  projecting optimistic behavior.
- Existing click-through, hit-testing, focus, z-order, bounded-message, and
  no-desktop-input guarantees remain covered by tests.
- Script and C++ contract names remain aligned; tests change in step with code.
- No live process, runtime state, binary, receipt, config, tray, hotkey, or voice
  provider is modified or activated.
- No visual acceptance claim is made without separate operator-visible proof.

Required commands, all with exit code 0:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lens_overlay_window_script.py tests/unit/test_native_orb_cpp_renderer.py -q
.venv\Scripts\python.exe -m ruff check tests/test_lens_overlay_window_script.py tests/unit/test_native_orb_cpp_renderer.py
.venv\Scripts\python.exe -m ruff format --check tests/test_lens_overlay_window_script.py tests/unit/test_native_orb_cpp_renderer.py
git diff --check origin/main...HEAD
.\scripts\check.ps1
```

## Worker Receipt

Return the commit hash, changed files, exact command results, contract-alignment
review, and an explicit statement that no live/runtime activation occurred.
