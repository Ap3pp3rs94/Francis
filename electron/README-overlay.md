# Francis Desktop Overlay Shell

This shell wraps the existing Francis HUD served from `http://127.0.0.1:8767` in Electron so it can run as a transparent Windows desktop overlay.

## What It Does

- creates a transparent, frameless, always-on-top overlay window
- loads the existing localhost HUD instead of bundling a second renderer
- exposes a small preload bridge at `window.FrancisDesktop`
- supports toggling click-through, always-on-top, Start At Login, display targeting, devtools, hide/show, and minimize
- supports startup-at-login control from both the tray and the live HUD shell
- registers `Ctrl+Shift+Alt+F` as a global show/hide shortcut
- registers `Ctrl+Shift+Alt+C` as a global click-through toggle so pointer control is recoverable
- lets the live HUD consume those shell controls directly when running inside Electron
- creates a tray control surface for show/hide, click-through, topmost, HUD restart, and quit
- persists overlay bounds, target display, always-on-top, and click-through state in the Electron user-data directory
- reflects the current launch-at-login state in the desktop shell lifecycle surface
- persists session continuity so unclean exits and managed HUD crashes surface as recovery state on the next launch
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
Before packaging, run `npm run overlay:prepare-runtime` or let `overlay:pack` / `overlay:dist` do it for you. That stages a bundled Python runtime under `dist/python-runtime-staging` and packages it as `resources/python-runtime`.

## Assumptions

- Windows is the primary target.
- The HUD remains the source of truth and continues to run from localhost, even when Electron starts it.
- This shell is intentionally thin: it does not replace HUD state, transport, or rendering architecture.
- Managed HUD startup in a source checkout still uses the repo-local `.venv`.
- Managed HUD startup in packaged builds now prefers the bundled runtime staged from the build machine's base Python install plus the repo `.venv` dependencies.
- In a source checkout, managed HUD startup keeps using the repo-local `workspace/`; in a packaged build it redirects workspace state into Electron user data.

## Current Limitations

- Click-through is a whole-window toggle, not pixel-perfect hit testing.
- Click-through should be treated as an operator mode change: once enabled, use the global shortcut to recover pointer control.
- If the HUD server is offline, Electron shows a fallback operator page instead of the real overlay.
- The shell stores preferences locally in `overlay-preferences.json`; use the HUD `Reset Layout` action if bounds, mode, or display targeting become undesirable.
- The shell also stores a small `overlay-session.json` continuity record so crash recovery can be surfaced on the next launch.
- The Windows portable build is unsigned. SmartScreen or local policy may require an explicit trust decision until code signing is added.
- Packaging assumes the build machine can supply a valid base Python home. If that is not discoverable from `.venv/pyvenv.cfg`, set `FRANCIS_OVERLAY_PYTHON_HOME` before running the package scripts.

## Current Operator Surface

- the HUD can move the overlay to any detected display and the choice persists across launches
- display topology changes are reconciled by the Electron shell so the overlay falls back cleanly if a monitor disappears
- the HUD can still refresh raw display topology for inspection when the desktop environment changes
- the HUD and tray can enable or disable launch-at-login without leaving the overlay surface
- the shell exposes HUD runtime state and can restart the managed HUD from the desktop control surface
- the tray mirrors those same shell controls so recovery does not depend on the HUD remaining interactive
- the HUD can now inspect build/session lifecycle state and toggle Start At Login from the desktop shell surface
- the shell can now be packaged into a portable Windows artifact with the Orb icon and current shell controls intact

## Next Extensions

- trim the staged runtime footprint now that the first bundled-runtime path exists
- add Windows signing once the distribution path stabilizes
- add richer per-display policies if Francis eventually needs different overlay presence on different monitors
- add selective hit-testing only if the whole-window click-through toggle stops being sufficient


