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
- `native/orb/native_orb_renderer.cpp`

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

`native/orb/native_orb_renderer.cpp` owns the current transparent desktop Orb
renderer. `scripts/lens-overlay-window.ps1` remains the lifecycle/control-plane
owner for start, stop, status, wake, voice, and bounded overlay controls. The
locked visual functions and constants include:

- `New-OrbVisualProjection`
- `New-NativeOrbControlSurface`
- `Set-NativeOrbRendererPosition`
- `Start-NativeOrbRenderer`
- `Stop-NativeOrbRenderer`
- `draw_pearlescent_liquid_blob`
- `draw_flow_streamer_field`
- `draw_glow_single_ring_field`
- visual contract: `native_cpp_orb.liquid_streamer_identity`
- renderer: `native_cpp_orb_renderer`
- overlay route marker: `/?francis_lens=orb_overlay`
- default native Orb surface size: `270`
- WPF transparent host: borderless window, transparent background, taskbar
  presence, topmost behavior, and native renderer lifecycle ownership
- native renderer: layered topmost click-through Win32/GDI+ window
- native movement bridge: bounded move-center message to the known renderer
  window only
- main streamer ring count: `15`
- fine streamer ring count: `5`
- single identity ring count: `20`
- rings follow the pearlescent blob flow
- single identity rings pulse independently
- render-only authority: no click, drag, typing, OS cursor control, network, or
  desktop mutation authority

The current renderer is transparent, animated, native C++, and render-only. It
must not be replaced with a static image, SVG-only rewrite, black backdrop,
green tint, title bar, decorative chrome, or authority-bearing desktop actor.

## Behavior Surface

The following behavior may be wired or hardened without changing the visual
appearance:

- substrate state readback
- truthful semantic state mapping
- docked operator presence as the default desktop posture
- ambient motion, only when explicitly enabled and bounded/non-interfering
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
- `tests/test_lens_overlay_window_script.py` asserts the WPF overlay host stays
  transparent, taskbar-visible, topmost, frame-synced, draggable, bound to the
  current Lens MCP body-state routes, and free of the removed WPF Orb visual
  renderer.
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
- shader or native Orb material appearance
- asset references
- visual proportions
- general visual personality

Do not add a visible debug frame, top bar, opaque background, fake state effect,
or standalone Orb demo path to production behavior.
