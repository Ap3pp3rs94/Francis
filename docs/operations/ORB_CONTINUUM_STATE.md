# Francis Orb Continuum State

This is the durable continuation state for the active Francis Orb continuum
mandate. It exists so another authorized session can resume from repository
truth without depending on chat memory.

## Active Mandate

Advance the Francis Orb into a truthful, substrate-backed, receipt-driven desktop
embodiment while preserving the current Orb visuals. The implementation order is:

1. Protect and understand.
2. Deliver a minimum truthful vertical slice.
3. Harden voice and receipts.
4. Harden overlay and operator behavior.
5. Execute a truthful Mona Lisa painting representation.
6. Add independent replay, evaluation, proposal, and continuation channels.
7. Validate and document the result.

## Non-Negotiable Visual Lock

The current Orb face is canonical and immutable. The locked surface is recorded
in `docs/operations/ORB_VISUAL_LOCK.md`.

Visually sensitive files:

- `apps/chat_ui/src/lens/orbGlyph.ts`
- `apps/chat_ui/src/App.tsx`
- `scripts/lens-overlay-window.ps1`

Do not change color, size, shape, glow, halo, opacity, material, ring counts,
blur, gradients, texture, shadows, highlights, asset references, or visual
proportions.

## Completed Tasks

- Voice turn correlation fields are preserved across `/chat/send` and overlay
  voice-turn receipts without claiming unsupported model cancellation.
- Overlay voice receipt paths distinguish explicit synthetic voice turns,
  microphone wake turns, stale reply suppression, speech playback, and provider
  unavailability.
- Phase 0 visual lock is documented and protected by focused tests.
- A first overlay-bound Lens observation contract exists at
  `POST /lens/mcp/observe`. It maps a requested desktop region through supplied
  or existing overlay context, calls only read-only screen/session MCP readbacks,
  writes a receipt, and truthfully reports that screenshots, pixels, OCR, and
  accessibility-tree evidence are not captured by this slice.
- A narrow `paint the Mona Lisa` / `draw the Mona Lisa` ingress now routes
  through the existing `/chat/send` mission path. It creates a governed mission
  and queued `plan.create` operation with sandbox-required operator metadata,
  overlay/lens observation requirements, voice-turn correlation when supplied,
  and a read-only Orb embodiment projection. It does not claim a painting was
  created.
- A bounded sandbox canvas operator adapter now exists as the
  `sandbox.canvas.paint_mona_lisa` executor capability. It runs through the
  existing operations substrate, consumes the Mona Lisa mission metadata, writes
  receipt-backed primitive actions, and creates a local SVG artifact from those
  primitives without desktop control or pasted/imported images.
- Mona Lisa mission advancement now deterministically queues the sandbox canvas
  operation after the first `plan.create` operation. The chat readback preserves
  the plan operation while exposing the queued `sandbox.canvas.paint_mona_lisa`
  operation as the next linked mission task; it does not auto-run the sandbox
  operation or claim a completed painting.
- A read-only Mona Lisa sandbox replay/evaluation readback now exists at
  `GET /operations/sandbox-canvas/mona-lisa/evaluation`. It resolves sandbox
  artifacts by operation ID, run ID, artifact directory, or latest sandbox run;
  replays `operator_actions.jsonl`; verifies the receipt, manifest, SVG,
  hashes, primitive sequence, no-image-import rule, and no-live-desktop-action
  rule; computes a deterministic primitive-contract recognizability heuristic;
  and returns bounded improvement proposals without writing files, approving
  proposals, promoting changes, controlling the desktop, or claiming pixel or
  visual-similarity evidence.
- A guarded Mona Lisa sandbox evaluation recording path now exists at
  `POST /operations/sandbox-canvas/mona-lisa/evaluation/record`. It requires
  `operations.write`, passes through the operator posture write guard, records
  the read-only replay evaluation into per-run durable review artifacts, writes
  a follow-up queue item, writes proposed-not-promoted improvement records, and
  exposes read-only queue/proposal readbacks at
  `GET /operations/sandbox-canvas/mona-lisa/evaluation-queue` and
  `GET /operations/sandbox-canvas/mona-lisa/improvement-proposals`.
- Orb semantic operator state is now mapped from existing Francis substrate
  readbacks instead of private UI state. `/system/orb` reports idle, queued,
  acting, completed, blocked, and faulted states from mission/operation backlog
  and handback evidence, and `/lens/mcp/status` carries that read-only semantic
  state into the overlay body-state projection without changing the locked Orb
  visuals or granting authority.

## Current Task

The current task is the minimum truthful vertical slice plus the first durable
improvement-channel surface. The latest completed sub-slice maps Orb semantic
operator state from mission/operation substrate readbacks into `/system/orb`,
`/lens/mcp/status`, and overlay runtime status receipts without changing the
locked Orb visuals or claiming execution authority.

Acceptance criteria for the completed observation sub-slice:

- `/lens/mcp/observe` exists on the existing Lens API surface
- the contract requires an overlay coordinate/boundary model
- missing overlay context is blocked before screen/session readback
- successful observation is metadata-only and read-only
- receipts distinguish requested, mapped, and actually inspected regions
- screenshots, pixels, OCR, and accessibility evidence remain unknown unless a
  future adapter truthfully provides them
- no new overlay application or lens app is created

Acceptance criteria for the completed Mona Lisa mission-ingress sub-slice:

- natural-language `paint the Mona Lisa` / `draw the Mona Lisa` intent routes
  through existing chat mission ingress, not a new command engine
- mission creation still passes through posture and permission gates
- mission metadata marks sandbox execution as required and not yet executed
- lens/overlay observation is required but not claimed as observed
- first operation is a queued `plan.create`, not a desktop action
- operation input/metadata preserve the sandbox/lens/orb contract
- Orb embodiment projection is read-only, mission-backed, and preserves visual
  lock
- no completed painting, artifact, pasted image, screenshot, pixel capture, or
  live desktop action is claimed

Acceptance criteria for the completed sandbox canvas operator sub-slice:

- the sandbox adapter is registered as an executor capability, not a standalone
  app or command engine
- the operation action maps through the existing operations runtime
- the adapter consumes mission metadata, operator contract, and lens/overlay
  observation metadata supplied by the Mona Lisa mission
- live desktop execution and image paste/import requests are refused
- execution writes `operator_actions.jsonl`, `manifest.json`, `receipt.json`,
  and an SVG artifact when not in dry-run mode
- the SVG is generated from discrete operator primitives and contains no image
  import
- the receipt records sandbox status, canvas bounds, requested/mapped/actual
  observation regions, Orb embodiment projection, artifact hashes, primitive
  count, governance, and truthful limitations
- operation run/readback exposes trace, run, artifact, mission, and memory
  receipt handles through the existing operation projection

Acceptance criteria for the completed sandbox replay/evaluation recording
sub-slice:

- recording requires `operations.write` and the existing operator posture write
  guard
- read-only evaluation remains separate from the mutating record route
- evaluation records, queue items, and improvement proposals are stored under
  the sandbox run artifact directory
- queue/proposal readback routes are read-only
- proposal records remain `proposed_not_promoted`
- recording does not run an operation, control the desktop, approve proposals,
  promote changes, claim visual similarity, or claim live desktop perception

Acceptance criteria for the completed Orb semantic-state sub-slice:

- Orb semantic state is derived from mission/operation substrate readbacks, not
  private UI state
- `/system/orb` exposes idle, queued, acting, completed, blocked, and faulted
  semantic states with count evidence and focus references
- failed tasks, failed missions, and deadlettered missions project as faulted
  state without hiding the underlying receipt/focus references
- Lens MCP body-state readback carries the Orb semantic state to
  `/lens/mcp/status`
- overlay runtime status JSON preserves semantic state fields for receipt and
  status readback
- the mapping remains read-only, preserves the visual lock, and grants no
  execution or mutation authority

## Pending Tasks

- Add structured observation receipts that include requested region, mapped
  overlay region, actual inspected region, source, status, evidence reference,
  inferred information, confidence, unknowns, and failure/refusal reason to the
  Mona Lisa mission/operator receipt chain.
- Improve Mona Lisa recognizability scoring with offline fixture or pixel
  evidence only when that evidence path is truthfully labeled as fixture,
  replay, sandbox, or live.
- Add replay/evaluation review scoring that can classify repeated failures
  across multiple sandbox runs without promoting proposals automatically.

## Architecture Map

Current Orb rendering path:

- Chat UI inline presenter: `apps/chat_ui/src/lens/orbGlyph.ts`
- Desktop overlay renderer: `scripts/lens-overlay-window.ps1`
- Overlay visual projection: `New-OrbVisualProjection`
- Desktop Orb surface: `New-OrbEnergySurface`

Current Orb state path:

- Substrate status: `src/francis/world_state/orb.py`
- System API routes: `/system/orb`, `/system/orb-status`, `/system/orb_status`
- Lens/Orb MCP body-state bridge: `src/francis/lens/mcp_status_bridge.py`
- Chat UI Lens MCP status parsing: `apps/chat_ui/src/lens/`

Current overlay path:

- Runtime host: `scripts/lens-overlay-window.ps1`
- Preflight: `scripts/lens-overlay-preflight.ps1`
- API authority and execution routes: `src/francis/api/routes/lens.py`
- Runtime state: `data/runtime/lens-overlay/status.json`

Current operator path:

- Mission store/runtime: `src/francis/missions/`
- Operation runtime: `src/francis/operations/runtime.py`
- Sandbox canvas adapter: `src/francis/agent/sandbox_canvas.py`
- MCP gateway bounded command surface: `src/francis/mcp_gateway/tools.py`
- Screen/session readback: `src/francis/screen_readback/tools.py`
- Takeover/input status surfaces exposed through MCP readbacks

Current voice path:

- Overlay voice runtime and wake listener: `scripts/lens-overlay-window.ps1`
- Voice setup helper: `scripts/lens-elevenlabs-voice-setup.ps1`
- Voice/LLM routing: `src/francis/chat/router.py`, `src/francis/api/routes/chat.py`
- Model/audio configuration: `config/models/specialized/audio.yaml`
- Settings and LLM adapter: `src/francis/settings.py`, `src/francis/llm/client.py`

Current receipt path:

- Lens MCP perception receipts: `data/lens/mcp_perception/*.json`
- Overlay runtime voice receipts: `data/runtime/lens-overlay/voice-status.json`
- Overlay voice-turn receipts: `data/runtime/lens-overlay/voice-turns/*.json`
- MCP gateway receipts: `.francis/mcp_gateway/receipts/*.json`
- Mission records and history: `data/missions/`
- Artifact and memory receipt surfaces exposed through existing API routes

Current governance path:

- API permission gate: `src/francis/governance/api_permission_gate.py`
- Lens authority routes and receipt readbacks: `src/francis/api/routes/lens.py`
- Mission write posture guard: `src/francis/api/routes/missions.py`
- System write posture guard: `src/francis/api/routes/system.py`
- MCP read-only versus approval-gated tool metadata:
  `src/francis/mcp_gateway/tools.py`

Current mission/event path:

- Mission API: `src/francis/api/routes/missions.py`
- Mission storage: `src/francis/missions/store.py`
- Mission runtime: `src/francis/missions/runtime.py`
- Reactor/event and telemetry surfaces remain candidates for receipt/replay
  wiring as the vertical slice progresses.

Safest integration seams:

- Continue extending `src/francis/lens/mcp_perception.py` only as the
  overlay-bound observation adapter, not as a second lens app.
- Add tests around `src/francis/lens/mcp_status_bridge.py` and
  `src/francis/screen_readback/tools.py` before adding new perception fields.
- Add mission metadata for Orb/lens/operator correlation rather than creating a
  separate mission engine.
- Continue extending the sandbox canvas operator only as a bounded adapter with
  receipts and explicit sandbox status.

Prohibited or high-risk surfaces:

- Do not create a second overlay application.
- Do not create a separate lens app.
- Do not let voice directly animate the Orb or control the desktop.
- Do not let the Orb UI manipulate the desktop directly.
- Do not claim screenshots, pixels, OCR, accessibility, or desktop vision unless
  an observation adapter returned evidence.
- Do not enable always-on microphone capture by default.
- Do not hardcode or commit API keys.
- Do not bypass mission routing, policy gates, or receipts.

## Lens-To-Overlay Wiring Rule

The transparent overlay is the desktop-space host. It owns monitor, viewport,
coordinate, application/window, canvas, Orb movement, pass-through, and
interaction-state boundaries.

The lens is the substrate-backed observation interface that operates through the
overlay when desktop-space perception is required. It must not operate without
the overlay coordinate and boundary model for desktop-space observations.

Required path:

Francis mission -> governed observation request -> lens contract -> transparent
overlay region and coordinate mapping -> approved capture or observation adapter
-> structured observation result -> receipt -> operator planning -> governed
desktop action -> post-action observation through the same lens/overlay path ->
verification receipt.

Every observation must distinguish:

- requested region
- mapped overlay region
- actual captured or inspected region
- observation source
- live, simulated, fixture, or replay status
- evidence artifact or safe reference
- inferred information
- confidence
- unknown information
- failure or refusal reason

## Voice-To-Orb Wiring Rule

Voice enters Francis. Francis creates governed substrate state. The Orb visibly
represents that real state.

Required path:

voice input -> voice input receipt -> transcript receipt -> Francis intent
interpretation -> mission creation -> governance -> Orb state transition ->
lens/overlay observation when needed -> desktop operator action when authorized
-> verification -> Francis response -> TTS -> playback result -> final linked
receipt.

Voice must not connect ElevenLabs directly to Orb animations or desktop controls.

Every voice input/output must produce or attach to receipts for microphone/session
start and stop, provider request, transcription, interpretation, mission routing,
authority decision, generated response text, TTS generation, audio artifact,
playback attempt, playback result, provider failure, and unavailable or
unconfigured state.

## Assumptions

- No new user approval is available during unattended execution.
- Live external provider calls should be avoided unless configuration already
  exists and the specific path is authorized.
- The Mona Lisa demonstration should start in a Francis-owned sandbox canvas
  unless the existing governed live desktop path is verified safe.
- Current screen readback is read-only and does not claim screenshots, pixels, or
  OCR.
- Existing dirty work belongs to the user or prior sessions and must be preserved.

## Validation Ledger

This validation ledger records Orb, voice, Lens, overlay, and sandbox evidence
only. Completion-model and Stage 17 validations are intentionally out of scope
for this Orb continuation state.

Validation for this checkpoint must include:

- `python -m pytest tests/test_orb_phase0_contracts.py -q` passed with
  `4 passed`.
- `python -m ruff check --no-cache tests/test_orb_phase0_contracts.py` passed.
- `git diff --check -- docs/operations/ORB_VISUAL_LOCK.md
  docs/operations/ORB_CONTINUUM_STATE.md tests/test_orb_phase0_contracts.py
  docs/operations/COMPLETION_LEDGER.md` passed.

Validated for the overlay-bound Lens observation sub-slice:

- `python -m pytest tests/unit/test_lens_mcp_perception.py
  tests/unit/test_lens_orb_mcp_status_bridge.py
  tests/unit/test_lens_orb_mcp_status_route.py
  tests/test_api_contract_chat_ui.py tests/test_orb_phase0_contracts.py -q`
  passed with `21 passed`.
- `python -m ruff check --no-cache src/francis/lens/mcp_perception.py
  src/francis/lens/mcp_status_bridge.py src/francis/lens/__init__.py
  src/francis/api/routes/lens.py tests/unit/test_lens_mcp_perception.py
  tests/unit/test_lens_orb_mcp_status_bridge.py
  tests/unit/test_lens_orb_mcp_status_route.py
  tests/test_api_contract_chat_ui.py tests/test_orb_phase0_contracts.py`
  passed.
- `python -m ruff format --check --no-cache` on the same files passed with
  `9 files already formatted`.
- TestClient probe of `POST /lens/mcp/observe` returned
  `kind=francis.lens.overlay.observation`, `status=observed`,
  `mapped=mapped`, `source=francis.screen.session`,
  `receipt_decision=observed`, `screenshots=false`, and `pixels=false`.

Validated for the Mona Lisa sandbox mission-ingress sub-slice:

- `python -m pytest
  tests\test_api_chat.py::test_chat_mission_command_declares_queued_mission_with_loop_context
  tests\test_api_chat.py::test_chat_mona_lisa_voice_intent_declares_truthful_sandbox_mission
  tests\test_api_chat.py::test_chat_send_basic_mode_answers_voice_hearing_probe
  tests\test_api_chat.py::test_chat_websocket_structured_message_declares_mission
  -q` passed with `4 passed`.
- `python -m ruff check --no-cache src\francis\chat\router.py
  src\francis\api\routes\chat.py src\francis\missions\runtime.py
  tests\test_api_chat.py` passed.
- `python -m ruff format --check --no-cache src\francis\chat\router.py
  src\francis\api\routes\chat.py src\francis\missions\runtime.py
  tests\test_api_chat.py` passed with `4 files already formatted`.

Validated for the Mona Lisa sandbox canvas operator sub-slice:

- `python -m pytest
  tests\test_api_operations.py::test_operations_run_mona_lisa_sandbox_canvas_from_chat_mission
  -q` passed.
- `python -m ruff check --no-cache src\francis\agent\sandbox_canvas.py
  src\francis\agent\executor.py src\francis\operations\runtime.py
  src\francis\api\routes\operations.py tests\test_api_operations.py` passed.
- `python -m ruff format --check --no-cache
  src\francis\agent\sandbox_canvas.py src\francis\agent\executor.py
  src\francis\operations\runtime.py src\francis\api\routes\operations.py
  tests\test_api_operations.py` passed with `5 files already formatted`.
- A local TestClient runtime review using temporary actor scopes created mission
  `msn_20260618_032722_946ff033`, ran operation
  `tsk_20260618_032722_4793b14d`, and produced sandbox artifact
  `data\sandbox_canvas\mona_lisa\run_1781753242_e6103710\mona_lisa_sandbox.svg`
  plus receipt
  `data\sandbox_canvas\mona_lisa\run_1781753242_e6103710\receipt.json`.

Validated for the automatic Mona Lisa sandbox queueing sub-slice:

- `python -m pytest
  tests\test_api_chat.py::test_chat_mona_lisa_voice_intent_declares_truthful_sandbox_mission
  tests\test_api_operations.py::test_operations_run_mona_lisa_sandbox_canvas_from_chat_mission
  tests\test_mission_runtime.py tests\unit\test_lens_mcp_perception.py
  tests\test_orb_phase0_contracts.py -q` passed with `17 passed`.
- `python -m ruff check --no-cache src\francis\missions\runtime.py
  src\francis\api\routes\chat.py tests\test_api_chat.py
  tests\test_api_operations.py` passed.

Validated for the Mona Lisa sandbox replay/evaluation sub-slice:

- `python -m pytest
  tests\test_api_operations.py::test_operations_run_mona_lisa_sandbox_canvas_from_chat_mission
  -q` passed.
- `python -m ruff check --no-cache src\francis\agent\sandbox_canvas.py
  src\francis\api\routes\operations.py tests\test_api_operations.py` passed.
- `python -m ruff format --check --no-cache
  src\francis\agent\sandbox_canvas.py src\francis\api\routes\operations.py
  tests\test_api_operations.py` passed with `3 files already formatted`.
- The focused test verified `GET /operations/sandbox-canvas/mona-lisa/evaluation`
  by operation ID, including read-only governance, primitive replay, hash
  checks, no live desktop actions, no SVG image import, no visual-similarity
  claim, a positive primitive-contract recognizability heuristic, bounded
  improvement proposals, and blocked readback for a missing artifact directory.

Validated for the Mona Lisa sandbox durable review queue sub-slice:

- `python -m pytest
  tests\test_orb_phase0_contracts.py
  tests\test_api_operations.py::test_operations_run_mona_lisa_sandbox_canvas_from_chat_mission
  -q` passed.
- `python -m ruff check --no-cache src\francis\agent\sandbox_canvas.py
  src\francis\api\routes\operations.py tests\test_api_operations.py
  tests\test_orb_phase0_contracts.py` passed.
- `python -m ruff format --check --no-cache
  src\francis\agent\sandbox_canvas.py src\francis\api\routes\operations.py
  tests\test_api_operations.py tests\test_orb_phase0_contracts.py` passed.
- `git diff --check -- src\francis\agent\sandbox_canvas.py
  src\francis\api\routes\operations.py tests\test_api_operations.py
  tests\test_orb_phase0_contracts.py docs\operations\ORB_CONTINUUM_STATE.md
  docs\operations\COMPLETION_LEDGER.md` passed.
- The focused test verified the guarded evaluation record route, per-run durable
  evaluation/queue/proposal artifact creation, read-only queue/proposal
  readbacks, proposed-not-promoted proposal status, and governance flags showing
  no operation run, desktop control, proposal approval, promotion, visual
  similarity claim, or live desktop perception claim.

Validated for the Orb semantic-state substrate sub-slice:

- `python -m pytest
  tests\unit\test_kernel_contracts.py::test_orb_semantic_operator_state_maps_substrate_counts
  tests\unit\test_kernel_contracts.py::test_orb_snapshot_handback_preserves_exact_mission_approval_handoff
  tests\unit\test_lens_orb_mcp_status_bridge.py -q` passed.
- `python -m pytest tests\test_lens_overlay_window_script.py
  tests\test_orb_phase0_contracts.py -q` passed.
- PowerShell parser check for `scripts\lens-overlay-window.ps1` returned
  `parse_ok`.
- `cd apps\chat_ui; node --test --experimental-strip-types
  src\lens\mcpStatus.test.ts src\lens\orbGlyph.test.ts` passed with
  `11 passed`.

## Blockers

- The lens/overlay observation contract is metadata-only; it does not yet provide
  screenshots, pixels, OCR, accessibility tree, or visual similarity evidence.
- No screenshot or pixel observation adapter is currently claimed by the read-only
  screen readback contract.
- Mission advancement now queues the sandbox canvas operation automatically, but
  operator execution is still a separate bounded operation run.
- The sandbox artifact has no automated screenshot/pixel visual similarity score
  yet. The current evaluator has only a deterministic primitive-contract
  recognizability heuristic.
- No live desktop painting run is verified safe.
- Voice can produce receipts and route through chat, and a narrow Mona Lisa
  phrase can create mission state when transcribed, but the full voice ->
  mission -> automatic operator dispatch -> Orb loop is not complete.
- True backend model-call cancellation is not currently supported; stale reply
  suppression is the bounded behavior.

## Receipt And Artifact Locations

- `data/runtime/lens-overlay/status.json`
- `data/runtime/lens-overlay/voice-status.json`
- `data/runtime/lens-overlay/voice-turn-status.json`
- `data/runtime/lens-overlay/voice-turns/*.json`
- `data/lens/mcp_perception/*.json`
- `data/sandbox_canvas/mona_lisa/*/operator_actions.jsonl`
- `data/sandbox_canvas/mona_lisa/*/manifest.json`
- `data/sandbox_canvas/mona_lisa/*/receipt.json`
- `data/sandbox_canvas/mona_lisa/*/mona_lisa_sandbox.svg`
- `data/sandbox_canvas/mona_lisa/*/evaluation_records/*.json`
- `data/sandbox_canvas/mona_lisa/*/review_queue/*.json`
- `data/sandbox_canvas/mona_lisa/*/improvement_proposals/*.json`
- `.francis/mcp_gateway/receipts/*.json`
- `data/missions/*/record.json`
- `data/missions/*/history.jsonl`
- `data/artifacts/`

## Repository State

- Branch: `main`
- Last observed head: `bf9f76bf docs(stage17): record quality evidence remediation for catalog pack`
- Worktree: dirty before this checkpoint; preserve unrelated changes.

## Exact Next Action

Add structured observation receipts to the Mona Lisa mission/operator receipt
chain so requested, mapped, and actual inspected regions, source/status,
evidence reference, inferred information, confidence, unknowns, and
failure/refusal reasons are carried as governed receipt truth.
