# Orb Body Rebuild Phase 1 Audit

This note locks the body-only rebuild boundary before the renderer changes.

## Scope Locked

The rebuild is limited to the Orb body and live visual contract.

Keep intact:

* orb-first startup and shell ownership in `electron/main.js`
* orb-only chat/menu/no-overlap behavior in `services/hud/app/static/index.html`
* control, safety, ownership, policy, execution, perception, desktop-authority, and receipt seams
* signal production and state vocabulary unless a narrower body-only adjustment is required

Do not use the orb rebuild to rework runtime governance.

## Current Live Read Owners

### Renderer body stack

The current WebGL body is still composed as supporting layers around a bright center:

* `francis-orb/renderer/OrbScene.ts`
  * adds `aura -> shell -> filaments -> particles -> core`
  * applies root scale `1.32`
  * still builds ambient and point lights even though the orb is mostly emissive
* `francis-orb/renderer/OrbCore.ts`
  * large sphere geometry with additive blending
  * current shader alpha and intensity still let the core read as the main object
* `francis-orb/renderer/OrbShell.ts`
  * still instantiates a full sphere shell with non-zero opacity in every profile
  * still contributes refractive/fresnel body mass even when visually subtle
* `francis-orb/renderer/OrbAura.ts`
  * large sprite aura still adds haze across a wide radius
* `francis-orb/renderer/OrbFilaments.ts`
  * already carries the best part of the current design
  * uses explicit ribbon geometry, partial arc masking, three layers, and multi-axis motion
  * is still visually subordinate to the core/shell/aura stack
* `francis-orb/renderer/OrbParticles.ts`
  * count is already `0` in config, so it should stay demoted or disappear entirely

### DOM and wrapper styling

The renderer is not the only thing defining the orb:

* `services/hud/app/static/index.html`
  * `#orb-render-root::before` and `::after` still paint a pseudo-core and pseudo-halo
  * `#orb-render-root canvas` and state-specific selectors still apply contrast/saturation/brightness/drop-shadow shaping
  * wrapper state styling still materially changes the body read by state
* `electron/orb-shell.html`
  * `#orb-fallback` still paints a complete fake orb with rings and a core underneath the renderer
  * `#orb-render-root canvas` still applies drop-shadow/contrast/saturation styling
  * this shell still carries a second orb identity instead of letting the renderer own the look

## What Stays

These pieces stay and are retuned rather than removed:

* `francis-orb/renderer/OrbFilaments.ts`
  * keep the explicit arc/ribbon strategy
  * rebuild it as the primary visible form language
* `francis-orb/renderer/shaders/filament.vertex.glsl`
* `francis-orb/renderer/shaders/filament.fragment.glsl`
  * keep shader-driven depth shaping and translucency
  * retune for a tighter intelligence-knot silhouette
* `francis-orb/core/state-profiles.ts`
  * keep state vocabulary
  * retune later for the rebuilt body
* `francis-orb/integration/createFrancisOrb.ts`
* `francis-orb/renderer/FrancisOrbEngine.ts`
  * keep the mount and frame loop contract
  * do not let this rebuild sprawl into engine ownership changes

## What Gets Rebuilt

These are Phase 2 rebuild targets:

* `francis-orb/renderer/OrbFilaments.ts`
  * make filaments the silhouette
  * reduce outer spread and make arc composition tighter and more ghostlike
* `francis-orb/renderer/OrbCore.ts`
* `francis-orb/renderer/shaders/core.fragment.glsl`
  * shrink the visual read of the core so it becomes a supporting nucleus
  * remove blob-leading alpha and glow mass
* `francis-orb/renderer/OrbShell.ts`
  * reduce to near-nonexistent support layer or remove from the visible body stack if not needed
* `francis-orb/renderer/OrbScene.ts`
  * reorder or remove layers so the body is filament-first
  * strip lighting that only supports a sphere-first read
* `francis-orb/core/config.ts`
  * reduce footprint and spread
  * bias toward compact body geometry instead of larger shell/aura fields

## What Gets Demoted or Removed

These are not allowed to define the new body:

* visible shell silhouette from `OrbShell`
* wide haze mass from `OrbAura`
* particle clutter from `OrbParticles`
* pseudo-core and pseudo-halo ornament in `index.html`
* canvas filter stacks in `index.html` that reshape the body by state
* fake fallback rings/core in `orb-shell.html` once the real renderer is mounted

## Live Visual Contract After Rebuild

The target contract for later phases is:

* the renderer owns the orb identity
* wrappers own only sizing, placement, and pointer semantics
* fallback ornament exists only for renderer failure or pre-mount bootstrap
* body-state changes are expressed primarily inside the renderer, not by DOM pseudo-elements or filter stacks

## Phase Plan

### Phase 2

Rebuild the body composition so the orb reads as a compact filament-first intelligence knot.

### Phase 3

Strip live wrapper ornament so the mounted renderer is the look in both the HUD path and standalone orb shell.

### Phase 4

Retune state profiles for the new body so idle, attentive, investigate, lock, commit, act, and yield remain legible without reintroducing blob behavior.

### Phase 5

Rebuild `services/hud/app/static/orb/francis-orb.js`, update renderer contract tests, and prove the live mount path is using the new renderer-first contract.
