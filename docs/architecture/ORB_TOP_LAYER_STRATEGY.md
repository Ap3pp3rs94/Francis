# Orb Top-Layer Strategy

Francis uses the strongest stable Windows posture available for a transparent desktop body, then degrades honestly where the compositor or integrity model prevents universal topmost behavior.

## Current Strategy

The live shell posture is implemented in:

* [`electron/main.js`](../../electron/main.js)
* [`electron/orb-surface.js`](../../electron/orb-surface.js)
* [`electron/orb-plan.js`](../../electron/orb-plan.js)

The Orb window is:

* a separate transparent BrowserWindow
* sized to full display bounds, not just work area, so it can inhabit the taskbar band
* pinned with Electron's `screen-saver` topmost level
* reinforced with `moveTop()` where available
* marked visible across workspaces with fullscreen visibility enabled
* kept responsive with background throttling disabled

## Taskbar Strategy

Taskbar interaction is a first-class target, not a clipping bug.

* the Orb window spans full display bounds so the shell does not trim the taskbar band away
* commit states are allowed to align with edge and taskbar targets instead of being clamped back into the work area
* idle and waiting states still perch inside safe workspace bounds so the Orb stays out of the user's way when not acting
* taskbar anchors such as Start and Show Desktop remain available through the desktop plan layer in [`electron/orb-plan.js`](../../electron/orb-plan.js)

## Stable Limits On Windows

The shell can stay above normal windows and most borderless surfaces, but not literally everything.

Known limits:

* elevated windows can outrank a non-elevated Electron process
* the secure desktop used by UAC prompts is not a normal composited surface and cannot be overlaid safely
* exclusive fullscreen games can bypass the desktop compositor entirely
* anti-cheat or protected rendering paths may block or suppress overlays
* capture-mode or degraded overlay posture may intentionally suspend the Orb for stability

Francis should not fake dominance in those cases. The shell should:

* keep the strongest safe topmost posture on normal desktop surfaces
* detect degraded or suspended overlay posture when possible
* remain honest about exclusive-fullscreen and protected-surface limits
* prefer stability and trust over compositor hacks that make the desktop unreliable
