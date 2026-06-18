# Francis Orb Visual Lock

This document records the current Orb face as canonical for the active Orb
continuum mandate. Behavior may be wired to substrate truth, but the rendered Orb
appearance is locked.

## Status

- Status: locked
- Locked as of: 2026-06-18
- Roadmap area: Phase 2, P1 interface, P7 execution posture, P9 observability
- Rule: build the body around the face; do not change the face

## Locked Visual Surface

The current Orb visual surface is formed by these files:

- `apps/chat_ui/src/lens/orbGlyph.ts`
- `apps/chat_ui/src/App.tsx`
- `scripts/lens-overlay-window.ps1`

These files are visually sensitive. They may be edited only when the rendered
Orb appearance remains unchanged and the change is narrowly isolated to behavior,
state wiring, status readback, receipts, or validation.

## Chat UI Inline Glyph

`apps/chat_ui/src/lens/orbGlyph.ts` is the read-only presenter used by the chat
UI body-state panel. The locked visual tokens are:

- core color: `#0b1220`
- ring color: `#dbe4f0`
- idle glow: `#cbd5e1`
- ready glow: `#eaf2ff`
- attention glow: `#fbe9cf`
- active glow: `#ffffff`

The inline glyph must remain a pure presenter. It must not perform network I/O,
grant execution authority, grant mutation authority, or invent Orb state.

## Desktop Overlay Orb

`scripts/lens-overlay-window.ps1` owns the current transparent desktop overlay
Orb renderer. The locked visual functions and constants include:

- `New-OrbVisualProjection`
- `New-OrbEnergySurface`
- `New-OrbTorusMesh`
- `New-OrbSphereMesh`
- `New-OrbEnergyMaterial`
- `Add-Orb3DEnergyRing`
- `Add-OrbEllipse`
- `New-OrbArgbColor`
- visual contract: `chat_ui.orbGlyph.energy_reference`
- renderer: `wpf_3d_animated_energy_orb`
- overlay route marker: `/?francis_lens=orb_overlay`
- default Orb surface size: `220`
- WPF transparent host: borderless window, transparent background, taskbar
  presence, topmost behavior
- 3D viewport: `Viewport3D`, `PerspectiveCamera`, camera z distance `3.2`,
  field of view `56`
- 3D ring count: `38`
- 2D fine orbit count: `56`
- 2D brighter orbit count: `12`
- outer glow size: `148 x 148`
- outer glow opacity: `0.38`
- outer glow blur radius: `16`
- core size: `64 x 64`
- hot center size: `34 x 34`
- ring material color family: silver/white values currently encoded in the
  renderer
- core and hot-center gradient stop values currently encoded in the renderer

The current renderer is transparent, 3D, animated, and frame-synced. It must not
be replaced with a new component, static image, SVG-only rewrite, black backdrop,
green tint, title bar, decorative chrome, or second overlay application.

## Behavior Surface

The following behavior may be wired or hardened without changing the visual
appearance:

- substrate state readback
- truthful semantic state mapping
- ambient motion, if bounded and non-interfering
- precision or task motion, if distinct from ambient drift
- cancellation and handback behavior
- receipts
- lens/overlay observation metadata
- voice input/output receipts
- operator planning and sandbox/live status

If a behavior change touches `scripts/lens-overlay-window.ps1`, it must avoid
changing the locked visual constants above unless a new explicit visual baseline
is approved by the operator.

## Existing Protection

- `apps/chat_ui/src/lens/orbGlyph.test.ts` asserts the inline glyph colors,
  readiness mapping, no network I/O, and no authority grant.
- `tests/test_lens_overlay_window_script.py` asserts the WPF overlay stays
  transparent, taskbar-visible, topmost, 3D, frame-synced, draggable, and bound
  to the current Lens MCP body-state routes.
- `tests/test_orb_phase0_contracts.py` asserts this manifest and the key locked
  renderer constants stay present.

## Prohibited Changes

Do not change the Orb:

- shape
- size
- scale
- color
- gradients
- opacity
- material
- texture
- glow
- halo
- rings
- blur
- shadows
- highlights
- particle/ring counts
- shader or WPF material appearance
- asset references
- visual proportions
- general visual personality

Do not add a visible debug frame, top bar, opaque background, fake state effect,
or standalone Orb demo path to production behavior.
