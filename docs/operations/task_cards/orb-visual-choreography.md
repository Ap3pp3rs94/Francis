# Task Card: Orb Right-Click Delivery And Visual-Lock Alignment

Task ID: `CR-LUMEN-001`

Assigned seat: LUMEN

Status: `ACTIVE` after LUMEN KICKOFF and ATLAS scope correction

## Objective

Finish and prove loss-resistant, ordered native Orb right-click request delivery
and align the documented main streamer-ring count with renderer truth, without
changing authority, shell behavior, or the live process.

## Branch And Worktree

- Branch: `codex/lumen-orb-choreography`
- Worktree: `D:\Francis-worktrees\lumen-orb-choreography`
- Assignment base: `8c84dc4e972b7921e9204e62f7cd655bd3ede037`
- Final review base: exact committed local `main` head after Control Room sync
- Never work in `D:\Francis`.

## RUNTIME ISOLATION

- Lease: `LEASE-LUMEN-001` in `control_room/RUNTIME_LEASES.md`
- `FRANCIS_DATA_DIR`: `D:\Francis-runtime-leases\lumen-orb-choreography\data`
- API / overlay / frontend ports: `18003` / `18783` / `15173`
- Permitted services: none; pytest/Ruff and one compile-only native build
- Operator-visible Orb: denied
- Startup command: prohibited; native build runs without `-Run` or `-Launch`
- Shutdown: prove no front-owned renderer/service/listener exists before review
- Cleanup: preserve build/test output; remove only proven front-owned temporary
  state and never touch the canonical runtime or an unknown process

## Files In Scope

- `native/orb/native_orb_renderer.cpp`
- `scripts/lens-overlay-window.ps1`
- `src/francis/lens/host_manifest.py`
- `docs/operations/ORB_VISUAL_LOCK.md`
- `tests/test_lens_overlay_window_script.py`
- `tests/test_lens_host_manifest_process_readback.py`
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
- right-click request kind `francis.native_orb_renderer.right_click_request`
- canonical visual-lock renderer identity and main streamer-ring count
- overlay request queue/drain status and readback
- click-through/no-activate shell behavior, bounded move/contact messages, and
  fail-closed authority flags
- visual state must never imply execution or input authority

## Acceptance Criteria

- Multiple right-click requests cannot overwrite one another; the queue is
  bounded and requests retain unique numeric sequence identity that is drained
  deterministically without relying only on filesystem timestamps.
- Malformed, stale, duplicate, or unrouteable requests fail closed and do not
  produce optimistic completion/readback claims.
- Request queue persistence, TTL, backlog readback, deduplication, and removal
  are bounded and distinguish queued, attempted, applied, and failed outcomes.
- The documented main streamer-ring count matches renderer implementation and
  every overlay/host-manifest readback plus direct tests.
- Existing click-through, hit-testing, focus, z-order, bounded-message, and
  no-desktop-input guarantees remain covered by tests.
- Script/C++ request contract names and sequence fields remain aligned; tests
  change in step with code.
- No live process, runtime state, binary, receipt, config, tray, hotkey, or voice
  provider is modified or activated.
- No canonical state-to-choreography or live visual acceptance claim is made by
  this card.

Required commands, all with exit code 0:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_lens_overlay_window_script.py tests/test_lens_host_manifest_process_readback.py tests/unit/test_native_orb_cpp_renderer.py -q
.venv\Scripts\python.exe -m ruff check src/francis/lens/host_manifest.py tests/test_lens_overlay_window_script.py tests/test_lens_host_manifest_process_readback.py tests/unit/test_native_orb_cpp_renderer.py
.venv\Scripts\python.exe -m ruff format --check src/francis/lens/host_manifest.py tests/test_lens_overlay_window_script.py tests/test_lens_host_manifest_process_readback.py tests/unit/test_native_orb_cpp_renderer.py
.\native\orb\build-native-orb-renderer.ps1
git diff --check main...HEAD
.\scripts\check.ps1
```

The native build command is compile-only. Passing `-Run` or `-Launch` violates
this card.

## Mandatory Review Questions

- MERIDIAN is required only if request/status schema or renderer ownership
  boundaries change beyond the existing contract.
- SENTINEL: do queue handling and visuals preserve no-input/no-authority,
  click-through, focus, hit-testing, and live-process exclusions?
- HARBOR: does the C++ source compile in isolation, do PowerShell/C++ contracts
  remain portable, and is the exact rebased head tested?
- VERA: do queue bounds/order/dedup/staleness and every ring-count truth surface
  have direct acceptance evidence?
- ARCHIVIST: can queued/attempted/applied/failed readback be traced without an
  optimistic completion claim?

## Worker Receipt

Return the commit hash, changed files, exact command results, queue/readback
contract review, and an explicit statement that no live/runtime activation
occurred and no broader choreography claim is made.
