# Francis Desktop Overlay Shell

This shell wraps the existing Francis HUD served from `http://127.0.0.1:8767` in Electron so it can run as a transparent Windows desktop overlay.

## What It Does

- creates a transparent, frameless, always-on-top overlay window
- loads the existing localhost HUD instead of bundling a second renderer
- exposes a small preload bridge at `window.FrancisDesktop`
- supports toggling click-through, always-on-top, display targeting, devtools, hide/show, and minimize
- registers `Ctrl+Shift+Alt+F` as a global show/hide shortcut
- registers `Ctrl+Shift+Alt+C` as a global click-through toggle so pointer control is recoverable
- lets the live HUD consume those shell controls directly when running inside Electron
- persists overlay bounds, target display, always-on-top, and click-through state in the Electron user-data directory
- reuses an already-running HUD if one exists, otherwise attempts to start the local HUD server automatically

## Run

1. Start the Francis HUD server so `http://127.0.0.1:8767` is reachable.
2. Install the shell dependency from the repo root:
   - `npm install`
3. Launch the overlay:
   - `npm run overlay:start`

For a guard-railed dev launch:

- `npm run overlay:dev`

That PowerShell helper checks the HUD URL first and, if it is down, lets the Electron shell attempt managed HUD startup automatically.

## Package

- `npm run overlay:pack` builds an unpacked portable app directory for local verification
- `npm run overlay:dist` builds the portable Windows executable in `dist/overlay`

The packaged shell includes the Francis HUD Python source under `resources/python-src` and will attempt to boot it locally when no HUD server is already running.

## Assumptions

- Windows is the primary target.
- The HUD remains the source of truth and continues to run from localhost, even when Electron starts it.
- This shell is intentionally thin: it does not replace HUD state, transport, or rendering architecture.
- Managed HUD startup needs a usable local Python runtime with the Francis Python dependencies available.
- In a source checkout, managed HUD startup keeps using the repo-local `workspace/`; in a packaged build it redirects workspace state into Electron user data.

## Current Limitations

- Click-through is a whole-window toggle, not pixel-perfect hit testing.
- Click-through should be treated as an operator mode change: once enabled, use the global shortcut to recover pointer control.
- If the HUD server is offline, Electron shows a fallback operator page instead of the real overlay.
- The shell stores preferences locally in `overlay-preferences.json`; use the HUD `Reset Layout` action if bounds, mode, or display targeting become undesirable.
- The Windows portable build is unsigned. SmartScreen or local policy may require an explicit trust decision until code signing is added.
- The shell can ship the HUD source, but it does not yet bundle its own Python interpreter or wheel cache.

## Current Operator Surface

- the HUD can move the overlay to any detected display and the choice persists across launches
- display topology changes are reconciled by the Electron shell so the overlay falls back cleanly if a monitor disappears
- the HUD can still refresh raw display topology for inspection when the desktop environment changes
- the shell exposes HUD runtime state and can restart the managed HUD from the desktop control surface
- the shell can now be packaged into a portable Windows artifact with the Orb icon and current shell controls intact

## Next Extensions

- bundle or provision the Python runtime so managed HUD startup works on machines without a preinstalled Francis Python environment
- add Windows signing once the distribution path stabilizes
- add richer per-display policies if Francis eventually needs different overlay presence on different monitors
- add selective hit-testing only if the whole-window click-through toggle stops being sufficient
