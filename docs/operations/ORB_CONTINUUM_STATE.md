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
- The Lens observation contract now reports explicit coordinate-boundary
  readback in `mapped_overlay_region.coordinate_boundary`, including
  coordinate space, overlay/requested edges, intersection region, outside
  edges, clipped status, bounds-checked status, and refusal reasons without
  claiming screenshots, pixels, OCR, accessibility, or visual similarity.
- The Lens observation contract now also reports explicit coordinate-transform
  readback in `mapped_overlay_region.coordinate_transform`, including requested
  to mapped deltas, overlay origin, overlay-local region, clipped
  overlay-local intersection, transform confidence basis, and limitations
  without claiming visual registration or capture.
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
- Structured observation receipts now carry the Mona Lisa mission/operator
  receipt chain. Mission ingress declares the required receipt schema, the
  sandbox operation carries the contract forward without claiming observation,
  sandbox execution writes requested/mapped/actual regions, source/status,
  evidence references, inferred information, confidence, unknowns, and
  failure/refusal reason into the run receipt, and replay/evaluation readbacks
  preserve that evidence without adding live desktop perception or authority.
- Mona Lisa sandbox recognizability scoring now includes a repo-local offline
  SVG geometry fixture. The evaluator blends the original primitive replay
  heuristic with fixture-labeled geometry/feature evidence, reports fixture ref
  and hash, and explicitly marks pixel evidence, reference-image use, and visual
  similarity claims as false.
- Replay/evaluation review scoring now classifies sandbox evaluation history
  across multiple recorded runs. The read-only evaluation queue response reports
  pass/fail counts, repeated failure classes, proposal counts, and next review
  action without writing files, running operations, approving proposals, or
  promoting changes.
- A read-only Orb/voice/overlay-lens validation proof now exists at
  `scripts/orb-voice-overlay-lens-validation.ps1`. It reads current overlay
  status, Lens MCP body-state, ChatGPT voice connector status, ChatGPT voice
  bridge receipts, Orb substrate status, and Mona Lisa sandbox replay status
  without starting tunnels, calling voice providers, launching desktop actions,
  changing Orb visuals, or claiming Stage 6 closure.
- ChatGPT voice connector control now has a bounded persistent HTTPS MCP URL
  record path. `scripts/chatgpt-voice-connector.ps1 -Mode RecordUrl` validates
  an operator-supplied HTTPS `/mcp` URL, writes only local runtime connector
  state, and does not start LocalTunnel, open a public tunnel, call ChatGPT,
  grant execution authority, or claim reachability.
- ChatGPT voice connector control now has a read-only persistent ingress plan
  mode. `scripts/chatgpt-voice-connector.ps1 -Mode PlanPersistentIngress`
  reports the local MCP endpoint, connector URL shape state, provider-tool
  readiness, and the governed `RecordUrl` handoff without writing runtime state,
  starting a process, opening a tunnel, or granting authority.
- ChatGPT voice connector control now has a bounded Cloudflare named-tunnel
  start path. `scripts/chatgpt-voice-connector.ps1 -Mode StartCloudflaredNamed`
  requires an explicit tunnel name, stable hostname, and `-ExposePublicTunnel`,
  records `ingress_mode=cloudflared_named_tunnel`, starts only recognized
  Francis connector processes, and reports the named tunnel separately from
  quick Cloudflare tunnels or LocalTunnel fallbacks without granting execution
  or mutation authority beyond connector runtime state.
- ChatGPT voice bridge transcript guards now reject `Transcript Unavailable`
  turns even when ChatGPT appends filler text after the unavailable marker. The
  bridge writes a rejected-turn receipt and does not forward the filler into
  Francis chat, the mission path, or the conversation ledger.
- The Orb/voice/overlay-lens validation proof now distinguishes a ChatGPT-source
  receipt from a usable ChatGPT transcript receipt. `Transcript Unavailable`
  receipts are counted and surfaced separately, and they do not satisfy the
  end-to-end usable transcript check.
- The Orb/voice/overlay-lens validation proof now embeds the read-only
  persistent ingress plan, so a connector URL failure includes local endpoint
  and provider-tool readiness without starting a tunnel or writing state.
- The persistent ingress plan now also reports local installer readiness and
  bounded install/configuration command hints. The plan remains read-only; it
  does not install providers or create public ingress.
- ChatGPT voice connector URL resolution now has explicit source tracking.
  Status, plan, and `RecordUrl` resolve URLs from an explicit argument, then
  `FRANCIS_CHATGPT_VOICE_CONNECTOR_URL`, then recorded runtime state, and report
  `connector_url_source` without starting tunnels or granting authority.
- The Orb/voice/overlay-lens validation proof no longer treats HTTPS `/mcp` URL
  shape as end-to-end proof. A shape-valid connector URL without a verified MCP
  reachability probe or fresh ChatGPT tool-call evidence reports
  `proof_partial_connector_reachability_unverified`.
- ChatGPT voice connector reachability verification now has an explicit bounded
  timeout. The Python connector probe defaults to five seconds, the MCP status
  script and connector wrapper pass the timeout through, and the Orb proof
  reports `connector_probe_timeout_seconds` without executing Francis tools,
  calling a model, opening a tunnel, or writing receipts.
- The Orb/voice/overlay-lens validation proof now separates historical ChatGPT
  voice receipts from fresh live-proof receipts. ChatGPT-source receipts outside
  the freshness window remain visible for diagnosis, but they no longer satisfy
  the live ChatGPT-origin receipt checks.
- ChatGPT voice bridge receipts now include both numeric `created_ts` and
  human-readable UTC `created_at` fields derived from the same timestamp. This
  improves receipt auditability without changing transcript forwarding,
  authority, or freshness rules.
- ChatGPT voice bridge receipts now include bounded ingress provenance fields:
  `ingress_transport`, `mcp_gateway_tool`, `mcp_server_tool`, and
  `mcp_server_transport`. The MCP gateway stamps internal tool-origin receipts,
  the public MCP server stamps the exported `francis_chatgpt_voice_ingress` tool
  name and its server transport, and the validation proof requires fresh usable
  `streamable-http` public-MCP transport evidence instead of trusting
  `source=chatgpt.voice` or MCP-shaped internal dispatch alone.
- Overlay voice-turn handback readback now formats `completed_at` through an
  invariant UTC timestamp helper so PowerShell cannot emit culture-specific date
  strings on Linux CI while preserving the voice-turn handback contract.
- ChatGPT voice connector persistent-ingress planning now classifies LocalTunnel
  URLs as `localtunnel_ephemeral`. A `.loca.lt` URL can remain an explicit
  fallback for live connector testing, but it no longer satisfies the
  persistent `RecordUrl` path or reports as a stable ingress candidate.
- The desktop overlay Orb now defaults to docked operator presence with
  `right_corner_locked` motion anchored at the bottom-right corner, so it does
  not behave like a screensaver. Manual drag is an explicit opt-in diagnostic
  mode, and bounded `bounded_desktop_roam` remains an explicit opt-in runtime
  mode for diagnostic or intentional movement. Runtime status still writes
  `overlay_position` with current window coordinates, work-area roam bounds,
  dock/drag support, and explicit no-authority flags, so Francis can show live
  Orb location truth without changing the locked visual face or claiming
  screen-capture authority.

## Current Task

The current task is the minimum truthful vertical slice plus the first durable
improvement-channel surface. The latest completed sub-slice maps Orb semantic
operator state from mission/operation substrate readbacks into `/system/orb`,
`/lens/mcp/status`, and overlay runtime status receipts without changing the
locked Orb visuals or claiming execution authority.

The latest completed receipt sub-slice adds structured observation receipts to
the Mona Lisa mission/operator chain. It is receipt/schema work only: it does
not add screenshots, pixels, OCR, live desktop perception, proposal approval,
promotion, or execution authority.

The latest completed lens/overlay spatial sub-slice strengthens
`/lens/mcp/observe` with explicit `coordinate_boundary` and
`coordinate_transform` readback for mapped and blocked regions. It records
overlay edges, requested edges, intersection region, outside edges, clipped
status, bounds-check status, requested-to-mapped deltas, overlay origin,
overlay-local region, clipped overlay-local intersection, and transform
confidence basis while preserving the metadata-only observation boundary.

The latest completed recognizability sub-slice adds offline fixture evidence for
the sandbox Mona Lisa artifact. It remains SVG/action replay evidence and does
not claim screenshot, OCR, accessibility, human recognizability, or live
visual-similarity proof.

The latest completed sandbox raster sub-slice writes a deterministic PNG
preview generated from the same sandbox operator primitives. This is sandbox
primitive pixel replay evidence only; it is not a desktop screenshot, live
capture, external reference-image comparison, human recognizability proof, or
visual-similarity score.

The latest completed post-action observation sub-slice links the sandbox
operator result back into the lens/overlay receipt chain. Fresh sandbox runs now
emit `francis.lens.overlay.post_action_observation_receipt` with the same
requested, mapped, and actual canvas regions as the structured observation
receipt. The post-action receipt references the action log, manifest, SVG, and
raster preview artifacts; it remains sandbox replay evidence and does not claim
screenshots, live desktop pixels, OCR, accessibility, visual similarity, or a
second overlay/lens application.

The latest completed improvement-channel sub-slice makes sandbox Mona Lisa
improvement proposals evidence-aware. When raster replay and post-action
observation receipts are present, the durable proposal channel no longer asks to
add generic sandbox pixel evidence. It proposes
`sandbox_canvas_plan_governed_live_observation_adapter`, which is a bounded
planning proposal for a future governed live observation adapter and remains
`proposed_not_promoted`.

The latest completed review-scoring sub-slice adds read-only aggregate review
evidence across recorded sandbox evaluation queue items. It identifies repeated
failure patterns and review actions, but it does not execute another run,
promote an improvement, or approve a proposal.

The latest completed validation-proof sub-slice adds the status-only proof
script for Orb/voice/overlay-lens continuity. The current live proof result
from `2026-06-19` is `proof_blocked_no_chatgpt_app_source_receipt`: the proof
found no fresh ChatGPT-source receipt in the current data window, no fresh
public `streamable-http` MCP server receipt, and no fresh usable public-MCP
transcript receipt. This is a truthful blocked proof state, not a voice-provider
failure and not an Orb visual issue.

If a stable connector URL is supplied through
`FRANCIS_CHATGPT_VOICE_CONNECTOR_URL`, the proof now records the URL source and
checks the shape without writing runtime state. Shape-valid but unverified URLs
remain partial proof until reachability and a fresh usable receipt from the
public ChatGPT voice MCP ingress tool confirm the bridge.

If connector verification is requested, the reachability probe is bounded by
`ConnectorProbeTimeoutSeconds` and remains read-only.

ChatGPT-origin voice receipts also have a bounded live-proof freshness window.
The default is 900 seconds. Receipts outside that window are counted as stale
and do not satisfy the live proof; source-only receipts without
`mcp_server_tool=francis_chatgpt_voice_ingress` remain diagnostic evidence, not
end-to-end MCP proof. Receipts with the MCP server tool but no
`mcp_server_transport=streamable-http` are now preserved for diagnosis but do
not satisfy the public ChatGPT connector proof.

Acceptance criteria for the completed observation sub-slice:

- `/lens/mcp/observe` exists on the existing Lens API surface
- the contract requires an overlay coordinate/boundary model
- missing overlay context is blocked before screen/session readback
- successful observation is metadata-only and read-only
- receipts distinguish requested, mapped, and actually inspected regions
- mapped regions include explicit coordinate-boundary readback with overlay
  edges, requested edges, intersection region, outside edges, and bounds status
- mapped regions include explicit coordinate-transform readback with
  source/target spaces, requested-to-mapped deltas, overlay origin,
  overlay-local region, clipped overlay-local intersection, transform
  confidence basis, and metadata-only limitations
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

Acceptance criteria for the completed structured observation receipt sub-slice:

- Mona Lisa mission ingress declares the structured observation receipt schema
  before any observation or sandbox execution is claimed
- the queued sandbox canvas operation carries the observation receipt contract
  as `contract_carried_to_sandbox_operation_not_recorded`
- sandbox execution writes `structured_observation_receipts` into the durable
  run receipt and mirrors the first structured receipt inside
  `lens_overlay_observation`
- each structured receipt includes requested region, mapped overlay region,
  actual inspected region, source, status, evidence reference, inferred
  information, confidence, unknowns, and failure/refusal reason
- sandbox evidence references point at local manifest/actions/artifact refs and
  hashes without embedding raw content
- replay/evaluation readback preserves the structured observation receipts and
  checks that the receipt references the sandbox manifest and live desktop
  pixels remain unknown
- the receipt path remains sandbox/read-only evidence and grants no desktop
  control, proposal approval, promotion, execution authority, or mutation
  authority

Acceptance criteria for the completed offline recognizability fixture sub-slice:

- recognizability scoring keeps the primitive replay heuristic visible
- a repo-local fixture defines required Mona Lisa feature labels and geometry
  zones without using a reference image
- evaluation readback reports fixture ref, fixture hash, target, source,
  evidence mode, feature matches, zone matches, score, and pass/fail state
- the fixture path is labeled `offline_svg_geometry`
- pixel evidence, reference-image use, and visual-similarity claims remain false
- the evaluator degrades truthfully to `fixture_unavailable` if the fixture file
  is unavailable
- proposal output no longer asks to add the offline geometry fixture that now
  exists; future work points toward optional truth-labeled pixel evidence or
  multi-run review scoring

Acceptance criteria for the completed multi-run review scoring sub-slice:

- evaluation queue readback includes a `review_scoring` aggregate
- scoring is read-only and derived only from recorded queue items
- scoring reports total records, pass/fail counts, improvement proposal count,
  failure-class counts, repeated failure classes, thresholds, and next review
  action
- repeated failure classification requires at least two records with the same
  failure class
- scoring does not write files, run operations, control the desktop, approve
  proposals, or promote changes

## Pending Tasks

- Install or configure a persistent HTTPS ingress provider for
  `http://127.0.0.1:8787/mcp`, then record the actual HTTPS `/mcp` URL with
  `scripts/chatgpt-voice-connector.ps1 -Mode RecordUrl`, so the proof can verify
  the connector URL instead of reporting `connector_url_not_provided`.
- As a non-mutating handoff, a stable URL may also be supplied as
  `FRANCIS_CHATGPT_VOICE_CONNECTOR_URL`; this only proves URL shape unless the
  validation proof is run with connector reachability verification or a fresh
  ChatGPT-origin tool-call receipt is observed.
- When running reachability verification, use the bounded proof path:
  `scripts\orb-voice-overlay-lens-validation.ps1 -VerifyConnector
  -ConnectorProbeTimeoutSeconds 5`.
- When validating a live ChatGPT voice handoff, require a fresh source receipt
  inside the configured freshness window. The default proof uses
  `ChatGptReceiptFreshnessSeconds=900`.
- When validating a live ChatGPT voice MCP handoff, require the receipt to carry
  `mcp_server_transport=streamable-http`. Direct/in-process tool calls and stdio
  MCP roundtrips are useful tests, but they do not prove the public ChatGPT
  connector path.
- Confirm live overlay microphone signal when the operator is present; the
  current safe readback remains `waiting_for_audio_signal`.

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
- ChatGPT voice connector control:
  `scripts/chatgpt-voice-connector.ps1`
- Orb/voice/overlay-lens validation proof:
  `scripts/orb-voice-overlay-lens-validation.ps1`
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

Validated for the structured Mona Lisa observation receipt sub-slice:

- `python -m pytest tests\unit\test_lens_mcp_perception.py
  tests\test_api_chat.py::test_chat_mona_lisa_voice_intent_declares_truthful_sandbox_mission
  tests\test_api_operations.py::test_operations_run_mona_lisa_sandbox_canvas_from_chat_mission
  tests\test_orb_phase0_contracts.py -q` passed with `16 passed`.
- `python -m ruff check --no-cache src\francis\lens\mcp_perception.py
  src\francis\chat\router.py src\francis\missions\runtime.py
  src\francis\agent\sandbox_canvas.py tests\unit\test_lens_mcp_perception.py
  tests\test_api_chat.py tests\test_api_operations.py
  tests\test_orb_phase0_contracts.py` passed.
- `python -m ruff format --check --no-cache` on the same source/test files
  passed with `8 files already formatted`.
- `.venv\Scripts\python.exe -m mypy src\francis\lens\mcp_perception.py
  src\francis\chat\router.py src\francis\missions\runtime.py
  src\francis\agent\sandbox_canvas.py` passed.
- A local TestClient probe confirmed queued contract carry-forward, sandbox
  structured observation receipt status `observed`, source `sandbox`, manifest
  evidence reference present, live desktop unknowns preserved, and replay
  evaluation `passed=true`.

Validated for the offline Mona Lisa recognizability fixture sub-slice:

- `python -m pytest
  tests\test_api_operations.py::test_operations_run_mona_lisa_sandbox_canvas_from_chat_mission
  tests\test_orb_phase0_contracts.py -q` passed with `5 passed`.
- `python -m ruff check --no-cache src\francis\agent\sandbox_canvas.py
  tests\test_api_operations.py tests\test_orb_phase0_contracts.py` passed.
- `python -m ruff format --check --no-cache src\francis\agent\sandbox_canvas.py
  tests\test_api_operations.py tests\test_orb_phase0_contracts.py` passed with
  `3 files already formatted`.
- `.venv\Scripts\python.exe -m mypy src\francis\agent\sandbox_canvas.py`
  passed.
- A local TestClient probe confirmed `classification=repeated_failure_pattern`,
  `failed_count=2`, repeated class `recognizability_threshold_not_met`, next
  action `review_repeated_failures_before_new_proposals`, and
  `promotes_changes=false`.
- A local TestClient probe confirmed replay evaluation `passed=true`,
  recognizability score `1.0`, basis
  `operator_primitive_replay_plus_offline_svg_geometry_fixture_not_pixel_similarity`,
  fixture mode `offline_svg_geometry`, fixture pass, and false
  pixel-evidence/reference-image/visual-similarity claims.

Validated for the multi-run review scoring sub-slice:

- `python -m pytest
  tests\test_api_operations.py::test_operations_run_mona_lisa_sandbox_canvas_from_chat_mission
  tests\test_orb_phase0_contracts.py -q` passed with `5 passed`.
- `python -m ruff check --no-cache src\francis\agent\sandbox_canvas.py
  tests\test_api_operations.py tests\test_orb_phase0_contracts.py` passed.
- `python -m ruff format --check --no-cache src\francis\agent\sandbox_canvas.py
  tests\test_api_operations.py tests\test_orb_phase0_contracts.py` passed with
  `3 files already formatted`.
- `.venv\Scripts\python.exe -m mypy src\francis\agent\sandbox_canvas.py`
  passed.

Validated for the read-only Orb/voice/overlay-lens validation proof sub-slice:

- PowerShell parser check for
  `scripts\orb-voice-overlay-lens-validation.ps1` returned `parse_ok`.
- `python -m pytest tests\test_orb_voice_overlay_lens_validation_script.py -q`
  passed with `2 passed`.
- A live status-only proof run of
  `scripts\orb-voice-overlay-lens-validation.ps1` returned
  `status=proof_partial_current_connector_url_missing`. It confirmed
  `overlay_status_readback=visible`, `lens_mcp_body_state_readback=ready`,
  `overlay_voice_input_readiness=waiting_for_audio_signal`,
  `chatgpt_voice_local_mcp_listener=local_ready_connector_url_needed`,
  `chatgpt_voice_bridge_receipt_observed=observed`,
  `chatgpt_app_source_receipt_observed=observed`, and
  `orb_substrate_readback=orb_status`.
- The same proof reported the current blockers truthfully:
  `chatgpt_voice_public_connector_url=missing` with
  `connector_url_not_provided`, and the persisted Mona Lisa sandbox replay
  evaluated read-only with recognizability score `1.0` but did not pass the
  latest structured-observation receipt checks.
- The proof explicitly preserved `no_orb_visual_change`,
  `no_second_overlay_application`, `no_second_lens_application`,
  `no_voice_direct_to_orb_animation`, no proposal approval, no promotion, and no
  Stage 6 closure claim.

Validated for the fresh structured Mona Lisa sandbox replay refresh:

- A governed TestClient runtime refresh used actor scopes
  `chat.send=["missions.write"]` and `api.operations=["operations.run"]`,
  routed `hey Francis paint the Mona Lisa in sandbox` through `/chat/send`, then
  ran only the queued sandbox operation through `/operations/{operation_id}/run`.
- The refresh created mission `msn_20260618_071446_b8b5e47b`, plan operation
  `tsk_20260618_071446_b3010a3d`, sandbox operation
  `tsk_20260618_071446_02e79510`, and artifact directory
  `data/sandbox_canvas/mona_lisa/run_1781766886_c71910f3`.
- The sandbox run returned `status=succeeded`,
  `output_status=sandbox_completed`, `structured_receipt_count=1`,
  `live_desktop_execution=false`, and `desktop_control=false`.
- `GET /operations/sandbox-canvas/mona-lisa/evaluation` for the sandbox
  operation returned `ok=true`, `status=evaluated`, `passed=true`,
  `structured_observation_receipt_present=true`,
  `structured_observation_evidence_references_manifest=true`,
  `structured_observation_unknowns_live_desktop_pixels=true`,
  `no_live_desktop_actions=true`, recognizability score `1.0`, offline fixture
  pass, `pixel_evidence=false`, and `visual_similarity_claim=false`.
- A live status-only proof run of
  `scripts\orb-voice-overlay-lens-validation.ps1` then returned
  `status=proof_partial_current_connector_url_missing`,
  `next_smallest_truthful_gap=record_current_https_mcp_connector_url_or_replace_tunnel_with_persistent_ingress`,
  `overlay.status=visible`, `overlay.mcp_body_live_status=ready`,
  `overlay.voice_input_status=waiting_for_audio_signal`,
  `chatgpt_voice_connector.local_endpoint_status=local_ready_connector_url_needed`,
  `orb.status=orb_status`, `mona_lisa_sandbox.passed=true`, and
  `mona_lisa_sandbox.artifact_dir=data/sandbox_canvas/mona_lisa/run_1781766886_c71910f3`.

Validated for the sandbox raster-preview evidence sub-slice:

- `src/francis/agent/sandbox_canvas.py` now writes
  `mona_lisa_sandbox_preview.png` beside the sandbox SVG, manifest, actions,
  and receipt when the sandbox run is not a dry run.
- The raster preview is generated from recorded sandbox operator primitives
  with mode `sandbox_operator_primitive_raster_replay`; the manifest, receipt,
  structured observation evidence, operation output, and evaluation readback
  all carry the preview path/hash and explicit no-screenshot/no-live-capture/
  no-visual-similarity flags.
- A fresh governed TestClient runtime run created mission
  `msn_20260619_181114_6998b325`, sandbox operation
  `tsk_20260619_181114_e4ce3f2b`, run
  `run_1781892674_0fec5f26`, and trace
  `trace_e26f02e29f9449f9`.
- The fresh sandbox artifact directory is
  `data/sandbox_canvas/mona_lisa/run_1781892674_0fec5f26`.
  The raster preview artifact is
  `data/sandbox_canvas/mona_lisa/run_1781892674_0fec5f26/mona_lisa_sandbox_preview.png`
  with SHA-256
  `cfb4a7b970451b90163e82d1a40629e4293e8f9c4ac6c965f21c8196d64aedac`.
- The recorded evaluation passed with
  `sandbox_raster_evidence.status=evaluated`,
  `sandbox_raster_evidence.evidence_mode=sandbox_operator_primitive_raster_replay`,
  `pixel_evidence=true`, `screenshot=false`,
  `live_desktop_capture=false`, `visual_similarity_claim=false`, and all
  optional raster evidence checks true.
- Manual image inspection confirmed the generated PNG is nonblank primitive
  sandbox output. This is not used as a visual-similarity score or human
  recognizability proof.
- `python -m pytest tests\test_api_operations.py::test_operations_run_mona_lisa_sandbox_canvas_from_chat_mission -q`
  passed.
- `python -m ruff check --no-cache src\francis\agent\sandbox_canvas.py
  tests\test_api_operations.py` passed.
- `python -m ruff format --check --no-cache
  src\francis\agent\sandbox_canvas.py tests\test_api_operations.py` passed.

Validated for the sandbox post-action observation receipt sub-slice:

- Fresh sandbox runs now write a linked
  `francis.lens.overlay.post_action_observation_receipt` under
  `receipt.post_action_observation_receipts[]` and under
  `receipt.lens_overlay_observation.post_action_observation_receipt`.
- The post-action observation receipt uses source
  `sandbox_canvas_post_action_raster_replay`, mode
  `sandbox_operator_primitive_raster_replay`,
  `uses_existing_overlay_coordinate_model=true`, and
  `creates_overlay_application=false`.
- Read-only evaluation now exposes
  `post_action_observation_receipts[]` and
  `optional_post_action_observation_checks` covering parent linkage, same mapped
  overlay region, raster preview reference/hash, no screenshot claim, no live
  desktop pixel claim, and no visual-similarity claim.
- A fresh governed TestClient runtime run created mission
  `msn_20260619_190801_042c76e8`, plan operation
  `tsk_20260619_190801_dd17bb99`, sandbox operation
  `tsk_20260619_190801_1a839f7c`, run
  `run_1781896081_817a667d`, and trace
  `trace_e89bdd06f32d435e`.
- The persisted post-action receipt id is
  `sandbox_canvas_7a30993bc5aa4495.post_action_observation.1`; its parent
  structured observation receipt is
  `sandbox_canvas_7a30993bc5aa4495.observation.1`.
- The fresh artifact directory is
  `data/sandbox_canvas/mona_lisa/run_1781896081_817a667d`.
  The recorded evaluation is
  `data/sandbox_canvas/mona_lisa/run_1781896081_817a667d/evaluation_records/eval_run_1781896081_817a667d_9af0feeadb2b.json`.
  The review queue item is
  `data/sandbox_canvas/mona_lisa/run_1781896081_817a667d/review_queue/queue_run_1781896081_817a667d_9af0feeadb2b.json`.
- The fresh evaluation passed with all
  `optional_post_action_observation_checks` true.
- `python -m pytest tests\test_api_operations.py::test_operations_run_mona_lisa_sandbox_canvas_from_chat_mission -q`
  passed.
- `python -m ruff check --no-cache src\francis\agent\sandbox_canvas.py
  tests\test_api_operations.py` passed.
- `python -m ruff format --check --no-cache
  src\francis\agent\sandbox_canvas.py tests\test_api_operations.py` passed.

Validated for the evidence-aware sandbox improvement proposal sub-slice:

- `src/francis/agent/sandbox_canvas.py` now makes Mona Lisa sandbox improvement
  proposals conditional on current evaluation evidence.
- If raster replay evidence or post-action observation receipts are missing,
  evaluation proposes `sandbox_canvas_complete_replay_evidence_chain`.
- If raster replay evidence and post-action observation receipts are present,
  evaluation proposes
  `sandbox_canvas_plan_governed_live_observation_adapter` instead of the stale
  `sandbox_canvas_add_pixel_or_multi_run_review` proposal.
- A fresh governed TestClient runtime run created mission
  `msn_20260619_191359_30874226`, plan operation
  `tsk_20260619_191359_679c60ad`, sandbox operation
  `tsk_20260619_191359_7dd1309e`, run
  `run_1781896439_9e54f1b2`, and trace
  `trace_abf6aea5f7544b8c`.
- The fresh recorded proposal is
  `data/sandbox_canvas/mona_lisa/run_1781896439_9e54f1b2/improvement_proposals/proposal_1_fe3eac9fbb7f_ceae9080.json`.
  It has `proposal_id=sandbox_canvas_plan_governed_live_observation_adapter`,
  `status=proposed_not_promoted`, `promotion.promoted=false`, and
  `promotion.silent_self_promotion_allowed=false`.
- The proposal validation requirements explicitly require an approved bounded
  live target region, real adapter evidence before labeling capture as live, no
  visual-similarity claim until a governed comparison path exists, and separate
  approval-gated execution, observation, and promotion.
- `python -m pytest tests\test_api_operations.py::test_operations_run_mona_lisa_sandbox_canvas_from_chat_mission -q`
  passed.
- `python -m ruff check --no-cache src\francis\agent\sandbox_canvas.py
  tests\test_api_operations.py` passed.
- `python -m ruff format --check --no-cache
  src\francis\agent\sandbox_canvas.py tests\test_api_operations.py` passed.

Validated for the persistent ChatGPT voice connector URL record path:

- PowerShell parser check for `scripts\chatgpt-voice-connector.ps1` returned
  `parse_ok`.
- `python -m pytest tests\test_chatgpt_voice_connector_script.py -q` passed.
- `python -m ruff check --no-cache tests\test_chatgpt_voice_connector_script.py`
  passed.
- `python -m ruff format --check --no-cache
  tests\test_chatgpt_voice_connector_script.py` passed with
  `1 file already formatted`.
- The focused tests verified that `-Mode RecordUrl` persists a valid HTTPS
  `/mcp` connector URL into runtime state with `ingress_mode=persistent_https`,
  `starts_process=false`, `opens_public_tunnel=false`, `writes_data=true`,
  `grants_execution_authority=false`, and zero MCP/tunnel PIDs.
- The focused tests also verified that non-HTTPS connector URLs are rejected as
  `connector_url_shape_invalid` without writing runtime state, starting a
  process, or opening a tunnel.

Validated for the read-only persistent ingress planning path:

- PowerShell parser check for `scripts\chatgpt-voice-connector.ps1` returned
  `parse_ok`.
- `python -m pytest tests\test_chatgpt_voice_connector_script.py -q` passed
  with `7 passed`.
- A live read-only plan run of
  `scripts\chatgpt-voice-connector.ps1 -Mode PlanPersistentIngress -Json`
  returned `status=persistent_ingress_url_needed`,
  `local_endpoint=http://127.0.0.1:8787/mcp`,
  `connector_url.reason=connector_url_not_provided`,
  `cloudflared.available=false`, `ngrok.available=false`,
  `caddy.available=false`, `ssh.available=true`,
  `starts_process=false`, `opens_public_tunnel=false`, and
  `writes_data=false`.

Validated for the ChatGPT voice unavailable-transcript guard:

- `python -m pytest tests\test_chatgpt_voice_bridge.py -q` passed with
  `7 passed`.
- `python -m ruff check --no-cache src\francis\chatgpt_voice_bridge.py
  tests\test_chatgpt_voice_bridge.py` passed.
- `python -m ruff format --check --no-cache
  src\francis\chatgpt_voice_bridge.py tests\test_chatgpt_voice_bridge.py`
  passed with `2 files already formatted`.
- The focused tests verified that exact `Transcript Unavailable` turns and
  `Transcript Unavailable` followed by filler text are rejected with
  `reason=transcript_unavailable`, `chat_forward.forwarded=false`, receipt
  writing preserved, no raw audio, no execution authority, and no conversation
  ledger write.

Validated for the usable ChatGPT transcript proof split:

- PowerShell parser check for
  `scripts\orb-voice-overlay-lens-validation.ps1` returned `parse_ok`.
- `python -m pytest tests\test_orb_voice_overlay_lens_validation_script.py -q`
  passed with `3 passed`.
- `python -m ruff check --no-cache
  tests\test_orb_voice_overlay_lens_validation_script.py` passed.
- `python -m ruff format --check --no-cache
  tests\test_orb_voice_overlay_lens_validation_script.py` passed with
  `1 file already formatted`.
- A live status-only proof run of
  `scripts\orb-voice-overlay-lens-validation.ps1` returned
  `status=proof_partial_current_connector_url_missing`,
  `clean_chatgpt_source_count=6`, `usable_chatgpt_source_count=5`,
  `transcript_unavailable_count=1`,
  `latest_usable_chatgpt_source=chatgpt-voice-recorded-a0e54da9ad8646e4`,
  `persistent_ingress_plan.status=persistent_ingress_url_needed`,
  `persistent_ingress_plan.local_mcp_listener.ready=true`,
  `cloudflared.available=false`, `ngrok.available=false`,
  `caddy.available=false`, `ssh.available=true`,
  `winget.available=true`, `choco.available=false`, `scoop.available=false`,
  and install hints for `cloudflared`, `ngrok`, and `caddy` via `winget`,
  `mona_lisa_sandbox.passed=true`, and
  `chatgpt_voice_connector.connector_url_reason=connector_url_not_provided`.

Validated for explicit ChatGPT voice connector URL source and reachability
truth:

- PowerShell parser checks for `scripts\chatgpt-voice-connector.ps1` and
  `scripts\orb-voice-overlay-lens-validation.ps1` returned `parse_ok`.
- `python -m pytest tests\test_chatgpt_voice_connector_script.py
  tests\test_orb_voice_overlay_lens_validation_script.py -q` passed.
- `python -m ruff check --no-cache tests\test_chatgpt_voice_connector_script.py
  tests\test_orb_voice_overlay_lens_validation_script.py` passed.
- `python -m ruff format --check --no-cache
  tests\test_chatgpt_voice_connector_script.py
  tests\test_orb_voice_overlay_lens_validation_script.py` passed with
  `2 files already formatted`.
- A live connector status readback with no current environment URL returned
  `status=not_started`, `connector_url_source=none`,
  `connector_url_shape_valid=false`, `connector_url_reason=connector_url_not_provided`,
  `starts_process=false`, `opens_public_tunnel=false`, and `writes_data=false`.
- A live process-scoped environment URL proof using
  `FRANCIS_CHATGPT_VOICE_CONNECTOR_URL=https://francis-env.example.test/mcp`
  returned `status=proof_partial_connector_reachability_unverified`,
  `next_smallest_truthful_gap=verify_current_https_mcp_connector_reachability_or_trigger_fresh_chatgpt_tool_call`,
  `connector_url_source=environment:FRANCIS_CHATGPT_VOICE_CONNECTOR_URL`,
  `connector_url_shape_valid=true`,
  `connector_reachability_status=verification_not_requested`,
  `connector_usable_for_chatgpt=false`, `starts_process=false`,
  `opens_public_tunnel=false`, and `writes_repo=false`.

Validated for bounded ChatGPT voice connector reachability timeouts:

- PowerShell parser checks for `scripts\chatgpt-voice-mcp.ps1`,
  `scripts\chatgpt-voice-connector.ps1`, and
  `scripts\orb-voice-overlay-lens-validation.ps1` returned `parse_ok`.
- `python -m pytest tests\unit\test_mcp_gateway_connector_probe.py
  tests\test_chatgpt_voice_mcp_script.py
  tests\test_chatgpt_voice_connector_script.py
  tests\test_orb_voice_overlay_lens_validation_script.py -q` passed.
- `python -m ruff check --no-cache src\francis\mcp_gateway\connector_probe.py
  tests\unit\test_mcp_gateway_connector_probe.py
  tests\test_chatgpt_voice_mcp_script.py
  tests\test_chatgpt_voice_connector_script.py
  tests\test_orb_voice_overlay_lens_validation_script.py` passed.
- `python -m ruff format --check --no-cache
  src\francis\mcp_gateway\connector_probe.py
  tests\unit\test_mcp_gateway_connector_probe.py
  tests\test_chatgpt_voice_mcp_script.py
  tests\test_chatgpt_voice_connector_script.py
  tests\test_orb_voice_overlay_lens_validation_script.py` passed with
  `5 files already formatted`.
- The focused tests verified `connector_probe_timeout` behavior without network
  dependency, default timeout propagation through MCP status and connector
  status, and `connector_probe_timeout_seconds=5` in the Orb proof surface.
- A live MCP status readback with
  `-ConnectorProbeTimeoutSeconds 1` returned
  `status=local_ready_connector_url_shape_valid`, `timeout=1`,
  `reachability_verified=false`, `probe_present=false`, `starts_process=false`,
  `opens_public_tunnel=false`, and `writes_data=false`.
- A live process-scoped environment URL proof with
  `-ConnectorProbeTimeoutSeconds 1` returned
  `status=proof_partial_connector_reachability_unverified`,
  `connector_reachability_status=verification_not_requested`,
  `connector_probe_timeout_seconds=1`, `starts_process=false`,
  `opens_public_tunnel=false`, and `writes_repo=false`.
- A live process-scoped environment URL proof with `-VerifyConnector
  -ConnectorProbeTimeoutSeconds 1` returned
  `status=proof_partial_connector_reachability_unverified`,
  `connector_reachability_status=not_verified`,
  `connector_reachability_probe_requested=true`,
  `connector_probe_timeout_seconds=1`, `connector_usable_for_chatgpt=false`,
  `starts_process=false`, `opens_public_tunnel=false`, and `writes_repo=false`.

Validated for fresh versus stale ChatGPT voice receipt proof:

- PowerShell parser check for `scripts\orb-voice-overlay-lens-validation.ps1`
  returned `parse_ok`.
- `python -m pytest tests\test_orb_voice_overlay_lens_validation_script.py -q`
  passed.
- `python -m pytest tests\test_orb_voice_overlay_lens_validation_script.py
  tests\test_chatgpt_voice_connector_script.py
  tests\test_chatgpt_voice_mcp_script.py tests\test_chatgpt_voice_bridge.py -q`
  passed.
- `python -m ruff check --no-cache
  tests\test_orb_voice_overlay_lens_validation_script.py` passed.
- `python -m ruff format --check --no-cache
  tests\test_orb_voice_overlay_lens_validation_script.py` passed with
  `1 file already formatted`.
- A live status-only proof run returned
  `status=proof_blocked_stale_chatgpt_app_source_receipt`,
  `next_smallest_truthful_gap=trigger_fresh_chatgpt_app_voice_tool_call_and_confirm_source_receipt`,
  `fresh_chatgpt_source_count=0`,
  `fresh_usable_chatgpt_source_count=0`, `stale_chatgpt_source_count=6`,
  `clean_chatgpt_source_count=6`, `usable_chatgpt_source_count=5`,
  `freshness_window_seconds=900`, latest ChatGPT receipt age `15569`,
  `starts_process=false`, `opens_public_tunnel=false`, and
  `writes_repo=false`.

Validated for ChatGPT voice bridge receipt timestamps:

- `python -m pytest tests\test_chatgpt_voice_bridge.py -q` passed.
- `python -m ruff check --no-cache src\francis\chatgpt_voice_bridge.py
  tests\test_chatgpt_voice_bridge.py` passed.
- `python -m ruff format --check --no-cache
  src\francis\chatgpt_voice_bridge.py tests\test_chatgpt_voice_bridge.py`
  passed with `2 files already formatted`.
- Focused tests verified `created_ts` and `created_at` on the ingress response
  and persisted receipt file.

Validated for MCP-origin ChatGPT voice receipt provenance:

- `python -m pytest tests\test_chatgpt_voice_bridge.py
  tests\test_mcp_client_roundtrip.py
  tests\test_orb_voice_overlay_lens_validation_script.py -q` passed.
- PowerShell parser check for
  `scripts\orb-voice-overlay-lens-validation.ps1` returned `parse_ok`.
- `python -m mypy src\francis\chatgpt_voice_bridge.py
  src\francis\mcp_gateway\tools.py src\francis\mcp_gateway\server.py` passed.
- Focused tests verified direct HTTP receipts record `ingress_transport=http_api`,
  internal MCP gateway tool calls record `ingress_transport=mcp_gateway_tool`
  and `mcp_gateway_tool=francis.chatgpt_voice.ingress`, public MCP server calls
  record `mcp_server_tool=francis_chatgpt_voice_ingress`, and the validation
  proof refuses source-only receipts as live ChatGPT MCP evidence.

Validated for cross-platform overlay voice-turn handback timestamp readback:

- `python -m pytest tests\test_lens_overlay_window_script.py -q` passed.
- `python -m pytest tests\test_lens_overlay_window_script.py
  tests\test_orb_voice_overlay_lens_validation_script.py -q` passed.
- PowerShell parser check for `scripts\lens-overlay-window.ps1` returned
  `parse_ok`.
- `python -m ruff check --no-cache tests\test_lens_overlay_window_script.py
  tests\test_orb_voice_overlay_lens_validation_script.py` passed.
- `python -m ruff format --check --no-cache
  tests\test_lens_overlay_window_script.py
  tests\test_orb_voice_overlay_lens_validation_script.py` passed.

Validated for live voice-commanded Orb movement:

- The running API initially forwarded `Francis move right` to chat, which proved
  the live service had not loaded the current Orb position command parser.
- The API was restarted on `127.0.0.1:8000`, and the overlay was restarted with
  the same ElevenLabs Emma voice, wake phrase, and overlay flags:
  `-VoiceProvider ElevenLabs`, `-ElevenLabsVoiceName Emma`,
  `-EnableWakeListen`, `-EnableVoiceLlm`, and `-DisableAutonomousMotion`.
- A live POST to `/chatgpt-voice/ingress` with transcript
  `Francis move right` returned `status=orb_position_command_queued`,
  `command=move_orb_right_side`, `reference_type=francis_identity`, and
  `chat_forward.status=suppressed_orb_position_command`.
- The overlay consumed the queued file request, deleted
  `data/runtime/lens-overlay/orb-position-command-request.json`, applied the
  right-side position, and wrote
  `data/runtime/lens-overlay/orb-position-commands/live-francis-right-after-restart-1781904675.json`
  with `status=orb_voice_command_applied`, `applied=true`,
  `overlay_left=1268`, `target_anchor=voice_command_right_side`, and
  `mutation_authority_scope=runtime_overlay_position_only`.
- The queued-file adapter now preserves `reference_type` into overlay voice
  status and applied overlay receipts.
- A live POST to `/chatgpt-voice/ingress` with transcript
  `Francis move left` returned `status=orb_position_command_queued`,
  `command=move_orb_left_side`, `reference_type=francis_identity`, and
  `chat_forward.status=suppressed_orb_position_command`.
- The overlay consumed the left-side request and wrote
  `data/runtime/lens-overlay/orb-position-commands/live-francis-left-reference-1781904853.json`
  with `status=orb_voice_command_applied`, `applied=true`,
  `reference_type=francis_identity`, `overlay_left=48`,
  `target_anchor=voice_command_left_side`, `stores_transcript=false`,
  `conversation_forwarding_suppressed=true`, `grants_execution_authority=false`,
  and `grants_mutation_authority=false`.
- `scripts/lens-command-palette-monitor.ps1 -Mode Probe -EnableVoiceChecks`
  returned `status=healthy`, `overlay_status=visible`,
  `voice_input_status=ready`, `selected_provider=ElevenLabs`,
  `selected_voice=Emma`, `orb_position_command_ready=true`,
  `latest_orb_position_command=move_orb_left_side`,
  `latest_orb_position_command_status=orb_voice_command_applied`,
  `latest_orb_position_command_applied=true`, and
  `latest_orb_position_command_receipt_observed=true`.
- `GET /chatgpt-voice/contract?actor=chatgpt.voice` returned `status=ready`
  with `orb_position_command_accepts_francis_identity_reference=true`.
- `python -m pytest tests\test_chatgpt_voice_bridge.py
  tests\test_lens_overlay_window_script.py::test_lens_overlay_voice_orb_position_command_is_local_and_bounded
  tests\test_lens_command_palette_monitor_script.py::test_lens_command_palette_monitor_probe_records_voice_health
  tests\test_lens_command_palette_monitor_script.py::test_lens_command_palette_monitor_reports_applied_orb_voice_command
  tests\unit\test_lens_orb_mcp_status_route.py -q` passed with `23 passed`.
- PowerShell parser checks for `scripts\lens-overlay-window.ps1` and
  `scripts\lens-command-palette-monitor.ps1` returned `parse_ok`.
- `git diff --check -- scripts\lens-overlay-window.ps1
  scripts\lens-command-palette-monitor.ps1
  src\francis\lens\command_palette_monitor.py
  tests\test_lens_overlay_window_script.py
  tests\test_lens_command_palette_monitor_script.py
  tests\unit\test_lens_orb_mcp_status_route.py` reported no whitespace errors
  aside from the existing Git CRLF warnings for the PowerShell files.
- The locked Orb visual surface was not changed. The only visually sensitive
  file touched was `scripts/lens-overlay-window.ps1`, and the edits were limited
  to command parsing, command-file receipt propagation, and runtime state.

Validated for completion-model readback after the live movement proof:

- The completion model parser was hardened to read wrapped `Roadmap area:`
  paragraphs from `docs/operations/COMPLETION_LEDGER.md` without truncating the
  continuation line.
- `python -m pytest tests\test_completion_model.py
  tests\test_francis_completion_model_script.py -q` passed after adding wrapped
  roadmap-area coverage.
- PowerShell parser check for `scripts\francis-completion-model.ps1` returned
  `parse_ok`.
- `scripts\francis-completion-model.ps1 -Mode Status` returned latest ledger
  title `2026-06-19 - Live Francis identity Orb movement proof` with full
  roadmap area `Stage 6 / Lens MVP, Orb embodiment, voice-to-substrate routing,
  overlay command receipts, and P9 observability.`
- The live API was restarted on `127.0.0.1:8000`, and
  `GET /completion-model/status` returned the same full roadmap area through
  the Python substrate route.

Validated for manual acoustic Orb command proof boundary:

- Local overlay speech-recognition Orb commands now stamp microphone-origin
  metadata and write a durable local Orb-position command receipt when applied.
- Queued ChatGPT/bridge-file Orb commands remain explicitly non-microphone
  origin and do not count as acoustic proof.
- `scripts/lens-command-palette-monitor.ps1` exposes
  `voice_monitor.manual_acoustic_orb_position_proof` so the operator can tell
  whether the acoustic `hey Francis move left/right` proof is observed, stale,
  ready, or missing.
- The sanitized API readback preserves that proof object through
  `/lens/command-palette/monitor` without exposing transcripts.
- PowerShell parser checks for `scripts\lens-overlay-window.ps1` and
  `scripts\lens-command-palette-monitor.ps1` returned `parse_ok`.
- `python -m pytest
  tests\test_lens_command_palette_monitor_script.py::test_lens_command_palette_monitor_probe_records_voice_health
  tests\test_lens_command_palette_monitor_script.py::test_lens_command_palette_monitor_reports_applied_orb_voice_command
  tests\test_lens_command_palette_monitor_script.py::test_lens_command_palette_monitor_reports_acoustic_orb_position_proof
  tests\test_lens_overlay_window_script.py::test_lens_overlay_voice_orb_position_command_is_local_and_bounded
  tests\unit\test_lens_orb_mcp_status_route.py -q` passed with `8 passed`.
- Live monitor readback returned `selected_provider=ElevenLabs`,
  `selected_voice=Emma`, `voice_input_status=ready`,
  `orb_position_command_ready=true`, and
  `manual_acoustic_orb_position_proof.status=ready_for_operator_acoustic_test`
  with `proof_observed=false`, `microphone_signal_observed=true`, and
  `api_injected_text_counts_as_proof=false`.
- The live API, overlay, and command-palette monitor were restarted with the
  patched code loaded. `GET /lens/command-palette/monitor` returned
  `route_status=healthy`, `overlay_status=visible`,
  `voice_input_status=ready`, `orb_position_command_ready=true`,
  `acoustic_proof_status=ready_for_operator_acoustic_test`,
  `acoustic_proof_observed=false`, `api_injected_text_counts_as_proof=false`,
  and `transcript_redacted=true`.
- `scripts/lens-command-palette-monitor.ps1` now accepts
  `-RequireManualAcousticOrbProof`. With that switch, the monitor adds
  `voice_manual_acoustic_orb_position_proof` to the checks list and fails until
  a fresh microphone-origin local speech command and matching applied
  Orb-position receipt are observed.
- Live normal probe returned `status=healthy`, `overlay_status=visible`,
  `voice_input_status=ready`, and
  `manual_acoustic_orb_position_proof.status=ready_for_operator_acoustic_test`.
- Live required-proof probe with `-RequireManualAcousticOrbProof` returned
  exit code `1`, `status=anomaly`,
  anomaly id `voice_manual_acoustic_orb_position_proof`, and evidence
  `no_fresh_acoustic_orb_position_receipt`.

Validated for Lens overlay observation coordinate-boundary/transform readback:

- `src/francis/lens/mcp_perception.py` now reports
  `mapped_overlay_region.coordinate_boundary` for mapped, out-of-bounds, and
  unavailable coordinate-model cases.
- The boundary object records coordinate space, overlay edges, requested edges,
  intersection region, within-bounds status, clipped status, outside edges,
  bounds-checked status, and the unavailable/refusal reason where applicable.
- `src/francis/lens/mcp_perception.py` now also reports
  `mapped_overlay_region.coordinate_transform` with source/target spaces,
  transform-applied status, requested-to-mapped deltas, overlay origin,
  overlay-local region, clipped overlay-local intersection, transform
  confidence basis, and metadata-only limitations.
- Out-of-bounds regions remain blocked before the screen/session MCP readback is
  called. Actual observed/captured regions stay explicitly
  `not_observed`/`not_captured`.
- `python -m pytest tests\unit\test_lens_mcp_perception.py -q` passed with
  `12 passed`.
- `python -m ruff check --no-cache src\francis\lens\mcp_perception.py
  tests\unit\test_lens_mcp_perception.py` passed.
- `python -m ruff format --check --no-cache
  src\francis\lens\mcp_perception.py
  tests\unit\test_lens_mcp_perception.py` passed.
- `git diff --check -- src\francis\lens\mcp_perception.py
  tests\unit\test_lens_mcp_perception.py` reported no whitespace errors.

## Blockers

- The lens/overlay observation contract is metadata-only; it does not yet provide
  screenshots, pixels, OCR, accessibility tree, or visual similarity evidence.
- No screenshot or pixel observation adapter is currently claimed by the read-only
  screen readback contract.
- Mission advancement now queues the sandbox canvas operation automatically, but
  operator execution is still a separate bounded operation run.
- The sandbox artifact now has deterministic primitive pixel replay through a
  generated PNG preview, but it still has no live screenshot, external
  reference-image comparison, human recognizability proof, or visual-similarity
  score.
- No live desktop painting run is verified safe.
- Voice can produce receipts and route through chat, and a narrow Mona Lisa
  phrase can create mission state when transcribed, but the full voice ->
  mission -> automatic operator dispatch -> Orb loop is not complete.
- Local voice/text command routing can now move the live Orb left/right through
  the existing bounded overlay command path. A manual acoustic microphone test
  with the operator saying `hey Francis move left/right` is still not recorded
  as evidence, but the monitor now exposes a proof boundary that will not count
  API-injected text as acoustic evidence.
- The current ChatGPT voice connector control supports persistent HTTPS URL
  planning, environment URL handoff, URL recording, and a bounded Cloudflare
  named-tunnel start path. The current public MCP URL may still be an ephemeral
  LocalTunnel or quick Cloudflare fallback until an operator-owned stable
  hostname/config is supplied; local MCP can be listening while current ChatGPT
  app reachability still remains unproven by the status proof.
- When the connector readback reports a LocalTunnel fallback (`localtunnel_fallback_replace_needed`),
  treat it as live-test diagnostic ingress only; it must be replaced by
  persistent HTTPS `/mcp` ingress before Francis accepts it as stable connector
  truth.
- The current ChatGPT voice proof has no fresh usable public-MCP-tool-origin
  receipt in the default freshness window. A fresh ChatGPT app call that reaches
  `francis_chatgpt_voice_ingress` and writes the matching receipt provenance is
  required before the proof can treat the bridge as live.
- True backend model-call cancellation is not currently supported; stale reply
  suppression is the bounded behavior.

## Receipt And Artifact Locations

- `data/runtime/lens-overlay/status.json`
- `data/runtime/lens-overlay/voice-status.json`
- `data/runtime/lens-overlay/voice-turn-status.json`
- `data/runtime/lens-overlay/voice-turns/*.json`
- `data/runtime/lens-overlay/orb-position-command-request.json`
- `data/runtime/lens-overlay/orb-position-commands/*.json`
- `data/lens/mcp_perception/*.json`
- `data/sandbox_canvas/mona_lisa/*/operator_actions.jsonl`
- `data/sandbox_canvas/mona_lisa/*/manifest.json`
- `data/sandbox_canvas/mona_lisa/*/receipt.json`
- `data/sandbox_canvas/mona_lisa/*/mona_lisa_sandbox.svg`
- `data/sandbox_canvas/mona_lisa/*/mona_lisa_sandbox_preview.png`
- `data/sandbox_canvas/mona_lisa/*/evaluation_records/*.json`
- `data/sandbox_canvas/mona_lisa/*/review_queue/*.json`
- `data/sandbox_canvas/mona_lisa/*/improvement_proposals/*.json`
- `.francis/mcp_gateway/receipts/*.json`
- `data/missions/*/record.json`
- `data/missions/*/history.jsonl`
- `data/artifacts/`

## Repository State

- Branch: `main`
- Last observed head: `6ab747337418`
- Worktree: dirty before this checkpoint; preserve unrelated changes.

## Exact Next Action

With the live overlay running, have the operator say
`hey Francis move left` or `hey Francis move right`, then run
`powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lens-command-palette-monitor.ps1 -Mode Probe -EnableVoiceChecks -RequireManualAcousticOrbProof -TimeoutSeconds 5`
and confirm it exits `0` with
`voice_monitor.manual_acoustic_orb_position_proof.status=fresh_acoustic_orb_position_command_observed`.
If that proof passes, ledger it. If it remains ready or missing, inspect
`data/runtime/lens-overlay/voice-status.json` and
`data/runtime/lens-overlay/orb-position-commands/*.json` before changing code.
Trigger a fresh ChatGPT app call through the public
`francis_chatgpt_voice_ingress` MCP tool only after the acoustic Orb movement
proof is resolved. The public ChatGPT app MCP proof remains the next
external-connector proof after the acoustic Orb movement proof.
