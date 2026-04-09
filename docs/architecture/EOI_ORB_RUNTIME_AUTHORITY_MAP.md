# EOI / Orb Runtime Authority Map

This note is the Section 1 handoff for the Francis master build prompt.

## Live EOI Spine

### Boot spine

1. `npm run overlay:start` launches the clean orb-first Electron shell from the repo root without a competing console host.
2. [electron/main.js](/D:/francis/electron/main.js) is the live desktop-shell entrypoint.
3. [electron/hud-runtime.js](/D:/francis/electron/hud-runtime.js) owns managed HUD boot, health probing, and reconnect semantics.
4. [services/hud/app/run_hud.py](/D:/francis/services/hud/app/run_hud.py) starts the local Uvicorn HUD server.
5. [services/hud/app/main.py](/D:/francis/services/hud/app/main.py) serves the shared HUD/orb renderer and the orb APIs.
6. [services/hud/app/static/index.html](/D:/francis/services/hud/app/static/index.html) is the live renderer for both the orb-only surface and the Lens surface.

### Window and surface hierarchy

- Orb window owner: [electron/main.js](/D:/francis/electron/main.js)
  - `createOrbWindow()`
  - `getOrbHudUrl()`
  - `showOrbWindow()`
- Orb window geometry/topmost owner: [electron/orb-surface.js](/D:/francis/electron/orb-surface.js)
- Lens window owner: [electron/main.js](/D:/francis/electron/main.js)
  - `createMainWindow()`
  - `getLensHudUrl()`
  - `showLensWindow()`
  - `hideLensWindow()`
- Startup hierarchy owner: [electron/startup-surface.js](/D:/francis/electron/startup-surface.js)
  - current law is `bootOrbWindow: true`
  - current law is `bootLensWindow: false`
  - Lens bootstrap is explicit, not default

### Orb-only renderer ownership

- Orb-only mode selector: [services/hud/app/static/index.html](/D:/francis/services/hud/app/static/index.html)
  - `orb=window`
  - `view=orb_only`
  - `orbWindowMode`
- Orb render bundle loaded at runtime:
  - [services/hud/app/static/orb/francis-orb.js](/D:/francis/services/hud/app/static/orb/francis-orb.js)
  - [services/hud/app/static/orb/orb-motion.js](/D:/francis/services/hud/app/static/orb/orb-motion.js)
  - [services/hud/app/static/orb/orb-surface-state.js](/D:/francis/services/hud/app/static/orb/orb-surface-state.js)

### Preload and bridge spine

- Renderer bridge owner: [electron/preload.js](/D:/francis/electron/preload.js)
  - exposes `window.FrancisDesktop`
- IPC authority owner: [electron/main.js](/D:/francis/electron/main.js)
  - `registerIpc()`
  - local shell state
  - show/hide
  - Lens open/close
  - panic/stop
  - desktop execution

## Ownership Map

### Orb runtime startup

- Authoritative files:
  - [electron/main.js](/D:/francis/electron/main.js)
  - [electron/hud-runtime.js](/D:/francis/electron/hud-runtime.js)
  - [services/hud/app/run_hud.py](/D:/francis/services/hud/app/run_hud.py)
  - [services/hud/app/main.py](/D:/francis/services/hud/app/main.py)
- Runtime truth:
  - Electron owns process boot, single-instance behavior, window creation, local authority loops, and managed HUD lifecycle.
  - The HUD server owns the HTTP surface the orb and Lens actually render.

### Orb window creation

- Authoritative files:
  - [electron/main.js](/D:/francis/electron/main.js)
  - [electron/orb-surface.js](/D:/francis/electron/orb-surface.js)
- Runtime truth:
  - Orb is a separate transparent Electron window over the full virtual desktop.
  - The orb renderer is not a standalone HTML file; it is the HUD-served `index.html` in orb-only mode.

### Orb-only renderer ownership

- Authoritative files:
  - [services/hud/app/static/index.html](/D:/francis/services/hud/app/static/index.html)
  - [services/hud/app/static/orb/orb-motion.js](/D:/francis/services/hud/app/static/orb/orb-motion.js)
  - [services/hud/app/static/orb/orb-surface-state.js](/D:/francis/services/hud/app/static/orb/orb-surface-state.js)
  - [services/hud/app/static/orb/francis-orb.js](/D:/francis/services/hud/app/static/orb/francis-orb.js)
- Runtime truth:
  - `index.html` owns orb-vs-Lens mode gating and the live orb shell behavior.
  - `orb-motion.js` owns the explicit orb body states and motion semantics.
  - `orb-surface-state.js` owns compact orb state labels and renderer-facing surface derivation.
  - `francis-orb.js` is the live compiled visual engine loaded by the renderer.

### Lens/HUD creation and visibility

- Authoritative files:
  - [electron/main.js](/D:/francis/electron/main.js)
  - [services/hud/app/main.py](/D:/francis/services/hud/app/main.py)
  - [services/hud/app/static/index.html](/D:/francis/services/hud/app/static/index.html)
- Runtime truth:
  - Electron decides when the Lens window exists and whether it is visible.
  - The HUD server serves the same root renderer for Lens and orb-only views.
  - Lens is secondary by window construction, not just by styling.

### Startup profile handling

- Authoritative file:
  - [electron/startup-profile.js](/D:/francis/electron/startup-profile.js)
- Runtime truth:
  - Startup posture is explicit and normalized here.
  - Recovery-safe posture is forced here, not inferred in the renderer.

### Startup preference handling

- Authoritative file:
  - [electron/preferences.js](/D:/francis/electron/preferences.js)
- Runtime truth:
  - Persisted startup profile, orb behavior mode, display target, contrast, density, and motion posture all normalize here.
  - Saved preferences feed both startup posture and runtime shell behavior.

### Orb control bridge

- Authoritative files:
  - [electron/preload.js](/D:/francis/electron/preload.js)
  - [electron/main.js](/D:/francis/electron/main.js)
- Runtime truth:
  - The renderer never owns shell authority directly.
  - The renderer asks through `window.FrancisDesktop`; Electron decides.

### Orb state / update flow

- Authoritative files:
  - [services/hud/app/orb.py](/D:/francis/services/hud/app/orb.py)
  - [packages/francis_presence/francis_presence/orb.py](/D:/francis/packages/francis_presence/francis_presence/orb.py)
  - [services/orchestrator/app/orb_authority.py](/D:/francis/services/orchestrator/app/orb_authority.py)
  - [services/orchestrator/app/orb_perception.py](/D:/francis/services/orchestrator/app/orb_perception.py)
  - [services/hud/app/static/index.html](/D:/francis/services/hud/app/static/index.html)
  - [services/hud/app/static/orb/orb-surface-state.js](/D:/francis/services/hud/app/static/orb/orb-surface-state.js)
- Runtime truth:
  - `orb.py` composes the orb payload seen by the renderer.
  - `packages/francis_presence/.../orb.py` shapes the orb identity, posture, and movement profile payload.
  - `orb_authority.py` owns queued authority commands and authority state receipts.
  - `orb_perception.py` owns target/perception normalization and focus-target contracts.
  - `index.html` merges shell state, orb payload, authority, and perception into the live surface.

### Orb-native controller ownership

- Authoritative live files:
  - [services/hud/app/static/orb/orb-motion.js](/D:/francis/services/hud/app/static/orb/orb-motion.js)
  - [services/hud/app/static/orb/francis-orb.js](/D:/francis/services/hud/app/static/orb/francis-orb.js)
  - [services/hud/app/static/index.html](/D:/francis/services/hud/app/static/index.html)
- Build-source files behind the bundle:
  - [francis-orb/control/OrbStateController.ts](/D:/francis/francis-orb/control/OrbStateController.ts)
  - [francis-orb/control/OrbAttentionController.ts](/D:/francis/francis-orb/control/OrbAttentionController.ts)
  - [francis-orb/control/OrbActionController.ts](/D:/francis/francis-orb/control/OrbActionController.ts)
  - [francis-orb/control/OrbTransitionController.ts](/D:/francis/francis-orb/control/OrbTransitionController.ts)
  - [francis-orb/renderer/FrancisOrbEngine.ts](/D:/francis/francis-orb/renderer/FrancisOrbEngine.ts)
- Runtime truth:
  - Live startup uses the compiled bundle under `services/hud/app/static/orb/`.
  - Durable controller changes should be made in `francis-orb/` source and then rebuilt into the static bundle.

### Orb-native policy ownership

- Local shell policy and safety:
  - [electron/orb-control-state.js](/D:/francis/electron/orb-control-state.js)
  - [electron/orb-ownership-state.js](/D:/francis/electron/orb-ownership-state.js)
  - [electron/orb-runtime-health.js](/D:/francis/electron/orb-runtime-health.js)
  - [electron/orb-panic.js](/D:/francis/electron/orb-panic.js)
- Server-side authority and approval gating:
  - [services/orchestrator/app/orb_authority.py](/D:/francis/services/orchestrator/app/orb_authority.py)
  - [services/orchestrator/app/lens_operator.py](/D:/francis/services/orchestrator/app/lens_operator.py)
  - [services/hud/app/orb.py](/D:/francis/services/hud/app/orb.py)
- Build-source renderer interjection policy:
  - [francis-orb/policy/InterjectionPolicy.ts](/D:/francis/francis-orb/policy/InterjectionPolicy.ts)
- Runtime truth:
  - Local shell policy decides whether the orb may claim interaction right now.
  - Orchestrator-side policy decides what commands/approvals exist and how they are receipted.
  - Renderer interjection policy exists, but only through the compiled orb bundle.

### Orb-native integration ownership

- Local desktop execution:
  - [electron/orb-plan.js](/D:/francis/electron/orb-plan.js)
  - [electron/windows-input.js](/D:/francis/electron/windows-input.js)
- Local capture/perception helpers:
  - [electron/orb-perception.js](/D:/francis/electron/orb-perception.js)
  - [electron/main.js](/D:/francis/electron/main.js)
- HUD/orchestrator integration:
  - [services/orchestrator/app/orb_perception.py](/D:/francis/services/orchestrator/app/orb_perception.py)
  - [services/hud/app/orchestrator_bridge.py](/D:/francis/services/hud/app/orchestrator_bridge.py)
  - [services/orchestrator/app/lens_operator.py](/D:/francis/services/orchestrator/app/lens_operator.py)
- Build-source signal mapping:
  - [francis-orb/integration/createFrancisOrb.ts](/D:/francis/francis-orb/integration/createFrancisOrb.ts)
  - [francis-orb/integration/signal-mapping.ts](/D:/francis/francis-orb/integration/signal-mapping.ts)
- Runtime truth:
  - Electron owns direct desktop actuation and local capture.
  - The HUD/orchestrator side owns perceptual contracts, action chips, and Lens-to-orchestrator bridging.

## Exact Runtime Ownership Summary

- EOI shell authority lives in [electron/main.js](/D:/francis/electron/main.js).
- Managed HUD process authority lives in [electron/hud-runtime.js](/D:/francis/electron/hud-runtime.js).
- Orb visual identity payload lives in [services/hud/app/orb.py](/D:/francis/services/hud/app/orb.py) plus [packages/francis_presence/francis_presence/orb.py](/D:/francis/packages/francis_presence/francis_presence/orb.py).
- Orb renderer semantics live in [services/hud/app/static/index.html](/D:/francis/services/hud/app/static/index.html) plus the live static orb assets under [services/hud/app/static/orb](/D:/francis/services/hud/app/static/orb).
- Local interaction safety and ownership live in the Electron `orb-*` modules, especially [electron/orb-ownership-state.js](/D:/francis/electron/orb-ownership-state.js), [electron/orb-control-state.js](/D:/francis/electron/orb-control-state.js), and [electron/orb-runtime-health.js](/D:/francis/electron/orb-runtime-health.js).
- Authority queue truth and receipts live in [services/orchestrator/app/orb_authority.py](/D:/francis/services/orchestrator/app/orb_authority.py).
- Perception/target truth lives in [services/orchestrator/app/orb_perception.py](/D:/francis/services/orchestrator/app/orb_perception.py).

## Non-Authoritative or Adjacent Surfaces

- [electron/orb-shell.html](/D:/francis/electron/orb-shell.html)
  - adjacent/manual smoke surface
  - not created by the live Electron boot path
- [francis-orb/integration/example-app.ts](/D:/francis/francis-orb/integration/example-app.ts)
  - example only
  - not part of the live desktop shell
- [services/hud/app/views](/D:/francis/services/hud/app/views)
  - live Lens content
  - not the orb startup spine
  - not the orb state-machine owner
- [electron/README-overlay.md](/D:/francis/electron/README-overlay.md)
  - descriptive only
  - not runtime truth
- tests and docs
  - useful guardrails
  - not runtime authority

## Shared-Surface Warnings

- [electron/main.js](/D:/francis/electron/main.js) is a shared authority choke point.
  - startup
  - IPC
  - local safety
  - orb visibility
  - Lens visibility
  - perception loop
  - authority loop
- [services/hud/app/static/index.html](/D:/francis/services/hud/app/static/index.html) is a shared renderer for:
  - orb-only desktop body
  - external-orb Lens posture
  - the broader Lens shell
- [services/hud/app/static/orb/francis-orb.js](/D:/francis/services/hud/app/static/orb/francis-orb.js) is the live runtime artifact, but its durable source lives under [francis-orb](/D:/francis/francis-orb).
- [services/hud/app/orb.py](/D:/francis/services/hud/app/orb.py) is a composition surface.
  - changing perception, authority, approvals, receipts, or voice upstream changes the live orb payload here.

## Highest-Value Future Change Points

### Section 2: Orb-first startup as law

- [electron/main.js](/D:/francis/electron/main.js)
- [electron/startup-surface.js](/D:/francis/electron/startup-surface.js)
- [electron/startup-profile.js](/D:/francis/electron/startup-profile.js)
- [electron/preferences.js](/D:/francis/electron/preferences.js)

### Section 3: Compact default orb surface

- [services/hud/app/static/index.html](/D:/francis/services/hud/app/static/index.html)
- [services/hud/app/static/orb/orb-surface-state.js](/D:/francis/services/hud/app/static/orb/orb-surface-state.js)
- [services/hud/app/orb.py](/D:/francis/services/hud/app/orb.py)

### Section 4: Orb-native state / transition hardening

- [services/hud/app/static/orb/orb-motion.js](/D:/francis/services/hud/app/static/orb/orb-motion.js)
- [services/hud/app/static/index.html](/D:/francis/services/hud/app/static/index.html)
- [packages/francis_presence/francis_presence/orb.py](/D:/francis/packages/francis_presence/francis_presence/orb.py)
- [francis-orb/control](/D:/francis/francis-orb/control)

### Section 5: Local-first safety / panic / authority drop

- [electron/main.js](/D:/francis/electron/main.js)
- [electron/orb-panic.js](/D:/francis/electron/orb-panic.js)
- [electron/orb-control-state.js](/D:/francis/electron/orb-control-state.js)
- [services/orchestrator/app/orb_authority.py](/D:/francis/services/orchestrator/app/orb_authority.py)

### Section 6: HUD outage containment / degraded mode

- [electron/main.js](/D:/francis/electron/main.js)
- [electron/orb-runtime-health.js](/D:/francis/electron/orb-runtime-health.js)
- [electron/hud-runtime.js](/D:/francis/electron/hud-runtime.js)
- [services/hud/app/static/index.html](/D:/francis/services/hud/app/static/index.html)
- [services/hud/app/static/orb/orb-surface-state.js](/D:/francis/services/hud/app/static/orb/orb-surface-state.js)

### Section 7: Input ownership / pass-through governor

- [electron/orb-ownership-state.js](/D:/francis/electron/orb-ownership-state.js)
- [electron/main.js](/D:/francis/electron/main.js)
- [services/hud/app/static/index.html](/D:/francis/services/hud/app/static/index.html)

### Section 8: Attention engine / targeting legibility

- [services/orchestrator/app/orb_perception.py](/D:/francis/services/orchestrator/app/orb_perception.py)
- [services/hud/app/orb.py](/D:/francis/services/hud/app/orb.py)
- [services/hud/app/static/index.html](/D:/francis/services/hud/app/static/index.html)
- [francis-orb/control/OrbAttentionController.ts](/D:/francis/francis-orb/control/OrbAttentionController.ts)

### Section 9: Action engine / execution body integration

- [electron/orb-plan.js](/D:/francis/electron/orb-plan.js)
- [electron/windows-input.js](/D:/francis/electron/windows-input.js)
- [services/orchestrator/app/orb_authority.py](/D:/francis/services/orchestrator/app/orb_authority.py)
- [services/hud/app/static/orb/orb-motion.js](/D:/francis/services/hud/app/static/orb/orb-motion.js)

### Section 10: Policy-governed autonomy

- [services/orchestrator/app/lens_operator.py](/D:/francis/services/orchestrator/app/lens_operator.py)
- [services/orchestrator/app/orb_authority.py](/D:/francis/services/orchestrator/app/orb_authority.py)
- [services/hud/app/orb.py](/D:/francis/services/hud/app/orb.py)
- [francis-orb/policy/InterjectionPolicy.ts](/D:/francis/francis-orb/policy/InterjectionPolicy.ts)

### Section 11: Perception stack / environmental embodiment

- [electron/main.js](/D:/francis/electron/main.js)
- [electron/orb-perception.js](/D:/francis/electron/orb-perception.js)
- [services/orchestrator/app/orb_perception.py](/D:/francis/services/orchestrator/app/orb_perception.py)

### Section 12: Desktop-native power

- [electron/main.js](/D:/francis/electron/main.js)
- [electron/orb-surface.js](/D:/francis/electron/orb-surface.js)
- [electron/windows-input.js](/D:/francis/electron/windows-input.js)

### Section 13: Receipts / trust / replayability

- [services/orchestrator/app/orb_authority.py](/D:/francis/services/orchestrator/app/orb_authority.py)
- [services/hud/app/orb_memory.py](/D:/francis/services/hud/app/orb_memory.py)
- [services/hud/app/orb.py](/D:/francis/services/hud/app/orb.py)
- [services/hud/app/views/execution_journal.py](/D:/francis/services/hud/app/views/execution_journal.py)

### Section 14: Lens/HUD demotion and support-role cleanup

- [electron/main.js](/D:/francis/electron/main.js)
- [services/hud/app/static/index.html](/D:/francis/services/hud/app/static/index.html)
- [services/hud/app/views](/D:/francis/services/hud/app/views)

### Section 15: Hardening / tests / notes / backend boundary

- [docs/architecture](/D:/francis/docs/architecture)
- [electron/*.test.cjs](/D:/francis/electron)
- [tests/unit](/D:/francis/tests/unit)

## Final Hardening Closure

- Canonical runtime note:
  - [EOI Runtime Model And Future Backend Boundary](./EOI_RUNTIME_MODEL_AND_BACKEND_BOUNDARY.md)
- This map remains the exact ownership index.
- The runtime-model note is the concise architectural defense against future drift.
