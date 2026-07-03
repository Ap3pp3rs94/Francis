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

Latest committed checkpoint: `43120459 fix(lens): surface summon hotkey collisions`.

What is materially true now:

- Francis summon config uses `Ctrl+Alt+F`, avoiding the known local Claude
  Desktop `Ctrl+Alt+Space` collision on this machine.
- `scripts/lens-hotkey-binding.ps1` records `hotkey_already_owned` as a visible
  blocked runtime receipt when Win32 `RegisterHotKey` fails.
- PowerShell status, Python preflight/readiness, and OS-binding execution
  preserve that blocker and point to `choose_unclaimed_global_hotkey`.
- The final summon enable flip remains an operator authority decision. The repo
  is prepared up to the decision surface; Francis did not self-grant summon.

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

## 5. Known truthful gaps

These still block any finished Orb embodiment claim:

- Summon: the final enable flip is not granted. Austin must explicitly approve
  the operator-authority decision before summon-anywhere can be enabled.
- Orb presence: overlay window, tray, Ctrl+M one-shot placement, and virtual
  pointer gestures still need one integrated stability proof across summon,
  dismiss, and host restart.
- Desktop bridge: `desktop_effect_confirmed` remains false until a post-action
  observer verifies target-side UI state after posted messages. The bridge must
  remain gated behind `FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE` and safe targets.
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
