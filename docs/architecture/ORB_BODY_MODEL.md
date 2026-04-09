# Orb Body Model

Francis now treats the Orb as the visible desktop body for Option A cursor authority, not as a decorative ambient widget.

## Runtime Surface

The live path is:

* [`electron/main.js`](../../electron/main.js): owns the Orb window, topmost posture, cursor authority handoff, and desktop execution.
* [`services/hud/app/static/index.html`](../../services/hud/app/static/index.html): owns the orb-only HUD renderer and live motion loop.
* [`services/hud/app/static/orb/orb-motion.js`](../../services/hud/app/static/orb/orb-motion.js): derives the Orb body intent for each animation frame.
* [`packages/francis_presence/francis_presence/orb.py`](../../packages/francis_presence/francis_presence/orb.py): emits the tunable motion law delivered to the shell.

## State Model

The Orb motion controller is explicit and human-legible. It now resolves one of these body states on every frame:

* `idle_anchored`: default perch near the active workspace edge or window boundary
* `attentive`: reduced drift while Francis is listening or waiting for the next bounded move
* `investigate`: short scouting arcs around candidate UI regions
* `target_lock`: damped, high-confidence focus over a likely target
* `commit_move`: direct travel to the real cursor execution point
* `hover_ready`: short dwell over a target before action
* `click_act`: fast compression pulse on click confirmation
* `drag_act`: tighter, forceful contact during drag
* `type_hold`: stable hold near insertion context during keyboard action
* `blocked_uncertain`: visible hesitation and recoil when confidence drops
* `waiting_for_user`: respectful side-anchor while user confirmation is required
* `abort_interrupted`: graceful retreat after handback or interruption

## Motion Law

The controller is built around three rules:

* idle motion is small and anchored, never center-screen wandering
* investigative motion is deliberate and curved, never random roaming
* commit states align to the real cursor target, including screen-edge controls and taskbar targets

The live tuning surface in the presence payload now exposes:

* anchor selection strategy
* idle amplitude
* hover dwell timing
* click pulse timing and scale
* lock, commit, hover, drag, and abort stiffness
* idle/commit/hover damping
* taskbar-safe margins

## Trust Contract

The Orb body is not allowed to imply action that the real cursor is not taking.

* commit states resolve toward the actual execution point
* hover and click states only appear when the body is at or near the real target
* blocked and waiting states retreat from dangerous controls instead of camping on them
* handback remains spatial and visible instead of disappearing into a jump cut
