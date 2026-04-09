# Francis Desktop Overlay Shell

This shell wraps the existing Francis HUD served from `http://127.0.0.1:8767` in Electron so Francis can run as a desktop presence layer on Windows.

The shell now splits into two surfaces:

- a dedicated Orb window that lives on the desktop outside the HUD
- a separate Lens window that stays hidden until the Orb opens it

The current operator contract is:

- Orb: compact body plus strip only
- Lens: deeper diagnostics, receipts, runtime-health detail, and longer interaction
- no inline mini-console on the live orb window

## What It Does

- creates a transparent, frameless, always-on-top desktop Orb window
- lets the Orb move freely across the full virtual desktop workspace instead of confining it to a small shell or a single panel
- keeps the full Lens HUD in a separate hidden window until explicitly opened
- loads the existing localhost HUD instead of bundling a second renderer
- loads the desktop Orb from the HUD's orb-only surface instead of a separate standalone renderer
- exposes a small preload bridge at `window.FrancisDesktop`
- supports toggling click-through, always-on-top, Start At Login, display targeting, devtools, hide/show, and minimize
- persists a startup profile so boot posture can be explicit instead of inferred from the last shell state
- supports startup-at-login control from both the tray and the live HUD shell
- registers `Ctrl+Shift+Alt+F` as a global show/hide shortcut
- registers `Ctrl+Shift+Alt+C` as a global click-through toggle so pointer control is recoverable
- lets the live HUD consume those shell controls directly when running inside Electron
- keeps the Orb outside the HUD so normal desktop presence does not require the full operator surface to stay visible
- attaches a local active-surface perception feed to the Orb using the active display thumbnail, foreground-window metadata, and a focused crop around the cursor
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

That default launch path is intentionally clean and detached so the desktop Orb can appear without a separate black console host overlapping the work surface.

For a guard-railed dev launch:

- `npm run overlay:dev`
- `npm run overlay:start:console`

`overlay:dev` keeps the console-bound engineering path on purpose: it checks the HUD URL first and, if it is down, lets the Electron shell attempt managed HUD startup automatically.

## Package

- `npm run overlay:pack` builds an unpacked portable app directory for local verification and emits `electron/generated/build-signing.json`
- `npm run overlay:pack:signed` builds the unpacked portable app directory and fails unless the resulting executable is signed
- `npm run overlay:installer` builds a guided NSIS installer in `dist/overlay` and emits `electron/generated/build-signing.json`
- `npm run overlay:installer:signed` builds the NSIS installer and fails unless the resulting installer is signed
- `npm run overlay:dist` builds both the portable executable and the NSIS installer in `dist/overlay`, then emits `electron/generated/build-signing.json`
- `npm run overlay:dist:signed` builds both Windows artifacts and fails unless the packaged outputs are signed
- `npm run overlay:verify-signing` inspects the current packaged artifacts with the vendored `signtool.exe` verifier
- `npm run overlay:verify-signing:required` fails if the current packaged artifacts are not signed
- `npm run overlay:verify-signing:public` fails unless the current packaged artifacts are signed, match `FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME`, match `FRANCIS_WINDOWS_SIGNING_CHAIN_HINT`, and are not self-issued
- `npm run overlay:signing-doctor` reports whether the current machine is ready for machine-local signed packaging, public-trust release signing, or blocked on missing publisher-grade signer material, and emits exact PowerShell env suggestions for the viable local-store and Azure routes without echoing configured secret values into the terminal
- `npm run overlay:signing-doctor:public` fails fast when the current machine is not ready for public-trust release signing
- `npm run overlay:verify-windows-signing-env` verifies the repo-owned public Windows sign-hook inputs: `signtool.exe`, `Azure.CodeSigning.Dlib.dll`, `metadata.json`, `.NET 8`, and metadata/env alignment
- `npm run release:publish:windows` is the canonical internal beta Windows publish command: it runs the bounded hardening lane, auto-selects a safe machine-local signer when needed, writes relabeled artifacts to `dist/internal-beta/windows/current`, and emits tester metadata plus an install guide
- `npm run release:publish:windows:internal-beta` is an explicit alias for that same internal QA / tester-only lane
- `npm run overlay:dist:public` is the direct public-trust distribution build and now runs both the signing doctor and the Windows sign-env verifier before runtime staging or packaging
- `npm run release:publish:windows:public` is the public-trust Windows publish command: it runs the signing doctor preflight, the Windows sign-env verifier, then `release:hardening`, then `overlay:dist:public`
- `npm run release:publish:windows:public:local` loads an ignored local env file from `scripts/signing-public.local.ps1` if present, then runs the public-trust Windows publish command

The packaged shell includes the Francis HUD Python source under `resources/python-src` and will attempt to boot it locally when no HUD server is already running.
Before packaging, run `npm run overlay:prepare-runtime` or let `overlay:pack` / `overlay:dist` do it for you. That stages a bundled Python runtime under `dist/python-runtime-staging` and packages it as `resources/python-runtime`.
The first staging run can take a while because it copies the embedded runtime, stdlib, DLLs, and site-packages; the script now emits explicit progress so long Windows copies are visible instead of looking hung.
The packaging flow now uses `electron/builder-config.cjs` so supported signing routes are explicit: local certificate signing through `CSC_LINK` / `WIN_CSC_LINK` and `CSC_KEY_PASSWORD` / `WIN_CSC_KEY_PASSWORD`, Windows cert-store signing through `FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME` and optional `FRANCIS_WINDOWS_SIGNING_SHA1`, or Azure Artifact Signing through repo-owned direct `signtool.exe` invocation. The public hook lives at `build/sign/windows-sign.cjs`, uses `AZURE_SIGN_SIGNSDK_SIGNSTOOL`, `AZURE_SIGN_DLIB_PATH`, `AZURE_SIGN_METADATA_PATH`, and optional `AZURE_SIGN_TIMESTAMP_URL`, and signs the exact file Electron Builder passes in with `Azure.CodeSigning.Dlib.dll` plus `metadata.json`. `release:publish:windows` is the first-class internal beta lane for QA / tester-only distribution and emits labeled bundle metadata; `overlay:dist:public` and `release:publish:windows:public` now preflight with both the signing doctor and `overlay:verify-windows-signing-env` before Windows packaging work; `release:publish:windows:public` keeps the publisher-name, non-self-issued, and expected-chain gates for public-trust distribution; and `overlay:signing-doctor` still narrows the identity-side blocker to missing publisher hint, missing chain hint, self-issued-only certs, publisher mismatch, or absent public-trust signer material without printing configured secret values back into the console.
The repo now also includes `scripts/signing-public.example.ps1` plus an ignored `scripts/signing-public.local.ps1` pattern so public-release signer configuration can live in one local PowerShell file instead of ad hoc shell residue.
Placeholder values such as `<legal publisher name>` are treated as unset, so the ignored local signer file can exist safely before real publisher material is provisioned.
`release:publish:windows:public:local` now also fails in PowerShell before npm starts if that local bootstrap file is missing, still placeholder-valued, or does not yet contain one complete signing route with both a publisher hint and a chain hint.
The generated signing manifest and verifier output now also capture primary-chain metadata such as `rootSubject`, `rootIssuer`, and `chainSubjects`, so leaf-vs-root signer identity is inspectable during public-release review.
See [`docs/operations/WINDOWS_PUBLIC_SIGNING.md`](../docs/operations/WINDOWS_PUBLIC_SIGNING.md) for the exact Artifact Signing client-tool, metadata, `.NET 8`, and local verification contract.

## Assumptions

- Windows is the primary target.
- The HUD remains the source of truth and continues to run from localhost, even when Electron starts it.
- This shell is intentionally thin: it does not replace HUD state, transport, or rendering architecture.
- Managed HUD startup in a source checkout still uses the repo-local `.venv`.
- Managed HUD startup in packaged builds now prefers the bundled runtime staged from the build machine's base Python install plus the repo `.venv` dependencies.
- In a source checkout, managed HUD startup keeps using the repo-local `workspace/`; in a packaged build it redirects workspace state into Electron user data.

## Current Limitations

- Lens click-through is still a whole-window toggle, not pixel-perfect hit testing.
- The Orb window now defaults to pass-through and only becomes interactive over the Orb/menu region, but it still relies on Electron window-level mouse-event toggling rather than true pixel hit testing.
- If the HUD server is offline, Electron shows a fallback operator page instead of the real overlay.
- The shell stores preferences locally in `overlay-preferences.json`; use the HUD `Reset Layout` action if bounds, mode, or display targeting become undesirable.
- The shell also stores a small `overlay-session.json` continuity record so crash recovery can be surfaced on the next launch.
- Without any configured signer route, the Windows portable build remains unsigned. SmartScreen or local policy may require an explicit trust decision.
- Without any configured signer route, the NSIS installer remains unsigned. SmartScreen or local policy may require an explicit trust decision.
- A machine-local self-signed cert can satisfy `overlay:verify-signing:required` and the internal beta lane, but `overlay:verify-signing:public` and `release:publish:windows:public` are intended for real publisher identities and reject self-issued signers.
- Uninstall removes installed app files and shortcuts, but retained shell state under Electron user data is intentionally not deleted automatically.
- Packaging assumes the build machine can supply a valid base Python home. If that is not discoverable from `.venv/pyvenv.cfg`, set `FRANCIS_OVERLAY_PYTHON_HOME` before running the package scripts.
- SignPath inputs are surfaced for audit only. The current overlay packaging flow is wired to local certificate signing and Azure Trusted Signing, not SignPath.

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
- the Orb now carries a richer active-surface perception contract with freshness, retention posture, display/window metadata, and a cursor-local focus crop instead of only a generic desktop-attached banner
- the HUD can now surface exact decommission steps, retained paths, and generated cleanup commands before uninstall
- the HUD and tray can now export a governed support bundle with lifecycle, recovery, runtime, and display posture
- the HUD now surfaces build provenance for package inputs, package targets, and bundled runtime posture
- shell-state portability now carries compatibility metadata and blocks mismatched import channels instead of silently applying them
- the shell can now be packaged as both a portable artifact and an NSIS installer with the Orb icon and current shell controls intact
- the Orb now lives in its own desktop window while the Lens HUD opens separately in external-Orb mode, and the Orb window itself is backed by the HUD's orb-only surface so the renderer path stays canonical
- the shell now attaches live Orb perception locally by sampling the current cursor display and the foreground window title/process into the Orb surface
- the shell now owns a governed Orb authority queue, so Away-eligible mouse and keyboard commands can be claimed locally, receipted into the workspace, and executed only after the Orb crosses the idle gate
- the shell now keeps a canonical local authority spine so stop, pause, local stop, remote-sync status, and disconnected posture are renderer-visible without the orb guessing
- the shell now keeps a canonical runtime-health state machine for the orb lane: `nominal`, `degraded`, `disconnected`, and `recovering`
- the shell now keeps a canonical ownership model for the orb lane: `pass_through`, `interactable_orb`, `interactable_lens`, and `restricted`
- the live orb strip now derives its controls from canonical authority, runtime health, and ownership instead of renderer-local heuristics alone
- the live orb window now demotes the old inline console surface entirely; detail entry points reroute to Lens instead of reopening a hidden mini panel

## Next Extensions

- trim the staged runtime footprint now that the first bundled-runtime path exists
- configure signer material and publish signed Windows artifacts now that the distribution path fails closed
- add richer per-display policies if Francis eventually needs different overlay presence on different monitors
- add selective hit-testing only if the whole-window click-through toggle stops being sufficient
- keep a small manual orb-shell smoke on Windows for startup, Lens handoff, stop/pause truth, degraded posture, and blur/focus ownership recovery


