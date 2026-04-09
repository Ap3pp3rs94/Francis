# Orb Runtime Readiness

This note tracks the focused orb-shell remediation lane that made Francis orb-first by default, safer locally, and cleaner about Lens vs orb responsibilities.

## What Is Now True

- startup is orb-first; Lens is created lazily and opened intentionally
- the live orb surface is strip-first and compact
- the live orb window no longer owns an inline console path
- deeper diagnostics, receipts, and longer interaction route to Lens
- stop is local-first and remains truthful if remote sync fails
- pause is conservative and does not pretend to interrupt a live commit
- runtime health is explicit and proof-gated:
  - `nominal`
  - `degraded`
  - `disconnected`
  - `recovering`
- ownership is explicit and proof-gated:
  - `pass_through`
  - `interactable_orb`
  - `interactable_lens`
  - `restricted`

## Automated Verification

Recommended focused lane:

```powershell
node --test electron/startup-surface.test.cjs electron/orb-behavior.test.cjs electron/orb-motion.test.cjs electron/orb-surface-state.test.cjs electron/orb-surface-contract.test.cjs electron/orb-control-state.test.cjs electron/orb-ownership-state.test.cjs electron/orb-runtime-health.test.cjs electron/orb-panic.test.cjs electron/degraded-mode.test.cjs electron/orb-surface.test.cjs electron/orb-perception.test.cjs electron/foreground-window.test.cjs electron/windows-input.test.cjs electron/orb-authority.test.cjs electron/orb-plan.test.cjs
```

Renderer/Electron syntax checks:

```powershell
node --check electron/main.js
node --check electron/preload.js
node --check electron/orb-control-state.js
node --check electron/orb-runtime-health.js
node --check electron/orb-ownership-state.js
node --check services/hud/app/static/orb/orb-surface-state.js
```

Also run an inline-script syntax check against `services/hud/app/static/index.html` after shared-renderer edits.

## Manual Live-Smoke Checklist

These checks are still worth doing on a real Windows desktop shell:

- startup:
  - orb is the first visible surface
  - strip is present and compact
  - Lens does not auto-open
- local safety:
  - Stop drops local authority immediately
  - if remote sync fails, the strip still reports local stop truthfully
  - Pause clears queued authority work and refuses to fake interruption of a live commit
- runtime health:
  - degraded/disconnected/recovering posture appears cleanly
  - stale `cursor live` does not remain after authority loss
- ownership:
  - orb returns to safe pass-through after blur/focus loss
  - orb does not remain sticky-interactive after degraded/disconnected paths
  - recovery does not silently restore orb interactivity without proof
- Lens boundary:
  - Lens opens cleanly from the strip
  - deeper detail is reviewed there, not through an inline orb console

## Known Narrow Risks

- Electron still uses whole-window mouse-event toggling instead of true pixel hit testing.
- A real transparent-window smoke is still important on Windows because automated capture of the orb layer is limited.
- Elevated windows, secure desktop, exclusive fullscreen, and protected rendering paths remain real Windows limits and should degrade honestly.

## Readiness Claim

This orb lane is ready for broader integration work if:

- the focused automated lane stays green
- the manual Windows smoke above is clean
- no new orb-window code reintroduces inline console responsibility

If any of those fail, prefer holding the orb in the safer compact/Lens-routed posture over reopening panel-era behavior.
