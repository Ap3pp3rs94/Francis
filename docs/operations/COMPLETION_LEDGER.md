# FRANCIS - COMPLETION_LEDGER

Shipped-state ledger for the current repository posture, hardening progress, and
productization gaps.

This file is intentionally narrower than `docs/canonical/ROADMAP.md`. The roadmap
defines the target state. This ledger records what is materially true in the repo,
using direct inspection plus validation that was actually run.

## 1. Document contract

Use this file for:

- current build posture
- high-confidence validated surfaces
- known gaps that still block a truthful "finished" claim
- the latest targeted validation evidence
- the first continuity/orientation source for recurring build automations

Do not use this file for:

- aspirational future capabilities
- unverified completion claims
- UI/demo descriptions that outrun server truth
- casual rewrites of canonical roadmap direction

Automation rule:

- recurring build automations should read this ledger first before re-reading the
  full canonical roadmap set
- canonical roadmap docs should be re-read when this ledger is missing, stale,
  contradicted by repo truth, or when milestone/workstream closure is being
  evaluated
- update this ledger at the end of a run when a validated surface materially
  changed, a major blocker was removed, or the strongest truthful build posture
  changed
- update `docs/canonical/BUILD_MANIFEST.md` or other canonical roadmap docs only
  when their own update contracts are actually met
- completion percentages are evidence claims, not progress decoration. They must
  be tied to a known baseline, validated repo evidence, and explicit remaining
  blockers; prompt-only, admin-only, diagnosis-only, or documentation-only turns
  must not move overall Francis or current build-phase percentages unless they
  close a documented governance/readiness gate with validation evidence.

## 2. Current build phase

Francis is in `Phase 2` per `docs/canonical/BUILD_MANIFEST.md`.

The strongest current posture is still the governed runtime spine, not the finished
operator product surface:

- `P9_OBSERVABILITY`: strongest plane today
- `P3_GOVERNANCE`: materially real
- `P1_INTERFACE`: partial
- `P7_EXECUTION`: partial
- `P8_MEMORY`: partial

Current active workstream: Orb embodiment / Stage 6 Lens runtime completion.
The current goal is ordered as summon prerequisites, Orb presence stability,
confirmed desktop bridge effects, voice replay proof, and one visible loop proof.

Older phase-history prose was moved to
`docs/operations/archive/COMPLETION_LEDGER_STATIC_HISTORY_2026-07-03.md` so the
main ledger stays under bounded readback limits without deleting evidence.

## 3. High-confidence current slice

Recent committed checkpoint before the active Orb-presence slice:
`60d21916 docs(operations): compact completion ledger readback`.

What is materially true now:

- Francis summon config uses `Ctrl+Alt+F`, avoiding the known local Claude
  Desktop `Ctrl+Alt+Space` collision on this machine.
- `scripts/lens-hotkey-binding.ps1` records `hotkey_already_owned` as a visible
  blocked runtime receipt when Win32 `RegisterHotKey` fails.
- PowerShell status, Python preflight/readiness, and OS-binding execution
  preserve that blocker and point to `choose_unclaimed_global_hotkey`.
- The final summon enable flip remains an operator authority decision. The repo
  is prepared up to the decision surface; Francis did not self-grant summon.
- The live Lens overlay can run as a virtual-screen coordinate plane including
  the taskbar, with the Orb moving inside that plane instead of being confined
  to a small window.
- The Orb click box remains bounded to the Orb core while the visual may extend
  outside that click box; hit testing passes through outside the Orb core.
- Ctrl+M one-shot Orb placement is bounded to overlay-owned position mutation
  and travels over render frames instead of snapping to the clicked point.
- The right-click Orb panel is small, receipted, and bounded to feature toggles
  plus chat/voice handoff metadata; it does not grant desktop execution.
- Continuous no-wake voice chat is not free-running; it is gated to Ctrl+V
  push-to-talk readback.
- The Orb desktop bridge now has a redacted post-action target observer. When
  the bridge is explicitly enabled and a safe target's observable UI state
  changes after posted messages, `desktop_effect_confirmed` can become true.

## 4. Latest validation evidence

> Older dated entries are archived under docs/operations/archive/ (see scripts/archive-completion-ledger.ps1).
> Historical undated ledger body is archived under docs/operations/archive/COMPLETION_LEDGER_STATIC_HISTORY_2026-07-03.md.

### 2026-07-03 18:18Z - Developer bridge unreadable output guard and ledger archive checkpoint

Current posture: Phase 2 / developer bridge operator trust blocks a known class
of unreadable local-model output before it reaches the operator channel. The
archive tooling for the completion ledger is present and safety-checked.

What changed:

- `OllamaParticipant` routes conservative symbol-heavy, non-wordlike replies
  through existing fallback machinery as `unreadable_rewritten`.
- The fallback keeps the `Francis1 output guard fallback:` prefix so existing
  collaboration, body-map, and driver consumers keep their current guard path.
- `_output_guard_rewrote()` treats unreadable rewrites as guard rewrites so
  drift-learning and receipt paths remain observable.
- `scripts/archive-completion-ledger.ps1` and archive files under
  `docs/operations/archive/` preserve old ledger history outside the bounded
  main ledger.

Validation:

- `.venv\Scripts\python.exe -m pytest tests\test_developer_bridge.py -q -k unreadable_model_output` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_developer_bridge.py -q -k output_guard` passed.
- `.venv\Scripts\python.exe -m ruff check src\francis\developer_bridge\ollama_participant.py tests\test_developer_bridge.py` passed.
- `scripts\archive-completion-ledger.ps1 -Apply` ran after commit `43120459`.

Remaining truthful gap:

- This guard prevents non-linguistic local-model output from being relayed as a
  normal operator reply, but it does not repair an unhealthy Ollama model,
  corrupt model blob, or GPU-offload issue. If Francis1/qwen2.5:7b continues
  returning unreadable output, run `scripts/ollama-doctor.ps1` and treat any
  continued gibberish as a local runtime/model-health issue before changing the
  Francis relay path again.
- Live Ollama replay after an Ollama doctor run has not been performed.

### 2026-07-03 18:40Z - Lens summon hotkey collision readback

Current posture: Phase 2 / Lens summon-anywhere prerequisites now avoid the
known local Claude Desktop `Ctrl+Alt+Space` collision by configuring the Francis
summon chord as `Ctrl+Alt+F`. The hotkey binding path records owned or blocked
Win32 `RegisterHotKey` failure as a visible `hotkey_already_owned` runtime
receipt instead of flattening it to generic missing-runtime behavior.

What changed:

- `config/runtime/lens/summon.json` declares `Ctrl+Alt+F` for the primary summon
  hotkey.
- Lens proof scripts, API tests, and UI Lens contract fixtures expect the
  configured `Ctrl+Alt+F` chord instead of `Ctrl+Alt+Space`.
- `scripts/lens-hotkey-binding.ps1` writes `status=hotkey_already_owned`,
  `error=hotkey_already_owned`, `blocker=hotkey_already_owned`, the requested
  chord, and the Win32 error into `data/runtime/lens-hotkey/status.json` when
  `RegisterHotKey` fails.
- PowerShell Status mode and Python preflight/readiness readbacks preserve that
  blocked runtime state and report `choose_unclaimed_global_hotkey` as the next
  gap.
- OS-binding execution receipts surface `hotkey_already_owned` instead of
  generic `global_hotkey_binding_failed` when the child runner reports the
  owned-chord blocker.

Validation:

- PowerShell parser validation for `scripts\lens-hotkey-binding.ps1` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_lens_hotkey_binding_script.py -q` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_api_lens_os_binding_authority.py -q` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_lens_summon_preflight_script.py tests\test_lens_command_palette_os_binding_proof_script.py tests\test_lens_summon_global_hotkey_binding_blocker_proof_script.py tests\test_lens_summon_authority_blocker_proof_script.py tests\test_lens_summon_anywhere_blockers_proof_script.py -q` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_api_lens.py::test_lens_status_projects_readonly_stage6_contract -q` passed.
- `node --test --experimental-strip-types src/lens/index.test.ts` passed from `apps/chat_ui`.
- `rg "Ctrl\+Alt\+Space" config scripts src tests apps/chat_ui/src/lens` returned no matches.
- `git diff --check` passed for the touched Lens hotkey/readback files, with only existing line-ending warnings.

Remaining truthful gap:

- This checkpoint does not prove `Ctrl+Alt+F` is unclaimed on every operator
  machine; it makes the collision outcome explicit and receipt-backed if the
  chord is owned.
- The summon binding is still governed by the existing authority and enablement
  gates. This does not claim full summon-anywhere readiness or Stage 6 closure.
- Full `scripts\check.ps1`, CI, and a live successful `RegisterHotKey` session
  were not run in this checkpoint.

### 2026-07-03 19:05Z - Orb presence overlay and virtual-pointer readback

Current posture: Phase 2 / Stage 6 Lens Orb presence has a validated overlay
checkpoint. The live Orb can occupy the full virtual-screen plane, including
over the Windows taskbar, while retaining a small Orb-core hit target and
receipt-backed virtual-pointer movement. This does not enable summon-anywhere
or default-on tray/hotkey authority.

What changed:

- `scripts/lens-overlay-window.ps1` now hosts the overlay as the virtual-screen
  coordinate plane and pins the WPF window topmost with Win32 `SetWindowPos`.
- Orb movement uses in-window offsets inside the full-screen overlay plane, so
  the Orb can reach screen edges while the click box stays limited to the Orb
  core.
- Ctrl+M one-shot placement now arms a transparent capture window and starts
  smootherstep render-frame travel before writing the final position receipt.
- Right-click Orb controls now expose a small receipted panel for wake listen,
  push-to-talk, LLM handoff, ambient motion, and bounded Orb chat handoff.
- Continuous voice chat readback now reports `push_to_talk_ctrl_v_required`
  with `continuous_voice_chat_free_run=false`.
- `src/francis/lens/status.py` surfaces `orb.move` as a command-palette action
  with `Ctrl+M` as a trigger that carries no authority by itself.
- Overlay and Orb contract tests were updated to lock the new full-screen plane,
  small hit-box, smooth travel, right-click controls, and virtual-pointer
  receipts.

Validation:

- PowerShell parser validation for `scripts\lens-overlay-window.ps1` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_lens_overlay_window_script.py -q` passed.
- `.venv\Scripts\python.exe -m ruff check src\francis\lens\status.py tests\test_lens_overlay_window_script.py` passed.
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\lens-resident-overlay-runtime-proof.ps1 -Mode Status -SupervisorRunSeconds 3 -ResidentSurfaceForegroundRunSeconds 2` passed after its built-in resident-surface retry.
- A main-root overlay stop/start cycle returned `stop_status=stopped`,
  `start_status=started`, and final status `visible` with runtime process alive.
- Live status readback after restart showed `overlay_runtime.overlay_window_visible=true`,
  `overlay_runtime.always_on_top=true`, `overlay_position.full_screen_overlay_plane=true`,
  `overlay_position.overlay_includes_taskbar=true`,
  `overlay_position.topmost_pin_applied=true`,
  `overlay_position.hit_test_passthrough_outside_click_box_enabled=true`,
  `click_hit_box_size=72`, and `reach_mode=full_screen_overlay_orb_offset`.
- `.venv\Scripts\python.exe -m pytest tests\unit\test_orb_operator.py tests\test_orb_phase0_contracts.py -q` passed.
- `.venv\Scripts\python.exe -m ruff check src\francis\input_actuator\orb_operator.py tests\unit\test_orb_operator.py tests\test_orb_phase0_contracts.py` passed.
- Live Orb pointer probe ran with `FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE=0`:
  move/click/type and move/click/drag/right-click sequences returned complete,
  final overlay Orb center was `(620, 640)`, newest overlay virtual-pointer
  receipts were present, `physical_input_performed=false`, and
  `user_mouse_taken=false`.
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\lens-tray-presence-api-execution-proof.ps1 -Mode Status` passed in an isolated data root, proving the governed API can start and stop real tray presence after fixture-granted resident/tray authority.

Remaining truthful gap:

- Production summon-anywhere is still blocked by governed enablement and
  authority gates. The live proof did not self-enable summon, default-on tray,
  or hotkey registration.
- `scripts\lens-summon-preflight.ps1 -Mode Status` still reports missing
  production prerequisites in the `required_before_enable` chain:
  resident host process, tray presence, overlay window, global hotkey binding,
  and summon binding.
- The tray proof used an isolated data root and fixture authority, then stopped
  tray and resident supervision before returning. It does not claim production
  tray is now running by default.
- The desktop bridge still has no post-action observer; `desktop_effect_confirmed`
  remains a Milestone 3 gap.

### 2026-07-03 19:12Z - Orb desktop bridge post-action observer

Current posture: Phase 2 / Stage 6 Orb desktop bridge still remains gated behind
`FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE=1`, but the bridge no longer has to report
every posted-message action as unconfirmed. It now records redacted target-side
state before and after posting messages and sets `desktop_effect_confirmed=true`
only when observable target-side state changes.

What changed:

- `src/francis/input_actuator/orb_desktop_bridge.py` records redacted before/after
  target observations for the resolved target window/control.
- The observer polls briefly after posting Win32 messages and reports
  `confirmed_target_state_changed` only on an observed state delta.
- Receipts include observer status, poll count, target-state changed flag, and
  redacted observation metadata without storing raw typed text.
- The bridge keeps the existing default-off gate, visible-only disabled path,
  and no user-cursor/no physical-input claims.
- Target resolution now rejects empty-title shell targets, the Francis Lens
  Overlay, Claude-titled windows, and common desktop shell window classes.
- Orb operator governance now propagates `desktop_effect_confirmed=true` when
  the bridge returns a confirmed effect.

Validation:

- `.venv\Scripts\python.exe -m ruff check src\francis\input_actuator\orb_desktop_bridge.py tests\unit\test_orb_desktop_bridge.py tests\unit\test_orb_operator.py` passed.
- `.venv\Scripts\python.exe -m pytest tests\unit\test_orb_desktop_bridge.py tests\unit\test_orb_operator.py -q` passed.
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\orb-operator-dry-run.ps1 -X 410 -Y 360 -Text "Milestone 3 dry run proof"` passed.
- A live orb-pointer probe with `FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE=0` returned
  `status=complete`, last action `visible_only`, bridge status
  `blocked_bridge_disabled`, `desktop_action_sent=false`,
  `desktop_effect_performed=false`, and `desktop_effect_confirmed=false`.

Remaining truthful gap:

- The observer confirmation path is proven with a fake Win32 target in unit
  tests, not by enabling the production bridge against a live operator-approved
  app window.
- The bridge remains default-off. A live enabled bridge proof must use an
  explicit operator-approved safe target and must still exclude Francis Lens
  Overlay and Claude windows.
- This does not complete the final visible-loop acceptance test; that still
  needs hotkey summon, operator-approved safe target action, confirmed effect,
  receipt, trace, and Lens/chat visibility in one repeatable runner.

## 5. Known truthful gaps

These still block any finished Orb embodiment claim:

- Summon: the final enable flip is not granted. Austin must explicitly approve
  the operator-authority decision before summon-anywhere can be enabled.
- Orb presence: overlay window, Ctrl+M one-shot placement, right-click controls,
  Ctrl+V gated voice readback, virtual pointer gestures, and host restart now
  have focused and live proof. Production summon/dismiss/tray integration still
  waits on governed resident, tray, hotkey, and summon authority.
- Desktop bridge: post-action observer support exists and can produce
  `desktop_effect_confirmed=true` when target-side state changes. The remaining
  gap is a live operator-approved safe-target proof with the bridge explicitly
  enabled; the bridge remains default-off.
- Voice: live Francis1 status replay and forced-garbage fallback proof still
  depend on the operator running `scripts/ollama-doctor.ps1` first.
- One visible loop: no repeatable end-to-end proof yet shows hotkey summon -> Orb
  appears -> operator-approved safe-target action -> confirmed effect -> receipt,
  trace, and chat/Lens UI visibility.

## 6. Update rule

Update this ledger only when at least one of the following is true:

- a validated surface materially changed
- a plane posture changed in a way that is now directly inspectable
- a major blocker was removed
- the latest evidence set changed and should replace stale validation claims
