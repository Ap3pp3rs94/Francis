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
- `scripts/ollama-doctor.ps1` now completes as a bounded health receipt instead
  of hanging or throwing on local CLI/Event Log/process readback quirks.
- The live Francis1/Ollama status replay now produces readable output through a
  same-provider readability repair when the primary local model returns
  unreadable output; the forced-garbage path still rewrites to
  `unreadable_rewritten` without leaking raw salad.

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

### 2026-07-03 19:32Z - Francis1 voice replay blocker after Ollama doctor

Current posture: Phase 2 / Orb embodiment Milestone 4 is blocked on local
Ollama model/runtime health, not on raw unreadable output leaking through the
developer bridge. The doctor now writes a bounded health report, and the
Francis1 reply lane still rewrites unreadable model output instead of relaying
symbol salad to the operator.

What changed:

- `scripts/ollama-doctor.ps1` now bounds external CLI probes with
  `CommandTimeoutSec` and returns timeout details instead of waiting forever.
- The doctor helper no longer uses a parameter named `Args`, avoiding collision
  with PowerShell's automatic `$args` variable when launching `ollama list`,
  `ollama ps`, and related probes.
- Doctor probe collections that are later counted are normalized to arrays under
  strict mode, and Event Log/process snapshots are best-effort so inaccessible
  local fields do not abort report export.
- `tests/test_ollama_doctor_script.py` locks the bounded command, strict-mode
  array, Event Log, process snapshot, and report-construction contracts.

Validation:

- PowerShell parser validation for `scripts\ollama-doctor.ps1` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_ollama_doctor_script.py -q` passed.
- `.venv\Scripts\python.exe -m ruff check tests\test_ollama_doctor_script.py` passed.
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\ollama-doctor.ps1 -Tag ollama_doctor_m4 -CommandTimeoutSec 5` completed and wrote:
  `data\logs\operations\ollama_doctor\ollama_doctor_m4_20260703_142950.log`,
  `.json`, and `_checks.csv`.
- The doctor check summary was 10 PASSED, 3 WARN, 2 SKIPPED, and 0 FAILED. API
  `/api/version` and `/api/tags` passed; `ollama list`, `ollama ps`, port 11434,
  process detection, model paths, model size scan, and `nvidia-smi` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_developer_bridge.py -q -k unreadable_model_output` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_developer_bridge.py -q -k output_guard` passed.
- `.venv\Scripts\python.exe -m ruff check src\francis\developer_bridge\ollama_participant.py tests\test_developer_bridge.py` passed.
- A live operator-scoped Francis1 status replay submitted prompt
  `collab-4d494e2aee18f190-ebb96481b08b` and received response
  `collab-52e42facbda0a874-4d30a811637e` with
  `output_guard_status=unreadable_rewritten`.

Remaining truthful gap:

- The Milestone 4 readable status reply requirement is not met. After a completed
  Ollama doctor run, the live Francis1/qwen2.5:7b lane still produced unreadable
  non-linguistic output.
- The forced-garbage fallback path is validated, and the live relay did not leak
  raw salad into the operator response. That is not equivalent to a healthy
  natural Francis1 reply.
- Treat the remaining blocker as local model blob/runtime/GPU-offload health
  until a new live operator-scoped status replay returns a readable reply. Do
  not proceed to the one-visible-loop acceptance proof on this evidence.

### 2026-07-03 19:47Z - Francis1 voice replay readability repair proof

Current posture: Phase 2 / Orb embodiment Milestone 4 now has a repeatable
Francis1/Ollama replay proof. The unhealthy primary local chat model is still
truthfully observed, but the developer bridge can recover a readable operator
reply through a same-provider fallback while preserving the unreadable-output
guard for forced garbage.

What changed:

- `src/francis/developer_bridge/ollama_participant.py` now performs a bounded
  readability repair after the primary Ollama response and before the output
  guard fallback.
- When primary output is unreadable, the participant retries same-provider local
  fallback models, defaulting to the already-installed `llama3.2:3b`.
- The execution trace records `readability_repair.status`, primary output
  quality metrics, fallback model attempts, and whether a readable fallback was
  used without storing raw unreadable primary output.
- Relay context explicitly states when same-provider readability repair was used.
- If all fallback attempts are still unreadable, the existing
  `unreadable_rewritten` output-guard fallback remains the operator-visible
  result.
- `scripts/francis1-ollama-replay-proof.ps1` now runs the repeatable Milestone 4
  proof: live operator-scoped status replay plus isolated forced-garbage
  injection.

Validation:

- Direct bounded Ollama probe showed `francis-chat`, `francis-chat:latest`, and
  `qwen2.5:7b-instruct` returned unreadable symbol-heavy output for a simple
  English prompt, while `llama3.2:3b` returned readable English.
- `.venv\Scripts\python.exe -m pytest tests\test_developer_bridge.py -q -k "unreadable_model_output or readable_same_provider_fallback"` passed.
- `.venv\Scripts\python.exe -m pytest tests\test_developer_bridge.py -q -k output_guard` passed.
- `.venv\Scripts\python.exe -m ruff check src\francis\developer_bridge\ollama_participant.py tests\test_developer_bridge.py` passed.
- PowerShell parser validation for `scripts\francis1-ollama-replay-proof.ps1`
  passed.
- `.venv\Scripts\python.exe -m pytest tests\test_francis1_ollama_replay_proof_script.py -q` passed.
- `.venv\Scripts\python.exe -m ruff check tests\test_francis1_ollama_replay_proof_script.py` passed.
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\francis1-ollama-replay-proof.ps1 -Mode Status -TimeoutSeconds 180` passed and wrote
  `data\logs\operations\francis1_ollama_replay_proof\francis1_ollama_replay_proof_20260703_144349.json`.
- The live proof submitted prompt `collab-bcaaf1147e93045a-8a8bf44b1b27` and
  received response `collab-561e281a6cc4b49e-7aa0ec9c1ce4` with
  `readable_reply_observed=true`, `readability_repair_status=readable_fallback_used`,
  `fallback_model_used=llama3.2:3b`, and `output_guard_status=not_applicable`.
- The forced-garbage proof submitted prompt `collab-047eba3f1dafd02e-84b74b5bee49`
  and received response `collab-dde08072831020a1-dcc41782960b` with
  `fallback_rewritten_observed=true`, `output_guard_status=unreadable_rewritten`,
  and `raw_garbage_leaked=false`.

Remaining truthful gap:

- The primary `francis-chat` model still appears unhealthy in this local runtime.
  The live readable reply is recovered through same-provider fallback
  `llama3.2:3b`, not proof that the primary model blob/GPU-offload path is fixed.
- The proof does not grant execution, mutation, training, or memory-write
  authority. It closes the voice replay proof requirement only.
- The one-visible-loop acceptance proof remains unbuilt and unproven.

### 2026-07-03 20:01Z - One visible loop proof gate

Current posture: Phase 2 / Orb embodiment Milestone 5 now has a repeatable proof
gate and presentation-demo integration. This is not final acceptance: the proof
truthfully remains blocked until Austin approves the summon enable decision and a
live safe-target desktop bridge action.

What changed:

- `scripts/francis-one-visible-loop-proof.ps1` now runs the one-visible-loop
  status proof: summon preflight, overlay/orb presence readback, optional
  operator-approved fixture safe-target action, receipt/trace/status paths, and
  explicit governance fields.
- The proof treats summon as blocked unless the required-before-enable chain is
  clear and `-OperatorApprovedSummonDecision` is passed. It does not self-enable
  summon.
- The fixture safe-target path enables `FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE=1`
  only inside the proof process, uses a fake safe Win32 target, and proves the
  post-action observer path with `desktop_effect_confirmed=true`.
- `scripts/francis-presentation-demo.ps1` can include the proof with
  `-IncludeOneVisibleLoopProof` and now surfaces the proof path, operator
  receipt path, desktop bridge receipt path, desktop confirmation, observer
  status, and chat/Lens render flags.

Validation:

- PowerShell parser validation passed for
  `scripts\francis-one-visible-loop-proof.ps1`.
- PowerShell parser validation passed for `scripts\francis-presentation-demo.ps1`.
- `.venv\Scripts\python.exe -m pytest tests\test_francis_one_visible_loop_proof_script.py tests\test_francis_presentation_demo_script.py -q`
  passed.
- `.venv\Scripts\python.exe -m ruff check tests\test_francis_one_visible_loop_proof_script.py tests\test_francis_presentation_demo_script.py`
  passed.
- Default one-visible-loop proof wrote
  `data\logs\operations\one_visible_loop\francis_one_visible_loop_proof_20260703_145744326.json`
  with `status=blocked`, `overlay_window_visible=true`,
  `reach_mode=full_screen_overlay_orb_offset`, and action `status=blocked`.
- Fixture safe-target one-visible-loop proof wrote
  `data\logs\operations\one_visible_loop\francis_one_visible_loop_proof_20260703_150058037.json`
  with proof `status=blocked`, action `status=passed`,
  `desktop_effect_confirmed=true`, and
  `target_observer_status=confirmed_target_state_changed`.
- Presentation demo proof integration wrote
  `.francis\presentation\demos\francis-presentation-demo-20260703-200057.json`
  with `ok=false`, failure `one_visible_loop_proof_blocked`,
  action `status=passed`, `desktop_effect_confirmed=true`, and the desktop
  bridge receipt path
  `.francis\one-visible-loop\20260703_150058037\orb_operator\desktop_bridge_receipts\orb_desktop_bridge_cf1feb79dc4c.json`.

Remaining truthful gap:

- The final Milestone 5 acceptance loop is still not complete. The proof gate
  does not show a real global-hotkey summon from anywhere, does not enable
  summon, does not perform a live operator-approved safe-target desktop bridge
  action, and does not verify that receipt, trace, and status are actually
  rendered in the chat/Lens UI.
- The next operator decision is singular: approve the summon enable flip and a
  live safe-target desktop bridge proof, or leave the proof in blocked status.

### 2026-07-03 20:07Z - Summon preflight live overlay readback

Current posture: Phase 2 / Orb embodiment Milestone 5 still remains blocked, but
the summon prerequisite readback is now narrower and more truthful. The live
overlay window is no longer reported as missing when its runtime state proves a
visible topmost overlay.

What changed:

- `scripts/lens-summon-preflight.ps1` now reads live tray and overlay runtime
  state from `data\runtime\lens-tray\status.json` and
  `data\runtime\lens-overlay\status.json`.
- The `overlay_window` required-before-enable dependency now becomes ready only
  when a live `lens.overlay.runtime_state` process reports
  `overlay_running`, `overlay_window_visible=true`, and `always_on_top=true`.
- The `tray_presence` dependency now has the same runtime-readback contract used
  by `scripts\lens-tray-presence.ps1`: matching live PID, `tray_running`, and
  `tray_icon_visible=true`.
- The preflight preserves the existing missing/blocker names for absent
  prerequisites, but adds runtime readback details and source fields so the
  proof can distinguish ready, stale, and missing states.

Validation:

- PowerShell parser validation passed for `scripts\lens-summon-preflight.ps1`.
- `.venv\Scripts\python.exe -m pytest tests\test_lens_summon_preflight_script.py -q`
  passed.
- `.venv\Scripts\python.exe -m ruff check tests\test_lens_summon_preflight_script.py`
  passed.
- Live summon preflight now reports `overlay_ready=true`,
  `overlay_state=visible_topmost`, and missing prerequisites
  `resident_host_process,tray_presence,global_hotkey_binding,summon_binding`.
- Default one-visible-loop proof wrote
  `data\logs\operations\one_visible_loop\francis_one_visible_loop_proof_20260703_150706740.json`
  with summon missing
  `resident_host_process,tray_presence,global_hotkey_binding,summon_binding`,
  `overlay_window_visible=true`, and action `status=blocked`.
- Fixture safe-target one-visible-loop proof wrote
  `data\logs\operations\one_visible_loop\francis_one_visible_loop_proof_20260703_150715329.json`
  with action `status=passed`, `desktop_effect_confirmed=true`, and
  `target_observer_status=confirmed_target_state_changed`.
- Presentation demo proof integration wrote
  `.francis\presentation\demos\francis-presentation-demo-20260703-200814.json`
  with `ok=false`, failure `one_visible_loop_proof_blocked`,
  action `status=passed`, `desktop_effect_confirmed=true`, and
  `target_observer_status=confirmed_target_state_changed`.

Remaining truthful gap:

- Milestone 5 is still not accepted. The remaining summon blockers are resident
  host process supervision, tray presence, global hotkey binding, and summon
  binding.
- Live runtime also shows stale/mismatched hotkey state: the persisted hotkey
  runtime status still reports `Ctrl+Alt+Space` while summon config now expects
  `Ctrl+Alt+F`. Do not treat summon-anywhere as ready until the runtime binding
  is refreshed and proven under the new chord.
- The final operator decision remains unchanged: Austin must approve the summon
  enable flip and a live safe-target desktop bridge proof.

### 2026-07-03 20:14Z - Summon stale hotkey chord readback

Current posture: Phase 2 / Orb embodiment Milestone 5 still remains blocked, but
the hotkey part of the summon prerequisite chain now exposes the exact stale
runtime chord mismatch inside both summon preflight and the one-visible-loop
proof artifact.

What changed:

- `scripts/lens-summon-preflight.ps1` now compares the runtime hotkey receipt's
  `global_hotkey` and `binding_scope` against the configured expected values.
- Stale or live mismatched hotkey state is reported as
  `global_hotkey_binding_stale_mismatched_chord` instead of only the generic
  `global_hotkey_binding_runtime_missing`.
- The hotkey readback now includes `global_hotkey_matches_expected` and
  `binding_scope_matches_expected` fields.
- `scripts/francis-one-visible-loop-proof.ps1` now carries the summon preflight
  hotkey, tray, and overlay runtime readbacks under its `summon` object so the
  acceptance artifact itself explains the current blockers.

Validation:

- PowerShell parser validation passed for `scripts\lens-summon-preflight.ps1`.
- PowerShell parser validation passed for
  `scripts\francis-one-visible-loop-proof.ps1`.
- `.venv\Scripts\python.exe -m pytest tests\test_lens_summon_preflight_script.py tests\test_francis_one_visible_loop_proof_script.py -q`
  passed.
- `.venv\Scripts\python.exe -m ruff check tests\test_lens_summon_preflight_script.py tests\test_francis_one_visible_loop_proof_script.py`
  passed.
- Live summon preflight reports `hotkey_state=stale_mismatched_hotkey`,
  `hotkey_blocker=global_hotkey_binding_stale_mismatched_chord`,
  `hotkey_actual=Ctrl+Alt+Space`, and `hotkey_expected=Ctrl+Alt+F`.
- One-visible-loop fixture proof wrote
  `data\logs\operations\one_visible_loop\francis_one_visible_loop_proof_20260703_151426754.json`
  with summon missing
  `resident_host_process,tray_presence,global_hotkey_binding,summon_binding`,
  `overlay_ready=true`, action `status=passed`,
  `desktop_effect_confirmed=true`, and the stale hotkey readback above.
- Presentation demo proof integration wrote
  `.francis\presentation\demos\francis-presentation-demo-20260703-201426.json`
  with `ok=false`, failure `one_visible_loop_proof_blocked`, action
  `status=passed`, `desktop_effect_confirmed=true`, and
  `target_observer_status=confirmed_target_state_changed`.

Remaining truthful gap:

- Milestone 5 is still not accepted. The hotkey runtime must be refreshed and
  proven under `Ctrl+Alt+F` after the proper authority path; the current runtime
  receipt is stale and still names `Ctrl+Alt+Space`.
- The proof still does not show a real global-hotkey summon from anywhere,
  Austin's enable approval, a live safe-target bridge action, or chat/Lens UI
  receipt/trace/status render verification.

### 2026-07-03 20:43Z - Stage 6 completion audit watchdog receipt

Current posture: Phase 2 / Orb embodiment Milestone 5 remains blocked, but the
Stage 6 completion-audit handoff now has a bounded visible receipt instead of an
unbounded wait when nested proof review exceeds the caller's budget.

What changed:

- `scripts/lens-stage6-completion-audit.ps1` now wraps normal audit execution in
  an outer watchdog unless explicitly running as its watchdog child.
- The watchdog preserves normal audit JSON when the child finishes, and returns a
  structured blocked receipt with `audit_status=timed_out`,
  `stage6_completion_audit_timeout`, child stdout/stderr capture paths, and
  `none_new_stage6_completion_audit` authority when the budget expires.
- Timeout handling kills the child process tree and reports the non-mutating
  governance posture instead of leaving the operator with a silent hang.
- `tests/test_lens_stage6_completion_audit_script.py` now asserts the watchdog
  receipt contract and passes the computed full-audit budget into the opt-in
  full audit harness so that explicit full runs are not undercut by the default
  watchdog.

Validation:

- PowerShell parser validation passed for
  `scripts\lens-stage6-completion-audit.ps1`.
- `.venv\Scripts\python.exe -m pytest tests\test_lens_stage6_completion_audit_script.py -q`
  passed with the existing full live audit skipped unless explicitly enabled.
- `.venv\Scripts\python.exe -m ruff check tests\test_lens_stage6_completion_audit_script.py`
  passed.
- Live bounded audit proof
  `.\scripts\lens-stage6-completion-audit.ps1 -Mode Status -OverallTimeoutSeconds 5 -ChildProofTimeoutSeconds 30`
  returned a blocked timeout receipt in about five seconds with
  `audit_status=timed_out`, `recommended_next_slice=bound_stage6_completion_audit_child_proofs_before_replay`,
  and `watchdog_killed_child_process_tree=true`.
- No leftover `lens-stage6-completion-audit.ps1` child process was observed after
  the timeout proof.
- One-visible-loop fixture proof wrote
  `data\logs\operations\one_visible_loop\francis_one_visible_loop_proof_20260703_154255868.json`
  with overlay `visible/topmost`, action `status=passed`,
  `desktop_effect_confirmed=true`, and an honest blocked summon state.

Remaining truthful gap:

- Milestone 5 is still not accepted. The repeatable proof still lacks a real
  global-hotkey summon from anywhere, Austin's enable approval, a live
  safe-target bridge action, and chat/Lens UI receipt/trace/status render
  verification.
- The audit watchdog bounds operator feedback; it does not itself satisfy
  resident host, tray presence, refreshed `Ctrl+Alt+F` hotkey binding, summon
  binding, or the final enable authority.

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
- Voice: `scripts/ollama-doctor.ps1` now completes, forced-garbage injection
  rewrites to `unreadable_rewritten` without raw salad, and the live Francis1
  status replay now returns readable output through same-provider fallback
  `llama3.2:3b`. The primary `francis-chat` model remains unhealthy and should
  be repaired separately, but Milestone 4 replay proof is now present.
- One visible loop: a repeatable proof gate now exists and proves fixture
  safe-target desktop confirmation. The summon preflight now consumes live
  overlay readback and no longer reports `overlay_window` as missing while the
  overlay is visible/topmost. Final acceptance remains blocked by resident host,
  tray presence, refreshed `Ctrl+Alt+F` hotkey binding, summon binding, Austin's
  approval for the enable flip/live safe-target action, and chat/Lens UI
  receipt/trace/status visibility.

## 6. Update rule

Update this ledger only when at least one of the following is true:

- a validated surface materially changed
- a plane posture changed in a way that is now directly inspectable
- a major blocker was removed
- the latest evidence set changed and should replace stale validation claims
