# Francis Desktop Overlay Shell

This shell wraps the existing Francis HUD served from `http://127.0.0.1:8767` in Electron so it can run as a transparent Windows desktop overlay.

## What It Does

- creates a transparent, frameless, always-on-top overlay window
- loads the existing localhost HUD instead of bundling a second renderer
- exposes a small preload bridge at `window.FrancisDesktop`
- supports toggling click-through, always-on-top, Start At Login, display targeting, devtools, hide/show, and minimize
- persists a startup profile so boot posture can be explicit instead of inferred from the last shell state
- supports startup-at-login control from both the tray and the live HUD shell
- registers `Ctrl+Shift+Alt+F` as a global show/hide shortcut
- registers `Ctrl+Shift+Alt+C` as a global click-through toggle so pointer control is recoverable
- lets the live HUD consume those shell controls directly when running inside Electron
- creates a tray control surface for show/hide, click-through, topmost, HUD restart, and quit
- persists overlay bounds, target display, always-on-top, and click-through state in the Electron user-data directory
- reflects the current launch-at-login state in the desktop shell lifecycle surface
- records build identity and lifecycle update posture so source checkouts and packaged builds are both inspectable
- surfaces retained-state migration posture so stale or unreadable shell schemas are visible before continuity is trusted
- surfaces degraded-mode posture so blocked runtime, migration, or update conditions become explicit instead of silently weakening trust
- persists an explicit motion-accessibility preference so reduced-motion posture is inspectable and operator-controlled
- persists explicit contrast and density accessibility preferences so long-session readability is operator-controlled instead of implicit
- records a local lifecycle history so update, rollback, portability, repair, and support actions remain inspectable
- surfaces provider posture so active model routing, fallback dependency, and privacy/runtime tradeoffs stay visible instead of hidden in environment residue
- surfaces authority posture so user, node, service, connector, and support authority stay distinguishable without exposing secret material
- surfaces signing posture so Windows packaging trust is inspectable before unsigned builds are treated as settled
- surfaces a guided repair path when updates, recovery, portability, or runtime checks leave the shell in an attention state
- surfaces explicit update-delivery posture so source, portable, and installer update paths are inspectable before the shell is treated as routine
- can repair retained shell state in place by normalizing legacy ledgers and quarantining unreadable ones before resetting only the affected files
- persists session continuity so unclean exits and managed HUD crashes surface as recovery state on the next launch
- supports guarded shell-state export and import so overlay posture can move machines without replaying authority
- enforces portability compatibility so shell-state imports are version-visible and can refuse mismatched channels
- exposes retained-state posture so uninstall and reinstall do not feel haunted
- surfaces first-run and reinstall diagnostics so runtime placement and writable roots are inspectable
- keeps rollback snapshots of shell state so updates, imports, and resets have a governed fallback path
- surfaces an explicit decommission plan so uninstall and reinstall are inspectable instead of haunted
- exports a governed support bundle so lifecycle, recovery, and runtime state can leave the shell as evidence
- records build provenance so packaged/runtime inputs are inspectable instead of implicit
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
- `npm run overlay:installer` builds a guided NSIS installer in `dist/overlay`
- `npm run overlay:dist` builds both the portable executable and the NSIS installer in `dist/overlay`

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
- The NSIS installer is also unsigned. SmartScreen or local policy may require an explicit trust decision until code signing is added.
- Uninstall removes installed app files and shortcuts, but retained shell state under Electron user data is intentionally not deleted automatically.
- Packaging assumes the build machine can supply a valid base Python home. If that is not discoverable from `.venv/pyvenv.cfg`, set `FRANCIS_OVERLAY_PYTHON_HOME` before running the package scripts.

## Current Operator Surface

- the HUD can move the overlay to any detected display and the choice persists across launches
- display topology changes are reconciled by the Electron shell so the overlay falls back cleanly if a monitor disappears
- the HUD can still refresh raw display topology for inspection when the desktop environment changes
- the HUD and tray can enable or disable launch-at-login without leaving the overlay surface
- the HUD and tray can persist startup profiles such as Operator Overlay, Quiet Overlay, and Core Services Only
- the shell exposes HUD runtime state and can restart the managed HUD from the desktop control surface
- the tray mirrors those same shell controls so recovery does not depend on the HUD remaining interactive
- the HUD can now inspect build/session lifecycle state and toggle Start At Login from the desktop shell surface
- the HUD can now inspect and acknowledge lifecycle update notices instead of treating build changes as silent mutation
- the HUD now surfaces a repair path with restart, rollback, support-bundle, and user-data actions when update posture degrades
- the HUD now surfaces migration discipline across retained shell files so schema drift and unreadable state stop being silent
- the HUD now surfaces explicit degraded-mode posture so restricted or review-first operation is visible to the operator
- the HUD now exposes accessibility posture for motion, contrast, density, keyboard recovery, and stress controls without leaving the overlay surface
- the HUD now surfaces recent lifecycle actions so shell updates, rollbacks, exports, imports, and repairs leave visible local history
- the HUD now surfaces model-provider posture so remote dependency and fallback narrowing are inspectable before execution is trusted
- the HUD now surfaces authority posture so connector credentials, support bindings, and secret-handling limits are inspectable without leaking raw values
- the HUD now surfaces signing posture so packaged distribution trust is explicit instead of being inferred from SmartScreen prompts
- the HUD now surfaces update-delivery posture so the safe path for source, portable, and installer updates is explicit
- the HUD and tray can now execute bounded retained-state repair instead of forcing a broad shell reset for every migration problem
- recovery now overrides startup posture safely, so unclean exits re-enter visible and interactive instead of hiding authority questions
- the HUD and tray can now export/import safe shell posture with explicit limits around login settings and live authority
- the HUD can now inspect retained shell surfaces and reset local shell residue without deleting workspace continuity
- the HUD can now inspect preflight diagnostics for runtime health, writable roots, startup support, and build posture
- the HUD and tray can now create and restore shell rollback snapshots without replaying live authority or workspace state
- the HUD can now surface exact decommission steps, retained paths, and generated cleanup commands before uninstall
- the HUD and tray can now export a governed support bundle with lifecycle, recovery, runtime, and display posture
- the HUD now surfaces build provenance for package inputs, package targets, and bundled runtime posture
- shell-state portability now carries compatibility metadata and blocks mismatched import channels instead of silently applying them
- the shell can now be packaged as both a portable artifact and an NSIS installer with the Orb icon and current shell controls intact

## Next Extensions

- trim the staged runtime footprint now that the first bundled-runtime path exists
- add Windows signing once the distribution path stabilizes
- add richer per-display policies if Francis eventually needs different overlay presence on different monitors
- add selective hit-testing only if the whole-window click-through toggle stops being sufficient


