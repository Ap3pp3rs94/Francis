# Francis Desktop Overlay Shell

This shell wraps the existing Francis HUD served from `http://127.0.0.1:8767` in Electron so it can run as a transparent Windows desktop overlay.

## What It Does

- creates a transparent, frameless, always-on-top overlay window
- loads the existing localhost HUD instead of bundling a second renderer
- exposes a small preload bridge at `window.FrancisDesktop`
- supports toggling click-through, always-on-top, devtools, hide/show, and minimize
- registers `Ctrl+Shift+Alt+F` as a global show/hide shortcut
- registers `Ctrl+Shift+Alt+C` as a global click-through toggle so pointer control is recoverable
- lets the live HUD consume those shell controls directly when running inside Electron
- persists overlay bounds, always-on-top, and click-through state in the Electron user-data directory

## Run

1. Start the Francis HUD server so `http://127.0.0.1:8767` is reachable.
2. Install the shell dependency from the repo root:
   - `npm install`
3. Launch the overlay:
   - `npm run overlay:start`

For a guard-railed dev launch:

- `npm run overlay:dev`

That PowerShell helper checks the HUD URL first and stops with a clear message if the server is down.

## Assumptions

- Windows is the primary target.
- The HUD remains the source of truth and continues to run from localhost.
- This shell is intentionally thin: it does not replace HUD state, transport, or rendering architecture.

## Current Limitations

- Click-through is a whole-window toggle, not pixel-perfect hit testing.
- Click-through should be treated as an operator mode change: once enabled, use the global shortcut to recover pointer control.
- If the HUD server is offline, Electron shows a fallback operator page instead of the real overlay.
- The shell stores preferences locally in `overlay-preferences.json`; use the HUD `Reset Layout` action if bounds or mode become undesirable.

## Next Extensions

- wire HUD controls to `window.FrancisDesktop`
- add persisted overlay preferences for click-through and window bounds
- add multi-display targeting and per-display overlay placement
- add packaged Windows distribution once the shell behavior settles
